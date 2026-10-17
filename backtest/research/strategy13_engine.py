"""Beidou orchestration through shared ledger and HeldMinuteCursor; no fill kernel."""
import numpy as np
from types import SimpleNamespace
from backtest.research.lot_rounding import budget_board_lots

from backtest.research import strategy13_rules as rules
from backtest.research import strategy12_engine as shared
from backtest.research.ashare_session import hit_limit_up, defer_sell_open_or_fill
from backtest.research.csv_common import day_bar_and_prev_closes
from backtest.research.csv_ledger import execute_buy, _sell, fee_order_id, release_fee_order, preview_buy_cash_needed, is_parking_lot


def strategy_lots(st, code):
    return [p for p in st.positions.get(code, []) if not is_parking_lot(st, p)]


def memory(st, code):
    return st.book_state.setdefault("beidou", {}).setdefault(code, rules.Memory())


def on_buy(st, code, reason, shares):
    if reason.startswith("parking:"):
        return
    trade = st.trades[-1]
    if reason == "pool":
        st.book_state.setdefault("beidou", {})[code] = rules.Memory(
            entry=trade["price"], base_shares=shares, peak=trade["price"],
            entry_idx=st.positions[code][-1].entry_idx)
    mem = memory(st, code)
    mem.buy_fees[st.positions[code][-1].lot_id] = sum(float(trade.get(k, 0.0)) for k in ("commission", "stamp_duty", "transfer_fee"))
    if reason == "add:beidou":
        mem.adds += 1
        mem.last_add = trade["price"]


def plan_exit(st, code, px, day, closes, *, day_i, ds, params, daily_close=False):
    lots = strategy_lots(st, code)
    if not lots:
        return None
    mem = memory(st, code)
    held = sum(p.shares for p in lots)
    mem.peak = max(mem.peak, px)
    if daily_close and mem.last_ma_day != ds:
        ma20 = np.mean([*closes, px][-20:]) if len(closes) >= 19 else None
        mem.below_days = mem.below_days + 1 if ma20 is not None and px < ma20 else 0
        mem.last_ma_day = ds
    age = day_i - mem.entry_idx
    reason = None
    if px <= mem.peak * (1 - params.clear_drawdown) + 1e-10:
        reason = "trail:beidou_clear"
    elif daily_close and px < mem.entry * (1 - params.stop_pct):
        reason = "stop_loss:beidou_hard"
    elif daily_close and mem.below_days >= params.ma_sessions:
        reason = "stop_loss:beidou_ma20"
    elif daily_close and 0 < age <= params.early_sessions and px <= mem.entry * (1 - params.early_loss) + 1e-10:
        reason = "stop_loss:beidou_early"
    if reason:
        return reason, held
    if mem.tier < len(params.tp_levels) and px + 1e-10 >= mem.entry * (1 + params.tp_levels[mem.tier]):
        wanted = rules.tp_shares(held, mem.base_shares, params.tp_fractions[mem.tier], params.base_floor)
        if wanted:
            return f"profit_take:beidou:{mem.tier}", wanted
        mem.tier += 1  # no executable lot at this tier; floor remains intact
    return None


def fill_pending(st, code, row, day, *, day_i, ds, limits, bucket=None, at=None):
    pending = st.book_state.setdefault("beidou_pending", {})
    if code not in pending or limits is None:
        return
    reason, wanted = pending[code]
    px = float(row.open)
    if defer_sell_open_or_fill(px, px, limits):
        st.stats["defer_sell_limit_down"] += 1
        return
    key = ("beidou", code, reason)
    order_id = fee_order_id(st, key)
    filled = 0
    mem = memory(st, code)
    for lot in list(strategy_lots(st, code)):
        if lot.entry_idx >= day_i or filled >= wanted:
            continue
        before = lot.shares
        cost = lot.cost
        cash_before = st.cash
        got = _sell(st, code, lot, px, day, reason, wanted_shares=min(before, wanted-filled),
                    day_i=day_i, bucket_id=bucket, order_id=order_id,
                    **({"at": at, "hm": bucket, "price_rule": "minute_pending_next_open"} if at is not None else {}))
        if got:
            fee = mem.buy_fees.get(lot.lot_id, 0.0) * got / before
            mem.buy_fees[lot.lot_id] = mem.buy_fees.get(lot.lot_id, 0.0) - fee
            # Cash delta includes shared per-order fee reallocations, stamp and transfer.
            pnl = st.cash - cash_before - got * cost - fee
            st.stats["beidou_realized"] = st.stats.get("beidou_realized", 0.0) + pnl
        filled += got
    if filled >= wanted or not st.positions.get(code):
        pending.pop(code)
        if reason.startswith("profit_take:beidou"):
            mem.tier += 1
        release_fee_order(st, key)
    else:
        pending[code] = reason, wanted - filled


def buy(st, code, px, closes, *, hooks, day_i, day, ds, names, exdiv, bucket=None, adding=False):
    if code in st.book_state.setdefault("beidou_pending", {}):
        return False
    lots = strategy_lots(st, code)
    if bool(lots) != adding:
        return False
    limits = shared._limits(st, code, closes, ds, names, exdiv)
    if limits is None or hit_limit_up(px, limits[0]):
        return False
    params = hooks["beidou_params"]
    model = getattr(st, "slippage_model", None)
    fill_px = model.buy_price(px) if model is not None else px
    if not np.isfinite(fill_px) or fill_px <= 0:
        return False
    shares = (rules.add_order(memory(st, code), px, params) if adding
              else max(100, budget_board_lots(params.base_budget, fill_px)))
    if not shares:
        return False
    capital = st.stats["beidou_capital"]
    cap = min(capital * rules.NAME_CAP, hooks["name_budget"])
    held_value = sum(p.shares for p in lots) * fill_px
    allowed = shares * fill_px + held_value <= cap + 1e-9
    gate = hooks.get("beidou_index_gate")
    if gate is not None:
        fraction = gate.get(day.date() if hasattr(day, "date") else day)
        if fraction is None:
            raise ValueError(f"missing HS300 gate for {ds}")
        prices = st.book_state.setdefault("beidou_marks", {})
        prices[code] = px
        exposure = sum(sum(p.shares for p in group) * prices.get(c, group[0].cost)
                       for c, group in st.positions.items() if group)
        equity = st.cash + exposure
        allowed &= exposure + shares * fill_px <= equity * fraction + 1e-9
    needed = preview_buy_cash_needed(st, code, fill_px, shares, day)
    if not allowed or needed > st.cash + 1e-9:
        st.stats["skip_cash"] += 1
        return False
    quota = st.daily_quota_used
    ok = execute_buy(st, code, px, needed, day_i, day,
                     reason="add:beidou" if adding else "pool", is_step=adding,
                     shares_override=shares, **({"bucket_id": bucket} if bucket is not None else {}))
    st.daily_quota_used = quota
    return ok


def prepare(st, codes, ds, exdiv):
    shared._prepare_day(st, codes, ds, exdiv)
    from backtest.research.exdiv_map import k_for
    for code in codes:
        factor = k_for(exdiv, code, ds)
        if factor is not None and st.positions.get(code) and strategy_lots(st, code):
            mem = memory(st, code)
            mem.entry *= factor
            mem.peak *= factor
            mem.last_add *= factor


def run_daily_day(st, pending_chase, *, hooks, bars, pool_days, day_i, day, ds, names, daily_quota, exdiv):
    prepare(st, list(st.positions), ds, exdiv)
    for code in list(st.positions):
        got = day_bar_and_prev_closes(bars[code], day) if code in bars else None
        if got is not None:
            row, closes = got
            fill_pending(st, code, row, day, day_i=day_i, ds=ds,
                         limits=shared._limits(st, code, closes, ds, names, exdiv))
    codes = list(dict.fromkeys([*st.positions, *pool_days.get(ds, [])]))
    for code in codes:
        got = day_bar_and_prev_closes(bars[code], day) if code in bars else None
        if got is None:
            continue
        row, closes = got
        st.book_state.setdefault("beidou_marks", {})[code] = float(row.open)
    for code in codes:
        got = day_bar_and_prev_closes(bars[code], day) if code in bars else None
        if got is None:
            continue
        row, closes = got
        if not strategy_lots(st, code) and code not in pool_days.get(ds, []):
            continue
        buy(st, code, float(row.open), closes, hooks=hooks, day_i=day_i, day=day,
            ds=ds, names=names, exdiv=exdiv, adding=bool(strategy_lots(st, code)))
    for code in list(st.positions):
        if not strategy_lots(st, code) or code not in bars:
            continue
        got = day_bar_and_prev_closes(bars[code], day)
        if got is None:
            continue
        row, closes = got
        mem = memory(st, code)
        if day_i > mem.entry_idx:
            mem.peak = max(mem.peak, float(row.high))
        pending = st.book_state.setdefault("beidou_pending", {})
        plan = plan_exit(st, code, float(row.close), day, closes, day_i=day_i, ds=ds,
                         params=hooks["beidou_params"], daily_close=True)
        if plan and (code not in pending or not plan[0].startswith("profit_take")):
            pending[code] = plan


class MinuteSession:
    """Signals use cursor close; unified next-open fill decisions persist across bars."""
    def __init__(self, st, pending_chase, *, hooks, minute_bars, daily_bars, pool_days,
                 day_i, day, ds, names, daily_quota, exdiv, slice_day,
                 price_context=None, fill_config=None, held_fill_states=None):
        codes = list(dict.fromkeys([*st.positions, *pool_days.get(ds, [])]))
        prepare(st, codes, ds, exdiv)
        self.frames, self.closes, self.limits = {}, {}, {}
        for c in codes:
            if c not in daily_bars or c not in minute_bars:
                continue
            prev = daily_bars[c].loc[daily_bars[c].index < day, "close"].astype(float).tolist()
            frame = slice_day(c, ds)
            if not prev or frame is None or frame.empty:
                continue
            self.frames[c] = {int(r.hm): r for r in frame.itertuples()}
            self.closes[c] = prev
            self.limits[c] = shared._limits(st, c, prev, ds, names, exdiv)
        self.clocks = {hm for f in self.frames.values() for hm in f}
        self.ctx = dict(st=st, hooks=hooks, day_i=day_i, day=day, ds=ds, names=names, exdiv=exdiv)
        self.fill_config = fill_config
        self.states = held_fill_states if held_fill_states is not None else {}
        self.cursors = {}
        self.pool = set(pool_days.get(ds, []))

    def advance_held(self, code, hm, phase):
        from backtest.research.minute_held_scan_core import HeldMinuteCursor
        st, hooks = self.ctx["st"], self.ctx["hooks"]
        row = self.frames.get(code, {}).get(hm)
        if row is None or not strategy_lots(st, code):
            return
        state = self.states.setdefault(("beidou", code), {})
        pending = st.book_state.setdefault("beidou_pending", {})
        mem = memory(st, code)
        if phase == "open":
            def decision(cursor, idx, at_phase):
                if at_phase == "open":
                    if code in pending:
                        state.pop("pending", None)
                        return cursor._exit(idx, row.open, pending[code][0] + ":next_open")
                    return None
                if code in pending:
                    return None
                if self.ctx["day_i"] > mem.entry_idx:
                    mem.peak = max(mem.peak, float(row.high))
                plan = plan_exit(st, code, float(row.close), self.ctx["day"], self.closes[code],
                                 day_i=self.ctx["day_i"], ds=self.ctx["ds"], params=hooks["beidou_params"],
                                 daily_close=hm == max(self.frames[code]))
                if plan:
                    pending[code] = plan
                    return cursor._price_exit(idx, row.close, plan[0])
                return None
            self.cursors[code] = HeldMinuteCursor(
                np.array([row.open]), np.array([row.high]), np.array([row.close]),
                l=np.array([row.low]), hm=np.array([hm]), cost=mem.entry, peak=mem.peak,
                n_days=self.ctx["day_i"]-mem.entry_idx, can_sell=True,
                stop_pct=None, profit_base=0., trail_ratio=0., phase_exit=decision,
                fill_config=self.fill_config, fill_state=state)
        cursor = self.cursors.get(code)
        if cursor is None:
            return
        event = cursor.advance(0, phase)
        if event is not None and code in pending:
            fill_pending(st, code, SimpleNamespace(open=event[1]), self.ctx["day"],
                         day_i=self.ctx["day_i"], ds=self.ctx["ds"], limits=self.limits[code],
                         bucket=hm, at=hm-1 if event[2].endswith(":next_open") else None)

    def after_open(self, hm):
        st = self.ctx["st"]
        for code, rows in self.frames.items():
            if hm in rows:
                st.book_state.setdefault("beidou_marks", {})[code] = float(rows[hm].open)
        for code in self.frames:
            rows = self.frames[code]
            if code in self.pool and hm == min(rows) and not strategy_lots(st, code):
                buy(**self.ctx, code=code, px=float(rows[hm].open), closes=self.closes[code],
                    bucket=hm, adding=False)

    def after_close(self, hm):
        st = self.ctx["st"]
        for code, rows in self.frames.items():
            if hm in rows:
                st.book_state.setdefault("beidou_marks", {})[code] = float(rows[hm].close)
        for code, rows in self.frames.items():
            row = rows.get(hm)
            if row is None:
                continue
            adding = bool(strategy_lots(st, code))
            if adding:
                buy(**self.ctx, code=code, px=float(row.close), closes=self.closes[code],
                    bucket=hm, adding=True)
