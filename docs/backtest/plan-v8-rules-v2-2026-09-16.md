# Plan：策略 8 规则 v2（0916 业务修订：加仓恢复 + 涨幅比例回撤阶梯 + T+1 止盈豁免）

> **落盘**：2026-09-16。**v1.1**（2026-09-16 两路评审修订，见 changelog §10）。
> **状态**：✅ **v1.1 · A/B/C 已实施**（分支 `feat/v8-rules-v2`，执行：Codex；切片 D 仍挂 E-R5 复核结论之后）。评审记录：[zcode-facts](../architecture/reviews/2026-09-16/plan-v8-rules-v2/zcode-facts.md) / [zcode-arch](../architecture/reviews/2026-09-16/plan-v8-rules-v2/zcode-arch.md) / [merge-consensus](../architecture/reviews/2026-09-16/plan-v8-rules-v2/merge-consensus.md)。
> **风险档**：**L1+**（触及 v8 卖点语义与 per_name 加仓锁——均为业务明示修订；不动成交核 E-R1–E-R5、不动 1–6/9/10）。
> **工作流**：走 [Codex 交接工作流](workflow-codex-handoff.md)。
> **业务源**：对话给定「金榕元回测交易策略8」修订版（2026-09-16），歧义已裁（§3）。
> **取代关系**：取代 money-modes 的 M-R3「per_name 已持跳过」/ P2「取消加仓」/ P1 档位表；M-R8 对比纪律、5 亿标准口径（PR #80）不变。
> **实施交接**：[handoff-v8-rules-v2-codex-impl-2026-09-16.md](handoff-v8-rules-v2-codex-impl-2026-09-16.md)（GO 后生效）。

---

## 0. 一句话

按业务修订版重写 strategy8 卖点：**恢复同码加仓（独立 lot 各 100 万）**、止盈从「绝对地板阶梯」改为「**涨幅比例回撤阶梯 + g≥15% 全局 +15% 底**」、**T+1 只评估止损不评估止盈**（峰值从 T+1 累计）；止损 30% 与追买三句不变。

## 1. 新规则精确数学（唯一权威定义）

记 `cost`=买价（lot 各自），`peak`=持仓期最高价（**从 T+1 起累计**——两引擎现状已满足：分钟 `csv_minute_backtest.py:552-554`、日线 `csv_daily_backtest.py:401`），`g = peak/cost − 1`，`px`=现价。

**所有档共同前置：`px ≥ cost` 才可止盈**（现状守卫 `strategy8_rules.py:78-79` 保留；跌破成本交止损侧）。

**止损**（不变）：T+1 起评估；`px ≤ cost×0.70` 触发。成交语义不变：日线 gap-open 按 open / touch 按触发价；**分钟 touch 按当根分钟 close**（`csv_minute_backtest.py:567-568`）。

**止盈**（重写；**n_days≥2 才评估**——T+1 不做止盈计算；峰值照常含 T+1 的 high）：

| 档 | 峰值涨幅区间（**按业务原文开闭**） | 触发条件（px ≤） | reason |
|---|---|---|---|
| — | g ≤ 0 | 不触发（止损兜底） | — |
| 1 | (0%, 6%) | `cost + 0.30×(peak−cost)`（回撤掉涨幅的 70%） | `trail:band:1` |
| 2 | [6%, 15%) | `cost × 1.02`（绝对 +2% 地板） | `trail:band:2` |
| 3 | [15%, 50%] | `max(cost × 1.15, cost + 0.60×(peak−cost))`（g≥15% 全局底） | `trail:band:3` |
| 4 | (50%, 100%] | `cost + 0.70×(peak−cost)` | `trail:band:4` |
| 5 | (100%, ∞) | `cost + 0.80×(peak−cost)` | `trail:band:5` |

- **档位判定用价格比较**（`peak` 与 `cost×(1+arm)` 直接比较；不用 `peak/cost−1` 浮点 g——6%/15% 处两种写法实证分歧，见 arch 评审 Y1）。
- reason 契约：**`trail:band:{1..5}`**（档序号）；`trail:` 前缀保 `sell_trail` 统计分类（`csv_ledger.py:248-249`）；`trail:peak_dd`/旧 `trail:band:N地板值` 退役；band3 的全局底/比例线出口共用 band3。
- 已知声明（业务推论，非缺陷）：档 1 在 g→0 时触发线→cost，**允许保本乃至费用后微亏（双边佣金 ≈-0.2%）退出**；档 2→3 在 15% 处保护线从 +2% 跳 +15%（业务裁的全局底）。
- 卖出为整 lot 卖出；多 lot 并存逐 lot 独立评估（现状机制）。

**加仓（恢复）**：per_name 下同码可再次买入，每次进场独立 100 万、独立 cost/peak/止损止盈/lot_id；**单码单日上限 2 笔**（chase 9:45 + 池买 14:55 各一，两个独立信号）；「独立样本」= 记账独立非风险独立（同码 lot 完全正相关，单码敞口无上限仅现金约束）。

**追买（不变，已核 `csv_simulate_loop.py:123-141` + `csv_ledger.py:105-111`）**：T+1 9:45 市价>开盘买 / <开盘弃 / 涨停弃（pop 在判定前）。

## 2. 现锁（V-R\*）

| # | 规则 |
|---|------|
| **V-R1** | 只改 strategy8 规则与 per_name 加仓锁；**1–6/9/10 行为逐字节不变**（v9/v10 为 daily_quota 且 ALLOW_ADD=False，不经覆写分支——评审 G4 证）；成交核 E-R1–E-R5、佣金、整百股、T+1、涨跌停 defer 不动。 |
| **V-R2** | 阶梯实现落 `strategy8_rules.py` 纯函数（band 数据化：arm 上界 + keep 比例 + 绝对底 + 价格比较判定）；`take_profit_reason` 加 `n_days<2 → None`（**签名默认 `n_days: int = 1` 与 4 参位置调用契约保持不变**）；peak 累计两引擎现状已满足（评审 §2 证），不改。 |
| **V-R3** | 加仓恢复 = 删 `apply_csv_strategy` 的 per_name→allow_add=False 两行覆写（`csv_strategy_books.py:105-106`）；`strategy8_rules.py:14 ALLOW_ADD=True` 现状已满足无需动。 |
| **V-R4** | golden（1/6 号书 byte-identical）必须不红；v8 断言按 [facts 评审 §4 清单](../architecture/reviews/2026-09-16/plan-v8-rules-v2/zcode-facts.md) 翻转（含易漏 `tests/test_csv_daily_backtest.py:324`）；`record_strategy8_params` 的 stats 键与 summarize 同步改（见 §7）。 |
| **V-R5** | `n_days≥2` 门经 rules 函数单点覆盖两引擎（评审 G1 证：两引擎均位置实参传 n_days）；numba 路径对 v8 不可达（G2），无需同步。 |
| **V-R6** | 5 亿标准口径与 M-R8 纪律不变；切片 D 双引擎重测峰值并发（**日线是资金风险侧**：v1 峰值 495 只/4.43 亿，v2 加仓+持有延长可能触顶；分钟侧先行估计 230-260 只安全）。 |

## 3. 人裁记录与待裁

**已裁（2026-09-16，业务/评审共识）**：阶梯语法=回撤幅度占最高涨幅比例（70/40/30/20）；g≥15% 全局底=买价×1.15；T+1 只评止损（峰值从 T+1 累计）；同码可加仓独立 100 万。

**待人裁 GO（PG）**：

| # | 问题 | 建议 |
|---|------|------|
| **PG-1** | 50%/100% 边界 | **已裁**：按业务原文（50%→档3、100%→档4） |
| **PG-2** | reason 契约 | **已裁**：`trail:band:1..5` |
| **PG-3** | 档 1 保本/微亏退出 | **已裁**：接受，HELP_LOCK 声明 |
| **PG-4** | E-R5 复核与 v2 顺序 | **已裁：先 E-R5 复核**；v2 切片 A/B/C 先行（无重跑依赖），**切片 D 挂 E-R5 复核结论后执行** |

## 4. 非目标

不做：改 1–6/9/10 任何规则；改成交核/佣金/T+1 语义；复权实施（E-R5 复核另裁）；改名单契约与 5 亿口径；v7；单码敞口上限参数（若 D 实测超资金，选项清单见 §8，业务另裁）。

## 5. 切片

从当时 master 开 `feat/v8-rules-v2`。A/B 分 commit。

| 切片 | 做什么 | 完成定义 |
|------|--------|----------|
| **A · rules 重写** | `strategy8_rules.py`：band 数据化 + 价格比较 + `n_days<2` 门 + reason 契约 + px≥cost 守卫保留 + docstring/HELP_LOCK/record stats；单测按 [arch 向量表](../architecture/reviews/2026-09-16/plan-v8-rules-v2/zcode-arch.md)（必收 #6/#10/#14/#16/#20/#21/#22）+ facts §4a 重写 | 全绿；1–6/9/10 golden 不红 |
| **B · 引擎放开 + 断言校准** | 删 `csv_strategy_books.py:105-106` 覆写；按 facts §4b-f 清单翻转断言；summarize v8 参数行（`csv_daily_backtest.py:590-598`）与 stats 键同步；引擎级向量 #21（minute scan 级 + daily simulate 级各一） | 全量 pytest 绿；fixture 窗 1–6/9/10 trades 逐字节不变 |
| **C · 文档** | HELP_LOCK 全部 stale 文案（`strategy8_rules.py:92-96`、`csv_daily_backtest.py:152-153`、`csv_minute_backtest.py:99/108/110`）+ README v8 段；**注记禁再生成 `tests/fixtures/csv_engine_pre_er1/`**（v8 快照将过期但无内容断言）；归档 plan 头部取代注记；本 plan 回写 | review |
| **D · 宿主 5 亿重跑**（非合入门） | 双引擎重跑 + research_* 四表再生成（宿主动作，仓内无脚本）；必报：**days==1 trail 退出占比前后对照**（v1=59.3%）、双引擎峰值并发/资金峰值、v2-vs-v1 卖因分解；若超 5 亿 → 选项报业务 | 短记落 docs/backtest/；数字不入库 |

## 6. 验证命令

```bash
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/test_strategy8_rules.py tests/test_csv_daily_backtest_v8.py tests/test_csv_minute_backtest_v8.py tests/test_csv_strategy_books.py tests/test_csv_daily_backtest.py tests/test_csv_minute_backtest.py
```

## 7. 代码落点

| 文件 | 动作 |
|------|------|
| `backtest/research/strategy8_rules.py` | band 数据化（arm/keep/绝对底）、价格比较、`n_days` 门、reason 契约、ALLOW_ADD 确认、docstring/HELP_LOCK/record stats |
| `backtest/research/csv_strategy_books.py` | 删 :105-106 覆写 |
| `backtest/research/csv_daily_backtest.py` | summarize v8 参数行（:590-598，**直接下标 `profit_base/peak_dd_arm/peak_dd_pct`，与 stats 键同步**）；HELP_LOCK :152-153 |
| `backtest/research/csv_minute_backtest.py` | HELP 文本 :99/:108/:110 |
| `tests/`（四文件 + `test_csv_daily_backtest.py:324`） | 按 facts §4 清单 |
| `docs/backtest/README.md`、归档 plan 头注记 | 文案 |

禁止改：`csv_ledger.py`、`csv_simulate_loop.py`、成交核、v7、1–6/9/10 书。

## 8. 风险

- **日线资金峰值**（§5-D 已锁重测）：v1 日线 495 只/4.43 亿 + 加仓 + T+1 持有延长 → 可能触 5 亿上限。超了报业务四选项：(i) 提 cash-total（改标准口径需人裁）(ii) 单码上限参数（新锁）(iii) 接受 skip_cash+配给观测 (iv) name_budget 改单码累计（语义变更，不建议顺手做）。
- **小赢分布重塑**：T+1 豁免推迟 59% 平仓样本的出口——是业务意图，但对照短记必须报占比变化防误读。
- **与 E-R5 叠加**：止损侧正交；止盈侧比例线档位对除权噪音敏感度略升（假触发集中在档 1/2 边缘微利位）——顺序建议见 PG-4。
- 断言翻转遗漏：facts §4 清单已全量（评审逐行核对过）。

## 9. 修订程序

改 V-R\*/规则表须改本文并回写；业务改档位值=改 band 数据。

## 10. Changelog

- **v1.1**（2026-09-16，两路评审）：档位边界按业务原文修正（50%→档3、100%→档4，删矛盾脚注）；补 px≥cost 前置与 reason 契约 `trail:band:1..5`；档位判定锁价格比较；n_days 默认值契约；V-R3 措辞（ALLOW_ADD 现状）；落点补 summarize/minute HELP；touch 语义措辞；单码单日 2 笔上限声明；切片 A 收边界向量表、B 收断言翻转清单、C 收 pre_er1 禁再生成、D 收 days==1 占比对照与双引擎峰值重测；§8 补资金四选项与 E-R5 叠加措辞。
- **v1.0**（2026-09-16）：初稿。

---

## 11. 实施记录（Codex 随本 PR 回写）

| 切片 | 状态 | commit | 备注 |
|------|------|--------|------|
| A · rules 重写 | ✅ | `241b607` | 向量表必收 #6/#10/#14/#16/#20/#21/#22；arch #6/#10/#22 期望与 plan 价式偶有出入，以 plan §1 为准 |
| B · 引擎放开 + 断言校准 | ✅ | `5176cab` | facts §4 翻转；`:88-93` 推演日价与引擎不符→按代码 `20251107@11.7 trail:band:3`；引擎向量 #21 |
| C · 文档 | ✅ | tip | HELP/README/归档取代注记/pre_er1 禁再生成 |
| D · 宿主 5 亿重跑 | ⏸ | | **挂 E-R5 复核结论后**（PG-4） |
