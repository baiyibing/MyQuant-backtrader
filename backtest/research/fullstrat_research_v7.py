"""Strategy 7 research replay: stage transitions occur only on real fills."""

from __future__ import annotations

from copy import deepcopy
from functools import partial
from collections.abc import Mapping

from backtest.research import csv_minute_backtest_v7 as v7
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
    index_days=None,
    *,
    config,
    cash_total=21_000_000.0,
    start=None,
    end=None,
    exdiv=None,
    exdiv_economics=None,
    names=None,
    fee=v7.DEFAULT_SCHEDULE,
    participation_rate=None,
    volume_for_bucket=None,
    initial_state=None,
):
    if participation_rate is not None or volume_for_bucket is not None:
        raise ValueError("batch4 is clock XOR slip; capacity is a separate axis")
    frames = minute_bars if v7._is_frame_map(minute_bars) else None
    minutes = {} if frames is not None else v7._minute_records(minute_bars)
    closes, pools = v7._daily_closes(daily_bars), v7._pool(pool_days)
    state = (
        deepcopy(initial_state)
        if initial_state is not None
        else v7.SimResult(float(cash_total))
    )
    state.research_orders = []
    state.research_initial_cash = float(state.cash)
    if exdiv_economics is not None:
        state.exdiv_economics = v7.ExDivEconomics(exdiv_economics)
    gate = (
        v7.build_index_gate({v7._as_date(d): float(c) for d, c in index_days.items()})
        if isinstance(index_days, Mapping)
        else {}
    )
    calendar = sorted(
        gate
        if isinstance(index_days, Mapping)
        else (map(v7._as_date, index_days) if index_days else set(minutes) | set(pools))
    )
    calendar = [
        d
        for d in calendar
        if (start is None or d >= v7._as_date(start))
        and (end is None or d <= v7._as_date(end))
    ]
    last_prices = {}
    for day in calendar:
        session = ResearchSession(config, day, state.research_orders)
        if state.exdiv_economics is not None:
            state.cash += state.exdiv_economics.settle(day.strftime("%Y%m%d"))
        cleared, sell_submitted, buying = set(), set(), set()
        needed = list(dict.fromkeys(pools.get(day, []) + list(state.positions)))
        symbols = (
            {s: v7._day_frame_records(frames.get(s), day) for s in needed}
            if frames is not None
            else minutes.get(day, {})
        )
        ordered = list(dict.fromkeys(needed + list(symbols)))
        for symbol in ordered:
            records = sorted(symbols.get(symbol, []), key=lambda r: int(r["hm"]))
            if not records:
                if symbol in pools.get(day, []):
                    v7._event(state, day, symbol, None, "skip", 0, None, "skip_no_1455")
                continue
            ymd = day.strftime("%Y%m%d")
            position = state.positions.get(symbol)
            if position is not None:
                v7._apply_exdiv_economics(state, position, ymd)
                factor = v7.k_for(exdiv, symbol, ymd)
                if factor is not None:
                    v7._rescale_position(position, factor)
            previous = v7.session_prev_close(closes.get(symbol, {}), day, symbol, exdiv)
            limits = v7.session_limit_prices(
                symbol, previous, (names or {}).get(symbol, "")
            )
            candidates = [
                OpenCandidate(
                    stamp(day, r["hm"]), float(r.get("open", r["close"])), limits
                )
                for r in records
            ]

            def submit_buy(symbol, px, hm, fraction, reason, kind, candidates):
                if symbol in buying:
                    return
                buying.add(symbol)

                def commit(fill_px, at):
                    position = state.positions.get(symbol)
                    position = v7._buy(
                        state,
                        position,
                        symbol,
                        day,
                        at.hour * 60 + at.minute
                        if config.clock_mode == NEXT_OPEN
                        else hm,
                        fill_px,
                        fraction,
                        reason,
                        kind,
                        fee=fee,
                    )
                    if position is None:
                        return False
                    stages = {
                        "add_a104": v7.FOUR,
                        "add_a108": v7.SIX,
                        "add_a112": v7.EIGHT,
                        "add_a116": v7.FULL,
                    }
                    if kind in stages:
                        position.stage = stages[kind]
                    state.trades[-1]["research_fill_at"] = at.isoformat()
                    buying.discard(symbol)
                    return True

                session.submit(
                    ResearchOrder(
                        symbol,
                        "buy",
                        available_at(day, hm),
                        px,
                        int(v7.NAME_BUDGET * fraction / px / 100) * 100,
                        commit,
                        candidates,
                        reject_buy_limit_down=True,
                        reason=reason,
                    )
                )

            def submit_sell(symbol, px, hm, reason, candidates, *, at_open=False):
                if symbol in sell_submitted:
                    return
                position = state.positions.get(symbol)
                eligible = [
                    lot for lot in position.lots if v7.t1_sellable(lot.buy_date, day)
                ]
                if not eligible:
                    return
                sell_submitted.add(symbol)

                def commit(fill_px, at):
                    position = state.positions.get(symbol)
                    if position is None:
                        return False
                    sold = v7._sell_lots(
                        state,
                        position,
                        day,
                        at.hour * 60 + at.minute
                        if config.clock_mode == NEXT_OPEN
                        else hm,
                        fill_px,
                        reason,
                        fee=fee,
                    )
                    if sold:
                        state.trades[-1]["research_fill_at"] = at.isoformat()
                    if symbol not in state.positions:
                        cleared.add(symbol)
                    return bool(sold)

                session.submit(
                    ResearchOrder(
                        symbol,
                        "sell",
                        available_at(day, hm, at_open=at_open),
                        px,
                        sum(lot.shares for lot in eligible),
                        commit,
                        candidates,
                        buy_day=min(lot.buy_date for lot in eligible),
                        reason=reason,
                    )
                )

            def on_row(
                row,
                *,
                symbol=symbol,
                limits=limits,
                previous=previous,
                candidates=candidates,
                last=False,
                first=False,
                at_open=False,
                submit_buy=submit_buy,
                submit_sell=submit_sell,
            ):
                hm, close = int(row["hm"]), float(row["close"])
                op = float(row.get("open", close))
                position = state.positions.get(symbol)
                if not at_open:
                    last_prices[symbol] = close
                    if position is not None:
                        position.peak = max(
                            position.peak, float(row.get("high", max(op, close)))
                        )
                if position is not None:
                    stop = v7.stop_decision(
                        position.stage,
                        entry_a=position.entry_A,
                        average_cost=position.avg_cost,
                    )
                    px = op if at_open else close
                    if stop.line is not None and px <= stop.line and limits is not None:
                        if not v7.defer_sell_at_limit(px, limits):
                            reasons = {
                                "dump_trial": "stop:trial_a090",
                                "clear_four": "stop:four_avg095",
                                "clear_six": "stop:six_avg0965",
                                "clear_eight": "stop:eight_avg0975",
                                "clear_full": "stop:full_avg098",
                            }
                            submit_sell(
                                symbol,
                                px,
                                hm,
                                reasons.get(stop.action, f"stop:{stop.action}"),
                                candidates,
                                at_open=at_open,
                            )
                if at_open:
                    return
                position = state.positions.get(symbol)
                if position is not None and v7.in_add_window(hm):
                    ladder = v7.ladder_decision(
                        position.stage, close, entry_a=position.entry_A
                    )
                    if (
                        ladder.action != "none"
                        and limits is not None
                        and not v7.skip_buy_at_limit(close, limits)
                        and not v7.defer_sell_at_limit(close, limits)
                    ):
                        submit_buy(
                            symbol,
                            close,
                            hm,
                            ladder.fraction,
                            "buy:" + ladder.action,
                            ladder.action,
                            candidates,
                        )
                if (
                    hm == 895
                    and symbol in pools.get(day, [])
                    and symbol not in state.positions
                    and symbol not in cleared
                    and not gate.get(day, False)
                    and previous is not None
                    and limits is not None
                    and not v7.skip_buy_at_limit(close, limits)
                    and not v7.defer_sell_at_limit(close, limits)
                ):
                    submit_buy(
                        symbol,
                        close,
                        hm,
                        v7.TRIAL_FRACTION,
                        "buy:trial",
                        "trial",
                        candidates,
                    )
                position = state.positions.get(symbol)
                if (
                    last
                    and position is not None
                    and position.last_add_date is not None
                    and v7.timer_due(
                        calendar, position.last_add_date, day, position.stage
                    )
                    and limits is not None
                    and not v7.defer_sell_at_limit(close, limits)
                ):
                    submit_sell(symbol, close, hm, "exit:timer10", candidates)

            for j, row in enumerate(records):
                if j == 0:
                    action = partial(on_row, row, first=True, at_open=True)
                    if config.clock_mode == NEXT_OPEN:
                        session.at(available_at(day, row["hm"], at_open=True), action)
                    else:
                        action()
                action = partial(on_row, row, first=j == 0, last=j == len(records) - 1)
                if config.clock_mode == NEXT_OPEN:
                    session.at(available_at(day, row["hm"]), action)
                else:
                    action()
            if symbol in pools.get(day, []) and not any(
                int(r["hm"]) == 895 for r in records
            ):
                v7._event(state, day, symbol, None, "skip", 0, None, "skip_no_1455")
        session.run()
        holdings = sum(
            p.shares * last_prices.get(s, p.avg_cost)
            for s, p in state.positions.items()
        )
        equity = state.cash + holdings
        if state.exdiv_economics is not None:
            equity += state.exdiv_economics.receivable_total
        state.equity_curve.append(
            dict(
                date=day.isoformat(), cash=state.cash, holdings=holdings, equity=equity
            )
        )
    return state
