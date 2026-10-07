#!/usr/bin/env python3
"""Opt-in, synthetic-only profiling of the public minute simulate entry."""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
from pathlib import Path
import pstats
import sys
import time

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.research.bench_minute_simulate_hotpath import _synthetic_inputs, sim


def run_profile(out_dir: Path, *, names: int = 16, days: int = 30,
                minutes: int = 240, top: int = 20) -> dict:
    """Reuse deterministic analytic fixtures (no RNG); write only two reports."""
    if min(names, days, minutes, top) <= 0 or days < 3 or minutes > 240:
        raise ValueError("positive sizes required; days >= 3; minutes <= 240")
    started = time.perf_counter()
    minute, daily, pools, labels, calendar = _synthetic_inputs(
        days, names, minutes, min(10, days - 1))
    build_s = time.perf_counter() - started
    profiler = cProfile.Profile()
    # Explicitly isolate this harness from an ambient numba opt-in. Restore it
    # even on failure; neither scan functions nor engine globals are wrapped.
    key = "CSV_SCAN_HELD_DAY_BACKEND"
    previous = os.environ.get(key)
    os.environ[key] = "python"
    try:
        started = time.perf_counter()
        state = profiler.runcall(
            sim.simulate, minute, daily, pools,
            calendar[0].strftime("%Y%m%d"), calendar[-1].strftime("%Y%m%d"),
            strategy="version6", total_cash=1e12, daily_quota=1e9,
            pool_names=labels)
        simulate_s = time.perf_counter() - started
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous
    started = time.perf_counter()
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs().sort_stats("cumulative").print_stats(top)
    rows = []
    for (filename, line, function), (primitive, calls, own, cumulative, _) in stats.stats.items():
        rows.append(dict(function=function, file=filename, line=line, calls=calls,
                         primitive_calls=primitive, self_s=own, cumulative_s=cumulative,
                         cumulative_share=cumulative / simulate_s))
    rows.sort(key=lambda row: row["cumulative_s"], reverse=True)
    scan_s = sum(row["cumulative_s"] for row in rows if row["function"] == "scan_held_day")
    report = dict(
        schema_version=1, scope="synthetic; machine-local; not representative",
        scenario=dict(names=names, days=days, minutes=minutes, strategy="version6",
                      generator="existing analytic deterministic builder; no RNG"),
        backend=dict(requested="python", effective="python"),
        stages=dict(input_build_and_frame_conversion_s=build_s,
                    frame_conversion_s=None, simulate_wall_s=simulate_s,
                    scan_profile_cumulative_s=scan_s),
        outcome=dict(buys=state.stats["buys"], trades=len(state.trades),
                     positions=sum(len(lots) for lots in state.positions.values())),
        profile_top=rows[:top],
        notes=["Build and frame conversion are inseparable in the reused builder.",
               "Scan is nested cumulative cProfile time, not an independent wall stage.",
               "Cumulative shares overlap; profiling overhead included; no warmup.",
               "Output assembly means report construction, not engine ledger assembly."])
    report["stages"]["output_assembly_s"] = time.perf_counter() - started
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "profile.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out_dir / "profile.txt").write_text(report["scope"] + "\n" + stream.getvalue(), encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--names", type=int, default=16)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--minutes", type=int, default=240)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        run_profile(args.out_dir, names=args.names, days=args.days,
                    minutes=args.minutes, top=args.top)
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
