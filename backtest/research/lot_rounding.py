"""Pure, explicit arithmetic profiles for research order quantities."""

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


def floor_board_lots(shares: int) -> int:
    """Reproduce shares // 100 * 100 for minute_cash_order.scale_out_exits chunks.

    ashare_volume_cap.VolumeCap.clamp keeps its own literal: that file is a frozen
    core pinned by tests/test_minute_orders_cli_lake.py (KNIFE_BASE)."""
    return shares // 100 * 100


def floordiv_board_lots(shares) -> int:
    """Reproduce int(shares // 100) * 100 for strategy12_rules.scale_memory (scaled // 100)."""
    return int(shares // 100) * 100


def scale_out_board_lots(shares_now: int, scale_frac) -> int:
    """Reproduce int(shares_now * float(scale_frac) // 100) * 100 for minute_cash_order.scale_out_exits."""
    return int(shares_now * float(scale_frac) // 100) * 100


def risk_unit_board_lots(budget: float, risk_frac: float, value: float) -> int:
    """Reproduce int((NAME_BUDGET * UNIT_RISK_FRAC / value) // 100) * 100 for strategy9_1_rules.unit_shares."""
    return int((budget * risk_frac / value) // 100) * 100


def rounded_partial_board_lots(shares: int, fraction: float) -> int:
    """Reproduce int(round(shares * fraction, 8)) // 100 * 100 for strategy9_2_engine.plan_exit partial sells."""
    return int(round(shares * fraction, 8)) // 100 * 100


def native_budget_board_lots(target: float, price: float) -> int:
    """Reproduce int(target / price / 100) * 100 for strategy7_engine._buy.

    fullstrat_research_v7 supplies target=v7.NAME_BUDGET * fraction,
    preserving int(v7.NAME_BUDGET * fraction / px / 100) * 100.
    """
    return int(target / price / 100) * 100


def double_floordiv_budget_board_lots(notional: float, buy_price: float) -> int:
    """Reproduce int(LOT_NOTIONAL // buy_price // 100) * 100 for unified_exit_modea._lot_shares."""
    return int(notional // buy_price // 100) * 100


def tail_capacity_board_lots(shares) -> int:
    """Reproduce int(shares) // 10 // 100 * 100 for tail_window_buy.tail_quote."""
    return int(shares) // 10 // 100 * 100


def tail_slice_board_lots(target: int, minute_count: int) -> int:
    """Reproduce target // len(TAIL_MINUTES) // 100 * 100 for TailParent.from_budget."""
    return target // minute_count // 100 * 100


def tail_budget_board_lots(budget: float, price: float) -> int:
    """Reproduce int(Decimal(str(budget)) / Decimal(str(price)) / 100) * 100 for TailParent.from_budget."""
    from decimal import Decimal

    return int(Decimal(str(budget)) / Decimal(str(price)) / 100) * 100
