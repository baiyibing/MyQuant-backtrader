<!-- agent=codex cmd-prefix=/home/box/.local/bin/codex exec --ephemeral 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-industry-align-next-2026-09-19.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-19/plan-industry-align-next-2026-09-19-r1/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本仓第一方回测是 **向量化 CSV**（日线/分钟）+ path-SSOT 只读行情。Cerebro / Rolling 已全局退场（2026-09-16，PR #58；禁止复活）。无实盘、无 QMT 下载、无 Redis 流。引擎分工见 `docs/backtest/engine-positioning-ssot.md`。把握不准可读代码或做实验，以事实为准。

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
🔴 **R1｜冻结验收命令与冻结表不一致，无法证明“生产文件未变”。**

证据：`docs/backtest/plan-industry-align-next-2026-09-19.md:165` 的 `git diff` 清单只有九个文件，漏掉同文 `:193–195` 明确冻结的：

```text
backtest/research/market_layer.py
backtest/research/csv_common.py
backtest/research/csv_daily_loader.py
```

这三个文件分别控制档位、名称口径、零量过滤，恰好属于本次契约主题。改动它们仍可能通过当前冻结命令。此外，比较 `BASE HEAD` 不检查未提交修改。

**建议**：至少补齐三个文件；更直接的是检查提交变更清单，仅允许约定的文档与测试路径，并要求交付工作区无未提交改动。保留逐文件冻结检查作为辅助证据即可。

🔴 **R2｜主目标包含 ST 名称与停牌分叉，但 Slice A 的实施清单只落实了 `limits=None`。**

证据：

- 设计稿 `:4` 将 `limits`、halt/zero-volume、ST name 一并列为主交付。
- 设计稿 `:102–112` 的测试范围与 DoD 只有 `limits=None` 和门后失败。
- `backtest/research/csv_common.py:85` 的 `_pool_names_asof` 按日期推进；`backtest/research/ashare_session.py:81` 的 `flatten_pool_names` 则合并整个窗口的名称。
- `tests/test_csv_daily_backtest.py:990` 的零量测试先经过日线加载器，不能单独证明分钟/v7 加载链的同等行为。

**建议**：在 Slice A 明确补两组契约，避免程序员按清单完成后仍漏交主目标：

1. 名称跨日从普通变 ST、从 ST 变普通：分别锁定 book 日期解析与 v7 窗口末名称行为；明确后者属于保留的非 PIT 近似。
2. 零量占位和缺失 bar：按日线、分钟、v7 的真实加载入口列出已有测试或新增测试，区分“加载器过滤”与“模拟器收到无 bar 后冻仓”。

不要求本轮修正历史行为，只要求把承诺的分叉落实为可执行契约。

🟡 **R3｜加仓测试的复用入口有参数吞失，需给出具体测试接线方案。**

证据：`tests/test_ashare_simulate_predicates.py:64` 的 `run(..., **kwargs)` 在 book 分支转发参数，但 v7 分支 `:67–72` 未转发 `kwargs`。直接复用它传 `cash_total=0`，不会形成预期的现金不足场景。

同时，`backtest/research/csv_minute_backtest_v7.py:202`、`:223` 的 `_buy` / `_sell_lots` 是私有函数。单独测试这些函数，不能证明 `simulate_v7` 的 gate 到成交调用链正确。

**建议**：

- 使用公开入口 `simulate_v7`，沿用已有 `seed` 的持仓注入方式。
- 在测试侧修正 v7 参数转发，或直接调用公开入口；无需新增生产 wrapper。
- 加仓至少覆盖“资金充足、实际成交”和“资金不足、产生 `skip_cash` 且现金/持仓阶段不变”。
- 将 `limits=None` 的两个来源——缺昨收、未知板块——都参数化覆盖。
- T+1 非成交若需要证明确实到达卖出尝试，可在测试侧用委托原函数的 spy；不要把私有 helper 提升为生产 API。

🟡 **R4｜验收命令的解释器与基线契约尚未闭合。**

证据：

- 设计稿 `:151–162` 直接使用 `python3`，而 `AGENTS.md:27–30` 要求显式解析解释器，禁止隐式使用系统 Python。
- 设计稿 F-R10 要求实施基线来自 `origin/master` tip；`:145–148` 却固定设计时 SHA，仅验证其存在且为 HEAD 祖先。祖先检查不能证明它是实施分支创建时的主分支 tip。

**建议**：验收命令统一使用明确配置的解释器；Linux CI 可显式指定其受控 Python 3.12。区分“设计取证 SHA”和“实施基线 SHA”，后者在建分支时记录。无需每次验收追逐不断变化的远端 tip。

🟡 **R5｜“不跑回测、不读湖”需明确允许合成数据模拟与临时 parquet 夹具。**

证据：设计稿 `:179` 写着 `no backtests run`，但要求执行的 `tests/test_ashare_simulate_predicates.py:64` 会调用三个模拟器；`tests/test_csv_daily_backtest.py:990` 会在 `tmp_path` 创建合成 parquet，再调用加载器与模拟器。

**建议**：明确禁止的是生产行情湖访问和研究 CLI 回测；允许测试内的合成行情、临时 parquet 与 `simulate*`。否则实施者可能为满足字面限制而绕过最有价值的端到端契约测试。

✅ **必查盲区核对与应保留的设计**

- **T+1 / 隔日成交**：日线卖出受日期资格检查约束，买入日不可卖（`csv_daily_backtest.py:329`、`:336`）；v7 按 lot 日期筛选（`csv_minute_backtest_v7.py:225`）。日线止盈不能统称“当日收盘”或“次日开盘”：same-bar 前缀走 close，其余写入 `pending_exit`，下一可卖日 open（`csv_daily_backtest.py:377`、`:398–401`、`:329–333`）。本轮不改这些时点是正确的。
- **未来数据**：昨收函数明确只取 `day < today`（`ashare_session.py:44–46`）。但 v7 窗口末 ST 名称存在非 PIT 信息使用，不能据此宣称整体“无未来信息”；应按 R2 明示保留。
- **复权口径**：日线加载默认 `dividend_type="none"`（`csv_daily_loader.py:96`）；成交与均线的原始价口径及除权近似已有 SSOT（`docs/backtest/engine-ashare-correctness.md:63`）。本轮测试应延续该口径，不引入筹码 front。
- **盈筹率**：本计划没有筹码计算需求，`cyqk` 的 0–1 尺度不进入本船，更不应接入 1–8 书。指定检查的 `backtest/chip_indicator.py` 当前不存在，不能引用为现行实现证据；现存筹码研究代码在 `backtest/research/chip/` 等路径。
- **涨跌停 / 停牌**：公共谓词分别拦涨停买入、跌停卖出（`ashare_session.py:73–78`）；板块档位包含主板 10%、创科 20%、北交 30%，名称 ST 优先返回 5%（`market_layer.py:45–66`）。这些是当前实现口径，不能包装成完整交易所规则。书策略还可能施加额外涨停卖出限制（`csv_daily_backtest.py:384–388`）；矩阵应区分公共门与策略门。
- **包边界 / path-SSOT**：与 `README.md:3–7`、`common/infra/data_root.py:192`、`:256` 的研究入口和数据路径边界一致，无须引入 LEBS、MockQMT 或恢复 Cerebro。
- **验证边界**：本轮仅静态只读取证，未执行会生成缓存或临时文件的测试。计划没有新增超时、并发或重试机制，因此无需构造相关计时实验。

**总评：方向正确、已有接口足以实施，无须生产 wrapper 或引擎重构；当前不建议直接 GO，先修 R1、R2，并补齐测试接线与验收口径后可进入 A→B→C。**
