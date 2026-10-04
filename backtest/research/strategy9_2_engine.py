"""Book-local turtle orchestration using the shared A-share fill ledger."""
from types import SimpleNamespace

from backtest.research import strategy9_2_rules as rules
from backtest.research import strategy12_engine as shared
from backtest.research.csv_common import day_bar_and_prev_closes
from backtest.research.exdiv_map import k_for
from backtest.research.csv_ledger import execute_buy, _sell
from backtest.research.csv_simulate_loop import run_pool_buys_day
from backtest.research.ashare_session import defer_sell_at_limit
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
    if px <= rules.stop_line(cost, mem.units, mem.last_add_price):
        reason = "stop_loss:turtle_tier"
    elif rules.time_stop(px, mem.entry, mem.units, day_i - mem.anchor_idx):
        reason = "force_sell:hold_days_5"
    elif rules.giveback(px, cost, mem.peak, mem.units):
        reason = "trail:profit_drawdown"
    if reason:
        return reason, shares
    seq, fraction = rules.scale_out(px, cost, mem.sell_band_seq)
    if fraction:
        mem.sell_band_seq = seq
        wanted = int(round(shares * fraction, 8)) // 100 * 100
        if wanted:
            return f"profit_take:band:{seq}", wanted
    return None


def fill_pending(st, code, row, day, *, day_i, ds, limits, bucket=None):
    pending = st.book_state.setdefault("turtle_pending", {})
    plan = pending.get(code)
    if plan is None:
        return
    reason, wanted = plan
    retry = st.book_state.setdefault("turtle_retry_day", {})
    if day_i < retry.get(code, day_i):
        return
    px = float(row.open)
    if defer_sell_at_limit(px, limits):
        retry[code] = day_i + 1
        st.stats["defer_sell_limit_down"] += 1
        st.stats["limit_down_pending"] = st.stats.get("limit_down_pending", 0) + 1
        return
    filled = 0
    for lot in shared.sell_lots(st, code, day_i, ds):
        amount = min(lot.sellable, wanted - filled)
        if amount <= 0:
            continue
        pos = next(p for p in st.positions[code] if p.lot_id == lot.lot_id)
        filled += _sell(st, code, pos, px, day, reason, wanted_shares=amount,
                        day_i=day_i, bucket_id=bucket)
    if filled >= wanted or not st.positions.get(code):
        pending.pop(code, None)
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
        memory_for(st, code).peak = max(memory_for(st, code).peak, float(row.high))
        plan = plan_exit(st, code, float(row.close), day, closes, day_i=day_i, ds=ds)
        if plan:
            pending[code] = plan


def run_minute_day(st, pending_chase, *, hooks, minute_bars, daily_bars, pool_days,
                   day_i, day, ds, names, daily_quota, exdiv, slice_day, scan):
    codes = list(dict.fromkeys([*st.positions, *pool_days.get(ds, [])]))
    prepare_day(st, codes, ds, exdiv)
    frames, closes, limits, pool_at = {}, {}, {}, {}
    for code in codes:
        if code not in daily_bars or code not in minute_bars:
            continue
        prev = daily_bars[code].loc[daily_bars[code].index < day, "close"].astype(float).tolist()
        frame = slice_day(code, ds)
        if not prev or frame is None or frame.empty:
            continue
        frames[code] = {int(row.hm): row for row in frame.itertuples()}
        closes[code] = prev
        limits[code] = shared._limits(st, code, prev, ds, names, exdiv)
        late = [hm for hm in frames[code] if 870 <= hm <= 895]
        if late:
            pool_at[code] = max(late)
    pending = st.book_state.setdefault("turtle_pending", {})
    for hm in sorted({hm for frame in frames.values() for hm in frame}):
        def quote(code):
            row = frames.get(code, {}).get(hm)
            return (float(row.close), closes[code]) if row is not None else None

        def add_quote(code):
            row = frames.get(code, {}).get(hm)
            return (float(row.high), closes[code], float(row.open)) if row is not None else None

        adds(st, hooks=hooks, day_i=day_i, day=day, ds=ds, names=names,
             quote=add_quote, exdiv=exdiv, bucket=hm)
        for code in list(st.positions):
            row = frames.get(code, {}).get(hm)
            if row is None or limits.get(code) is None:
                continue
            fill_pending(st, code, row, day, day_i=day_i, ds=ds, limits=limits[code], bucket=hm)
            if not st.positions.get(code):
                continue
            mem = memory_for(st, code)
            mem.peak = max(mem.peak, float(row.high))
            if code not in pending:
                plan = plan_exit(st, code, float(row.close), day, closes[code], day_i=day_i, ds=ds)
                if plan:
                    pending[code] = plan
                    # Close-triggered exit fills at the observed close, never a prior open.
                    fill_pending(st, code, SimpleNamespace(open=row.close), day,
                                 day_i=day_i, ds=ds, limits=limits[code], bucket=hm)

        buys(st, pending_chase, hooks=hooks, day_i=day_i, day=day, ds=ds, names=names,
             pool_days={ds: [c for c in pool_days.get(ds, []) if pool_at.get(c) == hm]},
             daily_quota=daily_quota, quote=quote, exdiv=exdiv, bucket=hm)
