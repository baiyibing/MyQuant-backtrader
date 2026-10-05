"""Record new synthetic v7/APP contracts once; migration must never re-record."""

from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
from collections import Counter
from contextlib import ExitStack, redirect_stdout
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from backtest.research import ashare_session
from backtest.research import csv_minute_backtest_topk_app_dropout as app
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research import minute_bar_scan_host as host
from backtest.research.ashare_exdiv_economics import ExDivEvent
from backtest.research.ashare_volume_cap import BucketVolume

FIXTURE = ROOT / "tests/fixtures/v7_app_optin_baseline_20261005.json"
CASES = (
    "default",
    "chronological",
    "short_cash",
    "tail_default",
    "tail_none",
    "tail_shares",
    "tail_lots",
    "participation",
    "exdiv",
    "economics",
    "index_gate",
    "frame_calendar",
    "names",
    "names_by_day",
    "audit",
    "host_version7",
    "sell_fill_only",
    "app_pred_minus_one",
    "app_identity",
)


def inputs():
    """Five stage stops, timer, T+1 partial exit, limits and missing quotes."""
    dates = [d.date() for d in pd.bdate_range("2026-06-01", periods=26)]
    days = dates[11:]
    codes = [f"{i:06d}.SZ" for i in range(1, 10)]
    rows = {c: [] for c in codes}
    daily = {c: {d: 10.0 for d in dates} for c in codes}

    def bar(code, day, hm, price, opening=None):
        rows[code].append(
            {
                "hm": hm,
                "ymd": day.strftime("%Y%m%d"),
                "time": pd.Timestamp(day) + pd.Timedelta(minutes=hm),
                "open": price if opening is None else opening,
                "high": max(price, opening or price),
                "low": price,
                "close": price,
                "volume": 1_000_000.0,
                "amount": price * 1_000_000.0,
            }
        )

    for day in days:
        for code in codes[:7]:
            bar(code, day, 570, 10.0)
            for hm in range(870, 898):
                bar(code, day, hm, 10.0)
            bar(code, day, 900, 10.0)
    # Stage progression on the second session; subsequent-day stops.
    for n, code in enumerate(codes[1:5], 1):
        for row in rows[code]:
            day = row["time"].date()
            hm = row["time"].hour * 60 + row["time"].minute
            if day == days[1] and hm >= 885:
                price = 10 * (1 + 0.04 * min(n, hm - 884))
                row.update(
                    open=price, high=price, low=price, close=price, amount=price * 1_000_000.0
                )
        daily[code][days[0]] = 10.5 if n == 1 else 11.0  # +12/+16 remain within the session band
        daily[code][days[1]] = 10.5
        # On day 1 a later stop sells yesterday's trial but locks today's adds.
        if n == 1:
            bar(code, days[1], 899, 9.6)
        for row in rows[code]:
            if row["time"].date() == days[2] and row["time"].hour == 9:
                row.update(open=9.6, high=10.0, low=9.6, close=10.0)
    # Trial stop first encounters limit-down, then a legal fill on the next day.
    for row in rows[codes[0]]:
        if row["time"].date() == days[1]:
            row.update(open=9.0, high=9.0, low=9.0, close=9.0)
        if row["time"].date() == days[2] and row["time"].hour == 9:
            row.update(open=8.9, high=10.0, low=8.9, close=10.0)
    daily[codes[0]][days[1]] = 9.0
    for code, price in zip(codes[7:], (11.0, 9.0), strict=True):
        bar(code, days[0], 895, price)
    missing = "000010.SZ"
    pool = {days[0]: codes + [missing], days[2]: codes[:5], days[3]: [missing]}
    frames = {
        c: pd.DataFrame(r).sort_values("time", kind="stable").set_index("time")
        for c, r in rows.items()
    }
    frames[codes[6]] = frames[codes[6]].loc[frames[codes[6]].index.date != days[5]]
    return frames, daily, pool, dates, days, codes


def canonical_artifact(name, blob):
    if name.endswith(".csv") and name in ("trades.csv", "daily_equity.csv"):
        # V7 skip rows contain empty optional numeric cells, unlike shared CSVs.
        import csv

        from scripts.research.generate_off_byte_baseline import _canonical_value

        reader = csv.DictReader(io.StringIO(blob.decode(), newline=""))
        return {
            "columns": reader.fieldnames,
            "rows": [
                {k: _canonical_value(k, v) if v else "" for k, v in row.items()} for row in reader
            ],
        }
    if name.endswith(".json"):
        return normalize(json.loads(blob))
    return blob.decode("utf-8")


def normalize(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, float):
        return format(Decimal(str(value)).quantize(Decimal("0.00000001")), "f")
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [normalize(v) for v in value]
    return value


def capture_case(case, output):
    frames, daily, pool, dates, days, codes = inputs()
    index = {d: 3000.0 for d in dates}
    opts = {"start": days[0], "end": days[-1]}
    audit = []
    if case == "chronological":
        opts["fix_minute_cash_order"] = True
    if case == "sell_fill_only":
        frame = frames[codes[2]]
        mask = frame.index.date == days[2]
        frame.loc[mask, "open"] = 9.45
        frame.loc[mask & (frame["hm"] == 870), "close"] = 9.6
    if case == "short_cash":
        opts["cash_total"] = 210_000.0
    if case.startswith("tail_"):
        opts.update(tail_window_buy=True, fix_minute_cash_order=True)
        unit = case.removeprefix("tail_")
        if unit != "default":
            opts["tail_volume_unit"] = None if unit == "none" else unit
        if unit == "lots":
            for frame in frames.values():
                frame["volume"] /= 100
    if case == "participation":
        opts.update(
            participation_rate=0.1,
            volume_for_bucket={
                (c, t.strftime("%Y%m%d"), t.hour * 60 + t.minute): BucketVolume(
                    10_000, t.hour * 60 + t.minute, "raw_shares_incremental"
                )
                for c, frame in frames.items()
                for t in frame.index
            },
        )
    if case in ("exdiv", "economics"):
        ds = days[1].strftime("%Y%m%d")
        opts["exdiv"] = {codes[5]: {ds: 0.9}}
        for row in ("open", "high", "low", "close"):
            mask = frames[codes[5]].index.date >= days[1]
            frames[codes[5]].loc[mask, row] *= 0.9
        if case == "economics":
            opts["exdiv_economics"] = {
                (codes[5], ds): ExDivEvent(
                    "synthetic-dividend", Decimal(0), Decimal(1), ds, days[4].strftime("%Y%m%d")
                )
            }
    if case in ("names", "names_by_day"):
        value = {codes[4]: "ST synthetic"}
        opts[case] = value if case == "names" else {d.strftime("%Y%m%d"): value for d in days}
    if case == "audit":
        opts["audit_sink"] = audit
    if case == "index_gate":
        index = {d: 3000.0 if i < 12 else 2000.0 for i, d in enumerate(dates)}
        pool[days[4]] = [codes[7]]
        frames[codes[7]] = frames[codes[6]].loc[frames[codes[6]].index.date >= days[4]].copy()
    output.mkdir(parents=True, exist_ok=True)
    extra = {}
    if case.startswith("app_") or case == "host_version7":
        app_dir = output / "inputs"
        app_dir.mkdir()
        for d, members in pool.items():
            (app_dir / f"{d:%Y%m%d}.csv").write_text(
                "".join(f"{c[:6]},Name {c}\n" for c in reversed(members)), encoding="utf-8"
            )
        pred = output / "pred.csv"
        pred.write_text(
            "datetime,instrument,score\n"
            + "".join(
                f"{d},SZ{c[:6]},{100 - j - i % 2}\n"
                for i, d in enumerate(dates)
                for j, c in enumerate(codes)
                if not (i == 11 and j == 0)
            ),
            encoding="utf-8",
        )
        with ExitStack() as stack:
            for module in (v7, app):
                stack.enter_context(
                    patch.object(module, "_load_cli_bars", return_value=(frames, daily))
                )
                stack.enter_context(patch.object(module, "load_index_daily", return_value=index))
            for module in (ashare_session, app):
                stack.enter_context(
                    patch.object(module, "load_limit_context", return_value=({}, {}))
                )
            captured = []
            module = v7 if case == "host_version7" else app
            simulator = module.simulate_v7

            def observe(*args, **kwargs):
                state = simulator(*args, **kwargs)
                captured.append(state)
                return state

            stack.enter_context(patch.object(module, "simulate_v7", side_effect=observe))
            if case == "host_version7":
                result = host.run_version7(days[0], days[-1], pool_dir=app_dir)
                extra["host"] = asdict(result)
                assert len(captured) == 1
                state = captured[0]
                v7.write_run_artifacts(state, output)
            else:
                dump = output / "pool"
                with redirect_stdout(io.StringIO()):
                    assert (
                        app.main(
                            [
                                "--start",
                                f"{days[0]:%Y%m%d}",
                                "--end",
                                f"{days[-1]:%Y%m%d}",
                                "--app-pool-dir",
                                str(app_dir),
                                "--pred",
                                str(pred),
                                "--asof",
                                case.removeprefix("app_"),
                                "--dump-pool-dir",
                                str(dump),
                                "--output-dir",
                                str(output),
                            ]
                        )
                        == 0
                    )
                pools = v7.load_pool_days(dump, days[0], days[-1])
                expected = list(reversed(codes if case.endswith("pred_minus_one") else codes[1:]))
                assert pools and pools[days[0]] == expected
                extra["pools"] = {d.isoformat(): members for d, members in pools.items()}
                assert len(captured) == 1
                state = captured[0]
                assert app.DEFAULT_CASH_TOTAL == 500_000_000.0
    else:
        state = v7.simulate_v7(
            frames, daily, pool, None if case == "frame_calendar" else index, **opts
        )
        v7.write_run_artifacts(state, output)
    counts = Counter(t["reason"] for t in state.trades)
    assert counts["buy:trial"] and any(t["side"] == "sell" for t in state.trades), case
    if case in ("default", "chronological", "audit", "frame_calendar"):
        for reason in (
            "buy:add_a104",
            "buy:add_a108",
            "buy:add_a112",
            "buy:add_a116",
            "stop:trial_a090",
            "stop:four_avg095",
            "stop:six_avg0965",
            "stop:eight_avg0975",
            "stop:full_avg098",
            "exit:timer10",
            "skip_limit_up",
            "defer_limit_down",
            "skip_no_1455",
        ):
            assert counts[reason], (case, reason, counts)
        assert not any(t["side"] == "buy" and t["symbol"] == codes[8] for t in state.trades)
        assert not any(
            t["side"] == "buy" and t["date"] == days[2].isoformat() and t["symbol"] in codes[:5]
            for t in state.trades
        )  # cleared_today
        partial = [t for t in state.trades if t["symbol"] == codes[1] and t["side"] == "sell"]
        assert {t["date"] for t in partial} >= {days[1].isoformat(), days[2].isoformat()}
    if case == "short_cash":
        assert counts["skip_cash"]
    if case == "index_gate":
        assert counts["skip_index_gate"]
    if case.startswith("tail_"):
        assert any(t["side"] == "buy" and t["hm"] == 870 for t in state.trades)
    if case == "participation":
        assert state.volume_cap.used and all(t["shares"] <= 1000 for t in state.trades)
        assert any(reason.startswith("skip_volume_unavailable") for reason in counts)
    if case == "sell_fill_only":
        assert any(
            t["symbol"] == codes[2]
            and t["side"] == "sell"
            and t["date"] == days[2].isoformat()
            and t["hm"] == 870
            and t["price"] == 9.6
            for t in state.trades
        )
    if case in ("names", "names_by_day"):
        assert counts["skip_limit_up"] > 1
    if case == "audit":
        assert audit and any(r["side"] == "sell" for r in audit)
    if case == "economics":
        assert state.exdiv_economics.applied_ids
        assert any(r["equity"] > r["cash"] + r["holdings"] for r in state.equity_curve)
        assert state.exdiv_economics.receivable_total == 0
        assert state.equity_curve[4]["cash"] > state.equity_curve[3]["cash"]
    if case == "exdiv":
        assert any(t["symbol"] == codes[5] and t["price"] == 9.0 for t in state.trades)
    if audit:
        (output / "audit.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    artifacts = {
        p.name: p.read_bytes()
        for p in output.iterdir()
        if p.name in ("trades.csv", "daily_equity.csv", "summary.txt", "audit.json")
    }
    extra["positions"] = {c: asdict(pos) for c, pos in state.positions.items()}
    extra["cash"] = state.cash
    return {
        "sha256": {n: sha256(b).hexdigest() for n, b in artifacts.items()},
        "canonical": {n: canonical_artifact(n, b) for n, b in artifacts.items()},
        "evidence": dict(reasons=dict(counts), **normalize(extra)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true", required=True)
    parser.parse_args()
    if FIXTURE.exists():
        parser.error("fixture exists; refusing overwrite (migration must not regenerate)")
    with tempfile.TemporaryDirectory(prefix="v7app-baseline-") as temp:
        cases = {c: capture_case(c, Path(temp) / c) for c in CASES}
    payload = {
        "pandas_major_minor": ".".join(pd.__version__.split(".")[:2]),
        "pandas": pd.__version__,
        "contract": "ordered CSV decimal 1e-8; raw writer SHA256",
        "cases": cases,
    }
    with FIXTURE.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"Recorded {len(cases)} new cases: {FIXTURE}")


if __name__ == "__main__":
    main()
