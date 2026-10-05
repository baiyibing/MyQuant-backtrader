"""合成 K 线：当根扫一个持仓，成交或跳过。不接策略，不读湖。"""

from pathlib import Path

import pytest

from backtest.research.bar_scan_exit import HeldPosition, OhlcBar, scan_bar_exit


def _pos(**kwargs):
    base = dict(cost=10.0, peak=10.0, stop_pct=0.02, drawdown_take_profit=0.50)
    base.update(kwargs)
    return HeldPosition(**base)


def test_gap_through_stop_fills_at_open():
    # 止损价 9.80。开盘已在止损价之下，按开盘价成交，不按止损价。
    result = scan_bar_exit(OhlcBar(9.70, 9.90, 9.50, 9.85), _pos())
    assert result.decision == "fill"
    assert result.fill_price == 9.70
    assert result.reason == "stop_loss:gap_open"


def test_touch_fills_at_stop_price_not_at_low():
    # 开盘在止损价之上，low 穿过 9.80，按止损价成交，即使收盘收回来。
    result = scan_bar_exit(OhlcBar(10.10, 10.20, 9.70, 10.00), _pos())
    assert result.decision == "fill"
    assert result.fill_price == pytest.approx(9.80)
    assert result.reason == "stop_loss:touch"
    assert result.fill_price != 9.70


def test_stop_wins_over_drawdown_on_the_same_bar():
    result = scan_bar_exit(
        OhlcBar(10.50, 12.00, 9.70, 11.00),
        _pos(peak=12.0),
    )
    assert result.reason == "stop_loss:touch"
    assert result.fill_price == pytest.approx(9.80)


def test_drawdown_take_profit_fills_at_close():
    # 峰值 12、成本 10，50% 回撤线是 11。收盘 11 恰好达到，按收盘价成交。
    result = scan_bar_exit(OhlcBar(11.80, 12.00, 11.00, 11.00), _pos(peak=12.0))
    assert result.decision == "fill"
    assert result.fill_price == 11.00
    assert result.reason == "profit_take:drawdown:50"
    assert result.peak == 12.0


def test_intrabar_drawdown_that_recovers_is_a_skip():
    # low 穿过回撤线，但收盘没有。这不是一张挂着的止盈单。
    result = scan_bar_exit(OhlcBar(11.80, 12.00, 10.20, 11.60), _pos(peak=12.0))
    assert result.decision == "skip"
    assert result.fill_price is None
    assert result.reason == ""


def test_close_below_cost_but_above_stop_does_not_take_profit():
    result = scan_bar_exit(OhlcBar(10.05, 10.10, 9.85, 9.90), _pos(peak=11.0))
    assert result.decision == "skip"


def test_high_lifts_peak_before_drawdown_check():
    # 进场峰值 10.5，本根 high 抬到 12，收盘 11 相对新峰值回撤一半。
    result = scan_bar_exit(OhlcBar(11.50, 12.00, 11.00, 11.00), _pos(peak=10.5))
    assert result.decision == "fill"
    assert result.reason == "profit_take:drawdown:50"
    assert result.peak == 12.0
    assert result.fill_price == 11.00


def test_quiet_bar_skips_and_keeps_higher_peak():
    # 峰值 11、成本 10，50% 回撤线是 10.5。收盘 10.70 还没到。
    result = scan_bar_exit(OhlcBar(10.60, 10.80, 10.50, 10.70), _pos(peak=11.0))
    assert result.decision == "skip"
    assert result.fill_price is None
    assert result.reason == ""
    assert result.peak == 11.0


def test_quiet_bar_reports_lifted_peak():
    # high 把峰值抬到 10.80，收盘 10.50 的回撤不到一半，只跳过并带回新峰值。
    result = scan_bar_exit(OhlcBar(10.45, 10.80, 10.40, 10.50), _pos(peak=10.4))
    assert result.decision == "skip"
    assert result.fill_price is None
    assert result.peak == 10.80


def test_rejects_bad_stop_and_broken_bar():
    with pytest.raises(ValueError):
        scan_bar_exit(OhlcBar(10, 10, 10, 10), _pos(stop_pct=0.0))
    with pytest.raises(ValueError):
        scan_bar_exit(OhlcBar(10, 9, 8, 10), _pos())


def test_module_is_not_an_order_system():
    import backtest.research.bar_scan_exit as mod
    text = Path(mod.__file__).read_text(encoding="utf-8")
    for banned in ("SubmitOrder", "order_type", "EventBus", "Fees", "write_lake", "4090", "minute_orders_backend"):
        assert banned not in text
    assert Path("backtest/research/csv_minute_backtest.py").is_file()

def test_explicit_same_bar_matches_default():
    bar = OhlcBar(10.10, 10.20, 9.70, 10.00)
    assert scan_bar_exit(bar, _pos(), timing="same_bar") == scan_bar_exit(bar, _pos())


def test_next_bar_touch_fills_at_next_open_not_stop():
    signal = OhlcBar(10.10, 10.20, 9.70, 10.00)
    nxt = OhlcBar(9.50, 9.60, 9.40, 9.55)
    result = scan_bar_exit(signal, _pos(), timing="next_bar", next_bar=nxt)
    assert result.decision == "fill"
    assert result.fill_price == 9.50
    assert result.reason == "stop_loss:touch:next_open"
    same = scan_bar_exit(signal, _pos())
    assert same.fill_price == pytest.approx(9.80)
    assert same.reason == "stop_loss:touch"


def test_next_bar_gap_fills_at_next_open_not_signal_open():
    signal = OhlcBar(9.70, 9.90, 9.50, 9.85)
    nxt = OhlcBar(9.40, 9.80, 9.30, 9.60)
    result = scan_bar_exit(signal, _pos(), timing="next_bar", next_bar=nxt)
    assert result.fill_price == 9.40
    assert result.reason == "stop_loss:gap_open:next_open"
    assert result.fill_price != signal.open


def test_next_bar_drawdown_fills_at_next_open():
    signal = OhlcBar(11.80, 12.00, 11.00, 11.00)
    nxt = OhlcBar(10.90, 11.20, 10.80, 11.10)
    result = scan_bar_exit(signal, _pos(peak=12.0), timing="next_bar", next_bar=nxt)
    assert result.decision == "fill"
    assert result.fill_price == 10.90
    assert result.reason == "profit_take:drawdown:50:next_open"
    assert result.peak == 12.0


def test_next_bar_skip_does_not_need_a_following_bar():
    result = scan_bar_exit(
        OhlcBar(10.60, 10.80, 10.50, 10.70),
        _pos(peak=11.0),
        timing="next_bar",
    )
    assert result.decision == "skip"
    assert result.fill_price is None
    assert result.reason == ""
    assert result.peak == 11.0


def test_next_bar_fill_without_next_bar_raises():
    with pytest.raises(ValueError):
        scan_bar_exit(OhlcBar(10.10, 10.20, 9.70, 10.00), _pos(), timing="next_bar")


def test_unknown_timing_and_same_bar_with_next_bar_raise():
    with pytest.raises(ValueError):
        scan_bar_exit(OhlcBar(10, 10, 10, 10), _pos(), timing="limit_book")
    with pytest.raises(ValueError):
        scan_bar_exit(
            OhlcBar(10, 10, 10, 10),
            _pos(),
            timing="same_bar",
            next_bar=OhlcBar(10, 10, 10, 10),
        )

