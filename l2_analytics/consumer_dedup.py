"""Infra exact-row dedup helpers; distinct same-TranID prints remain separate."""
from __future__ import annotations

from typing import TYPE_CHECKING

from l2_analytics._infra import require_l2

if TYPE_CHECKING:
    import duckdb


def exact_deduped_main_sql(alias: str = "m", *, extra_where: str | None = None) -> str:
    return require_l2("research.queries.consumer_dedup").exact_deduped_main_sql(
        alias, extra_where=extra_where,
    )


def exact_deduped_order_sql(alias: str = "o", *, extra_where: str | None = None) -> str:
    return require_l2("research.queries.consumer_dedup").exact_deduped_order_sql(
        alias, extra_where=extra_where,
    )


def register_dedup_views(con: duckdb.DuckDBPyConnection) -> None:
    return require_l2("research.queries.consumer_dedup").register_dedup_views(con)


def audit_main_dup_stats(
    con: duckdb.DuckDBPyConnection, *, date: str | None = None,
) -> dict[str, int]:
    return require_l2("research.queries.consumer_dedup").audit_main_dup_stats(con, date=date)


def __getattr__(name: str):
    if name in ("MAIN_EXACT_DUP_COLS", "ORDER_EXACT_DUP_COLS"):
        return getattr(require_l2("research.queries.consumer_dedup"), name)
    raise AttributeError(name)
