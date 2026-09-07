---
name: architecture-guard
description: Run CI gate scripts against staged changes to catch architecture contract violations before commit
tools: Bash, Grep, Glob, Read
---

Run the actual CI gate scripts on staged or working-tree changes. Same scripts that GitHub Actions run.

## Gate Scripts

Run the appropriate subset based on what changed (check `git diff --name-only main...HEAD`):

| Changed packages | Script to run |
|---|---|
| `common/`, `oskh_core/`, `oskh_db/`, `trade_decision/`, `live_trading/`, `executor_stream/` | `D:/anaconda3/envs/vanna312/python.exe scripts/run_common_package_contract_gates.py` |
| `oskh_core/` cash/capital/position/T+1/risk | `D:/anaconda3/envs/vanna312/python.exe scripts/run_stream_execution_contract_bundle.py` |
| Broad / unsure | `D:/anaconda3/envs/vanna312/python.exe scripts/run_merge_acceptance_gates_vanna311.py` |
| CSV mode only | `D:/anaconda3/envs/vanna312/python.exe scripts/verify_csv_signoff_readiness.py` |

## Individual Verify Scripts (run directly for narrow checks)

- `D:/anaconda3/envs/vanna312/python.exe scripts/verify_common_oskh_core_import_allowlist.py`
- `D:/anaconda3/envs/vanna312/python.exe scripts/verify_trade_decision_no_direct_sqlite.py`
- `D:/anaconda3/envs/vanna312/python.exe scripts/verify_trading_hot_path_no_qmt_session_api.py`
- `D:/anaconda3/envs/vanna312/python.exe scripts/verify_process_entrypoint_calendar_bootstrap.py`

Report exit code and any failures.
