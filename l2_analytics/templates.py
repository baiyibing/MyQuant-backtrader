"""Compatibility entrance for infra's offline research SQL templates."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from l2_analytics._infra import require_l2

if TYPE_CHECKING:
    import duckdb


def sql_dir() -> Path:
    return require_l2("research.queries.templates").sql_dir()


def load_template(name: str) -> str:
    return require_l2("research.queries.templates").load_template(name)


def run_template(
    con: duckdb.DuckDBPyConnection,
    name: str,
    *,
    extra_where: str = "",
    limit: int | None = None,
    order_by: str = "",
    params: Mapping[str, Any] | None = None,
) -> list[tuple[Any, ...]]:
    return require_l2("research.queries.templates").run_template(
        con, name, extra_where=extra_where, limit=limit, order_by=order_by, params=params,
    )


def __getattr__(name: str):
    if name == "TEMPLATE_FILES":
        return require_l2("research.queries.templates").TEMPLATE_FILES
    raise AttributeError(name)
