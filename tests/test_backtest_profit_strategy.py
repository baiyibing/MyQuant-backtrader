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
    text = (repo_root / "backtest" / "backtest_main_full.py").read_text(
        encoding="utf-8"
    )
    assert "version1.1" not in text
    assert "version2.1" not in text
    assert "select_strategies = strategies" in text


def test_rolling_strategy_indicator_config_drives_ma_construction():
    repo_root = Path(__file__).resolve().parents[1]
    text = (repo_root / "backtest" / "rolling_investment_strategy.py").read_text(
        encoding="utf-8"
    )
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


# ---------------------------------------------------------------------------
# 策略6（version6）：6% 盘中止损 + 1% 锚定分档回撤止盈
# 边界用例一律用跨线价（±0.002）而非恰好压线，规避浮点 epsilon；
# 触发价 < 买入价不止盈；峰值间隔不能 < 15 分钟。
# ---------------------------------------------------------------------------

from datetime import datetime as _dt


def _v6(**overrides):
    return StrategyFactory.create("version6", overrides or None)


def _st(cost=10.0, high=10.0, days=1):
    return _Status(cost_price=cost, hold_days=days, holding_high=high)


def test_v6_factory_registered_with_expected_defaults():
    s = StrategyFactory.create("version6")
    assert s.params["stop_loss_pct"] == 0.06
    assert s.params["profit_base_pct"] == 0.01
    assert s.params["trailing_rules"] == {1: 0.30, 2: 0.40, 3: 0.50, 4: 0.60}
    assert s.params["trailing_default"] == 0.70
    assert s.params["positive_trail_ratio"] == 0.50


def test_v6_stop_loss_triggers_at_6pct_not_5pct():
    s = _v6()  # 峰值=成本（无正利润历史），隔离止损分支
    ok, reason = s.should_sell(
        _st(cost=10.0, high=10.0), _dt(2025, 11, 3, 10, 0), 9.411
    )
    assert not ok  # -5.89% 未触发
    ok, reason = s.should_sell(
        _st(cost=10.0, high=10.0), _dt(2025, 11, 3, 10, 1), 9.398
    )
    assert ok and reason.startswith("stop_loss")


def test_v6_t1_trailing_30pct_of_peak_excess_above_1pct():
    s = _v6()
    now = _dt(2025, 11, 3, 10, 0)
    # 峰值 10.5（+5%，超额+4%）；T+1 档 30% → 触发线 = 1.01 + 0.3*0.04 = +2.2% → 10.22
    ok, reason = s.should_sell(_st(cost=10.0, high=10.5, days=1), now, 10.222)
    assert not ok
    ok, reason = s.should_sell(_st(cost=10.0, high=10.5, days=1), now, 10.218)
    assert ok and reason.startswith("profit_take:drawdown") and "T+1" in reason


def test_v6_tiers_t2_t3_t5():
    s = _v6()
    now = _dt(2025, 11, 4, 10, 0)
    # 峰值 +5%（超额 4%）：T+2 40% → 1.01+0.4*0.04=+2.6% → 10.26
    ok, _ = s.should_sell(_st(cost=10.0, high=10.5, days=2), now, 10.262)
    assert not ok
    ok, _ = s.should_sell(_st(cost=10.0, high=10.5, days=2), now, 10.258)
    assert ok
    # T+3 50% → +3.0% → 10.30
    ok, _ = s.should_sell(_st(cost=10.0, high=10.5, days=3), now, 10.302)
    assert not ok
    ok, _ = s.should_sell(_st(cost=10.0, high=10.5, days=3), now, 10.298)
    assert ok
    # T+5+ 70% → +3.8% → 10.38
    ok, reason = s.should_sell(_st(cost=10.0, high=10.5, days=5), now, 10.378)
    assert ok and "T+5" in reason
    ok, _ = s.should_sell(_st(cost=10.0, high=10.5, days=5), now, 10.382)
    assert not ok


def test_v6_fall_below_1pct_anchor_after_peak_still_trails():
    s = _v6()
    ok, reason = s.should_sell(
        _st(cost=10.0, high=10.5, days=1), _dt(2025, 11, 3, 14, 0), 10.05
    )
    assert ok and reason.startswith("profit_take:drawdown")


def test_v6_no_trail_when_peak_not_above_1pct():
    s = _v6()
    now = _dt(2025, 11, 3, 10, 0)
    ok, _ = s.should_sell(_st(cost=10.0, high=10.009, days=1), now, 10.002)
    assert not ok


def test_v6_tp_blocked_within_15_minutes_of_peak():
    s = _v6()
    peak_tm = _dt(2025, 11, 3, 10, 0)
    now = _dt(2025, 11, 3, 10, 14)
    ok, _ = s.should_sell(
        _st(cost=10.0, high=10.5, days=1), now, 10.20, indicators={"peak_time": peak_tm}
    )
    assert not ok
    later = _dt(2025, 11, 3, 10, 15)
    ok, reason = s.should_sell(
        _st(cost=10.0, high=10.5, days=1),
        later,
        10.20,
        indicators={"peak_time": peak_tm},
    )
    assert ok and reason.startswith("profit_take:drawdown")


def test_v6_no_trail_when_price_below_cost():
    s = _v6()
    ok, _ = s.should_sell(
        _st(cost=10.0, high=10.5, days=1), _dt(2025, 11, 3, 10, 20), 9.95
    )
    assert not ok


def test_v6_below_cost_without_stop_or_positive_peak_observes():
    s = _v6()
    # 开盘价 < 买入价、无正利润峰值、未触发 6% 止损 → 观察（无动作）
    ok, _ = s.should_sell(
        _st(cost=10.0, high=10.0, days=1), _dt(2025, 11, 3, 9, 31), 9.85
    )
    assert not ok
    ok, _ = s.should_sell(
        _st(cost=10.0, high=10.0, days=1), _dt(2025, 11, 3, 9, 32), 9.95
    )
    assert not ok


def test_v6_adapter_routes_sell_to_local_strategy():
    from backtest.preset_strategy_adapter import create_preset_strategy_adapter

    adapter = create_preset_strategy_adapter("version6")
    ok, reason = adapter.should_sell(
        _st(cost=10.0, high=10.0), _dt(2025, 11, 3, 10, 0), 9.398
    )
    assert ok and reason.startswith("stop_loss")


# ---------------------------------------------------------------------------
# 策略8（version8）：20% 止损 + 0%~15%→+2% + 15% 锚分档 + 涨幅>120% 最高价回撤 20%
# ---------------------------------------------------------------------------


def _v8(**overrides):
    return StrategyFactory.create("version8", overrides or None)


def test_v8_factory_registered_with_expected_defaults():
    s = StrategyFactory.create("version8")
    assert s.params["stop_loss_pct"] == 0.20


def test_v8_stop_loss_triggers_at_20pct_not_19pct():
    s = _v8()
    ok, _ = s.should_sell(
        _st(cost=10.0, high=10.0), _dt(2025, 11, 3, 10, 0), 8.011
    )
    assert not ok
    ok, reason = s.should_sell(
        _st(cost=10.0, high=10.0), _dt(2025, 11, 3, 10, 1), 7.989
    )
    assert ok and reason.startswith("stop_loss")


def test_v8_band_15_to_40_floors_at_15pct():
    s = _v8()
    now = _dt(2025, 11, 3, 10, 0)
    ok, _ = s.should_sell(_st(cost=10.0, high=13.0, days=1), now, 11.511)
    assert not ok
    ok, reason = s.should_sell(_st(cost=10.0, high=13.0, days=1), now, 11.489)
    assert ok and "trail:band:15" in reason


def test_v8_small_band_floors_at_2pct():
    s = _v8()
    now = _dt(2025, 11, 3, 10, 0)
    ok, _ = s.should_sell(_st(cost=10.0, high=10.10, days=1), now, 10.05)
    assert not ok
    ok, _ = s.should_sell(_st(cost=10.0, high=10.60, days=1), now, 10.201)
    assert not ok
    ok, reason = s.should_sell(_st(cost=10.0, high=10.60, days=1), now, 10.20)
    assert ok and "trail:band:2" in reason


def test_v8_no_tp_when_small_band_still_above_2pct():
    s = _v8()
    ok, _ = s.should_sell(
        _st(cost=10.0, high=11.50, days=1), _dt(2025, 11, 3, 10, 0), 11.40
    )
    assert not ok


def test_v8_peak_dd_when_gain_over_120pct():
    s = _v8()
    # 峰值 +200%：无分档地板；最高价×80%=24。23 只触峰回撤。
    ok, reason = s.should_sell(
        _st(cost=10.0, high=30.0, days=1), _dt(2025, 11, 3, 10, 0), 23.00
    )
    assert ok and "trail:peak_dd" in reason


def test_v8_adapter_routes_sell_to_local_strategy():
    from backtest.preset_strategy_adapter import create_preset_strategy_adapter

    adapter = create_preset_strategy_adapter("version8")
    ok, reason = adapter.should_sell(
        _st(cost=10.0, high=10.0), _dt(2025, 11, 3, 10, 0), 7.989
    )
    assert ok and reason.startswith("stop_loss")
