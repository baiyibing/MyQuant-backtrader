# AGENTS

Standalone backtrader + data fork (see [README.md](README.md)).

## Python

- Interpreter: `D:\anaconda3\envs\vanna311\python.exe`
- Never use system `python` / `pip` implicitly
- Install: `D:\anaconda3\envs\vanna311\python.exe -m pip install -r requirements.txt`

## Scope

Keep: `backtest/`, `oskh_data/`, `qlib_cost/`, `turnover-resist/`, slim `common/infra`, `trade_decision/presets`, thin `oskh_core` (TR bridge only).

Do not reintroduce live trading packages (`live_trading`, `executor_stream`, `redis_stream_bridge`, `stream_monitor`, `oskh_db`, full `strategy_config`).

## Encoding

UTF-8 without BOM for all text files. After writing `.py` / `.md`, verify NUL count is 0.

## Rust

`cd turnover-resist && cargo build` (do not `cargo build --manifest-path` from repo root).
