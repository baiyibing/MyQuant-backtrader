"""当根 K 线扫一个持仓：成交或跳过。

不是挂单簿，不是交易系统。不扩展订单类型，不挂单，不走事件总线，不进经纪商队列。
止损成交价与旧分钟引擎的 hl 触价相同，也与 Backtrader Stop 的成交价相同：
开盘已经穿过止损价则按开盘价成交；盘中 low 触及则按止损价成交。
回撤止盈与 version1 相同：先用本根 high 抬峰值，再只看收盘是否达到回撤比例，
达到则按收盘价成交。同一根先看止损。本函数不记手续费。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

Decision = Literal["fill", "skip"]


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


def scan_bar_exit(bar: OhlcBar, position: HeldPosition) -> BarScanExit:
    """给定一根 K 和一个持仓，返回成交或跳过。无跨 bar 状态。"""
    opening = _positive("open", bar.open)
    high = _positive("high", bar.high)
    low = _positive("low", bar.low)
    close = _positive("close", bar.close)
    if high < low or high < max(opening, close) or low > min(opening, close):
        raise ValueError("bar OHLC is inconsistent")

    cost = _positive("cost", position.cost)
    peak = _positive("peak", position.peak)
    stop_pct = float(position.stop_pct)
    drawdown = float(position.drawdown_take_profit)
    if not math.isfinite(stop_pct) or not 0.0 < stop_pct < 1.0:
        raise ValueError("stop_pct must be in (0, 1)")
    if not math.isfinite(drawdown) or not 0.0 < drawdown <= 1.0:
        raise ValueError("drawdown_take_profit must be in (0, 1]")

    # 与 scan_held_day_python 相同：先用本根 high 抬峰值，再判止损。
    new_peak = high if high > peak else peak
    stop_price = cost * (1.0 - stop_pct)
    if opening <= stop_price:
        return BarScanExit("fill", opening, "stop_loss:gap_open", new_peak)
    if low <= stop_price:
        return BarScanExit("fill", stop_price, "stop_loss:touch", new_peak)
    if close >= cost and new_peak > cost:
        retrace = (new_peak - close) / (new_peak - cost)
        if retrace >= drawdown:
            pct = int(round(drawdown * 100))
            return BarScanExit("fill", close, f"profit_take:drawdown:{pct}", new_peak)
    return BarScanExit("skip", None, "", new_peak)
