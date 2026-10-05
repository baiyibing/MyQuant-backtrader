"""Exact arithmetic comparisons against pre-B8 literals and frozen sizing."""
import math
import struct

from backtest.research.csv_ledger import _buy_size
from backtest.research.lot_rounding import (
    BOARD_LOT, STAR_MIN_DECLARE, budget_board_lots, budget_integer_shares,
    nonnegative_override_board_lots, supplementary_notional,
)

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
