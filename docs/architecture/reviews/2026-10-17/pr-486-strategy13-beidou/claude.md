# Claude review — PR #486 strategy13 Beidou (plan #485)

VERDICT=GO-WITH-NITS

Verdict: **GO-WITH-NITS**

Date: 2026-10-17 (Asia/Shanghai). Reviewed tip
`5f93b1ccc1c13188283957c6cf5bd16755c6ad13`
(`feat/strategy13-beidou-s1`, PR
[#486](https://github.com/baiyibing/MyQuant-backtrader/pull/486)).
Implements merged plan
[`docs/backtest/plan-strategy13-beidou-volume-start-2026-10-17.md`](../../../backtest/plan-strategy13-beidou-volume-start-2026-10-17.md)
(#485) against
[`docs/backtest/source-strategy13-beidou-manual-2026-10-11.md`](../../../backtest/source-strategy13-beidou-manual-2026-10-11.md).

`claude` CLI hung (~5+ min, unrecognized model `glm-5.3`, no artifact);
this review was completed in-process per the delegated brief. No merge.
No encode fixes in this commit (review artifact only).

## 1. Checks

| Check | Result |
| --- | --- |
| Human cut 1: base+pyramid; cash×20% hard cap; no 2% risk | **Pass.** Fixed ¥10k base (`BASE_BUDGET`), `NAME_CAP=0.20`, CLI+`init_book` clamp `min(name_budget, cash×20%)`, whole-order `skip_cash` (no shrink). No risk-formula path. |
| Human cut 2: ×42 @ ×1.6, ×35 per +10%, ≤10 adds | **Pass.** `add_order` / engine buy; failed fills do not advance `adds`; `Params.max_adds` cannot exceed 10. |
| Human cut 3: no theme/regulatory/B-class; chip default-off | **Pass.** Exporter A-only predicates; `--chip-single-peak` default False; no B-class flag. |
| Plan S1 exporter (prior-20 vol, D→T, PIT float, refuse stock_pool) | **Pass.** `v.shift().rolling(20)`, next observed bar file, `merge_asof` backward, explicit `--pool-dir`. |
| Plan S2 TP tiers + 10% floor, 25% clear, three stops, skim | **Pass.** Tiers once on current shares; `tp_shares` floor; trail clear; hard/MA20/early close stops; cumulative net-realized skim via `profit_skim_equity` → 100% of each +20% rung to 600036; parking lots isolated from strategy exits. |
| Plan S3 HS300 MA60/120 | **Pass.** `load_book_index_gate` → prior-session caps 50%/30%; blocks opens/adds only; product `run()` loads fail-closed. |
| Fail-closed name_budget / skip_cash | **Pass.** Cap+cash+fee shortfall → `skip_cash`; industry whole-order test. |
| PENDING / HELP_LOCK / BOOKS | **Pass.** `version13` in `PENDING_BOOK_NAMES` and `BOOKS`, not `BOOK_NAMES`; HELP_LOCK digest frozen; `FORBIDDEN_DEFAULT_STOCK_POOL`. |
| Path-SSOT / no drive letters in PR diff | **Pass.** Roots via `resolve_*`; no `D:`/`E:` in strategy13 files. |
| Data-free tests + honesty | **Pass.** 37/37 strategy13 tests green under `/workspace/vanna312/bin/python`. Plan/PR state host lake smoke and ch.10 win-rate are not acceptance. |

## 2. Residuals (Codex-flagged; not HOLD)

1. **Daily vs minute fill/add timing.** Daily: pool/add at open; close exits queue for next open. Minute: pool at first open; adds on every `after_close`; TP/stops may fill per shared `FillConfig` (same-bar vs next-open). Path identity is not claimed — document when comparing daily/minute books.
2. **Skim entitlement edge cases.** Cumulative monotone entitlement + whole-lot unpaid residuals reuse 6.55 parking stack; tests cover rung thresholds and no-unrealized trigger. Residual unpaid lots under thin cash/limit are stack behavior, not a Beidou-specific contract break.

## 3. Nits (non-blocking)

1. **Medium — daily/minute add cadence asymmetry.** Minute can take multiple pyramid adds within one session as closes step thresholds; daily evaluates adds once at open. Intentional reuse of shared minute hooks, but HELP_LOCK / run notes should keep this explicit so operators do not treat daily≡minute as a regression.
2. **Low — chip concentration formula.** Optional path uses `(p95−p05)/(p95+p05) ≤ 0.20` plus price above mode. Default-off; if chip is ever enabled as acceptance, confirm against the manual's「90%集中度」definition before turning it on.
3. **Low — `name_budget=1e99` book sentinel.** Relies on `init_book` / CLI `cash_total×20%` clamp. Direct `apply_csv_strategy("v13")` without capital context is fine in tests (init clamps to `st.cash`), but a comment near `register(... name_budget=1e99)` would prevent future “raise the cap” overrides from looking intentional.
4. **Low — exporter full-universe scan.** Host runs walk every `symbol=*/data.parquet` under the period root. Correctness OK; cost is operator concern, not a merge blocker.
5. **Info — host lake / ch.10 smoke still unrun.** Already honest in plan §6 / PR body (`OSKH_*` unset). Do not treat as acceptance or as a reason to HOLD.

## 4. Scope / shared surface

Shared diffs are narrow and gated: `init_book` + `profit_skim_equity` hook points, `after_open` optional minute callback, `version13` on cash-div / parking / index-gate allowlists. No golden regeneration; historical HELP_LOCKs untouched.

## 5. Verdict rationale

Human cuts and S1–S4 plan contracts are encoded; admission/pending/HELP_LOCK are correct; critical paths have data-free coverage; residuals are timing/ops honesty rather than fail-open or cut violations. **GO-WITH-NITS** — safe to merge after Human acknowledges nits (or a tiny follow-up doc note on daily≠minute add cadence). This review does **not** merge.
