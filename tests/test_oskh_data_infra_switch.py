"""Data-free integration across BT policy/configuration and the pinned infra IO."""
from __future__ import annotations

from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from oskh_data import reader as reader_module
from oskh_data.reader import StockDataReader, _INFRA_AVAILABLE

pytestmark_infra = pytest.mark.skipif(
    not _INFRA_AVAILABLE,
    reason="optional myquant-infra not installed (public CI)",
)


def write_bars(root: Path, period: str, adjust: str, symbol: str, close: float) -> pd.DataFrame:
    stamp = pd.Timestamp("2026-11-04" if period == "1d" else "2026-11-04 09:31:00")
    frame = pd.DataFrame({
        "time": [int(stamp.timestamp() * 1000)], "open": [close],
        "high": [close + 1.0], "low": [close - 1.0], "close": [close],
        "volume": pd.Series([1000], dtype="int64"), "amount": [close * 1000.0],
    })
    path = root / f"period={period}" / f"dividend_type={adjust}" / f"symbol={symbol.replace('.', '_')}" / "data.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return frame


@pytest.fixture
def lake(monkeypatch, tmp_path):
    container = tmp_path / "lake"
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(container))
    monkeypatch.setenv("OSKH_DATA_ROOT", str(workspace))
    monkeypatch.setenv("OSKH_DATA_READER_MODE", "parquet")
    for key in ("OSKH_PERIOD_1D_ROOT", "OSKH_PERIOD_1M_ROOT", "OSKH_ETF_DAILY_ROOT"):
        monkeypatch.delenv(key, raising=False)
    return container, workspace


@pytest.mark.parametrize("asset_type,symbol", [("stock", "600000.SH"), ("etf", "510050.SH")])
@pytest.mark.parametrize("mode", ["parquet", "duckdb", "duckdb_persistent"])
@pytestmark_infra
def test_real_daily_and_minute_io_uses_separate_roots(lake, asset_type, symbol, mode):
    container, workspace = lake
    tree = container / asset_type
    write_bars(tree, "1d", "front", symbol, 11.0)
    write_bars(tree, "1d", "none", symbol, 12.0)
    write_bars(tree, "1m", "none", symbol, 22.0)
    # Persistent daily artifacts belong to the workspace, not the parquet lake.
    output, _ = StockDataReader.build_persistent_db(asset_type=asset_type)
    assert output.parent == workspace / "stock_data"
    assert not list(container.glob("*.duckdb"))
    with StockDataReader(mode=mode, asset_type=asset_type) as reader:
        for adjust, close in (("front", 11.0), ("none", 12.0)):
            single = reader.read_stock(symbol, "20261104", "20261105", adjust_type=adjust)
            batch = reader.scan_stocks([symbol], "20261104", "20261105", adjust_type=adjust)
            assert_frame_equal(single, batch)
            assert list(single["close"]) == [close]
            assert list(single["symbol"]) == [symbol]
            assert single.index.name == "datetime"
        # Requested front must be checked locally, then coerced to raw by infra.
        minute = reader.read_stock(symbol, period="1m", adjust_type="front")
        assert list(minute["close"]) == [22.0]
        assert list(minute.index) == [pd.Timestamp("2026-11-04 09:31:00")]
        assert reader.scan_stocks([], adjust_type="none") is None
    with pytest.raises(RuntimeError, match="closed"):
        reader.read_stock(symbol, adjust_type="none")


@pytestmark_infra
def test_period_overrides_reach_infra_read_and_rebuild(lake, monkeypatch, tmp_path):
    container, workspace = lake
    override = tmp_path / "override"
    monkeypatch.setenv("OSKH_PERIOD_1D_ROOT", str(override / "period=1d"))
    write_bars(container / "stock", "1d", "front", "600000.SH", 1.0)
    write_bars(override, "1d", "front", "600000.SH", 99.0)
    output, _ = StockDataReader.build_persistent_db()
    for mode in ("parquet", "duckdb", "duckdb_persistent"):
        with StockDataReader(mode=mode, db_path=str(output)) as reader:
            assert list(reader.read_stock("600000.SH")["close"]) == [99.0]


@pytestmark_infra
def test_failed_rebuild_keeps_previous_database(lake):
    container, _ = lake
    frame = write_bars(container / "stock", "1d", "front", "600000.SH", 11.0)
    output, _ = StockDataReader.build_persistent_db()
    before = output.read_bytes()
    path = container / "stock" / "period=1d" / "dividend_type=front" / "symbol=600000_SH" / "data.parquet"
    frame.assign(volume=frame["volume"].astype("float64")).to_parquet(path, index=False)
    with pytest.raises(ValueError, match="schema drift"):
        StockDataReader.build_persistent_db()
    assert output.read_bytes() == before
    with StockDataReader(mode="duckdb_persistent") as reader:
        assert list(reader.read_stock("600000.SH")["close"]) == [11.0]


@pytestmark_infra
def test_missing_root_and_missing_persistent_db_fail_without_artifacts(monkeypatch, tmp_path):
    monkeypatch.delenv("OSKH_SOURCE_PARQUET_ROOT", raising=False)
    monkeypatch.delenv("OSKH_AUTHORITY_HINT_ROOT", raising=False)
    from common.infra.data_root import UnconfiguredDataRootError

    with pytest.raises(UnconfiguredDataRootError):
        StockDataReader(mode="parquet")
    with pytest.raises(FileNotFoundError, match="persistent file not found"):
        StockDataReader(base_dir=str(tmp_path), mode="duckdb_persistent")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("entry", ["read_stock", "scan_stocks"])
def test_as_of_date_fails_before_infra(monkeypatch, tmp_path, entry):
    backend = Mock()
    monkeypatch.setattr(reader_module._InfraStockDataReader, entry, backend)
    reader = StockDataReader(base_dir=str(tmp_path), mode="parquet")
    symbol = "600000.SH" if entry == "read_stock" else ["600000.SH"]
    with pytest.raises(NotImplementedError, match="as_of_date"):
        getattr(reader, entry)(symbol, as_of_date="20261104")
    backend.assert_not_called()


@pytest.mark.parametrize("asset_type", ["index", "invalid"])
def test_bt_rejects_asset_types_before_io(tmp_path, asset_type):
    from common.integrations.duckdb_daily_bars_adapter import DuckDBDailyBarsProxy

    with pytest.raises(ValueError, match="stock or etf"):
        StockDataReader(base_dir=str(tmp_path), asset_type=asset_type)
    with pytest.raises(ValueError, match="stock or etf"):
        DuckDBDailyBarsProxy(Mock(), asset_type=asset_type)
    with pytest.raises(ValueError, match="stock or etf"):
        reader_module.lazy_prev_close_reader(asset_type)
    with pytest.raises(ValueError, match="only daily"):
        StockDataReader.build_persistent_db(asset_type=asset_type)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("kwargs", [{"period": "1m"}, {"period": "all"}, {"adjust_type": "none"}, {"adjust_type": "back"}])
def test_retired_rebuild_fails_before_root_resolution(monkeypatch, kwargs):
    resolve = Mock(side_effect=AssertionError("unexpected IO/config resolution"))
    monkeypatch.setattr(reader_module, "_resolve_parquet_container", resolve)
    with pytest.raises(ValueError, match="only daily"):
        StockDataReader.build_persistent_db(**kwargs)
    resolve.assert_not_called()


@pytest.mark.parametrize("entry", ["reader", "scan", "etf", "cache", "proxy", "proxy_cfg"])
def test_real_caller_discovery_crosses_infra_forwarding_frames(monkeypatch, tmp_path, entry):
    from common.integrations.duckdb_daily_bars_adapter import DuckDBDailyBarsProxy
    from oskh_data import cache_port, etf_local_bars, freshness

    backend = Mock(return_value=pd.DataFrame({"close": [1.0]}))
    monkeypatch.setattr(reader_module._InfraStockDataReader, "read_stock", backend)
    monkeypatch.setattr(reader_module._InfraStockDataReader, "scan_stocks", backend)
    reader = StockDataReader(base_dir=str(tmp_path), mode="parquet")
    monkeypatch.setattr(etf_local_bars, "get_etf_stock_data_reader", lambda: reader)
    redis = Mock()
    monkeypatch.setattr(cache_port, "_get_redis", redis)
    monkeypatch.setattr(freshness, "get_previous_trading_day", lambda: "20261104")
    delegate = Mock()
    proxy = DuckDBDailyBarsProxy(delegate)
    proxy._reader = reader
    # Give the call expression a real restricted-module frame. No policy/caller mock.
    hot = ModuleType("trade_decision.k18_probe")
    hot.__dict__.update(reader=reader, etf_local_bars=etf_local_bars, cache_port=cache_port, proxy=proxy)
    expressions = {
        "reader": 'reader.read_stock("600000.SH", period="1m", adjust_type="front")',
        "scan": 'reader.scan_stocks(["600000.SH"], period="1m", adjust_type="front")',
        "etf": 'etf_local_bars.default_etf_fund_daily("510050.SH", "20261102", "20261104")',
        "cache": 'cache_port.get_daily_bars_cached("600000.SH", "20261102", "20261104", adjust="front")',
        "proxy": 'proxy.stock_daily_bars(symbol="600000.SH", start_date="20261102", end_date="20261104", adjust="front")',
        "proxy_cfg": 'proxy.stock_daily_bars_cfg_only(symbol="600000.SH", start_date="20261102", end_date="20261104", adjust="front")',
    }
    exec("def invoke():\n    return " + expressions[entry], hot.__dict__)
    with pytest.raises(RuntimeError, match="DataAccessPolicyError"):
        hot.invoke()
    backend.assert_not_called()
    redis.assert_not_called()
    delegate.stock_daily_bars.assert_not_called()


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expiry = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, *, ex=None):
        self.values[key] = value
        self.expiry[key] = ex
        return True

    def setex(self, key, seconds, value):
        return self.set(key, value, ex=seconds)

    def delete(self, key):
        self.values.pop(key, None)


@pytestmark_infra
def test_cache_roundtrip_pointer_rotation_and_invalidation(monkeypatch):
    from oskh_data import cache_port

    client = FakeRedis()
    monkeypatch.setattr(cache_port, "_get_redis", lambda: client)
    frame = pd.DataFrame({"close": [1.0]}, index=pd.Index(["20261104"], name="date"))
    assert cache_port.get_daily_bars_cached("600000.SH", "20261102", "20261104") is None
    assert cache_port.set_current_run_id("1d", "run-1")
    assert cache_port.set_daily_bars_cached(frame, "600000.SH", "20261102", "20261104", ttl_seconds=30)
    assert client.expiry["oskh_data:1d:run-1::600000.SH:20261102:20261104:none"] == 30
    assert_frame_equal(cache_port.get_daily_bars_cached("600000.SH", "20261102", "20261104"), frame)
    assert cache_port.set_current_run_id("1d", "run-2")
    assert cache_port.get_daily_bars_cached("600000.SH", "20261102", "20261104") is None
    assert cache_port.invalidate_current_run_id("1d")
    assert cache_port.get_current_run_id("1d") is None


@pytestmark_infra
def test_proxy_local_response_and_current_session_delegation(lake, monkeypatch):
    from common.integrations.duckdb_daily_bars_adapter import DuckDBDailyBarsProxy
    from oskh_data import freshness

    container, _ = lake
    write_bars(container / "stock", "1d", "front", "600000.SH", 11.0)
    output, _ = StockDataReader.build_persistent_db()
    monkeypatch.setattr(freshness, "get_previous_trading_day", lambda: "20261104")
    delegate = Mock()
    proxy = DuckDBDailyBarsProxy(delegate, db_path=str(output))
    try:
        response = proxy.stock_daily_bars(
            symbol="600000.SH", start_date="20261104", end_date="20261104", adjust="front",
        )
        assert response["ok"] and response["data"]["symbol"] == "600000.SH"
        assert len(response["data"]["bars"]) == 1
        assert response["data"]["bars"][0]["close"] == 11.0
        delegate.stock_daily_bars.assert_not_called()
        assert proxy.stock_daily_bars(
            symbol="600000.SH", start_date="20261104", end_date="20261105",
        ) is delegate.stock_daily_bars.return_value
        delegate.stock_daily_bars.assert_called_once()
    finally:
        if proxy._reader is not None:
            proxy._reader.close()


@pytestmark_infra
def test_standalone_rebuild_is_import_safe_and_passes_resolved_paths(lake, monkeypatch):
    from scripts.tr import rebuild_front_duckdb_standalone as rebuild

    container, workspace = lake
    build = Mock(return_value=(5, 2))
    monkeypatch.setattr(rebuild, "rebuild_front_duckdb", build)
    rebuild.main()
    build.assert_called_once_with(container / "stock" / "period=1d", workspace / "stock_data" / "stock_data_front.duckdb")


@pytestmark_infra
def test_path_b_keeps_day_filter_symbol_selection_and_merge_policy(lake):
    from oskh_data.daily_parquet_write import path_b_append_front_today

    container, workspace = lake
    frame = write_bars(container / "stock", "1d", "none", "600000.SH", 12.0)
    # Off-day and unrequested symbols must not leak into today's front mirror.
    extra = frame.assign(time=frame["time"] + 86_400_000, close=99.0)
    path = container / "stock" / "period=1d" / "dividend_type=none" / "symbol=600000_SH" / "data.parquet"
    pd.concat([frame, extra]).to_parquet(path, index=False)
    write_bars(container / "stock", "1d", "none", "600001.SH", 44.0)
    assert path_b_append_front_today(["600000.SH"], pd.Timestamp("2026-11-04"), workspace, mode="batch", max_workers=1) == 1
    output = container / "stock" / "period=1d" / "dividend_type=front"
    stored = pd.read_parquet(output / "symbol=600000_SH" / "data.parquet")
    assert_frame_equal(stored, frame)
    assert not (output / "symbol=600001_SH").exists()
