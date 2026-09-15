# MyQuant-backtrader hygiene backlog（头脑风暴续）

- 日期：2026-09-15
- 状态：进行中（一条条：Codex 改 → Grok 核）
- 前置：PR #34（hotpath / presets 快照 / simulate 骨架 / plan 归档）
- 禁区（不动）：改 6/8 卖点、重开 `--asof`、PortAna 定胜负、本仓复刻 LEBS/真栈、缺行 fail-closed→跳过、Cerebro 物理删除、Cursor CloudAgent

## 队列（可改）

| ID | 项 | 完成定义 |
|----|----|----------|
| **H1** ✓ | 考古 Backtrader 文档归档 + 短 CONTRIBUTING（含不要做） | `docs/backtest/` 根下订单/资金等考古 md 进 `_archive/fossils/`；根 `CONTRIBUTING.md`；链接修好；Grok 核无 🔴 |
| **H2** ✓ | 日/分钟 CLI 共用 argparse | `add_csv_backtest_common_args`；daily/minute `main` 去重；pytest 绿 |
| **H3** ✓ | L2 范围篱笆 | AGENTS/README 写明 L2 只读实验、不扩交易核；`run_l2_*` 不接新策略书 |
| **H4** ✓ | research 入口防误 import Cerebro | `test_research_face_imports`：向量化五模块可导入且不拉 backtrader；chip 对照仍可 bt |
| **H5** | 热路径下一步：日线 mark/循环微优化 | 有 plan + 不改成交语义的小步；有 bench/测试 |
| **H6** | CI 备注：numba 在 requirements，parity 必跑 | workflow/注释对齐；可选明确 marker |
| **H7** | `stock_pool/` vs `exports/` 生命周期一句 SSOT | README/pool-csv-contract 补短段 |

已合不重复：csv_common、csv_simulate_loop、presets 快照、plan `_archive/plans/`、numba trail 可选。
