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

from backtest.research.ashare_session import (
    defer_sell_at_limit,
    k_for,
    skip_buy_at_limit,
)
from backtest.research.book_capabilities import allows_price_add
from backtest.research.csv_common import (
    _pool_names_asof,
    book_limit_prices,
    day_bar_and_prev_closes,
)
from backtest.research.csv_ledger import (
    check_buy_cash,
    SimState,
    chase_decision,
    configure_s8,
    execute_buy,
    execute_parking_buy,
    is_parking_lot,
    parking_lots,
    Position,
    register_principal_lot,
    sleeve_parking_lots,
    trade_commission as trade_commission,
    hit_limit_down,
    hit_limit_up,
    market_close_mark,
    preview_buy_cash_needed,
    preview_final_buy_declaration,
    release_parking_cash,
    queue_limit_up_chase,
    note_cont_open,
    position_identity,
    s8_open_groups,
    s8_policy,
    uses_shrink_on_short_cash,
    _sell,
)
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.strategy6_50_rules import due_cont_rebuy_rise
from backtest.research.exdiv_map import mapped_prev_close
from backtest.research.minute_audit import record_rejection
from backtest.research.lot_rounding import BOARD_LOT, budget_board_lots

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
    if hooks.get("min_lot_top_up") or "min_lot_top_up" in st.stats:
        st.stats["min_lot_top_up"] = bool(hooks.get("min_lot_top_up", False))
    if hooks.get("profit_skim"):
        st.stats.setdefault("profit_skim_base", float(total_cash))
        st.stats.setdefault("profit_skim_withdrawn", 0.0)
        st.stats.setdefault("profit_skim_events", 0)
        if hooks.get("profit_skim_frac") is not None:
            st.stats.setdefault("profit_skim_frac", float(hooks["profit_skim_frac"]))
        st.stats.setdefault("profit_skim_pro_rata", bool(hooks.get("profit_skim_pro_rata")))
        st.stats.setdefault("profit_skim_keep_idle", bool(hooks.get("profit_skim_keep_idle")))
        st.stats.setdefault(
            "profit_skim_to_parking", bool(hooks.get("profit_skim_to_parking"))
        )
        st.stats.setdefault("profit_skim_parked", 0.0)
        st.stats.setdefault("profit_skim_cash_hold", 0.0)
        st.stats.setdefault("profit_skim_lock_drawn", 0.0)
        st.stats.setdefault("profit_skim_lock_restored", 0.0)
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
    exdiv_ref_fen: bool = False,
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
            prev_close, did_map = mapped_prev_close(exdiv, code, ymd, float(closes[-1]), **({"fen_round": True} if exdiv_ref_fen else {}))
        else:
            prev_close, did_map = reference_price_for(code, ymd), False
        if did_map:
            st.stats["exdiv_prev_close_mapped"] = (
                int(st.stats.get("exdiv_prev_close_mapped", 0)) + 1
            )
        limits = book_limit_prices(
            code, prev_close, names, qlib_limit_pct=qlib_limit_pct, as_of=ds
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
            shares, _, _, _ = preview_final_buy_declaration(
                st, code, buy_px, per_ch, day
            )
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
    exdiv_ref_fen: bool = False,
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
    order_budget: float | None = None,
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
    ``order_budget`` overrides the opt-in child order notional and floors to
    whole lots without the legacy supplementary 100-share fallback.
    """
    # Opt-in fixed slices use a hard notional budget without supplementary lots.
    # Default books retain their existing sizing and 100-share fallback.
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
    if order_budget is not None:
        per = order_budget
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
            prev_close, did_map = mapped_prev_close(exdiv, code, ds, float(closes[-1]), **({"fen_round": True} if exdiv_ref_fen else {}))
        else:
            prev_close, did_map = reference_price_for(code, ds), False
        if did_map:
            st.stats["exdiv_prev_close_mapped"] = (
                int(st.stats.get("exdiv_prev_close_mapped", 0)) + 1
            )
        limits = book_limit_prices(
            code, prev_close, names, qlib_limit_pct=qlib_limit_pct, as_of=ds
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
        unit_shares = None
        prepare_unit = st.book_state.get("prepare_unit")
        if prepare_unit is not None:
            unit_shares = prepare_unit(code, px, day)
            if not unit_shares:
                continue
            per = unit_shares * px
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
        if order_budget is not None:
            volume_kwargs["shares_override"] = budget_board_lots(per, px)
        if unit_shares is not None:
            volume_kwargs["shares_override"] = unit_shares
        if independent:
            volume_kwargs.update(position_id=f"{code}@{ds}", entry_signal_date=ds)
        if sizing == "per_name":
            if unit_shares is not None:
                per = unit_shares * px
            shares, _, _, _ = preview_final_buy_declaration(
                st,
                code,
                px,
                per,
                day,
                shares_override=volume_kwargs.get("shares_override"),
            )
            needed = preview_buy_cash_needed(st, code, px, shares, day)
            if needed > st.cash:
                release_parking_cash(st, needed)
            if (
                not uses_shrink_on_short_cash(st)
                and needed > st.cash + 1e-9
                and st.stats.get("parking_open_cover")
            ):
                st.stats["skip_cash"] = st.stats.setdefault("skip_cash", 0) + 1
                st.stats["skip_cash_notional"] = (
                    st.stats.setdefault("skip_cash_notional", 0.0) + per
                )
                record_rejection(st, code, day, "skip_cash", px)
                continue
            if not uses_shrink_on_short_cash(st) and not check_buy_cash(
                st,
                needed=needed,
                available=st.cash, date=ds, code=code,
            ):
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
    exdiv_ref_fen: bool = False,
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
            buy_quote_for=buy_quote_for, sizing=sizing, exdiv=exdiv, exdiv_ref_fen=exdiv_ref_fen,
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
            prev_close, did_map = mapped_prev_close(exdiv, code, ds, float(closes[-1]), **({"fen_round": True} if exdiv_ref_fen else {}))
        else:
            prev_close, did_map = reference_price_for(code, ds), False
        if did_map:
            st.stats["exdiv_prev_close_mapped"] = (
                int(st.stats.get("exdiv_prev_close_mapped", 0)) + 1
            )
        limits = book_limit_prices(
            code, prev_close, names, qlib_limit_pct=qlib_limit_pct, as_of=ds
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
        unit_shares = None
        prepare_unit = st.book_state.get("prepare_unit")
        if prepare_unit is not None:
            unit_shares = prepare_unit(code, px, day)
            if not unit_shares:
                continue
            per = unit_shares * px
        per = float(name_budget)
        if callable(name_lot_budget):
            per = float(name_lot_budget(name_budget, lots))
        if unit_shares is not None:
            per = unit_shares * px
        shares, _, _, _ = preview_final_buy_declaration(
            st,
            code,
            px,
            per,
            day,
            shares_override=unit_shares,
        )
        if not uses_shrink_on_short_cash(st) and not check_buy_cash(
            st,
            needed=preview_buy_cash_needed(st, code, px, shares, day),
            available=st.cash, date=ds, code=code,
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
        if unit_shares is not None:
            volume_kwargs["shares_override"] = unit_shares
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


def _execute_s8_price_add(
    st,
    *,
    code,
    px,
    per,
    day_i,
    day,
    reason,
    is_step,
    position_id,
    entry_signal_date,
    volume_kwargs,
) -> bool:
    """One S8 add fill; daily_quota stays vestigial for per_name books."""
    quota_used = st.daily_quota_used
    filled = execute_buy(
        st,
        code,
        px,
        per,
        day_i,
        day,
        reason=reason,
        is_step=is_step,
        position_id=position_id,
        entry_signal_date=entry_signal_date,
        **volume_kwargs,
    )
    st.daily_quota_used = quota_used
    return bool(filled)


def _run_s8_price_adds_day(
    st, *, day_i, day, ds, names, buy_quote_for, sizing, exdiv,
    qlib_limit_pct, forbid_all_trade_at_limit, buy_gate, volume_bucket_for,
    reference_price_for, confirm_peak_for, exdiv_ref_fen=False,
) -> None:
    policy = s8_policy(st)
    book = policy["name"]
    if not allows_price_add(book, sizing):
        return
    confirm = book == "version8_3"
    gate = policy["allow_new_name"]
    if confirm and callable(gate) and not gate(day):
        # 8.3 has always blocked both new positions and adds at the index gate.
        return
    if policy.get("index_blocks_s8_add") and callable(gate) and not gate(day):
        return
    step_cap = policy.get("step_cap")
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
            if (
                step_cap is not None
                and policy["code_steps"].get(code, 0) >= int(step_cap)
            ):
                # 票级上限在同一次访问的多组之间同样生效。
                st.stats["skip_step_cap"] = int(st.stats.get("skip_step_cap", 0)) + 1
                continue
            cost = float(getattr(group, "anchor_cost", None) or group.first_lot.cost)
            if cost <= 0:
                continue
            _rebuy_rise = None
            if policy.get("cont_stop_rebuy") and group.cont_rebuy_armed:
                lift = float(policy.get("cont_stop_rebuy_lift") or 0.20)
                _rebuy_rise = due_cont_rebuy_rise(
                    group.cont_rebuy_armed, px, cost, lift=lift,
                )
            _rebuy_due = _rebuy_rise is not None
            _sched_due = False
            _sched_rise = None
            schedule = policy.get("add_schedule")
            if schedule and not confirm:
                if policy.get("add_schedule_trigger") == "peak":
                    # 6.49 语义：档位以组峰值触发（盘中触线即记档），14:55 价成交；
                    # 已止损的 lot 不回补档位，executed_steps 继续往前走；价格低于成本不补档。
                    peak_px = float(getattr(group.first_lot, "peak", 0) or 0)
                    trig_rise = (
                        peak_px / cost - 1.0 if peak_px > cost else float(px) / cost - 1.0
                    )
                    sched_gate = float(px) > cost
                else:
                    trig_rise = float(px) / cost - 1.0
                    sched_gate = True
                allowed_sched = sum(1 for t, _f in schedule if trig_rise + 1e-12 >= t)
                if allowed_sched > group.executed_steps and sched_gate:
                    _sched_idx = min(group.executed_steps, len(schedule) - 1)
                    _sched_rise, _sched_frac = schedule[_sched_idx]
                    _sched_due = True
            # 双梯子书：分批腿(1)优先、基数腿(2)次之；单梯子书 use2 恒 False、行为不变。
            use2 = False
            rise = float(px) / cost - 1.0
            if confirm:
                peak = (
                    confirm_peak_for(code, group.first_lot)
                    if confirm_peak_for is not None else group.first_lot.peak
                )
                if group.supplement_done or px < cost or peak < cost * 1.03:
                    continue
            else:
                tranche_max = policy.get("tranche_max")
                offset = int(policy.get("add_offset") or 0)
                allowed1 = int((rise + 1e-12) / float(policy["add_step"])) - offset
                due1 = allowed1 > group.executed_steps and (
                    tranche_max is None or group.executed_steps < int(tranche_max)
                )
                due2 = False
                add_step2 = policy.get("add_step2")
                if add_step2:
                    allowed2 = int((rise + 1e-12) / float(add_step2))
                    cap2 = None
                    zone_caps = policy.get("base_zone_caps")
                    if zone_caps is not None:
                        cap2 = int(zone_caps[1]) if rise + 1e-12 >= 1.0 else int(zone_caps[0])
                    due2 = allowed2 > group.executed_steps2 and (
                        cap2 is None or group.executed_steps2 < cap2
                    )
                if not _rebuy_due and not _sched_due and not due1 and not due2:
                    continue
                use2 = not due1 and not _sched_due and not _rebuy_due  # schedule/rebuy 走 executed_steps，不走 steps2
            if reference_price_for is None:
                prev_close, did_map = mapped_prev_close(exdiv, code, ds, float(closes[-1]), **({"fen_round": True} if exdiv_ref_fen else {}))
            else:
                prev_close, did_map = reference_price_for(code, ds), False
            if did_map:
                st.stats["exdiv_prev_close_mapped"] = (
                    int(st.stats.get("exdiv_prev_close_mapped", 0)) + 1
                )
            limits = book_limit_prices(code, prev_close, names, qlib_limit_pct=qlib_limit_pct, as_of=ds)
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
            volume_kwargs = (
                {"bucket_id": volume_bucket_for(code)}
                if volume_bucket_for is not None else {}
            )
            add_kw = dict(
                code=code,
                px=px,
                day_i=day_i,
                day=day,
                position_id=position_id,
                entry_signal_date=group.entry_signal_date,
                volume_kwargs=volume_kwargs,
            )
            if _rebuy_due:
                any_fill = False
                step_fills = 0
                open_frac = policy.get("cont_stop_rebuy_open_frac")
                if open_frac:
                    if _execute_s8_price_add(
                        st,
                        per=group.budget * float(open_frac),
                        reason="add:cont_rebuy_open",
                        is_step=False,
                        **add_kw,
                    ):
                        any_fill = True
                        st.stats["add_cont_rebuy_open"] = (
                            int(st.stats.get("add_cont_rebuy_open", 0)) + 1
                        )
                if _execute_s8_price_add(
                    st,
                    per=group.budget * float(policy.get("cont_stop_rebuy_frac") or 1.0),
                    reason="add:cont_rebuy",
                    is_step=True,
                    **add_kw,
                ):
                    any_fill = True
                    step_fills += 1
                    group.cont_rebuy_armed.remove(_rebuy_rise)
                    group.cont_rebuy_done.append(_rebuy_rise)
                    st.stats["add_cont_rebuy"] = int(st.stats.get("add_cont_rebuy", 0)) + 1
                if _sched_due and policy.get("cont_stop_rebuy_with_schedule"):
                    if _execute_s8_price_add(
                        st,
                        per=group.budget * float(_sched_frac),
                        reason="add:tranche",
                        is_step=True,
                        **add_kw,
                    ):
                        any_fill = True
                        step_fills += 1
                        group.executed_steps += 1
                        if _sched_rise is not None:
                            note_cont_open(
                                group,
                                group.next_lot_id - 1,
                                float(_sched_rise),
                                from_rise=float(policy.get("cont_from_rise") or 0.40),
                            )
                if any_fill:
                    group.last_add_date = ds
                    if step_cap is not None and step_fills:
                        policy["code_steps"][code] = (
                            policy["code_steps"].get(code, 0) + step_fills
                        )
                continue
            if _sched_due:
                per = group.budget * float(_sched_frac)
                reason = "add:tranche"
            else:
                per = group.budget * (
                    0.50 if confirm else float(policy["step_frac2" if use2 else "step_frac"])
                )
                reason = "add:confirm3" if confirm else ("add:base20" if use2 else "add:step20")
            filled = _execute_s8_price_add(
                st,
                per=per,
                reason=reason,
                is_step=not confirm,
                **add_kw,
            )
            if filled:
                group.last_add_date = ds
                if confirm:
                    group.supplement_done = True
                elif use2:
                    group.executed_steps2 += 1
                else:
                    group.executed_steps += 1
                    if _sched_due and policy.get("cont_stop_rebuy") and _sched_rise is not None:
                        note_cont_open(
                            group,
                            group.next_lot_id - 1,
                            float(_sched_rise),
                            from_rise=float(policy.get("cont_from_rise") or 0.40),
                        )
                if step_cap is not None:
                    policy["code_steps"][code] = policy["code_steps"].get(code, 0) + 1


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
            limits = book_limit_prices(code, prev, names, qlib_limit_pct=qlib_limit_pct, as_of=ds)
            if limits is None:
                st.stats["skip_unknown_board"] += 1
                continue
            if skip_buy_at_limit(px, limits):
                st.stats["skip_limit_up"] += 1
                continue
            declared, _, _, _ = preview_final_buy_declaration(
                st,
                code,
                px,
                shares * px,
                day,
                shares_override=shares,
            )
            notional = declared * px
            if not uses_shrink_on_short_cash(st) and not check_buy_cash(
                st,
                needed=preview_buy_cash_needed(st, code, px, declared, day),
                available=st.cash, date=ds, code=code,
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
            if is_parking_lot(st, pos):
                continue
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


def extra_load_codes_for_strategy(strategy: str) -> set[str]:
    """Codes the lake must load even when they are absent from the pool."""
    from backtest.research.csv_strategy_books import normalize_csv_strategy

    name = normalize_csv_strategy(strategy)
    if name in {"version6_47", "version6_50", "version6_51", "version6_52", "version6_53"}:
        from backtest.research.strategy6_47_rules import PARKING_SYMBOL

        return {PARKING_SYMBOL}
    return set()


def bind_parking_session(
    st: SimState,
    hooks: dict,
    *,
    day_i: int,
    day,
    ds: str,
    names: dict,
    daily_bars: dict,
    exdiv=None,
    qlib_limit_pct=None,
) -> None:
    """Publish today's parking quote so strategy buys can unpark if cash is short."""
    st.book_state.pop("parking_session", None)
    if not hooks.get("parking_execute"):
        return
    symbol = hooks.get("parking_symbol")
    if not symbol:
        return
    got = (
        day_bar_and_prev_closes(daily_bars[symbol], day)
        if symbol in daily_bars else None
    )
    if got is None:
        return
    row, closes = got
    px = float(row["close"])
    if px <= 0 or not math.isfinite(px):
        return
    previous, _ = mapped_prev_close(exdiv, symbol, ds, float(closes[-1]))
    limits = book_limit_prices(
        symbol, previous, names, qlib_limit_pct=qlib_limit_pct, as_of=ds
    )
    if limits is None:
        return
    st.book_state["parking_session"] = {
        "symbol": symbol,
        "px": px,
        "day_i": day_i,
        "day": day,
        "ds": ds,
        "limits": limits,
    }


def run_parking_open_cover_day(
    st: SimState,
    hooks: dict,
    *,
    day_i: int,
    day,
    ds: str,
    names: dict,
    daily_bars: dict,
    exdiv=None,
    qlib_limit_pct=None,
    forbid_all_trade_at_limit: bool = False,
) -> None:
    """At the open, sell parking only to bring cash up to the buffer.

    Strategy buys run after this. Same-day parking stays T+1 locked. Limit-down
    defers; leftover shortfall still goes through ``release_parking_cash``.
    """
    if not hooks.get("parking_execute") or not hooks.get("parking_open_cover"):
        return
    symbol = hooks.get("parking_symbol")
    buffer = float(hooks.get("parking_buffer") or 0.0)
    if not symbol or buffer <= 0 or float(st.cash) + 1e-9 >= buffer:
        return
    lots = sleeve_parking_lots(st, symbol)
    if not lots:
        return
    got = (
        day_bar_and_prev_closes(daily_bars[symbol], day)
        if symbol in daily_bars else None
    )
    if got is None:
        return
    row, closes = got
    px = float(row["open"])
    if px <= 0 or not math.isfinite(px):
        return
    previous, _ = mapped_prev_close(exdiv, symbol, ds, float(closes[-1]))
    limits = book_limit_prices(
        symbol, previous, names, qlib_limit_pct=qlib_limit_pct, as_of=ds
    )
    if limits is None:
        return
    if defer_sell_at_limit(px, limits) or (
        forbid_all_trade_at_limit and (
            skip_buy_at_limit(px, limits) or defer_sell_at_limit(px, limits)
        )
    ):
        st.stats["skip_parking_limit"] = int(st.stats.get("skip_parking_limit", 0)) + 1
        return
    sold_any = False
    for lot in lots:
        while float(st.cash) + 1e-9 < buffer and int(getattr(lot, "shares", 0) or 0) >= BOARD_LOT:
            if lot.entry_idx >= day_i:
                st.stats["skip_parking_t1"] = int(st.stats.get("skip_parking_t1", 0)) + 1
                break
            shortfall = buffer - float(st.cash)
            raw = int(math.ceil(shortfall / px / BOARD_LOT) * BOARD_LOT)
            chunk = min(int(lot.shares), max(BOARD_LOT, raw))
            filled = _sell(
                st,
                symbol,
                lot,
                px,
                day,
                "parking:open_cover",
                day_i=day_i,
                wanted_shares=chunk,
                price_rule="parking_open",
            )
            if not filled:
                break
            sold_any = True
            st.stats["parking_sold_shares"] = (
                int(st.stats.get("parking_sold_shares", 0)) + int(filled)
            )
    if sold_any:
        st.stats["parking_open_cover_days"] = (
            int(st.stats.get("parking_open_cover_days", 0)) + 1
        )
        st.stats["parking_sells"] = int(st.stats.get("parking_sells", 0)) + 1


def _index_cut_state(st: SimState) -> dict:
    return st.book_state.setdefault("index_cut", {"latched": False, "memory": {}})


def _index_group_lots(st: SimState, code: str, position_id: str) -> list:
    return [
        pos
        for pos in st.positions.get(code, [])
        if getattr(pos, "position_id", None) == position_id and not is_parking_lot(st, pos)
    ]


def _index_open_quote(
    daily_bars: dict,
    code: str,
    day,
    ds: str,
    names: dict,
    exdiv,
    qlib_limit_pct,
):
    if not daily_bars or code not in daily_bars:
        return None
    got = day_bar_and_prev_closes(daily_bars[code], day)
    if got is None:
        return None
    row, closes = got
    px = float(row["open"])
    if px <= 0 or not math.isfinite(px):
        return None
    previous, _ = mapped_prev_close(exdiv, code, ds, float(closes[-1]))
    limits = book_limit_prices(
        code, previous, names, qlib_limit_pct=qlib_limit_pct, as_of=ds
    )
    if limits is None:
        return None
    return px, limits


def _execute_index_cuts(
    st: SimState,
    hooks: dict,
    *,
    day_i: int,
    day,
    ds: str,
    names: dict,
    daily_bars: dict,
    exdiv=None,
    qlib_limit_pct=None,
    forbid_all_trade_at_limit: bool = False,
) -> None:
    from backtest.research.strategy6_53_rules import index_cut_shares

    frac = float(hooks.get("index_cut_frac") or 0.50)
    min_keep = int(hooks.get("index_cut_min_keep") or 100)
    memory = _index_cut_state(st)["memory"]
    for code in list(st.positions):
        for position_id, _group in list(s8_open_groups(st, code)):
            lots = _index_group_lots(st, code, position_id)
            held = sum(int(pos.shares) for pos in lots)
            sell_n = index_cut_shares(held, frac=frac, min_keep=min_keep)
            if sell_n <= 0:
                continue
            quoted = _index_open_quote(
                daily_bars, code, day, ds, names, exdiv, qlib_limit_pct
            )
            if quoted is None:
                continue
            px, limits = quoted
            if defer_sell_at_limit(px, limits) or (
                forbid_all_trade_at_limit and hit_limit_up(px, limits[0])
            ):
                st.stats["defer_sell_limit_down"] = (
                    int(st.stats.get("defer_sell_limit_down", 0)) + 1
                )
                continue
            remain = sell_n
            sold = 0
            for lot in sorted(lots, key=lambda pos: (int(pos.entry_idx), int(pos.lot_id))):
                if remain <= 0:
                    break
                filled = _sell(
                    st,
                    code,
                    lot,
                    px,
                    day,
                    "index_cut",
                    day_i=day_i,
                    wanted_shares=remain,
                    price_rule="index_cut_open",
                )
                if filled:
                    sold += int(filled)
                    remain -= int(filled)
            if sold:
                memory[position_id] = int(memory.get(position_id, 0)) + sold
                st.stats["index_cut_shares"] = (
                    int(st.stats.get("index_cut_shares", 0)) + sold
                )
                st.stats["index_cut_events"] = int(st.stats.get("index_cut_events", 0)) + 1


def _execute_index_rebuys(
    st: SimState,
    hooks: dict,
    *,
    day_i: int,
    day,
    ds: str,
    names: dict,
    daily_bars: dict,
    exdiv=None,
    qlib_limit_pct=None,
    forbid_all_trade_at_limit: bool = False,
) -> None:
    policy = s8_policy(st)
    if policy is None:
        return
    memory = _index_cut_state(st)["memory"]
    for position_id, shares in list(memory.items()):
        want = int(shares)
        if want <= 0:
            memory.pop(position_id, None)
            continue
        group = policy["groups"].get(position_id)
        if group is None or group.closed:
            memory.pop(position_id, None)
            continue
        code = position_id.split("@", 1)[0]
        quoted = _index_open_quote(
            daily_bars, code, day, ds, names, exdiv, qlib_limit_pct
        )
        if quoted is None:
            continue
        px, limits = quoted
        if skip_buy_at_limit(px, limits) or (
            forbid_all_trade_at_limit and hit_limit_down(px, limits[1])
        ):
            st.stats["skip_limit_up"] = int(st.stats.get("skip_limit_up", 0)) + 1
            continue
        filled = execute_buy(
            st,
            code,
            px,
            want * px,
            day_i,
            day,
            reason="add:index_rebuy",
            shares_override=want,
            is_step=False,
            position_id=position_id,
            entry_signal_date=group.entry_signal_date,
        )
        if not filled:
            continue
        got = int(st.trades[-1]["shares"])
        left = want - got
        if left <= 0:
            memory.pop(position_id, None)
        else:
            memory[position_id] = left
        st.stats["index_rebuy_shares"] = int(st.stats.get("index_rebuy_shares", 0)) + got
        st.stats["index_rebuy_events"] = int(st.stats.get("index_rebuy_events", 0)) + 1


def run_index_gate_cut_day(
    st: SimState,
    hooks: dict,
    *,
    day_i: int,
    day,
    ds: str,
    names: dict,
    daily_bars: dict,
    exdiv=None,
    qlib_limit_pct=None,
    forbid_all_trade_at_limit: bool = False,
) -> None:
    """Open of a blocked SSE-MA10 episode: halt new chips and halve strategy book.

    Same episode is cut once. When the gate lifts, buy back remembered shares
    at the open before pool/adds. Parking lots are not touched.
    """
    if not hooks.get("index_cut"):
        return
    allow = hooks.get("allow_new_name")
    blocked = callable(allow) and not allow(day)
    state = _index_cut_state(st)
    if blocked:
        if not state["latched"]:
            _execute_index_cuts(
                st,
                hooks,
                day_i=day_i,
                day=day,
                ds=ds,
                names=names,
                daily_bars=daily_bars,
                exdiv=exdiv,
                qlib_limit_pct=qlib_limit_pct,
                forbid_all_trade_at_limit=forbid_all_trade_at_limit,
            )
            state["latched"] = True
        return
    if state["memory"]:
        _execute_index_rebuys(
            st,
            hooks,
            day_i=day_i,
            day=day,
            ds=ds,
            names=names,
            daily_bars=daily_bars,
            exdiv=exdiv,
            qlib_limit_pct=qlib_limit_pct,
            forbid_all_trade_at_limit=forbid_all_trade_at_limit,
        )
    state["latched"] = False


def working_equity(st: SimState, day, mark_bars: dict) -> float:
    """Cash + position marks; same sum as ``append_equity_and_eod_marks``."""
    eq = float(st.cash)
    if st.exdiv_economics is not None:
        eq += st.exdiv_economics.receivable_total
    for code, lots in st.positions.items():
        mark = market_close_mark(mark_bars.get(code), day) if mark_bars else None
        for pos in lots:
            last = float(pos.cost) if mark is None else mark
            eq += int(pos.shares) * last
    return eq


def _skim_quote(daily_bars, code, day, ds, names, exdiv, qlib_limit_pct):
    if not daily_bars or code not in daily_bars:
        return None
    got = day_bar_and_prev_closes(daily_bars[code], day)
    if got is None:
        return None
    row, closes = got
    px = float(row["close"])
    if px <= 0 or not math.isfinite(px):
        return None
    previous, _ = mapped_prev_close(exdiv, code, ds, float(closes[-1]))
    limits = book_limit_prices(
        code, previous, names, qlib_limit_pct=qlib_limit_pct, as_of=ds
    )
    return px, limits


def _skim_chunk_shares(gap: float, px: float, lot_shares: int) -> int:
    if gap <= 1e-9 or px <= 0 or lot_shares < BOARD_LOT:
        return 0
    raw = int(math.ceil(gap / px / BOARD_LOT) * BOARD_LOT)
    return min(int(lot_shares), max(BOARD_LOT, raw))


def _sell_skim_chunk(
    st: SimState,
    hooks: dict,
    *,
    gap: float,
    day_i: int,
    day,
    ds: str,
    names: dict,
    daily_bars: dict,
    exdiv=None,
    qlib_limit_pct=None,
    forbid_all_trade_at_limit: bool = False,
) -> int:
    """Sell one parking-then-strategy chunk to raise ``gap`` cash. Returns shares."""

    def _try_lot(code, lot, reason):
        if int(getattr(lot, "shares", 0) or 0) < BOARD_LOT:
            return 0
        if lot.entry_idx >= day_i:
            st.stats["skip_profit_skim_t1"] = int(st.stats.get("skip_profit_skim_t1", 0)) + 1
            return 0
        quote = _skim_quote(daily_bars, code, day, ds, names, exdiv, qlib_limit_pct)
        if quote is None:
            return 0
        px, limits = quote
        if limits is None:
            return 0
        if defer_sell_at_limit(px, limits) or (
            forbid_all_trade_at_limit and (
                skip_buy_at_limit(px, limits) or defer_sell_at_limit(px, limits)
            )
        ):
            st.stats["skip_profit_skim_limit"] = (
                int(st.stats.get("skip_profit_skim_limit", 0)) + 1
            )
            return 0
        chunk = _skim_chunk_shares(gap, px, int(lot.shares))
        if chunk < BOARD_LOT:
            return 0
        return int(
            _sell(
                st,
                code,
                lot,
                px,
                day,
                reason,
                day_i=day_i,
                wanted_shares=chunk,
                price_rule="profit_skim_eod_close",
            )
            or 0
        )

    symbol = hooks.get("parking_symbol")
    if symbol:
        for lot in list(parking_lots(st, symbol)):
            filled = _try_lot(symbol, lot, "parking:profit_skim")
            if filled:
                return filled
    for code, lots in list(st.positions.items()):
        for lot in list(lots):
            if is_parking_lot(st, lot):
                continue
            filled = _try_lot(code, lot, "profit_skim")
            if filled:
                return filled
    return 0


def _sellable_strategy_skim_lots(
    st: SimState,
    *,
    day_i: int,
    day,
    ds: str,
    names: dict,
    daily_bars: dict,
    exdiv=None,
    qlib_limit_pct=None,
    forbid_all_trade_at_limit: bool = False,
) -> list[tuple[str, object, float, float]]:
    """Strategy lots that can sell at EOD close. Parking excluded."""
    rows: list[tuple[str, object, float, float]] = []
    for code, lots in list(st.positions.items()):
        for lot in list(lots):
            if is_parking_lot(st, lot):
                continue
            if int(getattr(lot, "shares", 0) or 0) < BOARD_LOT:
                continue
            if lot.entry_idx >= day_i:
                st.stats["skip_profit_skim_t1"] = (
                    int(st.stats.get("skip_profit_skim_t1", 0)) + 1
                )
                continue
            quote = _skim_quote(daily_bars, code, day, ds, names, exdiv, qlib_limit_pct)
            if quote is None:
                continue
            px, limits = quote
            if limits is None:
                continue
            if defer_sell_at_limit(px, limits) or (
                forbid_all_trade_at_limit and (
                    skip_buy_at_limit(px, limits) or defer_sell_at_limit(px, limits)
                )
            ):
                st.stats["skip_profit_skim_limit"] = (
                    int(st.stats.get("skip_profit_skim_limit", 0)) + 1
                )
                continue
            mtm = int(lot.shares) * px
            if mtm <= 0:
                continue
            rows.append((code, lot, px, mtm))
    return rows


def _sell_skim_pro_rata(
    st: SimState,
    *,
    gap: float,
    day_i: int,
    day,
    ds: str,
    names: dict,
    daily_bars: dict,
    exdiv=None,
    qlib_limit_pct=None,
    forbid_all_trade_at_limit: bool = False,
) -> int:
    """Sell the same MV fraction of every sellable strategy lot. Returns shares."""
    rows = _sellable_strategy_skim_lots(
        st,
        day_i=day_i,
        day=day,
        ds=ds,
        names=names,
        daily_bars=daily_bars,
        exdiv=exdiv,
        qlib_limit_pct=qlib_limit_pct,
        forbid_all_trade_at_limit=forbid_all_trade_at_limit,
    )
    total = sum(mtm for *_, mtm in rows)
    if gap <= 1e-9 or total <= 1e-9:
        return 0
    frac = min(1.0, gap / total)
    sold = 0
    leftovers: list[tuple[str, object, float, float]] = []
    for code, lot, px, mtm in rows:
        want = int(math.floor(int(lot.shares) * frac / BOARD_LOT) * BOARD_LOT)
        leftovers.append((code, lot, px, mtm))
        if want < BOARD_LOT:
            continue
        filled = int(
            _sell(
                st,
                code,
                lot,
                px,
                day,
                "profit_skim",
                day_i=day_i,
                wanted_shares=want,
                price_rule="profit_skim_eod_close",
            )
            or 0
        )
        sold += filled
    if sold:
        return sold
    leftovers.sort(key=lambda row: row[3], reverse=True)
    for code, lot, px, _mtm in leftovers:
        if int(getattr(lot, "shares", 0) or 0) < BOARD_LOT:
            continue
        if px * BOARD_LOT > gap + 1e-9:
            continue
        filled = int(
            _sell(
                st,
                code,
                lot,
                px,
                day,
                "profit_skim",
                day_i=day_i,
                wanted_shares=BOARD_LOT,
                price_rule="profit_skim_eod_close",
            )
            or 0
        )
        if filled:
            return filled
    return 0


def _transfer_sleeve_to_principal(
    st: SimState,
    symbol: str,
    *,
    need: float,
    px: float,
    count_skim: bool = True,
) -> float:
    """Re-tag idle 600036 sleeve lots as 本金. Returns close-mark transferred."""
    if need <= 1e-6 or px <= 0 or not symbol:
        return 0.0
    transferred = 0.0
    lots = st.positions.setdefault(symbol, [])
    for lot in list(sleeve_parking_lots(st, symbol)):
        if transferred + 1e-6 >= need:
            break
        shares = int(getattr(lot, "shares", 0) or 0)
        if shares < BOARD_LOT:
            continue
        remain = need - transferred
        want = int(math.floor(remain / px / BOARD_LOT) * BOARD_LOT)
        if want < BOARD_LOT:
            continue
        chunk = min(shares, want)
        if chunk <= 0:
            continue
        if chunk >= shares:
            register_principal_lot(st, lot)
            transferred += shares * px
            st.stats["profit_skim_transfer_lots"] = (
                int(st.stats.get("profit_skim_transfer_lots", 0)) + 1
            )
            continue
        lot.shares = shares - chunk
        next_id = max((int(p.lot_id) for p in lots), default=-1) + 1
        moved = Position(
            code=symbol,
            shares=chunk,
            cost=float(lot.cost),
            entry_idx=int(lot.entry_idx),
            peak=float(lot.peak),
            peak_hm=int(getattr(lot, "peak_hm", -1)),
            lot_id=next_id,
        )
        lots.append(moved)
        register_principal_lot(st, moved)
        transferred += chunk * px
        st.stats["profit_skim_transfer_lots"] = (
            int(st.stats.get("profit_skim_transfer_lots", 0)) + 1
        )
    if transferred > 1e-6 and count_skim:
        st.stats["profit_skim_transferred"] = (
            float(st.stats.get("profit_skim_transferred", 0.0)) + transferred
        )
    return transferred


def _buy_skim_principal(
    st: SimState,
    hooks: dict,
    *,
    budget: float,
    day_i: int,
    day,
    ds: str,
    names: dict,
    daily_bars: dict,
    exdiv=None,
    qlib_limit_pct=None,
    forbid_all_trade_at_limit: bool = False,
    reason: str = "parking:profit_skim",
    count_skim: bool = True,
) -> float:
    """Lock idle cash into 600036 as 本金. Returns cash actually spent."""
    symbol = hooks.get("parking_symbol")
    if not symbol or budget <= 1e-6:
        return 0.0
    quote = _skim_quote(daily_bars, symbol, day, ds, names, exdiv, qlib_limit_pct)
    if quote is None:
        st.stats["skip_profit_skim_no_bar"] = (
            int(st.stats.get("skip_profit_skim_no_bar", 0)) + 1
        )
        return 0.0
    px, limits = quote
    if limits is None:
        st.stats["skip_profit_skim_unknown_board"] = (
            int(st.stats.get("skip_profit_skim_unknown_board", 0)) + 1
        )
        return 0.0
    at_limit = skip_buy_at_limit(px, limits) or defer_sell_at_limit(px, limits)
    if skip_buy_at_limit(px, limits) or (
        forbid_all_trade_at_limit and at_limit
    ):
        st.stats["skip_profit_skim_limit"] = (
            int(st.stats.get("skip_profit_skim_limit", 0)) + 1
        )
        return 0.0
    before = {id(lot) for lot in parking_lots(st, symbol)}
    cash0 = float(st.cash)
    execute_parking_buy(
        st, symbol, px, budget, day_i, day, reason=reason
    )
    for lot in parking_lots(st, symbol):
        if id(lot) not in before:
            register_principal_lot(st, lot)
    spent = max(0.0, cash0 - float(st.cash))
    if spent > 1e-6 and count_skim:
        st.stats["profit_skim_park_buys"] = (
            int(st.stats.get("profit_skim_park_buys", 0)) + 1
        )
    return spent


def _profit_skim_extracted(st: SimState) -> float:
    return (
        float(st.stats.get("profit_skim_parked", 0.0))
        + float(st.stats.get("profit_skim_withdrawn", 0.0))
    )


def _idle_fill_principal(
    st: SimState,
    hooks: dict,
    *,
    need: float,
    count_skim: bool,
    reason: str,
    day_i: int,
    day,
    ds: str,
    names: dict,
    daily_bars: dict,
    exdiv=None,
    qlib_limit_pct=None,
    forbid_all_trade_at_limit: bool = False,
) -> float:
    """Move idle sleeve / cash-above-buffer into 本金. Returns notional filled."""
    if need <= 1e-6:
        return 0.0
    symbol = hooks.get("parking_symbol")
    buffer = float(hooks.get("parking_buffer") or 0.0)
    filled = 0.0
    if symbol:
        quote = _skim_quote(daily_bars, symbol, day, ds, names, exdiv, qlib_limit_pct)
        if quote is not None:
            px, limits = quote
            if limits is not None and px > 0:
                filled += _transfer_sleeve_to_principal(
                    st, symbol, need=need, px=px, count_skim=count_skim
                )
    remain = max(0.0, need - filled)
    if remain > 1e-6:
        avail = max(0.0, float(st.cash) - buffer)
        if avail > 1e-6:
            spent = _buy_skim_principal(
                st,
                hooks,
                budget=min(remain, avail),
                day_i=day_i,
                day=day,
                ds=ds,
                names=names,
                daily_bars=daily_bars,
                exdiv=exdiv,
                qlib_limit_pct=qlib_limit_pct,
                forbid_all_trade_at_limit=forbid_all_trade_at_limit,
                reason=reason,
                count_skim=count_skim,
            )
            filled += spent
    return filled


def _profit_skim_owed(equity: float, *, base: float, step: float, frac: float, withdrawn: float) -> float:
    """Lifetime frac-of-base per completed +step rung, minus already withdrawn."""
    if base <= 0 or step <= 0 or frac <= 0:
        return 0.0
    gain = float(equity) / float(base) - 1.0
    rungs = int(gain / step + 1e-12) if gain > 0 else 0
    if rungs <= 0:
        return 0.0
    return max(0.0, rungs * frac * base - float(withdrawn))


def _run_profit_skim_to_parking(
    st: SimState,
    hooks: dict,
    *,
    owed: float,
    day_i: int,
    day,
    ds: str,
    names: dict,
    daily_bars: dict,
    exdiv=None,
    qlib_limit_pct=None,
    forbid_all_trade_at_limit: bool = False,
) -> None:
    """Lock owed rungs into 600036 from idle only. No strategy sells."""
    got = _idle_fill_principal(
        st,
        hooks,
        need=owed,
        count_skim=True,
        reason="parking:profit_skim",
        day_i=day_i,
        day=day,
        ds=ds,
        names=names,
        daily_bars=daily_bars,
        exdiv=exdiv,
        qlib_limit_pct=qlib_limit_pct,
        forbid_all_trade_at_limit=forbid_all_trade_at_limit,
    )
    if got > 1e-6:
        st.stats["profit_skim_parked"] = (
            float(st.stats.get("profit_skim_parked", 0.0)) + got
        )
        st.stats["profit_skim_events"] = int(st.stats.get("profit_skim_events", 0)) + 1
    leftover = max(0.0, owed - got)
    st.stats["profit_skim_pending_notional"] = leftover
    if leftover > 1e-6:
        st.stats["profit_skim_pending"] = int(st.stats.get("profit_skim_pending", 0)) + 1


def _restore_lock_from_idle(
    st: SimState,
    hooks: dict,
    *,
    day_i: int,
    day,
    ds: str,
    names: dict,
    daily_bars: dict,
    exdiv=None,
    qlib_limit_pct=None,
    forbid_all_trade_at_limit: bool = False,
) -> None:
    """Buy back 锁仓 sold for adds, after pending skim, before sleeve rebalance."""
    drawn = float(st.stats.get("profit_skim_lock_drawn", 0.0))
    if drawn <= 1e-6:
        return
    got = _idle_fill_principal(
        st,
        hooks,
        need=drawn,
        count_skim=False,
        reason="parking:lock_restore",
        day_i=day_i,
        day=day,
        ds=ds,
        names=names,
        daily_bars=daily_bars,
        exdiv=exdiv,
        qlib_limit_pct=qlib_limit_pct,
        forbid_all_trade_at_limit=forbid_all_trade_at_limit,
    )
    if got <= 1e-6:
        return
    st.stats["profit_skim_lock_drawn"] = max(0.0, drawn - got)
    st.stats["profit_skim_lock_restored"] = (
        float(st.stats.get("profit_skim_lock_restored", 0.0)) + got
    )
    st.stats["profit_skim_lock_restore_events"] = (
        int(st.stats.get("profit_skim_lock_restore_events", 0)) + 1
    )


def run_profit_skim_day(
    st: SimState,
    hooks: dict,
    *,
    day_i: int,
    day,
    ds: str,
    names: dict,
    daily_bars: dict,
    exdiv=None,
    qlib_limit_pct=None,
    forbid_all_trade_at_limit: bool = False,
) -> None:
    """Each +20% rung locks that gain into 600036 本金 from idle only.

    Order: transfer idle parking, spend cash above the parking buffer, leave
    unpaid rungs pending. Then restore 锁仓 sold for adds. Sleeve rebalance
    runs after this. Never sells strategy chips.
    """
    if not hooks.get("profit_skim"):
        return
    step = float(hooks.get("profit_skim_step") or 0.0)
    frac = float(
        hooks.get("profit_skim_frac")
        or st.stats.get("profit_skim_frac")
        or 0.0
    )
    base = float(hooks.get("profit_skim_base") or st.stats.get("profit_skim_base") or 0.0)
    if step <= 0 or frac <= 0 or base <= 0:
        return
    extracted = _profit_skim_extracted(st)
    to_parking = bool(hooks.get("profit_skim_to_parking"))
    equity = working_equity(st, day, daily_bars)
    owed = _profit_skim_owed(
        equity, base=base, step=step, frac=frac, withdrawn=extracted
    )
    if to_parking:
        if owed > 1e-6:
            _run_profit_skim_to_parking(
                st,
                hooks,
                owed=owed,
                day_i=day_i,
                day=day,
                ds=ds,
                names=names,
                daily_bars=daily_bars,
                exdiv=exdiv,
                qlib_limit_pct=qlib_limit_pct,
                forbid_all_trade_at_limit=forbid_all_trade_at_limit,
            )
        _restore_lock_from_idle(
            st,
            hooks,
            day_i=day_i,
            day=day,
            ds=ds,
            names=names,
            daily_bars=daily_bars,
            exdiv=exdiv,
            qlib_limit_pct=qlib_limit_pct,
            forbid_all_trade_at_limit=forbid_all_trade_at_limit,
        )
        return
    if owed <= 1e-6:
        return
    cash0 = float(st.cash)
    keep_idle = bool(hooks.get("profit_skim_keep_idle"))
    pro_rata = bool(hooks.get("profit_skim_pro_rata"))
    sold_shares = 0
    for _ in range(256):
        raised = max(0.0, float(st.cash) - cash0)
        need = owed - raised
        if need <= 1e-6:
            break
        if pro_rata:
            filled = _sell_skim_pro_rata(
                st,
                gap=need,
                day_i=day_i,
                day=day,
                ds=ds,
                names=names,
                daily_bars=daily_bars,
                exdiv=exdiv,
                qlib_limit_pct=qlib_limit_pct,
                forbid_all_trade_at_limit=forbid_all_trade_at_limit,
            )
        else:
            filled = _sell_skim_chunk(
                st,
                hooks,
                gap=need,
                day_i=day_i,
                day=day,
                ds=ds,
                names=names,
                daily_bars=daily_bars,
                exdiv=exdiv,
                qlib_limit_pct=qlib_limit_pct,
                forbid_all_trade_at_limit=forbid_all_trade_at_limit,
            )
        if filled:
            sold_shares += filled
            continue
        break
    raised = max(0.0, float(st.cash) - cash0)
    if keep_idle:
        take = min(owed, raised)
    else:
        take = min(owed, float(st.cash))
    if take > 1e-6:
        st.cash = float(st.cash) - take
        st.stats["profit_skim_withdrawn"] = (
            float(st.stats.get("profit_skim_withdrawn", 0.0)) + take
        )
        st.stats["profit_skim_events"] = int(st.stats.get("profit_skim_events", 0)) + 1
        leftover = owed - take
    else:
        leftover = owed
    if leftover > 1e-6:
        st.stats["profit_skim_pending"] = int(st.stats.get("profit_skim_pending", 0)) + 1
    if sold_shares:
        st.stats["profit_skim_sold_shares"] = (
            int(st.stats.get("profit_skim_sold_shares", 0)) + sold_shares
        )
        st.stats["profit_skim_sells"] = int(st.stats.get("profit_skim_sells", 0)) + 1


def run_parking_rebalance_day(
    st: SimState,
    hooks: dict,
    *,
    day_i: int,
    day,
    ds: str,
    names: dict,
    daily_bars: dict,
    exdiv=None,
    qlib_limit_pct=None,
    forbid_all_trade_at_limit: bool = False,
) -> None:
    """Put idle cash into 600036 after the strategy day; flatten below buffer.

    Lots are plain Position rows (not S8 groups) so trail / step / scale / peak
    scanners never sell them. Equity marks include their market value.
    """
    if not hooks.get("parking_execute"):
        return
    symbol = hooks.get("parking_symbol")
    if not symbol:
        return
    frac = float(hooks.get("parking_frac") or 0.0)
    buffer = float(hooks.get("parking_buffer") or 0.0)
    if frac <= 0:
        return
    got = (
        day_bar_and_prev_closes(daily_bars[symbol], day)
        if symbol in daily_bars else None
    )
    if got is None:
        st.stats["skip_parking_no_bar"] = int(st.stats.get("skip_parking_no_bar", 0)) + 1
        return
    row, closes = got
    px = float(row["close"])
    if px <= 0 or not math.isfinite(px):
        st.stats["skip_parking_no_bar"] = int(st.stats.get("skip_parking_no_bar", 0)) + 1
        return
    previous, _ = mapped_prev_close(exdiv, symbol, ds, float(closes[-1]))
    limits = book_limit_prices(
        symbol, previous, names, qlib_limit_pct=qlib_limit_pct, as_of=ds
    )
    if limits is None:
        st.stats["skip_parking_unknown_board"] = (
            int(st.stats.get("skip_parking_unknown_board", 0)) + 1
        )
        return
    lots = sleeve_parking_lots(st, symbol)
    held = sum(int(p.shares) for p in lots)
    mtm = held * px
    idle = float(st.cash) + mtm
    if idle <= buffer + 1e-9:
        target_shares = 0
    else:
        target_shares = budget_board_lots(max(0.0, idle - buffer) * frac, px)
    delta = int(target_shares) - held
    if abs(delta) < BOARD_LOT:
        return
    at_limit = skip_buy_at_limit(px, limits) or defer_sell_at_limit(px, limits)
    if forbid_all_trade_at_limit and at_limit:
        st.stats["skip_parking_limit"] = int(st.stats.get("skip_parking_limit", 0)) + 1
        return
    if delta >= BOARD_LOT:
        if skip_buy_at_limit(px, limits):
            st.stats["skip_parking_limit"] = int(st.stats.get("skip_parking_limit", 0)) + 1
            return
        execute_parking_buy(st, symbol, px, float(delta) * px, day_i, day)
        return
    if defer_sell_at_limit(px, limits):
        st.stats["skip_parking_limit"] = int(st.stats.get("skip_parking_limit", 0)) + 1
        return
    want = -delta
    sold = 0
    for lot in lots:
        if sold >= want:
            break
        if lot.entry_idx >= day_i:
            st.stats["skip_parking_t1"] = int(st.stats.get("skip_parking_t1", 0)) + 1
            continue
        chunk = min(int(lot.shares), want - sold)
        filled = _sell(
            st,
            symbol,
            lot,
            px,
            day,
            "parking:rebalance",
            day_i=day_i,
            wanted_shares=chunk,
            price_rule="parking_daily_close",
        )
        sold += int(filled)
    if sold:
        st.stats["parking_sells"] = int(st.stats.get("parking_sells", 0)) + 1
        st.stats["parking_sold_shares"] = (
            int(st.stats.get("parking_sold_shares", 0)) + sold
        )


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


def run_breakout_day(
    st, *, day_i, day, ds, names, pool_days, buy_quote_for,
    exdiv=None, exdiv_ref_fen=False, qlib_limit_pct=None, breakout_mult=1.2,
):
    """v6.11 突破书：T0 名单日记 A0=14:55 收盘；自 T+1 起 px ≥ A0×mult 即买 1 基。

    信号无限期有效；突破日 14:55 涨停则继续等；开组后 anchor_cost=A0。
    持仓期除权对 A0 等比缩放（与组内 lot 同口径）。
    """
    policy = s8_policy(st)
    if policy is None:
        return
    pending = st.book_state.setdefault("breakout_pending", {})
    for code in pool_days.get(ds, []):
        key = f"{code}@{ds}"
        if key in pending or key in policy["groups"]:
            continue
        quoted = buy_quote_for(code)
        if quoted is None:
            continue
        px, closes = quoted
        if not closes or float(px) <= 0:
            continue
        pending[key] = (float(px), day_i)
        st.stats["breakout_signals"] = int(st.stats.get("breakout_signals", 0)) + 1
    for key in list(pending):
        code, sig_ds = key.split("@", 1)
        a0, sig_idx = pending[key]
        if sig_idx >= day_i:
            continue
        kk = k_for(exdiv, code, ds) if exdiv is not None else None
        if kk is not None:
            a0 *= float(kk)
            pending[key] = (a0, sig_idx)
        if key in policy["groups"]:
            del pending[key]
            continue
        quoted = buy_quote_for(code)
        if quoted is None:
            continue
        px, closes = quoted
        if not closes or float(px) <= 0:
            continue
        if float(px) < a0 * float(breakout_mult):
            continue
        prev_close, _ = mapped_prev_close(
            exdiv, code, ds, float(closes[-1]),
            **({"fen_round": True} if exdiv_ref_fen else {}),
        )
        limits = book_limit_prices(
            code, prev_close, names, qlib_limit_pct=qlib_limit_pct, as_of=ds
        )
        if limits is None:
            st.stats["skip_unknown_board"] += 1
            continue
        if skip_buy_at_limit(px, limits):
            st.stats["skip_limit_up"] += 1
            continue
        filled = execute_buy(
            st, code, px, float(policy["name_budget"]), day_i, day,
            reason="breakout", position_id=key, entry_signal_date=sig_ds,
        )
        if filled:
            del pending[key]
            policy["groups"][key].anchor_cost = a0
            st.stats["breakout_buys"] = int(st.stats.get("breakout_buys", 0)) + 1
