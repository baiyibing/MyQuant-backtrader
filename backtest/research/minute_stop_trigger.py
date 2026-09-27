"""Opt-in minute H/L predicates; daily books and close scans stay unchanged."""

from backtest.research.csv_ledger import hit_limit_down


def validate_minute_stop_trigger(mode, strategy=None, fix_s11_exit_domain=False):
    if mode not in {"close", "hl"}:
        raise ValueError("--minute-stop-trigger must be hl or close")
    if mode == "hl" and (strategy == "version12" or fix_s11_exit_domain):
        raise ValueError("--minute-stop-trigger hl rejects version12 and --fix-s11-exit-domain")


def validate_low(mode, low, closes):
    validate_minute_stop_trigger(mode)
    if mode == "hl" and (low is None or len(low) != len(closes)):
        raise ValueError("--minute-stop-trigger hl requires aligned minute low prices")


def blocked_bar(mode, opening, high, limit_down):
    # Keep the existing opening-limit guard. In hl mode explicitly reject
    # floor-locked bars before evaluating either threshold.
    return limit_down > 0 and (
        hit_limit_down(opening, limit_down)
        or (mode == "hl" and hit_limit_down(high, limit_down))
    )


def target_fill(opening, high, cost, peak, n_days, target_pct, take_profit):
    """Fixed upward targets only; drawdown/MA callbacks retain their semantics."""
    if target_pct is None or target_pct <= 0 or take_profit is None:
        return None
    target = cost * (1.0 + target_pct)
    if high >= target:
        reason = take_profit(target, cost, peak, n_days)
        if reason:
            return max(opening, target), reason
    return None
