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
open buys. The native v7 schedule preserves its separate phase sequence and post-buy
timer here; book callbacks only decide individual events.

The cursor preserves the research scanner's high-before-gap-open approximation.
Gap stops settle in the open phase; hl touches and fixed-target checks run in
the close phase, even when a gap-target fill quotes open. These are OHLC phase
conventions, not tick-level ordering. See
``docs/backtest/s2c-x02-cash-order-boundary-2026-09-28.md`` and
``docs/backtest/minute-fill-policy-ssot.md`` (X2 / section 4) for the boundary
and S2-B hl cross-reference. This documentation does not change scheduling.
"""

from __future__ import annotations

from backtest.research.lot_rounding import (
    buy_quantity_increment,
    buy_quantity_minimum,
    floor_board_lots,
    scale_out_board_lots,
)

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Sequence

from backtest.research.minute_engine_policies import MinuteRowToken

from backtest.research.sell_pending_observability import pending_callback, record_sell_pending, record_limit, side_path

import numpy as np

from backtest.research.ashare_bars import AM_CLOSE, AM_OPEN, PM_CLOSE, PM_OPEN
from backtest.research.ashare_session import defer_sell_open_or_fill, defer_sell_at_limit, skip_buy_at_limit, t1_sellable
from backtest.research.csv_common import book_limit_prices
from backtest.research.csv_ledger import (
    CHASE_HM,
    IndependentExitPosition,
    account_sell_quantity,
    active_buy_quantity_rule,
    arm_cont_stop_rebuy,
    check_buy_cash,
    _sell,
    apply_exdiv_economics,
    exit_positions,
    fee_order_id,
    held_fill_key,
    execute_buy,
    hit_limit_down,
    peak_gap_blocks,
    position_is_open,
    rescale_position,
    rescale_s8_groups,
    s8_policy,
    trade_commission,
    uses_fee_aware_affordability,
    uses_shrink_on_short_cash,
)
from backtest.research.minute_audit import record_rejection
from backtest.research.csv_simulate_loop import (
    apply_capital_ration,
    run_chase_due_day,
    run_pool_buys_day,
    run_step_adds_day,
)
from backtest.research.exdiv_map import k_for, mapped_prev_close
from backtest.research.minute_held_scan_core import (
    HeldMinuteCursor,
    sell_allowed,
    stop_touch,
    stop_trigger,
)
from backtest.research.fill_config import FillConfig, is_open_fill
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
        defer_sell_open_or_fill(px if pending else float(cursor.o[idx]), px, limits)
    ):
        st.stats["defer_sell_limit_down"] += 1
        record_limit(st, code, pos.shares, day, at_hm, px if pending else float(cursor.o[idx]), limits, key=held_fill_key(pos))
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


def _side_price(config, px, *, line=None, low=None):
    if config is None or config == FillConfig() or config.fill_timing == "next_bar_open":
        return px
    at = config.fill_at
    if at == "line":
        if line is None:
            raise ValueError("fill_at=line requires an explicit stop/target line")
        return line
    if at == "bar_low":
        if line is None:
            raise ValueError("look-ahead: bar_low is not a causal fill for a last-print decision")
        return float(low)
    return px if at == "bar_last" else float(at)


def _side_pending(st, pos):
    return getattr(st, "held_fill_states", {}).get(held_fill_key(pos), {}).get("side_pending", [])


def _side_queued(st, pos):
    return any(order[0] is pos or isinstance(order[0], IndependentExitPosition)
               for order in _side_pending(st, pos))


def _side_sell(st, code, pos, px, day, reason, *, fill_config=None, **kwargs):
    if fill_config is not None and fill_config.fill_timing == "next_bar_open":
        state = st.held_fill_states.setdefault(held_fill_key(pos), {})
        order = (pos, reason, kwargs.get("wanted_shares"))
        if kwargs.get("order_id") is not None:
            order = (*order, kwargs["order_id"])
        state.setdefault("side_pending", []).append(order)
        path = side_path(reason)
        record_sell_pending(st, ds=day, hm=kwargs.get("hm"), code=code,
                            shares=kwargs.get("wanted_shares", pos.shares), path=path,
                            reason="next_bar_open_queued", key=(held_fill_key(pos), path, id(pos)))
        return 0
    return _sell(st, code, pos, px, day, reason, **kwargs)


def fill_side_pending(st, code, pos, px, day, day_i, limits, *, hm):
    """Consume side orders at eligible opens; the ledger owns lifetime cleanup."""
    orders = _side_pending(st, pos)
    counted_scale = False
    for order in list(orders):
        target, reason, wanted = order[:3]
        order_id = order[3] if len(order) > 3 else None
        if not position_is_open(st, target):
            orders.remove(order)
            continue
        if not np.isfinite(px) or px <= 0 or target.entry_idx >= day_i:
            continue
        if defer_sell_at_limit(px, limits):
            st.stats["defer_sell_limit_down"] += 1
            record_limit(st, code, wanted if wanted is not None else target.shares, day, hm, px, limits,
                         path=side_path(reason), key=(held_fill_key(pos), side_path(reason), id(target)))
            continue
        filled = _sell(st, code, target, px, day, reason + ":next_open",
                       day_i=day_i, hm=hm, price_rule="minute_pending_next_open",
                       **({"wanted_shares": wanted} if wanted is not None else {}),
                       **({"order_id": order_id} if order_id is not None else {}))
        if filled:
            if order in orders:
                orders.remove(order)
            if reason.startswith("stop_loss:step") and getattr(target, "shares", 1) <= 0:
                arm_cont_stop_rebuy(st, getattr(pos, "group", None), target.lot_id)
            stat = ("sell_stop_step" if reason.startswith("stop_loss:step") else
                    "sell_scale_out" if reason.startswith("scale_out:") else "sell_peak_dd_clear")
            if stat != "sell_scale_out" or not counted_scale:
                st.stats[stat] = int(st.stats.get(stat, 0)) + 1
            counted_scale = counted_scale or stat == "sell_scale_out"
            if reason == "peak_dd_clear":
                target.group.peak_dd_start = None


def _hit_limit_up_safe(px: float, limits) -> bool:
    """6.x 卖出 helper 共用：涨停也 defer（不影响主引擎梯子/止损路径）。"""
    try:
        from backtest.research.ashare_session import hit_limit_up
        return limits is not None and hit_limit_up(px, limits[0])
    except Exception:
        return False


def peak_dd_clear_exits(st, code, pos, px, day, day_i, limits, *,
                         peak_dd_exit=0.15, peak_dd_sessions=15, hm=None, fill_config=None, open_px=None):
    """6.14：从峰值回撤 >peak_dd_exit 且 peak_dd_sessions 个交易日内未收复 → 全组清仓。

    每日一次评估（close 相位、首次触线那分钟记录起始日）；峰值回撤重置为
    None（px ≥ peak 时清零计数）；与梯子/减仓并行，组级清仓走 _sell_s8_group。
    """
    if _side_pending(st, pos) or not peak_dd_exit or px <= 0 or not position_is_open(st, pos):
        return 0
    peak = float(pos.peak)
    if peak <= 0:
        return 0
    dd = (peak - float(px)) / peak
    if dd <= 0:
        pos.group.peak_dd_start = None
        return 0
    if dd < float(peak_dd_exit):
        return 0
    if pos.group.peak_dd_start is None:
        pos.group.peak_dd_start = day_i
        return 0
    if day_i - pos.group.peak_dd_start < int(peak_dd_sessions):
        return 0
    px = _side_price(fill_config, px)
    if (fill_config is None or fill_config.fill_timing != "next_bar_open") and (defer_sell_open_or_fill(px if open_px is None else open_px, px, limits) or _hit_limit_up_safe(px, limits)):
        st.stats["defer_sell_limit_down"] += 1
        record_limit(st, code, pos.shares, day, hm, px if open_px is None else open_px, limits, path="peak_dd_clear")
        return 0
    # 全组清仓：走组级卖出（复用 _sell 的 IndependentExitPosition 路径）
    filled = _side_sell(
        st, code, pos, px, day, "peak_dd_clear", day_i=day_i,
        hm=hm, price_rule="minute_trigger_bar_close", fill_config=fill_config,
    )
    if filled:
        st.stats["sell_peak_dd_clear"] = int(st.stats.get("sell_peak_dd_clear", 0)) + 1
        pos.group.peak_dd_start = None
    return 1 if filled else 0


def scale_out_exits(st, code, pos, px, day, day_i, limits, *, scale_step, scale_frac, scale_anchor="first_lot", hm=None, fill_config=None, open_px=None):
    """6.13：相对减仓锚价每满 scale_step 涨幅，卖出当时剩余持仓的 scale_frac。

    默认锚为首仓 A0（group.anchor_cost / first_lot.cost）。
    scale_anchor=\"weighted\"（6.51）改为组内剩余 lot 的股数加权均价。
    逐分钟 close 相位调用；每档一次（组计数器）；legacy 整百股向下、
    FIFO 切 lot。industry 若该档会留下不足一手的组级余额，则同一订单卖完
    该余额；规则只在组总量上应用，不能逐 lot 制造或保留零股。
    lot 级 T+1 由 _sell(wanted_shares) 保证；跌停顺延；组已同分钟离场则不触发。
    均价上移后不重置 scale_steps；allowed 低于已走档则本分钟不减仓。
    """
    if _side_pending(st, pos) or not scale_step or px <= 0 or not position_is_open(st, pos):
        return 0
    lots = [lot for lot in st.positions.get(code, [])
            if getattr(lot, "position_id", None) == pos.position_id]
    shares_now = sum(lot.shares for lot in lots)
    if str(scale_anchor) == "weighted":
        if shares_now <= 0:
            return 0
        anchor_cost = (
            sum(float(lot.shares) * float(lot.cost) for lot in lots) / float(shares_now)
        )
    else:
        anchor_cost = float(getattr(pos.group, "anchor_cost", None) or pos.group.first_lot.cost)
    if anchor_cost <= 0 or float(px) < anchor_cost:
        return 0
    allowed = int((float(px) / anchor_cost - 1.0 + 1e-12) / float(scale_step))
    if allowed <= pos.group.scale_steps:
        return 0
    if shares_now <= 0:
        pos.group.scale_steps = allowed
        return 0
    rounded_target = scale_out_board_lots(shares_now, scale_frac)
    target = account_sell_quantity(st, code, shares_now, rounded_target)
    absorbs_odd_remainder = target > rounded_target
    px = _side_price(fill_config, px)
    sold = 0
    queued = 0
    order_id = fee_order_id(st) if target > 0 else None
    if target > 0:
        for lot in lots:
            if sold + queued >= target:
                break
            chunk = min(lot.shares, target - sold - queued)
            if not absorbs_odd_remainder:
                chunk = floor_board_lots(chunk)
            if chunk <= 0 or lot.entry_idx >= day_i:
                continue
            if (fill_config is None or fill_config.fill_timing != "next_bar_open") and (defer_sell_open_or_fill(px if open_px is None else open_px, px, limits) or _hit_limit_up_safe(px, limits)):
                st.stats["defer_sell_limit_down"] += 1
                record_limit(st, code, chunk, day, hm, px if open_px is None else open_px, limits, path="scale_out")
                return sold
            filled = _side_sell(
                st, code, lot, px, day, "scale_out:5pct", day_i=day_i,
                hm=hm, price_rule="minute_trigger_bar_close", fill_config=fill_config,
                wanted_shares=chunk,
                **({"order_id": order_id} if order_id is not None else {}),
            )
            sold += int(filled)
            if fill_config is not None and fill_config.fill_timing == "next_bar_open":
                queued += chunk
    pos.group.scale_steps = allowed
    if sold:
        st.stats["sell_scale_out"] = int(st.stats.get("sell_scale_out", 0)) + 1
    return sold


def step_stop_exits(st, code, pos, px, day, day_i, limits, *, step_stop_pct, hm=None, fill_config=None, low=None, open_px=None):
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
            or _side_queued(st, lot)
            or not getattr(lot, "is_step", False)
            or lot.entry_idx >= day_i
        ):
            continue
        line = float(lot.cost) * (1.0 - float(step_stop_pct))
        trigger_px = low if fill_config is not None and fill_config.trigger_basis == "bar_low" else px
        if float(trigger_px) > line:
            continue
        fill_px = _side_price(fill_config, px, line=line, low=low)
        if (fill_config is None or fill_config.fill_timing != "next_bar_open") and (defer_sell_open_or_fill(fill_px if open_px is None else open_px, fill_px, limits) or _hit_limit_up_safe(fill_px, limits)):
            st.stats["defer_sell_limit_down"] += 1
            record_limit(st, code, lot.shares, day, hm, fill_px if open_px is None else open_px, limits, path="step_stop")
            continue
        filled = _side_sell(
            st, code, lot, fill_px, day,
            f"stop_loss:step{round(float(step_stop_pct) * 100)}", day_i=day_i,
            hm=hm, price_rule="minute_trigger_bar_close", fill_config=fill_config,
        )
        if filled:
            sold += 1
            st.stats["sell_stop_step"] = int(st.stats.get("sell_stop_step", 0)) + 1
            if lot.shares <= 0:
                arm_cont_stop_rebuy(st, getattr(pos, "group", None), lot.lot_id)
    return sold


def _independent_skip_supported(cursor) -> bool:
    """Fail closed: unknown cursor features keep the full Python bar loop."""
    if getattr(cursor, "_custom_fill", False):
        return False
    if cursor.session_volume is not None:
        return False
    if cursor.reserve_limit_up or cursor.defer_limit_up:
        return False
    if cursor.version9_plan is not None:
        return False
    if callable(getattr(cursor, "exit_plan", None)):
        return False
    if callable(getattr(cursor, "sell_gate", None)):
        return False
    if callable(getattr(cursor, "phase_exit", None)):
        return False
    return True


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
    price_context=None,
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

    session_factory = hooks.get("minute_session")
    session = (session_factory(
        st, pending_chase, hooks=hooks, minute_bars=minute_bars,
        daily_bars=daily_bars, pool_days=pool_days, day_i=day_i, day=day,
        ds=ds, names=names, daily_quota=daily_quota, exdiv=exdiv,
        slice_day=slice_day, price_context=price_context,
        fill_config=fill_config, held_fill_states=held_fill_states,
    ) if callable(session_factory) else None)
    events = {}
    for code in ([] if session is not None else list(st.positions)):
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
            v9_plan = (evaluate_version9_exit(hooks, daily_bars[code], day, st.stats)
                       if "version9_exit" in hooks and day_i > pos.entry_idx else None)
            cursor = HeldMinuteCursor(
                o,
                h,
                c,
                l=frame["low"].to_numpy(np.float64) if minute_stop_trigger == "hl" or (fill_config and fill_config.trigger_basis == "bar_low") else None,
                session_exit_reason=pos.pending_exit,
                session_volume=frame["volume"].to_numpy(np.float64) if minute_open else None,
                session_stats=st.stats,
                fill_config=fill_config,
                fill_state=held_fill_states.setdefault(held_fill_key(pos), {}),
                pending_log=pending_callback(st, code, pos, day),
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
            quantity_rule = active_buy_quantity_rule(st, code)
            parent = TailParent.from_budget(
                budget,
                px,
                declaration_increment=buy_quantity_increment(quantity_rule),
                declaration_minimum=buy_quantity_minimum(quantity_rule),
            )
            fee_aware = uses_fee_aware_affordability(st)
            shrink_short_cash = uses_shrink_on_short_cash(st)
            if fee_aware:
                order_debit = (
                    lambda notional, code=code: st.account_fee_schedule.debit_buy(
                        notional, day, code
                    )
                )
            else:
                order_debit = debit
            if independent_policy is not None and not shrink_short_cash:
                needed = parent.opening_debit(px, order_debit)
                if not check_buy_cash(st, needed=needed, available=st.cash, date=ds, code=code):
                    st.stats["skip_cash"] = st.stats.get("skip_cash", 0) + 1
                    st.stats["skip_cash_notional"] = (
                        st.stats.get("skip_cash_notional", 0.0) + parent.target_shares * px
                    )
                    record_rejection(st, code, day, "skip_cash", px)
                    continue
            tail_orders[code] = [parent, None, limits, order_debit]

    def fill_tail_slice(at_hm, only_code=None):
        nonlocal tail_settled_debits
        for code, order in tail_orders.items():
            if only_code is not None and code != only_code:
                continue
            if (code, at_hm) in tail_attempted:
                continue
            tail_attempted.add((code, at_hm))
            parent, merge_lot, limits, order_debit = order
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
            fee_aware = uses_fee_aware_affordability(st)
            shrink_short_cash = uses_shrink_on_short_cash(st)
            shares = (
                parent.requested_shares(
                    quote, order_debit if fee_aware else None
                )
                if independent_policy is not None and not shrink_short_cash
                else parent.allocation(
                    quote,
                    st.cash,
                    order_debit,
                    budget_debit_fn=order_debit if fee_aware else None,
                )
            )
            if shares <= 0:
                continue
            remaining_budget = max(0.0, parent.budget - parent.spent)
            quota_used = st.daily_quota_used
            if execute_buy(
                st,
                code,
                quote.price,
                remaining_budget if fee_aware else shares * quote.price,
                day_i,
                day,
                reason="pool:tail_window", bucket_id=at_hm,
                shares_override=shares, merge_lot=merge_lot, hm=at_hm,
                **({"position_id": f"{code}@{ds}", "entry_signal_date": ds}
                   if independent_policy is not None else {}),
            ):
                order[1] = st.positions[code][-1] if merge_lot is None else merge_lot
                parent.book(
                    int(st.trades[-1]["shares"]),
                    quote.price,
                    order_debit if fee_aware else None,
                )
                if hooks.get("sizing", "daily_quota") == "daily_quota":
                    tail_settled_debits += (
                        st.trades[-1]["notional"]
                        + st.trades[-1]["commission"]
                        + st.trades[-1].get("transfer_fee", 0.0)
                    )
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
            st_on=hooks.get("st_on"),
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

    clocks = set(events) | {CHASE_HM, AM_OPEN if minute_open else BUY_HM}
    if topk_buys is not None:
        clocks.update(topk_buys.clocks)
    if tail_window_buy:
        clocks.update(TAIL_MINUTES)
    if session is not None:
        clocks = session.clocks
    for at_hm in sorted(clocks):
        for phase in ("open", "close"):
            if session is not None:
                if phase == "close" and callable(getattr(session, "before_close", None)):
                    session.before_close(at_hm)
                for code in list(st.positions):
                    session.advance_held(code, at_hm, phase)
                if phase == "close":
                    session.after_close(at_hm)
                continue
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
                    defer_sell_open_or_fill(float(cursor.o[idx]), px, limits)
                ):
                    st.stats["defer_sell_limit_down"] += 1
                    record_limit(st, code, pos.shares, day, at_hm, float(cursor.o[idx]), limits, key=held_fill_key(pos))
                    continue
                volume_kwargs = {}
                if st.volume_cap is not None:
                    volume_kwargs = {
                        "bucket_id": at_hm,
                        "day_i": day_i,
                        "at": at_hm - 1 if is_open_fill(reason) or (minute_open and fill_config.fill_timing == "next_bar_open") else at_hm,
                    }
                price_rule = {
                    "stop_loss:gap_open": "minute_gap_open",
                    "stop_loss:touch": "minute_stop_price" if cursor.minute_stop_trigger == "hl" else "minute_trigger_bar_close",
                }.get(reason, "")
                if minute_open:
                    price_rule = "minute_trigger_bar_close"
                if reason.endswith(":next_open") or (minute_open and fill_config.fill_timing == "next_bar_open"):
                    price_rule = "minute_pending_next_open"
                with audit_scope(audit_sink, decision_hm=at_hm, quote_hm=at_hm, phase=phase):
                    before = len(st.trades)
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
                if minute_open and any(t["side"] == "SKIP" and t["reason"].startswith("skip_volume") for t in st.trades[before:]):
                    st.stats["defer_sell_volume"] += 1
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


def run_symbol_major_day(state, day, calendar, symbols_today, ordered, pool_today,
                         closes, last_prices, cleared_today, *, exdiv=None, names=None,
                         names_by_day=None, blocked_new=False, fee=None, audit_sink=None,
                         session):
    """Main-owned v7 OFF traversal; book callbacks handle individual events."""
    from backtest.research.strategy7_engine import _event
    from backtest.research.minute_audit import audit_scope

    for symbol in ordered:
        records = symbols_today.get(symbol, [])
        if not records:
            if symbol in pool_today:
                _event(state, day, symbol, None, "skip", 0, None, "skip_no_1455")
            continue
        previous, limits, name = session.begin_symbol(
            state, symbol, day, closes, exdiv, names, names_by_day)
        first = True
        open_checked = False
        for row_index, row in enumerate(records):
            hm = int(row["hm"])
            with audit_scope(audit_sink, decision_hm=hm, phase="close"):
                open_px, close_px, high_px = session.observe_row(
                    state, symbol, row, last_prices)
                position = state.positions.get(symbol)
                if position is not None:
                    session.stop(
                        state, position, symbol, day, hm, first, open_px,
                        close_px, high_px, previous, limits, fee, audit_sink)
                    if symbol not in state.positions:
                        cleared_today.add(symbol)
                    position = state.positions.get(symbol)
                    session.add(
                        state, position, symbol, day, hm, close_px, previous, limits, fee)
                if (hm == 895 and symbol in pool_today and symbol not in state.positions
                        and symbol not in cleared_today):
                    open_checked = True
                    session.trial(
                        state, symbol, day, hm, close_px, blocked_new,
                        previous, name, fee)
                with audit_scope(audit_sink, decision_hm=hm, phase="timer"):
                    if row_index == len(records) - 1:
                        session.timer(
                            state, symbol, day, hm, close_px, calendar,
                            previous, limits, fee, cleared_today)
                first = False

        session.finish_symbol(
            state, symbol, day, symbol in pool_today, open_checked,
            records)


@dataclass
class _V7DayCursor:
    symbol: str
    tokens: list[MinuteRowToken]
    previous: float | None
    limits: tuple[float, float] | None
    open_checked: bool = False


def run_v7_chronological_day(
    state: Any, day: date, calendar: Sequence[date],
    symbols_today: Mapping[str, list[dict[str, Any]]], ordered: Sequence[str],
    pool: Sequence[str], closes: Mapping[str, Mapping[date, float]],
    last_prices: dict[str, float], cleared_today: set[str], *,
    exdiv: Mapping[str, Mapping[str, float]] | None,
    names: Mapping[str, str] | None,
    names_by_day: Mapping[str, Mapping[str, str]] | None,
    blocked_new: bool, fee: Any, audit_sink: Any,
    tail_window_buy: bool = False,
    tail_volume_unit: str | None = "shares",
    session,
) -> None:
    """Main-owned v7 clock phases; timers observe the completed buy phase.

    Quote and decision clocks coincide: v7 has no target-minute fallback or
    chase. Stable ties retain the legacy pool/held/input-symbol order. All daily
    reference/economic work snapshots only positions held before any new buy.
    Missing-bar entitlement behavior deliberately remains the legacy X-13 rule.
    """
    from backtest.research.strategy7_engine import _event
    from backtest.research.minute_audit import audit_scope
    from backtest.research.tail_window_buy import TAIL_MINUTES, TAIL_START, resolve_tail_volume_unit
    if tail_window_buy:
        tail_volume_unit = resolve_tail_volume_unit(tail_volume_unit)
    cursors: list[_V7DayCursor] = []
    tail_parents: dict[str, TailParent] = {}
    tail_attempted: set[tuple[str, int]] = set()
    by_hm: dict[int, list[tuple[_V7DayCursor, int, dict[str, Any]]]] = {}
    for symbol in ordered:
        source = symbols_today.get(symbol, [])
        tokens = session.chronological_tokens(symbol, source)
        if not tokens:
            if symbol in pool:
                _event(state, day, symbol, None, "skip", 0, None,
                       "skip_no_tail_start" if tail_window_buy else "skip_no_1455")
            continue
        previous, limits, name = session.begin_symbol(
            state, symbol, day, closes, exdiv, names, names_by_day)
        cursor = _V7DayCursor(symbol, tokens, previous, limits)
        cursors.append(cursor)
        for token in tokens:
            by_hm.setdefault(token.hm, []).append((cursor, token.ordinal, token.row))

    if tail_window_buy:
        for tail_hm in TAIL_MINUTES:
            by_hm.setdefault(tail_hm, [])
    for hm, rows in sorted(by_hm.items()):
        duplicate_tail_symbols: set[str] = set()
        if tail_window_buy and hm in TAIL_MINUTES:
            seen: set[str] = set()
            for cursor, _, row in rows:
                if cursor.symbol in seen or row.get("_tail_duplicate", False):
                    duplicate_tail_symbols.add(cursor.symbol)
                seen.add(cursor.symbol)
        # As in the original scanner, this bar's high is observed before its
        # gap-open stop. It never advances a different, later minute.
        for cursor, _, row in rows:
            session.chronological_observe(
                state, cursor.symbol, row, last_prices, cursor.symbol in tail_parents)

        # Independent stop sells precede close buys. Opening fills settle first;
        # the original first-row-only gap rule and completed-volume clock stay.
        stopped_rows: set[tuple[str, int]] = set()
        for phase in ("open", "close"):
            for cursor, index, row in rows:
                symbol = cursor.symbol
                if (symbol, index) in stopped_rows:
                    continue
                position = state.positions.get(symbol)
                if position is None:
                    continue
                session.chronological_stop(
                    state, cursor, index, row, phase, stopped_rows, day, hm, audit_sink, fee,
                    cleared_today,
                )

            # The opening quote fixes quantity before the completed 14:30 bar
            # exists; cash only constrains each later close-phase child fill.
            if tail_window_buy and hm == TAIL_START and phase == "open":
                for cursor, _, row in rows:
                    symbol = cursor.symbol
                    if (symbol not in pool or symbol in state.positions
                            or symbol in cleared_today or cursor.open_checked):
                        continue
                    session.chronological_parent(
                        state, cursor, row, day, hm, duplicate_tail_symbols, blocked_new,
                        tail_parents, audit_sink,
                    )

        if tail_window_buy and hm in TAIL_MINUTES:
            present = {cursor.symbol for cursor, _, _ in rows}
            for symbol in tail_parents:
                if symbol not in present:
                    with audit_scope(audit_sink, decision_hm=hm, phase="close"):
                        _event(state, day, symbol, hm, "skip", 0, None, "skip_tail_quote")
        for cursor, _, row in rows:
            session.chronological_buy(
                state, cursor, row, day, hm, audit_sink, tail_window_buy, tail_parents,
                tail_attempted, duplicate_tail_symbols, tail_volume_unit, fee, pool,
                cleared_today, blocked_new,
            )

        # The last-bar timer depends on last_add_date and stage AFTER all buys.
        # Its proceeds never retry a failed buy in this hm.
        for cursor, index, row in rows:
            if index != len(cursor.tokens) - 1:
                continue
            session.chronological_timer(
                state, cursor, row, day, hm, calendar, audit_sink, fee, cleared_today,
            )

    for cursor in cursors:
        symbol = cursor.symbol
        if tail_window_buy:
            if symbol in pool and symbol not in state.positions and not cursor.open_checked:
                _event(state, day, symbol, None, "skip", 0, None, "skip_no_tail_start")
            continue
        if (symbol in pool and symbol not in state.positions and not cursor.open_checked
                and not any(token.hm == 895 for token in cursor.tokens)):
            _event(state, day, symbol, None, "skip", 0, None, "skip_no_1455")
