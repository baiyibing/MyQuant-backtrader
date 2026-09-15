# H16 = C soft+：加深 list-quality tooling

- 日期：2026-09-15
- 状态：已完成（Grok 核无有效 🔴；待 push + PR）
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md) · [plan-brainstorm-next-heavy-2026-09-15.md](plan-brainstorm-next-heavy-2026-09-15.md)（C soft+）
- 前置：H9 [plan-h9-list-quality-2026-09-15.md](plan-h9-list-quality-2026-09-15.md) · [reviews/.../h9-list-quality/grok.md](../architecture/reviews/2026-09-15/h9-list-quality/grok.md)
- 主题：**C soft+**（加深 in-repo pool list-quality；**非** MyQuant `run-manifest` hard）

## 目标

在 H9 之上加深只读 list-quality：脚本友好输出、跨日频次、日际 churn、更严日历 stem 报告（H9 Grok Issue 1）。仍只吃契约 CSV（`parse_pool_csv` / `validate_pool_dir`）；无湖、无 qlib、无 simulate/sell、**不接** run-manifest。

## 交付（选 4 项，无 scope creep）

1. 本 plan
2. `backtest/research/pool_list_quality.py`：
   - **JSON** 输出模式（`--format json`）
   - **Top-N** 跨日高频代码（`--top-n`，默认 20）
   - **Day-over-day churn**（相邻日 added/removed 计数 + 汇总）
   - **日历 stem**：八位但非合法日期的 stem 单独列表；`valid_calendar_day_count` 与 `day_count` 并列
   - **Markdown** 摘要（`--format markdown`）
3. CLI 透传：`scripts/research/report_pool_list_quality.py`（仍 re-export `main`）
4. Pytest 扩 `tests/test_report_pool_list_quality.py`
5. `pool-csv-contract.md` H9 节 → H9/H16；backlog **H16 ✓**；next-heavy C soft+ ✓ → next **run-manifest hard（仍延期）**
6. Grok → `docs/architecture/reviews/2026-09-15/h16-c-soft-list-quality/grok.md`；修有效 🔴；**push + PR → master**

## 明确不做

- **不**集成 MyQuant `run-manifest` / 不消费 manifest
- 不改 simulate / sell / 卖点 / `--asof`
- 不改 `validate_pool_dir` 契约语义；不写湖；不扩 L2；无 Cursor CloudAgent

## 完成定义

- pytest 绿；文档/backlog/next-heavy 同步；Grok 无有效 🔴；分支已 push 且 PR → master
