"""Data-free contract checks for the first block-new slice."""
import argparse
import inspect

import pandas as pd
import pytest

from backtest.research.bigvalue_regime import load_regime, with_bigvalue_gate
from backtest.research.csv_strategy_books import (
    _run_kwargs_topk_dropout, _run_kwargs_topk_score_exit, add_topk_dropout_args,
)


def fixture_file(tmp_path, **updates):
    data = dict(date=[20261009, 20261012, 20261013, 20261014, 20261015, 20261016],
                bigvalue=[2., 0., 2., 2., 0., 0.],
                ma5=[1., 1., 3., 3., 1., 1.], ma10=[2.] * 6)
    data.update(updates)
    path = tmp_path / 'regime.parquet'
    pd.DataFrame(data).to_parquet(path)
    return path


def bars():
    return {'600000.SH': pd.DataFrame(index=pd.to_datetime([
        '2026-10-09', '2026-10-12', '2026-10-13', '2026-10-14', '2026-10-15', '2026-10-16']))}


def test_tail_internal_zero_lag_confirm_and_seats(tmp_path):
    states = load_regime(fixture_file(tmp_path))
    assert '20261012' in states
    assert '20261015' not in states and '20261016' not in states
    gate = with_bigvalue_gate(None, bars(), states)
    assert not gate('A', '20261009')  # no previous session
    assert not gate('A', '20261012')  # under confirm
    assert not gate('A', '20261013')  # prior two death days, ignores today's golden
    assert not gate('A', '20261014')  # golden only one session
    assert gate('A', '20261015')  # two golden days
    assert gate.seat_ok('B', '20261015')
    assert gate.list_ok('B', '20261016')
    assert not gate('A', '20261016')  # trimmed exact prior day; no stale fallback


def test_equality_warmup_hole_no_cross_gap():
    states = dict(zip(['20261009','20261012','20261013','20261014'], [None,0,-1,-1]))
    gate = with_bigvalue_gate(None, bars(), states)
    assert not gate('A','20261012')
    assert gate('A','20261013')  # equal is neither death nor golden
    assert not gate('A','20261014')
    assert not gate('A','20261015')
    del states['20261013']
    gate = with_bigvalue_gate(None,bars(),states)
    assert not gate('A','20261015')
    states['20261011'] = 1
    with pytest.raises(ValueError,match='noncalendar'):
        with_bigvalue_gate(None,bars(),states)


@pytest.mark.parametrize('updates', [dict(date=[20261009]*6), dict(bigvalue=[0.]*6)])
def test_invalid_input(tmp_path, updates):
    with pytest.raises(ValueError):
        load_regime(fixture_file(tmp_path, **updates))


def test_missing_columns_and_path(tmp_path):
    path=tmp_path/'bad.parquet'
    pd.DataFrame({'date':[20261009]}).to_parquet(path)
    with pytest.raises(ValueError,match='missing columns'):
        load_regime(path)
    with pytest.raises(FileNotFoundError):
        load_regime(tmp_path/'absent.parquet')


def parse(flags):
    ap=argparse.ArgumentParser()
    add_topk_dropout_args(ap)
    return ap.parse_args(flags)


@pytest.mark.parametrize('flags,match', [
    (['--bigvalue-block-new'], 'requires --bigvalue-regime-file'),
    (['--bigvalue-regime-file','x'], 'require --bigvalue-block-new'),
    (['--bigvalue-block-new','--index-ma5-gate'], 'refuses'),
    (['--bigvalue-block-new','--bigvalue-regime-file','x','--bigvalue-ma-fast','10'], 'fast < slow'),
    (['--bigvalue-block-new','--bigvalue-regime-file','x','--bigvalue-confirm-days','0'], 'confirm-days'),
])
def test_cli_validation(flags, match):
    with pytest.raises(SystemExit,match=match):
        _run_kwargs_topk_dropout(parse(flags))


@pytest.mark.parametrize('flags', [['--bigvalue-block-new'],['--bigvalue-signal','state'],['--bigvalue-ma-fast','5']])
def test_score_exit_refuses_any_explicit_flag(flags):
    with pytest.raises(SystemExit,match='refuses any bigvalue'):
        _run_kwargs_topk_score_exit(parse(flags))


def test_kwargs_off_and_on(tmp_path, monkeypatch):
    from backtest.research import topk_dropout_scores
    monkeypatch.setattr(topk_dropout_scores,'load_scores_from_args',lambda **kw: {'20261015': {'A':1.}})
    old = _run_kwargs_topk_dropout(argparse.Namespace())
    assert _run_kwargs_topk_dropout(parse([])) == old
    assert 'bigvalue_regime' not in old
    path=fixture_file(tmp_path)
    on=_run_kwargs_topk_dropout(parse(['--bigvalue-block-new','--bigvalue-regime-file',str(path)]))
    assert on.pop('bigvalue_regime') == (load_regime(path),2)
    assert on == old


def test_both_entries_and_help_contract():
    from backtest.research import csv_daily_backtest, csv_minute_backtest
    from backtest.research.strategy_topk_dropout_rules import HELP_LOCK
    for module in (csv_daily_backtest,csv_minute_backtest):
        source=inspect.getsource(module)
        assert 'eligible_buy = with_bigvalue_gate(eligible_buy,' in source
        assert 'bigvalue_regime: tuple | None = None' in source
    for text in ('--bigvalue-block-new','表尾连续','次日全部新开不买','不强卖旧仓'):
        assert text in HELP_LOCK
