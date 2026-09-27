"""#208 P1/P2/P3 buy dispatch: fixed seats/budgets and opt-in limit handoff.

The caller advances sells and these buys on the same minute clock. The legacy
close path never constructs this dispatcher or adds its audit fields.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from backtest.research.ashare_bars import AM_OPEN, PM_CLOSE, _in_session
from backtest.research.ashare_session import hit_limit_down, hit_limit_up
from backtest.research.csv_common import book_limit_prices
from backtest.research.csv_simulate_loop import (
    _buy_denom, apply_capital_ration, run_pool_buys_day,
)
from backtest.research.exdiv_map import mapped_prev_close
from backtest.research.minute_audit import audit_scope


CLOSE_BUY_HM = 14 * 60 + 55
CLOSE_FALLBACK_START = 14 * 60 + 30


VWAP_SLICE_CLOCKS = (9 * 60 + 35, 10 * 60 + 30, 11 * 60 + 30,
                     13 * 60, 14 * 60, 14 * 60 + 55)


TOPK_EXEC_HELP_LOCK = """
TopK minute execution (#208 P1/P2/P3; topk_dropout only):
  --topk-exec close|open|intraday|vwap (default close; omitted = close).
  close: existing 14:55 close, last close in 14:30–14:55 if missing; reason=pool.
  open (opt-in): exact 09:30 open once; missing 09:30 skips, no later-row fallback.
  intraday (opt-in): first session open < limit_up; equality retries the same name.
  Sessions: [09:30,11:30] / [13:00,15:00]; all valid opens blocked → limit_retry_expired;
  no valid quotes → skip_no_bar. Current qlib 9.5% band remains unchanged.
  open/intraday freeze min(daily_quota, cash)*0.95/D at 09:30 buy dispatch;
  execution checks actual cash including fees, after same-minute open sells,
  before same-minute close sells. Original planned seats D stay fixed.
  Reasons: pool:open / pool:intraday; trades carry actual hm (minute of day).
  topk_execution.json records seats, original code, selection/quote/execution
  minutes, allocation cash, quota, outcomes and limit_retry_fills/limit_retry_expired.
  vwap (opt-in): equal-notional fixed-clock TWAP-style slicer, NOT volume-participation
  VWAP or strategy-8 tail-window-buy. Session window [09:35,11:30] / [13:00,14:55].
  Exact clocks 09:35,10:30,11:30,13:00,14:00,14:55; each quotes its bar open.
  Freeze q=min(daily_quota,cash)*cash_deploy_frac/D at 09:30; each slice gets q/6.
  Missing/invalid quotes, limits, sub-lot and other skips affect only that slice;
  no borrow, no roll-forward; same-seat fills accumulate, reason=pool:vwap.
  Strict open >= limit_up skips a slice; completed volume before hm only.
  vwap x --limit-walkdown is refused until separate human GO defines partial-fill
  handoff. --limit-walkdown (default OFF): first limit-up block hands whole q
  to the next eligible frozen rank; close/open recurse at 14:55/09:30, intraday
  only scans hm >= selection time. Cash/other failures never hand off.
  Substitute fills: pool:walkdown:<exec>; counter walkdown_fills.
  Sell rules are unchanged. topk_score_exit is excluded.
"""


def validate_topk_exec(mode, strategy, limit_walkdown=False):
    if mode not in ("close", "open", "intraday", "vwap"):
        raise ValueError(f"unknown --topk-exec {mode!r}; choose close, open, intraday or vwap")
    if mode == "vwap" and limit_walkdown:
        raise ValueError("--topk-exec vwap x --limit-walkdown is refused")
    if mode != "close" or limit_walkdown:
        from backtest.research.csv_strategy_books import normalize_csv_strategy

        if normalize_csv_strategy(strategy) != "topk_dropout":
            raise ValueError("--topk-exec open/intraday/vwap and --limit-walkdown apply only to topk_dropout")


def parse_topk_exec(value):
    import argparse

    try:
        validate_topk_exec(value, "topk_dropout")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return value


class TopkMinuteBuys:
    """One day-valid order per original planned seat, settled by the caller."""

    def __init__(self, st, *, mode, hooks, previous_and_frame, open_quote_for,
                 day_i, day, ds, names, daily_quota, exdiv, audit_sink=None,
                 limit_walkdown=False, close_quote_for=None):
        self.st, self.mode, self.hooks = st, mode, hooks
        self.day_i, self.day, self.ds = day_i, day, ds
        self.names, self.daily_quota, self.exdiv = names, daily_quota, exdiv
        self.audit_sink = audit_sink
        self.walkdown = limit_walkdown
        self.quote_bars = {}
        planner = hooks["planned_for_day"]
        self.planned = apply_capital_ration(
            list(planner(ds, list(st.positions))), ration=hooks.get("ration", "file_order"),
            ration_seed=hooks.get("ration_seed", 0), ds=ds,
        )
        self.denom = _buy_denom(self.planned, planner)
        self.seats = {code: i for i, code in enumerate(self.planned)}
        self.events, self.closes, self.limits = {}, {}, {}
        self.missing, self.unknown, self.done, self.retried = set(), set(), set(), set()
        self.last_quote = {}
        self.cash_basis = None
        if mode == "vwap":
            self.slice_results = {code: [] for code in self.planned}
            self.spent = {code: 0. for code in self.planned}
            self.filled = set()
        codes = self.planned
        if self.walkdown:
            self.roster = planner.walkdown_roster(ds)
            self.rank = {code: i for i, code in enumerate(self.roster)}
            self.reserved = set(self.planned) | set(st.positions)
            self.original = {code: code for code in self.planned}
            self.selected = {code: CLOSE_BUY_HM if mode == "close" else AM_OPEN for code in self.planned}
            self.active = dict(self.original)
            codes = list(dict.fromkeys([*self.planned, *self.roster]))
        for code in codes:
            got = previous_and_frame(code)
            if got is None:
                self.missing.add(code)
                continue
            closes, frame = got
            # Same inclusive session contract as ashare_bars.annotate_session.
            frame = frame.loc[_in_session(frame["hm"])].sort_values("hm", kind="stable")
            if mode == "vwap":
                frame = frame.loc[frame["hm"].between(VWAP_SLICE_CLOCKS[0], VWAP_SLICE_CLOCKS[-1])
                                  & frame["hm"].isin(VWAP_SLICE_CLOCKS)]
            if mode == "open":
                opening = open_quote_for(frame)
                frame = frame.iloc[:0] if opening is None else opening.to_frame().T
            quotes = [(int(row.hm), float(row.open)) for row in frame.itertuples()
                      if math.isfinite(float(row.open)) and float(row.open) > 0]
            if mode == "close":
                px = close_quote_for(frame)
                quotes = []
                if px is not None and math.isfinite(px) and px > 0:
                    hit = frame.loc[frame["hm"] == CLOSE_BUY_HM]
                    late = frame.loc[frame["hm"].between(CLOSE_FALLBACK_START, CLOSE_BUY_HM)]
                    self.quote_bars[code] = int((hit.iloc[0] if not hit.empty else late.iloc[-1])["hm"])
                    quotes = [(CLOSE_BUY_HM, px)]
            if not quotes:
                self.missing.add(code)
                continue
            previous, _ = mapped_prev_close(exdiv, code, ds, float(closes[-1]))
            if not math.isfinite(previous) or previous <= 0:
                self.missing.add(code)
                continue
            limits = book_limit_prices(code, previous, names,
                                       qlib_limit_pct=hooks.get("qlib_limit_pct"))
            if limits is None:
                self.unknown.add(code)
                continue
            self.closes[code], self.limits[code] = closes, limits
            for hm, px in quotes:
                self.events.setdefault(hm, []).append((code, px))

    @property
    def clocks(self):
        return set(self.events) | {AM_OPEN, PM_CLOSE} | (
            set(VWAP_SLICE_CLOCKS) if self.mode == "vwap" else set())

    def record(self, code, hm, reason, *, px=None, quote_hm=None, event=None, phase="open"):
        row = dict(event or {})
        row.update(date=self.ds, code=code, seat=self.seats[code], original_code=code,
                   selection_hm=AM_OPEN, decision_hm=hm, quote_hm=quote_hm,
                   execution_hm=hm if row.get("side") == "BUY" else None,
                   quota=self.quota, allocation_cash=self.cash_basis,
                   denominator=self.denom, reason=reason, price=px, phase=phase)
        if self.walkdown:
            row.update(original_code=self.original[code],
                       substitute_code=code if self.original[code] != code else None,
                       selection_hm=self.selected[code])
        if self.mode == "vwap" and hm in VWAP_SLICE_CLOCKS and phase == "open":
            row.update(slice_index=VWAP_SLICE_CLOCKS.index(hm), slice_hm=hm,
                       slice_budget=self.quota / len(VWAP_SLICE_CLOCKS))
            self.slice_results[code].append(row)
        self.st.topk_exec_audit.append(row)

    def advance(self, hm):
        if self.walkdown:
            self.advance_walkdown(hm)
            return
        if self.cash_basis is None:
            assert hm == AM_OPEN
            self.cash_basis = self.st.cash
            self.quota = (min(self.daily_quota, self.cash_basis)
                          * self.hooks["cash_deploy_frac"] / self.denom if self.denom else 0.)
            for code in ([] if self.mode == "vwap" else self.planned):
                reason = ("skip_no_bar" if code in self.missing else
                          "skip_unknown_board" if code in self.unknown else None)
                if reason:
                    self.st.stats[reason] += 1
                    self.done.add(code)
                    self.record(code, hm, reason)
        if self.mode == "vwap":
            self.advance_vwap(hm)
            return
        for code, px in self.events.get(hm, []):
            if code in self.done:
                continue
            if self.mode == "intraday" and px >= self.limits[code][0]:
                if code not in self.retried:
                    self.record(code, hm, "limit_retry_wait", px=px, quote_hm=hm)
                self.retried.add(code)
                self.last_quote[code] = (hm, px)
                continue
            # Only the upper-limit block retries. Every other outcome is final.
            self.done.add(code)
            self.attempt(code, hm, px)
        if hm == PM_CLOSE:
            for code in self.planned:
                if code in self.done:
                    continue
                self.st.stats["limit_retry_expired"] += 1
                self.done.add(code)
                quote_hm, px = self.last_quote[code]
                self.record(code, hm, "limit_retry_expired", px=px, quote_hm=quote_hm, phase="close")

    def advance_walkdown(self, hm):
        start = CLOSE_BUY_HM if self.mode == "close" else AM_OPEN
        if hm < start:
            return
        if self.cash_basis is None:
            self.cash_basis = self.st.cash
            self.quota = (min(self.daily_quota, self.cash_basis)
                          * self.hooks["cash_deploy_frac"] / self.denom if self.denom else 0.)
        quotes = {}
        for code, px in self.events.get(hm, []):
            quotes.setdefault(code, px)  # Stable first effective attempt, even for duplicate hm.
        phase = "close" if self.mode == "close" else "open"
        for original in self.planned:
            code = self.active[original]
            while code not in self.done:
                px = quotes.get(code)
                reason = ("skip_unknown_board" if code in self.unknown else
                          "skip_no_bar" if code in self.missing else None)
                if reason is None and px is None:
                    if hm != PM_CLOSE:
                        break  # Candidate can only use its next remaining session bar.
                    reason = "skip_no_remaining_bar"
                if reason:
                    self.st.stats[reason] = self.st.stats.get(reason, 0) + 1
                    self.record(code, hm, reason, phase=phase)
                else:
                    reason = self.attempt(code, hm, px)
                self.done.add(code)
                upper = (px is not None and code in self.limits and
                         (hit_limit_up(px, self.limits[code][0]) if self.mode == "close"
                          else px >= self.limits[code][0]))
                # Only a real upper-limit rejection transfers the seat. The open
                # contract also skips missing substitutes within an existing chain.
                handoff = (reason == "skip_limit_up" and upper) or (
                    self.mode == "open" and code != original and reason == "skip_no_bar")
                if not handoff:
                    break
                current_rank = self.rank.get(code)
                if current_rank is None:
                    # Planner and roster may diverge; never invent a handoff rank.
                    self.record(code, hm, "walkdown_missing_rank", phase=phase)
                    break
                candidate = next((c for c in self.roster
                                  if self.rank[c] > current_rank
                                  and c not in self.reserved and c not in self.st.positions), None)
                if candidate is None:
                    self.st.stats["walkdown_exhausted"] += 1
                    self.record(code, hm, "walkdown_exhausted", phase=phase)
                    break
                self.reserved.add(candidate)
                self.original[candidate] = original
                self.seats[candidate] = self.seats[original]
                self.selected[candidate] = hm
                self.active[original] = candidate
                self.record(candidate, hm, "walkdown_selected", phase=phase)
                code = candidate

    def advance_vwap(self, hm):
        if hm in VWAP_SLICE_CLOCKS:
            quotes = dict(self.events.get(hm, []))
            for code in self.planned:
                px = quotes.get(code)
                if px is None:
                    reason = "skip_unknown_board" if code in self.unknown else "skip_no_bar"
                    self.record(code, hm, reason)
                else:
                    self.attempt(code, hm, px)
        if hm == PM_CLOSE:
            for code in self.planned:
                rows = self.slice_results[code]
                valid = [row for row in rows if row["quote_hm"] is not None]
                if code in self.filled:
                    reason = "pool:vwap"
                elif valid and all(row["reason"] == "skip_limit_up" for row in valid):
                    reason = "skip_limit_up"
                elif not valid:
                    reason = "skip_unknown_board" if code in self.unknown else "skip_no_bar"
                else:
                    # Missing clocks do not hide the last concrete execution failure.
                    reason = valid[-1]["reason"]
                if reason.startswith("skip_") and not reason.startswith("skip_volume"):
                    self.st.stats[reason] = self.st.stats.get(reason, 0) + 1
                self.record(code, hm, reason, phase="close")

    def attempt(self, code, hm, px):
        def frozen_seat(_ds, _held):
            return [code]

        # Each invocation still uses the original D and 09:30 cash basis in
        # run_pool_buys_day, never the number of successful/remaining orders.
        frozen_seat.slot_count = self.denom
        emitted = []

        def capture(row):
            emitted.append(row)
            if callable(self.audit_sink):
                self.audit_sink(row)
            elif self.audit_sink is not None:
                self.audit_sink.append(row)

        before = self.st.stats.copy()
        phase = "close" if self.mode == "close" else "open"
        quote_hm = self.quote_bars.get(code, hm)
        substitute = self.walkdown and self.original[code] != code
        buy_reason = (f"pool:walkdown:{self.mode}" if substitute else
                      "pool" if self.mode == "close" else f"pool:{self.mode}")
        with audit_scope(capture, decision_hm=hm, quote_hm=quote_hm, phase=phase):
            run_pool_buys_day(
                self.st, {}, day_i=self.day_i, day=self.day, ds=self.ds,
                pool_days={}, daily_quota=self.daily_quota, names=self.names,
                allow_add=(code in self.filled if self.mode == "vwap"
                           else bool(self.hooks["allow_add"])), buy_gate=self.hooks.get("buy_gate"),
                buy_quote_for=lambda _code: (px, self.closes[code]),
                planned_for_day=frozen_seat, allocation_cash=self.cash_basis,
                cash_deploy_frac=self.hooks["cash_deploy_frac"],
                exdiv=self.exdiv, qlib_limit_pct=self.hooks.get("qlib_limit_pct"),
                limit_up_chase=False,
                forbid_all_trade_at_limit=self.hooks.get("forbid_all_trade_at_limit", False),
                allow_new_name=self.hooks.get("allow_new_name"),
                volume_bucket_for=(lambda _code: hm - 1 if self.mode == "vwap" else quote_hm)
                if self.st.volume_cap is not None else None,
                volume_at=hm if self.mode == "close" else hm - 1,
                buy_reason=buy_reason, buy_hm=hm,
                strict_limit_up=self.mode != "close",
                **({"order_budget": min(self.quota / len(VWAP_SLICE_CLOCKS),
                                        max(0., self.quota - self.spent[code]))}
                   if self.mode == "vwap" else {}),
            )
        if emitted:
            event = emitted[-1]
            reason = event["reason"]
            if event["side"] == "BUY" and code in self.retried:
                self.st.stats["limit_retry_fills"] += 1
            if reason == "skip_cash":
                self.st.stats["skip_cash"] = int(self.st.stats.get("skip_cash", 0)) + 1
        else:
            event = None
            reason = next((key for key in (
                "skip_held", "skip_index_gate", "skip_no_bar", "skip_unknown_board",
                "skip_limit_up", "skip_buy_gate", "skip_add_loser",
            ) if self.st.stats.get(key, 0) > before.get(key, 0)), "skip_budget")
            if reason == "skip_limit_up" and hit_limit_down(px, self.limits[code][1]):
                reason = "skip_limit_down"
        if self.mode == "vwap":
            # Existing rejection counters describe seats, not six slice attempts.
            # Keep concrete per-slice outcomes in the audit and tally at day end.
            for key in set(self.st.stats) | set(before):
                if key.startswith("skip_") and not key.startswith("skip_volume"):
                    if key in before:
                        self.st.stats[key] = before[key]
                    else:
                        self.st.stats.pop(key, None)
            if event is not None and event["side"] == "BUY":
                self.filled.add(code)
                self.spent[code] += event["notional"]
        if substitute and event is not None and event["side"] == "BUY":
            self.st.stats["walkdown_fills"] += 1
        self.record(code, hm, reason, px=px, quote_hm=quote_hm, event=event, phase=phase)
        return reason


def write_topk_exec_audit(out_dir, st):
    payload = {key: st.stats[key] for key in (
        "topk_exec", "limit_retry_fills", "limit_retry_expired",
    )}
    if st.stats.get("limit_walkdown"):
        payload.update(limit_walkdown=True, walkdown_fills=st.stats["walkdown_fills"],
                       walkdown_exhausted=st.stats["walkdown_exhausted"])
    payload["events"] = st.topk_exec_audit
    (Path(out_dir) / "topk_execution.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
