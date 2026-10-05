"""B7 hook resolution, cash-gate ownership and route boundaries."""
from dataclasses import asdict
import json

import pytest
from backtest.research.csv_ledger import (
    SimState, InsufficientCashError, check_buy_cash, configure_s8, execute_buy,
)
from backtest.research.csv_simulate_loop import init_sim_state, run_pool_buys_day
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.minute_audit import audit_scope
from tests.test_s8_independent_positions import DAYS, CODE, _pool
from tests.test_tail_window_shared import A, D1, bar, simulate, minute
from backtest.research.tail_window_buy import TAIL_MINUTES


def state(book, mode=None, cash=1000):
    hooks = apply_csv_strategy(book, name_budget=2000)
    if mode is not None:
        hooks['on_short_cash'] = mode
    st, pending, _ = init_sim_state(hooks, total_cash=cash, bars_loaded=1, pool_days={})
    return st, pending, hooks


@pytest.mark.parametrize('book,mode', [('version8', 'raise'), ('version6', 'skip')])
def test_omitted_and_explicit_default_snapshots(book, mode):
    implicit = state(book, cash=10000)
    explicit = state(book, mode, cash=10000)
    for st, pending, hooks in (implicit, explicit):
        _pool(st, pending, hooks, 0, 10)
    assert json.dumps(asdict(implicit[0]), default=str) == json.dumps(asdict(explicit[0]), default=str)
    assert 'on_short_cash' not in asdict(implicit[0])


@pytest.mark.parametrize('value', ['clip', '', None, 1, [], {}])
def test_illegal_mode_at_init(value):
    hooks = apply_csv_strategy('version8')
    hooks['on_short_cash'] = value
    with pytest.raises(ValueError, match='on_short_cash'):
        init_sim_state(hooks, total_cash=1, bars_loaded=0, pool_days={})


def test_pool_skip_counts_once_and_continues():
    st, pending, hooks = state('version8', 'skip', cash=1000)
    st.buy_cost_rate = 0
    trace = []
    with audit_scope(trace, decision_hm=895, phase='close'):
        run_pool_buys_day(st, pending, day_i=0, day=DAYS[0], ds='20251103',
                         pool_days={'20251103': [CODE, '300002.SZ']}, daily_quota=2000,
                         names={}, allow_add=True, buy_gate=None,
                         buy_quote_for=lambda code: (10, [10]), sizing='per_name',
                         name_budget=2000, name_lot_budget=lambda budget, lots: 2000 if not trace else 1000)
    assert st.stats['skip_cash'] == 1
    assert st.stats['skip_cash_notional'] == 2000
    assert [row['reason'] for row in trace].count('skip_cash') == 1
    assert [row['code'] for row in st.trades] == ['300002.SZ']


def test_non_s8_raise_before_counting():
    st, pending, hooks = state('version6', 'raise')
    before = asdict(st)
    with pytest.raises(InsufficientCashError):
        _pool(st, pending, hooks, 0, 10)
    assert asdict(st) == before


def test_helper_and_direct_ledger_never_count():
    st = SimState(cash=1000)
    before = asdict(st)
    assert check_buy_cash(st, needed=1000, available=1000, date='20251103', code=CODE)
    assert not check_buy_cash(st, needed=1000.01, available=1000, date='20251103', code=CODE)
    assert asdict(st) == before
    trace = []
    with audit_scope(trace, decision_hm=895, phase='close'):
        assert not execute_buy(st, CODE, 10, 2000, 0, DAYS[0])
    assert st.stats.get('skip_cash', 0) == 0
    assert len(trace) == 1 and trace[0]['reason'] == 'skip_cash'
    # Unresolved direct state derives the policy at call time.
    st.book_state['s8_independent'] = {}
    with pytest.raises(InsufficientCashError):
        check_buy_cash(st, needed=1001, available=1000, date='20251103', code=CODE)


def test_strict_tail_parent_skip(monkeypatch):
    original = minute.apply_csv_strategy
    def hooks(*args, **kwargs):
        return {**original(*args, **kwargs), 'on_short_cash': 'skip'}
    monkeypatch.setattr(minute, 'apply_csv_strategy', hooks)
    trace = []
    st = simulate({A: [bar(hm) for hm in TAIL_MINUTES]}, total_cash=27999, audit_sink=trace)
    assert not st.trades and not st.positions
    assert st.stats['skip_cash'] == 1
    assert st.stats['skip_cash_notional'] == 28000
    assert len(trace) == 1 and trace[0]['reason'] == 'skip_cash'
    assert st.cash == 27999


def test_unsupported_v7_and_strategy92():
    from backtest.research.csv_minute_backtest_v7 import simulate_v7
    with pytest.raises(ValueError, match='unsupported.*v7'):
        simulate_v7(None, None, None, on_short_cash='skip')
    with pytest.raises(ValueError, match='unsupported.*strategy9_2'):
        state('version9_2', 'skip')


def test_unsupported_topk_constructor():
    from backtest.research.topk_minute_exec import TopkMinuteBuys
    with pytest.raises(ValueError, match='unsupported.*topk'):
        TopkMinuteBuys(None, mode='open', hooks={'on_short_cash': 'skip'},
                       previous_and_frame=None, open_quote_for=None,
                       close_quote_for=None, day_i=0, day=DAYS[0], ds='20251103',
                       names={}, daily_quota=1000, exdiv=None)


def test_unsupported_fullstrat_before_inputs():
    from backtest.research.fullstrat_research_book import simulate
    with pytest.raises(ValueError, match='unsupported.*fullstrat'):
        simulate(None, None, None, None, None, config=None,
                 strategy='version6', on_short_cash='skip')


@pytest.mark.parametrize('clock', ['daily', 'minute_off', 'minute_on'])
def test_price_add_skip_preserves_success_markers(monkeypatch, clock):
    from tests.test_s8_independent_positions import _run, _no_exit, daily_engine, minute_engine
    engine = daily_engine if clock == 'daily' else minute_engine
    original = engine.apply_csv_strategy
    monkeypatch.setattr(engine, 'apply_csv_strategy',
                        lambda *args, **kwargs: {**original(*args, **kwargs), 'on_short_cash': 'skip'})
    st = _run(clock, 'version8', [10., 11., 12.1], [0],
              total_cash=1001100, take_profit=_no_exit)
    group, = st.book_state['s8_independent']['groups'].values()
    assert group.executed_steps == 0
    assert group.last_add_date == ''
    assert len([t for t in st.trades if t['side'] == 'BUY']) == 1
    assert st.stats.get('skip_cash', 0) == 0


def test_chase_skip_consumes_pending_without_skip_cash():
    from tests.test_s8_independent_positions import _chase
    st, pending, hooks = state('version8', 'skip', cash=100)
    _pool(st, pending, hooks, 0, 12., prev=10.)
    assert pending
    _chase(st, pending, hooks, 1, (12., 12.2, [12.]))
    assert not pending and not st.trades
    assert st.stats['chase_buy_fail'] == 1
    assert st.stats['chase_buy_fail_cash'] == 1
    assert st.stats.get('skip_cash', 0) == 0


def test_breakout_skip_preserves_signal_then_fills():
    from backtest.research.csv_simulate_loop import run_breakout_day
    st, _, _ = state('version6_11', 'skip', cash=100)
    key = f'{CODE}@20251103'
    st.book_state['breakout_pending'] = {key: (10., 0)}
    def attempt():
        run_breakout_day(st, day_i=1, day=DAYS[1], ds='20251104', names={},
                         pool_days={}, buy_quote_for=lambda code: (12., [12.]))
    attempt()
    assert key in st.book_state['breakout_pending']
    assert not st.positions and st.stats.get('skip_cash', 0) == 0
    st.cash = 10000
    attempt()
    assert key not in st.book_state['breakout_pending']
    assert st.stats['breakout_buys'] == 1
