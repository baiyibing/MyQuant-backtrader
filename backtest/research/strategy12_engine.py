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
        result.append(rules.SellLot(pos.lot_id, pos.shares, available, pos.is_step))
    return result


def plan_exit(st, code, px, day, closes, *, day_i, ds):
    return rules.exit_plan(code, px, day, closes, sell_lots(st, code, day_i, ds),
                           memory=memory_for(st, code))


def plan_buybacks(st, code, px, day, closes):
    del day
    mem = memory_for(st, code)
    plans = []
    for channel in ("reduced", "stopped"):
        item = getattr(mem, channel)
        if not item.shares and not item.latched:
            continue
        reason = rules.reclaim_signal(px, closes, channel=channel)
        if reason:
            plans.append((reason, rules.buyback_plan(px, closes, item, channel=channel)))
    return plans


def on_reclaim(st, code, reason, shares):
    channel = "reduced" if reason == rules.RECLAIM5 else "stopped"
    getattr(memory_for(st, code), channel).reclaimed(shares)


def queue_exit(st, code, plan, *, day_i, ds):
    """Pin a deferred daily exit to the lots sellable when the close signalled.

    Without this the next open re-allocates onto pool/chase/step lots bought
    after the signal, leaving the measured lot held and the cycle latched.
    """
    reason, wanted = plan
    return reason, wanted, rules.allocate_exit(sell_lots(st, code, day_i, ds), wanted,
                                               keep_anchor=reason == rules.REDUCE)


def fill_exit(st, code, px, day, *, day_i, ds, plan, limits, open_px,
              bucket_id=None, price_rule="") -> int:
    if defer_sell_at_limit(open_px, limits) or defer_sell_at_limit(px, limits):
        st.stats["defer_sell_limit_down"] += 1
        return 0
    reason, wanted, planned = plan[0], plan[1], plan[2] if len(plan) > 2 else None
    lots = sell_lots(st, code, day_i, ds)
    orders = (rules.clamp_exit(lots, planned) if planned is not None
              else rules.allocate_exit(lots, wanted, keep_anchor=reason == rules.REDUCE))
    filled = 0
    for lot_id, shares in orders:
        pos = next(p for p in st.positions[code] if p.lot_id == lot_id)
        filled += _sell(st, code, pos, px, day, reason, wanted_shares=shares,
                        day_i=day_i, bucket_id=bucket_id, price_rule=price_rule)
    channel = "reduced" if reason == rules.REDUCE else "stopped"
    getattr(memory_for(st, code), channel).sold(filled)
    return filled


def _prepare_day(st, codes, ds, exdiv):
    for code in codes:
        apply_exdiv_economics(st, code, ds)
        factor = k_for(exdiv, code, ds)
        if factor is not None:
            for pos in st.positions.get(code, []):
                rescale_position(pos, factor)
                st.stats["exdiv_adjusted_lots"] = st.stats.get("exdiv_adjusted_lots", 0) + 1


def _limits(st, code, closes, ds, names, exdiv):
    prev, mapped = mapped_prev_close(exdiv, code, ds, closes[-1])
    if mapped:
        st.stats["exdiv_prev_close_mapped"] = st.stats.get("exdiv_prev_close_mapped", 0) + 1
    limits = book_limit_prices(code, prev, names)
    if limits is None:
        st.stats["skip_unknown_board"] += 1
    return limits


def _normal_buys(st, pending_chase, *, hooks, day_i, day, ds, names, pool_days,
                 daily_quota, chase_quote, pool_quote, exdiv, volume_bucket_for=None,
                 ration=None):
    run_chase_due_day(st, pending_chase, day_i=day_i, day=day, ds=ds,
                      names=names, allow_add=True, buy_gate=None,
                      quotes_for=chase_quote, exdiv=exdiv,
                      volume_bucket_for=volume_bucket_for)
    run_pool_buys_day(st, pending_chase, day_i=day_i, day=day, ds=ds,
                      pool_days=pool_days, daily_quota=daily_quota,
                      names=names, allow_add=True, buy_gate=None,
                      buy_quote_for=pool_quote, sizing="per_name",
                      name_budget=hooks["name_budget"], exdiv=exdiv,
                      ration=hooks["ration"] if ration is None else ration,
                      ration_seed=hooks["ration_seed"],
                      volume_bucket_for=volume_bucket_for)
    run_step_adds_day(st, day_i=day_i, day=day, ds=ds, names=names,
                      buy_quote_for=pool_quote, sizing="per_name",
                      name_budget=hooks["name_budget"], exdiv=exdiv,
                      step_add=lambda lots, px: rules.step_add_due(
                          lots, px, memory=memory_for(st, lots[0].code)),
                      volume_bucket_for=volume_bucket_for)


def _buybacks(st, *, hooks, day_i, day, ds, names, quote, exdiv, volume_bucket_for=None):
    run_buybacks_day(st, day_i=day_i, day=day, ds=ds, names=names,
                     codes=memories(st), buy_quote_for=quote,
                     buyback_plan=hooks["buyback_plan"], on_reclaim=hooks["on_reclaim"],
                     exdiv=exdiv, volume_bucket_for=volume_bucket_for)


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
            pending[code] = queue_exit(st, code, plan, day_i=day_i, ds=ds)

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


def run_minute_day(st, pending_chase, *, hooks, minute_bars, daily_bars, pool_days,
                   day_i, day, ds, names, daily_quota, exdiv, slice_day, scan):
    """Advance bars chronologically so reclaim re-arms within the same day.

    The scanner's existing 5-tuple is retained; shares use its exit_state
    out-param. Pool/chase/steps keep their existing exact/fallback quote clocks.
    """
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
        prev = daily.loc[daily.index < day, "close"].astype(float).tolist()
        frame = slice_day(code, ds)
        if not prev or frame is None:
            continue
        frames[code] = {int(row.hm): row for row in frame.itertuples()}
        closes_by_code[code] = prev
        limits_by_code[code] = _limits(st, code, prev, ds, names, exdiv)
        times = list(frames[code])
        early = [hm for hm in times if 570 <= hm <= 585]
        late = [hm for hm in times if 870 <= hm <= 895]
        if early:
            chase_at[code] = max(early)
        if late:
            pool_at[code] = max(late)
    times = sorted({hm for frame in frames.values() for hm in frame})
    for hm in times:
        for code in list(st.positions):
            row = frames.get(code, {}).get(hm)
            limits = limits_by_code.get(code)
            if row is None or limits is None:
                continue
            eligible = [pos for pos in st.positions[code] if pos.entry_idx < day_i]
            if not eligible:
                continue
            anchor = eligible[0]
            state = {}
            idx, px, reason, _, _ = scan(
                np.array([row.open]), np.array([row.high]), np.array([row.close]),
                cost=anchor.cost, peak=anchor.peak, n_days=day_i - anchor.entry_idx,
                can_sell=True, stop_pct=None, profit_base=0., trail_ratio=0.,
                hm=np.array([hm]), peak_gap_min=0, limit_down=limits[1],
                gate_code=code, gate_day=day,
                daily_closes_ending_yesterday=closes_by_code[code],
                exit_plan=lambda c, px, d, closes: hooks["exit_plan"](
                    st, c, px, d, closes, day_i=day_i, ds=ds), exit_state=state,
            )
            if idx >= 0:
                fill_exit(st, code, px, day, day_i=day_i, ds=ds,
                          plan=(reason, state["shares"]), limits=limits,
                          open_px=float(row.open), bucket_id=hm)

        def quote(code):
            row = frames.get(code, {}).get(hm)
            return (float(row.close), closes_by_code[code]) if row is not None else None

        def pool_quote(code):
            return quote(code) if pool_at.get(code) == hm else None

        def chase_quote(code):
            if chase_at.get(code) != hm:
                return None
            first = next(iter(frames[code].values()))
            px, closes = quote(code)
            return float(first.open), px, closes

        bucket = (lambda _code: hm) if st.volume_cap is not None else None
        _normal_buys(st, pending_chase, hooks=hooks, day_i=day_i, day=day, ds=ds,
                     names=names, pool_days={ds: [c for c in planned if pool_at.get(c) == hm]},
                     daily_quota=daily_quota, chase_quote=chase_quote,
                     pool_quote=pool_quote, exdiv=exdiv, volume_bucket_for=bucket,
                     ration="file_order")
        _buybacks(st, hooks=hooks, day_i=day_i, day=day, ds=ds, names=names,
                   quote=quote, exdiv=exdiv, volume_bucket_for=bucket)
