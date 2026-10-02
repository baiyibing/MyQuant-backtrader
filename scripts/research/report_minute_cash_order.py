#!/usr/bin/env python3
"""Replay frozen synthetic X-02 inputs; emit unsorted OFF/ON execution sidecars.

This is a data-free regression report, not a lake backtest or a profit claim.
The fixtures are deliberately shared with the tests so their parameters cannot
quietly diverge from the counterexamples reviewed in the PR.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def money(value):
    return Decimal(str(value)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


def _json(value):
    if hasattr(value, "to_json"):
        return value.to_json(date_format="iso", orient="split")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def _dump(value):
    def normalize(item):
        if isinstance(item, dict):
            return {str(key): normalize(val) for key, val in item.items()}
        if isinstance(item, (list, tuple)):
            return [normalize(val) for val in item]
        return item
    return json.dumps(normalize(value), ensure_ascii=False, indent=2, default=_json) + "\n"


def _clock(row):
    return str(row["date"]).replace("-", ""), row["decision_hm"], {"open": 0, "close": 1, "timer": 2}[row["phase"]]


def _metrics(state, trace):
    residuals = []
    inventory = Counter()
    for index, row in enumerate(trace):
        side = row["side"].upper()
        if side not in {"BUY", "SELL"}:
            assert money(row["cash_before"]) == money(row["cash_after"]), row
            continue
        notional = row["price"] * row["shares"]
        inventory[row.get("code", row.get("symbol"))] += row["shares"] * (1 if side == "BUY" else -1)
        commission = row.get("commission")
        if commission is not None:
            expected = (row["cash_before"] - notional - commission if side == "BUY"
                        else row["cash_before"] + notional - commission)
            if money(expected) != money(row["cash_after"]):
                residuals.append(index)
    inversions = [{"index": i, "previous": trace[i - 1], "current": row}
                  for i, row in enumerate(trace) if i and _clock(row) < _clock(trace[i - 1])]
    counts = Counter(row["side"].upper() for row in trace)
    cash = [row[key] for row in trace for key in ("cash_before", "cash_after")]
    positions = {code: (sum(p.shares for p in pos) if isinstance(pos, list) else pos.shares)
                 for code, pos in state.positions.items()}
    share_residuals = {code: inventory[code] - positions.get(code, 0)
                      for code in inventory.keys() | positions.keys()
                      if inventory[code] != positions.get(code, 0)}
    return {"final_cash": str(money(state.cash)), "event_counts": dict(counts),
                "minimum_cash": str(money(min(cash))) if cash else None,
                "negative_cash_events": sum(money(value) < 0 for value in cash),
                "cash_conservation_residuals": residuals,
                "share_conservation_residuals": share_residuals,
                "first_clock_inversion": inversions[0] if inversions else None,
                "stats": getattr(state, "stats", {}), "equity": state.equity_curve,
                "position_shares": positions,
                "cap_used": {str(key): value for key, value in state.volume_cap.used.items()}
                if state.volume_cap else {}}


def capture_case(name, simulate, kwargs, output):
    legs, traces = {}, {}
    for enabled in (False, True):
        leg = "on" if enabled else "off"
        trace = []
        state = simulate(**kwargs, fix_minute_cash_order=enabled, audit_sink=trace)
        traces[leg] = trace
        legs[leg] = _metrics(state, trace)
        assert not legs[leg]["cash_conservation_residuals"]
        assert not legs[leg]["share_conservation_residuals"]
        assert not legs[leg]["negative_cash_events"]
        if enabled:
            assert legs[leg]["first_clock_inversion"] is None
        (output / f"{name}-{leg}.json").write_text(_dump(trace), encoding="utf-8")
    first = next((i for i, pair in enumerate(zip(traces["off"], traces["on"])) if pair[0] != pair[1]),
                 min(len(traces["off"]), len(traces["on"])))
    legs["first_execution_difference"] = {
        "index": first,
        "off": traces["off"][first] if first < len(traces["off"]) else None,
        "on": traces["on"][first] if first < len(traces["on"]) else None,
        "attribution": "cash/position availability at decision clock; subsequent differences are propagation",
    }
    fields = ("date", "code", "side", "price", "shares", "reason", "hm", "decision_hm", "quote_hm", "phase")
    def fill_rows(leg):
        return [{key: row.get("symbol") if key == "code" and "code" not in row else row.get(key)
                 for key in fields} for row in traces[leg] if row["side"].upper() in {"BUY", "SELL"}]
    off_fills, on_fills = fill_rows("off"), fill_rows("on")
    legs["removed_fills"] = [row for row in off_fills if row not in on_fills]
    legs["added_fills"] = [row for row in on_fills if row not in off_fills]
    if name in {"shared-same-close", "shared-fallback"}:
        assert off_fills == on_fills
        assert legs["off"]["equity"] == legs["on"]["equity"]
    legs["input_parameters_sha256"] = hashlib.sha256(_dump(kwargs).encode()).hexdigest()
    (output / f"{name}-inputs.json").write_text(_dump(kwargs), encoding="utf-8")
    return legs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from backtest.research.csv_minute_backtest import simulate
    from backtest.research.csv_minute_backtest_v7 import simulate_v7
    from tests.minute_cash_fixtures import chronological_case
    from tests.test_v7_cash_chronology import chronological_case as v7_case

    cases = {
        "shared-future": capture_case("shared-future", simulate, chronological_case(), args.output_dir),
        "shared-same-close": capture_case("shared-same-close", simulate, chronological_case(sell_hm=895), args.output_dir),
        "shared-fallback": capture_case("shared-fallback", simulate, chronological_case(sell_hm=893, buy_hm=890), args.output_dir),
        "v7-future": capture_case("v7-future", simulate_v7, v7_case(), args.output_dir),
    }
    source_files = ["backtest/research/csv_minute_backtest.py", "backtest/research/minute_cash_order.py",
                    "backtest/research/csv_minute_backtest_v7.py", "backtest/research/csv_ledger.py",
                    "backtest/research/csv_simulate_loop.py", "backtest/research/minute_audit.py",
                    "tests/fixtures/off_byte_baseline_eff77f3.json"]
    report = {"kind": "synthetic only; real lake NOT VERIFIED", "same_hm_policy": "open before close; independent close sells before close buys; v7 timer after buys",
                  "fallback_order_clock": "target decision_hm; selected earlier quote_hm and capacity bucket",
                  "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
                  "source_sha256": {path: hashlib.sha256((REPO / path).read_bytes()).hexdigest() for path in source_files},
                  "cases": cases, "unexplained_rule_changes": [],
                  "limitations": ["same-bar OHLC approximation", "stale fallback quotes", "X-13 missing-bar economics unchanged", "4090 not verified"]}
    (args.output_dir / "ab-summary.json").write_text(_dump(report), encoding="utf-8")
    print(_dump({name: {leg: {key: case[leg][key] for key in ("final_cash", "event_counts", "minimum_cash")}
                              for leg in ("off", "on")} for name, case in cases.items()}))


if __name__ == "__main__":
    main()
