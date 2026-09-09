# -*- coding: utf-8 -*-
"""hive 分树 S1 单测（plan-hive-ashare-pure-index-etf-split-l2-2026-09-09）。

覆盖：
- ``classify_daily_lake_kind`` §2.1 分类矩阵（含 ``000001.SH`` 指数 vs
  ``000001.SZ`` 股票的分类陷阱、裸码 unknown fail-closed）
- ``resolve_index_daily_root`` / ``resolve_etf_daily_root``：env 覆盖 +
  **不读 ``OSKH_PERIOD_1D_ROOT``**（plan F6 env 劫持回归）
- ``resolve_period_root`` 默认 ``stock/period=*``（新根优先 · 仅旧根存在时
  短暂回落 · 双双不存在指向新根）
- ``_file_path`` 三树路由（指数 none-only · unknown fail-closed · ETF/指数
  不进股票树）
- ETF reader 路径不受 ``OSKH_PERIOD_1D_ROOT`` 劫持（显式 base 隔离语义保留）
- 分钟树仅股票（``PeriodDataManager.get_file_path`` 非 A 股拒写）——本 fork
  已删 ``oskh_data/downloader``（QMT 下载归原仓），该例在本仓自动跳过。
"""

from __future__ import annotations

import pytest

_ALL_LAKE_ENV_KEYS = (
    "OSKH_PERIOD_1D_ROOT",
    "OSKH_PERIOD_1M_ROOT",
    "OSKH_SOURCE_PARQUET_ROOT",
    "OSKH_L2_PARQUET_ROOT",
    "OSKH_INDEX_DAILY_ROOT",
    "OSKH_ETF_DAILY_ROOT",
    "TURNOVER_RESIST_DATA_DIR",
)


@pytest.fixture(autouse=True)
def _isolate_lake_env(monkeypatch, tmp_path):
    """authority marker 指 tmp、清空全部湖根 env（每测独立容器）。"""
    marker_root = tmp_path / "authority"
    marker_root.mkdir()
    (marker_root / ".authority").touch()
    monkeypatch.setenv("OSKH_AUTHORITY_HINT_ROOT", str(marker_root))
    for key in _ALL_LAKE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    from common.infra import data_root as _dr

    _dr.reset_authority_fallback_warnings()
    yield marker_root
    _dr.reset_authority_fallback_warnings()


_CLASSIFY_CASES = [
    # §2.1 分类陷阱：同码不同所
    ("000001.SZ", "ashare"),
    ("000001.SH", "index"),
    ("000001_SH", "index"),
    ("000300.SH", "index"),
    ("399001.SZ", "index"),
    ("399006.SZ", "index"),
    # ETF 前缀 SSOT
    ("159915.SZ", "etf"),
    ("510050.SH", "etf"),
    ("513100.SH", "etf"),
    ("588000.SH", "etf"),
    # A 股前缀（沪深京）
    ("600519.SH", "ashare"),
    ("601318.SH", "ashare"),
    ("605111_SH", "ashare"),
    ("688001.SH", "ashare"),
    ("000002.SZ", "ashare"),
    ("002594.SZ", "ashare"),
    ("300750.SZ", "ashare"),
    ("430047.BJ", "ashare"),
    ("830799.BJ", "ashare"),
    ("920002.BJ", "ashare"),
    # unknown fail-closed：裸码 / B 股 / 可转债 / 板块指数
    ("000001", "unknown"),
    ("600519", "unknown"),
    ("880001.SH", "unknown"),
    ("900901.SH", "unknown"),
    ("200002.SZ", "unknown"),
    ("113000.SH", "unknown"),
    ("123456.SZ", "unknown"),  # 可转债 12x
    ("", "unknown"),
]


@pytest.mark.parametrize("symbol,expected", _CLASSIFY_CASES)
def test_classify_daily_lake_kind_matrix(symbol: str, expected: str) -> None:
    from oskh_data.lake_kind import classify_daily_lake_kind

    assert classify_daily_lake_kind(symbol) == expected


def test_kind_roots_env_override(monkeypatch, tmp_path) -> None:
    from common.infra.data_root import resolve_etf_daily_root, resolve_index_daily_root

    monkeypatch.setenv("OSKH_INDEX_DAILY_ROOT", str(tmp_path / "idx"))
    monkeypatch.setenv("OSKH_ETF_DAILY_ROOT", str(tmp_path / "etf"))
    assert resolve_index_daily_root() == tmp_path / "idx"
    assert resolve_etf_daily_root() == tmp_path / "etf"


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_kind_roots_never_read_period_1d_env(monkeypatch, _isolate_lake_env) -> None:
    """F6 劫持回归：OSKH_PERIOD_1D_ROOT 设置不影响 index/etf 根。"""
    from common.infra.data_root import (
        find_authority_marker,
        resolve_etf_daily_root,
        resolve_index_daily_root,
    )

    monkeypatch.setenv("OSKH_PERIOD_1D_ROOT", r"F:\hijack\period=1d")
    marker = find_authority_marker()
    assert marker is not None
    container = marker.parent
    assert resolve_index_daily_root() == container / "index" / "period=1d"
    assert resolve_etf_daily_root() == container / "etf" / "period=1d"


def test_kind_roots_explicit_root_wins(tmp_path) -> None:
    from common.infra.data_root import resolve_etf_daily_root, resolve_index_daily_root

    assert resolve_index_daily_root(explicit_root=tmp_path / "x") == tmp_path / "x"
    assert resolve_etf_daily_root(explicit_root=tmp_path / "y") == tmp_path / "y"


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_period_root_default_prefers_stock_tree(_isolate_lake_env) -> None:
    from common.infra.data_root import resolve_period_root

    container = _isolate_lake_env
    (container / "stock" / "period=1d").mkdir(parents=True)
    (container / "period=1d").mkdir(parents=True)  # 旧根也在
    assert resolve_period_root("1d") == container / "stock" / "period=1d"


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_period_root_default_legacy_fallback(_isolate_lake_env) -> None:
    from common.infra.data_root import resolve_period_root

    container = _isolate_lake_env
    (container / "period=1d").mkdir(parents=True)  # 仅旧根（E 回退点 / 未搬盘容器）
    assert resolve_period_root("1d") == container / "period=1d"


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_period_root_default_neither_exists_points_at_stock(_isolate_lake_env) -> None:
    from common.infra.data_root import resolve_period_root

    container = _isolate_lake_env
    assert resolve_period_root("1d") == container / "stock" / "period=1d"
    assert resolve_period_root("1m") == container / "stock" / "period=1m"


def test_period_root_env_still_wins(monkeypatch, tmp_path) -> None:
    from common.infra.data_root import resolve_period_root

    monkeypatch.setenv("OSKH_PERIOD_1D_ROOT", str(tmp_path / "env1d"))
    assert resolve_period_root("1d") == tmp_path / "env1d"


def test_file_path_three_tree_routing(monkeypatch, tmp_path) -> None:
    from oskh_data.daily_parquet_write import _file_path

    monkeypatch.setenv("OSKH_PERIOD_1D_ROOT", str(tmp_path / "stock1d"))
    monkeypatch.setenv("OSKH_INDEX_DAILY_ROOT", str(tmp_path / "idx"))
    monkeypatch.setenv("OSKH_ETF_DAILY_ROOT", str(tmp_path / "etf"))
    base = tmp_path / "legacy"

    p_idx = _file_path(base, "none", "000300.SH")
    assert p_idx == tmp_path / "idx" / "dividend_type=none" / "symbol=000300_SH" / "data.parquet"

    p_etf = _file_path(base, "none", "510050.SH")
    assert p_etf == tmp_path / "etf" / "dividend_type=none" / "symbol=510050_SH" / "data.parquet"

    p_etf_front = _file_path(base, "front", "159915.SZ")
    assert p_etf_front == tmp_path / "etf" / "dividend_type=front" / "symbol=159915_SZ" / "data.parquet"

    p_stock = _file_path(base, "none", "600519.SH")
    assert p_stock == tmp_path / "stock1d" / "dividend_type=none" / "symbol=600519_SH" / "data.parquet"


def test_file_path_index_none_only_and_unknown_fail_closed(monkeypatch, tmp_path) -> None:
    from oskh_data.daily_parquet_write import _file_path

    monkeypatch.setenv("OSKH_INDEX_DAILY_ROOT", str(tmp_path / "idx"))
    base = tmp_path / "legacy"

    # v1.3 人裁锁：指数树 none-only，front 拒写
    with pytest.raises(ValueError, match="none-only"):
        _file_path(base, "front", "000300.SH")

    # §2.1 fail-closed：不可分类 / 裸码拒写
    for bad in ("880001.SH", "900901.SH", "000001", "113000.SH"):
        with pytest.raises(ValueError, match="unclassifiable"):
            _file_path(base, "none", bad)


def test_reader_etf_make_path_not_hijacked(monkeypatch, tmp_path) -> None:
    from oskh_data.reader import StockDataReader

    monkeypatch.setenv("OSKH_PERIOD_1D_ROOT", str(tmp_path / "hijack"))
    monkeypatch.setenv("OSKH_ETF_DAILY_ROOT", str(tmp_path / "etfroot"))

    r = StockDataReader(asset_type="etf", mode="parquet")
    p = r._make_path("510050.SH", "1d", "none")
    assert p == (
        tmp_path / "etfroot" / "dividend_type=none" / "symbol=510050_SH" / "data.parquet"
    )

    # 显式 base_dir（测试/隔离语义保留）：base/etf/period=1d，不受 env 劫持
    r2 = StockDataReader(base_dir=str(tmp_path / "isol"), asset_type="etf", mode="parquet")
    p2 = r2._make_path("510050.SH", "1d", "none")
    assert p2 == (
        tmp_path / "isol" / "etf" / "period=1d"
        / "dividend_type=none" / "symbol=510050_SH" / "data.parquet"
    )

    # 股票读者语义不变：env 胜 base（path-SSOT D2）
    r3 = StockDataReader(mode="parquet")
    p3 = r3._make_path("600519.SH", "1d", "none")
    assert p3 == (
        tmp_path / "hijack" / "dividend_type=none" / "symbol=600519_SH" / "data.parquet"
    )


def test_minute_lake_stock_only(monkeypatch, tmp_path) -> None:
    # 本 fork 已移除 QMT 下载管线（oskh_data.downloader 归原仓），跳过。
    pytest.importorskip("oskh_data.downloader")
    from oskh_data.downloader import PeriodDataManager

    monkeypatch.setenv("OSKH_PERIOD_1M_ROOT", str(tmp_path / "m1"))

    p = PeriodDataManager.get_file_path(None, "1m", "none", "600519.SH")
    assert p == (
        tmp_path / "m1" / "dividend_type=none" / "symbol=600519_SH" / "data.parquet"
    )

    # hive-split v1.5：分钟树仅股票；指数/ETF 拒写（不再入分钟湖脏分区）
    for bad in ("000300.SH", "510050.SH", "159915.SZ", "880001.SH"):
        with pytest.raises(ValueError, match="stock-only"):
            PeriodDataManager.get_file_path(None, "1m", "none", bad)
