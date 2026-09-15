# AGENTS

Standalone research-face fork (see [README.md](README.md)). Since migration S2 (2026-09-09) this repo owns the research face; OSkhQuant1.3 stays the trading stack and keeps only the `oskh_factors` chip/bridge micropackage.

**成交引擎定位**：本仓 = 向量化。1.3 = LEBS + MockQMT 真栈。Qlib PortAnaRecord 停用；Cerebro 观察退役。见 [`docs/backtest/engine-positioning-ssot.md`](docs/backtest/engine-positioning-ssot.md)。成交核（档位 / 全卖因跌停 / Decimal 涨跌停价）见 [`docs/backtest/engine-ashare-correctness.md`](docs/backtest/engine-ashare-correctness.md)。入口命令见 [`docs/backtest/README.md`](docs/backtest/README.md)。

## Research entries

- 1/2/3/4/5/6/8/9/10 日线：`backtest/research/csv_daily_backtest.py --strategy version1|…|version6|version8|version9|version10`
- 1/2/3/4/5/6/8/9/10 分钟：`backtest/research/csv_minute_backtest.py --strategy version1|…|version6|version8|version9|version10`
- 7 金榕元：`backtest/research/csv_minute_backtest_v7.py`（`--pool-dir` 必填，不回落 `stock_pool/`）
- 9 底量超顶量：`scripts/data/export_strategy9_pool.py` 写名单，再 `--strategy version9 --pool-dir`（拒绝 `stock_pool/`）
- 10 换手阻力 / 源 B：`scripts/data/export_ta_pool.py` 写名单（湖当日有 K；不做 TopK），再 `--strategy version10 --pool-dir`（卖点同 6；拒绝 `stock_pool/`）
- 名单：`backtest/research/csv_pool.py`（与 1.3 `lebs/csv/universe.py` 同口径）
- 不要 `python -m backtest.lebs`（包不在本仓）。不要为新策略开 Cerebro。
- Cerebro 化石：仅 `backtest/backtest_main_full.py --allow-cerebro-fossil` 等旧对照；见 `docs/backtest/README.md` § Cerebro。
- presets 与 1.3 契约：`tests/test_presets_cross_repo_snapshot.py`（勿静默漂移）。

## Python

- Resolve order: `OSKH_MERGE_PYTHON` → `VANNA312_PYTHON` → `VANNA311_PYTHON` (legacy) → `D:\anaconda3\envs\vanna312\python.exe`
- Helper: `scripts/_script_bootstrap.py` (`resolve_oskh_python`)
- Conda: `D:\anaconda3\Scripts\conda.exe` · `conda activate vanna312`
- Never use system `python` / `pip` implicitly
- Install: `D:\anaconda3\envs\vanna312\python.exe -m pip install -r requirements.txt`

## Scope

Keep: `backtest/` (incl. `research/` + `research/chip/`), `oskh_data/`, `l2_analytics/`, `qlib_cost/`, `turnover-resist/` (Rust SSOT), `oskh_factors/` (full research copy), `strategies/` (`tr_filter`), research `scripts/` (analysis/backtest/data/diagnostics/gates/run incl. `run_l2_*` ETL), slim `common/infra`, `trade_decision/presets`, `oskh_core` (TR re-export + `a_share_symbol_normalize`).

**L2 篱笆：** `l2_analytics/` 与 `scripts/run/run_l2_*` 仅离线研究分析（CSV→Parquet ETL、聚合、DuckDB 查询）。不是 LEBS / MockQMT / 交易栈；不要把新 CSV 策略书接到 L2；不要借 L2 长大 live 包。

Do not reintroduce live trading packages (`live_trading`, `executor_stream`, `redis_stream_bridge`, `stream_monitor`, `oskh_db`, full `strategy_config`).

Consume only. All external downloads and vendor merges live in OSkhQuant1.3. This fork only reads the F lake.

## Data disks (do not mix)

- **Parquet** (hive-split v1.5 three trees `stock/period=1d|1m` · `index/period=1d` · `etf/period=1d`, loose adj/float parquet, TR bars, `tr_staging/`): `resolve_parquet_container()` / `resolve_period_root()` / `resolve_index_daily_root()` / `resolve_etf_daily_root()` / `resolve_source_parquet()` / `resolve_turnover_resist_parquet_root()`. With `F:\\stock_data\\.authority` and no env, this is F. Unset env is not a rollback. Index/ETF roots never read `OSKH_PERIOD_1D_ROOT`.
- **E workspace** (duckdb, exp, skip JSON, stale marker): `resolve_e_stock_data_container()` / `OSKH_DATA_ROOT`.
- `TURNOVER_RESIST_DATA_DIR` is opt-in rollback to an old E path; default follows the parquet container.
- This fork is read-only for market bars. New code must use resolvers, not cwd `stock_data/` literals.
- **CI data-free gates** (no F lake): `verify_oskh_data_contract.py`, `verify_data_path_ssot.py`, `verify_no_hardcoded_machine_paths.py`, `verify_tr_bridge_import_ssot.py` in `.github/workflows/python-tests.yml` before pip. See `docs/backtest/plan-h10-ci-path-gates-2026-09-15.md` · `docs/backtest/plan-h12-ci-tr-bridge-gate-2026-09-15.md`.

## Encoding

UTF-8 without BOM for all text files. After writing `.py` / `.md`, verify NUL count is 0.

## Rust

`cd turnover-resist && cargo build` (do not `cargo build --manifest-path` from repo root).
