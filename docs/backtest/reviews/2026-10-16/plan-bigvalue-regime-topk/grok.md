# Grok review — 2026-10-16

**Verdict: GO-WITH-NITS**

Target: [PR #480](https://github.com/baiyibing/MyQuant-backtrader/pull/480) tip `f561646` (`fix: reuse as-built open bucket gate for regime flatten`) on `feat/bigvalue-regime-topk-block-new-20261016`. Scope: Human full-switch cut (P1–P15 as default-OFF switches) + shared `bigvalue_regime` infrastructure; topk_dropout first consumer. Codex amended GO for the same scope. Do not merge.

## Defect-first checks

| # | Check | Result |
|---|---|---|
| 1 | Lead-lag R1 (no same-day look-ahead) | **Pass.** `confirmed_days` labels execution day `D` from exact prior book sessions only (`calendar[i-1]` state; confirm window `calendar[i-confirm_days:i]`). No asof/stale row; noncalendar signal dates in range hard-fail. |
| 2 | Defaults off / R11 off-path | **Pass.** CLI defaults: block-new/flatten OFF, golden-mult None; engines require `bigvalue_regime` for any behavior flag. Off-path kwargs omit regime; fixture trades/equity/stats unchanged aside from HELP_LOCK prose. |
| 3 | Drive-letter path SSOT | **Pass.** Explicit `--bigvalue-regime-file` only; no `E:/` / drive defaults in loader or CLI. |
| 4 | Flatten / golden wired | **Pass.** Not stubs: daily open flatten + limit-down pending; minute legacy + chronological via `regime_flat` / pending; golden via `golden_cash_fraction` → `cash_deploy_frac` with clamp `min(1.0, 0.95*M)`. |
| 5 | Shared module reusable | **Pass.** `bigvalue_regime.py` owns load/state/confirm/gate/flatten/cash; engines take kwargs; topk_dropout is CLI consumer only; other books refuse flags. |
| 6 | Fail-closed tests | **Pass.** `tests/test_bigvalue_regime.py` covers warmup/hole/equality, missing file/columns, P1 index refuse, score_exit refuse, flatten priority/OFF/T+1, 09:30 + limit-down/missing-open defer, golden clamp. |
| 7 | HELP_LOCK / tracker honesty | **Mostly pass; see nits.** HELP_LOCK and summary fixtures match full-switch. Tracker full-switch addendum accurate; one stale doc-map row. |

## As-built hm rewrite (`f561646`)

Prior tip introduced `cur_hm == 9*60+30` / `int(hm[idx]) == 570` for regime flatten and failed `test_scan_held_day_python_hm_comparisons_stay_as_built`. Fix **reuses** the existing session-open gate `int(self.hm[idx]) != 9 * 60 + 30` (and folds rejected flatten into that path). Allowlist **unchanged** — correct choice vs expanding comparisons. CI `pytest-and-gates` on `f561646`: **success**.

## Binding cuts (spot)

- P1 index coexistence refuses; P13 score_exit refuses any explicit bigvalue flag; other CLI books refuse.
- P7/P9 missing/warmup/under-confirm block opens (even flatten-only/golden-only); no flatten/mult on those days.
- P8 equality → `allowed_equal` (opens allowed), breaks confirmation streak.
- P10/P11/P12 stop → flatten → dropout; next open / exact 09:30; limit-down engine defer, no Q7.
- P14 parquet MA only; trailing-zero re-drop; P15 daily+minute shared day-frequency gate.

## Nits

1. **LOW — tracker doc-map stale.** `docs/backtest/topk-joint-research-tracker-2026-09-22.md` §11 table still describes the plan as「未人裁，非 impl GO」while Q12 + full-switch addendum and Codex GO supersede. Historical revision rows are fine; the live doc-map row should say switches shipped / see §14 + this review, or readers bounce.
2. **LOW — no real-lake / alpha.** Correct for this PR; do not treat fixture greens as regime alpha. Q8 remains open.

No HOLD blockers. No same-day look-ahead, no default-on surprise, no path SSOT leak, flatten/golden not stubs.

## CI

- Tip reviewed: `f561646b064d52f7889fa8f3463a084a4a396474`
- `pytest-and-gates`: **success** (completed 2026-10-16 ~18:23 CST)

## Disposition

GO-WITH-NITS to merge after Human ack of nits (or a tiny tracker doc-map follow-up). No merge by this review. No second PR.
