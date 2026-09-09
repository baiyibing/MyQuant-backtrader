#!/usr/bin/env python3
"""CLI: multi-day L2 CSV -> Parquet ETL orchestrator (P1).

Discovers YYYY-MM-DD subdirectories under --source-root and runs
etl_one_day() for each. Idempotent (skips days with manifest match).

Example:
  python scripts/run/run_l2_etl_multi_day.py ^
    --source-root C:\\Users\\Thinkpad\\Downloads --out-root stock_data/l2_parquet
"""

from __future__ import annotations

import argparse
import importlib.util as _ilu
import json
import re
import sys
import time
from pathlib import Path

_sb_dir = next(
    (_p for _p in Path(__file__).resolve().parents if _p.name == "scripts"),
    Path(__file__).resolve().parent,
)
_sb_spec = _ilu.spec_from_file_location("_script_bootstrap", _sb_dir / "_script_bootstrap.py")
if _sb_spec is None or _sb_spec.loader is None:
    raise ImportError("_script_bootstrap unavailable")
_bs_mod = _ilu.module_from_spec(_sb_spec)
sys.modules["_script_bootstrap"] = _bs_mod
_sb_spec.loader.exec_module(_bs_mod)
_bs_mod.ensure_repo_on_syspath(__file__)

from l2_analytics.etl_day import DayEtlResult, etl_one_day  # noqa: E402

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _discover_dates(source_root: Path) -> list[str]:
    return sorted(
        d.name for d in source_root.iterdir() if d.is_dir() and _DATE_RE.match(d.name)
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="L2 tick multi-day ETL orchestrator (DuckDB)")
    p.add_argument(
        "--source-root",
        required=True,
        help="Parent directory containing YYYY-MM-DD subdirs with *.csv",
    )
    p.add_argument(
        "--dates",
        default="",
        help="Comma-separated explicit dates (overrides auto-discovery)",
    )
    p.add_argument(
        "--out-root",
        default="",
        help="Output root (default: OSKH_L2_PARQUET_ROOT env var, else resolve_data_root()/stock_data/l2_parquet)",
    )
    p.add_argument("--memory-limit", default="18GB")
    p.add_argument("--threads", type=int, default=0, help="0 = cpu_count-1")
    p.add_argument("--chunk-files", type=int, default=400)
    p.add_argument("--force", action="store_true")
    p.add_argument("--max-files", type=int, default=0, help="Smoke: only first N csv per day")
    p.add_argument("--gap-free-sample", type=int, default=50)
    p.add_argument("--no-gap-free", action="store_true")
    p.add_argument("--stop-on-error", action="store_true", help="Abort on first failure")
    args = p.parse_args(argv)

    source_root = Path(args.source_root).resolve()
    if not source_root.is_dir():
        print(f"[l2_multi] ERROR: source-root not found: {source_root}", file=sys.stderr)
        return 3

    if args.dates.strip():
        dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    else:
        dates = _discover_dates(source_root)

    if not dates:
        print(f"[l2_multi] no YYYY-MM-DD subdirs under {source_root}", file=sys.stderr)
        return 3

    print(f"[l2_multi] {len(dates)} date(s) to process: {dates[0]}..{dates[-1]}", flush=True)
    t0 = time.perf_counter()

    results: list[DayEtlResult] = []
    errors: list[dict[str, str]] = []
    gap_free_failures = False

    for i, date in enumerate(dates):
        day_dir = source_root / date
        if not day_dir.is_dir():
            errors.append({"date": date, "error": f"directory not found: {day_dir}"})
            if args.stop_on_error:
                break
            continue

        print(f"[l2_multi] ({i + 1}/{len(dates)}) {date} ...", flush=True)
        try:
            r = etl_one_day(
                day_dir,
                out_root=args.out_root or None,
                memory_limit=args.memory_limit,
                threads=(args.threads or None),
                chunk_files=args.chunk_files,
                force=args.force,
                validate_gap_free=not args.no_gap_free,
                gap_free_sample=args.gap_free_sample,
                max_files=args.max_files,
            )
            results.append(r)
            if not r.gap_free_ok:
                gap_free_failures = True
            status = "SKIP" if r.skipped else f"{r.rows_main:,} rows"
            print(f"[l2_multi] ({i + 1}/{len(dates)}) {date}: {status} ({r.elapsed_s:.1f}s)", flush=True)
        except Exception as exc:
            errors.append({"date": date, "error": str(exc)})
            print(f"[l2_multi] ({i + 1}/{len(dates)}) {date}: FAILED — {exc}", file=sys.stderr, flush=True)
            if args.stop_on_error:
                break

    elapsed = time.perf_counter() - t0
    summary = {
        "total": len(dates),
        "succeeded": len(results),
        "failed": len(errors),
        "skipped": sum(1 for r in results if r.skipped),
        "elapsed_s": round(elapsed, 1),
        "errors": errors,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

    if errors:
        return 3
    if gap_free_failures:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
