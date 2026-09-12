<!-- agent=codex cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.10-fd3934a\node.EXE C:\Users\Thinkpad\AppData\Roaming\nvm\v24.19.0\node_modules\@openai\codex\bin\codex.js exec --ephemeral 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-pool-pipeline-r0r1-2026-09-12.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-12/plan-pool-pipeline-r0r1-2026-09-12/_parallel/<agent>/<agent>.md`。
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
评审已完成并写入 [_parallel/root/root.md](E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-12\plan-pool-pipeline-r0r1-2026-09-12\_parallel\root\root.md)（223 行，UTF-8 无 BOM，NUL=0；未改动任何业务代码）。

核心结论（侧重实现可操作性）：

🔴 四条必须修

1. **P-R3「湖省略停牌日、所以默认只写文档」的前提被实测推翻。** F 湖在停牌日写 `volume==0` 的平价占位 K：[csv_daily_backtest.py:213](E:\PycharmProjects\MyQuant-backtrader\backtest\research\csv_daily_backtest.py:213) 确实不读 `volume`，但只读探针显示 `000004_SZ` 有 382 行零量、最近 2026-06-22（2026-06-15..06-22 连续 8 个交易日 OHLC 全是 2.76/量 0，06-23 复牌 0.27→0.31）；前 400 只股票中 **98 只有 2023 年后的零量行，共 656 行**。默认降级会把不可成交日按可成交记进回测。建议把 C 升为默认落地：加载器多读 `volume` 列（schema 已含该列，零迁移），`volume==0 ≡ 缺 K`。

2. **`name_asof` 只修了「后日赢」，没修「旧名永久生效」。** [market_layer.py:57](E:\PycharmProjects\MyQuant-backtrader\backtest\research\market_layer.py:57) 里 ST 名 = 5% 窄板，与 plan §6「fail-open 偏宽板」的说法相反；pool CSV 是候选名单而非全市场快照，历史窗大多数 code 多数日子没有行，一旦观测到 `*ST` 就永久 5%。需补名称有效期/回退规则 + 反向回归测。

3. **B 缺可编码的 helper 契约。** `names` 在 `simulate` 顶部只赋值一次、3 个（日线）/4 个（分钟）`_named_limits` 调用点共用（[csv_daily_backtest.py:312](E:\PycharmProjects\MyQuant-backtrader\backtest\research\csv_daily_backtest.py:312)、[:326](E:\PycharmProjects\MyQuant-backtrader\backtest\research\csv_daily_backtest.py:326)）。评审给出了建议签名与「按日取表 + bisect + 按 ds 缓存」的落地契约。

4. **「volume==0 ≡ 缺 K」在日线做不到「无 K」**，因为缺 K 分支是 `continue`（[:318](E:\PycharmProjects\MyQuant-backtrader\backtest\research\csv_daily_backtest.py:318)），且估值循环用当日 close（[:468](E:\PycharmProjects\MyQuant-backtrader\backtest\research\csv_daily_backtest.py:468)）。需把 mark 回退到「最近一个有量交易日」，plan 未指明这个回退点。

🟡 六条应修（键缺口语义、as-of 性能实现、分钟 T+1/停牌不同构、`validate_pool_dir` 返回契约与 formula 边界、R0 脚本可测性与 bootstrap 导入、旧「后日赢」绿测必须删除而非改名保留）。

✅ 保留：T+1/无未来 bar（日线 [:332-341](E:\PycharmProjects\MyQuant-backtrader\backtest\research\csv_daily_backtest.py:332)、分钟 :630）、复权 `dividend_type=none` 单一口径、涨跌停档位、缺日=不买、扁平 `pool_names` 兼容式扩展、R0 胶水放 `scripts/data/`。

附最小实验：`load_pool_name_map` 后日赢复现（同一根 D1 bar，`*ST` 提前套用 → 买入判定从 buys=1 翻成 buys=0/skip_limit_up=1）、两个新 API 均不存在、停牌占位行统计，均附原始输出。

总评：骨架正确，但 C 的事实前提与 B 的前向分支必须改；补齐 R3/R9 的 API 与单测契约后方可进实现，按 v1.1 原样实施不通过。
