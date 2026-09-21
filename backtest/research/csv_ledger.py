# -*- coding: utf-8 -*-
"""Shared ledger for CSV daily / minute engines.

Position, SimState, buy/sell fills, and chase accounting live here so the
two simulate loops stay thin. This module must not import either engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from numbers import Integral
from typing import Optional

import pandas as pd

from backtest.research.ashare_fees import (
    COMMISSION,
    QLIB_CLOSE_COST as QLIB_CLOSE_COST,
    QLIB_MIN_COST as QLIB_MIN_COST,
    QLIB_OPEN_COST as QLIB_OPEN_COST,
    trade_commission,
)
from backtest.research.ashare_fill_clock import session_phase as _session_phase
from backtest.research.ashare_session import LIMIT_EPS, hit_limit_down as hit_limit_down, hit_limit_up
from backtest.research.ashare_volume_cap import VolumeCap
from backtest.research.ashare_exdiv_economics import ExDivEconomics
from backtest.research.market_layer import limit_prices

DEFAULT_TOTAL_CASH = 21_000_000.0
PEAK_GAP_MIN = 15
CHASE_HM = 9 * 60 + 45


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
        "skip_index_gate": 0,
        "skip_add_loser": 0,
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
    ride_with: Optional[int] = None  # 跟单：不评卖，父 lot 成交时同价同因出
    is_step: bool = False  # +20% 独立台阶，不占名单加仓、不跟父 lot 同出


@dataclass
class SimState:
    cash: float = DEFAULT_TOTAL_CASH
    positions: dict = field(default_factory=dict)
    daily_quota_used: float = 0.0
    supplementary_used: float = 0.0
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)
    stats: dict = field(default_factory=_empty_stats)
    buy_cost_rate: float = COMMISSION
    sell_cost_rate: float = COMMISSION
    min_cost: float = 0.0
    volume_cap: VolumeCap | None = field(default=None, repr=False, compare=False)
    exdiv_economics: ExDivEconomics | None = field(default=None, repr=False, compare=False)
    book_state: dict = field(default_factory=dict, repr=False, compare=False)
    book_on_buy: object = field(default=None, repr=False, compare=False)
    book_on_exdiv: object = field(default=None, repr=False, compare=False)


def _ymd(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y%m%d")


def _at_limit(price: float, limit: float) -> bool:
    """价格≈等于涨/跌停价。买入拦截请用 hit_limit_up（含越过涨停价）。"""
    return abs(price - limit) <= LIMIT_EPS


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


def queue_limit_up_chase(
    st: SimState, pending_chase: dict, code: str, per: float, sig_idx: int
) -> None:
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


def rescale_position(pos: Position, k: float) -> None:
    """Scale open-lot cost/peak into D-day price domain (ex-div day once).

    peak_hm / shares / pending_exit / reserved are untouched (X-R1).
    """
    factor = float(k)
    if factor <= 0:
        return
    pos.cost = float(pos.cost) * factor
    pos.peak = float(pos.peak) * factor


def apply_exdiv_economics(st: SimState, code: str, ds: str) -> None:
    """Ex-date snapshot before scan/buys; keep refs and lot identity unchanged.

    Bonus shares join their source lot, with a separate list-date T+1 lock.
    They are marked from ex-date, including shares awaiting a later listing.
    """
    account = st.exdiv_economics
    if account is None:
        return
    lots = st.positions.get(code, [])
    callback = ({"on_event": lambda event: st.book_on_exdiv(st, code, event)}
                if callable(st.book_on_exdiv) else {})
    entitlement = account.entitle(code, ds, [p.shares for p in lots], **callback)
    if entitlement is None:
        return
    for pos, added in zip(lots, entitlement.bonus_shares):
        if added:
            pos.shares += added
            date = entitlement.list_date
            locks = account.bonus_locks.setdefault(id(pos), {})
            locks[date] = locks.get(date, 0) + added
    st.cash += account.settle(ds)  # pay_date == ex_date is allowed


def _locked_bonus(account: ExDivEconomics, pos: Position, ds: str) -> int:
    # Same strict date ordering as t1_sellable; a later list_date stays locked.
    return sum(q for acquired, q in account.bonus_locks.get(id(pos), {}).items() if ds <= acquired)


def resolve_limit_prices(
    code: str, prev_close: float, name: str = ""
) -> Optional[tuple[float, float]]:
    return limit_prices(code, prev_close, name)


def market_close_mark(df, day) -> Optional[float]:
    """Data-driven close for ``day`` (or last prior bar).

    Returns ``None`` when ``df`` is missing or has no bar on/before ``day``.
    Callers that need a lot-cost fallback use ``last_close_mark``.
    """
    if df is None:
        return None
    if day in df.index:
        return float(df.loc[day]["close"])
    prior = df.loc[df.index < day]
    if prior.empty:
        return None
    return float(prior.iloc[-1]["close"])


def last_close_mark(df, day, fallback: float) -> float:
    """最近有 K 的 close；停牌日不用成本价冒充净值。"""
    m = market_close_mark(df, day)
    return float(fallback) if m is None else m


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
    ride_with: Optional[int] = None,
    is_step: bool = False,
    bucket_id: int | None = None,
    shares_override: int | None = None,
    at: int | None = None,
) -> bool:
    """常规/追买共用；open 调用方显式传 at，默认仍为 bucket 收盘。"""
    if px <= 0:
        return False
    if shares_override is None:
        shares, supp = _buy_size(per, px)
    else:
        if isinstance(shares_override, bool) or not isinstance(shares_override, Integral):
            raise ValueError("shares_override must be an integer share count")
        shares, supp = max(0, int(shares_override)) // 100 * 100, 0.0
        per = shares * px
    if shares <= 0:
        return False
    notional = shares * px
    comm = trade_commission(notional, st.buy_cost_rate, st.min_cost)
    if notional + comm > st.cash:
        return False
    if st.volume_cap is not None:
        key = (code, _ymd(day), bucket_id)
        shares, skip = st.volume_cap.clamp(
            key, bucket_id if at is None else at, shares, buy=True,
        )
        if not shares:
            _volume_skip(st, code, px, day, skip, bucket_id)
            return False
        notional = shares * px
        comm = trade_commission(notional, st.buy_cost_rate, st.min_cost)
        if shares_override is not None:
            per = notional
        supp = max(0.0, notional - per)
    st.cash -= notional + comm
    st.daily_quota_used += min(per, notional)
    st.stats["supplementary_used"] += supp
    st.stats["invested_notional"] += notional
    lots = st.positions.setdefault(code, [])
    lot_id = lots[-1].lot_id + 1 if lots else 0
    lots.append(
        Position(
            code,
            shares,
            px,
            entry_idx,
            px,
            lot_id=lot_id,
            ride_with=ride_with,
            is_step=bool(is_step) or reason == "add:step20",
        )
    )
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
            "session_phase": "",
            "price_rule": "",
        }
    )
    st.stats["buys"] += 1
    if lot_id > 0:
        st.stats["add_lots"] += 1
    if reason.startswith("chase"):
        st.stats["chase_buy"] += 1
    if st.volume_cap is not None:
        st.volume_cap.consume(key, shares)
    if callable(st.book_on_buy):
        st.book_on_buy(st, code, reason, shares)
    return True


def _volume_skip(st: SimState, code: str, px: float, day, reason: str,
                 bucket_id: int | None) -> None:
    family = reason.split(":", 1)[0]
    st.stats[family] = int(st.stats.get(family, 0)) + 1
    st.trades.append({"date": _ymd(day), "code": code, "side": "SKIP",
                      "price": px, "shares": 0, "notional": 0.0,
                      "commission": 0.0, "reason": reason, "bucket": bucket_id,
                      "session_phase": "", "price_rule": ""})


def _sell(st: SimState, code: str, pos: Position, px: float, day, reason: str, *,
          bucket_id: int | None = None, at: int | None = None,
          day_i: int | None = None, hm: int | None = None,
          session_phase: str = "", price_rule: str = "",
          wanted_shares: int | None = None) -> int:
    shares = pos.shares
    if wanted_shares is not None:
        if isinstance(wanted_shares, bool) or not isinstance(wanted_shares, Integral):
            raise ValueError("wanted_shares must be an integer share count")
        if day_i is None or pos.entry_idx >= day_i or wanted_shares <= 0:
            return 0
    if st.exdiv_economics is not None:
        ds = _ymd(day)
        group = [pos] + [p for p in st.positions.get(code, [])
                         if p.ride_with == pos.lot_id and p is not pos]
        # Linked exits remain atomic; wait for all bonus shares to unlock.
        if (len(group) > 1 or pos.ride_with is not None) and any(
            _locked_bonus(st.exdiv_economics, p, ds) for p in group
        ):
            st.stats["exdiv_econ_defer_linked_t1"] = st.stats.get("exdiv_econ_defer_linked_t1", 0) + 1
            return 0
        shares -= _locked_bonus(st.exdiv_economics, pos, ds)
        if st.volume_cap is not None and pos.pending_exit and shares < pos.shares:
            # δ5 pending exits are all-or-none, including when bonus is locked.
            st.stats["exdiv_econ_defer_pending_t1"] = st.stats.get("exdiv_econ_defer_pending_t1", 0) + 1
            return 0
        if shares <= 0:
            return 0
    if wanted_shares is not None:
        shares = min(shares, int(wanted_shares))
    if shares <= 0:
        return 0
    if st.volume_cap is not None:
        # Linked exits stay atomic: no orphan riders or new pending queues.
        group = [pos] + [p for p in st.positions.get(code, [])
                         if p.ride_with == pos.lot_id and p is not pos]
        child_ids = {p.lot_id for p in group if p is not pos}
        if any(p.ride_with in child_ids for p in st.positions.get(code, [])):
            _volume_skip(st, code, px, day, "skip_volume_cap:unsupported_ride_tree", bucket_id)
            return 0
        if day_i is None or any(p.entry_idx >= day_i for p in group):
            _volume_skip(st, code, px, day, "skip_volume_cap:t1", bucket_id)
            return 0
        key = (code, _ymd(day), bucket_id)
        wanted = shares if len(group) == 1 else sum(p.shares for p in group)
        allocated, skip = st.volume_cap.clamp(
            key, bucket_id if at is None else at, wanted,
            atomic=len(group) > 1 or pos.ride_with is not None or bool(pos.pending_exit),
        )
        if not allocated:
            _volume_skip(st, code, px, day, skip, bucket_id)
            return 0
        shares = min(shares, allocated)
    notional = shares * px
    comm = trade_commission(notional, st.sell_cost_rate, st.min_cost)
    st.cash += notional - comm
    # Human GO P2=B: annotate only after fill eligibility/price/size are settled.
    if hm is not None and not session_phase:
        try:
            session_phase = _session_phase(hm).value
        except ValueError:
            pass  # Unknown phase must never reject an otherwise valid fill.
    st.trades.append(
        {
            "date": _ymd(day),
            "code": code,
            "side": "SELL",
            "price": px,
            "shares": shares,
            "notional": notional,
            "commission": comm,
            "reason": reason,
            "lot": pos.lot_id,
            "session_phase": session_phase,
            "price_rule": price_rule,
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
    if st.volume_cap is not None:
        st.volume_cap.consume(key, shares)
    # S1: every booked sell decrements shares, including the default path.
    pos.shares -= shares
    if st.exdiv_economics is not None:
        locks = st.exdiv_economics.bonus_locks.pop(id(pos), {})
        if pos.shares and (locked := {d: q for d, q in locks.items() if ds <= d}):
            st.exdiv_economics.bonus_locks[id(pos)] = locked
    if pos.shares:
        return shares
    lots = st.positions.get(code) or []
    st.positions[code] = [p for p in lots if p is not pos]
    if not st.positions[code]:
        del st.positions[code]
    if getattr(pos, "ride_with", None) is not None:
        return shares
    riders = [
        p
        for p in (st.positions.get(code) or [])
        if getattr(p, "ride_with", None) == pos.lot_id
    ]
    for child in riders:
        _sell(st, code, child, px, day, reason,
              bucket_id=bucket_id, at=at, day_i=day_i, hm=hm,
              session_phase=session_phase, price_rule=price_rule)
    return shares
