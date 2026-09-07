# CLAUDE.md

This repository is a **slim backtrader fork** (pre RF-R0 snapshot). See [README.md](README.md) and [AGENTS.md](AGENTS.md).

## Python

`D:\anaconda3\envs\vanna311\python.exe` only.

## Quick checks

```powershell
D:\anaconda3\envs\vanna311\python.exe -c "import oskh_data, common.infra.timekeeping, trade_decision.presets"
D:\anaconda3\envs\vanna311\python.exe -m oskh_data.backfill --help
D:\anaconda3\envs\vanna311\python.exe -m pytest -q
```

## Docs

Backtest / chip / data docs live under `docs/backtest/`.
