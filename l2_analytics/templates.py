"""Load and run P0b SQL templates against ``l2_main`` / ``l2_order``."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Optional

import duckdb

_SQL_DIR = Path(__file__).resolve().parent / "sql"

# order_by allowlist: comma-separated identifiers each optionally ASC/DESC.
# Blocks injection like order_by="v; DROP TABLE t". Qualified names (a.b) and
# quoted identifiers are intentionally out of scope (raise -> caller fixes).
_ORDER_BY_RE = re.compile(
    r"^\s*[A-Za-z_][A-Za-z0-9_]*(\s+(ASC|DESC))?"
    r"(\s*,\s*[A-Za-z_][A-Za-z0-9_]*(\s+(ASC|DESC))?)*\s*$",
    re.IGNORECASE,
)

TEMPLATE_FILES = {
    "vwap": "vwap.sql",
    "vwap_adj": "vwap_adj.sql",
    "net_inflow": "net_inflow.sql",
    "large_order_cluster": "large_order_cluster.sql",
    "large_order_cluster_agg": "large_order_cluster_agg.sql",
    "buy_order_cluster": "buy_order_cluster.sql",
    "tick_speed": "tick_speed.sql",
    "session_distribution": "session_distribution.sql",
    "price_impact": "price_impact.sql",
    "limit_up_down": "limit_up_down.sql",
    "limit_up_down_true": "limit_up_down_true.sql",
    "opening_auction": "opening_auction.sql",
}


def sql_dir() -> Path:
    return _SQL_DIR


def load_template(name: str) -> str:
    if name not in TEMPLATE_FILES:
        raise KeyError(f"unknown template {name!r}; known={sorted(TEMPLATE_FILES)}")
    path = _SQL_DIR / TEMPLATE_FILES[name]
    return path.read_text(encoding="utf-8")


def run_template(
    con: duckdb.DuckDBPyConnection,
    name: str,
    *,
    extra_where: str = "",
    limit: Optional[int] = None,
    order_by: str = "",
    params: Optional[Mapping[str, Any]] = None,
) -> list[tuple[Any, ...]]:
    """Execute a template with optional AND-clause / ORDER BY / LIMIT wrappers.

    ``extra_where`` stays free-form for trusted internal callers; prefer ``$name``
    placeholders for *values* and pass them via ``params`` (bound by DuckDB), e.g.
    ``extra_where="stock_code = $code", params={"code": "000001.SZ"}``.
    ``order_by`` is validated against an identifier allowlist (raises ``ValueError``
    on anything else); ``limit`` is int-cast.
    """
    body = load_template(name).rstrip().rstrip(";")
    # Inject extra predicates before GROUP BY when present.
    if extra_where.strip():
        clause = extra_where.strip()
        if not clause.upper().startswith("AND"):
            clause = "AND " + clause
        if "GROUP BY" in body.upper():
            # insert before GROUP BY (last occurrence)
            idx = body.upper().rfind("GROUP BY")
            body = body[:idx] + f"  {clause}\n" + body[idx:]
        else:
            body = body + f"\n{clause}"
    if order_by.strip():
        if not _ORDER_BY_RE.match(order_by):
            raise ValueError(f"invalid order_by: {order_by!r}")
        body = body + f"\nORDER BY {order_by.strip()}"
    if limit is not None:
        body = body + f"\nLIMIT {int(limit)}"
    if params:
        return con.execute(body, dict(params)).fetchall()
    return con.execute(body).fetchall()
