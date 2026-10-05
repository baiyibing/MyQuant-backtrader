"""把已有分钟策略接到真核扫线。旧分钟入口保持原样。

一根 K、成交或跳过。默认 timing="same_bar"。止损仍是开盘穿过按开盘、
low 触及按止损价；策略书自己的卖点用这根收盘，成交或跳过，不另造订单类型。

均线、阶段与 dropout 卖出标记，由调用方把已经算好的结果传进来。
score-exit 的排名剔除与 SX0，也由调用方用 dropout_sell / sx0_sell 传入已经算好的卖出标记。
不在这里重算 SMA，不读湖，不挂单。

一根 K 上看不见的时钟不在这次判断里：峰差分钟、涨停保留窗、14:50 强平、
只在收盘那根才清的 T+1/T+4。那些仍留在旧分钟引擎。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from backtest.research import strategy2_rules
from backtest.research.bar_scan_exit import (
    BarScanExit,
    FillTiming,
    FillPrice,
    HeldPosition,
    OhlcBar,
    _ohlc,
    apply_fill_timing,
    check_fill_timing,
    scan_bar_exit,
)
from backtest.research.csv_strategy_books import csv_strategy_names
from backtest.research.strategy1_rules import (
    PROFIT_DRAWDOWN_PCT as V1_DRAWDOWN,
    STOP_PCT as V1_STOP,
)
from backtest.research.strategy10_rules import take_profit_reason as v10_take
from backtest.research.strategy11_rules import HOLD as V11_HOLD
from backtest.research.strategy11_rules import exit_signal as v11_exit
from backtest.research.strategy12_rules import HOLD20 as V12_HOLD20
from backtest.research.strategy12_rules import STOP as V12_STOP_REASON
from backtest.research.strategy12_rules import SellLot
from backtest.research.strategy12_rules import hold20_orders as v12_hold20
from backtest.research.strategy12_rules import stop_line as v12_stop_line
from backtest.research.strategy3_rules import STOP_PCT as V3_STOP
from backtest.research.strategy3_rules import take_profit_reason as v3_take
from backtest.research.strategy5_rules import take_profit_reason as v5_take
from backtest.research.strategy6_1_rules import STOP_PCT as V6_1_STOP
from backtest.research.strategy6_1_rules import take_profit_reason as v6_1_take
from backtest.research.strategy6_rules import STOP_PCT as V6_STOP
from backtest.research.strategy6_rules import take_profit_reason as v6_take
from backtest.research.strategy7_rules import (
    EIGHT,
    FOUR,
    FULL,
    SIX,
    TRIAL,
    stop_decision,
)
from backtest.research.strategy8_1_rules import STOP_PCT as V8_1_STOP
from backtest.research.strategy8_1_rules import take_profit_reason as v8_1_take
from backtest.research.strategy8_2_rules import STOP_PCT as V8_2_STOP
from backtest.research.strategy8_2_rules import take_profit_reason as v8_2_take
from backtest.research.strategy8_3_rules import STOP_PCT as V8_3_STOP
from backtest.research.strategy8_3_rules import take_profit_reason as v8_3_take
from backtest.research.strategy8_4_rules import STOP_PCT as V8_4_STOP
from backtest.research.strategy8_4_rules import take_profit_reason as v8_4_take
from backtest.research.strategy8_5_rules import STOP_PCT as V8_5_STOP
from backtest.research.strategy8_5_rules import take_profit_reason as v8_5_take
from backtest.research.strategy8_6_rules import STOP_PCT as V8_6_STOP
from backtest.research.strategy8_6_rules import take_profit_reason as v8_6_take
from backtest.research.strategy8_rules import STOP_PCT as V8_STOP
from backtest.research.strategy8_rules import take_profit_reason as v8_take
from backtest.research.strategy9_rules import stop_range_amplitude, effective_stop_ratio
from backtest.research.strategy9_rules import take_profit_reason as v9_take
from backtest.research.strategy10_rules import STOP_PCT as V10_STOP
from backtest.research.strategy_topk_dropout_rules import STOP_PCT as TOPK_STOP
from backtest.research.strategy_topk_score_exit_rules import STOP_PCT as TOPK_SCORE_EXIT_STOP
from backtest.research.topk_score_exit_rules import ScoreExitPlan, sell_reason

CLI_MINUTE = "backtest/research/csv_minute_backtest.py"
CLI_V7 = "backtest/research/csv_minute_backtest_v7.py"
CLI_TOPK_APP = "backtest/research/csv_minute_backtest_topk_app_dropout.py"

# 不在 csv_strategy_books 里、但有自己的分钟入口。
EXTRA_MINUTE_STRATEGIES: tuple[str, ...] = ("version7", "topk_app_dropout")

DrawdownOf = Callable[[int], float]
V7_STAGES = frozenset({TRIAL, FOUR, SIX, EIGHT, FULL})
# 与 csv_minute_backtest_v7 卖出原因相同，不另起名字。
_V7_REASONS = {
    "dump_trial": "stop:trial_a090",
    "clear_four": "stop:four_avg095",
    "clear_six": "stop:six_avg0965",
    "clear_eight": "stop:eight_avg0975",
    "clear_full": "stop:full_avg098",
}


def _v1_drawdown(n_days: int) -> float:
    del n_days
    return float(V1_DRAWDOWN)


@dataclass(frozen=True, slots=True)
class WiredBook:
    name: str
    stop_pct: float
    drawdown_of: DrawdownOf


@dataclass(frozen=True, slots=True)
class MinuteStrategyEntry:
    name: str
    cli: str
    status: str
    missing_field: str | None


_DRAWDOWN: dict[str, WiredBook] = {
    "version1": WiredBook("version1", float(V1_STOP), _v1_drawdown),
}

# 百分比止损与策略书卖点。卖点函数自己带着目标价、分档、持有期。
_PERCENT_STOP: dict[str, float] = {
    "version2": float(strategy2_rules.STOP_PCT),
    "version3": float(V3_STOP),
    "version6": float(V6_STOP),
    "version6_1": float(V6_1_STOP),
    "version8": float(V8_STOP),
    "version8_1": float(V8_1_STOP),
    "version8_2": float(V8_2_STOP),
    "version8_3": float(V8_3_STOP),
    "version8_4": float(V8_4_STOP),
    "version8_5": float(V8_5_STOP),
    "version8_6": float(V8_6_STOP),
    "version10": float(V10_STOP),
    "topk_dropout": float(TOPK_STOP),
    "topk_score_exit": float(TOPK_SCORE_EXIT_STOP),
}


def _v9_2_take(close: float, cost: float, peak: float, n_days: int) -> None:
    return None


def _version9_1_take(*args: object) -> None:
    return None


_BOOK_TAKE = {
    "version3": v3_take,
    "version5": v5_take,
    "version6": v6_take,
    "version6_1": v6_1_take,
    "version8": v8_take,
    "version8_1": v8_1_take,
    "version8_2": v8_2_take,
    "version8_3": v8_3_take,
    "version8_4": v8_4_take,
    "version8_5": v8_5_take,
    "version8_6": v8_6_take,
    "version9": v9_take,
    "version9_1": _version9_1_take,
    "version9_2": _v9_2_take,
    "version10": v10_take,
}

# 调用方必须传入已经算好的数。缺了就拒绝，不在扫线里重算序列。
_LEVEL_FIELD = {
    "version4": "sma5",
    "version11": "sma5",
    "version12": "ma10",
    "version7": "stage",
    "topk_app_dropout": "stage",
}

_BLOCKED_FIELD: dict[str, str] = {}


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


def _known(name: str) -> bool:
    return (
        name in _DRAWDOWN
        or name in _PERCENT_STOP
        or name in _BOOK_TAKE
        or name in _LEVEL_FIELD
        or name in _BLOCKED_FIELD
    )


def minute_strategy_entries() -> tuple[MinuteStrategyEntry, ...]:
    names = minute_strategy_names()
    unknown = [name for name in names if not _known(name)]
    if unknown:
        raise RuntimeError(f"minute strategy not classified for bar scan: {unknown}")
    stale = [
        name
        for name in (*_DRAWDOWN, *_PERCENT_STOP, *_BOOK_TAKE, *_LEVEL_FIELD, *_BLOCKED_FIELD)
        if name not in names
    ]
    if stale:
        raise RuntimeError(f"bar-scan classification has unknown strategies: {stale}")
    out: list[MinuteStrategyEntry] = []
    for name in names:
        if name in _BLOCKED_FIELD:
            out.append(MinuteStrategyEntry(name, _cli(name), "blocked", _BLOCKED_FIELD[name]))
        else:
            out.append(MinuteStrategyEntry(name, _cli(name), "wired", None))
    return tuple(out)


def wired_names() -> tuple[str, ...]:
    return tuple(entry.name for entry in minute_strategy_entries() if entry.status == "wired")


def blocked_entries() -> tuple[MinuteStrategyEntry, ...]:
    return tuple(entry for entry in minute_strategy_entries() if entry.status == "blocked")


def _level(name: str, level: float | None) -> float:
    if level is None:
        raise ValueError(f"{name} requires {_LEVEL_FIELD[name]}")
    number = float(level)
    if number != number or number <= 0:  # NaN
        raise ValueError(f"{name} {_LEVEL_FIELD[name]} must be a finite number > 0")
    if number == float("inf"):
        raise ValueError(f"{name} {_LEVEL_FIELD[name]} must be a finite number > 0")
    return number


def _stage_line(name: str, stage: str | None, cost: float, entry_a: float | None):
    if stage not in V7_STAGES:
        raise ValueError(f"{name} requires stage trial|four|six|eight|full")
    anchor = float(cost if entry_a is None else entry_a)
    decision = stop_decision(stage, entry_a=anchor, average_cost=float(cost))
    if decision.line is None:
        raise ValueError(f"{name} stage {stage} has no stop line")
    return decision


def _book_reason(
    name: str,
    close: float,
    cost: float,
    peak: float,
    n_days: int,
    level: float | None,
    prev_close: float | None,
    hold_mode: str | None,
    max_hold: bool = False,
) -> str | None:
    if name == "version2":
        return strategy2_rules.take_profit_reason(close, cost, peak, n_days)
    if name == "version4":
        sma5 = _level(name, level)
        if close < sma5:
            return "ma_signal:MA5"
        return None
    if name == "version11":
        sma5 = _level(name, level)
        mode = V11_HOLD if hold_mode is None else str(hold_mode)
        prior = prev_close if prev_close is not None else float("nan")
        decision = v11_exit(close, prior, sma5, hold_mode=mode)
        return decision.reason or None
    if name == "version12":
        ma10 = _level(name, level)
        line = v12_stop_line(ma10)
        if line is not None and 0 < close <= line:
            return V12_STOP_REASON
        lot = SellLot(lot_id=0, shares=100, sellable=100, n_days=int(n_days), cost=float(cost))
        if v12_hold20([lot], close):
            return V12_HOLD20
        return None
    if name == "version9":
        return v9_take(close, cost, peak, n_days, max_hold=max_hold)
    take = _BOOK_TAKE.get(name)
    if take is None:
        return None
    return take(close, cost, peak, n_days)


def _stage_exit(
    name: str,
    bar: OhlcBar,
    *,
    cost: float,
    peak: float,
    stage: str | None,
    entry_a: float | None,
    session_open: bool,
) -> BarScanExit:
    opening, high, _low, close = _ohlc(bar, "bar")
    new_peak = high if high > peak else peak
    decision = _stage_line(name, stage, cost, entry_a)
    line = float(decision.line)
    reason = _V7_REASONS.get(decision.action, f"stop:{decision.action}")
    # 策略 7 只在当日第一根用开盘跳空；之后只看这根收盘，不看 low。
    if session_open and opening <= line:
        return BarScanExit("fill", opening, reason, new_peak)
    if close <= line:
        return BarScanExit("fill", close, reason, new_peak)
    return BarScanExit("skip", None, "", new_peak)


def _version9_range_stop(
    bar: OhlcBar,
    *,
    cost: float,
    peak: float,
    ratio: float,
    timing: FillTiming,
    price: FillPrice,
    next_bar: OhlcBar | None,
) -> BarScanExit | None:
    """Apply the higher of today's range stop and the fixed cost stop.

    ``ratio`` is the effective ratio after comparing the two unclamped prices.
    Gap stops precede the existing close-based target; targets precede touches.
    """
    opening, high, low, close = _ohlc(bar, "bar")
    new_peak = high if high > peak else peak
    trigger = float(cost) * (1.0 - float(ratio))
    if opening <= trigger:
        result = BarScanExit("fill", opening, "stop_loss:gap_open", new_peak)
    elif v9_take(close, cost, new_peak, 1) == "profit_take:target":
        result = BarScanExit("fill", close, "profit_take:target", new_peak)
    elif low <= trigger:
        if price == "close" and timing == "same_bar":
            result = BarScanExit("fill", close, "stop_loss:touch:bar_close", new_peak)
        else:
            result = BarScanExit("fill", trigger, "stop_loss:touch", new_peak)
    else:
        return None
    return apply_fill_timing(result, timing=timing, next_bar=next_bar)


def invoke_minute_strategy(
    name: str,
    bar: OhlcBar,
    *,
    cost: float,
    peak: float,
    n_days: int = 1,
    max_hold: bool = False,
    timing: FillTiming = "same_bar",
    price: FillPrice = "stop",
    next_bar: OhlcBar | None = None,
    level: float | None = None,
    stage: str | None = None,
    entry_a: float | None = None,
    prev_close: float | None = None,
    hold_mode: str | None = None,
    session_open: bool = True,
    dropout_sell: bool | None = None,
    sx0_sell: bool | None = None,
    daily_bars=None,
    as_of=None,
) -> BarScanExit:
    """对一个已可卖的持仓扫一根 K。``n_days`` < 1 不是可卖 bar，直接拒绝。

    ``level`` 是调用方已经算好的 sma5 或 ma10。``stage`` 是策略 7 / topk_app 的阶段。
    默认 ``timing="same_bar"``。
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
    check_fill_timing(timing, next_bar)
    cost_f = float(cost)
    peak_f = float(peak)
    if cost_f <= 0 or peak_f <= 0:
        raise ValueError("cost and peak must be finite numbers > 0")

    if key == "topk_dropout":
        if dropout_sell is None:
            raise ValueError(
                "topk_dropout requires dropout_sell: caller must pass the already-decided "
                "dropout sell for this name today; the scan does not rank the day"
            )
        if not isinstance(dropout_sell, bool):
            raise ValueError("topk_dropout dropout_sell must be a bool")

    if key == "topk_score_exit":
        if dropout_sell is None or sx0_sell is None:
            raise ValueError(
                "topk_score_exit requires dropout_sell and sx0_sell: caller must pass the "
                "already-decided rank-dropout sell and the already-decided SX0 sell for "
                "this name today; the scan does not rank the day and does not treat a "
                "raw score as the exit"
            )
        if not isinstance(dropout_sell, bool):
            raise ValueError("topk_score_exit dropout_sell must be a bool")
        if not isinstance(sx0_sell, bool):
            raise ValueError("topk_score_exit sx0_sell must be a bool")

    if key == "version9":
        ratio = None
        if daily_bars is not None:
            if as_of is None:
                raise ValueError("version9 range stop requires as_of")
            ratio = stop_range_amplitude(daily_bars, as_of)
        stopped = _version9_range_stop(
            bar, cost=cost_f, peak=peak_f, ratio=effective_stop_ratio(ratio),
            timing=timing, price=price, next_bar=next_bar,
        )
        if stopped is not None:
            return stopped

    if key in _DRAWDOWN:
        book = _DRAWDOWN[key]
        position = HeldPosition(
            cost=cost_f,
            peak=peak_f,
            stop_pct=book.stop_pct,
            drawdown_take_profit=book.drawdown_of(held_days),
        )
        return scan_bar_exit(bar, position, timing=timing, price=price, next_bar=next_bar)

    if key in _LEVEL_FIELD and _LEVEL_FIELD[key] == "stage":
        judged = _stage_exit(
            key,
            bar,
            cost=cost_f,
            peak=peak_f,
            stage=stage,
            entry_a=entry_a,
            session_open=bool(session_open),
        )
        return apply_fill_timing(judged, timing=timing, next_bar=next_bar)

    new_peak = peak_f
    if key in _PERCENT_STOP:
        stopped = scan_bar_exit(
            bar,
            HeldPosition(
                cost=cost_f,
                peak=peak_f,
                stop_pct=_PERCENT_STOP[key],
                drawdown_take_profit=1.0,
            ),
            timing=timing,
            next_bar=next_bar,
            evaluate_drawdown=False,
            price=price,
        )
        if stopped.decision == "fill":
            return stopped
        new_peak = stopped.peak
        _opening, _high, _low, close = _ohlc(bar, "bar")
    else:
        _opening, high, _low, close = _ohlc(bar, "bar")
        new_peak = high if high > peak_f else peak_f

    if key == "topk_dropout":
        reason = "topk_drop:bottom" if dropout_sell else None
    elif key == "topk_score_exit":
        code = "held"
        plan = ScoreExitPlan(
            buy=(),
            sell=(),
            buy_bottom=(),
            sell_bottom=(code,) if dropout_sell else (),
            sell_sx0=(code,) if sx0_sell else (),
            also_bottom=(),
            buy_extra=(),
        )
        reason = sell_reason(code, plan)
    else:
        reason = _book_reason(
            key,
            close,
            cost_f,
            new_peak,
            held_days,
            level,
            prev_close,
            hold_mode,
            max_hold,
        )
    if not reason:
        return BarScanExit("skip", None, "", new_peak)
    judged = BarScanExit("fill", close, reason, new_peak)
    return apply_fill_timing(judged, timing=timing, next_bar=next_bar)
