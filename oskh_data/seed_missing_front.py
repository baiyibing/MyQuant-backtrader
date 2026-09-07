"""Seed missing front partitions by copying fresh none parquet (IPO / new listings).

``mirror_none_tail_to_front`` intentionally does **not** create front files when
absent (fail-closed). New IPOs therefore fail coverage with front ``MISSING``
even when none already reaches ``target_date``.

This helper copies ``dividend_type=none/.../data.parquet`` → ``front/...`` for
those symbols when none exists (optionally requiring none latest >= target).
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import pandas as pd

from oskh_data.pandas_typing import normalize_timestamp, timestamp_strftime
from oskh_data.downloader import _get_parquet_latest_date
from oskh_data.symbol_format import is_canonical_symbol, to_canonical_symbol, to_partition_key


@dataclass
class SeedStats:
    """Outcome of a seed-missing-front pass."""

    seeded: List[str] = field(default_factory=list)
    skipped_front_exists: List[str] = field(default_factory=list)
    skipped_no_none: List[str] = field(default_factory=list)
    skipped_none_stale: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def seeded_count(self) -> int:
        return len(self.seeded)


def _partition_parquet(base_dir: Path, adjust_type: str, canon: str) -> Path:
    part = to_partition_key(canon)
    from common.infra.data_root import resolve_period_root

    return (
        resolve_period_root("1d", base=Path(base_dir))
        / f"dividend_type={adjust_type}"
        / f"symbol={part}"
        / "data.parquet"
    )


def seed_missing_front_from_none(
    base_dir: Path | str,
    symbols: Iterable[str],
    *,
    require_none_min_date: Optional[str] = None,
) -> SeedStats:
    """Copy none → front for symbols whose front parquet is missing.

    Parameters
    ----------
    symbols:
        Canonical or partition-key style codes (``688825.SH`` / ``688825_SH``).
    require_none_min_date:
        If set (``YYYY-MM-DD`` / ``YYYYMMDD``), skip when none latest < this date.
    """
    base = Path(base_dir)
    stats = SeedStats()
    min_date = (
        normalize_timestamp(pd.Timestamp(require_none_min_date))
        if require_none_min_date
        else None
    )

    seen: set[str] = set()
    for raw in symbols:
        try:
            canon = to_canonical_symbol(str(raw).strip())
        except Exception:
            stats.errors.append(f"{raw}: bad_symbol")
            continue
        if not is_canonical_symbol(canon) or canon in seen:
            continue
        seen.add(canon)

        none_pq = _partition_parquet(base, "none", canon)
        front_pq = _partition_parquet(base, "front", canon)
        if front_pq.is_file():
            stats.skipped_front_exists.append(canon)
            continue
        if not none_pq.is_file():
            stats.skipped_no_none.append(canon)
            continue

        if min_date is not None:
            latest = _get_parquet_latest_date(none_pq)
            if latest is None:
                try:
                    df = pd.read_parquet(none_pq, columns=["time"])
                    if df.empty:
                        stats.skipped_none_stale.append(canon)
                        continue
                    latest = pd.to_datetime(int(df["time"].max()), unit="ms")
                except Exception as exc:  # noqa: BLE001
                    stats.errors.append(f"{canon}: none_read: {type(exc).__name__}: {exc}")
                    continue
            if normalize_timestamp(latest) < min_date:
                stats.skipped_none_stale.append(canon)
                continue

        try:
            front_pq.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(none_pq, front_pq)
            stats.seeded.append(canon)
        except Exception as exc:  # noqa: BLE001
            stats.errors.append(f"{canon}: copy: {type(exc).__name__}: {exc}")

    return stats


def missing_front_symbols_from_reports(
    reports: Sequence[object],
) -> List[str]:
    """Extract front lag symbols whose status is ``MISSING`` from CoverageReports."""
    out: List[str] = []
    for r in reports:
        adjust = getattr(r, "adjust_type", None)
        if adjust != "front":
            continue
        for item in getattr(r, "lag", []) or []:
            if not isinstance(item, (tuple, list)) or len(item) < 2:
                continue
            canon, status = str(item[0]), str(item[1])
            if status.upper() == "MISSING":
                out.append(canon)
    return out


def try_seed_ipo_front_from_coverage(
    base_dir: Path | str,
    reports: Sequence[object],
    target_date: str | pd.Timestamp,
) -> SeedStats:
    """Seed front ``MISSING`` symbols when none side looks fresh enough.

    Only acts on front ``MISSING`` entries. Does not touch lag-by-date holes
    (those need path-b-repair / QMT front refresh, not a full none copy).
    """
    symbols = missing_front_symbols_from_reports(reports)
    if not symbols:
        return SeedStats()
    target_str = timestamp_strftime(target_date, "%Y-%m-%d")
    return seed_missing_front_from_none(
        base_dir,
        symbols,
        require_none_min_date=target_str,
    )


__all__ = [
    "SeedStats",
    "missing_front_symbols_from_reports",
    "seed_missing_front_from_none",
    "try_seed_ipo_front_from_coverage",
]
