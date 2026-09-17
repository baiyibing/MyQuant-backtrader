from types import SimpleNamespace

import pandas as pd
import pytest

from backtest.research import csv_ledger
from backtest.research import unified_exit_modea as a
from backtest.research import unified_exit_modeb as b
from tests.test_unified_exit_modeb_exit import CODE, INST, SESS, daily, frames


@pytest.mark.parametrize("k", [0.5, 0.98, 0.73])
def test_exdiv_value_thresholds_and_fractional_shares(k):
    bars = daily((100., 100 * k, 100 * k, 100 * k))
    minutes = frames([(1, 1000, 101*k, 99*k, 100*k)])
    er = b.evaluate_exit_modeb(INST, a.StrategySpec(2, 3, 5, 5), bars, minutes, SESS,
                              end=SESS[-1], exdiv={CODE: {SESS[1]: k}})
    assert er.reason == "mark_end"
    assert er.shares == pytest.approx(10000 / k)
    assert er.pnl == pytest.approx(-1000)
    if k == 0.73:
        assert er.shares % 100 != 0


def test_exdiv_scales_peak_and_reference_before_fill():
    bars = daily((100., 104., 52., 52.))
    minutes = frames([(1, 1000, 106, 100, 104), (2, 1000, 53, 49, 49.3)])
    er = b.evaluate_exit_modeb(INST, a.StrategySpec(3, 3, y=5), bars, minutes, SESS,
                              end=SESS[-1], exdiv={CODE: {SESS[2]: .5}})
    assert er.reason == "trailing" and er.sell_date == SESS[2]
    assert er.shares == 20000
    assert er.pnl == pytest.approx(20000 * 49.3 * .999 - 1001000)


def test_exdiv_during_halt_preserves_frozen_value():
    er = b.evaluate_exit_modeb(INST, a.StrategySpec(0, None), daily(), frames([]), SESS,
                              end=SESS[-1], exdiv={CODE: {SESS[1]: .5, SESS[2]: .8}})
    assert er.shares == 25000 and er.sell_price == 40
    assert er.pnl == pytest.approx(-1000)


def test_exdiv_buy_filter_maps_prior_close(tmp_path):
    (tmp_path / f"{SESS[1]}.csv").write_text(f"code,name\n{CODE},synthetic\n", encoding="utf-8")
    # 50 -> 55 is limit-up on ex date despite raw previous close being 100.
    inst = b.assemble_instances(tmp_path, SESS, daily((100., 55., 55., 55.)),
                                exdiv={CODE: {SESS[1]: .5}})[0]
    assert not inst.opened and inst.skip_reason == "limit_up"


def test_event_loader_noise_band_and_no_event_unchanged(tmp_path):
    adj, ex = tmp_path / "adj.parquet", tmp_path / "ex.parquet"
    pd.DataFrame({"date": SESS[:3], "stock_code": [CODE]*3,
                  "cumulative_adj_factor": [1., 1.004, 2.008]}).to_parquet(adj)
    pd.DataFrame({"stock_code": [CODE]*2, "ex_date": SESS[1:3]}).to_parquet(ex)
    ratios = b.load_exdiv_ratios([CODE], SESS[0], SESS[-1], adj_factor_path=adj, ex_date_index_path=ex)
    assert ratios == {CODE: {SESS[2]: .5}}
    args = (INST, a.StrategySpec(1, 1), daily(), frames([(1, 1500, 101, 99, 100)]), SESS)
    assert b.evaluate_exit_modeb(*args) == b.evaluate_exit_modeb(*args, exdiv={})


def test_shared_ledger_shares_contract_untouched():
    pos = SimpleNamespace(cost=100., peak=110., shares=10000)
    csv_ledger.rescale_position(pos, .5)
    assert (pos.cost, pos.peak, pos.shares) == (50., 55., 10000)
