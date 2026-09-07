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

Do not reintroduce QMT / xtquant market download. The original repo owns that pipeline.

## Data disks (do not mix)

- **Parquet** (`period=1d/1m`, adj/float/etf, TR bars, `tr_staging/`): `resolve_parquet_container()` / `resolve_period_root()` / `resolve_source_parquet()` / `resolve_turnover_resist_parquet_root()`. With `F:\\stock_data\\.authority` and no env, this is F. Unset env is not a rollback.
- **E workspace** (duckdb, exp, skip JSON, stale marker): `resolve_e_stock_data_container()` / `OSKH_DATA_ROOT`.
- `TURNOVER_RESIST_DATA_DIR` is opt-in rollback to an old E path; default follows the parquet container.
- This fork is read-only for market bars. New code must use resolvers, not cwd `stock_data/` literals.

## Encoding

UTF-8 without BOM for all text files. After writing `.py` / `.md`, verify NUL count is 0.

## Rust

`cd turnover-resist && cargo build` (do not `cargo build --manifest-path` from repo root).
