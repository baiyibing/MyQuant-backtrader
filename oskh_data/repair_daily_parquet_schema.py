"""Repair 1d hive parquet column type drift (esp. volume float64→int64).

Used when DuckDB rebuild fails with::

    Schema validation failed: column type drift ... volume: ('int64', 'double')

Canonical types live in ``oskh_data.daily_parquet_write.CANONICAL_ARROW_TYPES``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

import pyarrow.parquet as pq

from oskh_data.daily_parquet_write import (
    CANONICAL_ARROW_TYPES,
    STANDARD_COLUMNS,
    canonicalize_arrow_daily_table,
)


@dataclass(frozen=True)
class SchemaDrift:
    path: Path
    symbol_dir: str
    mismatches: dict[str, tuple[str, str]]


def scan_schema_drift(
    base_dir: Path | str,
    *,
    period: str = "1d",
    adjust_types: Sequence[str] = ("none", "front"),
) -> List[SchemaDrift]:
    """Return partitions whose critical columns differ from canonical types."""
    base = Path(base_dir)
    required = ("time", "open", "high", "low", "close", "volume")
    expected = {col: str(CANONICAL_ARROW_TYPES[col]) for col in required}
    out: List[SchemaDrift] = []
    from common.infra.data_root import resolve_period_root

    for adj in adjust_types:
        period_dir = resolve_period_root(period) / f"dividend_type={adj}"
        if not period_dir.is_dir():
            continue
        for p in sorted(period_dir.glob("symbol=*/data.parquet")):
            schema = pq.read_schema(p)
            names = set(schema.names)
            if not set(required).issubset(names):
                continue
            current = {col: str(schema.field(col).type) for col in required}
            mismatched = {
                col: (expected[col], current[col])
                for col in required
                if expected[col] != current[col]
            }
            if mismatched:
                out.append(
                    SchemaDrift(
                        path=p,
                        symbol_dir=p.parent.name,
                        mismatches=mismatched,
                    )
                )
    return out


def repair_parquet_file(path: Path) -> bool:
    """Rewrite one parquet with canonical dtypes. Returns True if rewritten."""
    table = pq.ParquetFile(path).read(
        columns=[c for c in STANDARD_COLUMNS if c in pq.read_schema(path).names]
    )
    fixed = canonicalize_arrow_daily_table(table)
    before = {n: str(table.schema.field(n).type) for n in table.column_names if n in CANONICAL_ARROW_TYPES}
    after = {n: str(fixed.schema.field(n).type) for n in fixed.column_names if n in CANONICAL_ARROW_TYPES}
    if before == after:
        return False
    pq.write_table(fixed, path, compression="snappy")
    return True


def repair_schema_drift(
    base_dir: Path | str,
    *,
    period: str = "1d",
    adjust_types: Sequence[str] = ("none", "front"),
    apply: bool = False,
    drifts: Iterable[SchemaDrift] | None = None,
) -> tuple[int, int]:
    """Scan (and optionally rewrite) drifted partitions.

    Returns ``(drift_count, repaired_count)``.
    """
    found = list(drifts) if drifts is not None else scan_schema_drift(
        base_dir, period=period, adjust_types=adjust_types
    )
    repaired = 0
    if apply:
        for d in found:
            if repair_parquet_file(d.path):
                repaired += 1
    return len(found), repaired
