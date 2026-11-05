"""Compatibility entrances for infra's L2 process/temp sampling helpers."""
from pathlib import Path

from l2_analytics._infra import require_l2


def process_rss_bytes() -> int | None:
    return require_l2("ingest.perf").process_rss_bytes()


def note_peak(peak: list[int | None], value: int | None = None) -> None:
    require_l2("ingest.perf").note_peak(peak, value)


def dir_size_bytes(path: Path) -> int:
    return require_l2("ingest.perf").dir_size_bytes(path)


def note_temp_peak(peak: list[int | None], temp_dir: Path) -> None:
    require_l2("ingest.perf").note_temp_peak(peak, temp_dir)


def bytes_to_gb(n: int | None) -> float | None:
    return require_l2("ingest.perf").bytes_to_gb(n)
