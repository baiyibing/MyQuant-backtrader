# -*- coding: utf-8 -*-
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.research.ashare_bars import (
    bars_from_pool,
    load_daily_ohlc,
    load_minute_compact,
    load_session_bars,
)


def _write_bin(path: Path, ref: int, values: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = np.array([float(ref)], dtype="<f")
    body = np.asarray(values, dtype="<f")
    path.write_bytes(header.tobytes() + body.tobytes())


def test_unknown_source_is_rejected():
    with pytest.raises(ValueError, match="minute source"):
        load_minute_compact(["000001.SZ"], date(2026, 1, 6), date(2026, 1, 7), source="csv")
    with pytest.raises(ValueError, match="daily source"):
        load_daily_ohlc(["000001.SZ"], "20260106", "20260107", source="yahoo")


def test_empty_symbols_and_empty_pool_return_empty():
    assert load_minute_compact([], date(2026, 1, 6), date(2026, 1, 7)) == {}
    bars = bars_from_pool({}, date(2026, 1, 6), date(2026, 1, 7))
    assert bars.minute == {}
    assert bars.daily_close == {}


def test_load_session_bars_qlib_1min_and_require_root(tmp_path):
    cal = tmp_path / "calendars"
    cal.mkdir()
    (cal / "1min.txt").write_text(
        "2026-01-06 14:55:00\n2026-01-07 14:55:00\n", encoding="utf-8"
    )
    feat = tmp_path / "features" / "sz000739"
    _write_bin(feat / "close.1min.bin", 0, [10.0, 11.0])
    _write_bin(feat / "open.1min.bin", 0, [9.9, 10.9])
    _write_bin(feat / "high.1min.bin", 0, [10.1, 11.1])

    with pytest.raises(ValueError, match="qlib_root"):
        load_minute_compact(["000739.SZ"], date(2026, 1, 6), date(2026, 1, 7), source="qlib_1min")

    minute = load_minute_compact(
        ["000739.SZ"], date(2026, 1, 6), date(2026, 1, 7), source="qlib_1min", qlib_root=tmp_path
    )
    assert list(minute["000739.SZ"]["close"]) == [10.0, 11.0]
    (cal / "day.txt").write_text("2026-01-06\n2026-01-07\n", encoding="utf-8")
    _write_bin(feat / "close.day.bin", 0, [10.0, 11.0])
    _write_bin(feat / "open.day.bin", 0, [9.9, 10.9])
    _write_bin(feat / "high.day.bin", 0, [10.1, 11.1])
    _write_bin(feat / "low.day.bin", 0, [9.8, 10.8])
    session = load_session_bars(
        ["000739.SZ"],
        date(2026, 1, 6),
        date(2026, 1, 7),
        minute_source="qlib_1min",
        qlib_1min_root=tmp_path,
        daily_source="qlib_day",
        qlib_day_root=tmp_path,
    )
    assert session.minute_source == "qlib_1min"
    assert session.daily_source == "qlib_day"
    assert "000739.SZ" in session.minute
    assert session.daily_close["000739.SZ"][date(2026, 1, 7)] == 11.0


def test_load_daily_ohlc_qlib_day(tmp_path):
    cal = tmp_path / "calendars"
    cal.mkdir()
    (cal / "day.txt").write_text("2026-01-06\n2026-01-07\n", encoding="utf-8")
    feat = tmp_path / "features" / "sh600519"
    _write_bin(feat / "close.day.bin", 0, [100.0, 101.0])
    _write_bin(feat / "open.day.bin", 0, [99.0, 100.0])
    _write_bin(feat / "high.day.bin", 0, [101.0, 102.0])
    _write_bin(feat / "low.day.bin", 0, [98.0, 99.0])
    frames = load_daily_ohlc(
        ["600519.SH"], "20260106", "20260107", source="qlib_day", qlib_root=tmp_path, workers=1
    )
    assert list(frames["600519.SH"]["close"]) == [100.0, 101.0]
    assert list(frames["600519.SH"].index) == [pd.Timestamp("2026-01-06"), pd.Timestamp("2026-01-07")]
