"""Series-agnostic market regime core (plan-market-regime-unify-2026-10-18)."""

import pandas as pd
import pytest

from backtest.research import bigvalue_regime, market_regime


def _index_parquet(tmp_path, closes, ma5):
    days = pd.bdate_range("20260101", periods=len(closes))
    frame = pd.DataFrame({
        "date": [d.strftime("%Y%m%d") for d in days],
        "close": closes,
        "ma5": ma5,
    })
    path = tmp_path / "index_regime.parquet"
    frame.to_parquet(path, index=False)
    return path


def test_fast1_uses_value_column_as_fast_line(tmp_path):
    path = _index_parquet(tmp_path, [10.0] * 6 + [9.0] * 6, [10.0] * 6 + [9.5] * 6)
    states = market_regime.load_regime(path, fast=1, slow=5, value_col="close")
    values = list(states.values())
    assert values[:6] == [0] * 6             # close == ma5 → equal, neither state
    assert values[-3:] == [-1, -1, -1]       # close < ma5
    # no fake ma1 column is required, and ma1 absence is not "missing columns"
    assert "ma1" not in pd.read_parquet(path).columns


def test_fast1_missing_slow_ma_still_refuses(tmp_path):
    path = _index_parquet(tmp_path, [10.0] * 6, [10.0] * 6)
    frame = pd.read_parquet(path).drop(columns=["ma5"])
    frame.to_parquet(path, index=False)
    with pytest.raises(ValueError, match="missing columns"):
        market_regime.load_regime(path, fast=1, slow=5, value_col="close")


def test_bigvalue_shim_reexports_identity():
    for name in ("load_regime", "confirmed_days", "flatten_reason",
                 "golden_cash_fraction", "with_bigvalue_gate"):
        assert getattr(bigvalue_regime, name) is getattr(market_regime, name)
    assert market_regime.regime_cash_fraction is market_regime.golden_cash_fraction
    assert market_regime.with_regime_gate is market_regime.with_bigvalue_gate


def test_regime_cash_fraction_alias_semantics():
    days = {"20260115": "allowed_golden"}
    assert market_regime.regime_cash_fraction(days, "20260115", 2, 0.5) == 1.0
    assert market_regime.regime_cash_fraction(days, "20260115", 1.2, 0.5) == 0.6
    assert market_regime.regime_cash_fraction(days, "20260114", 2, 0.5) == 0.5
