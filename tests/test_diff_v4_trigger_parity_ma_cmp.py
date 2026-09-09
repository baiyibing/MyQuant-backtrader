# -*- coding: utf-8 -*-
"""G.6 Block 2: ma_cmp must not double-scale front-adjusted close."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from scripts.backtest import diff_v4_trigger_parity as parity_mod


def test_bt_eod_ma_cmp_uses_front_close_without_double_factor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """close_none=10, factor=2 → front close=20; ma_cmp must be 20 not 40."""
    trading_date = "20260703"
    front_close = 20.0
    factor = 2.0

    class _FakeReader:
        def read_stock(self, *_args: Any, **_kwargs: Any) -> pd.DataFrame:
            idx = pd.bdate_range(end=pd.Timestamp(trading_date), periods=12)
            closes = [18.0] * 11 + [front_close]
            return pd.DataFrame({"close": closes}, index=idx)

    monkeypatch.setattr(parity_mod, "StockDataReader", _FakeReader)
    monkeypatch.setattr(parity_mod, "get_adj_factor", lambda _stock, _date: factor)

    raw, got_factor, ma_val, ma_cmp, mode = parity_mod._bt_eod_snapshot(
        "000001.SZ",
        trading_date,
        "SELL",
        params=parity_mod.DEFAULT_V4_PARAMS,
    )

    assert mode == "eod_recomputed"
    assert raw == pytest.approx(front_close)
    assert got_factor == pytest.approx(factor)
    assert ma_val is not None
    assert ma_cmp == pytest.approx(front_close)
    assert ma_cmp != pytest.approx(front_close * factor)


def test_live_eod_ma_cmp_uses_front_close_without_double_factor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    front_close = 20.0
    factor = 2.0
    trading_date = "20260703"
    trade_days = pd.bdate_range(end=pd.Timestamp(trading_date), periods=12).strftime("%Y%m%d").tolist()

    def _fake_trade_days_df(*_args: Any, **_kwargs: Any) -> pd.DataFrame:
        return pd.DataFrame({"date": pd.to_datetime(trade_days)})

    def _fake_expected_trade_dates(_td_df: Any, count: int) -> list[str]:
        return trade_days[-count:]

    def _fake_daily_bars_df(*_args: Any, **_kwargs: Any) -> pd.DataFrame:
        return pd.DataFrame({"close": [front_close]})

    def _fake_aligned_close_series(_df_bar: Any, expected: list[str]) -> Any:
        import numpy as np

        return np.array([18.0] * (len(expected) - 1) + [front_close], dtype=float)

    monkeypatch.setattr(
        "live_trading.indicators.ma_provider._qmt_trade_days_df",
        _fake_trade_days_df,
    )
    monkeypatch.setattr(
        "live_trading.indicators.ma_provider._expected_trade_dates",
        _fake_expected_trade_dates,
    )
    monkeypatch.setattr(
        "live_trading.indicators.ma_provider._qmt_daily_bars_df",
        _fake_daily_bars_df,
    )
    monkeypatch.setattr(
        "live_trading.indicators.ma_provider._aligned_close_series",
        _fake_aligned_close_series,
    )
    monkeypatch.setattr(
        "live_trading.indicators.ma_provider._ma_fund_daily_adjust",
        lambda: "front",
    )
    monkeypatch.setattr(parity_mod, "get_adj_factor", lambda _stock, _date: factor)

    raw, got_factor, ma_val, ma_cmp, mode = parity_mod._live_eod_snapshot(
        "000001.SZ",
        trading_date,
        "SELL",
        params=parity_mod.DEFAULT_V4_PARAMS,
        bar_policy="prior_completed_session",
    )

    assert mode == "eod_recomputed"
    assert raw == pytest.approx(front_close)
    assert got_factor == pytest.approx(factor)
    assert ma_val is not None
    assert ma_cmp == pytest.approx(front_close)
    assert ma_cmp != pytest.approx(front_close * factor)
