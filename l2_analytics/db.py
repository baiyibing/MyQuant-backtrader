"""Host path selection for infra's offline L2 DuckDB research session."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from l2_analytics._infra import require_l2
from l2_analytics.ref_data import default_adj_factor_path

if TYPE_CHECKING:
    import duckdb


def default_parquet_root() -> Path:
    from common.infra.data_root import resolve_l2_parquet_root

    return resolve_l2_parquet_root()


def connect(
    *,
    parquet_root: str | Path | None = None,
    memory_limit: str = "18GB",
    threads: int | None = None,
    temp_directory: str | Path | None = None,
    adj_factor_path: str | Path | None = None,
    register_adj: bool = True,
) -> duckdb.DuckDBPyConnection:
    """Resolve host paths; requested references must exist (raw: register_adj=False)."""
    implementation = require_l2("research.queries.db")
    root = Path(parquet_root) if parquet_root else default_parquet_root()
    if register_adj and adj_factor_path is None:
        adj_factor_path = default_adj_factor_path()
    return implementation.connect(
        parquet_root=root, memory_limit=memory_limit, threads=threads,
        temp_directory=temp_directory, adj_factor_path=adj_factor_path,
        register_adj=register_adj,
    )
