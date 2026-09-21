<!-- agent=claude cmd-prefix=C:\Users\Thinkpad\AppData\Local\Microsoft\WinGet\Links\claude.EXE -p --no-session-persistence --output-format text --permission-mode bypassPermissions 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

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

【你的评审侧重】优先**综合裁决 + 跨文档交叉验证**：检查方案内部自洽（不自相矛盾）、跨节引用一致、与关联 plan/SSOT 的衔接；对抗性复核其他评审员的断言（凭代码/实验驳回误判）。 <prompt> -->
# 评审意见：plan-version11-machip-csv-2026-09-21（v0.3）

**评审角色**：综合裁决 + 跨文档交叉验证。
**交叉核对情况**：截至本人完成时，`_parallel/` 下四份并行稿（codex/kimi/cursor-auto/claude 槽位）**均只有 prompt 头或过程笔记，无成品意见**——无可交叉核对的条目，本稿独立完成。两点提醒主持侧：① cursor-auto 槽位以 `--mode plan` 启动（`_parallel/cursor-auto/cursor-auto.md:1` cmd-prefix 可见），是仓内已知空产陷阱（应 `--mode ask`）；② plan 头部承诺的「独立性让渡外部四稿」目前尚未兑现，P0–P7 人裁前须确认至少两家外部稿真实产出。

对主笔对抗稿（`plan-version11-machip-csv-2026-09-21-review-by-claude.md`）的 F1–F8 吸收做了逐条核对：**全部忠实回填**（F1→P0、F2→R9+§3.3、F3→§3.4+切片C、F4→§1 契约日、F5→R10、F6→R10 句2、F7→R8、F8→P4 重开；§5 勘误行号 `export_strategy9_pool.py:62-63`、`csv_ledger.py:79` 均已实测属实）。对抗稿遗留的 §4 Q4（契约日「评估窗分类」文档化）在 v0.3 无落点（见 🟢G3）。

---

## 🔴 必须修

### R1｜信号侧复权口径整体缺失，且与 R4 字面冲突（会系统性歪信号）
- 归档锁定口径有「价格」行：`_archive/plans/plan-ma-chip-edge-strategy-2026-09-07.md:31`
  > 价格 | 日线 `period=1d` **`adjust_type=front`**。禁止 `load_single_stock_data`
- 新 plan §1 转录表（:19-24）**丢掉了这一行**；而 R4（:53）把「除权」划给「CSV 引擎现行口径」。
- 引擎/先例现行口径全是 **none**：`csv_daily_loader.py:116`（`dividend_type must be one of ...`，default `"none"` :108）、`ashare_bars.py:177`（分钟硬编码 `dividend_type=none`）、`export_strategy9_pool.py:141`（`resolve_period_root("1d") / "dividend_type=none"`）。
- 后果：200 日筹码窗 + SMA20/60 + 布林 + 20 周线跨除权事件时，不复权价格会制造假突破/假破位（10 送 10 形如 -50% 暴跌），edge 信号系统性失真；实施者照 §1+R4 字面会用 none，与归档 front 锁定相反。
- **修法**：§1 补一行「信号计算价格 = front（归档锁定）；执行/涨跌停/T+1 = 引擎现行（none + `mapped_prev_close` 除权映射）」，并把 R4 的「除权」限定为执行侧；manifest 记录 adjust_type。

### R2｜契约日 T 的定义缺位——「市场次一交易日」与「该股信号后首根 bar 日」两种读法产生不同交易集
- 归档 FSM（`_archive/...2026-09-07.md:30`）：`pending_buy` 仅对「信号日后 **≤4 个自然日的下一根 bar**」有效——是**该股自己的下一根 bar**。
- 新 plan §1（:19）只说「按 ≤T-1 计算写入买日 T」，未定义 T 取市场日历次一交易日还是该股次一有 bar 日。
- 引擎侧事实使两读法分叉：池文件当日的 `skip_no_bar` **当日即消耗**（`csv_simulate_loop.py:260-263`），名字不会再出现在次日文件里。若 T=市场次日，停牌 1 天的票（bar 在 T+1，gap≤4 自然日，归档应买）会被静默丢弃；切片 B 的「stale >4 自然日消耗（导出器层）」（:85）也只有按「该股次一 bar 日」定义 T 才可实施。
- **修法**：§1/切片 B 明确 **T = 该股 D 后首根有 bar 的交易日，且 D→T 间隔 ≤4 自然日（超限丢弃 = skip_buy(stale) 消耗）**，名字写入 T 当日文件；manifest/P6 差异清单同时记录原信号日 D（对照 Cerebro `events.csv` 才可判读）。

---

## 🟡 应修

### Y1｜§1 转录表缺「抽样/板块/股本源」三行，实现会在 universe 分层上漂
§1 自称「归档 plan §2，已锁定口径」的转录，但丢了：抽样行（`_archive/...:44`：seed=20240907、hive front ∩ `float_shares.parquet`、每板 10 只、预热不足重抽）、板块行（`:45`：沪主板 `60xxxx.SH` 排 688 / 深主板 `000/001/002/003*.SZ` / 创业板 `300/301*.SZ`）、股本行（`:35`：`free_float_shares.circulating_capital` backward merge_asof、**不用 D 日一条股本铺整窗**）。P4/P5 只覆盖了其中一部分，板块分层与 688 排除**只存在于归档**。修法：§1 补三行或显式引用归档行名，并在切片 B DoD 把「每板分层抽样可复现」列为验收项。

### Y2｜「卖出日不重入」缺引擎机制（skip_held 挡不住）
引擎买侧只查 `st.positions`（`csv_simulate_loop.py:252-255`）；日循环先卖（`csv_daily_backtest.py:344`）后买（`:460`），当日开盘卖出的票到买循环时已不在 positions——若同日池文件含该码即买回，违反「卖出日不重入」。切片 C 内容清单未列该 gate（只在 DoD 有测试名）。修法：切片 C 显式加「sold-today 集合 + 买侧过滤」。

### Y3｜P3「复用 TR store 缓存」措辞会误导——store 的 cyqk 与 200 日窗非同量
TR store 链路是 window=1000 世界：`export_ta_pool.py:46`（"v0 唯一规则 resist_tr_bb_1000（window=1000）"）、`full_market_canonical_resist.py:642`（default 1000）；store schema 带 `cyqk_t/cyqk_t_1`（`oskh_data/turnover_resistance_store.py:31-32`）。切片 B 写的是「现算 window=200」✓ 正确，但 §3（:41）与 P3（:67）的「TR store 生态可复用 / 复用 TR store 缓存」字面会诱导读 store 的 cyqk 列。修法：P3 改为「复用 TR store **生态的装载/股本解析/bridge 件**；cyqk 一律 `compute_cyqk_series(window=200)` 现算，**禁读 store cyqk_t**」。

### Y4｜买入日 EOD 评估钩子的日内次序未 pin
钩子须在「当日卖循环 → 当日买循环 → **EOD 评估**」之后、T+1 卖循环之前执行（评估对象含当日新买入仓位、输入含当日收盘）；分钟侧同埋在 T 最后一条 bar 后。切片 C 未写次序，建议 DoD 加时序测试（T 买入仓位当日评估产生 pending_exit、T+1 开盘成交）。

---

## 🟢 可选

- **G1** P2「分钟 09:30 首根」须定义 bar 时间标签（湖首根标 09:30 还是 09:31），避免买/卖钟不对称。
- **G2** §8 建议补 `csv_daily_backtest.py --strategy 11 --help`（日线也是交付面；`--strategy` 经 `add_csv_strategy_arg`（`csv_strategy_books.py:161-168,327`）注入两 CLI，命令成立已验证）。
- **G3** 落实对抗稿 §4 Q4：在 export9/v11 导出器 docstring 各加一句「评估窗分类」（≤T 买即用 vs ≤T-1 边缘信号），防第三人第三次照搬。
- **G4** manifest 注明 `turnover_resist` 为 site-packages 外部依赖：实测 vanna312=Python 3.12.13，加载 `D:\anaconda3\envs\vanna312\Lib\site-packages\turnover_resist\turnover_resist.cp312-win_amd64.pyd`；repo 内 cp311 .pyd（`turnover-resist/python/turnover_resist/`）在本环境 ABI 不匹配、非实际加载件——「陈旧件」表述成立但建议写准为「ABI 不匹配残留件」。data-free 单测若真调 Rust 件，CI 机器需同款装件（现有 TR 测试已依赖，注明即可）。

---

## ✅ 做对的地方（逐条实测/复核）

1. **§2 八个 as-built 锚点无一虚构**（本人逐一验证）：export9「filename=买日 T、按 `date<=T` 计算」买即用语义（`export_strategy9_pool.py:2-4` docstring）；`pending_exit` 日线消费=开盘价成交+跌停 defer 且保留重试（`csv_daily_backtest.py:344-350`——与「skip_sell 保留 pending 下一日再试」天然对齐）；分钟引擎零消费（全文件 grep 无命中）；`skip_no_bar` 当日消耗（`csv_simulate_loop.py:262`）；chase pending 无 TTL（`:146` "keep pending for a later day"）；`limit_up_chase` 默认 True（`csv_strategy_books.py:134` setdefault + `csv_simulate_loop.py:223`）；`t1_sellable`（`ashare_session.py:39-41`）；AGENTS.md:22 预留句。
2. **实验复现主笔断言**：`import turnover_resist` → site-packages、`compute_cyqk_series` 存在（输出见 G4）。
3. **R9/R10 方向正确**：pin False 有既有机制先例（topk 书 `csv_strategy_books.py:811/:886` 已设 False）；Rust 子窗异常 NaN fail-closed（`algorithm.rs:474` `unwrap_or(f64::NaN)`）+ Python 等权法非等价（`chip/core.py:580-592` 自认「无衰减」）判断准确，skip 优于换算法。
4. **契约日 ≤T-1 写 T 的修正是本 plan 最关键的一处纠错**——正是 pool-CSV 架构对 T-1 边缘信号的正确映射，且把与 export9 先例「差一天」的照搬风险显式标出。
5. **周线防泄漏（F7）与 ma_infra 衔接一致**：`_daily_to_weekly` 确无 asof 参数（`weekly_macd_divergence.py:86-104` 全段 resample），R8 把「调用方先截 ≤D」的 pin 责任放到 ma_infra 测试，与 ma_infra plan §2 API 面（六件名全部存在）对得上；依赖排序（ma_infra 先 GO）双向声明一致。
6. **注册面可行**：`FORBIDDEN_DEFAULT_STOCK_POOL`（`csv_strategy_books.py:47`）增项与 `--pool-dir` 默认 `repo/stock_pool`（`:326`）的拒写机制自洽；别名 `11/v11/version11` 与 version10 先例（`:1088`）同款。
7. **R2 与切片 C 不矛盾**：注册新书 + frozenset 增项不改 1–10/12 书行为；与 strategy12 的并行冲突风险已在 §10 排序建议中交代。
8. **P5 预热数字成立**：2022-07→2024-01 约 370 交易日 > 200 日窗 + 20 周；P6 sanity bounds 是对抗稿好吸收。

## P0–P7 裁决输入（供人裁参考）

- **P0**：同意建议 a（框架移植先行）——7 份静态档案在、归档 §2 明令「禁止写策略有效」、可比性强；但 a 中「全市场信号统计并行另出」应给出挂靠（可排 strategy12 后），防许诺悬空。
- **P1**：同意 a/b 双跑、分钟 b 为准（v8 跨引擎先例）；日线近似=信号次日**收盘**成交（`csv_daily_backtest.py:458` 买价取 close，已实证）偏差入 HELP_LOCK 的处理方式正确。
- **P2**：同意；日线 `pending_exit` 原样即可（语义已对齐）。
- **P3**：同意独立导出器，但按 Y3 改措辞。
- **P4**：同意 seed-30 parity 为主交付 + 全市场敏感性。
- **P5/P6/P7**：同意（P7 逐条沿用归档对抗评审锁定，不重开，正确）。

---

**总评**：内部自洽度高、锚点取证质量在同类 plan 中属上乘（我逐条复核零虚构、对抗吸收忠实）；两处 🔴 均为「转录丢行/定义缺位」而非方向错误——R1 复权口径不修必歪信号，R2 契约日 T 不定义必分叉实现，连同 Y1–Y4 修订后即可进人裁。**修完 🔴 后可进实现（GO）**。
