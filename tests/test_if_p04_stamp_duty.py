from datetime import UTC, date, datetime

import pytest
from backtest.research.ashare_fees import INDUSTRY_ACCOUNT_FEES
from backtest.research.ledger_math import (
    STAMP_DUTY_RATE_BEFORE_CUTOVER,
    STAMP_DUTY_RATE_FROM_CUTOVER,
    StampDutyAccumulator,
    sell_stamp_duty,
    stamp_duty_rate,
)
from backtest.research.rule_profile import RuleProfile
from scripts.research.generate_off_byte_baseline import P04_CASES, run_p04_case

P04_COMPONENT_PROFILE = RuleProfile(
    name="industry",
    revision="industry-p04-stamp-duty-20261006",
    account_fee_schedule=True,
)


@pytest.mark.parametrize(
    "trade_date,expected",
    [
        ("20230827", STAMP_DUTY_RATE_BEFORE_CUTOVER),
        (date(2023, 8, 28), STAMP_DUTY_RATE_FROM_CUTOVER),
        (datetime(2023, 8, 29, 9, 30, tzinfo=UTC), STAMP_DUTY_RATE_FROM_CUTOVER),
    ],
)
def test_stamp_duty_rate_boundary_dates(trade_date, expected):
    assert stamp_duty_rate(trade_date) == expected


def test_stamp_duty_is_sell_notional_only_and_keeps_order_identity():
    accumulator = StampDutyAccumulator()
    before = accumulator.add_fill("continued-order", 1_000.0, "2023-08-25")
    after = accumulator.add_fill("continued-order", 2_000.0, "2023-08-28")

    assert sell_stamp_duty(1_000.0, "2023-08-25") == 1.0
    assert sell_stamp_duty(2_000.0, "2023-08-28") == 1.0
    assert before.allocations == (1.0,)
    assert after.allocations == (1.0, 1.0)
    assert after.total_fee == 2.0


def test_industry_schedule_requires_a_date_for_direct_sell_credit():
    with pytest.raises(ValueError, match="requires trade_date"):
        INDUSTRY_ACCOUNT_FEES.credit_sell(1_000.0)
    assert INDUSTRY_ACCOUNT_FEES.credit_sell(
        1_000.0, "2023-08-27", "600000.SH"
    ) == 993.99
    assert INDUSTRY_ACCOUNT_FEES.credit_sell(
        1_000.0, "2023-08-28", "600000.SH"
    ) == 994.49


@pytest.mark.parametrize(
    "book,engine",
    P04_CASES,
    ids=[f"{book}-{engine}" for book, engine in P04_CASES],
)
def test_industry_stamp_duty_components_cover_shared_and_native_paths(book, engine):
    state = run_p04_case(book, engine, rule_profile=P04_COMPONENT_PROFILE)
    fills = [row for row in state.trades if str(row["side"]).upper() in {"BUY", "SELL"}]
    buys = [row for row in fills if str(row["side"]).upper() == "BUY"]
    sells = [row for row in fills if str(row["side"]).upper() == "SELL"]

    assert buys and sells
    assert all(row["stamp_duty"] == 0.0 for row in buys)
    expected_rate = (
        STAMP_DUTY_RATE_BEFORE_CUTOVER if "pre-cutover" in engine else STAMP_DUTY_RATE_FROM_CUTOVER
    )
    assert sum(row["stamp_duty"] for row in sells) == pytest.approx(
        sum(row["notional"] for row in sells) * expected_rate
    )
    assert state.stats["stamp_duty_total"] == pytest.approx(sum(row["stamp_duty"] for row in sells))


def test_s8_group_stamp_duty_is_allocated_across_one_sell_order():
    state = run_p04_case("version8", "s8-group-post-cutover", rule_profile="industry")
    sells = [row for row in state.trades if row["side"] == "SELL"]
    assert [row["commission"] for row in sells] == [2.5, 2.5]
    assert [row["stamp_duty"] for row in sells] == [0.5, 0.5]
    assert sum(row["stamp_duty"] for row in sells) == 1.0
