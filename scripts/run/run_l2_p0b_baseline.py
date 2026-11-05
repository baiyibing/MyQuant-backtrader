#!/usr/bin/env python3
"""Host CLI defaults for infra's manual offline L2 research queries."""
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

from l2_analytics._infra import require_l2  # noqa: E402
from l2_analytics.db import default_parquet_root  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline L2 A/B/C/D latency baseline")
    parser.add_argument("--parquet-root", default="")
    parser.add_argument("--date", default="2026-07-17")
    parser.add_argument("--memory-limit", default="18GB")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--adj-factor-path", default=None, help="optional offline reference parquet")
    parser.add_argument("--raw-bc", action="store_true",
                        help="also time B/C against raw ticks when pre-aggregates exist")
    args = parser.parse_args(argv)

    implementation = require_l2("research.queries.p0b_baseline")
    root = Path(args.parquet_root) if args.parquet_root else default_parquet_root()
    output = Path(args.out_json) if args.out_json else root / f"p0b_baseline_{args.date}.json"
    options = ["--parquet-root", str(root), "--date", args.date,
               "--memory-limit", args.memory_limit, "--out-json", str(output)]
    if args.raw_bc:
        options.append("--raw-bc")
    if args.adj_factor_path is not None:
        options.extend(["--adj-factor-path", args.adj_factor_path])
    return implementation.main(options)


if __name__ == "__main__":
    raise SystemExit(main())
