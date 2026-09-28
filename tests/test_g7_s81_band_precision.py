"""G7 exact decimal-input bands; synthetic only, no lake."""
from argparse import ArgumentParser
from decimal import Decimal
from fractions import Fraction
from types import SimpleNamespace

import pytest

from backtest.research import strategy8_1_rules as rules
from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as minute
from backtest.research.csv_strategy_books import (
    add_csv_backtest_common_args, apply_csv_strategy, csv_run_kwargs_from_args,
)


# Return values immediately below / at / above every documented boundary.
EDGES = [
    ('0.06', None, .02, .02),
    ('0.15', .02, .02, .15),
    ('0.40', .15, .15, .30),
    ('0.60', .30, .30, .50),
    ('0.80', .50, .50, .70),
    ('1.00', .70, .70, .90),
    ('1.20', .90, .90, None),
]


@pytest.mark.parametrize('edge,below,at,above', EDGES)
@pytest.mark.parametrize('offset,index', [(-1, 0), (0, 1), (1, 2)])
def test_exact_edges_and_both_sides(edge, below, at, above, offset, index):
    ret = Fraction(edge) + offset * Fraction(1, 10**12)
    expected = (below, at, above)[index]
    assert rules.band_floor(ret, fix_s81_band_precision=True) == expected
    # Exercise original prices through the actual exit path too.
    peak = Decimal('10') * (1 + Decimal(edge) + offset * Decimal('0.000000000001'))
    reason = rules.take_profit_reason(10, 10, peak, fix_s81_band_precision=True)
    expected_reason = None if expected is None else f'trail:band:{round(expected * 100)}'
    if ret > Fraction('1.20'):
        expected_reason = 'trail:peak_dd'
    assert reason == expected_reason


def test_d23_exact_16_over_10_and_legacy_default():
    assert 16 / 10 - 1 == 0.6000000000000001
    assert rules.band_floor(16 / 10 - 1) == .50
    assert rules.band_floor(Decimal(6) / Decimal(10), fix_s81_band_precision=True) == .30
    assert rules.take_profit_reason(14, 10, 16) == 'trail:band:50'
    assert rules.take_profit_reason(14, 10, 16, fix_s81_band_precision=False) == 'trail:band:50'
    assert rules.take_profit_reason(14, 10, 16, fix_s81_band_precision=True) is None
    assert rules.take_profit_reason(13, 10, 16, fix_s81_band_precision=True) == 'trail:band:30'


@pytest.mark.parametrize('ret,floor', [(.05, None), (.08, .02), (.2, .15), (.5, .30), (.7, .50), (.9, .70), (1.1, .90), (1.3, None)])
def test_non_boundary_golden(ret, floor):
    assert rules.band_floor(ret) == rules.band_floor(ret, fix_s81_band_precision=True) == floor
    for px in (9, 10, 10.2, 11.5, 13, 15, 17, 19, 20):
        assert rules.take_profit_reason(px, 10, 10 * (1 + ret)) == rules.take_profit_reason(
            px, 10, 10 * (1 + ret), fix_s81_band_precision=True,
        )


@pytest.mark.parametrize('enabled', [False, True])
def test_cli_to_book_and_stats(enabled):
    parser = ArgumentParser()
    add_csv_backtest_common_args(parser, repo='.', end_default='20260928', cash_total_default=1000, daily_quota_default=1000)
    args = parser.parse_args(['--strategy', 'version8_1'] + (['--fix-s81-band-precision'] if enabled else []))
    kwargs = csv_run_kwargs_from_args(args)
    hooks = apply_csv_strategy(**kwargs)
    assert hooks['take_profit'](14, 10, 16) == (None if enabled else 'trail:band:50')
    st = SimpleNamespace(stats={})
    hooks['record_params'](st)
    assert st.stats.get('fix_s81_band_precision', False) is enabled
    if not enabled:
        assert 'fix_s81_band_precision' not in kwargs
        assert 'fix_s81_band_precision' not in st.stats


@pytest.mark.parametrize('engine', [daily, minute])
@pytest.mark.parametrize('enabled', [False, True])
def test_simulate_forwards_option(engine, enabled, monkeypatch):
    # Stop after real book construction, before any bar processing or I/O.
    class HooksChecked(Exception):
        pass

    def check(strategy, **kwargs):
        hooks = apply_csv_strategy(strategy, **kwargs)
        assert hooks['take_profit'](14, 10, 16) == (None if enabled else 'trail:band:50')
        raise HooksChecked

    monkeypatch.setattr(engine, 'apply_csv_strategy', check)
    frames = ({}, {}) if engine is minute else ({},)
    with pytest.raises(HooksChecked):
        engine.simulate(*frames, {}, '20260901', '20260902', strategy='version8_1', fix_s81_band_precision=enabled)


@pytest.mark.parametrize('engine', [daily, minute])
def test_wrong_book_run_rejected_before_lake(engine):
    with pytest.raises(ValueError, match='only by version8_1'):
        engine.run('20260901', '20260902', strategy='version8_2', fix_s81_band_precision=True)


def test_wrong_book_cli_and_hooks_rejected():
    with pytest.raises(SystemExit, match='only by version8_1'):
        csv_run_kwargs_from_args(SimpleNamespace(strategy='version8_2', fix_s81_band_precision=True))
    with pytest.raises(ValueError, match='only by version8_1'):
        apply_csv_strategy('version8_2', fix_s81_band_precision=True)


@pytest.mark.parametrize('engine', [daily, minute])
@pytest.mark.parametrize('enabled', [False, True])
def test_main_forwards_cli_flag(engine, enabled, monkeypatch, tmp_path):
    class RunChecked(Exception):
        pass

    def check(*args, **kwargs):
        assert kwargs.get('fix_s81_band_precision', False) is enabled
        raise RunChecked

    monkeypatch.setattr(engine, 'run', check)
    argv = ['--strategy', 'version8_1', '--out-dir', str(tmp_path / 'out')]
    if enabled:
        argv.append('--fix-s81-band-precision')
    with pytest.raises(RunChecked):
        engine.main(argv)


@pytest.mark.parametrize('enabled', [False, True])
def test_minute_scan_changes_only_boundary_exit(enabled):
    import numpy as np

    hooks = apply_csv_strategy('version8_1', fix_s81_band_precision=enabled)
    idx, px, reason, _, _ = minute.scan_held_day(
        np.array([14.0]), np.array([14.0]), np.array([14.0]),
        cost=10.0, peak=16.0, n_days=1, can_sell=True,
        stop_pct=.20, profit_base=.15, trail_ratio=0.0, peak_gap_min=0,
        take_profit=hooks['take_profit'],
    )
    if enabled:
        assert idx == -1
    else:
        assert (idx, px, reason) == (0, 14.0, 'trail:band:50')
