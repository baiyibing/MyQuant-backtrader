# -*- coding: utf-8 -*-
"""6.64：底仓 −5% / 档位 −10% 止损按入场 ATR14% 反向缩放（锚 3.8%）。"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from backtest.research.csv_minute_backtest import _atr_group_stops
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.strategy6_64_rules import (
    ATR_CLAMP_HARD,
    ATR_CLAMP_STEP,
    atr_inverse_threshold,
)

BUDGET = 10_000.0


def test_hooks_wire_atr_stop():
    hooks = apply_csv_strategy("version6_64")
    assert hooks["atr_stop_anchor"] == pytest.approx(0.038)
    assert hooks["atr_stop_window"] == 14
    assert hooks["atr_clamp_hard"] == (0.0333, 0.0833)
    assert hooks["atr_clamp_step"] == (0.07, 0.16)
    assert hooks["stop_pct"] == pytest.approx(0.05)
    assert hooks["step_stop_pct"] == pytest.approx(0.10)
    assert hooks["index_cut2_blocked_day"] is None  # 单段闸门
    sibling = apply_csv_strategy("version6_55")
    assert sibling.get("atr_stop_anchor") is None


def test_inverse_threshold_math():
    # 中位票（ATR=锚）：等同固定值
    assert atr_inverse_threshold(0.10, 0.038, clamp=ATR_CLAMP_STEP) == pytest.approx(0.10)
    # 高波动（ATR=7.6%）：收紧到下半钳
    assert atr_inverse_threshold(0.10, 0.076, clamp=ATR_CLAMP_STEP) == pytest.approx(0.07)
    # 低波动（ATR=2%）：放宽但不越上钳
    assert atr_inverse_threshold(0.10, 0.02, clamp=ATR_CLAMP_STEP) == pytest.approx(0.16)
    # 底仓档
    assert atr_inverse_threshold(0.05, 0.038, clamp=ATR_CLAMP_HARD) == pytest.approx(0.05)
    assert atr_inverse_threshold(0.05, 0.076, clamp=ATR_CLAMP_HARD) == pytest.approx(0.0333)
    assert atr_inverse_threshold(0.05, 0.02, clamp=ATR_CLAMP_HARD) == pytest.approx(0.0833)
    # 无 ATR 回退固定值
    assert atr_inverse_threshold(0.10, 0.0, clamp=ATR_CLAMP_STEP) == pytest.approx(0.10)


def _frame(atr_pct: float, days: int = 30) -> pd.DataFrame:
    idx = pd.date_range("2025-10-01", periods=days, freq="D")
    close = np.full(days, 100.0)
    rng = atr_pct * close[0]
    high = close + rng
    low = close - rng
    # TR ≈ max(high-low, |high-prev_close|, |low-prev_close|) = 2*rng
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close}, index=idx)


class _Group:
    entry_signal_date = "20251015"


class _Pos:
    position_id = "600000.SH@20251015"
    group = _Group()


def _hooks():
    return apply_csv_strategy("version6_64", name_budget=BUDGET)


def _st():
    class S:
        book_state = {}
        stats = {}
    return S()


def test_group_stops_scale_and_lock():
    st = _st()
    hooks = _hooks()
    frame = _frame(0.038)  # ATR14%≈7.6%（TR=2×3.8）→ ratio=0.5 → 双双收紧
    entry_day = dt.date(2025, 10, 15)
    stop, step, atr = _atr_group_stops(st, hooks, frame, _Pos(), 0.05, 0.10, entry_day)
    assert atr == pytest.approx(0.076, abs=1e-3)
    assert stop == pytest.approx(0.0333, abs=1e-4)  # 0.05×0.5 → 下钳
    assert step == pytest.approx(0.07, abs=1e-4)    # 0.10×0.5 → 下钳
    assert st.stats["atr_stop_groups"] == 1
    # 锁定：第二次调用不重算（换 frame 也不变）
    stop2, step2, _ = _atr_group_stops(st, hooks, _frame(0.02), _Pos(), 0.05, 0.10, entry_day)
    assert (stop2, step2) == (stop, step)
    assert st.stats["atr_stop_groups"] == 1


def test_group_stops_fixed_fallback_when_warmup():
    st = _st()
    hooks = _hooks()
    short = _frame(0.038, days=10)  # 不足 15 日
    stop, step, atr = _atr_group_stops(st, hooks, short, _Pos(), 0.05, 0.10, dt.date(2025, 10, 15))
    assert (stop, step, atr) == (0.05, 0.10, None)
    assert st.stats["atr_stop_fixed_fallback"] == 1
    # frame=None 同样回退
    st2 = _st()
    stop, step, _ = _atr_group_stops(st2, hooks, None, _Pos(), 0.05, 0.10, dt.date(2025, 10, 15))
    assert (stop, step) == (0.05, 0.10)
    assert st2.stats["atr_stop_fixed_fallback"] == 1


def test_sibling_books_do_not_scale():
    for book in ("version6_55", "version6_63", "version6_65"):
        assert apply_csv_strategy(book).get("atr_stop_anchor") is None
