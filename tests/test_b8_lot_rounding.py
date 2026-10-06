"""Exact arithmetic comparisons against pre-B8 literals and frozen sizing."""
import math
import struct

import pandas as pd
from backtest.research.ashare_fees import INDUSTRY_ACCOUNT_FEES
from backtest.research.csv_ledger import (
    SimState,
    _buy_size,
    bind_account_fee_schedule,
    execute_buy,
)
from backtest.research.lot_rounding import (
    BOARD_LOT,
    STAR_MIN_DECLARE,
    budget_board_lots,
    budget_integer_shares,
    nonnegative_override_board_lots,
    supplementary_notional,
)
from backtest.research.tail_window_buy import fee_aware_buy_quantity


def frozen_buy_size(per_quota: float, price: float, *, star_declare: bool = False) -> tuple[int, float]:
    """默认整百且可补足 100 股；STAR opt-in 按整数股、不补足，由入口校验。"""
    if price <= 0 or per_quota <= 0:
        return 0, 0.0
    if star_declare:
        # D23 X-10: integer shares, min 200 checked at entry; no top-up.
        return int(per_quota / price), 0.0
    shares = int(per_quota / price / 100.0) * 100
    supp = 0.0
    if shares == 0:
        notional = 100 * price
        supp = max(0.0, notional - per_quota)
        shares = 100
    return shares, supp


PRICES = [0.01, 0.03, 0.07, 0.1, 0.29, 1.1, 9.99, 33.33, 1999.99, 2000.0]
PRICES += [i / 37 for i in range(1, 74001, 37)]
SHARES = [-201, -200, -199, -100, -99, -1, 0, 1, 99, 100, 199, 200, 201]


def budget_cases():
    for px in PRICES:
        for per in [-1e6, -1.0, 0.0, 0.01, 99.0, 100.0, 199.0, 200.0, 201.0, 1e6]:
            yield per, px
        for shares in SHARES:
            boundary = shares * px
            for per in [math.nextafter(boundary, -math.inf), boundary,
                        math.nextafter(boundary, math.inf)]:
                yield per, px


def test_budget_board_lots_exact_literal():
    for per, px in budget_cases():
        assert budget_board_lots(per, px) == int(per / px / 100.0) * 100
        assert budget_board_lots(per, px) == int(per / px / 100.) * 100
    # True division and floor division differ even for familiar decimals.
    assert 1 // 0.1 == 9.0
    assert budget_integer_shares(1, 0.1) == 10


def test_budget_integer_shares_exact_literal():
    for per, px in budget_cases():
        assert budget_integer_shares(per, px) == int(per / px)


def test_nonnegative_override_board_lots_exact_literal():
    for shares in list(range(-20001, 20002)) + [10**18 - 1, 10**18, 10**18 + 1]:
        assert nonnegative_override_board_lots(shares) == max(0, int(shares)) // 100 * 100


def test_supplementary_notional_exact_literal():
    for per, px in budget_cases():
        for notional in [100 * px, per, math.nextafter(per, math.inf)]:
            expected = max(0.0, notional - per)
            actual = supplementary_notional(notional, per)
            assert actual == expected
            assert struct.pack('!d', actual) == struct.pack('!d', expected)


def test_buy_size_frozen_body():
    assert BOARD_LOT == 100
    assert STAR_MIN_DECLARE == 200
    for per, px in budget_cases():
        for star in [False, True]:
            actual = _buy_size(per, px, star_declare=star)
            expected = frozen_buy_size(per, px, star_declare=star)
            assert actual == expected
            assert struct.pack('!d', actual[1]) == struct.pack('!d', expected[1])
    for px in [-2000.0, -0.1, 0.0]:
        for per in [-1e6, 0.0, 1e6]:
            for star in [False, True]:
                assert _buy_size(per, px, star_declare=star) == frozen_buy_size(per, px, star_declare=star)


def test_industry_b8_03_skips_budget_below_one_lot_without_touching_legacy():
    from backtest.research.rule_profile import INDUSTRY

    assert _buy_size(999.0, 10.0) == (100, 1.0)
    assert _buy_size(999.0, 10.0, top_up_min_lot=False) == (0, 0.0)

    state = SimState(cash=10_000.0)
    state.rule_profile = INDUSTRY
    assert not execute_buy(
        state, "600000.SH", 10.0, 999.0, 0, pd.Timestamp("2026-10-06")
    )
    assert state.positions == {}
    assert state.trades == []
    assert state.stats["skip_min_lot_budget"] == 1
    assert state.stats["supplementary_used"] == 0.0


def test_industry_b8_04_sizes_one_lot_down_for_all_buy_fees():
    from backtest.research.rule_profile import INDUSTRY

    debit = lambda notional: INDUSTRY_ACCOUNT_FEES.debit_buy(
        notional, pd.Timestamp("2026-10-06"), "600000.SH"
    )
    assert fee_aware_buy_quantity(200, 10.0, 2000.0, 10_000.0, debit) == 100
    assert fee_aware_buy_quantity(
        250,
        10.0,
        2500.0,
        10_000.0,
        debit,
        increment=1,
        minimum=STAR_MIN_DECLARE,
    ) == 249
    assert debit(2000.0) > 2000.0
    assert debit(1000.0) <= 2000.0

    legacy = SimState(cash=10_000.0)
    assert execute_buy(
        legacy, "600000.SH", 10.0, 2000.0, 0, pd.Timestamp("2026-10-06")
    )
    assert legacy.trades[-1]["shares"] == 200

    industry = SimState(cash=10_000.0)
    industry.rule_profile = INDUSTRY
    bind_account_fee_schedule(industry, INDUSTRY_ACCOUNT_FEES)
    assert execute_buy(
        industry, "600000.SH", 10.0, 2000.0, 0, pd.Timestamp("2026-10-06")
    )
    assert industry.trades[-1]["shares"] == 100
    assert (
        industry.trades[-1]["notional"]
        + industry.trades[-1]["commission"]
        + industry.trades[-1]["transfer_fee"]
        <= 2000.0
    )


def test_industry_b8_06_helper_limits_quantity_by_available_cash():
    debit = lambda notional: INDUSTRY_ACCOUNT_FEES.debit_buy(
        notional, pd.Timestamp("2026-10-06"), "600000.SH"
    )
    assert fee_aware_buy_quantity(200, 10.0, 2000.0, 1005.01, debit) == 100
    assert fee_aware_buy_quantity(200, 10.0, 2000.0, 1005.00, debit) == 0


def test_slice2_quantity_profiles_exact_literals():
    from decimal import Decimal

    from backtest.research import lot_rounding as lr

    values = SHARES + [299.99999999, 300.00000001, 1 / 0.1, 1e6, 10**18 + 1]
    values += [math.nextafter(x, direction) for x in [100.0, 200.0, 300.0]
               for direction in [-math.inf, math.inf]]
    for x in values:
        assert lr.floor_board_lots(x) == x // 100 * 100
        scaled = Decimal(str(x))
        assert lr.floordiv_board_lots(scaled) == int(scaled // 100) * 100
        assert lr.tail_capacity_board_lots(scaled) == int(scaled) // 10 // 100 * 100
        for count in [1, 10, 28, 100]:
            assert lr.tail_slice_board_lots(int(x), count) == int(x) // count // 100 * 100
        for fraction in [-1.0, 0.0, 0.05, 0.1, 0.3, 0.5, 1.0, 1 / 0.1]:
            assert lr.scale_out_board_lots(x, fraction) == int(x * float(fraction) // 100) * 100
            assert lr.rounded_partial_board_lots(x, fraction) == int(round(x * fraction, 8)) // 100 * 100
            for px in [0.1, 0.3, 9.99, 33.33]:
                assert lr.risk_unit_board_lots(x, fraction, px) == int((x * fraction / px) // 100) * 100
    for per, px in budget_cases():
        assert lr.native_budget_board_lots(per, px) == int(per / px / 100) * 100
        assert lr.double_floordiv_budget_board_lots(per, px) == int(per // px // 100) * 100
        assert lr.tail_budget_board_lots(per, px) == int(Decimal(str(per)) / Decimal(str(px)) / 100) * 100
    for x in [299.99999999, 299.999999995, 299.999999999, 300.000000001]:
        assert lr.rounded_partial_board_lots(x, 1.0) == int(round(x * 1.0, 8)) // 100 * 100
