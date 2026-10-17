"""Data-free contract checks for the shared full-switch infrastructure."""
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
    assert on.pop('bigvalue_block_new') is True
    assert on.pop('bigvalue_flatten') is False
    assert on.pop('bigvalue_golden_mult') is None
    assert on.pop('bigvalue_base_frac') is None
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


@pytest.mark.parametrize('flag', ['--bigvalue-block-new', '--bigvalue-flatten', '--bigvalue-golden-mult'])
def test_all_behavior_flags_require_file_and_refuse_index(flag):
    flags = [flag] + (['2'] if flag.endswith('mult') else [])
    with pytest.raises(SystemExit, match='requires --bigvalue-regime-file'):
        _run_kwargs_topk_dropout(parse(flags))
    with pytest.raises(SystemExit, match='refuses'):
        _run_kwargs_topk_dropout(parse(flags + ['--index-ma5-gate']))
    with pytest.raises(SystemExit, match='refuses any bigvalue'):
        _run_kwargs_topk_score_exit(parse(flags))


def test_shared_cash_flatten_and_missing_without_block_flag():
    from backtest.research.bigvalue_regime import (
        confirmed_days,
        flatten_reason,
        golden_cash_fraction,
    )
    states = dict(zip(['20261009','20261012','20261013','20261014'], [-1,-1,1,1]))
    days = confirmed_days(bars(), states)
    assert flatten_reason(days, '20261013') is None  # default off
    assert flatten_reason(days, '20261013', True) == 'regime_flat:bigvalue_death'
    assert flatten_reason(days, '20261016', True) is None
    assert golden_cash_fraction(days, '20261015', 2) == 1.0
    assert golden_cash_fraction(days, '20261015', 0.5) == 0.475
    assert golden_cash_fraction(days, '20261013', 2) == 0.95
    assert golden_cash_fraction(days, '20261016', 2) == 0.95
    assert golden_cash_fraction(days, '20261015') == 0.95
    gate = with_bigvalue_gate(None, bars(), states, block_new=False)
    assert gate('A', '20261013')  # confirmed death, flatten-only can open
    assert not gate('A', '20261016')  # any behavior: missing is fail closed


def test_base_frac_pairs_with_golden_mult():
    from backtest.research.bigvalue_regime import confirmed_days, golden_cash_fraction
    states = dict(zip(['20261009','20261012','20261013','20261014'], [-1,-1,1,1]))
    days = confirmed_days(bars(), states)
    # Non-golden days sit at the lowered base; golden day = min(1, base*M).
    assert golden_cash_fraction(days, '20261013', 2, 0.5) == 0.5
    assert golden_cash_fraction(days, '20261016', 2, 0.5) == 0.5
    assert golden_cash_fraction(days, '20261015', 2, 0.5) == 1.0
    assert golden_cash_fraction(days, '20261015', 1.2, 0.5) == 0.6
    # Default base keeps the merged contract byte-identical.
    assert golden_cash_fraction(days, '20261015', 0.5) == 0.475


def test_base_frac_cli_contract(tmp_path, monkeypatch):
    from backtest.research import topk_dropout_scores
    monkeypatch.setattr(topk_dropout_scores,'load_scores_from_args',lambda **kw: {'20261015': {'A':1.}})
    path = fixture_file(tmp_path)
    on = _run_kwargs_topk_dropout(parse([
        '--bigvalue-block-new', '--bigvalue-regime-file', str(path),
        '--bigvalue-base-frac', '0.5',
        '--bigvalue-golden-mult', '2']))
    assert on.pop('bigvalue_base_frac') == 0.5
    assert on.pop('bigvalue_golden_mult') == 2.0
    # Alone it is not a behavior flag; out of range it refuses.
    with pytest.raises(SystemExit, match='require --bigvalue-block-new'):
        _run_kwargs_topk_dropout(parse(
            ['--bigvalue-base-frac', '0.5']))
    with pytest.raises(SystemExit, match='base-frac'):
        _run_kwargs_topk_dropout(parse([
            '--bigvalue-block-new', '--bigvalue-regime-file', str(path),
            '--bigvalue-base-frac', '1.5']))


@pytest.mark.parametrize('engine', ['daily', 'minute', 'minute_open'])
@pytest.mark.parametrize('flatten,stop,expected', [
    (False, 0., None), (True, 0., 'regime_flat:bigvalue_death'),
    (True, 0.05, 'stop_loss:gap_open'),
])
def test_engine_flatten_clock_priority_and_off(engine, flatten, stop, expected):
    from backtest.research import csv_daily_backtest as daily, csv_minute_backtest as minute
    code = '600000.SH'
    dates = ['20261009','20261012','20261013','20261014','20261015']
    frame = pd.DataFrame(dict(open=[10.,10.,10.,9.4,9.5],
                              high=[10.,10.,10.,9.8,9.8],
                              low=[10.,10.,10.,9.3,9.4],
                              close=[10.,10.,10.,9.7,9.6], volume=[1e6]*5),
                         index=pd.to_datetime(dates))
    states = dict(zip(dates, [1,1,-1,-1,1]))
    options = dict(strategy='topk_dropout', total_cash=100_000., daily_quota=100_000.,
                   topk=1, n_drop=0, stop_pct=stop, rule_profile='legacy',
                   scores_by_day={d:{code:1.} for d in dates},
                   bigvalue_regime=(states,1), bigvalue_flatten=flatten)
    pool = {'20261013':[code]}
    if engine == 'daily':
        st = daily.simulate({code:frame}, pool, '20261013','20261014', **options)
    else:
        rows = []
        for d in dates:
            for hm in (570,895):
                row = frame.loc[pd.Timestamp(d)].to_dict()
                row.update(ymd=d, hm=hm)
                if d == '20261014':
                    row['close'] = 9.6 if hm == 570 else 9.7
                rows.append(row)
        ms = pd.DataFrame(rows)
        ms.index = pd.to_datetime(ms.ymd) + pd.to_timedelta(ms.hm, unit='m')
        st = minute.simulate({code:ms}, {code:frame}, pool, '20261013','20261014',
                             **options, **({'topk_exec':'open'} if engine == 'minute_open' else {}))
    sells = [t for t in st.trades if t['side']=='SELL']
    if expected is None:
        assert sells == []
    else:
        assert len(sells) == 1, st.trades
        assert sells[0]['reason'] == expected
        assert sells[0]['date'] == '20261014'
        assert sells[0]['price'] == 9.4
        if engine != 'daily':
            assert sells[0]['price_rule'] in {'minute_regime_next_open', 'minute_gap_open'}
    assert not [t for t in st.trades if t['date']=='20261013' and t['side']=='SELL']


@pytest.mark.parametrize('engine', ['daily', 'minute', 'minute_open'])
@pytest.mark.parametrize('multiplier,expected_shares', [(None,9500), (2.,10000)])
def test_engine_golden_cash_clamp(engine, multiplier, expected_shares):
    from backtest.research import csv_daily_backtest as daily, csv_minute_backtest as minute
    code = '600000.SH'
    dates = ['20261009','20261012','20261013']
    ds = pd.DataFrame(dict(open=[10.]*3, high=[10.]*3, low=[10.]*3, close=[10.]*3),
                      index=pd.to_datetime(dates))
    options = dict(strategy='topk_dropout', total_cash=100_000., daily_quota=100_000.,
                   topk=1, n_drop=0, stop_pct=0., rule_profile='legacy',
                   buy_cost_rate=0., sell_cost_rate=0., min_cost=0.,
                   scores_by_day={'20261013':{code:1.}},
                   bigvalue_regime=({d:1 for d in dates},2), bigvalue_golden_mult=multiplier)
    pool = {'20261013':[code]}
    if engine == 'daily':
        st = daily.simulate({code:ds},pool,'20261013','20261013',**options)
    else:
        ms = pd.DataFrame(dict(ymd=['20261013']*2,hm=[570,895],open=[10.]*2,
                               high=[10.]*2,low=[10.]*2,close=[10.]*2,volume=[1e6]*2),
                          index=pd.to_datetime(['2026-10-13 09:30','2026-10-13 14:55']))
        st = minute.simulate({code:ms},{code:ds},pool,'20261013','20261013',**options,
                             **({'topk_exec':'open'} if engine == 'minute_open' else {}))
    assert [t['shares'] for t in st.trades if t['side']=='BUY'] == [expected_shares]
    assert st.cash >= 0


@pytest.mark.parametrize('mode', ['close','open'])
@pytest.mark.parametrize('missing_open', [False, True])
def test_minute_flatten_limit_down_defers_to_next_session(mode, missing_open):
    from backtest.research.csv_minute_backtest import simulate
    code = '600000.SH'
    dates = ['20261009','20261012','20261013','20261014','20261015']
    ds = pd.DataFrame(dict(open=[10.,10.,10.,9.,9.4],high=[10.,10.,10.,9.5,9.6],
                          low=[10.,10.,10.,9.,9.3],close=[10.,10.,10.,9.5,9.5]),
                      index=pd.to_datetime(dates))
    rows=[]
    for day in dates[2:]:
        for hm in (570,895):
            if missing_open and day == '20261014' and hm == 570:
                continue
            row=ds.loc[pd.Timestamp(day)].to_dict()
            row.update(ymd=day,hm=hm,volume=1e6)
            rows.append(row)
    ms=pd.DataFrame(rows)
    ms.index=pd.to_datetime(ms.ymd)+pd.to_timedelta(ms.hm,unit='m')
    st=simulate({code:ms},{code:ds},{'20261013':[code]},'20261013','20261015',
                strategy='topk_dropout',total_cash=100_000.,daily_quota=100_000.,
                topk=1,n_drop=0,stop_pct=0.,rule_profile='legacy',topk_exec=mode,
                scores_by_day={d:{code:1.} for d in dates},
                bigvalue_regime=(dict(zip(dates,[1,1,-1,1,1])),1),bigvalue_flatten=True)
    sells=[t for t in st.trades if t['side']=='SELL']
    assert [(t['date'],t['price'],t['reason']) for t in sells] == [
        ('20261015',9.4,'regime_flat:bigvalue_death')]
