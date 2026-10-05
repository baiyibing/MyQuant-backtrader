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
- `simulate` and the chronological adapter key carry by signal position ID
  or a position-owned lifetime token, never a recyclable Python object ID.
  The ledger removes carry on full closure (including linked lots); partial
  sells keep it until the remaining lot/group closes. Low-level
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

## Claim → test

Test names below are in `tests/test_minute_fill_config.py` unless a file is specified.

| Claim | Named test |
| --- | --- |
| Default path unchanged; golden bytes preserved | `test_defaults`, `test_version9_plan_defaults`; `tests/test_off_byte_baseline.py::test_off_byte_baseline_trades_equity_and_account`; `tests/test_partial_sell.py::test_default_trades_and_equity_byte_identical_to_pre_s1_head` |
| Hook-derived defaults for every registered book | `test_mapping`, `test_all_book_defaults_derived_from_hooks` |
| Explicit this-bar prices and next-open price independence | `test_this_bar_prices`, `test_next_open_prices`, `test_gap` |
| next_bar_open cross-day carry in both schedules, shared and independent positions | `test_simulate_carries_next_session` |
| Limit-down retry | `test_carry_and_limit_retry` |
| 14:55/15:00 this_bar time exits | `test_time_exits_stay_this_bar` |
| numba raises on non-default config, explicit and environment dispatch | `test_numba_refuses` |
| Default numba parity | `tests/test_scan_held_day_numba_parity.py::test_numba_gap_open_stop`, `test_numba_t0_no_sell_no_peak_update`, `test_numba_trail_hit`, `test_numba_force_sell_time` |
| version9_2/version12/minute_open reject custom config through simulate | `test_simulate_separate_engine_rejects_custom_config` (minute_open = version11) |
| absolute_exit bar_low guard | `test_simulate_absolute_exit_requires_bar_low` (version9_1) |
| Look-ahead rejects | `test_lookahead`, `test_callback_low_rejected_at_decision`, `test_target_cannot_assume_low_after_high` |
| Callback and trail timing | `test_target_and_trail` |
| Missing carry out-param fails closed | `test_missing_carry_state_fails_closed` |
| Stale carry cleared on other exit; same-code re-entry has no stale fill | `test_stale_carry_cleared_on_other_exit_and_same_code_reentry` |
| Partial sell retains carry; full sell clears it | `test_carry_retained_on_partial_sell_cleared_on_full_sell`; `tests/test_partial_sell.py::test_s1_partial_sell_conserves_cash_and_nonzero_lot`, `test_s1_deletes_only_empty_and_t1_blocks_override` |

The stale-state regression deterministically models object-ID reuse, queues an
actual last-bar next-open stop, then closes through the ledger with close_clear
before a later same-code entry. It checks immediate carry removal, distinct
lifetime keys, and the absence of a stale next-open SELL on the new position.

## Validation

Using `/tmp/mq-v6/bin/python` and `-p no:cacheprovider`:

- Requested four files: **196 passed** (42 fill-config cases), 4.01 s.
- Full suite, `-m "not production and not benchmark"`: **7424 passed,
  5 skipped, 24 deselected**, 29 warnings, 145.22 s.
- Exact collection: **7453 total collected; 7429 selected; 24 deselected**.
  The 7429 selected cases comprise the 7424 passes and 5 existing skips.
- No golden rewrites or new skips. All six written Python/Markdown files
  decode as UTF-8 without BOM and contain zero NUL bytes; `git diff --check` passes.
