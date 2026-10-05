"""Side orders preserve lot identity, decision quantities and session carry."""
import pytest

from backtest.research.fill_config import FillConfig
from backtest.research.csv_ledger import _sell, exit_positions, held_fill_key
from backtest.research.minute_cash_order import (
    fill_side_pending, peak_dd_clear_exits, scale_out_exits, step_stop_exits,
)
from tests.test_strategy6_8_rules import _state_with_step


CODE = '600000.SH'
LIMITS = (100., 5.)


def state():
    st, lots = _state_with_step()
    st.held_fill_states = {}
    pos, = exit_positions(st, CODE, 2)
    return st, lots, pos


def sells(st):
    return [t for t in st.trades if t['side'] == 'SELL']


@pytest.mark.parametrize('day_i,day', [(2, '2025-11-05'), (3, '2025-11-06')])
@pytest.mark.parametrize('kind', ['step', 'scale', 'peak'])
def test_next_open_and_session_carry(kind, day_i, day):
    st, lots, pos = state()
    config = FillConfig(fill_timing='next_bar_open')
    if kind == 'step':
        def decide():
            step_stop_exits(st, CODE, pos, 10.79, '2025-11-05', 2, LIMITS,
                            step_stop_pct=.1, fill_config=config)
        expected = lots[1].shares
    elif kind == 'scale':
        def decide():
            scale_out_exits(st, CODE, pos, 10.5, '2025-11-05', 2, LIMITS,
                            scale_step=.05, scale_frac=.6, fill_config=config)
        expected = int(sum(l.shares for l in lots) * .6 // 100) * 100
    else:
        pos.group.first_lot.peak = 12.
        pos.group.peak_dd_start = 0
        def decide():
            peak_dd_clear_exits(st, CODE, pos, 10., '2025-11-05', 2, LIMITS,
                               peak_dd_sessions=1, fill_config=config)
        expected = sum(l.shares for l in lots)
    decide()
    decide()
    assert not sells(st)
    fill_side_pending(st, CODE, pos, 5., day, day_i, LIMITS, hm=570)
    assert not sells(st)
    fill_side_pending(st, CODE, pos, 11., day, day_i, LIMITS, hm=571)
    result = sells(st)
    assert sum(t['shares'] for t in result) == expected
    assert all(t['price'] == 11. and t['reason'].endswith(':next_open')
               and t['price_rule'] == 'minute_pending_next_open' for t in result)
    fill_side_pending(st, CODE, pos, 11., day, day_i, LIMITS, hm=572)
    assert sells(st) == result
    if kind == 'scale':
        assert pos.group.scale_steps == 1


@pytest.mark.parametrize('fill_at,price', [('line', 10.8), ('bar_last', 11.), (10.9, 10.9), ('bar_low', 10.7)])
def test_step_low_and_this_bar_prices(fill_at, price):
    st, _, pos = state()
    step_stop_exits(st, CODE, pos, 11., '2025-11-05', 2, LIMITS,
                    step_stop_pct=.1, low=10.7,
                    fill_config=FillConfig('bar_low', 'this_bar', fill_at))
    assert len(sells(st)) == 1
    assert sells(st)[0]['price'] == pytest.approx(price)


@pytest.mark.parametrize('group_exit', [False, True])
def test_other_exit_clears_side_carry(group_exit):
    st, lots, pos = state()
    step_stop_exits(st, CODE, pos, 10.7, '2025-11-05', 2, LIMITS,
                    step_stop_pct=.1, fill_config=FillConfig(fill_timing='next_bar_open'))
    _sell(st, CODE, pos if group_exit else lots[1], 11., '2025-11-05', 'other', day_i=2)
    assert not st.held_fill_states.get(held_fill_key(pos), {}).get('side_pending')
    before = list(sells(st))
    fill_side_pending(st, CODE, pos, 11., '2025-11-06', 3, LIMITS, hm=570)
    assert sells(st) == before


@pytest.mark.parametrize('kind', ['scale', 'peak'])
@pytest.mark.parametrize('fill_at', ['bar_low', 'line'])
def test_last_print_rejects_forbidden_fill(kind, fill_at):
    st, _, pos = state()
    config = FillConfig('bar_low', 'this_bar', fill_at)
    with pytest.raises(ValueError, match='look-ahead|explicit stop/target line'):
        if kind == 'scale':
            scale_out_exits(st, CODE, pos, 10.5, '2025-11-05', 2, LIMITS,
                            scale_step=.05, scale_frac=.05, fill_config=config)
        else:
            pos.group.first_lot.peak = 12.
            pos.group.peak_dd_start = 0
            peak_dd_clear_exits(st, CODE, pos, 10., '2025-11-05', 2, LIMITS,
                               peak_dd_sessions=1, fill_config=config)


@pytest.mark.parametrize('strategy', ['version6_8', 'version6_10', 'version6_13', 'version6_14'])
@pytest.mark.parametrize('cross_session', [False, True])
def test_simulate_routes_step_order_to_next_open(monkeypatch, strategy, cross_session):
    import pandas as pd
    import backtest.research.csv_minute_backtest as module
    from backtest.research.csv_strategy_books import apply_csv_strategy
    hooks = apply_csv_strategy(strategy)
    # Isolate the side stop from the independent whole-group callback and scale-out.
    hooks.update(stop_pct=.9, take_profit=lambda *args: None, scale_out_step=None,
                 peak_dd_exit=None)
    monkeypatch.setattr(module, 'apply_csv_strategy', lambda *args, **kwargs: hooks)
    days = ['20251103', '20251104', '20251105',
            '20251106' if cross_session else '20251105']
    hm = [895, 895, 895 if cross_session else 600, 570 if cross_session else 601]
    frame = pd.DataFrame([(10., 10., 10., 10.), (12., 12., 12., 12.),
                          (11., 11., 10.7, 10.7), (11.3, 11.3, 11.3, 11.3)],
                         columns=['open', 'high', 'low', 'close'])
    frame['ymd'], frame['hm'], frame['volume'] = days, hm, 100_000
    frame.index = pd.to_datetime(days) + pd.to_timedelta(hm, unit='m')
    daily = pd.DataFrame({key: [10., 12., 11.5, 11., 11.3]
                          for key in ['open', 'high', 'low', 'close']},
                         index=pd.to_datetime(['20251031', '20251103', '20251104',
                                               '20251105', '20251106']))
    kwargs = dict(minute_bars={CODE: frame}, daily_bars={CODE: daily},
                  pool_days={days[0]: [CODE]}, start=days[0], end=days[-1],
                  strategy=strategy, stop_pct=.9, total_cash=5_000_000., daily_quota=1_000_000.,
                  name_budget=1_000_000.)
    legacy = module.simulate(**kwargs)
    queued = module.simulate(**kwargs, fill_config=FillConfig(fill_timing='next_bar_open'))
    old = [t for t in sells(legacy) if t['reason'].startswith('stop_loss:step')]
    new = [t for t in sells(queued) if t['reason'].startswith('stop_loss:step')]
    assert len(old) == len(new) == 1, str(legacy.trades)
    assert old[0]['price'] == 10.7
    assert new[0]['price'] == 11.3
    assert new[0]['reason'] == old[0]['reason'] + ':next_open'
    assert new[0]['price_rule'] == 'minute_pending_next_open'
