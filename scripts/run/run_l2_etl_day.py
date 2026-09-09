#!/usr/bin/env python3
"""CLI: one-day L2 CSV -> Parquet ETL (P0a).

Example:
  python scripts/run/run_l2_etl_day.py ^
    --source C:\\Users\\Thinkpad\\Downloads\\2026-07-17
"""

from __future__ import annotations

import argparse
import importlib.util as _ilu
import sys
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

from l2_analytics.etl_day import etl_one_day, result_to_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="L2 tick one-day ETL (DuckDB)")
    p.add_argument(
        "--source",
        required=True,
        help="Day directory named YYYY-MM-DD containing *.csv",
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
    p.add_argument("--max-files", type=int, default=0, help="Smoke: only first N csv")
    p.add_argument(
        "--gap-free-sample",
        type=int,
        default=0,
        help="0=all files (default); >0=size-stratified sample of that many CSVs",
    )
    p.add_argument("--no-gap-free", action="store_true")
    args = p.parse_args(argv)

    result = etl_one_day(
        args.source,
        out_root=args.out_root or None,
        memory_limit=args.memory_limit,
        threads=(args.threads or None),
        chunk_files=args.chunk_files,
        force=args.force,
        validate_gap_free=not args.no_gap_free,
        gap_free_sample=args.gap_free_sample,
        max_files=args.max_files,
    )
    print(result_to_json(result))
    return 0 if result.gap_free_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
