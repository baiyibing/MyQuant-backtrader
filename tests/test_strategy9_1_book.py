"""ATR turtle contract and shared-host regression checks."""
from types import SimpleNamespace
import pandas as pd
import pytest
from backtest.research import strategy9_1_rules as rules
from backtest.research.csv_strategy_books import (
    apply_csv_strategy, get_book, resolve_research_pool_dir,
)
from backtest.research import csv_daily_backtest as daily


def frame():
    return pd.DataFrame(dict(open=[100.]*30, high=[101.]*30,
                             low=[99.]*30, close=[100.]*30),
                        index=pd.bdate_range('2026-01-01', periods=30))


@pytest.mark.parametrize('alias', ['9.1', '9_1', 'v9.1', 'v9_1', 'version9_1'])
def test_hooks_aliases(alias, tmp_path):
    assert get_book(alias).tag == 'v9_1'
    hooks = apply_csv_strategy(alias)
    assert hooks['allow_add'] and hooks['sizing'] == 'per_name'
    assert 'stop_range' not in hooks
    assert hooks['take_profit'](110, 100, 110, 2) is None
    with pytest.raises(SystemExit, match='stop-pct'):
        apply_csv_strategy(alias, stop_pct=.1)
    with pytest.raises(SystemExit, match='stock_pool'):
        resolve_research_pool_dir(alias, None, repo=tmp_path)
    with pytest.raises(SystemExit, match='stop-pct'):
        get_book(alias).run_kwargs(SimpleNamespace(stop_pct=.1))


def test_atr_prior_true_range_and_units():
    f = frame()
    day = f.index[21]
    f.loc[f.index[20], ['high', 'low', 'close']] = [105, 103, 104]
    assert rules.atr(f, day) == pytest.approx((19*2+5)/20)
    f.loc[day, ['high', 'low']] = [1000, 1]
    assert rules.atr(f, day) == pytest.approx(2.15)
    assert rules.unit_shares(2) == 5000
    assert rules.atr(f, f.index[19]) is None


def test_frozen_units_last_fill_profit_cap_and_low():
    f = frame()
    st = SimpleNamespace(positions={}, stats={}, book_state={})
    line = rules.bind(st, {'600000': f})
    prepare = st.book_state['prepare_unit']
    day = f.index[21]
    assert prepare('600000', 100, day) == 5000
    lots = [SimpleNamespace(cost=100., shares=5000, pending_exit=None)]
    st.positions['600000'] = lots
    st.book_on_buy(st, '600000', 'pool', 5000)
    assert rules.stop_line(100, 2) == 96
    assert line('600000', day) == 99  # prior ten lows dominate
    assert prepare('600000', 100.99, day) is None
    for px in [101., 102., 103.]:
        assert prepare('600000', px, day) == 5000
        lots.append(SimpleNamespace(cost=px, shares=5000, pending_exit=None))
        st.book_on_buy(st, '600000', 'add:step20', 5000)
    assert rules.stop_line(103, 2) == 99
    assert prepare('600000', 104, day) is None
    assert not rules.may_add([SimpleNamespace(cost=110, shares=5000), lots[-1]], 104, 2, 2)
    f.loc[day, 'low'] = 1
    assert rules.low_line(f, day) == 99


def test_help_params_and_version9_unchanged():
    for token in ['NAME_BUDGET = 1_000_000', 'ATR_PERIOD = 20', 'UNIT_RISK_FRAC = 0.01',
                  '10_000', '0.5', '4 units', 'freeze ATR', 'prior 10']:
        assert token in rules.HELP_LOCK
    st = SimpleNamespace(stats={})
    rules.record_strategy9_1_params(st)
    assert st.stats['unit_risk'] == 10_000
    assert st.stats['atr_period'] == 20 and st.stats['max_units'] == 4
    old = apply_csv_strategy('version9')
    assert old['take_profit'](111, 100, 111, 1) == 'profit_take:target'
    assert callable(old['stop_range']) and not old['allow_add']


def test_daily_signal_entry_add_and_whole_low_exit():
    f = frame()
    dates = f.index
    f.loc[dates[22], ['open', 'high', 'low', 'close']] = [102, 103, 100, 102]
    f.loc[dates[23], ['open', 'high', 'low', 'close']] = [98, 100, 97, 98]
    st = daily.simulate({'600000': f}, {dates[21].strftime('%Y%m%d'): ['600000']},
                        dates[21].strftime('%Y%m%d'), dates[24].strftime('%Y%m%d'),
                        strategy='version9_1', total_cash=5_000_000,
                        rule_profile="legacy")
    buys = [t for t in st.trades if t['side'] == 'BUY']
    sells = [t for t in st.trades if t['side'] == 'SELL']
    assert len(buys) == 2
    assert all(t['shares'] == 5000 for t in buys)
    assert len(sells) == 2
    assert not st.positions


def test_short_history_skips():
    f = frame().iloc[:10]
    ds = f.index[5].strftime('%Y%m%d')
    st = daily.simulate({'600000': f}, {ds: ['600000']}, ds, ds,
                        strategy='version9_1', rule_profile="legacy")
    assert st.stats['skip_atr_history'] == 1
    assert not st.positions


def test_minute_low_trigger_and_exact_units():
    from backtest.research import csv_minute_backtest as minute
    f = frame()
    days = f.index[21:24]
    rows = []
    for j, day in enumerate(days):
        for hm in [930, 1455, 1500]:
            px = 100 if j == 0 else 102 if j == 1 else 100
            rows.append(dict(datetime=day + pd.Timedelta(hours=hm//100, minutes=hm%100),
                             ymd=day.strftime("%Y%m%d"), hm=(hm//100)*60+hm%100, open=px, high=px+1, low=98 if j == 2 else px,
                             close=px, volume=1_000_000))
    m = pd.DataFrame(rows).set_index('datetime')
    st = minute.simulate({'600000': m}, {'600000': f},
                         {days[0].strftime('%Y%m%d'): ['600000']},
                         days[0].strftime('%Y%m%d'), days[-1].strftime('%Y%m%d'),
                         strategy='version9_1', total_cash=5_000_000,
                         rule_profile="legacy")
    buys = [t for t in st.trades if t['side'] == 'BUY']
    sells = [t for t in st.trades if t['side'] == 'SELL']
    assert len(buys) == 2 and all(t['shares'] == 5000 for t in buys)
    assert len(sells) == 2
    assert not st.positions


def test_daily_limit_up_add_skip_and_limit_down_defer():
    f = frame()
    dates = f.index
    f.loc[dates[22], ['open', 'high', 'low', 'close']] = [110, 110, 100, 110]
    f.loc[dates[23], ['open', 'high', 'low', 'close']] = [99, 99, 99, 99]
    f.loc[dates[24], ['open', 'high', 'low', 'close']] = [98, 100, 97, 98]
    # Day 23 lower band is 99 (prior close 110): exit must persist.
    st = daily.simulate({'600000': f}, {dates[21].strftime('%Y%m%d'): ['600000']},
                        dates[21].strftime('%Y%m%d'), dates[24].strftime('%Y%m%d'),
                        strategy='version9_1', total_cash=5_000_000,
                        rule_profile="legacy")
    assert len([t for t in st.trades if t['side'] == 'BUY']) == 1
    assert st.stats['skip_limit_up'] >= 1
    assert st.stats['defer_sell_limit_down'] >= 1
    assert not st.positions


def test_atr_stop_can_rise_above_weighted_cost():
    f = frame()
    st = SimpleNamespace(positions={}, stats={}, book_state={})
    line = rules.bind(st, {'600000': f})
    day = f.index[21]
    assert st.book_state['prepare_unit']('600000', 100, day) == 5000
    st.positions['600000'] = [SimpleNamespace(cost=100., shares=5000)]
    st.book_on_buy(st, '600000', 'pool', 5000)
    st.positions['600000'].append(SimpleNamespace(cost=110., shares=5000))
    st.book_on_buy(st, '600000', 'add:step20', 5000)
    assert line('600000', day) == 106
