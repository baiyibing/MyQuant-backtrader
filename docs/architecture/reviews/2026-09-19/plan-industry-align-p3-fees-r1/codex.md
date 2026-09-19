<!-- agent=codex cmd-prefix=/home/box/.local/bin/codex exec --ephemeral 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-industry-align-p3-fees-2026-09-19.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-19/plan-industry-align-p3-fees-r1/_parallel/<agent>/<agent>.md`。
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
**结论：方向正确，现有 API 足以完成 docs/tests 切片，无需新增生产 wrapper；但验收清单尚未闭合，建议修订后进入实现。**

已通读全文并核对代码。全程只读，未执行测试、回测或写操作。读取并行目录时未见已完成意见，本评审独立形成。下文“设计稿”指 `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md`。

🔴 **R1｜Slice B 允许新增测试文件，但验收命令可能完全漏跑核心接线测试。**

证据：设计稿 `:143` 要求“Extend/add tests”，`:146–150` 要求 daily/minute/v7 接线、两 lot 和现金门验证；但 `:183–186` 只运行三个既有文件。现有 `tests/test_ashare_fees.py:22` 仅比较重导出公式，没有经过成交调用链。

若实现者把接线测试放进既有 daily/minute/v7 测试文件，或新建专用文件，§8 仍可全绿而没有验证本轮主要交付。

**修改建议：**明确测试落点并同步验收命令。可以全部扩展到 `test_ashare_fees.py`，也可以指定独立接线测试文件；逐项对应 Slice B 要求。不要把“现有公式测试通过”当作“费用接线闭环”。

🟡 **R2｜最低收费核心契约仍是待办措辞，应直接写清 v7 的聚合边界与数值。**

证据：设计稿 `:71` 写的是“Prefer documenting aggregate-vs-per-call”，尚不是可执行契约。

实际实现：

- `backtest/research/csv_ledger.py:242`：`_sell` 对单个 `Position` 计费。
- `backtest/research/csv_minute_backtest_v7.py:226`：先筛选满足 T+1、符合 `kind` 的 lot。
- `backtest/research/csv_minute_backtest_v7.py:242`：`state.cash += fee.credit_sell(sold * price)`，对本次调用的合计卖出额计费一次。

**建议写入明确 oracle：**两个均已满足 T+1 的 lot，各 100 股、成交价 10 元，卖费率 0.0015、最低 5 元：

| 调用方式 | 卖出费用 | 现金增加 |
|---|---:|---:|
| shared ledger 分别卖出两个 lot | 10 元 | 1,990 元 |
| v7 一次 `_sell_lots` 卖出两个 lot | 5 元 | 1,995 元 |
| v7 分两次调用分别卖出 | 10 元 | 1,990 元 |

这些数字由现有公式直接推导，并非本轮实验结果。应强调“**每次调用聚合**”，不是每股票、每天统一收费；当日新买 lot 不能计入卖出额。

🟡 **R3｜补齐测试调用链、私有函数边界和现金断言，避免测试绕过真实接线。**

设计稿 `:145–150` 目标正确，但仍缺程序员可直接照做的入口约定：

| 验证对象 | 已有入口与必要断言 |
|---|---|
| daily 参数接线 | `csv_daily_backtest.py:204` 的 `simulate`；显式传 `buy_cost_rate/sell_cost_rate/min_cost`，比较实际成交佣金和现金 |
| daily CLI 开关 | `csv_daily_backtest.py:683` 的 `main → run` 参数映射；用测试替身捕获参数，禁止进入行情加载 |
| minute 默认继承 | `csv_minute_backtest.py:493` 的 `simulate`；验证真实买卖，不只检查 `SimState` 字段 |
| v7 自定义费用 | `csv_minute_backtest_v7.py:274` 的 `simulate_v7(..., fee=...)`；验证买、卖两端现金变化 |

其中 `csv_ledger._sell`、v7 的 `_buy/_sell_lots` 是私有函数。**测试可以直接导入做局部 oracle，不必为测试新增生产 wrapper**；但局部测试不能替代公开 `simulate` 接线测试。v7 的 `fee` 默认参数已绑定对象，也不要通过事后替换模块 `DEFAULT_SCHEDULE` 来冒充参数透传验证。

现金门建议从“where cheap”改成必测：`csv_ledger.py:212` 和 v7 `:208` 都使用 `cost > cash` 拒单，应覆盖现金恰好足够与略低于含费金额两种情况，拒单时现金、持仓及成交记录不变。共享预检查另见 `csv_simulate_loop.py:287`。

可复用现有合成夹具：`tests/test_csv_daily_backtest.py:26`、`tests/test_csv_minute_backtest.py:336`、`tests/test_csv_minute_backtest_v7.py:38`。无需行情湖。

🟡 **R4｜Linux 验收缺少解释器前提，“禁止回测”也应明确豁免合成 simulate 单测。**

证据：

- 设计稿 `:183`、`:189–192` 使用裸 `python3`。
- `AGENTS.md:27–30` 要求按指定环境解析解释器，禁止隐式使用系统 Python。
- `.github/workflows/python-tests.yml:27` 先配置 Python 3.12；设计稿给 Linux 使用者的命令没有此前提。

建议使用已解析的解释器绝对路径，并记录版本。CI 可以注明由 `setup-python` 提供环境，不必另造安装流程。

另外，设计稿 `:101`、`:127` 禁止回测，而 `:146–148` 的接线证明必须执行合成 `simulate`。应明确为“禁止 CLI/湖数据回测；允许纯内存合成撮合单测”，避免执行者因字面禁令退回静态断言。

✅ **必查盲区核对**

- **T+1／隔日成交：**`ashare_session.py:39` 使用 `buy_date < session`；分钟扫描 `csv_minute_backtest.py:270` 拒绝 `n_days < 1`；v7 按 lot 买入日期过滤。日线 `csv_daily_backtest.py:329` 的 pending 出场是下一可卖日 open，`:398–401` 则区分同 bar close 与写入 pending。不得把所有日线卖点概括为次日开盘。本次费用契约未引入未来 bar；前收读取见 `ashare_session.py:44`、`csv_minute_backtest.py:464`。
- **复权：**默认原始价路径成立，见 `csv_daily_loader.py:96`、`ashare_bars.py:177`。但 daily loader 确实支持显式复权参数，不能宣称 API 强制只有 none。新增费用夹具应统一使用 none，不借用筹码 front 数据。
- **盈筹率：**本轮没有 cyqk 消费，应明确不适用，不向 1–8 书引入盈筹逻辑。所要求核对的 `backtest/chip_indicator.py` 在当前工作树不存在；`README.md:23–24` 已说明当前 chip 目录及旧宿主退场，不能继续引用旧包装作为现行 SSOT。
- **涨跌停／停牌：**公共门是涨停禁买、跌停禁卖，见 `ashare_session.py:73–78`；档位为主板 10%、创科 20%、北交 30%，当前名称 ST 优先返回 5%，见 `market_layer.py:43–65`。这是现有简化模型，不应写成完整交易所规则。部分策略另有更严格的涨跌停双禁规则，见 `csv_strategy_books.py:697`、`:772`。日线零量过滤见 `csv_daily_loader.py:83`，分钟整日零量过滤见 `ashare_bars.py:369`。v7 `limits=None` 分叉继续保留，不借费用切片改动。
- **包与路径边界：**入口、费用模块均属于 `backtest/research/`；`common/infra/data_root.py:134` 的湖根解析在未配置时明确报错。采用直接注入 bars 的测试即可避免触湖，无需 LEBS、MockQMT、presets 或 Cerebro。
- **并发／超时：**本方案没有新增此类机制，不触发专项最小实验要求。

✅ **应保留的设计**

- 保留双边 10bp 默认值和已有非对称可选费率，不静默统一两套账本。
- 独立费用对象、明确计费调用点符合成熟工具的设计思路；Backtrader 的 `CommInfoBase/getcommission` 可作为结构类比，但不能替代本仓行为证据。[官方说明](https://www.backtrader.com/docu/commission-schemes/commission-schemes/)
- 不新增印花税运行时扣款、保留 import fence，符合本轮授权范围；合同应明确这只是研究费用模型，不承诺完整券商税费还原。
- E-R6 残余经济失真与有限文件冻结证明的边界均已承认，不应扩大本轮工程。

**总评：可按现有基础实现；先修 R1 并补齐上述契约说明，再进入 Slice A→B→C，无需重开费用政策人裁或改生产代码。**
