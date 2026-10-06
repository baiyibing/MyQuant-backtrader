"""Common minute entry checks, staged to preserve caller error precedence."""
from backtest.research.csv_strategy_books import normalize_csv_strategy, validate_hold_days


def validate_minute_entry(strategy, *, stage, version9_sell=None, max_hold=False,
                          hold_days=20,
                          tail_window_buy=False, fix_minute_cash_order=False,
                          fix_s11_exit_domain=False):
    book = normalize_csv_strategy(strategy)
    if stage == "sell":
        from backtest.research.strategy9_rules import validate_sell_mode
        validate_sell_mode(book, version9_sell, max_hold)
        if max_hold and book != "version9":
            raise ValueError("max_hold is supported only by version9")
        validate_hold_days(book, hold_days)
    elif stage == "tail":
        if tail_window_buy and book not in {
            "version8", "version8_1", "version8_2", "version8_3",
            "version8_4", "version8_5", "version8_6",
        }:
            raise ValueError("--tail-window-buy applies only to version8 / version8.x in the shared entry")
    elif stage == "cash":
        if fix_minute_cash_order and book in {"version9_1", "version9_3"}:
            raise ValueError(f"--fix-minute-cash-order is not applicable to {book}")
    elif stage == "s11":
        if fix_s11_exit_domain and book != "version11":
            raise ValueError("fix_s11_exit_domain is supported only by version11")
    else:
        raise ValueError(f"unsupported validation stage: {stage}")
