"""Opt-in strategy 12 orchestration; shared ledger remains the fill authority."""

from __future__ import annotations

from decimal import Decimal

import numpy as np

from backtest.research import strategy12_rules as rules
from backtest.research.csv_common import book_limit_prices, day_bar_and_prev_closes
from backtest.research.csv_ledger import (
    _locked_bonus,
    _sell,
    apply_exdiv_economics,
    rescale_position,
)
from backtest.research.csv_simulate_loop import (
    apply_capital_ration,
    run_buybacks_day,
    run_chase_due_day,
    run_pool_buys_day,
    run_step_adds_day,
)
from backtest.research.ashare_session import defer_sell_at_limit
from backtest.research.exdiv_map import k_for, mapped_prev_close


def memories(st) -> dict[str, rules.CodeMemory]:
    return st.book_state.setdefault("strategy12", {})


def memory_for(st, code) -> rules.CodeMemory:
    return memories(st).setdefault(code, rules.CodeMemory())


def on_buy(st, code, reason, shares) -> None:
    if shares <= 0:
        return
    mem = memory_for(st, code)
    if mem.first_px is None:
        lots = st.positions.get(code) or []
        if lots and float(lots[-1].cost) > 0:
            mem.first_px = float(lots[-1].cost)
    if reason == "pool" or reason.startswith("chase"):
        mem.fresh_buy()
    elif reason == "add:step20":
        mem.steps += 1


def on_exdiv(st, code, event) -> None:
    factor = Decimal(1) + Decimal(str(event.bonus_ratio))
    residuals = rules.scale_memory(memory_for(st, code), factor)
    for channel, residual in residuals.items():
        key = f"strategy12_exdiv_{channel}_residual"
        st.stats[key] = st.stats.get(key, 0.0) + residual


def sell_lots(st, code, day_i, ds) -> list[rules.SellLot]:
    result = []
    for pos in st.positions.get(code, []):
        available = pos.shares if pos.entry_idx < day_i else 0
        if st.exdiv_economics is not None:
            available = max(0, available - _locked_bonus(st.exdiv_economics, pos, ds))
        result.append(rules.SellLot(
            pos.lot_id, pos.shares, available, pos.is_step,
            n_days=day_i - pos.entry_idx, cost=float(pos.cost),
        ))
    return result


def plan_exit(st, code, px, day, closes, *, day_i, ds):
    return rules.exit_plan(code, px, day, closes, sell_lots(st, code, day_i, ds),
                           memory=memory_for(st, code))


def plan_buybacks(st, code, px, day, closes):
    """Stop buyback is closed. Price returning to the first fill buys nothing."""
    del st, code, px, day, closes
    return []


def on_reclaim(st, code, reason, shares):
    if reason == rules.RECLAIM_FIRST:
        memory_for(st, code).stopped.reclaimed(shares)
        return
    channel = "reduced" if reason == rules.RECLAIM5 else "stopped"
    getattr(memory_for(st, code), channel).reclaimed(shares)


def queue_exit(st, code, plan, *, day_i, ds, px=None):
    """Pin a deferred daily exit to the lots sellable when the close signalled.

    Without this the next open re-allocates onto pool/chase/step lots bought
    after the signal, leaving the measured lot held and the cycle latched.
    """
    reason, wanted = plan[0], plan[1]
    lots = sell_lots(st, code, day_i, ds)
    if reason == rules.HOLD20:
        pinned = rules.hold20_orders(lots, 0.0 if px is None else px)
    else:
        pinned = rules.allocate_exit(lots, wanted, keep_anchor=reason == rules.REDUCE)
    return reason, wanted, pinned


def fill_exit(st, code, px, day, *, day_i, ds, plan, limits, open_px,
              bucket_id=None, price_rule="", at=None, hm=None) -> int:
    if defer_sell_at_limit(open_px, limits) or defer_sell_at_limit(px, limits):
        st.stats["defer_sell_limit_down"] += 1
        return 0
    reason, wanted, planned = plan[0], plan[1], plan[2] if len(plan) > 2 else None
    lots = sell_lots(st, code, day_i, ds)
    if reason == rules.HOLD20 and planned is None:
        planned = rules.hold20_orders(lots, px)
    orders = (rules.clamp_exit(lots, planned, keep_anchor=reason == rules.REDUCE) if planned is not None
              else rules.allocate_exit(lots, wanted, keep_anchor=reason == rules.REDUCE))
    filled = 0
    for lot_id, shares in orders:
        pos = next(p for p in st.positions[code] if p.lot_id == lot_id)
        filled += _sell(st, code, pos, px, day, reason, wanted_shares=shares,
                        day_i=day_i, bucket_id=bucket_id, price_rule=price_rule,
                        at=at, hm=hm)
    if reason == rules.STOP:
        memory_for(st, code).stopped.sold(filled)
    elif reason == rules.REDUCE:
        memory_for(st, code).reduced.sold(filled)
    return filled


def _prepare_day(st, codes, ds, exdiv):
    for code in codes:
        apply_exdiv_economics(st, code, ds)
        factor = k_for(exdiv, code, ds)
        if factor is not None:
            for pos in st.positions.get(code, []):
                rescale_position(pos, factor)
                st.stats["exdiv_adjusted_lots"] = st.stats.get("exdiv_adjusted_lots", 0) + 1


def _limits(st, code, closes, ds, names, exdiv, reference_price_for=None):
    if reference_price_for is None:
        prev, mapped = mapped_prev_close(exdiv, code, ds, closes[-1])
    else:
        prev, mapped = reference_price_for(code, ds), False
    if mapped:
        st.stats["exdiv_prev_close_mapped"] = st.stats.get("exdiv_prev_close_mapped", 0) + 1
    limits = book_limit_prices(code, prev, names, as_of=ds)
    if limits is None:
        st.stats["skip_unknown_board"] += 1
    return limits


def _normal_buys(st, pending_chase, *, hooks, day_i, day, ds, names, pool_days,
                 daily_quota, chase_quote, pool_quote, exdiv, volume_bucket_for=None,
                 ration=None, reference_price_for=None):
    run_chase_due_day(st, pending_chase, day_i=day_i, day=day, ds=ds,
                      names=names, allow_add=True, buy_gate=None,
                      quotes_for=chase_quote, exdiv=exdiv,
                      allow_new_name=hooks.get("allow_new_name"),
                      index_blocks_add=bool(hooks.get("index_blocks_add", False)),
                      volume_bucket_for=volume_bucket_for,
                      reference_price_for=reference_price_for)
    run_pool_buys_day(st, pending_chase, day_i=day_i, day=day, ds=ds,
                      pool_days=pool_days, daily_quota=daily_quota,
                      names=names, allow_add=True, buy_gate=None,
                      buy_quote_for=pool_quote, sizing="per_name",
                      name_budget=hooks["name_budget"], exdiv=exdiv,
                      ration=hooks["ration"] if ration is None else ration,
                      ration_seed=hooks["ration_seed"],
                      allow_new_name=hooks.get("allow_new_name"),
                      index_blocks_add=bool(hooks.get("index_blocks_add", False)),
                      volume_bucket_for=volume_bucket_for,
                      reference_price_for=reference_price_for)
    run_step_adds_day(st, day_i=day_i, day=day, ds=ds, names=names,
                      buy_quote_for=pool_quote, sizing="per_name",
                      name_budget=hooks["name_budget"], exdiv=exdiv,
                      step_add=lambda lots, px: rules.step_add_due(
                          lots, px, memory=memory_for(st, lots[0].code)),
                      volume_bucket_for=volume_bucket_for,
                      reference_price_for=reference_price_for)


def _buybacks(st, *, hooks, day_i, day, ds, names, quote, exdiv, volume_bucket_for=None,
              reference_price_for=None):
    run_buybacks_day(st, day_i=day_i, day=day, ds=ds, names=names,
                     codes=memories(st), buy_quote_for=quote,
                     buyback_plan=hooks["buyback_plan"], on_reclaim=hooks["on_reclaim"],
                     exdiv=exdiv, volume_bucket_for=volume_bucket_for,
                      reference_price_for=reference_price_for)


def run_daily_day(st, pending_chase, *, hooks, bars, pool_days, day_i, day,
                  ds, names, daily_quota, exdiv):
    """Close signal -> independent partial-exit queue -> next available open."""
    codes = list(dict.fromkeys([*st.positions, *memories(st)]))
    _prepare_day(st, codes, ds, exdiv)
    pending = st.book_state.setdefault("partial_exits", {})
    for code in codes:
        frame = bars.get(code)
        got = day_bar_and_prev_closes(frame, day) if frame is not None else None
        if got is None:
            continue
        row, closes = got
        limits = _limits(st, code, closes, ds, names, exdiv)
        if limits is None:
            continue
        if code in pending:
            if fill_exit(st, code, float(row["open"]), day, day_i=day_i, ds=ds,
                         plan=pending[code], limits=limits, open_px=float(row["open"]),
                         price_rule="daily_pending_next_open"):
                pending.pop(code)
        # A stop supersedes a queued MA5 reduction; no per-lot pending_exit abuse.
        plan = hooks["exit_plan"](st, code, float(row["close"]), day, closes,
                                  day_i=day_i, ds=ds)
        if plan is not None and (code not in pending or plan[0] == rules.STOP):
            pending[code] = queue_exit(
                st, code, plan, day_i=day_i, ds=ds, px=float(row["close"]),
            )

    def quote(code):
        frame = bars.get(code)
        got = day_bar_and_prev_closes(frame, day) if frame is not None else None
        return (float(got[0]["close"]), got[1]) if got is not None else None

    def chase_quote(code):
        frame = bars.get(code)
        got = day_bar_and_prev_closes(frame, day) if frame is not None else None
        return (float(got[0]["open"]), float(got[0]["close"]), got[1]) if got is not None else None

    _normal_buys(st, pending_chase, hooks=hooks, day_i=day_i, day=day, ds=ds,
                 names=names, pool_days=pool_days, daily_quota=daily_quota,
                 chase_quote=chase_quote, pool_quote=quote, exdiv=exdiv)
    _buybacks(st, hooks=hooks, day_i=day_i, day=day, ds=ds, names=names, quote=quote, exdiv=exdiv)


class MinuteSession:
    """Book callbacks driven exclusively by the shared (hm, phase) loop.

    A fresh row cursor preserves the historical per-bar retry and live whole-code
    allocation. Only queued FillConfig decisions survive to the next row/day.
    """

    def __init__(self, st, pending_chase, *, hooks, minute_bars, daily_bars,
                 pool_days, day_i, day, ds, names, daily_quota, exdiv, slice_day,
                 price_context=None, fill_config=None, held_fill_states=None):
        if price_context is not None and exdiv is not None:
            raise ValueError("X-01 price context requires exdiv=None (reference conversion occurs once)")
        reference_price_for = None if price_context is None else price_context.reference_price_for
        opening_codes = list(dict.fromkeys([*st.positions, *memories(st)]))
        _prepare_day(st, opening_codes, ds, exdiv)
        planned = apply_capital_ration(list(pool_days.get(ds, [])), ration=hooks["ration"],
                                     ration_seed=hooks["ration_seed"], ds=ds)
        codes = list(dict.fromkeys([*opening_codes, *pending_chase, *planned]))
        frames, closes_by_code, limits_by_code, chase_at, pool_at = {}, {}, {}, {}, {}
        for code in codes:
            daily = daily_bars.get(code)
            minute = minute_bars.get(code)
            if daily is None or minute is None or day not in daily.index:
                continue
            prev = (
                daily.loc[daily.index < day, "close"].astype(float).tolist()
                if price_context is None
                else price_context.previous_signal_closes_in_raw_domain(code, day)
            )
            frame = slice_day(code, ds)
            if not prev or frame is None:
                continue
            frames[code] = {int(row.hm): row for row in frame.itertuples()}
            closes_by_code[code] = prev
            limits_by_code[code] = _limits(st, code, prev, ds, names, exdiv, reference_price_for)
            times = list(frames[code])
            early = [hm for hm in times if 570 <= hm <= 585]
            late = [hm for hm in times if 870 <= hm <= 895]
            if early:
                chase_at[code] = max(early)
            if late:
                pool_at[code] = max(late)
        self.context = dict(st=st, pending_chase=pending_chase, hooks=hooks,
                            day_i=day_i, day=day, ds=ds, names=names,
                            daily_quota=daily_quota, exdiv=exdiv,
                            reference_price_for=reference_price_for)
        self.frames, self.closes, self.limits = frames, closes_by_code, limits_by_code
        self.chase_at, self.pool_at, self.planned = chase_at, pool_at, planned
        self.clocks = {hm for frame in frames.values() for hm in frame}
        self.fill_config = fill_config
        self.fill_states = held_fill_states if held_fill_states is not None else {}
        self.cursors = {}

    def advance_held(self, code, hm, phase):
        from backtest.research.minute_held_scan_core import HeldMinuteCursor

        ctx = self.context
        st, day_i, ds = ctx["st"], ctx["day_i"], ctx["ds"]
        row = self.frames.get(code, {}).get(hm)
        limits = self.limits.get(code)
        if row is None or limits is None:
            return
        state = self.fill_states.setdefault(("strategy12", code), {})
        if phase == "open":
            eligible = [pos for pos in st.positions.get(code, []) if pos.entry_idx < day_i]
            if not eligible:
                return
            anchor = eligible[0]

            def plan(c, px, day, closes):
                result = ctx["hooks"]["exit_plan"](st, c, px, day, closes,
                                                  day_i=day_i, ds=ds)
                if result is not None:
                    state["plan"] = (queue_exit(st, c, result, day_i=day_i, ds=ds, px=px)
                                     if self.fill_config is not None
                                     and self.fill_config.fill_timing == "next_bar_open"
                                     else result)
                return result

            cursor = HeldMinuteCursor(
                np.array([row.open]), np.array([row.high]), np.array([row.close]),
                cost=anchor.cost, peak=anchor.peak, n_days=day_i-anchor.entry_idx,
                can_sell=True, stop_pct=None, profit_base=0., trail_ratio=0.,
                hm=np.array([hm]), peak_gap_min=0, limit_down=limits[1],
                gate_code=code, gate_day=ctx["day"],
                daily_closes_ending_yesterday=self.closes[code],
                exit_plan=plan, exit_state={}, fill_config=self.fill_config,
                fill_state=state,
                l=np.array([row.low]) if hasattr(row, "low") else None,
            )
            self.cursors[code] = cursor
        else:
            cursor = self.cursors.pop(code, None)
            if cursor is None:
                return
        event = cursor.advance(0, phase)
        if event is None:
            return
        _, px, reason = event
        plan = state.pop("plan")
        # Memory channels use the book reason, never the execution suffix.
        opening = reason.endswith(":next_open")
        fill_exit(st, code, px, ctx["day"], day_i=day_i, ds=ds,
                  plan=plan, limits=limits, open_px=float(row.open), bucket_id=hm,
                  price_rule="minute_pending_next_open" if opening else "",
                  hm=hm if opening else None, at=hm-1 if opening else None)

    def after_close(self, hm):
        ctx = self.context
        st = ctx["st"]

        def quote(code):
            row = self.frames.get(code, {}).get(hm)
            return (float(row.close), self.closes[code]) if row is not None else None

        def pool_quote(code):
            return quote(code) if self.pool_at.get(code) == hm else None

        def chase_quote(code):
            if self.chase_at.get(code) != hm:
                return None
            first = next(iter(self.frames[code].values()))
            px, closes = quote(code)
            return float(first.open), px, closes

        bucket = (lambda _code: hm) if st.volume_cap is not None else None
        _normal_buys(**ctx,
                     pool_days={ctx["ds"]: [c for c in self.planned if self.pool_at.get(c) == hm]},
                     chase_quote=chase_quote, pool_quote=pool_quote,
                     volume_bucket_for=bucket, ration="file_order")
        _buybacks(**{k: v for k, v in ctx.items() if k not in ("pending_chase", "daily_quota")},
                  quote=quote, volume_bucket_for=bucket)
