# -*- coding: utf-8 -*-
"""策略 6 卖点纯函数（名单加仓 + T+1 起评止盈 + 两档回撤）。"""

from __future__ import annotations

import pytest

from backtest.research.strategy6_rules import (
    ALLOW_ADD,
    BAND_SPLIT,
    DD_GE6,
    DD_LT6,
    STOP_PCT,
    TP_MIN_DAYS,
    take_profit_reason,
    trail_hits,
)

COST = 10.0


def test_book_constants():
    assert ALLOW_ADD is True
    assert STOP_PCT == pytest.approx(0.02)
    assert TP_MIN_DAYS == 1
    assert BAND_SPLIT == pytest.approx(0.06)
    assert DD_LT6 == pytest.approx(0.70)
    assert DD_GE6 == pytest.approx(0.50)


def test_t0_blocks_trail():
    assert take_profit_reason(10.15, COST, 10.50, 0) is None
    assert take_profit_reason(10.30, COST, 10.60, 0) is None


def test_lt6_keep30_from_t1():
    assert take_profit_reason(10.15, COST, 10.50, 1) == "trail:band:lt6"
    assert take_profit_reason(10.151, COST, 10.50, 1) is None


def test_ge6_keep50_from_t1():
    assert take_profit_reason(10.30, COST, 10.60, 1) == "trail:band:ge6"
    assert take_profit_reason(10.31, COST, 10.60, 1) is None


def test_below_cost_no_trail():
    assert take_profit_reason(9.95, COST, 10.50, 2) is None


def test_legacy_trail_hits_unchanged():
    assert not trail_hits(9.95, 10.0, 10.50, 0.01, 0.30)
    assert trail_hits(10.218, 10.0, 10.50, 0.01, 0.30)
    assert not trail_hits(10.222, 10.0, 10.50, 0.01, 0.30)


def test_summarize_v6_dd_bands():
    from backtest.research.csv_artifacts import summarize
    from backtest.research.csv_ledger import SimState
    from backtest.research.strategy6_rules import record_strategy6_params

    st = SimState()
    record_strategy6_params(st, stop_pct=0.02)
    st.equity_curve = [("20251103", 21_000_000.0)]
    text = summarize(st, 21_000_000.0, "20251103", "20251103", engine="csv_daily_v6")
    assert "T+1起评止盈" in text
    assert "<6%回撤70%" in text
    assert "≥6%回撤50%" in text
    assert "加仓名单再现" in text
    assert "锚 1%" not in text
