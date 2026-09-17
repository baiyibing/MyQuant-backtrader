# -*- coding: utf-8 -*-
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.research.csv_ledger import (
    SimState,
    execute_buy,
    trade_commission,
)
from backtest.research.qlib_bin_daily import (
    load_qlib_bin_daily_bars,
    qlib_inst_dir,
    read_qlib_bin,
)


def _write_bin(path: Path, ref: int, values: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = np.array([float(ref)], dtype="<f")
    body = np.asarray(values, dtype="<f")
    path.write_bytes(header.tobytes() + body.tobytes())


def test_qlib_inst_dir_maps_dot_and_qlib():
    assert qlib_inst_dir("600519.SH") == "sh600519"
    assert qlib_inst_dir("SH600519") == "sh600519"
    assert qlib_inst_dir("000001.SZ") == "sz000001"
    assert qlib_inst_dir("920748.BJ") == "bj920748"


def test_load_qlib_bin_daily_bars_reads_close(tmp_path):
    cal = tmp_path / "calendars"
    cal.mkdir()
    (cal / "day.txt").write_text("2026-01-05\n2026-01-06\n2026-01-07\n", encoding="utf-8")
    feat = tmp_path / "features" / "sh600519"
    _write_bin(feat / "close.day.bin", 0, [8322.0, 8300.0, 8280.0])
    _write_bin(feat / "open.day.bin", 0, [8310.0, 8290.0, 8270.0])
    _write_bin(feat / "high.day.bin", 0, [8330.0, 8310.0, 8290.0])
    _write_bin(feat / "low.day.bin", 0, [8300.0, 8280.0, 8260.0])

    got = load_qlib_bin_daily_bars(
        {"600519.SH"}, "20260106", "20260107", qlib_root=tmp_path, workers=1
    )
    df = got["600519.SH"]
    assert list(df.index) == [pd.Timestamp("2026-01-06"), pd.Timestamp("2026-01-07")]
    assert list(df["close"]) == [8300.0, 8280.0]
    assert list(df["open"]) == [8290.0, 8270.0]


def test_read_qlib_bin_respects_ref_start(tmp_path):
    p = tmp_path / "close.day.bin"
    _write_bin(p, 2, [1.0, 2.0, 3.0])
    s = read_qlib_bin(p, 0, 4)
    assert list(s.index) == [2, 3, 4]
    assert list(s.values) == [1.0, 2.0, 3.0]


def test_trade_commission_qlib_floor_and_default():
    assert trade_commission(1_000_000, 0.0005, 5.0) == 500.0
    assert trade_commission(1_000, 0.0005, 5.0) == 5.0
    assert trade_commission(1_000_000, 0.001, 0.0) == 1000.0


def test_execute_buy_uses_qlib_open_cost():
    st = SimState(cash=2_000_000.0, buy_cost_rate=0.0005, sell_cost_rate=0.0015, min_cost=5.0)
    assert execute_buy(st, "600000.SH", 10.0, 1_000_000.0, 0, "20260106")
    assert st.trades[0]["commission"] == pytest.approx(500.0)
    assert st.cash == pytest.approx(2_000_000.0 - 1_000_000.0 - 500.0)
