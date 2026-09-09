"""Lightweight process / temp-dir sampling for L2 ETL and query baselines."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def process_rss_bytes() -> int | None:
    """Current process RSS in bytes; None if unavailable."""
    try:
        import psutil

        return int(psutil.Process().memory_info().rss)
    except (ImportError, OSError, AttributeError):
        return None


def note_peak(peak: list[int | None], value: int | None = None) -> None:
    """Update a single-slot peak tracker ``[current_max_or_None]``."""
    v = process_rss_bytes() if value is None else value
    if v is None:
        return
    cur = peak[0]
    if cur is None or v > cur:
        peak[0] = v


def dir_size_bytes(path: Path) -> int:
    """Sum regular-file sizes under ``path`` (0 if missing). Best-effort."""
    if not path.is_dir():
        return 0
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for name in files:
                try:
                    total += (Path(root) / name).stat().st_size
                except OSError:
                    continue
    except OSError:
        return total
    return total


def note_temp_peak(peak: list[int | None], temp_dir: Path) -> None:
    note_peak(peak, dir_size_bytes(temp_dir))


def bytes_to_gb(n: Optional[int]) -> Optional[float]:
    if n is None:
        return None
    return round(n / (1024**3), 3)
