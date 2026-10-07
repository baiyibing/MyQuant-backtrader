from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from backtest.research.ashare_fees import INDUSTRY_ACCOUNT_FEES
from backtest.research.ashare_volume_cap import BucketVolume, VolumeCap
from backtest.research.csv_ledger import (
    SimState,
    bind_account_fee_schedule,
    execute_buy,
    preview_final_buy_declaration,
)
from backtest.research.lot_rounding import (
    BOARD_BUY_QUANTITY,
    BSE_BUY_QUANTITY,
    STAR_BUY_QUANTITY,
    buy_quantity_increment,
    buy_quantity_rule,
)
from backtest.research.market_layer import buy_quantity_market
from backtest.research.rule_profile import INDUSTRY
from backtest.research.strategy7_engine import SimResult, _buy

DAY = date(2026, 10, 6)


def _industry_state(*, cash=1_000_000.0, volume_cap=None):
    state = SimState(cash=cash, volume_cap=volume_cap)
    state.rule_profile = INDUSTRY
    bind_account_fee_schedule(state, INDUSTRY_ACCOUNT_FEES)
    return state


@pytest.mark.parametrize("code", ["688001.SH", "689001.SH"])
def test_industry_star_uses_200_minimum_then_one_share_increments(code):
    assert (
        buy_quantity_rule(
            buy_quantity_market(code), exchange_quantity_rules=True
        )
        == STAR_BUY_QUANTITY
    )
    state = _industry_state()
    assert execute_buy(state, code, 10.0, 2_500.0, 0, DAY)
    assert state.trades[-1]["shares"] == 249


@pytest.mark.parametrize("code", ["920014.BJ", "430001.BJ", "830001.BJ", "870001.BJ"])
def test_industry_bse_uses_100_minimum_then_one_share_increments(code):
    assert (
        buy_quantity_rule(
            buy_quantity_market(code), exchange_quantity_rules=True
        )
        == BSE_BUY_QUANTITY
    )
    state = _industry_state()
    assert execute_buy(state, code, 10.0, 2_500.0, 0, DAY)
    assert state.trades[-1]["shares"] == 249


@pytest.mark.parametrize("code", ["600000.SH", "000001.SZ", "300001.SZ"])
def test_industry_main_and_chinext_remain_100_share_multiples(code):
    assert (
        buy_quantity_rule(
            buy_quantity_market(code), exchange_quantity_rules=True
        )
        == BOARD_BUY_QUANTITY
    )
    state = _industry_state()
    assert execute_buy(state, code, 10.0, 2_500.0, 0, DAY)
    assert state.trades[-1]["shares"] == 200


@pytest.mark.parametrize(
    ("code", "budget", "reason"),
    [
        ("688001.SH", 2_000.0, "skip_star_buy_declare_qty"),
        ("920014.BJ", 1_000.0, "skip_min_lot_budget"),
    ],
)
def test_industry_fee_aware_sizing_enforces_exchange_minimum(code, budget, reason):
    state = _industry_state()
    assert not execute_buy(state, code, 10.0, budget, 0, DAY)
    assert state.stats[reason] == 1
    assert state.trades == []


def test_p09_switch_is_opt_in_and_legacy_quantity_stays_board_lot():
    pre_p09 = replace(
        INDUSTRY,
        revision="industry-p08-20261006",
        exchange_quantity_rules=False,
    )
    state = SimState(cash=1_000_000.0)
    state.rule_profile = pre_p09
    bind_account_fee_schedule(state, INDUSTRY_ACCOUNT_FEES)
    assert execute_buy(state, "920014.BJ", 10.0, 2_500.0, 0, DAY)
    assert state.trades[-1]["shares"] == 200

    legacy = SimState(cash=1_000_000.0)
    assert execute_buy(legacy, "688001.SH", 10.0, 2_500.0, 0, DAY)
    assert legacy.trades[-1]["shares"] == 200


@pytest.mark.parametrize("code", ["688001.SH", "920014.BJ"])
def test_b8_12_preview_and_execution_use_the_same_final_declaration(code):
    state = _industry_state()
    preview, _, _, rule = preview_final_buy_declaration(
        state, code, 10.0, 2_500.0, pd.Timestamp(DAY)
    )
    assert buy_quantity_increment(rule) == 1
    assert preview == 249
    assert execute_buy(state, code, 10.0, 2_500.0, 0, DAY)
    assert state.trades[-1]["shares"] == preview


def test_volume_cap_partial_fill_is_not_a_new_star_declaration():
    code = "688001.SH"
    key = (code, "20261006", 895)
    cap = VolumeCap(
        1,
        {key: BucketVolume(100, 895, "raw_shares_incremental")},
    )
    state = _industry_state(volume_cap=cap)
    assert execute_buy(
        state,
        code,
        10.0,
        3_000.0,
        0,
        DAY,
        bucket_id=895,
    )
    assert state.trades[-1]["shares"] == 100


@pytest.mark.parametrize("code", ["688001.SH", "920014.BJ"])
def test_native_v7_uses_the_same_exchange_quantity_rules(code):
    state = SimResult(1_000_000.0)
    state.rule_profile = INDUSTRY
    bind_account_fee_schedule(state, INDUSTRY_ACCOUNT_FEES)
    position = _buy(
        state,
        None,
        code,
        DAY,
        895,
        100.0,
        0.20,
        "buy:trial",
        "trial",
        fee=INDUSTRY_ACCOUNT_FEES,
    )
    assert position is not None
    assert state.trades[-1]["shares"] == 1999
