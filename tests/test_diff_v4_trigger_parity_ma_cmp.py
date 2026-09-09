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


# live 侧用例（monkeypatch live_trading.indicators.ma_provider）随 1.3 迁移删去：
# live_trading 属主仓域（AGENTS.md 明确排除），本仓只保留 bt 侧 parity 覆盖。
