"""Reference views for L2 analytics: adj factors + prev_close (from stock_data)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb

from common.infra.data_root import resolve_source_parquet


def default_adj_factor_path() -> Path:
    return resolve_source_parquet("adj_factor.parquet")


def register_ref_views(
    con: duckdb.DuckDBPyConnection,
    *,
    adj_factor_path: Optional[str | Path] = None,
) -> dict[str, bool]:
    """Register ``l2_adj_factor`` / ``l2_prev_close`` when the parquet exists.

    ``l2_prev_close.prev_close`` is prior-day ``close_none`` (unadjusted) via LAG.
    ``prev_close_d_domain`` normalizes that raw prev close into **D-day price domain**
    via ``prev_close * cum_factor[D-1] / cum_factor[D]`` (= ``close_front[D-1] / cum[D]``)
    so board-limit templates stay correct on ex-dividend dates (plan §6 #4).
    ``cumulative_adj_factor`` also joins for front-adjusted prices (``Price * factor``).
    """
    path = Path(adj_factor_path) if adj_factor_path else default_adj_factor_path()
    registered = {"l2_adj_factor": False, "l2_prev_close": False}
    if not path.is_file():
        return registered
    pq = path.resolve().as_posix()
    con.execute(
        f"""
        CREATE OR REPLACE VIEW l2_adj_factor AS
        SELECT
          CAST(date AS DATE) AS date,
          CAST(stock_code AS VARCHAR) AS stock_code,
          close_front,
          close_none,
          cumulative_adj_factor,
          adj_factor_back
        FROM read_parquet('{pq}', hive_partitioning=0)
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW l2_prev_close AS
        SELECT
          stock_code,
          date,
          prev_close,
          prev_cum_factor,
          close_none,
          cumulative_adj_factor,
          CASE
            WHEN prev_close IS NULL OR prev_close <= 0 THEN NULL
            WHEN prev_cum_factor IS NULL OR cumulative_adj_factor IS NULL THEN prev_close
            WHEN cumulative_adj_factor = 0 THEN NULL
            ELSE prev_close * prev_cum_factor / cumulative_adj_factor
          END AS prev_close_d_domain
        FROM (
          SELECT
            stock_code,
            date,
            LAG(close_none) OVER (
              PARTITION BY stock_code ORDER BY date
            ) AS prev_close,
            LAG(cumulative_adj_factor) OVER (
              PARTITION BY stock_code ORDER BY date
            ) AS prev_cum_factor,
            close_none,
            cumulative_adj_factor
          FROM l2_adj_factor
        ) _
        """
    )
    registered["l2_adj_factor"] = True
    registered["l2_prev_close"] = True
    return registered
