<!-- agent=codex cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.02-c22c1a3\node.EXE C:\Users\Thinkpad\AppData\Roaming\nvm\v24.19.0\node_modules\@openai\codex\bin\codex.js exec --ephemeral 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07-r2/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本仓是 **Cerebro / path-SSOT 只读回测叉**：无实盘、无 QMT 下载、无 Redis 流。把握不准可读代码或做实验，以事实为准。

【本仓必查盲区（评审必须逐条核对）】
- **T+1 / 隔日成交**：买入信号能否在当日卖出？卖出是收盘价还是次日开盘？有无用到未来 bar？
- **复权口径**：均线与盈筹率是否同一套 `adjust_type`（本仓筹码默认 front）？
- **盈筹率尺度**：`cyqk_c` 是 0–1 还是 0–100？70% 阈值有无单位错误？
- **周均线定义**：20 周均线是周线 resample 后 SMA(20)，还是 100 日近似？
- **包边界**：算法走 `oskh_factors` / `qlib_cost`，Cerebro 包装走 `backtest/`，研究 CLI 走 `backtest/research/`。

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
评审完成。以下为评审意见本体（只读取证，未写任何文件）。

范围说明：已通读待评审 plan 全文，并对实现态做了代码级交叉验证——`backtest/research/ma_chip_edge_backtest.py` 与 `tests/test_ma_chip_edge_strategy.py` 已在提交 e9204ab 中存在；另核对 backtrader 安装版源码事件序、`oskh_factors.chip`/`qlib_cost/cyq.py`/`common/infra/data_root.py`、reader 契约，并在 F 盘做了只读数据探针。`r2/_parallel/` 下 claude/codex/cursor 各文件截至评审时仅含提示词 stub（无已完成意见），故本次为独立评审，无交叉引用编号。

## ✅ 做对且经代码/数据验证

1. **成交时序设计成立**。`Cerebro(cheat_on_open=True)` 时事件序为 `next_open → broker 撮合 → next`（[cerebro.py](D:/anaconda3/envs/vanna312/Lib/site-packages/backtrader/cerebro.py:1620) 起；`nextstart_open` 默认转调 `next_open`，[strategy.py](D:/anaconda3/envs/vanna312/Lib/site-packages/backtrader/strategy.py:277)）。单测已实证「edge→次日开盘 BUY@10.5、再次日开盘 SELL@8.5、买入日不卖」（tests/test_ma_chip_edge_strategy.py `test_edge_buys_next_open_and_first_day_down_sells_next_open`），「仅 `broker.set_coo` 不够」属实（无 cheat 标志时 cerebro 不调 `_next_open`）。
2. **盈筹率尺度正确**：`get_cyqk_c → get_winner`，内部以 `cumpdf.sum()` 归一化（[cyq.py](qlib_cost/cyq.py:229)），0–1，阈值 0.70 无单位错误。且实现绕开 `ChipDistribution.cyqk_c[0]` 的理由成立：该 Indicator 窗口取 `range(-period,0)`（不含当日，[chip_indicator.py](backtest/chip_indicator.py:131)），且其股本无 as-of。
3. **复权/单位口径一致**：日线锁定 front；实测 000001.SZ 2024 年日均换手按 volume(手)×100÷FloatVolume ≈ 0.73%（现实量级），证明 `_estimate_turnover` 的 ×100 假设与 hive 数据契约吻合（[shares.py](oskh_factors/chip/shares.py:170)）；且 `free_float_shares.parquet` 的 `circulating_capital` 与 `float_shares.parquet` 的 `FloatVolume` 同值（000001.SZ 均 1.94056e10），实现选用的股本口径与 SSOT 一致。
4. **包边界干净**：算法 SSOT 在 `oskh_factors.chip` / `qlib_cost`，`backtest/chip_algorithm.py` 仅 re-export（其 docstring 明示不改算法），CLI+Strategy 在 `backtest/research/`，未触碰 rolling/backtest_main。
5. **T+1/隔日成交因果链**：`cond/edge/sma` 均为逐行因果预计算，`next(D)` 收盘后置 `pending_buy`，`next_open(D+1)` 看当日 open 决定 skip 或下单；卖出同样一律下一根开盘。计划 §2 的表述与 [ma_chip_edge_backtest.py](backtest/research/ma_chip_edge_backtest.py:367) 一致。
6. **20 周均线实现是周线 resample + SMA(20)**（[ma_chip_edge_backtest.py](backtest/research/ma_chip_edge_backtest.py:100)），非 100 日近似；周 asof 只 backward 到 D，与计划锁定口径一致。
7. **数据/抽样可行性已证实**：front hive 5585 symbols；三板块候选池 sh_main 1705 / sz_main 1495 / chinext 1398，30 只抽样可行；股本历史 2001→2026-05 覆盖统计窗。
8. skip_sell 重试、统计窗前 edge 抹平（保留最后一日供窗内首日买入）等计划承诺行为已由单测覆盖（如 `test_skip_sell_retries_next_session`）。

## 🔴 必须修

**R1. 买入日「收阳但收盘 < SMA5」分支未定义，代码行为与 plan 字面差一天。**
plan §2 与 §4 的语义是「持有期任一日 H：close < sma5 → pending_sell → 次日开盘卖」（plan:20、77），买入日本身未排除；但代码在 `next()` 中 `hold_mode=='first_day'` 分支先比 `c<=buy_ref_close`，否则仅置 `hold_mode='ma5'`，同日的 `elif hold_mode=='ma5'` 分支不再执行（[ma_chip_edge_backtest.py](backtest/research/ma_chip_edge_backtest.py:403)）。故当买入日收盘高于前收但低于 SMA5（可构造：前四日 12/11.5/11.2/10.9，T 收 11.1，SMA5≈11.34）时，字面口径应在 T+1 开盘卖，实际要等 T+1 收盘再确认、T+2 开盘才卖。现有单测只覆盖「收阴/收平」与「收阳后某日跌破 SMA5」，无此组合。请裁定口径（A：买入日收盘也计入 H → 代码需改；B：评估自 T+1 起 → plan §2/§4 需明示例外并写清），并补对应单测。此条不修会让「等号 fail-closed」以外的离场时点存在两种互相矛盾的读法。

**R2. 计划 §2「对窗口调 `chip_algorithm`/`oskh_factors.chip`，`as_of_date=D`」缺真实 API 契约，照文编码会卡住。**
仓内不存在带 `as_of_date` 的顶层 chip 入口：as-of 参数只在 `adapt_columns(..., as_of_date)`（[core.py](oskh_factors/chip/core.py:28)）上，整窗便捷入口是 `compute_chip_factors`，它自动取末行日期为 as_of（[core.py](oskh_factors/chip/core.py:294)）。计划应固定为：每 D 取「含 D 的 80 行切片 → 预置 turnover_rate=volume×100/fs_asof(D) → `daily_chip_distribution(adapt_columns(...))` → `cyq.ChipFactor(close[D], dist).get_cyqk_c()`」，并注明 volume 单位是手（×100）与股本列 `circulating_capital`。否则实现者要么找不到入口、要么误用 `ChipDistribution`，要么复用私有的 `_load_*`（现状实现即直连 3 个下划线私有函数，[ma_chip_edge_backtest.py](backtest/research/ma_chip_edge_backtest.py:26)）。建议把该调用链提升为 `oskh_factors.chip` 的公共函数（如 `cyqk_series_asof`），研究层不再触碰私有符号。

## 🟡 应修

**Y1. 「未完成周丢弃」在序列末端不成立（plan:32 vs 代码）。**
`week_ma20_asof` 用整段 resample，若数据止于周三/周四，末根（未完成）周 bar 的 `_last_day`=该日且 ≤D，会被计入 asof MA；单测 `test_week_ma_asof_does_not_use_unfinished_week` 之所以通过，是因为夹具在后面又放了未来的周五（tests/test_ma_chip_edge_strategy.py），真实回测序列末端没有未来 bar。实测影响仅限最后一个可决策日（其后无 bar 可买入，P&L≈0），但 plan 表述与实现不符；建议补「序列止于周三」的夹具或把表述改成「中间未完成周丢弃、末周按已有日参与」，避免后续改 `--end`/回放窗口时埋雷。

**Y2. 计划承诺的单测清单（plan:72-80）大部分未按原意落地。**
已实现测试多用手工 `edge` 列驱动策略，真正走 `build_signal_frame` 的用例在无 F 盘时直接 `pytest.skip`（`test_edge_requires_finite_prev_and_false_prev`）；「D 与 D-1 都满足→不买」「D-1 为 NaN→不买」「买入日收阳+SMA5 离场」「skip_buy 消耗信号」均无真实 cond 级用例。由于 `cond/edge/cyqk` 是整条信号链的核心，建议注入假股本/假量价构造纯合成 cond（计划本身要求不依赖 F 盘，但需 mock `oskh_factors.chip.shares` 加载）。

**Y3. 全程换手用「D 日 asof 股本」是计划锁定的近似，但对含解禁/送转的 80 日窗有系统性偏差。**
现状每个窗口只取一个 `fs = shares[i]` 套用到整窗（[ma_chip_edge_backtest.py](backtest/research/ma_chip_edge_backtest.py:185)）。而代码已预计算每日 asof 序列 `shares_asof_series`（同文件:131），逐 bar 用 `shares[j]` 估当日换手几乎零额外 IO、显著更准；至少应在 plan §2/§3.3 记录该近似及量级（解禁日前后低估历史换手 → 筹码衰减偏慢），而非默认无偏。

**Y4. 统计口径易误读：`mean_single_name_return`/`median` 对「从未触发买入」的名字按 0% 计入。**
实现对所有 `stat_rows`（含 n_buys=0）取均值（[ma_chip_edge_backtest.py](backtest/research/ma_chip_edge_backtest.py:544)），若 30 只中大量不触发，mean≈0 会掩盖触发样本表现。plan:48 只单列 `names_with_buy`，未定义分母。建议同时输出「触发样本均值/中位」或在 summary 明示分母为全部抽样（并把触发率作为第一眼指标）。

**Y5. 统计窗边界对长假/长停牌不稳健。**
`feed` 从 `stats_start - 14 个自然日` 起截（[ma_chip_edge_backtest.py](backtest/research/ma_chip_edge_backtest.py:492)），若个股窗前最后交易日早于此（长假跨 15+ 天或个股停牌），`mask_pre_window_edges` 保留的「最后一根窗前 edge」会被截掉，窗内首日买入静默丢失。多数 A 股长假 ≤14 天不受影响，但建议用「窗前最后一个交易日」反推 feed 起点，而非固定 14 天。

## 🟢 可选

- **数据鲜度**：free_float 历史全表止于 2026-05-30，且个股粒度更早（000001.SZ 最后记录 2025-06-30）；`shares_asof_series` 无 >90 天 gap 告警（同文件:131 静默 merge_asof），建议复用 `_get_float_shares` 的 gap 日志并考虑把 `float_shares.parquet` 快照作为末端 forward-fill。
- **复现性**：`--end` 默认 `date.today()`，输出目录随运行日变化（plan:44、47）；「同一 seed 的 universe.csv 可复现」只在同日成立，建议示例命令显式带 `--end` 并落盘生成参数。
- **撮合近似**：无 filler 的 Market 单在「开盘未封板但立即涨停/跌停」的巨幅跳空日会全额成交；涨跌停价按 Python `round`（银行家舍入）而非交易所四舍五入。当前 ±0.01 容差基本覆盖，但建议在 summary 中把撮合假设（含 filler=None）写全。
- **边界股**：`689009.SH`（CDR）不在 `688` 排除内且被 10% 阈值覆盖（实际为科创板 20% 档）；全池仅个位数，影响可忽略，值得一行注释。

## 总评

该 plan 已把 T+1 因果、front 口径、cyqk 0–1、周线 asof、skip FSM 等最容易亏大钱/前视的点锁得基本正确，且实现与单测已落地、核心契约经代码与 F 盘数据验证成立；**可进实现/维持现状**，但需先裁定并补测 R1 的买入日离场分支、把 R2 的 chip 调用链固化为公共 API 契约，随后将 Y1–Y4 吸收进 r3 修订——其中 Y2 意味着「单测不依赖 F 盘」的承诺目前只在手工 edge 层面兑现，cond 级合成测试仍是空白。
