# Plan：向量化 A 股撮合核收口（2026-09-18）

> **落盘**：2026-09-18。**v1.3**（docs-only；本 PR 不写 Python）。v1.1 补 §0.3；v1.2 回填三路对抗勘误（[adversarial-errata.md](../architecture/reviews/2026-09-18/plan-ashare-engine-refactor/adversarial-errata.md) E-01..E-16）；v1.3 回填三席多模型评审（[merge-consensus.md](../architecture/reviews/2026-09-18/plan-ashare-engine-refactor-2026-09-18/merge-consensus.md) MC-1..MC-9）。
> **状态**：✅ **已人裁 GO**（2026-09-18 · **P1=A / P2=A / P3=C / P4=A / P5=A** · v1.3 @ `72178b7`）。实施走 [Codex 交接工作流](workflow-codex-handoff.md) 第 5 步。
> **风险档**：**引擎结构**——默认不改 1–10 / v7 成交数字。P2 若打开印花、除权改股、成交量上限，研究 NAV 作废并另开对照货币；未裁前当禁区。
> **业务源**：[engine-positioning-ssot.md](engine-positioning-ssot.md)（三件引擎）；[engine-ashare-correctness.md](engine-ashare-correctness.md)（E-R1–E-R6）；[pool-csv-contract.md](pool-csv-contract.md)；MyQuant [`docs/plan-three-repo-roadmap-2026-09-12.md`](../../../../MyQuant/docs/plan-three-repo-roadmap-2026-09-12.md) §1–§2；1.3 [`docs/backtest/backtest-architecture-ssot.md`](../../../../OSkhQuant1.3/docs/backtest/backtest-architecture-ssot.md)（只管辖 1.3）。
> **前置**：PR [#104](https://github.com/baiyibing/MyQuant-backtrader/pull/104)（`ashare_session` / `ashare_bars` / `ashare_fees`）**已合入 master**（`a61b1ad`，同 tip 含本 docs PR #105）。实施底 = 该 tip 起的 master。
> **工作流**：走 [Codex 交接工作流](workflow-codex-handoff.md)。
> **交接**：[handoff-ashare-engine-refactor-codex-impl-2026-09-18.md](handoff-ashare-engine-refactor-codex-impl-2026-09-18.md)（已随 GO 刷新，为 Codex 施工图）。
> **基线 tip**：`origin/master` `a61b1ad`（#104 + #105 已合）；`ashare_*` 符号以 #104 `28c4ce2` 为准，行号漂移以符号名为准。

---

## 0. 一句话

把本仓**已经抽出的** session / bars / fees 收成唯一向量化撮合核：策略只发意图，引擎只答能不能成交。**第一船（P1=A）交付 = 谓词与加载 SSOT 收口，双账本保留（§3/§5）**。三仓各自保留自己的回测，**不合引擎、不对净值、不把别人的回测再写一遍**。

```text
本 PR：docs only（plan + handoff + README/AGENTS 入口）
GO 后：feat/ashare-engine-refactor · 切片 A–C 合入门；D = 宿主对照（非合入门）
```

---

## 0.1 本仓定位（本 plan 不重开）

本仓回测回答的唯一问题：

> **这份日名单，按规则在日线 / 分钟上怎么成交。**

不当模型体检，不当 Paper 同源，不当柜台验收。入口仍是 `csv_daily_backtest` / `csv_minute_backtest` / `csv_minute_backtest_v7`（及独立新策略脚本）。对照货币仍是 **reason / 可卖 / 涨跌停 / 除权命中**，不是旧 `daily_equity.csv`，更不是 MyQuant PortAna 或 1.3 LEBS 净值。

业内分层（RQAlpha 约束开关、Hikyuu 账本、vn.py OMS 与策略分离）只用来收口**本仓向量化**。不引入这些框架，不复活 Cerebro，不把 Qlib Exchange 接回来当成交核。

---

## 0.2 三仓都有回测：用途不同，禁止做重

三仓「回测」不是一条链上的三个入口，是三个问题。权威已写在 positioning / 三仓路线图 / 1.3 SSOT。本 plan **只动本仓向量化内部结构**，并按下表守界。

| 仓 | 他们的回测叫什么 | 回答的问题 | 合法产物 | 本 plan **禁止**再做 |
|---|---|---|---|---|
| **MyQuant** | Qlib 训练 / IC / `backtest_daily` / 已停用的 PortAnaRecord、Exchange | 模型每天该买哪些；因子有没有边 | pred、IC/IR、`export_daily_pool` 日 CSV、`run-manifest` | 不 import qlib；不重建 PortAna / Exchange / 0.095 默认板；不写 handler / dump_bin / 分钟训练；不把组合研究报表做成产品 |
| **本仓** | 向量化 CSV 日线 + 分钟（策略书 1–10、v7 仓位机、topk_app 等） | 给定名单，规则怎么成交 | `trades.csv` / `summary.txt` / reason 计数 | 不仿 LEBS 事件环；不仿 MockQMT 报单；不接 Redis / live |
| **OSkhQuant1.3** | LEBS（bar 环 + **import MockQMT 撮合本体** + `trade_decision` + `capital.py`）+ MockQMT 真栈 | 同一套决策核过 Paper 撮合 / 真栈过不过 | LEBS 扫描、真栈 `--parity` | 不复刻 `matching_env` / executor；不在本仓重写 6/8/7 的 live 核；不把 `trade_fee_policy` 嵌进 simulate 热路径 |

跨仓只留两个接口（路线图 §2.4，不扩第三条）：

1. **名单契约**：`YYYYMMDD.csv`、裸六位、文件名=买入日 T。MyQuant `export_daily_pool.py --asof pred_minus_one` 与本仓技术分析导出都写这一份；本仓 `parse_pool_csv` / `validate_pool_dir` 消费。本 plan **不改契约、不新写导出器**。
2. **湖**：1.3 下载并写湖（含 `vendor_wind_st` → `st_daily.parquet`）。本仓与 MyQuant **只消费**，经 `oskh_data` / resolvers。本 plan **不拉数、不 merge vendor、不在本仓再做一份 ST 采集**。

对账纪律（路线图原则 3）：能比的是名单、reason、可卖股、涨跌停。**禁止**把本仓 NAV 与 PortAna、LEBS、真栈拧成一个数作为完成定义。

同名不同物，禁止合并语义：

| 名字 | MyQuant | 本仓（现状） | 1.3 | 本 plan |
|---|---|---|---|---|
| ST | `st_daily.parquet` 的当日 `is_st`，**打分/出池闸** | 名单第二列名字含 `ST`/`*ST` → **5% 涨跌停档** | 写湖的 vendor | 若 P3 打开 PIT 档位，只消费 1.3 已写的湖文件；**不当选股闸**（选股仍在上游名单） |
| 费率 | PortAna 5/15bp+最低 5（研究近似，已停用当产品） | `ashare_fees`：默认双边 10bp；另有 QLIB_PORTANA 开关 | `trade_fee_policy`：佣金+印花+沪市过户，**实盘/真栈 SSOT** | 研究档继续住 `ashare_fees`。P2 若对齐印花，**抄口径、不 import** 1.3/本仓根上的 live 模块进撮合环 |
| 策略 7 | 无 | 金榕元分钟仓位机，独立，不进 BOOKS | LEBS `--strategy turtle` / Paper 海龟 | **不是一份东西**。本 plan 不把 v7 注册进 1–10，不把 LEBS turtle 搬过来 |
| 分钟 | 可选 1min bin / 特征烟测（预测用，默认 2 分钟标签） | 成交用：湖 parquet 或 qlib **bin 只当行情源**（不 import qlib） | 真栈/LEBS 分钟桶 | 本 plan 只统一本仓加载帧；不在本仓训练分钟模型 |

1.3 的 `backtest-architecture-ssot.md` **只管辖 1.3**（第一方回测只有 LEBS）。它不描述本仓向量化，本 plan 也不去改它、不把它升成三仓总纲。

---

## 0.3 1.3 里两件回测：LEBS 做什么、真栈做什么

LEBS **只在 1.3**。本仓没有 `backtest/lebs/`，也不该再做一份。它不是通用回测，是 **Paper 决策核的快速扫描壳**。

权威：本仓 [engine-positioning-ssot.md](engine-positioning-ssot.md) §3.2–§3.3；1.3 `backtest-architecture-ssot.md` §1 / §3 / §4。

### 0.3.1 LEBS ≠ 真栈

| | **LEBS** | **MockQMT 真栈** |
|---|---|---|
| 入口 | `python -m backtest.lebs` | `run_mock_turtle_stack_scenario.py --parity` |
| 问什么 | 同一套 `trade_decision` + `capital.py`，用 Mock 撮合扫参，结果怎样 | 同一套决策核过 Bridge / executor / 结算流，验收过不过 |
| 成交 | bar 环 + **import MockQMT 撮合本体**（订单、笼子、整手） | 真报单回报，柜台换成 Mock |
| 进程 | 单进程研究壳 | 和 Paper 同一套拓扑 |
| 用途 | 规则已锁、产品要和 Paper **同源决策**时扫 | **验收唯一入口** |
| 不做 | 不承诺和实盘净值对齐（**parity 免责**）；不复刻 Redis / executor | 不用 LEBS 净值代替签字 |

一句话：LEBS =「决策已经是那份，撮合也尽量是 MockQMT 那份，但别拉起整栈」。真栈 =「栈过不过」。本仓向量化两件都不当。

### 0.3.2 LEBS 里面还有两条产品线

改一条只动一个目录，互不掺（1.3 SSOT：类似 paper / live 分目录）：

1. **海龟** `--strategy turtle`：吃 `stock_pool_turtle/`，和 PAPER / 真栈 **同一决策核**。这是 LEBS 主业。入口锚：`backtest/lebs/turtle/`。
2. **旧 CSV** `--strategy csv_v1..csv_v5`：吃 `stock_pool/`，隔夜短线旧轨。入口锚：`backtest/lebs/csv/`。**不是**本仓策略书 1–10，也不是策略 7。无 `preset_vN`。

CSV 回测不准去改那四条海龟线。LEBS 里禁止重写本仓 6/8/7。

### 0.3.3 选哪一件（四件，不是三件）

| 你要问的 | 用哪件 | 不要用 |
|---|---|---|
| 这份日名单、这套卖点，赚不赚、怎么扫 | **本仓向量化**（当根 close / 分钟触价，自写账本） | LEBS、PortAna、真栈 |
| 模型该买谁、出 CSV | **MyQuant**（训练 / IC / `export_daily_pool`） | 本仓撮合、PortAna 当产品 |
| 已经要上 Paper，决策核必须是 `trade_decision` | **1.3 LEBS** | 本仓向量化净值、真栈当扫参 |
| 改了资金、卖核、调度，栈过不过 | **1.3 真栈** | LEBS 净值代替签字 |

本仓策略 7（金榕元分钟机）**不是** LEBS turtle，也不是 Paper 海龟。名字像，池和仓位机不是一份。

本仓本 plan 只收向量化撮合核：**不仿 LEBS 事件环，不对 LEBS / 真栈净值，不在本仓冒充 `python -m backtest.lebs`**。规则在本仓锁清、真要上 Paper，再由人改 1.3 的 `trade_decision` → LEBS → 真栈。

---

## 1. 问题锚点（禁止重做已落地项）

| 事实 | 锚点 |
|------|------|
| 三件引擎分工已锁；Cerebro / PortAna 已退场 | [engine-positioning-ssot.md](engine-positioning-ssot.md) |
| NP3 分层倒置已合（#78）：daily/minute 双入口 + 共享核 | [handoff-np3-engine-layering](handoff-np3-engine-layering-codex-impl-2026-09-16.md)；`csv_common` / `csv_ledger` / `csv_artifacts` / `csv_daily_loader` |
| session / bars / fees 已抽（#104，已合 `a61b1ad`） | `ashare_session.py` / `ashare_bars.py` / `ashare_fees.py`；[engine-ashare-correctness.md](engine-ashare-correctness.md) §1 |
| E-R1–E-R6 成交锁 | 同上 §2。E-R6 **只改参考价**，shares / 现金红利不动 |
| 名单契约 + ST 名称 as-of | [pool-csv-contract.md](pool-csv-contract.md) |
| 分钟 cache 已迁入 `ashare_bars` | `load_minute_ohlc` / `minute_cache_path`；v7 另有 compact 帧 |
| 1–10 账本 ≠ v7 账本 | `csv_ledger.Position.entry_idx` vs `csv_minute_backtest_v7.Lot.buy_date` |
| v7 涨跌停 / T+1 已调 `ashare_session`（#104 后既成） | `csv_minute_backtest_v7.py` import `ashare_*`；切片 B 对 v7 是防回归 |
| 1–10 分钟加载经别名 | `load_minute_bars = load_minute_ohlc`（`ashare_bars.py`）；调用点 `csv_minute_backtest.py` |
| Mode B 除权 `shares/=k` **只在网格模块** | [plan-unified-exit-modeb](plan-unified-exit-modeb-2026-09-17.md) R1/R4；**禁止**回写 `rescale_position` |
| MyQuant 出名单管道已通 | `export_daily_pool.py`；R2/R5 已合。本仓只消费 CSV |
| 1.3 第一方回测只有 LEBS；真栈是验收，不是第二套研究引擎 | 1.3 `backtest-architecture-ssot.md` §1 / §3；本仓 positioning §3.2–§3.3 |
| LEBS 海龟 ≠ LEBS 旧 CSV ≠ 本仓 1–10 ≠ 本仓策略 7 | §0.3.2；turtle 吃 `stock_pool_turtle/`；csv_vN 吃 `stock_pool/` |

---

## 2. 现锁（R\* · 硬边界）

| # | 规则 |
|---|------|
| **R1** | **不重开四件回测。** 本仓向量化 / MyQuant 信号厂 / 1.3 LEBS / 1.3 真栈分管四个问题。LEBS 只在 1.3，且 LEBS ≠ 真栈（§0.3）。不合成一台，不互相当对照净值。 |
| **R2** | **不做重。** 不 import qlib；不复活 Cerebro / Rolling / PortAnaRecord；不复刻 LEBS / MockQMT / Redis / live；不在本仓重写 MyQuant 导出器或 1.3 拉数。 |
| **R3** | 新撮合代码只收口本仓已有零件。策略书（1–10）与 v7 **规则数字**默认不动。7 不进 BOOKS。topk_app_dropout 继续独立。 |
| **R4** | 名单契约一字不改：文件名=买入日 T；裸六位；缺日/空文件=当日不买。 |
| **R5** | E-R1–E-R4 不重开。E-R5/E-R6 残留（shares、现金红利、噪声带）**只在 P3 人裁后**才动；未裁视为锁。Mode B 的 `shares/=k` 继续只住 Mode B 模块。 |
| **R6** | 默认费率保持 `BILATERAL_10BP`（0.1% 双边、无最低）。QLIB_PORTANA 仍是对照开关，不当引擎默认。live `trade_fee_policy` 不进 simulate 热路径。 |
| **R7** | CI **data-free**。湖路径只经 resolvers，禁止硬编码盘符。fixture 外零真实 symbol。 |
| **R8** | 不把 `research/` 大改名为 `ashare/` 包（NP3 地图保持双入口 + 共享核）。新文件优先 `backtest/research/ashare_*.py` 或现有模块内收口。 |
| **R9** | 发现 plan 未覆盖的语义分叉 → **停下开 Q40+**，不自裁。 |

---

## 3. 人裁点（P\* · 未裁 = 禁止编码）

| # | 问题 | 建议默认 | 选项 |
|---|------|----------|------|
| **P1** | GO 后第一船 | **A**：只做谓词统一（切片 A–B）——T+1/涨跌停谓词与 `entry_idx` 日历映射收口；**双账本保留**（csv_ledger 与 v7 Lot 不合并），不开发费/除权/量限 | **A** 谓词统一先收口；**B** 先做 CLI/报告；**C** 先开发费 |
| **P2** | 研究费率要不要印花+过户+最低 | **A**：默认仍 10bp；`--fees full` 才对齐 `trade_fee_policy` **口径**（抄常数，不 import live；**近似**——`FeeSchedule` 表达不了沪市过户按码/豁免前缀/最低过户，errata E-11；旗名另开 plan 时定，**不得与现网 `--qlib-cost` 并存双 SSOT**） | **A** 开关默认关；**B** 改默认（重写 golden，另开对照）；**C** 本轮不做 |
| **P3** | E-R6 残留（shares / 现金红利 / ST PIT 档位） | **C**：本轮不做；分钟若成主研究面再按 E-R5 重开条件另开 plan | **A** 本轮改股数；**B** 只接 ST PIT 档位（消费湖，不当选股）；**C** 全部后置 |
| **P4** | 成交量上限（大资金乐观成交） | **A**：本轮不做；5 亿账户另开探针 | **A** 后置；**B** 默认关的 `--volume-cap`；**C** 默认开 |
| **P5** | 统一 `bt run` CLI | **A**：旧 CLI 保留为真身；本轮最多薄包装，不改 HELP_LOCK | **A** 薄包装；**B** 本轮不碰 CLI；**C** 换入口并改 HELP_LOCK（需另锁文案） |

未裁 = 实施按建议默认执行仍须头部先改成 ✅ 已人裁 GO。合本 docs PR ≠ 实施 GO。

> **已人裁（2026-09-18）**：**P1=A**（谓词统一，双账本保留）· **P2=A** · **P3=C** · **P4=A** · **P5=A**。P2/P3/P4 若开工另开 plan。

---

## 4. 非目标

| 不做 | 原因 |
|------|------|
| 改 MyQuant 训练 / pred / handler / 1min dump / PortAna | 信号厂的回测，不是本仓问题 |
| 改 1.3 LEBS / MockQMT / `trade_decision` / `capital.py` | 执行栈的回测，不是本仓问题 |
| 在本仓复刻 LEBS 事件环 / `matching_env` / `python -m backtest.lebs` | LEBS 只在 1.3（§0.3）；parity 免责也不搬过来 |
| 把本仓策略 7 与 LEBS turtle / Paper 海龟合成一份 | 池和仓位机不是一份 |
| 改 1.3 `backtest-architecture-ssot.md` 或把它写成三仓总纲 | 该文只管辖 1.3 |
| 改 MyQuant 三仓路线图正文（除非人裁要回写一行指针） | 本票只落本仓 docs |
| 复活 Cerebro；import qlib；接 Qlib Exchange | R2 |
| 把 v7 推进 BOOKS；用 `simulate_v7` 跑 Alpha158 | positioning §3.1 |
| 合并 Mode A 网格持仓跟踪（`unified_exit_modea.Instance`，第三套） | 网格模块自持，非本船 |
| 改 `rescale_position` 使 1–6/8 shares/=k | X-R1 / Mode B R1 |
| 改策略书止损/加仓数字、改 v7 阶梯 | 本票是引擎收口，不是调参 |
| 默认改 `COMMISSION=0.001` 或打开印花 | 未裁 P2；会废全部历史 NAV |
| 成交量上限当默认 | 未裁 P4 |
| 新建事件总线 / 日级订单簿仿 RQAlpha | 日名单 + 向量化扫描已是本仓正确形态 |
| 在本 docs PR 或未 GO 分支写撮合 Python | 工作流第 3 步 |

---

## 5. 切片（GO 且 #104 已合后，从当时 master 开 `feat/ashare-engine-refactor`）

| 切片 | 做什么 | 完成定义（DoD） |
|------|--------|-----------------|
| **A · 一帧分钟 + 禁复制** | v7 **默认湖路径**改走 `load_minute_ohlc`：整载 `(start,end)` 后按日切片；禁逐日调 loader、禁全市场 flatten。**帧契约三选一写死（MC-1）**：(a) 复用 1–10 `_slice_day`；(b) `_day_frame_records` 认书帧 `ymd`/DatetimeIndex；(c) 薄适配层——书帧无 `date` 列，按字面换即 `KeyError`。**topk 共用 v7 `_load_cli_bars`，非独立链（MC-4）**：`_load_cli_bars` 的 lake/qlib_1min 分叉写死，topk 湖路径跟 v7 适配走。**v7 湖路径 `use_cache=False`（MC-5）**：cache 键仅 `(start,end)`，小名单先写会被大名单命中走缺码整读合并——禁止 v7 覆写共享 cache。compact **降为模块私有并保留 qlib_1min 源与 `bars_from_pool` 链**。新策略禁止再写加载 / 涨停 / 佣金。文档：engine-ashare-correctness 模块表跟上 | data-free 测：v7 合成窗 reason 计数**与 trades 价格列**均与改造前一致（双加载器六差异：文件集/列/盘中过滤/去重/E-R4 零量日/cache——任一触发漂移 → 列允许漂移并 STOP）；**非空 bar 计数 > 0**（防空切片假绿）+ **topk 合成窗非空**；缺码路径给 data-free fixture（mock 行数上限，非仅口头 6.6GB）；1–10 / Mode B **填价与 reason 不动，cache 写路径允许变**；已知限制记录：cache 无新鲜度守卫、加载线程池无 timeout；无盘符字面量 |
| **B · 谓词统一（P1=A；双账本保留）** | T+1 只认 `buy_date < session`。1–10 的 `entry_idx` **映射到日历日**：映射只服务 T+1 谓词与日期打印；**`n_days` 一律仍按联合日历下标计数**（禁止按个股自身有 K 日数重建）。**谓词落点=现有调用点（MC-6）**：T+1/买卖闸在 simulate 环与 v7 事件环的**调用点**统一走 `t1_sellable` / `skip_buy_at_limit` / `defer_sell_at_limit`；**不改** `execute_buy` / `_sell` / v7 `_buy` / `_sell_lots` 填单契约（现状不含谓词，也不塞进去）；书侧保持 `limits is None` **先拒**（fail-closed，`skip_unknown_board`/冻仓）；`hit_limit_*` 保留给 `reserve_limit_up` / `open_board` / `forbid_all_trade_at_limit` / qlib 带内判定，不替换。v7 的 `Lot` 策略字段（stage / entry_A）留在 v7。**已知留存分叉不改（Q40+ 另裁）**：v7 卖/加仓侧 limits=None（**无昨收或未知板块两支**）谓词放行=fail-open（书引擎冻结拒卖）；v7 ST 名称平铺取窗末名非 PIT | 合成：T+1 拒卖、涨停 skip、跌停 defer 日线+分钟+v7 各至少 1 条；**None-limits 卖侧向量覆盖无昨收+未知板块两支**（记录现状行为）；日线卖出时点两支：`open_board` 同 bar 当日收 vs 其余 `pending_exit` 次日开；`csv_ledger.rescale_position` diff 空或仍 shares untouched；**golden 指涉物** = tests 内合成 golden + 宿主**改造前**短窗 trades/summary 基线先落盘（host 步骤）；切片 D reason 桶映射落 tests 内 dict（1–10 前缀分类计数器 vs v7 自由字符串，给示例键值） |
| **C · 围栏 + 入口文档** | import 围栏：simulate 热路径 AST 不得 import qlib / `trade_fee_policy` / LEBS。**热路径=枚举清单**：`csv_daily_backtest` / `csv_minute_backtest` / `csv_minute_backtest_v7` / `csv_ledger` / `csv_simulate_loop` / `csv_common` / `csv_strategy_books` / `ashare_session` / `ashare_bars` / `ashare_fees` / `unified_exit_modeb`，**加传递一层：`csv_daily_loader` / `csv_pool` / `market_layer` / `exdiv_map`**（禁 rglob 全 `research/` 目录——`research/engine.py` 现存 `trade_fee_policy` import，其处置连同 `legacy/engine.py` 另开卫生票）。README / AGENTS 一句「三仓回测不做重」。旧 CLI 保留（P5=A） | 围栏测锚点（MC-7）：新文件 `tests/test_ashare_simulate_import_fence.py` + `SIMULATE_HOT_PATH` 常量表与本清单**字节级一致**；HELP_LOCK 不改（除非 P5=C） |
| **D · 宿主对照**（**非合入门**） | 同窗 1–10 与 v7 各一短跑，比 reason 桶，不比与 LEBS/PortAna 的 NAV | 短记落 `docs/backtest/`；数字产物不入库；实现 PR 不勾选 |

P2/P3/P4 若裁成「做」，**另开 plan**，不塞进本船 A–C。

---

## 6. 验证

```bash
# 合入门（实现 PR；data-free）
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
```

- 本 docs PR：无 Python、不跑湖、不 merge 实施。
- CI data-free gates 必须过。
- 文本：UTF-8 无 BOM、NUL=0。
- 宿主 D：非合入门。禁止用 MyQuant / 1.3 净值当通过条件。

---

## 7. 代码落点（GO 后）

| 文件 | 动作 |
|------|------|
| `backtest/research/ashare_bars.py` | v7 湖路径改书格式（帧适配见 §5-A 三选一）；compact 降为**模块私有并保留**（qlib_1min 源 + `bars_from_pool` 链，**不删**） |
| `backtest/research/csv_minute_backtest_v7.py` | 加载改切片；Lot 策略字段保留 |
| `backtest/research/csv_ledger.py` | T+1 用日历日；**不改** `rescale_position` shares |
| `backtest/research/ashare_session.py` / `ashare_fees.py` | 只读复用，除非测试缺口 |
| `backtest/research/csv_daily_backtest.py` / `csv_minute_backtest.py` | 尽量只改调用，不改书行为 |
| `tests/test_ashare_*.py` / `test_csv_minute_backtest_v7.py` / ledger 测 | 更新 + 新合成向量 |
| `docs/backtest/engine-ashare-correctness.md` / `README.md` / `AGENTS.md` | 模块表 + 三仓不做重一句 |
| `backtest/research/csv_simulate_loop.py` / `csv_common.py` / `csv_strategy_books.py` | `entry_idx` 赋值（`execute_buy(day_i)`）与 `n_days` 消费所在；只改调用，**不改计数口径** |
| `backtest/research/qlib_bin_1min.py` + topk_app 脚本 | qlib_1min 源经 compact 链共存；topk **共用 v7 `_load_cli_bars`**（改 v7 湖路径=改 topk 湖帧，DoD 含 topk 合成窗非空）；topk 文件本身**不改** |
| `backtest/research/engine.py` / `backtest/legacy/engine.py` | `trade_fee_policy` import 处置**另开卫生票**，不塞本船 |
| `unified_exit_modeb.py` / `*_rules.py` / 1.3 / MyQuant | **不改** |

---

## 8. 三仓衔接（本仓侧只消费）

```
MyQuant  训练/IC → export_daily_pool → YYYYMMDD.csv
本仓 TA   chip/TR/手工              → 同一契约 CSV
                 ↓
本仓向量化  锁规则、扫参、reason
                 ↓  仅当要上 Paper
1.3 trade_decision → LEBS（扫参）→ MockQMT 真栈（验收）
                 （详见 §0.3；LEBS ≠ 真栈）
```

| 方向 | 本仓做什么 | 明确不做什么 |
|------|------------|--------------|
| ← MyQuant | 读 pred 导出的池；可选读 qlib **bin 当行情**（已有 `qlib_bin_1min`，不 import qlib） | 不训练、不改 keeper pred、不把 PortAna 当验收 |
| ← 1.3 湖 | 经 resolver 读 1d/1m none、除权因子、将来可选 `st_daily.parquet` | 不下载、不写 `.authority`、不改 vendor 脚本 |
| → 1.3 | 无代码依赖。晋升仍是「人把规则锁清再改 1.3 决策核」 | 不自动同步净值；不在本仓冒充 `python -m backtest.lebs` |

`tests/test_presets_cross_repo_snapshot.py` 继续防 1.3 presets 漂移。本 plan 不扩更多跨仓测试。

---

## 9. 修订程序

1. 人裁 P1–P5 → 回写本表 + 头部改为 ✅ 已人裁 GO（hash）。
2. 确认 #104 已合（或实施底包含等价 `ashare_*`）。
3. 刷新 handoff §0，去掉「待人裁」等待句，填 plan hash。
4. 开 `feat/ashare-engine-refactor`。遇未覆盖语义 → **停下 Q40+**。
5. 实现合入后回写「✅ 已实施（PR #N）」；切片 D 另短记。

---

## 10. Changelog

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.3 | 2026-09-18 | 回填三席多模型评审 merge-consensus MC-1..MC-9：切片 A 钉 v7 帧契约三选一 / topk 共用 `_load_cli_bars` / v7 湖路径 `use_cache=False` / 非空 bar 计数门；切片 B 谓词落点改为**调用点**（不改填单契约、书侧 None 先拒、`hit_limit_*` 保留）、None-limits 两支、卖出时点两支；切片 C 围栏加传递一层 + 测试锚点（`test_ashare_simulate_import_fence.py`）；§7 compact「不删」对齐、topk 行改述；§0/P2/§4 补句；handoff 全量同步 |
| v1.2 | 2026-09-18 | 回填三路对抗评审勘误 E-01..E-16（[adversarial-errata.md](../architecture/reviews/2026-09-18/plan-ashare-engine-refactor/adversarial-errata.md)）：P1=A 改述为谓词统一（双账本保留）；切片 A 补价格列/内存门/qlib_1min+topk 链处置；切片 B 钉 n_days 联合日历口径、None-limits 与 ST 非 PIT 留存分叉、golden 指涉物；切片 C 围栏改枚举清单；§7 补 simulate_loop/common/books 落点；基线刷新 `a61b1ad` |
| v1.1 | 2026-09-18 | 补 §0.3：LEBS 只在 1.3、LEBS≠真栈、海龟/旧 CSV 分轨、选哪一件四行、策略 7≠turtle |
| v1.0 | 2026-09-18 | 首版 docs-only：三仓回测守界、R1–R9、P1–P5（建议默认）、切片 A–D；状态 ⏳ 待人裁 GO |
