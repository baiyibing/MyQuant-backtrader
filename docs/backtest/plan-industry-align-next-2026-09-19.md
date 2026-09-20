# Plan: industry-align next (fill gates fork, zero-change default) (2026-09-19)

> **Status**: ✅ **Human GO P1=A closure (2026-09-20 Asia/Shanghai)** — **P1 closed as A**, superseding its 2026-09-19 keep-deferred status. P2/P4 remain deferred; P3 δ contracts/production cuts retain their separate authority. This closure ships docs SSOT + data-free contract tests only; production behavior stays as-built.
> **Main ship (single theme)**: Contractualize A-share fill gates fork (`limits`, halt/zero-volume, ST name) between book-engine and v7 paths, with default **zero behavior change**.
> **IMPLEMENTATION_BASE (fact anchor)**: `f46004d3bf3c9aa8314c5c3d0adcdebd730d9822` (full 40-char SHA of `origin/master` at implementation start).
> **P1=A closure base (2026-09-20)**: `41f8df331ed25aad4616bde56c77ddb7025c91ee`; all production Python must remain zero-diff against this base. The prior fact anchor and slices below describe the original fill-gates ship.
> **Business sources read**: `engine-positioning-ssot.md`, `engine-ashare-correctness.md`, `plan-industry-align-refactor-2026-09-18.md`, `plan-hygiene-backlog-2026-09-15.md`, `workflow-codex-handoff.md`.
> **Adversarial review note**: Three-lane review was BLOCKING; accepted host errata E-01..E-05 were backfilled in v0.2, and r1 merge-consensus MC-1..MC-5 are backfilled in this v0.3 draft.

---

## 0) One-line scope

Define, test, and document the already-existing fill-gate fork semantics (book-engine vs v7) so future edits cannot silently normalize them, while keeping all runtime behavior unchanged by default.

---

## 1) Why now (even though parts are already documented)

`plan-industry-align-refactor-2026-09-18.md` closed fill-clock naming and left deferred human cuts, but gate-fork semantics are still spread across multiple modules/tests and easy to misread as a bug instead of an intentional path fork.  
This ship makes that fork executable as contract (anchors + tests + docs), without reopening fill-clock behavior or replaying PR #108/#112 scope.

---

## 2) Verified as-built anchors (real file:line)

### 2.1 `limits=None` means different things by path

| Path | As-built behavior | Anchors |
|---|---|---|
| Book daily position loop | `limits is None` => `skip_unknown_board` and `continue` before lot/position sell logic | `backtest/research/csv_daily_backtest.py:321-323`, position loop starts at `:325` |
| Book minute position loop | Same early reject before minute scan/sell loop | `backtest/research/csv_minute_backtest.py:600-603`, position loop starts at `:609` |
| Book chase/pool helpers | Unknown board also rejected in shared loop utilities | `backtest/research/csv_simulate_loop.py:155-157`, `:260-261` |
| v7 first entry (trial buy at 14:55) | If `priced is None`, emit `skip_unknown_board`, no entry | `backtest/research/csv_minute_backtest_v7.py:390-391` |
| v7 already-held sell/add paths | Gate predicates can return "do not intercept" when `limits=None`, so flow may continue to sell/add attempt | `backtest/research/csv_minute_backtest_v7.py:342-353`, `:367-373`, `:402-405`; predicate definitions at `backtest/research/ashare_session.py:73-78` |

### 2.2 "Gate did not intercept" is not equal to "final fill happened"

| Phase | Evidence |
|---|---|
| Buy attempt can still fail after gate pass | v7 `_buy` returns `None` and logs `skip_cash` when shares/cash check fails (`backtest/research/csv_minute_backtest_v7.py:209-210`) |
| Sell attempt can still be non-fill after gate pass | v7 `_sell_lots` returns `0` when nothing T+1-eligible to sell (`backtest/research/csv_minute_backtest_v7.py:229-231`) |

### 2.3 Reuse existing T+1 / ST / halt tests (no redoing #108/#112)

| Contract area | Existing tests to reuse/extend |
|---|---|
| T+1 eligibility | `tests/test_ashare_session.py:15-18`, `tests/test_ashare_simulate_predicates.py:87` |
| Existing sell-side `limits=None` fork pin | `tests/test_ashare_simulate_predicates.py:119-134` (`test_none_limits_sell_side_records_existing_split`) |
| ST / board gating | `tests/test_csv_daily_backtest.py:883`, `:901`, `:925`, `:950`; `tests/test_csv_minute_backtest_v7.py:202` |
| Halt / zero-volume freeze + no-trade semantics | `tests/test_csv_daily_backtest.py:990+` (`test_zero_volume_placeholder_day_cannot_sell_or_buy_and_marks_last_close`) |
| Halt mark/equity semantics (mark only) | `tests/test_csv_daily_backtest.py:964`, `tests/test_daily_mark_cache.py:30-36` |
| Deferred cuts source (#112 context) | `docs/backtest/plan-industry-align-refactor-2026-09-18.md:129-132` (P1..P4) |

---

## 3) F-R* hard rule locks for this ship

| ID | Lock |
|---|---|
| **F-R1** | Keep repo positioning unchanged (research vectorized engine only; no LEBS/live stack blending). |
| **F-R2** | Keep PR #108 and #112 implemented behavior intact; do not reopen fill-clock behavior. |
| **F-R3** | Preserve existing fail-open/fail-closed mix exactly where it already exists (including v7 `limits=None` held-path behavior and ST-name semantics). |
| **F-R4** | Distinguish and test two states explicitly: **(a) gate did not intercept** vs **(b) trade filled**. Never collapse them. |
| **F-R5** | No Python production code edits by default. Allowed scope: docs + data-free contract tests only. |
| **F-R6** | No backtests, no lake reads, no production markers; CI checks must stay data-free. |
| **F-R7** | Do not fix/reinterpret ST PIT naming behavior in this ship; document as current fork. |
| **F-R8** | P1 is formally closed as A (2026-09-20): labels/tests/docs only, no fill-policy change. P2/P4 remain deferred; P3 δ cuts retain their separate authority and are not reopened here. |
| **F-R9** | Do not reintroduce Cerebro, qlib PortAna/Exchange, or cross-stack imports as "evidence". |
| **F-R10** | `IMPLEMENTATION_BASE` for any implementation branch must be explicit full 40-char SHA from `origin/master` tip; no inferred base via merge-base. |

---

## 4) P* human cuts (P1 closed as A, 2026-09-20)

| ID | Decision point | Human decision / current status |
|---|---|---|
| **P1** | Formal closure of the #112 fill-clock deferral | **Human GO: closed as A (2026-09-20)**. No real closing call auction model; `closing_call` / 14:57–15:00 are scan-window labels only. `_in_session`, scanners and fill eligibility stay as-built. **B** (minute touch skips 14:57–14:59) and **C** (skips 14:57–15:00) production behavior are **not authorized and forbidden this round**; expanding fill eligibility into those windows is also forbidden. |
| **P2** | #112 deferred trades output columns (`session_phase` / `price_rule`) | **A = keep deferred**, unchanged |
| **P3** | #112 deferred fees and ST PIT semantics changes | Original 2026-09-19 **A = keep deferred**; subsequent δ decisions are recorded separately in [engine correctness](engine-ashare-correctness.md). No δ production C merge is reopened here. |
| **P4** | #112 deferred touch-trigger vs mark coupling changes | **A = keep deferred**, unchanged |

P1 closes the 2026-09-19 keep-deferred stance as A; it does not reopen production behavior. P2/P4 remain deferred. Closure authority also appears in [fill-clock plan §5](plan-industry-align-refactor-2026-09-18.md) and [engine correctness](engine-ashare-correctness.md). Deliverable: docs SSOT + data-free pins in `tests/test_ashare_fill_clock.py`; retain the fixed `SIMULATE_HOT_PATH` import fence, add explicit phase-identifier absence and as-built scanner hm-comparison pins. No production Python edits, lake reads, backtests or production markers.

---

## 5) Non-goals

- No production behavior change.
- No Python runtime path edits in `backtest/research/*.py`.
- No fill-clock reopen, no new 14:57 execution policy.
- No "fix" of v7 ST naming or `limits=None` semantics.
- No backtest execution.
- No revalidation of #108/#112 implementation beyond contract anchoring.

---

## 6) Slices A -> B -> C (future implementation path; per-commit DoD)

### Slice A (commit A): fork-contract test additions (data-free only)

**Change scope**
- Add/extend tests that pin path-fork behavior for:
  - book early reject on `limits=None`,
  - reuse/extend `test_none_limits_sell_side_records_existing_split` as sell-side baseline pin,
  - v7 first-entry reject on `priced is None`,
  - v7 held-path (sell and **add**) `limits=None` gate-pass semantics,
  - post-gate non-fill outcomes (cash/eligibility failures) as separate assertions.

**Fork checklist (must be explicit, data-free, zero behavior change)**

1. **ST name cross-day retained fork**
   - Book side as-of resolver remains monotonic by day (`backtest/research/csv_common.py:85-107`) and consumed per session day (`backtest/research/csv_daily_backtest.py:291`; `backtest/research/csv_minute_backtest.py:565`).
   - v7 retains window-end flatten behavior from pool names (`backtest/research/ashare_session.py:81-85`, `:97`; loaded by `backtest/research/csv_minute_backtest_v7.py:546`, consumed as a flat `name` map at `:324`).
   - Reuse/add contract tests: `tests/test_csv_daily_backtest.py:909` and `:935` for book as-of behavior; add v7 cross-day name contract test to pin retained non-PIT fork.
2. **Zero-volume / missing-bar retained fork**
   - Daily loader filter: `_read_one_daily` drops zero-volume rows (`backtest/research/csv_daily_loader.py:83-84`), covered by `tests/test_csv_daily_backtest.py:73` and freeze/no-trade cases at `:990+`.
   - Minute loader filter: lake minute reader drops whole zero-volume days (`backtest/research/ashare_bars.py:369-371`), covered by `tests/test_csv_minute_backtest.py:27`.
   - Simulator no-bar freeze path remains distinct from loader filtering: book minute skips when day slice missing (`backtest/research/csv_minute_backtest.py:577-579`); v7 no-record path emits `skip_no_1455` for pool entry (`backtest/research/csv_minute_backtest_v7.py:315-317`, `:410-411`; covered by `tests/test_csv_minute_backtest_v7.py:110-113`).

**DoD**
- New/updated tests are data-free and deterministic.
- Tests prove both state layers: interception vs actual fill outcome.
- Slice A explicitly pins v7 held **add-side**: `limits=None` is not intercepted at gate layer, and a post-gate add failure is asserted as "not a fill" (F-R4).
- v7 held-add test landing uses **public** `simulate_v7` call path (not only private `_buy`); assert (a) gate not intercepted and (b) post-gate `skip_cash` / no-fill. If `tests/test_ashare_simulate_predicates.py` helper `run(..., **kwargs)` v7 branch drops kwargs (`:66-72`), adjust in tests-only or call `simulate_v7` directly.
- No production Python files changed.

### Slice B (commit B): docs as-built synchronization

**Change scope**
- Update `engine-ashare-correctness.md` with explicit fork matrix and caution text:
  - preserve fail-open where present,
  - do not treat OSS references as behavior evidence.

**DoD**
- Docs state "fork is intentional as-built contract" and separate from deferred cuts.
- Anchors point to verified file:line evidence.
- No behavior language implying a new fill model.

### Slice C (commit C): gate acceptance + freeze proof

**Change scope**
- Add a concise acceptance note (run record / handoff) proving frozen production files and data-free contract gates passed.

**DoD**
- Production file freeze diff check is clean versus `IMPLEMENTATION_BASE`.
- Required data-free contract gates pass.
- Any needed behavior change is escalated back to P* (not merged into this ship).

---

## 7) Linux/CI isomorphic acceptance (implementation PR; data-free only)

Use Linux/bash commands aligned with CI intent and the contract-gates runbook sequence:

```bash
set -euo pipefail

# 0) Base integrity
IMPLEMENTATION_BASE=41f3d11a34c665cc8a21b3e1d351b9e06b0466b5
[[ "$IMPLEMENTATION_BASE" =~ ^[0-9a-f]{40}$ ]]
git cat-file -e "$IMPLEMENTATION_BASE^{commit}"
git merge-base --is-ancestor "$IMPLEMENTATION_BASE" HEAD

# CI-equivalent prerequisite:
# - Use a controlled Python 3.12 environment with pytest and repo deps installed.
# - Bare system python without pytest does not constitute a plan failure.

# 1) Targeted quick tests (only touched contract tests, data-free)
python3 -m pytest -q -m "not production and not benchmark" \
  tests/test_ashare_session.py \
  tests/test_ashare_simulate_predicates.py \
  tests/test_csv_daily_backtest.py \
  tests/test_csv_minute_backtest.py \
  tests/test_csv_minute_backtest_v7.py \
  tests/test_daily_mark_cache.py \
  tests/test_ashare_simulate_import_fence.py

# 2) Data-free contract gates (real scripts under scripts/gates)
python3 scripts/gates/verify_oskh_data_contract.py
python3 scripts/gates/verify_data_path_ssot.py
python3 scripts/gates/verify_no_hardcoded_machine_paths.py
python3 scripts/gates/verify_tr_bridge_import_ssot.py

# 3) Freeze check: production files unchanged (must match §8 exactly)
FROZEN_PRODUCTION_FILES=(
  backtest/research/csv_daily_backtest.py \
  backtest/research/csv_minute_backtest.py \
  backtest/research/csv_minute_backtest_v7.py \
  backtest/research/csv_simulate_loop.py \
  backtest/research/ashare_session.py \
  backtest/research/market_layer.py \
  backtest/research/csv_common.py \
  backtest/research/csv_daily_loader.py \
  backtest/research/csv_ledger.py \
  backtest/research/ashare_bars.py \
  backtest/research/ashare_fees.py \
  backtest/research/strategy5_rules.py
)

git diff --exit-code "$IMPLEMENTATION_BASE" HEAD -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --cached --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"

# Optional guardrail: base->HEAD changed paths should stay in docs + named contract tests.
# git diff --name-only "$IMPLEMENTATION_BASE" HEAD
```

Pass criteria:
- exit code 0 for every executed command;
- no backtests run;
- no production-file diff versus `IMPLEMENTATION_BASE`.

---

## 8) Frozen production file table (default freeze)

| File | Freeze rationale |
|---|---|
| `backtest/research/csv_daily_backtest.py` | book daily fill/gate behavior |
| `backtest/research/csv_minute_backtest.py` | book minute fill/gate behavior |
| `backtest/research/csv_minute_backtest_v7.py` | v7 fork behavior (entry/held paths) |
| `backtest/research/csv_simulate_loop.py` | shared chase/pool gate handling |
| `backtest/research/ashare_session.py` | gate predicate primitives |
| `backtest/research/market_layer.py` | limit/ST leaf semantics used by gate computations |
| `backtest/research/csv_common.py` | shared `book_limit_prices` and calendar helpers on engine path |
| `backtest/research/csv_daily_loader.py` | zero-volume placeholder day filtering feeding freeze/no-trade behavior |
| `backtest/research/csv_ledger.py` | fill bookkeeping contracts |
| `backtest/research/ashare_bars.py` | session/bars boundary assumptions |
| `backtest/research/ashare_fees.py` | fee baseline untouched in this ship |
| `backtest/research/strategy5_rules.py` | force-sell timing stays as-built |

Only docs + data-free tests may change unless a human cut explicitly reopens behavior.
`FROZEN_PRODUCTION_FILES` in §7 must stay byte-identical to this table.

---

## 9) Short OSS analogy table (analogy only, not evidence)

| OSS analogy | Useful idea | Explicit limit in this repo |
|---|---|---|
| Order-state separation patterns (e.g., event-driven engines) | "Risk/gate pass" and "execution fill" are distinct states | Analogy only; behavior truth comes from this repo anchors/tests |
| Session-phase naming patterns | Label phases to reduce ambiguity | Labels do not authorize changing fill policy or reviving Cerebro/qlib PortAna |

---

## 10) Execution protocol

1. Keep this docs plan as the authority for the next implementation ship.
2. Human confirmed P1-P4 = A/A/A/A (2026-09-19, keep deferred); **P1 formally closed as A on 2026-09-20**, with P2/P4 still deferred. This closure uses the new base above and only the docs/test scope in §4; original slices above do not authorize new production behavior.
3. Implement only slices A->B->C with per-commit DoD.
4. If any production behavior change appears necessary, stop and open a new P* cut first.

---

## 11) Changelog

- **v0.4-P1-A-closure (2026-09-20 Asia/Shanghai)**: Human GO P1=A formally closes the 2026-09-19 fill-clock keep-deferred stance. No real closing call auction model; 14:57–15:00 / `closing_call` remain scan-window labels, with `_in_session` and fill eligibility as-built. B/C production filters and expansion into those windows are forbidden this round. Docs SSOT + data-free contracts only, zero production Python diff against `41f8df331ed25aad4616bde56c77ddb7025c91ee`; P2/P4 remain deferred and δ production C merges are not reopened.
- **v0.3-impl (2026-09-19)**: Implementation-start refresh: `IMPLEMENTATION_BASE` moved to `f46004d3bf3c9aa8314c5c3d0adcdebd730d9822` (current `origin/master` tip at execution start); status marked `Implemented-when-merged`.
- **v0.3-GO (2026-09-19)**: Human cut recorded: P1–P4 = A/A/A/A (keep deferred). Docs GO; feat A→B→C authorized under production freeze.
- **v0.3 (2026-09-19)**: Backfilled r1 merge-consensus MC-1..MC-5: unified §7 freeze commands with §8 via one `FROZEN_PRODUCTION_FILES` array (including `market_layer.py`/`csv_common.py`/`csv_daily_loader.py` plus worktree + staged diff checks), expanded Slice A with explicit ST-name cross-day and zero-volume/missing-bar retained-fork checklist, pinned v7 held-add test landing on public `simulate_v7` with gate-pass-vs-fill assertions, added CI-equivalent pytest environment prerequisite wording, and clarified P1-P4 wording as confirming prior deferral A (not reopening #112).
- **v0.2 (2026-09-19)**: Backfilled adversarial host errata E-01..E-05: replaced ghost gate scripts with real `scripts/gates/*` checks; corrected halt/zero-volume freeze anchors; added sell-side `limits=None` reuse pin reference; expanded frozen production table with verified on-path helpers (`market_layer.py`, `csv_common.py`, `csv_daily_loader.py`); and made Slice A DoD explicitly pin v7 held add-side fail-open plus gate-pass-vs-fill separation.
- **v0.1 (2026-09-19)**: Initial draft.
