"""Predeclared version9 sell experiments, using synthetic 2025 bars only."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from backtest.research import csv_daily_backtest as daily, csv_minute_backtest as minute
from backtest.research.csv_strategy_books import apply_csv_strategy, csv_run_kwargs_from_args
from backtest.research.strategy9_rules import SELL_MODES, version9_exit, stop_range_amplitude


def fixture_frame(history=21, high=10.25, low=9.75):
    days = pd.bdate_range('2025-09-01', periods=history + 4)
    frame = pd.DataFrame(dict(open=10., high=high, low=low, close=10.), index=days)
    return days, frame


def run_host(host, days, frame, history=21, mode=None, **kwargs):
    start, end = days[history].strftime('%Y%m%d'), days[-1].strftime('%Y%m%d')
    bars, pool = {'600000.SH': frame}, {start: ['600000.SH']}
    if host == daily:
        return host.simulate(bars, pool, start, end, strategy='version9', version9_sell=mode, **kwargs)
    rows = []
    for day, row in frame.iterrows():
        for hm in (570, 895, 900):
            rows.append(dict(row, time=day + pd.Timedelta(minutes=hm), hm=hm, ymd=day.strftime('%Y%m%d')))
    minutes = {'600000.SH': pd.DataFrame(rows).set_index('time')}
    return host.simulate(minutes, bars, pool, start, end, strategy='version9',
                         version9_sell=mode, minute_stop_trigger='hl', **kwargs)


def sells(st):
    return [t for t in st.trades if t['side'] == 'SELL']


@pytest.mark.parametrize('host', [daily, minute])
@pytest.mark.parametrize('mode,multiple', [('mean_tr3_tp10', 3), ('mean_tr2_or_prior10_low', 2)])
def test_yuan_stop(host, mode, multiple):
    days, frame = fixture_frame(high=10.05, low=9.95)
    # TR=.1 including entry; triggers remain above the exchange lower limit.
    frame.loc[days[22], 'low'] = 10 - multiple * .1 - .01
    st = run_host(host, days, frame, mode=mode)
    assert sells(st)[0]['reason'] == 'stop_loss:touch'
    assert sells(st)[0]['price'] == pytest.approx(10 - multiple * .1)
    assert st.stats['sell_mode'] == mode


@pytest.mark.parametrize('host', [daily, minute])
def test_one_tr_is_not_three(host):
    days, frame = fixture_frame()
    frame.loc[days[22], 'low'] = 9.49
    assert sells(run_host(host, days, frame, mode='mean_tr3_tp10')) == []


@pytest.mark.parametrize('host', [daily, minute])
@pytest.mark.parametrize('mode', [None, 'mean_tr3_tp10', 'range_amp_tp_amp'])
def test_targets(host, mode):
    days, frame = fixture_frame()
    frame.loc[days[22], ['high', 'close']] = 11.
    st = run_host(host, days, frame, mode=mode)
    assert sells(st)[0]['reason'] == 'profit_take:target'
    if host == minute:
        assert sells(st)[0]['price'] == pytest.approx(10.5 if mode == 'range_amp_tp_amp' else 11.)


@pytest.mark.parametrize('host', [daily, minute])
def test_large_amplitude_no_ten_percent(host):
    days, frame = fixture_frame(high=11.25, low=8.75)
    frame.loc[days[22], ['high', 'close']] = 11.
    assert sells(run_host(host, days, frame, mode='range_amp_tp_amp')) == []
    frame.loc[days[22], ['high', 'close']] = 12.5
    st = run_host(host, days, frame, mode='range_amp_tp_amp')
    assert sells(st)[0]['reason'] == 'profit_take:target'
    if host == minute:
        assert sells(st)[0]['price'] == pytest.approx(12.5)


@pytest.mark.parametrize('host', [daily, minute])
@pytest.mark.parametrize('mode', [None, 'range_amp_tp_amp'])
def test_range_stop(host, mode):
    days, frame = fixture_frame()
    amplitude = stop_range_amplitude(frame, days[22])
    frame.loc[days[22], 'low'] = 9.49
    st = run_host(host, days, frame, mode=mode)
    assert sells(st)[0]['price'] == pytest.approx(10 * (1-amplitude))
    assert sells(st)[0]['reason'] == 'stop_loss:touch'


@pytest.mark.parametrize('host', [daily, minute])
@pytest.mark.parametrize('mode', SELL_MODES)
@pytest.mark.parametrize('event', ['low', 'gain'])
def test_missing_no_fallback(host, mode, event):
    days, frame = fixture_frame(history=2)
    frame.loc[days[3], ['high', 'low', 'close']] = [11.5, 9., 11.] if event == 'gain' else [10.25, 9.1, 9.3]
    st = run_host(host, days, frame, history=2, mode=mode)
    assert sells(st) == []
    assert st.stats['skip_version9_exit:stop_window'] > 0
    if mode == 'mean_tr2_or_prior10_low':
        assert st.stats['skip_version9_exit:channel_window'] > 0


@pytest.mark.parametrize('host', [daily, minute])
@pytest.mark.parametrize('close,reason', [(11., None), (9.75, None), (9.74, 'close_below:prior_10d_low')])
def test_channel(host, close, reason):
    days, frame = fixture_frame()
    frame.loc[days[22], ['high', 'low', 'close']] = [max(close, 10.25), min(close, 9.75), close]
    st = run_host(host, days, frame, mode='mean_tr2_or_prior10_low')
    found = sells(st)
    assert [t['reason'] for t in found] == ([reason] if reason else [])
    if reason and host == minute:
        assert found[0]['price'] == pytest.approx(close)
        assert found[0]['date'] == days[22].strftime('%Y%m%d')


@pytest.mark.parametrize('host', [daily, minute])
@pytest.mark.parametrize('strategy,mode,max_hold', [('version6', SELL_MODES[0], False), ('version9', 'unknown', False), ('version9', SELL_MODES[2], True)])
def test_rejections(host, strategy, mode, max_hold, tmp_path):
    args = dict(strategy=strategy, version9_sell=mode, max_hold=max_hold)
    with pytest.raises(ValueError):
        apply_csv_strategy(**args)
    with pytest.raises(SystemExit):
        csv_run_kwargs_from_args(SimpleNamespace(**args))
    with pytest.raises(ValueError):
        if host == daily:
            host.simulate({}, {}, '20250901', '20250903', **args)
        else:
            host.simulate({}, {}, {}, '20250901', '20250903', **args)
    with pytest.raises(SystemExit):
        host.main(['--strategy', strategy, '--version9-sell', mode, '--pool-dir', str(tmp_path)] + (['--max-hold'] if max_hold else []))


def test_true_ranges_use_previous_close_and_roll():
    days, frame = fixture_frame()
    frame.loc[days[1], ['high', 'low', 'close']] = [12., 11., 11.5]
    plan = version9_exit(frame, days[21], 'mean_tr3_tp10')
    # 2 gap-up TR, 1.75 gap-down TR, eighteen .5 ranges.
    assert plan['stop_yuan'] == pytest.approx(3 * (2 + 1.75 + 18*.5)/20)
    frame.loc[days[21], 'high'] = 100.
    assert version9_exit(frame, days[21], 'mean_tr3_tp10') == plan


def test_version9_2_range_unchanged():
    from backtest.research.strategy9_2_rules import stop_range_amplitude as sibling_range
    days, frame = fixture_frame()
    assert sibling_range is stop_range_amplitude
    assert sibling_range(frame, days[21]) == pytest.approx(.05)


@pytest.mark.parametrize('mode', SELL_MODES)
def test_chronological_minute_yuan_and_ratio(mode):
    days, frame = fixture_frame(high=10.05, low=9.95)
    plan = version9_exit(frame, days[22], mode)
    trigger = 10 - plan['stop_yuan'] if plan['stop_yuan'] is not None else 10 * (1-plan['stop_ratio'])
    frame.loc[days[22], 'low'] = trigger - .01
    st = run_host(minute, days, frame, mode=mode, fix_minute_cash_order=True)
    assert sells(st)[0]['reason'] == 'stop_loss:touch'
    assert sells(st)[0]['price'] == pytest.approx(trigger)


@pytest.mark.parametrize('mode', SELL_MODES[:2])
@pytest.mark.parametrize('host', [daily, minute])
def test_opt_in_max_hold(host, mode):
    days = pd.bdate_range('2025-09-01', periods=46)
    frame = pd.DataFrame(dict(open=10., high=10.05, low=9.95, close=10.), index=days)
    st = run_host(host, days, frame, mode=mode, max_hold=True)
    assert sells(st)[0]['reason'] == 'force_sell:max_hold'


@pytest.mark.parametrize('missing', ['open', 'high', 'low', 'close'])
@pytest.mark.parametrize('mode', SELL_MODES)
def test_invalid_window_plan(missing, mode):
    days, frame = fixture_frame()
    frame.loc[days[2], missing] = np.nan
    plan = version9_exit(frame, days[21], mode)
    assert plan['stop_yuan'] is None
    assert plan['stop_ratio'] is None
    assert plan['take_profit_pct'] is None
