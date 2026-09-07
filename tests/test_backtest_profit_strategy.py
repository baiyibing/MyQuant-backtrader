from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from common.infra.timekeeping import CN_TZ

import numpy as np

from backtest.ProfitStrategy import StrategyFactory


@dataclass
class _Status:
    stock_code: str = "600000.SH"
    cost_price: float = 10.0
    hold_days: int = 1
    holding_high: float = 10.0


def test_backtest_version5_defaults_to_time_only_force_sell():
    strategy = StrategyFactory.create("version5")
    status = _Status(hold_days=30)

    should_sell, reason = strategy.should_sell(
        status=status,
        current_datetime=datetime(2026, 4, 2, 14, 40, 0, tzinfo=CN_TZ),
        current_price=10.0,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    )

    assert should_sell is False
    assert reason is None


def test_backtest_version5_force_sell_by_time():
    strategy = StrategyFactory.create("version5")
    status = _Status(hold_days=1)

    should_sell, reason = strategy.should_sell(
        status=status,
        current_datetime=datetime(2026, 4, 2, 14, 51, 0, tzinfo=CN_TZ),
        current_price=10.0,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    )

    assert should_sell is True
    assert "force_sell time" in str(reason)


def test_backtest_version5_limit_up_reserve_disabled_by_default():
    strategy = StrategyFactory.create("version5")
    status = _Status(hold_days=1)

    should_sell, _reason = strategy.should_sell(
        status=status,
        current_datetime=datetime(2026, 4, 2, 9, 35, 0, tzinfo=CN_TZ),
        current_price=10.0,
        is_limit_up=True,
        is_limit_down=False,
        indicators=None,
    )

    assert should_sell is False
    assert not hasattr(status, "_reserved_for_limit_up")


def test_backtest_version3_profit_target_effective_in_open_window_when_not_limit_up():
    strategy = StrategyFactory.create("version3")
    status = _Status(hold_days=3, cost_price=10.0, holding_high=12.1)

    should_sell, reason = strategy.should_sell(
        status=status,
        current_datetime=datetime(2026, 4, 2, 9, 35, 0, tzinfo=CN_TZ),
        current_price=12.1,  # +21%
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    )

    assert should_sell is True
    assert str(reason).startswith("profit_take:target")


def test_backtest_main_full_strategy_list_uses_valid_factory_versions():
    repo_root = Path(__file__).resolve().parents[1]
    text = (repo_root / "backtest" / "backtest_main_full.py").read_text(encoding="utf-8")
    assert "version1.1" not in text
    assert "version2.1" not in text
    assert "select_strategies = strategies" in text


def test_rolling_strategy_indicator_config_drives_ma_construction():
    repo_root = Path(__file__).resolve().parents[1]
    text = (repo_root / "backtest" / "rolling_investment_strategy.py").read_text(encoding="utf-8")
    assert "def _resolve_indicator_periods" in text
    assert "for period in self.indicator_periods" in text
    assert "'ma10': bt.indicators.SMA(data.close, period=10)" not in text
    assert "'ma5': bt.indicators.SMA(data.close, period=5)" not in text


def test_backtest_version4_accepts_numpy_real_ma_values():
    strategy = StrategyFactory.create("version4")
    status = _Status(cost_price=10.0, hold_days=2, holding_high=10.5)

    should_sell, reason = strategy.should_sell(
        status=status,
        current_datetime=datetime(2026, 4, 2, 14, 20, 0, tzinfo=CN_TZ),
        current_price=9.8,
        is_limit_up=False,
        is_limit_down=False,
        indicators={"ma5": np.float64(10.0)},
    )
    assert should_sell is True
    assert str(reason).startswith("ma_signal")

    should_buy, reason_buy = strategy.should_buy(
        status=status,
        current_datetime=datetime(2026, 4, 2, 14, 20, 0, tzinfo=CN_TZ),
        current_price=10.2,
        is_limit_up=False,
        is_limit_down=False,
        indicators={"ma10": np.float64(10.0)},
    )
    assert should_buy is True
    assert str(reason_buy).startswith("ma_signal")
