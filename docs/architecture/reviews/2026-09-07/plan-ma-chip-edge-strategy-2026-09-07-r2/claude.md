<!-- agent=claude cmd-prefix=C:\Users\Thinkpad\AppData\Local\Microsoft\WinGet\Links\claude.EXE -p --no-session-persistence --output-format text --permission-mode bypassPermissions 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07-r2/_parallel/<agent>/<agent>.md`。
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
所有关键断言已取证完毕（源码 + 3 组最小实验）。以下为综合裁决评审意见：

---

# 综合裁决评审：`docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md`（v3）

> 评审侧重：综合裁决 + 跨文档交叉验证。已读 r1 产物（`merge-consensus.md` / `review-by-cursor.md`）、kimi-k3-high 并行评审（已交叉核对其 R1–R4/O1–O5 与 E1–E3）、仓内实现 `backtest/research/ma_chip_edge_backtest.py`（commit e9204ab）与关联 SSOT 代码。**事实类断言均经源码取证或本人亲自复现实验**；kimi R1 已亲自复现确认（非仅引用）。

## 本人实验（可复现，PYTHONDONTWRITEBYTECODE=1，无文件写入）

**E-A/B/C（COO 成交时点，5-bar 合成 feed，edge 在 2024-01-04）**
```
A no-coo next_open -> [(2024-01-04, 10.0)]   # cheat_on_open+next_open，无 set_coo：同日开盘成交
B coo next_open     -> [(2024-01-04, 10.0)]   # 加 set_coo：结果相同 → set_coo 冗余但无害
C coo-only next()   -> [(2024-01-05, 10.0)]   # 仅 set_coo、next() 下单：下一根开盘成交
```
**E-R1（复现 kimi R1 停牌缺口）**：edge 于 01-03，停牌至 01-24 复牌：
```
trades: [('2024-01-24', 'BUY', 15.0)]   events: []   ← stale 信号静默成交，零事件
```
**E-R2（我的新发现，卖日 edge 重入）**：01-05 开盘卖 + 当日 edge=1：
```
trades: [('2024-01-04','BUY',10.5), ('2024-01-05','SELL',8.5)]   events: []   ← 卖日信号被静默丢弃
```

## 🔴 必须修

**R1（kimi R1，本人复现 CONFIRMED）：`pending_buy` 无过期机制，停牌缺口后 stale 买入静默成交**
- plan §2「决策时点」锁定「可测行为：D+1 开盘买或 skip」是二值口径；实测存在第三条路径「D+n 开盘买（n=停牌天数）」。停牌期间无 bar → `next_open` 不触发 → volume=0/涨停检查无从执行 → 3 周前的信号在复牌日成交，且 events.csv 零痕迹（E-R1 输出）。与 §2「skip_buy 消耗该次信号」意图冲突，会静默污染 30 只样本统计。
- 证据：`backtest/research/ma_chip_edge_backtest.py:387-395`（pending_buy 仅在 next_open 内消费，无 bar 则不消费，无过期）。
- 修法：实现一行级（置 pending 时记 `len(self.data)`，仅下一根 bar 允许买，否则记 `skip_buy(stale)` 并消耗）；plan §2「skip 后 FSM」行补一句「pending_buy 仅对信号日下一根 bar 有效；跨 bar 一律 skip_buy 并消耗」+ 对应单测（停牌缺口 → skip_buy(stale)）。
- 附议 kimi：pending_sell 不需对称修复（skip_sell 重试正是 plan 想要的行为，且持仓是真仓非 stale 信号）。

## 🟡 应修

**Y1（我的发现）：`_sold_today` 守卫静默丢弃「卖日 edge 重入」信号，plan 未定义此口径**
- 实现 `backtest/research/ma_chip_edge_backtest.py:413-421`：卖单在 S 日开盘完成后，S 日 next() 因 `not self._sold_today` 被整体跳过 → S 日 edge 信号既不买入也无任何事件（E-R2 复现）。T+1 规则下「S 日卖、S+1 开买」本合法；plan §2「仓位」行只锁了「单票最多 1 笔；已持仓忽略新开」，未覆盖「平仓当日即触发 edge」场景。二选一：plan 补一句「卖日不重入（保守）」或实现放开并记事件。当前实现比 plan 严格且无痕，属口径缺口。

**Y2（kimi R2，code-verified，附议）：「未完成周丢弃」字面与实现不符**
- plan §2「20 周均线」行「未完成周丢弃」；实现 `ma_chip_edge_backtest.py:100-114` 的 `week_ma20_asof` 在 D=数据末端时，末段 partial week 的 `_last_day`（=D 自身）≤ D，会参与计算（其周收盘=D 当日收盘，无未来价，因果安全）。仅影响统计窗最末 1–5 个交易日，量级小；且此行为与 plan「sma 含 D 合法」哲学更一致。建议按 kimi 方案改 plan 措辞（「未完成周仅在其 _last_day ≤ D 时参与」），不动代码。

**Y3（我的发现）：plan §4 锁定 9 条单测，`tests/test_ma_chip_edge_strategy.py` 实缺 2 条直接覆盖**
- 缺「D 与 D-1 都满足 → 不买」（现有 test_edge_requires_finite_prev_and_false_prev 只证首日有限非 edge，未证 cond 连续两日 True 次日不 edge）；缺「买入日收阳 → 直到收盘 < SMA5 的次日开盘卖」（MA5 离场路径无永久单测，kimi E2 case2 只是一次性验证）；收平（==）case 亦仅收阴覆盖。plan §6「单测全绿」会误报完成度。补两条合成数据单测即可。

## 🟢 可选

- **G1（kimi O1，实验佐证）**：§2 括注「仅 broker.set_coo 不够，订单会落到下一根开盘」——可观察结果对（我 E-C：仅 set_coo + next() 下单 → 下一根开盘成交），机理措辞可更精确：无 cheat_on_open 时 `next_open` 根本不被调用（`cerebro.py:1622-1624` 由 `p.cheat_on_open` 门控）。另据我 E-A：cheat_on_open+next_open 即使**不加** set_coo 也同日开盘成交，实现里 `set_coo(True)`（:500）冗余但无害，不必改。
- **G2**：§2「决策时点」行写「在日 D 的 next() 算 cond[D]」，已落地实现是 pandas 预计算信号帧（`build_signal_frame`）+ feed `edge` 线，结构不同但时序语义等价（逐日 asof 正确）。plan 可明示预计算路径合法，避免后人按字面重构。
- **G3（kimi R3，我降级为 🟢）**：§2 禁令对象 `oskh_data.float_shares` 模块不存在（仓内只有 `float_shares_history.py`，已 deprecated）——但该名恰在 CI gate 禁入名单（`scripts/gates/verify_oskh_data_contract.py:59`），禁令有 gate 背书、精神正确（勿绕 `resolve_source_parquet`）。改写为可执行口径即可，无实际风险。
- **G4（kimi R4，我降级为 🟢）**：events.csv 未按 stats_start 过滤（`ma_chip_edge_backtest.py:511` vs trades :506）——但 edge 掩码（`mask_pre_window_edges`）保证窗前无任何订单产生，污染路径实际不存在；对称过滤属防御性卫生，顺手可做。
- **G5（kimi O4，附议）**：`DEFAULT_CASH=1e6/票` 未写进 §2「组合」行，复现性建议锁定进 plan。

## ✅ 做对的地方（保留）

1. **T+1/成交链路正确**：`cheat_on_open=True, runonce=False` + `next_open()` 下 Market，D 收盘决策、D+1 开盘成交，无未来 bar——源码（`cerebro.py:1622-1628`、`bbroker.py:853-870`）+ 我 E-A/B/C 三方印证；禁用 `bt.Order.Open` 有据（本仓 `bt.Order` 无 `Open`，merge-consensus R1 已验）。
2. **复权口径统一**：均线与盈筹率同一份 `period=1d adjust_type=front` OHLC；禁用 `load_single_stock_data` 有据（`backtest/qmt_utils_adv.py:62-70` 确为 1m + `adjust_type="none"`）。
3. **cyqk_c 尺度**：`qlib_cost/cyq.py:184-193` `get_cyqk_c→get_winner`，:229-245 累计比例 0–1；阈值 0.70 无单位错误。
4. **不读 `ChipDistribution.cyqk_c[0]` 的理由全部属实**：窗口 `range(-period, 0)` 不含当日（`backtest/chip_indicator.py:104-118`）、`adapt_columns` 未传 `as_of_date`（:123）→ 股本无 asof。
5. **20 周均线**：真周线 W-FRI SMA(20)，同构 `_daily_to_weekly`（`oskh_factors/weekly_macd_divergence.py:47,86-104`），asof 键 `_last_day` 只 backward，非 100 日近似；本地复制、不改 oskh_factors，合包边界。
6. **包边界/SSOT**：`backtest/chip_algorithm.py` 是 `oskh_factors.chip` 的纯 re-export（头注 "Do not add algorithm here"）；CLI 落 `backtest/research/` 与 README.md:12 布局一致；抽样池 `resolve_period_root ∩ resolve_source_parquet`（`common/infra/data_root.py:188-249`），股本路径 `stock_data_path→resolve_source_parquet`（`oskh_factors/chip/paths.py:16-24`）同源，无 cwd 裸路径。
7. **费用**：万 0.5 + 最低 5 元 + 卖出印花税 0.05%（2023-08-28 起口径，2024+ 统计窗正确）；自写 `CommInfoBase`，不硬套 `trade_fee_policy`（repo 根独立模块，非 bt.CommInfoBase，禁令成立）。
8. **统计窗防污染**：窗前 edge 置假（保留窗前最后一日可窗内首日买入，语义正确）+ 加载自 2022-07-01（80 日筹码 + 60 日 + 20 周预热充足）+ `ready_for_stats` 重抽；trades 过滤 stats_start。
9. **跨文档自洽**：TL;DR/§1/§2 等号口径三处一致（≤ fail-closed）；边缘「两边有限」与 TL;DR「T-2 全可计算但非全真」一致；§2 与 merge-consensus R1–R3/Y1–Y5 的吸收关系可追溯、无自相矛盾；§7 关闭条件「§2 进 --help」已实现（HELP_LOCK 含成交方式/等号/skip FSM/统计窗四要点）。
10. **skip FSM 方向**：skip_sell 保留 pending 重试、skip_buy 消耗信号，plan/实现/单测三方一致。

## 总评

方案口径锁定质量高，我核对的全部事实断言（复权、cyqk_c 尺度、ChipDistribution 窗口、周均线定义、COO 成交机制、包边界、path-SSOT）均取证为真，内部自洽、与 r1 吸收记录一致。唯一实质缺口是 **R1：pending_buy 跨停牌缺口无过期**——与 §2「D+1 开盘买或 skip」二值锁定直接矛盾且静默无日志（已亲测复现），必须修；Y1（卖日重入口径未定义）与 Y2（未完成周措辞）建议同轮吸收。**修掉 R1（plan 补一句 + 一行级实现修复 + 单测）后，可进实现；已存在的实现应回补该修复。**
