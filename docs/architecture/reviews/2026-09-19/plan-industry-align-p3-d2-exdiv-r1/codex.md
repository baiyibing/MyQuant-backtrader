<!-- agent=codex cmd-prefix=/home/box/.local/bin/codex exec --ephemeral 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-19/plan-industry-align-p3-d2-exdiv-r1/_parallel/<agent>/<agent>.md`。
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
🔴 **R1｜跨日验收链引用了不存在的 API，必须修正。**

证据：`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:66`、`:185` 均要求使用 `load_exdiv_rates`；实际定义在 `backtest/research/exdiv_map.py:220`：

```python
def load_exdiv_ratios(
```

仓内生产代码和测试均使用 `load_exdiv_ratios`。应统一名称，并明确传入 `adj_factor_path`、`ex_date_index_path` 两个合成路径。只提供其中一个，另一个仍会触发 resolver（`exdiv_map.py:246`）。无需新增兼容别名或生产 wrapper。

🟡 **R2｜B6 应列清入口与 stub 位置，特别是 v7 的指数行情读取。**

计划 `:189` 对 daily 列了隔离项，但 minute/v7 仅给源组合矩阵，尚不足以防止测试意外读湖。

实际调用链：

- daily/minute 用公开 `run()`；daily `run()` 返回状态，本身不写产物（`csv_daily_backtest.py:628`），产物 writer 不属于这一层的必要 stub。
- v7 没有对应 `run()`，入口是 `main(argv)`（`csv_minute_backtest_v7.py:547`）。
- v7 非空 pool 必然调用 `load_index_daily(start,end)`（同文件 `:577`），随后写产物并汇总（`:587`）。只 stub 股票 bars、pool、exdiv 不足以隔离 I/O。
- book minute 的两个源走不同 loader：`_load_minute_compact` 与 `load_minute_bars`（`csv_minute_backtest.py:852`、`:863`）。

建议给 B6 增补逐入口 patch 清单，patch **消费模块绑定的名字**；v7 使用非空合成 pool，并隔离指数 loader、writer、summary。若要证明 map 确实被加载，不应直接 stub 掉整个 `load_limit_context`；应保留其调用链、替换它内部的读入依赖。`ashare_session.py:99` 对空 codes 不调用因子 loader，空 pool 夹具无法证明这一点。

🟡 **R3｜B5 的精确数值 oracle，应区分人工状态与公开模拟器可达状态。**

计划 `:98` 的“100 股、cost=10、现金=2000”适合作为人工账本 oracle；B5（`:188`）同时指向 v7，但该状态不能直接通过其公开入口初始化。

证据：

- `csv_minute_backtest_v7.py:277`：`simulate_v7` 无初始 Position 注入参数。
- `csv_minute_backtest_v7.py:208`：买入额为 `NAME_BUDGET × fraction`。
- `csv_minute_backtest_v7.py:57`、`strategy7_rules.py:22`：预算为 100 万，试仓比例为 20%。

因此价格 10 元时，自然试仓为 20,000 股；仅有 3000 元现金会跳过买入，不能得到上述 100 股存量。

建议明确：精确小数值案例用于 helper/人工账本；公开 v7 采用自然买入股数，以事件前快照为基准验证现金不变、股数不变和 raw mark 差额。无需改预算常量或新增生产注入接口。

🟡 **R4｜建议补一个“已有 pending_exit 跨除权日”的公开日线 pin。**

B2 已覆盖字段保留、新买、step、多事件，但未明确验证除权前产生的待卖指令在除权日如何执行。

证据：`csv_daily_backtest.py:333`：

```python
if pos.pending_exit and t1_sellable(calendar[pos.entry_idx].date(), day.date()):
```

该分支随后使用当日开盘价和映射后的跌停档位处理，且优先于重新评估卖点。仅证明 `pending_exit` 字符串未变，不能证明成交顺序正确。

建议补两个小向量：D−1 收盘产生 pending，D 除权后正常开盘成交；D 开盘跌停则继续保留 pending。断言原 reason、raw 开盘成交价、原股数，以及不重复缩放。全部可在既定测试文件内完成。

✅ **必查盲区核对**

- **T+1 / 隔日成交**：book 买入日不能卖；分钟另有 `n_days < 1` 拦截（`csv_minute_backtest.py:276`），v7 按 lot 买日过滤（`csv_minute_backtest_v7.py:229`）。日线普通止盈写入 pending，后续可卖日开盘执行；`same_bar` 分支仍当日收盘成交（`csv_daily_backtest.py:404`），不能概括成所有卖点均次日开盘。
- **未来数据**：昨收和 v4 SMA 使用此前 closes（`csv_common.py:43`、`strategy4_rules.py:38`）；计划 `:68` 正确区分日期截断与因子决策时刻可得性，不能据此宣称全链路 PIT 已证。
- **复权口径**：默认日线及分钟消费 none 域（`ashare_bars.py:88`、`:177`）；v4 保留原始历史 closes。计划如实记录 front/back/qlib 分源边界与混域残留，未把筹码 front 引入 CSV 书。
- **盈筹率**：本刀不涉及 cyqk。用户点名的 `backtest/chip_indicator.py` 当前不存在，不应作为现行实现引用；现存研究筹码筛选仍使用 0–1 阈值（`backtest/research/chip/filter_stock_pool_by_chip.py:23`）。建议 Non-goals 补一句明确不涉及盈筹率。
- **涨跌停 / 停牌**：市场层为主板 10%、创科 20%、北交 30%，名称 ST 优先 5%（`market_layer.py:44`、`:57`）；这是现有模型，并非历史全制度覆盖。共享市场限制是涨停禁买、跌停禁卖（`ashare_session.py:73`），策略自身仍可延迟涨停卖出。缺 bar 前置跳过、事件键不回放的残留已准确披露。
- **包与路径边界**：符合 `README.md:3` 的向量化研究定位；未引入 LEBS/Cerebro。未配置湖根时报错与路径解析后局部缺文件降级已正确区分（`common/infra/data_root.py:154`）。
- **私有 helper**：B3 直接测试 `_rescale_position` 合理，无须为测试新增生产 wrapper；分钟夹具可使用已有公开 `ashare_bars.annotate_session`（`:318`），避免新增对 `_annotate` 别名的依赖。

✅ **应保留的设计取舍**

参考价缩放与公司行动经济记账分开、公开模拟器与 helper 分层验证、冻结生产行为，都适合本刀。成熟工具也将拆股处理、红利权益登记和支付分别建模；这支持计划“不把参考价修正冒充总回报正确”的边界。[Zipline 官方 API](https://zipline.ml4trading.io/api-reference.html)

本轮只读核查，未运行测试或写操作；读取时未发现可交叉引用的已完成同行结论。本方案未新增超时、并发或重试机制，无对应时限实验结论。

**总评：方案基本可落地；修正 R1、补清测试入口与夹具约定后，可在人裁 GO 后进入 docs＋data-free tests 实施，不能据此批准生产行为改造或宣称经济正确性已闭合。**
