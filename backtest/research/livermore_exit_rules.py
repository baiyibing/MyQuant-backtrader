"""统一卖出 Mode B 的利弗莫尔卖点冻结本。

不是现行 ``--strategy version8`` 书。策略 8 现锁见 ``strategy8_rules``。
本模块只给 Mode B L2/L3 与其单测用，档位/僵持日数不再跟随宿主书改动。
"""

from __future__ import annotations

from typing import Optional

BAND_ARMS: tuple[float, ...] = (0.06, 0.15, 0.50, 1.00)
BAND1_MIN_MULT = 0.0
BAND_TRAIL_MIN_MULT = 1.06
BAND2_ABS_MULT = 1.02
BAND3_KEEP = 0.60
BAND3_GLOBAL_MULT = 1.15
BAND4_KEEP = 0.70
BAND5_KEEP = 0.80
GIVEBACK_MULT = 0.0
STALE_DAYS = 8


def band_of(cost: float, peak: float) -> Optional[int]:
    c = float(cost)
    p = float(peak)
    if c <= 0 or p <= c:
        return None
    if p < c * (1.0 + BAND_ARMS[0]):
        return 1
    if p < c * (1.0 + BAND_ARMS[1]):
        return 2
    if p < c * (1.0 + BAND_ARMS[2]):
        return 3
    if p < c * (1.0 + BAND_ARMS[3]):
        return 4
    return 5


def trigger_line(cost: float, peak: float, band: int) -> float:
    c = float(cost)
    p = float(peak)
    if band == 1:
        return c
    if band == 2:
        return c * BAND2_ABS_MULT
    if band == 3:
        return max(c * BAND3_GLOBAL_MULT, c + BAND3_KEEP * (p - c))
    if band == 4:
        return c + BAND4_KEEP * (p - c)
    return c + BAND5_KEEP * (p - c)


def never_armed(cost: float, peak: float) -> bool:
    b = band_of(cost, peak)
    return b is None or b == 1


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
) -> Optional[str]:
    if int(n_days) < 1:
        return None
    if cost <= 0 or px <= 0 or peak <= 0:
        return None
    if GIVEBACK_MULT > 0 and float(px) <= float(cost) * GIVEBACK_MULT:
        return "force_sell:giveback"
    if STALE_DAYS > 0 and int(n_days) >= STALE_DAYS and never_armed(cost, peak):
        return "force_sell:stale"
    if float(px) < float(cost):
        return None
    if BAND_TRAIL_MIN_MULT > 1.0 and float(peak) <= float(cost) * BAND_TRAIL_MIN_MULT:
        return None
    band = band_of(cost, peak)
    if band is None:
        return None
    if band == 1 and BAND1_MIN_MULT > 1.0 and float(px) < float(cost) * BAND1_MIN_MULT:
        return None
    line = trigger_line(cost, peak, band)
    if float(px) <= line:
        return f"trail:band:{band}"
    return None
