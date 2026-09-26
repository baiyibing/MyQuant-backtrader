"""Book research replay, isolated from the production simulator and ledger.

Strategy hooks, scanners, lot sizing, fees and marks remain engine primitives.
The experimental clock schedules decisions and books only actual fills.
"""

from __future__ import annotations

from functools import partial

import numpy as np

from backtest.research import csv_minute_backtest as book
from backtest.research import csv_ledger as ledger
from backtest.research import csv_simulate_loop as loop
from backtest.research.ashare_session import skip_buy_at_limit, defer_sell_at_limit
from backtest.research.fullstrat_research_hooks import (
    NEXT_OPEN,
    OpenCandidate,
    ResearchOrder,
    ResearchSession,
    available_at,
    stamp,
)


def simulate(
    minute_bars,
    daily_bars,
    pool_days,
    start,
    end,
    *,
    config,
    strategy,
    total_cash=book.DEFAULT_TOTAL_CASH,
    daily_quota=book.DEFAULT_DAILY_QUOTA,
    pool_names=None,
    pool_names_by_day=None,
    exdiv=None,
    exdiv_economics=None,
    pos_trail=book.POS_TRAIL,
    participation_rate=None,
    volume_for_bucket=None,
    **kwargs,
):
    if participation_rate is not None or volume_for_bucket is not None:
        raise ValueError("batch4 is clock XOR slip; capacity is a separate axis")
    hooks = loop.prepare_strategy_hooks(
        strategy, apply_fn=book.apply_csv_strategy, **kwargs
    )
    calendar = book.build_calendar(daily_bars, start, end)
    st, pending_chase, names_asof = loop.init_sim_state(
        hooks,
        total_cash=total_cash,
        bars_loaded=len(minute_bars),
        pool_days=pool_days,
        pool_names=pool_names,
        pool_names_by_day=pool_names_by_day,
    )
    # This isolated experimental replay retains its original lot/clock model.
    # Corrected independent groups belong to the public daily/minute engines.
    st.book_state.pop("s8_independent", None)
    if exdiv_economics is not None:
        st.exdiv_economics = book.ExDivEconomics(exdiv_economics, st.stats)
    st.research_orders = []
    st.research_initial_cash = float(total_cash)
    spans = {code: book.build_day_spans(frame) for code, frame in minute_bars.items()}
    for i, day in enumerate(calendar):
        ds = ledger._ymd(day)
        names = names_asof(ds)
        session = ResearchSession(config, day, st.research_orders)
        st.daily_quota_used = 0.0
        if st.exdiv_economics is not None:
            st.cash += st.exdiv_economics.settle(ds)
        if callable(hooks.get("bind_opening_held")):
            hooks["bind_opening_held"](ds, list(st.positions))
        frames, closes, limits = {}, {}, {}
        for code, frame in minute_bars.items():
            ddf = daily_bars.get(code)
            if ddf is None or day not in ddf.index:
                continue
            rows = book._slice_day(frame, spans[code], ds)
            prev = book._previous_rows(ddf, day)
            if rows is None or rows.empty or prev.empty:
                continue
            frames[code] = rows
            closes[code] = prev["close"].astype(float).tolist()
            ref, _ = book.mapped_prev_close(exdiv, code, ds, closes[code][-1])
            limits[code] = book.book_limit_prices(
                code, ref, names, qlib_limit_pct=hooks.get("qlib_limit_pct")
            )

        def candidates(code):
            return [
                OpenCandidate(stamp(day, row.hm), float(row.open), limits.get(code))
                for row in frames[code].itertuples()
            ]

        def quote(code, target, earliest):
            frame = frames.get(code)
            if frame is None:
                return None
            rows = frame.loc[(frame.hm >= earliest) & (frame.hm <= target)]
            return None if rows.empty else rows.iloc[-1]

        def buy(code, px, per, hm, reason, *, is_step=False):
            tentative, _ = ledger._buy_size(per, px)

            def commit(fill_px, at):
                used = st.daily_quota_used
                ok = ledger.execute_buy(
                    st, code, fill_px, per, i, day, reason=reason, is_step=is_step
                )
                if hooks.get("sizing") == "per_name":
                    st.daily_quota_used = used
                if ok:
                    st.trades[-1]["research_fill_at"] = at.isoformat()
                return ok

            def done(ok):
                if reason.startswith("chase") and not ok:
                    st.stats["chase_buy_fail"] += 1
                elif not ok:
                    key = (
                        "research_buy_expired"
                        if session.audit[-1]["reason"] == "same_day_expiry"
                        else "skip_cash"
                    )
                    st.stats[key] = st.stats.get(key, 0) + 1

            session.submit(
                ResearchOrder(
                    code,
                    "buy",
                    available_at(day, hm),
                    px,
                    tentative,
                    commit,
                    candidates(code),
                    reject_buy_limit_down=bool(hooks.get("forbid_all_trade_at_limit")),
                    reason=reason,
                    on_done=done,
                )
            )

        # Existing day scanner runs on each opening lot. It supplies a signal,
        # never an executed trade. State writeback waits until that signal time.
        for code in list(st.positions):
            if code not in frames or limits.get(code) is None:
                continue
            ledger.apply_exdiv_economics(st, code, ds)
            factor = book.k_for(exdiv, code, ds)
            rows = frames[code]
            o, h, c = (
                rows[col].to_numpy(np.float64) for col in ("open", "high", "close")
            )
            hm = rows.hm.to_numpy(np.int64)
            for pos in list(st.positions[code]):
                if factor is not None:
                    ledger.rescale_position(pos, factor)
                if pos.ride_with is not None:
                    continue
                reserve = {"reserved": bool(pos.reserved)}
                idx, px, reason, peak, peak_hm = book.scan_held_day(
                    o,
                    h,
                    c,
                    cost=pos.cost,
                    peak=pos.peak,
                    n_days=i - pos.entry_idx,
                    can_sell=book.t1_sellable(
                        calendar[pos.entry_idx].date(), day.date()
                    ),
                    stop_pct=hooks["stop_pct"],
                    profit_base=kwargs.get("profit_base") or 0.0,
                    trail_ratio=0.0,
                    pos_trail=pos_trail,
                    limit_down=limits[code][1],
                    limit_up=limits[code][0],
                    hm=hm,
                    peak_hm=pos.peak_hm,
                    peak_gap_min=int(hooks["peak_gap_min"]),
                    take_profit=hooks["take_profit"],
                    sell_gate=hooks.get("sell_gate"),
                    gate_code=code,
                    gate_day=day,
                    daily_closes_ending_yesterday=closes[code],
                    force_sell_hm=hooks.get("force_sell_hm"),
                    reserve_limit_up=bool(hooks.get("reserve_limit_up")),
                    defer_limit_up=bool(hooks.get("defer_limit_up")),
                    reserved=pos.reserved,
                    reserve_state=reserve,
                )

                def writeback(pos=pos, peak=peak, peak_hm=peak_hm, reserve=reserve):
                    pos.peak, pos.peak_hm = peak, peak_hm
                    pos.reserved = bool(reserve["reserved"])
                    pos.pending_exit = ""

                if idx < 0:
                    session.at(available_at(day, int(hm[-1])), writeback)
                    continue
                if defer_sell_at_limit(
                    float(o[idx]), limits[code]
                ) or defer_sell_at_limit(float(px), limits[code]):
                    st.stats["defer_sell_limit_down"] += 1
                    session.at(available_at(day, int(hm[idx])), writeback)
                    continue
                at = available_at(
                    day, int(hm[idx]), at_open=reason == "stop_loss:gap_open"
                )

                def signal(
                    code=code,
                    pos=pos,
                    px=px,
                    reason=reason,
                    at=at,
                    writeback=writeback,
                    rows=rows,
                ):
                    writeback()

                    def commit(fill_px, fill_at):
                        if not any(p is pos for p in st.positions.get(code, [])):
                            return False
                        group = [pos] + [
                            p
                            for p in st.positions[code]
                            if p.ride_with == pos.lot_id and p is not pos
                        ]
                        if any(p.entry_idx >= i for p in group):
                            return False
                        before = len(st.trades)
                        ledger._sell(
                            st,
                            code,
                            pos,
                            fill_px,
                            day,
                            reason,
                            hm=fill_at.hour * 60 + fill_at.minute,
                            price_rule="research_next_open"
                            if config.clock_mode == NEXT_OPEN
                            else "research_slip",
                        )
                        for trade in st.trades[before:]:
                            trade["research_fill_at"] = fill_at.isoformat()
                        return len(st.trades) > before

                    def done(filled):
                        if not filled and any(
                            p is pos for p in st.positions.get(code, [])
                        ):
                            # The lot remains held through the rest of the day.
                            # Keep observed peaks, but discard the expired exit.
                            high = float(rows["high"].max())
                            if high > pos.peak:
                                peak_row = rows.loc[rows["high"] == high].iloc[0]
                                pos.peak, pos.peak_hm = high, int(peak_row.hm)
                            pos.pending_exit = ""

                    session.submit(
                        ResearchOrder(
                            code,
                            "sell",
                            at,
                            px,
                            pos.shares,
                            commit,
                            candidates(code),
                            buy_day=calendar[pos.entry_idx].date(),
                            reason=reason,
                            on_done=done,
                        )
                    )

                if config.clock_mode == NEXT_OPEN:
                    session.at(at, signal)
                else:
                    signal()  # Slip retains the engine's default day ordering.

        def allowed(code, *, step=False):
            lots = st.positions.get(code, [])
            if lots and not hooks["allow_add"] and not step:
                st.stats["skip_held"] += 1
                return False
            new_gate = hooks.get("allow_new_name")
            if not step and callable(new_gate) and not new_gate(day):
                if not (lots and not hooks.get("index_blocks_add", True)):
                    st.stats["skip_index_gate"] += 1
                    return False
            if limits.get(code) is None:
                st.stats["skip_unknown_board"] += 1
                return False
            return True

        def price_gates(code, px, *, step=False):
            lots = st.positions.get(code, [])
            buy_gate = hooks.get("buy_gate")
            if callable(buy_gate) and not buy_gate(code, px, day, closes[code]):
                st.stats["skip_buy_gate"] += 1
                return False
            add_gate = hooks.get("add_gate")
            if lots and not step and callable(add_gate) and not add_gate(lots, px):
                st.stats["skip_add_loser"] += 1
                return False
            return True

        def chase_signal(code, row):
            if code not in pending_chase:
                return
            per, _ = pending_chase.pop(code)
            px = float(row.close)
            if not allowed(code):
                return
            quotes = book._chase_quotes(frames[code])
            if quotes is None:
                return
            decision = ledger.chase_decision(quotes[0], px, limits[code][0])
            if decision != "buy":
                key = "chase_skip_limit" if decision == "limit" else "chase_abandon"
                st.stats[key] += 1
                return
            if not price_gates(code, px):
                return
            buy(code, px, per, int(row.hm), "chase:T+1")

        for code, (_, sig) in list(pending_chase.items()):
            row = quote(code, book.CHASE_HM, book.AM_OPEN)
            if i > sig and row is not None:
                action = partial(chase_signal, code, row)
                if config.clock_mode == NEXT_OPEN:
                    session.at(available_at(day, int(row.hm)), action)
                else:
                    action()

        planned = loop.apply_capital_ration(
            list(pool_days.get(ds, [])),
            ration=hooks.get("ration", "file_order"),
            ration_seed=hooks.get("ration_seed", 0),
            ds=ds,
        )
        sizing = hooks.get("sizing", "daily_quota")
        name_budget = hooks.get("name_budget", 1_000_000.0)
        per_day = None

        def pool_signal(code, row, *, step=False):
            nonlocal per_day
            px = float(row.close)
            lots = st.positions.get(code, [])
            if step and (
                sizing != "per_name" or not lots or not hooks["step_add"](lots, px)
            ):
                return
            if per_day is None:
                per_day = (
                    min(daily_quota, st.cash)
                    * (hooks.get("cash_deploy_frac") or 1.0)
                    / max(1, len(planned))
                )
            per = name_budget if sizing == "per_name" else per_day
            if not allowed(code, step=step):
                return
            if skip_buy_at_limit(px, limits[code]) or (
                hooks.get("forbid_all_trade_at_limit")
                and defer_sell_at_limit(px, limits[code])
            ):
                if not step and hooks.get("limit_up_chase", True):
                    ledger.queue_limit_up_chase(st, pending_chase, code, per, i)
                else:
                    st.stats["skip_limit_up"] += 1
                return
            if not price_gates(code, px, step=step):
                return
            if sizing == "per_name" and callable(hooks.get("name_lot_budget")):
                per = float(hooks["name_lot_budget"](name_budget, lots))
            buy(
                code,
                px,
                per,
                int(row.hm),
                "add:step20" if step else "pool",
                is_step=step,
            )

        for code in planned:
            row = quote(code, book.BUY_HM, 870)
            if row is None:
                st.stats["skip_no_bar"] += 1
                continue
            action = partial(pool_signal, code, row)
            if config.clock_mode == NEXT_OPEN:
                session.at(available_at(day, int(row.hm)), action)
            else:
                action()
        if callable(hooks.get("step_add")):
            for code in list(st.positions):
                row = quote(code, book.BUY_HM, 870)
                if row is not None:
                    action = partial(pool_signal, code, row, step=True)
                    if config.clock_mode == NEXT_OPEN:
                        session.at(available_at(day, int(row.hm)), action)
                    else:
                        action()
        session.run()
        loop.append_equity_and_eod_marks(
            st, ds=ds, day=day, calendar_last=calendar[-1], mark_bars=daily_bars
        )
    ledger.finish_pending_chase(st, pending_chase)
    return st
