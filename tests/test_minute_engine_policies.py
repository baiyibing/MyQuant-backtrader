"""Main minute policy and API-only registration boundaries."""
from dataclasses import FrozenInstanceError, replace
import pytest
from backtest.research import csv_strategy_books as books
from backtest.research import minute_classification as classification
from backtest.research.minute_engine_policies import (
    LEGACY_MINUTE_POLICY, MinuteEnginePolicy, MinutePolicyContext,
    MinuteRowToken, minute_policy_for,
)
from backtest.research.rule_profile import INDUSTRY

@pytest.mark.parametrize('hooks,fix,execution,walk,expected', [
    ({}, False, 'close', False, False),
    ({'minute_open': True}, False, 'close', False, False),
    ({'minute_session': object()}, False, 'close', False, True),
    ({}, True, 'close', False, True),
    ({}, False, 'open', False, True),
    ({}, False, 'close', True, True),
])
def test_legacy_schedule(hooks, fix, execution, walk, expected):
    policy = minute_policy_for(hooks)
    assert policy is LEGACY_MINUTE_POLICY
    assert policy.chronological(hooks, fix_cash_order=fix,
                                topk_exec=execution, limit_walkdown=walk) == expected


def test_native_policy_and_context():
    policy = MinuteEnginePolicy(schedule='symbol_major')
    assert minute_policy_for({'minute_policy': policy}) is policy
    assert not policy.chronological({'minute_session': object()}, fix_cash_order=False,
                                    topk_exec='close', limit_walkdown=False)
    context = MinutePolicyContext(index_days=[], fee_schedule=object(), native_inputs={})
    assert context.index_days == []
    assert context.rule_profile is INDUSTRY
    with pytest.raises(FrozenInstanceError):
        context.index_days = None
    with pytest.raises(ValueError):
        MinuteEnginePolicy(schedule='other')
    with pytest.raises(TypeError):
        minute_policy_for({'minute_policy': object()})


def test_duplicate_clock_row_tokens():
    rows = [MinuteRowToken('000001', n, 1455, object()) for n in range(2)]
    assert rows[0].hm == rows[1].hm
    assert rows[0] != rows[1]
    assert [row.ordinal for row in rows] == [0, 1]


def test_minute_registration_preserves_public_names(monkeypatch):
    registry = {}
    monkeypatch.setattr(books, 'MINUTE_ONLY_BOOKS', registry)
    monkeypatch.setattr(classification, 'MINUTE_ONLY_BOOKS', registry)
    names = books.csv_strategy_names()
    entries = classification.minute_strategy_names()
    book = replace(books.get_book('v6'), name='version7', aliases=('version7', 'v7'),
                   apply=lambda **kw: {'minute_session': object()})
    books.register_minute_book(book)
    assert books.get_minute_book(' V7 ') is book
    assert books.get_minute_book('v6') is books.get_book('v6')
    assert books.csv_strategy_names() == names
    assert classification.minute_strategy_names() == entries
    assert classification.minute_strategy_entries()[-2].cli == classification.CLI_V7
    with pytest.raises(ValueError):
        books.get_book('version7')
    with pytest.raises(ValueError, match='already registered'):
        books.register_minute_book(book)
    with pytest.raises(ValueError, match='already registered'):
        books.register_minute_book(replace(book, name='other', aliases=('v6',)))
    registry['version7'] = replace(book, apply=lambda **kw: {})
    with pytest.raises(RuntimeError, match='version7.*missing minute exit hooks'):
        classification.minute_strategy_entries()


def test_main_calls_policy_boundaries_in_order(monkeypatch):
    from backtest.research import csv_minute_backtest as minute
    from tests.test_strategy11_engine import T, run
    events = []
    context = MinutePolicyContext(index_days=[T])
    original = minute.apply_csv_strategy

    def calendar(**kwargs):
        assert kwargs['context'] is context
        events.append('calendar')
        return minute.build_calendar(kwargs['daily_bars'], kwargs['start'], kwargs['end'])

    def initialize(hooks, **kwargs):
        assert kwargs.pop('context') is context
        events.append('initialize')
        return minute.init_sim_state(hooks, **kwargs)

    def day_start(st, **kwargs):
        assert kwargs['context'] is context
        events.append('day_start')

    def marks(st, **kwargs):
        assert kwargs.pop('context') is context
        events.append('marks')
        minute.append_equity_and_eod_marks(st, **kwargs)

    policy = MinuteEnginePolicy(calendar=calendar, initialize=initialize,
                                day_start=day_start, append_marks=marks)
    expected = run(minute, end=T)
    def apply(*args, **kwargs):
        return dict(original(*args, **kwargs), minute_policy=policy)
    monkeypatch.setattr(minute, 'apply_csv_strategy', apply)
    actual = run(minute, end=T, policy_context=context)
    assert events == ['calendar', 'initialize', 'day_start', 'marks']
    assert actual.trades == expected.trades
    assert actual.equity_curve == expected.equity_curve
    assert actual.stats == expected.stats
