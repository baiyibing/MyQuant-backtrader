"""Consumer-side exact-duplicate collapse for ``l2_main`` / ``l2_order`` reads (BT-03).

#526 kept source duplicate rows in the lake: gap-free counts DISTINCT TranID, so
byte-identical close prints (occasional vendor double-writes) stay in
``l2_main``. Consumers that ``SUM(Volume)`` / ``COUNT(*)`` over raw rows
double-count those prints. At the same time, vendor exports legitimately reuse
the last continuous-session TranID for every STAR (688xxx) after-hours
fixed-price print — same ``(stock_code, date, TranID)``, distinct
Time/Price/Volume/... — and those rows must be preserved.

This module is consumer-side ONLY: no lake rewrite, no ETL write-path change,
no gap-free weakening (``_check_gap_free`` untouched). The persisted aggregates
(``aggregates.DAILY_METRICS_SQL`` / ``CLUSTER_AGG_SQL``) read from the helpers
here; ad-hoc templates wanting deduped qty/amount should do the same (or use
the ``l2_main_exact_dedup`` view from :func:`register_dedup_views`) — the SQL
templates under ``l2_analytics/sql/`` still hit raw ``l2_main``.

Exact-dup identity (``MAIN_EXACT_DUP_COLS``): the full trade content set
``stock_code, date, TranID, Time, Price, Volume, SaleOrderVolume,
BuyOrderVolume, Type`` plus the derived-but-deterministic ``session`` (function
of Time) and ``instrument_type`` (function of stock_code). ``ts`` / ``trade_time``
are pure functions of date+Time, so rows equal on the identity set are equal on
every column and any survivor of a collapse is byte-identical.

Audit dict keys from :func:`audit_main_dup_stats` (all int, names stable):
  - ``rows_raw``                count(*) on raw ``l2_main``
  - ``rows_exact_unique``       row count after exact-row collapse
  - ``exact_dup_extra_rows``    ``rows_raw - rows_exact_unique`` (collapsed surplus)
  - ``same_tran_id_groups``     groups with >1 **distinct** exact-row sharing one
                                ``(stock_code, date, TranID)`` — the legit STAR pattern
  - ``same_tran_id_multi_rows`` deduped row count belonging to those multi groups

Cluster-join note: ``CLUSTER_AGG_SQL`` collapses exact dups on both sides, but
the main↔order join key is TranID only, so distinct same-TranID rows still fan
out there (pre-existing semantics, unchanged by this knife).
"""

from __future__ import annotations

from typing import Optional

import duckdb

# Full trade identity set — two l2_main rows equal on all of these are the same
# print written twice and are collapsed to one row for qty/amount aggregation.
MAIN_EXACT_DUP_COLS = (
    "stock_code",
    "date",
    "TranID",
    "Time",
    "session",
    "instrument_type",
    "Price",
    "Volume",
    "SaleOrderVolume",
    "BuyOrderVolume",
    "Type",
)

# l2_order counterpart: every non-derived column of the order-side row.
ORDER_EXACT_DUP_COLS = (
    "stock_code",
    "date",
    "TranID",
    "SaleOrderID",
    "SaleOrderPrice",
    "BuyOrderID",
    "BuyOrderPrice",
)


def _exact_dedup_sql(
    table: str,
    cols: tuple[str, ...],
    alias: str,
    extra_where: Optional[str],
) -> str:
    """FROM-clause fragment: one row per exact-distinct ``table`` row, as ``alias``."""
    partition = ", ".join(cols)
    where = f"WHERE {extra_where} " if extra_where else ""
    # ORDER BY TranID is a constant tiebreak (TranID is a partition key): all
    # rows in a partition are content-identical, so the survivor pick is
    # deterministic no matter which one row_number() = 1 keeps.
    return (
        f"(SELECT * FROM {table} {where}"
        f"QUALIFY row_number() OVER (PARTITION BY {partition} ORDER BY TranID) = 1) AS {alias}"
    )


def exact_deduped_main_sql(
    alias: str = "m",
    *,
    extra_where: Optional[str] = None,
) -> str:
    """FROM-clause fragment reading ``l2_main`` with exact-dup rows collapsed.

    ``extra_where`` (e.g. ``"date = CAST($date AS DATE)"``) is applied inside
    the subquery, before the window — safe because ``date`` is a partition key;
    use unqualified column names (the alias binds outside the subquery).
    """
    return _exact_dedup_sql("l2_main", MAIN_EXACT_DUP_COLS, alias, extra_where)


def exact_deduped_order_sql(
    alias: str = "o",
    *,
    extra_where: Optional[str] = None,
) -> str:
    """FROM-clause fragment reading ``l2_order`` with exact-dup rows collapsed."""
    return _exact_dedup_sql("l2_order", ORDER_EXACT_DUP_COLS, alias, extra_where)


def register_dedup_views(con: duckdb.DuckDBPyConnection) -> None:
    """Register ``l2_main_exact_dedup`` / ``l2_order_exact_dedup`` helper views.

    Raw ``l2_main`` / ``l2_order`` stay untouched for existing callers.
    """
    con.execute(
        f"CREATE OR REPLACE VIEW l2_main_exact_dedup AS SELECT * FROM {exact_deduped_main_sql('d')}"
    )
    con.execute(
        f"CREATE OR REPLACE VIEW l2_order_exact_dedup AS "
        f"SELECT * FROM {exact_deduped_order_sql('d')}"
    )


def audit_main_dup_stats(
    con: duckdb.DuckDBPyConnection,
    *,
    date: Optional[str] = None,
) -> dict[str, int]:
    """Count raw/exact-dup/same-TranID-multi structure of ``l2_main``.

    ``date`` optional restricts all counters to that trading day. Key names are
    stable — see the module docstring for the contract.
    """
    params: dict[str, str] = {}
    extra_where: Optional[str] = None
    if date is not None:
        extra_where = "date = CAST($date AS DATE)"
        params["date"] = date

    rows_raw = int(
        con.execute(
            f"SELECT count(*) FROM l2_main {'WHERE ' + extra_where if extra_where else ''}",
            params,
        ).fetchone()[0]
    )
    rows_exact_unique, same_tran_id_groups, same_tran_id_multi_rows = (
        int(v)
        for v in con.execute(
            f"""
            SELECT
              COALESCE(sum(cnt), 0),
              COALESCE(count(*) FILTER (WHERE cnt > 1), 0),
              COALESCE(sum(cnt) FILTER (WHERE cnt > 1), 0)
            FROM (
              SELECT count(*) AS cnt
              FROM {exact_deduped_main_sql("d", extra_where=extra_where)}
              GROUP BY stock_code, date, TranID
            )
            """,
            params,
        ).fetchone()
    )
    return {
        "rows_raw": rows_raw,
        "rows_exact_unique": rows_exact_unique,
        "exact_dup_extra_rows": rows_raw - rows_exact_unique,
        "same_tran_id_groups": same_tran_id_groups,
        "same_tran_id_multi_rows": same_tran_id_multi_rows,
    }
