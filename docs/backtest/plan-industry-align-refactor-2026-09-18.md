# Plan：研究成交时钟显式化（fill clock）（2026-09-18）

> **落盘**：2026-09-18。**v0.2**（docs-only 勘误；本次只改本 plan，不写 Python / 测试）。
> **状态**：⏳ **待评审 / 待人裁 GO**。合本 docs PR ≠ 实施 GO；P\* 未裁前禁止编码。
> **风险档**：**引擎结构 / 成交语义高敏**——目标是把既有决策、会话、价格规则命名并用 data-free 测试锁住；默认成交价、股数、reason、NAV 与产物契约必须为零变化。
> **业务源**：[引擎定位 SSOT](engine-positioning-ssot.md) · [A 股正确性 as-built](engine-ashare-correctness.md) · [Pool CSV contract](pool-csv-contract.md) · [#108 前置 plan](plan-ashare-engine-refactor-2026-09-18.md) · [PR #108](https://github.com/baiyibing/MyQuant-backtrader/pull/108)。
> **事实锚**：本 plan 的代码事实与引用行号核对基线为 `origin/master` `c44da87`（Merge PR #108）；本分支 `docs/industry-align-refactor-2026-09-18`。**实施 diff 基线另见 §7 / §9 / §11：它是人裁 GO 当时的 `origin/master` commit，当前不假装已知。**
> **工作流**：本文件是 [Codex 交接工作流](workflow-codex-handoff.md) **第 1 步（Plan 起草）**；评审规则见 [multi-ai-review-workflow.md](../engineering/multi-ai-review-workflow.md)。本次起草不运行 multi-agent review。
> **短注**：这是提案，不是编码，也不是修复 14:57–15:00 成交行为的授权。v0.1 的价格规则与“现有成交窗口”表述已由 §12 勘误；不得拿旧句起草实现测试。

---

## 0. 一句话

PR #108 已回答「**能不能成交**」；本 plan 只把仍散落在书引擎里的三只**研究成交时钟**做成命名叶子与 data-free 契约：

| 时钟 | 当前真义 | 本 plan 的动作 |
|------|----------|----------------|
| **决策时钟** | 三条买路径：池买·日线在文件名日 T 取 close；池买·分钟在 T 取 14:55 close，缺 14:55 才取 `[14:30, 14:55]` 最后一根 close；追买已在 T+1，日线取 T+1 close，分钟取 09:45 close（缺 bar 才取 `≤09:45` 最后一根 close） | 分路径命名并锁住；**只禁止把池买改成 T+1 open，不把追买误写成尚未发生或与池买同钟** |
| **会话时钟** | `_in_session` 接受 09:30–11:30、13:00–15:00；14:57 是拟新增标签分界。它只说明 bar 可进入当前扫描窗口，不说明已有交易所收盘集合竞价撮合；策略 5 可在 14:50 返回，池买截止 14:55 | 把已接受分钟标为 `continuous` / `closing_call`；**标签不是过滤器，也不是会话正确性结论** |
| **价格规则** | 书引擎已有多条取价：日线 gap-stop 当日 open、touch 当日 trigger、命中 same-bar 前缀时当日 close、确实写入 `pending_exit` 才下一可卖日 open；分钟 gap-stop 用 open、其余触价用该分钟 close。v7 另有规则 | 建**非全量选价器**的命名枚举与对照测试；**不建新调度器、不把 v7 写成已覆盖** |

目标交付只有「叶子模块 + 合成测试 + as-built 短表」。任何数值变化都必须先回到 P\*，不准藏进切片。

---

## 1. 业务源

### 1.1 本仓回答的问题

本仓是**向量化 CSV 研究回测**，只回答：

> 给定一份日名单，规则在日线 / 分钟行情上怎么成交。

它不是 Paper，不是柜台验收。MyQuant 负责信号 / 名单；本仓负责向量化研究；OSkhQuant1.3 的 LEBS 负责同源决策扫描，MockQMT 真栈负责执行验收。LEBS 只在 1.3，且 LEBS ≠ MockQMT 真栈；本仓没有 `backtest/lebs/`。

### 1.2 权威链

| 权威 | 本 plan 继承什么 |
|------|------------------|
| [engine-positioning-ssot.md](engine-positioning-ssot.md) §1 / §3.1 | 本仓只做日名单上的向量化成交；不合并三仓引擎，不互对 NAV |
| [engine-ashare-correctness.md](engine-ashare-correctness.md) §1–§3 | E-R1–E-R6、双账本、读取器与扫描内核冻结、对照货币 |
| [pool-csv-contract.md](pool-csv-contract.md) `As-of` | 池买的文件名日 T 就是决策 / 买入日；日线 close、分钟尾盘成交 |
| [plan-ashare-engine-refactor-2026-09-18.md](plan-ashare-engine-refactor-2026-09-18.md) §0.3 / §5 | #108 切片 A–C 的已裁边界，不重做、不回滚 |
| [README.md](../../README.md) `Run research backtest` | 旧 CSV CLI 保留为真身（P5=A），HELP_LOCK 不变 |
| [workflow-codex-handoff.md](workflow-codex-handoff.md) | docs plan → 评审 → 人裁 GO → handoff → 另分支实施；GO 前禁编码 |

### 1.3 市场时段与当前模型的差

公开市场时段事实用于**命名差异**：开盘集合竞价 09:15–09:25；连续竞价 09:30–11:30、13:00–14:57；收盘集合竞价 14:57–15:00。

当前 `_in_session` 从 09:30 开始、下午一直接受到 15:00（含端点）；仓内 L2 分类则以 14:57 为 `close_auction` 分界。研究核不得 import L2 ETL，本 plan 只把 14:57 作为拟新增的**扫描窗口标签分界**：若扫描实际到达这些 bar，现有 Python 分支可按该 bar open / close 取价；但策略 5 在有 14:50 bar 时会先返回，池买也截止 14:55。因此 `closing_call` 不等于“交易所收盘集合竞价已建模 / 已正确”，也不等于所有路径已有统一的 14:57–15:00 成交窗口。本 plan 先命名、先测试，**不据此改变成交**。

---

## 2. 现状锚点（禁止重做已落地项）

以下均以 `c44da87` 为准；行号会漂时，以符号名为准。

| 已落地事实 | HEAD 锚点 | 本 plan 的处理 |
|------------|-----------|----------------|
| PR #108 切片 A：分钟湖统一书帧；v7 / topk 共用加载链 | `engine-ashare-correctness.md:23-30`；`ashare_bars.load_minute_ohlc` | 不重做一帧分钟，不改 cache / compact 迁移 |
| `read_lake_minute_ohlc` 已字节级冻结 | `backtest/research/ashare_bars.py:328` `read_lake_minute_ohlc` | 整个符号不动；不为时钟标签改读取字节 |
| PR #108 切片 B：T+1 / 涨跌停谓词收口 | `ashare_session.py:29` `hit_limit_up`；`:34` `hit_limit_down`；`:39` `t1_sellable`；`:73` `skip_buy_at_limit`；`:77` `defer_sell_at_limit` | 不重开谓词，不把时钟标签变成成交许可 |
| 费率默认已锁 | `backtest/research/ashare_fees.py:53` `BILATERAL_10BP` | 保持双边 10bp；不设计印花表 |
| numba / Python 分钟扫描内核已锁 | `csv_minute_backtest.py:150` `_scan_held_day_numba_trail`；`:232` `scan_held_day_python`；`:323` `scan_held_day` | 三个符号字节不动；新模块不进入扫描器 |
| 双账本保留 | `csv_ledger.py:66` `Position`；`csv_minute_backtest_v7.py:61` `Lot` / `:69` `Position` | 不合并账本，不改填单函数 |
| PR #108 切片 C：import 围栏已落地 | `tests/test_ashare_simulate_import_fence.py:13-29` `SIMULATE_HOT_PATH` | 不扩大为 `research/` 扫描；无生产 import 时清单保持字节不动 |
| 旧 CLI 保留（旧 plan P5=A） | `README.md:47`；`csv_daily_backtest.py:158` `HELP_LOCK`；`csv_minute_backtest.py:114` `HELP_LOCK` | 不加入口、不改帮助文案 |

### 2.1 三只时钟的 as-built 证据

| 路径 | 现状 | 代码证据 |
|------|------|----------|
| 池买·日线 | 文件名日 T 就是决策 / 买入日，取 T 日 close | `pool-csv-contract.md:11-12`；`csv_daily_backtest.py:428-435` `_pool_quote_for` |
| 池买·分钟 | 文件名日 T 就是决策 / 买入日；有 14:55 bar 必取其 close；只有缺 14:55 时才取 `[14:30, 14:55]` 最后一根 close，否则不买。14:57–15:00 不会成为池买价 | `csv_minute_backtest.py:112` `BUY_HM`；`:469-476` `_buy_px` |
| 追买·日线 | 已在 T+1；`_chase_quotes_for` 给 `(open, close)`，共用环取第二个元素，故买价为 T+1 close，reason=`chase:T+1` | `csv_daily_backtest.py:403-410` `_chase_quotes_for`；`csv_simulate_loop.py:144/179` `run_chase_due_day` |
| 追买·分钟 | 已在 T+1；取 09:45 close，缺 bar 才取 `[AM_OPEN, 09:45]` 最后一根 close；不是 T+1 open | `csv_ledger.py:27` `CHASE_HM`；`:106-112` `chase_decision`；`csv_minute_backtest.py:479-490` `_chase_quotes`；`csv_simulate_loop.py:144/179` |
| 会话入口 | `AM_OPEN=09:30`、`AM_CLOSE=11:30`、`PM_OPEN=13:00`、`PM_CLOSE=15:00`，端点均含 | `ashare_bars.py:27-28`；`_in_session` `:302-306` |
| 开盘集合竞价 | 09:15–09:25 不被 `_in_session` 接受 | 同上 `_in_session` |
| 14:57 标签证据 | `_in_session` 接受 14:57–15:00；14:56 / 14:57 对 `_in_session`、`_buy_px`、`scan_held_day` 没有既有相位分支，`ashare_bars` 也没有 `CLOSING_CALL_OPEN`。L2 桶从 14:57 起标 `close_auction`，只作仓内分界证据，研究核不 import L2 ETL | `ashare_bars.py:302-306` `_in_session`、`:318-325` `annotate_session`；`csv_minute_backtest.py:283-319/469-476`；`l2_analytics/etl_day.py:118-119` `_session_sql`；`tests/test_l2_etl.py:121` |
| 策略 5 强卖 | `FORCE_SELL_HM=14:50`；扫描在首根 `cur_hm >= force_sell_hm` 时以该 bar close 返回。有 14:50 bar 时不会执行到 14:57–15:00 | `strategy5_rules.py:16`；`csv_minute_backtest.py:316-319` `scan_held_day_python` |
| 日线 `pending_exit` | **只有引擎确实写入 `pending_exit` 的 reason** 才在下一可卖日按 open 成交；不能概括成“全部非 same-bar” | `csv_daily_backtest.simulate` `:329-333`、`:377-401` |
| 日线 gap-stop | `stop_loss:gap_open` 在触发当日按 open 成交，不进 pending | `csv_daily_backtest.py:336-351` `simulate`；`tests/test_csv_daily_backtest.py:405-418` |
| 日线 touch-stop | `trigger = cost * (1-stop_pct)`；开盘未破但 `low <= trigger` 时，若未因跌停延期，则触发当日按 trigger 成交；不是 close，也不是下一 open | `csv_daily_backtest.py:338-359` `simulate`；`tests/test_csv_daily_backtest.py:200-217`（10×0.98=9.8）；`tests/test_exdiv_refprice_engines.py:203-219`（4.9，bar close=5.10） |
| 日线 same-bar | 默认前缀含 `open_board`；topk 书另含 `topk_drop` / `model_exit`。命中时只有通过涨跌停门才按当日 close 成交，否则可能不成交且不一定 pending | `csv_strategy_books.py:118/692/767`；`strategy_topk_dropout_rules.py:25`；`strategy_topk_score_exit_rules.py:25`；`csv_daily_backtest.py:378-401` |
| 分钟缺口止损 | 开盘已破阈值取该 bar open | `csv_minute_backtest.scan_held_day_python` `:277-285`；numba 同义分支 `:182-190` |
| 分钟其余触价 | 止损触价、sell gate、止盈 / trail、force 均取该分钟 close | `scan_held_day_python` `:283-319`；最终 `_sell` 调用 `csv_minute_backtest.simulate` `:643-651` |
| v7 | 独立价格路径：仅首 bar 可能用 open，其后用 close；池买严格 `hm==895`，缺则 `skip_no_1455`；计时退出用当日最后一根 close。它不在本 plan 的书引擎价格短表内 | `csv_minute_backtest_v7.py:327-340/381-411/398-404` |
| EOD 标记 | `append_equity_and_eod_marks` 用日线 `market_close_mark` 写权益与期末 `side=EOD_MARK`。这是估值标记，不并入上述三条买路径；P4 继续把触价资格与 15:00 标记分开 | `csv_simulate_loop.py:299-339`；`csv_ledger.py:159-172` `market_close_mark`；`csv_minute_backtest.py:729-735` |

---

## 3. 现锁（F-R\* · 本提案硬边界）

| ID | 规则 |
|----|------|
| **F-R1** | 本仓定位不变：只做向量化 CSV 研究成交。不是 Paper，不是柜台验收；不与 MyQuant 信号厂、1.3 LEBS 或实盘栈合并。LEBS 只在 1.3，LEBS ≠ MockQMT 真栈，本仓没有 `backtest/lebs/`。 |
| **F-R2** | PR #108 已落地的切片 A–C 不重做：一帧分钟、T+1 / 涨跌停谓词、import 围栏、冻结读取器、numba 内核锁、双账本与旧 CLI 均保持。 |
| **F-R3** | **不重开 E-R1–E-R6。** T+1 继续走 `t1_sellable`；涨跌停继续走现有谓词；E-R5/E-R6 只动参考价，shares 与现金红利不动；Mode B `shares/=k` 不回写 `rescale_position`。 |
| **F-R4** | 决策时钟分路径锁：池买·日线=T 日 close；池买·分钟=T 日 14:55 close，缺 14:55 才用 `[14:30, 14:55]` 最后一根 close；追买已是 T+1，日线=T+1 close、分钟=09:45 close（或既有 `≤09:45` fallback）。不得把**池买**改成 T+1 open，也不得把追买写成尚未发生、T+1 open 或与池买同一只钟。 |
| **F-R5** | 会话标签锁：`closing_call = hm ∈ [14:57, 15:00]` 是拟新增的**当前扫描窗口标签**；`_in_session` 接受这些 bar，扫描若实际到达仍按既有分支处理，但这不宣称交易所收盘集合竞价撮合已建模 / 已正确，也不宣称所有路径已有统一成交窗口。`session_phase` 不是过滤器，不改变扫描或成交资格；B/C 仍须另裁。 |
| **F-R6** | 价格规则锁是**具名路径而非全量选价器**：日线 `stop_loss:gap_open`=触发当日 open；`daily_stop_touch_at_trigger`=触发当日 trigger；命中 `daily_same_bar_prefixes` 且通过涨跌停门才按当日 close；只有确实写入 `pending_exit` 的 reason 才下一可卖日 open；分钟 gap-stop 用该 bar open、其余触价用该 bar close。v7 不在此短表。新叶子只命名，不替换 `simulate` / `scan_held_day`。 |
| **F-R7** | 默认费率仍为 `BILATERAL_10BP`；7 不进 BOOKS；双账本不合并；旧 CLI / HELP_LOCK 不变。 |
| **F-R8** | 实施结果不得改变成交价、股数、reason 值或计数、NAV、`trades.csv` 列、`summary` 快照、HELP_LOCK、`read_lake_minute_ohlc` 字节、`load_minute_ohlc` 行为、两个分钟扫描内核字节、`run_chase_due_day` / `append_equity_and_eod_marks` 或 `strategy5_rules.FORCE_SELL_HM`。任何此类选择只准进入 P\* 并先修订 plan。 |
| **F-R9** | import 边界不变：不 import qlib，不复活 Cerebro / Rolling / PortAna / Exchange，不重写 LEBS 事件环、`matching_env`、Redis 或 live。新叶子只允许标准库，加上从 `backtest.research.ashare_bars` **只读 import** `AM_OPEN/AM_CLOSE/PM_OPEN/PM_CLOSE`；不得本地重定义这四个名字，不得 import 其它本仓 / 第三方模块。模拟热路径不得 import `ashare_fill_clock`；该反向禁令必须进入 pytest 围栏，`rg` 只能补充。 |
| **F-R10** | 对照仍是 reason / 可卖 / 涨跌停；本 plan 只增加“这是当前扫描窗口标签”的限定。相位标签绿不等于交易所会话或集合竞价撮合对齐成功；不得用本仓 NAV 对 PortAna / LEBS / 实盘栈作为成功指标。 |
| **F-R11** | CI 必须 data-free；不读湖、不用真 symbol 行情。新代码不得出现硬编码盘符；行情路径若未来需要，仍只能走 resolver（本 plan 不新增行情读取）。 |
| **F-R12** | #108 已知分叉保持：书侧无昨收 / 未知板块先拒；v7 卖侧 `limits=None` fail-open；v7 ST 名称按窗末平铺、非 PIT。v7 整文件冻结且不纳入本 plan 的书引擎价格短表；不得写成涨跌停或价格规则已收口。默认**不动**，只能经 P3 另票。 |
| **F-R13** | 旧 plan P2（印花开关）、P3（改股 / 现金红利 / ST PIT）、P4（成交量上限）继续后置；本 plan 不重新设计费率或参与率。 |
| **F-R14** | 任何未覆盖语义都必须停下新增 P\* / 修订本文；未裁不得编码，合本 docs PR 也不构成 GO。 |

---

## 4. 为什么只做这一份、不是菜单

#108 已把成交许可、行情帧与依赖围栏收口；当前同一类缺口只有一个：**成交时钟虽已存在，却没有命名对象和横向契约表**。决策日、会话相位、价格选择必须在同一张表里才能避免“标签被误当过滤器”或“日线 / 分钟各自改口径”。

因此本 plan 只有一条船：**行为不变的 fill clock 显式化**。印花、除权改股、成交量上限、v7 fail-open、ST PIT、滑点与参与率都已有锁或后置裁决；把它们列成候选菜单会重开 #108 和 E-R\*，也会让一次结构提交同时承载数值语义。本 plan 不这样做。

唯一退出条件也只有一个：三只时钟均有名字、合成测试与 as-built 表，同时冻结符号无 diff。做不到即停，不以“顺手修得更像交易所”替代。

---

## 5. 人裁点（P\* · 未裁 = 禁止编码）

| ID | 问题 | 建议默认 | 选项与后果 |
|----|------|----------|------------|
| **P1** | GO 后是否只加当前扫描窗口的相位标签与测试、成交价完全不变？ | **A** | **A**：只命名 / 测试，`_in_session`、扫描器与既有取价均不改；A **不表示**集合竞价撮合已建模、已正确或“match existing exchange session”。**B**：分钟触价跳过 14:57–14:59。**C**：分钟触价跳过 14:57–15:00。若选 B/C，立即停止，先修订 plan；禁止在本 A–C 切片直接改扫描器。 |
| **P2** | 是否给 `trades.csv` 增加 `session_phase` / `price_rule` 列？ | **A：否** | **A**：本轮只在代码命名、测试与文档中可见，产物 schema 不漂移；**不加列不等于成交天然未变**，仍须由 F-R8/F-R9 冻结与反向 import 围栏证明。**B**：新增列；须停止并另裁 schema、下游快照和兼容性，不进当前切片。 |
| **P3** | 旧 P2/P3/P4 与已知 v7 分叉是否继续后置？ | **A：确认后置** | **A**：印花、改股 / 现金红利 / ST PIT、成交量上限、v7 `limits=None` fail-open、v7 ST 非 PIT 全部不进本船。**B**：不确认；停止并分别开 plan，不得扩写本船。 |
| **P4** | 15:00 bar 的“触价资格”与“官方收盘 / 标记价用途”是否分开裁？ | **A：分开；本轮两者都不改** | **A**：即使未来排除触价，也不得自动排除 15:00 的收盘 / 标记用途。**B**：二者联动改变；须先补行情时间戳证据、估值影响与独立 plan。P1=C 不自动回答 P4。 |

人裁建议为 **P1=A / P2=A / P3=A / P4=A**。头部状态改为「✅ 已人裁 GO（commit hash）」之前，即使建议默认无人反对，也仍视为未裁。

---

## 6. 非目标

| 不做 | 原因 / 边界 |
|------|-------------|
| 改 14:57–15:00 的成交资格、成交价或收盘标记 | P1 / P4 未裁；本船只命名当前扫描窗口，不宣称已实现交易所撮合 |
| 给模拟环加新成交调度器、订单对象或事件总线 | 本仓是向量化扫描；不仿 LEBS / OMS |
| 改日线 gap-stop / touch-trigger / same-bar / `pending_exit` 时点，或改分钟 open / close 取价 | F-R6；会改 trades 与 NAV |
| 给 `trades.csv` / summary 加列或相位计数 | P2 建议否；避免产物契约漂移 |
| 改 MyQuant 训练 / 名单导出；改 1.3 LEBS / MockQMT / `trade_decision` | 三仓分工不重叠 |
| import qlib，恢复 PortAna / Exchange，复活 Cerebro / Rolling | 已停用 / 已退场；不借行业参照搬框架 |
| 复制 vn.py OMS / CTP、RQAlpha 撮合器、backtrader Cerebro | 本仓只取公开实践中的“显式命名”原则 |
| 用本仓 NAV 对 PortAna / LEBS / 真栈，或承诺 parity | 引擎回答的问题不同 |
| 重开 E-R1–E-R6、改 `BILATERAL_10BP`、合并双账本、把 7 注册进 BOOKS | 既有 SSOT 硬锁 |
| 改 `read_lake_minute_ohlc` / `load_minute_ohlc`、numba / Python 扫描内核 | #108 冻结面；标签不应改变数据或扫描 |
| 推进印花、送转增股、现金红利、ST PIT、volume cap、滑点 / 参与率 | 旧裁决后置；不是 fill clock |
| 改 Mode B `shares/=k` / `rescale_position`、HELP_LOCK、旧 CLI | 已锁行为与入口契约 |
| 读湖、跑真实回测、使用真 symbol 行情 | CI 与本 plan 验证均 data-free |
| 在当前 `docs/industry-align-refactor-2026-09-18` 分支实施 | 当前分支只放 plan；实施必须在人裁 GO 后另开 feat 分支 |

---

## 7. 切片（仅在人裁 GO 后实施；共 3 片）

实施底必须是**人裁 GO 当时的 `origin/master` commit**（当前未知，不是 `c44da87` 的别名），另开 `feat/industry-align-refactor`；不得在本 docs 分支写代码。若该 commit ≠ `c44da87`，先重核本 plan 的事实锚点再写测试。每片一个未来 commit，A → B → C；任一行为漂移立即停下回到 P\*。

### 7.1 切片 A：纯叶子 fill clock

**动作**

- 新建 `backtest/research/ashare_fill_clock.py`；只允许标准库（例如 `enum`），以及 `from backtest.research.ashare_bars import AM_OPEN, AM_CLOSE, PM_OPEN, PM_CLOSE`（或等价的仅这四个名字）。不 import pandas / numpy / qlib、`trade_fee_policy`、LEBS、`simulate`、`scan_held_day` 或 `csv_simulate_loop`。
- 四个既有边界只读引用 `ashare_bars` 真源；叶子源码禁止再赋值 `AM_OPEN = ...`、`AM_CLOSE = ...`、`PM_OPEN = ...`、`PM_CLOSE = ...`。只在叶子新增 `CLOSING_CALL_OPEN = 14 * 60 + 57`；它是**标签分界**，不是 `ashare_bars` 已有常量，也不是现有成交窗口。
- 提供 `SessionPhase(str, Enum)`：`continuous` / `closing_call`，以及 `session_phase(hm)`。输入域只包括既有会话分钟；午休、开盘集合竞价与盘外分钟直接调用时显式拒绝（`ValueError`），不得默认为 `continuous`，也不得把该函数接进扫描器。
- `continuous` = 09:30–11:30、13:00–14:56；`closing_call` = `CLOSING_CALL_OPEN`（14:57）至 `PM_CLOSE`（15:00，含端点）。这些值只标记当前扫描窗口，不表示交易所忠实撮合。
- 提供 `FillPriceRule(str, Enum)`，值固定为 `daily_open_board_same_close`、`daily_stop_gap_open`、`daily_stop_touch_at_trigger`、`daily_pending_next_open`、`minute_gap_open`、`minute_trigger_bar_close`。该集合是本切片具名路径，**不是全量选价器**：same-bar 前缀还可含 `topk_drop` / `model_exit`，v7 与策略 9 等已记录分叉不纳入本切片。
- 提供文档常量 `POOL_FILE_DAY_RULE = "filename_day_is_decision_and_buy_day"`。不解析 CSV、不产生订单、不调用 `simulate` / `scan_held_day`。
- 不从任何现有生产模块 import 新叶子；这一步只建立词汇，不接线。反向禁令必须由切片 B 的 pytest 围栏拒绝。

**DoD**

- `ashare_fill_clock.py` 是唯一生产代码新增文件；AST import allowlist 只有标准库 + `ashare_bars` 上述四个名字，且 AST 证明四个名字均来自该 import、叶子没有本地再定义。
- `session_phase(14*60+57) == "closing_call"`，`session_phase(15*60) == "closing_call"`；合法连续竞价分钟只返回 `continuous`。
- `FillPriceRule` 只描述上述现有书引擎路径，没有 scheduler / fill / state mutation API，也不覆盖 v7。
- pytest 围栏机械拒绝 `SIMULATE_HOT_PATH` 中任何模块 import `ashare_fill_clock` / `backtest.research.ashare_fill_clock`；`rg -n "ashare_fill_clock" backtest/research --glob '!ashare_fill_clock.py'` 只作补充。
- 下述共用冻结文件相对实施 base 无 diff。

### 7.2 切片 B：data-free 契约测试

**动作**

- 新建 `tests/test_ashare_fill_clock.py`；只用整数、合成数组 / DataFrame 与现有纯函数，不读湖、不用真 symbol 行情。
- 用 AST 证明四个既有会话边界只从 `ashare_bars` 导入且叶子无本地再定义；14:57 仅是新增相位标签分界，不是新的会话终点或成交窗口。
- 用行为断言把六个具名价格规则映射到现有符号：日线走 `csv_daily_backtest.simulate`；分钟走 `csv_minute_backtest.scan_held_day_python`（或 `scan_held_day(..., use_numba=False)`）。不靠改生产代码或旧断言建立映射，不新开除权切片。
- 修改 `tests/test_ashare_simulate_import_fence.py` 的窄面：`SIMULATE_HOT_PATH` 元组按 #108 清单保持逐字节不变；只在 `forbidden_imports` 增加对 `ashare_fill_clock` / `backtest.research.ashare_fill_clock` 的拒绝并补机械断言。不得把叶子追加进热路径清单，也不得改 #108 plan。
- 盘外直接调用 `session_phase` 的 `ValueError` 只测叶子行为，不把叶子接进 `scan_held_day` / `simulate`。

**必须新增的测试名与断言**

| 测试名 | 机械断言 |
|--------|----------|
| `test_fill_clock_bounds_import_only_ashare_bars` | AST 证明 `AM_OPEN/AM_CLOSE/PM_OPEN/PM_CLOSE` 只由 `backtest.research.ashare_bars` import，叶子无本地赋值；运行值与真源相同 |
| `test_session_phase_labels_current_scan_window` | 09:24、11:31、12:59、15:01 直接调用显式拒绝；09:30、11:30、13:00、14:56 为 continuous；14:57 / 15:00 为 closing_call 且 `_in_session` 接受。测试名、注释和断言说明必须写“标签描述当前扫描窗口，不是交易所忠实 closing-call 撮合” |
| `test_pool_file_day_is_decision_and_buy_day` | 文件名日 T 合同不变；日线夹具在 T 以 close 买入；分钟夹具同时放置价格不同的 14:55 与 15:00 bar，必须以 14:55 close 买入。另造**缺 14:55**夹具才断言 `[14:30, 14:55]` 最后一根 fallback；两者都不是 T+1 open |
| `test_chase_buy_prices_use_existing_t1_quotes` | 合成日线追买在 T+1 以当日 close、合成分钟追买在 T+1 以 09:45 close（另测既有 `≤09:45` fallback），reason 均为 `chase:T+1`；均不是 T+1 open，也不是池日 T 尾盘 |
| `test_daily_open_board_rule_uses_same_day_close` | 夹具明确避开涨跌停；`open_board` 的 trade date 为触发日、price 为当日 close。测试说明 same-bar 集合不只 `open_board`，且踩涨跌停时不保证成交或 pending |
| `test_daily_stop_gap_rule_uses_same_day_open` | 复用等价于既有 gap 夹具：reason=`stop_loss:gap_open`，触发当日 price=open；不改 `tests/test_csv_daily_backtest.py:405-418` 旧断言 |
| `test_daily_stop_touch_rule_uses_same_day_trigger` | 买入 close=10.0，次日 open=9.85、low=9.50、close=9.60、`stop_pct=0.02`；reason=`stop_loss:touch`、当日 price=9.8。明确 9.8 不是 9.60，也不是再下一 open；不得改 `tests/test_csv_daily_backtest.py:200-217` 旧断言 |
| `test_daily_pending_exit_rule_uses_next_session_open` | 只选择已知会写入 `pending_exit` 的 reason（例如非 same-bar `ma_signal` / `force_sell:max_hold`），断言下一可卖 session 的 price=open；禁止再断言“全部非 same-bar reason” |
| `test_minute_gap_stop_rule_uses_bar_open` | 首个 bar open 已破阈值时 price = open、reason = `stop_loss:gap_open` |
| `test_minute_touch_rule_uses_bar_close` | open 未破、该分钟 close 触价时 price = close、reason = `stop_loss:touch` |
| `test_fill_clock_leaf_imports_only_allowed_bounds` | AST 只允许标准库 + 从 `ashare_bars` 导入上述四个名字；其余本仓 / 第三方 import 均失败，尤其 qlib、`trade_fee_policy`、LEBS、simulate / `scan_held_day` / `csv_simulate_loop` |
| `test_simulate_hot_path_forbids_fill_clock_import` | `SIMULATE_HOT_PATH` 字节仍等于 #108 清单；对裸名与全限定名的 import 夹具均由 `forbidden_imports` 拒绝；真实热路径逐项继续过围栏 |

**DoD**

- 上表测试全绿；`tests/test_ashare_simulate_import_fence.py` 只允许新增上述拒绝与断言，`SIMULATE_HOT_PATH` 元组及 `test_hot_path_list_matches_plan_bytes` 对 #108 的约束字节不动。
- 合成结果逐项等于六个具名 `FillPriceRule` 语义；表与枚举明确不是全量选价器、不含 v7；没有通过改旧断言来“适配”新数字。
- 无湖路径、无真代码、无 snapshot 更新；下述共用冻结文件相对实施 base 无 diff。

### 7.3 切片 C：as-built 文档回写（无代码接线）

**动作**

- 只在 `docs/backtest/engine-ashare-correctness.md` 模块表后补一张「现状成交时钟」短表：池买日线 / 分钟、追买日线 / 分钟、当前扫描窗口相位、六个具名书引擎价格规则及代码符号。
- 明写 14:57–15:00 的 `closing_call` 是**当前扫描窗口标签**：`_in_session` 接受这些 bar，扫描若到达仍按旧分支处理；这不是交易所忠实撮合，也不证明所有路径在该段成交。不宣称已修复。
- 明写价格短表不是全量选价器：same-bar 前缀不只 `open_board`，策略 9 证明夹具不能单独证明 open/close，v7 另有首 bar open / 严格 14:55 / 最后一根 close 规则且未纳入。
- 不在模拟环外加计数器，也不向 `trades.csv` / summary 接线。若评审要求相位计数或产物列，回到 P2，停止本片。

**DoD**

- 该 commit 只改 `engine-ashare-correctness.md`；模块表新增 `ashare_fill_clock.py`，短表与切片 B 六个枚举值逐字一致，并带“扫描窗口标签 / 非全量 / 不含 v7”限定。
- 文档继续声明读取器、内核、双账本、E-R1–E-R6 与价格数字未变。
- 不改 README / AGENTS / 旧 plan / HELP_LOCK；下述共用冻结文件相对实施 base 无 diff。

### A–C 共用冻结 diff 清单

实施 diff 不得触碰下列生产文件；生产面选择整文件冻结，强于只比行号。围栏测试文件是唯一窄冻结例外：

| 文件 | 冻结符号 / 契约 |
|------|-----------------|
| `backtest/research/ashare_bars.py` | 四个会话常量、`_in_session`、`read_lake_minute_ohlc`、`load_minute_ohlc` |
| `backtest/research/ashare_session.py` | `t1_sellable`、涨跌停命中与买卖谓词 |
| `backtest/research/ashare_fees.py` | `BILATERAL_10BP` / `DEFAULT_SCHEDULE` |
| `backtest/research/csv_daily_backtest.py` | `simulate`、日线价格时点、`HELP_LOCK` |
| `backtest/research/csv_minute_backtest.py` | `_scan_held_day_numba_trail`、`scan_held_day_python`、`scan_held_day`、`simulate`、`HELP_LOCK` |
| `backtest/research/csv_minute_backtest_v7.py` | `Lot` / `Position` / `_sell_lots` 与已知 fail-open 分叉 |
| `backtest/research/csv_ledger.py` | `Position`、`rescale_position`、`execute_buy`、`_sell`、trades 字段 |
| `backtest/research/csv_simulate_loop.py` | `run_chase_due_day`、`execute_buy(... reason="chase:T+1")` 调用、`append_equity_and_eod_marks`；追买价 / shares / NAV / EOD_MARK 不动 |
| `backtest/research/csv_strategy_books.py` | `daily_same_bar_prefixes` 与 BOOKS |
| `backtest/research/strategy5_rules.py` | `FORCE_SELL_HM=14:50` 与 `HELP_LOCK`；不得把强卖推到 15:00 |
| `backtest/research/csv_artifacts.py` | `trades.csv` / summary 产物契约 |
| `tests/test_ashare_simulate_import_fence.py` | **窄冻结**：`SIMULATE_HOT_PATH` 元组与 #108 字节不动；只允许在 `forbidden_imports` 增加 `ashare_fill_clock` 拒绝及对应测试，不再整文件冻结 |

机械门：相对实施 base，上表生产文件的 `git diff --exit-code` 必须为 0；围栏测试文件由定向 pytest 证明窄 diff 与 #108 元组不漂移。若其它冻结面必须改，当前 plan 即不再覆盖，停止并回到 P\*。

---

## 8. 命名参考与不 vendoring 理由

外部框架类比不作为行为证据；本 plan 的每个规则只以 `c44da87` 仓内符号与合成测试为锚。相位命名尤其不证明已有交易所忠实撮合。

v0.1 §8 的 vn.py / backtrader / RQAlpha / Qlib 名称表只作类比、不作行为证据（R7）。本版不再用它们指导切片，也不因此放宽不 import qlib、不复活 Cerebro 的禁令。

| 切片 | 采用的最小实践 | 仓内依据 | 明确不做 |
|------|----------------|----------|----------|
| **A · 命名叶子** | 会话边界单一真源、标签与成交许可分离 | 四边界只读 import `ashare_bars`；14:57 仅由仓内 L2 桶作为分界证据 | 不 import L2 ETL，不建 OMS / 网关 / 事件总线，不把标签接进扫描器 |
| **B · 契约测试** | 决策日、追买日与取价路径分别可执行验证 | 现有 daily / minute simulate、`csv_simulate_loop`、既有止损测试与 import fence | 不借测试改成交，不把六枚举当全量 selector，不以“标签绿”证明行业对齐 |
| **C · as-built 表** | 具名规则可审计，并标明适用边界与已知分叉 | reason、可卖、涨跌停及“当前扫描窗口标签” | 不 import qlib，不恢复 PortAna / Exchange，不复活 Cerebro / Rolling，不纳入 v7 为已覆盖 |

不开 vendor 目录，不复制外部实现，不新增框架依赖；禁令不因本次勘误放宽。

---

## 9. 验证命令（实施 PR；全部 data-free）

```powershell
# 定向契约
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/test_ashare_fill_clock.py tests/test_csv_daily_backtest.py tests/test_csv_minute_backtest.py tests/test_scan_held_day_numba_parity.py tests/test_ashare_simulate_import_fence.py

# 本仓既有合入门
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/

# data-free path / bridge gates
D:\anaconda3\envs\vanna312\python.exe scripts/gates/verify_oskh_data_contract.py
D:\anaconda3\envs\vanna312\python.exe scripts/gates/verify_data_path_ssot.py
D:\anaconda3\envs\vanna312\python.exe scripts/gates/verify_no_hardcoded_machine_paths.py
D:\anaconda3\envs\vanna312\python.exe scripts/gates/verify_tr_bridge_import_ssot.py
```

```bash
# 在从“人裁 GO 当时的 origin/master”新开的 feat 分支执行；这不是 c44da87 的别名
IMPLEMENTATION_BASE="$(git merge-base HEAD origin/master)"
git diff --exit-code "$IMPLEMENTATION_BASE"...HEAD -- \
  backtest/research/ashare_bars.py \
  backtest/research/ashare_session.py \
  backtest/research/ashare_fees.py \
  backtest/research/csv_daily_backtest.py \
  backtest/research/csv_minute_backtest.py \
  backtest/research/csv_minute_backtest_v7.py \
  backtest/research/csv_ledger.py \
  backtest/research/csv_simulate_loop.py \
  backtest/research/csv_strategy_books.py \
  backtest/research/strategy5_rules.py \
  backtest/research/csv_artifacts.py

# pytest 围栏是“不接线”的主门；rg 只作补充。代码中不得新增盘符字面量
rg -n "ashare_fill_clock" backtest/research --glob '!ashare_fill_clock.py'
rg -n '[A-Za-z]:[\\\\/]' backtest/research/ashare_fill_clock.py tests/test_ashare_fill_clock.py
```

预期：生产冻结 diff 为 0；`tests/test_ashare_simulate_import_fence.py` 只有 §7.2 允许的窄改动，且 pytest 证明 `SIMULATE_HOT_PATH` 仍逐字节等于 #108 清单并拒绝两种叶子 import；两条 `rg` 均无输出。不得运行湖上回测；不得用真实行情补充合入门。文本文件统一 UTF-8 无 BOM、NUL=0。

---

## 10. 代码落点（`c44da87` 事实锚）

| 文件:行 / 符号 | 当前职责 | GO 后动作 |
|-----------------|----------|-----------|
| `docs/backtest/pool-csv-contract.md:11-12` `As-of` | 文件名日 T = 买入日 / 决策日 | 只读权威；不改 |
| `backtest/research/ashare_bars.py:27-28` `AM_OPEN/AM_CLOSE/PM_OPEN/PM_CLOSE` | 既有会话四边界真源 | 切片 A 叶子只读 import；禁止复制；本文件不改 |
| `backtest/research/ashare_bars.py:302-306` `_in_session` | 09:30–11:30、13:00–15:00（含端点） | 切片 B 只断言标签描述当前扫描窗口；不称交易所撮合正确；代码不改 |
| `backtest/research/ashare_bars.py:328` `read_lake_minute_ohlc` | 冻结湖读取器 | 字节不动 |
| `l2_analytics/etl_day.py:118-119` `_session_sql`；`tests/test_l2_etl.py:121` | 14:57 起标 `close_auction` | 只作标签分界证据；研究核不 import L2 ETL，代码 / 测试均不改 |
| `backtest/research/ashare_session.py:29/34/39/73/77` | 涨跌停、T+1、买卖门谓词 | 不重开 E-R\*；代码不改 |
| `backtest/research/ashare_fees.py:53-55` `BILATERAL_10BP` / `DEFAULT_SCHEDULE` | 默认双边 10bp | 代码不改 |
| `backtest/research/csv_daily_backtest.py:204` `simulate`；`:329-333`；`:336-360`；`:370-401` | 已 pending 下一 open；gap-stop 当日 open；touch-stop 当日 trigger；same-bar 前缀当日 close但受涨跌停门约束 | 切片 B 从外部合成测试；代码不改，旧 9.8 / 9.4 断言不改 |
| `backtest/research/csv_daily_backtest.py:403-410` `_chase_quotes_for`；`:428-435` `_pool_quote_for` | 追买给 T+1 open/close 且共用环取 close；池日 T 取 close | 切片 B 分开锁追买与池买；代码不改 |
| `backtest/research/csv_strategy_books.py:118/692/767` `daily_same_bar_prefixes` | 默认 `open_board`；topk 接入 `topk_drop` / `model_exit` | 记录动态集合；代码不改，不把六枚举称全量 |
| `backtest/research/csv_minute_backtest.py:150/232/323` | numba 内核 / Python 参考 / wrapper | 切片 B 调参考路径；三个符号不改 |
| `backtest/research/csv_minute_backtest.py:277-319` `scan_held_day_python` 分支 | gap 用 open；其余触价用 close | 切片 B 锁行为；代码不改 |
| `backtest/research/csv_minute_backtest.py:112/469-490/685-713` `BUY_HM` / `_buy_px` / `_chase_quotes` / `_pool_quote_for` | 池买严格优先 14:55、缺失才用窗内 fallback；追买 T+1 取 09:45 或既有 fallback | 切片 B 用不同价的 15:00 bar 与 T+1 合成夹具锁路径；代码不改 |
| `backtest/research/csv_minute_backtest.py:493` `simulate`；`:613-651` | 传入会话分钟并最终填单 | 不 import 新叶子；代码不改 |
| `backtest/research/strategy5_rules.py:16` `FORCE_SELL_HM` | 14:50 强制卖阈值 | 整文件冻结；不改成 15:00，不把 14:57 称统一现有成交窗口 |
| `backtest/research/csv_ledger.py:66/141/194/242` | 书账本与填单 / E-R6 参考价缩放 | 整文件不改 |
| `backtest/research/csv_simulate_loop.py:144/179` `run_chase_due_day`；`:299` `append_equity_and_eod_marks`；`:324-339` `EOD_MARK` | 第二个 quote 是追买价并以 `chase:T+1` 买入；日线 close 标记 NAV / EOD_MARK | 整文件冻结；追买、shares、NAV、EOD_MARK 不改 |
| `backtest/research/csv_minute_backtest_v7.py:61/69/223/327-411` | v7 独立账本 / 卖出；首 bar open 分叉、严格 14:55、最后 bar close | 整文件不改；价格短表不覆盖，`limits=None` fail-open 继续披露 |
| `tests/test_ashare_simulate_import_fence.py:13-29` `SIMULATE_HOT_PATH`；`:32-48` `forbidden_imports` | #108 热路径固定清单；现围栏尚未拒叶子 | 元组字节不动；只增加叶子 import 拒绝与对应测试，不扩大扫描范围 |
| `backtest/research/ashare_fill_clock.py`（拟新增） | 纯命名叶子 | 切片 A 新建 |
| `tests/test_ashare_fill_clock.py`（拟新增） | 时钟 / 价格映射 data-free 契约 | 切片 B 新建 |
| `docs/backtest/engine-ashare-correctness.md`（现有） | A 股 as-built SSOT | 切片 C 仅补短表；当前 docs PR 不改 |

---

## 11. 修订程序

1. 当前只合本 plan；保持状态「⏳ 待评审 / 待人裁 GO」。合 docs PR 不触发实施。
2. 后续按工作流评审并逐条裁 P1–P4；证据裁决，不以多数票替代语义选择。
3. 若 P1≠A、P2=B、P3=B 或 P4=B，停止原切片，先修订范围、冻结面与 DoD；不得沿用“行为不变”的风险档直接编码。
4. 全部人裁后回写选项与 GO commit hash，并准备独立 handoff；GO 前不得创建实现提交。
5. 记录**人裁 GO 当时的 `origin/master` commit**，从该 commit 新开 `feat/industry-align-refactor`，按 A / B / C 分 commit。`c44da87` 只是真实事实与本文行号的核对锚，不是这个实施 base 的别名。若 GO 时 master ≠ `c44da87`，先重核锚点再写测试；契约以 v0.2 / §12 改正后的句子为准，不得复用 v0.1 的“四条价格规则”或“非 same-bar 全部 next open”。当前 docs 分支不得承载 Python 或测试。
6. 只运行 §9 data-free 门；遇任何成交价、股数、reason、NAV、产物 schema 或冻结文件 diff，立即 STOP，新增 P\*。
7. 实施 PR 合入后，才将本 plan 状态回写为「✅ 已实施（PR #N）」；不得提前宣称落地。

---

## 12. 勘误表（2026-09-18）

三份对抗评审不是投票。下表逐条记录 v0.1 让步、核对锚点与正文落点；状态仍为待评审 / 待人裁 GO。

### 12.1 v0.1 让步与正文改正

| ID | 来源 | v0.1 原句指向 | `c44da87` 核对锚点 | 让步 / 裁决 | 正文改正位置 |
|----|------|----------------|---------------------|-------------|--------------|
| **E1** | 2026-09-18 对抗评审：异议、领域安全、模式 | §0 / F-R6 / §7.1–§7.3 把日线价压成 `open_board` same-close 与“其余 pending next-open”；§7.2 又要求“非 same-bar reason”全部下一 open | `csv_daily_backtest.py:165-166` HELP；`:336-351` gap 当日 open；`:338-359` touch 当日 trigger；`tests/test_csv_daily_backtest.py:200-217` 价 9.8、`:405-418` 价 9.4；`tests/test_exdiv_refprice_engines.py:203-219` 价 4.9、bar close 5.10 | 接受。新增 `daily_stop_gap_open` 与 **`daily_stop_touch_at_trigger`**；`daily_pending_next_open` 只指已写入 `pending_exit` 的 reason。不得改 `simulate`、不得改旧 9.8 / 9.4 断言、不新开除权切片 | §0、§2.1、F-R6、§7.1–§7.3、§10 |
| **E2** | 2026-09-18 对抗评审：异议 | §0 / F-R4 用“当日尾盘或收盘”描述一只决策钟；§7.2 的“14:55 或 fallback”可被宽松夹具绕过；冻结表漏 `csv_simulate_loop.py` | 日线池买 `csv_daily_backtest.py:428-435`；分钟池买 `csv_minute_backtest.py:112/469-476`；日线追买 `:403-410`；分钟追买 `csv_minute_backtest.py:479-490`；`csv_ledger.py:27/106-112`；`csv_simulate_loop.py:144/179`；热路径清单 `tests/test_ashare_simulate_import_fence.py:13-29` | 接受。点名池买·日线、池买·分钟、追买·日线、追买·分钟三类路径（追买内含两个不同取价）；F-R4 只继续禁止把**池买**改 T+1 open。分钟夹具必须用不同价的 14:55 / 15:00 bar；另测缺 14:55 fallback；冻结追买与 EOD 落点 | §0、§2.1、F-R4/F-R8、§7.2、冻结表、§9、§10 |
| **E3** | 2026-09-18 对抗评审：异议、领域安全、模式 | §1.3 / F-R5 / P1 / §7.2–§7.3 把 `[14:57,15:00]` 写成现有成交窗口，并用 `match_existing_session` 命名测试 | `strategy5_rules.py:16` `FORCE_SELL_HM=14:50`；`csv_minute_backtest.py:316-319` 首根达阈值即返回；`:469-476` 池买截止 14:55；`ashare_bars.py:27-28/302-306/350-352` 只证明 bar 被接受；`l2_analytics/etl_day.py:118-119` 与 `tests/test_l2_etl.py:121` 只提供 14:57 标签分界 | 接受领域安全对“不得暗示集合竞价已正确”的警告；**不同意模式评审把“现有成交窗口”这一半也判为成立**。F-R5“标签不是过滤器”保留；14:57 改称新扫描窗口标签，不是统一既有成交窗口或交易所撮合。P1 默认仍 A，B/C 仍待人裁且本切片不落地 | §0、§1.3、§2.1、F-R5/F-R10、P1、§7.1–§7.3、冻结表、§8、§10 |
| **E4** | 2026-09-18 对抗评审：模式 | F-R9 / §7.1 要叶子“仅标准库”并本地定义四个会话整数，§7.2 只做相等测试 | `ashare_bars.py:27-28` 是四常量真源；现有消费方 `csv_minute_backtest.py:82-88`、`unified_exit_modeb.py:20-27` 均 import | 接受。叶子只读 import 这四个名字，禁止本地再定义；`CLOSING_CALL_OPEN` 可在叶子新增但只作标签。AST 证明来源与无本地赋值；其它本仓 / 第三方 import 仍禁，`ashare_bars.py` 仍冻结 | F-R9、§7.1、§7.2、§10 |
| **E5** | 2026-09-18 对抗评审：领域安全、模式 | §7.1 / §9 只用 `rg` 保证叶子不进 simulate；v0.1 又整文件冻结围栏测试，导致不能加机械拒绝 | `tests/test_ashare_simulate_import_fence.py:13-29` 热路径含 `csv_simulate_loop`；`:32-48` 现只拒 qlib / `trade_fee_policy` / `backtest.lebs` | 接受。`SIMULATE_HOT_PATH` 元组逐字节保持 #108 清单，叶子不追加进去；只在 `forbidden_imports` 增加裸名 / 全限定叶子拒绝并加测试。`rg` 降为补充。动机：P2=A 不加列不能阻止将来用 `closing_call` 做 `continue` 改价；本切片不授权该过滤器 | F-R9、P2、§7.1–§7.2、冻结表、§9、§10 |
| **E6** | 2026-09-18 对抗评审：异议、领域安全、模式 | 对抗评审要求勘误不得借机放宽既有禁令 | `engine-positioning-ssot.md`；`engine-ashare-correctness.md`；`ashare_fees.py:53-55`；`tests/test_ashare_simulate_import_fence.py:13-29` | **维持**：不 import qlib；不复活 Cerebro / Rolling / PortAna / Exchange；不合并本仓、MyQuant、LEBS、实盘栈，且 LEBS ≠ 实盘栈、本仓无 `backtest/lebs/`；不以本仓 NAV 对 LEBS / 实盘 / PortAna；不重做 #108；不编辑 `read_lake_minute_ohlc`、numba / Python 扫描内核字节；不重开 E-R1–E-R6；`BILATERAL_10BP`、双账本、7 不进 BOOKS 均维持。相位标签不得升格为会话对齐成功 | F-R1–F-R3、F-R7–F-R13、§6、§8、冻结表 |
| **E7** | 2026-09-18 对抗评审：异议 | 档头以 `c44da87` 为事实锚，§7 / §9 又以实施时 master 为 diff base，容易误读为同一个 commit | 本文引用行号在 `origin/master` `c44da87` 核过；实施命令为 `git merge-base HEAD origin/master` | 接受并拆开：事实锚=`c44da87`；实施 diff base=**人裁 GO 当时的 `origin/master` commit**，当前未知。若两者不同，实施前重核锚点；测试合同只采用 v0.2 勘误后句子 | 档头、§7、§9、§11 |

### 12.2 记录，不改成交，不新开切片

| ID | 来源 | 已核对记录 | 本 plan 处置 |
|----|------|------------|-------------|
| **R1** | 2026-09-18 对抗评审：异议 | same-bar 不只 `open_board`：默认 `csv_strategy_books.py:118`；topk 分别在 `strategy_topk_dropout_rules.py:25`、`strategy_topk_score_exit_rules.py:25` 增加 `topk_drop` / `model_exit`，接线在 `csv_strategy_books.py:692/767`。`csv_daily_backtest.py:378-399` 命中前缀才按当日 close；`:382-396` 涨跌停门可阻止成交且不一定 pending | 价格枚举 / 短表明确非全量；`open_board` 合成夹具必须避开涨跌停，不为变绿修改 `simulate` |
| **R2** | 2026-09-18 对抗评审：异议、领域安全 | v7 不适用书引擎价格表：`csv_minute_backtest_v7.py:327-340` 仅首 bar 可用 open；`:381-411` 严格 `hm==895`，缺则 `skip_no_1455`；`:398-404` 计时退出用最后一根 close。`limits=None` 卖侧仍 fail-open | F-R12 与整文件冻结维持；短表写“不含 v7”，不得称涨跌停 / 取价已收口 |
| **R3** | 2026-09-18 对抗评审：异议 | 策略 9 在 `strategy9_rules.py:4/25` 写 `force_sell:max_hold` 收盘记账、次日开盘离场；默认 same-bar 前缀不含 `force_sell`。`tests/test_strategy9_book.py:92-117` 卖出日与 reason 可证，但 OHLC 全为 10.0，不能单独证明价来自 open 而非 close；分钟 `force_sell:time` 才是当根 close（`csv_minute_backtest.py:316-319`） | 只记录枚举非全量，不新开策略 9 切片 |
| **R4** | 2026-09-18 对抗评审：异议 | `csv_simulate_loop.py:299-339` `append_equity_and_eod_marks` 写权益与 `side=EOD_MARK`；价格由 `csv_ledger.py:159-172` `market_close_mark` 提供，分钟 `simulate` 在 `csv_minute_backtest.py:729-735` 传日线 bars | 冻结该函数；不把 EOD 标记并成第四只产品买钟，不声称三条买路径锁住 NAV。P4 继续分开触价资格与 15:00 标记，本轮都不改 |
| **R5** | 2026-09-18 对抗评审：异议、领域安全 | **未核实并保持未核实**：湖 parquet 是否实际有 14:58/14:59/15:00 bar，及 `time` 是否会话钟点标成 UTC。代码 `ashare_bars.py:350-352` 会接受相应 hm，有 bar 才进入 `_in_session` | 不读湖，不在 plan 中宣称已有这些真实 bar；只陈述代码路径条件 |
| **R6** | 2026-09-18 对抗评审：领域安全 | winner-ratio 单位、印花与成交量上限不属于 fill clock | 不采纳扩大范围；F-R13 与非目标维持，避免把未纳入误读成漏审或已修复 |
| **R7** | 2026-09-18 对抗评审：模式 | v0.1 §8 把 vn.py、backtrader cheat-on-close、RQAlpha、Qlib 写成每片的开源对照。模式评审认为这些名字是装饰，删掉不改变 A/B/C，且不得因此放宽 qlib / Cerebro 禁令 | 同意工具名不是设计依据；§8 改为仓内锚点并保留禁令原文（E6）。不把收掉类比读成授权 vendor 或改成交 |

---

## 13. Changelog

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.2 | 2026-09-18 | 对 v0.1 作 E1–E7 勘误：补日线 stop 取价、拆分池买 / 追买路径、收窄 14:57 为扫描窗口标签、四边界改为 import 真源、增加反向 import 围栏、补冻结面并拆分事实锚 / 实施 base；记录 R1–R7，不改 P1–P4 建议默认，不标 GO |
| v0.1 | 2026-09-18 | docs-only 首版：唯一提案为 fill clock 显式化；P1–P4 待裁；切片 A–C 均要求行为不变 |
