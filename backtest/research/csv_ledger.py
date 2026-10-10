# -*- coding: utf-8 -*-
"""Shared ledger for CSV daily / minute engines.

Position, SimState, buy/sell fills, and chase accounting live here so the
two simulate loops stay thin. This module must not import either engine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from numbers import Integral
from typing import Optional

import pandas as pd

from backtest.research.ashare_fees import (
    COMMISSION,
    FeeSchedule,
    QLIB_CLOSE_COST as QLIB_CLOSE_COST,
    QLIB_MIN_COST as QLIB_MIN_COST,
    QLIB_OPEN_COST as QLIB_OPEN_COST,
    trade_commission,
)
from backtest.research.ashare_fill_clock import session_phase as _session_phase
from backtest.research.ashare_session import (
    LIMIT_EPS,
    defer_sell_at_limit,
    hit_limit_down as hit_limit_down,
    hit_limit_up,
)
from backtest.research.ashare_volume_cap import VolumeCap
from backtest.research.ashare_exdiv_economics import ExDivEconomics
from backtest.research.book_capabilities import uses_s8_independent as _uses_s8_independent
from backtest.research.market_layer import (
    buy_quantity_market,
    limit_prices,
    transfer_fee_market,
)
from backtest.research.minute_audit import record_fill, record_rejection
from backtest.research.ledger_math import (
    FeeAccumulator,
    StampDutyAccumulator,
    TransferFeeAccumulator,
)
from backtest.research.lot_rounding import (
    BOARD_LOT,
    STAR_MIN_DECLARE,
    budget_buy_quantity,
    budget_board_lots,
    budget_integer_shares,
    buy_quantity_increment,
    buy_quantity_minimum,
    buy_quantity_rule,
    nonnegative_override_buy_quantity,
    nonnegative_override_board_lots,
    supplementary_notional,
)
from backtest.research.tail_window_buy import fee_aware_buy_quantity

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
        "skip_st": 0,
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
class IndependentPosition(Position):
    """Only the selected per-name 8.x books add identity to lot snapshots."""

    position_id: str = ""
    entry_signal_date: str = ""


@dataclass
class IndependentGroup:
    code: str
    entry_signal_date: str
    budget: float
    first_lot: IndependentPosition
    next_lot_id: int = 1
    executed_steps: int = 0
    scale_steps: int = 0  # 分批减仓已卖档数（6.13+）
    peak_dd_start: int | None = None  # 回撤 >15% 起始日 idx（6.14 峰值兜底）
    executed_steps2: int = 0  # 第二梯子（基数腿）计数，仅双梯子书使用
    anchor_cost: float | None = None  # 梯子/止损锚价；None = 首仓成本（默认）
    supplement_done: bool = False
    last_add_date: str = ""
    closed: bool = False
    exit_day_idx: int | None = None
    t1_deferred_bonus_lots: set[int] = field(default_factory=set)
    cont_open: dict[int, float] = field(default_factory=dict)
    cont_rebuy_armed: list[float] = field(default_factory=list)
    cont_rebuy_done: list[float] = field(default_factory=list)


class IndependentExitPosition:
    """Live exit view of one signal group, without changing its fill lots.

    Costs use the same commission-exclusive fill-price convention as Position.
    The first lot remains the entry/peak/pending anchor even after a partial
    T+1 exit removes it from the ledger. Price adds keep that original anchor.
    """

    def __init__(self, st, position_id: str, group: IndependentGroup, day_i=None, *, day=None):
        self.st = st
        self.position_id = position_id
        self.group = group
        self.day_i = day_i
        self.day = day  # Original-exit lock attribution only; not a fill-lot field.

    @property
    def lots(self):
        return [
            p for p in self.st.positions.get(self.code, [])
            if getattr(p, "position_id", None) == self.position_id
        ]

    @property
    def code(self):
        return self.group.code

    @property
    def entry_signal_date(self):
        return self.group.entry_signal_date

    @property
    def shares(self):
        return sum(p.shares for p in self.lots)

    @property
    def cost(self):
        anchor = (s8_policy(self.st) or {}).get("cost_anchor", "weighted")
        if anchor == "first_lot":
            # 6.x 书：step 加仓仅同进同出，不进止损/梯子的成本基数。
            # v6.11 突破书：锚 = 信号日 A0（T0 收盘），优先于首仓成交价。
            base = getattr(self.group, "anchor_cost", None)
            return float(base) if base else float(self.group.first_lot.cost)
        lots = self.lots
        if len(lots) == 1:
            return lots[0].cost  # Preserve single-lot float boundaries exactly.
        shares = sum(p.shares for p in lots)
        return (
            sum(p.shares * p.cost for p in lots) / shares
            if shares else self.group.first_lot.cost
        )

    @property
    def entry_idx(self):
        return self.group.first_lot.entry_idx

    @property
    def lot_id(self):
        return self.group.first_lot.lot_id

    @property
    def ride_with(self):
        return None

    @property
    def is_step(self):
        return False

    @property
    def peak(self):
        return self.group.first_lot.peak

    @peak.setter
    def peak(self, value):
        self.group.first_lot.peak = value

    @property
    def peak_hm(self):
        return self.group.first_lot.peak_hm

    @peak_hm.setter
    def peak_hm(self, value):
        self.group.first_lot.peak_hm = value

    @property
    def reserved(self):
        return self.group.first_lot.reserved

    @reserved.setter
    def reserved(self, value):
        self.group.first_lot.reserved = value

    @property
    def pending_exit(self):
        return self.group.first_lot.pending_exit

    @pending_exit.setter
    def pending_exit(self, value):
        if value and not self.group.first_lot.pending_exit:
            self.group.exit_day_idx = self.day_i
            if self.day is not None and self.st.exdiv_economics is not None:
                # Some daily exits latch without attempting a fill that day.
                self.group.t1_deferred_bonus_lots.update(
                    p.lot_id for p in self.lots
                    if _locked_bonus(self.st.exdiv_economics, p, _ymd(self.day))
                )
        elif not value:
            self.group.exit_day_idx = None
            self.group.t1_deferred_bonus_lots.clear()
        self.group.first_lot.pending_exit = value


class InsufficientCashError(RuntimeError):
    """The account cannot fund the actual whole-lot order notional plus fees."""

    def __init__(self, *, date: str, code: str, needed: float, available: float):
        self.date = date
        self.code = code
        self.needed = float(needed)
        self.available = float(available)
        self.shortfall = self.needed - self.available
        super().__init__(
            f"InsufficientCashError: date={date} code={code} "
            f"needed={self.needed:.8f} available={self.available:.8f} "
            f"shortfall={self.shortfall:.8f}"
        )


def reject_short_cash_override(hooks: dict, entry: str) -> None:
    """Dedicated engines retain their frozen cash and counting contracts."""
    if "on_short_cash" in hooks:
        raise ValueError(f"on_short_cash is unsupported for {entry}")


def resolve_buy_cash_mode(st, hooks: dict) -> None:
    """Resolve after policy binding; keep configuration out of snapshots."""
    default_mode = (
        "raise"
        if getattr(st, "book_state", {}).get("s8_independent") is not None
        else "skip"
    )
    if "on_short_cash" in hooks:
        mode = hooks["on_short_cash"]
        if mode not in ("raise", "skip"):
            raise ValueError("on_short_cash must be 'raise' or 'skip'")
        if uses_shrink_on_short_cash(st) and mode != default_mode:
            raise ValueError(
                "rule_profile='industry' shrink_on_short_cash conflicts with "
                f"explicit non-default on_short_cash={mode!r}; remove the override"
            )
    else:
        mode = default_mode
    st.on_short_cash = mode


def configure_s8(st, hooks: dict) -> None:
    if hooks.get("name") == "version9_2":
        reject_short_cash_override(hooks, "strategy9_2_engine")
    _configure_s8(st, hooks)
    resolve_buy_cash_mode(st, hooks)


def check_buy_cash(st, *, needed, available, date, code) -> bool:
    """Decide an existing whole-order debit without counting or resizing."""
    if needed > available:
        mode = getattr(st, "on_short_cash", None)
        if mode is None:
            mode = "raise" if s8_policy(st) is not None else "skip"
        if mode == "raise":
            raise InsufficientCashError(
                date=date, code=code, needed=needed, available=available,
            )
        return False
    return True


def uses_s8_independent(name: str | None, sizing: str | None) -> bool:
    """True iff this book should bind S8 and default on_short_cash to raise."""
    return _uses_s8_independent(name, sizing)


def _configure_s8(st, hooks: dict) -> None:
    """Bind the selected per-name hooks once, including direct shared-loop use."""
    name = hooks.get("name")
    if not uses_s8_independent(name, hooks.get("sizing")):
        return
    if s8_policy(st) is not None:
        return
    st.book_state["s8_independent"] = {
        "name": name,
        "name_budget": float(hooks["name_budget"]),
        "allow_new_name": hooks.get("allow_new_name"),
        "add_step": float(hooks.get("add_step") or 0.20),
        "step_frac": float(hooks.get("step_frac") or 1.0),
        "cost_anchor": str(hooks.get("cost_anchor") or "weighted"),
        "step_cap": hooks.get("step_cap"),  # per-code step lot cap; None = unlimited
        "code_steps": {},
        "add_step2": hooks.get("add_step2"),  # 第二梯子档距；None = 单梯子（v8 系）
        "step_frac2": hooks.get("step_frac2"),
        "tranche_max": hooks.get("tranche_max"),  # 第一梯子（分批腿）每组上限笔数
        "add_offset": int(hooks.get("add_offset") or 0),  # 首档前跳过的档数（v6.11）
        "add_schedule": hooks.get("add_schedule"),  # [(阈值涨幅, 占基数比)]（v6.18）
        # "peak" = 组峰值触发档位（v6.49）；None/其他 = 现价对首仓成本的涨幅触发
        "add_schedule_trigger": hooks.get("add_schedule_trigger"),
        "base_zone_caps": hooks.get("base_zone_caps"),  # (涨幅<100% 上限, ≥100% 上限)
        "cont_stop_rebuy": bool(hooks.get("cont_stop_rebuy")),
        "cont_from_rise": hooks.get("cont_from_rise"),
        "cont_stop_rebuy_lift": hooks.get("cont_stop_rebuy_lift"),
        "cont_stop_rebuy_frac": hooks.get("cont_stop_rebuy_frac"),
        "cont_stop_rebuy_open_frac": hooks.get("cont_stop_rebuy_open_frac"),
        "cont_stop_rebuy_with_schedule": bool(
            hooks.get("cont_stop_rebuy_with_schedule")
        ),
        "min_lot_top_up": bool(hooks.get("min_lot_top_up")),
        "index_blocks_s8_add": bool(hooks.get("index_blocks_s8_add")),
        "groups": {},
    }


def s8_policy(st):
    return st.book_state.get("s8_independent")


def _identity_tagged(bucket, pos) -> bool:
    return any(item is pos for item in bucket)


def _tag_identity(bucket, pos) -> None:
    if not _identity_tagged(bucket, pos):
        bucket.append(pos)


def is_parking_lot(st, pos) -> bool:
    """True for cash-sleeve lots that must not take strategy exits.

    Tags the Position object, not ``id(pos)``. CPython reuses freed ids, so a
    later strategy lot can be skipped by index_cut / skim if only the integer
    address is stored.
    """
    return _identity_tagged(st.book_state.get("parking_lot_ids", ()), pos)


def is_principal_lot(st, pos) -> bool:
    """True for skim-locked 600036 lots that stay in NAV as 本金."""
    return _identity_tagged(st.book_state.get("parking_principal_ids", ()), pos)


def parking_lots(st, symbol: str) -> list:
    return [p for p in st.positions.get(symbol, []) if is_parking_lot(st, p)]


def sleeve_parking_lots(st, symbol: str) -> list:
    return [p for p in parking_lots(st, symbol) if not is_principal_lot(st, p)]


def principal_parking_lots(st, symbol: str) -> list:
    return [p for p in parking_lots(st, symbol) if is_principal_lot(st, p)]


def unpark_parking_lots(st, symbol: str) -> list:
    """Idle sleeve first, then lock. 6.50/6.51 have sleeve only."""
    return sleeve_parking_lots(st, symbol) + principal_parking_lots(st, symbol)


def register_parking_lot(st, pos) -> None:
    _tag_identity(st.book_state.setdefault("parking_lot_ids", []), pos)


def register_principal_lot(st, pos) -> None:
    register_parking_lot(st, pos)
    _tag_identity(st.book_state.setdefault("parking_principal_ids", []), pos)


def note_cont_open(group: IndependentGroup, lot_id: int, rise: float, *, from_rise: float) -> None:
    """Remember a live continuation-tranche lot so a later step-stop can re-arm it."""
    if float(rise) + 1e-12 >= float(from_rise):
        group.cont_open[int(lot_id)] = float(rise)


def arm_cont_stop_rebuy(st, group: IndependentGroup | None, lot_id: int) -> bool:
    """Move a fully stopped continuation lot onto the group's one-shot rebuy queue."""
    policy = s8_policy(st)
    if group is None or not policy or not policy.get("cont_stop_rebuy"):
        return False
    rise = group.cont_open.pop(int(lot_id), None)
    if rise is None or rise in group.cont_rebuy_armed or rise in group.cont_rebuy_done:
        return False
    group.cont_rebuy_armed.append(float(rise))
    st.stats["arm_cont_rebuy"] = int(st.stats.get("arm_cont_rebuy", 0)) + 1
    return True


def held_codes(st) -> list[str]:
    """Lexicographic live codes. Cash-competing loops must not use insert order."""
    return sorted(st.positions)


def held_position_items(st) -> list[tuple[str, list]]:
    """``(code, lots)`` in ``held_codes`` order. Lots stay in ledger list order."""
    return [(code, list(st.positions[code])) for code in held_codes(st)]


def s8_open_groups(st, code: str):
    """Visit each live signal group once, sorted by position_id."""
    policy = s8_policy(st)
    if policy is None:
        return
    seen = set()
    rows = []
    for pos in st.positions.get(code, []):
        if is_parking_lot(st, pos):
            continue
        position_id = getattr(pos, "position_id", None)
        if position_id is None or position_id in seen:
            continue
        seen.add(position_id)
        group = policy["groups"][position_id]
        if not group.closed:
            rows.append((position_id, group))
    rows.sort(key=lambda item: item[0])
    yield from rows


def position_identity(pos) -> dict:
    if isinstance(pos, (IndependentPosition, IndependentExitPosition)):
        return {"position_id": pos.position_id, "entry_signal_date": pos.entry_signal_date}
    return {}


def exit_positions(st, code: str, day_i: int | None = None, *, day=None) -> list:
    """Return aggregate exit views only for the six independent-position books."""
    if s8_policy(st) is None:
        return list(st.positions.get(code, []))
    return [
        IndependentExitPosition(st, position_id, group, day_i, day=day)
        for position_id, group in s8_open_groups(st, code)
    ]


def held_fill_key(pos):
    """Stable group ID or a lifetime token retained by its lot (never recycled)."""
    position_id = getattr(pos, "position_id", None)
    if position_id:
        return position_id
    if not hasattr(pos, "_held_fill_token"):
        pos._held_fill_token = object()
    return pos._held_fill_token


def lot_identity(pos):
    """Per-object token for same-day maps. Not CPython's recycled ``id(pos)``."""
    token = getattr(pos, "_lot_identity", None)
    if token is None:
        token = object()
        pos._lot_identity = token
    return token


def position_is_open(st, pos) -> bool:
    if isinstance(pos, IndependentExitPosition):
        return not pos.group.closed and pos.shares > 0
    return any(p is pos for p in st.positions.get(pos.code, []))


def rescale_s8_groups(st, code: str, k: float) -> None:
    """Rescale a retained entry anchor only when its lot has already exited.

    Live entry lots are rescaled by the engine's existing per-lot loop.
    """
    live_ids = {id(p) for p in st.positions.get(code, [])}
    for _position_id, group in s8_open_groups(st, code):
        if group.anchor_cost:
            group.anchor_cost *= float(k)
        if id(group.first_lot) not in live_ids:
            rescale_position(group.first_lot, k)


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
    star_lot_declare_check: bool = field(default=False, repr=False, compare=False, kw_only=True)

    def __post_init__(self):
        # Runtime diagnostics deliberately stay outside dataclasses.asdict:
        # account snapshots and the frozen OFF artifacts must not gain fields.
        self.on_short_cash = None
        self.sell_pending_events = []
        self.sell_pending_open = []
        self._sell_pending_history = {}


def bind_account_fee_schedule(st, schedule: FeeSchedule) -> None:
    """Bind an opt-in runtime schedule without changing SimState snapshots."""
    if not schedule.per_order:
        raise ValueError("account fee schedule must use per-order commission")
    st.account_fee_schedule = schedule
    st._fee_accumulators = {
        "BUY": FeeAccumulator(schedule.buy_rate, schedule.min_cost),
        "SELL": FeeAccumulator(schedule.sell_rate, schedule.min_cost),
    }
    st._stamp_duty_accumulator = (
        StampDutyAccumulator() if schedule.dated_sell_stamp_duty else None
    )
    st._transfer_fee_accumulator = (
        TransferFeeAccumulator() if schedule.dated_bilateral_transfer_fee else None
    )
    st._fee_totals = {"commission": 0.0, "stamp_duty": 0.0, "transfer_fee": 0.0}
    st._fee_order_rows = {}
    st._fee_order_keys = {}
    st._fee_order_seq = 0
    st.buy_cost_rate = schedule.buy_rate
    st.sell_cost_rate = schedule.sell_rate
    st.min_cost = schedule.min_cost
    if not hasattr(st, "stats"):
        st.stats = {}
    if schedule.dated_sell_stamp_duty:
        st.stats["stamp_duty_total"] = 0.0
    if schedule.dated_bilateral_transfer_fee:
        st.stats["transfer_fee_total"] = 0.0


def fee_order_id(st, key=None):
    """Return a unique order id, optionally retained by a continuation key."""
    if not hasattr(st, "_fee_accumulators"):
        return None
    if key is not None and key in st._fee_order_keys:
        return st._fee_order_keys[key]
    st._fee_order_seq += 1
    order_id = st._fee_order_seq
    if key is not None:
        st._fee_order_keys[key] = order_id
    return order_id


def release_fee_order(st, key) -> None:
    if hasattr(st, "_fee_order_keys"):
        st._fee_order_keys.pop(key, None)


def preview_order_fees(
    st, side: str, order_id, notional: float, trade_date=None, symbol: str | None = None
) -> float:
    """Preview the total fee delta for one order fill without mutating state."""
    commission = st._fee_accumulators[side].preview(order_id, notional).fee_delta
    stamp_duty = 0.0
    if side == "SELL" and st._stamp_duty_accumulator is not None:
        if trade_date is None:
            raise ValueError("sell stamp duty requires a trade date")
        stamp_duty = st._stamp_duty_accumulator.preview(
            order_id, notional, trade_date
        ).fee_delta
    transfer_fee = 0.0
    if st._transfer_fee_accumulator is not None:
        if trade_date is None or symbol is None:
            raise ValueError("transfer fee requires trade date and symbol")
        transfer_fee = st._transfer_fee_accumulator.preview(
            order_id, notional, transfer_fee_market(symbol), trade_date
        ).fee_delta
    return commission + stamp_duty + transfer_fee


def _accrue_order_fee(st, side: str, order_id, row: dict) -> float:
    """Book one fill and rewrite per-order commission and stamp allocations."""
    accumulator = st._fee_accumulators[side]
    rows = st._fee_order_rows.setdefault(order_id, [])
    rows.append(row)
    accrual = accumulator.add_fill(order_id, row["notional"])
    for fill, commission in zip(rows, accrual.allocations):
        fill["commission"] = commission
    stamp_delta = 0.0
    if side == "SELL" and st._stamp_duty_accumulator is not None:
        stamp = st._stamp_duty_accumulator.add_fill(
            order_id, row["notional"], row["date"]
        )
        for fill, amount in zip(rows, stamp.allocations):
            fill["stamp_duty"] = amount
        stamp_delta = stamp.fee_delta
    elif st.account_fee_schedule.dated_sell_stamp_duty:
        for fill in rows:
            fill["stamp_duty"] = 0.0
    transfer_delta = 0.0
    if st._transfer_fee_accumulator is not None:
        symbol = row.get("code", row.get("symbol"))
        transfer = st._transfer_fee_accumulator.add_fill(
            order_id,
            row["notional"],
            transfer_fee_market(symbol),
            row["date"],
        )
        for fill, amount in zip(rows, transfer.allocations):
            fill["transfer_fee"] = amount
        transfer_delta = transfer.fee_delta
    st._fee_totals["commission"] += accrual.fee_delta
    st._fee_totals["stamp_duty"] += stamp_delta
    st._fee_totals["transfer_fee"] += transfer_delta
    if st.account_fee_schedule.dated_sell_stamp_duty:
        st.stats["stamp_duty_total"] = st._fee_totals["stamp_duty"]
    if st.account_fee_schedule.dated_bilateral_transfer_fee:
        st.stats["transfer_fee_total"] = st._fee_totals["transfer_fee"]
    return accrual.fee_delta + stamp_delta + transfer_delta


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
    st: SimState, pending_chase: dict, code: str, per: float, sig_idx: int,
    *, entry_signal_date: str | None = None,
) -> None:
    st.stats["skip_limit_up"] += 1
    key = f"{code}@{entry_signal_date}" if entry_signal_date is not None else code
    if key in pending_chase:
        st.stats["chase_overwrite"] += 1
    pending_chase[key] = (per, sig_idx)


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


def apply_exdiv_economics(st: SimState, code: str, ds: str) -> float:
    """Ex-date snapshot before scan/buys; keep refs and lot identity unchanged.

    Bonus shares join their source lot, with a separate list-date T+1 lock.
    They are marked from ex-date, including shares awaiting a later listing.
    Returns cash posted on this call (same-day pay or 0).
    """
    account = st.exdiv_economics
    if account is None:
        return 0.0
    lots = st.positions.get(code, [])
    callback = ({"on_event": lambda event: st.book_on_exdiv(st, code, event)}
                if callable(st.book_on_exdiv) else {})
    entitlement = account.entitle(code, ds, [p.shares for p in lots], **callback)
    if entitlement is None:
        return 0.0
    for pos, added in zip(lots, entitlement.bonus_shares):
        if added:
            pos.shares += added
            date = entitlement.list_date
            locks = account.locks_for(pos)
            locks[date] = locks.get(date, 0) + added
    posted = account.settle(ds)  # pay_date == ex_date is allowed
    st.cash += posted
    return float(posted)


def _locked_bonus(account: ExDivEconomics, pos: Position, ds: str) -> int:
    # Same strict date ordering as t1_sellable; a later list_date stays locked.
    return sum(q for acquired, q in account.peek_locks(pos).items() if ds <= acquired)


def resolve_limit_prices(
    code: str, prev_close: float, name: str = "", as_of=None
) -> Optional[tuple[float, float]]:
    return limit_prices(code, prev_close, name, as_of=as_of)


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


def _buy_size(
    per_quota: float,
    price: float,
    *,
    star_declare: bool = False,
    top_up_min_lot: bool = True,
) -> tuple[int, float]:
    """Size a buy; legacy may top up one board lot, industry B8-03 may not."""
    if price <= 0 or per_quota <= 0:
        return 0, 0.0
    if star_declare:
        # D23 X-10: integer shares, min 200 checked at entry; no top-up.
        return budget_integer_shares(per_quota, price), 0.0
    shares = budget_board_lots(per_quota, price)
    supp = 0.0
    if shares == 0 and top_up_min_lot:
        notional = BOARD_LOT * price
        supp = supplementary_notional(notional, per_quota)
        shares = BOARD_LOT
    return shares, supp


def allows_min_lot_top_up(st) -> bool:
    """Return whether one board lot may be funded from the cash pool.

    Book/CLI ``min_lot_top_up`` is the business switch (6.50+ default on).
    Industry B8-03 stays off unless that switch is on.
    """
    policy = s8_policy(st)
    if policy and bool(policy.get("min_lot_top_up")):
        return True
    return not bool(
        getattr(getattr(st, "rule_profile", None), "supplementary_min_lot", False)
    )


def uses_fee_aware_affordability(st) -> bool:
    """Return whether buy declarations must include all industry buy fees."""
    return bool(
        getattr(getattr(st, "rule_profile", None), "fee_aware_affordability", False)
    )


def uses_shrink_on_short_cash(st) -> bool:
    """Return whether short cash shrinks the declaration instead of using B7."""
    return bool(
        getattr(getattr(st, "rule_profile", None), "shrink_on_short_cash", False)
    )


def uses_exchange_quantity_rules(st) -> bool:
    """Return whether exchange-specific buy declarations are active."""
    return bool(
        getattr(getattr(st, "rule_profile", None), "exchange_quantity_rules", False)
    )


def uses_account_odd_lot_exit(st) -> bool:
    """Return whether partial sells must absorb an account-level odd remainder."""
    return bool(
        getattr(getattr(st, "rule_profile", None), "account_odd_lot_exit", False)
    )


def sell_board_lot(code: str) -> int:
    """Return the remainder threshold used by an account-level sell order."""
    return STAR_MIN_DECLARE if buy_quantity_market(code) == "STAR" else BOARD_LOT


def account_sell_quantity(
    st: SimState, code: str, held_shares: int, wanted_shares: int
) -> int:
    """Expand a partial order to include the whole sub-lot account remainder.

    Lot-row allocation happens after this calculation.  This deliberately
    avoids applying the rule independently to each source lot.
    """
    held = max(0, int(held_shares))
    wanted = max(0, int(wanted_shares))
    if not uses_account_odd_lot_exit(st):
        return wanted
    if wanted == 0 or wanted >= held:
        return wanted
    remainder = held - wanted
    if 0 < remainder < sell_board_lot(code):
        return held
    return wanted


def active_buy_quantity_rule(st, code: str) -> str:
    """Resolve the exact declaration rule used by preview and execution."""
    return buy_quantity_rule(
        buy_quantity_market(code),
        exchange_quantity_rules=uses_exchange_quantity_rules(st),
        star_lot_declare_check=st.star_lot_declare_check,
    )


def preview_buy_declaration(
    st: SimState,
    code: str,
    px: float,
    per: float,
    *,
    shares_override: int | None = None,
) -> tuple[int, float, int, str]:
    """Return final declared shares before any volume-cap partial fill.

    Loop cash gates call this same primitive as ``execute_buy`` so B8-12 cannot
    check a board-lot quantity and later submit a different STAR/BSE quantity.
    """
    rule = active_buy_quantity_rule(st, code)
    if shares_override is None:
        if buy_quantity_increment(rule) == BOARD_LOT:
            shares, supp = _buy_size(
                per,
                px,
                top_up_min_lot=allows_min_lot_top_up(st),
            )
        elif px <= 0 or per <= 0:
            shares, supp = 0, 0.0
        else:
            shares, supp = budget_buy_quantity(per, px, rule), 0.0
            if allows_min_lot_top_up(st) and shares < BOARD_LOT:
                shares = BOARD_LOT
                supp = supplementary_notional(shares * px, per)
    else:
        if isinstance(shares_override, bool) or not isinstance(shares_override, Integral):
            raise ValueError("shares_override must be an integer share count")
        shares = nonnegative_override_buy_quantity(shares_override, rule)
        supp = 0.0
    wanted_shares = shares
    return shares, supp, wanted_shares, rule


def preview_final_buy_declaration(
    st: SimState,
    code: str,
    px: float,
    per: float,
    day,
    *,
    shares_override: int | None = None,
) -> tuple[int, float, int, str]:
    """Preview the fee-aware final declaration for one strategy order."""
    shares, supp, wanted_shares, rule = preview_buy_declaration(
        st, code, px, per, shares_override=shares_override
    )
    if uses_fee_aware_affordability(st) and shares > 0:
        topped = supp > 0 and allows_min_lot_top_up(st)
        budget = float(st.cash) if topped else per
        cash_cap = st.cash if (topped or uses_shrink_on_short_cash(st)) else per
        shares = fee_aware_buy_quantity(
            shares,
            px,
            budget,
            cash_cap,
            lambda notional: st.account_fee_schedule.debit_buy(notional, day, code),
            increment=buy_quantity_increment(rule),
            minimum=buy_quantity_minimum(rule),
        )
        if topped and shares > 0:
            supp = supplementary_notional(shares * px, per)
        else:
            supp = 0.0
    return shares, supp, wanted_shares, rule


def preview_buy_cash_needed(st: SimState, code: str, px: float, shares: int, day) -> float:
    """Cash debit for the declaration used by loop and ledger pre-checks."""
    notional = shares * px
    if uses_fee_aware_affordability(st):
        return st.account_fee_schedule.debit_buy(notional, day, code)
    return notional + trade_commission(notional, st.buy_cost_rate, st.min_cost)


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
    position_id: str | None = None,
    entry_signal_date: str | None = None,
    merge_lot: Position | None = None,
    hm: int | None = None,
    order_id=None,
) -> bool:
    """常规/追买共用；open 调用方显式传 at，默认仍为 bucket 收盘。"""
    if px <= 0:
        return False
    from backtest.research.st_status import st_blocks_buy

    if st_blocks_buy(st, code, _ymd(day)):
        st.stats["skip_st"] = int(st.stats.get("skip_st", 0)) + 1
        record_rejection(st, code, day, "skip_st", px)
        return False
    policy = s8_policy(st)
    group = None
    if policy is not None:
        if position_id is not None and (
            not isinstance(position_id, str) or "@" not in position_id
        ):
            raise ValueError(
                f"position_id must have the form code@entry_signal_date: {position_id!r}"
            )
        entry_signal_date = entry_signal_date or (
            position_id.split("@", 1)[1] if position_id else _ymd(day)
        )
        position_id = position_id or f"{code}@{entry_signal_date}"
        group = policy["groups"].get(position_id)
        if merge_lot is not None and (
            not isinstance(merge_lot, IndependentPosition)
            or merge_lot.position_id != position_id
            or merge_lot.entry_signal_date != entry_signal_date
            or group is None or group.first_lot is not merge_lot
        ):
            raise ValueError("merge_lot must be the same signal position's initial lot")
        if group is not None and (
            group.closed or group.first_lot.pending_exit
            or reason == "pool" or reason.startswith("chase")
            or (reason == "pool:tail_window" and merge_lot is None)
        ):
            return False  # One initial fill per source signal, even if called twice.
        if reason.startswith("add:") and group is None:
            raise ValueError(f"price add requires an open position_id: {position_id}")
    if merge_lot is not None and (
        merge_lot.code != code or merge_lot.entry_idx != entry_idx
        or not any(lot is merge_lot for lot in st.positions.get(code, []))
    ):
        raise ValueError("merge_lot must be an existing same-code, same-day buy lot")
    no_min_lot_top_up = not allows_min_lot_top_up(st)
    fee_aware = uses_fee_aware_affordability(st)
    shares, supp, wanted_shares, quantity_rule = preview_final_buy_declaration(
        st, code, px, per, day, shares_override=shares_override
    )
    if (
        shares_override is not None
        and buy_quantity_increment(quantity_rule) == BOARD_LOT
    ):
        # Keep the frozen B8 helper call at the ledger boundary; preview and
        # execution intentionally normalize the same explicit declaration.
        normalized_board_override = nonnegative_override_board_lots(shares_override)
        if not fee_aware:
            shares = normalized_board_override
    if shares_override is not None and not fee_aware:
        per = shares * px
    # This is the new buy declaration, not its eventual fill. A later cap may
    # fill <200; a subsequent execute_buy call is a NEW declaration, including
    # residual retries / merge_lot. Held-position sell unwinds stay separate.
    if quantity_rule == "STAR" and shares < STAR_MIN_DECLARE:
        reason_code = "skip_star_buy_declare_qty"
        st.stats[reason_code] = st.stats.get(reason_code, 0) + 1
        record_rejection(st, code, day, reason_code, px)
        return False
    if quantity_rule == "BSE" and shares < BOARD_LOT:
        if shares_override is None and no_min_lot_top_up:
            reason_code = "skip_min_lot_budget"
            st.stats[reason_code] = st.stats.get(reason_code, 0) + 1
            record_rejection(st, code, day, reason_code, px)
        return False
    if shares <= 0:
        if (
            shares_override is None
            and no_min_lot_top_up
            and quantity_rule != "STAR"
            and (
                not fee_aware
                or wanted_shares <= 0
                or fee_aware_buy_quantity(
                    wanted_shares,
                    px,
                    per,
                    per,
                    lambda notional: st.account_fee_schedule.debit_buy(
                        notional, day, code
                    ),
                )
                <= 0
            )
        ):
            reason_code = "skip_min_lot_budget"
            st.stats[reason_code] = st.stats.get(reason_code, 0) + 1
            record_rejection(st, code, day, reason_code, px)
        elif fee_aware:
            record_rejection(st, code, day, "skip_cash", px)
        return False
    per_order_fees = hasattr(st, "_fee_accumulators")
    if per_order_fees:
        order_id = fee_order_id(st) if order_id is None else order_id
    notional = shares * px
    comm = (
        st.account_fee_schedule.buy_fee(notional)
        if per_order_fees
        else trade_commission(notional, st.buy_cost_rate, st.min_cost)
    )
    needed = (
        st.account_fee_schedule.debit_buy(notional, day, code)
        if fee_aware
        else notional + comm
    )
    if needed > st.cash:
        release_parking_cash(st, needed)
    if needed > st.cash + 1e-9 and st.stats.get("parking_open_cover"):
        st.stats["skip_cash"] = int(st.stats.get("skip_cash", 0)) + 1
        st.stats["skip_cash_notional"] = (
            float(st.stats.get("skip_cash_notional", 0.0)) + float(needed)
        )
        record_rejection(st, code, day, "skip_cash", px)
        return False
    if not check_buy_cash(st, needed=needed, available=st.cash,
                          date=_ymd(day), code=code):
        record_rejection(st, code, day, "skip_cash", px)
        return False
    if st.volume_cap is not None:
        key = (code, _ymd(day), bucket_id)
        shares, skip = st.volume_cap.clamp(
            key, bucket_id if at is None else at, shares, buy=True,
        )
        if not shares:
            _volume_skip(st, code, px, day, skip, bucket_id,
                         position_id=position_id, entry_signal_date=entry_signal_date)
            return False
        notional = shares * px
        comm = (
            st.account_fee_schedule.buy_fee(notional)
            if per_order_fees
            else trade_commission(notional, st.buy_cost_rate, st.min_cost)
        )
        if shares_override is not None:
            per = notional
        supp = supplementary_notional(notional, per)
    cash_before = st.cash
    if not per_order_fees:
        st.cash -= notional + comm
    st.daily_quota_used += min(per, notional)
    st.stats["supplementary_used"] += supp
    st.stats["invested_notional"] += notional
    lots = st.positions.setdefault(code, [])
    identity = (
        {"position_id": position_id, "entry_signal_date": entry_signal_date}
        if policy is not None else {}
    )
    if merge_lot is None:
        lot_id = lots[-1].lot_id + 1 if lots else 0
        if policy is not None:
            lot_id = group.next_lot_id if group is not None else 0
        position_type = IndependentPosition if policy is not None else Position
        pos = position_type(
            code,
            shares,
            px,
            entry_idx,
            px,
            lot_id=lot_id,
            ride_with=ride_with,
            is_step=bool(is_step) or reason == "add:step20",
            **identity,
        )
        lots.append(pos)
        if policy is not None:
            if group is None:
                policy["groups"][position_id] = IndependentGroup(
                    code, entry_signal_date, policy["name_budget"], pos,
                )
            else:
                group.next_lot_id += 1
    else:
        lot_id = merge_lot.lot_id
        merge_lot.cost = ((merge_lot.cost * merge_lot.shares + px * shares)
                          / (merge_lot.shares + shares))
        merge_lot.shares += shares
        # Children are one T+0 lot: keep the first fill's peak and its -1 clock.
        # The original scanner starts updating that peak only from T+1.
        # The group's first_lot remains this object, so its price-add anchor is
        # the weighted initial-lot cost known at the time of the add decision.
    trade = {
        "date": _ymd(day),
        "code": code,
        "side": "BUY",
        "price": px,
        "shares": shares,
        "notional": notional,
        "commission": comm if not per_order_fees else 0.0,
        "reason": reason,
        "lot": lot_id,
        "session_phase": "",
        "price_rule": "",
        **identity,
    }
    st.trades.append(trade)
    if per_order_fees:
        comm = _accrue_order_fee(st, "BUY", order_id, trade)
        st.cash -= notional + comm
    if hm is not None:
        # Opt-in tail fills carry their execution clock; OFF keeps its columns.
        st.trades[-1]["hm"] = int(hm)
    record_fill(st, st.trades[-1], cash_before)
    st.stats["buys"] += 1
    if lot_id > 0 and merge_lot is None:
        st.stats["add_lots"] += 1
    if reason.startswith("chase"):
        st.stats["chase_buy"] += 1
    if st.volume_cap is not None:
        st.volume_cap.consume(key, shares)
    if callable(st.book_on_buy):
        st.book_on_buy(st, code, reason, shares)
    return True


def execute_parking_buy(
    st: SimState,
    code: str,
    px: float,
    per: float,
    entry_idx: int,
    day,
    *,
    reason: str = "parking:rebalance",
    bucket_id: int | None = None,
    at: int | None = None,
    hm: int | None = None,
) -> bool:
    """Buy the cash-sleeve name without creating an S8 group or using quota."""
    if px <= 0 or per <= 0:
        return False
    shares, _supp, _wanted, _rule = preview_final_buy_declaration(
        st, code, px, per, day
    )
    if shares <= 0:
        st.stats["skip_parking_size"] = int(st.stats.get("skip_parking_size", 0)) + 1
        return False
    per_order_fees = hasattr(st, "_fee_accumulators")
    order_id = fee_order_id(st) if per_order_fees else None
    notional = shares * px
    fee_aware = uses_fee_aware_affordability(st)
    comm = (
        st.account_fee_schedule.buy_fee(notional)
        if per_order_fees
        else trade_commission(notional, st.buy_cost_rate, st.min_cost)
    )
    needed = (
        st.account_fee_schedule.debit_buy(notional, day, code)
        if fee_aware
        else notional + comm
    )
    if needed > st.cash:
        st.stats["skip_parking_cash"] = int(st.stats.get("skip_parking_cash", 0)) + 1
        return False
    key = (code, _ymd(day), bucket_id)
    if st.volume_cap is not None:
        shares, skip = st.volume_cap.clamp(
            key, bucket_id if at is None else at, shares, buy=True,
        )
        if not shares:
            st.stats["skip_parking_volume"] = int(st.stats.get("skip_parking_volume", 0)) + 1
            _volume_skip(st, code, px, day, skip, bucket_id)
            return False
        notional = shares * px
        comm = (
            st.account_fee_schedule.buy_fee(notional)
            if per_order_fees
            else trade_commission(notional, st.buy_cost_rate, st.min_cost)
        )
    cash_before = st.cash
    if not per_order_fees:
        st.cash -= notional + comm
    lots = st.positions.setdefault(code, [])
    lot_id = lots[-1].lot_id + 1 if lots else 0
    pos = Position(code, shares, px, entry_idx, px, lot_id=lot_id)
    lots.append(pos)
    register_parking_lot(st, pos)
    trade = {
        "date": _ymd(day),
        "code": code,
        "side": "BUY",
        "price": px,
        "shares": shares,
        "notional": notional,
        "commission": comm if not per_order_fees else 0.0,
        "reason": reason,
        "lot": lot_id,
        "session_phase": "",
        "price_rule": "",
    }
    st.trades.append(trade)
    if per_order_fees:
        comm = _accrue_order_fee(st, "BUY", order_id, trade)
        st.cash -= notional + comm
    if hm is not None:
        st.trades[-1]["hm"] = int(hm)
    record_fill(st, st.trades[-1], cash_before)
    st.stats["buys"] += 1
    st.stats["parking_buys"] = int(st.stats.get("parking_buys", 0)) + 1
    st.stats["parking_notional"] = float(st.stats.get("parking_notional", 0.0)) + notional
    if st.volume_cap is not None:
        st.volume_cap.consume(key, shares)
    return True


def release_parking_cash(st: SimState, needed: float) -> None:
    """Sell T+1 parking lots so a strategy buy can debit ``needed`` cash."""
    session = st.book_state.get("parking_session")
    if session is None or needed <= st.cash + 1e-9:
        return
    symbol = session["symbol"]
    px = float(session["px"])
    day_i = int(session["day_i"])
    day = session["day"]
    limits = session["limits"]
    if px <= 0 or not math.isfinite(px):
        return
    if defer_sell_at_limit(px, limits):
        st.stats["skip_parking_limit"] = int(st.stats.get("skip_parking_limit", 0)) + 1
        return
    sold_any = False
    lock_raised = 0.0
    for lot in unpark_parking_lots(st, symbol):
        if st.cash + 1e-9 >= needed:
            break
        if lot.entry_idx >= day_i:
            st.stats["skip_parking_t1"] = int(st.stats.get("skip_parking_t1", 0)) + 1
            continue
        shortfall = needed - st.cash
        raw = int(math.ceil(shortfall / px / BOARD_LOT) * BOARD_LOT)
        chunk = min(int(lot.shares), max(BOARD_LOT, raw))
        draw_lock = is_principal_lot(st, lot)
        cash_before = float(st.cash)
        filled = _sell(
            st,
            symbol,
            lot,
            px,
            day,
            "parking:unpark",
            day_i=day_i,
            wanted_shares=chunk,
            price_rule="parking_daily_close",
        )
        if filled:
            sold_any = True
            st.stats["parking_sold_shares"] = (
                int(st.stats.get("parking_sold_shares", 0)) + int(filled)
            )
            if draw_lock:
                lock_raised += max(0.0, float(st.cash) - cash_before)
    if sold_any:
        st.stats["parking_unpark"] = int(st.stats.get("parking_unpark", 0)) + 1
        st.stats["parking_sells"] = int(st.stats.get("parking_sells", 0)) + 1
        if lock_raised > 1e-6 and st.stats.get("profit_skim_to_parking"):
            st.stats["profit_skim_lock_drawn"] = (
                float(st.stats.get("profit_skim_lock_drawn", 0.0)) + lock_raised
            )


def _volume_skip(st: SimState, code: str, px: float, day, reason: str,
                 bucket_id: int | None, *, position_id: str | None = None,
                 entry_signal_date: str | None = None) -> None:
    family = reason.split(":", 1)[0]
    st.stats[family] = int(st.stats.get(family, 0)) + 1
    identity = (
        {"position_id": position_id, "entry_signal_date": entry_signal_date}
        if s8_policy(st) is not None and position_id is not None else {}
    )
    trade = {"date": _ymd(day), "code": code, "side": "SKIP",
             "price": px, "shares": 0, "notional": 0.0,
             "commission": 0.0, "reason": reason, "bucket": bucket_id,
             "session_phase": "", "price_rule": "", **identity}
    if getattr(getattr(st, "account_fee_schedule", None), "dated_sell_stamp_duty", False):
        trade["stamp_duty"] = 0.0
    if getattr(
        getattr(st, "account_fee_schedule", None), "dated_bilateral_transfer_fee", False
    ):
        trade["transfer_fee"] = 0.0
    st.trades.append(trade)
    record_fill(st, st.trades[-1], st.cash)


def _sell(st: SimState, code: str, pos: Position, px: float, day, reason: str, *,
          bucket_id: int | None = None, at: int | None = None,
          day_i: int | None = None, hm: int | None = None,
          session_phase: str = "", price_rule: str = "",
          wanted_shares: int | None = None, _group_exit: bool = False,
          order_id=None) -> int:
    if isinstance(pos, IndependentExitPosition):
        return _sell_s8_group(
            st, code, pos, px, day, reason,
            bucket_id=bucket_id, at=at, day_i=day_i, hm=hm,
            session_phase=session_phase, price_rule=price_rule,
            wanted_shares=wanted_shares,
        )
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
        if (st.volume_cap is not None and pos.pending_exit and not _group_exit
                and shares < pos.shares):
            # δ5 pending exits are all-or-none, including when bonus is locked.
            st.stats["exdiv_econ_defer_pending_t1"] = st.stats.get("exdiv_econ_defer_pending_t1", 0) + 1
            return 0
        if shares <= 0:
            return 0
    if wanted_shares is not None:
        shares = min(shares, int(wanted_shares))
    if shares <= 0:
        return 0
    requested_shares = shares
    per_order_fees = hasattr(st, "_fee_accumulators")
    order_key = None
    if per_order_fees and order_id is None:
        base_reason = reason.replace(":next_open", "").replace("|t1_deferred", "")
        order_key = ("sell", held_fill_key(pos), base_reason)
        order_id = fee_order_id(st, order_key)
    if st.volume_cap is not None:
        # Linked exits stay atomic: no orphan riders or new pending queues.
        group = [pos] + [p for p in st.positions.get(code, [])
                         if p.ride_with == pos.lot_id and p is not pos]
        child_ids = {p.lot_id for p in group if p is not pos}
        if any(p.ride_with in child_ids for p in st.positions.get(code, [])):
            _volume_skip(st, code, px, day, "skip_volume_cap:unsupported_ride_tree", bucket_id,
                         **position_identity(pos))
            return 0
        if day_i is None or any(p.entry_idx >= day_i for p in group):
            _volume_skip(st, code, px, day, "skip_volume_cap:t1", bucket_id,
                         **position_identity(pos))
            return 0
        key = (code, _ymd(day), bucket_id)
        wanted = shares if len(group) == 1 else sum(p.shares for p in group)
        allocated, skip = st.volume_cap.clamp(
            key, bucket_id if at is None else at, wanted,
            atomic=(len(group) > 1 or pos.ride_with is not None
                    or (bool(pos.pending_exit) and not _group_exit)),
        )
        if not allocated:
            _volume_skip(st, code, px, day, skip, bucket_id, **position_identity(pos))
            return 0
        shares = min(shares, allocated)
    notional = shares * px
    comm = (
        st.account_fee_schedule.sell_fee(notional)
        if per_order_fees
        else trade_commission(notional, st.sell_cost_rate, st.min_cost)
    )
    cash_before = st.cash
    # Human GO P2=B: annotate only after fill eligibility/price/size are settled.
    if hm is not None and not session_phase:
        try:
            session_phase = _session_phase(hm).value
        except ValueError:
            pass  # Unknown phase must never reject an otherwise valid fill.
    trade = {
        "date": _ymd(day),
        "code": code,
        "side": "SELL",
        "price": px,
        "shares": shares,
        "notional": notional,
        "commission": comm if not per_order_fees else 0.0,
        "reason": reason,
        "lot": pos.lot_id,
        "session_phase": session_phase,
        "price_rule": price_rule,
        **position_identity(pos),
    }
    st.trades.append(trade)
    if per_order_fees:
        comm = _accrue_order_fee(st, "SELL", order_id, trade)
    st.cash += notional - comm
    record_fill(st, st.trades[-1], cash_before)
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
    if order_key is not None and shares >= requested_shares:
        release_fee_order(st, order_key)
    # S1: every booked sell decrements shares, including the default path.
    pos.shares -= shares
    if st.exdiv_economics is not None:
        locks = st.exdiv_economics.pop_locks(pos)
        if pos.shares and (locked := {d: q for d, q in locks.items() if ds <= d}):
            st.exdiv_economics.locks_for(pos).update(locked)
    if pos.shares:
        return shares
    lots = st.positions.get(code) or []
    st.positions[code] = [p for p in lots if p is not pos]
    if not st.positions[code]:
        del st.positions[code]
    policy = s8_policy(st)
    if policy is not None and isinstance(pos, IndependentPosition):
        if not any(
            getattr(p, "position_id", None) == pos.position_id
            for p in st.positions.get(code, [])
        ):
            policy["groups"][pos.position_id].closed = True
    carry_states = getattr(st, "held_fill_states", None)
    if carry_states is not None:
        state = carry_states.get(held_fill_key(pos), {})
        orders = state.get("side_pending", [])
        orders[:] = [order for order in orders if order[0] is not pos]
        position_id = getattr(pos, "position_id", None)
        if not position_id or not any(
            getattr(p, "position_id", None) == position_id
            for p in st.positions.get(code, [])
        ):
            carry_states.pop(held_fill_key(pos), None)
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
              session_phase=session_phase, price_rule=price_rule,
              order_id=order_id)
    return shares


def _sell_s8_group(
    st: SimState, code: str, pos: IndependentExitPosition, px: float, day,
    reason: str, *, bucket_id: int | None, at: int | None,
    day_i: int | None, hm: int | None, session_phase: str, price_rule: str,
    wanted_shares: int | None,
) -> int:
    """Latch one group exit and retain its T+1-locked shares for the next open.

    A group is one exit order, while each fill lot retains its trade row.
    Completed-volume limits retain their per-lot partial fills; any unfilled
    shares keep the group's pending exit and fee-order identity.
    """
    if wanted_shares is not None:
        raise ValueError("independent-position exits must target the whole position")
    day_i = pos.day_i if day_i is None else day_i
    if day_i is None:
        raise ValueError("independent-position exit requires day_i for T+1")
    if not position_is_open(st, pos):
        return 0
    lots = pos.lots
    if s8_policy(st)["name"] in {"version8_2", "version8_6"} and len(lots) == 1:
        # These books cannot add within a position. Keep their single-lot
        # settlement, volume-attempt and existing pending rules unchanged.
        if lots[0].entry_idx >= day_i:
            return 0
        return _sell(
            st, code, lots[0], px, day, reason,
            bucket_id=bucket_id, at=at, day_i=day_i, hm=hm,
            session_phase=session_phase, price_rule=price_rule,
        )
    pos.pending_exit = reason
    if pos.group.exit_day_idx is None:
        pos.group.exit_day_idx = day_i
    # Later ex-dates cannot retroactively make the original exit T+1-locked.
    if st.exdiv_economics is not None and day_i == pos.group.exit_day_idx:
        pos.group.t1_deferred_bonus_lots.update(
            p.lot_id for p in lots if _locked_bonus(st.exdiv_economics, p, _ymd(day))
        )
    sellable = [p for p in lots if p.entry_idx < day_i]
    if not sellable:
        return 0
    order_key = ("s8-group-exit", pos.position_id)
    order_id = fee_order_id(st, order_key)
    filled = 0
    for lot in sellable:
        lot_reason = reason
        if day_i > pos.group.exit_day_idx and (
            lot.entry_idx >= pos.group.exit_day_idx
            or lot.lot_id in pos.group.t1_deferred_bonus_lots
        ):
            lot_reason += "|t1_deferred"
        filled += _sell(
            st, code, lot, px, day, lot_reason,
            bucket_id=bucket_id, at=at, day_i=day_i, hm=hm,
            session_phase=session_phase, price_rule=price_rule, _group_exit=True,
            order_id=order_id,
        )
    if pos.group.closed:
        release_fee_order(st, order_key)
    return filled
