# OP06 reject stock conversion stuffed into cash/bonus columns

Knife #4, BT-only defensive gate from the three-repo-closeout inventory.
Identity facts frozen from
`docs/operations/evidence/hithink-artifact-2026-10-30/coverage-identity-facts.json`:
东兴证券 601198.SH → 中金公司 601995.SH at 0.4376 target shares per source
share (record 2026-10-16, delist 2026-10-19) cannot be expressed in the
cash/bonus ten-column schema.

Fix in `backtest/research/corp_actions_econ_gate.py`:
- `PINNED_STOCK_CONVERSIONS` frozen constant; never loaded from JSON at runtime.
- Primary rule: any row whose code is a pinned conversion source is blocked.
- Secondary (defense-in-depth): pinned ratio in bonus/transfer columns blocks
  only when event_id/source carries conversion markers (pinned codes, 换股,
  conversion, stock merger), so unrelated codes with an equal bonus ratio stay
  eligible.
- Stable reason key: `unsupported_stock_conversion_in_cash_bonus_schema`.

FIELDS unchanged; no target-code columns, no universe auto-add, no lake publish,
no conversion consumer. Out of scope: OSkh mirror, Knives #5–#6.

Validation with /workspace/vanna312/bin/python:
- pytest tests/test_corp_actions_op06_conversion_gate.py
  tests/test_corp_actions_economics_gate.py -q: 35 passed.
- Full suite: 9860 passed; 6 pre-existing test_oskh_data_integration failures
  reproduced on clean HEAD 178dd97 (environment data-path dependent).

Draft commit only; no push, PR or merge (parent handles).
