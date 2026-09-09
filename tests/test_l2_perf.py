"""Unit tests for l2_analytics.perf helpers."""

from __future__ import annotations

from pathlib import Path

from l2_analytics.perf import bytes_to_gb, dir_size_bytes, note_peak, process_rss_bytes


def test_process_rss_bytes() -> None:
    rss = process_rss_bytes()
    assert rss is None or rss > 0


def test_note_peak() -> None:
    peak: list[int | None] = [None]
    note_peak(peak, 10)
    note_peak(peak, 5)
    note_peak(peak, 20)
    assert peak[0] == 20


def test_dir_size_bytes(tmp_path: Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"x" * 100)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.bin").write_bytes(b"y" * 50)
    assert dir_size_bytes(tmp_path) == 150
    assert dir_size_bytes(tmp_path / "missing") == 0


def test_bytes_to_gb() -> None:
    assert bytes_to_gb(None) is None
    assert bytes_to_gb(1024**3) == 1.0
