"""Centralized symbol-format conversion.

Canonical symbol = **dot** format (broker/xtquant/Redis/execution_log/strategy):
``603196.SH``.
Partition key    = **underscore** format (Hive partition dir / path-safe):
``603196_SH``.

Why two formats (intentional, not debt): dots in Hive partition dir names
mishandle on Windows DuckDB — ``finish_adj_factor_duckdb.py`` documents
``symbol_dir=000001_SZ%5Cdata_parquet``. So partition **dirs** use underscore;
the duckdb ``symbol`` **column** uses canonical dot (``build_persistent_db``
normalizes via ``UPDATE stock_data SET symbol = REPLACE(symbol, '_', '.')``,
see ``reader.py``).

Rule: ALL Python-side symbol translation MUST go through these two helpers —
no ad-hoc ``.replace()``. SQL-level ``REPLACE(symbol, '_', '.')`` in
``reader.py`` is DB-side normalization and stays as-is.

See ``docs/engineering/plan-symbol-format-centralize-2026-06-25.md`` (if present)
and memory ``duckdb-symbol-format-preheat-trap``.
"""
from __future__ import annotations

import re

__all__ = ["to_partition_key", "to_canonical_symbol", "is_canonical_symbol"]

# A-share broker/xtquant form: 6 digits + .SH/.SZ/.BJ
_CANONICAL_SYMBOL_RE = re.compile(r"^\d{6}\.(SH|SZ|BJ)$")


def is_canonical_symbol(symbol: str) -> bool:
    """True iff ``symbol`` is a canonical A-share code (e.g. ``000001.SZ``)."""
    return bool(_CANONICAL_SYMBOL_RE.match(symbol or ""))


def to_partition_key(symbol: str) -> str:
    """Canonical dot symbol -> underscore partition-key / path-safe form.

    ``603196.SH`` -> ``603196_SH``. Use for Hive partition dir names and file paths.
    """
    return symbol.replace(".", "_")


def to_canonical_symbol(key: str) -> str:
    """Underscore partition-key / ``symbol=...`` dir name -> canonical dot symbol.

    ``603196_SH`` or ``symbol=603196_SH`` -> ``603196.SH``. Use when reading
    symbols back from partition dir names into the trading layer.

    Does **not** infer an exchange from a bare 6-digit CSV cell (``000001``
    stays ``000001``). Pool CSVs use
    ``oskh_core.a_share_symbol_normalize.canonical_from_bare_code`` via
    ``backtest.research.csv_pool.parse_pool_csv``.

    Market-suffix aware (``_SH/_SZ/_BJ``) for precision; falls back to blanket
    underscore->dot only when no recognized suffix. Safe for A-share codes
    (6 digits + market suffix, no internal underscore) — equivalent to both the
    historical suffix-only and blanket ``.replace()`` patterns.
    """
    if key.startswith("symbol="):
        key = key[len("symbol="):]
    for us, dot in (("_SH", ".SH"), ("_SZ", ".SZ"), ("_BJ", ".BJ")):
        if key.endswith(us):
            return key[: -len(us)] + dot
    return key.replace("_", ".")
