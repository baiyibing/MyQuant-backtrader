# H13：CYQ / TR 产品边界（MyQuant numba feeder vs 本仓 Rust）

- 日期：2026-09-15
- 状态：已完成（Grok 核无有效 🔴；已开 PR）
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)（软扩展；H1–H12 已收口）
- 主题：**D 边界澄清**（文档 only；无算法 / 无 Rust rewrite）
- 前置：MyQuant 2026-09-14 全市场 exact CYQ / `winner_ratio`（numba）已落地；本仓 H11 chip/TR inventory

## 目标

把 **两条产品路径** 写清楚，避免后续把 MyQuant 日频 `winner_ratio` 馈源与本仓 Rust `turnover-resist`（审计 / Store / 策略 10）混为一谈，或在本仓复刻 MyQuant CYQ feeder。

| 路径 | 仓 / 入口 | 角色 |
|------|-----------|------|
| **MyQuant CYQ feeder** | `MyQuant/my_scripts/build_winner_ratio.py`（numba） | 全市场日频 exact `winner_ratio` parquet；买过滤外置馈源；算法对齐本仓 `qlib_cost.cyq` SSOT |
| **本仓 Rust TR** | `turnover-resist` → bridge → Store | Canonical TR / cyqk **审计与 Store**；策略 10 / `export_ta_pool` / `tr_filter` |

证据（只读，不迁代码；兄弟仓 checkout）：`MyQuant/my_scripts/build_winner_ratio.py`、`MyQuant/docs/winner-ratio-cyq-parity-2026-09-14.md`（约 5569×166；用户确认全市场 ~53s 量级）。

## 交付

1. 本 plan
2. [chip/chip-slowpath-inventory-2026-09-15.md](chip/chip-slowpath-inventory-2026-09-15.md) 新节：MyQuant numba CYQ vs Rust TR 边界；later offload 仍指本仓 minute/hybrid 等
3. `docs/backtest/README.md` chip / hygiene 短指针；可选 `AGENTS.md` / `chip/README.md`；[CONTRIBUTING.md](../../CONTRIBUTING.md) don’t-do 一行：不在本仓复刻 MyQuant CYQ feeder
4. Backlog **H13 ✓** + 刷新「next heavy」：D1 profile minute/hybrid；C soft 加深 list-quality；run-manifest hard 仍延期
5. Grok → `docs/architecture/reviews/2026-09-15/h13-cyq-tr-boundary/grok.md`；修有效 🔴；**push + PR → master**
6. PR 后另写 [plan-brainstorm-next-heavy-2026-09-15.md](plan-brainstorm-next-heavy-2026-09-15.md)

## 明确不做

- 不改 simulate / 卖点 / 6/8 / chip / TR **算法**
- 不在本仓 reimplement MyQuant `build_winner_ratio` / 迁 numba feeder
- 不 Full Rust rewrite / 新 PyO3 API；不删 Cerebro；不扩 L2
- 不接 MyQuant `run-manifest` 硬集成；无 Cursor CloudAgent

## 完成定义

- 边界文档落地；inventory / README / backlog / CONTRIBUTING 同步；Grok 无有效 🔴；分支已 push 且 PR 指向 master；next-heavy plan 已写
