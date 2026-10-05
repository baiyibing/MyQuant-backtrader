import numpy as np
import pytest
from backtest.research.fill_config import FillConfig, default_fill_config, DEFAULT_FILL_CONFIGS
from backtest.research.csv_minute_backtest import scan_held_day_python, scan_held_day


def scan(o=(100., 96.), h=(101., 97.), c=(94., 96.), **kw):
    args = dict(cost=100., peak=100., n_days=1, can_sell=True,
                stop_pct=.05, profit_base=10., trail_ratio=0., peak_gap_min=0)
    args.update(kw)
    return scan_held_day_python(np.array(o), np.array(h), np.array(c), **args)


@pytest.mark.parametrize('mode,price', [('close',94.), ('hl',95.)])
def test_defaults(mode, price):
    kw = dict(minute_stop_trigger=mode, l=np.array([93., 95.]))
    legacy = scan(**kw)
    explicit = scan(fill_config=default_fill_config(mode), **kw)
    assert legacy == explicit
    assert explicit[:3] == (0,price,'stop_loss:touch')


def test_mapping():
    assert default_fill_config(hooks={'bind_absolute_exit': object()}) == DEFAULT_FILL_CONFIGS['absolute_exit']
    assert DEFAULT_FILL_CONFIGS['version9_plan'] == FillConfig()
    for path in ['trail', 'take_profit', 'force_sell', 'close_clear']:
        assert DEFAULT_FILL_CONFIGS[path] == FillConfig()


@pytest.mark.parametrize('at,price', [('line',95.), ('bar_last',94.), ('bar_low',93.), (92.5,92.5)])
def test_this_bar_prices(at,price):
    assert scan(l=np.array([93.,95.]), fill_config=FillConfig('bar_low','this_bar',at))[:3] == (0,price,'stop_loss:touch')


@pytest.mark.parametrize('at', ['bar_open','bar_high','bar_low','bar_last','line',92.5])
def test_next_open_prices(at):
    assert scan(fill_config=FillConfig('bar_last','next_bar_open',at))[:3] == (1,96.,'stop_loss:touch:next_open')


@pytest.mark.parametrize('timing,idx,price,reason', [('this_bar',0,90.,'stop_loss:gap_open'),('next_bar_open',1,96.,'stop_loss:gap_open:next_open')])
def test_gap(timing,idx,price,reason):
    assert scan(o=(90.,96.),fill_config=FillConfig('bar_last',timing,'line'))[:3] == (idx,price,reason)


@pytest.mark.parametrize('basis,at', [('bar_last','bar_open'),('bar_low','bar_open'),('bar_last','bar_low'),('bar_low','bar_high'),('bar_last','bar_high')])
def test_lookahead(basis,at):
    with pytest.raises(ValueError,match='look-ahead'):
        FillConfig(basis,'this_bar',at)


def test_carry_and_limit_retry():
    state = {}
    cfg = FillConfig(fill_timing='next_bar_open')
    assert scan(o=(100.,),h=(101.,),c=(94.,),fill_config=cfg,fill_state=state)[0] == -1
    assert state == {'pending':'stop_loss:touch:next_open'}
    result = scan(o=(90.,92.),h=(90.,93.),c=(90.,92.),limit_down=90.,fill_config=cfg,fill_state=state)
    assert result[:3] == (1,92.,'stop_loss:touch:next_open')
    assert state == {}


@pytest.mark.parametrize('hm', [895,900])
def test_time_exits_stay_this_bar(hm):
    cfg = FillConfig(fill_timing='next_bar_open')
    assert scan(c=(100.,100.),hm=np.array([hm,hm+1]),stop_pct=None,force_sell_hm=hm,fill_config=cfg)[:3] == (0,100.,'force_sell:time')
    assert scan(c=(100.,100.),hm=np.array([hm,hm+1]),stop_pct=None,close_clear=lambda *a:'clear',fill_config=cfg)[:3] == ((0,100.,'clear') if hm==900 else (1,100.,'clear'))


@pytest.mark.parametrize('env', [False,True])
def test_numba_refuses(monkeypatch,env):
    import backtest.research.csv_minute_backtest as m
    monkeypatch.setattr(m,'_NUMBA_SCAN_AVAILABLE',True)
    if env:
        monkeypatch.setenv('CSV_SCAN_HELD_DAY_BACKEND','numba')
    with pytest.raises(ValueError,match='non-default fill_config'):
        scan_held_day(np.array([100.]),np.array([101.]),np.array([94.]),cost=100.,peak=100.,n_days=1,can_sell=True,stop_pct=.05,profit_base=10.,trail_ratio=0.,fill_config=FillConfig(fill_at='line'),use_numba=None if env else True)


def test_version9_plan_defaults():
    plan = dict(stop_yuan=5.,stop_ratio=None,channel_low=None,take_profit_pct=.1)
    assert scan(version9_plan=plan) == scan(version9_plan=plan,fill_config=DEFAULT_FILL_CONFIGS['version9_plan'])
    assert scan(version9_plan=plan)[:3] == (0,94.,'stop_loss:touch')


@pytest.mark.parametrize('next_open', [False,True])
def test_target_and_trail(next_open):
    cfg = FillConfig(fill_timing='next_bar_open') if next_open else None
    assert scan(o=(100.,106.),h=(111.,107.),c=(110.,106.),stop_pct=None,take_profit=lambda px,*a: 'profit_take:target' if px>=110 else None,take_profit_pct=.1,fill_config=cfg)[:3] == ((1,106.,'profit_take:target:next_open') if next_open else (0,110.,'profit_take:target'))
    assert scan(o=(100.,106.),h=(120.,107.),c=(105.,106.),stop_pct=None,profit_base=.01,trail_ratio=.5,fill_config=cfg)[:3] == ((1,106.,'trail:T+1:next_open') if next_open else (0,105.,'trail:T+1'))


def test_callback_low_rejected_at_decision():
    with pytest.raises(ValueError,match='look-ahead'):
        scan(c=(110.,106.),l=np.array([99.,105.]),stop_pct=None,take_profit=lambda *a:'profit_take',fill_config=FillConfig('bar_low','this_bar','bar_low'))


def test_missing_carry_state_fails_closed():
    with pytest.raises(ValueError,match='fill_state'):
        scan(o=(100.,),h=(101.,),c=(94.,),fill_config=FillConfig(fill_timing='next_bar_open'))


def test_all_book_defaults_derived_from_hooks():
    from backtest.research.csv_strategy_books import BOOKS, apply_csv_strategy
    from backtest.research.fill_config import book_fill_defaults
    for name in BOOKS:
        hooks = apply_csv_strategy(name,scores_by_day={'20260101': {'000001': 1.}})
        defaults = book_fill_defaults(hooks)
        assert defaults['stop'] == (DEFAULT_FILL_CONFIGS['absolute_exit'] if 'bind_absolute_exit' in hooks else FillConfig())
        assert defaults['force_sell'] == FillConfig()
        assert defaults['close_clear'] == FillConfig()


@pytest.mark.parametrize('cash_order', [False,True])
@pytest.mark.parametrize('strategy', ['version3','version8'])
def test_simulate_carries_next_session(strategy,cash_order):
    import pandas as pd
    from backtest.research.csv_minute_backtest import simulate
    days = ['20260901','20260902','20260903']
    hm = [895,900,570]
    frame = pd.DataFrame([(10.,10.,10.,10.),(10.,10.,9.3,9.4),(9.2,9.4,9.1,9.3)],columns=['open','high','low','close'])
    frame['ymd'],frame['hm'],frame['volume'] = days,hm,100_000
    frame.index = pd.to_datetime(days) + pd.to_timedelta(hm,unit='m')
    daily = pd.DataFrame({k:[10.]*4 for k in ['open','high','low','close']},index=pd.to_datetime(['20260831']+days))
    audit = []
    st = simulate(audit_sink=audit,minute_bars={'600000.SH':frame},daily_bars={'600000.SH':daily},pool_days={days[0]:['600000.SH']},start=days[0],end=days[-1],strategy=strategy,total_cash=100_000.,daily_quota=10_000.,name_budget=10_000.,stop_pct=.05,fix_minute_cash_order=cash_order,fill_config=FillConfig(fill_timing='next_bar_open'))
    sells = [t for t in st.trades if t['side']=='SELL']
    assert len(sells)==1
    assert sells[0]['price']==9.2
    assert sells[0]['reason']=='stop_loss:touch:next_open'
    assert sells[0]['price_rule']=='minute_pending_next_open'
    assert [t for t in audit if t['side']=='SELL'][0]['phase']=='open'


def test_target_cannot_assume_low_after_high():
    with pytest.raises(ValueError,match='look-ahead'):
        scan(o=(100.,106.),h=(111.,107.),c=(105.,106.),l=np.array([99.,105.]),minute_stop_trigger='hl',stop_pct=None,take_profit=lambda *a:'profit_take:target',take_profit_pct=.1,fill_config=FillConfig('bar_low','this_bar','bar_low'))
