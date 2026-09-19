# plan-industry-align-p3-fees v0.1 -> v0.2 host errata

Date: 2026-09-19  
Plan under review: `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md`

## Lane verdict roll-up

| Lane | Verdict | Host note |
|---|---|---|
| dissent-steelman | BLOCKING | Correctly flags non-runnable §8 bundle commands and wording drift risk. |
| domain-safety | BLOCKING | Correctly flags fail-closed acceptance gap and under-specified tip-lock enforcement. |
| pattern-evidence | CONDITIONAL | Confirms §3 scoping is good; blocks on ghost scripts and wording precision. |

## Host spot-check evidence (`file:line`)

- Ghost commands appear in plan §8: `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:160`, `:163`; files absent on branch.
- Real CI contract gates are existing `scripts/gates/verify_*.py`: `.github/workflows/python-tests.yml:40-43`.
- Research trade booking uses commission-only fields: `backtest/research/csv_ledger.py:211`, `:229`, `:244`, `:254`.
- Research boundary keeps stamp/transfer outside this path: `backtest/research/ashare_fees.py:9-10`.
- Daily override vs minute/v7 asymmetry is real: `backtest/research/csv_daily_backtest.py:230-232`, `:272-280`, `:683-685`; `backtest/research/csv_minute_backtest.py:520`, `:549`; `backtest/research/csv_minute_backtest_v7.py:24`, `:279`.
- `origin/master` fetched in this review still matches plan base SHA `c65b10dd6d26342bd9ec1cbed5465d875f82470f`.

## Errata table (E-01..)

| ID | Severity | Issue | Host decision | v0.2 backfill |
|---|---|---|---|---|
| E-01 | BLOCKING | §8 cites non-existent bundle scripts | Accept | Replace with real `scripts/gates/verify_*.py` only; remove ghost bundle steps |
| E-02 | HIGH | Stamp-tax wording overstates as-built research path | Accept | Rephrase delta1 + P3.2 to "fee contract + stamp-tax boundary", explicitly commission-only booking |
| E-03 | MEDIUM | Asymmetry claim not pinned in quick tests | Accept | Add `tests/test_ashare_simulate_predicates.py` to targeted quick tests |
| E-04 | MEDIUM | F-R8 intent (tip provenance) under-enforced in shell checks | Accept | Add explicit `git fetch origin master` + equality check against `origin/master` |
| E-05 | MEDIUM | Scope lock could drift via unfrozen helper paths | Accept | Expand freeze file set with `ashare_session.py`, `market_layer.py`, `csv_common.py`, `csv_artifacts.py` |

## Blocking findings status

- **Resolved in v0.2 draft text**: E-01.
- **No remaining blockers after v0.2 textual patch**; residuals are guardrail-strengthening items (E-02..E-05) incorporated as preventive edits.
