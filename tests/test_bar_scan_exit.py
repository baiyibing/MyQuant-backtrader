"""Synthetic bar scenarios mapped onto HeldMinuteCursor + FillConfig.

Build one-row OHLC arrays (two for next-open fills); advance open then close.
Cost 10 and stop_pct 0.02 give a 9.80 stop: gaps use open, bar_low touches
use the line, and stops precede the 50% close drawdown callback. Open lifts
peak before that callback; recovered/quiet bars skip. next_bar_open queues
signals for the following open, while skips need no following bar. Disable
peak-gap gating to isolate these bar rules; stop_pct=0 disables the stop.
"""

import pytest

from backtest.research.fill_config import FillConfig
from backtest.research.minute_held_scan_core import HeldMinuteCursor


def _drawdown(close, cost, peak, n_days):
    if close >= cost and peak > cost and (peak - close) / (peak - cost) >= 0.50:
        return "profit_take:drawdown:50"
    return None


def _cursor(*bars, **kwargs):
    o, h, l, c = (list(values) for values in zip(*bars))
    options = dict(
        cost=10.0, peak=10.0, stop_pct=0.02, n_days=1, can_sell=True,
        profit_base=0.0, trail_ratio=0.0, peak_gap_min=0,
        take_profit=_drawdown, fill_config=FillConfig(),
    )
    options.update(kwargs)
    return HeldMinuteCursor(o=o, h=h, l=l, c=c, **options)


def _advance_bar(cursor, idx=0):
    opening = cursor.advance(idx, "open")
    closing = cursor.advance(idx, "close")
    return opening if opening is not None else closing


def _touch_config(timing="this_bar"):
    return FillConfig(trigger_basis="bar_low", fill_timing=timing, fill_at="line")


def test_gap_through_stop_fills_at_open():
    cursor = _cursor((9.70, 9.90, 9.50, 9.85))
    assert cursor.advance(0, "open") == (0, 9.70, "stop_loss:gap_open")
    assert cursor.advance(0, "close") is None


def test_touch_fills_at_stop_price_not_at_low():
    cursor = _cursor((10.10, 10.20, 9.70, 10.00), fill_config=_touch_config())
    assert cursor.advance(0, "open") is None
    idx, price, reason = cursor.advance(0, "close")
    assert idx == 0
    assert price == pytest.approx(9.80)
    assert price != 9.70
    assert reason == "stop_loss:touch"


def test_stop_wins_over_drawdown_on_the_same_bar():
    cursor = _cursor((10.50, 12.00, 9.70, 11.00), peak=12.0,
                     fill_config=_touch_config())
    assert _drawdown(11.0, 10.0, 12.0, 1) == "profit_take:drawdown:50"
    idx, price, reason = _advance_bar(cursor)
    assert idx == 0
    assert reason == "stop_loss:touch"
    assert price == pytest.approx(9.80)


def test_drawdown_take_profit_fills_at_close():
    cursor = _cursor((11.80, 12.00, 11.00, 11.00))
    assert cursor.advance(0, "open") is None
    assert cursor.peak == 12.0
    assert cursor.advance(0, "close") == (0, 11.00, "profit_take:drawdown:50")


def test_intrabar_drawdown_that_recovers_is_a_skip():
    cursor = _cursor((11.80, 12.00, 10.20, 11.60), peak=12.0)
    assert _advance_bar(cursor) is None
    assert cursor.peak == 12.0


def test_close_below_cost_but_above_stop_does_not_take_profit():
    cursor = _cursor((10.05, 10.10, 9.85, 9.90), peak=11.0)
    assert _advance_bar(cursor) is None


def test_high_lifts_peak_before_drawdown_check():
    cursor = _cursor((11.50, 12.00, 11.00, 11.00), peak=10.5)
    assert cursor.advance(0, "open") is None
    assert cursor.peak == 12.0
    assert cursor.advance(0, "close") == (0, 11.00, "profit_take:drawdown:50")
    assert cursor.peak == 12.0


def test_quiet_bar_skips_and_keeps_higher_peak():
    cursor = _cursor((10.60, 10.80, 10.50, 10.70), peak=11.0)
    assert _advance_bar(cursor) is None
    assert cursor.peak == 11.0


def test_quiet_bar_reports_lifted_peak():
    cursor = _cursor((10.45, 10.80, 10.40, 10.50), peak=10.4)
    assert _advance_bar(cursor) is None
    assert cursor.peak == 10.80


def test_zero_stop_pct_disables_stop():
    # bar_scan_exit raised on stop_pct=0; HeldMinuteCursor treats stop_pct outside
    # (0,1) as stop disabled (minute_held_scan_core.advance: stop_enabled).
    cursor = _cursor((9.70, 9.90, 9.50, 9.60), stop_pct=0.0)
    assert cursor.advance(0, "open") is None
    assert cursor.advance(0, "close") is None
    assert cursor.fill_state == {}
    assert cursor.first_exit_attempted is False

    cursor = _cursor((9.00, 9.90, 8.00, 9.60), stop_pct=0.0,
                     fill_config=_touch_config())
    assert cursor.advance(0, "open") is None
    assert cursor.advance(0, "close") is None
    assert cursor.fill_state == {}
    assert cursor.first_exit_attempted is False


def test_broken_ohlc_is_not_validated_by_cursor():
    # bar_scan_exit raised ValueError on inconsistent OHLC; the shared cursor
    # does not validate bars — callers/loaders own bar consistency. This test
    # pins that so the dropped check is explicit, not silent.
    cursor = _cursor((10.00, 9.00, 8.00, 10.00))
    assert cursor.advance(0, "open") is None
    assert cursor.advance(0, "close") is None
    assert cursor.peak == 10.0

    cursor = _cursor((10.00, 9.00, 8.00, 10.00), fill_config=_touch_config())
    assert cursor.advance(0, "open") is None
    idx, price, reason = cursor.advance(0, "close")
    assert idx == 0
    assert price == pytest.approx(9.80)
    assert reason == "stop_loss:touch"


@pytest.mark.parametrize(
    "signal,next_bar,config,reason",
    [
        ((10.10, 10.20, 9.70, 10.00), (9.50, 9.60, 9.40, 9.55),
         _touch_config("next_bar_open"), "stop_loss:touch:next_open"),
        ((9.70, 9.90, 9.50, 9.85), (9.40, 9.80, 9.30, 9.60),
         _touch_config("next_bar_open"), "stop_loss:gap_open:next_open"),
        ((11.80, 12.00, 11.00, 11.00), (10.90, 11.20, 10.80, 11.10),
         FillConfig(fill_timing="next_bar_open"), "profit_take:drawdown:50:next_open"),
    ],
    ids=["touch", "gap", "drawdown"],
)
def test_next_bar_signal_queues_then_fills_at_next_open(signal, next_bar, config, reason):
    cursor = _cursor(signal, next_bar, fill_config=config)
    assert _advance_bar(cursor) is None
    assert cursor.fill_state == {"pending": reason}
    assert not cursor.first_exit_attempted
    if reason.startswith("profit_take"):
        assert cursor.peak == 12.0
    assert cursor.advance(1, "open") == (1, next_bar[0], reason)
    assert cursor.fill_state == {}
    assert cursor.advance(1, "close") is None


def test_next_bar_skip_does_not_need_a_following_bar():
    cursor = _cursor((10.45, 10.80, 10.40, 10.50), peak=10.4,
                     fill_config=FillConfig(fill_timing="next_bar_open"))
    assert _advance_bar(cursor) is None
    assert cursor.fill_state == {}
    assert cursor.peak == 10.80


def test_next_bar_signal_without_following_bar_stays_pending():
    # bar_scan_exit raised when next_bar was missing on a fill; the cursor carries
    # the pending exit in fill_state to the next session (next_bar_open carry).
    cursor = _cursor((10.10, 10.20, 9.70, 10.00),
                     fill_config=_touch_config("next_bar_open"))
    assert _advance_bar(cursor) is None
    assert cursor.fill_state == {"pending": "stop_loss:touch:next_open"}
    assert not cursor.first_exit_attempted


def test_fill_config_rejects_unknown_timing():
    with pytest.raises(ValueError, match="fill_timing"):
        FillConfig(fill_timing="limit_book")
