#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C16 offline spot-check: dump adj_factor for a few symbols (no QMT).

Default symbols: 600000.SH / 000001.SZ / 300750.SZ. Human still compares against
broker quote screenshots by 2026-07-31; this script only surfaces local parquet.

Usage:
  python scripts/diagnostics/dump_adj_factor_spot_check.py
  python scripts/diagnostics/dump_adj_factor_spot_check.py --date 20260724
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _P

_sb_dir = next((_p for _p in _P(__file__).resolve().parents if _p.name == "scripts"), _P(__file__).resolve().parent.parent)
_sb_spec = _ilu.spec_from_file_location("_script_bootstrap", _sb_dir / "_script_bootstrap.py")
if _sb_spec is None or _sb_spec.loader is None:
    raise ImportError("_script_bootstrap unavailable")
_bs_mod = _ilu.module_from_spec(_sb_spec)
_sys.modules["_script_bootstrap"] = _bs_mod
_sb_spec.loader.exec_module(_bs_mod)
_bs_mod.ensure_repo_on_syspath(__file__)

_DEFAULT_SYMBOLS = ("600000.SH", "000001.SZ", "300750.SZ")


def _normalize_date(raw: str) -> str:
    text = str(raw or "").strip().replace("-", "")
    if len(text) == 8 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    return str(raw or "").strip()


def dump_rows(symbols: List[str], date_iso: str) -> Dict[str, Any]:
    import pandas as pd

    from oskh_factors.chip.adj_factor import get_adj_factor
    from oskh_factors.chip.paths import stock_data_path

    parquet = str(stock_data_path("adj_factor.parquet"))
    table = None
    try:
        table = pd.read_parquet(parquet)
    except Exception as exc:  # noqa: BLE001 — diagnostic dump
        table = None
        table_error = f"{type(exc).__name__}: {exc}"
    else:
        table_error = None

    rows_out: List[Dict[str, Any]] = []
    for sym in symbols:
        entry: Dict[str, Any] = {"symbol": sym, "date": date_iso}
        try:
            entry["cumulative_adj_factor"] = float(get_adj_factor(sym, date_iso, strict=False))
            entry["ok"] = True
        except Exception as exc:  # noqa: BLE001 — diagnostic dump
            entry["ok"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"
        if table is not None and not table.empty and "stock_code" in table.columns and "date" in table.columns:
            d = pd.to_datetime(table["date"], errors="coerce")
            target = pd.Timestamp(date_iso)
            hit = table[(table["stock_code"].astype(str) == sym) & (d == target)]
            if not hit.empty:
                rec = hit.iloc[0]
                for key in ("close_front", "close_none", "cumulative_adj_factor", "adj_factor_back"):
                    if key in hit.columns:
                        try:
                            val = float(rec[key])
                        except (TypeError, ValueError):
                            entry[key] = rec[key]
                            continue
                        entry[key] = None if (val != val) else val  # NaN → null
        rows_out.append(entry)
    out: Dict[str, Any] = {
        "parquet_path": parquet,
        "date": date_iso,
        "rows": rows_out,
        "note": "offline dump only; human broker quote对照 still required for C16 close",
    }
    if table_error:
        out["table_error"] = table_error
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump adj_factor spot-check rows (C16 prep)")
    parser.add_argument("--date", default="20260724", help="YYYYMMDD or YYYY-MM-DD")
    parser.add_argument(
        "--symbols",
        default=",".join(_DEFAULT_SYMBOLS),
        help="Comma-separated symbols",
    )
    args = parser.parse_args()
    symbols = [s.strip() for s in str(args.symbols).split(",") if s.strip()]
    date_iso = _normalize_date(args.date)
    report = dump_rows(symbols, date_iso)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    ok_n = sum(1 for r in report["rows"] if r.get("ok"))
    print(f"\nadj_factor spot-check: {ok_n}/{len(report['rows'])} ok", file=sys.stderr)
    return 0 if ok_n == len(report["rows"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
