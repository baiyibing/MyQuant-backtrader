from dataclasses import replace

import pandas as pd
import pytest
from backtest.research.ashare_fees import INDUSTRY_ACCOUNT_FEES
from backtest.research.csv_ledger import (
    InsufficientCashError,
    SimState,
    bind_account_fee_schedule,
    configure_s8,
    execute_buy,
)
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.rule_profile import INDUSTRY
from backtest.research.strategy7_engine import minute_hooks

DAY = pd.Timestamp("2025-11-03")
CODE = "600000.SH"


def _industry_s8_state(cash: float) -> SimState:
    state = SimState(cash=cash)
    state.rule_profile = INDUSTRY
    bind_account_fee_schedule(state, INDUSTRY_ACCOUNT_FEES)
    configure_s8(state, apply_csv_strategy("version8", name_budget=20_000.0))
    assert state.on_short_cash == "raise"
    return state


def test_industry_b8_06_shrinks_s8_buy_instead_of_raising():
    state = _industry_s8_state(15_000.0)

    assert execute_buy(state, CODE, 10.0, 20_000.0, 0, DAY)
    buy = state.trades[-1]
    assert buy["shares"] == 1400
    assert buy["notional"] + buy["commission"] + buy["transfer_fee"] <= 15_000.0
    assert state.cash >= 0


def test_industry_b8_06_skips_zero_affordable_quantity_without_raising():
    state = _industry_s8_state(1_000.0)

    assert not execute_buy(state, CODE, 10.0, 20_000.0, 0, DAY)
    assert state.trades == []
    assert state.positions == {}


def test_pre_p08_profile_still_reaches_b7_raise_mode():
    state = SimState(cash=15_000.0)
    state.rule_profile = replace(
        INDUSTRY,
        revision="industry-p07-20261006",
        shrink_on_short_cash=False,
    )
    bind_account_fee_schedule(state, INDUSTRY_ACCOUNT_FEES)
    configure_s8(state, apply_csv_strategy("version8", name_budget=20_000.0))

    with pytest.raises(InsufficientCashError):
        execute_buy(state, CODE, 10.0, 20_000.0, 0, DAY)


@pytest.mark.parametrize(
    ("book", "mode"),
    [("version8", "skip"), ("version6", "raise")],
)
def test_industry_rejects_explicit_non_default_b7_mode(book, mode):
    state = SimState()
    state.rule_profile = INDUSTRY
    hooks = apply_csv_strategy(book)
    hooks["on_short_cash"] = mode

    with pytest.raises(ValueError, match="conflicts.*explicit non-default on_short_cash"):
        configure_s8(state, hooks)


@pytest.mark.parametrize(
    ("hooks", "mode"),
    [
        (apply_csv_strategy("version8"), "raise"),
        (apply_csv_strategy("version6"), "skip"),
        (minute_hooks(), "skip"),
    ],
)
def test_industry_allows_omitted_or_explicit_default_b7_mode(hooks, mode):
    state = SimState()
    state.rule_profile = INDUSTRY
    hooks = dict(hooks)
    hooks["on_short_cash"] = mode

    configure_s8(state, hooks)
    assert state.on_short_cash == mode
