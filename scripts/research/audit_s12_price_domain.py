"""Frozen synthetic X-01 replay and independent, real-call-context fill audit.

This is synthetic evidence, not a lake/4090 validation. The optional wrappers
observe the existing ledger calls; they never change trades CSVs or cash.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
import sys
from contextlib import contextmanager
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
from backtest.research import csv_minute_backtest as minute
from backtest.research import csv_simulate_loop as loop
from backtest.research import strategy12_engine as engine
from backtest.research.csv_common import book_limit_prices
from backtest.research.csv_ledger import market_close_mark
from backtest.research.signal_price_domain import (
    build_s12_price_context,
    build_source_metadata,
)

CODE = "000001.SZ"
START = "20251103"
MONEY = Decimal("0.01")


def money(value):
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def transformed(raw, factor=0.5, offset=0):
    """Known synthetic affine formula; no fitting of observed market prices."""
    a, b = Decimal(str(factor)), Decimal(str(offset))
    result = {}
    for code, frame in raw.items():
        out = frame.copy(deep=True)
        for column in ("open", "high", "low", "close"):
            out[column] = [float(a * Decimal(str(v)) + b) for v in frame[column]]
        result[code] = out
    return result


def context_for(front, raw, mins, *, factor=0.5, offset=0, transforms=None):
    metadata = build_source_metadata(
        front, raw, mins, source_snapshot_id="x01-frozen-synthetic-v1",
        provenance={"kind": "synthetic_fixture", "algorithm": "known_affine_fixture",
                    "anchor_version": "fixture-v1"},
    )
    if transforms is None:
        transforms = {
            (code, day.strftime("%Y%m%d")): {"A": str(factor), "B": str(offset)}
            for code, frame in raw.items() for day in frame.index
        }
    return build_s12_price_context(front, raw, minute_bars=mins,
                                   metadata=metadata, transforms=transforms)


def fixture(paths=None, *, code=CODE, historical=10.0, daily_closes=None,
            factor=0.5, offset=0):
    if paths is None:
        paths = [[(895, 10.0)], [(570, 10.0), (585, 10.0), (895, 10.0)]]
    days = pd.bdate_range(START, periods=len(paths))
    history = pd.bdate_range(end=days[0] - pd.Timedelta(days=1), periods=12)
    values = [historical] * len(history) + (
        [historical] * len(paths) if daily_closes is None else list(daily_closes)
    )
    raw = {code: pd.DataFrame({c: values for c in ("open", "high", "low", "close")},
                              index=history.append(days))}
    rows = [{"time": day + pd.Timedelta(minutes=hm), "ymd": day.strftime("%Y%m%d"),
             "hm": hm, "open": px, "high": px, "low": px, "close": px}
            for day, prices in zip(days, paths) for hm, px in prices]
    mins = {code: pd.DataFrame(rows).set_index("time")}
    front = transformed(raw, factor, offset)
    return mins, raw, front, days


def _shares(st, code):
    return sum(pos.shares for pos in st.positions.get(code, []))


def _usage(st):
    return {} if st.volume_cap is None else dict(st.volume_cap.used)


def _actual_minute_context():
    frame = inspect.currentframe()
    try:
        frame = frame.f_back
        while frame is not None:
            if frame.f_code is engine.run_minute_day.__code__:
                return dict(frame.f_locals)
            frame = frame.f_back
    finally:
        del frame
    raise AssertionError("fill audit requires an actual run_minute_day caller")


@contextmanager
def capture_fills(events, *, ctx=None, rejected_calls=None):
    """Capture actual before/after balances and the scheduler's live hm.

    Patching the two call sites is confined to this dedicated replay wrapper.
    No time is inferred from reason, trade row order or a subsequent sort.
    """
    def wrapper(real):
        def call(st, code, *args, **kwargs):
            call_context = _actual_minute_context()
            cash_before, shares_before = st.cash, _shares(st, code)
            used_before, append_seq = _usage(st), len(st.trades)
            result = real(st, code, *args, **kwargs)
            hm, ds = int(call_context["hm"]), call_context["ds"]
            appended = st.trades[append_seq:]
            if not appended:
                assert st.cash == cash_before
                assert _shares(st, code) == shares_before
                assert _usage(st) == used_before
                if rejected_calls is not None:
                    rejected_calls.append({"date": ds, "code": code, "hm": hm,
                                           "ledger_call": real.__name__,
                                           "cash_unchanged": True,
                                           "shares_unchanged": True, "volume_unchanged": True})
            closes = call_context["closes_by_code"][code]
            reference = (ctx.reference_price_for(code, ds) if ctx is not None
                         else float(closes[-1]))
            for seq, trade in enumerate(appended, start=append_seq):
                if trade["side"] not in ("BUY", "SELL"):
                    continue
                fee, quantity, price = trade["commission"], trade["shares"], trade["price"]
                sign = 1 if trade["side"] == "BUY" else -1
                cash_after, shares_after = st.cash, _shares(st, code)
                assert money(cash_after) == money(cash_before - sign * quantity * price - fee)
                assert shares_after == shares_before + sign * quantity
                used_after = _usage(st)
                cap_delta = sum(used_after.values()) - sum(used_before.values())
                assert st.volume_cap is None or cap_delta == quantity
                assert money(cash_after) >= 0
                events.append({
                    "date": trade["date"], "code": code, "side": trade["side"],
                    "price": price, "shares": quantity, "reason": trade["reason"],
                    "cash_before": cash_before, "cash_after": cash_after, "hm": hm,
                    "append_seq": seq, "decision_hm": hm, "quote_hm": hm,
                    "fill_phase": "close", "lot_id": trade["lot"], "commission": fee,
                    "bucket_id": kwargs.get("bucket_id"),
                    "volume_at": kwargs.get("at", kwargs.get("bucket_id")),
                    "signal_domain": "raw_at_session_D" if ctx else "front",
                    "reference_price": reference, "mark_domain": "none" if ctx else "front",
                    "flags": {"fix_s12_price_domain": ctx is not None,
                              "economics_enabled": st.exdiv_economics is not None},
                    "shares_before": shares_before, "shares_after": shares_after,
                    "share_residual": shares_after - shares_before - sign * quantity,
                    "volume_delta": cap_delta,
                    "volume_residual": 0 if st.volume_cap is None else cap_delta - quantity,
                    "cash_residual_fen": str(money(cash_after) - money(
                        cash_before - sign * quantity * price - fee)),
                })
            return result
        return call

    with patch.object(loop, "execute_buy", wrapper(loop.execute_buy)), \
            patch.object(engine, "_sell", wrapper(engine._sell)):
        yield


def replay(mins, raw, front, days, *, enabled, factor=0.5, offset=0,
           pool=None, ctx=None, audit=None, **kwargs):
    if enabled and ctx is None:
        ctx = context_for(front, raw, mins, factor=factor, offset=offset)
    events = []
    params = {"strategy": "12", "total_cash": 5_000_000, "name_budget": 1_000_000}
    params.update(kwargs)
    if enabled:
        params.update(fix_s12_price_domain=True, s12_price_context=ctx)
    real_mark = minute.append_equity_and_eod_marks

    def mark(st, **mark_kwargs):
        real_mark(st, **mark_kwargs)
        if audit is not None:
            day = mark_kwargs["day"]
            positions = {code: {"shares": _shares(st, code),
                                "raw_mark": market_close_mark(raw.get(code), day),
                                "book_mark": market_close_mark(mark_kwargs["mark_bars"].get(code), day)}
                         for code in st.positions if st.positions[code]}
            receivable = 0 if st.exdiv_economics is None else st.exdiv_economics.receivable_total
            audit["daily_accounts"].append({
                "date": mark_kwargs["ds"], "cash": st.cash, "receivable": receivable,
                "positions": positions, "book_equity": st.equity_curve[-1][1],
                "raw_equity": st.cash + receivable + sum(
                    p["shares"] * p["raw_mark"] for p in positions.values()),
                "cumulative_fees": sum(t["commission"] for t in st.trades),
            })

    if audit is not None:
        audit.update(daily_accounts=[], rejected_ledger_calls=[])
    with capture_fills(events, ctx=ctx if enabled else None,
                       rejected_calls=None if audit is None else audit["rejected_ledger_calls"]), \
            patch.object(minute, "append_equity_and_eod_marks", mark):
        st = minute.simulate(mins, ctx.raw_daily if enabled else front,
                             {START: [next(iter(raw))]} if pool is None else pool,
                             START, days[-1].strftime("%Y%m%d"), **params)
    return st, events


def _hash_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _state_report(st, events, audit):
    fields = ("date", "code", "side", "price", "shares", "reason", "cash_before",
              "cash_after", "hm")
    return {
        "fill_count": len(events), "fill_tuples": [[e[k] for k in fields] for e in events],
        "events": events, "equity": st.equity_curve,
        "eod_marks": [t for t in st.trades if t["side"] == "EOD_MARK"],
        "cash": st.cash, "cash_min": min([st.cash] + [e["cash_after"] for e in events]),
        "negative_balance_count": sum(money(e["cash_after"]) < 0 for e in events),
        "share_residual": sum(e["share_residual"] for e in events),
        "volume_residual": sum(e["volume_residual"] for e in events),
        "cash_residual_fen": str(sum(Decimal(e["cash_residual_fen"]) for e in events)),
        "missing_or_rejection_counts": {key: value for key, value in st.stats.items()
                                        if any(token in key for token in ("skip", "missing", "defer"))},
        **audit,
        "stats": st.stats,
    }


def _fill_differences(off, on):
    """Keep observed append order; pair by event identity, never recompute cash."""
    identity = ("date", "code", "side", "reason", "hm", "lot_id")
    compared = ("price", "shares", "cash_before", "cash_after", "commission")
    differences = []
    unused = list(range(len(on)))
    for old in off:
        match = next((i for i in unused if all(old[k] == on[i][k] for k in identity)), None)
        if match is None:
            differences.append({"kind": "removed", "OFF": old, "ON": None})
            continue
        unused.remove(match)
        new = on[match]
        changed = [k for k in compared if old[k] != new[k]]
        if changed:
            differences.append({"kind": "changed", "fields": changed, "OFF": old, "ON": new})
    differences.extend({"kind": "added", "OFF": None, "ON": on[i]} for i in unused)
    return differences


def _mark_differences(off, on):
    result = []
    for old, new in zip(off, on):
        assert old["date"] == new["date"]
        if old == new:
            continue
        held_old = {c: p["shares"] for c, p in old["positions"].items()}
        held_new = {c: p["shares"] for c, p in new["positions"].items()}
        mark_only = (held_old == held_new and old["cash"] == new["cash"]
                     and old["receivable"] == new["receivable"])
        result.append({"date": old["date"], "mark_only": mark_only,
                       "OFF": old, "ON": new,
                       "book_equity_delta_fen": str(money(new["book_equity"] - old["book_equity"]))})
    return result


def _reference_audit(ctx, code, day, expected):
    view = ctx.day_signal_view(code, day)
    actual = book_limit_prices(code, view.prev_ref_raw, {})
    independent = (money(expected * Decimal("1.10")), money(expected * Decimal("0.90")))
    differences = [money(view.prev_ref_raw) - expected,
                   money(actual[0]) - independent[0], money(actual[1]) - independent[1]]
    assert differences == [Decimal(0)] * 3
    return {"date": day.strftime("%Y%m%d"), "code": code, "board_band": "main/10%",
            "reference_unrounded": str(view.prev_ref_unrounded),
            "reference_rounded": str(money(view.prev_ref_raw)),
            "independent_reference": str(expected),
            "independent_source": "known synthetic fixture; 非官方行情，官方 preClose 不可得",
            "ON_limits": actual, "independent_limits": [str(v) for v in independent],
            "differences_yuan": [str(v) for v in differences]}


def generate_report():
    cases = []
    configurations = [(f"constant_factor_{factor}", factor, 0) for factor in (0.5, 0.96, 1.0, 1.05, 1.2)]
    configurations.append(("affine_A1_Bminus1", 1.0, -1))
    for label, factor, offset in configurations:
        inputs = fixture(factor=factor, offset=offset)
        mins, raw, front, days = inputs
        ctx = context_for(front, raw, mins, factor=factor, offset=offset)
        off_audit, on_audit = {}, {}
        off, off_events = replay(*inputs, enabled=False, factor=factor, offset=offset, audit=off_audit)
        on, on_events = replay(*inputs, enabled=True, factor=factor, offset=offset,
                               ctx=ctx, audit=on_audit)
        off_report = _state_report(off, off_events, off_audit)
        on_report = _state_report(on, on_events, on_audit)
        # With constant raw prices and no economics, fees are the only lost wealth,
        # including OFF accounts whose reported mark is in the wrong unit.
        for account in [*off_audit["daily_accounts"], *on_audit["daily_accounts"]]:
            assert money(account["raw_equity"] + account["cumulative_fees"]) == money(5_000_000)
        assert [(e["side"], e["price"], e["shares"]) for e in on_events] == [("BUY", 10., 100_000)]
        assert all(money(value) == money(4_999_000) for _, value in on.equity_curve)
        if factor == 1 and offset == 0:
            assert off.trades == on.trades and off.equity_curve == on.equity_curve
        first = next((i for i in range(max(len(off_events), len(on_events)))
                      if i >= len(off_events) or i >= len(on_events)
                      or tuple(off_events[i][k] for k in ("date", "side", "price", "shares", "reason", "hm"))
                      != tuple(on_events[i][k] for k in ("date", "side", "price", "shares", "reason", "hm"))), None)
        attribution = (["限价：F=R−1，OFF参考9导致假涨停拒池买，ON通用逆变换还原raw参考10"]
                       if offset else {
            0.5: ["限价：OFF假涨停拒池买/入追买队列，次日错误限价拒追；ON首日原始价正常买"],
            0.96: ["估值：成交相同，OFF以9.6记100000股，ON以raw10记市值"],
            1.0: ["控制：成交与现金/NAV相同"],
            1.05: ["信号阈值：OFF次日假MA5减仓50000股", "估值：front10.5恢复raw10"],
            1.2: ["估值：front12恢复raw10", "限价：OFF错误跌停10.8抑制扫描；ON正确参考10"],
        }[factor])
        differences = _fill_differences(off_events, on_events)
        expected_changes = {0.5: ["added"], 0.96: [], 1.0: [], 1.05: ["removed"], 1.2: []}
        expected = ["added"] if offset else expected_changes[factor]
        assert [difference["kind"] for difference in differences] == expected
        for difference in differences:
            difference["attribution"] = "signal_threshold" if factor == 1.05 else "limit_reference"
        marks = _mark_differences(off_audit["daily_accounts"], on_audit["daily_accounts"])
        cases.append({"case": label, "factor": factor, "offset": offset, "input_hash": _hash_json([
            {code: frame.to_dict(orient="split") for code, frame in bars.items()}
            for bars in inputs[:3]]), "OFF": off_report, "ON": on_report,
            "first_fill_difference_index": first, "fill_differences": differences,
            "mark_differences": marks, "mark_only_dates": [d["date"] for d in marks if d["mark_only"]],
            "attribution": attribution,
            "raw_account_plus_fees_conserved": True,
            "reference_audit": [_reference_audit(ctx, CODE, day, Decimal("10.00")) for day in days],
            "unexplained": []})
    rounding_samples = []
    for reference in (1.014, 1.005):
        mins, raw, front, days = fixture(paths=[[(895, 1.1)]], historical=reference)
        ctx = context_for(front, raw, mins)
        rounding_samples.append(_reference_audit(ctx, CODE, days[0], Decimal("1.01")))
    source_files = [Path(__file__), REPO_ROOT / "backtest/research/signal_price_domain.py",
                    REPO_ROOT / "backtest/research/strategy12_engine.py",
                    REPO_ROOT / "backtest/research/csv_simulate_loop.py",
                    REPO_ROOT / "backtest/research/csv_minute_backtest.py"]
    baseline = REPO_ROOT / "tests/fixtures/off_byte_baseline_eff77f3.json"
    return {"evidence": "synthetic_only; 真实数据未验证，待 4090",
            "head_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                                                text=True).strip(),
            "source_hashes": {str(p.relative_to(REPO_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in source_files},
            "off_baseline_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest(),
            "parameters_hash": _hash_json({"cash": 5_000_000, "budget": 1_000_000,
                                             "cost": 0.001, "pool": {START: [CODE]}}),
            "tuple_columns": ["date", "code", "side", "price", "shares", "reason",
                              "cash_before", "cash_after", "hm"],
            "cases": cases, "rounding_reference_audit": rounding_samples, "unexplained": [],
            "limits": ["δ6默认关闭，raw_accounting_only不等同总回报", "仅合成数学夹具，无真实湖PIT结论"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    report = generate_report()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "synthetic-ab.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    lines = ["# X-01 合成 A/B", "", "真实数据未验证，待 4090。", "",
             "| A / B | OFF/ON 成交数 | OFF 期末 NAV | ON 期末 NAV | 归因 |",
             "|---|---:|---:|---:|---|"]
    for case in report["cases"]:
        off, on = case["OFF"], case["ON"]
        lines.append(f"| {case['factor']} / {case['offset']} | {off['fill_count']}/{on['fill_count']} | "
                     f"{money(off['equity'][-1][1])} | {money(on['equity'][-1][1])} | "
                     + "；".join(case["attribution"]) + " |")
    lines.extend(["", "逐笔元组、增删/字段差异、实际调用时钟、逐日账户/mark、输入/代码/参数哈希见 synthetic-ab.json。",
                  "A=0.96 的两个持仓日与 A=1.05 首日仅 mark 改变；A=1.05 次日另消除假减仓。",
                  "1.014 和 1.005 均先落分为 1.01，再得涨停 1.11 / 跌停 0.91；独立合成对照差额为 0。",
                  "所有现金按 Decimal HALF_UP 到分验算；股数/量预算残差及未解释项为 0。",
                  "本次量门关闭；volume_residual=0 仅证明未消耗量预算，容量守恒由定向测试覆盖。",
                  "缺失输入为 0，拒绝统计保留实际 stats；未进入 ledger 的限价拒绝不可冒充已观测的 ledger 未成交调用。",
                  "六组合成恒价账户的 raw 市值 + cash + 累计费用逐日守恒；旧混域 book NAV 不守恒。"])
    markdown = "\n".join(lines) + "\n"
    (args.out_dir / "synthetic-ab.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
