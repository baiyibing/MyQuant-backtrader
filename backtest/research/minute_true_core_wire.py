"""把已有分钟策略接到真核扫线。旧分钟入口保持原样。

卖点若只是一根 K 上的固定止损比例加一个利润回撤，就调用 ``scan_bar_exit``：
成交或跳过，时点 ``same_bar`` / ``next_bar``。不造挂单簿，不发明第二种成交价。

缺一个扫线没有的字段时，记为 blocked，不写适配器。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from backtest.research.bar_scan_exit import (
    BarScanExit,
    FillTiming,
    HeldPosition,
    OhlcBar,
    scan_bar_exit,
)
from backtest.research.csv_strategy_books import csv_strategy_names
from backtest.research.strategy1_rules import (
    PROFIT_DRAWDOWN_PCT as V1_DRAWDOWN,
    STOP_PCT as V1_STOP,
)
from backtest.research.strategy2_rules import (
    DRAWDOWN_THRESHOLDS as V2_DRAWDOWN,
    STOP_PCT as V2_STOP,
)

CLI_MINUTE = "backtest/research/csv_minute_backtest.py"
CLI_V7 = "backtest/research/csv_minute_backtest_v7.py"
CLI_TOPK_APP = "backtest/research/csv_minute_backtest_topk_app_dropout.py"

# 不在 csv_strategy_books 里、但有自己的分钟入口。
EXTRA_MINUTE_STRATEGIES: tuple[str, ...] = ("version7", "topk_app_dropout")

Status = Literal["wired", "blocked"]
DrawdownOf = Callable[[int], float]


def _v1_drawdown(n_days: int) -> float:
    del n_days
    return float(V1_DRAWDOWN)


def _v2_drawdown(n_days: int) -> float:
    held = int(n_days)
    return float(V2_DRAWDOWN.get(held, V2_DRAWDOWN[max(V2_DRAWDOWN)]))


@dataclass(frozen=True, slots=True)
class WiredBook:
    name: str
    stop_pct: float
    drawdown_of: DrawdownOf


@dataclass(frozen=True, slots=True)
class MinuteStrategyEntry:
    name: str
    cli: str
    status: Status
    missing_field: str | None


_WIRED: dict[str, WiredBook] = {
    "version1": WiredBook("version1", float(V1_STOP), _v1_drawdown),
    "version2": WiredBook("version2", float(V2_STOP), _v2_drawdown),
}

# 一个缺的字段。扫线只有 stop_pct 和单一 drawdown_take_profit，这些书对不上。
_BLOCKED_FIELD: dict[str, str] = {
    "version3": "profit_target",
    "version4": "sma5",
    "version5": "profit_target",
    "version6": "band_split",
    "version6_1": "give_band",
    "version7": "stage",
    "version8": "floor_mult",
    "version8_1": "profit_base",
    "version8_2": "trigger_band",
    "version8_3": "livermore_band",
    "version8_4": "profit_target",
    "version8_5": "profit_target",
    "version8_6": "floor_mult",
    "version9": "max_hold",
    "version10": "profit_base",
    "version11": "sma5",
    "version12": "ma10",
    "topk_dropout": "score",
    "topk_score_exit": "score",
    "topk_app_dropout": "stage",
}


class MinuteStrategyNotOnBarScan(ValueError):
    """这本书不能接到扫线。``missing_field`` 是扫线没有的那一个字段。"""

    def __init__(self, name: str, missing_field: str) -> None:
        self.name = name
        self.missing_field = missing_field
        super().__init__(f"{name} is not on the bar scan; missing {missing_field}")


def minute_strategy_names() -> tuple[str, ...]:
    """csv_minute_backtest 的注册书，再加上 v7 与 topk_app_dropout。"""
    books = csv_strategy_names()
    overlap = [name for name in EXTRA_MINUTE_STRATEGIES if name in books]
    if overlap:
        raise RuntimeError(f"extra minute strategy already registered: {overlap}")
    return books + EXTRA_MINUTE_STRATEGIES


def _cli(name: str) -> str:
    if name == "version7":
        return CLI_V7
    if name == "topk_app_dropout":
        return CLI_TOPK_APP
    return CLI_MINUTE


def minute_strategy_entries() -> tuple[MinuteStrategyEntry, ...]:
    names = minute_strategy_names()
    unknown = [name for name in names if name not in _WIRED and name not in _BLOCKED_FIELD]
    if unknown:
        raise RuntimeError(f"minute strategy not classified for bar scan: {unknown}")
    stale = [
        name
        for name in (*_WIRED, *_BLOCKED_FIELD)
        if name not in names
    ]
    if stale:
        raise RuntimeError(f"bar-scan classification has unknown strategies: {stale}")
    out: list[MinuteStrategyEntry] = []
    for name in names:
        if name in _WIRED:
            out.append(MinuteStrategyEntry(name, _cli(name), "wired", None))
        else:
            out.append(
                MinuteStrategyEntry(name, _cli(name), "blocked", _BLOCKED_FIELD[name])
            )
    return tuple(out)


def wired_names() -> tuple[str, ...]:
    return tuple(entry.name for entry in minute_strategy_entries() if entry.status == "wired")


def blocked_entries() -> tuple[MinuteStrategyEntry, ...]:
    return tuple(entry for entry in minute_strategy_entries() if entry.status == "blocked")


def invoke_minute_strategy(
    name: str,
    bar: OhlcBar,
    *,
    cost: float,
    peak: float,
    n_days: int = 1,
    timing: FillTiming = "same_bar",
    next_bar: OhlcBar | None = None,
) -> BarScanExit:
    """对一个已可卖的持仓扫一根 K。``n_days`` < 1 不是可卖 bar，直接拒绝。

    version2 的回撤比例按持仓日从策略书取出，再交给扫线。不在扫线外改成交价。
    """
    key = str(name)
    entries = {entry.name: entry for entry in minute_strategy_entries()}
    if key not in entries:
        raise ValueError(f"unknown minute strategy {name!r}")
    entry = entries[key]
    if entry.status != "wired":
        raise MinuteStrategyNotOnBarScan(key, str(entry.missing_field))
    held_days = int(n_days)
    if held_days < 1:
        raise ValueError("bar scan wire is for a sellable bar; n_days must be >= 1")
    book = _WIRED[key]
    position = HeldPosition(
        cost=float(cost),
        peak=float(peak),
        stop_pct=book.stop_pct,
        drawdown_take_profit=book.drawdown_of(held_days),
    )
    return scan_bar_exit(bar, position, timing=timing, next_bar=next_bar)
