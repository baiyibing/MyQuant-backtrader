# RB-07: layered CI and shared pytest marker (ZERO-DIFF)

The existing `.github/workflows/python-tests.yml` steps remain in one required
job, `pytest-and-gates`, with their order and behavior preserved. Layer comments
make the early failure boundaries explicit:

| Layer | Existing checks |
| --- | --- |
| L0 (pre-pip) | Data-free path/contract gates: `verify_oskh_data_contract.py`, `verify_data_path_ssot.py`, `verify_no_hardcoded_machine_paths.py`, `verify_tr_bridge_import_ssot.py` under `scripts/gates/`. |
| L1 (post-pip) | Registry admission (`scripts/gates/verify_book_admission.py`), baseline admission (`scripts/gates/verify_baseline_admission.py`), capability admission (`scripts/gates/verify_book_capability_classification.py`), and minute classification (`scripts/check_minute_classification.py`). |
| L2 | Existing pandas 3.0.6 pin assertion, `ruff check bt_contract`, and numba import assertion. |
| L3 | Required pytest suite with `-m "not production and not benchmark"`. |

MC-6 uses [`scripts/ci_pytest_marker.txt`](../../scripts/ci_pytest_marker.txt) as
the marker SSOT for CI and [pre-push](../../.githooks/pre-push). The expression
is unchanged. Pre-push retains `-x` and `PREPUSH_PYTEST_ARGS`; a missing marker
file fails with an explicit message when the pytest path runs.

Existing admission context: [RB-01](rb01-github-branch-protection-steps-2026-10-06.md),
[RB-03](rb03-baseline-admission-checklist-2026-10-06.md), and
[RB-04](rb04-book-capabilities-truth-table-2026-10-06.md).
No lake-backed gates are added. Durations have not been measured.
Parallelization is deferred to keep the branch-protection required check
`pytest-and-gates` stable. The RB-01 cancel-in-progress policy, pandas pin,
`byte_skip_reason`, fixtures, baselines, HELP_LOCK, and simulation are unchanged.

## Windows CRLF marker reads

Both `.githooks/pre-push` and `.github/workflows/python-tests.yml` normalize `scripts/ci_pytest_marker.txt` with `tr -d '\r'` before `pytest -m`, so a CRLF checkout cannot leave a stray CR inside the marker expression.
