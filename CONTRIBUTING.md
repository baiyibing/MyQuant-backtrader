# Contributing

本仓是独立研究脸：日名单 CSV + 向量化回测、筹码 / 换手阻力研究。交易栈与 LEBS / MockQMT 验收归 OSkhQuant1.3。提交前阅读 [AGENTS.md](AGENTS.md) 与 [成交引擎定位](docs/backtest/engine-positioning-ssot.md)。

## 研究入口与数据

- 日线 / 分钟使用 `backtest/research/csv_daily_backtest.py` / `csv_minute_backtest.py`；策略 7 使用独立的 `csv_minute_backtest_v7.py`。参数与名单要求见 [回测专题](docs/backtest/README.md)。
- 行情只读 F 湖；下载与 vendor 合并在 OSkhQuant1.3。路径使用 resolver，遵守 [AGENTS.md 的盘符分层](AGENTS.md#data-disks-do-not-mix)，不要写死 cwd `stock_data/`；E 盘工作区与 F 湖分开。

## 不要做

- 不引回 `live_trading`、`executor_stream`、`redis_stream_bridge`、`stream_monitor`、`oskh_db` 或完整 `strategy_config`，不复刻 LEBS / MockQMT。
- 不在本仓运行 `python -m backtest.lebs`，不恢复 Qlib `PortAnaRecord` 回测。
- 不为新策略开 Cerebro，不新增 `ProfitStrategy.StrategyN` 或扩 Rolling；保留现有 Cerebro 代码用于旧对照。
- 不静默漂移成交核、策略书或与 1.3 的 presets 契约；相关改动须同步规则文档与契约检查。
- 不在本仓复刻 MyQuant 全市场日频 CYQ / `winner_ratio` feeder（`build_winner_ratio.py`）；该产品路径在兄弟仓 MyQuant；本仓 Rust `turnover-resist` 是 TR/cyqk 审计与 Store，见 [plan-h13-cyq-tr-boundary-2026-09-15.md](docs/backtest/plan-h13-cyq-tr-boundary-2026-09-15.md)。

## PR 与验证

PR 写清问题、改动与验证结果，使用 GitHub Actions 的 [Python 测试与契约 gates](.github/workflows/python-tests.yml)；涉及 Rust 时还需通过 [Rust 检查](.github/workflows/turnover-resist-rust.yml)。本地 CLI 可用，无需 CloudAgent。

### 刷新 presets 跨仓基线

`tests/fixtures/presets_cross_repo_baseline.json` 固定一次已核对的 OSkhQuant1.3 commit 与其 `trade_decision/presets.py` SHA-256，使没有兄弟仓 checkout 的 CI 也能发现本仓副本漂移。该基线仅证明与所记录 commit 一致，**不证明已同步 OSkhQuant1.3 最新版本**；有兄弟仓时测试仍会直接逐字节比较。

仅在 presets 契约已在两仓有意同步后刷新：在 OSkhQuant1.3 运行 `git rev-parse HEAD`，并对其 `trade_decision/presets.py` 计算完整 SHA-256；将结果分别写入 fixture 的 `upstream_commit` 与 `presets_sha256`。确认本仓同名文件的 SHA-256 相同，再运行 `pytest -q tests/test_presets_cross_repo_snapshot.py`。fixture 与本仓 presets 变更应在同一 PR 中接受审查。

本地 Python 按 [AGENTS.md](AGENTS.md#python) 解析解释器，不隐式使用系统 `python` / `pip`；Rust 在 `turnover-resist/` 内构建。文本使用 UTF-8 无 BOM，写入 `.py` / `.md` 后确认 NUL 为 0。
