"""Adopted open/fill limit pair, including turtle next-day retry."""
from types import SimpleNamespace

import pytest

from backtest.research import strategy9_2_engine as engine
from backtest.research.fill_config import FillConfig
from backtest.research.minute_cash_order import (
    peak_dd_clear_exits, scale_out_exits, step_stop_exits,
)
from tests.test_side_sell_fill_config import CODE, state, sells
from tests.test_v92_minute_fold import run_seeded


@pytest.mark.parametrize('kind', ['step_stop', 'scale_out', 'peak_dd_clear'])
@pytest.mark.parametrize('opening,fill,blocked', [(5., 10., True), (10., 5., True), (10., 10., False)])
@pytest.mark.parametrize('config_default', [False, True])
def test_side_sell_limit_pair(kind, opening, fill, blocked, config_default):
    st, _, pos = state()
    # Explicit numeric fills isolate the decision price from the execution price.
    config = FillConfig() if config_default else FillConfig(fill_at=fill)
    decision = fill if config_default else 10.
    limits = (100., 5.)
    kwargs = dict(open_px=opening, hm=600, fill_config=config)
    if kind == 'step_stop':
        step_stop_exits(st, CODE, pos, decision, '2025-11-05', 2, limits,
                        step_stop_pct=.1, **kwargs)
    elif kind == 'scale_out':
        # Both decision quotes cross a profitable scale band.
        pos.group.anchor_cost = 4.
        scale_out_exits(st, CODE, pos, decision, '2025-11-05', 2, limits,
                        scale_step=.05, scale_frac=.6, **kwargs)
    else:
        pos.group.first_lot.peak = 12.
        pos.group.peak_dd_start = 0
        peak_dd_clear_exits(st, CODE, pos, decision, '2025-11-05', 2, limits,
                            peak_dd_sessions=1, **kwargs)
    assert bool(sells(st)) is not blocked
    assert st.stats['defer_sell_limit_down'] == int(blocked)
    if not blocked:
        assert all(t['price'] == fill for t in sells(st))


@pytest.mark.parametrize('opening,fill,blocked', [(8.1, 8.8, True), (9.5, 8.1, True), (9.5, 8.8, False)])
@pytest.mark.parametrize('chronological', [False, True])
def test_minute_touch_pair_and_next_day_retry(monkeypatch, opening, fill, blocked, chronological):
    # A line below the floor permits an open-at-floor touch (rather than gap)
    # when the chosen explicit fill is above that line.
    monkeypatch.setattr(engine.rules, 'chosen_stop', lambda *args: 8.)
    st = run_seeded(monkeypatch, [[(600, opening, 9.6, 7.9, 8.8),
                                  (601, 9.5, 9.6, 9.4, 9.5)],
                                 [(600, 9.5, 9.6, 9.4, 9.5)]],
                    fill_config=FillConfig('bar_low', 'this_bar', fill),
                    fix_minute_cash_order=chronological)
    result = sells(st)
    assert len(result) == 1
    assert result[0]['reason'] == 'stop_loss:touch'
    assert result[0]['date'] == ('20260304' if blocked else '20260303')
    assert result[0]['price'] == (9.5 if blocked else fill)
    assert st.stats['defer_sell_limit_down'] == int(blocked)
    assert st.stats.get('limit_down_pending', 0) == int(blocked)


@pytest.mark.parametrize('opening,line,blocked', [(8.1, 8., True), (9.5, 8.1, True), (9.5, 8.8, False)])
def test_daily_touch_pair(monkeypatch, opening, line, blocked):
    st, _, _ = state()
    monkeypatch.setattr(engine.rules, 'chosen_stop', lambda *args: line)
    row = SimpleNamespace(open=opening, low=7.9, close=8.8)
    assert engine.fill_stop(st, CODE, row, None, '2025-11-05', day_i=2,
                            ds='20251105', limits=(100., 8.1))
    assert bool(sells(st)) is not blocked
    assert st.stats['defer_sell_limit_down'] == int(blocked)
    assert st.stats.get('limit_down_pending', 0) == int(blocked)
    if blocked:
        assert st.book_state['turtle_retry_day'][CODE] == 3
        engine.fill_pending(st, CODE, SimpleNamespace(open=9.5), '2025-11-05',
                            day_i=2, ds='20251105', limits=(100., 8.1))
        assert not sells(st)
        engine.fill_pending(st, CODE, SimpleNamespace(open=9.5), '2025-11-06',
                            day_i=3, ds='20251106', limits=(100., 8.1))
        assert sells(st)


@pytest.mark.parametrize('kind', ['step_stop', 'scale_out', 'peak_dd_clear'])
def test_next_open_uses_execution_open_not_decision_open(kind):
    from backtest.research.minute_cash_order import fill_side_pending
    st, _, pos = state()
    kwargs = dict(open_px=5., fill_config=FillConfig(fill_timing='next_bar_open'))
    if kind == 'step_stop':
        step_stop_exits(st, CODE, pos, 10., '2025-11-05', 2, (100., 5.),
                        step_stop_pct=.1, **kwargs)
    elif kind == 'scale_out':
        scale_out_exits(st, CODE, pos, 10.5, '2025-11-05', 2, (100., 5.),
                        scale_step=.05, scale_frac=.6, **kwargs)
    else:
        pos.group.first_lot.peak = 12.
        pos.group.peak_dd_start = 0
        peak_dd_clear_exits(st, CODE, pos, 10., '2025-11-05', 2, (100., 5.),
                            peak_dd_sessions=1, **kwargs)
    assert not sells(st)
    assert st.stats['defer_sell_limit_down'] == 0
    fill_side_pending(st, CODE, pos, 5., '2025-11-05', 2, (100., 5.), hm=601)
    assert not sells(st)
    assert st.stats['defer_sell_limit_down'] == (2 if kind == 'scale_out' else 1)
    fill_side_pending(st, CODE, pos, 10., '2025-11-05', 2, (100., 5.), hm=602)
    assert sells(st)


def test_pair_reuses_single_price_eps():
    from backtest.research.ashare_session import (
        LIMIT_EPS, defer_sell_at_limit, defer_sell_open_or_fill,
    )
    for opening in (5., 5. + LIMIT_EPS / 2, 5. + LIMIT_EPS * 2, 10.):
        for fill in (5., 5. + LIMIT_EPS / 2, 5. + LIMIT_EPS * 2, 10.):
            assert defer_sell_open_or_fill(opening, fill, (100., 5.)) == (
                defer_sell_at_limit(opening, (100., 5.)) or
                defer_sell_at_limit(fill, (100., 5.)))
    assert not defer_sell_open_or_fill(5., 5., None)
