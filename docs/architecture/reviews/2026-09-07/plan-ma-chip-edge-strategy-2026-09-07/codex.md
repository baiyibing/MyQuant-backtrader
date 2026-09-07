<!-- agent=codex cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.02-c22c1a3\node.EXE C:\Users\Thinkpad\AppData\Roaming\nvm\v24.19.0\node_modules\@openai\codex\bin\codex.js exec --ephemeral 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本仓是 **Cerebro / path-SSOT 只读回测叉**：无实盘、无 QMT 下载、无 Redis 流。把握不准可读代码或做实验，以事实为准。

【本仓必查盲区（评审必须逐条核对）】
- **T+1 / 隔日成交**：买入信号能否在当日卖出？卖出是收盘价还是次日开盘？有无用到未来 bar？
- **复权口径**：均线与盈筹率是否同一套 `adjust_type`（本仓筹码默认 front）？
- **盈筹率尺度**：`cyqk_c` 是 0–1 还是 0–100？70% 阈值有无单位错误？
- **周均线定义**：20 周均线是周线 resample 后 SMA(20)，还是 100 日近似？
- **包边界**：算法走 `oskh_factors` / `qlib_cost`，Cerebro 包装走 `backtest/`，研究 CLI 走 `backtest/research/`。

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


[runner] codex TIMEOUT after 900s (partial output above, if any)
[stderr-partial]
Reading additional input from stdin...
OpenAI Codex v0.153.4
--------
workdir: E:\PycharmProjects\MyQuant-backtrader
model: deepseek-v4-flash
provider: custom
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR]
reasoning effort: high
reasoning summaries: none
session id: 01a07ad1-d12f-7cc0-9c49-ea467b4633c1
--------
user
你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本仓是 **Cerebro / path-SSOT 只读回测叉**：无实盘、无 QMT 下载、无 Redis 流。把握不准可读代码或做实验，以事实为准。

【本仓必查盲区（评审必须逐条核对）】
- **T+1 / 隔日成交**：买入信号能否在当日卖出？卖出是收盘价还是次日开盘？有无用到未来 bar？
- **复权口径**：均线与盈筹率是否同一套 `adjust_type`（本仓筹码默认 front）？
- **盈筹率尺度**：`cyqk_c` 是 0–1 还是 0–100？70% 阈值有无单位错误？
- **周均线定义**：20 周均线是周线 resample 后 SMA(20)，还是 100 日近似？
- **包边界**：算法走 `oskh_factors` / `qlib_cost`，Cerebro 包装走 `backtest/`，研究 CLI 走 `backtest/research/`。

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

【你的评审侧重】优先审**实现可操作性**：函数名/文件位置/调用链/API 契约——程序员能否照此编码？哪里会卡住？哪些 import 是私有的需 wrapper？
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md"' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1112ms:
# Plan：均线 + 盈筹率边缘买入试验（v2）

> **状态**：已吸收 2026-09-07 三路对抗；待 fan-out / merge-consensus  
> **日期**：2026-09-07  
> **范围**：Cerebro 日线研究回测。不做实盘。价格/量约束后续单开。  
> **对抗回填**：`docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/review-by-cursor.md`

## 0. TL;DR

研究 CLI：T 日开盘买入，当且仅当 **T-1 四条件全真且可计算**，且 **T-2 四条件全可计算但非全真**。持有：买入日收盘 ≤ T-1 收盘则次日开盘出；否则拿到收盘 < SMA5 的次日开盘出。随机 10 深主板 + 10 沪主板 + 10 创业板，统计窗 2024-01-01 至今。

盈筹率 **不** 直接读 `ChipDistribution.cyqk_c[0]`（窗口不含当日、股本无 as_of）。策略内对 **含 T-1 的 80 日窗口** 调 `chip_algorithm` / `oskh_factors.chip`，`as_of_date=T-1`。

## 1. 背景

用户口头规则（2026-09-07）：

1. **买入（T 日开盘）**：t-1 价格 > 20 日均线 and > 20 周均线 and > 60 日均线 and 盈筹率 > 70%；t-2 **不同时**满足。
2. **持有**：T 收盘 < t-1 价格 → T+1 开盘卖；T 收盘 > T-1 收盘 → 持有到收盘 < 5 日均线。
3. 先 30 只试验；后续再加价格/量约束。

不改 `backtest_main_full.py` / `rolling_investment_strategy.py`。

## 2. 锁定口径

| 项 | 锁定 |
|----|------|
| 决策时点 | 在 **日 D 的 next()**（D 收盘已知）算 `cond[D]`；若边缘成立则 `buy(exectype=Open)` → 成交在 **D+1 开盘**。此时 T=D+1，T-1=D，T-2=D-1 |
| 价格 | 日线 `period=1d` **`adjust_type=front`**。禁止 `load_single_stock_data`（默认 1m + none） |
| 比均线 | `close[0] > sma20[0]` 在日 D **仅当** SMA 的输入止于 D（即 `bt.SMA` 的 `[0]` 在 D 的 next() 正好含 D，这是对的）。**禁止在日 T 用 `sma[0]` 去判断 T-1**（那会含 T）。实现只在 D 收盘算 cond，不要在 T 开盘用错一期 |
| 20 周均线 | 按 `oskh_factors.weekly_macd_divergence._daily_to_weekly` 同构：`W-FRI` + `_last_day=max`。asof 键 = `_last_day`，**只 backward** 到 D。未完成周（`_last_day` > D）丢弃。不改 `oskh_factors`（复制 10 行到 research 文件） |
| 盈筹率 | 阈值 **0.70**（`get_cyqk_c` 为 0–1）。窗口 = 截至 D 的最近 80 根 **含 D** 的 OHLC；`adapt_columns(..., stock_code=, as_of_date=D)`；再 `daily_chip_distribution` + `ChipFactor(close_D, dist)`。NaN → 该日 cond 不可计算 |
| 边缘 | `cond[D] is True` 且 `cond[D-1] is False`。**两边都必须有限**（四输入皆非 NaN）。T-2/D-1 为 NaN ≠ 边缘 |
| 等号 | 买入日收盘 **≤** T-1 收盘 → 次日开盘卖（fail-closed） |
| MA5 离场 | 持有期日 H：`close[0] < sma5[0]` → `sell(exectype=Open)` 次日开。买入日 **禁止任何卖单** |
| T+1 | 买入日不挂卖；卖出一律下一根 Open。不接 `TPlus1QueueManager`，用策略状态机保证 |
| 仓位 | 单票最多 1 笔；已持仓忽略新开 |
| 涨跌停 / 停牌 | **不成交、不进净值**，写入 `events.csv`（涨停开买 / 跌停开卖 / volume=0）。创业板 20%、主板 10%、ST 5%；昨收用 **none 昨收** 若拿得到，否则本轮用 front 昨收并在 summary 声明偏差 |
| 费用 | 自写 `bt.CommInfoBase`：佣金万 0.5、最低 5 元、卖出印花税 0.05%。不把 `trade_fee_policy` 当 Cerebro 插件 |
| 抽样 | seed=`20240907`；代码池 = hive `period=1d/dividend_type=front` ∩ `float_shares.parquet`（`resolve_source_parquet`，禁止 `from oskh_data.float_shares import`）。每板抽 10，预热不足则重抽，报告实际只数 |
| 板块 | 沪主板 `60xxxx.SH` 排除 `688`；深主板 `000/001/002/003*.SZ`；创业板 `300/301*.SZ`。不要抄 `chip_backtest` 的 `60/68` 前缀 |
| 区间 | 统计 2024-01-01 → `--end`（默认今天）；加载从 **2022-07-01** |
| 组合 | **单票独立 Cerebro + 等额本金**（新模式，不同于 `chip_selection_backtest` 多 feed 共享资金）。事后等权拼净值 |
| 文件 | `backtest/research/ma_chip_edge_backtest.py`（CLI + Strategy，不放根目录） |
| 输出 | `backtest_output/ma_chip_edge_{seed}_{end}/`：`universe.csv` `trades.csv` `events.csv` `per_stock_stats.csv` `summary.md` |

## 3. 方案取舍

### 3.1 可行性

口径按 §2 补齐后可行。`ChipDistribution` warmup 单测只证明 NaN≠0，**不**证明本策略。周线 asof 按 `_daily_to_weekly` 本地复制。次新不够 20 周则重抽。

### 3.2 必要性

必须单独 research CLI。策略放 CLI 同文件，不进 `backtest/` 根。不并入 rolling。

对抗 dissent 主张「先全市场扫描、先改 Indicator」：**驳回**。用户本轮要的是可下单的试验框架 + 30 只表现；全市场与 Indicator 修补单开。

### 3.3 优缺点

- 优点：时间因果锁死；单测可覆盖边缘 / T+1 / MA5 / T-2 NaN。
- 缺点：30 只不能代表全市场；`cyqk_c>0.70` 在仓内文档是抛压区，本轮只验证框架。
- `summary.md` **禁止**写「策略有效 / 因子有效」，只报触发数、收益、回撤、skip 事件数。

## 4. 实施步骤

1. `backtest/research/ma_chip_edge_backtest.py`：抽样、加载、策略、报告。
2. `tests/test_ma_chip_edge_strategy.py`（合成数据，不依赖 F 盘）：
   - D 满足、D-1 不满足且有限 → D+1 开盘买
   - D 与 D-1 都满足 → 不买
   - D-1 为 NaN → 不买
   - 买入日收阴/收平 → 次日开盘卖
   - 买入日收阳 → 直到收盘 < SMA5 的次日开盘卖
   - 买入日 next() 内不得卖
3. 跑 30 只试验。

```powershell
D:\anaconda3\envs\vanna312\python.exe backtest/research/ma_chip_edge_backtest.py --seed 20240907 --start 20240101
```

## 5. 本轮不做

- 价格约束、量约束
- 改 `ChipDistribution` / `oskh_factors` / `qlib_cost`
- 全市场扫描、分钟线、实盘、LEBS
- 精细涨跌停撮合（只 skip）

## 6. 验证

- 单测全绿。
- 30 只 exit 0；打印每板只数、触发买入数、等权收益、skip 数。
- `scripts/gates/verify_oskh_data_contract.py` 绿。

## 7. 关闭条件

- §2 出现在 CLI `--help`。
- 同一 seed 的 `universe.csv` 可复现。
- fan-out 无新架构 🔴，或剩余 🔴 已降为 §5。


exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/review-by-cursor.md" -ErrorAction SilentlyContinue' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'rg --files backtest common oskh_factors oskh_data qlib_cost scripts tests | head -200' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1273ms:
# cursor 对抗综合（host，不计独立票）

评审对象：`docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md` v1  
三路：dissent-steelman / domain-safety / pattern-evidence（2026-09-07）

## 1. 主笔让步（立场修正）

1. **不把 `ChipDistribution[0]` 当 T-1 盈筹率 SSOT。** Indicator 窗口不含当日 OHLC、却用 `close[0]`；且 `adapt_columns` 不传 `as_of_date` 会吃最新股本。v2 改为策略内用含 T-1 的 80 日窗口 + `as_of_date=T-1`。
2. **策略文件不放 `backtest/` 根。** 与现有 research CLI 内嵌 Strategy 的模式对齐。
3. **T-2 必须有限。** NaN 不得当「边缘成立」。
4. **均线只用 `[-1]` 已完成值。** 禁止 `sma[0]`（含当日）。
5. **涨跌停/停牌成交不进净值。** 只记事件。
6. **费用不假装 `trade_fee_policy` 即插 Cerebro。** 自写买卖不对称佣金+印花+最低 5 元，或文档化 `setcommission` 占位。

**未让步：** 用户明确要 30 只抽样试验 + 基本策略框架。不改为「先全市场扫描、不写策略」。不并入 `rolling_investment_strategy`。盈筹率方向本轮仍不论证，但 `summary.md` 禁止写成因子有效。

## 2. 勘误表（已回填 v2）

| ID | 来源 | 动作 |
|----|------|------|
| D-F1 / S-F1 / P-F9 | 筹码窗口与股本时点 | v2 §2 重锁计算路径 |
| S-F2 | SMA 含 T | 锁 `close[-1] > sma[-1]` |
| S-F3 | 周线 asof | 锁 `_last_day` + backward asof |
| S-F6 | Cerebro 同日卖 | 锁「买入日禁卖、卖出一律次日 Open」 |
| S-F7 | 涨跌停仍成交 | 改为 skip，不进净值 |
| S-F8 | T-2 NaN | 要求 T-2 四条件有限 |
| S-F9 / P-F7 | 费率 | 自写 CommInfo，含 min_commission |
| P-F4 | 策略落点 | 移入 `backtest/research/` |
| P-F5 | 抽样源 | float_shares ∩ hive，不用 scan_stocks 抽代码 |
| P-F11 | gate | 新文件禁 `oskh_data.float_shares` 等下载模块 |
| D-F2 / D-F3 / D-F4 | 先全市场 / 不写 CLI | **驳回**（与用户指令冲突）；报告披露偏差即可 |

## 3. 对 §3 的 host 裁决

- §3.1：口径补齐后可实施。
- §3.2：独立 research CLI 必要；根目录策略文件不必要。
- §3.3：30 只是用户指定的试验，不是全市场结论。


 exited 1 in 1756ms:
head: 
Line |
   2 |  … est common oskh_factors oskh_data qlib_cost scripts tests | head -200
     |                                                                ~~~~
     | The term 'head' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'rg --files backtest common oskh_factors oskh_data qlib_cost scripts tests 2>$null | Select-Object -First 250' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1080ms:
oskh_factors\__init__.py
oskh_factors\weekly_macd_divergence.py
oskh_factors\price_bb.py
common\__init__.py
scripts\_write_chip_readme_once.py
tests\__init__.py
tests\test_turnover_resist_bridge.py
scripts\_script_bootstrap.py
tests\test_turnover_resistance_store.py
tests\test_profit_strategy_preset_parity.py
tests\test_preset_strategy_adapter.py
tests\test_oskh_data_integration.py
tests\test_data_path_ssot_write_symmetry.py
tests\test_data_path_authority_marker.py
tests\test_chip_indicator_warmup_semantics.py
tests\test_backtest_profit_strategy.py
tests\test_backtest_mock_qmt_pipeline.py
tests\test_backtest_engine_smoke.py
tests\conftest.py
tests\bench_stock_data_reader_multiprocess.py
qlib_cost\筹码分布因子.ipynb
qlib_cost\__init__.py
qlib_cost\utils.py
qlib_cost\turnover_coefficient_ops.py
qlib_cost\requirements.txt
qlib_cost\README.md
qlib_cost\qlib_workflow.py
qlib_cost\plotting.py
qlib_cost\factor_expr.py
qlib_cost\factor_analyze.py
qlib_cost\distribution_of_chips.py
qlib_cost\cyq_ops.py
qlib_cost\cyq.py
oskh_data\etf_local_bars.py
oskh_data\etf_limits.py
oskh_data\daily_parquet_write.py
oskh_data\cache_port.py
oskh_data\audit.py
oskh_data\adj_factor_meta.py
oskh_data\adj_factor.py
oskh_data\integrity.py
oskh_data\freshness.py
oskh_data\float_shares_history.py
oskh_data\parquet_meta.py
oskh_data\pandas_typing.py
oskh_data\period_schema.py
oskh_data\__init__.py
oskh_data\turnover_resistance_store.py
oskh_data\symbol_format.py
oskh_data\seed_missing_front.py
oskh_data\repair_daily_parquet_schema.py
oskh_data\reader.py
oskh_data\py.typed
backtest\preset_strategy_adapter.py
backtest\portfolio_manager.py
backtest\LimitUpDownManager.py
backtest\__init__.py
backtest\TPlus1QueueManager.py
scripts\ops\verify_tr_staging_migration.py
oskh_factors\bridge\__init__.py
oskh_factors\bridge\turnover_resist.py
backtest\chip_indicator.py
backtest\chip_algorithm.py
backtest\backtest_main_full.py
backtest\global_capital_manager.py
backtest\legacy\engine.py
scripts\tr\rebuild_front_duckdb_standalone.py
common\integrations\__init__.py
backtest\legacy\__init__.py
scripts\tr\compute_turnover_resistance_bands.py
backtest\legacy\mock_qmt_backtrader_adapter.py
scripts\tr\backfill_turnover_resistance_yearly.py
scripts\tr\backfill_turnover_resistance_bands.py
backtest\rolling_investment_strategy.py
backtest\StockStatus.py
common\integrations\duckdb_daily_bars_adapter.py
backtest\ProfitStrategy.py
backtest\qmt_utils_adv.py
scripts\run\__init__.py
oskh_factors\chip\__init__.py
oskh_factors\chip\window_guard.py
scripts\run\run_multi_ai_review.py
oskh_factors\chip\shares.py
scripts\run\multi_ai_common.py
oskh_factors\chip\paths.py
oskh_factors\chip\core.py
oskh_factors\chip\constants.py
oskh_factors\chip\bands.py
oskh_factors\chip\adj_factor.py
scripts\gates\verify_data_path_ssot.py
scripts\gates\verify_oskh_data_contract.py
backtest\tools\__init__.py
backtest\tools\read_app_data.py
backtest\tools\parse_log.py
backtest\tools\file_rename_dates.py
backtest\tools\file_compare.py
scripts\research\full_market_chip_resist.py
scripts\research\full_market_canonical_resist.py
scripts\research\chip_window_sensitivity.py
scripts\research\benchmark_turnover_resist_bridge.py
scripts\research\preflight_chip_diagnosis.py
scripts\research\full_market_equal_weight_resist_v2.py
scripts\research\full_market_equal_weight_resist.py
scripts\research\spot_check_chip_factors.py
scripts\research\verify_single_stock_turnover_resist.py
backtest\research\daily_chip_logger.py
backtest\research\chip_selection_backtest.py
common\infra\__init__.py
backtest\research\chip_factor_analysis.py
common\infra\trading_calendar_pmc.py
backtest\research\chip_backtest.py
common\infra\trace_context.py
common\infra\timekeeping.py
common\infra\security.py
backtest\research\filter_chip_stocks.py
common\infra\runtime_config.py
backtest\research\evaluate_turnover_chip_factors.py
common\infra\quant_logger.py
common\infra\qmt_utils_adv.py
backtest\research\filter_stock_pool_by_chip.py
common\infra\pandas_frame_utils.py
common\infra\exceptions.py
backtest\research\rolling_ic_chip_factors.py
common\infra\data_root.py
common\infra\constants.py
scripts\research\verify_turnover_resistance_alignment.py
backtest\research\verify_adj_minute_chip.py
backtest\research\__init__.py
backtest\research\verify_mvp_min.py
backtest\research\verify_minute_chip.py
backtest\research\verify_float_shares_time_dimension_baseline.py
backtest\research\verify_chip_pool_enhancement.py
backtest\research\verify_chip_factor_consistency.py
backtest\research\verify_cerebro_chip.py

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "oskh_factors/weekly_macd_divergence.py"' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "backtest/chip_indicator.py"' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1099ms:
# -*- coding: utf-8 -*-
"""周线 MACD 底背离因子（纯算法，零 oskh_data 依赖 — RFC-003 包规约）。

方案 SSOT：``docs/engineering/plan-weekly-macd-divergence-2026-07-20.md`` v3。
输入为**前复权**日线 DataFrame（DatetimeIndex；复权由调用方/数据层保证——多年
轻新低检测必须复权，否则除权跳空 → 假新低 → 假背离），输出信号列表。
批量扫描 runner / 数据装载见 ``scripts/analysis/weekly_macd_divergence.py``。

三级判定：

1. 候选背离（60 周窗口三条件 AND）：价格创 60 周新低（严格 ``<``）+
   DIF 未同步新低 + 绿柱收敛（``macd_hist < 0`` 且 abs 收敛——v1 语义修正，
   需求文档伪代码未限定符号，但文字描述是「绿柱收敛」，红柱 abs 收缩不算）。
2. 合并 + 分类：相邻候选间隔 <8 周 → 同一次背离事件（v1 修参考代码 merge bug：
   与上一个 kept 候选比间隔 ``last_kept``，非 ``candidates[-1]``）；
   按 trailing-52 周窗口内事件序号标 first/second/third/excessive
   （防全程累加把 90 周前事件误当序列 → STRONG 误标）。
3. 趋势评级：``close > MA200`` → uptrend；不足 200 周 → ``is_uptrend=None``
   （unknown，强度判定时视为「不满足 uptrend 条件」）。

口径：

- 日线→周线：``resample('W-FRI')`` on **DatetimeIndex**（A 股交易日周 Mon-Fri，
  周收盘 = 该周最后交易日收盘）。
- MACD(12,26,9) ``ewm adjust=False``（标准交易软件口径，种子=首值）。
- ``signal_date`` = 该周**最后交易日**（非周五标签，节假日周对齐真实可交易日）。
- ``as_of_date`` = 扫描快照日（provenance，非 point-in-time）。前复权 repaint
  数学无害（乘性因子 c>0，min/max/符号比较不变 → 信号 date/type/strength 稳定）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, cast

import pandas as pd

# ---------------------------------------------------------------------------
# 常量（方案 §2 默认值，均可由入口参数覆盖）
# ---------------------------------------------------------------------------

DEFAULT_LOOKBACK_WEEKS = 60  # 条件 A/B 回望窗口（方案默认）
DEFAULT_MIN_GAP_WEEKS = 8  # 候选合并阈值：<8 周同一事件
DEFAULT_COUNT_WINDOW_WEEKS = 52  # 分类计数窗口（trailing-52 周，~1 年）
DEFAULT_MIN_HISTORY_WEEKS = 260  # skip 底线（295=MA200 全覆盖；260-294 可检但 trend=unknown）
MA200_WINDOW_WEEKS = 200
WEEK_RULE = "W-FRI"  # A 股交易日周 Mon-Fri，周五收盘为周收盘

_TYPE_BY_ORDINAL = {1: "first", 2: "second", 3: "third"}
TYPE_EXCESSIVE = "excessive"
STRENGTH_STRONG = "STRONG"
STRENGTH_MEDIUM = "MEDIUM"
STRENGTH_WEAK = "WEAK"

_TYPE_CN = {"first": "第1次底背离", "second": "第2次底背离", "third": "第3次底背离", TYPE_EXCESSIVE: "多次底背离(过度)"}
_TREND_CN = {True: "上涨趋势", False: "非上涨趋势", None: "趋势未知"}
_STRENGTH_CN = {STRENGTH_STRONG: "强烈买入", STRENGTH_MEDIUM: "中等关注", STRENGTH_WEAK: "信号较弱"}


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DivergenceSignal:
    """单条底背离信号（CSV 一行；r1 codex 🔴4 明确字段）。"""

    stock_code: str
    signal_date: str  # YYYY-MM-DD，该周最后交易日
    close: float  # 前复权周收盘
    dif: float
    macd_hist: float
    divergence_type: str  # first / second / third / excessive
    is_uptrend: Optional[bool]  # None = unknown（不足 200 周历史）
    signal_strength: str  # STRONG / MEDIUM / WEAK
    as_of_date: str  # 扫描快照日（provenance）
    description: str


# ---------------------------------------------------------------------------
# 管线各阶段（方案 §3 结构）
# ---------------------------------------------------------------------------


def _daily_to_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    """日线 → 周线（W-FRI）。``_last_day`` = 该周最后交易日（signal_date 真源）。"""
    if not isinstance(daily.index, pd.DatetimeIndex):
        raise TypeError(
            "daily 必须是 DatetimeIndex（reader 输出契约）；resample 不能用 on='time'（int64 ms 列会 TypeError）"
        )
    d = daily.copy()
    d["_last_day"] = d.index
    weekly = d.resample(WEEK_RULE).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "_last_day": "max",
        }
    )
    return cast(pd.DataFrame, weekly.dropna())


def _compute_macd(
    weekly_close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """标准 MACD：``ewm(span, adjust=False)``（交易软件口径，种子=首值）。"""
    ema_fast = weekly_close.ewm(span=fast, adjust=False).mean()
    ema_slow = weekly_close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd_hist = (dif - dea) * 2
    return pd.DataFrame({"dif": dif, "dea": dea, "macd_hist": macd_hist})


def _find_candidates(macd_df: pd.DataFrame, lookback: int = DEFAULT_LOOKBACK_WEEKS) -> List[int]:
    """第一级：三条件 AND，返回候选点位置（positional int）。"""
    close = macd_df["close"].to_numpy(dtype=float)
    dif = macd_df["dif"].to_numpy(dtype=float)
    hist = macd_df["macd_hist"].to_numpy(dtype=float)
    candidates: List[int] = []
    for t in range(lookback, len(macd_df)):
        # 条件 A：价格创 lookback 周新低（严格 <，非 ≤）
        if not close[t] < close[t - lookback : t].min():
            continue
        # 条件 B：DIF 未同步新低（核心背离）
        if not dif[t] > dif[t - lookback : t].min():
            continue
        # 条件 C：绿柱收敛（v1 修正：限定 macd_hist < 0；红柱 abs 收缩不算）
        if not (hist[t] < 0 and abs(hist[t]) < abs(hist[t - 1])):
            continue
        candidates.append(t)
    return candidates


def _merge_and_classify(
    candidates: Sequence[int],
    min_gap: int = DEFAULT_MIN_GAP_WEEKS,
    count_window: int = DEFAULT_COUNT_WINDOW_WEEKS,
) -> List[Dict[str, Any]]:
    """第二级：相邻候选 <min_gap 周合并为同一事件 + trailing-count_window 计数分类。

    v1 修参考代码 merge bug：与上一个 **kept** 候选比间隔（``last_kept``），
    非 ``candidates[-1]``（随 filtered 增长变化）。合并保留首次出现点为代表
    （信号最早可行动日）。
    """
    events: List[Dict[str, Any]] = []
    last_kept: Optional[int] = None
    for pos in candidates:
        if last_kept is None or pos - last_kept >= min_gap:
            events.append({"pos": pos, "divergence_type": ""})
            last_kept = pos
        # 间隔 < min_gap → 并入当前事件（不新建；仍与 last_kept 比下一个）
    positions = [e["pos"] for e in events]
    for i, ev in enumerate(events):
        ordinal = 1 + sum(1 for p in positions[:i] if 0 < ev["pos"] - p <= count_window)
        ev["divergence_type"] = _TYPE_BY_ORDINAL.get(ordinal, TYPE_EXCESSIVE)
    return events


def _describe(divergence_type: str, is_uptrend: Optional[bool], strength: str) -> str:
    return f"{_TYPE_CN.get(divergence_type, divergence_type)} {_TREND_CN[is_uptrend]} {_STRENGTH_CN.get(strength, strength)}"


def _assess_trend_and_grade(
    events: Sequence[Dict[str, Any]],
    weekly: pd.DataFrame,
    stock_code: str,
    as_of_date: str,
) -> List[DivergenceSignal]:
    """第三级：MA200 趋势 + STRONG/MEDIUM/WEAK 评级，落成 DivergenceSignal。

    MA200 = 200 周滚动均值；不足 200 周 → ``is_uptrend=None``（unknown），
    强度判定中视为「不满足 uptrend 条件」（v3 §2.5：不系统性降级较早信号，
    但 CSV 标注 unknown 与 False 区别）。
    """
    ma200 = cast(pd.Series, weekly["close"].rolling(MA200_WINDOW_WEEKS).mean())
    signals: List[DivergenceSignal] = []
    for ev in events:
        t = int(ev["pos"])
        ma = ma200.iloc[t]
        is_uptrend: Optional[bool] = None if pd.isna(ma) else bool(weekly["close"].iloc[t] > ma)
        dtype = str(ev["divergence_type"])
        if dtype == "second" and is_uptrend is True:
            strength = STRENGTH_STRONG
        elif (dtype == "first" and is_uptrend is True) or (dtype == "second" and is_uptrend is not True):
            strength = STRENGTH_MEDIUM
        else:
            strength = STRENGTH_WEAK
        signal_day = cast(pd.Timestamp, pd.Timestamp(weekly["_last_day"].iloc[t])).date().isoformat()
        signals.append(
            DivergenceSignal(
                stock_code=stock_code,
                signal_date=signal_day,
                close=round(float(weekly["close"].iloc[t]), 3),
                dif=round(float(weekly["dif"].iloc[t]), 4),
                macd_hist=round(float(weekly["macd_hist"].iloc[t]), 4),
                divergence_type=dtype,
                is_uptrend=is_uptrend,
                signal_strength=strength,
                as_of_date=as_of_date,
                description=_describe(dtype, is_uptrend, strength),
            )
        )
    return signals


def detect_weekly_macd_divergence(
    daily: Optional[pd.DataFrame],
    stock_code: str,
    *,
    lookback: int = DEFAULT_LOOKBACK_WEEKS,
    min_gap: int = DEFAULT_MIN_GAP_WEEKS,
    count_window: int = DEFAULT_COUNT_WINDOW_WEEKS,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    min_history_weeks: int = DEFAULT_MIN_HISTORY_WEEKS,
    as_of_date: str = "",
) -> Optional[List[DivergenceSignal]]:
    """纯因子入口：前复权日线 DataFrame → 底背离信号列表。

    ``daily`` 须为 DatetimeIndex、含 ``open/high/low/close/volume`` 列（reader 输出
    契约）。返回 ``list[DivergenceSignal]``（可为空 = 无信号）；``None`` = skipped
    （空数据或周线数 < ``min_history_weeks``）。
    """
    if daily is None or len(daily) == 0:
        return None
    weekly = _daily_to_weekly(daily)
    if len(weekly) < min_history_weeks:
        return None
    macd = _compute_macd(cast(pd.Series, weekly["close"]), fast, slow, signal)
    weekly = pd.concat([weekly, macd], axis=1)
    candidates = _find_candidates(weekly, lookback=lookback)
    events = _merge_and_classify(candidates, min_gap=min_gap, count_window=count_window)
    return _assess_trend_and_grade(events, weekly, stock_code, as_of_date)


 succeeded in 1007ms:
# -*- coding: utf-8 -*-
"""
chip_indicator.py — COST 筹码分布 backtrader Indicator (Step 1 MVP-min)

将 chip_algorithm.py 封装为 backtrader.Indicator 子类，
在策略 next() 中可直接引用 self.chip.cyqk_c[0] 等。

用法示例（在 RollingInvestmentStrategy.__init__ 中）:

    from backtest.chip_indicator import ChipDistribution
    self.chip = ChipDistribution(
        self.datas[0], period=80, data_freq='1d'
    )

注意：MVP-min 使用固定流通股本占位 turnover_rate（不可用于生产）。
"""

import backtrader as bt
import numpy as np
import pandas as pd

from backtest.chip_algorithm import (  # noqa: E402
    adapt_columns,
    daily_chip_distribution,
    turnover_chip_factors,
    cyq,
)
from common.infra.quant_logger import get_logger

logger = get_logger(__name__)

# P0-3 fix: 模块级 fault 计数器，用于策略检测计算异常
_CHIP_FAULT_COUNT: int = 0


def get_chip_fault_count() -> int:
    """返回自进程启动以来 chip indicator 的异常 fault 次数。

    策略可在 next() 中检查：若 fault_count > 0，应停止交易并告警。
    """
    return _CHIP_FAULT_COUNT


class ChipDistribution(bt.Indicator):
    """
    筹码分布因子 Indicator。

    输出 4 条 line：
    - cyqk_c：获利比例（筹码分布中价格低于当前收盘价的比例）
    - asr：活跃筹码比（收盘价 ±10% 范围内的筹码占比）
    - ckdw：筹码重心（成本分布中心偏离度）
    - prp：价格相对成本位置（收盘价 / 平均成本 - 1）

    参数：
    - period: 回看窗口（交易日数），默认 80
    - data_freq: 数据频率，'1d'（日线）或 '1m'（分钟线），默认 '1d'
    - dist_method: 日线模式下的分布假设，'triang'（三角分布）或 'uniform'（均匀分布），默认 'triang'
    - stock_code: 标的代码（如 '000001.SZ'），用于查找真实流通股本计算 turnover_rate
    """

    lines = ("cyqk_c", "asr", "ckdw", "prp")
    params = (
        ("period", 80),
        ("data_freq", "1d"),
        ("dist_method", "triang"),
        ("stock_code", ""),
    )

    plotinfo = dict(
        plot=True,
        subplot=True,
        plotname="Chip Distribution",
    )

    plotlines = dict(
        cyqk_c=dict(_name="CYQK_C", _method="line"),
        asr=dict(_name="ASR", _method="line"),
        ckdw=dict(_name="CKDW", _method="line"),
        prp=dict(_name="PRP", _method="line"),
    )

    def __init__(self):
        super(ChipDistribution, self).__init__()
        self.addminperiod(self.p.period)

    def _set_nan_lines(self):
        self.lines.cyqk_c[0] = float("nan")
        self.lines.asr[0] = float("nan")
        self.lines.ckdw[0] = float("nan")
        self.lines.prp[0] = float("nan")

    def prenext(self):
        # Warmup 阶段显式写 NaN，避免 backtrader line 默认值被误读为有效 0.0。
        self._set_nan_lines()

    def next(self):
        if len(self.data) < self.p.period:
            self._set_nan_lines()
            return

        # 收集窗口数据 → DataFrame
        window_data = {
            "close": np.array(
                [self.data.close[i] for i in range(-self.p.period, 0)],
                dtype=np.float64,
            ),
            "high": np.array(
                [self.data.high[i] for i in range(-self.p.period, 0)],
                dtype=np.float64,
            ),
            "low": np.array(
                [self.data.low[i] for i in range(-self.p.period, 0)],
                dtype=np.float64,
            ),
            "volume": np.array(
                [self.data.volume[i] for i in range(-self.p.period, 0)],
                dtype=np.float64,
            ),
        }
        df = pd.DataFrame(window_data)

        try:
            arr = adapt_columns(df, stock_code=self.p.stock_code or None)

            if self.p.data_freq == "1m":
                # P0-4 fix: 分钟线模式使用 hybrid 路径（日线 front 定框架 + 分钟线微调），
                # 代替纯分钟线筹码分布（QMT 分钟线不支持复权，除权日存在价格断裂）
                from backtest.chip_algorithm import hybrid_chip_distribution
                from oskh_data.reader import StockDataReader

                daily_reader = StockDataReader(mode="duckdb_persistent")
                end_date = self.data.datetime.date(0).strftime("%Y%m%d")
                start_date = (
                    pd.Timestamp(end_date) - pd.Timedelta(days=self.p.period * 2)
                ).strftime("%Y%m%d")
                daily_df = daily_reader.read_stock(
                    self.p.stock_code,
                    start_time=start_date,
                    end_time=end_date,
                    period="1d",
                    adjust_type="front",
                )
                daily_reader.close()

                if daily_df is None or len(daily_df) < self.p.period:
                    raise ValueError(
                        f"日线 front 数据不足: 需要 >= {self.p.period} 天，"
                        f"实际 {len(daily_df) if daily_df is not None else 0} 天"
                    )

                daily_df = daily_df.sort_index()
                daily_uniq = daily_df.index.normalize().unique()
                daily_mask = daily_df.index.normalize().isin(daily_uniq[-self.p.period:])
                daily_arr = adapt_columns(
                    daily_df.loc[daily_mask], stock_code=self.p.stock_code or None
                )
                dist = hybrid_chip_distribution(daily_arr, arr)
            else:
                dist = daily_chip_distribution(arr, method=self.p.dist_method)

            close_price = float(self.data.close[0])
            cf = cyq.ChipFactor(close_price, dist)

            self.lines.cyqk_c[0] = cf.get_cyqk_c()
            self.lines.asr[0] = cf.get_asr()
            self.lines.ckdw[0] = cf.get_ckdw()
            self.lines.prp[0] = cf.get_prp()

        except (ValueError, KeyError) as e:
            # 预期内：数据不足、停牌、列缺失、窗口不够等
            logger.warning(
                "ChipDistribution expected NaN",
                context={"stock": self.p.stock_code, "reason": str(e)},
            )
            self._set_nan_lines()
        except Exception as e:
            # P0-3 fix: 异常 NaN（计算错误、除零、数据损坏等）→ 记 fault
            global _CHIP_FAULT_COUNT
            _CHIP_FAULT_COUNT += 1
            logger.error(
                "ChipDistribution fault NaN",
                context={
                    "stock": self.p.stock_code,
                    "fault_count": _CHIP_FAULT_COUNT,
                    "exc": str(e),
                },
            )
            self._set_nan_lines()


class TurnoverChipFactor(bt.Indicator):
    """
    换手率半衰期筹码分布因子 Indicator（Phase 2）。

    输出 4 条 line：
    - arc：平均持仓盈亏（>0 盈利，<0 亏损）
    - vrc：筹码集中度（越大越分散，越小越集中）
    - src：盈亏分布偏度（>0 右偏，<0 左偏）
    - krc：盈亏分化度（越大分化越严重）

    参数：
    - period: 回看窗口（交易日数），默认 60
    - stock_code: 股票代码（用于查找真实流通股本）
    """

    lines = ("arc", "vrc", "src", "krc")
    params = (("period", 60), ("stock_code", ""))

    plotinfo = dict(plot=True, subplot=True, plotname="Turnover Chip")

    def __init__(self):
        self.addminperiod(self.p.period)

    def _set_nan_lines(self):
        self.lines.arc[0] = float("nan")
        self.lines.vrc[0] = float("nan")
        self.lines.src[0] = float("nan")
        self.lines.krc[0] = float("nan")

    def prenext(self):
        # warmup 阶段统一 NotReady 语义。
        self._set_nan_lines()

    def next(self):
        if len(self.data) < self.p.period:
            self._set_nan_lines()
            return
        try:
            tr = np.array(
                [self.data.turnover_rate[i] for i in range(-self.p.period, 0)],
                dtype=np.float64,
            )
            cl = np.array(
                [self.data.close[i] for i in range(-self.p.period, 0)],
                dtype=np.float64,
            )
            # 如果 turnover_rate line 不在数据中（NaN），用 volume 估算
            if np.isnan(tr).all():
                from backtest.chip_algorithm import _estimate_turnover, _get_float_shares
                vol = np.array(
                    [self.data.volume[i] for i in range(-self.p.period, 0)],
                    dtype=np.float64,
                )
                # P1-2 fix: 使用真实流通股本而非 100 亿默认值
                fs = _get_float_shares(self.p.stock_code) if self.p.stock_code else None
                if fs is not None and fs > 0:
                    tr = _estimate_turnover(vol, float_shares=fs)
                else:
                    # 无流通股本数据时使用默认值，但记录警告
                    logger.warning(
                        "TurnoverChipFactor using 100亿 default float_shares",
                        context={"stock": self.p.stock_code},
                    )
                    tr = _estimate_turnover(vol)

            result = turnover_chip_factors(tr, cl, window=self.p.period)
            self.lines.arc[0] = result["arc"]
            self.lines.vrc[0] = result["vrc"]
            self.lines.src[0] = result["src"]
            self.lines.krc[0] = result["krc"]
        except (ValueError, KeyError) as e:
            logger.warning(
                "TurnoverChipFactor expected NaN",
                context={"reason": str(e)},
            )
            self._set_nan_lines()
        except Exception as e:
            global _CHIP_FAULT_COUNT
            _CHIP_FAULT_COUNT += 1
            logger.error(
                "TurnoverChipFactor fault NaN",
                context={"fault_count": _CHIP_FAULT_COUNT, "exc": str(e)},
            )
            self._set_nan_lines()


exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "backtest/chip_algorithm.py"' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "oskh_factors/chip/__init__.py"; "`n===== core.py ====="; Get-Content -Raw -LiteralPath "oskh_factors/chip/core.py"' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1023ms:
# -*- coding: utf-8 -*-
"""Cerebro-facing re-export of ``oskh_factors.chip`` (SSOT).

Do not add algorithm here. Change ``oskh_factors.chip`` / ``qlib_cost`` instead.
"""
from __future__ import annotations

from qlib_cost import cyq
from oskh_factors.chip.adj_factor import adj_minute_prices, get_adj_factor
from oskh_factors.chip.core import (
    adapt_columns,
    adj_minute_chip_distribution,
    compute_chip_factors,
    compute_crossday_turnover_resistance,
    compute_equal_weight_cyqk,
    daily_chip_distribution,
    derived_chip_factors,
    hybrid_chip_distribution,
    minute_chip_distribution,
    turnover_chip_factors,
)
from oskh_factors.chip.shares import (
    _estimate_turnover,
    _get_float_shares,
    _get_free_float_shares,
    _load_float_shares_map,
    _load_free_float_shares,
)
from oskh_factors.price_bb import bb_position

__all__ = [
    "adapt_columns",
    "adj_minute_chip_distribution",
    "adj_minute_prices",
    "bb_position",
    "compute_chip_factors",
    "compute_crossday_turnover_resistance",
    "compute_equal_weight_cyqk",
    "cyq",
    "daily_chip_distribution",
    "derived_chip_factors",
    "get_adj_factor",
    "hybrid_chip_distribution",
    "minute_chip_distribution",
    "turnover_chip_factors",
    "_estimate_turnover",
    "_get_float_shares",
    "_get_free_float_shares",
    "_load_float_shares_map",
    "_load_free_float_shares",
]


 succeeded in 849ms:

===== core.py =====
# -*- coding: utf-8 -*-
"""Chip distribution and cross-day turnover resistance core (RFC-003 §5.1)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional, cast

from common.infra.quant_logger import get_logger
from qlib_cost.distribution_of_chips import make_price_grid
from qlib_cost import cyq
from qlib_cost.cyq import calc_curpdf
from qlib_cost import turnover_coefficient_ops as tco

from oskh_factors.chip.adj_factor import get_adj_factor
from oskh_factors.chip.shares import (
    _estimate_turnover,
    _get_float_shares,
    _get_free_float_shares,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 列名适配器
# ---------------------------------------------------------------------------
def adapt_columns(
    df: pd.DataFrame,
    stock_code: Optional[str] = None,
    as_of_date: Optional[pd.Timestamp] = None,
    use_free_float: bool = False,
) -> np.ndarray:
    """
    适配 backtrader DataFrame 列名到 cyq.py 期望的列名契约。

    cyq.py:100 要求 [\"close\", \"high\", \"low\", \"vol\", \"turnover_rate\"]
    现有数据：volume（非 vol），无 turnover_rate。
    传入 stock_code 时从 float_shares.parquet / history 获取流通股本计算 turnover_rate。

    Args:
        df: backtrader 风格的 DataFrame（columns: close, high, low, volume）
        stock_code: 标的代码（如 '000001.SZ'），用于查找真实流通股本
        as_of_date: 可选，按该日期查询历史股本（用于回测避免前视）
        use_free_float: True=自由流通股本（freeFloatCapital），False=流通股本（FloatVolume）

    Returns:
        np.ndarray with columns: close, high, low, vol, turnover_rate
    """
    df = df.rename(columns={"volume": "vol"})
    if "turnover_rate" not in df.columns:
        if use_free_float:
            float_shares = _get_free_float_shares(stock_code, date=as_of_date)
        else:
            float_shares = _get_float_shares(stock_code, date=as_of_date)
        df["turnover_rate"] = _estimate_turnover(
            np.asarray(df["vol"].values, dtype=np.float64), float_shares
        )
    return cast(
        np.ndarray,
        df[["close", "high", "low", "vol", "turnover_rate"]].values,
    )


# ---------------------------------------------------------------------------
# 日线筹码分布（三角/均匀 PDF fallback）
# ---------------------------------------------------------------------------
def daily_chip_distribution(arr: np.ndarray, method: str = "triang") -> pd.Series:
    """
    日线筹码分布：使用三角/均匀 PDF 假设。

    直接委托给 qlib_cost 的 calc_dist_chips()。

    Args:
        arr: adapt_columns() 输出 (N, 5) 数组
        method: "triang" 或 "uniform"

    Returns:
        pd.Series, index=price, values=chip volume
    """
    return cyq.calc_dist_chips(arr, method=method)


# ---------------------------------------------------------------------------
# 分钟线筹码分布（实际量价累积，跳过 PDF 假设）
# ---------------------------------------------------------------------------
def minute_chip_distribution(
    arr: np.ndarray,
    step: float = 0.01,
    stock_code: str = "",
) -> pd.Series:
    """
    分钟线筹码分布：用每分钟的实际 (close, volume) 构建直方图。

    跳过三角/均匀 PDF 假设，直接用量价累积。
    但仍需假设分钟内成交价格代表值为 close。

    Args:
        arr: adapt_columns() 输出 (N, 5) 数组。
             N ≈ 80 天 × 240 分钟 = 19,200。
             columns: close, high, low, vol, turnover_rate
        step: 价格步长（元）
        stock_code: 标的代码（仅用于异常时的日志上下文）

    Returns:
        pd.Series, index=price（以 step 为步长）, values=累计 chip volume
    """
    close = arr[:, 0]   # 分钟 close
    vol = arr[:, 3]     # 分钟 volume
    turnover = arr[:, 4]  # 分钟 turnover_rate（从日线按 volume 占比分配后）

    min_p = float(np.nanmin(close))
    max_p = float(np.nanmax(close))
    if np.isnan(min_p) or np.isnan(max_p) or max_p <= min_p:
        # P1-5 fix: 记录原因（停牌/一字板/数据异常），不再静默返回空
        label = f"{stock_code} " if stock_code else ""
        reason = (
            f"{label}价格全部相同 (max={max_p} <= min={min_p})，"
            f"可能原因：停牌、一字板涨跌停、或数据异常"
        )
        logger.warning(reason)
        return pd.Series(dtype=float, name="cumpdf")

    price_bins = make_price_grid(min_p, max_p, step)
    cumpdf = np.zeros(len(price_bins), dtype=np.float64)

    # 按日期分组，每日内用 decay 模型累积
    # arr 按时间排序，每日的 decay 由该日的分钟 turnover_rate 计算
    decay = turnover.copy()
    diff = 1.0 - decay

    for i in range(len(close)):
        if np.isnan(close[i]) or vol[i] <= 0:
            continue
        # 找到该分钟的成交量归属的价格 bin
        idx = int((close[i] - min_p) / step)
        if idx < 0:
            idx = 0
        elif idx >= len(price_bins):
            idx = len(price_bins) - 1

        curpdf = np.zeros(len(price_bins), dtype=np.float64)
        curpdf[idx] = vol[i] * decay[i]

        if i == 0:
            cumpdf = curpdf
        else:
            cumpdf = cumpdf * diff[i] + curpdf

    # 归一化
    total = cumpdf.sum()
    if total > 0:
        cumpdf /= total

    return pd.Series(cumpdf, index=price_bins, name="cumpdf")


# ---------------------------------------------------------------------------
# 方案 A：日线定框架 + 分钟线做日内偏移（§10.4.2）
# ---------------------------------------------------------------------------
def hybrid_chip_distribution(
    daily_arr: np.ndarray,
    minute_today_arr: np.ndarray,
    step: float = 0.01,
) -> pd.Series:
    """
    混合筹码分布：历史日线三角PDF + 当日分钟线量价累积。

    §10.4.2 方案 A — 日线定框架，分钟线只做当日新开仓成本的微调。
    与 pure minute (80天×240分钟) 相比，大幅降低计算量。

    Args:
        daily_arr: adapt_columns() 输出 (N, 5)，N 天日线，最后一行为当日
        minute_today_arr: adapt_columns() 输出 (M, 5)，当日分钟线
        step: 价格步长（元）

    Returns:
        pd.Series, index=price, values=累计 chip volume
    """
    # 价格网格：覆盖日线 + 分钟线的完整范围
    max_p = max(float(np.nanmax(daily_arr[:, 1])),
                float(np.nanmax(minute_today_arr[:, 0])))
    min_p = min(float(np.nanmin(daily_arr[:, 2])),
                float(np.nanmin(minute_today_arr[:, 0])))
    if max_p <= min_p:
        # P1-5 fix
        logger.warning(
            f"hybrid_chip_distribution: 日线+分钟线价格范围为空 "
            f"(max={max_p} <= min={min_p})，可能停牌或数据异常"
        )
        return pd.Series(dtype=float, name="cumpdf")

    xs = make_price_grid(min_p, max_p, step)
    n_days = len(daily_arr)
    curpdfs = np.zeros((n_days, len(xs)), dtype=np.float64)

    # 历史日（0 到 n_days-2）：三角 PDF
    for i in range(n_days - 1):
        curpdfs[i] = cyq.calc_curpdf(
            float(daily_arr[i, 0]), float(daily_arr[i, 1]),
            float(daily_arr[i, 2]), float(daily_arr[i, 3]),
            min_p, max_p, step, method="triang",
        )

    # 当日（最后一"天"）：分钟线量价直方图
    today_close = minute_today_arr[:, 0]
    today_vol = minute_today_arr[:, 3]
    today_pdf = np.zeros(len(xs), dtype=np.float64)
    for j in range(len(today_close)):
        if np.isnan(today_close[j]) or today_vol[j] <= 0:
            continue
        idx = int((today_close[j] - min_p) / step)
        if 0 <= idx < len(xs):
            today_pdf[idx] += today_vol[j]
    if today_pdf.sum() > 0:
        today_pdf /= today_pdf.sum()
    curpdfs[n_days - 1] = today_pdf

    # 换手率：历史日用日线值，当日用日线值（分钟 turnover 之和应与日线一致）
    turnover = daily_arr[:, 4].copy()

    cum_vol = cyq.calc_cumpdf(curpdfs, turnover)
    return pd.Series(cum_vol, index=xs, name="cumpdf")


def adj_minute_chip_distribution(
    arr: np.ndarray,
    stock_code: str,
    date,
    step: float = 0.01,
) -> pd.Series:
    """
    方案 B：复权因子校正后的分钟线筹码分布（§10.4.2）。

    流程：
    1. 用 get_adj_factor() 查询该标的首日的累积复权乘数
    2. 对价格列（close/high/low）乘上复权因子，量列（vol/turnover_rate）不变
    3. 调用 minute_chip_distribution() 计算筹码分布

    Args:
        arr: adapt_columns() 输出 (N, 5)，未复权分钟线
        stock_code: 标的代码
        date: 截面日期（用于查询复权因子）
        step: 价格步长

    Returns:
        pd.Series, index=price（等效前复权）, values=chip volume
    """
    factor = get_adj_factor(stock_code, date, strict=True)
    # P1-2: NaN 保护 — 复权因子不可用时不应进入筹码计算
    if pd.isna(factor):
        raise ValueError(
            f"adj_minute_chip_distribution: factor is NaN for {stock_code} @ {date}"
        )
    if factor == 1.0:
        # 无复权差异，直接走原始路径
        return minute_chip_distribution(arr, step=step)

    arr_adj = arr.copy()
    arr_adj[:, 0] = arr[:, 0] * factor  # close
    arr_adj[:, 1] = arr[:, 1] * factor  # high
    arr_adj[:, 2] = arr[:, 2] * factor  # low
    # vol (col 3) 和 turnover_rate (col 4) 保持不变

    return minute_chip_distribution(arr_adj, step=step)


# ---------------------------------------------------------------------------
# 便捷函数：从 DataFrame 一步计算 ChipFactor
# ---------------------------------------------------------------------------
def compute_chip_factors(
    df: pd.DataFrame,
    method: str = "triang",
    data_freq: str = "1d",
    stock_code: Optional[str] = None,
    daily_df: Optional[pd.DataFrame] = None,
) -> dict:
    """
    从 backtrader 风格的 DataFrame 计算 4 个筹码分布因子。

    Args:
        df: 包含 close, high, low, volume 列的 DataFrame（N 行窗口）
        method: 日线模式用 "triang" 或 "uniform"；分钟线模式忽略
        data_freq: "1d" 或 "1m"
        stock_code: 股票代码（如 "000001.SZ"），用于查找真实流通股本。
                    为 None 时抛 ValueError（P0-18 强制要求传入有效 stock_code）
        daily_df: 日线前复权 DataFrame（仅 data_freq="1m" 时需要）。
                  用于 hybrid_chip_distribution —— 历史日线定框架 + 当日分钟线微调，
                  解决 QMT 分钟线不支持复权导致的除权日筹码失真。

    Returns:
        dict with keys: cyqk_c, asr, ckdw, prp
    """
    as_of_date = None
    if isinstance(df.index, pd.DatetimeIndex) and len(df.index) > 0:
        as_of_date = cast(pd.Timestamp, pd.Timestamp(str(df.index[-1]))).normalize()  # pyright: ignore[reportAttributeAccessIssue]
    arr = adapt_columns(df, stock_code=stock_code, as_of_date=as_of_date)

    if data_freq == "1m":
        # P0-4 fix: 分钟线模式使用 hybrid 路径，日线 front 定框架 + 分钟线 none 微调
        if daily_df is not None and len(daily_df) > 0:
            daily_as_of = None
            if isinstance(daily_df.index, pd.DatetimeIndex) and len(daily_df.index) > 0:
                daily_as_of = cast(pd.Timestamp, pd.Timestamp(str(daily_df.index[-1]))).normalize()  # pyright: ignore[reportAttributeAccessIssue]
            daily_arr = adapt_columns(
                daily_df,
                stock_code=stock_code,
                as_of_date=daily_as_of,
            )
            dist = hybrid_chip_distribution(daily_arr, arr)
        else:
            raise ValueError(
                "data_freq='1m' 需要 daily_df 参数（日线前复权数据）。"
                "纯分钟线筹码分布在除权日前后存在价格断裂，已弃用。"
                "请调用方通过 StockDataReader(adjust_type='front') 加载日线数据后传入。"
            )
    else:
        dist = daily_chip_distribution(arr, method=method)

    close_price = float(arr[-1, 0])  # 最新 bar 的 close
    cf = cyq.ChipFactor(close_price, dist)

    return {
        "cyqk_c": cf.get_cyqk_c(),
        "asr": cf.get_asr(),
        "ckdw": cf.get_ckdw(),
        "prp": cf.get_prp(),
    }


# ---------------------------------------------------------------------------
# Phase 2: 换手率半衰期筹码分布因子（ARC/VRC/SRC/KRC）
# ---------------------------------------------------------------------------
def turnover_chip_factors(
    turnover_rate: np.ndarray,
    close: np.ndarray,
    window: int = 60,
) -> dict:
    """
    计算换手率衰减筹码分布因子（ARC/VRC/SRC/KRC）。

    基于广发证券多因子 alpha 系列报告 #27 的换手率半衰期模型。
    不需要 OHLC 分布假设，仅需换手率和收盘价。

    Args:
        turnover_rate: 换手率序列（比例，0-1），长度 ≥ window
        close: 收盘价序列，长度 ≥ window
        window: 滚动窗口（默认 60）

    Returns:
        dict with keys: arc, vrc, src, krc
    """
    if len(turnover_rate) < window or len(close) < window:
        return {"arc": np.nan, "vrc": np.nan, "src": np.nan, "krc": np.nan}

    # 截取最后 window 个值
    tr = np.asarray(turnover_rate[-window:], dtype=np.float64).flatten()
    cl = np.asarray(close[-window:], dtype=np.float64).flatten()

    chips = tco.calc_distribution_of_chips(tr, cl, window)
    return {
        "arc": float(chips[0]),
        "vrc": float(chips[1]),
        "src": float(chips[2]),
        "krc": float(chips[3]),
    }


# ---------------------------------------------------------------------------
# 跨日衍生 chip 因子
# ---------------------------------------------------------------------------
def derived_chip_factors(
    cyqk_today: float,
    cyqk_yesterday: float,
    turnover_today: float,
) -> dict:
    """
    跨日衍生 chip 因子。

    Args:
        cyqk_today: 当日获利筹码比例
        cyqk_yesterday: 上一日获利筹码比例
        turnover_today: 当日换手率（比例，0-1）

    Returns:
        dict with keys: profit_chip_diff, turnover_ratio, turnover_resistance
    """
    profit_chip_diff = cyqk_today - cyqk_yesterday
    if turnover_today > 0:
        turnover_resistance = profit_chip_diff / turnover_today
    else:
        turnover_resistance = 0.0

    return {
        "profit_chip_diff": round(profit_chip_diff, 6),
        "turnover_ratio": round(turnover_today, 6),
        "turnover_resistance": round(turnover_resistance, 4),
    }


def _fmt_cyqk(val: float):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    return round(float(val), 4)


def compute_crossday_turnover_resistance(
    df: pd.DataFrame,
    stock_code: str,
    window: int = 1000,
    method: str = "triang",
) -> dict:
    """
    截面日 T 的 canonical 换手阻力。

    今日窗口：最近 window 个交易日（含 T），默认 1000≈4 年；
    昨日窗口：再往前 window 日（含 T-1）。
    分母为今日窗口 adapt_columns 末行 turnover_rate（arr_t[-1, 4]），按 as_of_date 查股本。
    """
    if df is None or df.empty:
        raise ValueError("empty dataframe")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("df index must be DatetimeIndex")

    idx = cast(pd.DatetimeIndex, df.index)
    df = df.sort_index()
    unique_dates = idx.normalize().unique()  # pyright: ignore[reportAttributeAccessIssue]
    if len(unique_dates) < window:
        raise ValueError(f"need {window} trading days, got {len(unique_dates)}")

    as_of_t = cast(pd.Timestamp, pd.Timestamp(unique_dates[-1])).normalize()  # pyright: ignore[reportAttributeAccessIssue]
    mask_t = idx.normalize().isin(unique_dates[-window:])  # pyright: ignore[reportAttributeAccessIssue]
    df_t = df.loc[mask_t]

    arr_t = adapt_columns(df_t, stock_code=stock_code, as_of_date=as_of_t)
    dist_t = daily_chip_distribution(arr_t, method=method)
    cf_t = cyq.ChipFactor(float(arr_t[-1, 0]), dist_t)
    cyqk_today = cf_t.get_cyqk_c()
    turnover_today = float(arr_t[-1, 4])

    out = {
        "cyqk_c": _fmt_cyqk(cyqk_today),
        "cyqk_c_yesterday": "",
        "profit_chip_diff": "",
        "turnover_ratio": round(turnover_today, 6),
        "turnover_resistance": "",
        "window": int(window),
    }

    if len(unique_dates) < window + 1:
        return out

    prev_dates = unique_dates[-(window + 1):-1]
    as_of_y = cast(pd.Timestamp, pd.Timestamp(prev_dates[-1])).normalize()  # pyright: ignore[reportAttributeAccessIssue]
    mask_y = idx.normalize().isin(prev_dates)  # pyright: ignore[reportAttributeAccessIssue]
    df_y = df.loc[mask_y]
    arr_y = adapt_columns(df_y, stock_code=stock_code, as_of_date=as_of_y)
    dist_y = daily_chip_distribution(arr_y, method=method)
    cf_y = cyq.ChipFactor(float(arr_y[-1, 0]), dist_y)

    derived = derived_chip_factors(
        cyqk_today, cf_y.get_cyqk_c(), turnover_today,
    )
    out["cyqk_c_yesterday"] = _fmt_cyqk(cf_y.get_cyqk_c())
    out["profit_chip_diff"] = derived["profit_chip_diff"]
    out["turnover_ratio"] = derived["turnover_ratio"]
    out["turnover_resistance"] = derived["turnover_resistance"]
    return out


# ---------------------------------------------------------------------------
# 等权重筹码分布（市面常见指标对比实现）
# ---------------------------------------------------------------------------
def compute_equal_weight_cyqk(
    df: pd.DataFrame,
    stock_code: str,
    window: int = 1000,
    method: str = "triang",
) -> dict:
    """
    等权重筹码分布（无换手率衰减）—— 与市面常见筹码分布 APP 对齐的对比实现。

    与 canonical 路径 ``compute_crossday_turnover_resistance`` 的核心差异：
    1. **无衰减**：历史日筹码等权重累加，不使用 ``calc_cumpdf`` 的换手率衰减模型；
    2. **窗口**：默认 120 个交易日（市面常见指标通常用 100~130 日）；
    3. **无 turnover 估算**：本函数仅输出筹码分布因子，不计算换手率及阻力。

    Args:
        df: 日线 DataFrame（含 close/high/low/volume）
        stock_code: 标的代码
        window: 筹码分布窗口（交易日），默认 120
        method: PDF 方法，"triang" 或 "uniform"

    Returns:
        dict: cyqk_c, asr, ckdw, prp, cost_p05...cost_p95, close, window
    """
    if df is None or df.empty:
        raise ValueError("empty dataframe")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("df index must be DatetimeIndex")

    idx = cast(pd.DatetimeIndex, df.index)
    df = df.sort_index()
    unique_dates = idx.normalize().unique()  # pyright: ignore[reportAttributeAccessIssue]
    if len(unique_dates) < window:
        raise ValueError(f"need {window} trading days, got {len(unique_dates)}")

    as_of = cast(pd.Timestamp, pd.Timestamp(unique_dates[-1])).normalize()  # pyright: ignore[reportAttributeAccessIssue]
    win_dates = unique_dates[-window:]
    mask = idx.normalize().isin(win_dates)  # pyright: ignore[reportAttributeAccessIssue]
    df_w = df.loc[mask]

    arr = adapt_columns(df_w, stock_code=stock_code, as_of_date=as_of)
    close = float(arr[-1, 0])

    # 等权重累加：不用 calc_cumpdf，直接 sum(curpdf)
    max_p = float(np.nanmax(arr[:, 1]))
    min_p = float(np.nanmin(arr[:, 2]))
    step = 0.01
    if max_p <= min_p:
        return {
            "cyqk_c": float("nan"), "asr": float("nan"), "ckdw": float("nan"), "prp": float("nan"),
            "cost_p05": float("nan"), "cost_p10": float("nan"), "cost_p50": float("nan"),
            "cost_p90": float("nan"), "cost_p95": float("nan"),
            "close": close, "window": window, "method": method,
        }

    xs = make_price_grid(min_p, max_p, step)
    curpdfs = np.zeros((len(arr), len(xs)))
    for i in range(len(arr)):
        row = arr[i]
        pdf = calc_curpdf(row[0], row[1], row[2], row[3], min_p, max_p, step, method)
        curpdfs[i] = pdf

    cum_vol = np.sum(curpdfs, axis=0)
    dist = pd.Series(cum_vol, index=xs, name="cumpdf")

    cf = cyq.ChipFactor(close, dist)
    return {
        "cyqk_c": _fmt_cyqk(cf.get_cyqk_c()),
        "asr": _fmt_cyqk(cf.get_asr()),
        "ckdw": _fmt_cyqk(cf.get_ckdw()),
        "prp": _fmt_cyqk(cf.get_prp()),
        "cost_p05": round(float(cf.get_cost(0.05)), 2),
        "cost_p10": round(float(cf.get_cost(0.10)), 2),
        "cost_p50": round(float(cf.get_cost(0.50)), 2),
        "cost_p90": round(float(cf.get_cost(0.90)), 2),
        "cost_p95": round(float(cf.get_cost(0.95)), 2),
        "close": close,
        "window": window,
        "method": method,
    }



exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "oskh_factors/chip/shares.py"' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "qlib_cost/cyq.py"' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 925ms:
# -*- coding: utf-8 -*-
"""Float shares loaders and turnover estimation (RFC-003 §5.2)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional, cast

from common.infra.quant_logger import get_logger
from oskh_factors.chip.paths import stock_data_path

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 流通股本数据
# ---------------------------------------------------------------------------
# 默认值：100 亿股（中大盘典型值）。仅在 _estimate_turnover(float_shares=None) 窄路径使用。
_FLOAT_SHARES_DEFAULT: int = 10_000_000_000

# 模块级缓存
_float_shares_cache: Optional[pd.DataFrame] = None
_free_float_shares_cache: Optional[pd.DataFrame] = None


def _load_float_shares_map(parquet_path: Optional[str] = None) -> pd.DataFrame:
    """加载流通股本 Parquet（当前快照），缓存到模块级变量。"""
    global _float_shares_cache
    if _float_shares_cache is not None:
        return _float_shares_cache
    import os as _os
    if parquet_path is None:
        parquet_path = str(stock_data_path("float_shares.parquet"))
    if _os.path.exists(parquet_path):
        _float_shares_cache = pd.read_parquet(parquet_path)
    else:
        _float_shares_cache = pd.DataFrame()
    return _float_shares_cache


def _load_free_float_shares(parquet_path: Optional[str] = None) -> pd.DataFrame:
    """加载自由流通股本 Parquet（miniQMT Capital 财务表），缓存到模块级变量。"""
    global _free_float_shares_cache
    if _free_float_shares_cache is not None:
        return _free_float_shares_cache
    import os as _os
    if parquet_path is None:
        parquet_path = str(stock_data_path("free_float_shares.parquet"))
    if not _os.path.exists(parquet_path):
        _free_float_shares_cache = pd.DataFrame()
        return _free_float_shares_cache
    df = pd.read_parquet(parquet_path)
    if not df.empty and "m_timetag" in df.columns:
        df = df.copy()
        df["m_timetag"] = pd.to_datetime(df["m_timetag"]).dt.normalize()
    _free_float_shares_cache = df
    return _free_float_shares_cache


def _get_float_shares(stock_code: Optional[str] = None, date=None) -> float:
    """
    获取流通股本（circulating_capital / FloatVolume）。

    1. date is not None → free_float_shares.parquet → circulating_capital
    2. date is None     → float_shares.parquet → FloatVolume
    """
    if stock_code and date is not None:
        ffs = _load_free_float_shares()
        if not ffs.empty:
            target_date = cast(pd.Timestamp, pd.Timestamp(date)).normalize()  # pyright: ignore[reportAttributeAccessIssue]
            subset = ffs.loc[
                (ffs["stock_code"] == stock_code) & (ffs["m_timetag"] <= target_date)
            ]
            matches = subset.sort_values(by="m_timetag")
            if len(matches) > 0:
                row = matches.iloc[-1]
                fs = row.get("circulating_capital")
                if fs is not None and fs > 0:
                    gap_days = int((target_date - pd.Timestamp(row["m_timetag"])).days)
                    if gap_days > 90:
                        logger.warning(
                            "circulating_capital history gap >90 days",
                            context={
                                "stock": stock_code,
                                "target_date": target_date.strftime("%Y-%m-%d"),
                                "found_date": cast(pd.Timestamp, pd.Timestamp(row["m_timetag"])).strftime("%Y-%m-%d"),
                                "gap_days": gap_days,
                            },
                        )
                    return float(fs)

    if stock_code:
        df = _load_float_shares_map()
        if not df.empty:
            row = df[df["stock_code"] == stock_code]
            if len(row) > 0:
                fs = row.iloc[0].get("FloatVolume") or row.iloc[0].get("float_shares")  # v2 compat
                if fs is not None and fs > 0:
                    return float(fs)
        # P0-18 FIX: 有 stock_code 但找不到数据时抛异常，禁止静默回退 100 亿默认值
        logger.error(
            "float_shares missing",
            context={"stock": stock_code, "date": str(date)},
        )
        raise ValueError(
            f"float_shares missing for {stock_code}"
            f"{f' (date={date})' if date else ''}; "
            f"chip calculation cannot proceed with default"
        )

    # P0-18 FIX: stock_code=None 也不允许静默回退 —— 没有股票代码就无法查流通股本，
    # 使用 100 亿默认值会产生严重失真的筹码分布。调用方必须提供 stock_code。
    logger.error(
        "float_shares unavailable: stock_code not provided",
        context={"stock": stock_code, "date": str(date)},
    )
    raise ValueError(
        "float_shares unavailable: stock_code is required "
        "for chip calculation; cannot use 100亿 default"
    )


def _get_free_float_shares(stock_code: Optional[str] = None, date=None) -> float:
    """
    获取自由流通股本（freeFloatCapital）。

    查询逻辑：
    1. date is not None → 查 free_float_shares.parquet（Capital 财务表）
       → merge_asof: m_timetag <= target_date 的最新行
       → gap > 90 天：warning + 继续用旧值
    2. 查不到 → raise ValueError
       （不回退 FloatVolume：194 亿 vs 86 亿，不同口径）
    3. date is None → raise ValueError
       （get_instrument_detail 不返回 freeFloatCapital）
    """
    if stock_code and date is not None:
        ffs = _load_free_float_shares()
        if not ffs.empty:
            target_date = cast(pd.Timestamp, pd.Timestamp(date)).normalize()  # pyright: ignore[reportAttributeAccessIssue]
            subset = ffs.loc[
                (ffs["stock_code"] == stock_code) & (ffs["m_timetag"] <= target_date)
            ]
            matches = subset.sort_values(by="m_timetag")
            if len(matches) > 0:
                row = matches.iloc[-1]
                ff = row.get("freeFloatCapital")
                if ff is not None and ff > 0:
                    gap_days = int((target_date - pd.Timestamp(row["m_timetag"])).days)
                    if gap_days > 90:
                        logger.warning(
                            "freeFloatCapital history gap >90 days; using stale value "
                            "(free-float changes rarely, stale is better than switching to FloatVolume)",
                            context={
                                "stock": stock_code,
                                "target_date": target_date.strftime("%Y-%m-%d"),
                                "found_date": cast(pd.Timestamp, pd.Timestamp(row["m_timetag"])).strftime("%Y-%m-%d"),
                                "gap_days": gap_days,
                            },
                        )
                    return float(ff)

    raise ValueError(
        f"freeFloatCapital missing for {stock_code}"
        f"{f' (date={date})' if date else ''}"
        f"; FloatVolume fallback intentionally NOT used "
        f"(different metric: FloatVolume={194}亿 vs freeFloatCapital={86}亿 for 000001.SZ)"
    )


def _estimate_turnover(volume: np.ndarray, float_shares: Optional[float] = None) -> np.ndarray:
    """
    估算 turnover_rate。

    公式：turnover_rate = (volume * 100) / float_shares
    单位换算：volume（手） × 100 = 股 ÷ 流通股本（股）。

    Args:
        volume: 成交量数组（单位：手）
        float_shares: 流通股本（股）。为 None 时回退到 100 亿默认值。
                      P0-18 后主路径（adapt_columns→compute_chip_factors）已强制要求
                      stock_code 并 fail-close；None 分支仅服务于外部调用者
                      （chip_indicator TurnoverChipFactor 无 stock_code 时、chip_factor_analysis）。

    Returns:
        turnover_rate 数组（比例，0-1，非百分比）
    """
    if float_shares is None:
        logger.warning(
            "_estimate_turnover using 100亿 default float_shares; "
            "turnover_rate may be significantly distorted for small-cap stocks",
            context={},
        )
        fs = float(_FLOAT_SHARES_DEFAULT)
    else:
        fs = float_shares
    return (volume.astype(np.float64) * 100.0) / fs



 succeeded in 883ms:
"""
Author: hugo2046 shen.lan123@gmail.com
Date: 2023-03-27 15:02:44
LastEditors: hugo2046 shen.lan123@gmail.com
LastEditTime: 2023-03-29 10:50:17
Description: 计算筹码分布
"""
from typing import Any, Optional, Union, cast

import numpy as np
import pandas as pd
from loguru import logger
from numba import jit

from .distribution_of_chips import calc_adj_turnover, calc_triang_pdf, calc_uniform_pdf, make_price_grid

#################### 计算概率分布 ####################


def calc_curpdf(
    close: float,
    high: float,
    low: float,
    vol: float,
    min_p: Optional[float] = None,
    max_p: Optional[float] = None,
    step: float = 0.01,
    method: str = "triang",
) -> np.ndarray:
    """计算当日的curpdf

    Args:
        close (float): 收盘价
        high (float): 最高价
        low (float): 最低价
        vol (float): 成交量
        min_p (float): N日的最低价
        max_p (float): N日的最高价
        step (float): min_p至max_p的步长.Defaults to 0.01.
        method (str, optional): 计算概率分布的方法. Defaults to "triang".
            triang: 三角分布
            uniform: 平均分布

    Returns:
        np.ndarray: 成交量分布
    """
    method_norm = method.lower()

    if method_norm == "triang":

        return calc_triang_pdf(close, high, low, vol, min_p, max_p, step)

    elif method_norm == "uniform":

        return calc_uniform_pdf(close, high, low, vol, min_p, max_p, step)

    else:
        raise ValueError("method must be triang or uniform")


@jit(nopython=True)
def calc_cumpdf(curpdf: np.ndarray, turnover: np.ndarray, A: float = 1.0) -> np.ndarray:
    """计算N日累计的cumpdf

    Args:
        curpdf (np.ndarray): curpdf
        turnover (np.ndarray): 换手率
        A (float, optional): 系数. Defaults to 1.0.

    Returns:
        np.ndarray: 累计的vol (形状为 (N_prices,))
    """
    decay: np.ndarray = turnover * A
    diff: np.ndarray = 1 - decay

    mul_array: np.ndarray = (curpdf.T * decay).T
    size: int = len(turnover)
    cumpdf: np.ndarray = np.empty(size)
    for i in range(size):
        cumpdf = cumpdf * diff[i] + mul_array[i] if i else curpdf[i] * decay[i]

    return cumpdf


def calc_dist_chips(
    arr: Union[pd.DataFrame, np.ndarray], method: str, step: float = 0.01
) -> pd.Series:
    """计算筹码分布
       close也能是avg
    Args:
        arr (pd.DataFrame|np.ndarray): index-date columns - close|avg, high, low, vol, turnover_rate
        method (str): 计算分布的方法
            triang: 三角分布
            uniform: 平均分布
            turn_coeff: 换手率系数
    Returns:
        pd.Series: index-price, value-vol
    """
    if isinstance(arr, pd.DataFrame):
        frame = arr[["close", "high", "low", "vol", "turnover_rate"]]
        values = frame.to_numpy()
    else:
        values = np.asarray(arr)

    method_norm = method.lower()
    cum_vol: pd.Series

    if method_norm in {"triang", "uniform"}:

        # max_p,min_p可能区间为nan
        max_p: float = float(np.nanmax(values[:, 1]))
        min_p: float = float(np.nanmin(values[:, 2]))
        try:
            xs: np.ndarray = make_price_grid(min_p, max_p, step)
        except ValueError as e:
            logger.warning(f"min_p:{min_p}, max_p:{max_p};此段时间可能停牌,请检查")
            raise e

        try:
            curpdf: np.ndarray = np.apply_along_axis(
                lambda x: calc_curpdf(
                    x[0], x[1], x[2], x[3], min_p, max_p, step, method_norm
                ),
                1,
                values,
            )
        except Exception as e:
            print(min_p, max_p)
            raise e
        cum_vol_arr = calc_cumpdf(curpdf, values[:, 4])
        cum_vol = pd.Series(cum_vol_arr, index=xs)

    elif method_norm == "turn_coeff":

        turn_coeff: np.ndarray = calc_adj_turnover(values[:, 4])
        total_vol: float = float(values[:, 3].sum())
        coeff_series = pd.Series(
            data=turn_coeff,
            index=values[:, 1],
        )
        grouped = coeff_series.groupby(level=0).sum()
        cum_vol = pd.Series(grouped.to_numpy() * total_vol, index=grouped.index)

    else:
        raise ValueError(f"unknown method: {method}")

    return cum_vol


#################### 筹码分布因子 ####################


class ChipFactor:
    def __init__(
        self,
        close: float,
        cumpdf: pd.Series,
    ) -> None:

        self.close = close
        self.cumpdf = cumpdf  # 过去N日的成交分布

        self.cumpdf.index.names = ["price"]
        self.cumpdf.name = "cumpdf"

    @staticmethod
    def winsorize(cumpdf: pd.Series, scale: int = 3) -> pd.Series:

        std_val = float(cumpdf.std())
        mean_val = float(cumpdf.mean())

        return cumpdf.clip(mean_val - scale * std_val, mean_val + scale * std_val)

    def get_asr(self, lower: float = 0.9, upper: float = 1.1) -> float:
        """活动筹码

        当前价位上下10%的区间中筹码分布的所占比例
        ------
        该指标值很高时，说明股价处于筹码密集区，反之，当指标值很小时，说明当前股价处于无筹码的真空地带。
        如果近期股价上涨/下跌时该指标值较小，说明上下没有明显的支撑/阻力。
        """
        return self.get_winner(upper * self.close) - self.get_winner(lower * self.close)

    def get_cyqk_c(self) -> float:
        """盈利占比

        当前价位以下的筹码分布占比=getwinner(close)
        ------
        当盈利占比很高时，此时市场中大部分投资者都是处于盈利状态，该股票面临抛售压力。
        当没有大盘支撑和利好的基本面信息的情况下，该股票在市场上是会面临供大于求，根据供需理论，会导致股票价格的下跌。
        当盈利占比很低时，此时股票的价格也是处于历史比较低的价位。股票价格上涨的空间也比较大。
        """
        return self.get_winner(self.close)

    def get_ckdw(self, scale: int = 3) -> float:
        """成本重心

        成本重心CKDW=（平均成本价-最低成本价）/（最高成本价-最低成本价）
        ------
        当成本重心（筹码低位密集指标值）很小，筹码分布会呈现低位密集状态。一般股价放量突破单峰密集，会是一轮上涨行情的开始。

        为了避免极值影响,max/min经过三次正太分布winsorize获得
        """
        winsorize: pd.Series = self.cumpdf

        if scale is not None:
            # 当scale不为None时，对cumpdf进行winsorize
            winsorize: pd.Series = self.winsorize(winsorize, scale)
        # 平均成本
        mean: float = self.get_cost(0.5)
        min_p = float(cast(Any, winsorize.idxmin()))
        max_p = float(cast(Any, winsorize.idxmax()))

        return (mean - min_p) / (max_p - min_p)

    def get_prp(self) -> float:
        """价格相对位置

        价格相对位置PRP=(当前价格-平均成本) / 平均成本
        ------
        当价格相对位置指标值越小，当前所处的价位就越低。
        """

        # 平均成本
        avg: float = self.get_cost(0.5)

        return self.close / avg - 1

    def get_winner(self, price: float) -> float:
        """计算时某一价位的获利比例

        Args:
            price (float): 价格

        Returns:
            float: 获利比例
        """
        tot_cnt: float = self.cumpdf.sum()  # 总筹码数
        # P0-17 FIX: 空/损坏分布返回 NaN，禁止静默返回 0.0 伪装"0%获利盘"
        if tot_cnt <= 0 or len(self.cumpdf) == 0:
            return float("nan")
        # 累计筹码比例
        acc_cum: pd.Series = self.cumpdf / tot_cnt

        return acc_cum[acc_cum.index <= price].sum()

    def get_cost(self, winner_ratio: float) -> float:
        """给定累计获利比率winner_ratio,计算对应的价位,表示在此价位上winner_ratio的筹码处于获利状态

        Args:
            winner_ratio (float): 0~1之间的数值 表示累计获利比率

        Returns:
            float: 获利盘的价位
        """
        if (winner_ratio < 0) or (winner_ratio > 1):
            raise ValueError("winner_ratio must be in [0,1]")

        tot_cnt: float = self.cumpdf.sum()  # 总筹码数
        # P0-17 FIX: 空/损坏分布返回 NaN，避免 pandas 零除 warning + 隐式 NaN 传播
        if tot_cnt <= 0 or len(self.cumpdf) == 0:
            return float("nan")
        # 累计筹码比例
        acc_cum: pd.Series = (self.cumpdf / tot_cnt).cumsum()

        threshold_ser = cast(pd.Series, acc_cum[acc_cum < winner_ratio])
        if threshold_ser.empty:
            return float("nan")
        return float(cast(Any, threshold_ser.index[-1]))


exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "common/infra/data_root.py"' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "oskh_factors/chip/paths.py"' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1198ms:
# -*- coding: utf-8 -*-
"""Single-source data root resolution (M-003b · RFC-003).

Two containers — do not mix:

* Parquet hive + loose source files (``period=1d/1m``, adj/float/etf):
  ``resolve_parquet_container()`` / ``resolve_period_root()`` /
  ``resolve_source_parquet()``. With ``F:/stock_data/.authority`` and no env,
  this resolves to F (unset env is not a rollback).
* E workspace (duckdb, exp, skip JSON, stale marker):
  ``resolve_e_stock_data_container()`` / ``OSKH_DATA_ROOT``.
* TR bar input + ``tr_staging/`` share the parquet container (F when authority
  exists): ``resolve_turnover_resist_parquet_root()`` /
  ``resolve_tr_staging_dir()``. ``TURNOVER_RESIST_DATA_DIR`` is opt-in rollback.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Iterable, Optional, Set

AUTHORITY_MARKER_NAME = ".authority"
_DEFAULT_AUTHORITY_HINTS = (Path("F:/stock_data"),)
_AUTHORITY_WARNED: Set[str] = set()


def resolve_data_root(
    *,
    explicit_root: Optional[str] = None,
    env_var: Optional[str] = None,
    fallback_marker: str = "stock_data",
) -> Path:
    """Resolve repository/data root directory.

    Priority:
    1) explicit_root argument
    2) environment variable (default OSKH_DATA_ROOT)
    3) walk ``__file__`` parents until ``fallback_marker`` directory exists
    4) slim-fork fallback: this package's repo root (no ``main.py`` / local tree)
    """
    if explicit_root:
        return Path(explicit_root)
    if env_var is None:
        from common.infra.constants import EnvVarKeys

        env_var = EnvVarKeys.OSKH_DATA_ROOT
    env_root = os.environ.get(env_var)
    if env_root:
        return Path(env_root)
    p = Path(__file__).resolve().parent
    fallback: Path | None = None
    for ancestor in [p, *p.parents]:
        if not (ancestor / fallback_marker).is_dir():
            continue
        if (ancestor / "main.py").is_file():
            return ancestor
        if fallback is None:
            fallback = ancestor
    if fallback is not None:
        return fallback
    # Slim fork has no main.py and may not have a local stock_data/ tree.
    return Path(__file__).resolve().parents[2]


def authority_hint_roots() -> tuple[Path, ...]:
    """Roots that may hold the path-SSOT ``.authority`` marker (plan D7).

    Production default is ``F:/stock_data``. Tests may monkeypatch this
    function or set ``OSKH_AUTHORITY_HINT_ROOT`` (not a product env).
    """
    raw = str(os.environ.get("OSKH_AUTHORITY_HINT_ROOT") or "").strip()
    if raw:
        return (Path(raw),)
    return _DEFAULT_AUTHORITY_HINTS


def find_authority_marker(hints: Optional[Iterable[Path]] = None) -> Optional[Path]:
    """Return the first existing ``<hint>/.authority`` file, else None."""
    for hint in hints if hints is not None else authority_hint_roots():
        marker = Path(hint) / AUTHORITY_MARKER_NAME
        if marker.is_file():
            return marker
    return None


def reset_authority_fallback_warnings() -> None:
    """Test hook: clear the once-per-process D7 warning latch."""
    _AUTHORITY_WARNED.clear()


def resolve_e_stock_data_container(*, explicit_root: Optional[str] = None) -> Path:
    """E workspace ``stock_data/`` (duckdb / exp / skip JSON / stale marker).

    Always under ``OSKH_DATA_ROOT``; does not follow the F parquet authority flip.
    """
    return resolve_data_root(explicit_root=explicit_root) / "stock_data"


def resolve_turnover_resist_parquet_root(*, explicit_root: Optional[str] = None) -> Path:
    """Rust TR bridge parquet input container (same root as ``resolve_parquet_container``).

    Holds ``period=1d/`` hive plus float / free-float parquet. Rust reads parquet
    files, not DuckDB. DuckDB stays on E via ``resolve_e_stock_data_container``.

    Priority:
    1) explicit_root
    2) ``TURNOVER_RESIST_DATA_DIR`` (explicit override / rollback to old E path)
    3) ``resolve_parquet_container()``
    """
    if explicit_root:
        return Path(explicit_root)
    env = os.environ.get("TURNOVER_RESIST_DATA_DIR")
    if env:
        return Path(env)
    return resolve_parquet_container()


def resolve_tr_staging_dir(*, explicit_root: Optional[str] = None) -> Path:
    """Yearly TR backfill staging parquet (same F container as canonical)."""
    return resolve_turnover_resist_parquet_root(explicit_root=explicit_root) / "tr_staging"


def resolve_parquet_container(*, explicit_root: Optional[str] = None) -> Path:
    """Parquet-family container (period hive + loose source parquet).

    Priority:
    1) explicit_root
    2) ``OSKH_SOURCE_PARQUET_ROOT``
    3) ``<authority_marker_parent>`` when ``F:/stock_data/.authority`` (or hint) exists
    4) ``resolve_e_stock_data_container()`` (E default when no marker)
    """
    if explicit_root:
        return Path(explicit_root)
    from common.infra.constants import EnvVarKeys

    env_root = os.environ.get(EnvVarKeys.OSKH_SOURCE_PARQUET_ROOT)
    if env_root:
        return Path(env_root)
    marker = find_authority_marker()
    if marker is not None:
        return marker.parent
    return resolve_e_stock_data_container()


def _warn_authority_env_missing(*, env_key: str, resolved: Path) -> None:
    """Once-per-process hint when env unset but authority marker steered to F."""
    marker = find_authority_marker()
    if marker is None:
        return
    latch = f"{env_key}:{marker}"
    if latch in _AUTHORITY_WARNED:
        return
    _AUTHORITY_WARNED.add(latch)
    warnings.warn(
        f"path-SSOT authority marker present at {marker} but {env_key} is unset; "
        f"using {resolved} from marker parent. Set {env_key} explicitly to silence, "
        f"or set it to the E path to roll back. Unset alone is not a rollback.",
        UserWarning,
        stacklevel=3,
    )


def resolve_l2_parquet_root(*, explicit_root: Optional[str] = None) -> Path:
    """Resolve the L2 tick parquet root directory (single source for all L2 consumers).

    Priority:
    1) explicit_root argument
    2) ``OSKH_L2_PARQUET_ROOT`` env var (L2-specific override; e.g. ``F:\\stock_data\\l2_parquet``)
    3) ``resolve_parquet_container() / "l2_parquet"``

    Returns the path without checking existence (callers decide).
    """
    if explicit_root:
        return Path(explicit_root)
    from common.infra.constants import EnvVarKeys

    env_root = os.environ.get(EnvVarKeys.OSKH_L2_PARQUET_ROOT)
    if env_root:
        return Path(env_root)
    resolved = resolve_parquet_container() / "l2_parquet"
    _warn_authority_env_missing(
        env_key=EnvVarKeys.OSKH_L2_PARQUET_ROOT, resolved=resolved
    )
    return resolved


def resolve_period_root(
    period: str,
    *,
    explicit_root: Optional[str] = None,
    base: Optional[Path] = None,
) -> Path:
    """Resolve the parquet root for a given period (e.g. ``period=1m``).

    Priority:
    1) explicit_root argument
    2) ``OSKH_PERIOD_{PERIOD}_ROOT`` env var (period-specific override; e.g.
       ``OSKH_PERIOD_1M_ROOT=F:\\stock_data\\period=1m``)
    3) ``base / f"period={period}"`` if ``base`` given
    4) ``resolve_parquet_container() / f"period={period}"`` (default)

    Returns the period directory without checking existence. When the env var
    is set, ``base`` is ignored (override wins regardless of caller's base).
    """
    if explicit_root:
        return Path(explicit_root)
    env_key = f"OSKH_PERIOD_{period.upper()}_ROOT"
    env_root = os.environ.get(env_key)
    if env_root:
        return Path(env_root)
    if base is not None:
        return base / f"period={period}"
    resolved = resolve_parquet_container() / f"period={period}"
    _warn_authority_env_missing(env_key=env_key, resolved=resolved)
    return resolved


def resolve_source_parquet(
    name: str, *, explicit_root: Optional[str] = None
) -> Path:
    """Resolve a loose source-parquet file path (single source; plan-data-path-ssot D1).

    散装 parquet 源文件族（adj_factor.parquet / float_shares.parquet /
    free_float_shares.parquet / turnover_resistance_daily.parquet /
    ex_date_index.parquet / etf 目录等）——磁盘空间原因常与周期 parquet 同置
    另一块物理盘。

    Priority（与 ``resolve_period_root`` 同型）:
    1) explicit_root 参数（罕见；= 含文件族的容器目录）
    2) ``OSKH_SOURCE_PARQUET_ROOT`` env var（容器目录覆盖，如 ``F:/stock_data``）
    3) ``resolve_parquet_container()``（权威 marker 或 E 默认）

    不检查存在性（调用方 fail-visible：FileNotFoundError 带路径）。
    """
    if explicit_root:
        return Path(explicit_root) / name
    from common.infra.constants import EnvVarKeys

    env_root = os.environ.get(EnvVarKeys.OSKH_SOURCE_PARQUET_ROOT)
    if env_root:
        return Path(env_root) / name
    container = resolve_parquet_container()
    resolved = container / name
    _warn_authority_env_missing(
        env_key=EnvVarKeys.OSKH_SOURCE_PARQUET_ROOT, resolved=resolved
    )
    return resolved


 succeeded in 1044ms:
# -*- coding: utf-8 -*-
"""Stock table path resolution (RFC-003 §4.3 · M-003b)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from common.infra.data_root import resolve_data_root


def resolve_stock_data_root(*, explicit_root: Optional[str] = None) -> Path:
    return resolve_data_root(explicit_root=explicit_root)


def stock_data_path(filename: str, *, explicit_root: Optional[str] = None) -> Path:
    """散装 parquet 单源（plan-data-path-ssot D1）：默认经 resolve_source_parquet
    （honors OSKH_SOURCE_PARQUET_ROOT）；``explicit_root`` 保持 repo 根语义
    （root/stock_data/filename，测试/工具用）。"""
    if explicit_root:
        return resolve_stock_data_root(explicit_root=explicit_root) / "stock_data" / filename
    from common.infra.data_root import resolve_source_parquet

    return resolve_source_parquet(filename)


exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'rg -n "def |class |adapt_columns|as_of|adjust_type|resample|W-FRI|_daily_to_weekly|ChipFactor|cyqk|front|none|volume|停牌|SMA|open|TPlus1|LimitUp|comm|commission|cheat" backtest/research/chip_selection_backtest.py' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'rg -n "def |class |adapt_columns|as_of|adjust_type|front|none|volume|停牌|cyqk|CommInfo|cheat|TPlus1" backtest/research/chip_backtest.py | Select-Object -First 160' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 860ms:
52:from backtest.chip_algorithm import adapt_columns, daily_chip_distribution, minute_chip_distribution, cyq
53:from common.infra.data_root import resolve_source_parquet
63:def _get_reader():
83:        "filter": lambda df: df[(df["cyqk_c"] >= 0.2) & (df["cyqk_c"] <= 0.8)],
87:        "filter": lambda df: df[(df["cyqk_c"] >= 0.5) & (df["cyqk_c"] <= 1.0)],
91:        "filter": lambda df: df[df["cyqk_c"] <= 0.8],
95:        "filter": lambda df: df[df["cyqk_c"] >= 0.2],
103:class EqualWeightStrategy(bt.Strategy):
106:    def __init__(self):
109:    def next(self):
128:def load_data(code: str, bars: int = 120, reader=None) -> pd.DataFrame:
131:    df = reader.read_stock(code, period='1d', adjust_type='none')
140:def compute_chip_factor(code: str, freq: str = "1d", reader=None) -> dict:
145:        df = reader.read_stock(code, period='1m', adjust_type='none')
161:        arr = adapt_columns(df, stock_code=code)
167:        cf = cyq.ChipFactor(ct, dist)
170:            "cyqk_c": cf.get_cyqk_c(),
179:def run_backtest(codes: list, label: str, bars: int = 60, reader=None) -> dict:
183:    cerebro.broker.setcommission(commission=COMMISSION)
219:def main():
253:        chip_df = pd.DataFrame(results).sort_values("cyqk_c", ascending=False)
267:        chip_df = pd.DataFrame(results).sort_values("cyqk_c", ascending=False)
276:    print(f"\n  cyqk_c: median={chip_df['cyqk_c'].median():.3f}  "
277:          f"HIGH(>0.8)={(chip_df['cyqk_c']>0.8).sum()}  "
278:          f"LOW(<0.2)={(chip_df['cyqk_c']<0.2).sum()}  "
279:          f"MID[0.2-0.8]={((chip_df['cyqk_c']>=0.2)&(chip_df['cyqk_c']<=0.8)).sum()}")

 succeeded in 885ms:
40:from backtest.chip_algorithm import adapt_columns, daily_chip_distribution, minute_chip_distribution, cyq
54:class ChipFactorStrategy(bt.Strategy):
70:    def __init__(self):
82:        self.records = []  # (date, stock_code, cyqk_c, asr, ckdw, prp)
86:    def next(self):
93:            cyqk = float(chip.cyqk_c[0])
97:            if not all(np.isfinite(v) for v in (cyqk, asr_v, ckdw_v, prp_v)):
100:            self.records.append((dt, code, cyqk, asr_v, ckdw_v, prp_v))
108:def _get_reader():
115:def code_to_data(code: str, freq: str = "1d", reader=None) -> pd.DataFrame:
120:    df = reader.read_stock(code, start_time='20000101', period=freq, adjust_type='none')
145:def load_stock_pool(date_str: str) -> list:
168:def main():
222:                arr = adapt_columns(df, stock_code=code)
229:                    "cyqk_c": cf.get_cyqk_c(),
267:            columns=["date", "stock_code", "cyqk_c", "asr", "ckdw", "prp"],
280:    df_latest = df_latest.sort_values("cyqk_c", ascending=False)
285:        cyqk = row["cyqk_c"]
287:        if cyqk > 0.8:
289:        elif cyqk < 0.2:
291:        print(f"{row['stock_code']:<14} {cyqk:8.4f} {row['asr']:8.4f} "
295:    for col in ["cyqk_c", "asr", "ckdw", "prp"]:

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'rg -rn "hive|dividend_type|period=1d|read_stock|read_stock_bars|read_daily|load_daily" common oskh_data backtest --glob "*.py" | Select-Object -First 120' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'rg -n "def read_stock|def __init__|adjust_type|period|start_time|end_time" oskh_data/reader.py | Select-Object -First 80' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1354ms:
oskh_data\adj_factor.py:        str(base / "n=front"),
oskh_data\adj_factor.py:        str(base / "n=back"),
oskh_data\adj_factor.py:        str(base / "n=none"),
backtest\backtest_main_full.py:from qmt_utils_adv import to_datetime, n_codes, batch_format_stock_codes, load_single_stock_data, \
backtest\backtest_main_full.py:            stock_df = n_codes(file_path)
backtest\chip_indicator.py:                daily_df = daily_reader.n(
common\infra\constants.py:    # Paper/ops: arcn reconnect JSON when a new OS process starts (INSTANCE_ID shard unchanged).
common\infra\data_root.py:* Parquet n + loose source files (``n/1m``, adj/float/etf):
common\infra\data_root.py:    Holds ``n/`` n plus float / free-float parquet. Rust reads parquet
common\infra\data_root.py:    """Parquet-family container (period n + loose source parquet).
backtest\portfolio_manager.py:from qmt_utils_adv import n_codes, batch_format_stock_codes, get_stock_data_from_cache, to_datetime, is_close
backtest\rolling_investment_strategy.py:from qmt_utils_adv import n_codes, batch_format_stock_codes, is_trading_day, to_datetime, is_close
oskh_data\seed_missing_front.py:This helper copies ``n=none/.../data.parquet`` → ``front/...`` for
oskh_data\seed_missing_front.py:        / f"n={adjust_type}"
oskh_data\integrity.py:    n_codes,
oskh_data\integrity.py:        df = n_codes(str(file_path))
oskh_data\repair_daily_parquet_schema.py:"""Repair 1d n parquet column type drift (esp. volume float64→int64).
oskh_data\repair_daily_parquet_schema.py:        period_dir = resolve_period_root(period) / f"n={adj}"
oskh_data\freshness.py:            resolve_period_root('1d') / 'n=none' /
oskh_data\daily_parquet_write.py:never used to write n files.
oskh_data\daily_parquet_write.py:# Canonical Arrow/pandas dtypes for 1d n (rebuild schema gate uses the same contract).
oskh_data\daily_parquet_write.py:    """Cast a daily n table to ``CANONICAL_ARROW_TYPES`` (volume→int64, etc.)."""
oskh_data\daily_parquet_write.py:    d = period_root / f"n={adjust_type}" / f"symbol={part}"
oskh_data\daily_parquet_write.py:    """Read one n file via ``ParquetFile`` (not ``pq.read_table``).
oskh_data\daily_parquet_write.py:    ``pq.read_table(path)`` may open a Dataset over the parent n tree and
oskh_data\daily_parquet_write.py:    """Write downloader ``processed_data`` map to n partitions."""
oskh_data\daily_parquet_write.py:        / "n=none" / "symbol=*" / "data.parquet"
oskh_data\reader.py:        # DuckDB 与运营文件仍在 E 容器；parquet n 经 _parquet_container + resolver。
oskh_data\reader.py:        df = self.n(
oskh_data\reader.py:    def n(
oskh_data\reader.py:                "StockDataReader.n(as_of_date=...) is not implemented yet; "
oskh_data\reader.py:                return self._n_parquet(stock_code, start_time, end_time,
oskh_data\reader.py:                return self._n_parquet(stock_code, start_time, end_time,
oskh_data\reader.py:            return self._n_persistent(stock_code, start_time, end_time, columns, con)
oskh_data\reader.py:            return self._n_parquet(stock_code, start_time, end_time,
oskh_data\reader.py:        period_dir = _resolve_period_root(period, base=base) / f'n={adjust_type}'
oskh_data\reader.py:                n_partitioning=1,
oskh_data\reader.py:                    _resolve_period_root('1m', base=base) / 'n=none' / 'symbol=*' / 'data.parquet'
oskh_data\reader.py:                                      n_partitioning=1, union_by_name=True)
oskh_data\reader.py:    def _n_parquet(self, stock_code, start_time, end_time,
oskh_data\reader.py:                   f'n={adjust_type}' / '*' / 'data.parquet').replace('\\', '/')
oskh_data\reader.py:        sql = f"{select_clause} FROM read_parquet('{glob}', n_partitioning=1)"
oskh_data\reader.py:    def _n_persistent(self, stock_code, start_time, end_time, columns, con):
oskh_data\reader.py:                f'n={adjust_type}' / f'symbol={safe}' / 'data.parquet')
oskh_data\reader.py:    full_dir = _resolve_period_root(period) / f'n={adjust_type}'
oskh_data\reader.py:    period_dir = _resolve_period_root(period) / f"n={adjust_type}"
oskh_data\reader.py:    period_dir = resolve_period_root('1d') / 'n=front'
backtest\qmt_utils_adv.py:    n_codes,
backtest\qmt_utils_adv.py:    "n_codes",
backtest\qmt_utils_adv.py:    """Load one symbol's 1m bars into a Cerebro feed (SSOT cache, no cwd n)."""
oskh_data\etf_local_bars.py:            df = reader.n(
oskh_data\etf_local_bars.py:            "ETF n failed; fund_daily returns empty",
oskh_data\period_schema.py:"""Period / adjust-type helpers for local n reads (no QMT download)."""
oskh_data\period_schema.py:    """Time-range checks for local n reads."""
oskh_data\parquet_meta.py:    """Return the latest date in a n parquet via pyarrow metadata, or None."""
common\integrations\duckdb_daily_bars_adapter.py:                df = reader.n(
backtest\research\chip_factor_analysis.py:    df = reader.n(code, period='1d', adjust_type='front')
backtest\research\chip_backtest.py:    df = reader.n(code, start_time='20000101', period=freq, adjust_type='none')
backtest\research\daily_chip_logger.py:    df = reader.n(code, period=freq, adjust_type='none')
backtest\StockStatus.py:from qmt_utils_adv import n_codes, batch_format_stock_codes, get_stock_data_from_cache,to_datetime,is_close
backtest\research\chip_selection_backtest.py:    df = reader.n(code, period='1d', adjust_type='none')
backtest\research\chip_selection_backtest.py:        df = reader.n(code, period='1m', adjust_type='none')
backtest\research\evaluate_turnover_chip_factors.py:    df = reader.n(code, period='1d', adjust_type='front')
backtest\research\filter_chip_stocks.py:    front_dir = str(resolve_period_root("1d") / "n=front")
backtest\research\filter_chip_stocks.py:    df = reader.n(code, start_time='20000101', end_time=date_str,
backtest\research\filter_stock_pool_by_chip.py:    df = reader.n(code, period='1d', adjust_type='front')
backtest\research\ma_chip_edge_backtest.py:def _list_front_n_codes() -> set[str]:
backtest\research\ma_chip_edge_backtest.py:    root = resolve_period_root("1d") / "n=front"
backtest\research\ma_chip_edge_backtest.py:    pool = _list_float_codes() & _list_front_n_codes()
backtest\research\ma_chip_edge_backtest.py:        df = reader.n(
common\infra\timekeeping.py:    """UTC wall time YYYYMMDD_HHMMSS for arcn filenames (no microseconds)."""
common\infra\qmt_utils_adv.py:# E workspace (duckdb / ops). Parquet n is resolved inside StockDataReader.
common\infra\qmt_utils_adv.py:# RF-R2: lazy StockDataReader instances keyed by base_dir (parquet mode, same n as legacy).
common\infra\qmt_utils_adv.py:    return reader.n(
common\infra\qmt_utils_adv.py:                    adjust_path = period_path / f"n={adjust_type}"
common\infra\qmt_utils_adv.py:    def n_codes(file_path: str) -> Optional[pd.DataFrame]:
common\infra\qmt_utils_adv.py:            logger.error("n_codes failed for %s: %s", file_path, exc)
common\infra\qmt_utils_adv.py:def n_codes(file_path: str) -> Optional[pd.DataFrame]:
common\infra\qmt_utils_adv.py:    return StockCodeProcessor.n_codes(file_path)
common\infra\qmt_utils_adv.py:    """Load OHLCV from local n. RF-R2: default routes through ``oskh_data.StockDataReader``."""
backtest\research\rolling_ic_chip_factors.py:    df = reader.n(code, period='1d', adjust_type='front')
backtest\research\verify_adj_minute_chip.py:MINUTE_DIR = str(resolve_period_root("1m") / "n=none")
backtest\research\verify_adj_minute_chip.py:        df_d = reader.n(code, period='1d', adjust_type='front')
backtest\research\verify_adj_minute_chip.py:        df_m = reader.n(code, period='1m', adjust_type='none')
backtest\research\verify_cerebro_chip.py:    df = reader.n("000001.SZ", period='1d', adjust_type='none')
backtest\research\verify_chip_factor_consistency.py:MINUTE_DIR = str(resolve_period_root("1m") / "n=none")
backtest\research\verify_chip_factor_consistency.py:DAILY_DIR = str(resolve_period_root("1d") / "n=front")
backtest\research\verify_chip_factor_consistency.py:        df = reader.n(code, period='1m', adjust_type='none')
backtest\research\verify_chip_factor_consistency.py:        df = reader.n(code, period='1d', adjust_type='front')
backtest\research\verify_chip_pool_enhancement.py:    df = reader.n(code, period='1d', adjust_type='front')
backtest\research\verify_chip_pool_enhancement.py:    df = reader.n(code, period='1d', adjust_type='front')
backtest\research\verify_float_shares_time_dimension_baseline.py:DAILY_DIR = str(resolve_period_root("1d") / "n=front")
backtest\research\verify_float_shares_time_dimension_baseline.py:def _n(code: str, bars: int, start: Optional[str], end: Optional[str]) -> Optional[pd.DataFrame]:
backtest\research\verify_float_shares_time_dimension_baseline.py:        df = _n(code, bars=bars, start=start, end=end)
backtest\research\verify_minute_chip.py:    df_min = reader.n(STOCK_CODE, period='1m', adjust_type='none')
backtest\research\verify_minute_chip.py:    df_day = reader.n(STOCK_CODE, period='1d', adjust_type='none')
backtest\research\verify_mvp_min.py:PARQUET_DIR = str(resolve_period_root("1d") / "n=none")
backtest\research\verify_mvp_min.py:    df = reader.n(stock_code, period='1d', adjust_type='none')

 succeeded in 1299ms:
31:from common.infra.data_root import resolve_period_root as _resolve_period_root
109:def _enforce_adjust_type_policy(adjust_type: str) -> None:
112:    交易热路径（live_trading.* / trade_decision.*）必须使用 adjust_type="none"，
113:    白名单模块（如 MA 指标提供者）除外。若调用方未找到且 adjust_type != "none"，
116:    if adjust_type == 'none':
122:            f"for non-none adjust_type='{adjust_type}'"
127:                "adjust_type_policy_violation",
130:                    "adjust_type": adjust_type,
131:                    "policy": "交易热路径必须使用 adjust_type='none'",
136:                f"must use adjust_type='none', got '{adjust_type}' "
144:    def __init__(
241:        """根据 asset_type 和 adjust_type 返回 DuckDB 文件路径。
245:        默认（无 adjust_type 上下文时）: 自动探测可用的 DuckDB，避免因 stock_data.duckdb
271:    def _adjust_db_path(self, adjust_type: str) -> Optional[Path]:
278:            adj = str(adjust_type or 'none').strip().lower()
282:        suffix = _ADJUST_DB_SUFFIX.get(adjust_type, '_none')
293:        period: str = '1d',
294:        adjust_type: str = 'front',
305:            period: 数据周期
306:            adjust_type: 复权类型
315:            start_time=timestamp_strftime(target_ts - pd.Timedelta(days=400), '%Y%m%d'),
316:            end_time=target_date,
317:            period=period,
318:            adjust_type=adjust_type,
322:            return False, f"{stock_code}: {period}/{adjust_type} 返回空数据"
329:                f"{stock_code}: {period}/{adjust_type} 最新日期为 {timestamp_strftime(max_date, '%Y-%m-%d')}，"
351:                f"{stock_code}: {period}/{adjust_type} 窗口内仅 {expected_trading_days} 个 SSE 交易日，"
356:            f"{stock_code}: {period}/{adjust_type} 覆盖 {target_date}"
360:    def read_stock(
363:        start_time: Optional[str] = None,
364:        end_time: Optional[str] = None,
365:        period: str = '1d',
366:        adjust_type: str = 'front',
383:            _enforce_adjust_type_policy(adjust_type)
384:        if period in MINUTE_PERIODS:
385:            adjust_type = 'none'
389:                return self._read_stock_parquet(stock_code, start_time, end_time,
390:                                                period, adjust_type, columns)
391:            con = self._get_persistent_con(period, adjust_type)
393:                return self._read_stock_parquet(stock_code, start_time, end_time,
394:                                                period, adjust_type, columns)
395:            return self._read_stock_persistent(stock_code, start_time, end_time, columns, con)
397:            return self._read_stock_parquet(stock_code, start_time, end_time,
398:                                            period, adjust_type, columns)
403:        start_time: Optional[str] = None,
404:        end_time: Optional[str] = None,
405:        period: str = '1d',
406:        adjust_type: str = 'front',
420:        if period in MINUTE_PERIODS:
421:            adjust_type = 'none'
424:            return self._scan_parquet(stock_codes, start_time, end_time,
425:                                      period, adjust_type, columns)
427:            if period in MINUTE_PERIODS:
428:                return self._scan_parquet(stock_codes, start_time, end_time,
429:                                          period, adjust_type, columns)
430:            return self._scan_duckdb(stock_codes, start_time, end_time,
431:                                     period, adjust_type, columns)
434:                return self._scan_parquet(stock_codes, start_time, end_time,
435:                                          period, adjust_type, columns)
436:            con = self._get_persistent_con(period, adjust_type)
438:                return self._scan_parquet(stock_codes, start_time, end_time,
439:                                          period, adjust_type, columns)
440:            return self._scan_persistent(stock_codes, start_time, end_time, columns, con)
447:        period: str = '1d',
448:        adjust_type: str = 'front',
455:        period='1d':
459:        period='1m' → :memory: + read_parquet(glob) 视图（不再使用持久化 .duckdb）
467:        suffix = _ADJUST_DB_SUFFIX.get(adjust_type, '_none')
469:            base / f'stock_data{"_minute" if period == "1m" else ""}{suffix if period != "1m" else ""}.duckdb'
476:        style = _detect_style(base, period, adjust_type)
477:        period_dir = _resolve_period_root(period, base=base) / f'dividend_type={adjust_type}'
478:        glob_pattern = str(period_dir / '*' / 'data.parquet').replace('\\', '/')
479:        _validate_parquet_schema_consistency(base, period=period, adjust_type=adjust_type)
493:        _sample_files = sorted(period_dir.glob("symbol=*/data.parquet"))
560:    def _get_persistent_con(self, period: str, adjust_type: str = 'front'):
561:        """返回 period 对应的持久化连接。分钟线使用 :memory: + read_parquet(glob) 视图。"""
562:        if period in MINUTE_PERIODS:
569:                    _resolve_period_root('1m', base=base) / 'dividend_type=none' / 'symbol=*' / 'data.parquet'
587:        adjust_db = self._adjust_db_path(adjust_type)
592:                f"Persistent DB not found for adjust_type={adjust_type} ({adjust_db}); falling back to parquet for correctness"

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "backtest/research/ma_chip_edge_backtest.py"' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "git -C \"E:\\PycharmProjects\\MyQuant-backtrader\" status --short; git -C \"E:\\PycharmProjects\\MyQuant-backtrader\" log --oneline -5 -- backtest/research/ma_chip_edge_backtest.py" in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1090ms:
#!/usr/bin/env python3
"""均线 + 盈筹率边缘买入试验（plan v2）。

T = 信号日的下一根交易日：在日 D 收盘确认 cond[D] 且 cond[D-1] 有限为假，
于 D+1 开盘买入。买入日收盘 <= T-1 收盘则次日开盘卖；否则收到收盘 < SMA5
的次日开盘卖。买入日不挂卖。涨跌停/停牌不成交。

用法：
    python backtest/research/ma_chip_edge_backtest.py --seed 20240907 --start 20240101
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)

import backtrader as bt

from backtest.chip_algorithm import adapt_columns, daily_chip_distribution, cyq
from common.infra.data_root import resolve_period_root, resolve_source_parquet
from oskh_data import StockDataReader
from oskh_data.symbol_format import to_canonical_symbol

CHIP_WINDOW = 80
WEEK_RULE = "W-FRI"
CYQK_TH = 0.70
LOAD_START = "20220701"
DEFAULT_SEED = 20240907
DEFAULT_CASH = 1_000_000.0


def board_of(code: str) -> Optional[str]:
    num, _, exch = code.partition(".")
    if exch == "SH" and num.startswith("688"):
        return None
    if exch == "SH" and num.startswith("60"):
        return "sh_main"
    if exch == "SZ" and num.startswith(("000", "001", "002", "003")):
        return "sz_main"
    if exch == "SZ" and num.startswith(("300", "301")):
        return "chinext"
    return None


def limit_pct(code: str) -> float:
    num = "".join(c for c in code if c.isdigit())
    if num.startswith(("300", "301", "688")):
        return 0.20
    return 0.10


def is_limit_open(code: str, open_px: float, prev_close: float, *, up: bool) -> bool:
    if not np.isfinite(open_px) or not np.isfinite(prev_close) or prev_close <= 0:
        return False
    pct = limit_pct(code)
    target = round(prev_close * (1 + pct if up else 1 - pct), 2)
    return abs(open_px - target) <= 0.01 + 1e-9


def week_ma20_asof(close: pd.Series) -> pd.Series:
    """20 周均线，asof 键为该周最后交易日（无未来价）。"""
    daily = pd.DataFrame({"close": close.to_numpy(), "_last_day": close.index}, index=close.index)
    weekly = daily.resample(WEEK_RULE).agg({"close": "last", "_last_day": "max"}).dropna()
    weekly["ma20"] = weekly["close"].rolling(20, min_periods=20).mean()
    w_last = weekly["_last_day"].tolist()
    w_ma = weekly["ma20"].to_numpy(dtype=np.float64)
    out = np.full(len(close), np.nan, dtype=np.float64)
    wi = 0
    for i, d in enumerate(close.index):
        while wi < len(w_last) and w_last[wi] <= d:
            wi += 1
        if wi > 0:
            out[i] = w_ma[wi - 1]
    return pd.Series(out, index=close.index)


def cyqk_series(df: pd.DataFrame, stock_code: str, window: int = CHIP_WINDOW) -> pd.Series:
    """截至当日（含）的 80 日筹码盈筹率，股本 as_of 当天。"""
    n = len(df)
    out = np.full(n, np.nan, dtype=np.float64)
    closes = df["close"].to_numpy(dtype=np.float64)
    for i in range(window - 1, n):
        sl = df.iloc[i - window + 1 : i + 1]
        as_of = pd.Timestamp(df.index[i])
        try:
            arr = adapt_columns(sl, stock_code=stock_code, as_of_date=as_of)
            dist = daily_chip_distribution(arr)
            out[i] = float(cyq.ChipFactor(float(closes[i]), dist).get_cyqk_c())
        except Exception:
            out[i] = np.nan
    return pd.Series(out, index=df.index)


def build_signal_frame(df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
    """给日线 OHLCV 加上均线、盈筹率、finite、cond、edge。"""
    out = df.copy()
    close = out["close"]
    out["sma5"] = close.rolling(5, min_periods=5).mean()
    out["sma20"] = close.rolling(20, min_periods=20).mean()
    out["sma60"] = close.rolling(60, min_periods=60).mean()
    out["week_ma20"] = week_ma20_asof(close)
    out["cyqk"] = cyqk_series(out, stock_code)
    finite = (
        np.isfinite(out["sma20"])
        & np.isfinite(out["sma60"])
        & np.isfinite(out["week_ma20"])
        & np.isfinite(out["cyqk"])
    )
    cond = finite & (close > out["sma20"]) & (close > out["sma60"]) & (
        close > out["week_ma20"]
    ) & (out["cyqk"] > CYQK_TH)
    prev_cond = cond.shift(1)
    prev_finite = finite.shift(1)
    edge = cond & (prev_cond == False) & prev_finite.fillna(False)  # noqa: E712
    out["finite"] = finite
    out["cond"] = cond
    out["edge"] = edge
    return out


class SignalPandasData(bt.feeds.PandasData):
    lines = ("sma5", "edge")
    params = (
        ("datetime", None),
        ("open", -1),
        ("high", -1),
        ("low", -1),
        ("close", -1),
        ("volume", -1),
        ("sma5", -1),
        ("edge", -1),
    )


class AShareCommInfo(bt.CommInfoBase):
    params = (
        ("commission", 0.00005),
        ("min_commission", 5.0),
        ("stamp_tax", 0.0005),
        ("stocklike", True),
        ("commtype", bt.CommInfoBase.COMM_PERC),
        ("percabs", True),
    )

    def _getcommission(self, size, price, pseudoexec):
        notional = abs(size) * price
        comm = max(notional * self.p.commission, self.p.min_commission)
        if size < 0:
            comm += notional * self.p.stamp_tax
        return comm


@dataclass
class RunResult:
    code: str
    board: str
    trades: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    equity_end: float = DEFAULT_CASH
    n_buys: int = 0
    skipped: bool = False
    skip_reason: str = ""


class MaChipEdgeStrategy(bt.Strategy):
    params = (("stock_code", ""),)

    def __init__(self):
        self.pending_buy = False
        self.pending_sell = False
        self.hold_mode: Optional[str] = None
        self.buy_ref_close: Optional[float] = None
        self.trades: list[dict] = []
        self.events: list[dict] = []
        self._entry_price = 0.0

    def _dt(self) -> date:
        return self.data.datetime.date(0)

    def next(self):
        code = self.p.stock_code
        o = float(self.data.open[0])
        c = float(self.data.close[0])
        vol = float(self.data.volume[0])
        sma5 = float(self.data.sma5[0])
        prev_c = float(self.data.close[-1]) if len(self.data) > 1 else np.nan
        d = self._dt().isoformat()

        if self.pending_sell and self.position:
            if vol <= 0 or is_limit_open(code, o, prev_c, up=False):
                self.events.append({"date": d, "code": code, "event": "skip_sell", "open": o})
            else:
                self.sell(size=self.position.size)
                self.trades.append(
                    {
                        "date": d,
                        "code": code,
                        "side": "SELL",
                        "price": o,
                        "size": int(self.position.size),
                    }
                )
            self.pending_sell = False
            self.hold_mode = None
            self.buy_ref_close = None

        if self.pending_buy and not self.position:
            if vol <= 0 or is_limit_open(code, o, prev_c, up=True):
                self.events.append({"date": d, "code": code, "event": "skip_buy", "open": o})
            else:
                size = int(self.broker.getcash() / o / 100.0) * 100
                if size >= 100:
                    self.buy(size=size)
                    self.hold_mode = "first_day"
                    self.buy_ref_close = prev_c
                    self._entry_price = o
                    self.trades.append(
                        {"date": d, "code": code, "side": "BUY", "price": o, "size": size}
                    )
            self.pending_buy = False

        if self.hold_mode == "first_day" and self.position:
            if self.buy_ref_close is not None and c <= self.buy_ref_close:
                self.pending_sell = True
            else:
                self.hold_mode = "ma5"
        elif self.hold_mode == "ma5" and self.position:
            if np.isfinite(sma5) and c < sma5:
                self.pending_sell = True

        if len(self.data) < 2:
            return
        if (not self.position) and (not self.pending_sell) and float(self.data.edge[0]) > 0.5:
            self.pending_buy = True


def _list_float_codes() -> set[str]:
    path = resolve_source_parquet("float_shares.parquet")
    if not path.is_file():
        return set()
    s = pd.read_parquet(path, columns=["stock_code"])["stock_code"].astype(str)
    return {to_canonical_symbol(x.replace(".", "_")) if "." not in x else x for x in s}


def _list_front_hive_codes() -> set[str]:
    root = resolve_period_root("1d") / "dividend_type=front"
    if not root.is_dir():
        return set()
    out: set[str] = set()
    for p in root.iterdir():
        if p.name.startswith("symbol=") and (p / "data.parquet").is_file():
            out.add(to_canonical_symbol(p.name[len("symbol=") :]))
    return out


def candidates_by_board(seed: int) -> dict[str, list[str]]:
    pool = _list_float_codes() & _list_front_hive_codes()
    rng = np.random.default_rng(seed)
    out: dict[str, list[str]] = {}
    for board in ("sz_main", "sh_main", "chinext"):
        cands = [c for c in pool if board_of(c) == board]
        cands.sort()
        rng.shuffle(cands)
        out[board] = cands
    return out


def load_front_daily(code: str, start: str, end: str) -> Optional[pd.DataFrame]:
    reader = StockDataReader(mode="parquet")
    try:
        df = reader.read_stock(
            code,
            start_time=start,
            end_time=end,
            period="1d",
            adjust_type="front",
        )
    finally:
        reader.close()
    if df is None or df.empty:
        return None
    if not isinstance(df.index, pd.DatetimeIndex):
        if "time" in df.columns:
            df = df.set_index(pd.to_datetime(df["time"]))
        else:
            return None
    df = df.sort_index()
    need = {"open", "high", "low", "close", "volume"}
    if not need.issubset(df.columns):
        return None
    return df[list(need)].astype(np.float64)


def ready_for_stats(sig: pd.DataFrame, stats_start: pd.Timestamp) -> bool:
    pre = sig.loc[sig.index < stats_start]
    if pre.empty:
        return False
    return bool(pre["finite"].any())


def run_one(code: str, board: str, sig: pd.DataFrame, stats_start: pd.Timestamp, cash: float) -> RunResult:
    warmup_from = stats_start - pd.Timedelta(days=14)
    feed_df = sig.loc[sig.index >= warmup_from].copy()
    feed_df = feed_df.dropna(subset=["open", "close"])
    feed_df["edge"] = feed_df["edge"].astype(float)
    feed_df["sma5"] = feed_df["sma5"].astype(float)
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.setcash(cash)
    cerebro.broker.set_coo(True)
    cerebro.broker.addcommissioninfo(AShareCommInfo())
    data = SignalPandasData(dataname=feed_df)
    cerebro.adddata(data, name=code)
    cerebro.addstrategy(MaChipEdgeStrategy, stock_code=code)
    strat = cerebro.run()[0]
    return RunResult(
        code=code,
        board=board,
        trades=list(strat.trades),
        events=list(strat.events),
        equity_end=float(cerebro.broker.getvalue()),
        n_buys=sum(1 for t in strat.trades if t["side"] == "BUY"),
    )


def _write_report(out_dir: Path, universe: pd.DataFrame, results: list[RunResult], stats: pd.DataFrame) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    universe.to_csv(out_dir / "universe.csv", index=False, encoding="utf-8")
    trades = [t for r in results for t in r.trades]
    events = [e for r in results for e in r.events]
    pd.DataFrame(trades).to_csv(out_dir / "trades.csv", index=False, encoding="utf-8")
    pd.DataFrame(events).to_csv(out_dir / "events.csv", index=False, encoding="utf-8")
    stats.to_csv(out_dir / "per_stock_stats.csv", index=False, encoding="utf-8")
    n_trig = int((stats["n_buys"] > 0).sum()) if len(stats) else 0
    eq = float(stats["ret"].mean()) if len(stats) else float("nan")
    lines = [
        "# ma_chip_edge trial",
        "",
        "框架试验，不论证因子有效。",
        "",
        f"- names: {len(stats)}",
        f"- names_with_buy: {n_trig}",
        f"- mean_single_name_return: {eq:.4f}" if np.isfinite(eq) else "- mean_single_name_return: nan",
        f"- skip_events: {len(events)}",
        "",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main(argv: Optional[Iterable[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="MA + cyqk_c edge entry trial (plan v2)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--start", default="20240101", help="stats window start YYYYMMDD")
    ap.add_argument("--end", default="", help="YYYYMMDD, default today")
    ap.add_argument("--per-board", type=int, default=10)
    ap.add_argument("--cash", type=float, default=DEFAULT_CASH)
    ap.add_argument("--codes", default="", help="comma codes, skip random sample")
    args = ap.parse_args(list(argv) if argv is not None else None)

    end = args.end or date.today().strftime("%Y%m%d")
    stats_start = pd.Timestamp(args.start)
    results: list[RunResult] = []
    stat_rows = []
    used = []

    def _try_code(code: str, board: str) -> Optional[RunResult]:
        raw = load_front_daily(code, LOAD_START, end)
        if raw is None or len(raw) < CHIP_WINDOW + 60:
            return None
        sig = build_signal_frame(raw, code)
        if not ready_for_stats(sig, stats_start):
            return None
        return run_one(code, board, sig, stats_start, args.cash)

    if args.codes:
        for code in [c.strip() for c in args.codes.split(",") if c.strip()]:
            board = board_of(code) or "other"
            run = _try_code(code, board)
            if run is None:
                results.append(RunResult(code, board, skipped=True, skip_reason="unusable"))
                continue
            results.append(run)
            used.append({"code": code, "board": board, "replaced": False})
            stat_rows.append(
                {
                    "code": code,
                    "board": board,
                    "n_buys": run.n_buys,
                    "n_trades": len(run.trades),
                    "n_skips": len(run.events),
                    "equity_end": run.equity_end,
                    "ret": run.equity_end / args.cash - 1.0,
                }
            )
    else:
        cands = candidates_by_board(args.seed)
        for board, codes in cands.items():
            got = 0
            for code in codes:
                if got >= args.per_board:
                    break
                run = _try_code(code, board)
                if run is None:
                    continue
                results.append(run)
                used.append({"code": code, "board": board, "replaced": False})
                stat_rows.append(
                    {
                        "code": code,
                        "board": board,
                        "n_buys": run.n_buys,
                        "n_trades": len(run.trades),
                        "n_skips": len(run.events),
                        "equity_end": run.equity_end,
                        "ret": run.equity_end / args.cash - 1.0,
                    }
                )
                got += 1

    out_dir = Path(REPO) / "backtest_output" / f"ma_chip_edge_{args.seed}_{end}"
    stats = pd.DataFrame(stat_rows)
    _write_report(out_dir, pd.DataFrame(used), results, stats)
    print(f"wrote {out_dir}")
    print(stats.to_string(index=False) if len(stats) else "no names ran")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


 succeeded in 1309ms:
warning: unable to access 'C:\Users\Thinkpad/.config/git/ignore': Permission denied
warning: unable to access 'C:\Users\Thinkpad/.config/git/ignore': Permission denied
warning: could not open directory '.pytest_cache/': Permission denied
?? backtest/research/ma_chip_edge_backtest.py
?? docs/architecture/
?? docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md
?? docs/engineering/
?? docs/prompts/
?? scripts/run/

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "D:\\anaconda3\\envs\\vanna312\\python.exe -c \"import backtrader as bt, inspect, os; print(bt.__version__); print(os.path.dirname(inspect.getfile(bt)))\"" in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "Get-ChildItem -LiteralPath \"F:\\stock_data\" -ErrorAction SilentlyContinue | Select-Object Name, Mode; \"----period=1d----\"; Get-ChildItem -LiteralPath \"F:\\stock_data\\period=1d\" -ErrorAction SilentlyContinue | Select-Object Name; \"----div front----\"; Get-ChildItem -LiteralPath \"F:\\stock_data\\period=1d\\dividend_type=front\" -ErrorAction SilentlyContinue | Select-Object -First 8 Name" in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1422ms:

Name                                      Mode
----                                      ----
etf                                       d----
l2_parquet                                d----
period=1d                                 d----
period=1m                                 d----
tr_staging                                d----
.authority                                -a---
.ex_date_changed_20260903.txt             -a---
.run_daily_adjusted_fast_20260903.log     -a---
.step1_download_complete_20260903         -a---
.step1_front_complete_20260903            -a---
.update_adjusted_daily_skip_20260903.json -a---
adj_factor.meta.json                      -a---
adj_factor.parquet                        -a---
ex_date_index.parquet                     -a---
float_shares.parquet                      -a---
free_float_shares.parquet                 -a---
turnover_resistance_daily.parquet         -a---
----period=1d----
dividend_type=back                        
dividend_type=front                       
dividend_type=none                        
----div front----
symbol=000001_SZ                          
symbol=000002_SZ                          
symbol=000004_SZ                          
symbol=000006_SZ                          
symbol=000007_SZ                          
symbol=000008_SZ                          
symbol=000009_SZ                          
symbol=000010_SZ                          


 succeeded in 2935ms:
1.9.78.123
D:\anaconda3\envs\vanna312\Lib\site-packages\backtrader

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "rg -n \"def _runnext|cheat_on_open|cheat_on_close|def run|broker.next|_brokernotify|strategy._next\" D:\\anaconda3\\envs\\vanna312\\Lib\\site-packages\\backtrader\\cerebro.py | Select-Object -First 60" in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "rg -n \"def set_coo|def next|cheat_on_open|coo|_check_then_notify|Order.Market|order.execute|def execute\" D:\\anaconda3\\envs\\vanna312\\Lib\\site-packages\\backtrader\\brokers\\bbroker.py | Select-Object -First 80" in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1968ms:
242:      - ``cheat_on_open`` (default: ``False``)
250:        For cheat_on_open order execution, it is also necessary to make the
259:        with ``True`` to activate ``cheat_on_open`` execution. Will only do it
260:        if ``cheat_on_open`` is also ``True``
291:        ('cheat_on_open', False),
1025:    def runstop(self):
1030:    def run(self, **kwargs):
1171:    def runstrategies(self, iterstrat, predata=False):
1181:        if self.p.cheat_on_open and self.p.broker_coo:
1360:    def _brokernotify(self):
1365:        self._broker.next()
1377:    def _runnext_old(self, runstrats):
1423:            self._brokernotify()
1463:            self._brokernotify()
1498:    def _runnext(self, runstrats):
1622:                if self.p.cheat_on_open:
1628:            self._brokernotify()
1687:            if self.p.cheat_on_open:
1693:            self._brokernotify()

 succeeded in 1577ms:
104:              *execution type*, remaining size (``order.executed.remsize``) and
187:        - ``coo`` (default: ``False``)
189:          *Cheat-On-Open* Setting this to ``True`` with ``set_coo`` enables
237:        ('coo', False),
318:    def set_coo(self, coo):
320:        self.p.coo = coo
695:            size = order.executed.remsize
727:            if not self.p.coo:
733:                if order.exectype == Order.Market:
828:            order.execute(dtcoc or data.datetime[ago],
859:            if not self.p.coo and order.data.datetime[0] <= order.created.dt:
1059:        if order.exectype == Order.Market:
1176:    def next(self):

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command '$p="D:'"\\anaconda3\\envs\\vanna312\\Lib\\site-packages\\backtrader\\brokers\\bbroker.py\"; "'$lines=Get-Content -LiteralPath $p; $lines[700..880] -join "`n"' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command '$p="D:'"\\anaconda3\\envs\\vanna312\\Lib\\site-packages\\backtrader\\cerebro.py\"; "'$lines=Get-Content -LiteralPath $p; $lines[1490..1700] -join "`n"' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1529ms:

        # Get comminfo object for the data
        comminfo = self.getcommissioninfo(order.data)

        # Check if something has to be compensated
        if order.data._compensate is not None:
            data = order.data._compensate
            cinfocomp = self.getcommissioninfo(data)  # for actual commission
        else:
            data = order.data
            cinfocomp = comminfo

        # Adjust position with operation size
        if ago is not None:
            # Real execution with date
            position = self.positions[data]
            pprice_orig = position.price

            psize, pprice, opened, closed = position.pseudoupdate(size, price)

            # if part/all of a position has been closed, then there has been
            # a profitandloss ... record it
            pnl = comminfo.profitandloss(-closed, pprice_orig, price)
            cash = self.cash
        else:
            pnl = 0
            if not self.p.coo:
                price = pprice_orig = order.created.price
            else:
                # When doing cheat on open, the price to be considered for a
                # market order is the opening price and not the default closing
                # price with which the order was created
                if order.exectype == Order.Market:
                    price = pprice_orig = order.data.open[0]
                else:
                    price = pprice_orig = order.created.price

            psize, pprice, opened, closed = position.update(size, price)

        # "Closing" totally or partially is possible. Cash may be re-injected
        if closed:
            # Adjust to returned value for closed items & acquired opened items
            if self.p.shortcash:
                closedvalue = comminfo.getvaluesize(-closed, pprice_orig)
            else:
                closedvalue = comminfo.getoperationcost(closed, pprice_orig)

            closecash = closedvalue
            if closedvalue > 0:  # long position closed
                closecash /= comminfo.get_leverage()  # inc cash with lever

            cash += closecash + pnl * comminfo.stocklike
            # Calculate and substract commission
            closedcomm = comminfo.getcommission(closed, price)
            cash -= closedcomm

            if ago is not None:
                # Cashadjust closed contracts: prev close vs exec price
                # The operation can inject or take cash out
                cash += comminfo.cashadjust(-closed,
                                            position.adjbase,
                                            price)

                # Update system cash
                self.cash = cash
        else:
            closedvalue = closedcomm = 0.0

        popened = opened
        if opened:
            if self.p.shortcash:
                openedvalue = comminfo.getvaluesize(opened, price)
            else:
                openedvalue = comminfo.getoperationcost(opened, price)

            opencash = openedvalue
            if openedvalue > 0:  # long position being opened
                opencash /= comminfo.get_leverage()  # dec cash with level

            cash -= opencash  # original behavior

            openedcomm = cinfocomp.getcommission(opened, price)
            cash -= openedcomm

            if cash < 0.0:
                # execution is not possible - nullify
                opened = 0
                openedvalue = openedcomm = 0.0

            elif ago is not None:  # real execution
                if abs(psize) > abs(opened):
                    # some futures were opened - adjust the cash of the
                    # previously existing futures to the operation price and
                    # use that as new adjustment base, because it already is
                    # for the new futures At the end of the cycle the
                    # adjustment to the close price will be done for all open
                    # futures from a common base price with regards to the
                    # close price
                    adjsize = psize - opened
                    cash += comminfo.cashadjust(adjsize,
                                                position.adjbase, price)

                # record adjust price base for end of bar cash adjustment
                position.adjbase = price

                # update system cash - checking if opened is still != 0
                self.cash = cash
        else:
            openedvalue = openedcomm = 0.0

        if ago is None:
            # return cash from pseudo-execution
            return cash

        execsize = closed + opened

        if execsize:
            # Confimrm the operation to the comminfo object
            comminfo.confirmexec(execsize, price)

            # do a real position update if something was executed
            position.update(execsize, price, data.datetime.datetime())

            if closed and self.p.int2pnl:  # Assign accumulated interest data
                closedcomm += self.d_credit.pop(data, 0.0)

            # Execute and notify the order
            order.execute(dtcoc or data.datetime[ago],
                          execsize, price,
                          closed, closedvalue, closedcomm,
                          opened, openedvalue, openedcomm,
                          comminfo.margin, pnl,
                          psize, pprice)

            order.addcomminfo(comminfo)

            self.notify(order)
            self._ococheck(order)

        if popened and not opened:
            # opened was not executed - not enough cash
            order.margin()
            self.notify(order)
            self._ococheck(order)
            self._bracketize(order, cancel=True)

    def notify(self, order):
        self.notifs.append(order.clone())

    def _try_exec_historical(self, order):
        self._execute(order, ago=0, price=order.created.price)

    def _try_exec_market(self, order, popen, phigh, plow):
        ago = 0
        if self.p.coc and order.info.get('coc', True):
            dtcoc = order.created.dt
            exprice = order.created.pclose
        else:
            if not self.p.coo and order.data.datetime[0] <= order.created.dt:
                return    # can only execute after creation time

            dtcoc = None
            exprice = popen

        if order.isbuy():
            p = self._slip_up(phigh, exprice, doslip=self.p.slip_open)
        else:
            p = self._slip_down(plow, exprice, doslip=self.p.slip_open)

        self._execute(order, ago=0, price=p, dtcoc=dtcoc)

    def _try_exec_close(self, order, pclose):
        # pannotated allows to keep track of the closing bar if there is no
        # information which lets us know that the current bar is the closing
        # bar (like matching end of session bar)
        # The actual matching will be done one bar afterwards but using the
        # information from the actual closing bar

        dt0 = order.data.datetime[0]
        # don't use "len" -> in replay the close can be reached with same len
        if dt0 > order.created.dt:  # can only execute after creation time

 succeeded in 1434ms:

                    writer.next()

    def _disable_runonce(self):
        '''API for lineiterators to disable runonce (see HeikinAshi)'''
        self._dorunonce = False

    def _runnext(self, runstrats):
        '''
        Actual implementation of run in full next mode. All objects have its
        ``next`` method invoke on each data arrival
        '''
        datas = sorted(self.datas,
                       key=lambda x: (x._timeframe, x._compression))
        datas1 = datas[1:]
        data0 = datas[0]
        d0ret = True

        rs = [i for i, x in enumerate(datas) if x.resampling]
        rp = [i for i, x in enumerate(datas) if x.replaying]
        rsonly = [i for i, x in enumerate(datas)
                  if x.resampling and not x.replaying]
        onlyresample = len(datas) == len(rsonly)
        noresample = not rsonly

        clonecount = sum(d._clone for d in datas)
        ldatas = len(datas)
        ldatas_noclones = ldatas - clonecount
        lastqcheck = False
        dt0 = date2num(datetime.datetime.max) - 2  # default at max
        while d0ret or d0ret is None:
            # if any has live data in the buffer, no data will wait anything
            newqcheck = not any(d.haslivedata() for d in datas)
            if not newqcheck:
                # If no data has reached the live status or all, wait for
                # the next incoming data
                livecount = sum(d._laststatus == d.LIVE for d in datas)
                newqcheck = not livecount or livecount == ldatas_noclones

            lastret = False
            # Notify anything from the store even before moving datas
            # because datas may not move due to an error reported by the store
            self._storenotify()
            if self._event_stop:  # stop if requested
                return
            self._datanotify()
            if self._event_stop:  # stop if requested
                return

            # record starting time and tell feeds to discount the elapsed time
            # from the qcheck value
            drets = []
            qstart = datetime.datetime.utcnow()
            for d in datas:
                qlapse = datetime.datetime.utcnow() - qstart
                d.do_qcheck(newqcheck, qlapse.total_seconds())
                drets.append(d.next(ticks=False))

            d0ret = any((dret for dret in drets))
            if not d0ret and any((dret is None for dret in drets)):
                d0ret = None

            if d0ret:
                dts = []
                for i, ret in enumerate(drets):
                    dts.append(datas[i].datetime[0] if ret else None)

                # Get index to minimum datetime
                if onlyresample or noresample:
                    dt0 = min((d for d in dts if d is not None))
                else:
                    dt0 = min((d for i, d in enumerate(dts)
                               if d is not None and i not in rsonly))

                dmaster = datas[dts.index(dt0)]  # and timemaster
                self._dtmaster = dmaster.num2date(dt0)
                self._udtmaster = num2date(dt0)

                # slen = len(runstrats[0])
                # Try to get something for those that didn't return
                for i, ret in enumerate(drets):
                    if ret:  # dts already contains a valid datetime for this i
                        continue

                    # try to get a data by checking with a master
                    d = datas[i]
                    d._check(forcedata=dmaster)  # check to force output
                    if d.next(datamaster=dmaster, ticks=False):  # retry
                        dts[i] = d.datetime[0]  # good -> store
                        # self._plotfillers2[i].append(slen)  # mark as fill
                    else:
                        # self._plotfillers[i].append(slen)  # mark as empty
                        pass

                # make sure only those at dmaster level end up delivering
                for i, dti in enumerate(dts):
                    if dti is not None:
                        di = datas[i]
                        rpi = False and di.replaying   # to check behavior
                        if dti > dt0:
                            if not rpi:  # must see all ticks ...
                                di.rewind()  # cannot deliver yet
                            # self._plotfillers[i].append(slen)
                        elif not di.replaying:
                            # Replay forces tick fill, else force here
                            di._tick_fill(force=True)

                        # self._plotfillers2[i].append(slen)  # mark as fill

            elif d0ret is None:
                # meant for things like live feeds which may not produce a bar
                # at the moment but need the loop to run for notifications and
                # getting resample and others to produce timely bars
                for data in datas:
                    data._check()
            else:
                lastret = data0._last()
                for data in datas1:
                    lastret += data._last(datamaster=data0)

                if not lastret:
                    # Only go extra round if something was changed by "lasts"
                    break

            # Datas may have generated a new notification after next
            self._datanotify()
            if self._event_stop:  # stop if requested
                return

            if d0ret or lastret:  # if any bar, check timers before broker
                self._check_timers(runstrats, dt0, cheat=True)
                if self.p.cheat_on_open:
                    for strat in runstrats:
                        strat._next_open()
                        if self._event_stop:  # stop if requested
                            return

            self._brokernotify()
            if self._event_stop:  # stop if requested
                return

            if d0ret or lastret:  # bars produced by data or filters
                self._check_timers(runstrats, dt0, cheat=False)
                for strat in runstrats:
                    strat._next()
                    if self._event_stop:  # stop if requested
                        return

                    self._next_writers(runstrats)

        # Last notification chance before stopping
        self._datanotify()
        if self._event_stop:  # stop if requested
            return
        self._storenotify()
        if self._event_stop:  # stop if requested
            return

    def _runonce(self, runstrats):
        '''
        Actual implementation of run in vector mode.

        Strategies are still invoked on a pseudo-event mode in which ``next``
        is called for each data arrival
        '''
        for strat in runstrats:
            strat._once()
            strat.reset()  # strat called next by next - reset lines

        # The default once for strategies does nothing and therefore
        # has not moved forward all datas/indicators/observers that
        # were homed before calling once, Hence no "need" to do it
        # here again, because pointers are at 0
        datas = sorted(self.datas,
                       key=lambda x: (x._timeframe, x._compression))

        while True:
            # Check next incoming date in the datas
            dts = [d.advance_peek() for d in datas]
            dt0 = min(dts)
            if dt0 == float('inf'):
                break  # no data delivers anything

            # Timemaster if needed be
            # dmaster = datas[dts.index(dt0)]  # and timemaster
            slen = len(runstrats[0])
            for i, dti in enumerate(dts):
                if dti <= dt0:
                    datas[i].advance()
                    # self._plotfillers2[i].append(slen)  # mark as fill
                else:
                    # self._plotfillers[i].append(slen)
                    pass

            self._check_timers(runstrats, dt0, cheat=True)

            if self.p.cheat_on_open:
                for strat in runstrats:
                    strat._oncepost_open()
                    if self._event_stop:  # stop if requested
                        return

            self._brokernotify()
            if self._event_stop:  # stop if requested
                return

            self._check_timers(runstrats, dt0, cheat=False)

            for strat in runstrats:
                strat._oncepost(dt0)
                if self._event_stop:  # stop if requested

codex
Backtrader 订单时点是我评审的关键疑点，先跑一个只读内存实验验证「next() 下单实际成交于哪根 bar 开盘」，避免靠文档猜。
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "@'
import datetime
import backtrader as bt
import pandas as pd

dates = pd.bdate_range(\"2024-01-02\", periods=8)
px = [10.0 + i for i in range(len(dates))]
df = pd.DataFrame({
    \"open\": px, \"high\": [p + 0.5 for p in px], \"low\": [p - 0.5 for p in px],
    \"close\": px, \"volume\": [1000.0] * len(dates),
}, index=dates)

class S(bt.Strategy):
    def __init__(self):
        self.log = []
        self.bought_at = None
    def next(self):
        d = self.data.datetime.date(0).isoformat()
        pos = int(self.position.size) if self.position else 0
        self.log.append((d, pos, float(self.broker.getcash()), len(self)))
        if len(self) == 4 and not self.bought_at:
            self.buy()   # plain market order created in next() of bar idx 4
            self.bought_at = d
    def notify_order(self, order):
        if order.status == order.Completed:
            print(\"FILL created_dt=%s executed_dt=%s price=%s size=%s\" % (
                bt.num2date(order.created.dt).date(),
                bt.num2date(order.executed.dt).date(),
                order.executed.price, order.executed.size))

c = bt.Cerebro(stdstats=False)
c.adddata(bt.feeds.PandasData(dataname=df))
c.addstrategy(S)
c.broker.setcash(100000)
st = c.run()[0]
print(\"STRATEGY LOG (date,pos,cash,len):\")
for row in st.log:
    print(row)
'@ | D:\\anaconda3\\envs\\vanna312\\python.exe -" in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 3177ms:
FILL created_dt=2024-01-05 executed_dt=2024-01-08 price=14.0 size=1
STRATEGY LOG (date,pos,cash,len):
('2024-01-02', 0, 100000.0, 1)
('2024-01-03', 0, 100000.0, 2)
('2024-01-04', 0, 100000.0, 3)
('2024-01-05', 0, 100000.0, 4)
('2024-01-08', 1, 99986.0, 5)
('2024-01-09', 1, 99986.0, 6)
('2024-01-10', 1, 99986.0, 7)
('2024-01-11', 1, 99986.0, 8)

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command '$p="D:'"\\anaconda3\\envs\\vanna312\\Lib\\site-packages\\backtrader\\order.py\"; rg -n \"Market|Close|Limit|Open|Historical|class Order\" "'$p | Select-Object -First 40' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "rg -n \"exectype=Order\\.|exectype=bt\\.Order\\.|Order\\.Open|Order\\.Market\" backtest --glob \"*.py\" | Select-Object -First 40" in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1460ms:
35:class OrderExecutionBit(object):
88:class OrderData(object):
104:      - pricelimit: holds pricelimit for StopLimit (which has trigger first)
222:class OrderBase(with_metaclass(MetaParams, object)):
237:    T_Close, T_Day, T_Date, T_None = range(4)
242:    (Market, Close, Limit, Stop, StopLimit, StopTrail, StopTrailLimit,
243:     Historical) = range(8)
244:    ExecTypes = ['Market', 'Close', 'Limit', 'Stop', 'StopLimit', 'StopTrail',
245:                 'StopTrailLimit', 'Historical']
289:        tojoin.append('Price Limit: {}'.format(self.pricelimit))
315:            self.exectype = Order.Market
335:        if self.exectype in [Order.StopTrail, Order.StopTrailLimit]:
528:class Order(OrderBase):
585:        if self.exectype == Order.Market:
608:                if self.exectype == Order.StopTrailLimit:
614:                if self.exectype == Order.StopTrailLimit:
628:class StopLimitBuyOrder(BuyOrder):
640:class StopLimitSellOrder(SellOrder):

 succeeded in 1421ms:
backtest\rolling_investment_strategy.py:409:                        bt.Order.Market: "市价单",
backtest\rolling_investment_strategy.py:1424:                        order_exectype = bt.Order.Market
backtest\rolling_investment_strategy.py:1428:                    order_exectype = bt.Order.Market
backtest\rolling_investment_strategy.py:1431:                    order_exectype = bt.Order.Market
backtest\rolling_investment_strategy.py:1664:                    exectype=bt.Order.Limit,      # 改为限价单
backtest\rolling_investment_strategy.py:1952:                    exectype=bt.Order.Market,
backtest\research\chip_factor_analysis.py:210:                    self.buy(data=d, size=size, exectype=bt.Order.Close)

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "@'
import pandas as pd, pyarrow.parquet as pq, os
from pathlib import Path
root = Path(\"F:/stock_data\")

def show(path, ncols=12, nrows=4):
    print(\"=== \", path)
    if not path.exists():
        print(\"MISSING\"); return None
    f = pq.ParquetFile(path)
    print(\"rows\", f.metadata.num_rows, \"cols\", f.metadata.schema.names)
    df = f.read(columns=f.metadata.schema.names[:ncols]).to_pandas()
    print(df.head(nrows).to_string())
    print(df.tail(1).to_string())
    for c in df.columns:
        if df[c].dtype == \"object\":
            print(c, \"sample\", df[c].iloc[0] if len(df) else None)
    return df

fs = show(root/\"float_shares.parquet\", 12, 3)
ffs = show(root/\"free_float_shares.parquet\", 14, 3)
'@ | D:\\anaconda3\\envs\\vanna312\\python.exe -" in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "oskh_data/__init__.py"; "==== float_shares_history.py head ===="; $l=Get-Content -LiteralPath "oskh_data/float_shares_history.py" -TotalCount 80; $l -join "`n"' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1690ms:
# -*- coding: utf-8 -*-
"""Local market-data *read* infrastructure.

This fork does not download from QMT. Bars, adj factors, and float-share
sidecars are produced by the original repo and consumed via path-SSOT.
"""
from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from oskh_data.period_schema import PeriodDataManager, StockDataManager
    from oskh_data.reader import DEFAULT_READER_MODE, StockDataReader

__all__ = [
    "StockDataReader",
    "DEFAULT_READER_MODE",
    "PeriodDataManager",
    "StockDataManager",
]

_LAZY_EXPORTS = {
    "StockDataReader": ("oskh_data.reader", "StockDataReader"),
    "DEFAULT_READER_MODE": ("oskh_data.reader", "DEFAULT_READER_MODE"),
    "PeriodDataManager": ("oskh_data.period_schema", "PeriodDataManager"),
    "StockDataManager": ("oskh_data.period_schema", "StockDataManager"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))

==== float_shares_history.py head ====
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
.. deprecated:: 2026-05-30

Replaced by ``oskh_data/free_float_shares.py`` which reads freeFloatCapital +
circulating_capital directly from miniQMT ``Capital`` financial table (historical
quarterly data, no akshare dependency). This module is retained for the
``--source snapshot`` fallback only; remove after full migration to
free_float_shares.parquet.

Original doc: Backfill float_shares history parquet. Sources: 1) snapshot 2) akshare.
"""

import argparse
import os

from common.infra.data_root import resolve_parquet_container, resolve_source_parquet
import sys
from pathlib import Path
from typing import Any, List, cast

import pandas as pd

from oskh_data.pandas_typing import normalize_timestamp

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

DEFAULT_SNAPSHOT_PATH = str(resolve_source_parquet("float_shares.parquet"))
DEFAULT_HISTORY_PATH = str(resolve_parquet_container() / "float_shares_history.parquet")


def business_days(start_date: str, end_date: str) -> List[pd.Timestamp]:
    return list(pd.bdate_range(pd.Timestamp(start_date), pd.Timestamp(end_date)))


def build_snapshot_backfill(snapshot_df: pd.DataFrame, dates: List[pd.Timestamp]) -> pd.DataFrame:
    base = snapshot_df[["stock_code", "FloatVolume", "TotalVolume", "name"]].copy()
    frames = []
    for d in dates:
        day_df = base.copy()
        day_df["date"] = d.normalize()
        frames.append(day_df)
    if not frames:
        return pd.DataFrame(columns=cast(Any, ["date", "stock_code", "FloatVolume", "TotalVolume", "name"]))
    out = pd.concat(frames, ignore_index=True)
    return pd.DataFrame(out[["date", "stock_code", "FloatVolume", "TotalVolume", "name"]])


def merge_history(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        merged = incoming.copy()
    else:
        merged = pd.concat([existing, incoming], ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"]).dt.normalize()
    merged = merged.drop_duplicates(subset=["date", "stock_code"], keep="last")
    merged = merged.sort_values(["stock_code", "date"]).reset_index(drop=True)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill float_shares history parquet (deprecated; use free_float_shares.py)"
    )
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--snapshot-path", default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--history-output", default=DEFAULT_HISTORY_PATH)
    parser.add_argument("--replace", action="store_true", help="replace output instead of merge")
    parser.add_argument("--max-stocks", type=int, default=0, help="limit to first N stocks (0=all)")
    parser.add_argument("--codes", default=None, help="comma-separated stock codes")
    args = parser.parse_args()

    start_ts = normalize_timestamp(pd.Timestamp(args.start_date))
    end_ts = normalize_timestamp(pd.Timestamp(args.end_date))
    if end_ts < start_ts:
        raise ValueError("end-date must be >= start-date")

    snapshot_df = pd.read_parquet(args.snapshot_path)

 succeeded in 4792ms:
===  F:\stock_data\float_shares.parquet
rows 5531 cols ['stock_code', 'FloatVolume', 'TotalVolume', 'name', 'updated_at']
  stock_code   FloatVolume   TotalVolume   name                        updated_at
0  000001.SZ  1.940560e+10  1.940592e+10   平安银行  2026-05-30T08:46:10.372664+00:00
1  000002.SZ  9.716936e+09  1.193071e+10   万 科Ａ  2026-05-30T08:46:10.372664+00:00
2  000004.SZ  1.262891e+08  1.323803e+08  *ST国华  2026-05-30T08:46:10.372664+00:00
     stock_code  FloatVolume  TotalVolume  name                        updated_at
5530  920992.BJ   49017283.0   96730934.0  中科美菱  2026-05-30T08:46:10.372664+00:00
stock_code sample 000001.SZ
name sample 平安银行
updated_at sample 2026-05-30T08:46:10.372664+00:00
===  F:\stock_data\free_float_shares.parquet
rows 385130 cols ['stock_code', 'm_timetag', 'freeFloatCapital', 'circulating_capital', 'restrict_circulating_capital', 'total_capital']
  stock_code  m_timetag  freeFloatCapital  circulating_capital  restrict_circulating_capital  total_capital
0  000001.SZ 2001-10-15      1.409362e+09         1.409362e+09                           0.0   1.945822e+09
1  000001.SZ 2001-12-31      1.409362e+09         1.409362e+09                           0.0   1.945822e+09
2  000001.SZ 2002-03-31      1.409362e+09         1.409362e+09                           0.0   1.945822e+09
       stock_code  m_timetag  freeFloatCapital  circulating_capital  restrict_circulating_capital  total_capital
385129  920992.BJ 2026-04-21        31447283.0           49017283.0                           0.0     96730934.0
stock_code sample 000001.SZ

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "@'
import pandas as pd, pyarrow.parquet as pq
from pathlib import Path
root = Path(\"F:/stock_data/period=1d/dividend_type=front\")

for sym in [\"000001_SZ\", \"000004_SZ\"]:
    f = root / f\"symbol={sym}\" / \"data.parquet\"
    pf = pq.ParquetFile(f)
    print(\"====\", sym, \"rows\", pf.metadata.num_rows, \"cols\", pf.schema_arrow.names)
    df = pf.read().to_pandas()
    print(df.dtypes.to_string())
    print(df.head(2).to_string())
    print(df.tail(2).to_string())
    if \"time\" in df.columns:
        df[\"time\"] = pd.to_datetime(df[\"time\"])
        df = df.set_index(\"time\").sort_index()
    elif isinstance(df.index, pd.DatetimeIndex):
        pass
    else:
        print(\"no time col; index\", df.index)
        continue
    seg = df.loc[\"2024-01-01\":\"2026-09-03\"]
    print(\"2024-2026 rows:\", len(seg), \"zero-vol:\", int((seg[\"volume\"]==0).sum()))
    zv = seg[seg[\"volume\"]==0]
    print(zv.head(10).to_string() if len(zv) else \"no zero-vol rows\")
    # long calendar gaps
    s = seg.index.to_series()
    gaps = s.diff().dt.days
    print(\"max gap days:\", gaps.max(), \"date:\", s.loc[gaps.idxmax()] if len(gaps) else None)
    big = gaps[gaps > 7]
    print(\"gaps>7d:\", len(big))
    if len(big): print(big.to_string())
'@ | D:\\anaconda3\\envs\\vanna312\\python.exe -" in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 3158ms:
==== 000001_SZ rows 8707 cols ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']
time        int64
open      float64
high      float64
low       float64
close     float64
volume      int64
amount    float64
           time      open      high       low     close  volume  amount
0  663206400000 -2.658801 -2.658801 -2.658801 -2.658801       0     0.0
1  663292800000 -2.658801 -2.658801 -2.658801 -2.658801       0     0.0
               time   open   high    low  close   volume        amount
8705  1788393600000  11.88  12.08  11.83  11.88  1105134  1.324230e+09
8706  1788480000000  11.86  12.00  11.85  11.89   814373  9.699484e+08
2024-2026 rows: 0 zero-vol: 0
no zero-vol rows
max gap days: nan date: None
gaps>7d: 0
==== 000004_SZ rows 8668 cols ['time', 'open', 'high', 'low', 'close', 'volume', 'amount', '__index_level_0__']
time        int64
open      float64
high      float64
low       float64
close     float64
volume      int64
amount    float64
                    time      open      high       low     close  volume  amount
1991-01-07  663206400000  4.237779  4.237779  4.237779  4.237779       0     0.0
1991-01-08  663292800000  4.237779  4.237779  4.237779  4.237779       0     0.0
                     time  open  high   low  close  volume     amount
2026-07-10  1783641600000  0.45  0.46  0.45   0.46   36306  1667186.0
2026-07-13  1783900800000  0.51  0.51  0.51   0.51   34886  1779194.0
2024-2026 rows: 0 zero-vol: 0
no zero-vol rows
max gap days: nan date: None
gaps>7d: 0

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "@'
import pandas as pd, pyarrow.parquet as pq
from pathlib import Path
root = Path(\"F:/stock_data/period=1d/dividend_type=front\")

for sym in [\"000001_SZ\", \"000004_SZ\"]:
    f = root / f\"symbol={sym}\" / \"data.parquet\"
    df = pq.read_table(f).to_pandas()
    print(\"====\", sym, \"index type:\", type(df.index).__name__, df.index.dtype, \"cols:\", list(df.columns))
    # build proper datetime index
    if \"time\" in df.columns:
        df = df.assign(_dt=pd.to_datetime(df[\"time\"], unit=\"ms\")).set_index(\"_dt\").sort_index()
    seg = df.loc[\"2024-01-01\":\"2026-09-03\"]
    print(\"2024-09 rows:\", len(seg), \"first:\", seg.index[0], \"last:\", seg.index[-1])
    zv = seg[seg[\"volume\"] == 0]
    print(\"zero-vol:\", len(zv))
    print(zv.head(8).to_string())
    s = seg.index.to_series()
    gaps = s.diff().dt.days
    big = gaps[gaps > 10]
    print(\"gaps>10d:\", len(big))
    print(big.tail(10).to_string())
    print(\"min open:\", seg[\"open\"].min(), \"min close:\", seg[\"close\"].min(), \"min vol:\", seg[\"volume\"].min())
'@ | D:\\anaconda3\\envs\\vanna312\\python.exe -" in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 3204ms:
==== 000001_SZ index type: RangeIndex int64 cols: ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']
2024-09 rows: 648 first: 2024-01-02 00:00:00 last: 2026-09-03 00:00:00
zero-vol: 0
Empty DataFrame
Columns: [time, open, high, low, close, volume, amount]
Index: []
gaps>10d: 2
_dt
2024-02-19    11.0
2026-02-24    11.0
min open: 7.127000000000001 min close: 7.167 min vol: 353013
==== 000004_SZ index type: DatetimeIndex datetime64[ns] cols: ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']
2024-09 rows: 610 first: 2024-01-02 00:00:00 last: 2026-07-13 00:00:00
zero-vol: 37
                     time  open  high   low  close  volume  amount
_dt                                                               
2025-04-29  1745884800000  8.39  8.39  8.39   8.39       0     0.0
2026-04-28  1777334400000  2.76  2.76  2.76   2.76       0     0.0
2026-04-29  1777420800000  2.76  2.76  2.76   2.76       0     0.0
2026-04-30  1777507200000  2.76  2.76  2.76   2.76       0     0.0
2026-05-06  1778025600000  2.76  2.76  2.76   2.76       0     0.0
2026-05-07  1778112000000  2.76  2.76  2.76   2.76       0     0.0
2026-05-08  1778198400000  2.76  2.76  2.76   2.76       0     0.0
2026-05-11  1778457600000  2.76  2.76  2.76   2.76       0     0.0
gaps>10d: 2
_dt
2024-02-19    11.0
2026-02-24    11.0
min open: 0.25 min close: 0.26 min vol: 0

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "oskh_data/symbol_format.py"' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "@'
from oskh_data import StockDataReader
r = StockDataReader(mode=\"parquet\")
df = r.read_stock(\"000001.SZ\", start_time=\"20240101\", end_time=\"20240115\", period=\"1d\", adjust_type=\"front\")
print(type(df).__name__, df.shape)
print(df.index, df.index.dtype, list(df.columns))
print(df.head(3).to_string())
r.close()
print(\"closed ok\")
'@ | D:\\anaconda3\\envs\\vanna312\\python.exe -" in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1819ms:
"""Centralized symbol-format conversion.

Canonical symbol = **dot** format (broker/xtquant/Redis/execution_log/strategy):
``603196.SH``.
Partition key    = **underscore** format (Hive partition dir / path-safe):
``603196_SH``.

Why two formats (intentional, not debt): dots in Hive partition dir names
mishandle on Windows DuckDB — ``finish_adj_factor_duckdb.py`` documents
``symbol_dir=000001_SZ%5Cdata_parquet``. So partition **dirs** use underscore;
the duckdb ``symbol`` **column** uses canonical dot (``build_persistent_db``
normalizes via ``UPDATE stock_data SET symbol = REPLACE(symbol, '_', '.')``,
see ``reader.py``).

Rule: ALL Python-side symbol translation MUST go through these two helpers —
no ad-hoc ``.replace()``. SQL-level ``REPLACE(symbol, '_', '.')`` in
``reader.py`` is DB-side normalization and stays as-is.

See ``docs/engineering/plan-symbol-format-centralize-2026-06-25.md`` (if present)
and memory ``duckdb-symbol-format-preheat-trap``.
"""
from __future__ import annotations

import re

__all__ = ["to_partition_key", "to_canonical_symbol", "is_canonical_symbol"]

# A-share broker/xtquant form: 6 digits + .SH/.SZ/.BJ
_CANONICAL_SYMBOL_RE = re.compile(r"^\d{6}\.(SH|SZ|BJ)$")


def is_canonical_symbol(symbol: str) -> bool:
    """True iff ``symbol`` is a canonical A-share code (e.g. ``000001.SZ``)."""
    return bool(_CANONICAL_SYMBOL_RE.match(symbol or ""))


def to_partition_key(symbol: str) -> str:
    """Canonical dot symbol -> underscore partition-key / path-safe form.

    ``603196.SH`` -> ``603196_SH``. Use for Hive partition dir names and file paths.
    """
    return symbol.replace(".", "_")


def to_canonical_symbol(key: str) -> str:
    """Underscore partition-key / ``symbol=...`` dir name -> canonical dot symbol.

    ``603196_SH`` or ``symbol=603196_SH`` -> ``603196.SH``. Use when reading
    symbols back from partition dir names into the trading layer.

    Market-suffix aware (``_SH/_SZ/_BJ``) for precision; falls back to blanket
    underscore->dot only when no recognized suffix. Safe for A-share codes
    (6 digits + market suffix, no internal underscore) — equivalent to both the
    historical suffix-only and blanket ``.replace()`` patterns.
    """
    if key.startswith("symbol="):
        key = key[len("symbol="):]
    for us, dot in (("_SH", ".SH"), ("_SZ", ".SZ"), ("_BJ", ".BJ")):
        if key.endswith(us):
            return key[: -len(us)] + dot
    return key.replace("_", ".")


 succeeded in 5758ms:
[WARN] QuantLoggerFactory not initialized, fallback mode active
DataFrame (10, 8)
DatetimeIndex(['2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05',
               '2024-01-08', '2024-01-09', '2024-01-10', '2024-01-11',
               '2024-01-12', '2024-01-15'],
              dtype='datetime64[ns]', name='datetime', freq=None) datetime64[ns] ['time', 'open', 'high', 'low', 'close', 'volume', 'amount', 'symbol']
                     time   open   high    low  close   volume        amount     symbol
datetime                                                                               
2024-01-02  1704153600000  7.467  7.497  7.287  7.287  1158366  1.075742e+09  000001.SZ
2024-01-03  1704240000000  7.267  7.297  7.227  7.277   733610  6.736736e+08  000001.SZ
2024-01-04  1704326400000  7.267  7.267  7.157  7.187   864194  7.874701e+08  000001.SZ
closed ok

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "tests/test_chip_indicator_warmup_semantics.py"' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "scripts/gates/verify_oskh_data_contract.py" | Select-Object -First 1' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 2087ms:
import backtrader as bt
import numpy as np
import pandas as pd

from backtest.chip_indicator import ChipDistribution, TurnoverChipFactor


class _ChipPandasData(bt.feeds.PandasData):
    lines = ("turnover_rate",)
    params = (("turnover_rate", -1),)


def _build_ohlcv_df(n: int = 60) -> pd.DataFrame:
    close = np.linspace(10.0, 12.0, n)
    df = pd.DataFrame(
        {
            "open": close * 0.999,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(n, 1_000_000.0),
            "turnover_rate": np.full(n, 0.015),
        },
        index=pd.date_range("2024-01-01", periods=n, freq="D"),
    )
    return df


class _CaptureChipDistribution(bt.Strategy):
    params = (("period", 20),)

    def __init__(self):
        self.ind = ChipDistribution(self.datas[0], period=self.p.period, data_freq="1d", stock_code="000001.SZ")
        self.samples = []

    def prenext(self):
        self._capture()

    def next(self):
        self._capture()

    def _capture(self):
        self.samples.append(
            (
                len(self.data),
                (
                    float(self.ind.cyqk_c[0]),
                    float(self.ind.asr[0]),
                    float(self.ind.ckdw[0]),
                    float(self.ind.prp[0]),
                ),
            )
        )


class _CaptureTurnoverChip(bt.Strategy):
    params = (("period", 10),)

    def __init__(self):
        self.ind = TurnoverChipFactor(self.datas[0], period=self.p.period, stock_code="000001.SZ")
        self.samples = []

    def prenext(self):
        self._capture()

    def next(self):
        self._capture()

    def _capture(self):
        self.samples.append(
            (
                len(self.data),
                (
                    float(self.ind.arc[0]),
                    float(self.ind.vrc[0]),
                    float(self.ind.src[0]),
                    float(self.ind.krc[0]),
                ),
            )
        )


def _run(strategy_cls):
    cerebro = bt.Cerebro(stdstats=False)  # type: ignore[reportCallIssue]
    data = _ChipPandasData(dataname=_build_ohlcv_df())  # type: ignore[reportCallIssue]
    cerebro.adddata(data)
    cerebro.addstrategy(strategy_cls)
    result = cerebro.run()
    return result[0]


def test_chip_distribution_warmup_uses_nan_not_zero():
    strat = _run(_CaptureChipDistribution)
    warmup = [vals for bar, vals in strat.samples if bar < strat.p.period]
    ready = [vals for bar, vals in strat.samples if bar >= strat.p.period]

    assert warmup
    assert all(all(np.isnan(v) for v in vals) for vals in warmup)
    assert ready
    assert any(all(np.isfinite(v) for v in vals) for vals in ready)


def test_turnover_chip_warmup_uses_nan_not_zero():
    strat = _run(_CaptureTurnoverChip)
    warmup = [vals for bar, vals in strat.samples if bar < strat.p.period]
    ready = [vals for bar, vals in strat.samples if bar >= strat.p.period]

    assert warmup
    assert all(all(np.isnan(v) for v in vals) for vals in warmup)
    assert ready
    assert any(all(np.isfinite(v) for v in vals) for vals in ready)


 succeeded in 2121ms:
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fail CI / preflight if ``oskh_data`` violates package boundary contracts,
or if live_trading / trade_decision modules misuse adjust_type in daily bar calls.

Checks performed:
  1. oskh_data does not import from backtest/ (no reverse dependency)
  2. oskh_data does not import from oskh_core / oskh_db (orthogonal)
  3. oskh_data does not import backtrader at module level, and must not
     import xtquant anywhere (this fork has no QMT download)
  3b. backtest/ must not import download modules or xtquant
  4. data_audit.db direct sqlite3 access is whitelisted in oskh_data/audit.py
  5. live_trading/ and trade_decision/ hot-path calls to stock_daily_bars /
     stock_daily_bars_cfg_only / read_stock must use adjust_type="none"
     (whitelist: live_trading_ma_indicator_provider.py)

Usage (repo root)::

  python scripts/gates/verify_oskh_data_contract.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List, Tuple

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2] if _HERE.parent.name == "gates" else _HERE.parents[1]
_OSKH_DATA = _REPO / "oskh_data"

# Forbidden anywhere in oskh_data (including nested / lazy imports)
_FORBIDDEN_ANYWHERE_IMPORTS: Tuple[Tuple[str, str], ...] = (
    ("backtest", "oskh_data must not depend on backtest/"),
    ("oskh_core", "oskh_data must not depend on oskh_core (orthogonal)"),
    ("oskh_db", "oskh_data must not depend on oskh_db (orthogonal)"),
    ("xtquant", "this fork has no QMT download; xtquant is forbidden"),
)

# Forbidden only at module top-level (delayed import inside functions OK)
_FORBIDDEN_MODULE_LEVEL_IMPORTS: Tuple[Tuple[str, str], ...] = (
    ("backtrader", "backtrader must not be imported at module level (use delayed import)"),
    ("xtquant", "xtquant must not be imported at module level (use delayed import)"),
)

# Back-compat alias for older call sites / docs
_FORBIDDEN_MODULE_IMPORTS = _FORBIDDEN_ANYWHERE_IMPORTS + _FORBIDDEN_MODULE_LEVEL_IMPORTS

_BACKTEST_DIR = _REPO / "backtest"

# This fork keeps thin backtest/ shims that re-export oskh_data CLIs.
_BACKTEST_SHIM_WHITELIST: set[str] = set()

# backtest/ must read local hive only — download/update lives in oskh_data + scripts/
_FORBIDDEN_BACKTEST_IMPORT_MODULES: Tuple[str, ...] = (
    "xtquant",
    "oskh_data.backfill",
    "oskh_data.float_shares",
    "oskh_data.float_shares_history",
    "oskh_data.adj_factor",
    "oskh_data.integrity",
    "oskh_data.download_ops",
    "oskh_data.minute_backfill",
    "oskh_data.etf_backfill",
    "oskh_data.downloader",
    "oskh_data.qmt_xtdata",
    "oskh_data.download_transport",
)

_FORBIDDEN_BACKTEST_CALL_NAMES: Tuple[str, ...] = (
    "DataDownloader",
    "download_history_data2",
    "download_market_data",
    "get_miniqmt_data",
    "download_data",
)

# Whitelist: modules allowed to use direct sqlite3 (independent audit db)
_SQLITE_WHITELIST = {
    "oskh_data/audit.py": "data_audit.db is an independent operations audit database, "
                          "isolated from the oskh_db.DatabaseGateway five-db routing. "
                          "See plan-refactor-backtest-data-to-oskh-data-2026-05-16.md §10.1 E.",
}

# Modules allowed to use adjust_type != "none" (explicitly documented reason required)
_ADJUST_TYPE_WHITELIST: Tuple[str, ...] = (
    "live_trading/indicators/ma_provider.py",
)

# Hot-path directories to scan for adjust_type misuse
_HOT_PATH_DIRS: Tuple[Path, ...] = (
    _REPO / "live_trading",
    _REPO / "trade_decision",
)

# Method/function names and their adjust keyword parameter names
_ADJUST_KEYWORD_TARGETS: Tuple[Tuple[str, str], ...] = (
    ("stock_daily_bars", "adjust"),
    ("stock_daily_bars_cfg_only", "adjust"),
    ("read_stock", "adjust_type"),
)

_RED = "\033[91m"
_GREEN = "\033[92m"
_RESET = "\033[0m"


def _collect_py_files(root: Path) -> List[Path]:
    return sorted(f for f in root.rglob("*.py") if f.name != "__init__.py")


# ------------------------------------------------------------------
# Check 1-3: oskh_data module-level imports
# ------------------------------------------------------------------

def _check_module_imports(path: Path) -> List[str]:
    errors: List[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        errors.append(f"{path}: syntax error: {e}")
        return errors

    # Layering: catch nested/lazy imports of oskh_core / oskh_db / backtest
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden, reason in _FORBIDDEN_ANYWHERE_IMPORTS:
                    if alias.name == forbidden or alias.name.startswith(forbidden + "."):
                        errors.append(f"{path}: import '{alias.name}' — {reason}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for forbidden, reason in _FORBIDDEN_ANYWHERE_IMPORTS:
                    if node.module == forbidden or node.module.startswith(forbidden + "."):
                        errors.append(f"{path}: from '{node.module}' import ... — {reason}")

    # Heavy deps: only forbid at module top-level (delayed import OK)
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden, reason in _FORBIDDEN_MODULE_LEVEL_IMPORTS:
                    if alias.name == forbidden or alias.name.startswith(forbidden + "."):
                        errors.append(f"{path}: module-level 'import {alias.name}' — {reason}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for forbidden, reason in _FORBIDDEN_MODULE_LEVEL_IMPORTS:
                    if node.module == forbidden or node.module.startswith(forbidden + "."):
                        errors.append(f"{path}: module-level 'from {node.module} import ...' — {reason}")

    return errors


def _check_backtest_no_download_ops(path: Path) -> List[str]:
    """backtest/ is read-only for market data; no download/update imports or calls."""
    relative = str(path.relative_to(_REPO)).replace("\\", "/")
    if relative in _BACKTEST_SHIM_WHITELIST:
        return []
    errors: List[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        errors.append(f"{path}: syntax error: {e}")
        return errors

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "xtquant" or alias.name.startswith("xtquant."):
                    errors.append(
                        f"{path}: backtest must not import xtquant "
                        f"(market download lives in the original repo)"
                    )
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            for forbidden in _FORBIDDEN_BACKTEST_IMPORT_MODULES:
                if mod == forbidden or mod.startswith(forbidden + "."):
                    errors.append(
                        f"{path}: backtest must not import download module '{mod}' "
                        f"(market download lives in the original repo)"
                    )
            if mod == "oskh_data" and node.names:
                for alias in node.names:
                    if alias.name in {"DataDownloader", "PeriodDataManager", "StockDataManager"}:
                        errors.append(
                            f"{path}: backtest must not import oskh_data.{alias.name} "
                            f"(download SSOT is outside backtest)"
                        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _resolve_call_name(node)
            if name in _FORBIDDEN_BACKTEST_CALL_NAMES:
                errors.append(
                    f"{path}: backtest must not call {name}() "
                    f"(download/update → scripts/ or oskh_data CLI)"
                )
        if isinstance(node, ast.Name) and node.id == "DataDownloader":
            errors.append(
                f"{path}: backtest must not reference DataDownloader "
                f"(download/update → scripts/ or oskh_data CLI)"
            )

    return errors


# ------------------------------------------------------------------
# Check 4: sqlite3 whitelist
# ------------------------------------------------------------------

def _check_sqlite_whitelist(path: Path) -> List[str]:
    errors: List[str] = []
    relative = str(path.relative_to(_REPO)).replace("\\", "/")
    if relative in _SQLITE_WHITELIST:
        return errors

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return errors

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sqlite3":
                    errors.append(
                        f"{path}: direct 'import sqlite3' not allowed. "
                        f"Whitelisted files: {list(_SQLITE_WHITELIST)}"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module == "sqlite3":
                errors.append(
                    f"{path}: direct 'from sqlite3 import ...' not allowed. "
                    f"Whitelisted files: {list(_SQLITE_WHITELIST)}"
                )

    return errors


# ------------------------------------------------------------------
# Check 5: adjust_type guard (static scan)
# ------------------------------------------------------------------

def _check_adjust_type_hot_path() -> List[str]:
    """Scan live_trading/ and trade_decision/ for calls to stock_daily_bars /
    read_stock with adjust_type != 'none'.
    """
    errors: List[str] = []
    for hot_dir in _HOT_PATH_DIRS:
        if not hot_dir.is_dir():
            continue
        for py_file in _collect_py_files(hot_dir):
            relative = str(py_file.relative_to(_REPO)).replace("\\", "/")
            if relative in _ADJUST_TYPE_WHITELIST:
                continue

            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                # match func name: stock_daily_bars(...), stock_daily_bars_cfg_only(...),
                # or .read_stock(...)
                func_name = _resolve_call_name(node)
                if not func_name:
                    continue

                for target_name, kw_name in _ADJUST_KEYWORD_TARGETS:
                    if func_name != target_name:
                        continue
                    # check keyword arguments
                    for kw in node.keywords:
                        if kw.arg == kw_name:
                            val = _resolve_constant(kw.value)
                            if val is not None and val != "none":
                                errors.append(
                                    f"{relative}: {func_name}(..., {kw_name}='{val}') — "
                                    f"adjust_type must be 'none' in hot-path modules. "
                                    f"Whitelist: {list(_ADJUST_TYPE_WHITELIST)}"
                                )
    return errors


def _resolve_call_name(node: ast.Call) -> str | None:
    """Extract function/method name from a Call node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _resolve_constant(node: ast.expr) -> str | None:
    """Resolve ast.Constant string value, or None if not a simple string literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main() -> int:
    errors: List[str] = []

    # Checks 1-4: oskh_data package boundaries
    if not _OSKH_DATA.is_dir():
        print(f"{_RED}oskh_data/ directory not found{_RESET}")
        return 1

    for py_file in _collect_py_files(_OSKH_DATA):
        errors.extend(_check_module_imports(py_file))
        errors.extend(_check_sqlite_whitelist(py_file))

    if _BACKTEST_DIR.is_dir():
        for py_file in sorted(_BACKTEST_DIR.rglob("*.py")):
            errors.extend(_check_backtest_no_download_ops(py_file))

    # Check 5: adjust_type hot-path guard
    errors.extend(_check_adjust_type_hot_path())

    if errors:
        print(f"{_RED}oskh_data contract violations ({len(errors)}):{_RESET}")
        for e in errors:
            print(f"  {_RED}✗{_RESET} {e}")
        return 1

    print(f"{_GREEN}oskh_data contract: OK{_RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


codex
现在用真实 F 盘数据做只读 pipeline 验证（不写任何文件）：盈筹率尺度/覆盖率、周线 warmup、边缘触发、以及草稿策略实际成交日期 vs 记录日期。
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "@'
import time
import numpy as np, pandas as pd

from backtest.research.ma_chip_edge_backtest import (
    load_front_daily, build_signal_frame, cyqk_series, week_ma20_asof,
    run_one, MaChipEdgeStrategy,
)

for code in (\"000001.SZ\", \"000004.SZ\"):
    t0 = time.monotonic()
    raw = load_front_daily(code, \"20220701\", \"20240630\")
    t1 = time.monotonic()
    print(\"==\", code, \"bars\", 0 if raw is None else len(raw), \"load_s\", round(t1-t0,1))
    if raw is None: continue
    sig = build_signal_frame(raw, code)
    n_fin = int(sig[\"finite\"].sum()); n_cond = int(sig[\"cond\"].sum()); n_edge = int(sig[\"edge\"].sum())
    print(\"finite\", n_fin, \"cond\", n_cond, \"edge\", n_edge)
    print(\"cyqk finite range:\", float(sig[\"cyqk\"].min()), float(sig[\"cyqk\"].max()),
          \"mean\", round(float(sig[\"cyqk\"].mean()),4), \">0.70 count\", int((sig[\"cyqk\"]>0.70).sum()))
    fw = sig[\"finite\"].idxmax() if n_fin else None
    print(\"first finite day:\", fw, \"first week_ma20 finite:\", sig.loc[sig[\"week_ma20\"].notna()].index[0] if sig[\"week_ma20\"].notna().any() else None)
    edges = sig[sig[\"edge\"]]
    print(\"edge dates:\", list(edges.index[:5].astype(str)), \"...\" if len(edges)>5 else \"\")
    run = run_one(code, \"test\", sig, pd.Timestamp(\"20240101\"), 1_000_000.0)
    print(\"trades:\", run.trades[:8], \"events:\", run.events[:8], \"n_buys\", run.n_buys, \"eq_end\", round(run.equity_end,2))
    t2 = time.monotonic()
    print(\"total_s\", round(t2-t0,1))
'@ | D:\\anaconda3\\envs\\vanna312\\python.exe -" in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 71465ms:
[WARN] QuantLoggerFactory not initialized, fallback mode active
[32m2026-09-07 15:51:03.478[0m | [33m[1mWARNING [0m | [36moskh_factors.chip.shares[0m:[36m_get_float_shares[0m:[36m81[0m - [33m[1mcirculating_capital history gap >90 days[0m
[32m2026-09-07 15:51:34.783[0m | [33m[1mWARNING [0m | [36moskh_factors.chip.shares[0m:[36m_get_float_shares[0m:[36m81[0m - [33m[1mcirculating_capital history gap >90 days[0m
== 000001.SZ bars 484 load_s 0.1
finite 390 cond 66 edge 9
cyqk finite range: 0.0002739325246594334 1.0 mean 0.3811 >0.70 count 95
first finite day: 2022-11-18 00:00:00 first week_ma20 finite: 2022-11-18 00:00:00
edge dates: ['2022-11-29', '2022-12-30', '2023-03-01', '2024-02-21', '2024-03-26'] ...
trades: [{'date': '2024-02-22', 'code': '000001.SZ', 'side': 'BUY', 'price': 8.727, 'size': 114500}, {'date': '2024-03-27', 'code': '000001.SZ', 'side': 'BUY', 'price': 8.637, 'size': 115700}, {'date': '2024-03-28', 'code': '000001.SZ', 'side': 'SELL', 'price': 8.587000000000002, 'size': 115700}, {'date': '2024-04-02', 'code': '000001.SZ', 'side': 'BUY', 'price': 8.706999999999999, 'size': 113900}, {'date': '2024-04-03', 'code': '000001.SZ', 'side': 'SELL', 'price': 8.607, 'size': 113900}, {'date': '2024-04-18', 'code': '000001.SZ', 'side': 'BUY', 'price': 8.657, 'size': 113100}, {'date': '2024-04-26', 'code': '000001.SZ', 'side': 'BUY', 'price': 8.667, 'size': 112900}, {'date': '2024-04-29', 'code': '000001.SZ', 'side': 'SELL', 'price': 8.636999999999999, 'size': 112900}] events: [] n_buys 5 eq_end 1005851.42
total_s 35.9
== 000004.SZ bars 484 load_s 0.0
finite 390 cond 55 edge 21
cyqk finite range: 0.0003857187741505325 1.0000000000000002 mean 0.343 >0.70 count 64
first finite day: 2022-11-18 00:00:00 first week_ma20 finite: 2022-11-18 00:00:00
edge dates: ['2022-12-05', '2023-02-01', '2023-04-17', '2023-04-24', '2023-05-04'] ...
trades: [{'date': '2024-03-18', 'code': '000004.SZ', 'side': 'BUY', 'price': 15.02, 'size': 66500}] events: [] n_buys 1 eq_end 1000000.0
total_s 28.9

codex
000004 出现「有 BUY 记录但净值分毫未动」的反常现象，需要解剖它到底是挂单未成交还是记录口径问题。用带 notify_order 的内存子类复跑（仍不写盘）。
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "@'
import pandas as pd
from backtest.research.ma_chip_edge_backtest import (
    load_front_daily, build_signal_frame, run_one, MaChipEdgeStrategy, SignalPandasData, AShareCommInfo,
)
import backtrader as bt

code = \"000004.SZ\"
raw = load_front_daily(code, \"20220701\", \"20240630\")
sig = build_signal_frame(raw, code)
seg = sig.loc[\"2024-03-01\":\"2024-04-15\"]
print(seg[[\"open\",\"high\",\"low\",\"close\",\"volume\",\"edge\"]].to_string())

class Diag(MaChipEdgeStrategy):
    def notify_order(self, order):
        if order.status in (order.Completed, order.Canceled, order.Margin, order.Rejected):
            print(\"ORDER\", order.ordtype, bt.num2date(order.created.dt).date(),
                  \"->\", bt.num2date(order.executed.dt).date() if order.executed.dt else None,
                  \"status\", order.getstatusname(), \"price\", order.executed.price if order.executed.dt else None,
                  \"size\", order.executed.size if order.executed.dt else None)

warmup_from = pd.Timestamp(\"20240101\") - pd.Timedelta(days=14)
feed_df = sig.loc[sig.index >= warmup_from].copy().dropna(subset=[\"open\",\"close\"])
feed_df[\"edge\"] = feed_df[\"edge\"].astype(float)
feed_df[\"sma5\"] = feed_df[\"sma5\"].astype(float)
c = bt.Cerebro(stdstats=False)
c.broker.setcash(1_000_000.0)
c.broker.set_coo(True)
c.broker.addcommissioninfo(AShareCommInfo())
c.adddata(SignalPandasData(dataname=feed_df), name=code)
c.addstrategy(Diag, stock_code=code)
st = c.run()[0]
print(\"trades:\", st.trades)
print(\"events:\", st.events)
print(\"value:\", c.broker.getvalue(), \"cash:\", c.broker.getcash())
'@ | D:\\anaconda3\\envs\\vanna312\\python.exe -" in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 42222ms:
[WARN] QuantLoggerFactory not initialized, fallback mode active
[32m2026-09-07 15:52:39.190[0m | [33m[1mWARNING [0m | [36moskh_factors.chip.shares[0m:[36m_get_float_shares[0m:[36m81[0m - [33m[1mcirculating_capital history gap >90 days[0m
             open   high    low  close    volume   edge
datetime                                               
2024-03-01  12.76  13.16  12.50  12.79  115714.0  False
2024-03-04  12.79  13.66  12.30  13.10  129949.0  False
2024-03-05  12.91  13.02  12.42  12.60   94931.0  False
2024-03-06  12.37  13.86  12.34  13.86  217414.0  False
2024-03-07  13.44  13.77  13.02  13.11  229505.0  False
2024-03-08  13.11  13.50  12.70  13.26  140456.0  False
2024-03-11  13.03  13.74  12.90  13.62  133432.0  False
2024-03-12  13.52  14.00  13.30  13.65  134978.0  False
2024-03-13  13.53  14.40  13.52  13.83  165185.0  False
2024-03-14  13.60  15.21  13.51  15.21  229213.0  False
2024-03-15  15.50  16.73  14.78  15.87  374946.0   True
2024-03-18  15.02  15.88  14.82  15.62  256970.0  False
2024-03-19  15.40  15.48  15.18  15.18  141392.0  False
2024-03-20  15.10  15.31  14.90  15.10  102789.0  False
2024-03-21  15.13  15.21  14.81  14.88   93123.0  False
2024-03-22  15.03  15.08  14.37  14.56   93988.0  False
2024-03-25  14.41  15.12  14.30  14.60   96942.0  False
2024-03-26  14.34  15.04  14.07  14.80   95487.0  False
2024-03-27  14.65  15.00  14.40  14.67   96875.0  False
2024-03-28  14.64  15.50  14.43  15.45  178645.0   True
2024-03-29  15.26  15.37  14.92  15.05   97259.0  False
2024-04-01  15.05  15.19  14.88  14.98   69640.0  False
2024-04-02  15.00  15.11  14.15  14.58   87302.0  False
2024-04-03  14.55  14.55  13.50  13.50   81063.0  False
2024-04-08  13.52  13.79  13.20  13.25   61313.0  False
2024-04-09  13.20  13.33  12.88  13.27   51947.0  False
2024-04-10  13.10  13.28  12.42  12.56   58559.0  False
2024-04-11  12.49  12.92  12.39  12.69   44937.0  False
2024-04-12  12.66  12.89  12.39  12.41   34559.0  False
2024-04-15  11.18  11.91  11.17  11.17   88343.0  False
ORDER 0 2024-03-18 -> 2024-03-19 status Margin price 0.0 size 0
trades: [{'date': '2024-03-18', 'code': '000004.SZ', 'side': 'BUY', 'price': 15.02, 'size': 66500}]
events: []
value: 1000000.0 cash: 1000000.0

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "qlib_cost/__init__.py" | Select-Object -First 1; "--- reader mode/default head ---"; $l=Get-Content -LiteralPath "oskh_data/reader.py"; $l[0..70] -join "`n"' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "rg -rn \"Order\\.Open|exectype=Open|exectype=['\\\"]Open|Order\\.Close|Order\\.Market|Order\\.Limit\" --glob \"*.py\" --glob \"*.md\" . | Select-Object -First 40" in E:\PycharmProjects\MyQuant-backtrader
 exited 1 in 1686ms:
 succeeded in 2211ms:
# pyright: reportUnusedImport=false
# re-export hub — imports consumed by external callers; pyright cannot trace cross-module re-export
"""qlib_cost — 筹码分布纯算法包。

核心算法仅依赖 numpy/pandas/numba，无可视化/外部依赖。
用法::

    from qlib_cost import ChipFactor, calc_dist_chips, calc_cumpdf, calc_curpdf
    from qlib_cost import calc_distribution_of_chips, calc_rc, calc_roll_cyq
"""

from .cyq import ChipFactor, calc_curpdf, calc_cumpdf, calc_dist_chips
from .distribution_of_chips import calc_adj_turnover, calc_triang_pdf, calc_uniform_pdf
from .turnover_coefficient_ops import (
    calc_distribution_of_chips,
    calc_rc,
    calc_roll_cyq,
)
from .utils import rolling_frame, rolling_windows

--- reader mode/default head ---
"""
统一股票数据读取层，支持三种模式：
  parquet          — pd.read_parquet() 逐文件读取（默认，兼容回退）
  duckdb           — DuckDB :memory: + read_parquet(glob) 批量扫描
  duckdb_persistent — DuckDB 连接 .duckdb 持久化文件 + 查表

  配置优先级: 环境变量 STOCK_DATA_READER_MODE > config/reader.yaml > 默认 parquet

  复权类型按物理分文件隔离:
  stock_data_none.duckdb / stock_data_front.duckdb / stock_data_back.duckdb
"""
from __future__ import annotations
from .symbol_format import to_partition_key, to_canonical_symbol

import os
import sys
import threading
import time
from pathlib import Path
from typing import List, Literal, Optional

import duckdb
import pandas as pd

from oskh_data.pandas_typing import as_timestamp, index_normalize_series, normalize_timestamp, timestamp_strftime

from common.infra.quant_logger import get_logger
from common.infra.data_root import resolve_data_root as _resolve_data_root
from common.infra.data_root import resolve_e_stock_data_container as _resolve_e_stock_data_container
from common.infra.data_root import resolve_parquet_container as _resolve_parquet_container
from common.infra.data_root import resolve_period_root as _resolve_period_root

logger = get_logger(__name__)

MINUTE_PERIODS = frozenset({'1m', '5m', '10m', '15m', '30m', '1h'})

# 核心 ETF 代码段正则（防呆用，避免 asset_type="stock" 时误读 ETF 数据）
# Phase 2 P1 fix: added missing Shanghai ETF prefixes 516, 517, 520, 562, 589
_ETF_CODE_PATTERN = (
    r'^(510|511|512|513|515|516|517|518|520|560|561|562|563|588|589|159)\d{3}$'
)

# 复权类型 → DuckDB 文件后缀映射
_ADJUST_DB_SUFFIX: dict[str, str] = {
    'none': '_none',
    'front': '_front',
    'back': '_back',
}

# 需要复权防误用校验的模块前缀
_RESTRICTED_MODULE_PREFIXES = ('live_trading.', 'trade_decision.')
# 允许使用非 none 复权类型的白名单模块
_ADJUST_WHITELIST_MODULES: tuple[str, ...] = (
    'live_trading.indicators.ma_provider',
)

def _resolve_default_mode() -> str:
    """按优先级解析默认 mode: 环境变量 > config/reader.yaml > parquet."""
    from common.infra.constants import EnvVarKeys

    env_val = os.environ.get(EnvVarKeys.OSKH_DATA_READER_MODE) or os.environ.get("STOCK_DATA_READER_MODE")
    if env_val:
        return env_val
    try:
        import yaml

        config_path = _resolve_data_root() / "config" / "reader.yaml"
        if config_path.exists():
            with open(config_path, "r") as f:
                cfg = yaml.safe_load(f) or {}
            yaml_val = cfg.get("mode")

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-ChildItem -Recurse -LiteralPath "docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07" -ErrorAction SilentlyContinue | Select-Object FullName, Length' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1246ms:

FullName
--------                                                                                                               
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_plan…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_prom…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\revie…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…
E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_para…


exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-ChildItem -Recurse -File -LiteralPath "docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName.Substring((Get-Location).Path.Length+1) + " | " + $_.Length }' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1240ms:
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_plan_version.txt | 142
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_prompt.md | 4715
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\review-by-cursor.md | 2284
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_parallel\claude\_plan_version.txt | 142
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_parallel\claude\_prompt.md | 4715
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_parallel\claude\claude.md | 5464
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_parallel\codex\_plan_version.txt | 142
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_parallel\codex\_prompt.md | 4715
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_parallel\codex\codex.md | 5143
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_parallel\cursor-auto\_plan_version.txt | 142
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_parallel\cursor-auto\_prompt.md | 4715
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_parallel\cursor-auto\cursor-auto.md | 322
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_parallel\kimi\_plan_version.txt | 142
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_parallel\kimi\_prompt.md | 4715
docs\architecture\reviews\2026-09-07\plan-ma-chip-edge-strategy-2026-09-07\_parallel\kimi\kimi.md | 5673

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/_parallel/kimi/kimi.md"' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/_parallel/codex/codex.md"' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1263ms:
<!-- agent=kimi cmd-prefix=C:\Users\Thinkpad\.kimi-code\bin\kimi.EXE -m kimi-code/k3 --output-format text -p 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本仓是 **Cerebro / path-SSOT 只读回测叉**：无实盘、无 QMT 下载、无 Redis 流。把握不准可读代码或做实验，以事实为准。

【本仓必查盲区（评审必须逐条核对）】
- **T+1 / 隔日成交**：买入信号能否在当日卖出？卖出是收盘价还是次日开盘？有无用到未来 bar？
- **复权口径**：均线与盈筹率是否同一套 `adjust_type`（本仓筹码默认 front）？
- **盈筹率尺度**：`cyqk_c` 是 0–1 还是 0–100？70% 阈值有无单位错误？
- **周均线定义**：20 周均线是周线 resample 后 SMA(20)，还是 100 日近似？
- **包边界**：算法走 `oskh_factors` / `qlib_cost`，Cerebro 包装走 `backtest/`，研究 CLI 走 `backtest/research/`。

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

【你的评审侧重】优先**跑实验验证关键行为**：对 timeout/budget/safety-valve/并发锁/异步/fallback/重试类设计，构造最小实验（slow fn + tight budget → 测调用方何时返回）。读码不够时动手测——**docstring 不可信**（docstring 宣称的行为可能被 stdlib/框架吞掉，如 `ThreadPoolExecutor.__exit__`→`shutdown(wait=True)` 让超时从不生效）。保持这个习惯。 <prompt> -->


[runner] kimi exit=1
[stderr]
kimi version 0.39.1
error: failed to run prompt: provider.auth_error: 403 You've reached your weekly (7-day) usage limit. Your quota will reset when the current 7-day window ends. To continue now, purchase extra usage or upgrade your plan: https://www.kimi.com/membership/subscription?tab=quota
See log: C:/Users/Thinkpad/.kimi-code/logs/kimi-code.log



 succeeded in 1205ms:
<!-- agent=codex cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.02-c22c1a3\node.EXE C:\Users\Thinkpad\AppData\Roaming\nvm\v24.19.0\node_modules\@openai\codex\bin\codex.js exec --ephemeral 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本仓是 **Cerebro / path-SSOT 只读回测叉**：无实盘、无 QMT 下载、无 Redis 流。把握不准可读代码或做实验，以事实为准。

【本仓必查盲区（评审必须逐条核对）】
- **T+1 / 隔日成交**：买入信号能否在当日卖出？卖出是收盘价还是次日开盘？有无用到未来 bar？
- **复权口径**：均线与盈筹率是否同一套 `adjust_type`（本仓筹码默认 front）？
- **盈筹率尺度**：`cyqk_c` 是 0–1 还是 0–100？70% 阈值有无单位错误？
- **周均线定义**：20 周均线是周线 resample 后 SMA(20)，还是 100 日近似？
- **包边界**：算法走 `oskh_factors` / `qlib_cost`，Cerebro 包装走 `backtest/`，研究 CLI 走 `backtest/research/`。

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


exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/_parallel/cursor-auto/cursor-auto.md"' in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command 'Get-Content -Raw -LiteralPath "docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/_parallel/claude/claude.md"' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1747ms:
<!-- agent=cursor:auto cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.02-c22c1a3\node.exe C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.02-c22c1a3\index.js --model auto -p --output-format text --trust -f --mode plan --workspace E:\PycharmProjects\MyQuant-backtrader <prompt> -->


 succeeded in 1845ms:
<!-- agent=claude cmd-prefix=C:\Users\Thinkpad\AppData\Local\Microsoft\WinGet\Links\claude.EXE -p --no-session-persistence --output-format text --permission-mode bypassPermissions 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本仓是 **Cerebro / path-SSOT 只读回测叉**：无实盘、无 QMT 下载、无 Redis 流。把握不准可读代码或做实验，以事实为准。

【本仓必查盲区（评审必须逐条核对）】
- **T+1 / 隔日成交**：买入信号能否在当日卖出？卖出是收盘价还是次日开盘？有无用到未来 bar？
- **复权口径**：均线与盈筹率是否同一套 `adjust_type`（本仓筹码默认 front）？
- **盈筹率尺度**：`cyqk_c` 是 0–1 还是 0–100？70% 阈值有无单位错误？
- **周均线定义**：20 周均线是周线 resample 后 SMA(20)，还是 100 日近似？
- **包边界**：算法走 `oskh_factors` / `qlib_cost`，Cerebro 包装走 `backtest/`，研究 CLI 走 `backtest/research/`。

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

【你的评审侧重】优先**综合裁决 + 跨文档交叉验证**：检查方案内部自洽（不自相矛盾）、跨节引用一致、与关联 plan/SSOT 的衔接；对抗性复核其他评审员的断言（凭代码/实验驳回误判）。 <prompt> -->
API Error: Request rejected (429) · [1310][您已达到每周/每月使用上限，您的限额将在 2026-09-08 22:34:22 重置。][20260907154554cc0636926d7e4a3c]


[runner] claude exit=1
[stderr]
[claude-code:unrecognized_model] {"model":"glm-5.3","query_source":"generate_session_title"}



exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "rg -n \"exectype=Open|决策时点|20 周均线|涨跌停|ST|none 昨收|ChipDistribution|as_of_date|events.csv|trades.csv|0.70|T\\+1|组合|等额本金|80 日|次日开盘\" docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md" in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "rg -n \"def next|pending_buy|self\\.buy\\(|trades\\.append|pending_sell|hold_mode|buy_ref_close|set_coo|vol <= 0|is_limit_open|def limit_pct|def week_ma20_asof|def cyqk_series|def ready_for_stats|warmup_from|edge\\[0\\]|def run_one\" backtest/research/ma_chip_edge_backtest.py" in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1309ms:
10:研究 CLI：T 日开盘买入，当且仅当 **T-1 四条件全真且可计算**，且 **T-2 四条件全可计算但非全真**。持有：买入日收盘 ≤ T-1 收盘则次日开盘出；否则拿到收盘 < SMA5 的次日开盘出。随机 10 深主板 + 10 沪主板 + 10 创业板，统计窗 2024-01-01 至今。
12:盈筹率 **不** 直接读 `ChipDistribution.cyqk_c[0]`（窗口不含当日、股本无 as_of）。策略内对 **含 T-1 的 80 日窗口** 调 `chip_algorithm` / `oskh_factors.chip`，`as_of_date=T-1`。
18:1. **买入（T 日开盘）**：t-1 价格 > 20 日均线 and > 20 周均线 and > 60 日均线 and 盈筹率 > 70%；t-2 **不同时**满足。
19:2. **持有**：T 收盘 < t-1 价格 → T+1 开盘卖；T 收盘 > T-1 收盘 → 持有到收盘 < 5 日均线。
28:| 决策时点 | 在 **日 D 的 next()**（D 收盘已知）算 `cond[D]`；若边缘成立则 `buy(exectype=Open)` → 成交在 **D+1 开盘**。此时 T=D+1，T-1=D，T-2=D-1 |
31:| 20 周均线 | 按 `oskh_factors.weekly_macd_divergence._daily_to_weekly` 同构：`W-FRI` + `_last_day=max`。asof 键 = `_last_day`，**只 backward** 到 D。未完成周（`_last_day` > D）丢弃。不改 `oskh_factors`（复制 10 行到 research 文件） |
32:| 盈筹率 | 阈值 **0.70**（`get_cyqk_c` 为 0–1）。窗口 = 截至 D 的最近 80 根 **含 D** 的 OHLC；`adapt_columns(..., stock_code=, as_of_date=D)`；再 `daily_chip_distribution` + `ChipFactor(close_D, dist)`。NaN → 该日 cond 不可计算 |
34:| 等号 | 买入日收盘 **≤** T-1 收盘 → 次日开盘卖（fail-closed） |
35:| MA5 离场 | 持有期日 H：`close[0] < sma5[0]` → `sell(exectype=Open)` 次日开。买入日 **禁止任何卖单** |
36:| T+1 | 买入日不挂卖；卖出一律下一根 Open。不接 `TPlus1QueueManager`，用策略状态机保证 |
38:| 涨跌停 / 停牌 | **不成交、不进净值**，写入 `events.csv`（涨停开买 / 跌停开卖 / volume=0）。创业板 20%、主板 10%、ST 5%；昨收用 **none 昨收** 若拿得到，否则本轮用 front 昨收并在 summary 声明偏差 |
43:| 组合 | **单票独立 Cerebro + 等额本金**（新模式，不同于 `chip_selection_backtest` 多 feed 共享资金）。事后等权拼净值 |
45:| 输出 | `backtest_output/ma_chip_edge_{seed}_{end}/`：`universe.csv` `trades.csv` `events.csv` `per_stock_stats.csv` `summary.md` |
51:口径按 §2 补齐后可行。`ChipDistribution` warmup 单测只证明 NaN≠0，**不**证明本策略。周线 asof 按 `_daily_to_weekly` 本地复制。次新不够 20 周则重抽。
61:- 优点：时间因果锁死；单测可覆盖边缘 / T+1 / MA5 / T-2 NaN。
62:- 缺点：30 只不能代表全市场；`cyqk_c>0.70` 在仓内文档是抛压区，本轮只验证框架。
72:   - 买入日收阴/收平 → 次日开盘卖
73:   - 买入日收阳 → 直到收盘 < SMA5 的次日开盘卖
84:- 改 `ChipDistribution` / `oskh_factors` / `qlib_cost`
86:- 精细涨跌停撮合（只 skip）

 succeeded in 1191ms:
55:def limit_pct(code: str) -> float:
62:def is_limit_open(code: str, open_px: float, prev_close: float, *, up: bool) -> bool:
70:def week_ma20_asof(close: pd.Series) -> pd.Series:
87:def cyqk_series(df: pd.DataFrame, stock_code: str, window: int = CHIP_WINDOW) -> pd.Series:
183:        self.pending_buy = False
184:        self.pending_sell = False
185:        self.hold_mode: Optional[str] = None
186:        self.buy_ref_close: Optional[float] = None
194:    def next(self):
203:        if self.pending_sell and self.position:
204:            if vol <= 0 or is_limit_open(code, o, prev_c, up=False):
208:                self.trades.append(
217:            self.pending_sell = False
218:            self.hold_mode = None
219:            self.buy_ref_close = None
222:        if self.pending_buy and not self.position:
223:            if vol <= 0 or is_limit_open(code, o, prev_c, up=True):
228:                    self.buy(size=size)
229:                    self.hold_mode = "first_day"
230:                    self.buy_ref_close = prev_c
233:                    self.trades.append(
236:            self.pending_buy = False
238:        if self.hold_mode == "first_day" and (self.position or bought_today):
239:            if self.buy_ref_close is not None and c <= self.buy_ref_close:
240:                self.pending_sell = True
242:                self.hold_mode = "ma5"
243:        elif self.hold_mode == "ma5" and self.position:
245:                self.pending_sell = True
249:        if (not self.position) and (not self.pending_sell) and float(self.data.edge[0]) > 0.5:
250:            self.pending_buy = True
310:def ready_for_stats(sig: pd.DataFrame, stats_start: pd.Timestamp) -> bool:
317:def run_one(code: str, board: str, sig: pd.DataFrame, stats_start: pd.Timestamp, cash: float) -> RunResult:
318:    warmup_from = stats_start - pd.Timedelta(days=14)
319:    feed_df = sig.loc[sig.index >= warmup_from].copy()
325:    cerebro.broker.set_coo(True)

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command '$l=Get-Content -LiteralPath "backtest/research/ma_chip_edge_backtest.py"; $l[175..265] -join "`n"' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1939ms:
    skip_reason: str = ""


class MaChipEdgeStrategy(bt.Strategy):
    params = (("stock_code", ""),)

    def __init__(self):
        self.pending_buy = False
        self.pending_sell = False
        self.hold_mode: Optional[str] = None
        self.buy_ref_close: Optional[float] = None
        self.trades: list[dict] = []
        self.events: list[dict] = []
        self._entry_price = 0.0

    def _dt(self) -> date:
        return self.data.datetime.date(0)

    def next(self):
        code = self.p.stock_code
        o = float(self.data.open[0])
        c = float(self.data.close[0])
        vol = float(self.data.volume[0])
        sma5 = float(self.data.sma5[0])
        prev_c = float(self.data.close[-1]) if len(self.data) > 1 else np.nan
        d = self._dt().isoformat()

        if self.pending_sell and self.position:
            if vol <= 0 or is_limit_open(code, o, prev_c, up=False):
                self.events.append({"date": d, "code": code, "event": "skip_sell", "open": o})
            else:
                self.sell(size=self.position.size)
                self.trades.append(
                    {
                        "date": d,
                        "code": code,
                        "side": "SELL",
                        "price": o,
                        "size": int(self.position.size),
                    }
                )
            self.pending_sell = False
            self.hold_mode = None
            self.buy_ref_close = None

        bought_today = False
        if self.pending_buy and not self.position:
            if vol <= 0 or is_limit_open(code, o, prev_c, up=True):
                self.events.append({"date": d, "code": code, "event": "skip_buy", "open": o})
            else:
                size = int(self.broker.getcash() / o / 100.0) * 100
                if size >= 100:
                    self.buy(size=size)
                    self.hold_mode = "first_day"
                    self.buy_ref_close = prev_c
                    self._entry_price = o
                    bought_today = True
                    self.trades.append(
                        {"date": d, "code": code, "side": "BUY", "price": o, "size": size}
                    )
            self.pending_buy = False

        if self.hold_mode == "first_day" and (self.position or bought_today):
            if self.buy_ref_close is not None and c <= self.buy_ref_close:
                self.pending_sell = True
            else:
                self.hold_mode = "ma5"
        elif self.hold_mode == "ma5" and self.position:
            if np.isfinite(sma5) and c < sma5:
                self.pending_sell = True

        if len(self.data) < 2:
            return
        if (not self.position) and (not self.pending_sell) and float(self.data.edge[0]) > 0.5:
            self.pending_buy = True


def _list_float_codes() -> set[str]:
    path = resolve_source_parquet("float_shares.parquet")
    if not path.is_file():
        return set()
    s = pd.read_parquet(path, columns=["stock_code"])["stock_code"].astype(str)
    return {to_canonical_symbol(x.replace(".", "_")) if "." not in x else x for x in s}


def _list_front_hive_codes() -> set[str]:
    root = resolve_period_root("1d") / "dividend_type=front"
    if not root.is_dir():
        return set()
    out: set[str] = set()
    for p in root.iterdir():

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "rg -n \"range\\(-self.p.period, 0\\)|close_price = float|adapt_columns\\(df, stock_code|def next\\(self\\)|def _daily_to_weekly|def adapt_columns|def daily_chip_distribution|as_of_date|def get_cyqk_c|def get_winner|def compute_crossday|def compute_chip_factors\" backtest/chip_indicator.py oskh_factors/chip/core.py oskh_factors/weekly_macd_divergence.py qlib_cost/cyq.py" in E:\PycharmProjects\MyQuant-backtrader
exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command '$p="D:'"\\anaconda3\\envs\\vanna312\\Lib\\site-packages\\backtrader\\order.py\"; (Get-Content -LiteralPath "'$p)[235..248] -join "`n"; "--- bbroker ---"; $b="D:'"\\anaconda3\\envs\\vanna312\\Lib\\site-packages\\backtrader\\brokers\\bbroker.py\"; (Get-Content -LiteralPath "'$b)[720..740] -join "`n"; "--- bbroker created-check ---"; (Get-Content -LiteralPath $b)[855..865] -join "`n"' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1193ms:
qlib_cost/cyq.py:184:    def get_cyqk_c(self) -> float:
qlib_cost/cyq.py:229:    def get_winner(self, price: float) -> float:
backtest/chip_indicator.py:96:    def next(self):
backtest/chip_indicator.py:104:                [self.data.close[i] for i in range(-self.p.period, 0)],
backtest/chip_indicator.py:108:                [self.data.high[i] for i in range(-self.p.period, 0)],
backtest/chip_indicator.py:112:                [self.data.low[i] for i in range(-self.p.period, 0)],
backtest/chip_indicator.py:116:                [self.data.volume[i] for i in range(-self.p.period, 0)],
backtest/chip_indicator.py:123:            arr = adapt_columns(df, stock_code=self.p.stock_code or None)
backtest/chip_indicator.py:161:            close_price = float(self.data.close[0])
backtest/chip_indicator.py:224:    def next(self):
backtest/chip_indicator.py:230:                [self.data.turnover_rate[i] for i in range(-self.p.period, 0)],
backtest/chip_indicator.py:234:                [self.data.close[i] for i in range(-self.p.period, 0)],
backtest/chip_indicator.py:241:                    [self.data.volume[i] for i in range(-self.p.period, 0)],
oskh_factors/weekly_macd_divergence.py:27:- ``as_of_date`` = 扫描快照日（provenance，非 point-in-time）。前复权 repaint
oskh_factors/weekly_macd_divergence.py:77:    as_of_date: str  # 扫描快照日（provenance）
oskh_factors/weekly_macd_divergence.py:86:def _daily_to_weekly(daily: pd.DataFrame) -> pd.DataFrame:
oskh_factors/weekly_macd_divergence.py:175:    as_of_date: str,
oskh_factors/weekly_macd_divergence.py:207:                as_of_date=as_of_date,
oskh_factors/weekly_macd_divergence.py:225:    as_of_date: str = "",
oskh_factors/weekly_macd_divergence.py:242:    return _assess_trend_and_grade(events, weekly, stock_code, as_of_date)
oskh_factors/chip/core.py:28:def adapt_columns(
oskh_factors/chip/core.py:31:    as_of_date: Optional[pd.Timestamp] = None,
oskh_factors/chip/core.py:44:        as_of_date: 可选，按该日期查询历史股本（用于回测避免前视）
oskh_factors/chip/core.py:53:            float_shares = _get_free_float_shares(stock_code, date=as_of_date)
oskh_factors/chip/core.py:55:            float_shares = _get_float_shares(stock_code, date=as_of_date)
oskh_factors/chip/core.py:68:def daily_chip_distribution(arr: np.ndarray, method: str = "triang") -> pd.Series:
oskh_factors/chip/core.py:271:def compute_chip_factors(
oskh_factors/chip/core.py:294:    as_of_date = None
oskh_factors/chip/core.py:296:        as_of_date = cast(pd.Timestamp, pd.Timestamp(str(df.index[-1]))).normalize()  # pyright: ignore[reportAttributeAccessIssue]
oskh_factors/chip/core.py:297:    arr = adapt_columns(df, stock_code=stock_code, as_of_date=as_of_date)
oskh_factors/chip/core.py:308:                as_of_date=daily_as_of,
oskh_factors/chip/core.py:320:    close_price = float(arr[-1, 0])  # 最新 bar 的 close
oskh_factors/chip/core.py:407:def compute_crossday_turnover_resistance(
oskh_factors/chip/core.py:418:    分母为今日窗口 adapt_columns 末行 turnover_rate（arr_t[-1, 4]），按 as_of_date 查股本。
oskh_factors/chip/core.py:435:    arr_t = adapt_columns(df_t, stock_code=stock_code, as_of_date=as_of_t)
oskh_factors/chip/core.py:457:    arr_y = adapt_columns(df_y, stock_code=stock_code, as_of_date=as_of_y)
oskh_factors/chip/core.py:513:    arr = adapt_columns(df_w, stock_code=stock_code, as_of_date=as_of)

 succeeded in 1110ms:
    # Time Restrictions for orders
    T_Close, T_Day, T_Date, T_None = range(4)

    # Volume Restrictions for orders
    V_None = range(1)

    (Market, Close, Limit, Stop, StopLimit, StopTrail, StopTrailLimit,
     Historical) = range(8)
    ExecTypes = ['Market', 'Close', 'Limit', 'Stop', 'StopLimit', 'StopTrail',
                 'StopTrailLimit', 'Historical']

    OrdTypes = ['Buy', 'Sell']
    Buy, Sell = range(2)

--- bbroker ---
            # if part/all of a position has been closed, then there has been
            # a profitandloss ... record it
            pnl = comminfo.profitandloss(-closed, pprice_orig, price)
            cash = self.cash
        else:
            pnl = 0
            if not self.p.coo:
                price = pprice_orig = order.created.price
            else:
                # When doing cheat on open, the price to be considered for a
                # market order is the opening price and not the default closing
                # price with which the order was created
                if order.exectype == Order.Market:
                    price = pprice_orig = order.data.open[0]
                else:
                    price = pprice_orig = order.created.price

            psize, pprice, opened, closed = position.update(size, price)

        # "Closing" totally or partially is possible. Cash may be re-injected
        if closed:
--- bbroker created-check ---
            dtcoc = order.created.dt
            exprice = order.created.pclose
        else:
            if not self.p.coo and order.data.datetime[0] <= order.created.dt:
                return    # can only execute after creation time

            dtcoc = None
            exprice = popen

        if order.isbuy():
            p = self._slip_up(phigh, exprice, doslip=self.p.slip_open)

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command '$l=Get-Content -LiteralPath "docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md"; for($i=0; $i -lt $l.Count; $i++){ "{0}: {1}" -f ($i+1), $l[$i] } | Select-Object -Skip 45' in E:\PycharmProjects\MyQuant-backtrader
 exited 1 in 903ms:
ParserError: 
Line |
   2 |  �� i=0; $i -lt $l.Count; $i++){ "{0}: {1}" -f ($i+1), $l[$i] } | Select- ��
     |                                                                ~
     | An empty pipe element is not allowed.

exec
"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command '$l=Get-Content -LiteralPath "docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md"; $out=@(); for($i=0; $i -lt $l.Count; $i++){ $out += ("{0}: {1}" -f ($i+1), $l[$i]) }; $out[45..($out.Count-1)] -join "`n"' in E:\PycharmProjects\MyQuant-backtrader
 succeeded in 1034ms:
46: 
47: ## 3. 方案取舍
48: 
49: ### 3.1 可行性
50: 
51: 口径按 §2 补齐后可行。`ChipDistribution` warmup 单测只证明 NaN≠0，**不**证明本策略。周线 asof 按 `_daily_to_weekly` 本地复制。次新不够 20 周则重抽。
52: 
53: ### 3.2 必要性
54: 
55: 必须单独 research CLI。策略放 CLI 同文件，不进 `backtest/` 根。不并入 rolling。
56: 
57: 对抗 dissent 主张「先全市场扫描、先改 Indicator」：**驳回**。用户本轮要的是可下单的试验框架 + 30 只表现；全市场与 Indicator 修补单开。
58: 
59: ### 3.3 优缺点
60: 
61: - 优点：时间因果锁死；单测可覆盖边缘 / T+1 / MA5 / T-2 NaN。
62: - 缺点：30 只不能代表全市场；`cyqk_c>0.70` 在仓内文档是抛压区，本轮只验证框架。
63: - `summary.md` **禁止**写「策略有效 / 因子有效」，只报触发数、收益、回撤、skip 事件数。
64: 
65: ## 4. 实施步骤
66: 
67: 1. `backtest/research/ma_chip_edge_backtest.py`：抽样、加载、策略、报告。
68: 2. `tests/test_ma_chip_edge_strategy.py`（合成数据，不依赖 F 盘）：
69:    - D 满足、D-1 不满足且有限 → D+1 开盘买
70:    - D 与 D-1 都满足 → 不买
71:    - D-1 为 NaN → 不买
72:    - 买入日收阴/收平 → 次日开盘卖
73:    - 买入日收阳 → 直到收盘 < SMA5 的次日开盘卖
74:    - 买入日 next() 内不得卖
75: 3. 跑 30 只试验。
76: 
77: ```powershell
78: D:\anaconda3\envs\vanna312\python.exe backtest/research/ma_chip_edge_backtest.py --seed 20240907 --start 20240101
79: ```
80: 
81: ## 5. 本轮不做
82: 
83: - 价格约束、量约束
84: - 改 `ChipDistribution` / `oskh_factors` / `qlib_cost`
85: - 全市场扫描、分钟线、实盘、LEBS
86: - 精细涨跌停撮合（只 skip）
87: 
88: ## 6. 验证
89: 
90: - 单测全绿。
91: - 30 只 exit 0；打印每板只数、触发买入数、等权收益、skip 数。
92: - `scripts/gates/verify_oskh_data_contract.py` 绿。
93: 
94: ## 7. 关闭条件
95: 
96: - §2 出现在 CLI `--help`。
97: - 同一 seed 的 `universe.csv` 可复现。
98: - fan-out 无新架构 🔴，或剩余 🔴 已降为 §5。


