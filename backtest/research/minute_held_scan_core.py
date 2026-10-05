"""Shared held-minute decision core and resumable scan state."""
from __future__ import annotations
from dataclasses import dataclass, field
from backtest.research.csv_ledger import PEAK_GAP_MIN, peak_gap_blocks, hit_limit_down, hit_limit_up
from backtest.research.ashare_session import LIMIT_EPS as _LIMIT_EPS
from backtest.research.minute_stop_trigger import blocked_bar, target_fill, validate_low
from backtest.research.strategy9_rules import plan_stop_price, plan_close_reason
from backtest.research.strategy3_rules import reserve_step_minute
from backtest.research.strategy6_rules import trail_hits
CLOSE_CLEAR_HM = 15 * 60

def sell_allowed(can_sell, n_days):
    return can_sell and n_days >= 1

def stop_touch(ret, stop_pct):
    return ret <= -stop_pct

def limit_down_blocks(px, limit_down):
    return limit_down > 0.0 and (px - _LIMIT_EPS) <= limit_down

def stop_trigger(cost, stop_pct):
    return cost * (1.0 - stop_pct)


def gap_stop(px_open, trigger):
    return px_open <= trigger


def force_due(cur_hm, force_sell_hm):
    return cur_hm >= int(force_sell_hm)


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
    l: object = None
    minute_stop_trigger: str = "close"
    take_profit_pct: float | None = None
    version9_plan: dict | None = None
    version9_max_hold: bool = False
    stop_range_ratio: float | None = None
    current_reserved: bool = field(init=False)
    lu_today: bool = field(default=False, init=False)
    saw_close_hm: bool = field(default=False, init=False)
    first_exit_attempted: bool = field(default=False, init=False)
    is_true_day_last: bool = field(default=False, init=False)
    _open_state: dict[int, tuple[bool, float, int]] = field(default_factory=dict, init=False)

    def __post_init__(self):
        validate_low(self.minute_stop_trigger, self.l, self.c)
        self.peak = float(self.peak)
        self.peak_hm = int(self.peak_hm)
        self.current_reserved = bool(self.reserved)
        if self.stop_range_ratio is not None:
            # Range stop replaces the percent stop for trigger and touch, as the
            # original scan_held_day_python did before the shared core existed.
            self.stop_pct = self.stop_range_ratio
        if self.version9_plan is not None:
            self.take_profit_pct = self.version9_plan["take_profit_pct"]
            self.take_profit = lambda px, cost, peak, n_days: plan_close_reason(
                dict(self.version9_plan, channel_low=None), px, cost, n_days, self.version9_max_hold)

    def _exit(self, idx, px, reason):
        self.first_exit_attempted = True
        return idx, float(px), reason

    def advance(self, idx: int, phase: str):
        """Observe one phase and return ``(idx, price, reason)`` or None."""
        if phase not in ("open", "close"):
            raise ValueError(f"unsupported minute phase: {phase}")
        self.is_true_day_last = idx == len(self.c) - 1
        if self.first_exit_attempted or not sell_allowed(self.can_sell, self.n_days):
            return None
        cur_hm = int(self.hm[idx]) if self.hm is not None else idx
        stop_enabled = isinstance(self.stop_pct, float) and 0 < self.stop_pct < 1
        if self.stop_range_ratio is not None:
            stop_enabled = True
        trigger = stop_trigger(self.cost, self.stop_pct) if stop_enabled else None
        if self.version9_plan is not None:
            trigger = plan_stop_price(self.version9_plan, self.cost)
            stop_enabled = trigger is not None
        px_open, px_close = float(self.o[idx]), float(self.c[idx])
        if phase == "open":
            # Keep the original scanner's OHLC ordering, including rejected fills.
            hi = float(self.h[idx])
            if hi > self.peak:
                self.peak, self.peak_hm = hi, cur_hm
            if cur_hm == CLOSE_CLEAR_HM:
                self.saw_close_hm = True
            skip_bar = blocked_bar(self.minute_stop_trigger, px_open, hi, self.limit_down)
            self._open_state[idx] = skip_bar, self.peak, self.peak_hm
            if not skip_bar and stop_enabled and gap_stop(px_open, trigger):
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
        trigger = (plan_stop_price(self.version9_plan, self.cost) if self.version9_plan is not None
                   else stop_trigger(self.cost, self.stop_pct) if stop_enabled else None)
        if stop_enabled:
            touched = (float(self.l[idx]) <= trigger if self.minute_stop_trigger == "hl"
                       else (px_close <= trigger if self.version9_plan is not None else stop_touch(ret, self.stop_pct)))
            if touched:
                fill_px = trigger if self.minute_stop_trigger == "hl" else px_close
                return self._exit(idx, fill_px, "stop_loss:touch")
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
        if self.version9_plan is not None and self.is_true_day_last:
            reason = plan_close_reason(dict(self.version9_plan, take_profit_pct=None), px_close, self.cost, self.n_days)
            if reason:
                return self._exit(idx, px_close, reason)
        if self.minute_stop_trigger == "hl" and not callable(self.exit_plan) and not callable(self.sell_gate):
            fill = target_fill(float(self.o[idx]), float(self.h[idx]), self.cost, self.peak,
                               self.n_days, self.take_profit_pct, self.take_profit)
            if fill is not None:
                return self._exit(idx, *fill)
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
        if self.force_sell_hm is not None and force_due(cur_hm, self.force_sell_hm):
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

