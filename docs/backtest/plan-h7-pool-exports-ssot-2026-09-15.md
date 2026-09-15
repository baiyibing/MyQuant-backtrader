# H7：stock_pool/ vs exports/ 生命周期 SSOT

- 日期：2026-09-15
- 状态：已完成（Grok 核无有效 🔴）
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)

## 目标

用**短 SSOT 段**写清 `stock_pool/` 与 `exports/` 的生命周期分工，避免把可变默认目录当成实验快照。文档-only；不改引擎行为（至多一行 docstring，本切片未改 Python）。

## 生命周期（本切片采纳）

| 树 | 角色 |
|----|------|
| `stock_pool/` | **可变默认**：策略 1–6/8 未传 `--pool-dir` 时的日名单树；可被日常覆盖；**不是**实验/冻结快照 |
| `exports/` | **实验 / 冻结跑**：导出器写出的可复现目录（R5 / 策略 9 / 10 等）；用 `--pool-dir` 显式指向 |
| 策略 9 / 10 | 必须 `--pool-dir`；**拒绝** `stock_pool/`（即使显式传入） |
| 策略 7 | 必须 `--pool-dir`（海龟池等）；不回落本仓 `stock_pool/` |

## 交付

1. 本 plan
2. `docs/backtest/pool-csv-contract.md` 补 SSOT 段；根 `README.md` / `docs/backtest/README.md` 指针
3. 无 Python 行为变更
4. backlog H7 ✓；若 H1–H7 均 ✓ 则标记队列完成
5. Grok → `docs/architecture/reviews/2026-09-15/h7-pool-exports-ssot/grok.md`；修有效 🔴；不 push

## 明确不做

- 不改 `csv_pool` / CLI 默认路径逻辑
- 不迁移或清空 `stock_pool/` 内容
- 不 push；无 Cursor CloudAgent

## 完成定义

- 契约 + README 指针一致；Grok 无有效 🔴；队列 H1–H7 全 ✓
