# 人裁卡：敏感结论 → 要不要动默认（2026-09-20）

**范围：只读 Human GO B；生产 C 冻结。** 依据合并 PR [#136](https://github.com/baiyibing/MyQuant-backtrader/pull/136)–[#140](https://github.com/baiyibing/MyQuant-backtrader/pull/140)。BASE `f2fe151…`（#136 合入）。本卡 **docs-only**，不改生产 fill/scan/fee/defaults/CLI。本轮 **不预选 C**。

## 1. 背景与范围

| 项 | 锁定 |
|---|---|
| 人裁入口 | #136 pitfall eval → Human GO **B**（只读敏感对照） |
| 已交付 | batch1 合成（#137）、batch2 真湖 Book/v7（#138）、batch3 Mode B clock（#140） |
| 生产 | `production_C=frozen`；热路径相对 BASE 未改 |
| 禁令 | 局部 bp ≠ 全策略结论；Book / v7 / Mode B **分列**，禁混比引擎优劣 |

## 2. 证据摘要（关键数字 + DATA_GAP）

| 批 | 数据 | Clock / 同价 / 局部 Δ | 全策略 NAV·DD·rank | 其它缺口 |
|---|---|---|---|---|
| **batch1** #137 | 合成局部价 | Book 共同 7、同价 14.3%；v7 共同 10、同价 10%；构造局部均值 Book≈−127bp / v7≈−73bp | **DATA_GAP** | 无生产分钟湖；Mode B clock 未做 |
| **batch2** #138 | 真 START 分钟，`qlib_bin_1min` **READ_OK** | Book 15→8 共同，`same_price_rate=0.125`，`mean_price_diff_bp≈+9.0`；v7 180→35 共同，同价≈0.086，`mean_price_diff_bp≈−1.06`；有 exit mark 局部 Δ：Book≈**−8.78bp**（n=7），v7≈**−1.97bp**（n=20） | **DATA_GAP** | Mode B 发运时 **NOT_RUN**；volume 轴全部 **DATA_GAP** |
| **batch3** #140 | Mode B，同窗同符号 | 10 实例 / **2** close-path 共同成交；`same_price_rate=0`；`mean_local_return_delta_bp≈−8.59`；`open_gap=0`；oracle 全标 `EX_POST_UPPER_BOUND_NOT_EXECUTABLE` | **DATA_GAP** | 样本稀（10/2）；禁并入可执行均值 |

## 3. 高风险路径（须点名）

1. **书追买同价率**（batch2 真湖）：共同成交同价率 **0.125**（1/8）——与 #136「同 bar close 决策/成交」机制风险同向。
2. **v7 加仓同价率**（batch2 真湖）：共同成交同价率 **≈0.086**（3/35）——加仓同价路径仍存在，但显著低于书追买。
3. **Mode B 样本稀**：仅 2 笔可执行 close-path；均值 ≈−8.59bp **不可外推**。

## 4. 硬约束：局部 bp 不能当全策略默认依据

- 上表局部 Δ 均为**独立注入事件**等权均值，非组合收益、非回撤、非排名。
- 三批全策略 NAV / 最大回撤 / 策略排名均为 **DATA_GAP（空白）**——**禁止**用局部 bp 裁决是否改生产默认。
- Book / v7 / Mode B 分列报告；**禁止**跨引擎比总 NAV 论优劣。

## 5. 人裁选项（三选一；本轮不预选 C）

| 选项 | 含义 | 本轮状态 |
|---|---|---|
| **A. 继续只读扩样** | 扩窗 / 扩票 / 补全策略 NAV·DD·rank（仍只读 B） | 可选 |
| **B. 暂不动默认** | 维持生产 fill / scan / fee / defaults / CLI | 可选 |
| **C. 开行为变更** | 须**分路径**另开计划（书追买钟、v7 加仓钟、Mode B 退出钟、费用/滑点/容量分别裁） | **本轮禁止自动选**；须另行人裁 |

## 6. 建议下一刀（建议非裁决）

**建议（非裁决）：B，或 A→再裁。**  
在全策略 NAV/DD/rank 仍为 DATA_GAP、Mode B 仅 2 笔可执行样本的前提下，**不足以**授权 C。若人侧要加压证据，优先 A（扩窗/扩票 + 闭环 NAV），再回头看是否动默认；否则选 B 冻结生产，保留高风险路径备忘。

## 7. 引用

| 文档 / PR | 链接 |
|---|---|
| #136 pitfall eval（Human GO B 入口） | [PR](https://github.com/baiyibing/MyQuant-backtrader/pull/136) · [eval](eval-minute-pitfall-vs-asbuilt-2026-09-20.md) |
| 计划 | [plan-minute-sensitivity-b-2026-09-20.md](plan-minute-sensitivity-b-2026-09-20.md) |
| batch1 结果 | [results…batch1…](results-minute-sensitivity-b-batch1-2026-09-20.md) · [PR #137](https://github.com/baiyibing/MyQuant-backtrader/pull/137) |
| batch2 结果 | [results…batch2…](results-minute-sensitivity-b-batch2-2026-09-20.md) · [PR #138](https://github.com/baiyibing/MyQuant-backtrader/pull/138) |
| batch3 Mode B | [results…batch3…](results-minute-sensitivity-b-batch3-modeb-2026-09-20.md) · [PR #140](https://github.com/baiyibing/MyQuant-backtrader/pull/140) |
| 导出 README | [minute_sensitivity_b_20260920/README.md](../../../backtest/research/exports/minute_sensitivity_b_20260920/README.md) |
