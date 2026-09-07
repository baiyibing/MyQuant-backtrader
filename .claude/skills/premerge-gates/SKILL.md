---
name: premerge-gates
description: Run the right pre-merge gate scripts based on what files changed
disable-model-invocation: true
---

Run the correct CI gate scripts based on `git diff --name-only main...HEAD`.

## Step 1: Detect changed packages

```bash
git diff --name-only main...HEAD | awk -F/ '{print $1}' | sort -u
```

## Step 2: Run matching gates

| If any changed file is in... | Run this script |
|---|---|
| `common/`, `oskh_core/`, `oskh_db/`, `trade_decision/`, `live_trading/`, `executor_stream/` | `D:/anaconda3/envs/vanna311/python.exe scripts/run_common_package_contract_gates.py` |
| `oskh_core/` (cash, capital_pool, position, T+1, risk_engine) | `D:/anaconda3/envs/vanna311/python.exe scripts/run_stream_execution_contract_bundle.py` |
| Broad change / unsure | `D:/anaconda3/envs/vanna311/python.exe scripts/run_merge_acceptance_gates_vanna311.py` (covers everything) |
| CSV-only change | `D:/anaconda3/envs/vanna311/python.exe scripts/verify_csv_signoff_readiness.py` |

## Step 3: Report

List each script run with its exit code. If all pass (exit 0), report "All gates green". If any fail, report the failing script(s) and suggest running them individually for detail.
