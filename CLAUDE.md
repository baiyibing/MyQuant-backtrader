# CLAUDE.md

This repository is the **research face**: vectorized CSV backtests + chip/TR. LEBS / MockQMT live in OSkhQuant1.3. See [README.md](README.md), [AGENTS.md](AGENTS.md), and [docs/backtest/engine-positioning-ssot.md](docs/backtest/engine-positioning-ssot.md).

## Python

`D:\anaconda3\envs\vanna312\python.exe` (Python 3.12). Resolve via `OSKH_MERGE_PYTHON` / `VANNA312_PYTHON` first.

```powershell
# conda activate vanna312
D:\anaconda3\envs\vanna312\python.exe --version
D:\anaconda3\envs\vanna312\python.exe -c "import oskh_data, common.infra.timekeeping, trade_decision.presets"
D:\anaconda3\envs\vanna312\python.exe -m pytest -q
```

## Docs

Backtest / chip / data docs live under `docs/backtest/`.
