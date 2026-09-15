# Plan：资金管理模式化 + 策略 8 每股 100 万（daily_quota / per_name 双模式）

> **落盘**：2026-09-16。**v1.1**（2026-09-16 评审修订，见 changelog §10）。
> **状态**：🚧 **v1.1 · 已人裁 GO（2026-09-16），实施中**（分支 `feat/money-modes-v8-pername`，执行：Codex；前置 cerebro-retire 已合入；A–C 完成，D 待宿主检查）。人裁结果见 §3。
> **风险档**：**L1**（研究面引擎参数化 + 策略书切换；不碰成交核 E-R1–E-R4、不碰 1.3、不写湖、不写 `stock_pool/`）。
> **业务源**：MyQuant `docs/bucket_policy/金榕元交易回测策略--0913--策略8.docx`（§1 摘录对照）。
> **工作流**：走 [Codex 交接工作流](workflow-codex-handoff.md)。权威细则：MyQuant `ai-code-review-governance.md`、`multi-ai-review-workflow.md`。
> **前置**：[plan-cerebro-retire-2026-09-16.md](plan-cerebro-retire-2026-09-16.md) 已在 PR #58 完成 A→D，P5 双真源已由 Cerebro 退场消解；#58 已合并（e89d1b8），本 plan A/B 已实施。
> **成交核现锁**：[engine-ashare-correctness.md](engine-ashare-correctness.md)（E-R1–E-R4，本轮不动）。名单契约 [pool-csv-contract.md](pool-csv-contract.md) 不动。
> **实施交接**：[handoff-money-modes-v8-pername-codex-impl-2026-09-16.md](handoff-money-modes-v8-pername-codex-impl-2026-09-16.md)（人裁 GO 后生效）。

---

## 0. 一句话

把共享 CSV 引擎的资金管理从单一「日额度均分」扩成**策略书级双模式**（`daily_quota` 现状 / `per_name` 每股预算），并按 0913 docx 把策略 8 切到「**每股票 100 万 + 止损 30%**」；其余策略 1–6/9/10 默认行为**逐字节不变**。

```text
CsvStrategyBook.sizing = "daily_quota"（1–6/9/10，默认，行为锁死）
                     | "per_name"    （v8 切换目标；每码 name_budget=1M，类 v7 NAME_BUDGET）
run_pool_buys_day：daily_quota → per = min(quota, cash)/n（现状）
                   per_name    → per = name_budget（不除 n；现金不足 skip_cash）
```

---

## 1. 业务需求对照（docx 2026-09-13 原文 → 现状 → 差异）

docx 原文（`金榕元交易回测策略--0913--策略8.docx`）：

> 1. 单个股票金额100万，不够100股在资金池补齐100股
> 2. 止损点：30%
> 3. 止盈：基础止盈15%，0%＜涨幅≤15%，回撤到2%涨幅触发止盈；15%＜涨幅≤40%，回撤到15%触发；40%＜涨幅≤60%→30%；60%＜涨幅≤80%→50%；80%＜涨幅≤100%→70%；100%＜涨幅≤120%→90%；涨幅＞120%，回撤达到最高价\*20%触发止盈
> 三、尾盘涨停不能买入股：T+1日9:45分 市价>开盘价 买入；市价<开盘价 弃买

| # | docx 条款 | 现状（[strategy8_rules.py](../../backtest/research/strategy8_rules.py) / 引擎） | 差异 |
|---|-----------|------|------|
| 1 | 每股票 100 万；不足 100 股补齐 | 每日 100 万均分：`per = min(daily_quota, cash)/n`（[csv_simulate_loop.py:145](../../backtest/research/csv_simulate_loop.py#L145)）；force-min 100 股已有（[csv_ledger.py:168](../../backtest/research/csv_ledger.py#L168) `_buy_size`） | **核心变更**：新增 `per_name` 模式并让 v8 使用；force-min 保留（docx「资金池补齐」条款；**v7 无此行为**，见 M-R2） |
| 2 | 止损 30% | `STOP_PCT = 0.20`；⚠️ Cerebro 侧另有 `ProfitStrategy.py:760` 预设 20% 双真源 | CSV 侧改 `0.30`；Cerebro 真源由前置退场 plan 消解（P5） |
| 3 | 止盈阶梯 | `PROFIT_BASE=0.15`、`BANDS`（(lo,hi] 半开区间：15/40/60/80/100/120 → 15/30/50/70/90 地板）、`PEAK_DD`（>120% 回撤峰价 20%）**已与 docx 一致** | 唯一差异：第一档现行有「须先摸到 +6%」武装（`SMALL_ARM=0.06`，注释「用户口径：2%×2」），docx 未提 → **P1 人裁** |
| 4 | 尾盘涨停不买；T+1 9:45 市价>开盘买、<开盘弃 | 已有（`chase_decision` + `chase:T+1`） | 语义不变；`per_ch` 在 per_name 模式下 = `name_budget` |

**解读锁定（评审 🟡-3 裁决，防后人重读 docx 翻案）**：docx「涨幅」= **持仓期峰值涨幅**（峰值/买价 − 1），峰值 = 持仓期最高价（日线用日 high、分钟用 bar high，T+1 起算；docx 前六档未写峰值来源，此处写死）；「回撤到 X 触发」= 现价 ≤ 买价 ×(1+X)（含等号）；120% 边界点归 90% 地板档。

**引擎时机差距（显式声明，不埋认知雷）**：docx 语义 = 盘中回撤即时触发。日线引擎 = **收盘价确认 → 次日开盘成交**，且不看日内 low（日内击穿地板收盘收回的不触发）——相对 docx **少触发**止盈且成交价带隔夜跳空；分钟版逐分钟评估同 bar 成交，接近 docx 语义。**跨引擎结论以分钟版为准，日线版仅长窗近似**（止损 touch 日线按触发价成交偏乐观、分钟按 bar close 保守，同属此声明族）。

---

## 2. 现状（禁止重做已落地项；锚点经评审核验）

| 已落地 | 锚点 |
|--------|------|
| 总资金 2100 万 `DEFAULT_TOTAL_CASH` | [csv_ledger.py:17](../../backtest/research/csv_ledger.py#L17) |
| 日额度 100 万 `DEFAULT_DAILY_QUOTA`，开盘重置 | [csv_daily_backtest.py:135](../../backtest/research/csv_daily_backtest.py#L135)、:339；分钟 :826 |
| 均分公式 `per = min(daily_quota, st.cash)/len(planned)` | [csv_simulate_loop.py:145](../../backtest/research/csv_simulate_loop.py#L145) |
| 排单 `queue_limit_up_chase`（per_ch 由排单日 `per` 写入） | [csv_simulate_loop.py:164-165](../../backtest/research/csv_simulate_loop.py#L164)；chase 日仅消费（:91/:104/:123） |
| 整百股向下取整 + force-min 100 股 + 补充资金统计 | [csv_ledger.py:168](../../backtest/research/csv_ledger.py#L168) `_buy_size`（force-min :174-177）；`execute_buy` :181（佣金 :198、现金拒单 :199、lot 独立记账 :205-207） |
| v8 卖点阶梯（BANDS/SMALL_ARM/PEAK_DD）、`ALLOW_ADD=True` 多 lot | [strategy8_rules.py](../../backtest/research/strategy8_rules.py)（STOP_PCT :17、SMALL_ARM :20、BANDS :26-32、ALLOW_ADD :14） |
| 策略书注册（name/tag/allow_add/apply/run_kwargs） | [csv_strategy_books.py:40](../../backtest/research/csv_strategy_books.py#L40) `CsvStrategyBook`；`apply_csv_strategy` **:89**，hooks 注入 :92-100（allow_add 注入 :92） |
| 双引擎共享 `run_pool_buys_day` | 日线 [csv_daily_backtest.py:445](../../backtest/research/csv_daily_backtest.py#L445)、分钟 [csv_minute_backtest.py:936](../../backtest/research/csv_minute_backtest.py#L936)（买侧 sizing 全经此二函数；卖侧 `scan_held_day`/pending_exit 与 sizing 无关） |
| v7 每码预算先例 `NAME_BUDGET=1M`、现金不足 `skip_cash`（**无 force-min**） | [csv_minute_backtest_v7.py:48](../../backtest/research/csv_minute_backtest_v7.py#L48)、:188-193 |
| stats 预置 `_empty_stats`（无 skip_cash 键） | [csv_ledger.py:24-54](../../backtest/research/csv_ledger.py#L24)；新增 stats 须 `setdefault` 模式（csv_ledger 本轮禁改） |
| 分钟引擎自动对照 `maybe_compare_daily`（caption「差来自卖点时钟」） | [csv_daily_backtest.py:714/:731-748](../../backtest/research/csv_daily_backtest.py#L714)；分钟 :1091-1095 |

---

## 3. 现锁（M-R\*）

| # | 规则 |
|---|------|
| **M-R1** | sizing 模式是**策略书属性**（`CsvStrategyBook.sizing`），不是全局 CLI 开关。**不加 `--sizing` 参数**（防 1–6/9/10 被误切导致跨策略不可比）。仅加 `--name-budget`（默认 1,000,000）覆盖 per_name 书的预算值。1–6/9/10 书锁 `daily_quota`；v8 书切 `per_name`。 |
| **M-R2** | `per_name` 语义：每码单次买入目标 = `name_budget`，整百股向下取整；**skip_cash 对齐 v7**（`notional+佣金 > st.cash` → 整笔跳过，不缩量、不挪用差额；名单序 = 契约 CSV 序，先到先得）；**force-min 是 docx「资金池补齐」条款、v7 无此行为**（预算 < 100 股市值时强买 100 股，超额记 `supplementary_used` 统计；仅 `--name-budget` 小值可激活）。**偏差声明**：现实 `stock_pool/` 文件为代码升序，现金受限日（21M ≈ 21 码并发上限）的入选集合系统性偏向小代码，早期窗约 45% 名单买不进——名单序语义 = 导出器契约，本 plan 不定义优先级（P4）；切片 D 必须报告逐日 bought/skip/宽度表让偏差可见。stats 增项：`skip_cash`（笔数）、`skip_cash_notional`（被跳过目标金额），经 `setdefault` 写入。 |
| **M-R3** | `per_name` 模式下已持有 → **skip**（`skip_held`），含 chase 当日已持有；**实施硬锁：`apply_csv_strategy`（csv_strategy_books.py:89-105）在 `sizing=="per_name"` 时覆写 `hooks["allow_add"]=False`**（hook 层单点，保证池买 :147 / chase :94 两路径同锁；不许在引擎分支各改一处）。`per_ch = name_budget` 由排单日写入（:164-165），chase 日先 pop 再买，现金不足 = `chase_buy_fail` **永久弃单不重试**（与 v7 同构；排单不冻结现金）。`chase_buy_fail` 拆「现金不足 / shares≤0」计数（后者 force-min 下不可达，出现即 bug）。v8 旧 `ALLOW_ADD=True`（各 lot 独立）仅在 `daily_quota` 模式下保留供历史复跑——两模式行为分叉写入 HELP_LOCK。 |
| **M-R4** | v8 止损改 30%（docx §2；CSV 侧 `strategy8_rules.STOP_PCT`，Cerebro 真源由前置退场 plan 消解）；止盈阶梯维持现行 `BANDS`/`PEAK_DD`（与 docx §3 一致，解读见 §1 锁定段）；第一档武装 `SMALL_ARM=6%` **已裁去武装（P1）**：`band_floor` 第一档分支改为 docx 字面 (0,15%] → 2% 地板。卖出执行时机沿用各引擎现行语义，日线/分钟差距按 §1 声明族对业务显式披露。**止损滑出量化**（连续跌停 defer 下实际成交）：10% 板约 -34%、20% 板约 -45%~-50%、30% 板约 -51%；单 lot 最大亏损 ≈ 0.51M ≈ 21M 的 2.4%——切片 D 从 trades 事后统计实际滑出分布（不动 csv_ledger stats）。 |
| **M-R5** | 回归锁：`daily_quota` 模式默认路径 **trades CSV 逐字节不变**（1–6/9/10 任选两策略 fixture 窗前后对照）。`stats`/`summary.txt` 允许**新增**字段（sizing、name_budget、skip_cash、skip_cash_notional、chase_buy_fail 拆分），既有字段值不得变。**禁止重生成** `tests/fixtures/csv_engine_pre_er1/version8_trades.csv` 静态锚点（`generate_snapshot.py` 不重跑）。`daily_quota_used` 在 per_name 分支不累加并注释 vestigial（现状亦从未参与 enforcement，仅 :202 累加 :339 重置）。 |
| **M-R6** | 不碰：成交核 E-R1–E-R4、佣金、整百股、涨跌停 defer、T+1、`csv_ledger.py` 记账结构（含 `_empty_stats`/`_buy_size`/`execute_buy`）、v7 引擎本体、MyQuant 仓、`stock_pool/`。 |
| **M-R7** | 本轮只做两模式。`equal_risk`（等风险定仓）/ `equity_pct`（净值比例额度）**后置另开 plan**，连枚举占位都不加。 |
| **M-R8** | **对比纪律**（评审 🟡-6）：①跨策略表只允许同 sizing 比 NAV；跨 sizing 只比 lot 级指标（每笔收益分布/胜率/单码敞口），summary 自带 `sizing` 字段做工件自描述。②v8 的 daily_quota 对照基线 = 切换前同窗同池工件（记录基线工件 commit/日期）。③切换后首次宿主烟测**必须先重跑 daily v8（per_name）同窗工件**再做分钟对照（否则 `maybe_compare_daily` 的「差来自卖点时钟」caption 会把 sizing 差错误归因）；或把 caption 触发条件改为双方 sizing 一致——二选一，实施时定，写进交接文档。 |

**人裁点（2026-09-16 已裁，采纳默认）**

| # | 问题 | 裁决 |
|---|------|------|
| **P1** | 第一档止盈是否保留「先摸到 +6% 才武装 +2% 地板」？ | **已裁：按 docx 字面去武装**（删 `SMALL_ARM` + `band_floor` 第一档分支；切片 D 留有/无武装 A/B 数据点；恢复路径=一个常量+多处单测+文案）。 |
| **P2** | `per_name` 模式下 v8 是否取消同码加仓？ | **已裁：取消**。硬锁见 M-R3（hook 层强制 + skip_held/chase_skip_held 单测）。 |
| **P3** | 采纳 M-R8 对比纪律？ | **已裁：采纳**（切片 C/D 落地）。 |
| **P4** | 名单序偏差：现金不足整笔跳过时，入选优先级=名单行序（现实=代码升序）可否接受？ | **已裁：接受现状**（缩量买=无业务背书的第三种语义）；排序列后置另开 plan。 |
| **P5** | v8 止损双真源（Cerebro `ProfitStrategy.py:760`）如何处置？ | **已消解（PR #58，2026-09-16）**：Cerebro 栈已删除（切片 A：`59ba18d`），v8 规则默认止损真源保留 `strategy8_rules.STOP_PCT`（退场时为 20%，本 plan 切片 B 已改为 30%）。[退场 plan](plan-cerebro-retire-2026-09-16.md) 已合并于 e89d1b8；前置满足。 |

---

## 4. 非目标

| 不做 | 原因 |
|------|------|
| 统一 v7 引擎到共享引擎 | 仓位机 ladder/分批止盈语义独立；两模式并存正是本 plan 的结论 |
| `equal_risk` / `equity_pct` 模式 | M-R7 后置 |
| 改 1–6/9/10 的任何默认行为 | 跨策略可比性 |
| 改成交核 / 佣金 / 整百股 / defer | E-R\* 现锁 |
| `--sizing` 全局开关 | M-R1 |
| 改 v8 选股/名单侧 | 本轮只动资金与卖点参数 |
| Cerebro 退场本身 | 前置 plan 管（本 plan 只消费其结果） |

---

## 5. 切片

从**当时 master** 开 `feat/money-modes-v8-pername`。**前置**：cerebro-retire 已合入。A/B 分 commit，D 不阻塞合入。

| 切片 | 做什么 | 完成定义 |
|------|--------|----------|
| **A · 模式框架** | `CsvStrategyBook` 加 `sizing: str = "daily_quota"`、`name_budget: float = 1_000_000.0`；`apply_csv_strategy` 注入 hooks（含 M-R3 的 per_name→allow_add=False 覆写）；`run_pool_buys_day` 加 per_name 分支（skip_cash/skip_cash_notional、daily_quota_used 不累加、chase_buy_fail 拆分）；CLI `--name-budget`；stats 记录 sizing/name_budget | 1–6/9/10 现有测试全绿 + fixture 窗 trades 逐字节对照通过；新增单测：per_name 不均分、skip_cash（含 notional）、chase 排单预算、force-min 用 `--name-budget` 小值构造（budget=3,000、px=40 → 强买 100 股 supp=1,000，**不按 1M 写**）、per_name 同码再现 → skip_held+1 且 add_lots 恒 0 |
| **B · v8 切换** | v8 书 `sizing="per_name"`、`name_budget=1M`；`STOP_PCT 0.30`；**P1 已裁=去武装**（删 `SMALL_ARM` 及 `band_floor` 第一档分支与相关单测）；HELP_LOCK、模块 docstring、`--stop-pct` help（csv_strategy_books.py:136）、summarize 文案更新 | 测试全绿，含：`tests/test_csv_daily_backtest_v8.py`（`test_t1_no_sell_on_entry_day` :40、`test_gap_open_stop_20pct` :59、`test_summarize_v8_params` :195、`test_held_name_adds_independent_lot` :210 四例更新）、`tests/test_strategy8_rules.py::test_stop_hits_20pct`（:36，阈值改 6.989/7.011 对）、`tests/test_csv_minute_backtest_v8.py::test_simulate_held_name_adds_lot`（:233，随 P2 改）；chase 到期日已持 → chase_skip_held 单测 |
| **C · 文档** | README v8 例注（每股 100 万/止损 30%）；**共享引擎 HELP_LOCK 修**（csv_daily_backtest.py:153/:166「按名单均分/每日 100 万」加「资金模式见策略书（v8=每股预算）」、csv_minute_backtest.py:109 同步）；M-R8 ③ 的 caption 修正（若选该路径）；本 plan 状态回写 | review |
| **D · 宿主烟测**（非合入门） | 一窗 v8 per_name vs 切前 daily_quota 工件（基线 commit 记录）；**先重跑 daily per_name 再分钟对照**（M-R8）；输出：逐日 bought/skip/宽度表、NAV 对照、（P1 去武装时）有/无武装 A/B、止损滑出分布（trades 事后算） | `summary.txt` + 对照短记落 `docs/backtest/`；数字不入库 |

---

## 6. 验证命令

```bash
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/test_csv_strategy_books.py tests/test_strategy8_rules.py tests/test_csv_daily_backtest_v8.py tests/test_csv_minute_backtest_v8.py tests/test_csv_daily_backtest.py
# A 切片回归（fixture 窗 trades 前后对照）：
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py --strategy version6 --start <T0> --end <T1> --pool-dir <fixture>
# D 烟测（宿主）：
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py --strategy version8 --start 20251023 --end 20260909
# 旧止损复现回滚路径（如需对照）：
#   --stop-pct 0.2
```

---

## 7. 代码落点（实施分支）

| 文件 | 动作 |
|------|------|
| `backtest/research/csv_strategy_books.py` | `CsvStrategyBook` 加 `sizing`/`name_budget`；`apply_csv_strategy`（:89-105）hooks 注入 + per_name→allow_add=False 覆写；v8 注册项改 per_name；argparse 加 `--name-budget`；`--stop-pct` help（:136）更新 |
| `backtest/research/csv_simulate_loop.py` | `run_pool_buys_day`（:135-172）按模式算 `per` + skip_cash 计数；per_name 分支不累 `daily_quota_used`；`run_chase_due_day` 仅 :94-98 已持分支随 P2 生效（per_ch 逻辑无需改，评审 🟡9） |
| `backtest/research/csv_daily_backtest.py` / `csv_minute_backtest.py` | 调用点透传 sizing/name_budget（:445 / :936）；HELP_LOCK 共享文案（:153/:166、分钟 :109）；重置逻辑不动 |
| `backtest/research/strategy8_rules.py` | `STOP_PCT = 0.30`；模块 docstring（:3）；HELP_LOCK（含模式分叉说明）；（P1 裁去武装则删 SMALL_ARM :20 及 band_floor :38 分支） |
| `tests/test_csv_strategy_books.py` | per_name 模式用例（分配/skip/chase/force-min/allow_add 锁） |
| `tests/test_csv_daily_backtest_v8.py`（:40/:59/:195/:210）、`tests/test_strategy8_rules.py`（:36 及 P1 相关 :17-21/:54-60）、`tests/test_csv_minute_backtest_v8.py`（:233） | 按切片 B 清单更新 |
| `docs/backtest/README.md` | v8 例注 |

禁止改：`csv_ledger.py`（记账/`_buy_size`/`execute_buy`/`_empty_stats`）、`csv_minute_backtest_v7.py`、`docs/architecture/reviews/**`、MyQuant 仓。

---

## 8. 风险

- 名单宽度 × 100 万 > 可用现金时大量 `skip_cash`（21M ≈ 21 码并发上限；早期窗 ~45% 名单买不进且偏向小代码）——预期行为（M-R2 偏差声明 + P4），烟测 D 报告让偏差可见，不是失败。
- 30% 止损与跌停 defer 交互：滑出区间约 -34%~-51%（M-R4 量化），单 lot ≤ 21M 的 2.4%。
- chase 排单累积（per_name 每笔 1M）：到期按排单序先到先得，现金不足**永久弃单**（chase_buy_fail），不预冻结（评审 🟡2 裁决：预冻结引入资金死锁面不值）；现状 daily_quota 单笔 ≤1M/n 几乎不会触发，切换后确定性可触发，靠拆分计数观测。
- summary 新增字段可能碰快照类测试：允许新增字段值，快照断言更新（行为变更非 bug，M-R5 校准断言而非放宽 gate）；**不得重生成** pre_er1 静态 fixture。
- 分钟引擎 `maybe_compare_daily` 混 sizing 误归因（M-R8 ③ 已锁处置）。
- daily_quota 模式既有的静默买败（`csv_simulate_loop.py:172` 返回值被忽略）不改（M-R5 行为锁），两种模式观测面不对称属已知声明。

---

## 9. 修订程序

改 M-R\* 须改本文并回写状态。P1–P5 人裁结果记入 §3 表格。`equal_risk` 等新模式另开 dated plan，不塞进本文件。

## 10. Changelog

- **v1.1**（2026-09-16，吸收两路评审）：新增 M-R8 对比纪律与 P3/P4；P5 从两难改为「前置 cerebro-retire 消解」；P1 默认翻转（去武装）并呈两路分歧；M-R2 补名单序偏差声明 + skip_cash_notional + force-min 措辞修正（v7 无 force-min）；M-R3 加 hook 层 allow_add 硬锁 + chase 弃单终态；M-R4 补解读锁定/时机差距声明/滑出量化；§2 锚点勘误（apply_csv_strategy :89；排单 :164-165；`_empty_stats`）；§7 测试落点补全（test_csv_daily_backtest_v8 / test_strategy8_rules / test_csv_minute_backtest_v8 / `--stop-pct` help / HELP_LOCK 共享文案）；§8 补 fixture 禁重生成、caption 陷阱、静默买败声明。
- **v1.0**（2026-09-16）：初稿。

---

## 11. 实施记录（Codex 随本 PR 回写）

| 切片 | 状态 | commit | 备注 |
|------|------|--------|------|
| A · 模式框架 | ✅ | `c63c0a4` | 579 passed / 3 skipped；新增 summary 用例后策略书 26 passed；策略 1/6 trades 与 9f4303c 基线逐字节一致；静态 pre_er1 未动 |
| B · v8 切换（P1 去武装已裁） | ✅ | `12d1910` | 前置 e89d1b8 已合入；六文件门禁 141 passed；ST 名称门禁显式走历史 daily_quota 加仓路径，保留断言 |
| C · 文档 | ✅ | 本切片提交（见 git log） | README / 共享 HELP_LOCK 已同步；M-R8③ 选先重跑 daily per_name 的流程锁，已写回交接 |
| D · 宿主烟测（非合入门） | ☐ | | |
