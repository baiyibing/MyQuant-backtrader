"""一根 K 扫一个持仓：成交或跳过。成交时点可配。

不是挂单簿，不是交易系统。不扩展订单类型，不挂单，不走事件总线，不进经纪商队列。
默认 timing="same_bar"，与未加开关时的 scan_bar_exit 相同：
止损开盘已经穿过则按开盘价成交；盘中 low 触及则按止损价成交。
回撤止盈先用本根 high 抬峰值，再只看收盘是否达到回撤比例，达到则按收盘价成交。
timing="next_bar" 仍用这根 K 判断成交或跳过，但成交价改成下一根开盘，不在下一根上重判。
同一根先看止损。本函数不记手续费。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

Decision = Literal["fill", "skip"]
FillTiming = Literal["same_bar", "next_bar"]


@dataclass(frozen=True, slots=True)
class OhlcBar:
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True, slots=True)
class HeldPosition:
    """一个已持仓。stop_pct 例如 0.02；drawdown_take_profit 例如 0.50。"""

    cost: float
    peak: float
    stop_pct: float
    drawdown_take_profit: float


@dataclass(frozen=True, slots=True)
class BarScanExit:
    decision: Decision
    fill_price: float | None
    reason: str
    peak: float


def _positive(name: str, value: float) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a finite number > 0")
    return number


def _ohlc(bar: OhlcBar, label: str) -> tuple[float, float, float, float]:
    opening = _positive(f"{label} open", bar.open)
    high = _positive(f"{label} high", bar.high)
    low = _positive(f"{label} low", bar.low)
    close = _positive(f"{label} close", bar.close)
    if high < low or high < max(opening, close) or low > min(opening, close):
        raise ValueError(f"{label} OHLC is inconsistent")
    return opening, high, low, close


def check_fill_timing(timing: FillTiming, next_bar: OhlcBar | None) -> None:
    """same_bar 不接收下一根。next_bar 时点可以先不给下一根，跳过时用不到。"""
    if timing not in ("same_bar", "next_bar"):
        raise ValueError("timing must be 'same_bar' or 'next_bar'")
    if timing == "same_bar" and next_bar is not None:
        raise ValueError("next_bar is only used when timing is 'next_bar'")


def apply_fill_timing(
    result: BarScanExit,
    *,
    timing: FillTiming = "same_bar",
    next_bar: OhlcBar | None = None,
) -> BarScanExit:
    """本根已判定。same_bar 保持成交价。next_bar 且成交时改成下一根开盘，不重判。"""
    check_fill_timing(timing, next_bar)
    if timing == "same_bar" or result.decision != "fill":
        return result
    if next_bar is None:
        raise ValueError("next_bar is required when timing is 'next_bar' and this bar fills")
    next_open, _, _, _ = _ohlc(next_bar, "next_bar")
    return BarScanExit("fill", next_open, f"{result.reason}:next_open", result.peak)


def scan_bar_exit(
    bar: OhlcBar,
    position: HeldPosition,
    *,
    timing: FillTiming = "same_bar",
    next_bar: OhlcBar | None = None,
    evaluate_drawdown: bool = True,
) -> BarScanExit:
    """给定一根 K 和一个持仓，返回成交或跳过。无跨调用状态。

    timing 默认 same_bar。next_bar 只在 next_bar 时点、且本根要成交时使用。
    evaluate_drawdown 默认 True。False 时只判止损，回撤留给调用方自己的卖点。
    """
    check_fill_timing(timing, next_bar)

    opening, high, low, close = _ohlc(bar, "bar")

    cost = _positive("cost", position.cost)
    peak = _positive("peak", position.peak)
    stop_pct = float(position.stop_pct)
    drawdown = float(position.drawdown_take_profit)
    if not math.isfinite(stop_pct) or not 0.0 < stop_pct < 1.0:
        raise ValueError("stop_pct must be in (0, 1)")
    if evaluate_drawdown and (not math.isfinite(drawdown) or not 0.0 < drawdown <= 1.0):
        raise ValueError("drawdown_take_profit must be in (0, 1]")

    # 与 scan_held_day_python 相同：先用本根 high 抬峰值，再判止损。
    new_peak = high if high > peak else peak
    stop_price = cost * (1.0 - stop_pct)
    result: BarScanExit
    if opening <= stop_price:
        result = BarScanExit("fill", opening, "stop_loss:gap_open", new_peak)
    elif low <= stop_price:
        result = BarScanExit("fill", stop_price, "stop_loss:touch", new_peak)
    elif evaluate_drawdown and close >= cost and new_peak > cost:
        retrace = (new_peak - close) / (new_peak - cost)
        if retrace >= drawdown:
            pct = int(round(drawdown * 100))
            result = BarScanExit("fill", close, f"profit_take:drawdown:{pct}", new_peak)
        else:
            result = BarScanExit("skip", None, "", new_peak)
    else:
        result = BarScanExit("skip", None, "", new_peak)

    return apply_fill_timing(result, timing=timing, next_bar=next_bar)
