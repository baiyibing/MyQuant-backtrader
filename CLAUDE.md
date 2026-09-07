# CLAUDE.md

This repository is a **slim backtrader fork**. See [README.md](README.md) and [AGENTS.md](AGENTS.md).

## Python

`D:\anaconda3\envs\vanna312\python.exe` (Python 3.12). Resolve via `OSKH_MERGE_PYTHON` / `VANNA312_PYTHON` first.

```powershell
# conda activate vanna312
D:\anaconda3\envs\vanna312\python.exe --version
D:\anaconda3\envs\vanna312\python.exe -c "import oskh_data, common.infra.timekeeping, trade_decision.presets"
D:\anaconda3\envs\vanna312\python.exe -m oskh_data.backfill --help
D:\anaconda3\envs\vanna312\python.exe -m pytest -q
```

## Docs

Backtest / chip / data docs live under `docs/backtest/`.
