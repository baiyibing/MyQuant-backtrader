<!-- agent=grok cmd-prefix=/home/box/.local/bin/grok -p 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

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

【你的评审侧重】优先**实现 / 协议 / Linux-VM CLI**：核对实现是否可落地、协议/契约用词是否越界、Linux 侧 CLI 与编排是否可 headless 跑通。 --permission-mode bypassPermissions --always-approve <prompt> -->
先读设计稿全文，再对照仓内代码与协议取证；本轮只出评审意见，不改任何文件。设计稿已读完。接下来对照实现锚点、CLI/验收脚本和仓内协议，并顺带看一眼并行评审目录里是否已有完整意见。并行评审尚未完成，先独立取证：核对事件门、k 方向、缩放顺序、入口跳过与 Linux 验收命令。其他评审已有完整条目。正在交叉核对，并补上 CLI/入口接线与函数名方面的独立取证。# 评审：P3 δ2 ex-div 契约计划 v0.2（实现 / 协议 / Linux-VM CLI）

对照 `IMPLEMENTATION_BASE=1ad010cca013afe8186f20275cbdcca71e500823`（确为 PR #121 merge；HEAD `796b235` 为其后代）。基线后 tracked 仅本 plan + `plan-industry-align-p3-d2-exdiv-codex-adv-r1/`，冻结 15 文件 `git diff --exit-code` 为零。本刀无新增 timeout/budget/并发锁；**无对应时限实验**（N/A）。`qlib_bin_*` 的 `ThreadPoolExecutor` 不在本刀改动面——B6 必须 stub 掉读取器，避免踩 `__exit__→shutdown(wait=True)`。

并行目录 **codex / cursor-auto / kimi 已完成**。其 🔴 API 名、双路径 resolver、B6 stub、B5/v7 股数、pending×除权 均经源码独立复核，下文引用编号；不重复其实验原文。

亲自复现（`python3 -c`，无写盘）：`hasattr(em,"load_exdiv_rates") is False`；`limit_prices("600000.SH", 1.65)=(1.82, 1.49)`；`300001.SZ→(1.98,1.32)`；`*ST→(1.73,1.57)`；`1.65*0.9` 浮点 `round_fen=1.48`；`k_for(inf)→inf`（仅排 `<=0`/NaN）。

---

## 🔴 必须修

### R1｜验收链 API 名写错：`load_exdiv_rates` 不存在（同意 codex R1 / cursor-auto R1 / kimi K-R1）

`plan:66`、`:185` 写「经真实 `load_exdiv_rates`」。仓内只有 `load_exdiv_ratios`（`exdiv_map.py:220`，`__all__:349`；daily/minute/`load_limit_context` 调用点全是 ratios）。adv-r1 errata 原文用对名，v0.2 回填笔误。照此实现直接 `ImportError`。改为 `load_exdiv_ratios`，**不要**加兼容别名。

---

## 🟡 应修（落地 / 协议 / headless CLI）

### Y1｜B1「绝不走真实 resolver」须钉死双路径（同意 cursor-auto R2 / kimi K-Y1）

`exdiv_map.py:246-253` 中 `adj_factor_path` 与 `ex_date_index_path` **各自**回落 `resolve_source_parquet`。只传一个：已配湖则静默读真实 parquet；未配则 `UnconfiguredDataRootError`（`data_root.py:275-299`，解析阶段不在后续 try 内——plan:82 这句是对的）。B1/B2 必须写成：

`load_exdiv_ratios(..., adj_factor_path=..., ex_date_index_path=...)` 两路径皆显式 tmp_path。

### Y2｜B6 入口/stub 不够跑 headless（同意并补 CLI 写面；codex R2 / cursor-auto Y2 / kimi K-Y3）

`plan:189` 把 daily「artifact writer」写进 `run()` 隔离清单，但：

- 书 daily/minute **`run()` 只 return `SimState`**（`csv_daily_backtest.py:633-635`、`csv_minute_backtest.py:929`）；`write_run_artifacts` 在 **`main()`**（daily `:721`、minute `:998`）。误测 `main()` 会写 `backtest_output/`，且已存在目录直接 `SystemExit: refuse overwrite`。
- 书 minute `run(use_cache=True)` 默认（`:793`）；不 stub `load_minute_bars` / `_load_minute_compact` 可能写窗口 cache。
- v7 **没有 `run()`**，入口是 `main()`（`:547`）；非空 pool 必调 `load_index_daily`（`:577-579`）再 `write_run_artifacts`（`:586-588`）。
- 整 stub `load_limit_context` 绕过「确实加载 map」；空 `codes` 时 `ashare_session.py:99` 根本不调 loader。

B6 应给**逐入口 patch 消费模块绑定名**：daily `run` → `load_pool_day_map` / `load_daily_ohlc` / `load_exdiv_ratios` / `simulate`；minute `run(..., use_cache=False)` → 分源 stub `_load_minute_compact` vs `load_minute_bars`；v7 测 `main(argv)` 时必须 stub `_load_cli_bars`（或 `bars_from_pool`）、`load_index_daily`、writer，并保留 `load_limit_context` 调用、只替换其内部读入。禁止打到真实湖 / qlib `ThreadPoolExecutor`。

### Y3｜B4 半分 oracle 必须钉主板代码，禁止 float 旁路（实验）

`plan:187` 写 `3.30×0.5→1.65→(1.82,1.49)` 未钉 `code`。同 1.65：

| 代码 | 结果 |
|---|---|
| `600000.SH` | `(1.82, 1.49)` |
| `300001.SZ` | `(1.98, 1.32)` |
| `*ST` | `(1.73, 1.57)` |
| `round_fen(1.65*0.9)` | **1.48** ≠ 1.49 |

B4 写死 `session_prev_close` 返回值送入 `session_limit_prices("600000.SH", mapped)`（或 `limit_prices`）；期望值只允许来自该调用。`test_ashare_session.py:21-33` 算出 mapped=9.5 却把 **raw** 送档位——计划标证据缺口正确，补链时不要再犯。

另：书 `book_limit_prices` 在 `qlib_limit_pct is not None` 时走 float `p*(1±pct)`、不分（`csv_common.py:66-81`，v9/v10 hook）。B2/B4 step 涨停向量应钉 **默认书**（`qlib_limit_pct=None` → Decimal），不要拿 topk 书当档位 oracle。

### Y4｜Linux CLI 危险组合：分钟 `--qlib-day-root` 不会跳过 map（协议，不改生产）

日线 `run()`：`use_qlib_bins or dividend_type!="none"` → `exdiv=None`（`csv_daily_backtest.py:585-588`）；`--qlib-data-root` 即跳过。分钟 `run()` **无条件** `load_exdiv_ratios`（`:883`）；`--qlib-day-root` 还迫使 `daily_source="qlib_day"`（`:968`）。`qlib_day` dump 后复权（`qlib_bin_daily.py:6`），`qlib_1min` 为 none（`qlib_bin_1min.py:4`）。对已连续域昨收再乘 k → 档位/止损距错位。

同意 cursor-auto Y1 / kimi K-Y2 的风险定性；**不同意本刀把 P3δ2.5 从 A 改成生产 fail-closed**（与 F-R2/F-R5、host「不强制重开 B/C」冲突）。人裁维持 A 时，B6 必须把 `daily=qlib_day` × 仍加载 map 标为**危险组合必测**（期望=仍加载，不是「已安全」），并在未来 Slice A 的 CLI help / `docs/backtest/README.md` 写红字：日线 `--qlib-data-root` 跳过 ≠ 分钟 `--qlib-day-root` 跳过。真要入口拒绝，走 P3δ2.5=B 另案。

### Y5｜§8.2 解释器链与 3.12 断言打架（Linux headless）

```230:233:docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md
P3_D2_PYTHON="${OSKH_MERGE_PYTHON:-${VANNA312_PYTHON:-${VANNA311_PYTHON:-}}}"
: "${P3_D2_PYTHON:?Set OSKH_MERGE_PYTHON to the controlled Python 3.12 executable}"
```

AGENTS 允许 `VANNA311` 兜底，下一行却 `assert sys.version_info[:2]==(3,12)`。仅设 3.11 时：可执行、断言红、错误信息还怪 `OSKH_MERGE_PYTHON`。建议：链只留 `OSKH_MERGE_PYTHON`/`VANNA312_PYTHON`；缺则 fail 并打印「需要 3.12 可执行文件」。gates 路径与 CI 一致即可；**不必**宣称逐步顺序同构（gates 在 CI 里 pip 之前，四脚本不依赖 pandas）。kimi 对 cursor-auto Y6 的降级成立，不升 🔴。

### Y6｜B5 小数值 oracle 不能当 v7 公开初态（同意 codex R3 / kimi K-Y4）

`simulate_v7` 无 Position 注入；试仓 `NAME_BUDGET×0.2`，px=10 → 20,000 股，cash=2000 会 `skip_cash`。分层：书 helper/`simulate` 用 §2.4 的 100 股；公开 v7 用事件前快照比 Δ。

### Y7｜缺 pending_exit × 除权日公开日线 pin（同意 codex R4 / kimi K-Y5）

`csv_daily_backtest.py:333-338`：pending 用**当日 raw open** + **已映射**跌停门，且优先于重评。字段未改 ≠ 成交顺序正确。补：D−1 写 pending → D 除权正常开盘成交 / 开盘跌停续 defer；断言 reason、raw 开盘价、原股数。

---

## 🟢 可选

- §9 增列 `qlib_bin_daily.py` / `qlib_bin_1min.py`（域约定 SSOT；全路径审计已能兜底）。
- Non-goals 显式排除盈筹/`cyqk`（仓内无 `backtest/chip_indicator.py`）。
- Slice A 把 `engine-ashare-correctness.md` E-R6「仅 `run()` 加载」改成 daily 连续域跳过 vs minute/v7 始终加载。
- B1 可选 pin：手工 `k=inf` 穿过 `k_for`（loader `isfinite` 不产 inf）——plan:64 措辞已精确，钉住防「顺手修」。
- 本轮 `_parallel/` 若入库，扩 §8.3 白名单；否则保持 untracked。

---

## ✅ 做对的地方（保留）

- docs-only、零生产 diff、经济残留 deferred、不 redo E-R6；五项人裁默认 A 且 **未冒充 GO**。
- 事件门四格、`k=prev_cum/cum`、`j<=5e-3` 等号不修正、无 ex 须 `j>1e-2`、helper 非幂等「一次性」——与 `exdiv_map.py:28-30,294-316`、`csv_ledger.py:147-156` 及三引擎扫描前缩放顺序一致。
- 书 cost/peak only vs v7 `entry_A/avg_cost/peak/Lot.price`（`add1_A1` 仅 helper；公开路径从不赋值）分叉清楚。
- E-d2-01/02/06/08 证据限度、`qlib_day`≠`qlib_1min`、resolver 失败 vs 缺文件空 map 降级，均与代码相符。
- F-R8/§8.2 禁止湖/CLI 回测；§8.1 SHA 钉死 + perl UTF-8/BOM/NUL；本 VM `/usr/bin/perl` 存在，headless 静态核可跑。
- F-R10 不混 LEBS/Cerebro/Mode A/B；import fence 不扩 rglob。

---

## 必查盲区

| 盲区 | 结论 |
|---|---|
| T+1 | 买日不可卖：`t1_sellable`（`ashare_session.py:39-41`）；分钟扫描器另有 `n_days<1` 不更新峰（`csv_minute_backtest.py:276-277`）；v7 按 lot 买日过滤（`:229-241`）。日线普通止盈→`pending_exit` 次日 **open**；`same_bar` 仍当日 close（`:404-407`）。无未来 bar（昨收 `closes[:pos]`）。见 Y7。 |
| 复权 | 默认 none；未把筹码 front 套进 CSV 书。混域活风险见 Y4（文档/B6，不改生产）。 |
| 盈筹 | 本刀未引入；`backtest/chip_indicator.py` 不存在。 |
| 涨跌停/停牌 | E-R2：主板 10 / 创科 20 / 北交 30 / ST 5 / 未知 `None`；涨停禁买、跌停禁卖。缺 bar 在缩放前 `continue`，无跨停牌补队列——已如实披露。v7 `limits=None` 持仓侧 fail-open 属 δ4，本刀冻结。 |
| 包边界 | 全程 `backtest/research/`；无 LEBS/`presets`/Cerebro 复活。 |

---

## 同行交叉

- **同意**：codex R1–R4；cursor-auto R1/R2、Y2–Y4；kimi K-R1、K-Y1/Y3–Y5。Decimal 1.48≠1.49、inf 穿透、§2.4 书侧 oracle 以本次 `python3 -c` 与 kimi Exp2/4/5 一致。
- **部分不同意 cursor-auto Y1 / kimi K-Y2 的处置**：混域是真风险，但本刀 F-R5 冻结「不补 minute/v7 跳过」；一次到位应落在 **B6 危险组合 + CLI 红字**，不要顺手改生产。
- **同意 kimi 对 cursor-auto Y6 的降级**：CI 行锚大体对，顺序差无功能影响。
- 独有增量：Y2 `run()` vs `main()` 写盘/`use_cache`；Y3 板块分叉实验；Y5 解释器链；Y4 CLI 开关不对称。

**总评**：as-built 契约质量高，锚点与冻结纪律可落地；唯一硬伤是 `load_exdiv_rates` 笔误。**改 R1，并把 Y1/Y2 写进 Slice B 合同后，人裁 GO 可进 docs + data-free tests；本 PR 仍是 docs-only，不可改生产、不可宣称经济守恒已闭合。**
