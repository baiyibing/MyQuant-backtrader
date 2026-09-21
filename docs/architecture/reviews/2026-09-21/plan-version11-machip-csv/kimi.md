<!-- agent=kimi cmd-prefix=C:\Users\Thinkpad\.kimi-code\bin\kimi.EXE -m kimi-code/k3 --output-format text -p 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】E:/PycharmProjects/MyQuant-backtrader/docs/backtest/plan-version11-machip-csv-2026-09-21.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-21\plan-version11-machip-csv/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本地 redis/数据库已就绪、国金 miniqmt 已登录；把握不准可读代码或做实验，以事实为准。

【裁决原则（重要）】
- 视自己与其他评审者为同行专家，**参考学习、互相验证、取长补短**：结论交叉核对、补彼此盲区，而非单纯挑错。
- **事实类断言**（函数位置 / SQL / 行为 / 数值等可验证项）→ **以代码与实验为准**：读代码取证，把握不准时跑最小实验，不靠票数下结论。
- **经验/取舍类断言**（该不该这样做、风险量级、更稳的写法）→ **以业内 A 股量化惯例与成熟开源实践为准**。
- **SSOT 一致性检查**：若方案涉及数据格式/符号规范/配置键/API 契约等，**必须对照仓库 SSOT 文档**（`docs/backtest/data/symbol-format-ssot.md`、`docs/SSOT.md`、`docs/operations/disclosure-data-source-ssot.md` 等）检查是否冲突。若方案与 SSOT 不一致，标记为 🔴 并指出具体 SSOT 文件及条目。
- **★ 安全阀/超时/并发类设计，必须跑最小实验验证行为**（不只读代码！）：timeout / budget / safety-valve / circuit-breaker / 并发锁 / 异步 / fallback / 重试——这些 bug 藏在 stdlib/框架行为里（如 `ThreadPoolExecutor.__exit__`→`shutdown(wait=True)` 让超时从不生效），**读代码看不出来**。实验格式：构造 slow fn + tight budget → 测调用方**何时返回**（`time.monotonic` 对比 budget_s vs 实际）。2026-07-04 实测：option-X budget docstring 宣称 "releases caller" 但实际 8s 才返（非 1s budget）——**docstring 不可信，实验为准**。**实验结论须附可复现脚本 + 完整原始输出**（含进程 pid/存活检查等），与官方文档/CPython 源码矛盾的结论标注「建议主持裁/下游复核」。2026-07-16 教训：r3 kimi 实验「subprocess.run(timeout) 不杀子进程」结论错，r4 qoder 引源码 + 主持裁亲自实验（child TERMINATED）才纠正——下游 incorporate 实验断言须亲自复现。

【输出格式】
按严重度分级，每条尽量带 file:line 证据：
- 🔴 必须修（事实错误 / 会误导实现 / 逻辑矛盾）
- 🟡 应修（设计缺口 / 风险）
- 🟢 可选（nice-to-have）
- ✅ 做对的地方（保留）
末尾给一句总评 + 是否可进实现。

【你的评审侧重】优先**跑实验验证关键行为**：对 timeout/budget/safety-valve/并发锁/异步/fallback/重试类设计，构造最小实验（slow fn + tight budget → 测调用方何时返回）。读码不够时动手测——**docstring 不可信**（docstring 宣称的行为可能被 stdlib/框架吞掉，如 `ThreadPoolExecutor.__exit__`→`shutdown(wait=True)` 让超时从不生效）。保持这个习惯。 <prompt> -->
• 其他评审员的 md 目前只有 prompt 头、暂无成品意见，我独立完成。继续核实 `csv_simulate_loop.py` 关键断言。

• 现在跑最小实验验证关键行为。先看 `run_pool_buys_day` / `run_chase_due_day` 完整签名以便构造实验。

• 评审完成，意见已写入我的并行槽位。以下为评审全文：

  # kimi 评审（侧重：最小实验验证关键行为）

  评审基线：plan v0.3。§2 全部锚点已逐条读码复核；skip FSM / cyqk 失败语义 / T+1 已跑最小实验（vanna312，`PYTHONDONTWRITEBYTECODE=1`，零文件写入）。其他评审员槽位（claude/codex/cursor-auto）截至落笔仅有 prompt 头、无成品，无可交叉条目。

  ## 实验记录（可复现）

  均在 `MyQuant-backtrader` 下以 vanna312 python stdin 执行：

  - **E1**：`compute_cyqk_series` 存在于 site-packages（`__init__.py` + cp312 pyd；repo cp311 pyd 未参与 import——plan 锚点属实）。正常窗输出 ∈[0,1]、前 window-1 个 NaN；`window=0` / `n<window` → 全 NaN。
  - **E2 逐窗 fail-closed**：300 根合成序列，shares[0]=0 → 仅 `out[199]` NaN、`out[200]` 起有效；shares[250]=0 → `out[250..299]` NaN、`out[249]` 有效。**坏股本日只毒化含该日的窗，非全序列**。
  - **E3**：长度不匹配 → **抛 `ValueError`**（非全 NaN，与 repo `turnover-resist/src/algorithm.rs:448-456` 源码相悖——安装件与仓内源码分歧，以安装件实测为准，建议下游复核 pyd 版本）。
  - **E4**：窗内 volume=0 不毒窗；close=NaN → 该窗 NaN。
  - **E5 skip FSM**：`buy_quote_for→None` → `skip_no_bar=1`、无持仓、无重试残留（信号当日消耗）；默认 `limit_up_chase=True` 买价≥涨停 → chase 入队；`quotes_for→None` 连跑 day_i=1/2/5/10/30 → pending **30 天无过期**；`t1_sellable` 同日 False、次日 True。

  ## 🔴 必须修

  **kimi-R1｜cyqk 失败模型写错，会误导导出器实现。** Plan §2 称「子窗异常全 NaN fail-closed」、R10 称「失败（NaN/异常窗）即 skip」——实测真实契约是两层：① 窗内坏日 → **该窗** NaN（非全序列，E2）；② 形状错误 → **抛 ValueError**（E3）。后果：只查 NaN 不 catch → 全市场导出遇 ragged 输入中途崩溃；或误读「全 NaN」为"任一坏日整列作废" → 过度 skip。修订：§2 改「逐窗 NaN + 形状错误抛异常（实测安装 pyd）」；切片 B DoD 增「异常捕获记 skip」「单坏日仅毒化含该日窗」两条 pin。

  ## 🟡 应修

  - **kimi-Y1｜ST 板档未处置。** 池契约 `docs/backtest/pool-csv-contract.md:19-21`：无名称列按前缀分板（主板 10%）；9/10 导出器写裸码无名称列。version11 全市场会含 ST/*ST（5% 档），09:30 新钟的涨停拦截/跌停 defer 将用错阈值。二选一：导出器滤 ST，或写可选名称列；全市场模式 DoD 前必须定。
  - **kimi-Y2｜分钟侧 09:30 pending 卖的跌停 defer 未 pin。** 日线既有语义是 defer 留 pending 次日再试（`csv_daily_backtest.py:344-350`）；分钟全新消费若不写明，T+1 一字跌停开盘会出现「跌停强卖」或「pending 丢弃」。切片 C DoD 增「09:30 跌停 defer、次日再评」pin。
  - **kimi-Y3｜P6 可免费加强。** 实测静态档案恰 7 份，含 `cyqk80`/`cyqk90_nobb`/`nocyqk`/`nobb` 消融轴——差异清单应按消融轴对照，对 P0「0.70 抛压区」之争提供最便宜旁证（不改 P0 建议 a）。
  - **kimi-Y4｜chase 危害表述偏轻。** 「默认 True 会 T+2 追买」——E5 实测无 bar 时 pending 永不过期（30 天仍在队），比 T+2 更严重；R9 pin False 必要。切片 C 加回归 pin：涨停拦截后 pending_chase 为空。

  ## 🟢 可选

  - G1：P1 的 a/b 选项在「问题」列未标定义，编辑性补齐。G2：§2「`csv_minute_backtest.py:338` 无该参数」引用弱（:338 是函数定义行），实质（grep 零命中）为真，建议改引 grep。G3：导出器应像 export9（`export_strategy9_pool.py:126`）前置剔 volume==0 bar。G4：切片 B DoD 记一行 seed-30 实测耗时作全市场外推依据。

  ## ✅ 做对的地方

  - §2 锚点**全部复核为真**（export9:62-63 拒写、`csv_ledger.py:79`、日线 :344-350、分钟零消费、`ashare_session.py:39-41`、`algorithm.rs:436`、`core.py:580` 非等价、`_daily_to_weekly` W-FRI+last_day=max、`csv_strategy_books.py:47/:1088/:134` 注册与 chase 默认 True 四处处方）。
  - gap #3/#4 对抗层证伪全部经 E5 实验坐实——R9 与新 EOD 钩子确为必需。
  - 契约日口径（≤T-1 计算写 T）与池契约 SSOT `pool-csv-contract.md:11-12` **一致**；对 export9 先例的偏离识别正确。
  - R10 方向正确：仓内确无等价 Python 回退；E2 与归档口径精确吻合。R8 前置 ma_infra plan 真实存在、API 名对齐。P6 sanity bounds 是好习惯。

  ## 总评

  事实基础扎实（锚点零误判）、SSOT 合规、关键风险全部经实验坐实；唯一硬伤是 cyqk 失败语义两层契约被压成一句「全 NaN」。**修 kimi-R1 并落实 Y1/Y2 后可进实现**（P0–P7 人裁照旧；P0 倾向选项 a，Y3 消融对照可同步喂人裁）。

=0 不毒化 cyqk 输出；导出器应像 export9（`export_strategy9_pool.py:126`）一样前置剔除 volume==0  bar，保持与归档口径一致。
- kimi-G4：性能基线缺一行——全市场 200 日窗 cyqk 导出建议切片 B DoD 记录 seed-30 实测耗时（Rust rayon 逐日并行，预期分钟级），作为全市场一跑的外推依据。

## ✅ 做对的地方

- §2 锚点**全部复核为真**：export9 拒写 `stock_pool/`（`:62-63` SystemExit）；`csv_ledger.py:79` pending_exit；日线消费 `csv_daily_backtest.py:344-350`（次日开盘卖、跌停 defer 留 pending）；分钟引擎 pending_exit grep 零命中；`t1_sellable` `ashare_session.py:39-41`；`compute_cyqk_series` `algorithm.rs:436`；`compute_equal_weight_cyqk` `core.py:580` docstring 自认等权非等价；`_daily_to_weekly` W-FRI+`_last_day`=max（`weekly_macd_divergence.py:86-101`）；`FORBIDDEN_DEFAULT_STOCK_POOL`（`csv_strategy_books.py:47`）与别名注册模式（`:1088`）；`limit_up_chase` 默认 True 四处处方（`:134`/`csv_daily_backtest.py:295`/`csv_minute_backtest.py:590`/`csv_simulate_loop.py:223`）。
- gap #3/#4 的「对抗层证伪」全部经实验证实（E5）：skip_no_bar 当日消耗、chase 无过期、t1_sellable 结构挡买入日卖——R9 与新 EOD 钩子确为必需，非过度设计。
- 契约日口径（≤T-1 计算写入 T）与池契约 SSOT `pool-csv-contract.md:11-12`「文件名=买入日 T」**一致**；对 export9「≤T 写 T」先例的偏离识别正确、理由充分（本信号 D 收盘决策、次日执行）。
- R10 方向正确：仓内确无等价 Python 回退（`compute_cyqk_series` 仅存在于 Rust crate）；E2 逐窗 NaN 与归档「窗内坏日→该日 NaN」精确吻合。
- R8 前置依赖真实存在且 API 名对齐（ma_infra plan v0.1：sma_asof/sma_series/bb_asof/weekly_sma_asof/daily_to_weekly/sma_live 六件）。
- P6 的 sanity bounds（信号数/笔数数量级校验）是好的评审卫生习惯，防止差异清单不可判读。

## 总评

事实基础扎实（锚点零误判）、SSOT 合规、关键风险识别全部经实验坐实；唯一硬伤是 cyqk 失败语义的两层契约被压成一句「全 NaN」。**修 kimi-R1 并落实 Y1/Y2 后可进实现**（P0–P7 人裁流程照旧；P0 本人倾向选项 a，Y3 的消融对照可同步喂给人裁）。
