# Plan: industry-align P3 delta1 fee contract (2026-09-19)

> **Status**: Proposed **v0.3.2** + **human GO 2026-09-19**: P3.1/P3.2/P3.3 = **A/A/A** (keep defaults). Multi-ai r1 consensus GO-WITH-NITS; MC-1/MC-2 errata applied. Docs-only until Slice A/B/C. No production Python edits in this PR.
> **Main ship (single implementable ship this round)**: **delta1** — research fee contract + stamp-tax boundary clarity for CSV daily/minute engines.
> **IMPLEMENTATION_BASE (origin/master full SHA after fetch)**: `f548cc2ff808e7ecd5357e4d3786a62c76d8f8c5`.
> **Host intent lock**: Explicitly park **P1** (14:57 fill window), **P2** (trades columns), **P4** (touch↔mark coupling) this round.
> **Default recommendation**: zero behavior change (document as-built; add/extend data-free tests only).
> **Adversarial r2 record**: [codex-adv-r2](../architecture/reviews/2026-09-19/plan-industry-align-p3-fees-codex-adv-r2/) — host errata E-r2-01..06; lanes dissent-steelman / domain-safety / pattern-evidence (all rc=0).

---

## 0) One-line scope

Make research-engine fee semantics explicit and testable (FeeSchedule / defaults / asymmetry / floor behavior), while keeping current fill prices, reasons, shares, and NAV behavior unchanged by default and keeping stamp/transfer outside research hot path.

---

## 1) Why this ship now

Prior fill-clock and fill-gates plans already closed other fronts and kept deferred cuts parked:

- `docs/backtest/plan-industry-align-refactor-2026-09-18.md:131-132` records P3/P4 as deferred and non-goals for that ship.
- `docs/backtest/plan-industry-align-next-2026-09-19.md:3` confirms P1-P4 = A/A/A/A (keep deferred), and `:77-80` keeps P1/P2/P3/P4 as separate deferred decisions.
- `docs/backtest/engine-ashare-correctness.md:13` already states fee SSOT headline (default bilateral 10bp; qlib PortAna variant) but without a consolidated delta1 contract table.

So this round chooses only one main implementable ship: **delta1 fee contract**, and parks all others.

---

## 2) Verified as-built anchors (fee SSOT + consumption)

### 2.1 Fee SSOT module anchors

| Contract item | As-built anchor |
|---|---|
| Fee formula function | `backtest/research/ashare_fees.py:24` `trade_commission(notional, rate, min_cost)` |
| Structured schedule type | `backtest/research/ashare_fees.py:34` `FeeSchedule` |
| Research default schedule | `backtest/research/ashare_fees.py:53` `BILATERAL_10BP = FeeSchedule(COMMISSION, COMMISSION, 0.0)` |
| qlib PortAna schedule | `backtest/research/ashare_fees.py:54` `QLIB_PORTANA = FeeSchedule(QLIB_OPEN_COST, QLIB_CLOSE_COST, QLIB_MIN_COST)` |
| Module default pointer | `backtest/research/ashare_fees.py:55` `DEFAULT_SCHEDULE = BILATERAL_10BP` |
| Existing unit tests | `tests/test_ashare_fees.py:10-24` |

### 2.2 How CSV engines consume this today

| Path | As-built behavior | Anchors |
|---|---|---|
| Daily engine runtime override path | Daily supports optional qlib-cost override (buy 5bp / sell 15bp / min 5) and writes rates into `SimState` when provided | `backtest/research/csv_daily_backtest.py:230-232`, `:272-280`, `:658-660`, `:683-685` |
| Minute engine default path | Minute `simulate` initializes state via shared loop and does not set fee override knobs in this file; fee rates come from `SimState` defaults | `backtest/research/csv_minute_backtest.py:549`; `backtest/research/csv_simulate_loop.py:102`; `backtest/research/csv_ledger.py:87-89` |
| Ledger charge points (daily/minute shared) | Commission is charged in shared buy/sell ledger paths via `trade_commission` | `backtest/research/csv_ledger.py:15-20`, `:211`, `:244` |
| Per-name pool cash precheck uses same formula | Shared loop precheck uses `trade_commission` for cash sufficiency | `backtest/research/csv_simulate_loop.py:27`, `:287-289` |
| v7 explicit typed fee schedule | v7 imports `DEFAULT_SCHEDULE, FeeSchedule`, and buy/sell/simulate accept `fee: FeeSchedule = DEFAULT_SCHEDULE` | `backtest/research/csv_minute_backtest_v7.py:24`, `:204`, `:225`, `:279` |

### 2.3 Boundary: live broker fee policy must stay out of research hot path

- Import fence rejects `trade_fee_policy` in simulate hot path: `tests/test_ashare_simulate_import_fence.py:46-48`.
- Alias/relative cases are explicitly tested: `tests/test_ashare_simulate_import_fence.py:70-76`.
- `ashare_fees` is already in the enumerated hot-path list: `tests/test_ashare_simulate_import_fence.py:13-25`.

This is the existing boundary to preserve: research fee SSOT stays local to `backtest/research/ashare_fees.py`; live broker fee logic remains out-of-path.

---


## 2.4) Floor / min-charge unit (as-built; E-r2-02 / MC-2)

Document, do not unify in δ1. Charge granularity is **per function call**, not per symbol/day.

| Path | Charge unit (as-built) | Implication |
|------|------------------------|-------------|
| Shared book ledger sell/buy via `trade_commission` | Per ledger `_sell` / `_buy` call (one Position/lot path) | Two lots can pay floor twice |
| v7 `_sell_lots` / buy via `FeeSchedule` | Aggregate notional for that call, then one `credit_sell` / `debit_buy` | Same rates may not match book total |

**Locked two-lot numeric oracle** (T+1-sellable lots; sell 15bp + min 5 ≡ `QLIB_PORTANA` sell side; 2×100 shares @ 10):

| Call pattern | Commission | Cash increase |
|---|---:|---:|
| Book `_sell` ×2 (each lot separately) | 10 | 1990 |
| v7 one `_sell_lots` (both lots in one call) | 5 | 1995 |
| v7 two `_sell_lots` (one lot each call) | 10 | 1990 |

Default `BILATERAL_10BP` (min=0) yields 2 on both paths — **does not expose the floor fork**. Slice B oracle must use `QLIB_PORTANA` / explicit 15bp+min5. Anchors: `csv_ledger.py` `_sell` + `csv_minute_backtest_v7.py` `_sell_lots` → `fee.credit_sell`.

## 2.5) Cash-gate observability (E-r2-04 / MC-nits)

Fees participate in cash sufficiency before a fill on shared/v7 paths. δ1 documents this path dependence; it does **not** change fill prices.

**As-built artifact note (do not confuse with P2):** book-path `trades` dict already has a `commission` field and `write_run_artifacts` dumps it to `trades.csv`. v7 `_event` has **no** commission column. δ1 does **not** alter book schema and does **not** add a commission column to v7 events. Memory oracles may assert book `trades[].commission`. EOD_MARK rows use `commission: 0.0` and must not be treated as sell charges. P2 remains parked (no `session_phase` / `price_rule` columns).

## 3) Delta roadmap table (P3 split; exactly one main ship selected)

| Delta ship | Scope summary | This PR |
|---|---|---|
| **delta1 (main ship this round)** | Research fee contract + stamp-tax boundary clarity: `FeeSchedule`, `BILATERAL_10BP`, `QLIB_PORTANA`, `trade_commission`, and daily/minute/v7 consumption map | **YES (plan only)** |
| delta2 | Ex-div / lot-cost rescale as-built contract refinements (note E-R6 already covers core behavior; do not redo) | **NOT this PR** |
| delta3 | ST PIT alignment (book as-of vs v7 window-end semantics) | **NOT this PR** |
| delta4 | v7 `limits=None` fail-open policy changes (already contractualized in next plan) | **NOT this PR** |
| delta5 | Volume participation cap design | **NOT this PR** |

---

## 4) F-R* hard locks for delta1

| ID | Lock |
|---|---|
| **F-R1** | Docs/tests only by default; no production behavior change to fill price, reason, shares, NAV. |
| **F-R2** | Keep research default as current unless a later human cut reopens it (`BILATERAL_10BP` remains default). |
| **F-R3** | Document current buy/sell asymmetry and min-floor behavior exactly as built; do not silently normalize schedules across engines. |
| **F-R4** | Research path remains commission-only booking at current call sites; do not invent a separate stamp-tax runtime booking line. |
| **F-R5** | Preserve boundary: no `trade_fee_policy` import into research simulate hot path. |
| **F-R6** | Keep P1/P2/P4 out-of-scope in this ship; no 14:57 eligibility changes, no `trades.csv` schema changes, no touch<->mark coupling edits. |
| **F-R7** | Keep all gates data-free for this ship; no backtests and no lake-dependent validation requirements. |
| **F-R8** | `IMPLEMENTATION_BASE` must be explicit full 40-char SHA from fetched `origin/master` tip (no inferred merge-base substitution). |

---

## 5) P* human cuts (delta1 only)

> **Human GO recorded 2026-09-19 (Asia/Shanghai):** P3.1=A, P3.2=A, P3.3=A — keep plan defaults; proceed to multi-ai fan-out then Slice A→B→C docs/tests ship.

| ID | Decision point | Default recommendation | As-built evidence to preserve |
|---|---|---|---|
| **P3.1** ✅ Human GO 2026-09-19 | Research default schedule: keep bilateral 10bp vs move default to qlib PortAna 5/15bp+min5 | **A = keep current `BILATERAL_10BP` default** | `ashare_fees.py:53-55`, `engine-ashare-correctness.md:13` |
| **P3.2** | Stamp-tax boundary wording in research docs (explicit line vs boundary-only contract text) | **A = boundary-only wording; keep as-built commission booking and no new stamp line** | `ashare_fees.py:9-10`; ledger charges via shared `trade_commission` at buy/sell call-sites (`csv_ledger.py:211`, `:244`) |
| **P3.3** | Boundary enforcement: live broker fee policy vs research fee SSOT | **A = keep strict fence (no hot-path import)** | `test_ashare_simulate_import_fence.py:46-48`, `:70-76` |

---

## 6) Non-goals (explicitly parked this round)

- **E-R6 vs old P3 economics (E-r2-05):** E-R6 covers reference-price rescale only; shares/cash-dividend / economic NAV residuals remain deferred — do not describe them as already closed by E-R6.
- **No P1** changes: do not edit 14:57 fill window behavior.
- **No P2** changes: do not add `trades.csv` columns.
- **No P4** changes: do not couple/decouple touch-trigger and marking semantics in runtime code.
- No rewrite of v7 `limits=None` policy.
- No ex-div behavioral redesign.
- No volume participation cap implementation.
- No backtest execution in this ship.

---

## 7) Slices A -> B -> C for delta1 (future implementation path, not this docs-only PR)

### Slice A (contract text + anchor consolidation)

- Consolidate fee contract table in backtest docs (as-built defaults, asymmetry, floor behavior).
- Add explicit "research-only fee SSOT boundary" paragraph with import-fence anchors.
- No Python production edits.

### Slice B (data-free contract tests)

Prior adversarial E-03 / quick predicate pins are **not** sufficient fee-wiring proof (**E-r2-01** / **MC-1**).

**Test landing (pick one; must appear in §8):** extend `tests/test_ashare_fees.py` **or** add `tests/test_ashare_fee_wiring.py`. Private `_sell` / `_buy` may be imported for local numeric oracles, but cannot replace public `simulate` / `simulate_v7` wiring pins.

- Extend/add tests to pin:
  - **dual default pointers:** `DEFAULT_SCHEDULE is BILATERAL_10BP` (v7/module) **and** `SimState()` `(buy_cost_rate, sell_cost_rate, min_cost) == (COMMISSION, COMMISSION, 0.0)` with numeric parity to the schedule (book/minute do **not** read `FeeSchedule` objects),
  - formula parity on buy/sell charge points used by ledger/shared loop,
  - **daily** opt-in qlib-cost override actually reaches charge sites (two-state) via `simulate(..., buy_cost_rate=..., sell_cost_rate=..., min_cost=...)`,
  - **minute** path inherits documented SimState/default rates (synthetic `simulate`; assert post-trade commissions),
  - **v7** custom `FeeSchedule` pass-through on buy/sell/`simulate_v7(..., fee=...)` (do not fake pass-through by monkeypatching module `DEFAULT_SCHEDULE`),
  - **floor charge unit** two-lot oracle per §2.4 locked totals (use `QLIB_PORTANA` / 15bp+min5),
  - cash-gate interaction oracle: cash exactly enough vs one fen short; reject leaves cash/positions/trades unchanged (**E-r2-04**).
- Limit/predicate asymmetry tests may remain, but must not be labeled as fee-wiring closure.
- Keep all tests synthetic/data-free; no lake reads. **F-R7 clarification:** ban CLI/lake backtests; **allow** in-memory synthetic `simulate` / `simulate_v7` unit tests.

### Slice C (acceptance + freeze proof)

- Record command-level acceptance results and production freeze checks.
- Any required behavior change must stop and reopen human cut (P3.*), not be folded into delta1.

---

## 8) Linux/CI isomorphic acceptance (real scripts only; data-free)

Notes:
- This docs-only PR does not execute these commands.
- When delta1 implementation runs, use real scripts only (no ghost script names).

```bash
set -euo pipefail

IMPLEMENTATION_BASE=f548cc2ff808e7ecd5357e4d3786a62c76d8f8c5
[[ "$IMPLEMENTATION_BASE" =~ ^[0-9a-f]{40}$ ]]
git fetch origin master
CURRENT_MASTER="$(git rev-parse origin/master)"
[[ "$CURRENT_MASTER" =~ ^[0-9a-f]{40}$ ]]
if [[ "$CURRENT_MASTER" != "$IMPLEMENTATION_BASE" ]]; then
  echo "origin/master moved to $CURRENT_MASTER; keep IMPLEMENTATION_BASE pinned and document drift before changing it."
  exit 1
fi
git cat-file -e "$IMPLEMENTATION_BASE^{commit}"
git merge-base --is-ancestor "$IMPLEMENTATION_BASE" HEAD

# Interpreter: use project venv / CI setup-python (AGENTS.md). Bare system python3 without pytest/pandas is not a plan failure.
# 1a) Fee-wiring contract surface (MUST include Slice B landing file; formula-only is not closure)
python3 -m pytest -q -m "not production and not benchmark" \
  tests/test_ashare_fees.py \
  tests/test_ashare_fee_wiring.py
# If wiring pins live only in test_ashare_fees.py, drop the second path; do not omit wiring coverage.
# 1b) Fence + predicate side evidence (NOT labeled fee-wiring closure)
python3 -m pytest -q -m "not production and not benchmark" \
  tests/test_ashare_simulate_import_fence.py \
  tests/test_ashare_simulate_predicates.py

# 2) Contract gates (runbook-aligned real scripts)
python3 scripts/gates/verify_oskh_data_contract.py
python3 scripts/gates/verify_data_path_ssot.py
python3 scripts/gates/verify_no_hardcoded_machine_paths.py
python3 scripts/gates/verify_tr_bridge_import_ssot.py

# 3) Production freeze proof
FROZEN_PRODUCTION_FILES=(
  backtest/research/ashare_fees.py
  backtest/research/csv_ledger.py
  backtest/research/csv_simulate_loop.py
  backtest/research/csv_daily_backtest.py
  backtest/research/csv_minute_backtest.py
  backtest/research/csv_minute_backtest_v7.py
  backtest/research/ashare_session.py
  backtest/research/market_layer.py
  backtest/research/csv_common.py
  backtest/research/csv_artifacts.py
)

git diff --exit-code "$IMPLEMENTATION_BASE" HEAD -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --cached --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
```

Pass criteria:

- All executed commands exit with code 0.
- No CLI/lake backtests are run; synthetic in-memory simulate unit tests are allowed.
- Fee-wiring pytest invocation includes the Slice B landing file(s); predicates/fence alone are not closure.
- No ghost script names are invoked.
- Production freeze diffs remain zero unless a new human cut reopens behavior.

---

## 9) Frozen production file table (delta1 default)

| File | Freeze reason |
|---|---|
| `backtest/research/ashare_fees.py` | Fee SSOT semantics must not drift in docs-only ship. |
| `backtest/research/csv_ledger.py` | Shared buy/sell commission debit/credit behavior. |
| `backtest/research/csv_simulate_loop.py` | Shared pool/chase cash precheck behavior. |
| `backtest/research/csv_daily_backtest.py` | Daily qlib-cost override wiring and simulate behavior. |
| `backtest/research/csv_minute_backtest.py` | Minute path should continue inheriting ledger defaults unless reopened. |
| `backtest/research/csv_minute_backtest_v7.py` | Explicit `FeeSchedule` default usage on v7 path. |
| `backtest/research/ashare_session.py` | T+1/limit predicates and session semantics must stay unchanged in delta1. |
| `backtest/research/market_layer.py` | Board/ST limit-band SSOT; unknown-board `None` behavior must not drift. |
| `backtest/research/csv_common.py` | Shared book-path limit wrapper semantics should remain unchanged. |
| `backtest/research/csv_artifacts.py` | Keep `trades.csv` schema untouched (P2 lock). |

Default editable surface for delta1: docs + data-free tests only.

**Freeze claim scope (E-r2-03):** zero-diff on the listed production files proves only those paths are untouched. It does **not** by itself prove P1 session-window or unrelated loader filters are immutable. P1/P2/P4 stay parked; do not widen this ship to edit them. Optional acceptance: path-allowlist that new commits only touch docs/ + data-free tests/ + the listed freeze set.

---

## 10) Short OSS analogy table (analogy only, not behavior evidence)

| Analogy | Useful idea | Limit in this repo |
|---|---|---|
| Exchange simulators with configurable commission schedules | Separate policy object for fee rates/floor | Behavior truth must come from repo anchors/tests, not external API semantics |
| Broker adapters that model taxes separately | Keep policy decomposition explicit | Do not add new stamp-tax runtime line without explicit human cut |

---

## 11) Changelog

- **v0.3.2 (2026-09-19)**: Multi-ai r1 host consensus GO-WITH-NITS. MC-1: §8 must run Slice B fee-wiring landing file; predicates/fence are side evidence; allow synthetic simulate under F-R7. MC-2: lock §2.4 two-lot numeric oracle (book 10/1990 vs v7-one-call 5/1995 under QLIB_PORTANA). Dual default pointers + §2.5 as-built commission-column wording. Human A/A/A unchanged; no production edits. Record: [plan-industry-align-p3-fees-r1](../architecture/reviews/2026-09-19/plan-industry-align-p3-fees-r1/).
- **v0.3.1 (2026-09-19)**: Human GO on P3.1/P3.2/P3.3 = A/A/A; refresh `IMPLEMENTATION_BASE` to post-PR #119 master tip; start classic multi-ai fan-out.
- **v0.3 (2026-09-19)**: Host-parallel Codex adversarial r2 (dissent-steelman / domain-safety / pattern-evidence, all rc=0). Backfilled E-r2-01..06: reopen fee-wiring Slice B requirements; document floor charge unit; narrow freeze claim; cash-gate observability; E-R6 residual wording; refresh `IMPLEMENTATION_BASE` to current master tip. Record: [codex-adv-r2](../architecture/reviews/2026-09-19/plan-industry-align-p3-fees-codex-adv-r2/). No production/test code edits; no backtests.
- **v0.2 (2026-09-19)**: Applied adversarial errata E-01..E-05: removed ghost acceptance scripts in §8, tightened stamp-tax boundary wording to commission-only as-built research booking, added asymmetry pin test to quick suite, hardened `IMPLEMENTATION_BASE` tip check against fetched `origin/master`, and expanded freeze file set for P1/P2/P4 lock safety.
- **v0.1 (2026-09-19)**: Initial docs-only P3 delta1 plan. Selects exactly one main ship (fee contract), parks P1/P2/P4, sets explicit `IMPLEMENTATION_BASE`, and defines data-free acceptance/freeze protocol.
