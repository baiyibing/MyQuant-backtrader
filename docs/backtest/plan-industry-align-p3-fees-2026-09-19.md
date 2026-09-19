# Plan: industry-align P3 delta1 fee contract (2026-09-19)

> **Status**: Proposed **v0.3** (host-parallel Codex adversarial r2 errata-applied; docs-only). Independent 3-lane `codex exec` completed; see review record. No production Python edits in this PR.
> **Main ship (single implementable ship this round)**: **delta1** — research fee contract + stamp-tax boundary clarity for CSV daily/minute engines.
> **IMPLEMENTATION_BASE (origin/master full SHA after fetch)**: `9e2e9eb774345d0d0bf6075192739780a3f0ee47`.
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


## 2.4) Floor / min-charge unit (as-built; E-r2-02)

Document, do not unify in δ1:

| Path | Charge unit (as-built) | Implication |
|------|------------------------|-------------|
| Shared book ledger sell/buy via `trade_commission` | Per ledger call / lot path as wired today | Two lots can pay floor twice |
| v7 path accepting `FeeSchedule` | Prefer documenting aggregate-vs-per-call from current call sites | Same rates may not match book total |

Slice B must include a **two-lot numeric oracle** that locks the *documented* as-built totals (not a forced cross-engine equality).

## 2.5) Cash-gate observability (E-r2-04)

Fees participate in cash sufficiency before a fill on shared/v7 paths. δ1 documents this path dependence; it does **not** add trades.csv commission columns or change fill prices. Acceptance may assert in-memory cash/commission oracles; artifact schema stays frozen unless a later human cut reopens P2.

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

| ID | Decision point | Default recommendation | As-built evidence to preserve |
|---|---|---|---|
| **P3.1** | Research default schedule: keep bilateral 10bp vs move default to qlib PortAna 5/15bp+min5 | **A = keep current `BILATERAL_10BP` default** | `ashare_fees.py:53-55`, `engine-ashare-correctness.md:13` |
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

Prior adversarial E-03 / quick predicate pins are **not** sufficient fee-wiring proof (**E-r2-01**).

- Extend/add tests to pin:
  - default schedule identity (`DEFAULT_SCHEDULE is BILATERAL_10BP`),
  - formula parity on buy/sell charge points used by ledger/shared loop,
  - **daily** opt-in qlib-cost override actually reaches charge sites (two-state),
  - **minute** path inherits documented SimState/default rates,
  - **v7** custom `FeeSchedule` pass-through on buy/sell/simulate,
  - **floor charge unit** two-lot oracle per §2.4 (as-built totals),
  - cash-gate interaction oracle where cheap to assert in-memory (**E-r2-04**).
- Limit/predicate asymmetry tests may remain, but must not be labeled as fee-wiring closure.
- Keep all tests synthetic/data-free; no lake reads.

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

IMPLEMENTATION_BASE=9e2e9eb774345d0d0bf6075192739780a3f0ee47
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

# 1) Targeted quick tests (delta1 contract surface, data-free)
python3 -m pytest -q -m "not production and not benchmark" \
  tests/test_ashare_fees.py \
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
- No backtests are run.
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

- **v0.3 (2026-09-19)**: Host-parallel Codex adversarial r2 (dissent-steelman / domain-safety / pattern-evidence, all rc=0). Backfilled E-r2-01..06: reopen fee-wiring Slice B requirements; document floor charge unit; narrow freeze claim; cash-gate observability; E-R6 residual wording; refresh `IMPLEMENTATION_BASE` to current master tip. Record: [codex-adv-r2](../architecture/reviews/2026-09-19/plan-industry-align-p3-fees-codex-adv-r2/). No production/test code edits; no backtests.
- **v0.2 (2026-09-19)**: Applied adversarial errata E-01..E-05: removed ghost acceptance scripts in §8, tightened stamp-tax boundary wording to commission-only as-built research booking, added asymmetry pin test to quick suite, hardened `IMPLEMENTATION_BASE` tip check against fetched `origin/master`, and expanded freeze file set for P1/P2/P4 lock safety.
- **v0.1 (2026-09-19)**: Initial docs-only P3 delta1 plan. Selects exactly one main ship (fee contract), parks P1/P2/P4, sets explicit `IMPLEMENTATION_BASE`, and defines data-free acceptance/freeze protocol.
