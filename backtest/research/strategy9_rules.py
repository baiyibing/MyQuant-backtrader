"""策略 9（底量超顶量）卖点纯函数。

买点不在本模块：由 ``export_strategy9_pool.py`` 写成契约日 CSV，引擎按名单买。
卖：止损幅度每个交易日从此前 20 根日线重算，不在入场锁定；盈利达到成本的 10% 返回已有 reason
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
  止损幅度每个交易日从此前 20 根日线重算，不在入场锁定。
  幅度=(20 根最高 high - 最低 low)/窗口前一根 close；触发价=成本*(1-幅度)。
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
    st.stats["stop_mode"] = "range_amp_20_trailing"
    st.stats["range_bars"] = RANGE_BARS
    st.stats["profit_target"] = TAKE_PROFIT_PCT
    st.stats["max_hold"] = MAX_HOLD if max_hold else None


def stop_range_status(frame, day):
    """Return (daily range amplitude, missing-window reason), using bars before day."""
    prior = frame.loc[frame.index < pd.Timestamp(day)].tail(RANGE_BARS + 1)
    if len(prior) < RANGE_BARS + 1:
        return None, "short_history"
    window = prior.iloc[1:]
    if not {"high", "low"}.issubset(window.columns):
        return None, "missing_hl"
    high = pd.to_numeric(window["high"], errors="coerce").to_numpy(float)
    low = pd.to_numeric(window["low"], errors="coerce").to_numpy(float)
    if not (np.isfinite(high).all() and np.isfinite(low).all()) or (high < low).any():
        return None, "missing_hl"
    base = pd.to_numeric(pd.Series([prior.iloc[0].get("close")]), errors="coerce").iloc[0]
    if not np.isfinite(base) or base <= 0:
        return None, "missing_base_close"
    ratio = float((high.max() - low.min()) / base)
    if not np.isfinite(ratio):
        return None, "missing_hl"
    return ratio, None


def stop_range_amplitude(frame, day) -> Optional[float]:
    """(max(high) - min(low)) of prior 20 bars / close of prior 21st bar."""
    return stop_range_status(frame, day)[0]


def evaluate_stop_range(hooks, frame, day, stats):
    """Evaluate the version9 hook once per session evaluation; count missing inputs."""
    ratio = hooks["stop_range"](frame, day)
    if ratio is None:
        reason = stop_range_status(frame, day)[1]
        key = f"skip_stop_range:{reason}"
        stats[key] = stats.get(key, 0) + 1
    return ratio


SELL_MODES = ("mean_tr3_tp10", "range_amp_tp_amp", "mean_tr2_or_prior10_low")


def validate_sell_mode(strategy, mode, max_hold=False):
    if mode is None:
        return
    if strategy != "version9" or mode not in SELL_MODES:
        raise ValueError("version9_sell requires version9 and one of " + repr(SELL_MODES))
    if mode == "mean_tr2_or_prior10_low" and max_hold:
        raise ValueError("mean_tr2_or_prior10_low rejects max_hold")


def version9_exit(frame, day, mode):
    """Session plan from strictly prior bars; distances are in yuan."""
    prior = frame.loc[frame.index < pd.Timestamp(day)]
    plan = dict(stop_ratio=None, stop_yuan=None, take_profit_pct=None, channel_low=None)
    window = prior.tail(21)
    valid = len(window) == 21 and {"open", "high", "low", "close"}.issubset(window.columns)
    if valid:
        values = window[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce").to_numpy(float)
        valid = np.isfinite(values).all() and (values[:, 1] >= values[:, 2]).all() and (values[:, 3] > 0).all()
    if valid:
        if mode == "range_amp_tp_amp":
            amplitude = stop_range_amplitude(frame, day)
            plan.update(stop_ratio=amplitude, take_profit_pct=amplitude)
        else:
            high, low, previous = values[1:, 1], values[1:, 2], values[:-1, 3]
            mean = float(np.maximum.reduce([high-low, abs(high-previous), abs(low-previous)]).mean())
            plan["stop_yuan"] = mean * (3 if mode == "mean_tr3_tp10" else 2)
            if mode == "mean_tr3_tp10":
                plan["take_profit_pct"] = TAKE_PROFIT_PCT
    if mode == "mean_tr2_or_prior10_low":
        channel = prior.tail(10)
        if len(channel) == 10 and {"open", "high", "low", "close"}.issubset(channel.columns):
            vals = channel[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce").to_numpy(float)
            if np.isfinite(vals).all() and (vals[:, 1] >= vals[:, 2]).all():
                plan["channel_low"] = float(vals[:, 2].min())
    return plan


def evaluate_version9_exit(hooks, frame, day, stats):
    plan = hooks["version9_exit"](frame, day)
    if plan["stop_ratio"] is None and plan["stop_yuan"] is None:
        key = "skip_version9_exit:stop_window"
        stats[key] = stats.get(key, 0) + 1
    if stats.get("sell_mode") == "mean_tr2_or_prior10_low" and plan["channel_low"] is None:
        key = "skip_version9_exit:channel_window"
        stats[key] = stats.get(key, 0) + 1
    return plan


def plan_stop_price(plan, cost):
    if plan["stop_yuan"] is not None:
        return cost - plan["stop_yuan"]
    if plan["stop_ratio"] is not None:
        return cost * (1 - plan["stop_ratio"])
    return None


def plan_close_reason(plan, close, cost, n_days, max_hold=False):
    if plan["channel_low"] is not None and close < plan["channel_low"]:
        return "close_below:prior_10d_low"
    pct = plan["take_profit_pct"]
    if pct is not None and close >= cost * (1 + pct):
        return "profit_take:target"
    if max_hold and n_days >= MAX_HOLD:
        return "force_sell:max_hold"
    return None
