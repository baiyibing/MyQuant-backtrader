#!/usr/bin/env python3
"""CLI: per-price-level net inflow for one stock x date (L2 ticks).

Per-price breakdown of the same net_inflow convention as ``sql/net_inflow.sql``
(Type=B 主动买 / Type=S 主动卖, continuous auction only, stock only), but
grouped by ``Price`` (or by price-bin of configurable width) instead of
collapsing to one row per stock x date.

Columns:
  stock_code, date, price (or price_bin), buy_notional, sell_notional,
  net_inflow, buy_volume, sell_volume, ticks

Example:
  python scripts/run/run_l2_net_inflow_by_price.py ^
    --date 2026-07-17 --stock-code 000001.SZ --out-csv net_inflow_000001.csv

Notes:
- 口径与 net_inflow.sql 一致：Type=B 主动买 / Type=S 主动卖，仅连续竞价
  (session LIKE 'continuous%')，仅 instrument_type='stock'。
- 未对标东财/同花顺（数据约定口径，非厂商口径）。
- Price 在 ETL 已 TRY_CAST(DECIMAL(10,3))，哨兵/离群值 → NULL，被 SUM 自然排除。
"""

from __future__ import annotations

import argparse
import csv
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

from l2_analytics.db import connect, default_parquet_root  # noqa: E402

# Identifier allowlist for order_by (mirrors templates._ORDER_BY_RE scope).
_ALLOWED_ORDER_BY = {
    "price", "price_bin", "buy_notional", "sell_notional", "net_inflow",
    "buy_volume", "sell_volume", "volume", "ticks",
}


def _build_sql(
    *,
    date: str,
    stock_code: str,
    bin_width: float,
    order_by: str,
    limit: int,
) -> str:
    """Build the per-price (or per-price-bin) net inflow query.

    ``bin_width <= 0`` → group by exact ``Price`` (DECIMAL(10,3)).
    ``bin_width > 0``  → group by ``FLOOR(Price / width) * width`` as ``price_bin``.
    """
    if bin_width > 0:
        # Round to 3 decimals to avoid float noise in bin edges (A 股 tick = 0.01).
        bin_expr = f"ROUND(FLOOR(Price / {bin_width}) * {bin_width}, 3)"
        price_col = f"{bin_expr} AS price_bin"
        group_col = "price_bin"
        order_col_default = "price_bin"
    else:
        price_col = "Price AS price"
        group_col = "Price"
        order_col_default = "Price"

    ob = order_by.strip() or order_col_default
    if ob not in _ALLOWED_ORDER_BY:
        raise ValueError(
            f"invalid order_by {ob!r}; allowed={sorted(_ALLOWED_ORDER_BY)}"
        )
    direction = "DESC" if ob in ("net_inflow", "buy_notional", "sell_notional",
                                  "buy_volume", "sell_volume", "volume", "ticks") else "ASC"
    limit_clause = f"LIMIT {int(limit)}" if limit and limit > 0 else ""

    return f"""
    SELECT
      stock_code,
      date,
      {price_col},
      SUM(CASE WHEN Type = 'B' THEN Volume * Price ELSE 0 END) AS buy_notional,
      SUM(CASE WHEN Type = 'S' THEN Volume * Price ELSE 0 END) AS sell_notional,
      SUM(CASE WHEN Type = 'B' THEN Volume * Price ELSE -Volume * Price END) AS net_inflow,
      SUM(CASE WHEN Type = 'B' THEN Volume ELSE 0 END) AS buy_volume,
      SUM(CASE WHEN Type = 'S' THEN Volume ELSE 0 END) AS sell_volume,
      SUM(Volume) AS volume,
      COUNT(*) AS ticks
    FROM l2_main
    WHERE instrument_type = 'stock'
      AND session LIKE 'continuous%'
      AND date = DATE '{date}'
      AND stock_code = '{stock_code}'
      AND Price IS NOT NULL
    GROUP BY stock_code, date, {group_col}
    ORDER BY {ob} {direction}
    {limit_clause}
    """.strip()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Per-price-level net inflow for one stock x date (L2 ticks)"
    )
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--stock-code", required=True, help="canonical, e.g. 000001.SZ")
    p.add_argument("--parquet-root", default="")
    p.add_argument("--memory-limit", default="18GB")
    p.add_argument(
        "--bin-width", type=float, default=0.0,
        help="price bin width in yuan; 0 = exact price (default)",
    )
    p.add_argument(
        "--order-by", default="",
        help=f"one of {sorted(_ALLOWED_ORDER_BY)}; default = price ASC / net_inflow DESC",
    )
    p.add_argument("--limit", type=int, default=0, help="0 = all rows")
    p.add_argument("--out-json", default="", help="write JSON report to this path")
    p.add_argument("--out-csv", default="", help="write rows to this CSV path")
    args = p.parse_args(argv)

    root = Path(args.parquet_root) if args.parquet_root else default_parquet_root()
    temp_dir = root / "_duckdb_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    con = connect(parquet_root=root, memory_limit=args.memory_limit, temp_directory=temp_dir)
    try:
        sql = _build_sql(
            date=args.date,
            stock_code=args.stock_code,
            bin_width=args.bin_width,
            order_by=args.order_by,
            limit=args.limit,
        )
        rows = con.execute(sql).fetchall()

        # Full-day totals (independent of limit/order_by) for cross-check vs
        # l2_daily_metrics convention.
        totals_row = con.execute(f"""
            SELECT
              SUM(CASE WHEN Type = 'B' THEN Volume * Price ELSE 0 END),
              SUM(CASE WHEN Type = 'S' THEN Volume * Price ELSE 0 END),
              SUM(CASE WHEN Type = 'B' THEN Volume * Price ELSE -Volume * Price END),
              SUM(Volume), COUNT(*)
            FROM l2_main
            WHERE instrument_type = 'stock'
              AND session LIKE 'continuous%'
              AND date = DATE '{args.date}'
              AND stock_code = '{args.stock_code}'
              AND Price IS NOT NULL
        """).fetchone()
    finally:
        con.close()

    if totals_row is None:
        totals_row = (0.0, 0.0, 0.0, 0, 0)

    columns = [
        "stock_code", "date", "price" if args.bin_width <= 0 else "price_bin",
        "buy_notional", "sell_notional", "net_inflow",
        "buy_volume", "sell_volume", "volume", "ticks",
    ]

    from decimal import Decimal
    from datetime import date as _date

    def _conv(v: Any) -> Any:
        if isinstance(v, Decimal):
            return float(v)
        if isinstance(v, _date):
            return v.isoformat()
        return v

    records = [dict(zip(columns, (_conv(v) for v in r))) for r in rows]

    # Headline totals (full-day, independent of limit/order_by) for cross-check
    # vs l2_daily_metrics convention.
    total_buy = float(totals_row[0] or 0)
    total_sell = float(totals_row[1] or 0)
    total_net = float(totals_row[2] or 0)
    total_volume = int(totals_row[3] or 0)
    total_ticks = int(totals_row[4] or 0)

    report: dict[str, Any] = {
        "date": args.date,
        "stock_code": args.stock_code,
        "bin_width": args.bin_width,
        "order_by": args.order_by or ("price_bin" if args.bin_width > 0 else "price"),
        "limit": args.limit,
        "n_price_levels": len(records),
        "totals": {
            "buy_notional": total_buy,
            "sell_notional": total_sell,
            "net_inflow": total_net,
            "volume": total_volume,
            "ticks": total_ticks,
        },
        "rows": records,
    }

    out_json = Path(args.out_json) if args.out_json else None
    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    if args.out_csv:
        csv_path = Path(args.out_csv)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(columns)
            for r in records:
                w.writerow([r[c] for c in columns])

    print(json.dumps(
        {k: v for k, v in report.items() if k != "rows"},
        ensure_ascii=False, indent=2,
    ))
    print(f"[rows] {len(records)} price levels")
    if out_json:
        print(f"[wrote] {out_json}")
    if args.out_csv:
        print(f"[wrote] {Path(args.out_csv).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
