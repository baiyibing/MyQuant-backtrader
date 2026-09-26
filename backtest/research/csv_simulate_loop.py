# -*- coding: utf-8 -*-
"""Shared daily/minute simulate() skeleton: chase, pool buys, equity/EOD mark.

Sell loops stay in each engine on purpose (daily bar rules vs ``scan_held_day``).
Call sites inject quote providers so buy/chase prices differ without forking
limit / gate / sizing logic.
"""

from __future__ import annotations

import hashlib
import math
import random
from typing import Callable, Optional

import pandas as pd

from backtest.research.ashare_session import skip_buy_at_limit
from backtest.research.csv_common import (
    _pool_names_asof,
    book_limit_prices,
    day_bar_and_prev_closes,
)
from backtest.research.csv_ledger import (
    InsufficientCashError,
    SimState,
    _buy_size,
    chase_decision,
    configure_s8,
    execute_buy,
    trade_commission,
    hit_limit_down,
    hit_limit_up,
    market_close_mark,
    queue_limit_up_chase,
    position_identity,
    s8_open_groups,
    s8_policy,
)
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.exdiv_map import mapped_prev_close
from backtest.research.minute_audit import record_rejection

# quotes_for(code) -> (open_px, buy_px, closes_ending_yesterday) or None to keep pending
ChaseQuotesFn = Callable[[str], Optional[tuple[float, float, list[float]]]]
# buy_quote_for(code) -> (buy_px, closes_ending_yesterday) or None -> skip_no_bar
PoolQuoteFn = Callable[[str], Optional[tuple[float, list[float]]]]


def prepare_strategy_hooks(
    strategy: str,
    *,
    name_budget=None,
    stop_pct=None,
    take_profit=None,
    record_params=None,
    profit_base=None,
    tiers=None,
    tier_default=None,
    ration="file_order",
    ration_seed=0,
    apply_fn=None,
    **extra,
) -> dict:
    """Unpack ``apply_csv_strategy``; callers read engine-specific hook keys.

    Pass ``apply_fn`` from the engine module so tests can monkeypatch
    ``csv_daily_backtest.apply_csv_strategy`` (or minute) and still win.
    Extra kwargs (e.g. topk scores) forward to the strategy book apply.
    """
    fn = apply_fn or apply_csv_strategy
    return fn(
        strategy,
        name_budget=name_budget,
        stop_pct=stop_pct,
        take_profit=take_profit,
        record_params=record_params,
        profit_base=profit_base,
        tiers=tiers,
        tier_default=tier_default,
        ration=ration,
        ration_seed=ration_seed,
        **extra,
    )


def _buy_denom(planned: list[str], planned_for_day) -> int:
    """Vacancy mode sizes off the original buy list, so an empty seat stays cash."""
    slots = (
        getattr(planned_for_day, "slot_count", None)
        if callable(planned_for_day)
        else None
    )
    if slots:
        return int(slots)
    return len(planned)


def apply_capital_ration(
    planned: list[str], *, ration: str, ration_seed: int, ds: str
) -> list[str]:
    """Return the day's stable capital-ration order without mutating input."""
    ordered = list(planned)
    if ration == "file_order":
        return ordered
    if ration != "seeded_shuffle":
        raise ValueError(f"unsupported capital ration {ration!r}")
    digest = hashlib.sha256(f"{int(ration_seed)}:{ds}".encode("utf-8")).digest()
    random.Random(int.from_bytes(digest, "big")).shuffle(ordered)
    return ordered


def init_sim_state(
    hooks: dict,
    *,
    total_cash: float,
    bars_loaded: int,
    pool_days: dict,
    pool_names: Optional[dict[str, str]] = None,
    pool_names_by_day: Optional[dict[str, dict[str, str]]] = None,
    daily_quota: Optional[float] = None,
) -> tuple[SimState, dict[str, tuple[float, int]], Callable[[str], dict[str, str]]]:
    """SimState + pending_chase + names_asof after strategy hooks are applied."""
    st = SimState(cash=float(total_cash))
    st.book_on_buy = hooks.get("on_buy")
    st.book_on_exdiv = hooks.get("on_exdiv")
    hooks["record_params"](st)
    configure_s8(st, hooks)
    if daily_quota is not None:
        st.stats["daily_quota"] = float(daily_quota)
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
    exdiv: Optional[dict] = None,
    ds: Optional[str] = None,
    qlib_limit_pct: Optional[float] = None,
    allow_new_name=None,
    add_gate=None,
    index_blocks_add: bool = True,
    volume_bucket_for: Callable[[str], int | None] | None = None,
    reference_price_for: Callable[[str, str], float] | None = None,
) -> None:
    """T+1 chase for due codes; ``quotes_for`` supplies open/buy/prev closes."""
    independent = s8_policy(st) is not None
    due = [c for c, (_per, sig) in pending_chase.items() if day_i > sig]
    for chase_key in due:
        code = chase_key.split("@", 1)[0] if independent else chase_key
        per_ch, _sig = pending_chase[chase_key]
        if code in st.positions and not allow_add:
            pending_chase.pop(chase_key)
            st.stats["skip_held"] += 1
            st.stats["chase_skip_held"] += 1
            record_rejection(st, code, day, "chase_skip_held")
            continue
        if callable(allow_new_name) and not allow_new_name(day):
            if not (not independent and code in st.positions and not index_blocks_add):
                pending_chase.pop(chase_key)
                st.stats["skip_index_gate"] += 1
                continue
        quoted = quotes_for(code)
        if quoted is None:
            # Missing bar / quotes / prev closes: keep pending for a later day.
            continue
        open_px, buy_px, closes = quoted
        pending_chase.pop(chase_key)
        ymd = ds if ds is not None else pd.Timestamp(day).strftime("%Y%m%d")
        if reference_price_for is None:
            prev_close, did_map = mapped_prev_close(exdiv, code, ymd, float(closes[-1]))
        else:
            prev_close, did_map = reference_price_for(code, ymd), False
        if did_map:
            st.stats["exdiv_prev_close_mapped"] = (
                int(st.stats.get("exdiv_prev_close_mapped", 0)) + 1
            )
        limits = book_limit_prices(
            code, prev_close, names, qlib_limit_pct=qlib_limit_pct
        )
        if limits is None:
            st.stats["skip_unknown_board"] += 1
            continue
        limit_up, _ = limits
        decision = (
            "limit"
            if skip_buy_at_limit(buy_px, limits)
            else chase_decision(open_px, buy_px, limit_up)
        )
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
        lots = [] if independent else st.positions.get(code, [])
        if lots and callable(add_gate) and not add_gate(lots, buy_px):
            st.stats["skip_add_loser"] += 1
            continue
        quota_used = st.daily_quota_used
        volume_kwargs = (
            {"bucket_id": volume_bucket_for(code)}
            if volume_bucket_for is not None
            else {}
        )
        if independent:
            volume_kwargs.update(
                position_id=chase_key, entry_signal_date=chase_key.split("@", 1)[1],
            )
        volume_skips = sum(
            int(st.stats.get(k, 0))
            for k in ("skip_volume_cap", "skip_volume_unavailable")
        )
        if not execute_buy(
            st, code, buy_px, per_ch, day_i, day, reason="chase:T+1", **volume_kwargs
        ):
            st.stats["chase_buy_fail"] += 1
            shares, _ = _buy_size(per_ch, buy_px)
            if (
                sum(
                    int(st.stats.get(k, 0))
                    for k in ("skip_volume_cap", "skip_volume_unavailable")
                )
                > volume_skips
            ):
                key = "chase_buy_fail_volume"
            else:
                key = "chase_buy_fail_shares" if shares <= 0 else "chase_buy_fail_cash"
            st.stats[key] = st.stats.setdefault(key, 0) + 1
        if st.stats.get("sizing") == "per_name":
            # daily_quota_used is vestigial; per_name never consumes a day quota.
            st.daily_quota_used = quota_used


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
    sizing: str = "daily_quota",
    name_budget: float = 1_000_000.0,
    ration: str = "file_order",
    ration_seed: int = 0,
    exdiv: Optional[dict] = None,
    planned_for_day=None,
    cash_deploy_frac: Optional[float] = None,
    qlib_limit_pct: Optional[float] = None,
    limit_up_chase: bool = True,
    forbid_all_trade_at_limit: bool = False,
    allow_new_name=None,
    add_gate=None,
    name_lot_budget=None,
    index_blocks_add: bool = True,
    volume_bucket_for: Callable[[str], int | None] | None = None,
    volume_at: int | None = None,
    sold_today: set[str] | None = None,
    reference_price_for: Callable[[str, str], float] | None = None,
    handle_planned_code: Callable[[str], bool] | None = None,
    allocation_cash: float | None = None,
    buy_reason: str = "pool",
    buy_hm: int | None = None,
    strict_limit_up: bool = False,
) -> None:
    """Pool buys for ``ds``; ``buy_quote_for`` supplies buy price + prev closes.

    ``planned_for_day(ds, held_codes)`` is optional (default None). When set, its
    return replaces the pool file list before capital ration — old books unchanged.
    ``handle_planned_code(code)`` may consume one ordered slot (True), allowing
    opt-in child orders to compete with normal pool adds in the same cash order.
    ``allocation_cash`` freezes the daily-quota basis for opt-in schedulers.
    ``buy_reason`` / ``buy_hm`` label opt-in buys without changing default rows.
    ``strict_limit_up`` uses P1's literal open < upper-band contract; the
    default retains the legacy epsilon comparison.
    """
    policy = s8_policy(st)
    independent = policy is not None
    raw = list(pool_days.get(ds, []))
    if callable(planned_for_day):
        held_codes = list(st.positions.keys())
        raw = list(planned_for_day(ds, held_codes))
    if sold_today:
        st.stats["skip_sold_today"] += sum(code in sold_today for code in raw)
        raw = [code for code in raw if code not in sold_today]
    planned = apply_capital_ration(raw, ration=ration, ration_seed=ration_seed, ds=ds)
    if not planned:
        return
    if sizing == "per_name":
        per = name_budget
    else:
        frac = 1.0 if cash_deploy_frac is None else float(cash_deploy_frac)
        if not 0 < frac <= 1:
            raise ValueError(
                f"cash_deploy_frac must be in (0, 1], got {cash_deploy_frac!r}"
            )
        cash_basis = st.cash if allocation_cash is None else allocation_cash
        per = min(daily_quota, cash_basis) * frac / _buy_denom(planned, planned_for_day)
    for code in planned:
        if handle_planned_code is not None and handle_planned_code(code):
            continue
        if independent and f"{code}@{ds}" in policy["groups"]:
            continue
        if code in st.positions and not allow_add:
            st.stats["skip_held"] += 1
            record_rejection(st, code, day, "skip_held")
            continue
        if callable(allow_new_name) and not allow_new_name(day):
            if not (not independent and code in st.positions and not index_blocks_add):
                st.stats["skip_index_gate"] += 1
                continue
        quoted = buy_quote_for(code)
        if quoted is None:
            st.stats["skip_no_bar"] += 1
            continue
        px, closes = quoted
        if not closes:
            st.stats["skip_no_bar"] += 1
            continue
        if reference_price_for is None:
            prev_close, did_map = mapped_prev_close(exdiv, code, ds, float(closes[-1]))
        else:
            prev_close, did_map = reference_price_for(code, ds), False
        if did_map:
            st.stats["exdiv_prev_close_mapped"] = (
                int(st.stats.get("exdiv_prev_close_mapped", 0)) + 1
            )
        limits = book_limit_prices(
            code, prev_close, names, qlib_limit_pct=qlib_limit_pct
        )
        if limits is None:
            st.stats["skip_unknown_board"] += 1
            continue
        limit_up, limit_down = limits
        if independent:
            # Price/limit checks must see this signal's own initial budget.
            per = (
                float(name_lot_budget(name_budget, []))
                if callable(name_lot_budget) else float(name_budget)
            )
        upper_blocked = px >= limit_up if strict_limit_up else skip_buy_at_limit(px, limits)
        blocked = upper_blocked or (
            forbid_all_trade_at_limit and hit_limit_down(px, limit_down)
        )
        if blocked:
            if limit_up_chase:
                queue_limit_up_chase(
                    st, pending_chase, code, per, day_i,
                    **({"entry_signal_date": ds} if independent else {}),
                )
            else:
                st.stats["skip_limit_up"] += 1
            continue
        if callable(buy_gate) and not buy_gate(code, px, day, closes):
            st.stats["skip_buy_gate"] += 1
            if len(closes) < 10:
                st.stats["skip_sma_warmup"] += 1
            continue
        lots = [] if independent else st.positions.get(code, [])
        if lots and callable(add_gate) and not add_gate(lots, px):
            st.stats["skip_add_loser"] += 1
            continue
        if sizing == "per_name" and callable(name_lot_budget):
            per = float(name_lot_budget(name_budget, lots))
        volume_kwargs = (
            {"bucket_id": volume_bucket_for(code)}
            if volume_bucket_for is not None
            else {}
        )
        if volume_at is not None:
            volume_kwargs["at"] = volume_at
        if buy_hm is not None:
            volume_kwargs["hm"] = buy_hm
        if independent:
            volume_kwargs.update(position_id=f"{code}@{ds}", entry_signal_date=ds)
        if sizing == "per_name":
            shares, _ = _buy_size(per, px)
            notional = shares * px
            if (
                notional + trade_commission(notional, st.buy_cost_rate, st.min_cost)
                > st.cash
            ):
                if independent:
                    raise InsufficientCashError(
                        date=ds, code=code,
                        needed=notional + trade_commission(notional, st.buy_cost_rate, st.min_cost),
                        available=st.cash,
                    )
                st.stats["skip_cash"] = st.stats.setdefault("skip_cash", 0) + 1
                st.stats["skip_cash_notional"] = (
                    st.stats.setdefault("skip_cash_notional", 0.0) + per
                )
                record_rejection(st, code, day, "skip_cash", px)
                continue
            quota_used = st.daily_quota_used
            execute_buy(st, code, px, per, day_i, day, reason=buy_reason, **volume_kwargs)
            # Ledger's daily_quota_used is vestigial, not per_name enforcement.
            st.daily_quota_used = quota_used
        else:
            execute_buy(st, code, px, per, day_i, day, reason=buy_reason, **volume_kwargs)


def run_step_adds_day(
    st: SimState,
    *,
    day_i: int,
    day,
    ds: str,
    names: dict[str, str],
    buy_quote_for: PoolQuoteFn,
    sizing: str = "daily_quota",
    name_budget: float = 1_000_000.0,
    exdiv: Optional[dict] = None,
    qlib_limit_pct: Optional[float] = None,
    forbid_all_trade_at_limit: bool = False,
    buy_gate=None,
    name_lot_budget=None,
    step_add=None,
    volume_bucket_for: Callable[[str], int | None] | None = None,
    reference_price_for: Callable[[str, str], float] | None = None,
    confirm_peak_for: Callable[[str, object], float] | None = None,
) -> None:
    """Off-list scan; selected 8.x books add once per independent group/day."""
    if s8_policy(st) is not None:
        _run_s8_price_adds_day(
            st, day_i=day_i, day=day, ds=ds, names=names,
            buy_quote_for=buy_quote_for, sizing=sizing, exdiv=exdiv,
            qlib_limit_pct=qlib_limit_pct, forbid_all_trade_at_limit=forbid_all_trade_at_limit,
            buy_gate=buy_gate, volume_bucket_for=volume_bucket_for,
            reference_price_for=reference_price_for,
            confirm_peak_for=confirm_peak_for,
        )
        return
    if not callable(step_add) or sizing != "per_name":
        return
    for code in list(st.positions.keys()):
        lots = st.positions.get(code) or []
        if not lots:
            continue
        quoted = buy_quote_for(code)
        if quoted is None:
            continue
        px, closes = quoted
        if not closes or float(px) <= 0:
            continue
        if not step_add(lots, px):
            continue
        if reference_price_for is None:
            prev_close, did_map = mapped_prev_close(exdiv, code, ds, float(closes[-1]))
        else:
            prev_close, did_map = reference_price_for(code, ds), False
        if did_map:
            st.stats["exdiv_prev_close_mapped"] = (
                int(st.stats.get("exdiv_prev_close_mapped", 0)) + 1
            )
        limits = book_limit_prices(
            code, prev_close, names, qlib_limit_pct=qlib_limit_pct
        )
        if limits is None:
            st.stats["skip_unknown_board"] += 1
            continue
        limit_up, limit_down = limits
        blocked = hit_limit_up(px, limit_up) or (
            forbid_all_trade_at_limit and hit_limit_down(px, limit_down)
        )
        if blocked:
            st.stats["skip_limit_up"] += 1
            continue
        if callable(buy_gate) and not buy_gate(code, px, day, closes):
            st.stats["skip_buy_gate"] += 1
            continue
        per = float(name_budget)
        if callable(name_lot_budget):
            per = float(name_lot_budget(name_budget, lots))
        shares, _ = _buy_size(per, px)
        notional = shares * px
        if (
            notional + trade_commission(notional, st.buy_cost_rate, st.min_cost)
            > st.cash
        ):
            st.stats["skip_cash"] = int(st.stats.get("skip_cash", 0)) + 1
            st.stats["skip_cash_notional"] = (
                float(st.stats.get("skip_cash_notional", 0.0)) + per
            )
            record_rejection(st, code, day, "skip_cash", px)
            continue
        quota_used = st.daily_quota_used
        volume_kwargs = (
            {"bucket_id": volume_bucket_for(code)}
            if volume_bucket_for is not None
            else {}
        )
        execute_buy(
            st,
            code,
            px,
            per,
            day_i,
            day,
            reason="add:step20",
            is_step=True,
            **volume_kwargs,
        )
        st.daily_quota_used = quota_used


def _run_s8_price_adds_day(
    st, *, day_i, day, ds, names, buy_quote_for, sizing, exdiv,
    qlib_limit_pct, forbid_all_trade_at_limit, buy_gate, volume_bucket_for,
    reference_price_for, confirm_peak_for,
) -> None:
    policy = s8_policy(st)
    book = policy["name"]
    if sizing != "per_name" or book not in {"version8", "version8_3", "version8_4", "version8_5"}:
        return
    confirm = book == "version8_3"
    gate = policy["allow_new_name"]
    if confirm and callable(gate) and not gate(day):
        # 8.3 has always blocked both new positions and adds at the index gate.
        return
    for code in list(st.positions):
        quoted = buy_quote_for(code)
        if quoted is None:
            continue
        px, closes = quoted
        if not closes or float(px) <= 0:
            continue
        groups = list(s8_open_groups(st, code))
        for position_id, group in groups:
            if group.last_add_date == ds or group.first_lot.pending_exit:
                continue
            cost = float(group.first_lot.cost)
            if cost <= 0:
                continue
            if confirm:
                peak = (
                    confirm_peak_for(code, group.first_lot)
                    if confirm_peak_for is not None else group.first_lot.peak
                )
                if group.supplement_done or px < cost or peak < cost * 1.03:
                    continue
            elif int((float(px) / cost - 1.0) / 0.20 + 1e-12) <= group.executed_steps:
                continue
            if reference_price_for is None:
                prev_close, did_map = mapped_prev_close(exdiv, code, ds, float(closes[-1]))
            else:
                prev_close, did_map = reference_price_for(code, ds), False
            if did_map:
                st.stats["exdiv_prev_close_mapped"] = (
                    int(st.stats.get("exdiv_prev_close_mapped", 0)) + 1
                )
            limits = book_limit_prices(code, prev_close, names, qlib_limit_pct=qlib_limit_pct)
            if limits is None:
                st.stats["skip_unknown_board"] += 1
                continue
            limit_up, limit_down = limits
            if hit_limit_up(px, limit_up) or (
                forbid_all_trade_at_limit and hit_limit_down(px, limit_down)
            ):
                st.stats["skip_limit_up"] += 1
                continue
            if callable(buy_gate) and not buy_gate(code, px, day, closes):
                st.stats["skip_buy_gate"] += 1
                continue
            per = group.budget * (0.50 if confirm else 1.0)
            quota_used = st.daily_quota_used
            volume_kwargs = (
                {"bucket_id": volume_bucket_for(code)}
                if volume_bucket_for is not None else {}
            )
            filled = execute_buy(
                st, code, px, per, day_i, day,
                reason="add:confirm3" if confirm else "add:step20",
                is_step=not confirm, position_id=position_id,
                entry_signal_date=group.entry_signal_date, **volume_kwargs,
            )
            st.daily_quota_used = quota_used
            if filled:
                group.last_add_date = ds
                if confirm:
                    group.supplement_done = True
                else:
                    group.executed_steps += 1


def run_buybacks_day(
    st: SimState,
    *,
    day_i: int,
    day,
    ds: str,
    names: dict[str, str],
    codes,
    buy_quote_for: PoolQuoteFn,
    buyback_plan=None,
    on_reclaim=None,
    exdiv: Optional[dict] = None,
    qlib_limit_pct: Optional[float] = None,
    volume_bucket_for: Callable[[str], int | None] | None = None,
    reference_price_for: Callable[[str, str], float] | None = None,
) -> None:
    """Fourth buy cause; ordinary ledger fills bounded by each channel's memory.

    A zero-sized qualified reclaim is delivered too: residual=2 re-arms dust
    without a buy. Cash is checked at the call site, before the capacity gate.
    """
    if not callable(buyback_plan):
        return
    for code in list(codes):
        quoted = buy_quote_for(code)
        if quoted is None:
            continue
        px, closes = quoted
        if not closes or px <= 0:
            continue
        for reason, shares in buyback_plan(st, code, px, day, closes):
            if not shares:
                on_reclaim(st, code, reason, 0)
                continue
            if reference_price_for is None:
                prev, _ = mapped_prev_close(exdiv, code, ds, float(closes[-1]))
            else:
                prev = reference_price_for(code, ds)
            limits = book_limit_prices(code, prev, names, qlib_limit_pct=qlib_limit_pct)
            if limits is None:
                st.stats["skip_unknown_board"] += 1
                continue
            if skip_buy_at_limit(px, limits):
                st.stats["skip_limit_up"] += 1
                continue
            notional = shares * px
            if (
                notional + trade_commission(notional, st.buy_cost_rate, st.min_cost)
                > st.cash
            ):
                st.stats["skip_cash"] = st.stats.get("skip_cash", 0) + 1
                st.stats["skip_cash_notional"] = (
                    st.stats.get("skip_cash_notional", 0.0) + notional
                )
                continue
            quota_used = st.daily_quota_used
            volume_kwargs = (
                {"bucket_id": volume_bucket_for(code)}
                if volume_bucket_for is not None
                else {}
            )
            if execute_buy(
                st,
                code,
                px,
                notional,
                day_i,
                day,
                reason=reason,
                shares_override=shares,
                **volume_kwargs,
            ):
                on_reclaim(st, code, reason, st.trades[-1]["shares"])
            st.daily_quota_used = quota_used


def run_eod_exits(
    st, *, day, ds, bars, eod_exit, hold_modes, exdiv=None,
    signal_bars_front=None, strategy=None, fix_s11_exit_domain=False,
):
    """Evaluate opt-in book exits after buys; only schedule the next open.

    Keep book state outside Position so existing ledger snapshots stay identical.
    The entry index and lot identify each holding across sells and re-entries.
    """
    if signal_bars_front is not None or fix_s11_exit_domain:
        from backtest.research.csv_strategy_books import normalize_csv_strategy

        if (not fix_s11_exit_domain or signal_bars_front is None
                or normalize_csv_strategy(strategy) != "version11"):
            raise ValueError("signal_bars_front requires version11 + fix_s11_exit_domain=True")
    if not callable(eod_exit):
        return
    live = set()
    for code, lots in st.positions.items():
        if signal_bars_front is None:
            got = day_bar_and_prev_closes(bars[code], day) if code in bars else None
        else:
            got = day_bar_and_prev_closes(signal_bars_front[code], day)
        for pos in lots:
            key = (code, pos.entry_idx, pos.lot_id)
            live.add(key)
            if got is None or pos.pending_exit:
                continue
            row, closes = got
            if signal_bars_front is None:
                previous, _ = mapped_prev_close(exdiv, code, ds, closes[-1])
            else:
                # INITIAL uses strictly pre-T front; only SMA's input appends T.
                previous = closes[-1]
            decision = eod_exit(
                closes + [float(row["close"])], previous, hold_modes.get(key)
            )
            hold_modes[key] = decision.hold_mode
            if decision.reason:
                pos.pending_exit = decision.reason
    for key in hold_modes.keys() - live:
        del hold_modes[key]


def require_market_marks(
    st: SimState,
    *,
    ds: str,
    day,
    mark_bars: dict[str, pd.DataFrame],
    mark_source_for: Callable[[str], str] | None = None,
) -> None:
    """Validate all held marks before any equity/EOD writes, regardless of fills."""
    for code, lots in st.positions.items():
        if not lots:
            continue
        mark = market_close_mark(mark_bars.get(code), day)
        if mark is None or not math.isfinite(mark) or mark <= 0:
            source = mark_source_for(code) if mark_source_for is not None else "raw_daily"
            raise ValueError(f"missing valid raw mark code={code} date={ds} domain=none path={source}")


def append_equity_and_eod_marks(
    st: SimState,
    *,
    ds: str,
    day,
    calendar_last,
    mark_bars: dict[str, pd.DataFrame],
    require_market_mark: bool = False,
    mark_source_for: Callable[[str], str] | None = None,
) -> None:
    """Append equity point; on last calendar day emit EOD_MARK trades.

    Mark close is resolved once per code (not per lot): same data-driven
    close for every lot; ``pos.cost`` only when no on/prior bar exists.
    """
    if require_market_mark:
        require_market_marks(st, ds=ds, day=day, mark_bars=mark_bars,
                             mark_source_for=mark_source_for)
    eq = st.cash
    if st.exdiv_economics is not None:
        eq += st.exdiv_economics.receivable_total
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
                        "session_phase": "",
                        "price_rule": "",
                        **position_identity(pos),
                    }
                )
