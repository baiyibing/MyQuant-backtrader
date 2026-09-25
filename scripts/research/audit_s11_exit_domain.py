"""Data-free X-03 replay with call-site audit sidecars, never rewritten trade CSVs.

Run with an explicitly selected interpreter and --out-dir. This is a dedicated,
single-threaded synthetic replay, not a production tracing hook or lake runner.
The wrapper captures ledger balances before/after each real call, the live
caller's reference/limits, and the selected opening quote. It fails on unfamiliar
call sites rather than reconstructing clocks from trade reasons or row order.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import platform
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as minute
from backtest.research import csv_simulate_loop as loop
from backtest.research.csv_artifacts import write_run_artifacts

CODE = "600000.SH"
START, END = "20240902", "20240904"
TUPLE_FIELDS = ("date", "code", "side", "price", "shares", "reason",
                "cash_before", "cash_after", "hm")
GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_eff77f3.json"


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                       allow_nan=False) + "\n").encode("utf-8")


def write_json(path, value):
    path.write_bytes(json_bytes(value))


def fixture(*, control=False, scale=1., offset=0.):
    dates = pd.bdate_range("20240826", periods=8)
    closes = [10.] * 5 + [10.5, 9.45, 9.7]
    opens = [10.] * 5 + [10.2, 9.45, 9.7]
    raw = pd.DataFrame({"open": opens, "close": closes,
                        "high": np.maximum(opens, closes),
                        "low": np.minimum(opens, closes), "volume": 100_000.},
                       index=dates)
    front = raw.copy()
    if not control:
        front.loc[front.index < pd.Timestamp("20240903"),
                  ["open", "high", "low", "close"]] *= .9
    front[["open", "high", "low", "close"]] = (
        front[["open", "high", "low", "close"]] * scale + offset
    )
    rows = []
    for day, row in raw.iterrows():
        for hm in (570, 585, 895):
            rows.append({"time": day + pd.Timedelta(minutes=hm),
                         "ymd": day.strftime("%Y%m%d"), "hm": hm,
                         "open": row["open"] if hm == 570 else row["close"],
                         "high": row["high"], "low": row["low"],
                         "close": row["close"], "volume": 10_000.})
    minutes = pd.DataFrame(rows).set_index("time")
    exdiv = {} if control else {CODE: {"20240903": .9}}
    return {CODE: raw}, {CODE: front}, {CODE: minutes}, exdiv


def held_shares(st):
    return {code: sum(pos.shares for pos in lots) for code, lots in st.positions.items()}


class Replay:
    """Intercept actual engine phase/quote and ledger calls without changing them."""

    def __init__(self, engine, enabled):
        self.engine = engine
        self.enabled = enabled
        self.fills = []
        self.attempts = []
        self.signals = []
        self.eod = []
        self.quote = None
        self.pool_phase = None

    @property
    def signal_domain(self):
        return "front" if self.enabled else "legacy_execution_bars"

    def book_call(self, original, args, kwargs, caller, side):
        st, code = args[:2]
        before, shares_before = st.cash, held_shares(st)
        used_before = dict(st.volume_cap.used) if st.volume_cap else {}
        first = len(st.trades)
        context = caller.f_locals
        if side == "BUY":
            assert caller.f_code is loop.run_pool_buys_day.__code__
            assert self.pool_phase is not None
            phase = self.pool_phase
            if self.engine is minute:
                assert self.quote is not None and int(self.quote["hm"]) == 570
                quote_hm = int(self.quote["hm"])
                quote_price = float(self.quote["open"])
            else:
                quote_hm, quote_price = None, float(context["quoted"][0])
        else:
            assert caller.f_code is self.engine.simulate.__code__
            # This replay deliberately exercises the pending-open branch only.
            # Read the exact live quote, and fail if an unrelated sell path appears.
            assert context["pos"].pending_exit
            phase = "open"
            if self.engine is minute:
                quote_hm = int(context["opening"]["hm"])
                quote_price = float(context["opening"]["open"])
                assert kwargs["hm"] == quote_hm == 570
            else:
                quote_hm, quote_price = None, float(context["row"]["open"])
        reference = float(context["prev_close"])
        limits = [float(value) for value in context["limits"]]
        result = original(*args, **kwargs)
        shares_after = held_shares(st)
        used_after = dict(st.volume_cap.used) if st.volume_cap else {}
        appended = st.trades[first:]
        fills = [row for row in appended if row["side"] in ("BUY", "SELL")]
        assert len(fills) <= 1, "unexpected linked fill in this economics-OFF fixture"
        attempt = {"side": side, "code": code, "cash_before": before,
                   "cash_after": st.cash, "shares_before": shares_before,
                   "shares_after": shares_after, "filled": bool(fills),
                   "fill_phase": phase, "quote_hm": quote_hm,
                   "bucket_id": kwargs.get("bucket_id"), "volume_at": kwargs.get("at"),
                   "volume_used_before": {str(k): v for k, v in used_before.items()},
                   "volume_used_after": {str(k): v for k, v in used_after.items()}}
        self.attempts.append(attempt)
        if not fills:
            assert st.cash == before and shares_after == shares_before
            assert used_after == used_before
            return result
        row = fills[0]
        assert float(row["price"]) == quote_price
        sign = -1 if side == "BUY" else 1
        expected_cash = before + sign * row["shares"] * row["price"] - row["commission"]
        assert money(st.cash) == money(expected_cash)
        expected_shares = shares_before.get(code, 0) - sign * row["shares"]
        assert shares_after.get(code, 0) == expected_shares
        assert all(shares_after.get(other, 0) == qty for other, qty in shares_before.items()
                   if other != code)
        self.fills.append({
            **{name: row[name] for name in TUPLE_FIELDS[:6]},
            "cash_before": before, "cash_after": st.cash,
            "hm": quote_hm, "append_seq": first,
            "decision_hm": quote_hm, "quote_hm": quote_hm,
            "fill_phase": phase, "lot_id": row["lot"],
            "commission": row["commission"], "bucket_id": kwargs.get("bucket_id"),
            "volume_at": kwargs.get("at"), "signal_domain": self.signal_domain,
            "reference_price": reference, "limit_prices": limits,
            "mark_domain": "none", "flags": {"fix_s11_exit_domain": self.enabled,
                                                 "exdiv_economics": False},
            "cash_formula_residual_fen": str(money(st.cash) - money(expected_cash)),
            "share_residual": shares_after.get(code, 0) - expected_shares,
            "shares_before": shares_before, "shares_after": shares_after,
        })
        return result

    @contextlib.contextmanager
    def capture(self):
        original_buy, original_sell = loop.execute_buy, self.engine._sell
        original_pool = self.engine.run_pool_buys_day
        original_eod = self.engine.run_eod_exits
        original_marks = self.engine.append_equity_and_eod_marks

        def buy(*args, **kwargs):
            return self.book_call(original_buy, args, kwargs, sys._getframe(1), "BUY")

        def sell(*args, **kwargs):
            return self.book_call(original_sell, args, kwargs, sys._getframe(1), "SELL")

        def pool(*args, **kwargs):
            # The engine's explicit pool phase, before EOD evaluation, is the
            # source of this label. No trade reason or appended row is consulted.
            self.pool_phase = "EOD" if self.engine is daily else "open"
            try:
                return original_pool(*args, **kwargs)
            finally:
                self.pool_phase = None

        def eod(st, **kwargs):
            actual_exit = kwargs["eod_exit"]

            def decision(closes, previous, mode):
                result = actual_exit(closes, previous, mode)
                live = sys._getframe(1).f_locals
                self.signals.append({"date": kwargs["ds"], "code": live["code"],
                                     "lot_id": live["pos"].lot_id, "phase": "EOD",
                                     "signal_domain": self.signal_domain,
                                     "previous": previous, "closes_including_today": closes,
                                     "mode_before": mode, "mode_after": result.hold_mode,
                                     "pending_reason": result.reason})
                return result

            return original_eod(st, **{**kwargs, "eod_exit": decision})

        def marks(st, **kwargs):
            result = original_marks(st, **kwargs)
            raw = kwargs["mark_bars"]
            day = kwargs["day"]
            marks_by_code = {code: float(frame.loc[frame.index <= day, "close"].iloc[-1])
                             for code, frame in raw.items() if any(frame.index <= day)}
            quantities = held_shares(st)
            expected = st.cash + sum(qty * marks_by_code[code] for code, qty in quantities.items())
            assert money(st.equity_curve[-1][1]) == money(expected)
            self.eod.append({"date": kwargs["ds"], "cash": st.cash,
                             "equity": st.equity_curve[-1][1], "shares": quantities,
                             "raw_marks": marks_by_code, "mark_domain": "none",
                             "pending": {code: [pos.pending_exit for pos in lots]
                                         for code, lots in st.positions.items()},
                             "receivable": 0., "nav_formula_residual_fen": "0.00"})
            return result

        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(loop, "execute_buy", buy))
            stack.enter_context(patch.object(self.engine, "_sell", sell))
            stack.enter_context(patch.object(self.engine, "run_pool_buys_day", pool))
            stack.enter_context(patch.object(self.engine, "run_eod_exits", eod))
            stack.enter_context(patch.object(self.engine, "append_equity_and_eod_marks", marks))
            if self.engine is minute:
                original_open = minute._open_quote_for

                def opening(*args, **kwargs):
                    result = original_open(*args, **kwargs)
                    self.quote = None if result is None else result.copy()
                    return result

                stack.enter_context(patch.object(minute, "_open_quote_for", opening))
            yield self


def run_case(output, engine_name, enabled, *, control=False, scale=1., offset=0.):
    raw, front, minutes, exdiv = fixture(control=control, scale=scale, offset=offset)
    engine = daily if engine_name == "daily" else minute
    pools = {START: [CODE]}
    params = {"strategy": "version11", "total_cash": 100_000., "daily_quota": 5_000.,
              "fix_s11_exit_domain": enabled, "exdiv": exdiv}
    inputs = {"pool": pools, "start": START, "end": END,
              "frames_sha256": {domain: digest(frames[CODE].to_csv().encode("utf-8"))
                                 for domain, frames in (("raw_daily", raw), ("front_daily", front),
                                                        ("raw_minute", minutes))}}
    with Replay(engine, enabled).capture() as replay:
        args = (raw,) if engine_name == "daily" else (minutes, raw)
        st = engine.simulate(*args, pools, START, END, **params,
                             **({"signal_bars_front": front} if enabled else {}))
    output.mkdir(parents=True, exist_ok=True)
    with contextlib.redirect_stdout(io.StringIO()):
        write_run_artifacts(output, st, "X-03 synthetic replay; real data unverified", "")
    minimum_cash = min([100_000., st.cash] + [row["cash_after"] for row in replay.fills])
    trace = {"kind": "synthetic_only", "engine": engine_name,
             "tuple_fields": TUPLE_FIELDS, "inputs": inputs, "params": params,
             "input_sha256": digest(json_bytes(inputs)), "params_sha256": digest(json_bytes(params)),
             "trades_csv_sha256": digest((output / "trades.csv").read_bytes()),
             "equity_csv_sha256": digest((output / "daily_equity.csv").read_bytes()),
             "fills": replay.fills, "ledger_attempts": replay.attempts,
             "signals": replay.signals, "eod": replay.eod,
             "checks": {"cash_minimum": minimum_cash, "negative_cash": minimum_cash < 0,
                        "cash_residual_fen": "0.00", "share_residual": 0,
                        "nav_residual_fen": "0.00", "volume_budget_residual": 0,
                        "volume_budget_note": "capacity OFF; no consumed volume budget",
                        "missing_or_refusal_counts": {key: value for key, value in st.stats.items()
                                                      if key.startswith(("skip_", "defer_"))},
                        "economic_entitlements": "OFF: no bonus shares/dividend cash/receivables"},
             "stats": st.stats}
    assert not trace["checks"]["negative_cash"]
    write_json(output / "trace.json", trace)
    return trace


def comparable_fills(trace):
    return [{name: row[name] for name in (*TUPLE_FIELDS, "commission", "fill_phase")}
            for row in trace["fills"]]


def comparison(off, on):
    off_fills, on_fills = comparable_fills(off), comparable_fills(on)
    first_fill = next((i for i in range(max(len(off_fills), len(on_fills)))
                       if off_fills[i:i + 1] != on_fills[i:i + 1]), None)
    signal_keys = ("date", "code", "mode_after", "pending_reason")
    off_decisions = [{key: row[key] for key in signal_keys} for row in off["signals"]]
    on_decisions = [{key: row[key] for key in signal_keys} for row in on["signals"]]
    first_signal = next((i for i in range(max(len(off_decisions), len(on_decisions)))
                         if off_decisions[i:i + 1] != on_decisions[i:i + 1]), None)
    return {"fill_counts": {"OFF": len(off_fills), "ON": len(on_fills)},
            "first_fill_divergence": first_fill, "first_signal_divergence": first_signal,
            "removed_fills": [row for row in off_fills if row not in on_fills],
            "added_fills": [row for row in on_fills if row not in off_fills],
            "per_day": [{"date": a["date"], "off_equity": a["equity"],
                         "on_equity": b["equity"],
                         "nav_delta_fen": str(money(b["equity"]) - money(a["equity"])),
                         "off_cash": a["cash"], "on_cash": b["cash"],
                         "off_shares": a["shares"], "on_shares": b["shares"],
                         "raw_mark_delta": {code: b["raw_marks"][code] - price
                                            for code, price in a["raw_marks"].items()}}
                        for a, b in zip(off["eod"], on["eod"], strict=True)],
            "attribution": {"signal_threshold": "front INITIAL/HOLD; false raw SMA break removed",
                            "limits": "unchanged raw execution reference and exdiv map",
                            "valuation": "unchanged raw mark prices; holding changes after false exit",
                            "cash_availability": "only missing false sale proceeds and fee",
                            "holdings_availability": "ON retains 400 shares after cancelled pending",
                            "downstream": "no subsequent pool; no further propagation in fixture"},
            "unexplained": []}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    sources = [ROOT / "scripts/research/audit_s11_exit_domain.py", *sorted(
        (ROOT / "backtest/research").glob("*.py"))]
    source_hashes = {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in sources}
    report = {"kind": "synthetic_only", "real_data_validation": "真实数据未验证，待 4090",
              "python": sys.version, "pandas": pd.__version__, "platform": platform.platform(),
              "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "code_sha256": digest(json_bytes(source_hashes)), "source_hashes": source_hashes,
              "off_baseline_file_sha256": digest(GOLDEN.read_bytes()),
              "off_baseline_source": "eff77f375f5636e3e9659aa8fd753404035f2782",
              "off_baseline_v11": json.loads(GOLDEN.read_text(encoding="utf-8"))["cases"],
              "engines": {}, "limits": ["X-08 exporter/CYQK 未验", "Slice D 未完成",
                                          "δ6 economics OFF", "X-20 预热不改",
                                          "锚点测试只证明本夹具；既有 float SMA 等号边界可能翻转"],
              "unexplained": []}
    report["off_baseline_v11"] = {key: value for key, value in report["off_baseline_v11"].items()
                                  if key.startswith("version11/")}
    summary = ["# X-03 合成逐笔 A/B", "", "真实数据未验证，待 4090。", "",
               "| 引擎 | OFF/ON 成交数 | OFF 最终现金 | ON 最终现金 | OFF NAV | ON NAV | 差额 |",
               "|---|---|---|---|---|---|---|"]
    for engine in ("daily", "minute"):
        base = args.out_dir / engine
        off = run_case(base / "off", engine, False)
        on = run_case(base / "on", engine, True)
        diff = comparison(off, on)
        for label, scale, offset in (("scaled", .37, 0.), ("affine", .37, 2.)):
            transformed = run_case(base / label, engine, True, scale=scale, offset=offset)
            assert comparable_fills(transformed) == comparable_fills(on)
            assert transformed["eod"] == on["eod"]
            assert [(r["mode_after"], r["pending_reason"]) for r in transformed["signals"]] == [
                (r["mode_after"], r["pending_reason"]) for r in on["signals"]]
        control_off = run_case(base / "true_break_off", engine, False, control=True)
        control_on = run_case(base / "true_break_on", engine, True, control=True)
        assert comparable_fills(control_off) == comparable_fills(control_on)
        assert control_off["eod"] == control_on["eod"]
        assert len(control_on["fills"]) == 2
        assert len(off["fills"]) == 2 and len(on["fills"]) == 1
        assert money(off["eod"][-1]["equity"]) == Decimal("99671.92" if engine == "daily" else "99792.04")
        assert money(on["eod"][-1]["equity"]) == Decimal("99675.80" if engine == "daily" else "99795.92")
        assert money(on["eod"][-1]["equity"]) - money(off["eod"][-1]["equity"]) == Decimal("3.88")
        diff["controls"] = {"front_times_0_37": "PASS", "front_times_0_37_plus_2": "PASS",
                            "genuine_same_domain_break_still_sells_next_open": "PASS"}
        report["engines"][engine] = diff
        last = diff["per_day"][-1]
        summary.append(f"| {engine} | 2 / 1 | {money(last['off_cash'])} | {money(last['on_cash'])} | "
                       f"{money(last['off_equity'])} | {money(last['on_equity'])} | {last['nav_delta_fen']} |")
    write_json(args.out_dir / "report.json", report)
    summary += ["", "OFF raw SMA5=9.99 触发假 pending；ON front SMA5=9.18 保留 400 股。",
                "两腿 raw mark 相同，最终差额 3.88 为被取消卖单的手续费；不解释为收益能力。",
                "trace.json 保留真实账本调用顺序、原始 float、逐笔现金和股数守恒。",
                "日线 hm=null、phase=open/EOD；分钟从实际选中报价捕获 09:30（570）。",
                "未解释差异 0。本夹具的正缩放、正仿射与真实破位对照均通过。",
                "既有 float SMA 等号边界仍可能翻转（5.12×0.37）；不宣称任意浮点边界不变。",
                "无权益凭空补齐：除权后财富下降保留 δ6 economics OFF 限制。", ""]
    (args.out_dir / "summary.md").write_text("\n".join(summary), encoding="utf-8")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
