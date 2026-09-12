<!-- agent=codex cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.10-fd3934a\node.EXE C:\Users\Thinkpad\AppData\Roaming\nvm\v24.19.0\node_modules\@openai\codex\bin\codex.js exec --ephemeral 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-unify-csv-strategies-1-8-2026-09-12.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-12/plan-unify-csv-strategies-1-8-2026-09-12/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本仓第一方回测是 **向量化 CSV**（日线/分钟）+ path-SSOT 只读行情。Cerebro / Rolling 观察退役。无实盘、无 QMT 下载、无 Redis 流。引擎分工见 `docs/backtest/engine-positioning-ssot.md`。把握不准可读代码或做实验，以事实为准。

【本仓必查盲区（评审必须逐条核对）】
- **T+1 / 隔日成交**：买入日 `n_days=0` 能否卖出？日线止盈是当日收盘还是 `pending_exit` 次日开？有无用到未来 bar？
- **复权口径**：向量化成交与均线必须同一套 `adjust_type=none`。禁止把筹码默认 front 套到 CSV 书上。
- **盈筹率尺度**：本仓筹码 `cyqk` 是 0–1。本 plan 若声明不适用，禁止把盈筹带进 1–8 书。
- **涨跌停 / 停牌**：涨停禁买可卖、跌停禁卖；`limit_pct` 档位与北交/ST 是否建模必须写清。
- **包边界**：研究 CLI 走 `backtest/research/`。不要把 LEBS / MockQMT / `presets.py` 当本仓向量化实现。Cerebro 仅考古。

【裁决原则（重要）】
- 视自己与其他评审者为同行专家，**参考学习、互相验证、取长补短**：结论交叉核对、补彼此盲区，而非单纯挑错。
- **事实类断言**（函数位置 / 行为 / 数值等可验证项）→ **以代码与实验为准**：读代码取证，把握不准时跑最小实验，不靠票数下结论。
- **经验/取舍类断言**（该不该这样做、风险量级、更稳的写法）→ **以业内 A 股量化惯例与成熟开源实践为准**（backtrader / 本仓 Cerebro）。
- **SSOT 一致性检查**：对照 `README.md` 布局、`common/infra/data_root.py` path-SSOT、`backtest/chip_indicator.py` 筹码包装。勿引用本仓不存在的实盘/LEBS 文档当硬 SSOT。
- **★ 安全阀/超时/并发类设计，必须跑最小实验验证行为**（不只读代码！）：timeout / budget / safety-valve / circuit-breaker / 并发锁 / 异步 / fallback / 重试——这些 bug 藏在 stdlib/框架行为里（如 `ThreadPoolExecutor.__exit__`→`shutdown(wait=True)` 让超时从不生效），**读代码看不出来**。实验格式：构造 slow fn + tight budget → 测调用方**何时返回**（`time.monotonic` 对比 budget_s vs 实际）。2026-07-04 实测：option-X budget docstring 宣称 "releases caller" 但实际 8s 才返（非 1s budget）——**docstring 不可信，实验为准**。**实验结论须附可复现脚本 + 完整原始输出**（含进程 pid/存活检查等），与官方文档/CPython 源码矛盾的结论标注「建议主持裁/下游复核」。2026-07-16 教训：r3 kimi 实验「subprocess.run(timeout) 不杀子进程」结论错，r4 qoder 引源码 + 主持裁亲自实验（child TERMINATED）才纠正——下游 incorporate 实验断言须亲自复现。

【输出格式】
按严重度分级，每条尽量带 file:line 证据：
- 🔴 必须修（事实错误 / 会误导实现 / 逻辑矛盾）
- 🟡 应修（设计缺口 / 风险）
- 🟢 可选（nice-to-have）
- ✅ 做对的地方（保留）
末尾给一句总评 + 是否可进实现。

【你的评审侧重】优先审**实现可操作性**：函数名/文件位置/调用链/API 契约——程序员能否照此编码？哪里会卡住？哪些 import 是私有的需 wrapper？ <prompt> -->
## 评审：`docs/backtest/plan-unify-csv-strategies-1-8-2026-09-12.md` v1.1（侧重实现可操作性）

**交叉核对状态**：`_parallel/{claude,codex,cursor-auto,cursor-kimi-k3-high}/*.md` 当前只有 `<prompt>` 头（321–5423 B），**无已完成意见可引**（`_parallel/cursor-auto/cursor-auto.md` 全文仅 cmd-prefix 注释）。本评审独立完成，未等待。
**写盘声明**：遵守硬约束，未创建/修改/删除任何文件；本轮只做读操作与两个无写盘实验（`python -B`）。请主持把本文收录进本槽。

---

### 🔴 必须修

**R1（实施阻断）策略 4 的卖侧钩子没有数据通路，U-R7 按现结构写不出来。**
`take_profit(px, cost, peak, n_days)` 看不见历史收盘序列，而 hooks 只在 simulate 入口定一次：

```
csv_strategy_books.py:70   hooks = dict(book.apply(**kwargs))
csv_strategy_books.py:75   if hooks.get("take_profit") is None: raise ...
csv_daily_backtest.py:450  reason = take_profit(close, pos.cost, pos.peak, n_days)
```

`apply_csv_strategy` 调用点（`csv_daily_backtest.py:385-393`）只传 stop_pct/take_profit/record_params/profit_base/tiers/tier_default，**没有 bars / day / closes**。U-R7 又要求"均线唯一输入 = 引擎已持有的 none 日线 `index < day`"且禁止引入 `chip_indicator` / 新引擎。若给 `take_profit` 追加实参，现网闭包 `_tp(px, cost, peak, n_days=1)`（`csv_strategy_books.py:199`）与 `strategy8_rules.take_profit_reason` 会 TypeError 或参数错位——这是 6/8 热路径。
**修**：切片 A 就把契约钉成二者之一并写进 §4：(a) 调用点扩为 `take_profit(close, cost, peak, n_days, ctx)`，`ctx` 含 `code/day/closes_before_day`，引擎构造 ctx（需同时改 6/8 两个闭包与 v8 函数签名，属热路径，必须在引擎切片做）；(b) 保留 4 参，引擎在每日循环前调 `hooks["prepare"](code, day, closes)` 注入历史。推荐 (a)（(b) 引入跨日可变状态，难测）。

**R2（事实错误）U-R10 的"行为字节级不变"对 `_limit_prices` 不成立，已实测。**
v7 是 float 乘后 HALF_UP（`csv_minute_backtest_v7.py:217-219` + `:78-79`），日线/分钟共用的是 Decimal 直乘路径（`csv_daily_backtest.py:275-285`）。399,802 组 (prev_close 1.00–2000.00 × {10%,20%}) 中 **1073 组不同**，例：`prev=1.65, pct=0.10 → v7 跌停 1.48 vs Decimal 1.49`（脚本+原始输出见附录 A，`D:\anaconda3\envs\vanna312\python.exe -B`）。
`_limit_prices` 直接决定 v7 的涨/跌停拦截（`csv_minute_backtest_v7.py:219` → 撮合），单函数搬家即 silently 改 v7 阈值，正是 U-R12 自己声明要避免的那类改动。
**修**：市场层保留两个具名函数（`limit_prices_decimal` / `limit_prices_float_fen`），或 v7 只搬 `round_fen`/`limit_pct`、本地保留 `_limit_prices`；否则把 U-R10 改成"接受 v7 阈值变更"并补 v7 回归基线。**同时**：`docs/backtest/plan-strategy7-turtle-csv-minute-2026-09-11.md:102` 的 v7 import allowlist（含 `_limit_prices`/`round_fen`）必须同步改，U-R28 只提了 README/SSOT/AGENTS 书单。

**R3（规格缺前提，会误导实现）1/2 的止盈缺 `px ≥ cost` 前置，会与化石反向。**
U-R4 只写"`peak>cost` 才评"。日线在 `low > cost×0.98` 但 `close = cost×0.99` 时，止损不触发，收盘回撤 = (peak−0.99cost)/(peak−cost) 仍可能 ≥0.5 → 以 `profit_take:drawdown` 卖出**亏损单**。化石不会：`ProfitStrategy.py:130-134` 先 `current_price < cost` 早退；本仓既有 v6 也显式守卫：

```
strategy6_rules.py:99    if float(px) < float(cost):
strategy6_rules.py:100       return False
```

**修**：U-R4/U-R5 明写 `px >= cost`（或 `pnl > 0`，对齐 `trade_decision/presets.py:485`/`:522`）；否则 U-R22 的 `profit_take` 桶会装进亏损离场，与"化石对照货币"自相矛盾。

**R4（规格缺键，实施者会卡住）1–5 的"抄哪一份源"没定，仓内两份源在 v3 上直接互斥。**
U-R14 只说"研究规则与 presets 不对齐承诺"，但没说唯一的 port 源是 `backtest/ProfitStrategy.py` 还是 `trade_decision/presets.py`（后者是与 1.3 共享的卖核，见 `tests/test_profit_strategy_preset_parity.py`）。冲突是硬的：
- 顺序：化石 v3 **先止损再保留**（`ProfitStrategy.py:255` → `:263-309`）；presets v3 **先保留/开板再止损**（`presets.py:564-569` → `:593-596`）。
- 覆盖：presets v3 内含 force_sell(14:50)（`presets.py:570-592`）与 presets v5 的 `limit_up_reserve_enabled`/`stop_loss_pct` 开关（`presets.py:655-675`），plan 的 3/5 都没有。
- reason 词表：化石 `profit_take:drawdown`（`:143`）、presets `bucket_preset:versionN:...`（`:484/:523/:569/:695`）。
**修**：§2 顶部加一行"port 源 = `backtest/ProfitStrategy.py::StrategyN`（Cerebro 化石）；presets.py 仅作对照，差异入 HELP_LOCK"，并把 U-R6 的"顺序与化石对齐"注明该化石即 ProfitStrategy。这是本 plan 唯一未回答的"程序员第一步读哪份代码"。

---

### 🟡 应修

**R5 新 kwargs 的透传链没列全，`run(**)` 会 TypeError。** U-R2 允许 `buy_gate`/`force_hm`，但 `run()`/`simulate()` 现签名无这两参，而 CLI 走 `run(**csv_run_kwargs_from_args(args))`（`csv_daily_backtest.py:900`、`:544-559`、`:363-379`）。§3 只在 csv_daily 行写了 `buy_gate`。需补"引擎 API 契约表"：`run/simulate/run_kwargs` 各新增哪些 kwarg、默认值、谁负责默认恒真（建议引擎 `hooks.get("buy_gate")`，`apply_csv_strategy` 不强制）。

**R6 v3 日线第三钟缺 T+1 前置与插入点。** U-R19/U-R20 未写 `n_days >= 1`。日线循环里 `n_days` 一算出来（`csv_daily_backtest.py:420`）就插分支，会把买入日收盘当卖点。必须写"插在 `if n_days >= 1:`（`:429`）块内、止损之后"，并用 `hooks["book"] == "v3"` 判定（已有：`csv_strategy_books.py:73` `hooks["book"] = book.tag`），不要用 `strategy` 字符串。

**R7 `scan_held_day` 返回契约未钉死。** v3 的 `reserved` 需回写 `pos`，但现返回 5 元组（`csv_minute_backtest.py:411/:444`），v6/v8 两个单测共 13 处按 5 元解包（`tests/test_csv_minute_backtest.py:18`、`tests/test_csv_minute_backtest_v8.py:19/:42/...`）。plan 只说"可扩签名"。建议：返回契约改为小 dataclass（或 6 元组 + 一次性改全部调用点），并写明 `pos.reserved = new_reserved` 的回写责任在 `csv_minute_backtest.py:583-584` 旁。

**R8 `Position` 只有一份，"日线/分钟各加"与事实不符。** `csv_minute_backtest.py` 无 `class Position`/`class SimState`（`:33-60` 全从日线 import；`:563-584` 直接用 `pos.entry_idx/peak/peak_hm`）。改一处 `csv_daily_backtest.py:121-130` 即两引擎生效；照字面在分钟模块再建一份会分叉并违反"不改 6/8 Position"。

**R9 `load_pool_days` 旧签名必须留壳。** U-R24 新函数是 `load_pool_day_map(pool_dir, start, end, ...)`，参数序与现 `load_pool_days(start, end, pool_dir=None)`（`csv_daily_backtest.py:288-289`）不同；单测直接调 `sim.load_pool_days("20251103","20251103", pool_dir=tmp_path)`（`tests/test_csv_daily_backtest.py:526`），分钟 `run()` 也调（`csv_minute_backtest.py:720`）。plan 需写"保留旧签名薄壳委托新函数"。

**R10 `summarize` 与 stats 桶的隐雷。** `csv_daily_backtest.py:726` 的 `elif st.stats.get("sell_book") == "v6" or "trail_t1" in st.stats:` 会把任何设了 `trail_t1` 的新书拉进 v6 格式化分支，对 `stop_pct` 做 `:.0%`（4/5 为 `None` → TypeError）；`:735/:747` 是直接下标取值。U-R22 需附：新桶加入 `SimState.stats` 默认（`:142-164`）、新书禁设 `trail_t1`、summarize 改成严格按 book 分支。

**R11 `--stop-pct/--profit-base/--trail-t*` 对 1–5 静默失效。** `add_csv_strategy_args` 无条件注册这些开关（`csv_strategy_books.py:104-147`），而 U-R2/§3 禁止 1–5 走 `strategy6_kwargs_from_args`。用户对 v1 传 `--stop-pct 0.03` 会无提示无效。建议 book 的 `run_kwargs` 显式消费覆盖，或对非 6/8 书传参即 `SystemExit`。

**R12 ≥10 交易日预载的**日历源**没命名。** U-R21 说"对齐策略 7 F-R1（实现 11）"，但 F-R1 的 11 来自**指数日线湖**（`csv_minute_backtest_v7.py:419-422`：`preload = [d for d in sessions if d < start][-11:]`，不足即抛错），本仓 `warmup_start` 是**日历日**减法（`csv_daily_backtest.py:216-217`）。`pandas-market-calendars>=5.0` 在 `requirements.txt` 且可导入，但用它算 preload 与"对齐 7"不是一回事。需钉死来源（指数日线湖 / pmc SSE / bars 自身日期）+ 不足 10 根即该票 `skip_sma_warmup` 的判定口径。

**R13 §6 验收命令漏掉 v6/v8 热路径单测。** `tests/test_csv_daily_backtest_v8.py`、`tests/test_csv_minute_backtest_v8.py` 是 pending/涨跌停/`sell_trail` 桶的唯一回归（U-R3/U-R19/U-R22 直接改这些行为），命令里没有；`test_ma_chip_edge_strategy.py` 在 U-R12 再导出下也值得跑。命令用 `^` 续行是 cmd 语法，本机 shell 为 PowerShell（应为反引号或单行）。

**R14 U-R22"前缀家族"的对端未命名，且 `open_board` 在化石里没有机器可读前缀。** 化石 open-board 原因串是中文自由文本：

```
ProfitStrategy.py:306   return (
ProfitStrategy.py:307       True,
ProfitStrategy.py:308       f"开盘10分钟后开板，卖出，盈利{profit_ratio * 100:.2f}%",
```

既非 `open_board` 也非 `profit_take`。须写明"对照对象 = `backtest/ProfitStrategy.py`"，并把 `open_board`（以及 `ma_signal:MA5` 相对化石 `ma_signal 价格...`、`force_sell:time` 相对化石 `force_sell time ...`，`:361/:513`）标为"新 token/同族但不逐字"。

---

### 🟢 可选

- **R15** HELP_LOCK 建议补两条声明：v3 日线存在**两个成交钟**（开板当日收盘 vs +20% 次日开）；v1/v2/v5 的 `gap_down_pct` 未建模（`presets.py:429-451` 默认 0=关闭，闭着无差，写清免后人误认为已实现）。
- **R16** `csv_daily_backtest.py:565` 的 `SystemExit("no pool CSVs ... under stock_pool/")` 在 `--pool-dir` 生效后文案要带实际目录。
- **R17** §4 注释里的"`buy_gate` 默认恒真"建议提升为 U-R2 正文，避免实现者在 `apply_csv_strategy` 里加 `raise`（现 `:75-78` 对 take_profit/record_params 就是硬 raise，容易被顺手抄到 buy_gate）。
- **R18** `backtest_main_full.py` 全部逻辑在 `if __name__ == "__main__"` 内（`:167`）且 import 期就 `os.makedirs("logs")`（`:33`）；化石门放在 `parse_args` 之后即可（`:176` 后，`load_stock_data` 之前），但 import 期副作用无法避免，建议在 HELP/文档写明。

---

### ✅ 做对的地方（保留）

- **U-R3 的位置与语义完全正确**：`trigger = pos.cost * (1.0 - stop_pct)`（`csv_daily_backtest.py:430`；`scan_held_day` `:413`、`:433`）在 `stop_pct=None` 时确实 TypeError；"仅 `isinstance(float) and 0<x<1` 才算止损"与 `hit_limit_up` 的 `LIMIT_EPS`（`:81`）设计同源，"禁 `or 0`/`or 1.0`"是对的。
- **U-R4/U-R5/U-R6/U-R7/U-R8 的数值逐条与化石吻合**：2%+50%（`ProfitStrategy.py:112-113`）、`{1:0.50,2:0.40,3:0.30,4:0.20,5:0.10}`（`:163`）、4%+20%（`:737`）、MA10/MA5（`:338-339`）、14:50/`time_only`（`:397-399`）。
- **U-R12 的 limit_pct 表正确**：`300/301/688=0.20 else 0.10`（`ma_chip_edge_backtest.py:92-96`），"不是 8%"的纠偏准确；"再导出"可实施。
- **复权与筹码边界核对通过**：成交与日线同吃 `dividend_type=none`（`csv_daily_backtest.py:340`、`csv_minute_backtest.py:323`），1–5 书不引 `cyqk`/`chip_indicator` 与代码事实一致（CSV 引擎无该引用）；U-R7 禁 `chip_indicator`/`front` 正确。
- **T+1/隔日成交与 plan 自洽**：pending 次日开盘成交（`csv_daily_backtest.py:422-426`）、买入日 `n_days=0` 不进任何卖分支（`:422`/`:429`）、分钟 `can_sell=(n_days >= 1)`（`:572` + `scan_held_day:418-420`）→ U-R8"日线不做强制卖/买入日不挂 pending"、U-R18"T+0 不卖/T+1 09:31 不强制"成立。无未来 bar 引入的路径是合格的（`peak` 用当日 high、决策用当日 close、成交用次日 open 已在 HELP_LOCK `:99-104` 声明）。
- **U-R24/U-R10 对 7 的保护方向正确**：v7 空 CSV 仍进 map（`csv_minute_backtest_v7.py:463` `result[day] = parse_pool_csv(path)`），指数日历由指数日线决定（`:419-422`），"禁 `pool_dir=None` 回落"与 7-plan F-R5 一致。
- **U-R23 实施序识别准**：`tests/test_csv_strategy_books.py:21` 硬断言 `("version6","version8")`，names 元组确实必须跟 register 走；`_sell` 只有一份（`csv_daily_backtest.py:665`，分钟 `:58` import）→ U-R22 的统计桶改一处即覆盖两引擎，这是对现有基础的合理复用。

---

### 盲区逐条核对

| 项 | 结论 | 证据 |
|---|---|---|
| T+1 / 隔日成交 | ✅ 事实成立；**唯 R6**：U-R19 新分支未写 `n_days>=1` | `csv_daily_backtest.py:422/429` |
| 复权口径 | ✅ 成交/均线可同源 none | `csv_daily_backtest.py:340`、`csv_minute_backtest.py:323` |
| 盈筹率尺度 | ✅ 未带入 1–8；CSV 引擎无 cyqk/chip 引用 | `cssv` 引擎 grep 0 命中 |
| 涨跌停/停牌 | ✅ 涨停禁买可卖/跌停禁卖实现齐全；档位表准确、北交/ST 已声明不建模（R2 才是搬家风险） | `csv_daily_backtest.py:255-285`、U-R12 |
| 包边界 | ✅ 全落 `backtest/research/`；`presets.py` 只读；Cerebro 仅 E 切片 | `csv_strategy_books.py:104`、§3 |
| SSOT 一致 | ✅ 与 `engine-positioning-ssot.md:41/:45` 不冲突；**需补** v7 plan allowlist（R2） | `plan-strategy7-...md:102` |

**主持裁 5 问速答**：1) U-R8 与 B′ 自洽（B′ 只测"+2%→次日开"、U-R25 禁"日线天天 force"，与 U-R8 一致）。2) U-R19 不会改 6/8 pending，**前提**是按 `hooks["book"]=="v3"` 判据实现并放在 `n_days>=1` 内（见 R6）。3) U-R24 分叉对 7 够用，但单测要断言"全空 CSV → map 有键、symbol 集为空"，且指数日历来源不变。4) `scan_held_day` 契约未钉死（R7），6/8 回归可测但需改 13 处解包点。5) 新 🔴 四条：R1/R2/R3/R4（均非对抗已吸收项，其中 R2 带实验、R4 为跨文档互斥）。

---

### 附录 A：`_limit_prices` 等价性最小实验（可复现）

```python
# D:\anaconda3\envs\vanna312\python.exe -B -c '<本脚本>'   # 无写盘
from decimal import Decimal, ROUND_HALF_UP
v7    = lambda prev, pct: tuple(float(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                                for v in (prev*(1+pct), prev*(1-pct)))
def daily(prev, pct):
    p = Decimal(str(prev)); s = Decimal("0.01")
    return (float((p*(1+Decimal(str(pct)))).quantize(s, rounding=ROUND_HALF_UP)),
            float((p*(1-Decimal(str(pct)))).quantize(s, rounding=ROUND_HALF_UP)))
bad = []; n = 0
for cents in range(100, 200001):
    prev = cents/100.0
    for pct in (0.10, 0.20):
        n += 1
        if v7(prev, pct) != daily(prev, pct): bad.append((prev, pct, v7(prev, pct), daily(prev, pct)))
print("compared", n, "mismatches", len(bad)); [print(r) for r in bad[:5]]
```

原始输出（两次运行一致；`v7()`/`daily()` 分别照抄 `csv_minute_backtest_v7.py:217-219` 与 `csv_daily_backtest.py:275-285`）：

```
python 3.12.13 D:\anaconda3\envs\vanna312\python.exe
compared 399802 mismatches 1073
(1.65, 0.1, (1.82, 1.48), (1.82, 1.49))
(4.35, 0.1, (4.79, 3.91), (4.79, 3.92))
(5.35, 0.1, (5.89, 4.81), (5.89, 4.82))
(7.85, 0.1, (8.64, 7.06), (8.64, 7.07))
(8.45, 0.1, (9.2, 7.6), (9.2, 7.61))
```

结论与 CPython/官方文档无矛盾（纯 Decimal/float 语义），无需下游复核；但 **R2 的修复选择建议主持裁**（保 v7 字节级不变 vs 统一到 Decimal 并接受一次阈值变更）。

---

### 总评

v1.1 的"引擎时钟 vs 四参钩子"拆分方向正确、数值对齐化石的功课扎实，A→E 切片与实施序（先引擎短接、后 register、names 最后）是本 plan 最强的部分；但它把"钩子能接完 3/4/5"的信心中留了一个真空——**策略 4 的卖侧在现有 hooks 契约下无数据通路（R1）**，且 1–5 的 port 源未指定（R4），加上两处可证伪的断言（R2 字节级不变、R3 止盈前提缺失），照此编码会在第一周就撞墙或悄悄跑出与化石不同的票。这四条里 R3/R4 是文档改动，R1/R2 需要一次契约级决策——都属于动手前就能定完的事。

**建议：不可直接进实现；清掉 R1–R4 后（R1 需主持选定 (a)/(b)、R2 需决定 v7 是否接受阈值变更）即可开工，🟡 可随切片消化。**
