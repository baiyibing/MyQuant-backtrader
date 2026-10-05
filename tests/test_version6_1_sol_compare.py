# -*- coding: utf-8 -*-
"""Lock version6 vs version6_1 parametric diffs for the 6.1 sol note.

Docs-faithful constants only — no NAV, no writer bytes, no lake.
See docs/backtest/note-version6_1-sol-vs-version6-2026-10-02.md.
"""

from __future__ import annotations

import pytest

from backtest.research import strategy6_1_rules as v61
from backtest.research import strategy6_rules as v6
from backtest.research.csv_strategy_books import get_book


def test_v6_vs_v61_stop_and_sizing_differ():
    b6 = get_book("version6")
    b61 = get_book("version6_1")
    assert b6.tag == "v6"
    assert b61.tag == "v6_1"
    assert getattr(b6, "sizing", "daily_quota") in (None, "daily_quota")
    assert b61.sizing == "per_name"
    assert b61.name_budget == pytest.approx(1_000_000.0)
    assert v6.STOP_PCT == pytest.approx(0.02)
    assert v61.STOP_PCT == pytest.approx(0.05)
    assert v6.TP_MIN_DAYS == v61.TP_MIN_DAYS == 1
    assert v6.PEAK_GAP_MIN == v61.PEAK_GAP_MIN == 15


def test_v6_two_band_vs_v61_unbounded_ladder():
    # v6: px below cost never take-profits.
    assert v6.take_profit_reason(9.50, 10.0, 10.50, 1) is None
    # v61 Q2: below-cost exit allowed on ladder line.
    assert v61.take_profit_reason(9.50, 10.0, 10.05, 1) == "trail:ladder:0"
    # v6 two-band reason codes.
    assert v6.take_profit_reason(10.15, 10.0, 10.50, 1) == "trail:band:lt6"
    assert v6.take_profit_reason(10.30, 10.0, 10.60, 1) == "trail:band:ge6"
    # v61 unbounded high band (A=100% → band 20).
    assert v61.give_band(20.0, 10.0) == 20
    assert v61.take_profit_reason(15.49, 10.0, 20.0, 1) == "trail:ladder:100"


def test_v61_aliases_and_book_registration():
    assert get_book("6.1").name == "version6_1"
    assert get_book("v6.1").name == "version6_1"
    assert get_book("version6_1").help_lock == v61.HELP_LOCK
