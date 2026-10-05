"""Version11's session decision uses the shared held cursor."""
import numpy as np
import pytest

from backtest.research import csv_minute_backtest as minute
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.fill_config import FillConfig, book_fill_defaults
from backtest.research.minute_held_scan_core import HeldMinuteCursor
from tests.test_strategy11_engine import CODE, T, NEXT, THIRD, frames, run, fills


@pytest.mark.parametrize("chronological", [False, True])
def test_default_pending_eod_next_session_open_and_t1(chronological):
    assert book_fill_defaults(apply_csv_strategy('version11'))['stop'] == FillConfig(fill_timing='next_bar_open')
    entry = run(minute, end=T, fix_minute_cash_order=chronological)
    assert [t['side'] for t in fills(entry)] == ['BUY']
    state = run(minute, fix_minute_cash_order=chronological)
    sell = fills(state)[1]
    assert (sell['date'], sell['price'], sell['reason']) == (NEXT, 10.1, 'ma_signal:entry_nonpositive')


@pytest.mark.parametrize("chronological", [False, True])
@pytest.mark.parametrize("block", ['limit', 'zero', 'nan'])
def test_open_rejection_carries_to_next_session(block, chronological):
    ds, ms = frames()
    mask = (ms[CODE]['ymd'] == NEXT) & (ms[CODE]['hm'] == 570)
    if block == 'limit':
        ms[CODE].loc[mask, 'open'] = 8.82
    else:
        ms[CODE].loc[mask, 'volume'] = 0 if block == 'zero' else np.nan
    state = run(minute, ds=ds, ms=ms, fix_minute_cash_order=chronological)
    assert [t['date'] for t in fills(state)] == [T, THIRD]
    assert state.stats['defer_sell_limit_down' if block == 'limit' else 'defer_sell_volume'] == 1


@pytest.mark.parametrize("chronological", [False, True])
@pytest.mark.parametrize("config, price", [(FillConfig(fill_at=10.05), 10.05), (FillConfig(), 10.)])
def test_custom_last_fill_reaches_cursor(monkeypatch, chronological, config, price):
    seen = []
    original = HeldMinuteCursor.advance
    def advance(self, idx, phase):
        if self.session_volume is not None:
            seen.append(self.fill_config)
        return original(self, idx, phase)
    monkeypatch.setattr(HeldMinuteCursor, 'advance', advance)
    state = run(minute, fill_config=config, fix_minute_cash_order=chronological)
    assert config in seen
    assert fills(state)[1]['price'] == price


def test_cursor_t1_blocks_pending_session_exit():
    cursor = HeldMinuteCursor([10.], [10.], [10.], 10., 10., 1, False,
                              None, 0., 0., hm=[570], session_exit_reason='ma_signal:SMA5',
                              session_volume=[100.], session_stats={},
                              fill_config=FillConfig(fill_timing='next_bar_open'))
    assert cursor.advance(0, 'open') is None
    assert cursor.advance(0, 'close') is None


@pytest.mark.parametrize("config, message", [
    (FillConfig(trigger_basis='bar_low', fill_at='bar_low'), 'look-ahead'),
    (FillConfig(fill_at='line'), 'explicit stop/target line'),
])
def test_session_callback_rejects_noncausal_or_missing_line(config, message):
    with pytest.raises(ValueError, match=message):
        run(minute, fill_config=config)
