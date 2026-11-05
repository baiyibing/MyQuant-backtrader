"""Host reference-path selection for infra's offline L2 reference views."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from l2_analytics._infra import require_l2

if TYPE_CHECKING:
    import duckdb


def default_adj_factor_path() -> Path:
    from common.infra.data_root import resolve_source_parquet

    return resolve_source_parquet("adj_factor.parquet")


def register_ref_views(
    con: duckdb.DuckDBPyConnection,
    *,
    adj_factor_path: str | Path | None = None,
) -> dict[str, bool]:
    implementation = require_l2("research.queries.ref_data")
    path = default_adj_factor_path() if adj_factor_path is None else adj_factor_path
    return implementation.register_ref_views(con, adj_factor_path=path)
