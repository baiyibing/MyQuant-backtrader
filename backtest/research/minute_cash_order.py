"""Opt-in chronological minute scheduling; the legacy scanner stays untouched.

The cursor preserves the research scanner's high-before-gap-open approximation.
Only settlement is split into open and close; this is not an intrabar tick model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from backtest.research.ashare_bars import AM_CLOSE, AM_OPEN, PM_CLOSE, PM_OPEN
from backtest.research.ashare_session import defer_sell_at_limit, t1_sellable
from backtest.research.csv_common import book_limit_prices
from backtest.research.csv_ledger import (
    CHASE_HM,
    PEAK_GAP_MIN,
    _sell,
    apply_exdiv_economics,
    hit_limit_down,
    hit_limit_up,
    peak_gap_blocks,
    rescale_position,
    rescale_s8_groups,
)
from backtest.research.csv_simulate_loop import (
    run_chase_due_day,
    run_pool_buys_day,
    run_step_adds_day,
)
from backtest.research.exdiv_map import k_for, mapped_prev_close
from backtest.research.minute_audit import audit_scope
from backtest.research.strategy3_rules import reserve_step_minute
from backtest.research.strategy6_rules import trail_hits

BUY_HM = 14 * 60 + 55
CLOSE_CLEAR_HM = 15 * 60


@dataclass
class HeldMinuteCursor:
    """One lot's resumable equivalent of ``scan_held_day_python``.

    For each hm, call every row's open then every row's close in row order.
    A returned candidate ends this lot's scan, even if the outer limit/capacity
    gate rejects or partially fills.
    """

    o: object
    h: object
    c: object
    cost: float
    peak: float
    n_days: int
    can_sell: bool
    stop_pct: float | None
    profit_base: float
    trail_ratio: float
    pos_trail: float = 0.0
    limit_down: float = 0.0
    hm: object = None
    peak_hm: int = -1
    peak_gap_min: int = PEAK_GAP_MIN
    take_profit: object = None
    sell_gate: object = None
    gate_code: object = None
    gate_day: object = None
    daily_closes_ending_yesterday: object = None
    force_sell_hm: int | None = None
    reserve_limit_up: bool = False
    defer_limit_up: bool = False
    limit_up: float = 0.0
    reserved: bool = False
    reserve_state: dict | None = None
    exit_plan: object = None
    exit_state: dict | None = None
    close_clear: object = None
    current_reserved: bool = field(init=False)
    lu_today: bool = field(default=False, init=False)
    saw_close_hm: bool = field(default=False, init=False)
    first_exit_attempted: bool = field(default=False, init=False)
    is_true_day_last: bool = field(default=False, init=False)
    _open_state: dict[int, tuple[bool, float, int]] = field(default_factory=dict, init=False)

    def __post_init__(self):
        self.peak = float(self.peak)
        self.peak_hm = int(self.peak_hm)
        self.current_reserved = bool(self.reserved)

    def _exit(self, idx, px, reason):
        self.first_exit_attempted = True
        return idx, float(px), reason

    def advance(self, idx: int, phase: str):
        """Observe one phase and return ``(idx, price, reason)`` or None."""
        if phase not in ("open", "close"):
            raise ValueError(f"unsupported minute phase: {phase}")
        self.is_true_day_last = idx == len(self.c) - 1
        if self.first_exit_attempted or not self.can_sell or self.n_days < 1:
            return None
        cur_hm = int(self.hm[idx]) if self.hm is not None else idx
        stop_enabled = isinstance(self.stop_pct, float) and 0 < self.stop_pct < 1
        px_open, px_close = float(self.o[idx]), float(self.c[idx])
        if phase == "open":
            # Keep the original scanner's OHLC ordering, including rejected fills.
            hi = float(self.h[idx])
            if hi > self.peak:
                self.peak, self.peak_hm = hi, cur_hm
            if cur_hm == CLOSE_CLEAR_HM:
                self.saw_close_hm = True
            skip_bar = self.limit_down > 0 and hit_limit_down(px_open, self.limit_down)
            self._open_state[idx] = skip_bar, self.peak, self.peak_hm
            if not skip_bar and stop_enabled and px_open <= self.cost * (1.0 - self.stop_pct):
                return self._exit(idx, px_open, "stop_loss:gap_open")
            return None
        # All opens in this hm have already run. Each close uses only its own
        # open's skip flag and peak, as in the row-wise scanner; later rows must
        # not change an earlier row's close predicate or exit peak.
        observed_peak = self.peak, self.peak_hm
        skip_bar, self.peak, self.peak_hm = self._open_state.pop(idx)
        if not skip_bar:
            event = self._close(idx, cur_hm, px_close, stop_enabled)
            if event is not None:
                return event
        # The legacy fallback follows the full loop, even if its last row used
        # continue (limit-open, defer_limit_up or reserve). Never run on a pause.
        if (
            self.close_clear is not None
            and self.is_true_day_last
            and not self.saw_close_hm
            and not (self.limit_down > 0 and hit_limit_down(px_close, self.limit_down))
        ):
            reason = self.close_clear(self.cost, self.peak, self.n_days)
            if reason:
                return self._exit(idx, px_close, reason)
        self.peak, self.peak_hm = observed_peak
        return None

    def _close(self, idx, cur_hm, px_close, stop_enabled):
        ret = px_close / self.cost - 1.0
        if stop_enabled and ret <= -self.stop_pct:
            return self._exit(idx, px_close, "stop_loss:touch")
        if self.defer_limit_up and self.limit_up > 0 and hit_limit_up(px_close, self.limit_up):
            self.lu_today = True
        if self.defer_limit_up and self.lu_today:
            return None
        if self.reserve_limit_up:
            is_limit_up = self.limit_up > 0 and hit_limit_up(px_close, self.limit_up)
            self.current_reserved, reason = reserve_step_minute(
                reserved=self.current_reserved,
                hm=cur_hm,
                is_limit_up=is_limit_up,
            )
            if self.reserve_state is not None:
                self.reserve_state["reserved"] = self.current_reserved
            if reason:
                return self._exit(idx, px_close, reason)
            if self.current_reserved and is_limit_up:
                return None
        blocked = self.peak_hm >= 0 and peak_gap_blocks(cur_hm - self.peak_hm, self.peak_gap_min)
        if not blocked:
            if callable(self.exit_plan):
                plan = self.exit_plan(
                    self.gate_code,
                    px_close,
                    self.gate_day,
                    self.daily_closes_ending_yesterday or [],
                )
                if plan is not None:
                    reason, shares = plan
                    if self.exit_state is None:
                        raise ValueError("partial exit_plan requires exit_state out-param")
                    self.exit_state["shares"] = shares
                    return self._exit(idx, px_close, reason)
            elif callable(self.sell_gate):
                reason = self.sell_gate(
                    self.gate_code,
                    px_close,
                    self.gate_day,
                    self.daily_closes_ending_yesterday or [],
                )
                if reason:
                    return self._exit(idx, px_close, reason)
            elif self.take_profit is not None:
                reason = self.take_profit(px_close, self.cost, self.peak, self.n_days)
                if reason:
                    return self._exit(idx, px_close, reason)
            elif trail_hits(px_close, self.cost, self.peak, self.profit_base, self.trail_ratio):
                return self._exit(idx, px_close, f"trail:T+{max(1, self.n_days)}")
        if self.force_sell_hm is not None and cur_hm >= int(self.force_sell_hm):
            if self.limit_down > 0 and hit_limit_down(px_close, self.limit_down):
                return None
            return self._exit(idx, px_close, "force_sell:time")
        if (
            self.close_clear is not None
            and cur_hm == CLOSE_CLEAR_HM
            and not (self.limit_down > 0 and hit_limit_down(px_close, self.limit_down))
        ):
            reason = self.close_clear(self.cost, self.peak, self.n_days)
            if reason:
                return self._exit(idx, px_close, reason)
        return None


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
):
    """Advance holdings and cash at (hm, open/close, existing stable order)."""
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
        prev_close, did_map = mapped_prev_close(exdiv, code, ds, float(previous.iloc[-1]["close"]))
        if did_map:
            st.stats["exdiv_prev_close_mapped"] = (
                int(st.stats.get("exdiv_prev_close_mapped", 0)) + 1
            )
        limits = book_limit_prices(code, prev_close, names, qlib_limit_pct=qlib_limit_pct)
        if limits is None:
            st.stats["skip_unknown_board"] += 1
            continue
        o, h, c = (frame[key].to_numpy(np.float64) for key in ("open", "high", "close"))
        hm = frame["hm"].to_numpy(np.int64)
        for pos in list(st.positions.get(code, [])):
            if pos.ride_with is not None:
                continue
            sellable = t1_sellable(calendar[pos.entry_idx].date(), day.date())
            if minute_open:
                opening = _open_quote_for(frame)
                if pos.pending_exit and sellable and opening is not None:
                    pending_open.append((code, pos, opening, limits))
                continue
            cursor = HeldMinuteCursor(
                o,
                h,
                c,
                cost=pos.cost,
                peak=pos.peak,
                n_days=day_i - pos.entry_idx,
                can_sell=sellable,
                stop_pct=hooks["stop_pct"],
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
            "qlib_limit_pct": qlib_limit_pct,
            "buy_gate": hooks.get("buy_gate"),
            "forbid_all_trade_at_limit": bool(hooks.get("forbid_all_trade_at_limit", False)),
            "name_lot_budget": hooks.get("name_lot_budget"),
        }
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
            ration=hooks.get("ration", "file_order"),
            ration_seed=hooks.get("ration_seed", 0),
            planned_for_day=hooks.get("planned_for_day"),
            cash_deploy_frac=hooks.get("cash_deploy_frac"),
            limit_up_chase=bool(hooks.get("limit_up_chase", True)),
            allow_new_name=hooks.get("allow_new_name"),
            add_gate=hooks.get("add_gate"),
            index_blocks_add=hooks.get("index_blocks_add", True),
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
    for at_hm in sorted(clocks):
        for phase in ("open", "close"):
            for code, pos, cursor, idx, limits in events.get(at_hm, []):
                if not any(lot is pos for lot in st.positions.get(code, [])):
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
                        "at": at_hm - 1 if reason == "stop_loss:gap_open" else at_hm,
                    }
                price_rule = {
                    "stop_loss:gap_open": "minute_gap_open",
                    "stop_loss:touch": "minute_trigger_bar_close",
                }.get(reason, "")
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
                        exdiv=exdiv,
                        qlib_limit_pct=qlib_limit_pct,
                        allow_new_name=hooks.get("allow_new_name"),
                        add_gate=hooks.get("add_gate"),
                        index_blocks_add=hooks.get("index_blocks_add", True),
                    )
            if not minute_open and at_hm == BUY_HM and phase == "close":
                with audit_scope(
                    audit_sink, decision_hm=BUY_HM, phase="close", quote_for=pool_bucket
                ):
                    pool_and_step()
