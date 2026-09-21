<!-- agent=claude cmd-prefix=C:\Users\Thinkpad\AppData\Local\Microsoft\WinGet\Links\claude.EXE -p --no-session-persistence --output-format text --permission-mode bypassPermissions 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】E:/PycharmProjects/MyQuant-backtrader/docs/backtest/plan-ma-infra-shared-2026-09-21.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-21\plan-ma-infra-shared/_parallel/<agent>/<agent>.md`。
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
评审完成。说明：读取并行目录时 codex/claude 仅含 prompt 头、kimi 仅 2 行草稿、cursor-auto 为空——**无同轮实质意见可交叉核对**，以下为独立完成（所引事实均已读码验证）。

---

# 评审：plan-ma-infra-shared-2026-09-21.md（ma_infra 共享均线基础设施）

## 🔴 必须修

**R-A（§1 现状盘点两处事实错误——会误导实现）**
- 「布林带 **无存活实现**」（§1 表第 3 行）为假。仓内至少三处活体：
  - `oskh_factors/price_bb.py:11-22`：`bb_position`，`std = np.std(close[-period:])`（np 默认 **ddof=0**）；
  - `scripts/data/full_market_chip_resist.py:43-49`：`compute_bollinger`，`roll.std(ddof=0)`（`scripts/research/full_market_chip_resist.py:41` 还有第二份拷贝）；
  - `oskh_factors/chip/bands.py:27` 起的 `tr_bollinger_bands` 族 + `oskh_data/turnover_resistance_store.py:406 load_bb_breakout`（bb 列已入存储）。
- 「`sma_asof`——**全仓唯一** MA 实现」表述过强：上列两件内部各自计算滚动 SMA（`roll.mean()` / `np.mean(close[-period:])`）。准确说法是「backtest/research 书侧唯一通用 asof SMA 纯函数」。

  为什么必须修而非措辞瑕疵：本 plan 的立身之本是「均线 SSOT」。盘点漏掉存活件 → SSOT 边界没画清。尤其 **σ 口径在仓内已实际分裂**：chip 侧 ddof=0 vs 本 plan ddof=1（后者忠实承袭归档锁 `_archive/plans/plan-ma-chip-edge-strategy-2026-09-07.md:33` `σ=rolling.std(ddof=1)`，这个我已核实，✅）。version11 的边缘条件是 `D high > 布林上轨`（plan-version11 §1），σ 口径**直接改变信号**——若实施者以为仓内无布林件而“顺手复用” `price_bb`/`compute_bollinger`，ddof 差异对 20 根样本约差 ~2.6% 的 σ，静默改信号。修法：§1 表更正两行 + 明确 SSOT 范围声明（「收敛范围=书侧/研究侧 asof 口径；chip 侧 ddof=0 件不在本刀收敛范围，两套并存、用途隔离」）。

## 🟡 应修

**R-B（R2「import fence 现状不动」给的是假保障；*_frame 落地路径有结构性矛盾）**
fence 实体是 `tests/test_ashare_simulate_import_fence.py:17-33,52-56`：固定 15 模块清单，禁的只有 qlib/`trade_fee_policy`/`backtest.lebs`/`ashare_fill_clock`——**不含 pandas、不含 ma_infra**，且热路径本就重度 pandas（`csv_simulate_loop.py:15`、`csv_daily_backtest.py:29` 等 7 处）。所以 R2 写的「`*_frame` 批量件可 import pandas 且不得被 simulate 热路径 import（import fence 现状不动）」：fence 对此**零约束力**，这条 hard lock 不可判定、不可违反也不可满足。更深一层：切 B 后 `csv_strategy_books`（在热路径清单内）经 `strategy4_rules` 传递 import `ma_infra` 模块本身——将来 `*_frame` 若与六件**同模块**，pandas 必然被热路径传递引入，R2 意图被结构性击穿。修法：R2 改述真实机制并预埋规则——「`*_frame` pandas 件一律独立子模块（如 `ma_infra_frame.py`），书侧/热路径模块禁 import 该子模块」，落地时补一个 4 行 AST pin 测试即可（不必现在扩 fence，与 AGENTS.md:21「禁止扩成全目录扫描」纪律一致）。

**R-C（`daily_to_weekly`「移植副本」实为跨范式重写，缺差分 pin）**
源体 `oskh_factors/weekly_macd_divergence.py:86-104` 是 **DataFrame + `resample(W-FRI)`** 聚合（`close:"last"`、`_last_day:"max"`、末尾 `dropna()`，`WEEK_RULE="W-FRI"` 见 :47）；plan §2 的签名是 `(dates, closes)` 序列、且 R2/§2 注释禁 pandas——**照抄不可能，必须纯 Python 重写** pandas 的 W-FRI 分桶语义。暗礁：周六开新桶（ISO 周一起算的直觉会错）、年末跨年周归属、`dropna()` 对含 NaN 周的丢弃行为、close-last 与 _last_day-max 在重复/乱序日期下的口径。归档 §2:34 锁的口径正是「与该 pandas 函数同构」，故重写件**必须差分验证**才配称同构。修法：切 A DoD 增一条「与 `weekly_macd_divergence._daily_to_weekly` 在含周六/跨年/缺日样本上差分 pin（测试内 import pandas 不违反 R2——那是测试不是模块）」；只靠「周线 asof 无未来」单一 pin 捂不住分桶边界错。

**R-D（R5 `sma_live` 边界语义是前置条件式表述，失败模式未定）**
R5 写「`sma_live` 输入序列长 ≥ n−1」——是前置条件还是触发 None？与同条「不足 n 根返回 None（非 0 非 NaN）」的 fail-soft 基调不衔接。strategy12 切 A DoD 已假设「历史不足 5/10 根 → None 有 pin」（plan-strategy12 §7 A 行）。修法：R5 改为「`len(prev) < n−1` → None；px ≤ 0 → None（或显式 ValueError，人裁定一个）」，别留二义。

**R-E（R3「两处并存」缺防漂移锚）**
同一 W-FRI 周线换算两处手写（oskh_factors 权威 vs ma_infra 移植），正是 OSkh 设计原则⑩「同一事实只在一处手写」要防的快照腐烂形态。plan 已声明合并另开非目标（✅ 取舍清楚），但应补最低成本锚：R-C 的差分 pin 本身就是防漂移闸 + ma_infra 侧出处注释除指向源函数外，加一句「冲突时以差分测试裁判」。这样两处并存的代价被封住。

## 🟢 可选

- **R-F** §7 定向命令行补 `tests/test_strategy4_rules.py`（sma_asof 直接 pin 所在，`tests/test_strategy4_rules.py:4-16`）与 `tests/test_csv_daily_backtest.py`（:180/:190 的 strategy4 SMA pin）；虽然第二行全量跑覆盖了，但切 B 的快速回路应打到直接 pin 文件。
- **R-G** 切 A 测试加一条性质 pin：`sma_series` 前缀输出逐点等于 `sma_asof`（同一序列滑动窗口），六件内部自洽性一测锁定。
- **R-H** AGENTS.md Research entries 加一行「MA/布林/周线一律 `backtest/research/ma_infra.py`，书内禁自写均线」——AGENTS.md:9-23 是所有 agent 的权威入口，strategy12/version11 各自 R8 只锁住自己，SSOT 的**发现性**应挂在共享层（v12 切 C 已有增行先例格式）。

## ✅ 做对的地方（保留）

- **跨 plan 接线完全一致**：v12 R8 消费 `sma_asof`/`sma_live`、v11 R8 消费 `sma_asof`/`sma_series`/`bb_asof`/`weekly_sma_asof`，与 §2 六件 API 逐名对上，无孤儿无缺件；v12 P2-B「昨收序列截 n−1 + 当前分钟价」= `sma_live` 语义，逐字对齐。
- **锚点属实**：`sma_asof` 确在 `strategy4_rules.py:23-27`（含 `n=int(n)`、`len<n`→None）；`_daily_to_weekly` 确在 `weekly_macd_divergence.py:86`，W-FRI+last_day=max 转述准确。HEAD 锚无矛盾：git 实测 `599a894`（v8）→`40f660d`（12/11 plans）→`4adad96`（本 plan），各 plan 锚各自成稿时 HEAD，正常。
- **ddof=1 忠实承袭归档锁**（`plan-ma-chip-edge-strategy-2026-09-07.md:33`），非本 plan 新发明；「pandas 默认对齐」说法也对（`rolling.std` 默认 ddof=1）。
- **R1/P3 最小迁移路线正确**：只 re-export + import 改向、gate 逻辑不动；v4 既有三层 pin（test_strategy4_rules / test_csv_daily_backtest:180-190 / test_csv_strategy_books.py:107）天然构成零变更证明，`git diff 仅 import 行` 是可核验 DoD。
- **R4 PIT 纪律（序列截止权在调用方）**与 v4 模块 docstring「刻意不含今日收盘」、v12 R3、v11 R6 同构，三 plan 一套话。
- **P4 选 research 位置**理由成立（三消费方两个在书侧；oskh_factors 是因子库，AGENTS.md:3 职责分野清晰）；R3 不动 oskh_factors 公共 API 同时尊重归档锁「不改 oskh_factors」。
- **P1/P2 YAGNI**（EMA/WMA 不做、`*_frame` 缓做）判断正确：strategy7 `alternate_tp_decision` 的 moving_average 是外部传入不自行计算（`strategy7_rules.py:92`），确无 EMA/WMA 消费方。
- **风险档「低」成立**：纯函数 + 零行为重构，无安全阀/超时/并发面——按裁决原则无须跑 ★ 类实验（我核实了本 plan 不含 timeout/budget/锁类设计）。
- **§9 顺序建议正确**：ma_infra 最小最先行，12/11 直接消费，依赖序无环（v11/v12 互不依赖、均前置依赖本 plan）。

---

## 总评

方案骨架健康：API 面与两个消费 plan 逐名咬合、锚点真实、迁移路线最小、PIT 纪律贯穿。真正的缺口集中在「SSOT 自我认知」上——盘点把存活的 ddof=0 布林族看漏（🔴R-A）、把不可照抄的 pandas 重写称作移植副本且无差分闸（R-C）、把不设防的 fence 当保障（R-B）。**修订 R-A/R-C/R-D 三条（半天文档工作量，零代码成本）后可进 P1–P4 人裁；R-B 以改述+预埋规则处理。** 按「激进一次到位」取向：一次把 SSOT 边界、σ 口径并存图、差分 pin 写死，比事后追认便宜得多。
