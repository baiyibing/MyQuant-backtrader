"""Naming leaf for existing research paths; no scheduling or execution policy.

SessionPhase / session_phase label the current scan window, not faithful
exchange closing-call matching or fill eligibility. FillPriceRule contains
non-exhaustive book-engine names and excludes v7; POOL_FILE_DAY_RULE names the
existing file-day convention, not evidence of signal availability.

This module owns no hl scan/fill loop, X-02 cash ordering, TopK buy dispatch,
JR Mode B replay, v7 timers, or NAV marking. Those remain with their existing
engines and callers. The fixed hot-path import fence permits csv_ledger to
import this leaf only for write-site labels; scanners gain no import or filter.

S2-E (Human GO "继续S2-E", 2026-09-28) freezes this naming boundary only.
See docs/backtest/minute-fill-policy-ssot.md section 4 and
docs/backtest/s2e-ashare-fill-clock-boundary-2026-09-28.md. Historical P1=A,
P2=B label wiring and P4=A touch/mark separation keep their existing scope.
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
