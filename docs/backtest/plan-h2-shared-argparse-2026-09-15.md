# H2：日/分钟 CLI 共用 argparse

- 日期：2026-09-15
- 状态：待 Codex 实施 / Grok 核
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)

## 目标
去掉 `csv_daily_backtest.main` / `csv_minute_backtest.main` 里重复的公共 CLI 开关；抽出 `add_csv_backtest_common_args`，公开 flag 名与默认值保持不变。

## 抽出
`add_csv_backtest_common_args(ap, *, repo, end_default, end_help=None, ...)`（建议放 `csv_strategy_books.py`，或新建薄 `csv_cli.py` / 挂 `csv_common.py`——优先与现有 `add_csv_strategy_arg` / `add_strategy6_ratio_args` 同层）：

公共（两端今日一致）：
- `--start` default `"20251023"`
- `--end`（**默认/help 由调用方传入**：daily 现为 `"20260909"` 无 help；minute 现为 `MINUTE_LAKE_END` + lake help）
- `--cash-total` → `DEFAULT_TOTAL_CASH`
- `--daily-quota` → `DEFAULT_DAILY_QUOTA`
- `--workers` default `16`
- `--pool-dir` default `Path(repo) / "stock_pool"`
- 调用 `add_csv_strategy_arg(ap)` + `add_strategy6_ratio_args(ap)`（或由 helper 内部调用，保持顺序与今日相近）

## 接线
- **daily** `main`：`add_csv_backtest_common_args(...)` 后自加 `--out-dir`
- **minute** `main`：同上后自加 `--no-cache` / `--rebuild-cache`
- 解析后逻辑、`run(...)` kwargs、产物路径不变

## 约束
- 公开 CLI flag 名与默认值与现状 bit-identical（含 minute `--end` help 文案）
- **不改** simulate / 卖点 / 成交语义
- 不扩 L2、不碰 Cerebro

## 测试
- `/workspace/vanna312/bin/python -m pytest -q tests/test_csv_daily_backtest.py tests/test_csv_minute_backtest.py tests/test_csv_strategy_books.py tests/test_csv_daily_outdir.py`
- 若易加：对 helper 做 argparse smoke（`--help` / 公共默认值），非必须

## 完成定义
- 两端 `main` 不再各自手写公共 `add_argument` 块
- pytest 绿；Grok 复核无有效 🔴（flag 漂移 / 语义漂移）
