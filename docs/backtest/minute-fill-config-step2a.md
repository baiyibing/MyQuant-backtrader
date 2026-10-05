# Step 2a: shared held-minute fill configuration

`FillConfig` is a frozen global sell-price policy accepted by `run`, `simulate`,
`scan_held_day`, `scan_held_day_python`, and `HeldMinuteCursor`. No CLI changes.
`book_fill_defaults` derives the path mapping from existing hooks/flags; no
strategy rules or registry entries change.

## Default path mapping

| Path | trigger_basis | fill_timing | fill_at (touch) | Gap fill |
| --- | --- | --- | --- | --- |
| shared default | bar_last | this_bar | bar_last | bar_open |
| hl stop | bar_low | this_bar | line | bar_open |
| absolute_exit | bar_low (required) | this_bar | line | bar_open |
| version9_plan stop | bar_last (hl opt-in: bar_low) | this_bar | bar_last (hl: line) | bar_open |
| trail | bar_last | this_bar | bar_last | n/a; stop gap has priority |
| take_profit callback | bar_last | this_bar | bar_last | n/a |
| hl fixed take_profit | upward high touch (existing predicate) | this_bar | line | max(bar_open, line) |
| force_sell / reserve / version9 EOD | bar_last | this_bar | bar_last | n/a |
| close_clear (including missing-15:00 fallback) | bar_last | this_bar | bar_last | n/a |

`trigger_basis` controls the stop comparison. Target/callback/trail predicates
remain exactly the existing book predicates. Explicit custom prices/timing
apply to stops, fixed targets, take-profit callbacks and the built-in trail.
Sell-gate/partial-exit callbacks, reserve exits and time/EOD exits retain their
existing timing and price. An omitted config or the equivalent path default
retains the original predicates, including floating-point comparison order.

## Execution and validation

- `next_bar_open` always fills at the next available eligible open, regardless
  of `fill_at`. Gap signals also queue for that next open and retain
  `stop_loss:gap_open:next_open`. Other queued reasons append `:next_open`.
- Last-bar signals carry to the next session, following next-bar execution.
  Existing opening/floor limit-down checks block execution and retry at later
  opens; there are no new limit, T+1, capacity or partial-fill rules.
  Queued fills use opening-quote audit metadata and the existing opening
  completed-volume timing (the previous minute, where a cap is configured).
- `simulate` carries state by signal position ID or lot identity. Low-level
  scans accept a mutable `fill_state` out-param: reuse it across sessions.
  A scan that needs to carry but has no out-param raises instead of losing it.
  A direct cursor exposes its `fill_state` for resumption.
- Time exits at 14:55/15:00 retain this-bar last-print execution. An already
  queued price exit retains priority over later signals, including time exits.
- Same-bar high sells and earlier-open fills are forbidden. Last-print stop
  decisions also forbid bar-low fills. Intrabar low decisions may fill at low,
  line, specified positive finite price or subsequent last print. Callback/trail
  decisions additionally reject low prints at runtime; OHLC cannot establish
  that a target-triggering high preceded the low.
  Lines and specified floats are explicit execution assumptions, not earlier
  observed OHLC prints; callbacks without an explicit line reject `line`.
- If the existing dispatcher would select numba, non-default config raises
  `ValueError` for `use_numba=True` or the numba environment backend. Select
  Python explicitly for custom policies. Existing numba-ineligible paths
  remain Python; the numba implementation is unchanged.
- Separate minute engines (version9_2, version12, minute_open) reject custom
  config instead of silently ignoring it. Daily, v7, bar_scan_exit and the
  minute wire registry are untouched.

## Registered CSV books and default paths

All shared rows use this_bar, with bar_last touch / bar_open stop gap unless
marked absolute_exit. Callback columns describe existing hooks (a callback
may return no exit). H/L remains opt-in for supported shared books.

| Registered book | Default path(s) |
| --- | --- |
| version1 | shared; take_profit |
| version2 | shared; take_profit |
| version3 | shared; take_profit |
| version4 | shared; sell_gate; take_profit |
| version5 | shared; take_profit; force_sell |
| version6 | shared; take_profit |
| version6_1 | shared; take_profit |
| version6_2 | shared; take_profit |
| version6_3 | shared; take_profit |
| version6_4 | shared; take_profit |
| version6_5 | shared; take_profit |
| version6_6 | shared; take_profit |
| version6_7 | shared; take_profit |
| version6_8 | shared; take_profit |
| version6_9 | shared; take_profit |
| version6_10 | shared; take_profit |
| version6_11 | shared; take_profit |
| version6_12 | shared; take_profit |
| version8 | shared; take_profit |
| version8_1 | shared; take_profit |
| version8_2 | shared; take_profit |
| version8_3 | shared; take_profit |
| version8_4 | shared; take_profit |
| version8_5 | shared; take_profit; close_clear |
| version8_6 | shared; take_profit; close_clear |
| version9 | shared range stop; take_profit; version9_plan only with existing version9_sell opt-in |
| version9_2 | Separate run_minute_day (excluded) |
| version10 | shared; take_profit |
| version11 | shared; take_profit |
| version12 | Separate run_minute_day (excluded) |
| topk_dropout | shared; sell_gate; take_profit |
| topk_score_exit | shared; sell_gate; take_profit |
| version9_1 | absolute_exit; inert take_profit callback |
