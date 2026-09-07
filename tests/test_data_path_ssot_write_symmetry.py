# -*- coding: utf-8 -*-
"""path-SSOT PR-2 写侧契约：写后路径 == 读路径（plan r1 D2）。

防两类回归：
- 双后缀陷阱（评审 A5）：把 period 根当 base_dir 传入会得到
  ``period=1d/period=1d/...``；
- 读写分叉（评审 R1 实证）：读路径走 resolver、写入传 raw base
  ——env 置位后同一次写会读 F 写 E。
"""
from __future__ import annotations

import pandas as pd

from common.infra.data_root import resolve_period_root
from oskh_data.daily_parquet_write import _file_path, write_processed_data


def test_file_path_env_wins_over_base(monkeypatch, tmp_path):
    default_container = tmp_path / "default_stock_data"
    f_root = tmp_path / "f_authority"
    monkeypatch.setenv("OSKH_PERIOD_1D_ROOT", str(f_root))
    got = _file_path(default_container, "front", "600000.SH")
    assert got == (
        f_root / "dividend_type=front" / "symbol=600000_SH" / "data.parquet"
    )
    # 读侧同一 env → 写后路径 == 读路径（读写对称）
    read_side = resolve_period_root("1d") / "dividend_type=front" / "symbol=600000_SH" / "data.parquet"
    assert got == read_side


def test_file_path_legacy_equivalence_without_env(monkeypatch, tmp_path):
    monkeypatch.delenv("OSKH_PERIOD_1D_ROOT", raising=False)
    monkeypatch.setattr(
        "common.infra.data_root.find_authority_marker", lambda: None
    )
    container = tmp_path / "stock_data"
    got = _file_path(container, "front", "600000.SH")
    assert got == (
        container / "period=1d" / "dividend_type=front"
        / "symbol=600000_SH" / "data.parquet"
    )
    assert got.parts.count("period=1d") == 1  # 无双后缀


def test_write_processed_data_lands_on_env_root(monkeypatch, tmp_path):
    """e2e：env 指向 F 根时，写盘落 F、默认容器不新增（D2 静默分叉防线）。"""
    default_container = tmp_path / "default_stock_data"
    f_root = tmp_path / "f_authority"
    monkeypatch.setenv("OSKH_PERIOD_1D_ROOT", str(f_root))
    df = pd.DataFrame(
        {"time": [1758931200000], "open": [10.0], "high": [10.2],
         "low": [9.8], "close": [10.0], "volume": [1000.0], "amount": [10000.0]}
    )
    ok_n, errs = write_processed_data(
        default_container, "front", {"600000.SH": df}, mode="legacy"
    )
    assert ok_n == 1 and errs == []
    landed = list(f_root.rglob("data.parquet"))
    assert len(landed) == 1, "写入必须落在 env 权威根"
    assert not (default_container / "period=1d").exists(), "默认容器不得新增"
