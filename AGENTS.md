# AGENTS

Standalone backtrader + data fork (see [README.md](README.md)).

## Python

- Resolve order: `OSKH_MERGE_PYTHON` → `VANNA312_PYTHON` → `VANNA311_PYTHON` (legacy) → `D:\anaconda3\envs\vanna312\python.exe`
- Helper: `scripts/_script_bootstrap.py` (`resolve_oskh_python`)
- Conda: `D:\anaconda3\Scripts\conda.exe` · `conda activate vanna312`
- Never use system `python` / `pip` implicitly
- Install: `D:\anaconda3\envs\vanna312\python.exe -m pip install -r requirements.txt`

## Scope

Keep: `backtest/`, `oskh_data/`, `qlib_cost/`, `turnover-resist/`, `oskh_factors/`, slim `common/infra`, `trade_decision/presets`, thin `oskh_core` (TR re-export only).

Do not reintroduce live trading packages (`live_trading`, `executor_stream`, `redis_stream_bridge`, `stream_monitor`, `oskh_db`, full `strategy_config`).

## Encoding

UTF-8 without BOM for all text files. After writing `.py` / `.md`, verify NUL count is 0.

## Rust

`cd turnover-resist && cargo build` (do not `cargo build --manifest-path` from repo root).
