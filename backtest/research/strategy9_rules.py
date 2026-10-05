"""策略 9（底量超顶量）卖点纯函数。

买点不在本模块：由 ``export_strategy9_pool.py`` 写成契约日 CSV，引擎按名单买。
卖：止损距离每个交易日从此前 20 个真实波幅的简单算术均值重算，不在入场锁定；盈利达到成本的 10% 返回已有 reason
``profit_take:target``（不是新订单类型）。启用 --max-hold 后满 20 个交易日记
``force_sell:max_hold``，次日开盘离场。无分档回撤止盈；不加仓。
禁止默认 ``stock_pool/``（那是隔夜手工池，不是本信号）。
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

BOOK_TAG = "v9"
ALLOW_ADD = False
PEAK_GAP_MIN = 0

RANGE_BARS = 20
RANGE_LOOKBACK_CALENDAR_DAYS = 60
TAKE_PROFIT_PCT = 0.10
MAX_HOLD = 20
REQUIRES_EXPLICIT_POOL = True

HELP_LOCK = """
策略 9 卖点（--strategy version9）：
  买点 = 底量超顶量名单（export_strategy9_pool.py），不是 stock_pool/。
  必须显式 --pool-dir；指向本仓 stock_pool/ 立即退出。
  止损距离每个交易日从此前 20 个真实波幅的简单算术均值重算，不在入场锁定。
  触发价=成本 - 2 × 前20日真实波幅简单算术均值（元）；非百分比、非 Wilder。
  使用 T 前21根日线，TR=max(high-low, abs(high-prev_close), abs(low-prev_close))；排除 T。
  缺窗口当天不止损、不回落固定比例；--stop-pct 不接受。
  盈利达到成本的 10% 返回已有 reason
  profit_take:target（不是新订单类型），次日开盘卖。无分档回撤止盈；不加仓。
  20 交易日强平默认 OFF；启用 --max-hold 后，持仓交易日数 n_days>=20 收盘记 force_sell:max_hold，次日开盘卖
  （跌停则 defer）。已持仓票跳过，不叠加 lot；peak_gap_min=0。
  落盘：backtest_output/csv_{daily|minute}_v9_{start}_{end}/
"""


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
    *, max_hold: bool = False,
) -> Optional[str]:
    """T+1 后价格达到成本的 10% 优先止盈，启用 max_hold 时否则满持有期强平。"""
    del peak
    if n_days < 1:
        return None
    if cost > 0 and float(px) >= float(cost) * (1.0 + TAKE_PROFIT_PCT):
        return "profit_take:target"
    if max_hold and int(n_days) >= MAX_HOLD:
        return "force_sell:max_hold"
    return None


def record_strategy9_params(st, *, max_hold: bool = False) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = None
    st.stats["stop_mode"] = "cost_minus_2x_mean_true_range_20_yuan_trailing_daily"
    st.stats["range_bars"] = RANGE_BARS
    st.stats["profit_target"] = TAKE_PROFIT_PCT
    st.stats["max_hold"] = MAX_HOLD if max_hold else None


def mean_true_range(frame, day):
    """Simple mean of 20 true ranges in yuan, using only bars strictly before T."""
    prior = frame.loc[frame.index < pd.Timestamp(day)].tail(RANGE_BARS + 1)
    if len(prior) < RANGE_BARS + 1 or not {"high", "low", "close"}.issubset(prior.columns):
        return None
    values = prior[["high", "low", "close"]].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    if not np.isfinite(values).all() or (values[:, 0] < values[:, 1]).any():
        return None
    high, low = values[1:, 0], values[1:, 1]
    prev_close = values[:-1, 2]
    ranges = np.maximum.reduce((high - low, np.abs(high - prev_close), np.abs(low - prev_close)))
    average = float(ranges.mean())
    return average if np.isfinite(average) else None


def stop_range_status(frame, day):
    distance = mean_true_range(frame, day)
    if distance is not None:
        return distance, None
    prior = frame.loc[frame.index < pd.Timestamp(day)].tail(RANGE_BARS + 1)
    return None, "short_history" if len(prior) < RANGE_BARS + 1 else "missing_ohlc"


def stop_mean_true_range_status(frame, day):
    """Return twice the simple mean of 20 prior true ranges, in yuan."""
    prior = frame.loc[frame.index < pd.Timestamp(day)].tail(RANGE_BARS + 1)
    if len(prior) < RANGE_BARS + 1:
        return None, "short_history"
    if not {"open", "high", "low", "close"}.issubset(prior.columns):
        return None, "invalid_ohlc"
    values = prior[["open", "high", "low", "close"]].apply(
        pd.to_numeric, errors="coerce").to_numpy(float)
    if not np.isfinite(values).all() or (values[:, 1] < values[:, 2]).any():
        return None, "invalid_ohlc"
    high, low, prev_close = values[1:, 1], values[1:, 2], values[:-1, 3]
    ranges = np.maximum.reduce((high - low, np.abs(high - prev_close), np.abs(low - prev_close)))
    distance = float(2 * ranges.mean())
    return (distance, None) if np.isfinite(distance) else (None, "invalid_ohlc")


def stop_mean_true_range_distance(frame, day) -> Optional[float]:
    return stop_mean_true_range_status(frame, day)[0]


def evaluate_stop_range(hooks, frame, day, stats):
    """Evaluate the version9 hook once per session evaluation; count missing inputs."""
    distance = hooks["stop_range"](frame, day)
    if distance is None:
        reason = stop_mean_true_range_status(frame, day)[1]
        key = f"skip_stop_range:{reason}"
        stats[key] = stats.get(key, 0) + 1
    return distance
