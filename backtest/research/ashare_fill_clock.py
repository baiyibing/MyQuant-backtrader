"""Names for existing research paths; no scheduling or execution policy.

Session phases label the current scan window, not faithful exchange closing-call
matching. Price rules are non-exhaustive book-engine names and exclude v7.
"""

from enum import Enum

from backtest.research.ashare_bars import AM_OPEN, AM_CLOSE, PM_OPEN, PM_CLOSE


CLOSING_CALL_OPEN = 14 * 60 + 57
POOL_FILE_DAY_RULE = "filename_day_is_decision_and_buy_day"


class SessionPhase(str, Enum):
    continuous = "continuous"
    closing_call = "closing_call"


def session_phase(hm: int) -> SessionPhase:
    """Label an accepted session minute; reject minutes outside the scan window."""
    if AM_OPEN <= hm <= AM_CLOSE or PM_OPEN <= hm < CLOSING_CALL_OPEN:
        return SessionPhase.continuous
    if CLOSING_CALL_OPEN <= hm <= PM_CLOSE:
        return SessionPhase.closing_call
    raise ValueError(f"Minute outside the current scan window: {hm}")


class FillPriceRule(str, Enum):
    daily_open_board_same_close = "daily_open_board_same_close"
    daily_stop_gap_open = "daily_stop_gap_open"
    daily_stop_touch_at_trigger = "daily_stop_touch_at_trigger"
    daily_stop_close = "daily_stop_close"
    daily_pending_next_open = "daily_pending_next_open"
    minute_gap_open = "minute_gap_open"
    minute_trigger_bar_close = "minute_trigger_bar_close"
