"""Synthetic SELL diagnostics with account hashes captured from origin/master."""
import csv
from dataclasses import asdict
from hashlib import sha256
import json

import pandas as pd
import pytest

from backtest.research import csv_minute_backtest as minute
from backtest.research.csv_artifacts import write_run_artifacts
from backtest.research.fill_config import FillConfig
from tests.test_side_sell_fill_config import CODE, state, sells
from tests.test_v92_minute_fold import run_seeded as _run_seeded


def run_seeded(*args, **kwargs):
    kwargs.setdefault("rule_profile", "legacy")
    return _run_seeded(*args, **kwargs)


def account_hash(st):
    return sha256(json.dumps(dict(trades=st.trades, equity_curve=st.equity_curve,
        cash=st.cash, positions={c: [asdict(p) for p in lots] for c, lots in st.positions.items()},
        stats=st.stats), sort_keys=True, default=str).encode()).hexdigest()


def run_main(kind, cash_order=False):
    days = ['20260901', '20260902', '20260903']
    rows = [(10., 10., 10., 10.), (10., 10., 9.3, 9.4),
            (9.2, 9.4, 9.1, 9.3) if kind == 'filled' else (9., 9., 9., 9.)]
    frame = pd.DataFrame(rows, columns=['open', 'high', 'low', 'close'])
    frame['ymd'], frame['hm'], frame['volume'] = days, [895, 900, 570], 100_000
    frame.index = pd.to_datetime(days) + pd.to_timedelta(frame['hm'].to_numpy(), unit='m')
    if kind == 'suspended':
        frame = frame.iloc[:2]
    daily = pd.DataFrame({k: [10.] * 4 for k in ['open', 'high', 'low', 'close']},
                         index=pd.to_datetime(['20260831'] + days))
    return minute.simulate(minute_bars={CODE: frame}, daily_bars={CODE: daily},
        pool_days={days[0]: [CODE]}, start=days[0], end=days[-1], strategy='version3',
        total_cash=100_000., daily_quota=10_000., name_budget=10_000., stop_pct=.05,
        fix_minute_cash_order=cash_order, fill_config=FillConfig(fill_timing='next_bar_open'),
        rule_profile="legacy")


def run_side(opening=5., fill=10.):
    from backtest.research.minute_cash_order import step_stop_exits
    st, _, pos = state()
    step_stop_exits(st, CODE, pos, 10., '2025-11-05', 2, (100., 5.),
                    step_stop_pct=.1, hm=600, open_px=opening,
                    fill_config=FillConfig(fill_at=fill))
    return st


def run_side_queue(filled=False):
    from backtest.research.minute_cash_order import step_stop_exits, fill_side_pending
    st, _, pos = state()
    step_stop_exits(st, CODE, pos, 10.7, '2025-11-05', 2, (100., 5.),
                    step_stop_pct=.1, hm=600, fill_config=FillConfig(fill_timing='next_bar_open'))
    fill_side_pending(st, CODE, pos, 5., '2025-11-06', 3, (100., 5.), hm=570)
    if filled:
        fill_side_pending(st, CODE, pos, 11., '2025-11-06', 3, (100., 5.), hm=571)
    return st


def run_turtle_fill_limit():
    from backtest.research import strategy9_2_engine as engine
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(engine.rules, 'chosen_stop', lambda *args: 8.)
        return run_seeded(patch, [[(600, 9.5, 9.6, 7.9, 8.8)]],
                          fill_config=FillConfig('bar_low', 'this_bar', 8.1))


def run_turtle():
    with pytest.MonkeyPatch.context() as patch:
        return run_seeded(patch, [[(600, 8.1, 8.1, 8.1, 8.1)]])


# Same synthetics as origin/master (927d75d); stats now include skip_st=0.
MASTER_HASHES = {
    "filled/False": "027b06b7e06169f97e3586a18c6006f45a33f91792a5aa56498eee33011875c0",
    "filled/True": "027b06b7e06169f97e3586a18c6006f45a33f91792a5aa56498eee33011875c0",
    "blocked/False": "c5d6633587e5d61c3a5c6c4abf9d7737087ba084723c94cb753c84bae9b9bd79",
    "blocked/True": "c5d6633587e5d61c3a5c6c4abf9d7737087ba084723c94cb753c84bae9b9bd79",
    "suspended/False": "c5d6633587e5d61c3a5c6c4abf9d7737087ba084723c94cb753c84bae9b9bd79",
    "suspended/True": "c5d6633587e5d61c3a5c6c4abf9d7737087ba084723c94cb753c84bae9b9bd79",
    "side/limit_down_open": "5b350be9b2e03853778027d9e396dfea6a5a83fadfb1b721a64efd9ae98ba4b9",
    "side/limit_down_fill": "5b350be9b2e03853778027d9e396dfea6a5a83fadfb1b721a64efd9ae98ba4b9",
    "turtle": "5f4058b63a955f9dfe79078a2d39d409e498d94989f7cf8efaf003a112585faa",
    "side_queue/False": "5b350be9b2e03853778027d9e396dfea6a5a83fadfb1b721a64efd9ae98ba4b9",
    "side_queue/True": "3d68171cbe2ac31daaec43449c6e29629228ea32fabc4a251c946fb8a98fc36d",
    "turtle_fill_limit": "5f4058b63a955f9dfe79078a2d39d409e498d94989f7cf8efaf003a112585faa",
    "turtle_partial_queue": "2f605a44a9af6f69e12b3ee4091ef134ccf187f852c47fb222396dcd5bd27d1a"
}


@pytest.mark.parametrize('cash_order', [False, True])
@pytest.mark.parametrize('kind', ['filled', 'blocked', 'suspended'])
def test_main_events_and_pending(kind, cash_order, tmp_path):
    st = run_main(kind, cash_order)
    assert account_hash(st) == MASTER_HASHES[f'{kind}/{cash_order}']
    assert 'sell_pending_events' not in asdict(st)
    assert 'sell_pending_open' not in asdict(st)
    queued = next(e for e in st.sell_pending_events if e['reason'] == 'next_bar_open_queued')
    assert (queued['ds'], queued['hm'], queued['code']) == ('20260902', 900, CODE)
    if kind == 'filled':
        assert st.sell_pending_open == []
        assert sells(st)[0]['price'] == 9.2
    else:
        expected = 'limit_down_open' if kind == 'blocked' else 'suspended_no_bar'
        assert any(e['reason'] == expected for e in st.sell_pending_events)
        row, = st.sell_pending_open
        assert (row['since_ds'], row['since_hm']) == ('20260902', 900)
        assert (row['last_ds'], row['last_hm']) == ('20260903', 570 if kind == 'blocked' else None)
        assert row['shares'] == 1000
    # Consumers cannot mutate any account result or the two frozen CSV artifacts.
    before = account_hash(st)
    write_run_artifacts(tmp_path / 'observed', st, 'summary', '')
    assert account_hash(st) == before
    with (tmp_path / 'observed' / 'pending_sells.csv').open(newline='') as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == ['kind', 'code', 'shares', 'reason', 'since_ds',
                                    'since_hm', 'last_ds', 'last_hm', 'detail']
        rows = list(reader)
        assert sum(row['kind'] == 'open' for row in rows) == (kind != 'filled')
    st.sell_pending_events, st.sell_pending_open = [], []
    write_run_artifacts(tmp_path / 'unobserved', st, 'summary', '')
    for name in ['trades.csv', 'daily_equity.csv']:
        assert (tmp_path / 'observed' / name).read_bytes() == (tmp_path / 'unobserved' / name).read_bytes()
    assert not (tmp_path / 'unobserved' / 'pending_sells.csv').exists()
    write_run_artifacts(tmp_path / 'observed', st, 'summary', '')
    assert not (tmp_path / 'observed' / 'pending_sells.csv').exists()


@pytest.mark.parametrize('opening,fill,reason', [(5., 10., 'limit_down_open'),
                                                (10., 5., 'limit_down_fill')])
def test_side_limit_events(opening, fill, reason):
    st = run_side(opening, fill)
    assert account_hash(st) == MASTER_HASHES[f'side/{reason}']
    event, = st.sell_pending_events
    assert (event['path'], event['reason'], event['ds'], event['hm']) == ('step_stop', reason, '20251105', 600)


@pytest.mark.parametrize('filled', [False, True])
def test_side_queue_and_open_list(filled):
    from backtest.research.sell_pending_observability import finish_pending_sells
    st = run_side_queue(filled)
    assert account_hash(st) == MASTER_HASHES[f'side_queue/{filled}']
    finish_pending_sells(st)
    assert st.sell_pending_events[0]['reason'] == 'next_bar_open_queued'
    assert st.sell_pending_events[0]['path'] == 'step_stop'
    if filled:
        assert not st.sell_pending_open
    else:
        row, = st.sell_pending_open
        assert row['detail'] == 'step_stop'
        assert row['shares'] == st.positions[CODE][1].shares
        assert (row['reason'], row['since_ds'], row['since_hm']) == ('limit_down_open', '20251105', 600)


def test_turtle_limit_pending():
    st = run_turtle()
    assert account_hash(st) == MASTER_HASHES['turtle']
    assert any(e['reason'] == 'limit_down_open' and e['path'] == 'v9_2_turtle'
               for e in st.sell_pending_events)
    row, = st.sell_pending_open
    assert (row['code'], row['shares'], row['since_ds'], row['since_hm']) == (CODE, 1000, '20260303', 600)
    assert row['detail'] == 'v9_2_turtle'


def test_cursor_callback_is_optional_and_preserves_return():
    from tests.test_minute_fill_config import scan
    observed, plain = {}, {}
    events = []
    kwargs = dict(fill_config=FillConfig(fill_timing='next_bar_open'))
    with_log = scan(fill_state=observed, pending_log=lambda reason, hm: events.append((reason, hm)), **kwargs)
    without_log = scan(fill_state=plain, **kwargs)
    assert with_log == without_log == (1, 96., 'stop_loss:touch:next_open', 101., 0)
    assert observed == plain == {}
    assert events == [('next_bar_open_queued', 0)]


def test_turtle_fill_limit_and_partial_queue(monkeypatch):
    st = run_turtle_fill_limit()
    assert account_hash(st) == MASTER_HASHES['turtle_fill_limit']
    assert any(e['path'] == 'v9_2_turtle' and e['reason'] == 'limit_down_fill'
               for e in st.sell_pending_events)
    with pytest.MonkeyPatch.context() as patch:
        partial = run_seeded(patch, [[(600, 13., 13., 13., 13.)]], units=3,
                             fill_config=FillConfig(fill_timing='next_bar_open'))
    assert account_hash(partial) == MASTER_HASHES['turtle_partial_queue']
    queued, = [e for e in partial.sell_pending_events if e['reason'] == 'next_bar_open_queued']
    assert queued['shares'] == partial.sell_pending_open[0]['shares'] == 300


@pytest.mark.parametrize('volume,price,reason', [(0., 10., 'no_volume'),
                                               (1000., 9., 'limit_down_open')])
def test_session_cursor_deferral_callback(volume, price, reason):
    import numpy as np
    from backtest.research.csv_ledger import SimState
    from backtest.research.minute_held_scan_core import HeldMinuteCursor
    events, outcomes = [], []
    for observer in [None, lambda reason, hm: events.append((reason, hm))]:
        stats = SimState().stats
        stats["defer_sell_volume"] = 0
        cursor = HeldMinuteCursor(np.array([price]), np.array([price]), np.array([price]),
            10., 10., 1, True, .05, 10., 0., hm=np.array([570]), limit_down=9.,
            session_exit_reason='stop_loss:touch', session_volume=np.array([volume]),
            session_stats=stats, pending_log=observer,
            fill_config=FillConfig(fill_timing='next_bar_open'))
        outcomes.append((cursor.advance(0, 'open'), stats, cursor.first_exit_attempted))
    assert outcomes[0] == outcomes[1]
    assert events == [(reason, 570)]


def test_open_list_retains_group_tail_after_entry_lot_sold():
    from backtest.research.csv_ledger import _sell
    from backtest.research.sell_pending_observability import carry_session, finish_pending_sells
    st, lots, pos = state()
    remaining = lots[1].shares
    _sell(st, CODE, pos, 11., '2025-11-04', 'stop_loss:touch', day_i=1)
    assert lots[0] not in st.positions[CODE]
    assert pos.pending_exit
    before = account_hash(st)
    frame = pd.DataFrame({'hm': [600]})
    carry_session(st, '20251104', lambda code: frame)
    finish_pending_sells(st)
    row, = st.sell_pending_open
    assert (row['code'], row['shares'], row['since_ds'], row['since_hm']) == (CODE, remaining, '20251104', 600)
    assert account_hash(st) == before
