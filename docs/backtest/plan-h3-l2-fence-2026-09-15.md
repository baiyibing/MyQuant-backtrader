# H3：L2 范围篱笆

- 日期：2026-09-15
- 状态：待 Codex 实施 / Grok 核
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)

## 目标
在 AGENTS / README 写清：`l2_analytics/` 与 `scripts/run/run_l2_*` 只做离线 L2 分析（ETL / 聚合），不扩成交易核或策略书入口。

## 要写清的篱笆
- **是**：research 只读 L2（CSV→Parquet ETL、DuckDB 聚合、离线查询）；`run_l2_*` 保持 ETL / aggregates。
- **不是**：LEBS / MockQMT / 真栈撮合；不把新 CSV 策略书接到 L2；不借 L2 长大 `live_trading` 等已禁包。

## 交付
1. `AGENTS.md` Scope：在 Keep 中的 `l2_analytics/` / `run_l2_*` 旁补短篱笆句（或紧邻 Scope 段）。
2. 根 `README.md` Layout 行：`l2_analytics/` 写明 offline analytics only（不扩交易/策略书）。
3. 可选：`docs/backtest/README.md` Hygiene 一句若自然。
4. `plan-hygiene-backlog`：H1/H2 标完成，H3 先进行中再完成。

## 不要
- 不改 `l2_analytics/` 代码、不改 `run_l2_*` 行为
- 不接策略书 / Cerebro / 成交核
- 不 push；无 Cursor CloudAgent

## 完成定义
- 文档篱笆可读；Grok 复核无有效 🔴（范围表述歧义 / 暗示 L2 可接交易）。
