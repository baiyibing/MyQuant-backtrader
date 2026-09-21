<!-- agent=claude cmd-prefix=C:\Users\Thinkpad\AppData\Local\Microsoft\WinGet\Links\claude.EXE -p --no-session-persistence --output-format text --permission-mode bypassPermissions 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】E:/PycharmProjects/MyQuant-backtrader/docs/backtest/plan-strategy12-jinrongyuan-2026-09-21.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-21\plan-strategy12-jinrongyuan/_parallel/<agent>/<agent>.md`。
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
四位并行席位中 codex/cursor-auto 仅有 prompt 桩、kimi 刚起步（无已完成意见可交叉核对），按指令独立完成。所有取证已闭环，输出评审意见如下。

---

# 评审意见：plan-strategy12-jinrongyuan-2026-09-21（v0.4）

**评审定位**：综合裁决 + 跨文档交叉验证。锚点基线说明：plan 自称 HEAD `599a894`，当前 master 实为 `0d28ef2c`（`.git/refs/heads/master`）——**全部 §2 锚点我已在当前工作树逐一复核，仍全部成立**，故仅记漂移不计过错。同行席位（codex/cursor-auto/kimi）截至本次完成时点无已落盘意见可引用，以下为独立结论；主笔对抗稿 F1–F8 已作为交叉对象逐条核对。

## 🔴 必须修

**R-1｜P6 事实前提失实：「单码单日上限沿用引擎现状」——引擎根本没有任何单码单日买入上限闸。**
`csv_simulate_loop.py` 全文 grep `max_add|same_day|per_day|buys_today|MAX_.*ADD` 零命中；「chase+池买 2 笔」是 14:55/9:45 两个时点的**调度涌现结果**，不是可「沿用」的机制。P6 借一句失实前提把「台阶与名单加仓并存上限」这个人裁点实质空转掉了。更要命的是引入买回后，单码单日买向笔数变为：池买 1 + chase 1 + 台阶 N + MA5 收复买回 + MA10 收复买回（止损当日站回 MA10 与池买同在 14:55 完全可能）——**没有闸的「现状」在新买因加入后已不是现状**。修法：P6 改写为「现状=无显式闸，结构性 2 笔；加买回后理论上限 X 笔，是否加闸（建议：单码单日总买向 ≤N 笔或 notional 上限）交人裁」，并把该问题从「沿用」改回真问题。

**R-2｜减仓重复触发语义未定义——「掉下五日线减仓 50%」在**减仓后未收复期间**（连续多日收在 MA5 下方）是否每日再减 50%？**
P3 定义了单次减仓、P4 定义了收复买回与「允许无限次循环」，但循环的**环内重入**没有语义：若实现者按字面每日评估，将得到 50%^n 几何衰减到持仓灰尘 + 记忆逐日累加，而单次收复「全额买回」累加记忆（P4）会造成一次性远超原仓位的买入脉冲（仅靠 P9-④ 市值闸兜底）。docx 沉默 ≠ 可以不定义——这是本 plan 自评「中高风险（股数/现金流不变量）」的核心裸露面。修法：P3/P4 增补一条明确语义（建议：减仓记忆未清零期间不重复触发，即同一「下方周期」只减一次；或明确按日重复并给出收敛证明），并入 Slice C 引擎级测试 DoD（连续 N 日 MA5 下方场景 pin）。

## 🟡 应修

**Y-1｜γ 引擎面枚举与 Slice C 自相矛盾：§0 说引擎「只加最小面」两项（shares 覆写 + wanted_shares），但 Slice C 的「送转缩放回调」是第三处引擎触点。**
当前引擎无任何书侧 exdiv 事件回调：`apply_exdiv_economics`（csv_ledger.py:164-183）在引擎内部执行，书侧 gate 只在逐 bar 评估时被调用。书要感知送转日必须二选一：① 引擎加第三个 opt-in 钩子（exdiv 回调）——γ 枚举要如实扩为三项；② 书侧逐日 diff 各码 `sum(lot.shares)` 自行侦测——脆弱（与 chase/step 加仓混淆，需排除买向 lot 变化）。plan 未裁，实施者会随手发明。建议 ①，并在 §0/Slice B 如实计入 γ 面。

**Y-2｜部分卖/买回的「实际成交回报」契约缺失：记忆股数必须按**实际成交量**更新，而非请求量。**
两处代码证据：① `csv_ledger.py:332`——`_sell` 无 volume_cap、无 pending_exit 时，`shares -= _locked_bonus(...)` **静默缩减**锁定送转股，成交 < 请求；② `csv_ledger.py:359`——volume_cap 分支 `shares = min(shares, allocated)` 可部分分配。若书侧记忆按请求量清零/累加，减仓记忆与持仓将系统性漂移（正是 plan 自评的股数不变量风险）。修法：Slice B 明确新部分卖 helper 的返回契约（返回实际成交股数或 0），Slice C DoD 增 pin「锁定送转股存在时部分卖 → 记忆=实际成交」。

**Y-3｜sell_gate → wanted_shares 的接线契约未定义。**
现有钩子签名返回 `Optional[str]`（strategy4_rules.py:36-41），daily 引擎拿到 reason 后走整仓路径（csv_daily_backtest.py:392-423）。γ 说「卖出路径可选 wanted_shares」但没说书怎么把股数传给引擎：是 sell_gate 返回 `str | tuple[str, int]`（侵入既有钩子签名，R1 零变更承诺要重新论证），还是书侧编排直接调新 helper 绕过 sell_gate（推荐，gate 仍只做信号、股数由书侧状态机计算）。二选一不裁，Slice B 编码即卡。另注意 daily 引擎 limit 阻断时 reason 只以字符串进 `pos.pending_exit`（:416/:423）——部分卖跨日递延无法借道 pending_exit 携带股数，这反过来印证「独立队列」的必要性，但递延部分卖的**次日执行语义**（次日开盘价重评还是机械执行）plan 未写。

**Y-4｜R8 硬锁依赖一个未人裁 GO 的前置 plan，且 §10 修订程序未设 GO 顺序门。**
ma_infra plan 状态为「v0.1 · draft（未评审、未人裁，GO 前禁编码）」（plan-ma-infra-shared-2026-09-21.md:3）；其 §9 建议「本 plan 最先 GO/实施」——但 strategy12 的 §10 流程（P2–P9 人裁 → GO → Codex 交接）没有把「ma_infra 已 GO/合入」列为本书 GO 前置条件。若顺序颠倒，Codex 无头实施会在 R8 与「模块不存在」之间自作主张（大概率书内自写均线，直接违反 R8）。修法：§10 增一行「本书 GO ⇒ ma_infra 须已 GO；否则 R8 降级方案须人裁登记」。

**Y-5｜头部宣称「锚点行号全套勘误」，但 HELP_LOCK pin 归属勘误未回填。**
对抗稿 §5 明确：help_lock 内容 pin 在 `tests/test_csv_strategy_books.py:176-179`（我已复核：`assert "策略 8" in BOOKS["version8"].help_lock` 等 4 行确实在此），milestones 文件锁的是注册+里程碑语义（test_strategy8_milestones.py 全文无 HELP_LOCK 断言）。plan §2「里程碑书先例」行仍把「HELP_LOCK + 冻结语义 pin」整体锚到 test_strategy8_milestones.py。Slice A 要照此找 pin 会找错文件。半勘误=头部声明失真，须补。

**Y-6｜跨文档链接断链：前序引用 `_archive/plans/plan-v8-rules-v2-2026-09-16.md` 不存在。**
Glob `docs/backtest/**/plan-v8-rules-v2*.md` 仅命中根级 `docs/backtest/plan-v8-rules-v2-2026-09-16.md`（未归档或已移出）。§7 前序引用指向 `_archive/plans/` 是死链，v8 先例是本书买侧的全部依据，评审者/实施者点开即 404。改链接或移档二选一。

**Y-7｜P3 卖出顺序只定了两端，中间层未定义。**
「is_step 先卖、lot_id==0 最后」之后，非 step 非 lot0 的 lot（池买加仓、chase、**买回新建 lot**）之间的顺序未定。策略 12 持仓结构里中间层是常态（减仓→买回→再减仓循环会不断制造中间层 lot），不同顺序改变各 lot 残留成本与后续 step/止盈行为 → 回测数字不可复现。一行补齐即可（建议：中间层按 lot_id 升序，即 FIFO）。

**Y-8｜F8（多 lot 拆卖费用偏差）声称已吸收，但无任何落点。**
对抗稿 F8 裁定「min_cost=5 逐笔最低佣金在拆卖下略高估 + 研究引擎无印花税，记入 HELP_LOCK 声明，不改」。v0.4 头部宣称吸收 F1–F8，但全文只在 P2 出现 HELP_LOCK（内容=跨引擎口径差），费用偏差声明没有进 Slice A 的 HELP_LOCK DoD。补一句即可闭环。

## 🟢 可选

- **G-1**：P8 决策输入漏了同族反例——金榕元 7 先例是 `--pool-dir` 必填、不回落 `stock_pool/`（MyQuant AGENTS.md:13）。P8 只摆了 8 vs 9/10；人裁前应把「同族 7=强制、8=默认」两先例都放上桌。
- **G-2**：Slice B「默认参数行为与 HEAD 逐字节等价」措辞过强（文件必然有 diff），建议改为「默认参数下 trades/equity 输出逐字节等价」并以此设计 pin（输出对比而非行为描述）。
- **G-3**：R1「现有全量 pytest（1399+）」我按静态口径复核为 877 个 `def test_`（92 文件）——参数化展开后 1399+ 可信但未运行验证，建议 GO 前跑一次 collect-only 把数字钉死，避免 R1 成为无法判定的硬锁。
- **G-4**：R-2 修复后，「止损当日同时满足 MA10 站回买回（旧记忆）」与「止损卖出」同日共存的资金/顺序语义，顺带在 P5 写一句（卖出先行、买回后评即可）。

## ✅ 做对的地方（保留）

1. **§2 as-built 锚点质量极高，全部独立复核通过**（在 HEAD `0d28ef2c`）：chase_decision `csv_ledger.py:115-121`、Position `:70-82`、step_add_due lot0 锚 `strategy8_rules.py:61-64`、may_add 接线 `csv_strategy_books.py:573`、v8 注册 `:1018-1031`、分钟喂数 `csv_minute_backtest.py:669`、T 日拦截 `csv_simulate_loop.py:283-288`、skip_held 仅挡持仓中 `:253-254`。
2. **F1–F8 吸收忠实**：P3（is_step 先卖保 lot0 台阶锚）、P5（双记忆并存）、R3 措辞（现价=探测值不入序列）、P9 四锁、独立部分卖队列、stats 桶——逐条与对抗稿 §1 对得上，且「`ma12:` 落 else 桶 sell_pos_trail」我已在 `csv_ledger.py:384-397` 亲证（`startswith("ma_signal")` 不匹配 `ma12:`），R5 的必要性成立。
3. **「_sell 本体无 T+1、仅 volume_cap 分支 `:347` 查」的关键判断正确**——这正是 P9-② 的立论基础，实测属实（:347-349）。
4. **「不复用 pending_exit」的排除决策有据**：per-lot 字符串（:79）+ volume_cap 下全或无（:333-336）+ daily 引擎 limit 阻断只存字符串（:416/:423），三重证据齐。
5. **P9-③ 送转缩放语义与代码现实吻合**：`rescale_position` 不动 shares（:152-160 docstring X-R1）、bonus 增股入源 lot（:177-182），按 k 缩放记忆+现金红利不动是正确推论。
6. **R7 与 MyQuant AGENTS.md:22（version11=ma_chip 预留）一致**，无编号冲突；数据窗口终点 20260909 与既有 lake pin（test_csv_strategy_books.py:168）一致。
7. **无 SSOT 冲突**：不新增数据路径/符号格式/配置键，池与 MA 消费走既有引擎喂数与 resolvers 纪律（R6），symbol-format/disclosure SSOT 均不触及。
8. γ 方案相对 α（过度抽象）与 β（不可实现）的排除论证成立，opt-in 默认 None + 输出等价 pin 的护栏设计符合本仓 R1/R2 惯例。

## 总评

骨架与锚点质量在同类 plan 中属上乘、对抗回填基本忠实，但 **P6 的「沿用现状上限」是失实前提（R-1）与减仓环内重入语义缺失（R-2）两处会直接改变策略风险面貌的硬伤未除，外加 γ 面枚举/回报契约/前置 GO 顺序三个实施级缺口**——**修完 🔴×2 + Y-1/Y-2/Y-4 后可进实现**；P2–P9 人裁照常进行，建议 R-1/R-2 升为必答题加入 §4 对外征答。

*（编排层备注一句：cursor-auto 座位 workspace 被钉在 OSkhQuant1.3 而非本仓，若其产出空泛/失据，先查此因。）*
