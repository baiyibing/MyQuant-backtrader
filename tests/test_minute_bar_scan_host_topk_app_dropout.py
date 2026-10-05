"""Data-free contract for the standalone topk_app_dropout host entry."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backtest.research import ashare_session, csv_minute_backtest_v7 as v7
from backtest.research import csv_minute_backtest_topk_app_dropout as app
from backtest.research import minute_bar_scan_host as host, strategy7_engine
from backtest.research.topk_app_dropout import DEFAULT_TOPK
from backtest.research.csv_minute_backtest_topk_app_dropout import DEFAULT_CASH_TOTAL


@pytest.fixture
def wiring(monkeypatch):
    pools = {date(2026, 1, 9): ['000001.SZ'], date(2026, 1, 12): ['000002.SZ']}
    minute, daily = {'000001.SZ': [1, 2]}, {'daily': []}
    index, exdiv, names = {'index': 3000}, {'exdiv': 0.9}, {'000001.SZ': 'ST fixture'}
    mocks = {}
    for module, name, result in [
        (v7, 'load_pool_days', pools), (app, 'build_intersect_pool_days', pools),
        (v7, '_load_cli_bars', (minute, daily)), (v7, 'load_index_daily', index),
        (ashare_session, 'load_limit_context', (exdiv, names)),
        (strategy7_engine, 'simulate_native', SimpleNamespace(trades=[], equity_curve=[], cash=DEFAULT_CASH_TOTAL)),
    ]:
        mocks[name] = Mock(return_value=result)
        monkeypatch.setattr(module, name, mocks[name])
    shared = Mock(side_effect=AssertionError('must not use shared simulate'))
    monkeypatch.setattr(host.csv_minute_backtest, 'simulate', shared)
    mocks['shared'] = shared
    monkeypatch.setattr(host, 'run_simulate', Mock(side_effect=AssertionError('must not use run_simulate')))
    monkeypatch.setattr(host, 'load_scores_from_args', Mock(side_effect=AssertionError('must not load scores')))
    return SimpleNamespace(mocks=mocks, pools=pools, minute=minute, daily=daily,
                           index=index, exdiv=exdiv, names=names)


def argv():
    return ['--source', 'lake', '--symbol', '000001.SZ', '--start', '20260109',
            '--end', '20260112', '--strategy', 'topk_app_dropout']


@pytest.mark.parametrize('prebuilt', [False, True])
@pytest.mark.parametrize('empty', [False, True])
@pytest.mark.parametrize('custom', [False, True])
def test_cli_loads_once(tmp_path, wiring, capsys, prebuilt, empty, custom):
    w = wiring
    app_dir = tmp_path / 'app'
    app_dir.mkdir()
    pred = tmp_path / 'pred.pkl'
    pred.touch()
    pool_dir = tmp_path / 'prebuilt'
    args = argv() + ['--app-pool-dir', str(app_dir), '--pred', str(pred)]
    if prebuilt:
        args += ['--pool-dir', str(pool_dir)]
    if custom:
        args += ['--cash', '123456', '--topk', '7', '--asof', 'identity']
    pools = {} if empty else w.pools
    w.mocks['load_pool_days'].return_value = pools
    w.mocks['build_intersect_pool_days'].return_value = pools
    cash = 123456. if custom else DEFAULT_CASH_TOTAL
    assert DEFAULT_CASH_TOTAL == 500_000_000.0
    assert DEFAULT_TOPK == 50
    assert host.main(args) == 0
    assert 'bars=2' in capsys.readouterr().out
    start, end = date(2026, 1, 9), date(2026, 1, 12)
    if prebuilt:
        w.mocks['load_pool_days'].assert_called_once_with(pool_dir, start, end)
        w.mocks['build_intersect_pool_days'].assert_not_called()
    else:
        w.mocks['load_pool_days'].assert_not_called()
        w.mocks['build_intersect_pool_days'].assert_called_once_with(
            app_dir, pred, '20260109', '20260112', topk=7 if custom else DEFAULT_TOPK,
            asof='identity' if custom else 'pred_minus_one', dump_dir=None)
    w.mocks['_load_cli_bars'].assert_called_once_with(pools, start, end)
    w.mocks['load_limit_context'].assert_called_once_with(
        pool_dir if prebuilt else app_dir,
        {c for codes in pools.values() for c in codes}, start, end)
    if empty:
        w.mocks['load_index_daily'].assert_not_called()
    else:
        w.mocks['load_index_daily'].assert_called_once_with(start, end)
    w.mocks['simulate_native'].assert_called_once_with(
        w.minute, w.daily, pools, [] if empty else w.index, cash_total=cash,
        start=start, end=end, exdiv=w.exdiv, names=w.names)
    w.mocks['shared'].assert_not_called()


@pytest.mark.parametrize('inputs', [{}, {'app_pool_dir': 'missing'}, {'pred': 'missing'},
                                  {'app_pool_dir': 'missing', 'pred': 'missing'}])
def test_missing_inputs_fail_before_loaders(wiring, monkeypatch, inputs):
    monkeypatch.setenv('OSKH_TURTLE_POOL_DIR', 'must-not-fall-back')
    with pytest.raises((ValueError, FileNotFoundError)):
        host.run_topk_app_dropout('20260109', '20260112', **inputs)
    for mock in wiring.mocks.values():
        mock.assert_not_called()


def test_missing_pred_file_fails_before_loaders(tmp_path, wiring):
    with pytest.raises(FileNotFoundError, match='pred missing'):
        host.run_topk_app_dropout('20260109', '20260112', app_pool_dir=tmp_path,
                                  pred=tmp_path / 'missing')
    for mock in wiring.mocks.values():
        mock.assert_not_called()


@pytest.mark.parametrize('flag', [['--app-pool-dir', 'app'], ['--pred', 'pred'],
                                 ['--asof', 'identity']])
def test_book_only_flags_rejected(wiring, flag):
    args = argv()
    args[-1] = 'version7'
    assert host.main(args + flag) == 1
    for mock in wiring.mocks.values():
        mock.assert_not_called()


@pytest.mark.parametrize('extra', [['--source', 'qlib_1min'], ['--qlib-root', 'root'],
                                  ['--lake-root', 'root'], ['--cost', '10'],
                                  ['--peak', '10'], ['--held', '000001.SZ'],
                                  ['--asof-pool-names'], ['--end', '20260101']])
def test_invalid_cli_fails_before_loaders(wiring, extra):
    assert host.main(argv() + ['--pool-dir', 'pool'] + extra) == 1
    for mock in wiring.mocks.values():
        mock.assert_not_called()
