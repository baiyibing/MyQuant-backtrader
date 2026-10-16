# Codex review — 2026-10-16

Verdict: **GO-WITH-NITS**.

Scope allowed: **first slice = block-new-opens only**. Human authorized Codex review→impl on 2026-10-16; this overrides R13/header as the GO gate, without closing the remaining P* or Q8/Q12.

Reviewed full plan #478, tracker Q12, HELP_LOCK, add_topk_dropout_args, _run_kwargs_topk_dropout, make_eligible_buy / seat_ok and index_ma5_buy_days. Follow existing seat eligibility; do not touch ranking, sell logic or cash deployment.

Dependency verified: #475 merged 2026-10-16, origin/master contains c2a7b20e2eb8c98434c90f0a5ae2f8ca1e383d9f. scripts/data/bigdata_ma_cross.py requires explicit --csv; no drive default or drive probing remains. R9 dependency passes source review; run path gate with implementation.

Binding first-slice defaults: continuous state (R6), fast=5 / slow=10 (P6), confirm-days=2 (P4). Missing exact preceding signal session blocks new opens that day and continues (milder P7 alternative), never stale-asof fallback. Warmup / insufficient consecutive confirmation blocks (P9). Equality is neither death nor golden, breaks confirmation and permits opens on the equality day when history is valid; no force-flat. For non-equal states fewer than N consecutive same-state sessions blocks; both confirmed golden and equality allow, confirmed death blocks. Missing/nonfinite observations in the confirmation window block. Calendar is the existing book union daily-bar calendar including loaded prehistory; reject noncalendar parquet dates within its covered interval. T uses only exact S preceding T; confirmation uses exact preceding calendar sessions.

Refuse --index-ma5-gate with bigvalue behavior (R12); this does not settle P1. topk_score_exit refuses any explicitly supplied bigvalue flag (P13). Read precomputed parquet ma* only, never second rolling (P14); re-drop trailing bigvalue zeros, preserve internal zeros. Daily and minute wire the same block arm (P15). Flags default off; off-path kwargs and engine behavior unchanged (R11).

Out of first slice: --bigvalue-flatten and --bigvalue-golden-mult encoding (R8/P3/P10–P12), force-flat, edge and state-and-edge. Omit unsupported flags entirely; state is the only accepted signal.

Must-fix with implementation: (1) supersede stale #475/header status with this review and tracker addendum; (2) explicit calendar binding after bars load, avoiding parquet dates as a surrogate calendar; (3) tests for lag, missing sessions, tail zeros, equality, warmup/confirmation, validation, default-off and both entry points; (4) HELP_LOCK + tracker + tests together. Plan §4.2 warmup/death/death example conflicts with N=2: only the last N valid sessions count, so two death sessions confirm regardless of older warmup. This review pins that interpretation.

Deferred: P1 coexistence decision, flatten clock/priority/limits, golden sizing, edge experiments, real-lake performance and alpha claims. No lake run required or authorized by this slice. Q6/Q8 and 0.95 risk_degree unchanged.

Implementation validation: `/workspace/vanna312/bin/python -m pytest -q tests/test_bigvalue_regime.py tests/test_topk_dropout_*.py tests/test_csv_strategy_books.py` → **189 passed**. Machine-path gate OK. UTF-8 without BOM / NUL checks pass. Ruff new module/tests clean; whole touched files report 12 pre-existing diagnostics, compared programmatically with origin/master by code/message (no additions). Entry wiring tested statically plus shared gate/kwargs data-free tests; no full lake daily/minute run. Diagnostics remain attached to eligibility for inspection, rather than introducing changes to engine stats. Review and implementation stop for Grok; no merge.
