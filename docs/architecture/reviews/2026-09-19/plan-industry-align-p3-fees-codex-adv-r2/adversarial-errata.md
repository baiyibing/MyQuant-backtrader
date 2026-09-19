# Host errata — P3 δ1 fee plan adversarial r2 (host-parallel Codex)

> Date: 2026-09-19  
> Input plan: `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md` **v0.2** (merged via PR #116)  
> Lanes: host-parallel independent `codex exec` (`gpt-6-astra` + `xhigh`) via host-parallel `codex exec` (launcher in PR #117: `scripts/run/run_codex_adversarial_lanes.py`)  
> Artifacts: `dissent-steelman.md` / `domain-safety.md` / `pattern-evidence.md` (all rc=0)  
> This host synthesis is **not** an independent vote; evidence over ballots.

## Lane verdicts (evidence summary)

| Lane | Verdict | Top themes |
|------|---------|------------|
| dissent-steelman | **BLOCKING** on “v0.2 ready to implement”; keeps δ1 single-ship | E-03 fee-wiring ≠ predicates; floor unit; freeze gaps |
| domain-safety | **REQUEST_CHANGES** on contract text; keeps δ1 | freeze claim overbroad; floor lot vs aggregate |
| pattern-evidence | **CONDITIONAL**; keeps δ1 | E-03 not closed; floor granularity; baseline drift |

**Host decision:** do **not** treat v0.2 as implementation-ready. Stay docs-only. Backfill plan to **v0.3**. Do **not** reopen P1/P2/P4 behavior. Do **not** pull ST PIT / ex-div economics into δ1 production work.

## Errata table (E-r2-*)

| ID | Sev | Sources | Issue | Host decision | v0.3 backfill |
|----|-----|---------|-------|---------------|---------------|
| **E-r2-01** | HIGH | D-01, PE-01 | Slice B / prior E-03 still treats limit/predicate asymmetry pins as fee-wiring proof; `test_ashare_fees` + ledger buy coverage ≠ daily override / minute default / v7 custom schedule wiring | **Accept** — mark prior E-03 **not closed**; Slice B must list explicit fee-wiring assertions (default identity, daily opt-in override, minute/SimState defaults, v7 `FeeSchedule` pass-through, floor+proportional cash oracles) | §7 Slice B + changelog; status note |
| **E-r2-02** | HIGH | D-02, DS-02, PE-02 | “min/floor” has no charge unit; book path can apply per-lot while v7 aggregates — same rates can yield different total commission | **Accept as-built docs** — document charge unit(s) with a two-lot numeric example; do **not** unify engines in δ1 | new §2.4 floor/charge-unit table |
| **E-r2-03** | HIGH | D-03, DS-01 | Freeze file list cannot substantiate “P1/P4 locked / zero behavior change” for session window / zero-volume filters outside the listed files | **Accept** — either expand freeze with cited deps **or** narrow claim to “listed production fee/simulate files unchanged”; prefer **narrow claim** + optional path-allowlist check for docs/tests-only deltas | §8/§9 claim language; keep P1/P2/P4 parked |
| **E-r2-04** | MED | D-04 | Fee participates in cash-gate before fill; v7 artifacts may not persist schedule/commission | **Accept docs** — state cash-gate path dependence + observability limits; no schema change in δ1 | short §2.5 observability note |
| **E-r2-05** | MED | D-05, PE-03 | §3/δ2 wording can read as E-R6 closing old P3 economics (shares / cash dividend) | **Accept wording** — E-R6 = ref-price rescale only; shares/cash-div residual stays explicitly deferred | roadmap / non-goals clarification |
| **E-r2-06** | MED | PE-04, all lanes | `IMPLEMENTATION_BASE` `c65b10d…` is ancestor of HEAD `9e2e9eb774345d0d0bf6075192739780a3f0ee47` (PR #116 merge); §8 tip-equality fails closed (correct) but blocks green acceptance until drift is recorded | **Accept** — for this docs r2 PR set `IMPLEMENTATION_BASE` to full 40-char HEAD after fetch; keep fail-closed tip check | header + §8 |

## Explicit non-goals (unchanged)

- No P1 14:57 window, P2 trades columns, P4 touch↔mark.
- No production Python in this docs ship.
- No stamp-tax booking line; research stays commission-as-built + boundary text.
- No Cerebro / PortAna revival; OSS analogy only.

## Next after v0.3

1. Human cut on P3.1–P3.3 (defaults still A/A/A unless reopened).
2. Optional multi-ai fan-out on v0.3 text.
3. Only then Slice A/B/C implementation (tests+docs; freeze proof).
