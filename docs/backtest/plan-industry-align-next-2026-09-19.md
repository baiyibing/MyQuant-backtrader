# Plan: industry-align next (fill gates fork, zero-change default) (2026-09-19)

> **Status**: Draft for human cut (docs-only planning ship; not implemented).
> **Main ship (single theme)**: Contractualize A-share fill gates fork (`limits`, halt/zero-volume, ST name) between book-engine and v7 paths, with default **zero behavior change**.
> **IMPLEMENTATION_BASE (fact anchor)**: `41f3d11a34c665cc8a21b3e1d351b9e06b0466b5` (full 40-char SHA of `origin/master` at authoring time, and branch `HEAD` before this docs commit).
> **Business sources read**: `engine-positioning-ssot.md`, `engine-ashare-correctness.md`, `plan-industry-align-refactor-2026-09-18.md`, `plan-hygiene-backlog-2026-09-15.md`, `workflow-codex-handoff.md`.

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
| ST / board gating | `tests/test_csv_daily_backtest.py:883`, `:901`, `:925`, `:950`; `tests/test_csv_minute_backtest_v7.py:202` |
| Halt / zero-K freeze semantics | `tests/test_csv_daily_backtest.py:964`, `tests/test_daily_mark_cache.py:30-36` |
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
| **F-R8** | Keep deferred #112 cuts as separate ships unless explicitly reopened by human cut (default = keep deferred). |
| **F-R9** | Do not reintroduce Cerebro, qlib PortAna/Exchange, or cross-stack imports as "evidence". |
| **F-R10** | `IMPLEMENTATION_BASE` for any implementation branch must be explicit full 40-char SHA from `origin/master` tip; no inferred base via merge-base. |

---

## 4) P* human cuts (default recommendation: keep deferred / separate ship)

| ID | Decision point | Default recommendation |
|---|---|---|
| **P1** | #112 deferred `B/C` options that would change 14:57 fill behavior | **A = keep deferred** (separate ship) |
| **P2** | #112 deferred trades output columns (`session_phase` / `price_rule`) | **A = keep deferred** |
| **P3** | #112 deferred fees and ST PIT semantics changes | **A = keep deferred** |
| **P4** | #112 deferred touch-trigger vs mark coupling changes | **A = keep deferred** |

No P* is reopened by this docs-only ship.

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
  - v7 first-entry reject on `priced is None`,
  - v7 held-path "gate pass != guaranteed fill".

**DoD**
- New/updated tests are data-free and deterministic.
- Tests prove both state layers: interception vs actual fill outcome.
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
# 0) Base integrity
IMPLEMENTATION_BASE=41f3d11a34c665cc8a21b3e1d351b9e06b0466b5
[[ "$IMPLEMENTATION_BASE" =~ ^[0-9a-f]{40}$ ]]
git cat-file -e "$IMPLEMENTATION_BASE^{commit}"
git merge-base --is-ancestor "$IMPLEMENTATION_BASE" HEAD

# 1) Targeted quick tests (only touched contract tests, data-free)
python3 -m pytest -q -m "not production and not benchmark" \
  tests/test_ashare_session.py \
  tests/test_ashare_simulate_predicates.py \
  tests/test_csv_daily_backtest.py \
  tests/test_csv_minute_backtest_v7.py \
  tests/test_daily_mark_cache.py

# 2) Common package contract gates (runbook required)
python3 scripts/run_common_package_contract_gates.py

# 3) Stream execution bundle (run only if touched scope requires it)
# python3 scripts/run_stream_execution_contract_bundle.py

# 4) Freeze check: production files unchanged
git diff --exit-code "$IMPLEMENTATION_BASE" HEAD -- \
  backtest/research/ashare_session.py \
  backtest/research/csv_daily_backtest.py \
  backtest/research/csv_minute_backtest.py \
  backtest/research/csv_minute_backtest_v7.py \
  backtest/research/csv_simulate_loop.py \
  backtest/research/csv_ledger.py \
  backtest/research/strategy5_rules.py \
  backtest/research/ashare_bars.py \
  backtest/research/ashare_fees.py
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
| `backtest/research/csv_ledger.py` | fill bookkeeping contracts |
| `backtest/research/ashare_bars.py` | session/bars boundary assumptions |
| `backtest/research/ashare_fees.py` | fee baseline untouched in this ship |
| `backtest/research/strategy5_rules.py` | force-sell timing stays as-built |

Only docs + data-free tests may change unless a human cut explicitly reopens behavior.

---

## 9) Short OSS analogy table (analogy only, not evidence)

| OSS analogy | Useful idea | Explicit limit in this repo |
|---|---|---|
| Order-state separation patterns (e.g., event-driven engines) | "Risk/gate pass" and "execution fill" are distinct states | Analogy only; behavior truth comes from this repo anchors/tests |
| Session-phase naming patterns | Label phases to reduce ambiguity | Labels do not authorize changing fill policy or reviving Cerebro/qlib PortAna |

---

## 10) Execution protocol

1. Keep this docs plan as the authority for the next implementation ship.
2. Human confirms P1-P4 remain deferred (default A).
3. Implement only slices A->B->C with per-commit DoD.
4. If any production behavior change appears necessary, stop and open a new P* cut first.

