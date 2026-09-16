# v8 规则 v2 plan 评审裁决合并（merge-consensus）

> 评审对象：[plan-v8-rules-v2-2026-09-16.md] v1.0 · 2026-09-16
> 评审方：zcode-facts（3 项代码声称全证真 + 2🔴 规格缺口 + 断言翻转清单 §4）、zcode-arch（1🔴 文本自矛盾 + 边界测试向量表 + 语义连锁）
> 双方结论：**READY-AFTER-FIXES**

## 裁决清单（v1.1 已回写）

| # | 发现 | 裁决 |
|---|------|------|
| 🔴 arch-R1 | g=50%/100% 档位归属：表（≤50% 归三档，+30% 线）与脚注（属上档，+35%/+80% 线）矛盾 | **业务原文为准**：「15%＜涨幅≤50%」→ 50% 归三档；「50%＜涨幅≤100%」→ 100% 归四档；「＞100%」五档。脚注删误。最终区间：`(0,6%) / [6%,15%) / [15%,50%] / (50%,100%] / (100%,∞)`（g=15% 起全局底 1.15 覆盖 band2 的 +2%） |
| 🔴 facts-1 | §1 缺「px ≥ cost」前置（字面实现会在亏损价触发一/二档） | 表头补前置行；保留现状守卫（`strategy8_rules.py:78-79`）；切片 A 保留 below-cost 用例 |
| 🔴 facts-2 | 止盈 reason 契约未定义 | **定 `trail:band:{1..5}`（档序号，非地板值）**；`trail:` 前缀保 `sell_trail` 分类（`csv_ledger.py:248-249`）；`peak_dd` reason 退役；band3 的全局底/比例线出口共用 band3（研究侧可由 (px,peak,cost) 重算绑定线） |
| 🟡 facts | `n_days: int = 1` 默认值与 4 参调用契约保持（3 参旧调用面靠它翻转为 None） | 写入 V-R2 |
| 🟡 facts | `ALLOW_ADD=True` 是现状（no-op）；真锁仅 `csv_strategy_books.py:105-106` 两行覆写 | V-R3 措辞改 |
| 🟡 双方 | 落点表漏：`csv_daily_backtest.py:590-598`（summarize v8 参数行直接下标 `profit_base/peak_dd_arm/peak_dd_pct`，分钟引擎 :70 复用）、`csv_minute_backtest.py:99/108/110` HELP 文本 | §7 补 |
| 🟡 facts | touch 成交语义：日线按触发价、**分钟按当根 close**（`csv_minute_backtest.py:567-568`） | §1 措辞修 |
| 🟡 facts | 同码单日 chase(9:45)+池买(14:55) 可各 +100 万（双计与「独立样本」意图一致） | §1 声明「单码单日上限 2 笔」；切片 D 资金按 200 万/码/日上界 |
| 🟡 arch-Y1 | 档位判定浮点基准（g 式与价式在 6% 实证分歧；15% 不可精确表示） | **锁价格比较**：`peak` 与 `cost×(1+arm)` 直接比较；单测用 ε 偏移向量（arch 向量表 #6/#10 进切片 A） |
| 🟡 arch-Y6 | band1 允许保本/费用后微亏退出（g→0 线→cost；佣金后 ≈-0.2%） | 业务 70% 回撤的必然推论，**声明不改**；HELP_LOCK 一句 |
| 🟢 arch | 59.3% 平仓 lot 是 days==1 trail 退出 → T+1 豁免重塑小赢分布 | 切片 D 必报「days==1 trail 占比」前后对照 |
| 🟢 arch | E-R5 与 v2 顺序：止盈侧比例线对除权噪音敏感度略升 | 切片 D 短记附除权标注视图；**先 E-R5 复核再 5 亿重跑**为推荐顺序，最终顺序人裁（GO 时定） |
| 🟢 facts | 断言翻转全清单（§4a-f，含易漏 `test_csv_daily_backtest.py:324`） | 切片 B 直接消费该清单 |
| 🟢 facts | pre_er1 fixture 涉 v8 但无内容断言 | 切片 C 注记**禁再生成** |

## 结论

plan v1.1 回写完毕 → READY，待人裁 GO：
- **PG-1**：50%/100% 边界按业务原文（50→三档 / 100→四档）确认；
- **PG-2**：reason 契约 `trail:band:1..5` 确认；
- **PG-3**：band1 保本退出声明接受；
- **PG-4**：E-R5 复核与 v2 重跑顺序（推荐先 E-R5）。
