from dataclasses import replace
from datetime import date

import pytest

from backtest.research import strategy9_2_engine, strategy12_engine, strategy12_rules
from backtest.research.ashare_fees import INDUSTRY_ACCOUNT_FEES
from backtest.research.csv_ledger import (
    IndependentGroup,
    IndependentPosition,
    Position,
    SimState,
    account_sell_quantity,
    bind_account_fee_schedule,
    configure_s8,
    exit_positions,
)
from backtest.research.minute_cash_order import scale_out_exits
from backtest.research.rule_profile import INDUSTRY
from backtest.research.strategy7_engine import (
    Lot as V7Lot,
    Position as V7Position,
    SimResult,
    _sell_lots,
)

PRE_P10 = replace(
    INDUSTRY,
    revision="industry-p09-20261006",
    account_odd_lot_exit=False,
)


def _shared_state(profile=INDUSTRY, *, cash=100_000.0):
    state = SimState(cash=cash)
    state.rule_profile = profile
    bind_account_fee_schedule(state, INDUSTRY_ACCOUNT_FEES)
    return state


@pytest.mark.parametrize(
    ("code", "held", "wanted", "industry_wanted"),
    [
        ("600000.SH", 150, 100, 150),
        ("688001.SH", 300, 200, 300),
        ("688001.SH", 400, 200, 200),
        ("600000.SH", 50, 0, 0),
        ("600000.SH", 200, 500, 500),
    ],
)
def test_sell_quantity_absorbs_only_a_sub_board_lot_account_remainder(
    code, held, wanted, industry_wanted
):
    assert account_sell_quantity(_shared_state(), code, held, wanted) == industry_wanted
    assert account_sell_quantity(_shared_state(PRE_P10), code, held, wanted) == wanted


def _s8_scale_state(profile):
    code = "600000.SH"
    state = _shared_state(profile)
    configure_s8(
        state,
        {"name": "version6_13", "sizing": "per_name", "name_budget": 10_000.0},
    )
    position_id = f"{code}@20261005"
    first = IndependentPosition(
        code, 50, 10.0, 0, 10.0, lot_id=0,
        position_id=position_id, entry_signal_date="20261005",
    )
    second = IndependentPosition(
        code, 100, 10.0, 0, 10.0, lot_id=1, is_step=True,
        position_id=position_id, entry_signal_date="20261005",
    )
    state.positions[code] = [first, second]
    state.book_state["s8_independent"]["groups"][position_id] = IndependentGroup(
        code, "20261005", 10_000.0, first, next_lot_id=2,
    )
    return state, code, exit_positions(state, code, 1, day="20261006")[0]


def test_s8_scale_out_absorbs_group_remainder_without_per_lot_residues():
    legacy, code, legacy_position = _s8_scale_state(PRE_P10)
    industry, _, industry_position = _s8_scale_state(INDUSTRY)
    args = (10.5, "20261006", 1, (12.0, 8.0))
    kwargs = {"scale_step": 0.05, "scale_frac": 0.67, "hm": 600}

    assert scale_out_exits(legacy, code, legacy_position, *args, **kwargs) == 100
    assert sum(lot.shares for lot in legacy.positions[code]) == 50

    assert scale_out_exits(industry, code, industry_position, *args, **kwargs) == 150
    assert code not in industry.positions
    sells = [row for row in industry.trades if row["side"] == "SELL"]
    assert [row["shares"] for row in sells] == [50, 100]
    assert sum(row["commission"] for row in sells) == pytest.approx(5.0)


def test_strategy9_2_scale_out_expands_star_odd_remainder():
    def plan(profile):
        state = _shared_state(profile)
        code = "688001.SH"
        state.positions[code] = [Position(code, 200, 10.0, 0, 10.0)]
        memory = strategy9_2_engine.memory_for(state, code)
        memory.entry = memory.cost = 10.0
        memory.peak = 20.0
        memory.units = 1
        return strategy9_2_engine.plan_exit(
            state, code, 20.0, None, [], day_i=1, ds="20261006"
        )

    assert plan(PRE_P10) == ("profit_take:band:4", 100)
    assert plan(INDUSTRY) == ("profit_take:band:4", 200)


def test_strategy12_reduce_expands_star_odd_remainder_and_releases_anchor():
    def sell(profile):
        state = _shared_state(profile)
        code = "688001.SH"
        state.positions[code] = [Position(code, 300, 10.0, 0, 10.0)]
        filled = strategy12_engine.fill_exit(
            state,
            code,
            11.0,
            "20261006",
            day_i=1,
            ds="20261006",
            plan=(strategy12_rules.REDUCE, 200),
            limits=(12.0, 8.0),
            open_px=11.0,
        )
        return state, filled

    legacy, legacy_filled = sell(PRE_P10)
    industry, industry_filled = sell(INDUSTRY)
    assert legacy_filled == 200
    assert legacy.positions["688001.SH"][0].shares == 100
    assert industry_filled == 300
    assert "688001.SH" not in industry.positions


def test_v7_kind_exit_includes_sellable_odd_remainder_in_same_order():
    def sell(profile):
        state = SimResult(0.0)
        state.rule_profile = profile
        bind_account_fee_schedule(state, INDUSTRY_ACCOUNT_FEES)
        position = V7Position("688001.SH", 10.0)
        position.lots = [
            V7Lot(200, date(2026, 10, 5), 10.0, "trial"),
            V7Lot(100, date(2026, 10, 5), 10.0, "add"),
        ]
        position.avg_cost = 10.0
        state.positions[position.symbol] = position
        filled = _sell_lots(
            state,
            position,
            date(2026, 10, 6),
            600,
            11.0,
            "exit:trial",
            kind="trial",
            fee=INDUSTRY_ACCOUNT_FEES,
        )
        return state, filled

    legacy, legacy_filled = sell(PRE_P10)
    industry, industry_filled = sell(INDUSTRY)
    assert legacy_filled == 200
    assert legacy.positions["688001.SH"].shares == 100
    assert industry_filled == 300
    assert "688001.SH" not in industry.positions
