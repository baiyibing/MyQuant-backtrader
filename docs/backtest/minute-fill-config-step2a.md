# Step 2a: shared held-minute fill configuration

`FillConfig` is a frozen global sell-price policy accepted by `run`, `simulate`,
`scan_held_day`, `scan_held_day_python`, and `HeldMinuteCursor`. No CLI changes.
`book_fill_defaults` derives the path mapping from existing hooks/flags; no
strategy rules or registry entries change.

## Default path mapping

| Path | trigger_basis | fill_timing | fill_at (touch) | Gap fill |
| --- | --- | --- | --- | --- |
| version11 EOD pending (A2) | bar_last | next_bar_open | opening price | AM_OPEN next session |
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
- Folded version9_2 accepts custom
  config instead of rejecting it at the separate-engine guard. Daily, v7, bar_scan_exit and the
  minute wire registry are untouched.
- A1 (2026-10-05): `step_stop`, `scale_out`, and `peak_dd_clear_exits`
  now consume FillConfig. None and the hook-derived stop default preserve
  existing predicates, float order, metadata and event order. Step stops may
  trigger on bar low and fill at their lot line, last print, low or a positive
  specified price. Scale-out and peak drawdown still decide on last prints;
  this-bar low and line fills fail closed for those decisions.
- Next-open side orders retain lot identity and decided scale-out quantities in
  `held_fill_states[held_fill_key(pos)]`, carrying across sessions. They use
  `:next_open` reasons and `minute_pending_next_open`, with only the existing
  limit check on the execution open. There is no open+fill limit-pair rule.
  Closed lots are removed from carry by the ledger; repeated decisions cannot
  duplicate an outstanding lot order or count a scale step twice.

- 2026-10-05 14:13 人裁：A3 / B9 stay excluded；A1 pipe / A2 follow in separate PRs，见 [step-2b decisions](note-2b-decisions-2026-10-05.md)。

## Registered CSV books and default paths

All shared rows use this_bar, with bar_last touch / bar_open stop gap unless
marked absolute_exit or version11 EOD pending. Callback columns describe existing hooks (a callback
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
| version6_8 | shared; take_profit; step_stop side sells (A1 FillConfig) |
| version6_9 | shared; take_profit |
| version6_10 | shared; take_profit; step_stop side sells (A1 FillConfig) |
| version6_11 | shared; take_profit |
| version6_12 | shared; take_profit |
| version6_13 | shared; take_profit; step_stop / scale_out side sells (A1 FillConfig) |
| version6_14 | shared; take_profit; step_stop / scale_out / peak_dd_clear_exits side sells (A1 FillConfig) |
| version6_15 | shared; take_profit; step_stop / scale_out / peak_dd_clear_exits side sells (A1 FillConfig) |
| version6_16 | shared; take_profit; step_stop / scale_out / peak_dd_clear_exits side sells (A1 FillConfig) |
| version6_17 | shared; take_profit; step_stop / scale_out / peak_dd_clear_exits side sells (A1 FillConfig) |
| version8 | shared; take_profit |
| version8_1 | shared; take_profit |
| version8_2 | shared; take_profit |
| version8_3 | shared; take_profit |
| version8_4 | shared; take_profit |
| version8_5 | shared; take_profit; close_clear |
| version8_6 | shared; take_profit; close_clear |
| version9 | shared range stop; take_profit; version9_plan only with existing version9_sell opt-in |
| version9_2 | Shared minute_session / HeldMinuteCursor; explicit chosen-stop line |
| version10 | shared; take_profit |
| version11 | EOD pending session exit; next_bar_open at AM_OPEN |
| version12 | Main chronological loop + HeldMinuteCursor callback; custom FillConfig accepted |
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
| Folded books accept custom config through simulate | `test_simulate_folded_books_accept_custom_config` |
| absolute_exit bar_low guard | `test_simulate_absolute_exit_requires_bar_low` (version9_1) |
| Side sells accept custom configs; default/None unchanged | `test_simulate_side_sells_accept_custom_config`, `test_simulate_side_sells_default_config_unchanged`; `tests/test_side_sell_fill_config.py` (next-open, session carry, limit retry, no duplicate, other-exit cleanup, low trigger and look-ahead rejection) |
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

version6_14/version6_15 classification and peak_dd_exit guard follow-up (PR #368)
on master `2e3ef2e` (v6f off-byte overlay v4, 36 books):

- Touched tests (`tests/test_minute_bar_scan_host.py`,
  `tests/test_minute_fill_config.py`) plus `tests/test_off_byte_baseline.py`:
  **630 passed**, 6.62 s; off-byte fixtures unchanged.
- `tests/test_csv_strategy_books.py::test_registered_books_are_explicit` gains
  version6_15 (master `2e3ef2e` registered it without updating that list).
- Full suite, `-m "not production and not benchmark"`: **7524 passed,
  5 skipped, 24 deselected**, 29 warnings.
- All changed Python/Markdown files are UTF-8 without BOM with zero
  NUL bytes; `git diff --check` passes.

Side-sell fail-closed follow-up after rebase on master `a55e3c85`:

- `tests/test_minute_fill_config.py` and `tests/test_off_byte_baseline.py`:
  **191 passed**, 4.11 s; off-byte fixtures unchanged.
- Full suite, `-m "not production and not benchmark"`: **7480 passed,
  5 skipped, 24 deselected**, 29 warnings, 173.41 s.
- The three changed Python/Markdown files are UTF-8 without BOM with zero
  NUL bytes; `git diff --check` passes.

Original step 2a validation before this follow-up:

- Requested four files: **196 passed** (42 fill-config cases), 4.01 s.
- Full suite, `-m "not production and not benchmark"`: **7424 passed,
  5 skipped, 24 deselected**, 29 warnings, 145.22 s.
- Exact collection: **7453 total collected; 7429 selected; 24 deselected**.
  The 7429 selected cases comprise the 7424 passes and 5 existing skips.
- No golden rewrites or new skips. All six written Python/Markdown files
  decode as UTF-8 without BOM and contain zero NUL bytes; `git diff --check` passes.

A1 side-sell pipe validation after rebase (Human “A1 pipe”, 2026-10-05;
branch base `origin/master ccac8e2a`, `/tmp/mq-v6/bin/python`):

- Requested four files, run with `-p no:cacheprovider -q`:
  `tests/test_side_sell_fill_config.py`, `tests/test_minute_fill_config.py`,
  `tests/test_scan_held_day_numba_parity.py`, and
  `tests/test_off_byte_baseline.py`: **248 passed, 0 failed**, 5.62 s.
- Full suite, run with `-p no:cacheprovider -q
  -m "not production and not benchmark"`: **7636 passed, 4 skipped,
  24 deselected, 0 failed**, 29 warnings, 142.15 s.
- `git diff --stat origin/master -- tests/fixtures` is empty.
- The updated Markdown file decodes as UTF-8, has no BOM and zero NUL
  bytes; `git diff --check` passes.


## Step 2b A2 — version11 minute fold (2026-10-05)

Version11 held sells now use `scan_held_day` / `HeldMinuteCursor` in both
`simulate` and the chronological cash-order loop. The EOD rule still sets
`Position.pending_exit`; its hook-derived default is `next_bar_open`, eligible
only at AM_OPEN (09:30) in the next session. It does not retry later that day.
AM_OPEN buys and daily rules are unchanged. Version12 is folded in the A2
follow-ups below, including the final version9_2 fold. Version9_1 is untouched.

Default behavior differences: none in the off-byte cases. Price validity,
positive finite opening volume, limit-down and T+1 checks retain their results;
volume is checked before limit-down. Zero/nonfinite volume or a blocked open
carries the EOD decision to another session. Legacy reasons and opening audit
fields are retained without adding a `:next_open` suffix. Historical fixtures
remain frozen; no overlay is needed.

New opt-in behavior: version11 accepts custom FillConfig through the cursor.
`this_bar` fills the pending decision at the AM_OPEN bar's last print or a
specified positive price, with the shared outer open/fill limit checks and
close-phase volume capacity. `next_bar_open` keeps the session opening rule and
ignores `fill_at`. Callback low/high/open look-ahead combinations and a missing
explicit line fail closed as elsewhere. No intraday strategy decision is added.


A2 version11 post-rebase verification (Python `/tmp/mq-v6/bin/python`,
base `origin/master 34bfdd73`):

- Off-byte and fold tests (`-p no:cacheprovider -q tests/test_off_byte_baseline.py tests/test_v11_minute_fold.py`):
  **176 passed, 0 failed**, 4.43 s.
- Full suite (`-p no:cacheprovider -q -m "not production and not benchmark"`):
  **7650 passed, 4 skipped, 24 deselected, 29 warnings, 0 failed**, 143.75 s.
- `git diff --stat origin/master -- tests/fixtures`: **empty**.


## Step 2b A2 — version12 minute fold (2026-10-05)

Version12 now always uses `minute_cash_order.run_chronological_day`.
`strategy12_engine.MinuteSession` prepares exdiv, price-domain references and
quote clocks, then supplies held and buy callbacks; it owns no minute loop.
Each code/bar uses `HeldMinuteCursor.exit_plan / exit_state`, with live lot
allocation and `fill_exit` clamp/memory updates. A new row cursor preserves
partial/rejected-fill retries on later bars. `run_daily_day` and strategy12_rules
are unchanged. Version9_2 is folded below; version9_1 is untouched.

Default differences: none in the frozen daily/minute CSV bytes and account
snapshots, participation 0.1 replay, or validated identity/nonunit X-01 replays.
All opens precede closes in the main loop; S12 default decisions remain at close,
with held sells before chase → pool → step-add → closed buyback at each hm.
The max-available 09:30–09:45 and 14:30–14:55 clocks, open/fill limit checks,
T+1/bonus lock, lot clamp, exdiv preparation and reference conversion remain.
The existing S12 MA10-stop overlay stays active and unmodified; no new overlay.

Interface differences: `fix_minute_cash_order=True` formerly raised an
inapplicable-book error; it now accepts S12 and produces the same fills/NAV as
omission. The old rejection tests now assert flag-on/off equality, including
X-01. Custom FillConfig formerly failed the separate-engine guard; it now reaches
the cursor. Positive-price execution uses that price; next_bar_open pins the
signal-time lot allocation and executes at the next eligible open, including
across sessions. It clamps against current T+1/bonus eligibility and cannot
reallocate onto later buys. Opening fills use `at=hm-1` with execution-hm capacity and
`minute_pending_next_open` metadata. With participation enabled the completed
execution bucket is therefore unavailable at open, matching the shared
fail-closed policy; no previous-bucket capacity is borrowed.
Default close metadata/buckets stay unchanged. Callback low-print look-ahead
and missing-line configurations fail through shared cursor validation; the
book's MA decision still uses close. X-02 audit_sink remains excluded.
The dedicated X-01 audit now reads live callback context instead of deleted
run_minute_day locals.


A2 version12 verification (Python `/tmp/mq-v6/bin/python`, pandas 3.0.6,
base `origin/master bedfef4`):

- `tests/test_off_byte_baseline.py`: **165 passed, 0 failed**, 3.87 s;
  version12 daily/minute raw CSV hashes and complete account snapshots match
  the branch base and the active frozen S12 overlay.
- `test_v12_minute_fold.py`, `test_strategy12_engine.py`,
  `test_s12_price_domain.py`, `test_partial_sell.py`,
  `test_minute_cash_chronology.py`, `test_minute_fill_config.py`:
  **258 passed, 0 failed**, 4.11 s.
- Final full suite (`-p no:cacheprovider -q -m "not production and not benchmark"`):
  **7679 passed, 5 skipped, 24 deselected, 29 warnings, 0 failed**, 145.26 s (0:02:25).
- `git diff --stat origin/master -- tests/fixtures`: **empty**.
- Baseline replay: default and X-01 identity/front=raw*0.5 each retain
  **3 BUY / 3 SELL**, final equity **4,892,514.7375**; participation 0.1 retains
  **3 BUY / 3 SELL**, final equity **4,998,941.0**. All trade rows match.
  Cash-order flag-on was rejected at the base; now it matches default.


## Step 2b A2 — version9_2 minute fold (2026-10-05)

Version9_2 now uses `minute_cash_order.run_chronological_day` with
`strategy9_2_engine.MinuteSession` and `HeldMinuteCursor.phase_exit`.
No book retains a `run_minute_day` hook; external retired hooks fail clearly.
Only one shared chronological minute loop remains for the folded books.
Version9_1, strategy9_2_rules and the version9_2 daily engine are unchanged.

Default ordering remains adds first, then each held code's pending retry,
chosen stop, peak/plan exit, then pool buys at its maximum available
14:30–14:55 bar. Gap-open quotes are observed inside the close callback to
preserve legacy per-code settlement order after adds. Default chosen stops
use open for gaps and close for touches; limit-down retries wait until the
next day. Turtle quantities, scale-band memory and T+1 residuals are retained.

Non-default FillConfig now reaches the cursor. Low-only stops are opt-in;
touch stops have an explicit chosen-stop line. Plans without a line reject
line pricing and noncausal low pricing. Next-open orders retain pending reason
and quantity across sessions and use opening metadata (`at=hm-1`, execution
hm/bucket, `minute_pending_next_open`). Participation cannot consume the
uncompleted opening bucket. `fix_minute_cash_order=True` remains equivalent
to omission. Default CSV bytes match base `322c36a`; no new overlay is needed
and no existing fixture was modified.


A2 version9_2 final verification (Python `/tmp/mq-v6/bin/python`,
pandas 3.0.6, branch base `322c36a`):

- Off-byte (`-p no:cacheprovider -q tests/test_off_byte_baseline.py`):
  **165 passed, 0 failed**, 4.24 s.
- Fold/book/config (`test_v92_minute_fold.py`, `test_strategy9_2_book.py`,
  `test_minute_fill_config.py`, same pytest options):
  **129 passed, 0 failed**, 1.17 s.
- Full suite (`-p no:cacheprovider -q -m "not production and not benchmark"`):
  **7707 passed, 5 skipped, 24 deselected, 29 warnings, 0 failed**,
  129.82 s (0:02:09).
- Base/final replay, default and `fix_minute_cash_order=True`: each
  **6 BUY / 6 SELL**, final equity **5,054,460.412500001**.
  Daily: **6 BUY / 6 SELL**, final equity **5,005,689.371**.
  All trade rows, equity curves, stats and both production CSV hashes match.
- Participation 0.1: **0 BUY / 0 SELL**, final equity **5,000,000.0**
  on both revisions. The bare option has no volume lookup and fails closed;
  an additional replay with raw incremental fixture BucketVolume also has
  no fills. This checks equality, not successful partial-volume executions.
- `git diff 322c36a -- tests/fixtures`: **empty**. The local, uncommitted
  `A2_V92_DELTA.md` records all interface differences and per-case deltas.
