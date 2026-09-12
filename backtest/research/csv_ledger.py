# -*- coding: utf-8 -*-
"""Shared ledger for CSV daily / minute engines.

Position, SimState, buy/sell fills, and chase accounting live here so the
two simulate loops stay thin. This module must not import either engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from backtest.research.market_layer import limit_prices

DEFAULT_TOTAL_CASH = 21_000_000.0
COMMISSION = 0.001
PEAK_GAP_MIN = 15
CHASE_HM = 9 * 60 + 45
LIMIT_EPS = 0.001


def _empty_stats() -> dict:
    return {
        "buys": 0,
        "skip_limit_up": 0,
        "skip_unknown_board": 0,
        "chase_buy": 0,
        "chase_abandon": 0,
        "chase_skip_limit": 0,
        "chase_no_bar": 0,
        "chase_overwrite": 0,
        "chase_buy_fail": 0,
        "chase_pending_eod": 0,
        "chase_skip_held": 0,
        "skip_held": 0,
        "add_lots": 0,
        "skip_no_bar": 0,
        "skip_buy_gate": 0,
        "skip_sma_warmup": 0,
        "sell_stop": 0,
        "sell_trail": 0,
        "sell_pos_trail": 0,
        "sell_profit_take": 0,
        "sell_open_board": 0,
        "sell_force": 0,
        "sell_ma": 0,
        "defer_sell_limit_down": 0,
        "invested_notional": 0.0,
        "supplementary_used": 0.0,
        "bars_loaded": 0,
        "pool_days": 0,
    }


@dataclass
class Position:
    code: str
    shares: int
    cost: float  # 买入价（收盘成交价）
    entry_idx: int  # 全局日历下标
    peak: float  # 持仓期最高价（起始=买入价；T+1 起用每日 high 更新）
    peak_hm: int = -1  # 峰值所在分钟 hm；跨日为负间隔，分钟止盈用
    lot_id: int = 0  # 同码多笔：各自成本/峰值
    pending_exit: str = ""  # 日线止盈：次日开盘离场原因
    reserved: bool = False  # 策略 3 涨停保留状态；分钟引擎复用本类


@dataclass
class SimState:
    cash: float = DEFAULT_TOTAL_CASH
    positions: dict = field(default_factory=dict)
    daily_quota_used: float = 0.0
    supplementary_used: float = 0.0
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)
    stats: dict = field(default_factory=_empty_stats)


def _ymd(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y%m%d")


def _at_limit(price: float, limit: float) -> bool:
    """价格≈等于涨/跌停价。买入拦截请用 hit_limit_up（含越过涨停价）。"""
    return abs(price - limit) <= LIMIT_EPS


def hit_limit_up(price: float, limit_up: float) -> bool:
    """买价达到或超过涨停价则不可买（含舍入导致买价高于算出的涨停价）。"""
    return float(price) + LIMIT_EPS >= float(limit_up)


def hit_limit_down(price: float, limit_down: float) -> bool:
    """卖价达到或低于跌停价则不可卖。"""
    return float(price) - LIMIT_EPS <= float(limit_down)


def peak_gap_blocks(gap, peak_gap_min: int = PEAK_GAP_MIN) -> bool:
    """同会话分钟差 < 15 则挡住止盈；隔夜/午休 gap<0 视为满足。"""
    return 0 <= int(gap) < int(peak_gap_min)


def chase_decision(open_px: float, px: float, limit_up: float) -> str:
    """T+1 09:45：市价>开盘且非涨停 → buy；否则 abandon / limit。"""
    if hit_limit_up(px, limit_up):
        return "limit"
    if px > open_px:
        return "buy"
    return "abandon"


def queue_limit_up_chase(st: SimState, pending_chase: dict, code: str, per: float, sig_idx: int) -> None:
    st.stats["skip_limit_up"] += 1
    if code in pending_chase:
        st.stats["chase_overwrite"] += 1
    pending_chase[code] = (per, sig_idx)


def finish_pending_chase(st: SimState, pending_chase: dict) -> None:
    st.stats["chase_pending_eod"] = len(pending_chase)
    st.stats["chase_explained"] = chase_explained(st)


def chase_explained(st: SimState) -> int:
    """涨停跳过应对齐的追买分解合计。"""
    return (
        int(st.stats.get("chase_buy", 0))
        + int(st.stats.get("chase_abandon", 0))
        + int(st.stats.get("chase_skip_limit", 0))
        + int(st.stats.get("chase_no_bar", 0))
        + int(st.stats.get("chase_pending_eod", 0))
        + int(st.stats.get("chase_overwrite", 0))
        + int(st.stats.get("chase_buy_fail", 0))
        + int(st.stats.get("chase_skip_held", 0))
    )


def resolve_limit_prices(
    code: str, prev_close: float, name: str = ""
) -> Optional[tuple[float, float]]:
    return limit_prices(code, prev_close, name)


def last_close_mark(df, day, fallback: float) -> float:
    """最近有 K 的 close；停牌日不用成本价冒充净值。"""
    if df is None:
        return float(fallback)
    if day in df.index:
        return float(df.loc[day]["close"])
    prior = df.loc[df.index < day]
    if prior.empty:
        return float(fallback)
    return float(prior.iloc[-1]["close"])


def _buy_size(per_quota: float, price: float) -> tuple[int, float]:
    """常规额度内最大整百股；不足 100 股用补充资金补足（返回 (shares, supp_used))。"""
    if price <= 0 or per_quota <= 0:
        return 0, 0.0
    shares = int(per_quota / price / 100.0) * 100
    supp = 0.0
    if shares == 0:
        notional = 100 * price
        supp = max(0.0, notional - per_quota)
        shares = 100
    return shares, supp


def execute_buy(
    st: SimState,
    code: str,
    px: float,
    per: float,
    entry_idx: int,
    day,
    *,
    reason: str = "pool",
) -> bool:
    """常规/追买共用：整百股 + force_min + 0.1% 佣金。成功返回 True。"""
    if px <= 0:
        return False
    shares, supp = _buy_size(per, px)
    if shares <= 0:
        return False
    notional = shares * px
    comm = notional * COMMISSION
    if notional + comm > st.cash:
        return False
    st.cash -= notional + comm
    st.daily_quota_used += min(per, notional)
    st.stats["supplementary_used"] += supp
    st.stats["invested_notional"] += notional
    lots = st.positions.setdefault(code, [])
    lot_id = lots[-1].lot_id + 1 if lots else 0
    lots.append(Position(code, shares, px, entry_idx, px, lot_id=lot_id))
    st.trades.append(
        {
            "date": _ymd(day),
            "code": code,
            "side": "BUY",
            "price": px,
            "shares": shares,
            "notional": notional,
            "commission": comm,
            "reason": reason,
            "lot": lot_id,
        }
    )
    st.stats["buys"] += 1
    if lot_id > 0:
        st.stats["add_lots"] += 1
    if reason.startswith("chase"):
        st.stats["chase_buy"] += 1
    return True


def _sell(st: SimState, code: str, pos: Position, px: float, day, reason: str) -> None:
    notional = pos.shares * px
    comm = notional * COMMISSION
    st.cash += notional - comm
    st.trades.append(
        {
            "date": _ymd(day),
            "code": code,
            "side": "SELL",
            "price": px,
            "shares": pos.shares,
            "notional": notional,
            "commission": comm,
            "reason": reason,
            "lot": pos.lot_id,
        }
    )
    if reason.startswith("stop_loss"):
        st.stats["sell_stop"] += 1
    elif reason.startswith("trail"):
        st.stats["sell_trail"] += 1
    elif reason.startswith("profit_take"):
        st.stats["sell_profit_take"] += 1
    elif reason.startswith("open_board"):
        st.stats["sell_open_board"] += 1
    elif reason.startswith("force_sell"):
        st.stats["sell_force"] += 1
    elif reason.startswith("ma_signal"):
        st.stats["sell_ma"] += 1
    else:
        st.stats["sell_pos_trail"] += 1
    lots = st.positions.get(code) or []
    st.positions[code] = [p for p in lots if p is not pos]
    if not st.positions[code]:
        del st.positions[code]
