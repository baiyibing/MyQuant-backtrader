"""Pure, explicit arithmetic profiles for shared CSV buy sizing."""

BOARD_LOT = 100
STAR_MIN_DECLARE = 200


def budget_board_lots(per: float, price: float) -> int:
    """Reproduce int(per / price / 100.0) * 100 for ledger and pool order_budget.

    Divide by price, then by the float lot size, then truncate; no top-up.
    Fullstrat tentative sizing uses this through ledger._buy_size.
    """
    return int(per / price / 100.0) * 100


def budget_integer_shares(per: float, price: float) -> int:
    """Reproduce int(per / price) for ledger._buy_size's STAR branch."""
    return int(per / price)


def nonnegative_override_board_lots(shares: int) -> int:
    """Reproduce max(0, int(shares)) // 100 * 100 for ledger.execute_buy.

    The caller retains Integral/bool validation before this arithmetic.
    """
    return max(0, int(shares)) // 100 * 100


def supplementary_notional(notional: float, per: float) -> float:
    """Reproduce max(0.0, notional - per) for ledger top-up and post-capacity sizing."""
    return max(0.0, notional - per)
