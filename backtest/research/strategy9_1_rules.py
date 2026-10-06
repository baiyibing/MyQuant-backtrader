"""Classic ATR turtle sell book; first entry consumes strategy9 SCAN pools."""
from __future__ import annotations

from backtest.research.lot_rounding import risk_unit_board_lots
import numpy as np
import pandas as pd

BOOK_TAG = "v9_1"
ALLOW_ADD = True
PEAK_GAP_MIN = 0  # Absolute stops need no peak confirmation delay.
NAME_BUDGET = 1_000_000
ATR_PERIOD = 20
UNIT_RISK_FRAC = 0.01
MAX_UNITS = 4
HELP_LOCK = """
version9_1 / v9_1: export_strategy9_pool.py SCAN only (vol-ratio=2,
top-lead=40, drop=40%, turnover off unless --turnover-check); explicit pool required.
NAME_BUDGET = 1_000_000; ATR_PERIOD = 20; UNIT_RISK_FRAC = 0.01.
Unit risk = 10_000 yuan; shares = floor_to_lot(10_000 / ATR(20)).
True range = max(high-low, abs(high-prev_close), abs(low-prev_close)).
ATR = simple mean of prior 20 true ranges, excluding decision day;
freeze ATR and unit shares at first fill for the life of the position.
First unit on SCAN signal (not a breakout). Add at last_fill + 0.5 * ATR,
only mark > weighted cost; max 4 units. Skip limit-up buys; no chase.
Whole-position stop = last_fill - 2 * ATR, raised on adds;
exit also at today's low <= prior 10 daily lows minimum (excluding today).
Touch exits use gap open or trigger; minute lows always participate.
T+1 residuals defer; limit-down sells defer. Short ATR history skips/counts buys.
Chronological --fix-minute-cash-order is unsupported (fail closed).
No profit target or range stop; --stop-pct refused; peak_gap_min=0.
Output: csv_{daily|minute}_v9_1_{start}_{end}/.
"""

def atr(frame, day):
    prior = frame.loc[frame.index < pd.Timestamp(day)].tail(ATR_PERIOD + 1)
    if len(prior) < ATR_PERIOD + 1 or not {"high", "low", "close"}.issubset(prior):
        return None
    h = prior.high.to_numpy(float)[1:]
    l = prior.low.to_numpy(float)[1:]
    c = prior.close.to_numpy(float)[:-1]
    if not np.isfinite(np.concatenate([h,l,c])).all() or (h < l).any():
        return None
    value = float(np.maximum.reduce([h-l, abs(h-c), abs(l-c)]).mean())
    return value if value > 0 else None

def unit_shares(value):
    return risk_unit_board_lots(NAME_BUDGET, UNIT_RISK_FRAC, value)

def may_add(lots, px, value, units):
    cost = sum(p.cost*p.shares for p in lots)/sum(p.shares for p in lots)
    return units < MAX_UNITS and px > cost and px >= lots[-1].cost + 0.5*value

def stop_line(last_fill, value):
    return last_fill - 2*value

def low_line(frame, day):
    prior = frame.loc[frame.index < pd.Timestamp(day)].tail(10)
    if len(prior) < 10:
        return None
    lows = prior.low.to_numpy(float)
    return float(lows.min()) if np.isfinite(lows).all() else None

def record_strategy9_1_params(st):
    st.stats.update(sell_book=BOOK_TAG, stop_pct=None, stop_mode="atr_frozen_last_fill",
                    name_budget=NAME_BUDGET, atr_period=ATR_PERIOD,
                    unit_risk_frac=UNIT_RISK_FRAC, unit_risk=10_000,
                    max_units=MAX_UNITS, add_atr=0.5, stop_atr=2, exit_low_bars=10)

def bind(st, frames):
    memory = {}
    def prepare(code, px, day):
        lots = st.positions.get(code, [])
        if not lots:
            memory.pop(code, None)
        mem = memory.get(code)
        if mem is None or mem["units"] == 0:
            value = atr(frames[code], day)
            if value is None:
                st.stats["skip_atr_history"] = st.stats.get("skip_atr_history", 0) + 1
                return None
            mem = dict(atr=value, shares=unit_shares(value), units=0, last_fill=None)
            memory[code] = mem
        if any(p.pending_exit for p in lots):
            return None
        if lots and not may_add(lots, px, mem["atr"], mem["units"]):
            return None
        return mem["shares"]
    def bought(state, code, reason, shares):
        mem = memory[code]
        mem["units"] += 1
        mem["last_fill"] = state.positions[code][-1].cost
    def line(code, day):
        mem = memory.get(code)
        if not mem or mem["last_fill"] is None:
            return None
        stop = stop_line(mem["last_fill"], mem["atr"])
        low = low_line(frames[code], day)
        return max(stop, low) if low is not None else stop
    st.book_on_buy = bought
    st.book_state["prepare_unit"] = prepare
    return line
