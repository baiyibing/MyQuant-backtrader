"""P1 batch 3: persisted per-day pre-aggregates (plan §3.6.1, highest-ROI "更快").

Build small per-day tables once from the existing ``l2_main`` / ``l2_order`` tick
parquet so the client's repeated questions hit tiny tables (sub-ms) instead of
re-scanning ~1.6GB/day of ticks. No ETL rerun required — aggregates are derived
from whatever hive / legacy flat tick parquet already exist.

Storage layout (hive, v5.9+):
  - ``date=YYYY-MM-DD/daily_metrics.parquet`` -> view ``l2_daily_metrics``
  - ``date=YYYY-MM-DD/cluster_agg.parquet``   -> view ``l2_cluster_agg``
Legacy flat ``{date}.daily_metrics.parquet`` is still readable via ``db.connect``.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import duckdb

from l2_analytics.db import connect, default_parquet_root
from l2_analytics.paths import (
    cluster_agg_path,
    daily_metrics_path,
    day_dir,
)

# #10 cluster threshold — kept identical to the large_order_cluster template
# HAVING so the materialized table stays small (只留大单聚簇).
_CLUSTER_MIN_FILLS = 5
_CLUSTER_MIN_NOTIONAL = 1_000_000

# #9 headline reproducible metrics per stock_code x date, stock + continuous 口径
# (matches vwap / net_inflow template defaults). $date binds the trading day.
DAILY_METRICS_SQL = """
SELECT
  stock_code,
  date,
  SUM(Volume * Price) / NULLIF(SUM(Volume), 0) AS vwap,
  SUM(CASE WHEN Type = 'B' THEN Volume * Price ELSE -Volume * Price END) AS net_inflow,
  SUM(CASE WHEN Type = 'B' THEN Volume * Price ELSE 0 END) AS buy_notional,
  SUM(CASE WHEN Type = 'S' THEN Volume * Price ELSE 0 END) AS sell_notional,
  SUM(Volume) AS volume,
  COUNT(*) AS ticks
FROM l2_main
WHERE instrument_type = 'stock'
  AND session LIKE 'continuous%'
  AND date = CAST($date AS DATE)
GROUP BY stock_code, date
ORDER BY stock_code
"""

# #10 拆单聚簇 per stock_code x date x SaleOrderID, materialized with the default
# HAVING threshold. $date binds the trading day.
CLUSTER_AGG_SQL = f"""
SELECT
  o.stock_code,
  o.date,
  o.SaleOrderID,
  COUNT(*) AS fill_count,
  SUM(m.Volume) AS total_volume,
  SUM(m.Volume * m.Price) AS total_notional,
  MIN(m.TranID) AS first_tran_id,
  MAX(m.TranID) AS last_tran_id
FROM l2_order o
INNER JOIN l2_main m
  ON o.stock_code = m.stock_code AND o.date = m.date AND o.TranID = m.TranID
WHERE m.instrument_type = 'stock'
  AND m.session LIKE 'continuous%'
  AND m.date = CAST($date AS DATE)
GROUP BY o.stock_code, o.date, o.SaleOrderID
HAVING COUNT(*) >= {_CLUSTER_MIN_FILLS} OR SUM(m.Volume * m.Price) >= {_CLUSTER_MIN_NOTIONAL}
ORDER BY o.stock_code, o.SaleOrderID
"""


def _copy_to_parquet(con: duckdb.DuckDBPyConnection, select_sql: str, date: str, out: Path) -> int:
    """COPY (select_sql bound on $date) TO out; return row count written."""
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    con.execute(
        f"COPY ({select_sql}) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)",
        {"date": date},
    )
    os.replace(tmp, out)
    # Drop legacy flat agg if present (migration cleanup).
    if out.parent.name.startswith("date="):
        legacy_flat = out.parent.parent / f"{date}.{out.name}"
        if legacy_flat.is_file():
            legacy_flat.unlink()
    return int(con.execute(f"SELECT count(*) FROM read_parquet('{out.as_posix()}')").fetchone()[0])


def build_aggregates_for_date(
    con: duckdb.DuckDBPyConnection,
    *,
    date: str,
    out_root: str | Path,
    force: bool = False,
) -> dict[str, Any]:
    """Build both per-day aggregate parquet for one date from ``l2_main`` / ``l2_order``.

    Skips when the target files already exist and ``force`` is False. An empty day
    (0 daily-metrics rows) writes no file and is reported as ``skipped`` with 0 rows.
    """
    root = Path(out_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    day_dir(root, date).mkdir(parents=True, exist_ok=True)
    dm_path = daily_metrics_path(root, date)
    ca_path = cluster_agg_path(root, date)

    if not force and dm_path.is_file() and ca_path.is_file():
        return {
            "date": date,
            "daily_metrics_rows": int(
                con.execute(f"SELECT count(*) FROM read_parquet('{dm_path.as_posix()}')").fetchone()[0]
            ),
            "cluster_agg_rows": int(
                con.execute(f"SELECT count(*) FROM read_parquet('{ca_path.as_posix()}')").fetchone()[0]
            ),
            "daily_metrics_path": str(dm_path),
            "cluster_agg_path": str(ca_path),
            "daily_metrics_s": 0.0,
            "cluster_agg_s": 0.0,
            "skipped": True,
        }

    # Empty-day guard: if there are no stock/continuous ticks for the date, skip
    # both builds (leave no files) so the multi-day loop doesn't choke.
    has_rows = int(
        con.execute(
            "SELECT count(*) FROM l2_main WHERE instrument_type = 'stock' "
            "AND session LIKE 'continuous%' AND date = CAST($date AS DATE)",
            {"date": date},
        ).fetchone()[0]
    )
    if has_rows == 0:
        for stale in (dm_path, ca_path):
            if stale.is_file():
                stale.unlink()
        return {
            "date": date,
            "daily_metrics_rows": 0,
            "cluster_agg_rows": 0,
            "daily_metrics_path": str(dm_path),
            "cluster_agg_path": str(ca_path),
            "daily_metrics_s": 0.0,
            "cluster_agg_s": 0.0,
            "skipped": True,
        }

    t0 = time.perf_counter()
    dm_rows = _copy_to_parquet(con, DAILY_METRICS_SQL.strip(), date, dm_path)
    dm_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    ca_rows = _copy_to_parquet(con, CLUSTER_AGG_SQL.strip(), date, ca_path)
    ca_s = time.perf_counter() - t1

    return {
        "date": date,
        "daily_metrics_rows": dm_rows,
        "cluster_agg_rows": ca_rows,
        "daily_metrics_path": str(dm_path),
        "cluster_agg_path": str(ca_path),
        "daily_metrics_s": dm_s,
        "cluster_agg_s": ca_s,
        "skipped": False,
    }


def _dates_from_manifest(root: Path) -> list[str]:
    manifest = root / "_manifest.jsonl"
    if not manifest.is_file():
        return []
    dates: list[str] = []
    with manifest.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            d = obj.get("date")
            if d:
                dates.append(str(d))
    return sorted(set(dates))


def build_all_aggregates(
    parquet_root: Optional[str | Path] = None,
    *,
    dates: Optional[list[str]] = None,
    force: bool = False,
    memory_limit: str = "18GB",
) -> list[dict[str, Any]]:
    """Build aggregates for the given dates (or all manifest dates) under one connection."""
    root = Path(parquet_root).resolve() if parquet_root else default_parquet_root()
    target_dates = list(dates) if dates else _dates_from_manifest(root)
    con = connect(parquet_root=root, memory_limit=memory_limit)
    try:
        return [
            build_aggregates_for_date(con, date=d, out_root=root, force=force)
            for d in target_dates
        ]
    finally:
        con.close()
