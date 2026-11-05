"""Knife 18 step 1: public read entrances must enforce adjustment policy.

Only caller discovery and storage boundaries are replaced. The real public
entries and policy run together, without a lake, Redis, or QMT connection.
BT's StockDataReader supports stock/ETF only; there is no index entrance.
"""

from pathlib import Path
from types import ModuleType
from typing import Any, Callable
from unittest.mock import Mock, call

import pandas as pd
import pytest


@pytest.fixture
def reader_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setenv("OSKH_DATA_READER_MODE", "parquet")
    from oskh_data import reader

    assert reader.DEFAULT_READER_MODE == "parquet"
    monkeypatch.setattr(reader, "logger", Mock())
    return reader


@pytest.fixture(params=["live_trading.something", "trade_decision.something", ""])
def rejected_caller(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    reader_module: ModuleType,
) -> str:
    caller = str(request.param)
    # Inject caller identity as in #558; leave the policy itself intact.
    monkeypatch.setattr(reader_module, "_get_caller_module", lambda: caller)
    return caller


@pytest.fixture
def make_reader(
    reader_module: ModuleType, tmp_path: Path,
) -> Callable[[str], Any]:
    def make(asset_type: str) -> Any:
        return reader_module.StockDataReader(
            base_dir=str(tmp_path), project_root=str(tmp_path), asset_type=asset_type,
        )

    return make


@pytest.fixture
def backend_spies(
    monkeypatch: pytest.MonkeyPatch, reader_module: ModuleType,
) -> dict[str, Mock]:
    spies = {}
    # The switch removes local storage implementations. Spy on the real infra
    # boundary so every original #563 entry/mode/period gate still runs intact.
    for name in ("read_stock", "scan_stocks", "_daily_connection", "_read_parquet", "_query"):
        spy = Mock(name=name, return_value=pd.DataFrame({"close": [1.0]}))
        monkeypatch.setattr(reader_module._InfraStockDataReader, name, spy)
        spies[name] = spy
    return spies


def assert_no_backend_calls(spies: dict[str, Mock]) -> None:
    for spy in spies.values():
        spy.assert_not_called()


@pytest.mark.parametrize("entry", ["read_stock", "scan_stocks"])
@pytest.mark.parametrize("asset_type", ["stock", "etf"])
@pytest.mark.parametrize("adjust", ["front", "back"])
@pytest.mark.parametrize("period", ["1d", "1m"])
@pytest.mark.parametrize("mode", ["parquet", "duckdb", "duckdb_persistent"])
def test_reader_rejects_before_any_backend(
    rejected_caller: str, make_reader: Callable[[str], Any],
    backend_spies: dict[str, Mock], entry: str, asset_type: str,
    adjust: str, period: str, mode: str,
) -> None:
    reader = make_reader(asset_type)
    # Exercise every dispatch branch without opening a DuckDB connection.
    reader._mode = mode
    symbol = "510180.SH" if asset_type == "etf" else "000001.SZ"
    symbols = symbol if entry == "read_stock" else [symbol]

    with pytest.raises(RuntimeError, match="DataAccessPolicyError"):
        getattr(reader, entry)(symbols, adjust_type=adjust, period=period)

    assert_no_backend_calls(backend_spies)


@pytest.mark.parametrize("entry", ["read_stock", "scan_stocks"])
@pytest.mark.parametrize("asset_type", ["stock", "etf"])
def test_none_still_reaches_reader_backend(
    rejected_caller: str, make_reader: Callable[[str], Any],
    backend_spies: dict[str, Mock], entry: str, asset_type: str,
) -> None:
    reader = make_reader(asset_type)
    symbol = "510180.SH" if asset_type == "etf" else "000001.SZ"
    symbols = symbol if entry == "read_stock" else [symbol]
    backend = backend_spies[entry]

    assert getattr(reader, entry)(symbols, adjust_type="none") is backend.return_value
    backend.assert_called_once_with(symbols, None, None, "1d", "none", None)


@pytest.mark.parametrize("asset_type", ["stock", "etf"])
@pytest.mark.parametrize("adjust", ["front", "back"])
def test_ma_provider_whitelist_still_reaches_reader_backend(
    monkeypatch: pytest.MonkeyPatch, reader_module: ModuleType,
    make_reader: Callable[[str], Any], backend_spies: dict[str, Mock],
    asset_type: str, adjust: str,
) -> None:
    monkeypatch.setattr(
        reader_module, "_get_caller_module",
        lambda: "live_trading.indicators.ma_provider",
    )
    reader = make_reader(asset_type)
    backend = backend_spies["read_stock"]
    symbol = "510180.SH" if asset_type == "etf" else "000001.SZ"

    assert reader.read_stock(symbol, adjust_type=adjust) is backend.return_value
    backend.assert_called_once_with(symbol, None, None, "1d", adjust, None)


@pytest.mark.parametrize("adjust", ["front", "back"])
def test_etf_fund_daily_propagates_policy_rejection(
    monkeypatch: pytest.MonkeyPatch, rejected_caller: str,
    make_reader: Callable[[str], Any], backend_spies: dict[str, Mock], adjust: str,
) -> None:
    from oskh_data import etf_local_bars

    monkeypatch.setattr(etf_local_bars, "logger", Mock())
    get_reader = Mock(return_value=make_reader("etf"))
    monkeypatch.setattr(etf_local_bars, "get_etf_stock_data_reader", get_reader)

    with pytest.raises(RuntimeError, match="DataAccessPolicyError"):
        etf_local_bars.default_etf_fund_daily(
            "510180.SH", "20261102", "20261104", adjust=adjust,
        )

    get_reader.assert_called_once_with()
    assert_no_backend_calls(backend_spies)


def test_etf_fund_daily_keeps_non_policy_failure_soft(
    monkeypatch: pytest.MonkeyPatch, rejected_caller: str,
    make_reader: Callable[[str], Any], backend_spies: dict[str, Mock],
) -> None:
    from oskh_data import etf_local_bars

    monkeypatch.setattr(etf_local_bars, "logger", Mock())
    monkeypatch.setattr(
        etf_local_bars, "get_etf_stock_data_reader", Mock(return_value=make_reader("etf")),
    )
    backend = backend_spies["read_stock"]
    backend.side_effect = RuntimeError("storage unavailable")

    assert etf_local_bars.default_etf_fund_daily(
        "510180.SH", "20261102", "20261104", adjust="none",
    ).empty
    backend.assert_called_once()


@pytest.mark.parametrize("adjust", ["front", "back", " FRONT ", " Back "])
def test_cache_rejects_before_redis_or_pointer_access(
    monkeypatch: pytest.MonkeyPatch, rejected_caller: str, adjust: str,
) -> None:
    from oskh_data import cache_port

    redis = Mock()
    get_redis = Mock(return_value=redis)
    get_run_id = Mock(return_value="k18-run")
    monkeypatch.setattr(cache_port, "_get_redis", get_redis)
    monkeypatch.setattr(cache_port, "get_current_run_id", get_run_id)

    with pytest.raises(RuntimeError, match="DataAccessPolicyError"):
        cache_port.get_daily_bars_cached(
            "000001.SZ", "20261102", "20261104", adjust=adjust,
        )

    get_redis.assert_not_called()
    get_run_id.assert_not_called()
    redis.get.assert_not_called()


def test_cache_none_still_returns_cached_bars(
    monkeypatch: pytest.MonkeyPatch, rejected_caller: str,
) -> None:
    from oskh_data import cache_port

    redis = Mock()
    redis.get.side_effect = [b"k18-run", b"fake-parquet"]
    monkeypatch.setattr(cache_port, "_get_redis", Mock(return_value=redis))
    expected = pd.DataFrame({"close": [1.0]})
    decode = Mock(return_value=expected)
    monkeypatch.setattr(pd, "read_parquet", decode)

    assert cache_port.get_daily_bars_cached(
        "000001.SZ", "20261102", "20261104", adjust="none",
    ) is expected
    assert redis.get.call_args_list == [
        call("oskh_data:current_run_id:1d"),
        call("oskh_data:1d:k18-run::000001.SZ:20261102:20261104:none"),
    ]
    decode.assert_called_once()


@pytest.mark.parametrize("entry", ["stock_daily_bars", "stock_daily_bars_cfg_only"])
@pytest.mark.parametrize("asset_type", ["stock", "etf"])
@pytest.mark.parametrize("adjust", ["front", "back"])
def test_proxy_t_minus_1_propagates_rejection_without_qmt_fallback(
    monkeypatch: pytest.MonkeyPatch, rejected_caller: str,
    make_reader: Callable[[str], Any], backend_spies: dict[str, Mock],
    entry: str, asset_type: str, adjust: str,
) -> None:
    from common.integrations.duckdb_daily_bars_adapter import DuckDBDailyBarsProxy
    from oskh_data import freshness

    # Pin the external calendar result; exercise the real T-1 routing predicate.
    monkeypatch.setattr(freshness, "get_previous_trading_day", lambda: "20261104")
    delegate = Mock()
    proxy = DuckDBDailyBarsProxy(delegate, asset_type=asset_type)
    proxy._reader = make_reader(asset_type)
    symbol = "510180.SH" if asset_type == "etf" else "000001.SZ"

    with pytest.raises(RuntimeError, match="DataAccessPolicyError"):
        getattr(proxy, entry)(
            symbol=symbol, start_date="20261102", end_date="20261104",
            adjust=adjust,
        )

    assert_no_backend_calls(backend_spies)
    delegate.stock_daily_bars.assert_not_called()
    delegate.stock_daily_bars_cfg_only.assert_not_called()


@pytest.mark.parametrize("entry", ["stock_daily_bars", "stock_daily_bars_cfg_only"])
def test_proxy_keeps_non_policy_failure_fallback(
    monkeypatch: pytest.MonkeyPatch, rejected_caller: str,
    make_reader: Callable[[str], Any], backend_spies: dict[str, Mock], entry: str,
) -> None:
    from common.integrations import duckdb_daily_bars_adapter as adapter
    from oskh_data import freshness

    monkeypatch.setattr(adapter, "logger", Mock())
    monkeypatch.setattr(freshness, "get_previous_trading_day", lambda: "20261104")
    delegate = Mock()
    proxy = adapter.DuckDBDailyBarsProxy(delegate)
    proxy._reader = make_reader("stock")
    backend = backend_spies["read_stock"]
    backend.side_effect = RuntimeError("storage unavailable")

    result = getattr(proxy, entry)(
        symbol="000001.SZ", start_date="20261102", end_date="20261104",
        adjust="none", trace_id="k18-probe", timeout_sec=1.0, poll_sec=0.1,
    )

    assert result is delegate.stock_daily_bars.return_value
    backend.assert_called_once()
    delegate.stock_daily_bars.assert_called_once_with(
        symbol="000001.SZ", start_date="20261102", end_date="20261104",
        adjust="none", trace_id="k18-probe", timeout_sec=1.0, poll_sec=0.1,
    )
