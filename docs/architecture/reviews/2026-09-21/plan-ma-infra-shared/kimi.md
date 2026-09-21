<!-- agent=kimi cmd-prefix=C:\Users\Thinkpad\.kimi-code\bin\kimi.EXE -m kimi-code/k3 --output-format text -p 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

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

【你的评审侧重】优先**跑实验验证关键行为**：对 timeout/budget/safety-valve/并发锁/异步/fallback/重试类设计，构造最小实验（slow fn + tight budget → 测调用方何时返回）。读码不够时动手测——**docstring 不可信**（docstring 宣称的行为可能被 stdlib/框架吞掉，如 `ThreadPoolExecutor.__exit__`→`shutdown(wait=True)` 让超时从不生效）。保持这个习惯。 <prompt> -->
• 我先读待评审文档全文，并查看并行评审目录里是否已有其他评审员的完成稿。

• claude/codex 目前只有 prompt 头，未完成。看 kimi.md 和 cursor-auto.md 是否已完成。

• 交叉核对情况：claude/codex/cursor-auto 三份均只有 prompt 头（未完成），无可交叉核对的已落地意见；kimi.md 为本会话实时输出流。以下为独立完成稿。

  ---

  # 评审：plan-ma-infra-shared-2026-09-21（v0.1 draft）

  **取证与实验声明**：已读 plan 全文、`strategy4_rules.py`、`weekly_macd_divergence.py`、两个消费方 plan、import fence 测试；并用 vanna312（python 3.12.13 / pandas 2.3.3 / ruff 0.12.0）跑了 5 组最小实验（E1–E5，stdin 注入、零文件写入，脚本与原始输出附文末）。本 plan 无 timeout/并发/异步/重试类设计，实验火力集中在它真正依赖的 stdlib/框架行为：pandas resample/rolling 语义与"移植副本"可行性。

  ## 🔴 必须修

  **R1. §1 现状盘点两处事实错误（"全仓唯一 MA" / "布林无存活实现"均不成立）**

  - plan L18 称 `sma_asof` 为"全仓唯一 MA 实现"。事实：`oskh_factors/weekly_macd_divergence.py:183` 有存活的周线 MA：`weekly["close"].rolling(MA200_WINDOW_WEEKS).mean()`。
  - plan L20 称布林带"**无存活实现**（随 Cerebro 退场删除）"。事实：仓内有 3 份存活布林副本，`scripts/data/full_market_canonical_resist.py:246-255`：

    ```python
    bb_mid = float(close_series.rolling(20).mean().iloc[-1])
    bb_std = float(close_series.rolling(20).std().iloc[-1])
    ```

    同码还复制于 `scripts/research/full_market_canonical_resist.py:248`、`scripts/gates/verify_single_stock_turnover_resist.py:399`。且该副本 `<20` 根时回落为全序列 `mean()/std()`（`:252-253`）——与 plan R5「不足 n 根返回 None」口径**分歧**，这恰是收敛 SSOT 的最强论据，盘点却写成"无"。

    影响：P1 人裁将基于错误盘点决策；且这些既有副本是否纳入后续迁移，plan 非目标只字未提。**修**：盘点写实（可改述为"书侧消费路径上无共享实现，存量 3 份 scripts 副本口径已分裂"），并声明 scripts 副本归入非目标还是后续收敛。

  **R2. API 面对自己锁定的消费方不齐套：缺周线序列件，实测逐日 asof 不可行**

  version11 R8 硬锁消费 ma_infra（`plan-version11-machip-csv-2026-09-21.md` L54），其边缘检测需 **cond[D] 与 cond[D-1] 两边的 20 周线值**（同 plan L18「两边都必须有限」）。ma_infra §2 只给标量 `weekly_sma_asof`（L33）。逐日截断调标量件的复杂度实测（E4，n=1000 日、5000 票全市场）：

  ```
  E4 weekly-convert per call: pure-py 2.59 ms | pandas 6.06 ms
  E4 per-day-asof x 1000 days x 5000 symbols: pure-py 215.5 min | pandas 504.6 min
  ```

  3.6–8.4 小时/次导出，不可行；若在导出器内自制"换算一次+滚动"逻辑则违反 version11 R8「不自写均线」。**修**：§2 增加 `weekly_sma_series`（一次 W-FRI 换算 + 周窗滚动 + 逐日对齐回填），并建议同补 `bb_series`（bb 逐日标量虽可行但同样 O(n²) 浪费）。P1 的答案就是"不齐套"，plan 应在自己的人裁栏先写明。

  ## 🟡 应修

  **R3. `daily_to_weekly` 返回日期语义未 pin——E1 实测 Friday 标签可为非交易日**

  E1 原始输出（2024-09-13 周五休市）：

  ```
  label=2024-09-13  last_day=2024-09-12  close=4
  ```

  W-FRI 的 bin 标签是 Friday 日历日（节假日照样是标签），真最后交易日是 `_last_day`。plan §2 签名 `list[tuple[date, float]]`（L32）未指明返回哪个。若实现返回 Friday 标签，version11 周线 asof join 在节假短周会错一周（D=09-12 时标签 09-13 的本周被排除）。**修**：R5 语义 pin 增三条——① date=周最后交易日（`_last_day=max`，非 Friday 标签）；② 保留末端未完成周（version11 P7 已锁"可参与"）；③ 停牌空周无 bar（E1：09-30 全周消失，09-27 下一根直接 10-11）。

  **R4. R3 接受"移植副本两处并存"，但切片 A DoD 无 vs 原实现的等价 pin——漂移无哨兵**

  E2 实测：朴素纯 Python port 可与 pandas resample 逐值对齐（含节假短周+停牌空周），证明等价 pin 廉价可行。plan L65 的 pin 清单（None 边界/live 拼接/ddof=1/周线无未来）独缺这一条。两处并存而无等价测试 = 静默漂移定时炸弹。**修**：切片 A DoD 增「`daily_to_weekly` vs pandas resample 参照（测试内联 pandas，合成日期含节假短周/空周）逐值相等」。

  **R5. R2 内部矛盾 + weekly 两件能否用 pandas 未裁决**

  R2（L41）提「`*_frame` 批量件可 import pandas」，但 §2 无 `*_frame` 件、P2 明说"本刀不做"（L51）——死文本；且未说 `daily_to_weekly`/`weekly_sma_asof` 算不算"标量件零第三方依赖"。事实补充：fence 不拦 pandas（`tests/test_ashare_simulate_import_fence.py:52-56` 只禁 qlib/lebs/trade_fee_policy/fill_clock），故这是纯度选择而非门禁约束。**修（建议）**：weekly 两件走纯 Python（E4：2.59 ms/1000 日，比 pandas 还快 2.3 倍，全模块零依赖），R2 删 `*_frame` 句或标注"预留"。

  **R6. 切片 B 三处文字自相矛盾**

  切片 B 内容列「调用点改向」（L66）vs P3 建议「gate 逻辑不动」（L52）vs DoD「`git diff` 仅 import 行」（L66）。事实：`csv_strategy_books.py:483-484` 以模块属性消费（`strategy4_rules.buy_gate`），re-export 后**全仓零调用点需改**。矛盾文字会诱导实施者改 gate 函数体、扩大 diff 对抗 R1。**修**：统一为「仅 re-export + 删原 def」；DoD 写实为「diff 仅 import 行 + 删除原 def 4 行」。

  ## 🟢 可选

  - **R7**：R5「`sma_live` 输入序列长 ≥ n−1」（L44）有歧义——是调用方预截还是函数自取尾窗？建议 pin「函数自取末 n−1 根（与 `sma_asof` 尾窗语义一致），不足返回 None」，与 §2 注释「截 n-1 + px」对齐。
  - **R8**：`sma_series` pin 须用 `pytest.approx` 而非 `==`（E5：前缀和 vs 窗口和 FP 漂移 1.24e-12 / 2500 点）；并明示前 n−1 位为 None。
  - **R9**：§7 验证命令建议加 `tests/test_strategy4_rules.py`——被迁移符号的直接 pin（现只列了 test_ma_infra + test_csv_strategy_books）。
  - **R10**：`sma_live` 的消费方依赖 strategy12 P2-B 裁决（`plan-strategy12-jinrongyuan-2026-09-21.md` L63，P2 未裁）。若 P2 裁 A（全昨收 MA），sma_live 暂无消费方，与 plan 自己的 P1/YAGNI 原则冲突——建议人裁顺序上先裁 strategy12 P2，或在 P1 栏声明 sma_live 为「P2-B 预留」。
  - **R11**：`from ... import sma_asof as sma_asof` 的 F401 消法实测通过（ruff 0.12.0 默认规则 `All checks passed!`）；仓内另有 `# noqa: F401` 先例（`oskh_core/turnover_resist_bridge.py:4`），两式皆可，选定即行。

  ## ✅ 做对的地方

  - 种子 API 选择稳妥：`strategy4_rules.py:23-27` 与 §1 行号逐字吻合；`tests/test_strategy4_rules.py:5-6` 经 re-export 零变更全绿（符号原地保留）。
  - bb 口径 ddof=1 与存量实现同源（E3：pandas `rolling(20).std()` 默认 ddof=1，且 ≠ ddof=0），与归档口径、version11 P7 三方一致。
  - R4 PIT 纪律「只做数学、截止权在调用方」与 strategy4 先例（模块 docstring「均线输入刻意不含今日收盘」）、strategy12 R3 完全同构。
  - P4 位置有充分先例：scripts→`backtest.research` import 已有 20+ 处（`export_strategy9_pool.py:26` 等）；fence 为固定清单不扫新文件（`test_ashare_simulate_import_fence.py:17-33`）。
  - 无 SSOT 冲突：本仓无 `docs/SSOT.md`；模块无符号/数据格式/配置键面。

  ## 实验附录（可复现）

  脚本：vanna312 python stdin 注入，含 E1（W-FRI 节假短周+停牌空周 resample 行为）、E2（纯 Python port vs pandas resample 逐值对拍）、E3（rolling std ddof / mean min_periods）、E4（逐日周线 asof 性能外推）、E5（前缀和 FP 漂移）+ ruff stdin 检查。关键原始输出已随对应条目引用（E1 见 R3、E4 见 R2、E5 见 R8）；E2 输出 `pure-python port == pandas resample: True`；E3 输出 `rolling(20).std() == ddof=1: True`、`first 19 are NaN: True`。

  ## 总评

  方向正确、范围克制、种子选择稳——这是一个该做的收敛；但 §1 盘点有两处实测证伪的事实错误，且 API 面对 version11 已硬锁的消费**不齐套**（缺周线序列件，实测逐日 asof 需 3.6–8.4 小时不可行）。**当前不可进实现**；修掉 R1/R2 两处 🔴 并补齐 R3/R4 两条 pin 后可 GO（🟡 均为一两句话级别的修订，不动架构）。

