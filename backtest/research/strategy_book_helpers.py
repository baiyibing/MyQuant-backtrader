"""Pure book helpers; policy constants remain in each strategy book."""
from __future__ import annotations
from datetime import date
from typing import Callable, Mapping, Optional
from backtest.research.market_layer import as_date
from backtest.research.strategy7_rules import build_index_gate

def stop_hits(px, cost, stop_pct):
    if cost <= 0 or px <= 0:
        return False
    return float(px) / float(cost) - 1.0 <= -float(stop_pct)

def lot_budget(name_budget, _lots):
    return float(name_budget)

def may_add(lots, px):
    return bool(lots) and float(px) > 0

def step_add_due(lots, px, step):
    if float(step) <= 0 or float(px) <= 0 or (not lots):
        return False
    parent = next((p for p in lots if int(getattr(p, 'lot_id', -1)) == 0), None)
    if parent is None:
        return False
    cost = float(getattr(parent, 'cost', 0) or 0)
    if cost <= 0:
        return False
    n_steps = sum((1 for p in lots if getattr(p, 'is_step', False)))
    allowed = int((float(px) / cost - 1.0) / float(step) + 1e-12)
    return allowed > n_steps

def build_sse_ma10_block_new(closes, *, symbol):
    return build_index_gate(closes, symbol=symbol)

def allow_new_name_from_gate(block_new, *, INDEX_GATE_ON):
    if not INDEX_GATE_ON or block_new is None:
        return None

    def allow(day) -> bool:
        return not bool(block_new.get(as_date(day), False))
    return allow

def load_sse_ma10_block_new(start, end, *, root, build_sse_ma10_block_new):
    from backtest.research.csv_minute_backtest_v7 import load_index_daily

    def _ymd(value) -> date:
        text = str(value).replace('-', '')[:8]
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    closes = load_index_daily(_ymd(start), _ymd(end), root=root)
    return build_sse_ma10_block_new(closes)

def trail_line(cost, peak, *, FLOOR_MULT, KEEP_FRAC):
    rise = max(0.0, float(peak) - float(cost))
    return max(float(cost) * float(FLOOR_MULT), float(cost) + float(KEEP_FRAC) * rise)

def close_unarmed_reason(cost, peak, n_days, days, multiplier, reason):
    if int(n_days) < int(days):
        return None
    if float(cost) <= 0 or float(peak) <= 0:
        return None
    if float(peak) < float(cost) * float(multiplier):
        return reason
    return None

def give_band(peak, cost, *, BAND_WIDTH):
    if float(cost) <= 0 or float(peak) <= float(cost):
        raise ValueError('peak must be above positive cost')
    rise = float(peak) / float(cost) - 1.0
    return int((rise + 1e-12) / BAND_WIDTH)

def peak_dd_active(peak, cost, *, PEAK_DD_RISE):
    return float(peak) / float(cost) - 1.0 + 1e-12 > PEAK_DD_RISE

def floor_gain(peak, cost, *, FLOOR_STEPS):
    rise = float(peak) / float(cost) - 1.0
    for upper, gain in FLOOR_STEPS:
        if rise + 1e-12 < upper:
            return gain
    return None

def mid_peak_dd_active(peak, cost, *, MID_PEAK_DD_RISE, peak_dd_active):
    rise = float(peak) / float(cost) - 1.0
    return rise + 1e-12 >= MID_PEAK_DD_RISE and (not peak_dd_active(peak, cost))

def fixed_target_reason(px, cost, target):
    if px >= cost * (1.0 + target):
        return "profit_take:target"
    return None

def load_book_index_gate(book, start, end):
    from importlib import import_module

    if book in ("version8", "version8_3"):
        module = import_module("backtest.research.strategy8_rules")
    elif book in ("version12", "version8_4", "version8_5", "version8_6"):
        module = import_module("backtest.research.strategy" + book[7:] + "_rules")
    elif book == "version6_45":
        module = import_module("backtest.research.strategy6_45_rules")
    else:
        return None
    # 8.3 冻结包闸门无条件开，仍沿用 8 的 loader。
    if module.INDEX_GATE_ON or book == "version8_3":
        return module.load_sse_ma10_block_new(start, end)
    return None
