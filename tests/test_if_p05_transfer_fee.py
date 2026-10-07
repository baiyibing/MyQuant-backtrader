from datetime import UTC, date, datetime

import pytest
from backtest.research.ashare_fees import INDUSTRY_ACCOUNT_FEES
from backtest.research.ledger_math import (
    TRANSFER_FEE_RATE_BSE_BEFORE_CUTOVER,
    TRANSFER_FEE_RATE_FROM_CUTOVER,
    TRANSFER_FEE_RATE_SH_SZ_BEFORE_CUTOVER,
    TransferFeeAccumulator,
    bilateral_transfer_fee,
    transfer_fee_rate,
)
from backtest.research.market_layer import transfer_fee_market
from backtest.research.rule_profile import RuleProfile
from scripts.research.generate_off_byte_baseline import P05_CASES, run_p05_case

P05_COMPONENT_PROFILE = RuleProfile(
    name="industry",
    revision="industry-p05-transfer-fee-20261006",
    account_fee_schedule=True,
)


@pytest.mark.parametrize(
    "symbol,expected",
    [
        ("600000.SH", "SH_SZ"),
        ("000001.SZ", "SH_SZ"),
        ("688001.SH", "SH_SZ"),
        ("920014.BJ", "BSE"),
        ("430001.BJ", "BSE"),
    ],
)
def test_transfer_fee_market_uses_market_layer_board_table(symbol, expected):
    assert transfer_fee_market(symbol) == expected


@pytest.mark.parametrize(
    "market,trade_date,expected",
    [
        ("SH_SZ", "20220428", TRANSFER_FEE_RATE_SH_SZ_BEFORE_CUTOVER),
        ("SH_SZ", date(2022, 4, 29), TRANSFER_FEE_RATE_FROM_CUTOVER),
        ("BSE", datetime(2022, 4, 28, 15, 0, tzinfo=UTC),
         TRANSFER_FEE_RATE_BSE_BEFORE_CUTOVER),
        ("BSE", "2022-04-29", TRANSFER_FEE_RATE_FROM_CUTOVER),
    ],
)
def test_transfer_fee_rate_boundary_dates(market, trade_date, expected):
    assert transfer_fee_rate(market, trade_date) == expected


def test_transfer_fee_is_bilateral_by_notional_with_no_minimum():
    assert bilateral_transfer_fee(1_000.0, "SH_SZ", "2022-04-28") == 0.02
    assert bilateral_transfer_fee(1_000.0, "BSE", "2022-04-28") == 0.025
    assert bilateral_transfer_fee(1.0, "SH_SZ", "2022-04-29") == 0.00001

    accumulator = TransferFeeAccumulator()
    first = accumulator.add_fill("order", 1_000.0, "BSE", "2022-04-28")
    second = accumulator.add_fill("order", 2_000.0, "BSE", "2022-04-29")
    assert first.allocations == (0.025,)
    assert second.allocations == (0.025, 0.02)
    assert second.total_fee == 0.045


def test_industry_schedule_debits_transfer_fee_on_both_sides():
    assert INDUSTRY_ACCOUNT_FEES.debit_buy(
        1_000.0, "2022-04-28", "600000.SH"
    ) == 1005.02
    assert INDUSTRY_ACCOUNT_FEES.credit_sell(
        1_000.0, "2022-04-29", "000001.SZ"
    ) == 993.99


@pytest.mark.parametrize(
    "book,engine",
    P05_CASES,
    ids=[f"{book}-{engine}" for book, engine in P05_CASES],
)
def test_industry_transfer_fee_components_cover_shared_and_native_paths(book, engine):
    state = run_p05_case(book, engine, rule_profile=P05_COMPONENT_PROFILE)
    fills = [row for row in state.trades if str(row["side"]).upper() in {"BUY", "SELL"}]

    assert any(str(row["side"]).upper() == "BUY" for row in fills)
    assert any(str(row["side"]).upper() == "SELL" for row in fills)
    for row in fills:
        symbol = row.get("code", row.get("symbol"))
        assert row["transfer_fee"] == bilateral_transfer_fee(
            row["notional"], transfer_fee_market(symbol), row["date"]
        )
    assert state.stats["transfer_fee_total"] == pytest.approx(
        sum(row["transfer_fee"] for row in fills)
    )
