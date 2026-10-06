"""Book-local turtle orchestration using the shared A-share fill ledger."""

from backtest.research.lot_rounding import rounded_partial_board_lots
from backtest.research.sell_pending_observability import pending_callback, record_limit
from types import SimpleNamespace

from backtest.research import strategy9_2_rules as rules
from backtest.research import strategy12_engine as shared
from backtest.research.csv_common import day_bar_and_prev_closes
from backtest.research.exdiv_map import k_for
from backtest.research.csv_ledger import (
    execute_buy,
    fee_order_id,
    release_fee_order,
    _sell,
)
from backtest.research.csv_simulate_loop import run_pool_buys_day
from backtest.research.ashare_session import defer_sell_open_or_fill
from backtest.research.ashare_session import hit_limit_up


def memory_for(st, code):
    return st.book_state.setdefault("strategy9_2", {}).setdefault(code, rules.Memory())


def on_buy(st, code, reason, shares):
    if shares <= 0:
        return
    lots = st.positions[code]
    if len(lots) == 1:
        st.book_state.setdefault("strategy9_2", {})[code] = rules.Memory()
    mem = memory_for(st, code)
    px = st.trades[-1]["price"]
    if mem.units == 0:
        mem.entry = px
        mem.peak = px
    total = sum(p.shares for p in lots)
    mem.cost = (mem.cost * (total - shares) + px * shares) / total
    mem.units += 1
    mem.last_add_price = px
    mem.anchor_idx = lots[-1].entry_idx


def plan_exit(st, code, px, day, closes, *, day_i, ds):
    lots = st.positions.get(code, [])
    if not lots:
        return None
    mem = memory_for(st, code)
    shares = sum(p.shares for p in lots)
    cost = mem.cost
    mem.peak = max(mem.peak, px)
    reason = None
    if rules.time_stop(px, mem.entry, mem.units, day_i - mem.anchor_idx):
        reason = "force_sell:hold_days_20"
    elif rules.giveback(px, cost, mem.peak, mem.units):
        reason = "trail:profit_drawdown"
    if reason:
        return reason, shares
    seq, fraction = rules.scale_out(px, cost, mem.sell_band_seq)
    if fraction:
        mem.sell_band_seq = seq
        wanted = rounded_partial_board_lots(shares, fraction)
        if wanted:
            return f"profit_take:band:{seq}", wanted
    return None


def fill_stop(st, code, row, frame, day, *, day_i, ds, limits, minute=False, bucket=None):
    """Dispatch one chosen stop through the existing limit/T+1 residual path."""
    if code in st.book_state.setdefault("turtle_pending", {}):
        return False
    if not any(lot.sellable > 0 for lot in shared.sell_lots(st, code, day_i, ds)):
        return False
    trigger = rules.chosen_stop(memory_for(st, code).cost, frame, day)
    if trigger is None:
        return False
    if float(row.open) <= trigger:
        px, reason = float(row.open), "stop_loss:gap_open"
    elif float(row.close if minute else row.low) <= trigger:
        px = float(row.close) if minute else trigger
        reason = "stop_loss:touch"
    else:
        return False
    st.book_state["turtle_pending"][code] = reason, sum(p.shares for p in st.positions[code])
    fill_pending(st, code, SimpleNamespace(open=px), day, day_i=day_i, ds=ds,
                 limits=limits, bucket=bucket, limit_open=float(row.open))
    return True


def fill_pending(st, code, row, day, *, day_i, ds, limits, bucket=None, at=None, limit_open=None):
    pending = st.book_state.setdefault("turtle_pending", {})
    plan = pending.get(code)
    if plan is None:
        return
    reason, wanted = plan
    retry = st.book_state.setdefault("turtle_retry_day", {})
    if day_i < retry.get(code, day_i):
        return
    px = float(row.open)
    if defer_sell_open_or_fill(px if limit_open is None else limit_open, px, limits):
        retry[code] = day_i + 1
        st.stats["defer_sell_limit_down"] += 1
        st.stats["limit_down_pending"] = st.stats.get("limit_down_pending", 0) + 1
        record_limit(st, code, wanted, ds, bucket, px if limit_open is None else limit_open, limits,
                     path="v9_2_turtle", key=("turtle", code))
        return
    order_key = ("strategy9_2-exit", code, reason)
    order_id = fee_order_id(st, order_key)
    filled = 0
    for lot in shared.sell_lots(st, code, day_i, ds):
        amount = min(lot.sellable, wanted - filled)
        if amount <= 0:
            continue
        pos = next(p for p in st.positions[code] if p.lot_id == lot.lot_id)
        filled += _sell(st, code, pos, px, day, reason, wanted_shares=amount,
                        day_i=day_i, bucket_id=bucket,
                        order_id=order_id,
                        **({"at": at, "hm": bucket, "price_rule": "minute_pending_next_open"}
                           if at is not None else {}))
    if filled >= wanted or not st.positions.get(code):
        pending.pop(code, None)
        st._sell_pending_history.pop(("turtle", code), None)
        release_fee_order(st, order_key)
    else:
        pending[code] = reason, wanted - filled


def buys(st, pending_chase, *, hooks, day_i, day, ds, names, pool_days,
         daily_quota, quote, exdiv, bucket=None, reference_price_for=None):
    pending = st.book_state.setdefault("turtle_pending", {})
    run_pool_buys_day(st, pending_chase, day_i=day_i, day=day, ds=ds,
                      names=names, pool_days={ds: [c for c in pool_days.get(ds, []) if c not in pending]},
                      daily_quota=daily_quota, allow_add=False, buy_gate=None,
                      buy_quote_for=quote, sizing="per_name", name_budget=hooks["name_budget"],
                      name_lot_budget=lambda budget, lots: rules.lot_budget(budget, 0),
                      exdiv=exdiv, limit_up_chase=False,
                      ration=hooks["ration"], ration_seed=hooks["ration_seed"],
                      volume_bucket_for=(lambda c: bucket) if bucket is not None else None,
                      reference_price_for=reference_price_for)


def adds(st, *, hooks, day_i, day, ds, names, quote, exdiv, bucket=None,
         reference_price_for=None):
    for code in list(st.positions):
        if code in st.book_state.setdefault("turtle_pending", {}):
            continue
        got = quote(code)
        if got is None:
            continue
        high, closes, open_px = got
        limits = shared._limits(st, code, closes, ds, names, exdiv, reference_price_for)
        if limits is None:
            continue
        mem = memory_for(st, code)
        # Successful fills alone advance units; failures terminate the bounded scan.
        while rules.add_due(mem.entry, mem.units, high):
            px = max(open_px, rules.next_add_line(mem.entry, mem.units))
            if hit_limit_up(px, limits[0]):
                st.stats["skip_limit_up"] += 1
                break
            quota = st.daily_quota_used
            ok = execute_buy(st, code, px, rules.lot_budget(hooks["name_budget"], mem.units),
                             day_i, day, reason="add:turtle_line", is_step=True,
                             **({"bucket_id": bucket} if bucket is not None else {}))
            st.daily_quota_used = quota
            if not ok:
                break


def prepare_day(st, codes, ds, exdiv):
    # Keep the cycle's price anchors in the same domain as the shared lot rescaling.
    shared._prepare_day(st, codes, ds, exdiv)
    for code in codes:
        factor = k_for(exdiv, code, ds)
        if factor is not None and st.positions.get(code):
            mem = memory_for(st, code)
            for field in ("entry", "last_add_price", "peak", "cost"):
                setattr(mem, field, getattr(mem, field) * factor)


def run_daily_day(st, pending_chase, *, hooks, bars, pool_days, day_i, day,
                  ds, names, daily_quota, exdiv):
    from backtest.research.csv_ledger import reject_short_cash_override
    reject_short_cash_override(hooks, "strategy9_2_engine")
    prepare_day(st, list(st.positions), ds, exdiv)
    pending = st.book_state.setdefault("turtle_pending", {})
    for code in list(st.positions):
        got = day_bar_and_prev_closes(bars[code], day)
        if got is None:
            continue
        row, closes = got
        limits = shared._limits(st, code, closes, ds, names, exdiv)
        if limits is not None:
            fill_pending(st, code, row, day, day_i=day_i, ds=ds, limits=limits)

    def quote(code):
        got = day_bar_and_prev_closes(bars[code], day) if code in bars else None
        return (float(got[0].open), got[1]) if got else None

    def add_quote(code):
        got = day_bar_and_prev_closes(bars[code], day) if code in bars else None
        return (float(got[0].high), got[1], float(got[0].open)) if got else None

    buys(st, pending_chase, hooks=hooks, day_i=day_i, day=day, ds=ds, names=names,
         pool_days=pool_days, daily_quota=daily_quota, quote=quote, exdiv=exdiv)
    adds(st, hooks=hooks, day_i=day_i, day=day, ds=ds, names=names, quote=add_quote, exdiv=exdiv)
    for code in list(st.positions):
        got = day_bar_and_prev_closes(bars[code], day)
        if got is None or code in pending:
            continue
        row, closes = got
        limits = shared._limits(st, code, closes, ds, names, exdiv)
        if limits is not None and fill_stop(st, code, row, bars[code], day,
                                           day_i=day_i, ds=ds, limits=limits):
            continue
        memory_for(st, code).peak = max(memory_for(st, code).peak, float(row.high))
        plan = plan_exit(st, code, float(row.close), day, closes, day_i=day_i, ds=ds)
        if plan:
            pending[code] = plan


class MinuteSession:
    """Turtle hooks hosted by the shared clock, with cursor-owned exit prices.

    The legacy OHLC convention observes adds first, then each code's open and
    close exits in holding order. Keep that account order in the close phase;
    a gap quote still uses the cursor's open phase. This is not tick ordering.
    """

    def __init__(self, st, pending_chase, *, hooks, minute_bars, daily_bars,
                 pool_days, day_i, day, ds, names, daily_quota, exdiv, slice_day,
                 price_context=None, fill_config=None, held_fill_states=None):
        from backtest.research.csv_ledger import reject_short_cash_override
        reject_short_cash_override(hooks, "strategy9_2_engine")
        codes = list(dict.fromkeys([*st.positions, *pool_days.get(ds, [])]))
        prepare_day(st, codes, ds, exdiv)
        self.frames, self.closes, self.limits, self.pool_at = {}, {}, {}, {}
        for code in codes:
            if code not in daily_bars or code not in minute_bars:
                continue
            prev = daily_bars[code].loc[daily_bars[code].index < day, "close"].astype(float).tolist()
            frame = slice_day(code, ds)
            if not prev or frame is None or frame.empty:
                continue
            self.frames[code] = {int(row.hm): row for row in frame.itertuples()}
            self.closes[code] = prev
            self.limits[code] = shared._limits(st, code, prev, ds, names, exdiv)
            late = [hm for hm in self.frames[code] if 870 <= hm <= 895]
            if late:
                self.pool_at[code] = max(late)
        self.clocks = {hm for frame in self.frames.values() for hm in frame}
        self.context = dict(st=st, pending_chase=pending_chase, hooks=hooks,
                            day_i=day_i, day=day, ds=ds, names=names,
                            daily_quota=daily_quota, exdiv=exdiv)
        self.pool_codes = list(pool_days.get(ds, []))
        self.daily_bars = daily_bars
        self.fill_config = fill_config
        self.fill_states = held_fill_states if held_fill_states is not None else {}

    def before_close(self, hm):
        def quote(code):
            row = self.frames.get(code, {}).get(hm)
            return (float(row.high), self.closes[code], float(row.open)) if row is not None else None
        adds(**{k: v for k, v in self.context.items() if k not in ("pending_chase", "daily_quota")},
             quote=quote, bucket=hm)

    def advance_held(self, code, hm, phase):
        import numpy as np
        from backtest.research.minute_held_scan_core import HeldMinuteCursor

        if phase != "close":
            return
        ctx = self.context
        st, day_i, ds = ctx["st"], ctx["day_i"], ctx["ds"]
        row = self.frames.get(code, {}).get(hm)
        limits = self.limits.get(code)
        if row is None or limits is None:
            return
        pending = st.book_state.setdefault("turtle_pending", {})
        state = self.fill_states.setdefault(("strategy9_2", code), {})

        def settle(event):
            if event is None:
                return
            _, px, _reason = event
            # Keep turtle reasons/memory and the historical ledger byte schema.
            fill_pending(st, code, SimpleNamespace(open=px), ctx["day"],
                         day_i=day_i, ds=ds, limits=limits, bucket=hm,
                         limit_open=(float(row.open) if stage == "stop" and _reason == "stop_loss:touch" else px),
                         **({"at": hm - 1} if _reason.endswith(":next_open") else {}))

        def decision(cursor, idx, at_phase):
            if stage == "pending":
                if at_phase != "open" or code not in pending:
                    return None
                if day_i < st.book_state.setdefault("turtle_retry_day", {}).get(code, day_i):
                    return None
                delayed = state.get("pending")
                # A decision queued on this row cannot execute on its own open.
                if delayed and state.get("queued_at") == (ds, hm):
                    return None
                state.pop("pending", None)
                state.pop("queued_at", None)
                return cursor._exit(idx, row.open, delayed or pending[code][0])
            if stage == "stop":
                if code in pending or not any(lot.sellable > 0 for lot in shared.sell_lots(st, code, day_i, ds)):
                    return None
                line = rules.chosen_stop(memory_for(st, code).cost, self.daily_bars[code], ctx["day"])
                if line is None:
                    return None
                gap = float(row.open) <= line
                if at_phase == "open" and gap:
                    px, reason = float(row.open), "stop_loss:gap_open"
                elif at_phase == "close" and not gap and float(row.low if cursor.fill_config.trigger_basis == "bar_low" else row.close) <= line:
                    px, reason = float(row.close), "stop_loss:touch"
                else:
                    return None
                pending[code] = reason, sum(p.shares for p in st.positions[code])
                return cursor._price_exit(idx, px, reason, line=line, gap=gap,
                                          intrabar=cursor.fill_config.trigger_basis == "bar_low")
            if at_phase != "close":
                return None
            mem = memory_for(st, code)
            mem.peak = max(mem.peak, float(row.high))
            if code in pending:
                return None
            plan = plan_exit(st, code, float(row.close), ctx["day"], self.closes[code], day_i=day_i, ds=ds)
            if plan is None:
                return None
            pending[code] = plan
            return cursor._price_exit(idx, row.close, plan[0])

        for stage in ("pending", "stop", "plan"):
            if not st.positions.get(code):
                break
            cursor = HeldMinuteCursor(
                np.array([row.open]), np.array([row.high]), np.array([row.close]),
                l=np.array([row.low]), hm=np.array([hm]),
                cost=memory_for(st, code).cost, peak=memory_for(st, code).peak,
                n_days=day_i - min(p.entry_idx for p in st.positions[code]),
                can_sell=any(lot.sellable > 0 for lot in shared.sell_lots(st, code, day_i, ds)),
                stop_pct=None, profit_base=0., trail_ratio=0.,
                phase_exit=decision, fill_config=self.fill_config, fill_state=state,
                pending_log=pending_callback(st, code, st.positions[code][0], ds,
                                             path="v9_2_turtle", key=("turtle", code),
                                             shares=lambda: pending[code][1]),
            )
            settle(cursor.advance(0, "open"))
            settle(cursor.advance(0, "close"))
            if state.get("pending"):
                state.setdefault("queued_at", (ds, hm))
            if stage == "stop" and cursor.first_exit_attempted:
                break
            if stage == "stop" and state.get("pending"):
                break

    def after_close(self, hm):
        def quote(code):
            row = self.frames.get(code, {}).get(hm)
            return (float(row.close), self.closes[code]) if row is not None else None
        ds = self.context["ds"]
        buys(**self.context,
             pool_days={ds: [c for c in self.pool_codes if self.pool_at.get(c) == hm]},
             quote=quote, bucket=hm)
