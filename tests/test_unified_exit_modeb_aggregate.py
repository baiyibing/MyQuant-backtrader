import json
import subprocess
import sys

import pandas as pd
import pytest

from backtest.research import unified_exit_modea as a
from backtest.research import unified_exit_modeb as b
from tests.test_unified_exit_modeb_exit import CODE, INST, SESS, daily, frames


def test_oracle_q38_keeps_same_day_before_and_after_blocked_minute():
    for rows, hm in [([(1, 600, 110, 109, 110), (1, 660, 90, 90, 90)], 600),
                     ([(1, 600, 90, 90, 90), (1, 660, 110, 109, 110)], 660)]:
        er = b.oracle_exits([INST], daily(), frames(rows), SESS)[a.instance_key(INST)]
        assert (er.reason, er.sell_price, er.sell_hm) == ('oracle', 110, hm)


def test_oracle_compares_rescaled_proceeds_and_falls_back():
    exdiv = {CODE: {SESS[2]: .5}}
    bars = daily((100, 100, 50, 50))
    minutes = frames([(1, 600, 105, 105, 105), (2, 600, 55, 55, 55)])
    er = b.oracle_exits([INST], bars, minutes, SESS, exdiv=exdiv)[a.instance_key(INST)]
    assert er.sell_date == SESS[2] and er.shares == 20000
    fallback = b.oracle_exits([INST], daily(), frames([(1, 600, 90, 90, 90)]), SESS)
    assert fallback[a.instance_key(INST)].reason == 'mark_end'
    assert not fallback[a.instance_key(INST)].is_trade


def test_equity_exdiv_drawdown_and_sell_before_buy():
    second = a.Instance(CODE, 'synthetic', SESS[2], 50., True)
    instances = [INST, second]
    minutes = frames([(1, 900, 110, 110, 110), (2, 900, 50, 50, 50),
                      (3, 900, 55, 55, 55)])
    events = {CODE: {SESS[2]: .5}}
    exits = b.evaluate_matrix(instances, [a.StrategySpec(1, 2)], daily(), minutes,
                              SESS, end=SESS[-1], exdiv=events)['r1_n2']
    rows, lots, cap = b.build_daily_equity(instances, exits, minutes, SESS, exdiv=events)
    assert [r['equity'] - a.CASH_POOL for r in rows] == pytest.approx([-1000, 99000, -3000, 97000])
    assert lots == 1 and cap == 1_000_000
    m = b.aggregate_strategy('r1_n2', instances, exits, minutes, SESS, exdiv=events)
    assert m.total_pnl == pytest.approx(97000)
    assert m.total_return == pytest.approx(97000 / a.CASH_POOL)
    assert m.annualized == pytest.approx((1 + m.total_return)**(365/322)-1)
    assert m.max_drawdown == pytest.approx(102000 / (a.CASH_POOL + 99000))
    assert m.win_rate == .5
    assert m.profit_factor == pytest.approx(99000 / 2000)


def test_halt_exdiv_and_delist_changes_only_final_value():
    minutes = frames([(1, 900, 100, 100, 100)])
    events = {CODE: {SESS[2]: .73}}
    key = a.instance_key(INST)
    hold = b.evaluate_matrix([INST], [a.StrategySpec(0, None)], daily(), minutes,
                             SESS, end=SESS[-1], exdiv=events)['anchor_hold_end']
    zero = b.delisting_zero_exits([INST], hold, SESS, end=SESS[-1])
    normal_rows, _, _ = b.build_daily_equity([INST], hold, minutes, SESS, exdiv=events)
    zero_rows, _, _ = b.build_daily_equity([INST], zero, minutes, SESS, exdiv=events)
    assert normal_rows[:-1] == zero_rows[:-1]
    assert [r['mtm'] for r in normal_rows] == pytest.approx([1_000_000]*4)
    assert zero_rows[-1]['mtm'] == 0
    assert zero[key].pnl == pytest.approx(-1001000)
    m = b.aggregate_strategy('delist_zero', [INST], zero, minutes, SESS, exdiv=events)
    assert m.total_return * a.CASH_POOL == pytest.approx(m.total_pnl)
    assert not zero[key].is_trade


def test_pipeline_reports_robustness_and_isolation(tmp_path):
    sessions = ['20251023', '20251024', '20260407', '20260408', '20260909']
    pool = tmp_path / 'pool'
    pool.mkdir()
    for day in (sessions[0], sessions[2]):
        (pool / f'{day}.csv').write_text(f'code,name\n{CODE},synthetic\n', encoding='utf-8')
    bars = {CODE: pd.DataFrame({'open': [100]*5, 'close': [100]*5},
                               index=pd.to_datetime(sessions))}
    minutes = {CODE: pd.DataFrame({'ymd': sessions, 'hm': [900]*5,
                                   'high': [100]*5, 'low': [100]*5, 'close': [100]*5})}
    out = tmp_path / 'unified_exit_modeb'
    result = b.run_modeb(pool, sessions=sessions, bars=bars, minute_bars=minutes, exdiv={}, out_dir=out)
    assert len([s for s in b.iter_grid() if s.rule == 2]) == 18
    assert len(result['ranked']) == 19
    assert set(result['anchors']) == {'anchor_hold_end', 'r1_n1', 'oracle', 'delist_zero'}
    robust = result['robustness']
    assert len(robust['half_windows']['h1']) == len(robust['half_windows']['h2']) == 19
    assert robust['half_windows']['top20_overlap'] == 19
    assert robust['plateau'] and robust['board'] and robust['month'] and robust['next_open_buy']
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['meta']['mode'] == 'B'
    assert 'open-gap' in summary['meta']['price_domain']
    assert 'Q38=A' in summary['meta']['oracle']
    assert summary['meta']['minute_coverage']['covered_codes'] == 1
    assert (out / 'ranking.csv').exists()
    detail = pd.read_csv(out / 'instance_detail_top.csv')
    assert 'sell_hm' in detail.columns
    assert set(detail.loc[detail.is_trade, 'sell_hm']) == {900}
    assert not (tmp_path / 'unified_exit_modea').exists()
    with pytest.raises(ValueError, match='Mode B'):
        b.run_modeb(pool, out_dir=tmp_path / 'unified_exit_modea' / 'nested')


def test_cli_help_and_default_directory():
    run = subprocess.run([sys.executable, 'scripts/research/run_unified_exit_modeb.py', '--help'],
                          capture_output=True, text=True, check=True)
    assert '模式 B' in run.stdout and '窄网格' in run.stdout
    assert b.DEFAULT_OUT_DIR.as_posix() == 'backtest_output/unified_exit_modeb'
