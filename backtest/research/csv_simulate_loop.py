# -*- coding: utf-8 -*-
"""Shared daily/minute simulate() skeleton: chase, pool buys, equity/EOD mark.

Sell loops stay in each engine on purpose (daily bar rules vs ``scan_held_day``).
Call sites inject quote providers so buy/chase prices differ without forking
limit / gate / sizing logic.
"""

from __future__ import annotations

from typing import Callable, Optional

import pandas as pd

from backtest.research.csv_common import _named_limits, _pool_names_asof
from backtest.research.csv_ledger import (
    SimState,
    chase_decision,
    execute_buy,
    hit_limit_up,
    market_close_mark,
    queue_limit_up_chase,
)
from backtest.research.csv_strategy_books import apply_csv_strategy

# quotes_for(code) -> (open_px, buy_px, closes_ending_yesterday) or None to keep pending
ChaseQuotesFn = Callable[[str], Optional[tuple[float, float, list[float]]]]
# buy_quote_for(code) -> (buy_px, closes_ending_yesterday) or None -> skip_no_bar
PoolQuoteFn = Callable[[str], Optional[tuple[float, list[float]]]]


def prepare_strategy_hooks(
    strategy: str,
    *,
    stop_pct=None,
    take_profit=None,
    record_params=None,
    profit_base=None,
    tiers=None,
    tier_default=None,
    apply_fn=None,
) -> dict:
    """Unpack ``apply_csv_strategy``; callers read engine-specific hook keys.

    Pass ``apply_fn`` from the engine module so tests can monkeypatch
    ``csv_daily_backtest.apply_csv_strategy`` (or minute) and still win.
    """
    fn = apply_fn or apply_csv_strategy
    return fn(
        strategy,
        stop_pct=stop_pct,
        take_profit=take_profit,
        record_params=record_params,
        profit_base=profit_base,
        tiers=tiers,
        tier_default=tier_default,
    )


def init_sim_state(
    hooks: dict,
    *,
    total_cash: float,
    bars_loaded: int,
    pool_days: dict,
    pool_names: Optional[dict[str, str]] = None,
    pool_names_by_day: Optional[dict[str, dict[str, str]]] = None,
) -> tuple[SimState, dict[str, tuple[float, int]], Callable[[str], dict[str, str]]]:
    """SimState + pending_chase + names_asof after strategy hooks are applied."""
    st = SimState(cash=float(total_cash))
    hooks["record_params"](st)
    st.stats["bars_loaded"] = int(bars_loaded)
    st.stats["pool_days"] = len(pool_days)
    pending_chase: dict[str, tuple[float, int]] = {}
    names_asof = _pool_names_asof(pool_names, pool_names_by_day)
    return st, pending_chase, names_asof


def run_chase_due_day(
    st: SimState,
    pending_chase: dict[str, tuple[float, int]],
    *,
    day_i: int,
    day,
    names: dict[str, str],
    allow_add: bool,
    buy_gate,
    quotes_for: ChaseQuotesFn,
) -> None:
    """T+1 chase for due codes; ``quotes_for`` supplies open/buy/prev closes."""
    due = [c for c, (_per, sig) in pending_chase.items() if day_i > sig]
    for code in due:
        per_ch, _sig = pending_chase[code]
        if code in st.positions and not allow_add:
            pending_chase.pop(code)
            st.stats["skip_held"] += 1
            st.stats["chase_skip_held"] += 1
            continue
        quoted = quotes_for(code)
        if quoted is None:
            # Missing bar / quotes / prev closes: keep pending for a later day.
            continue
        open_px, buy_px, closes = quoted
        pending_chase.pop(code)
        prev_close = float(closes[-1])
        limits = _named_limits(code, prev_close, names)
        if limits is None:
            st.stats["skip_unknown_board"] += 1
            continue
        limit_up, _ = limits
        decision = chase_decision(open_px, buy_px, limit_up)
        if decision == "limit":
            st.stats["chase_skip_limit"] += 1
            continue
        if decision != "buy":
            st.stats["chase_abandon"] += 1
            continue
        if callable(buy_gate) and not buy_gate(code, buy_px, day, closes):
            st.stats["skip_buy_gate"] += 1
            if len(closes) < 10:
                st.stats["skip_sma_warmup"] += 1
            continue
        if not execute_buy(st, code, buy_px, per_ch, day_i, day, reason="chase:T+1"):
            st.stats["chase_buy_fail"] += 1


def run_pool_buys_day(
    st: SimState,
    pending_chase: dict[str, tuple[float, int]],
    *,
    day_i: int,
    day,
    ds: str,
    pool_days: dict[str, list[str]],
    daily_quota: float,
    names: dict[str, str],
    allow_add: bool,
    buy_gate,
    buy_quote_for: PoolQuoteFn,
) -> None:
    """Pool buys for ``ds``; ``buy_quote_for`` supplies buy price + prev closes."""
    planned = list(pool_days.get(ds, []))
    if not planned:
        return
    per = min(daily_quota, st.cash) / len(planned)
    for code in planned:
        if code in st.positions and not allow_add:
            st.stats["skip_held"] += 1
            continue
        quoted = buy_quote_for(code)
        if quoted is None:
            st.stats["skip_no_bar"] += 1
            continue
        px, closes = quoted
        if not closes:
            st.stats["skip_no_bar"] += 1
            continue
        prev_close = float(closes[-1])
        limits = _named_limits(code, prev_close, names)
        if limits is None:
            st.stats["skip_unknown_board"] += 1
            continue
        limit_up, _ = limits
        if hit_limit_up(px, limit_up):
            queue_limit_up_chase(st, pending_chase, code, per, day_i)
            continue
        if callable(buy_gate) and not buy_gate(code, px, day, closes):
            st.stats["skip_buy_gate"] += 1
            if len(closes) < 10:
                st.stats["skip_sma_warmup"] += 1
            continue
        execute_buy(st, code, px, per, day_i, day, reason="pool")


def append_equity_and_eod_marks(
    st: SimState,
    *,
    ds: str,
    day,
    calendar_last,
    mark_bars: dict[str, pd.DataFrame],
) -> None:
    """Append equity point; on last calendar day emit EOD_MARK trades.

    Mark close is resolved once per code (not per lot): same data-driven
    close for every lot; ``pos.cost`` only when no on/prior bar exists.
    """
    eq = st.cash
    # code -> market close, or None => use per-lot cost fallback
    mark_by_code: dict[str, Optional[float]] = {}
    for code, lots in st.positions.items():
        if code not in mark_by_code:
            mark_by_code[code] = market_close_mark(mark_bars.get(code), day)
        m = mark_by_code[code]
        for pos in lots:
            last = float(pos.cost) if m is None else m
            eq += pos.shares * last
    st.equity_curve.append((ds, eq))

    if day == calendar_last and st.positions:
        for code, lots in st.positions.items():
            m = mark_by_code[code]
            for pos in lots:
                last = float(pos.cost) if m is None else m
                st.trades.append(
                    {
                        "date": ds,
                        "code": code,
                        "side": "EOD_MARK",
                        "price": last,
                        "shares": pos.shares,
                        "notional": pos.shares * last,
                        "commission": 0.0,
                        "lot": pos.lot_id,
                    }
                )
