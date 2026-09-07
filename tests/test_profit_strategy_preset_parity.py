from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backtest.ProfitStrategy import StrategyFactory
from common.infra.timekeeping import CN_TZ
from trade_decision.presets import SellPresetContext, evaluate_sell_preset


@dataclass
class _Status:
    stock_code: str = "600000.SH"
    cost_price: float = 10.0
    hold_days: int = 1
    holding_high: float = 10.0


def _compare_should_sell(
    *,
    version: str,
    status: _Status,
    current_datetime: datetime,
    current_price: float,
    is_limit_up: bool,
    indicators=None,
) -> None:
    strategy = StrategyFactory.create(version)
    bt_should_sell, _bt_reason = strategy.should_sell(
        status=status,
        current_datetime=current_datetime,
        current_price=current_price,
        is_limit_up=is_limit_up,
        is_limit_down=False,
        indicators=indicators,
    )
    preset_decision = evaluate_sell_preset(
        version,
        strategy.params,
        SellPresetContext(
            cost_price=float(status.cost_price),
            current_price=float(current_price),
            holding_high=float(status.holding_high),
            hold_days=int(status.hold_days),
            is_limit_up=bool(is_limit_up),
            now_local=current_datetime,
            indicators=indicators,
            reserved_for_limit_up=bool(getattr(status, "_reserved_for_limit_up", False)),
        ),
    )
    assert bt_should_sell is preset_decision.should_sell


def test_version1_parity_stop_loss():
    _compare_should_sell(
        version="version1",
        status=_Status(cost_price=10.0, holding_high=10.5, hold_days=2),
        current_datetime=datetime(2026, 4, 2, 14, 30, 0, tzinfo=CN_TZ),
        current_price=9.7,
        is_limit_up=False,
    )


def test_version2_parity_dynamic_drawdown():
    _compare_should_sell(
        version="version2",
        status=_Status(cost_price=100.0, holding_high=120.0, hold_days=1),
        current_datetime=datetime(2026, 4, 2, 14, 30, 0, tzinfo=CN_TZ),
        current_price=110.0,
        is_limit_up=False,
    )


def test_version3_parity_profit_target_after_open_window():
    _compare_should_sell(
        version="version3",
        status=_Status(cost_price=10.0, holding_high=12.1, hold_days=3),
        current_datetime=datetime(2026, 4, 2, 9, 45, 0, tzinfo=CN_TZ),
        current_price=12.1,
        is_limit_up=False,
    )


def test_version4_parity_ma_sell_signal():
    _compare_should_sell(
        version="version4",
        status=_Status(cost_price=10.0, holding_high=10.5, hold_days=3),
        current_datetime=datetime(2026, 4, 2, 14, 10, 0, tzinfo=CN_TZ),
        current_price=9.8,
        is_limit_up=False,
        indicators={"ma5": 10.0},
    )


def test_version5_parity_force_sell_time():
    _compare_should_sell(
        version="version5",
        status=_Status(cost_price=10.0, holding_high=10.2, hold_days=1),
        current_datetime=datetime(2026, 4, 2, 14, 51, 0, tzinfo=CN_TZ),
        current_price=10.0,
        is_limit_up=False,
    )
