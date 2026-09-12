<!-- agent=claude cmd-prefix=C:\Users\Thinkpad\AppData\Local\Microsoft\WinGet\Links\claude.EXE -p --no-session-persistence --output-format text --permission-mode bypassPermissions 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-unify-csv-strategies-1-8-2026-09-12.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-12/plan-unify-csv-strategies-1-8-2026-09-12/_parallel/<agent>/<agent>.md`。
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

【你的评审侧重】优先**综合裁决 + 跨文档交叉验证**：检查方案内部自洽（不自相矛盾）、跨节引用一致、与关联 plan/SSOT 的衔接；对抗性复核其他评审员的断言（凭代码/实验驳回误判）。 <prompt> -->
核对完毕。四家并行评审槽位（codex / claude / cursor-auto / cursor-kimi-k3-high）截至本轮读取时均只有 prompt 头、尚无正文，无可交叉条目；顶层两份为主持裁对抗纪要，其已锁项（None 止损短接、14:50 时钟、reason 前缀、SMA 预载、池函数禁回落、市场层叶子、实施序）我逐条对代码复核属实，不再重打。以下为独立完成的综合裁决评审。

---

# 评审：plan-unify-csv-strategies-1-8-2026-09-12.md（v1.1）

**评审侧重**：综合裁决 + 跨文档交叉验证（内部自洽、跨节引用、SSOT 衔接、对代码事实断言逐条取证）。
**取证范围**：`csv_daily_backtest.py`、`csv_minute_backtest.py`、`csv_minute_backtest_v7.py`、`csv_strategy_books.py`、`csv_pool.py`、`strategy6/8_rules.py`、`ma_chip_edge_backtest.py`、`backtest_main_full.py`、`chip_indicator.py`、README/AGENTS/docs README、SSOT、相关测试。

## 🔴 必须修

### R1｜策略 4 的 MA5 卖在锁定钩子面上**无法实现**——卖槽缺 `(code, day)` 上下文

- plan:87（U-R7）：「卖：现价 < **截至昨收** SMA5 → `ma_signal:MA5`（走卖槽…）」；plan:142-144（§4）：`take_profit(px, cost, peak, n_days)` 「4 的 MA5 卖…看不见 hm」。
- 但「截至昨收 SMA5」是 **(code, day) 的函数**，而两个引擎的卖槽调用点都不传 code/day：
  - `backtest/research/csv_daily_backtest.py:450`
    ```python
    reason = take_profit(close, pos.cost, pos.peak, n_days)
    ```
  - `backtest/research/csv_minute_backtest.py:438`（scan_held_day 内，同样只有 4 参）
- U-R26 只定义了**买侧** `buy_gate(code, px, day, daily_closes_ending_yesterday)`；§3 落点两行（plan:126-127）也未给策略 4 的卖侧接线任何引擎改动授权。书是纯函数（plan:124「新建纯函数」），`apply_csv_strategy`（csv_strategy_books.py:68-79）也不接收 bars/day。**程序员照锁编码，切片 D 必卡死或被迫私自改引擎热路径**——这正是 U-R2 想防的事。
- **修法（建议进 v1.2 再开一轮 🔴 清空）**：镜像买侧，加可选卖槽 `sell_gate(code, px, day, daily_closes_ending_yesterday) -> Optional[str]`（书缺省 None 恒过，6/8 热路径不变）；或明确授权 scan_held_day/日线循环为书 4 扩参。U-R2 的「6/8 热路径保持」措辞可原样保留。

## 🟡 应修

### Y1｜策略 3 日线「开板→跌停收盘 defer」的**次日语义未定义**（U-R19/U-R20）

- plan:81：「reserved 且收盘开板 → 当日收盘卖，但 `hit_limit_down(close)` → 不成交、defer」。open_board 明确「不走 pending_exit」（plan:80），那 defer 之后第二天走什么路径：重试 open_board？落回止损/止盈正常评估？`reserved` 是否清掉？均未写。天地板（开盘涨停、收盘跌停）极罕见但 A 股真实存在，实现者会各写各的。建议补一行：「defer 次日起回到当日正常评估（重算 reserved），open_board 不跨日重试」。

### Y2｜14:50 强制卖的**跌停禁卖守卫未指定落点**（U-R8/U-R18）

- 分钟引擎现有守卫是「分钟 open 触跌停→整分钟跳过」：
  - `backtest/research/csv_minute_backtest.py:428`
    ```python
    if limit_down > 0 and hit_limit_down(px_open, limit_down):
        continue
    ```
- 14:50 分支若写在该检查之前，就能把封死跌停的收盘价卖进账本（违反 U-R1「跌停禁卖」）；若同分钟 open 正常但 close==跌停价，同样应 defer。需在 U-R8 补：force 分支置于 open-跌停跳过之后，且 `hit_limit_down(px_close)` 时 defer 计数、不成交。（顺带声明：现有 `stop_loss:touch` 在 close==跌停价仍成交是 6/8 已知乐观失真，本轮不改，建议入 §7。）

### Y3｜策略 4 在**分钟引擎**的 11 交易日预载没进 §3 落点

- U-R21（plan:88）只说「策略 4 的 `run()` 股票日线预载 ≥10 交易日（实现 11）」，未区分引擎。分钟引擎 `run()` 的日线加载沿用**日历减法** warmup：
  - `backtest/research/csv_minute_backtest.py:725`（`load_start = warmup_start(start)` → `csv_daily_backtest.py:216-217`，`pd.Timedelta(days=10)` ≈ 6-7 个交易日）
- 若 `--strategy version4` 可跑分钟引擎（书对两引擎通用），开头两周 `skip_sma_warmup` 会大面积误伤。§3 的 csv_minute_backtest.py 行必须补「4 的日线预载同改 11 交易日」，或显式锁 version4 仅日线。

### Y4｜689（科创板 CDR）跌出 `limit_pct` 表与「不建模」声明两头

- `backtest/research/ma_chip_edge_backtest.py:92-96`：`300/301/688 → 0.20，否则 0.10`。689（如 689009）真实涨跌幅是 20%，现表给 0.10。U-R12 只声明「不建模北交/ST；验收宇宙禁 BJ/ST」——689 既非北交也非 ST。验收宇宙排除清单应加 689，或注明归 688 档（另开议题）。

### Y5｜`--stop-pct` 与无止损书（version4/5）同传时的行为未定义

- 比例参数是共享 CLI：`csv_strategy_books.py:104-111`（`add_strategy6_ratio_args` 给两引擎 argparse 都加 `--stop-pct`）。plan:125 只锁「1–5 的 run_kwargs 不得走 `strategy6_kwargs_from_args`」。用户传 `--strategy version4 --stop-pct 0.05` 是静默忽略还是 fail-closed 拒绝？按本仓「不静默回退」的一贯风格（test_csv_strategy_books.py:37 命名即此意），应锁：**None 止损书收到显式 `--stop-pct` → SystemExit**。

### Y6｜U-R22 新桶未命名，summarize 卖出行未跟

- 现状三桶把一切非 stop/trail 塞进 `sell_pos_trail`：`csv_daily_backtest.py:682-687`。U-R22（plan:73）只说「`profit_take*` 单独桶；`open_board`/`force_sell*`/`ma_signal*` 不得计入 `sell_pos_trail`」——后三者各建桶还是共桶？`summarize` 卖出行（csv_daily_backtest.py:747）怎么展示？各给名字（如 `sell_open_board` / `sell_force` / `sell_ma`），否则切片 A 的「统计桶」完成定义无法断言。

## 🟢 可选

- **G1** register 插入序陷阱：`csv_strategy_names()` 返回 `tuple(BOOKS)`（csv_strategy_books.py:40-41）按**注册插入序**；切片 B/B′/C/D 逐个插入 register 调用必须落在源码正确位置（v5 先于 v6 插、v3 再插到 v5 前），不是追加。验收串（plan:184）会立刻抓错，但建议在 U-R23 写一句「源码位置按字典序插入」。
- **G2** 化石门应放在 `backtest_main_full.py` 的 backtrader 重导入**之前**（现 line 16-23 模块顶层 `import backtrader`），否则「非 0 退出」仍要付整个 import 代价。
- **G3** §6 验收串建议补 `test_csv_daily_backtest_v8.py`、`test_csv_minute_backtest_v8.py`、`test_ma_chip_edge_strategy.py`（limit_pct 再导出回归）。
- **G4** 两套 `_limit_prices` 并存（日线 Decimal 直乘 vs v7 `round_fen` 浮点乘后 HALF_UP，v7:217-219）：极边缘浮点误差可差 1 分。本轮「只搬家」保持各自不动是对的，建议在 market_layer 文档写明「刻意不统一」。
- **G5** 追买走 `buy_gate` 时，closes 窗口相对信号日**右移一天**（追买日的「截至昨收」含信号日收盘）——语义合理但与信号日 gate 不对称，HELP_LOCK 提一句免得后人当 bug 修。

## ✅ 做对的地方（代码逐条核实）

- **§9.1.2 行号引用全部准确**：`csv_daily_backtest.py:430`（`trigger = pos.cost * (1.0 - stop_pct)`）、`csv_minute_backtest.py:413`（同式）、`:433`（`ret <= -stop_pct`）——None 止损确会 TypeError，先短接后 register 的 U-R23/U-R3 成立。
- **U-R9 属实**：`load_pool_days` 已有 `pool_dir` 形参（csv_daily:288-292）但 `run()` 未传（csv_daily:562、csv_minute:720）且 CLI 无 `--pool-dir`——「只接线」判断准确。
- **U-R12 表核对无误**（ma_chip:92-96）；且 U-R17 有据：strategy8 本就 `PEAK_GAP_MIN = 0`（strategy8_rules.py:15），只有 6 是 15。
- **U-R10/U-R24 对 7 的行为描述属实**：`--pool-dir` 必填（v7:498-500）、空 CSV 仍进 map（v7:463）、`if pools` 才走指数日历否则日期区间（v7:506-509）——空文件分叉足以保住 7 的日历契约（主持裁问题 3：是）。
- **U-R15 名单契约与 `csv_pool.py` 现实现一致**（utf-8-sig/可表头/裸六位，:17-56）；6/8 空名单日落出 map（`if codes:`，csv_daily:302）与「缺日=不买」一致。
- **T+1 / 未来 bar / 复权三盲区干净**：`n_days=0` 两引擎均不卖不挂 pending（csv_daily:429-450；csv_minute:419）；peak 用当日 high 在收盘评估**之前**更新、买入用当根 close、prev_close 严格取 `index < day`——无未来 bar；成交与净值全程 `dividend_type=none`（csv_daily:340、csv_minute:323）。
- **盈筹盲区满足**：`cyqk` 确为 0–1 获利比例（chip_indicator.py:49），plan:47 明令 1–5 书/市场层禁入 chip——无夹带。
- **U-R21 的「11」有先例**：v7 指数门预载正是 11 个交易日（v7:419-421）。
- **U-R8 与切片 B′ 自洽**（主持裁问题 1）：分钟 14:50 时钟 / 日线只 +2% pending、无每日 force，v1 的「15:00=已过 14:50」撤回正确——否则每个可卖收盘都 force，+2% 永不当选。B′ 完成定义双轨（分钟测 14:50、日线测次日开）无矛盾。
- **U-R19 不动 6/8 pending 路径**（主持裁问题 2）：第三成交钟是书 3 专属分支，pending_exit 语义（csv_daily:422-427）不被触碰，切片 C 含 6/8 pending 回归项。
- **scan_held_day 扩签名可回归**（主持裁问题 4）：新参数全部带默认值（reserved/limit_up/force_hm 缺省关闭），6/8 调用点零改动，切片 A 的「6/8/7 旧单测绿」即回归门。
- **包边界干净**：所有落点在 `backtest/research/`；`presets.py` 不动；无 LEBS/MockQMT 搬运；Cerebro 只加门（U-R13 对象 `backtest_main_full.py` 确为 Cerebro 入口，line 16-20）。
- **实施序 U-R23/U-R28 是本轮最大结构性优点**：引擎→register→names 元组→文档，配 `test_csv_strategy_books.py:21` 现存 names 断言作每切片锚点，避免不可逆巨型 commit。

## 总评

**方向正确、事实底子罕见地扎实**——v1.1 绝大多数可验证断言（行号、函数、行为）与代码逐条相符，对抗回填质量高；但 **U-R7 的策略 4 卖槽缺 `(code, day)` 上下文是唯一的真阻断**（R1），照锁编码切片 D 必然卡死或逼出私自改热路径。**裁：R1（+Y1/Y2 各补一句）回填 v1.2 后可进实现；切片 A/B/B′/C 不受 R1 影响，可在回填期间先行启动。**
