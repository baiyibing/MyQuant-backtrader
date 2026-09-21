<!-- agent=kimi cmd-prefix=C:\Users\Thinkpad\.kimi-code\bin\kimi.EXE -m kimi-code/k3 --output-format text -p 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

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

【你的评审侧重】优先**跑实验验证关键行为**：对 timeout/budget/safety-valve/并发锁/异步/fallback/重试类设计，构造最小实验（slow fn + tight budget → 测调用方何时返回）。读码不够时动手测——**docstring 不可信**（docstring 宣称的行为可能被 stdlib/框架吞掉，如 `ThreadPoolExecutor.__exit__`→`shutdown(wait=True)` 让超时从不生效）。保持这个习惯。 <prompt> -->
• 并行目录里其他评审员（claude/codex/cursor-auto）目前只有 prompt 桩，无已完成意见——我独立评审。先取证代码锚点。

• 核心锚点陆续坐实。再查 `lot_budget` 语义（P9④ 上限建议可能与 v8 多笔加仓冲突）、`scan_held_day` 卖闸评估时点、HELP_LOCK，并提取 docx 原文核对转录。

• 关键行为差异已定位（分钟引擎 sell_gate 是逐分钟扫描、首触即发，非 14:55）。现在按我的评审侧重跑最小实验，坐实 `_sell` 部分卖记账门与 T+1 缺口：

• 实验坐实三个关键事实。再核一处：日线引擎 sell_gate 触发后到底是当日收盘成交还是次日开盘（P2-B 日线退化口径的依据），以及 daily_quota 与买回的关系：

• 取证完成，证据充分。以下为评审意见。

  ---

  # 评审意见：plan-strategy12-jinrongyuan-2026-09-21（v0.4）

  评审基线：仓 `MyQuant-backtrader` HEAD `0d28ef2`（plan 锚点标 `599a894`；`git log 599a894..HEAD -- backtest/research/` 为空，锚点内容仍然有效，仅标签陈旧）。并行目录中 claude/codex/cursor-auto 目前只有 prompt 桩、无已完成意见，本轮独立完成。docx 原文已提取核对（`OSkhQuant1.3/docs/bucket_policy/金榕元交易回测策略--0921-策略12.docx`），转录与 §1 一致，含 plan 未点破的一点：规则 5 在 docx 中标的是「**止盈**」。

  ## 实验验证（可复现）

  实验一：`_sell` 的 T+1 缺口 / 部分卖记账门 / stats 桶 / chase 等值边界（stdin 脚本，无文件写）：

  ```python
  import sys, datetime; sys.path.insert(0, ".")   # cwd=MyQuant-backtrader, vanna312
  from backtest.research.csv_ledger import SimState, Position, _sell, chase_decision
  st = SimState(cash=1e7); pos = Position(code="X", shares=1000, cost=10.0, entry_idx=5, peak=10.0, lot_id=0)
  st.positions["X"] = [pos]
  _sell(st, "X", pos, 10.0, datetime.date(2026,9,21), "ma12:probe", day_i=5)   # entry_idx==day_i → T+0
  class FakeCap:
      def clamp(self, key, at, wanted, atomic=False): return (min(400, wanted), "skip_volume_cap:probe")
      def consume(self, key, shares): pass
  st2 = SimState(cash=1e7, volume_cap=FakeCap()); pos2 = Position(code="Y", shares=1000, cost=10.0, entry_idx=0, peak=10.0, lot_id=0)
  st2.positions["Y"] = [pos2]
  _sell(st2, "Y", pos2, 10.0, datetime.date(2026,9,21), "ma12:probe", day_i=5)
  print(chase_decision(10.0, 10.0, 11.0))
  ```

  原始输出：

  ```
  E1a T+0 sold? lots: None | trade shares: 1000 | reason bucket sell_pos_trail: 1 | sell_ma: 0
  E2 partial under cap: lot shares left: 600 | trade shares: 400
  E3 chase px==open -> abandon
  ```

  另：`pytest tests/ --collect-only -q` → `1401 tests collected in 3.64s`（plan R1「1399+」成立）。

  实验结论：① P9② 前提为真——`_sell` 本体无 T+1 检查（volume_cap=None 时 T+0 lot 被整仓卖出），T+1 全靠调用点过滤（`csv_daily_backtest.py:344/352`、`csv_minute_backtest.py:656`），减仓基数必须自算 t1_sellable；② R5 前提为真——`ma12:` reason 现落 `sell_pos_trail` 桶；③ 部分卖记账（`csv_ledger.py:400-401` `pos.shares -= shares`）**仅在 volume_cap/exdiv 非空时可达**，默认配置下整 lot 移除走 `:408-411`——切片 B 的 wanted_shares 必须重构这个分支，且「默认参数零 diff」的 pin 要专门压住 `:400-411`。

  ## 🔴 必须修

  **K1. §3 与 P3/§7B 卖 lot 顺序自相矛盾。** §3 缺口 1（plan:42）写「跨 lot **FIFO** 取整百股」；P3（plan:71）与切片 B DoD（plan:92）写「**is_step lot 先卖、lot_id==0 最后**」。FIFO=最旧优先=lot0 最先，与「lot0 最后」直接冲突。照 §3 编码必破坏台阶锚（`strategy8_rules.py:61-64`：`parent is None → return False`）。须删改 §3 的「FIFO」表述，统一为 P3 口径。

  **K2. P2-B 的「14:55 评估当根成交（v8 时钟先例）」是错误先例，会误导实现。** 分钟引擎卖出扫描是**逐分钟、首触即发**：`scan_held_day_python` 的 `for i in range(n)` 循环内每分钟调 `sell_gate(...)`，触发即 return（`csv_minute_backtest.py:285-329`，sell_gate 调用在 `:316-322`）；v8 卖出走同一扫描的 take_profit 分支。14:55 是**买侧**时钟（模块 docstring `csv_minute_backtest.py:125`「买入：池 CSV 当日候选、14:55 收盘价」），卖侧无此先例。若 v12 要 14:55 一次性评估 MA 出场，那是全新机制（防盘中来回打脸的设计选择，可成立），必须自立论据、不能挂「v8 先例」；若复用 sell_gate 钩子则天然是逐分钟口径。两个选择实现路径不同，P2-B 须改写清楚。

  **K3. P9④ 建议的「当日该码市值+在途买回 ≤100 万」与 v8 多笔加仓语义冲突，按此实现规则 5 会失效。** v8 的 `lot_budget`：「每笔都是整笔 name_budget」（`strategy8_rules.py:47-49`），名单再现+台阶可合法持有数笔 100 万。一旦台阶加仓后市值 >100 万，该 cap 将**永久禁止买回**——恰是多 lot 场景下买回最重要。对抗层真正识别出的风险是「止损清空→名字再入池/追买→MA10 收复又买回→持仓翻倍」（`csv_simulate_loop.py:253-254` skip_held 仅挡持仓中，此判断正确），但药方开错。正确方向是**记忆与新买因的冲抵规则**（人裁选项：池/chase 新买入时清零 stopped/reduced 记忆，或新买入股数先冲抵记忆），而非市值 cap。

  ## 🟡 应修

  **K4. v12 继承 v8 `PEAK_GAP_MIN=15`，MA 闸会被峰值间隙阻断延迟。** `scan_held_day_python` 中 sell_gate 包在 `if not peak_blocked:` 内（`csv_minute_backtest.py:312-314`）；v8 `PEAK_GAP_MIN=15`（`strategy8_rules.py:18`），v4=0。破五日线若发生在刚创日内新高 15 分钟内会被压后——对「跌穿均线」型信号语义不符。plan 全文未提此继承行为。须显式裁决（MA 通道 peak_gap_min=0 或 HELP_LOCK 明示）。

  **K5. lot0 锚死亡边界无规则。** P3「is_step 先卖、lot0 最后」不保证 lot0 存活：持有 lot0=100 + 两台阶 lot 时 50% 减仓可能耗尽 lot0 → `step_add_due` 因 `parent is None` 永久停加（`strategy8_rules.py:61-63`）。须补一条：减仓保留 lot0 ≥100 股（减额相应缩水），或明示接受台阶终止。

  **K6. 减仓基数须扣 locked bonus（exdiv 启用时）。** P9③ 只覆盖「记忆股数按 k 缩放」，未覆盖基数计算：`_sell` 在 exdiv 下扣 `_locked_bonus`（`csv_ledger.py:332`），且 linked/pending 场景走 defer（`:326-336`）。v12 若带 exdiv 跑，部分卖基数=t1_sellable **且** 扣 locked bonus，否则撞全或无分支或卖出未上市红股。另 P9③ 未给取整规则（k 缩放后非整百如何处理：建议 floor100 + 残余记 stats）。

  **K7. `shares_override` 的账目语义未定义。** `execute_buy` 内 `supp = max(0.0, notional - per)`、`daily_quota_used += min(per, notional)`、`invested_notional`（`csv_ledger.py:263-267`）都以 `per` 为锚；买回单传 shares_override 时 `per` 传什么（建议 per=notional）须写进切片 B 契约，否则 supp/quota 统计漂移。

  **K8. P4「允许无限次循环」缺 anti-whipsaw 讨论。** 逐分钟口径下同一根 MA5 可日内反复穿越：减→买→再减，每轮付佣金+可能同日多次。docx 虽无次数限制，但建议提供选项（每通道每日一次 latch）供人裁，成本量级一句话即可。

  ## 🟢 可选

  - K9. 锚点标签 `599a894` 陈旧（现 HEAD `0d28ef2`），内容有效，建议刷新标签。§1 规则 6 锚 `csv_ledger.py:115-122` 与 §2 `115-121` 不一致，统一为 115-121。
  - K10. §2「may_add（恒 True）」不精确：实为 `bool(lots) and float(px) > 0`（`strategy8_rules.py:52-54`）；「execute_buy 无 shares 覆写（:219-229）」指向的是 `_buy_size`，execute_buy 本体在 `:232-248`。
  - K11. chase 等值边界：实验三证 `px == open → "abandon"`，docx 只写 `>`/`<`，等值属解释性行为，HELP_LOCK 一句话即可。
  - K12. 「独立部分卖队列」建议明示其载体主要是**日线**引擎的次日开盘通道（日线无 volume_cap，`_sell` 必走整 lot 移除 `:408-411`）；分钟引擎可当日当根成交，不需要队列。
  - K13. P5「先评止损后评减仓」与 docx 的「止盈/止损」二分一致，建议 P5 顺带裁决：止损清空后 reduced 记忆若随后 MA5 先收复，买回价量是否受现价≥MA10 前不得买回的约束（plan 已答「不被压到慢通道」，逻辑自洽，仅需人裁签字）。

  ## ✅ 做对的地方

  - 对抗回填的四锁（P9①②③）前提全部经实验/代码坐实：`_sell` 无 T+1（实验一）、`execute_buy` 无 shares 覆写（`csv_ledger.py:248`）、`rescale_position` 不动 shares（`:152-161` docstring X-R1）、bonus 入源 lot（`:177-182`）、pending_exit 全或无（`:333-336` + `:354` atomic）→「独立部分卖队列」结论正确。
  - R5 的 stats 桶缺口为真（实验一：`ma12:` 落 `sell_pos_trail`），扩桶要求必要且位置准确（`:384-397`）。
  - P2-B 日线退化口径与代码一致：sell_gate reason 非 same_bar → `pending_exit` → 次日开盘成交（`csv_daily_backtest.py:398-425` + `daily_same_bar_prefixes=("open_board",)`）。
  - R8 与 ma_infra plan 的 API 面（`sma_asof`/`sma_live`，不足 n 根返 None）完全对齐；R7 与 AGENTS.md:22 的 version11 预留一致；version11/12 当前均未注册；测试基数 1401 与 R1 相符。
  - 切片 C DoD 含「当日买回当日不可再减（T+1）」「送转日记忆缩放」「skip_cash」，正是本策略最危险的三处不变量，覆盖到位。

  ## 总评

  骨架方向（γ 最小引擎面 + 书侧状态机 + ma_infra 消费）正确且贴合仓内现状，对抗回填质量高；但 §3/P3 顺序矛盾（K1）、P2-B 假先例（K2）、P9④ 药方错误（K3）三处会直接误导编码，必须先修订。**结论：暂不可进实现——完成 K1–K3 修订并人裁 K4–K6 后可 GO**（修订量小，均为文档级，不动骨架）。

