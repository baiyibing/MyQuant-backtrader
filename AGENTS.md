# AGENTS

Standalone research-face fork (see [README.md](README.md)). Since migration S2 (2026-09-09) this repo owns the research face; OSkhQuant1.3 stays the trading stack and keeps only the `oskh_factors` chip/bridge micropackage.

**成交引擎定位**：本仓 = 向量化。1.3 = LEBS + MockQMT 真栈。Qlib PortAnaRecord 停用；Cerebro / Rolling 已退场（2026-09-16）。见 [`docs/backtest/engine-positioning-ssot.md`](docs/backtest/engine-positioning-ssot.md)。成交核（档位 / 全卖因跌停 / Decimal 涨跌停价）见 [`docs/backtest/engine-ashare-correctness.md`](docs/backtest/engine-ashare-correctness.md)。入口命令见 [`docs/backtest/README.md`](docs/backtest/README.md)。

三仓回测不做重：MyQuant 出信号，本仓向量化研究，1.3 执行验收；LEBS 只在 1.3，且 LEBS ≠ MockQMT 真栈。本仓无 `python -m backtest.lebs` 入口。旧 CSV CLI 保留真身，HELP_LOCK 不变（P5=A）。

## Research entries

- 1/2/3/4/5/6/8/9/10 日线：`backtest/research/csv_daily_backtest.py --strategy version1|…|version6|version8|version9|version10`
- 1/2/3/4/5/6/8/9/10 分钟：`backtest/research/csv_minute_backtest.py --strategy version1|…|version6|version8|version9|version10`
- 7 金榕元：`backtest/research/csv_minute_backtest_v7.py`（`--pool-dir` 必填，不回落 `stock_pool/`）
- 12 金榕元均线减仓书：CSV 入口 `--strategy version12`（别名 `12/v12`）；#151 follow-up 行业约定：分钟湖/成交域默认 raw `--dividend-type none`（front 仅可选 fail-closed，缺 1m/front 分区即失败），日线信号域固定 `front`，盘中成交继续分钟 raw，除权仅走显式 economics/文档路径（禁止 front 日线 + none 分钟下静默双重调整）。默认 `stock_pool/`，与 7 独立入口及必填池分工不同。MA5 周期减仓/买回 + MA10 止损/买回；latch=A、residual=2。
- topk_app_dropout（新策略，不改策略 7）：`backtest/research/csv_minute_backtest_topk_app_dropout.py`；名单可选先 `scripts/data/export_topk_app_dropout_pool.py`。禁止 `register` 进 1–10 BOOKS。
- 9 底量超顶量：`scripts/data/export_strategy9_pool.py` 写名单，再 `--strategy version9 --pool-dir`（拒绝 `stock_pool/`）
- 10 换手阻力 / 源 B：`scripts/data/export_ta_pool.py` 写名单（湖当日有 K；不做 TopK），再 `--strategy version10 --pool-dir`（卖点同 6；拒绝 `stock_pool/`）
- 11 ma_chip（已移植，本 PR）：`scripts/data/export_strategy11_pool.py` 写 `<out-dir>/pool/`，再日线 / 分钟 `--strategy version11 --pool-dir <out-dir>/pool`（拒绝 `stock_pool/`）。D 后首 bar T 且 ≤4 自然日；周线显式 prefix；日线契约收盘 / 分钟 09:30 open；volume=A 未完成桶买 skip / pending 卖 defer，禁追买。分钟要求 lake volume 并绕过旧无量缓存；D 静态档案对照仍待跑。
- 统一卖出规则网格 · 模式 A：`scripts/research/run_unified_exit_modea.py`（库 `backtest/research/unified_exit_modea.py`；产出 `backtest_output/unified_exit_modea/`；提案 `docs/backtest/stock-backtest-unified-exit-proposal-2026-09-17.md`）
- 统一卖出规则网格 · 模式 B：`scripts/research/run_unified_exit_modeb.py`（默认 P1=A 窄网格；Q38=A 分钟 oracle；产出独立目录 `backtest_output/unified_exit_modeb/`）。
- 名单：`backtest/research/csv_pool.py`（与 1.3 `lebs/csv/universe.py` 同口径）
- 不要 `python -m backtest.lebs`（包不在本仓；LEBS 只在 1.3，且 LEBS ≠ 真栈）。Cerebro 已退场，禁止复活。
- 向量化撮合核收口 plan（已人裁 GO：A/A/C/A/A；范围 A→B→C，D 后置）：`docs/backtest/plan-ashare-engine-refactor-2026-09-18.md` §0.3 / §5。热路径固定清单由 `tests/test_ashare_simulate_import_fence.py` 锁定，禁止扩成 research 全目录扫描。
- Cerebro / Rolling 已退场（2026-09-16）；chip / ma_chip 对照产物为静态档案，代码路径已删。version11 CSV 已按 [独立计划](docs/backtest/plan-version11-machip-csv-2026-09-21.md) 移植（本 PR，A–C），成交时点与 volume=A 已人裁；框架验证非已验证多头，D 对照未完成。
- presets 与 1.3 契约：`tests/test_presets_cross_repo_snapshot.py`（勿静默漂移）。

## Python

- Resolve order: `OSKH_MERGE_PYTHON` → `VANNA312_PYTHON` → `VANNA311_PYTHON` (legacy) → `D:\anaconda3\envs\vanna312\python.exe`
- Helper: `scripts/_script_bootstrap.py` (`resolve_oskh_python`)
- Conda: `D:\anaconda3\Scripts\conda.exe` · `conda activate vanna312`
- Never use system `python` / `pip` implicitly
- Install: `D:\anaconda3\envs\vanna312\python.exe -m pip install -r requirements.txt`

## Scope

Keep: `backtest/` (incl. `research/` + `research/chip/`), `oskh_data/`, `l2_analytics/`, `qlib_cost/`, `turnover-resist/` (Rust SSOT for TR/cyqk audit & Store), `oskh_factors/` (full research copy), `strategies/` (`tr_filter`), research `scripts/` (analysis/backtest/data/diagnostics/gates/run incl. `run_l2_*` ETL), slim `common/infra`, `trade_decision/presets`, `oskh_core` (TR re-export + `a_share_symbol_normalize`).

**CYQ / TR boundary (H13):** full-market daily `winner_ratio` feeder lives in sibling **MyQuant** (`build_winner_ratio.py`, numba); do **not** reimplement it here. This repo’s Rust path is TR/Store/audit — see `docs/backtest/plan-h13-cyq-tr-boundary-2026-09-15.md` and chip inventory §E.

**L2 篱笆：** `l2_analytics/` 与 `scripts/run/run_l2_*` 仅离线研究分析（CSV→Parquet ETL、聚合、DuckDB 查询）。不是 LEBS / MockQMT / 交易栈；不要把新 CSV 策略书接到 L2；不要借 L2 长大 live 包。

Do not reintroduce live trading packages (`live_trading`, `executor_stream`, `redis_stream_bridge`, `stream_monitor`, `oskh_db`, full `strategy_config`).

Consume only. All external downloads and vendor merges live in OSkhQuant1.3. This fork only reads the configured lake.

## Data disks (do not mix)

- **不要猜数据在哪**：没设定 `OSKH_SOURCE_PARQUET_ROOT`（或 `OSKH_AUTHORITY_HINT_ROOT` + `.authority`）、文件不存在，就报错。禁止写死 E:/F:、禁止探测盘符、禁止缺失时返回空表假装没数据。
- **Parquet** (hive-split v1.5 three trees `stock/period=1d|1m` · `index/period=1d` · `etf/period=1d`, loose adj/float parquet, TR bars, `tr_staging/`): `resolve_parquet_container()` / `resolve_period_root()` / `resolve_index_daily_root()` / `resolve_etf_daily_root()` / `resolve_source_parquet()` / `resolve_turnover_resist_parquet_root()`. Index/ETF roots never read `OSKH_PERIOD_1D_ROOT`.
- **Workspace** (duckdb, exp, skip JSON, stale marker): `resolve_e_stock_data_container()` / `OSKH_DATA_ROOT`.
- `TURNOVER_RESIST_DATA_DIR` is opt-in rollback to an old workspace path; default follows the parquet container.
- This fork is read-only for market bars. New code must use resolvers, not cwd `stock_data/` literals.
- **申万一级（只消费）**：`oskh_data/industry_sw_l1.py` 读 `vendor_wind_sw_l1/` 下的 `sw_l1_map.csv` / `wind_l1_map.csv`（两份都要有）。采集与 merge 只在 1.3。Mode A/B 用 `--industry` 才分层，缺表即失败。
- **CI data-free gates** (no F lake): `verify_oskh_data_contract.py`, `verify_data_path_ssot.py`, `verify_no_hardcoded_machine_paths.py`, `verify_tr_bridge_import_ssot.py` in `.github/workflows/python-tests.yml` before pip. See `docs/backtest/plan-h10-ci-path-gates-2026-09-15.md` · `docs/backtest/plan-h12-ci-tr-bridge-gate-2026-09-15.md`.

## Encoding

UTF-8 without BOM for all text files. After writing `.py` / `.md`, verify NUL count is 0.

## Rust

`cd turnover-resist && cargo build` (do not `cargo build --manifest-path` from repo root).
