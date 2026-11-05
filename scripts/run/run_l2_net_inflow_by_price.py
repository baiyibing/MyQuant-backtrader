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
    parser = argparse.ArgumentParser(
        description="Per-price-level net inflow for one stock x date (L2 ticks)",
    )
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--stock-code", required=True, help="canonical, e.g. 000001.SZ")
    parser.add_argument("--parquet-root", default="")
    parser.add_argument("--memory-limit", default="18GB")
    parser.add_argument("--bin-width", type=float, default=0.0,
                        help="price bin width in yuan; 0 = exact price")
    parser.add_argument("--order-by", default="", help="price/price_bin, notional, volume or ticks")
    parser.add_argument("--limit", type=int, default=0, help="0 = all rows")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-csv", default="")
    args = parser.parse_args(argv)

    implementation = require_l2("research.queries.net_inflow_by_price")
    root = Path(args.parquet_root) if args.parquet_root else default_parquet_root()
    return implementation.main([
        "--parquet-root", str(root), "--date", args.date, "--stock-code", args.stock_code,
        "--memory-limit", args.memory_limit, "--bin-width", str(args.bin_width),
        "--order-by", args.order_by, "--limit", str(args.limit),
        "--out-json", args.out_json, "--out-csv", args.out_csv,
    ])


if __name__ == "__main__":
    raise SystemExit(main())
