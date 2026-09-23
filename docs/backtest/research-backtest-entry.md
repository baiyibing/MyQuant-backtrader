# 本仓回测研究入口

> **日期**：2026-09-22  
> **这份文档管什么**：本仓向量化回测在做什么、名单从哪来、策略号 / Mode A/B / TopK 怎么挂到同一件「收益最大化」上。  
> **这份文档不管什么**：成交核数字（档位 / 跌停 / 除权）见 [engine-ashare-correctness.md](engine-ashare-correctness.md)；复制粘贴命令见 [README.md](README.md)；三件引擎分工见 [engine-positioning-ssot.md](engine-positioning-ssot.md)。

本仓回测不是一堆互不相关的策略名。共同问题是：

**给定一份按日的买入名单（信号），在向量化引擎上把买卖规则调到总收益最大。**

分类轴有两条，Grok Bot 探索刀再加一问：

1. **名单从哪来**（`stock_pool` / qlib pred / 海龟 / 独立导出器）  
2. **规则怎么搜**（人工改书 / 机器网格 / 分数轮换 / 冻结意图回放）  
3. **问的是什么**（总收益最大化，还是成交时钟 / 滑点 / 引擎合同）

策略 1–12、Mode A/B、TopK、以及 Grok Bot 还在跑的探索，都先落到这三格再谈数字。换书不等于换宇宙；不同名单、不同现金、不同成交时钟、不同问题的净值不能直接排名。

三仓分工不变：MyQuant 出信号（及 qlib 分），本仓做向量化研究，OSkhQuant1.3 做执行验收。本仓没有 `python -m backtest.lebs`。Qlib `PortAnaRecord` 停用；Cerebro / Rolling 已退场。

---

## 1. 三份主名单

日名单契约统一：`YYYYMMDD.csv`、首列裸六位码。细则 [pool-csv-contract.md](pool-csv-contract.md)。`stock_pool/` 是可变默认树，**不是**实验快照；可复现跑用 `exports/` + `--pool-dir`。

| 名单 | 典型路径 | 信号怎么来 | 挂在这棵树上的实验 |
|------|----------|------------|--------------------|
| **`stock_pool`** | 本仓 `stock_pool/`（1–6/8/12 省略 `--pool-dir` 时的默认） | 人工日名单（确认人维护；不是全市场、不是 qlib TopK） | 策略 1–6、**策略 8 / 8.x / 12**（人工改书）、**Mode A/B**（机器网格） |
| **qlib / pred** | MyQuant `export_daily_pool.py` → `exports/…`；或 `--pred-csv` / `--scores-dir`；**另一条**走冻结 `intents.csv`（不是日 CSV 池） | 模型日分 | **`topk_dropout` / `topk_score_exit`**（CSV 书、引擎实仓轮换）；**joint-return-v1**（MQ 出意图、本仓分钟回放，见 §5） |
| **海龟** | 1.3 `stock_pool_turtle/`（本仓策略 7 **必须** `--pool-dir`，不回落 `stock_pool/`） | 海龟/金榕元选股日名单 | **策略 7** 金榕元仓位机 |

这三棵树不是同一宇宙。pred Top10 与手工 `stock_pool` 几乎不重叠（[m5-list-attribution-2026-03-09.md](m5-list-attribution-2026-03-09.md)）。策略 7 ≠ 1.3 LEBS turtle ≠ Paper 海龟：池和仓位机都不是一份。

---

## 2. 其他发信号方式

主名单之外，还有独立导出器。它们**自己写一份** `YYYYMMDD.csv` 树，再交给共用引擎；禁止默默改用 `stock_pool/`。

| 信号 | 导出 | 书 / 入口 | 备注 |
|------|------|-----------|------|
| 底量超顶量 | `scripts/data/export_strategy9_pool.py` | `--strategy version9` | 必须 `--pool-dir`；指向 `stock_pool/` 立即退出 |
| 换手阻力 / 源 B | `scripts/data/export_ta_pool.py` | `--strategy version10`（卖点冻结策略 6 旧公式） | 湖当日有 K；不做 TopK；拒绝 `stock_pool/` |
| ma_chip | `scripts/data/export_strategy11_pool.py` → `<out>/pool/` | `--strategy version11` | 拒绝 `stock_pool/`；框架验证非已验证多头 |
| app ∩ qlib TopK | `scripts/data/export_topk_app_dropout_pool.py`（可选） | `csv_minute_backtest_topk_app_dropout.py` | **不是** `topk_dropout`；仓位机借策略 7 函数，不改 v7；禁止 register 进 1–10 BOOKS |

以后若再出现新信号（别的因子、别的人工池、别的模型分），先问：它是**新的一棵名单树**，还是旧树上换了一本书。新树走 `exports/` + 显式 `--pool-dir`；不要写进可变 `stock_pool/`。

---

## 3. 同一份名单上的两种搜法：策略 8 vs Mode A/B

这是 `stock_pool` 上最容易撞名的一对。

给定同一窗口（典型 `20251023–20260909`）、同一棵 `stock_pool/`，目标都是把**总收益率**做上去。差别只在谁在搜规则：

| | **策略 8（及 8.x / 12）** | **Mode A / Mode B** |
|--|---------------------------|---------------------|
| 是什么 | 一本完整交易书（买、加仓、止损、止盈、僵持、涨停保留、上证十日线门） | 不是策略号。统一卖出规则的**网格**，两种成交时钟 |
| 怎么搜 | **人工**：一次改一个旋钮，跑分钟 5 亿看净值。证据：`docs/backtest/plan-v8-*.md` 三十多份 + README 归档目录 | **机器**：固定 N 天 / 止盈止损 / 移动止损，全扫参数 |
| 现行入口 | `--strategy version8`；现行宿主包 `stop10-max101-80-gap15-reserve-stale8` | `scripts/research/run_unified_exit_modea.py` / `run_unified_exit_modeb.py` |
| 和对方的关系 | 金榕元系列前三版（0911/0913/0916）落在策略 8；第 4 版买侧骨架 + 均线出场 = **策略 12** | 提案明确**故意不抄**策略 8 的买卖规则（Q18：除名单和交易所规则外可以探索），避免人工书锁死搜索空间 |
| 净值 | `csv_minute_v8_*`（常 5 亿） | `backtest_output/unified_exit_modea/` · `unified_exit_modeb/`（名义现金 11 亿） |

两者**不能拿净值直接排名**（提案 [§9.3](stock-backtest-unified-exit-proposal-2026-09-17.md)）：买入价、涨停追不追、现金池、同码再上名单、上证门、加仓台阶都不一样。同一问题、两套搜法。

- 策略 8 计划入口：[plan-v8-stop10-max101-80-gap15-reserve-stale8-2026-09-19.md](plan-v8-stop10-max101-80-gap15-reserve-stale8-2026-09-19.md)（现行包）；规则 v2 起点：[plan-v8-rules-v2-2026-09-16.md](plan-v8-rules-v2-2026-09-16.md)
- Mode A/B 提案：[stock-backtest-unified-exit-proposal-2026-09-17.md](stock-backtest-unified-exit-proposal-2026-09-17.md)
- 策略 12：[plan-strategy12-jinrongyuan-2026-09-21.md](plan-strategy12-jinrongyuan-2026-09-21.md)

策略 1–6 也是 `stock_pool` 上的人工书（卖点更早、更简单）；策略 6 仍是常用对照。它们和策略 8 共用引擎，不是另一份名单。

---

## 4. 策略号对照

共用日线 / 分钟入口：`backtest/research/csv_daily_backtest.py` / `csv_minute_backtest.py`。必须 `--strategy`，无缺省。规则正文以各书 `HELP_LOCK` 为准。

| 号 / 名 | 默认名单 | 搜法 | 一句话 |
|---------|----------|------|--------|
| version1…5 | `stock_pool/` | 人工书 | 早期卖点（止损/回撤/涨停保留/均线/2% 止盈等）；已持通常不叠加 lot |
| version6 | `stock_pool/` | 人工书 | 名单加仓 + 2% 止损 + 分档回撤；`daily_quota` |
| version7 | **海龟池，必填 `--pool-dir`** | 人工仓位机 | 独立入口 `csv_minute_backtest_v7.py`，不进 1–10 BOOKS |
| version8 / 8.1 / 8.2 / 8.3 | `stock_pool/` | **人工优化主线** | per_name 100 万；8.x 为冻结里程碑，不要当现行宿主书 |
| version9 | 导出器，拒绝 `stock_pool/` | 人工书 + 独立买点 | 底量超顶量；止损 8%、满 20 日强平 |
| version10 | 导出器，拒绝 `stock_pool/` | 人工书 + 独立买点 | TR 源 B；卖点冻结 v6 旧公式 |
| version11 | 导出器，拒绝 `stock_pool/` | 人工书 + 独立买点 | ma_chip CSV 移植 |
| version12 | `stock_pool/` | 人工书（金榕元第 4 版） | v8 买侧骨架 + MA5/MA10 减仓买回 |
| **topk_dropout** | pred 分 + `--pool-dir` 日历 | 分数轮换 | qlib TopkDropout 底座；联合研究页 [topk-joint-research-tracker-2026-09-22.md](topk-joint-research-tracker-2026-09-22.md) |
| topk_score_exit | 同 dropout | 分数轮换 + 额外卖 | 持仓当日 score≤0 再卖一刀；不是 app 池 |
| topk_app_dropout | app ∩ TopK | 求交后走 v7 仓位机函数 | 独立 CLI；不是 50/5 实仓 dropout |
| **Mode A** | `stock_pool/` | **机器网格** | 日线收盘买、日线收盘卖 |
| **Mode B** | `stock_pool/` | **机器网格** | 日线收盘买、分钟缺口/收盘卖 |
| **joint-return-v1** | qlib 分 → MQ `intents.csv`（**不是** `stock_pool/`，也不是 TopK 日 CSV） | 冻结组合约束 + 分钟回放 | 隔离研究链；**不是** `--strategy topk_dropout`。见 §5 |

`live_pool/*sell.csv` 不能当多日卖出。禁止「今日池 CSV 没有就清仓」来冒充 TopK 轮换。

---

## 5. Grok Bot 还在做的探索（怎么归类、具体是什么）

**Grok Bot ≠ 第四份名单。** 机器分工是：文档/编码/data-free 在 **Grok Bot 虚拟机**（Codex），重数在 **4090 物理机**（没有 Codex）。它跑的刀有的是收益最大化，有的只问「成交假设变了数字怎么变」。先按「问什么」分开，再挂回 §1 的名单。

### 5.1 还在推进：joint-return-v1（qlib 分家族 · 冻结意图回放）

这是 **qlib bot 9/21 主线、今天交给 bt 续跑** 的那条，不是 `--strategy topk_dropout`。交接正文：[handoff-joint-return-qlib-to-bt-2026-09-22.md](handoff-joint-return-qlib-to-bt-2026-09-22.md)。9/21–9/22 事项账见 §5.6。

| 格 | 填什么 |
|----|--------|
| 名单 | MyQuant 冻结 pred（研究默认 **50/5**，不改线上 10/3）→ `intents.csv` + manifest。**没有** `YYYYMMDD.csv` 日池 |
| 搜法 | MQ 先做**组合约束**（只开 P-BASE；chase / 弱信号 / anti / Mode B 分列堵住），本仓**不重新选票、不改数量**，只回放成交 |
| 问什么 | 「信息有、组合没」：同一信号如何成仓；分钟延迟会不会把净超额吃掉。验收看换手 / 回撤 / 净超额，**不看 RankIC** |
| 现在卡哪 | 约束 **PASS**；旧钟收窄回放 **0 成交**（BUG_ALIGNMENT：15:03/16:00 空窗口）。MQ #97 时钟已合。4090 **只重出** `narrow_clock_20260922` pack。**Mode B 停**，等 P-BASE 有真实成交后由 **bt 主管**开真湖 |

不要把约束 PASS、旧钟 0 成交 NAV、或 `topk_dropout` CSV 书对一个数。

### 5.2 已收口但仍常被当成「Grok 在探索」：Mode A/B · 甲/乙利弗莫尔（`stock_pool` · 收益最大化）

这是 Q18「除名单和交易所规则外天马行空」那条探索，**已经跑完宿主 E**，不是 joint-return。

| 实验 | 名单 | 搜法 | 具体是什么 | 结论口径 |
|------|------|------|------------|----------|
| **Mode A** | `stock_pool` | 机器网格 | 日线收盘买、日线收盘卖；固定 N / 止盈止损 / trailing | 11 亿名义池；见统一卖出提案 |
| **Mode B** | 同上 | 机器网格 | 买仍是名单日收盘；卖改为分钟 **open 缺口再 close 触价**（Q39） | 与 Mode A、与 v8 分钟包都不可混排 |
| **甲 · 利弗莫尔** | 同上（Mode B 那 4169 笔实开） | 只换卖点 / 路径状态 | `livermore_l2_stale8_y10` 等臂；**不是**策略 8 入场 | 扁平 +10% 止盈赢过抄 v8 档；L3「坐住」证伪。**不再给这 4169 笔加卖点旋钮** |
| **乙** | 同上 | 人工书 | **整本策略 8**（14:55 试探、只加赢家、上证门、5 亿），不是 Mode B 的又一行 | 甲/乙两本账，净值不得混排 |

短记：[livermore-jia-yi-host-note-2026-09-17.md](livermore-jia-yi-host-note-2026-09-17.md) · [unified-exit-modeb-host-note-2026-09-17.md](unified-exit-modeb-host-note-2026-09-17.md)

### 5.3 不是收益排名：分钟敏感对照 B（时钟 / 滑点）

Grok Bot 在 4090 填过 batch1–4，问的是 **fill 假设**，不是「哪本书更赚钱」。

- 对象分列：**Book**（1–8 等，默认 `stock_pool`）、**策略 7**（海龟池）、**Mode B**（`stock_pool` 网格）。禁止跨引擎比 NAV
- 轴：局部事件价（batch1–2）、Mode B `next_tradable_open`（batch3）、全策略默认时钟 NAV 缺口 + research-only clock/slip hooks（batch4 / Slice D，戳 `batch4_fullstrat_hooks_d_20260921b`）
- 局部 bp **不准**贴进全策略 NAV 表。`production_C=frozen`（生产 fill / scan / fee / 默认时钟不动）
- version9 / version10 基线用的是 **s9_bvot / s10_tr 导出池**，不是 `stock_pool`，不能和 Book v8 行重排

计划 / 结果：[plan-minute-sensitivity-b-2026-09-20.md](reviews/plan-minute-sensitivity-b-2026-09-20.md) · [batch4 结果](reviews/results-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md)

### 5.4 不要算进「名单收益实验」的 Grok 刀

| 刀 | 问什么 | 状态 |
|----|--------|------|
| 策略 11 Slice D（seed-30 vs 静态档案） | ma_chip CSV 对照，**不宣称收益** | 先 STOP（Grok Bot VM 到不了 4090）；后宿主已跑 seed-30 导出 + 日频冒烟，**`ma_chip_edge_*` 对照仍缺档**（§5.5） |
| industry-align P3（δ1–δ6 费率 / 除权 / ST / volume） | 成交核合同，不是选股 | 研究合同文档化；生产路径多数冻结 |
| 架构 fan-out 评审（`docs/architecture/reviews/**/grok.md`） | 计划 / PR 核对 | 不是回测跑数 |

这些可以在工程专题页跟，**不要**开成策略 13，也**不要**和 §1 三份名单的 NAV 表混排。

### 5.5 2026-09-21 Grok Bot BT 经手账（按线收，不是第四份名单）

昨日 BT 侧经手的是 **实施 / 补洞 / 敏感格**，多数**不是** §1 的收益最大化探索。生产 **fill / scan / fee 全天冻结**（`production_C=frozen`）。下面按线归类；数字只作该线内部对照，禁止跨池、跨引擎、跨问法排名。

| 线 | 归到哪 | 9/21 做了什么 | 进度（核对日 2026-09-22） |
|----|--------|----------------|---------------------------|
| **1. batch4 version10 补洞** | §2 源 B 名单 + §5.3 敏感格 | TR store 刷窗 → `export_ta_pool` 写 `s10_tr`（**不是** `stock_pool/`）→ Book v10 baseline → docs [#149](https://github.com/baiyibing/MyQuant-backtrader/pull/149) | **完成并合入** `dbefea8`。窗内 NAV **+0.12%** / DD **−0.06%**。同窗 v9（`s9_bvot`）+0.25% 只作对照，**禁止**与 v8/`stock_pool` 重排 |
| **2a. ma_infra** | 工程基建（均线口径），不是策略号 | [#150](https://github.com/baiyibing/MyQuant-backtrader/pull/150) handoff → [#154](https://github.com/baiyibing/MyQuant-backtrader/pull/154) 实现 | **已合** |
| **2b. strategy12 A–C** | `stock_pool` 人工书（金榕元第 4 版） | [#151](https://github.com/baiyibing/MyQuant-backtrader/pull/151)：latch=A、残差=2、S1 部分卖丢股修 | **已合** |
| **2c. version11 A–C** | §2 ma_chip 导出树 | [#152](https://github.com/baiyibing/MyQuant-backtrader/pull/152) A–C 已合。Slice D 静态对照缺 `ma_chip_edge_*` 曾 STOP；后来宿主装了真 `turnover_resist` pyd，seed-30 导出 + 日频冒烟已跑，**对照仍缺档** | 主实施 **完成**；静态对照 **仍欠** `backtest_output/ma_chip_edge_*` 路径 |
| **2d. #158 价域 follow-up** | 策略 12 分钟契约，不是新网格 | 分钟允许 `--dividend-type none`、日线信号固定 `front`；缺 `1m/front` fail-closed；混合域禁止静默双重除权 | 代码 **已合** `161f13a`。日线五本只落了 **paths-only** 短记（[slice-d-daily-front-smoke](reviews/slice-d-daily-front-smoke-newtest_4090-2026-09-21.md)，**无 NAV**）。**分钟五本**（s12 + v8/8_1/8_2/8_3，`--dividend-type none`，窗 20251023–20260909）昨晚还在 4090 跑，**仓库内仍无结果回填** |
| **3. fullstrat clock/slip** | §5.3 研究钩子，不是生产成交 | [#156](https://github.com/baiyibing/MyQuant-backtrader/pull/156)：H2 全 fill next-open + Q2 按成交价重定量。4090 填格 → docs [#159](https://github.com/baiyibing/MyQuant-backtrader/pull/159) | **这条线收完**（合入 `12e6d43`） |
| **4. 人裁（过程里反复停）** | 书契约，不是搜参 | #151 latch/残差；#152 契约日 + 周线 prefix + 量能闸；#156 H2 / 卖单过期次日重评 / Q2 定量；分钟湖无 front → **分钟 none + 日线 front** | **均已裁定并落地** |

9/21 晚还挂着、**今天已变**的：

| 项 | 9/21 晚 | 2026-09-22 核对 |
|----|---------|-----------------|
| [#160](https://github.com/baiyibing/MyQuant-backtrader/pull/160) Cargo.lock 刷新 | OPEN | **已合**（工程，与名单收益无关） |
| [#161](https://github.com/baiyibing/MyQuant-backtrader/pull/161) Rust host 移交 1.3 | OPEN | **已合**（工程文档，与名单收益无关） |
| #152 `ma_chip_edge_*` 对照 | 缺路径 | **仍缺** |
| #158 分钟五本是否 docs 回填 | 还在跑 | **仍未落文档**（只有日线 paths-only） |

还没收的两件都不是新策略号：一件是 v11 静态档案路径，一件是 s12 分钟五本的宿主数字要不要写进 `docs/backtest/reviews/`。要续核就只核这两件，不要重开 fill/scan/fee。

### 5.6 2026-09-21 Grok Bot **qlib** 经手账（联合收益一条线）

qlib 昨天盯的是 **MQ 组合约束真数**，不是 BT 的 #149/#151/#156。顺序：

**约束真数（已 PASS）→ 成交/NAV 实测（现在重出时钟 pack）→ Mode B 真湖（bt 主管，未开）**

| 事项 | 9/21 | 9/22 核对 |
|------|------|-----------|
| **1. 组合约束真数** control_only → P-BASE | 催 4090：plans → freeze 缺字段挂 → 补齐 freeze → portfolio；因 BT `code_shas` 旧 tip 停掉未落盘的旧跑，对齐后重开 | **已收口**。约束审计 PASS（~7.2h）。产物 `runs/.../portfolio/joint-return-control-only-50-5/`（2470 intents）。换手/回撤/净超额 **NOT_RUN** 是合同分界（这步不出成交），不是白跑 |
| **2. 瘦合同 MQ #95** | 只拿它跑真数，代码无新刀 | **保持关闭**（9/20 已合） |
| **3. 与 bt 的约束交接** | 只读线交过来，未另起平行大计划 | **已对齐，无新阻塞** |
| **4. 未动** | 线上 10/3、pred、anti/弱信号、Mode B 真湖未开 | **仍挂**。完整收益不在昨天账上 |

今天新开、且已交给 bt 的（不算 9/21 遗留）：

1. BT #162 冻结 `--bars` 已合。  
2. 全集回放覆盖 INPUT_BLOCKED → 人裁收窄 614 满窗。  
3. 收窄回放语义 PASS、**0 成交** → bt 定性 **BUG_ALIGNMENT**（15:03/16:00 空窗口）。  
4. MQ #97 时钟已合 `1c1fe43`；合同 hash 变了；4090 **只重出** `narrow_clock_20260922`（尚未有 intents）。pack 齐了 **bt 派 4090 重跑 P-BASE**；有非零成交前 **不交 Mode B**。

正文：[handoff-joint-return-qlib-to-bt-2026-09-22.md](handoff-joint-return-qlib-to-bt-2026-09-22.md)。RACI 指针：MQ `docs/operations/grok-bot-raci-workflow.md`（SSOT 在本仓 operations，若分支未合入则以该指针为准）。

---

---

## 6. 最短入口（命令细节在 README）

复制粘贴以 [README.md](README.md)「本仓研究入口」代码块为准。这里只指路。

| 你要跑的 | CLI |
|----------|-----|
| 策略 1–6 / 8 / 9 / 10 / 11 / 12 / topk_dropout | `csv_daily_backtest.py` 或 `csv_minute_backtest.py --strategy …` |
| 策略 7 | `csv_minute_backtest_v7.py --pool-dir <海龟池>` |
| topk_app_dropout | `csv_minute_backtest_topk_app_dropout.py` |
| Mode A | `scripts/research/run_unified_exit_modea.py --pool-dir stock_pool …` |
| Mode B | `scripts/research/run_unified_exit_modeb.py --pool-dir stock_pool …` |
| joint-return 冻结回放 | `scripts/research/run_joint_return_replay.py --intents … --bars … --arm P-BASE --fill-mode M-LAG`（见 [frozen-explicit-price](joint-return-frozen-explicit-price.md)） |
| 名单质量对照 | `scripts/research/report_pool_list_quality.py` |
| 已跑完的 CSV 盘后人工分析包 | `scripts/research/export_csv_human_analysis.py --run-dir <run>`；提示词 [prompt-csv-human-analysis.md](prompt-csv-human-analysis.md) |

Python：`D:\anaconda3\envs\vanna312\python.exe`（或 `OSKH_MERGE_PYTHON` / `VANNA312_PYTHON`）。湖路径必须已设定 `OSKH_SOURCE_PARQUET_ROOT`，缺失即报错，不猜盘符。

产物在宿主 `backtest_output/`（gitignored）。新跑另开目录，禁止覆盖归档包。

---

## 7. 净值什么时候可以比、什么时候不能

可以比：同一棵名单树、同一窗口、同一现金口径、同一成交时钟（日线收盘 ≠ 分钟 14:55 ≠ Mode B 分钟触价），只换书或只换网格参数。

不能比（常见翻车）：

- `stock_pool` 净值 vs qlib TopK 净值 vs 海龟池净值
- 策略 8 的 5 亿分钟包 vs Mode A/B 的 11 亿网格
- 默认现金 2100 万 vs `--cash-total 5e8`
- 日线 `--qlib-data-root`（后复权 day.bin，跳过 E-R6）vs 数据湖 none/front
- 把 pred CSV 丢进 `--strategy version6|version8` 当「联合 TopK」（M5 已否）
- **`topk_dropout` CSV 书 vs joint-return-v1 意图回放**（同分家族、不同工件、不同成交核）
- 分钟敏感 B 的局部事件 bp vs 全策略 NAV；Book vs v7 vs Mode B
- 甲（Mode B 卖点臂）vs 乙（整本策略 8）
- 本仓向量化 vs 1.3 LEBS vs MockQMT 真栈（三件不做重，不对一个数）
- 合成 / 冻结 `BT_RESEARCH_REPLAY_PASS` vs 真实收益（绿 ≠ 已测净超额）

跨 sizing（`daily_quota` vs `per_name`）只比 lot 收益分布 / 胜率 / 单码敞口，不用 NAV 排名。

---

## 8. 文档地图

| 主题 | 文档 |
|------|------|
| **本页（问题地图）** | 本文 |
| 命令与 SSOT 表 | [README.md](README.md) |
| 名单 CSV 契约 | [pool-csv-contract.md](pool-csv-contract.md) |
| CSV 盘后人工分析（固定包） | [prompt-csv-human-analysis.md](prompt-csv-human-analysis.md) |
| 引擎定位 | [engine-positioning-ssot.md](engine-positioning-ssot.md) |
| 成交核 | [engine-ashare-correctness.md](engine-ashare-correctness.md) |
| stock_pool 机器网格 | [stock-backtest-unified-exit-proposal-2026-09-17.md](stock-backtest-unified-exit-proposal-2026-09-17.md) · Mode B [plan-unified-exit-modeb-2026-09-17.md](plan-unified-exit-modeb-2026-09-17.md) |
| stock_pool 人工主书（现行 v8） | [plan-v8-stop10-max101-80-gap15-reserve-stale8-2026-09-19.md](plan-v8-stop10-max101-80-gap15-reserve-stale8-2026-09-19.md) |
| qlib TopK 联合研究（CSV 书） | [topk-joint-research-tracker-2026-09-22.md](topk-joint-research-tracker-2026-09-22.md) · GitHub [#164](https://github.com/baiyibing/MyQuant-backtrader/issues/164) |
| **joint-return-v1（意图回放，Grok Bot/4090）** | 交接 [handoff-joint-return-qlib-to-bt-2026-09-22.md](handoff-joint-return-qlib-to-bt-2026-09-22.md) · [frozen-explicit-price](joint-return-frozen-explicit-price.md) · MQ [contract](../../../MyQuant/docs/reviews/joint-return-v1/contract.md) |
| Mode B 甲/乙利弗莫尔 | [livermore-jia-yi-host-note-2026-09-17.md](livermore-jia-yi-host-note-2026-09-17.md) |
| 分钟敏感对照 B（非收益排名） | [plan-minute-sensitivity-b-2026-09-20.md](reviews/plan-minute-sensitivity-b-2026-09-20.md) |
| **2026-09-21 Grok Bot BT 经手账** | 本文 §5.5 |
| 海龟 / 策略 7 | [_archive/plans/plan-strategy7-turtle-csv-minute-2026-09-11.md](_archive/plans/plan-strategy7-turtle-csv-minute-2026-09-11.md) |
| 策略 9 / 10 | [_archive/plans/plan-strategy9-bottom-vol-2026-09-13.md](_archive/plans/plan-strategy9-bottom-vol-2026-09-13.md) · [_archive/plans/plan-strategy10-tr-pool-2026-09-13.md](_archive/plans/plan-strategy10-tr-pool-2026-09-13.md) |
| 策略 11 / 12 | [plan-version11-machip-csv-2026-09-21.md](plan-version11-machip-csv-2026-09-21.md) · [plan-strategy12-jinrongyuan-2026-09-21.md](plan-strategy12-jinrongyuan-2026-09-21.md) |

---

## 9. 以后加实验时先填这四格

1. **名单**：三份主名单之一，独立导出树，还是 MQ 冻结意图（joint-return）？  
2. **搜法**：人工改书、机器网格、分数轮换，还是固定意图回放？  
3. **问什么**：总收益，还是时钟 / 滑点 / 引擎合同？后三类不要开新策略号。  
4. **入口**：已有 CLI + `--strategy`，还是必须独立脚本（策略 7 / Mode A/B / app_dropout / `run_joint_return_replay.py` 先例）？

填不清就不要开新策略号。Grok Bot 的 scratch（`_agent_runs/`）不入库、不当 SSOT。结果写 `backtest_output/` 新目录，并在对应专题页记一笔，不要只改 HELP_LOCK。
