"""ModeB research fills and portfolio replay; original default API is untouched.

The signal evaluator below mirrors the frozen engine at 32b78b1, with one
explicit after_day mask: expiry discards an intent without discarding price
history needed to reevaluate trailing/stale conditions next session.
"""

from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.research import unified_exit_modeb as modeb
from backtest.research import unified_exit_modea as modea
from backtest.research.ashare_session import session_limit_prices
from backtest.research.fullstrat_research_hooks import (
    NEXT_OPEN,
    OpenCandidate,
    ResearchOrder,
    ResearchSession,
    available_at,
    stamp,
)


def _first_hit(path, spec, *, lp, tol, index_block=None, after_day=""):
    n = path.close.size
    if n == 0:
        return None
    sl_on = spec.rule in (2, 4, 5, 6) and spec.y is not None
    tp_on = spec.rule in (2, 4, 6) and spec.x is not None
    trail_on = spec.rule == 3
    live_on = spec.rule in (4, 5)
    bands_on = spec.rule == 4 and spec.x is None
    expire_on = spec.rule in (1, 2, 3, 6)
    index_on = spec.rule == 6
    ev = np.zeros(n, dtype=np.int8)
    fill = path.close.copy()
    peak = None
    if trail_on or live_on:
        peak = modeb._close_peak(path)
    if expire_on:
        ev[(path.held >= spec.n) & path.is_last] = 4
    if trail_on:
        ev[path.close < peak * (1.0 - spec.y / 100.0)] = 3
        fill[ev == 3] = path.close[ev == 3]
    if live_on:
        stale = (path.held >= spec.n) & (
            peak < path.cost * (1.0 + modeb.s8.BAND_ARMS[0])
        )
        ev[stale] = 5
        fill[stale] = path.close[stale]
        if bands_on:
            line = modeb._v8_band_line(path.cost, peak)
            band = (
                (path.close >= path.cost)
                & (peak > path.cost * modeb.s8.BAND_TRAIL_MIN_MULT)
                & (path.close <= line)
            )
            ev[band] = 6
            fill[band] = path.close[band]
    if tp_on:
        hit = path.close >= path.cost * (1.0 + spec.x / 100.0)
        ev[hit] = 2
        fill[hit] = path.close[hit]
    if sl_on:
        hit = path.close <= path.cost * (1.0 - spec.y / 100.0)
        ev[hit] = 1
        fill[hit] = path.close[hit]
    if index_on and index_block:
        blocked = np.fromiter(
            (bool(index_block.get(str(ymd), False)) for ymd in path.ymd),
            dtype=bool,
            count=n,
        )
        ev[blocked] = 7
        fill[blocked] = path.open[blocked]
    if tp_on:
        hit = path.open >= path.cost * (1.0 + spec.x / 100.0)
        ev[hit] = 2
        fill[hit] = path.open[hit]
    if sl_on:
        hit = path.open <= path.cost * (1.0 - spec.y / 100.0)
        ev[hit] = 1
        fill[hit] = path.open[hit]
    open_ld = modeb._ld_mask(path.open, path.prev, lp, tol)
    fill_ld = modeb._ld_mask(fill, path.prev, lp, tol)
    blocker = open_ld | ((ev > 0) & fill_ld)
    prev_cum = np.empty(n, dtype=np.int32)
    prev_cum[0] = 0
    if n > 1:
        prev_cum[1:] = np.cumsum(blocker.astype(np.int32))[:-1]
    starts = np.flatnonzero(
        np.concatenate(([True], path.day_id[1:] != path.day_id[:-1]))
    )
    already = prev_cum > prev_cum[starts[path.day_id]]
    sell = (ev > 0) & ~open_ld & ~fill_ld & ~already
    sell &= path.ymd > after_day
    if not sell.any():
        return None
    i = int(np.flatnonzero(sell)[0])
    code = int(ev[i])
    if code == 6:
        reason = (
            modeb.s8.take_profit_reason(
                float(path.close[i]),
                float(path.cost[i]),
                float(peak[i]),
                int(path.held[i]),
            )
            or "trail:band"
        )
    else:
        reason = modeb._REASON[code]
    return i, reason, float(fill[i])


def evaluate_exit(
    inst, spec, daily, minutes, sessions, *, config, end, tol, exdiv, index_block, audit
):
    if config.clock_mode != NEXT_OPEN:
        er = modeb.evaluate_exit_modeb(
            inst,
            spec,
            daily,
            minutes,
            sessions,
            end=end,
            tol=tol,
            exdiv=exdiv,
            index_block=index_block,
        )
        if not er.is_trade:
            if er.sell_date == inst.list_date:
                mark = minutes.last_close(inst.symbol, inst.list_date)
                if mark is not None:
                    for day in sessions:
                        if inst.list_date < day <= end:
                            mark *= (exdiv or {}).get(inst.symbol, {}).get(day, 1.0)
                    return modeb._result(
                        inst,
                        er.sell_date,
                        er.sell_hm,
                        mark,
                        er.shares,
                        er.hold_sessions,
                        er.reason,
                        trade=False,
                    )
            return er
        return modeb._result(
            inst,
            er.sell_date,
            er.sell_hm,
            config.price(er.sell_price, "sell"),
            er.shares,
            er.hold_sessions,
            er.reason,
            trade=True,
        )
    refs = modeb._previous_refs(daily, inst.symbol, exdiv)
    path = modeb._instance_path(inst, minutes, sessions, refs, end=end, exdiv=exdiv)
    lp = modeb.limit_pct(inst.symbol, inst.name)
    after = ""
    while True:
        hit = _first_hit(
            path, spec, lp=lp, tol=tol, index_block=index_block, after_day=after
        )
        if hit is None:
            return modeb._result(
                inst,
                path.mark_day,
                path.mark_hm,
                path.mark_price,
                path.mark_shares,
                path.mark_held,
                "mark_end",
                trade=False,
            )
        idx, reason, px = hit
        day, hm = str(path.ymd[idx]), int(path.hm[idx])
        # Q39 gives gap stop/take-profit and the index rule open priority.
        stop_open = (
            spec.rule in (2, 4, 5, 6)
            and spec.y is not None
            and path.open[idx] <= path.cost[idx] * (1 - spec.y / 100)
        )
        take_open = (
            spec.rule in (2, 4, 6)
            and spec.x is not None
            and path.open[idx] >= path.cost[idx] * (1 + spec.x / 100)
        )
        index_open = spec.rule == 6 and bool(index_block.get(day, False))
        at = available_at(day, hm, at_open=stop_open or take_open or index_open)
        session = ResearchSession(config, day, audit)
        rows = np.flatnonzero(path.ymd == day)
        limits = session_limit_prices(inst.symbol, refs.get(day), inst.name)
        candidates = [
            OpenCandidate(stamp(day, path.hm[j]), float(path.open[j]), limits)
            for j in rows
        ]
        result = []

        def commit(fill_px, fill_at):
            result.append(
                modeb._result(
                    inst,
                    day,
                    fill_at.hour * 60 + fill_at.minute,
                    fill_px,
                    float(path.shares[idx]),
                    int(path.held[idx]),
                    reason,
                    trade=True,
                )
            )
            return True

        session.submit(
            ResearchOrder(
                inst.symbol,
                "sell",
                at,
                px,
                int(path.shares[idx]),
                commit,
                candidates,
                buy_day=modea.ymd_to_date(inst.list_date),
                reason=reason,
            )
        )
        session.run()
        if result:
            return result[0]
        after = day  # New strategy evaluation on later sessions; no retained intent.


def build_daily_equity(instances, exits, minutes, sessions, *, cash_pool, exdiv):
    """Replay fills and unslipped market marks, including the entry session.

    The native ModeB loop initializes a new lot's mark to buy_price because
    its default buy is exactly the daily close. With slip those prices differ;
    keep the actual close as the frozen mark even across missing later bars.
    """
    buys = {}
    for inst in instances:
        buys.setdefault(inst.list_date, []).append(inst)
    cash, held, rows, peak_lots = float(cash_pool), {}, [], 0
    for day in sessions:
        for key, (inst, shares, price) in list(held.items()):
            factor = (exdiv or {}).get(inst.symbol, {}).get(day, 1.0)
            shares /= factor
            price *= factor
            er = exits[key]
            if er.is_trade and er.sell_date == day:
                cash += er.shares * er.sell_price * (1 - modea.COMMISSION)
                del held[key]
                continue
            last = minutes.last_close(inst.symbol, day)
            held[key] = (inst, shares, price if last is None else last)
        for inst in buys.get(day, []):
            shares = float(modea._lot_shares(inst.buy_price))
            cash -= shares * inst.buy_price * (1 + modea.COMMISSION)
            mark = minutes.last_close(inst.symbol, day)
            if mark is None:
                raise ValueError(f"missing entry mark: {inst.symbol} {day}")
            held[modea.instance_key(inst)] = (inst, shares, mark)
        mtm = sum(shares * price for _, shares, price in held.values())
        peak_lots = max(peak_lots, len(held))
        rows.append(
            dict(date=day, equity=cash + mtm, cash=cash, lots=len(held), mtm=mtm)
        )
    return rows, peak_lots, peak_lots * modea.LOT_NOTIONAL


def run(
    pool_dir,
    *,
    config,
    start=modea.DEFAULT_START,
    end=modea.DEFAULT_END,
    bars=None,
    minute_bars=None,
    sessions=None,
    exdiv=None,
    index_block=None,
    out_dir,
    cash_pool=modea.CASH_POOL,
    tol=modea.DEFAULT_TOL,
    workers=8,
):
    if bars is None or minute_bars is None:
        raise ValueError("batch4 requires explicit same-lineage daily and minute bars")
    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ValueError(f"refuse reusing research artifacts: {out_dir}")
    sess = modea.load_session_calendar(start, end, sessions=sessions)
    daily = modea._prepare_bars(bars)
    minutes = modeb._prepare_minutes(minute_bars)
    codes = list(daily)
    if exdiv is None:
        exdiv = modeb.load_exdiv_ratios(codes, modeb.warmup_start(start, days=20), end)
    if index_block is None:
        index_block = modeb.load_sse_ma10_block_ymd(start, end)
    index_block = modeb._block_ymd(index_block)
    signals = modeb.assemble_instances(pool_dir, sess, daily, tol=tol, exdiv=exdiv)
    matrix, metrics, all_audit, equities = {}, [], [], {}
    for spec in modeb.iter_grid():
        if spec.rule == 0:  # Market marks are not fills or executable oracle trades.
            continue
        admitted, exits, audit = [], {}, []
        cash = float(cash_pool)
        pending_proceeds = {}
        for day in sess:
            cash += pending_proceeds.pop(day, 0.0)
            session = ResearchSession(config, day, audit)
            for inst in signals:
                if not inst.opened or inst.list_date != day:
                    continue
                refs = modeb._previous_refs(daily, inst.symbol, exdiv)
                limits = session_limit_prices(inst.symbol, refs.get(day), inst.name)
                pk = minutes.packed.get(inst.symbol)
                sl = None if pk is None else pk.slices.get(day)
                if sl is None:
                    raise ValueError(f"missing entry minutes: {inst.symbol} {day}")
                a, b = sl
                # The daily close is available only after the last START bar.
                decision = available_at(day, int(pk.hm[b - 1]))
                candidates = [
                    OpenCandidate(stamp(day, pk.hm[j]), float(pk.open[j]), limits)
                    for j in range(a, b)
                ]

                def commit(px, at, inst=inst):
                    nonlocal cash
                    shares = modea._lot_shares(px)  # Q2: fill price, not signal shares.
                    cost = shares * px * (1 + modea.COMMISSION)
                    if shares <= 0 or cost > cash:
                        return False
                    filled = replace(inst, buy_price=px)
                    er = evaluate_exit(
                        filled,
                        spec,
                        daily,
                        minutes,
                        sess,
                        config=config,
                        end=end,
                        tol=tol,
                        exdiv=exdiv,
                        index_block=index_block,
                        audit=audit,
                    )
                    admitted.append(filled)
                    exits[modea.instance_key(filled)] = er
                    cash -= cost
                    if er.is_trade:
                        pending_proceeds[er.sell_date] = pending_proceeds.get(
                            er.sell_date, 0.0
                        ) + er.shares * er.sell_price * (1 - modea.COMMISSION)
                    return True

                session.submit(
                    ResearchOrder(
                        inst.symbol,
                        "buy",
                        decision,
                        inst.buy_price,
                        modea._lot_shares(inst.buy_price),
                        commit,
                        candidates,
                        reason="daily_close_entry",
                    )
                )
            session.run()
        metric = modeb.aggregate_strategy(
            spec.label(),
            admitted,
            exits,
            minutes,
            sess,
            cash_pool=cash_pool,
            exdiv=exdiv,
        )
        equity, peak_lots, capital = build_daily_equity(
            admitted, exits, minutes, sess, cash_pool=cash_pool, exdiv=exdiv
        )
        total = (equity[-1]["equity"] - cash_pool) / cash_pool
        # Keep the native trade statistics; portfolio metrics come from the
        # complete cash/holding replay with actual market marks above.
        metric = replace(
            metric,
            total_return=total,
            annualized=modea._annualize(total),
            max_drawdown=modea._max_drawdown(equity),
            peak_concurrent_lots=peak_lots,
            peak_concurrent_capital=capital,
        )
        metrics.append(metric)
        matrix[spec.label()] = exits
        equities[spec.label()] = equity
        all_audit.extend(dict(row, strategy=spec.label()) for row in audit)
    ranked = modea.rank_strategies(metrics)
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([asdict(m) for m in ranked]).to_csv(
        out_dir / "ranking.csv", index=False
    )
    pd.DataFrame(equities[ranked[0].label]).to_csv(
        out_dir / "daily_equity.csv", index=False
    )
    (out_dir / "research_orders.json").write_text(
        json.dumps(all_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return dict(ranked=ranked, matrix=matrix, research_orders=all_audit)
