---
name: ruff-check
description: Run Ruff lint + format check on changed Python files, with optional auto-fix
disable-model-invocation: false
---

Run Ruff checks on changed Python files.

## Quick check (current branch vs main)

```bash
git diff --name-only main...HEAD -- '*.py' | xargs -r D:/anaconda3/envs/vanna312/python.exe -m ruff check
```

## Auto-fix

```bash
git diff --name-only main...HEAD -- '*.py' | xargs -r D:/anaconda3/envs/vanna312/python.exe -m ruff check --fix
```

## Format check

```bash
git diff --name-only main...HEAD -- '*.py' | xargs -r D:/anaconda3/envs/vanna312/python.exe -m ruff format --check
```

## Full project (slow, use sparingly)

```bash
D:/anaconda3/envs/vanna312/python.exe -m ruff check --select F401,F841 live_trading/ common/ oskh_core/ oskh_db/ trade_decision/ executor_stream/ eod_reconcile/ redis_stream_bridge/ stream_monitor/ strategies/ strategy_config/ bucket_policy/
```

Report check results with file paths, line numbers, and fix suggestions.
