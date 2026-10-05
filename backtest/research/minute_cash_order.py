"""Shared-minute X-02 scheduling and resumable held-position exits.

This module owns ``HeldMinuteCursor`` (scan state and exit candidates),
``advance_independent_exit`` (whole-signal-position exits through the existing
ledger, settling T+1-eligible lots), and ``run_chronological_day`` (shared account
dispatch by hm, open/close phase, and existing stable order). The legacy
independent-position path also uses the cursor and exit helper; those calls
alone do not imply chronological account scheduling.

The shared entry selects scheduling: ``--fix-minute-cash-order`` defaults OFF
and is refused ON for version12. Valid TopK non-close execution or walkdown
also selects chronological dispatch with the flag OFF; real limits alone do
not. Quotes, fallback buckets, book rules and ledger gates retain their own
contracts. Same-hm close sell proceeds may fund later close buys, never earlier
open buys. The independent v7 scheduler and its post-buy timer stay in
``csv_minute_backtest_v7``; this module does not own their order.

The cursor preserves the research scanner's high-before-gap-open approximation.
Gap stops settle in the open phase; hl touches and fixed-target checks run in
the close phase, even when a gap-target fill quotes open. These are OHLC phase
conventions, not tick-level ordering. See
``docs/backtest/s2c-x02-cash-order-boundary-2026-09-28.md`` and
``docs/backtest/minute-fill-policy-ssot.md`` (X2 / section 4) for the boundary
and S2-B hl cross-reference. This documentation does not change scheduling.
"""

from __future__ import annotations

import numpy as np

from backtest.research.ashare_bars import AM_CLOSE, AM_OPEN, PM_CLOSE, PM_OPEN
from backtest.research.ashare_session import defer_sell_at_limit, skip_buy_at_limit, t1_sellable
from backtest.research.csv_common import book_limit_prices
from backtest.research.csv_ledger import (
    CHASE_HM,
    PEAK_GAP_MIN,
    IndependentExitPosition,
    InsufficientCashError,
    _sell,
    apply_exdiv_economics,
    exit_positions,
    execute_buy,
    hit_limit_down,
    hit_limit_up,
    position_is_open,
    rescale_position,
    rescale_s8_groups,
    s8_policy,
    trade_commission,
)
from backtest.research.csv_simulate_loop import (
    apply_capital_ration,
    run_chase_due_day,
    run_pool_buys_day,
    run_step_adds_day,
)
from backtest.research.exdiv_map import k_for, mapped_prev_close
from backtest.research.minute_held_scan_core import HeldMinuteCursor
from backtest.research.fill_config import is_open_fill
from backtest.research.minute_audit import audit_scope
from backtest.research.strategy9_rules import evaluate_version9_exit
from backtest.research.tail_window_buy import (
    TAIL_MINUTES,
    TAIL_START,
    TailParent,
    resolve_tail_volume_unit,
    tail_quote,
)

BUY_HM = 14 * 60 + 55
CLOSE_CLEAR_HM = 15 * 60


def advance_independent_exit(
    st, code, pos, cursor, idx, phase, limits, *, day, day_i, audit_sink=None,
):
    """Advance a whole signal position and settle only its T+1-eligible lots.

    A remembered T+1 or volume tail exits at the next tradable bar open.
    With a completed-volume cap its first eligible point is the bar close.
    Fresh signals retain the scanner's existing limit-down gate/retry rules.
    """
    if not position_is_open(st, pos):
        return
    at_hm = int(cursor.hm[idx])
    cursor.cost = pos.cost
    cursor.peak, cursor.peak_hm = pos.peak, pos.peak_hm
    pending = bool(pos.pending_exit)
    if pending:
        pending_phase = "close" if st.volume_cap is not None else "open"
        if phase != pending_phase or not any(
            lot.entry_idx < day_i and lot.position_id == pos.position_id
            for lot in st.positions.get(code, [])
        ):
            return
        px = float(cursor.c[idx] if phase == "close" else cursor.o[idx])
        reason = pos.pending_exit
    else:
        event = cursor.advance(idx, phase)
        pos.peak, pos.peak_hm = cursor.peak, cursor.peak_hm
        pos.reserved = cursor.current_reserved
        if event is None:
            return
        _, px, reason = event
    if not np.isfinite(px) or px <= 0:
        return
    if (
        (not pending and defer_sell_at_limit(float(cursor.o[idx]), limits))
        or defer_sell_at_limit(px, limits)
    ):
        st.stats["defer_sell_limit_down"] += 1
        return
    volume_kwargs = {}
    if st.volume_cap is not None:
        volume_kwargs = {
            "bucket_id": at_hm,
            "at": at_hm - 1 if phase == "open" else at_hm,
        }
    if pending:
        price_rule = "minute_trigger_bar_close" if phase == "close" else "minute_pending_next_open"
    else:
        price_rule = {
            "stop_loss:gap_open": "minute_gap_open",
            "stop_loss:touch": "minute_stop_price" if cursor.minute_stop_trigger == "hl" else "minute_trigger_bar_close",
        }.get(reason, "")
        if reason.endswith(":next_open"):
            price_rule = "minute_pending_next_open"
    with audit_scope(audit_sink, decision_hm=at_hm, quote_hm=at_hm, phase=phase):
        _sell(
            st, code, pos, px, day, reason, day_i=day_i, **volume_kwargs,
            hm=at_hm if price_rule else None, price_rule=price_rule,
        )


def scale_out_exits(st, code, pos, px, day, day_i, limits, *, scale_step, scale_frac, hm=None):
    """6.13：相对首仓锚价每满 scale_step 涨幅，卖出当时剩余持仓的 scale_frac。

    逐分钟 close 相位调用；每档一次（组计数器）；整百股向下、FIFO 切 lot；
    lot 级 T+1 由 _sell(wanted_shares) 保证；跌停顺延；组已同分钟离场则不触发。
    """
    if not scale_step or px <= 0 or not position_is_open(st, pos):
        return 0
    anchor_cost = float(getattr(pos.group, "anchor_cost", None) or pos.group.first_lot.cost)
    if anchor_cost <= 0 or float(px) < anchor_cost:
        return 0
    allowed = int((float(px) / anchor_cost - 1.0 + 1e-12) / float(scale_step))
    if allowed <= pos.group.scale_steps:
        return 0
    lots = [lot for lot in st.positions.get(code, [])
            if getattr(lot, "position_id", None) == pos.position_id]
    shares_now = sum(lot.shares for lot in lots)
    if shares_now <= 0:
        pos.group.scale_steps = allowed
        return 0
    target = int(shares_now * float(scale_frac) // 100) * 100
    sold = 0
    if target > 0:
        for lot in lots:
            if sold >= target:
                break
            chunk = min(lot.shares, target - sold)
            chunk = chunk // 100 * 100
            if chunk <= 0 or lot.entry_idx >= day_i:
                continue
            if defer_sell_at_limit(px, limits):
                st.stats["defer_sell_limit_down"] += 1
                return sold
            filled = _sell(
                st, code, lot, px, day, "scale_out:5pct", day_i=day_i,
                hm=hm, price_rule="minute_trigger_bar_close",
                wanted_shares=chunk,
            )
            sold += int(filled)
    pos.group.scale_steps = allowed
    if sold:
        st.stats["sell_scale_out"] = int(st.stats.get("sell_scale_out", 0)) + 1
    return sold


def step_stop_exits(st, code, pos, px, day, day_i, limits, *, step_stop_pct, hm=None):
    """6.8：step lot 自带独立止损（相对自身买价 −step_stop_pct，触发只卖该 lot）。

    在组级退出评估之后逐分钟 close 调用；组已同分钟离场则 lots 已空、自然不触发。
    T+1 按 lot entry_idx；跌停顺延次日再评；止损线随 E-R6 缩放后的 lot 成本走。
    """
    if not step_stop_pct or px <= 0 or not position_is_open(st, pos):
        return 0
    sold = 0
    for lot in list(st.positions.get(code, [])):
        if (
            getattr(lot, "position_id", None) != pos.position_id
            or not getattr(lot, "is_step", False)
            or lot.entry_idx >= day_i
        ):
            continue
        line = float(lot.cost) * (1.0 - float(step_stop_pct))
        if float(px) > line:
            continue
        if defer_sell_at_limit(px, limits):
            st.stats["defer_sell_limit_down"] += 1
            continue
        filled = _sell(
            st, code, lot, px, day,
            f"stop_loss:step{round(float(step_stop_pct) * 100)}", day_i=day_i,
            hm=hm, price_rule="minute_trigger_bar_close",
        )
        if filled:
            sold += 1
            st.stats["sell_stop_step"] = int(st.stats.get("sell_stop_step", 0)) + 1
    return sold



def run_chronological_day(
    st,
    pending_chase,
    *,
    hooks,
    minute_bars,
    daily_bars,
    pool_days,
    day_i,
    day,
    ds,
    names,
    daily_quota,
    exdiv,
    calendar,
    slice_day,
    profit_base=None,
    pos_trail=0.0,
    audit_sink=None,
    tail_window_buy=False,
    tail_volume_unit="shares",
    exdiv_ref_fen=False,
    minute_stop_trigger="close",
    fill_config=None,
    held_fill_states=None,
    topk_exec="close",
    limit_walkdown=False,
):
    """Advance holdings and cash at (hm, open/close, existing stable order)."""
    if tail_window_buy:
        tail_volume_unit = resolve_tail_volume_unit(tail_volume_unit)
    # Import helpers at call time to preserve the historical public entry module.
    from backtest.research.csv_minute_backtest import (
        _buy_px,
        _chase_quotes,
        _open_quote_for,
        _previous_rows,
    )

    minute_open = bool(hooks.get("minute_open"))
    qlib_limit_pct = hooks.get("qlib_limit_pct")
    day_trade_start = len(st.trades)
    bind_opening = hooks.get("bind_opening_held")
    if callable(bind_opening):
        bind_opening(ds, list(st.positions))

    frames = {}

    if held_fill_states is None:
        held_fill_states = {}

    def frame_for(code):
        if code not in frames:
            frame = slice_day(code, ds) if code in minute_bars else None
            if frame is not None:
                valid = frame["hm"].between(AM_OPEN, AM_CLOSE) | frame["hm"].between(
                    PM_OPEN, PM_CLOSE
                )
                frame = frame.loc[valid].sort_values("hm", kind="stable")
                if frame.empty:
                    frame = None
            frames[code] = frame
        return frames[code]

    events = {}
    pending_open = []
    for code in list(st.positions):
        ddf = daily_bars.get(code)
        if ddf is None or day not in ddf.index:
            continue
        frame = frame_for(code)
        if frame is None:
            continue
        previous = _previous_rows(ddf, day)
        if previous.empty:
            continue
        # Preserve original day-start eligibility (including missing-bar behavior).
        apply_exdiv_economics(st, code, ds)
        kk = k_for(exdiv, code, ds)
        if kk is not None:
            rescale_s8_groups(st, code, kk)
            for pos in list(st.positions.get(code, [])):
                rescale_position(pos, kk)
                st.stats["exdiv_adjusted_lots"] = int(st.stats.get("exdiv_adjusted_lots", 0)) + 1
        prev_close, did_map = mapped_prev_close(exdiv, code, ds, float(previous.iloc[-1]["close"]), **({"fen_round": True} if exdiv_ref_fen else {}))
        if did_map:
            st.stats["exdiv_prev_close_mapped"] = (
                int(st.stats.get("exdiv_prev_close_mapped", 0)) + 1
            )
        limits = book_limit_prices(code, prev_close, names, qlib_limit_pct=qlib_limit_pct, as_of=ds)
        if limits is None:
            st.stats["skip_unknown_board"] += 1
            continue
        o, h, c = (frame[key].to_numpy(np.float64) for key in ("open", "high", "close"))
        hm = frame["hm"].to_numpy(np.int64)
        for pos in exit_positions(st, code, day_i, day=day):
            if pos.ride_with is not None:
                continue
            sellable = t1_sellable(calendar[pos.entry_idx].date(), day.date())
            if minute_open:
                opening = _open_quote_for(frame)
                if pos.pending_exit and sellable and opening is not None:
                    pending_open.append((code, pos, opening, limits))
                continue
            v9_plan = (evaluate_version9_exit(hooks, daily_bars[code], day, st.stats)
                       if "version9_exit" in hooks and day_i > pos.entry_idx else None)
            cursor = HeldMinuteCursor(
                o,
                h,
                c,
                l=frame["low"].to_numpy(np.float64) if minute_stop_trigger == "hl" or (fill_config and fill_config.trigger_basis == "bar_low") else None,
                fill_config=fill_config,
                fill_state=held_fill_states.setdefault(getattr(pos, "position_id", None) or id(pos), {}),
                minute_stop_trigger=minute_stop_trigger, take_profit_pct=st.stats.get("profit_target"),
                cost=pos.cost,
                peak=pos.peak,
                n_days=day_i - pos.entry_idx,
                can_sell=sellable,
                stop_pct=hooks["stop_pct"],
                version9_plan=v9_plan, version9_max_hold=bool(st.stats.get("max_hold")),
                profit_base=profit_base if profit_base is not None else 0.0,
                trail_ratio=0.0,
                pos_trail=pos_trail,
                limit_down=limits[1],
                hm=hm,
                peak_hm=int(pos.peak_hm),
                peak_gap_min=int(hooks["peak_gap_min"]),
                take_profit=hooks["take_profit"],
                sell_gate=hooks.get("sell_gate"),
                gate_code=code,
                gate_day=day,
                daily_closes_ending_yesterday=previous["close"].astype(float).tolist(),
                force_sell_hm=hooks.get("force_sell_hm"),
                reserve_limit_up=bool(hooks.get("reserve_limit_up")),
                defer_limit_up=bool(hooks.get("defer_limit_up")),
                limit_up=limits[0],
                reserved=bool(pos.reserved),
                close_clear=hooks.get("close_clear"),
            )
            for idx, at_hm in enumerate(hm):
                events.setdefault(int(at_hm), []).append((code, pos, cursor, idx, limits))

    def bucket_for(code, target, earliest):
        frame = frame_for(code)
        if frame is None:
            return None
        hit = frame.loc[frame["hm"] == target]
        if not hit.empty:
            return int(hit["hm"].iloc[0])
        eligible = frame.loc[frame["hm"].between(earliest, target)]
        return None if eligible.empty else int(eligible["hm"].iloc[-1])

    def chase_bucket(code):
        return bucket_for(code, CHASE_HM, AM_OPEN)

    def pool_bucket(code):
        return AM_OPEN if minute_open else bucket_for(code, BUY_HM, 14 * 60 + 30)

    def previous_and_frame(code):
        ddf = daily_bars.get(code)
        if ddf is None or day not in ddf.index:
            return None
        frame = frame_for(code)
        if frame is None:
            return None
        previous = _previous_rows(ddf, day)
        if previous.empty:
            return None
        return previous["close"].astype(float).tolist(), frame

    def chase_quotes(code):
        got = previous_and_frame(code)
        if got is None:
            return None
        closes, frame = got
        quotes = _chase_quotes(frame)
        return None if quotes is None else (*quotes, closes)

    def pool_quote(code):
        got = previous_and_frame(code)
        if got is None:
            return None
        closes, frame = got
        if minute_open:
            opening = _open_quote_for(frame)
            if opening is None:
                return None
            volume = float(opening["volume"])
            if not np.isfinite(volume) or volume <= 0:
                st.stats["skip_buy_volume"] += 1
                return None
            px = float(opening["open"])
        else:
            px = _buy_px(frame)
        if px is None or px <= 0 or (minute_open and not np.isfinite(px)):
            return None
        return px, closes

    topk_buys = None
    if topk_exec != "close" or limit_walkdown:
        from backtest.research.topk_minute_exec import TopkMinuteBuys

        topk_buys = TopkMinuteBuys(
            st, mode=topk_exec, hooks=hooks, previous_and_frame=previous_and_frame,
            limit_walkdown=limit_walkdown, close_quote_for=_buy_px,
            open_quote_for=_open_quote_for, day_i=day_i, day=day, ds=ds,
            names=names, daily_quota=daily_quota, exdiv=exdiv, exdiv_ref_fen=exdiv_ref_fen, audit_sink=audit_sink,
        )

    tail_codes = set()
    tail_orders = {}
    tail_ordered_pool = []
    tail_attempted = set()
    independent_policy = s8_policy(st)
    tail_settled_debits = 0.0  # Only restores 8.1's full-list allocation basis.

    def debit(notional):
        return notional + trade_commission(notional, st.buy_cost_rate, st.min_cost)

    def reject_tail(reason):
        key = "tail_skip_" + reason
        st.stats[key] = int(st.stats.get(key, 0)) + 1

    def start_tail_parents():
        """Freeze quantities at 14:30 open without reserving account cash."""
        raw = list(pool_days.get(ds, []))
        tail_ordered_pool.extend(apply_capital_ration(
            raw, ration=hooks.get("ration", "file_order"),
            ration_seed=hooks.get("ration_seed", 0), ds=ds,
        ))
        if not raw:
            return
        sizing = hooks.get("sizing", "daily_quota")
        frac = hooks.get("cash_deploy_frac")
        per = (float(hooks.get("name_budget", 1_000_000.0)) if sizing == "per_name"
               else min(daily_quota, st.cash) * (1.0 if frac is None else float(frac)) / len(raw))
        for code in dict.fromkeys(tail_ordered_pool):
            # Independent books treat every later signal as a fresh first buy.
            # All such slots are consumed here, even when no parent can be built.
            if independent_policy is not None:
                tail_codes.add(code)
                if f"{code}@{ds}" in independent_policy["groups"]:
                    continue
            elif code in st.positions:
                continue  # 8.1 keeps its original 14:55 pool-add decision.
            else:
                tail_codes.add(code)
            allow_new = hooks.get("allow_new_name")
            if callable(allow_new) and not allow_new(day):
                st.stats["skip_index_gate"] += 1
                continue
            budget = per
            if sizing == "per_name" and callable(hooks.get("name_lot_budget")):
                budget = float(hooks["name_lot_budget"](per, []))
            got = previous_and_frame(code)
            if got is None:
                st.stats["skip_no_bar"] += 1
                continue
            closes, frame = got
            opening = frame.loc[frame["hm"] == TAIL_START]
            if len(opening) != 1 or bool(opening.iloc[0].get("_tail_duplicate", False)):
                st.stats["skip_no_bar"] += 1
                continue
            px = float(opening.iloc[0]["open"])
            if not np.isfinite(px) or px <= 0:
                st.stats["skip_no_bar"] += 1
                continue
            prev_close, did_map = mapped_prev_close(exdiv, code, ds, float(closes[-1]), **({"fen_round": True} if exdiv_ref_fen else {}))
            if did_map:
                st.stats["exdiv_prev_close_mapped"] = int(st.stats.get("exdiv_prev_close_mapped", 0)) + 1
            limits = book_limit_prices(code, prev_close, names, qlib_limit_pct=qlib_limit_pct, as_of=ds)
            if limits is None:
                st.stats["skip_unknown_board"] += 1
                continue
            buy_gate = hooks.get("buy_gate")
            if callable(buy_gate) and not buy_gate(code, px, day, closes):
                st.stats["skip_buy_gate"] += 1
                continue
            parent = TailParent.from_budget(budget, px)
            if independent_policy is not None:
                needed = parent.opening_debit(px, debit)
                if needed > st.cash:
                    raise InsufficientCashError(
                        date=ds, code=code, needed=needed, available=st.cash,
                    )
            tail_orders[code] = [parent, None, limits]

    def fill_tail_slice(at_hm, only_code=None):
        nonlocal tail_settled_debits
        for code, order in tail_orders.items():
            if only_code is not None and code != only_code:
                continue
            if (code, at_hm) in tail_attempted:
                continue
            tail_attempted.add((code, at_hm))
            parent, merge_lot, limits = order
            frame = frame_for(code)
            rows = frame.loc[frame["hm"] == at_hm]
            if len(rows) != 1 or bool(rows.iloc[0].get("_tail_duplicate", False)):
                reject_tail("quote")
                continue
            quote = tail_quote(rows.iloc[0], at_hm, tail_volume_unit)
            if quote is None:
                reject_tail("quote")
                continue
            if skip_buy_at_limit(quote.price, limits):
                reject_tail("limit_up")
                continue
            if (hooks.get("forbid_all_trade_at_limit", False)
                    and hit_limit_down(quote.price, limits[1])):
                reject_tail("limit_down")
                continue
            shares = (parent.requested_shares(quote) if independent_policy is not None
                      else parent.allocation(quote, st.cash, debit))
            if shares <= 0:
                continue
            quota_used = st.daily_quota_used
            if execute_buy(
                st, code, quote.price, shares * quote.price, day_i, day,
                reason="pool:tail_window", bucket_id=at_hm,
                shares_override=shares, merge_lot=merge_lot, hm=at_hm,
                **({"position_id": f"{code}@{ds}", "entry_signal_date": ds}
                   if independent_policy is not None else {}),
            ):
                order[1] = st.positions[code][-1] if merge_lot is None else merge_lot
                parent.book(int(st.trades[-1]["shares"]), quote.price)
                if hooks.get("sizing", "daily_quota") == "daily_quota":
                    tail_settled_debits += st.trades[-1]["notional"] + st.trades[-1]["commission"]
            if hooks.get("sizing") == "per_name":
                st.daily_quota_used = quota_used

    def pool_and_step():
        skips = int(st.stats.get("skip_volume_unavailable", 0)) + int(
            st.stats.get("skip_volume_cap", 0)
        )
        common = {
            "day_i": day_i,
            "day": day,
            "ds": ds,
            "names": names,
            "buy_quote_for": pool_quote,
            "volume_bucket_for": pool_bucket if st.volume_cap is not None else None,
            "sizing": hooks.get("sizing", "daily_quota"),
            "name_budget": hooks.get("name_budget", 1_000_000.0),
            "exdiv": exdiv,
            "exdiv_ref_fen": exdiv_ref_fen,
            "qlib_limit_pct": qlib_limit_pct,
            "buy_gate": hooks.get("buy_gate"),
            "forbid_all_trade_at_limit": bool(hooks.get("forbid_all_trade_at_limit", False)),
            "name_lot_budget": hooks.get("name_lot_budget"),
        }
        planned_for_day = hooks.get("planned_for_day")
        ration = hooks.get("ration", "file_order")
        handle_planned_code = None
        if tail_window_buy:
            def remaining_pool(_ds, _held_codes):
                return list(tail_ordered_pool)

            def handle_tail_code(code):
                if code in tail_codes:
                    fill_tail_slice(BUY_HM, only_code=code)
                    return True
                # A name cleared after parent creation cannot open a late parent.
                return code not in st.positions

            # Keep the original full-list denominator and precomputed ration.
            remaining_pool.slot_count = len(tail_ordered_pool)
            planned_for_day, ration = remaining_pool, "file_order"
            handle_planned_code = handle_tail_code
        run_pool_buys_day(
            st,
            pending_chase,
            **common,
            pool_days=pool_days,
            daily_quota=daily_quota,
            allow_add=bool(hooks["allow_add"]),
            volume_at=AM_OPEN - 1 if minute_open else None,
            sold_today={t["code"] for t in st.trades[day_trade_start:] if t["side"] == "SELL"}
            if hooks.get("skip_sold_today")
            else None,
            ration=ration,
            ration_seed=hooks.get("ration_seed", 0),
            planned_for_day=planned_for_day,
            cash_deploy_frac=hooks.get("cash_deploy_frac"),
            limit_up_chase=bool(hooks.get("limit_up_chase", True)),
            allow_new_name=hooks.get("allow_new_name"),
            add_gate=hooks.get("add_gate"),
            index_blocks_add=hooks.get("index_blocks_add", True),
            handle_planned_code=handle_planned_code,
            # Restore the pool's unsliced cash basis; today's settled sells are
            # included, while new parent budgets stay frozen at 14:30.
            allocation_cash=(st.cash + tail_settled_debits
                             if tail_window_buy and hooks.get("sizing", "daily_quota") == "daily_quota"
                             else None),
        )
        if minute_open:
            st.stats["skip_buy_volume"] += (
                int(st.stats.get("skip_volume_unavailable", 0))
                + int(st.stats.get("skip_volume_cap", 0))
                - skips
            )
        run_step_adds_day(st, **common, step_add=hooks.get("step_add"))

    def sell_pending_open():
        for code, pos, opening, limits in pending_open:
            px, volume = float(opening["open"]), float(opening["volume"])
            if not np.isfinite(px) or px <= 0:
                continue
            if not np.isfinite(volume) or volume <= 0:
                st.stats["defer_sell_volume"] += 1
                continue
            if defer_sell_at_limit(px, limits):
                st.stats["defer_sell_limit_down"] += 1
                continue
            before = len(st.trades)
            with audit_scope(audit_sink, decision_hm=AM_OPEN, quote_hm=AM_OPEN, phase="open"):
                _sell(
                    st,
                    code,
                    pos,
                    px,
                    day,
                    pos.pending_exit,
                    bucket_id=AM_OPEN,
                    at=AM_OPEN - 1,
                    day_i=day_i,
                    hm=AM_OPEN,
                    price_rule="minute_pending_next_open",
                )
            if any(
                t["side"] == "SKIP" and t["reason"].startswith("skip_volume")
                for t in st.trades[before:]
            ):
                st.stats["defer_sell_volume"] += 1

    clocks = set(events) | {CHASE_HM, AM_OPEN if minute_open else BUY_HM}
    if topk_buys is not None:
        clocks.update(topk_buys.clocks)
    if tail_window_buy:
        clocks.update(TAIL_MINUTES)
    for at_hm in sorted(clocks):
        for phase in ("open", "close"):
            for code, pos, cursor, idx, limits in events.get(at_hm, []):
                if isinstance(pos, IndependentExitPosition):
                    advance_independent_exit(
                        st, code, pos, cursor, idx, phase, limits,
                        day=day, day_i=day_i, audit_sink=audit_sink,
                    )
                    continue
                if not position_is_open(st, pos):
                    continue
                event = cursor.advance(idx, phase)
                pos.peak, pos.peak_hm = cursor.peak, cursor.peak_hm
                pos.reserved = cursor.current_reserved
                if event is None:
                    continue
                _, px, reason = event
                if limits[1] > 0 and (
                    defer_sell_at_limit(float(cursor.o[idx]), limits)
                    or defer_sell_at_limit(px, limits)
                ):
                    st.stats["defer_sell_limit_down"] += 1
                    continue
                volume_kwargs = {}
                if st.volume_cap is not None:
                    volume_kwargs = {
                        "bucket_id": at_hm,
                        "day_i": day_i,
                        "at": at_hm - 1 if is_open_fill(reason) else at_hm,
                    }
                price_rule = {
                    "stop_loss:gap_open": "minute_gap_open",
                    "stop_loss:touch": "minute_stop_price" if cursor.minute_stop_trigger == "hl" else "minute_trigger_bar_close",
                }.get(reason, "")
                if reason.endswith(":next_open"):
                    price_rule = "minute_pending_next_open"
                with audit_scope(audit_sink, decision_hm=at_hm, quote_hm=at_hm, phase=phase):
                    _sell(
                        st,
                        code,
                        pos,
                        px,
                        day,
                        reason,
                        **volume_kwargs,
                        hm=at_hm if price_rule else None,
                        price_rule=price_rule,
                    )
            if topk_buys is not None and phase == ("close" if topk_exec == "close" else "open"):
                topk_buys.advance(at_hm)
            if tail_window_buy and at_hm == TAIL_START and phase == "open":
                with audit_scope(audit_sink, decision_hm=TAIL_START, phase="open", quote_hm=TAIL_START):
                    start_tail_parents()
            if (tail_window_buy and at_hm in TAIL_MINUTES and at_hm != BUY_HM
                    and phase == "close"):
                with audit_scope(audit_sink, decision_hm=at_hm, phase="close", quote_hm=at_hm):
                    fill_tail_slice(at_hm)
            if minute_open and at_hm == AM_OPEN and phase == "open":
                sell_pending_open()
                with audit_scope(
                    audit_sink, decision_hm=AM_OPEN, phase="open", quote_for=pool_bucket
                ):
                    pool_and_step()
            if at_hm == CHASE_HM and phase == "close":
                with audit_scope(
                    audit_sink, decision_hm=CHASE_HM, phase="close", quote_for=chase_bucket
                ):
                    run_chase_due_day(
                        st,
                        pending_chase,
                        day_i=day_i,
                        day=day,
                        ds=ds,
                        names=names,
                        allow_add=bool(hooks["allow_add"]),
                        buy_gate=hooks.get("buy_gate"),
                        quotes_for=chase_quotes,
                        volume_bucket_for=chase_bucket if st.volume_cap is not None else None,
                        exdiv=exdiv, exdiv_ref_fen=exdiv_ref_fen,
                        qlib_limit_pct=qlib_limit_pct,
                        allow_new_name=hooks.get("allow_new_name"),
                        add_gate=hooks.get("add_gate"),
                        index_blocks_add=hooks.get("index_blocks_add", True),
                    )
            if topk_buys is None and not minute_open and at_hm == BUY_HM and phase == "close":
                with audit_scope(
                    audit_sink, decision_hm=BUY_HM, phase="close", quote_for=pool_bucket
                ):
                    pool_and_step()
