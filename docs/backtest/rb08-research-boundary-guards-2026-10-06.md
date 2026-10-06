# RB-08 research execution boundary guards

H-RB-04 / RB-08 adds data-free family tags and AST import guards for the existing
explicit `SIMULATE_HOT_PATH` enumeration. The enumeration and its order remain
unchanged; no research-wide recursive scan is introduced.

`backtest/research/research_family_tags.py` lists the current fullstrat research
modules, joint-return modules (including the run-protocol adapter), and the
minute-orders backend package. Its import prefixes cover bare, qualified,
relative, and package-member imports through the existing fence's AST resolver.
Aliases and imports inside functions or inactive branches are checked too.

Leaves may be reused. Non-default clocks/slip, joint-return execution, and
minute-orders execution remain isolated from the simulate hot path. The ledger's
existing fill-clock labeling exception does not exempt these families.

ZERO-DIFF: no simulation behavior, fixtures, baselines, HELP_LOCK, book order,
or execution registrations change. No workflow gate is added; focused tests
provide the data-free guard. RB-09/10+ and moving fullstrat into main are outside
this change.

Validation: `/workspace/venv/bin/python -m pytest -q tests/test_ashare_simulate_import_fence.py`.
