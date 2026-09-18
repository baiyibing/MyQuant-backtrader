# Plan：研究成交时钟显式化（fill clock）（2026-09-18）

> **落盘**：2026-09-18。**v0.1**（docs-only；本 PR 只新增本 plan，不写 Python / 测试）。
> **状态**：⏳ **待评审 / 待人裁 GO**。合本 docs PR ≠ 实施 GO；P\* 未裁前禁止编码。
> **风险档**：**引擎结构 / 成交语义高敏**——目标是把既有决策、会话、价格规则命名并用 data-free 测试锁住；默认成交价、股数、reason、NAV 与产物契约必须为零变化。
> **业务源**：[引擎定位 SSOT](engine-positioning-ssot.md) · [A 股正确性 as-built](engine-ashare-correctness.md) · [Pool CSV contract](pool-csv-contract.md) · [#108 前置 plan](plan-ashare-engine-refactor-2026-09-18.md) · [PR #108](https://github.com/baiyibing/MyQuant-backtrader/pull/108)。
> **基线 tip**：`origin/master` `c44da87`（Merge PR #108）；本分支 `docs/industry-align-refactor-2026-09-18`。
> **工作流**：本文件是 [Codex 交接工作流](workflow-codex-handoff.md) **第 1 步（Plan 起草）**；评审规则见 [multi-ai-review-workflow.md](../engineering/multi-ai-review-workflow.md)。本次起草不运行 multi-agent review。
> **短注**：这是提案，不是编码，也不是修复 14:57–15:00 成交行为的授权。

---

## 0. 一句话

PR #108 已回答「**能不能成交**」；本 plan 只把仍散落在书引擎里的三只**研究成交时钟**做成命名叶子与 data-free 契约：

| 时钟 | 当前真义 | 本 plan 的动作 |
|------|----------|----------------|
| **决策时钟** | `YYYYMMDD.csv` 文件名日 T = 决策日 / 买入日；当日尾盘或收盘成交 | 命名并锁住；**不是缺陷，不改成 T+1 开盘** |
| **会话时钟** | `_in_session` 接受 09:30–11:30、13:00–15:00；14:57–15:00 当前也会进入分钟扫描 | 把已接受分钟标为 `continuous` / `closing_call`；**标签不是过滤器** |
| **价格规则** | 日线 `open_board` 当日 close；其余 `pending_exit` 下一可卖日 open；分钟缺口止损用 open，其余触价用该分钟 close | 建命名枚举 / 常量与对照测试；**不建新调度器** |

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
| [pool-csv-contract.md](pool-csv-contract.md) `As-of` | 文件名日 T 就是决策 / 买入日，当日尾盘或收盘成交 |
| [plan-ashare-engine-refactor-2026-09-18.md](plan-ashare-engine-refactor-2026-09-18.md) §0.3 / §5 | #108 切片 A–C 的已裁边界，不重做、不回滚 |
| [README.md](../../README.md) `Run research backtest` | 旧 CSV CLI 保留为真身（P5=A），HELP_LOCK 不变 |
| [workflow-codex-handoff.md](workflow-codex-handoff.md) | docs plan → 评审 → 人裁 GO → handoff → 另分支实施；GO 前禁编码 |

### 1.3 市场时段与当前模型的差

公开市场时段事实用于**命名差异**：开盘集合竞价 09:15–09:25；连续竞价 09:30–11:30、13:00–14:57；收盘集合竞价 14:57–15:00。

当前代码的窗口从 09:30 开始，所以开盘集合竞价已在窗外；下午窗口却一直到 15:00（含端点），所以 14:57–15:00 仍被分钟触价扫描当作普通会话 bar。这个差目前没有名字。本 plan 先命名、先测试，**不据此直接改变成交**。

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
| 池日 T | 文件名日就是决策 / 买入日；日线取当日 close，分钟取当日 14:55（缺失时取 14:30–14:55 最后一根）close | `pool-csv-contract.md:11-12`；`csv_daily_backtest.py:428-448` `_pool_quote_for`；`csv_minute_backtest.py:112` `BUY_HM` / `:469-476` `_buy_px` |
| 会话入口 | `AM_OPEN=09:30`、`AM_CLOSE=11:30`、`PM_OPEN=13:00`、`PM_CLOSE=15:00`，端点均含 | `ashare_bars.py:27-28`；`_in_session` `:302-306` |
| 开盘集合竞价 | 09:15–09:25 不被 `_in_session` 接受 | 同上 `_in_session` |
| 收盘集合竞价 | 14:57–15:00 被 `_in_session` 接受，当前没有独立相位名 | 同上 `_in_session`；`annotate_session` `:318-325` |
| 日线 `pending_exit` | 下一可卖日按 open 成交 | `csv_daily_backtest.simulate` `:329-333` |
| 日线 `open_board` | `daily_same_bar_prefixes` 命中后当日 close 成交；其余 reason 写入 `pending_exit` | `csv_strategy_books.py:118`；`csv_daily_backtest.simulate` `:370-401` |
| 分钟缺口止损 | 开盘已破阈值取该 bar open | `csv_minute_backtest.scan_held_day_python` `:277-285`；numba 同义分支 `:182-190` |
| 分钟其余触价 | 止损触价、sell gate、止盈 / trail、force 均取该分钟 close | `scan_held_day_python` `:283-319`；最终 `_sell` 调用 `csv_minute_backtest.simulate` `:643-651` |

---

## 3. 现锁（F-R\* · 本提案硬边界）

| ID | 规则 |
|----|------|
| **F-R1** | 本仓定位不变：只做向量化 CSV 研究成交。不是 Paper，不是柜台验收；不与 MyQuant 信号厂、1.3 LEBS 或实盘栈合并。LEBS 只在 1.3，LEBS ≠ MockQMT 真栈，本仓没有 `backtest/lebs/`。 |
| **F-R2** | PR #108 已落地的切片 A–C 不重做：一帧分钟、T+1 / 涨跌停谓词、import 围栏、冻结读取器、numba 内核锁、双账本与旧 CLI 均保持。 |
| **F-R3** | **不重开 E-R1–E-R6。** T+1 继续走 `t1_sellable`；涨跌停继续走现有谓词；E-R5/E-R6 只动参考价，shares 与现金红利不动；Mode B `shares/=k` 不回写 `rescale_position`。 |
| **F-R4** | 决策时钟锁：文件名日 T = 决策 / 买入日，当日尾盘或收盘成交。不得借“行业对齐”改成次日开盘。 |
| **F-R5** | 会话标签锁：`closing_call = hm ∈ [14:57, 15:00]`；这段当前仍被 `_in_session` 接受。`session_phase` 只描述已接受 bar，不改变过滤、扫描或成交资格；开盘集合竞价仍不入会话。 |
| **F-R6** | 价格规则锁：日线 `open_board` 当日 close；其余 `pending_exit` 下一可卖日 open；分钟开盘已破止损取 open，否则触价取该分钟 close。新叶子只命名，不提供调度器替换 `simulate` / `scan_held_day`。 |
| **F-R7** | 默认费率仍为 `BILATERAL_10BP`；7 不进 BOOKS；双账本不合并；旧 CLI / HELP_LOCK 不变。 |
| **F-R8** | 实施结果不得改变成交价、股数、reason 值或计数、NAV、`trades.csv` 列、`summary` 快照、HELP_LOCK、`read_lake_minute_ohlc` 字节、`load_minute_ohlc` 行为或两个分钟扫描内核字节。任何此类选择只准进入 P\* 并先修订 plan。 |
| **F-R9** | import 边界不变：不 import qlib，不复活 Cerebro / Rolling / PortAna / Exchange，不重写 LEBS 事件环、`matching_env`、Redis 或 live。新叶子仅依赖标准库整数 / 枚举语义，且不被模拟环 import。 |
| **F-R10** | 对照货币仍是 reason / 可卖 / 涨跌停，加上本 plan 的**相位标签**；不得用本仓 NAV 对 PortAna / LEBS / 实盘栈作为成功指标。 |
| **F-R11** | CI 必须 data-free；不读湖、不用真 symbol 行情。新代码不得出现硬编码盘符；行情路径若未来需要，仍只能走 resolver（本 plan 不新增行情读取）。 |
| **F-R12** | #108 已知分叉保持：书侧无昨收 / 未知板块先拒；v7 卖侧 `limits=None` fail-open；v7 ST 名称按窗末平铺、非 PIT。默认**不动**，只能经 P3 另票。 |
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
| **P1** | GO 后是否只加相位标签与测试、成交价完全不变？ | **A** | **A**：只命名 / 测试，14:57–15:00 仍参与现有扫描。**B**：分钟触价跳过 14:57–14:59。**C**：分钟触价跳过 14:57–15:00。若选 B/C，立即停止，先修订 plan；禁止在本 A–C 切片直接改扫描器。 |
| **P2** | 是否给 `trades.csv` 增加 `session_phase` / `price_rule` 列？ | **A：否** | **A**：本轮只在代码命名、测试与文档中可见，产物契约不漂移。**B**：新增列；须停止并另裁 schema、下游快照和兼容性，不进当前切片。 |
| **P3** | 旧 P2/P3/P4 与已知 v7 分叉是否继续后置？ | **A：确认后置** | **A**：印花、改股 / 现金红利 / ST PIT、成交量上限、v7 `limits=None` fail-open、v7 ST 非 PIT 全部不进本船。**B**：不确认；停止并分别开 plan，不得扩写本船。 |
| **P4** | 15:00 bar 的“触价资格”与“官方收盘 / 标记价用途”是否分开裁？ | **A：分开；本轮两者都不改** | **A**：即使未来排除触价，也不得自动排除 15:00 的收盘 / 标记用途。**B**：二者联动改变；须先补行情时间戳证据、估值影响与独立 plan。P1=C 不自动回答 P4。 |

人裁建议为 **P1=A / P2=A / P3=A / P4=A**。头部状态改为「✅ 已人裁 GO（commit hash）」之前，即使建议默认无人反对，也仍视为未裁。

---

## 6. 非目标

| 不做 | 原因 / 边界 |
|------|-------------|
| 改 14:57–15:00 的成交资格、成交价或收盘标记 | P1 / P4 未裁；本船只命名现状 |
| 给模拟环加新成交调度器、订单对象或事件总线 | 本仓是向量化扫描；不仿 LEBS / OMS |
| 改日线 `open_board` / `pending_exit` 时点，或改分钟 open / close 取价 | F-R6；会改 trades 与 NAV |
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

实施底必须是**届时最新 master**，另开 `feat/industry-align-refactor`；不得在本 docs 分支写代码。每片一个未来 commit，A → B → C；任一行为漂移立即停下回到 P\*。

### 7.1 切片 A：纯叶子 fill clock

**动作**

- 新建 `backtest/research/ashare_fill_clock.py`；只允许标准库（例如 `enum`）与整数常量，不 import pandas / numpy / qlib，也不 import 模拟环。
- 定义整数常量 `AM_OPEN / AM_CLOSE / PM_OPEN / PM_CLOSE / CLOSING_CALL_OPEN`；提供 `SessionPhase(str, Enum)`：`continuous` / `closing_call`，以及 `session_phase(hm)`。输入域只包括既有会话分钟；午休、开盘集合竞价与盘外分钟应显式拒绝（`ValueError`），不得默认为 `continuous`。
- `continuous` = 09:30–11:30、13:00–14:56；`closing_call` = `CLOSING_CALL_OPEN`（14:57）至 `PM_CLOSE`（15:00，含端点）。四个既有会话边界必须在切片 B 与 `ashare_bars` 对账，不能成为无人校验的第二份魔数。
- 提供 `FillPriceRule(str, Enum)`，值固定为 `daily_open_board_same_close`、`daily_pending_next_open`、`minute_gap_open`、`minute_trigger_bar_close`。
- 提供文档常量 `POOL_FILE_DAY_RULE = "filename_day_is_decision_and_buy_day"`。不解析 CSV、不产生订单、不调用 `simulate` / `scan_held_day`。
- 不从任何现有生产模块 import 新叶子；这一步只建立词汇，不接线。

**DoD**

- `ashare_fill_clock.py` 是唯一生产代码新增文件；AST import allowlist 只有标准库。
- `session_phase(14*60+57) == "closing_call"`，`session_phase(15*60) == "closing_call"`；合法连续竞价分钟只返回 `continuous`。
- `FillPriceRule` 只描述现有路径，没有 scheduler / fill / state mutation API。
- `rg -n "ashare_fill_clock" backtest/research --glob '!ashare_fill_clock.py'` 无结果；即新叶子未进入 simulate 热路径。
- 下述共用冻结文件相对实施 base 无 diff。

### 7.2 切片 B：data-free 契约测试

**动作**

- 新建 `tests/test_ashare_fill_clock.py`；只用整数、合成数组 / DataFrame 与现有纯函数，不读湖、不用真 symbol 行情。
- 新叶子的四个既有会话边界逐项对账 `ashare_bars.AM_OPEN / AM_CLOSE / PM_OPEN / PM_CLOSE`；14:57 仅新增“相位分界”，不是新的会话终点。
- 用行为断言把四个价格规则名映射到现有符号：日线走 `csv_daily_backtest.simulate`；分钟走 `csv_minute_backtest.scan_held_day_python`（或 `scan_held_day(..., use_numba=False)`）。不靠改生产代码建立映射。
- 直接检查叶子 import 只含标准库；`SIMULATE_HOT_PATH` 不变。若未来要求生产 import，先修订 plan 并同步围栏，不能在本片顺手接线。

**必须新增的测试名与断言**

| 测试名 | 机械断言 |
|--------|----------|
| `test_fill_clock_bounds_match_ashare_bars` | 新叶子 09:30 / 11:30 / 13:00 / 15:00 四边界与 `ashare_bars` 常量逐项相等 |
| `test_session_phase_boundaries_match_existing_session` | 09:24 不在会话；09:30 continuous；11:30 continuous；13:00 continuous；14:56 continuous；14:57 closing_call 且 `_in_session`；15:00 closing_call 且 `_in_session`；15:01 不在会话；盘外调用 `session_phase` 显式拒绝 |
| `test_pool_file_day_is_decision_and_buy_day` | 常量明确为文件名日 T；合成日线在 T 以 close 买入，合成分钟在 T 以 14:55（或既有 fallback）close 买入，均不是 T+1 开盘 |
| `test_daily_open_board_rule_uses_same_day_close` | 合成日线中 `open_board` 的 trade date 为触发日、price 为该日 close |
| `test_daily_pending_exit_rule_uses_next_session_open` | 非 same-bar reason 先写 pending，下一可卖 session 的 price 为 open |
| `test_minute_gap_stop_rule_uses_bar_open` | 首个 bar open 已破阈值时 price = open、reason = `stop_loss:gap_open` |
| `test_minute_touch_rule_uses_bar_close` | open 未破、该分钟 close 触价时 price = close、reason = `stop_loss:touch` |
| `test_fill_clock_leaf_imports_only_stdlib` | AST 中无 repo / 第三方 import；尤其无 qlib、`trade_fee_policy`、LEBS、simulate 模块 |

**DoD**

- 上表测试全绿；`tests/test_ashare_simulate_import_fence.py` 原测试与 `SIMULATE_HOT_PATH` 字节不动。
- 合成结果逐项等于 `FillPriceRule` 对应语义；没有通过改旧断言来“适配”新数字。
- 无湖路径、无真代码、无 snapshot 更新；下述共用冻结文件相对实施 base 无 diff。

### 7.3 切片 C：as-built 文档回写（无代码接线）

**动作**

- 只在 `docs/backtest/engine-ashare-correctness.md` 模块表后补一张「现状成交时钟」短表：决策日 T、会话相位、四条价格规则及代码符号。
- 明写 14:57–15:00 的 `closing_call` 是**现状标签**，仍在 `_in_session` / 分钟扫描内；不宣称已按交易所阶段修复。
- 不在模拟环外加计数器，也不向 `trades.csv` / summary 接线。若评审要求相位计数或产物列，回到 P2，停止本片。

**DoD**

- 该 commit 只改 `engine-ashare-correctness.md`；模块表新增 `ashare_fill_clock.py`，短表与切片 B 枚举值逐字一致。
- 文档继续声明读取器、内核、双账本、E-R1–E-R6 与价格数字未变。
- 不改 README / AGENTS / 旧 plan / HELP_LOCK；下述共用冻结文件相对实施 base 无 diff。

### A–C 共用冻结 diff 清单

实施 diff 不得触碰下列文件 / 符号；这里选择整文件冻结，强于只比行号：

| 文件 | 冻结符号 / 契约 |
|------|-----------------|
| `backtest/research/ashare_bars.py` | 四个会话常量、`_in_session`、`read_lake_minute_ohlc`、`load_minute_ohlc` |
| `backtest/research/ashare_session.py` | `t1_sellable`、涨跌停命中与买卖谓词 |
| `backtest/research/ashare_fees.py` | `BILATERAL_10BP` / `DEFAULT_SCHEDULE` |
| `backtest/research/csv_daily_backtest.py` | `simulate`、日线价格时点、`HELP_LOCK` |
| `backtest/research/csv_minute_backtest.py` | `_scan_held_day_numba_trail`、`scan_held_day_python`、`scan_held_day`、`simulate`、`HELP_LOCK` |
| `backtest/research/csv_minute_backtest_v7.py` | `Lot` / `Position` / `_sell_lots` 与已知 fail-open 分叉 |
| `backtest/research/csv_ledger.py` | `Position`、`rescale_position`、`execute_buy`、`_sell`、trades 字段 |
| `backtest/research/csv_strategy_books.py` | `daily_same_bar_prefixes` 与 BOOKS |
| `backtest/research/csv_artifacts.py` | `trades.csv` / summary 产物契约 |
| `tests/test_ashare_simulate_import_fence.py` | `SIMULATE_HOT_PATH` 与围栏断言 |

机械门：相对实施 base，上表文件的 `git diff --exit-code` 必须为 0。若任何文件必须改，当前 plan 即不再覆盖，停止并回到 P\*。

---

## 8. 每片的业内实践与不 vendoring 理由

| 切片 | 借鉴的成熟实践 | 开源工具 | 本仓只取什么 | 为什么不拷进本仓 |
|------|----------------|----------|----------------|------------------|
| **A · 命名叶子** | 策略信号、交易会话与网关撮合分层；连续竞价和集合竞价是不同会话语义 | **vn.py** | 用纯枚举给会话阶段命名，把“标签”与“能否成交”分开 | 本仓无网关 / OMS / CTP 需求；搬事件引擎会把向量化研究扩成 live 栈 |
| **B · 契约测试** | 决策 bar 与成交 bar 必须是显式选项；撮合频率、价格限制、滑点与费用是可测试配置 | **backtrader**（cheat-on-close 显式开关）、**RQAlpha / RQAlpha-Plus**（`price_limit` / `volume_limit` / 滑点 / 费用分项） | 只锁“当日 close / 次日 open / 分钟 open-or-close”是具名规则 | Cerebro 已退场；参与率、滑点、印花不在本切片，引入框架会重开价格与费率语义 |
| **C · as-built 表** | deal price / limit threshold 与 point-in-time instruments 均应显式、可审计 | **Microsoft Qlib** | 只取“成交规则是命名参数并有表可查” | PortAna / Exchange 已停用；不 import qlib，不采用其默认成交时点，也不把 PIT 选股逻辑塞进撮合核 |

这些是架构类比，不是兼容性目标。不开 vendor 目录，不复制实现，不新增框架依赖。

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
# 在 feat 分支记录实施 base 后执行；冻结文件必须无 diff
IMPLEMENTATION_BASE="$(git merge-base HEAD origin/master)"
git diff --exit-code "$IMPLEMENTATION_BASE"...HEAD -- \
  backtest/research/ashare_bars.py \
  backtest/research/ashare_session.py \
  backtest/research/ashare_fees.py \
  backtest/research/csv_daily_backtest.py \
  backtest/research/csv_minute_backtest.py \
  backtest/research/csv_minute_backtest_v7.py \
  backtest/research/csv_ledger.py \
  backtest/research/csv_strategy_books.py \
  backtest/research/csv_artifacts.py \
  tests/test_ashare_simulate_import_fence.py

# 叶子未接入生产模拟环；代码中不得新增盘符字面量
rg -n "ashare_fill_clock" backtest/research --glob '!ashare_fill_clock.py'
rg -n '[A-Za-z]:[\\\\/]' backtest/research/ashare_fill_clock.py tests/test_ashare_fill_clock.py
```

预期：前一条 `rg` 无输出；后一条也无输出。不得运行湖上回测；不得用真实行情补充合入门。文本文件统一 UTF-8 无 BOM、NUL=0。

---

## 10. 代码落点（`c44da87` 事实锚）

| 文件:行 / 符号 | 当前职责 | GO 后动作 |
|-----------------|----------|-----------|
| `docs/backtest/pool-csv-contract.md:11-12` `As-of` | 文件名日 T = 买入日 / 决策日 | 只读权威；不改 |
| `backtest/research/ashare_bars.py:27-28` `AM_OPEN/AM_CLOSE/PM_OPEN/PM_CLOSE` | 既有会话四边界 | 切片 B 对账；代码不改 |
| `backtest/research/ashare_bars.py:302-306` `_in_session` | 09:30–11:30、13:00–15:00（含端点） | 切片 B 断言 14:57 / 15:00 仍接受；代码不改 |
| `backtest/research/ashare_bars.py:328` `read_lake_minute_ohlc` | 冻结湖读取器 | 字节不动 |
| `backtest/research/ashare_session.py:29/34/39/73/77` | 涨跌停、T+1、买卖门谓词 | 不重开 E-R\*；代码不改 |
| `backtest/research/ashare_fees.py:53-55` `BILATERAL_10BP` / `DEFAULT_SCHEDULE` | 默认双边 10bp | 代码不改 |
| `backtest/research/csv_daily_backtest.py:204` `simulate`；`:329-333`；`:370-401` | pending 下一 open；open_board same close | 切片 B 从外部合成测试；代码不改 |
| `backtest/research/csv_daily_backtest.py:428-448` `_pool_quote_for` | 池日 T 取当日 close 并进入 `run_pool_buys_day` | 切片 B 从外部合成测试；代码不改 |
| `backtest/research/csv_strategy_books.py:118` `daily_same_bar_prefixes` | `open_board` 的 same-bar 名单 | 代码不改 |
| `backtest/research/csv_minute_backtest.py:150/232/323` | numba 内核 / Python 参考 / wrapper | 切片 B 调参考路径；三个符号不改 |
| `backtest/research/csv_minute_backtest.py:277-319` `scan_held_day_python` 分支 | gap 用 open；其余触价用 close | 切片 B 锁行为；代码不改 |
| `backtest/research/csv_minute_backtest.py:112/469-476/685-713` `BUY_HM` / `_buy_px` / `_pool_quote_for` | 池日 T 取当日 14:55 或既有 fallback close | 切片 B 从外部合成测试；代码不改 |
| `backtest/research/csv_minute_backtest.py:493` `simulate`；`:613-651` | 传入会话分钟并最终填单 | 不 import 新叶子；代码不改 |
| `backtest/research/csv_ledger.py:66/141/194/242` | 书账本与填单 / E-R6 参考价缩放 | 整文件不改 |
| `backtest/research/csv_minute_backtest_v7.py:61/69/223` | v7 独立账本 / 卖出 | 整文件不改 |
| `tests/test_ashare_simulate_import_fence.py:13-29` `SIMULATE_HOT_PATH` | #108 热路径白名单 | 字节不改；不扩大扫描范围 |
| `backtest/research/ashare_fill_clock.py`（拟新增） | 纯命名叶子 | 切片 A 新建 |
| `tests/test_ashare_fill_clock.py`（拟新增） | 时钟 / 价格映射 data-free 契约 | 切片 B 新建 |
| `docs/backtest/engine-ashare-correctness.md`（现有） | A 股 as-built SSOT | 切片 C 仅补短表；当前 docs PR 不改 |

---

## 11. 修订程序

1. 当前只合本 plan；保持状态「⏳ 待评审 / 待人裁 GO」。合 docs PR 不触发实施。
2. 后续按工作流评审并逐条裁 P1–P4；证据裁决，不以多数票替代语义选择。
3. 若 P1≠A、P2=B、P3=B 或 P4=B，停止原切片，先修订范围、冻结面与 DoD；不得沿用“行为不变”的风险档直接编码。
4. 全部人裁后回写选项与 GO commit hash，并准备独立 handoff；GO 前不得创建实现提交。
5. 从**届时 master** 新开 `feat/industry-align-refactor`，按 A / B / C 分 commit。当前 docs 分支不得承载 Python 或测试。
6. 只运行 §9 data-free 门；遇任何成交价、股数、reason、NAV、产物 schema 或冻结文件 diff，立即 STOP，新增 P\*。
7. 实施 PR 合入后，才将本 plan 状态回写为「✅ 已实施（PR #N）」；不得提前宣称落地。

---

## 12. Changelog

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.1 | 2026-09-18 | docs-only 首版：唯一提案为 fill clock 显式化；P1–P4 待裁；切片 A–C 均要求行为不变 |
