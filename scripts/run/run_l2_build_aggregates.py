#!/usr/bin/env python3
"""P1 batch 3: build persisted per-day L2 pre-aggregates (idempotent).

Builds ``{date}.daily_metrics.parquet`` / ``{date}.cluster_agg.parquet`` from the
existing tick parquet under ``l2_parquet``. No ETL rerun required.
"""

from __future__ import annotations

import argparse
import importlib.util as _ilu
import json
import sys
from pathlib import Path
from typing import Any

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

from l2_analytics.aggregates import build_all_aggregates  # noqa: E402
from l2_analytics.db import default_parquet_root  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--parquet-root", default="")
    p.add_argument("--date", action="append", default=[], help="repeatable; default = all manifest dates")
    p.add_argument("--force", action="store_true")
    p.add_argument("--memory-limit", default="18GB")
    p.add_argument("--out-json", default="")
    args = p.parse_args(argv)

    root = Path(args.parquet_root) if args.parquet_root else default_parquet_root()
    dates = list(args.date) if args.date else None
    results = build_all_aggregates(
        root, dates=dates, force=args.force, memory_limit=args.memory_limit
    )
    report: dict[str, Any] = {"parquet_root": str(root), "results": results}

    out_path = Path(args.out_json) if args.out_json else root / "agg_build.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[wrote] {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
