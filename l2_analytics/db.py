"""DuckDB session helpers for L2 analytics views."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import duckdb

from common.infra.data_root import resolve_l2_parquet_root
from l2_analytics.paths import (
    has_hive_main,
    has_legacy_flat_main,
    hive_cluster_agg_glob,
    hive_daily_metrics_glob,
    hive_main_glob,
    hive_order_glob,
    legacy_flat_main_glob,
    legacy_flat_order_glob,
)
from l2_analytics.ref_data import register_ref_views


def default_parquet_root() -> Path:
    """L2 tick parquet root under market-data tree (not ``data/`` business DBs).

    Single source: delegates to ``resolve_l2_parquet_root()`` which honors
    ``OSKH_L2_PARQUET_ROOT`` env var (L2-specific override, e.g. ``F:\\stock_data\\l2_parquet``)
    and falls back to ``{resolve_data_root()}/stock_data/l2_parquet`` (``OSKH_DATA_ROOT``).
    """
    return resolve_l2_parquet_root()


def _union_parquet_view(con: duckdb.DuckDBPyConnection, view: str, globs: list[str]) -> None:
    """CREATE VIEW from one or more read_parquet globs (UNION ALL if multi)."""
    if not globs:
        raise ValueError(f"no globs for view {view}")
    if len(globs) == 1:
        body = f"SELECT * FROM read_parquet('{globs[0]}', hive_partitioning=0)"
    else:
        parts = [
            f"SELECT * FROM read_parquet('{g}', hive_partitioning=0)" for g in globs
        ]
        body = "\nUNION ALL BY NAME\n".join(parts)
    con.execute(f"CREATE OR REPLACE VIEW {view} AS {body}")


def connect(
    *,
    parquet_root: Optional[str | Path] = None,
    memory_limit: str = "18GB",
    threads: Optional[int] = None,
    temp_directory: Optional[str | Path] = None,
    adj_factor_path: Optional[str | Path] = None,
    register_adj: bool = True,
) -> duckdb.DuckDBPyConnection:
    """Open in-memory DuckDB and register ``l2_main`` / ``l2_order`` views.

    Prefers hive ``date=*/main.parquet``; also unions legacy flat
    ``*.main.parquet`` when both exist (migration window).
    ``hive_partitioning=0`` — ``date`` is a data column from ETL (not only dir).
    """
    root = Path(parquet_root) if parquet_root else default_parquet_root()
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"parquet_root not found: {root}")

    main_globs: list[str] = []
    order_globs: list[str] = []
    if has_hive_main(root):
        main_globs.append(hive_main_glob(root))
        order_globs.append(hive_order_glob(root))
    if has_legacy_flat_main(root):
        main_globs.append(legacy_flat_main_glob(root))
        order_globs.append(legacy_flat_order_glob(root))
    if not main_globs:
        # Fresh empty root: register empty-friendly hive glob (fails on first
        # query until ETL writes). Prefer explicit error on connect for clarity.
        raise FileNotFoundError(
            f"no L2 parquet under {root} (expected date=*/main.parquet or *.main.parquet)"
        )

    n_threads = threads if threads is not None else max(1, (os.cpu_count() or 4) - 1)
    tmp = Path(temp_directory) if temp_directory else (root / "_duckdb_tmp")
    tmp.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(database=":memory:")
    con.execute(f"SET memory_limit='{memory_limit}'")
    con.execute(f"SET threads={int(n_threads)}")
    con.execute(f"SET temp_directory='{tmp.as_posix()}'")
    _union_parquet_view(con, "l2_main", main_globs)
    _union_parquet_view(con, "l2_order", order_globs)

    dm_globs: list[str] = []
    if any(root.glob("date=*/daily_metrics.parquet")):
        dm_globs.append(hive_daily_metrics_glob(root))
    if any(root.glob("*.daily_metrics.parquet")):
        dm_globs.append((root / "*.daily_metrics.parquet").as_posix())
    if dm_globs:
        _union_parquet_view(con, "l2_daily_metrics", dm_globs)

    ca_globs: list[str] = []
    if any(root.glob("date=*/cluster_agg.parquet")):
        ca_globs.append(hive_cluster_agg_glob(root))
    if any(root.glob("*.cluster_agg.parquet")):
        ca_globs.append((root / "*.cluster_agg.parquet").as_posix())
    if ca_globs:
        _union_parquet_view(con, "l2_cluster_agg", ca_globs)

    if register_adj:
        register_ref_views(con, adj_factor_path=adj_factor_path)
    return con
