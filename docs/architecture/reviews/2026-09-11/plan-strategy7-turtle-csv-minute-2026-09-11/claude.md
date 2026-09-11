<!-- agent=claude cmd-prefix=C:\Users\Thinkpad\AppData\Local\Microsoft\WinGet\Links\claude.EXE -p --no-session-persistence --output-format text --permission-mode bypassPermissions 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-strategy7-turtle-csv-minute-2026-09-11.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-11/plan-strategy7-turtle-csv-minute-2026-09-11/_parallel/<agent>/<agent>.md`。
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
# 评审：`docs/backtest/plan-strategy7-turtle-csv-minute-2026-09-11.md`（v1.1）

**评审侧重**：综合裁决 + 跨文档交叉验证。已逐项对码取证；并行目录里 `claude.md`/`codex.md` 仅含 prompt 头（48 行全为注释）、`cursor-auto`/`cursor-kimi` 各 1 行——**无可交叉的已完成同行意见**；仅 host 的 `review-by-cursor.md` 可核，其 11 条让步我逐条对码验证均属实（见 ✅6/7/8/9）。本 plan 无 timeout/budget/并发类设计，★ 强制实验不触发；仅对「指数湖已补齐」做了只读取证（见 ✅2）。

---

## 🔴 必须修

**R1 · 指数闸暖机「≥10 个交易日」差一天，`gate[start]` 按本文公式不可算，与自家「暖机不足→抛错」自相矛盾**
- 证据：plan.md:207「preload：`--start` 之前 ≥10 个交易日」；plan.md:205「连续两个**已完成**交易日收盘 < MA10 → 禁新开」。
- 推导：`gate[T]` 需要 `close[T-1]<MA10[T-1]` **且** `close[T-2]<MA10[T-2]`；`MA10[T-2]` 需要收盘价 `[T-11 .. T-2]`。预载恰好 10 个交易日（`[T-10..T-1]`）时缺 `T-11`：
  - 严格实现 → 首跑必抛「暖机不足」（文档给的最小值永远不够，规格自矛盾）；
  - 宽松实现（`rolling(10)` 出 NaN → 比较为 False）→ **首日闸静默放宽**，而 §11 验收只看窗内闸日，恰好测不到第一天。
- 修法一句话：preload 改「≥ **11** 个交易日」（或明文规定 streak 从 `MA10[T-2]` 可得之日起评，首日按 block 保守）；§8.6 补边界用例「恰好 10 日预载必须被拒」。参考：策略 6 的 `WARMUP_DAYS=10` 是**日历日**暖机（csv_daily_backtest.py:50 + :241-242 `pd.Timedelta(days=int(days))`），用途不同，不能照搬数字——plan.md:87 对这一点的批评本身准确。

## 🟡 应修

**Y1 · 交替止盈「当时加权成本」冻结时点未定义，且未满仓触发 band 后与加仓/计时的交互空白**
- plan.md:176-177「档位 = **当时**加权成本 ×[1.3,1.5,1.8,2.0]」「未满仓也可触发」。若 band1 在 7 成触发（×1.10 加仓被涨停禁买跳过后完全可能）、随后又加到 9 成，band2–4 基准是否随 avg 重算？band 卖出后 `stage` 是否维持、5 日计时（仅未满 9 成适用，plan.md:197）是否仍挂着？规则引擎需要确定答案，建议：档位在 band1 首触发时冻结、band 卖出不改 stage。

**Y2 · `load_daily_bars` 静默丢票 → 昨收缺失时该票当日行为未定义**
- csv_daily_backtest.py:401-404：`except Exception: continue`，读失败/空 df 的票直接从返回 dict 消失。v7 拿它取昨收算涨跌停（plan.md:114）；缺昨收时该票是 skip 当日还是无涨停约束地交易？应对齐 H-R15 的「股票缺数不升格进程失败、当日该票 skip」并记 reason。

**Y3 · §7 reason 最低集与 §4.1 承诺不闭环**
- plan.md:112「现金不够则该腿 skip 并 **记 reason**」，但 §7 表无 `skip_cash`；开盘跌停 defer（plan.md:115）、缺 14:55 不开仓（plan.md:113）也无码。§11 人工验收靠这些对账，建议补 `skip_cash` / `defer_limit_down` / `skip_no_1455`。

## 🟢 可选

1. **H-R10 触发词**「清空可卖腿」（plan.md:31）建议改为「清仓至 0（flat）」：减试错后可卖腿也是 0 但仓位仍在，「新开」语义本不适用，字面实现易误判。
2. `write_run_artifacts(out_dir, st: SimState, ...)` 实际只读 `st.trades`/`st.equity_curve`（csv_daily_backtest.py:770-775）；白名单允许 import 它又禁 `SimState`——plan 补一句「传 duck-typed 自有账本」，防实现者顺手 import `SimState` 违禁。
3. `--end` 超股票 1m 湖尾（`MINUTE_LAKE_END="20260909"`，csv_daily_backtest.py:52，未入白名单）时应显式报错，否则按 H-R15 逐日 skip 会静默产出零交易空跑。
4. §5 只提醒清 `OSKH_PERIOD_*`；指数树唯一 env 劫持面是 `OSKH_INDEX_DAILY_ROOT`（data_root.py:241-244 明言**永不读** `OSKH_PERIOD_1D_ROOT`），可补一句。
5. 「v7 自己的 cache 文件名」实际只能靠独立 `cache_dir` 实现——文件名 `minute_none_{start}_{end}.parquet` 在函数内写死（csv_minute_backtest.py:177-179），`cache_dir` 是参数。写明「独立目录」即可。
6. 实测池每日仅 ~2–3 票（`stock_pool_turtle` 23 个 CSV 共 69 行），3×90 万 ≪ 2100 万现金，§4.1「受现金约束」与 jump_nine 现金 skip 分支现窗基本不会触发——不是错，供 slice E 预期管理。
7. 3a 后 7 成无止损（H-R12 人裁）风险量级：约 70 万敞口、最长 5 个交易日内仅剩 `cost×1.3` 与计时两条退出。已声明偏离且有暴跌单测（§8.2），不重开裁决；建议 summary.txt 加一行「无止损窗口持仓统计」便于事后复盘。

## ✅ 做对的地方（保留）

1. **允许/禁止 import 双清单与代码 100% 对得上**（逐项核验）：白名单全部真实存在——`utc_ms_range`/`warn_stale_period_env`/`_ymd`/`round_fen`/`hit_limit_up`/`hit_limit_down`/`_limit_prices`/`load_pool_days`/`load_daily_bars`/`write_run_artifacts`/`COMMISSION=0.001`（csv_daily_backtest.py:41,228-383,766）、`resolve_period_root`/`resolve_index_daily_root`（common/infra/data_root.py:192,256）、`classify_daily_lake_kind`（oskh_data/lake_kind.py:36）、`to_partition_key`（oskh_data.symbol_format）、`TURTLE_ADD_BANDS`（trade_decision/turtle/buy.py:12，**本仓内**，非 1.3 依赖）。被禁符号也全部真实存在（`execute_buy`:638、`_sell`:681、`SimState`:100、`chase_decision`:219、`summarize`:706、`maybe_compare_daily`:849、`scan_held_day` csv_minute:390）——禁令有的放矢，非稻草人。
2. **指数湖可用性实测通过（只读实验）**：`F:/stock_data/index/period=1d/dividend_type=none/symbol=000001_SH/data.parquet` 存在，5328 行、2004-10-13→**2026-09-11**、2026-07-15..09-11 共 43 行、窗内 `close<=0` 为 0；且 2004–2014 逐年全部行 close≤0（共 2485 行坏值）——H-R15「close≤0 → 抛错」不是过度设计，是真的会踩的坑。复现：`pd.read_parquet(<上述路径>)` 后按 `time`(ms,UTC) 分年统计 `close<=0`。
3. **§2 对照表与 1.3 源码逐字吻合**：1.3 `trade_decision/turtle/stop.py:40-56`「trial avg×0.96；==1 → avg×1.01；else avg×1.02」，与 plan §2 Paper 列三个数字全对上；本仓确无 `turtle/stop.py`（仅 buy/sell），H-R9 属实。
4. **数字基线全对**：`DEFAULT_TOTAL_CASH=21_000_000.0`（csv_daily_backtest.py:39）、佣金 0.001 双边无最低（:41 注释与分钟链 cerebro 对齐）、`BUY_HM=14*60+55=895`（csv_minute_backtest.py:72）、`hm=utc.hour*60+utc.minute` 无时区二次转换（:149）、湖钟点标 UTC（csv_daily_backtest.py:233 docstring）——§4.1/H-R11 各条有据。
5. **`_buy_px` 14:30–14:55 回退真实存在**（csv_minute_backtest.py:472 `hm>=14*60+30 …取最后一根`），H-R11 禁回退是对真实行为的精准禁令；`can_sell=(n_days>=1)` 仓位级 T+1 也真实存在（:553），H-R5 改 lot 级有据。
6. **README LEBS 陈旧属实**：docs/backtest/README.md:5-14 称研究主入口 LEBS/`backtest/lebs/turtle/`，本仓 `backtest/lebs/` Glob 0 命中——H-R16 不以该文选型正确（§3 禁 `backtest.lebs` 属无害防御）。
7. **v1.1 对 avg×0.99 死路径的修复算术正确**：7 成 avg=(0.4+0.3×1.04)/0.7≈1.0171A，×0.99≈1.0069A>A×0.99，旧规则必先全清使 §4.4 不可达；H-R1 只留 A×0.99 后两节自洽，§8.2 还专测「avg×0.99 与 A×0.99 之间不得全清」。
8. **T+1 / 无未来 bar 全链干净**：可卖=`lot.buy_date<today`、残留次日重评不挂单扫尾；`gate[T]=f(≤T-1)`；14:55 用当根 close；触线只用 close、开盘破线才用 open（H-R13）；峰值=已走分钟 high 的 running max（H-R7）。涨停可卖/跌停禁卖 defer 符合 A 股实务（H-R4 纠正了 v1 原文的方向错误）。
9. **名单与湖窗口实测匹配**：`stock_pool_turtle` 恰为 20260804–20260909 共 23 个 CSV，格式（无表头、首列代码）与 `load_pool_days`（csv_daily_backtest.py:331-351，显式 `pool_dir` 参数存在）兼容；`--end 20260909` 不超 `MINUTE_LAKE_END`。
10. §4.2–§4.8 状态机内部自洽（A/A1 双梯子、chop 后 A 梯子作废、jump_nine/计时/止损子序交叉核对无矛盾）；§9 切片顺序与 §8 单测映射清晰；不 `git commit`、UTF-8 无 BOM 等执行约束齐备。

---

**总评**：这是本目录里少见的高完成度 plan——白/黑 import 清单、Paper 对照、数据路径全部经得起对码，v1.1 回填后内部自洽；唯一规格级错误是指数闸暖机差 1 个交易日（R1，一句话可修），外加三处「实现时会卡住问人」的定义空白（Y1–Y3）。**修完 R1、补 Y1–Y3 的一句话定义后即可进实现**；R1 不修则首跑大概率在闸上抛错或首日闸语义静默偏离。
