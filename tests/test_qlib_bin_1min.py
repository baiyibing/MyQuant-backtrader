# -*- coding: utf-8 -*-
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.research.qlib_bin_1min import daily_closes_from_minutes, load_qlib_bin_1min_bars


def _write_bin(path: Path, ref: int, values: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = np.array([float(ref)], dtype="<f")
    body = np.asarray(values, dtype="<f")
    path.write_bytes(header.tobytes() + body.tobytes())


def test_load_qlib_bin_1min_bars_reads_window(tmp_path):
    cal = tmp_path / "calendars"
    cal.mkdir()
    (cal / "1min.txt").write_text(
        "\n".join(
            [
                "2026-01-05 14:55:00",
                "2026-01-06 14:55:00",
                "2026-01-07 14:55:00",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    feat = tmp_path / "features" / "sz000739"
    _write_bin(feat / "close.1min.bin", 0, [10.0, 11.0, 12.0])
    _write_bin(feat / "open.1min.bin", 0, [9.9, 10.9, 11.9])
    _write_bin(feat / "high.1min.bin", 0, [10.1, 11.1, 12.1])

    got = load_qlib_bin_1min_bars(
        {"000739.SZ"}, date(2026, 1, 6), date(2026, 1, 7), qlib_root=tmp_path, workers=1
    )
    frame = got["000739.SZ"]
    assert list(frame["date"]) == [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)]
    assert list(frame["hm"]) == [895, 895, 895]
    assert list(frame["close"]) == [10.0, 11.0, 12.0]
    daily = daily_closes_from_minutes(got)
    assert daily["000739.SZ"][date(2026, 1, 6)] == 11.0
