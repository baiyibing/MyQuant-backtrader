# Plan：NP3 引擎分层倒置修复（双入口 + 单共享核；纯机械重构）

> **落盘**：2026-09-16。**v1.2**（2026-09-16 人裁 GO P1–P4 全采纳，见 changelog §10）。
> **状态**：✅ **已实施并合入**（PR [#78](https://github.com/baiyibing/MyQuant-backtrader/pull/78) / merge `71f0f3f`，2026-09-16；切片 A→D + nit 全部完成；Grok 核 [GO-WITH-NITS](../../../architecture/reviews/2026-09-16/pr-78-np3-engine-layering/grok-review.md)（nit 已于 `2951fca` 修）；zcode 宿主预合入 PASS：D-smoke daily+minute `trades.csv` 逐字节一致、N-R6=0、结构性锁 OK。计划评审记录：[zcode-facts](../../../architecture/reviews/2026-09-16/plan-np3-engine-layering/zcode-facts.md) / [zcode-arch](../../../architecture/reviews/2026-09-16/plan-np3-engine-layering/zcode-arch.md) / [merge-consensus](../../../architecture/reviews/2026-09-16/plan-np3-engine-layering/merge-consensus.md)）。
> **风险档**：**L1**（纯搬移重构；零行为变更；byte-identical golden + 补充单测兜底）。
> **工作流**：走 [Codex 交接工作流](../../workflow-codex-handoff.md)。
> **上游**：[strategic-analysis-opus5-next-2026-09-16.md](../../strategic-analysis-opus5-next-2026-09-16.md) §6 NP3；人裁方向（2026-09-16）：「**双入口 + 单共享核**，不是单引擎；不做 big-bang 卖环合并（G 禁区仍在）」。
> **成交核现锁**：[engine-ashare-correctness.md](../../engine-ashare-correctness.md)（E-R1–E-R5；本轮不动任何语义）。
> **实施交接**：[handoff-np3-engine-layering-codex-impl-2026-09-16.md](../../handoff-np3-engine-layering-codex-impl-2026-09-16.md)（人裁 GO 2026-09-16 后生效）。

---

## 0. 一句话

把 `csv_minute_backtest.py:33-75` 从 `csv_daily_backtest` import 的 **41 个符号**按真身归属下沉/改指：29 个直接改指既有模块，10 个（含伴生）抽入两个新共享模块（`csv_artifacts.py` 6 符号 / `csv_daily_loader.py` 4 符号 + `_PERIOD_ENV_KEYS`），常量归位（3 进 csv_common、MINUTE_LAKE_END 留 minute 自用、`_progress` 进 csv_common）——**两条 `simulate()` 与两套卖环原地不动**，diff 零行为变更。

```text
今天：minute ──41 符号──> daily（含转发/再导出/叶子耦合）
目标：minute ──> csv_common / csv_ledger / market_layer / csv_pool /
                 csv_strategy_books / strategy6_rules（改指真身）
        ──> csv_artifacts.py（新：汇总/落盘/对照三件套/…）
        ──> csv_daily_loader.py（新：日线加载+_read_one_daily/warmup/env 卫生）
双入口（csv_daily / csv_minute CLI）不变；卖环分家不变。
```

---

## 1. 现状锚点（2026-09-16 双路评审核验）

### 1.1 符号→处置总表（41 项，评审逐一对真身）

| 处置 | 符号（定义锚点经核验） |
|------|------------------------|
| **改指 `csv_ledger.py`**（14） | CHASE_HM:20, DEFAULT_TOTAL_CASH:17, PEAK_GAP_MIN:19, SimState:71, chase_decision:105, execute_buy:181, finish_pending_chase:121, queue_limit_up_chase:114, hit_limit_down:95, hit_limit_up:90, last_close_mark:162, peak_gap_blocks:100, `_sell`:229, `_ymd`:81 |
| **改指 `csv_common.py`**（3+1） | build_calendar:44, `_named_limits`:58, `_pool_names_asof`:62（消除 daily:83-88 转发）；**`_progress`（daily:201，纯 print，随本表从 daily 迁入 common）** |
| **改指 `market_layer.py`**（1） | utc_ms_range:25 |
| **改指 `csv_pool.py`**（1+直呼） | load_pool_names_by_day:161；**load_pool_days 处置见 P3：直呼 `load_pool_day_map(actual_pool_dir, start, end, key="ymd", empty_in_map=False)`（daily:214 wrapper 退役；csv_pool 保持 repo-无感）** |
| **改指 `csv_strategy_books.py`**（8） | add_csv_backtest_common_args:202, apply_csv_strategy:91, csv_run_kwargs_from_args:288, engine_book:144, resolve_research_pool_dir:268, help_lock_all:152, normalize_csv_strategy:75, help_lock_for:148（minute:1121 显式传 shared → 改指零行为；**daily:184 wrapper 保留**，daily:826 依赖其默认值） |
| **改指 `strategy6_rules.py`**（2） | POS_TRAIL:19, trail_hits:34 |
| **抽出 `csv_artifacts.py`（新，6 符号=4+2 伴生）** | summarize:562, write_run_artifacts:678, maybe_compare_daily:765, **find_daily_equity_csv:695, format_equity_compare:719（🔴 评审补：maybe_compare_daily 的伴生，不随迁即成环/NameError）** |
| **抽出 `csv_daily_loader.py`（新，4 符号+1 常量）** | load_daily_bars:262, **`_read_one_daily`:222（🔴 评审补：load_daily_bars 的伴生）**, warmup_start:188, warn_stale_period_env:192, **`_PERIOD_ENV_KEYS`:140-146（🟡 评审补）**；模块内本地复算 `REPO`（同公式零行为差） |
| **常量归位** | DEFAULT_DAILY_QUOTA:135 / WARMUP_DAYS:136 / STRATEGY4_CALENDAR_SLACK_DAYS:137 → `csv_common.py`；**MINUTE_LAKE_END:139 → 留 `csv_minute_backtest.py` 自定义自用**（daily 函数体零使用、minute 唯一消费者；进 loader = 病灶降级复刻，评审改判） |

### 1.2 全树消费者闭包（评审核验，13 处）

| 消费者 | 处置 |
|--------|------|
| `csv_minute_backtest.py:33-75`（41 符号） | A/B/C 全量改指（plan 主体） |
| `tests/test_csv_daily_backtest.py:17`（`sim.` 属性 13+ 处：`_read_one_daily`×5 :86/:108/:963/:964/:1020、`summarize`×4 :217/:733/:752/:764、`load_pool_days` :743、`write_run_artifacts` :787、`format_equity_compare` :801、`find_daily_equity_csv` :814） | 改指新模块（loader/artifacts） |
| `tests/test_csv_minute_backtest.py:11`、`tests/test_csv_minute_backtest_v8.py:11`（`from … import chase_explained`） | 改指 `csv_ledger` |
| `tests/test_csv_daily_backtest_v8.py:200`（`SimState, summarize`）、`tests/test_csv_strategy_books.py:352`（`summarize`） | 改指真身/artifacts |
| `tests/test_csv_daily_outdir.py`、`test_strategy9_book.py`、`test_strategy10_tr_pool.py`、`tests/fixtures/csv_engine_pre_er1/generate_snapshot.py`（`sim.main`/`sim.run`/`sim.simulate` 等非搬移符号） | 不受影响，零动作 |
| bench 脚本（`bench_minute_simulate_hotpath.py:91-111` 等 setattr） | **patch 目标全在 minute 命名空间，本次不受影响**（评审结案，无需动作） |

- **测试面保留清单（N-R9）**：daily 的 `_ = (...)` pin 块（:107-131）、`chase_explained` import（:73）、`_limit_prices` 别名（:211）等服务于测试的绑定**不在 N-R4 打击面，保留**；pin 注释改为「仅测试」。`to_partition_key`（:133）在 `_read_one_daily` 迁走后成 daily unused import——删除（写明，防实施者犹豫）。
- **围栏**：新模块自动受 `test_research_face_ast_no_backtrader`（rglob）约束；D 片把两新模块加进 `_VECTORIZED_RESEARCH_FACE`（:43-49）获子进程检查。

## 2. 现锁（N-R\*）

| # | 规则 |
|---|------|
| **N-R1** | **不合并卖环 / 不合并 `simulate()`**（G 禁区）：两条 CLI 入口、两套卖环、两份 HELP_LOCK 文案职责不变。 |
| **N-R2** | **纯机械搬移**：被移动函数/常量**函数体零改动**（含 docstring、默认参数、`# noqa`）；只允许「改 import 指向 + 移动定义 + 模块 docstring 归属说明（🟡-6 契约句）」。禁止顺手改签名/重命名/性能优化/格式化无关行。 |
| **N-R3** | **行为锁**：每片 `pytest -q tests/` 全绿 + byte-identical golden 绿 + **B/C 片各自补的 data-free 单测绿**（见 §5）；宿主对照件（可选，非合入门）：daily/minute 各跑一窗 trades 与重构前逐字节一致。 |
| **N-R4** | **不留兼容 re-export**（被下沉符号）；消费者闭包按 §1.2 全量改指。**测试面保留清单除外（N-R9）**。 |
| **N-R5** | **无环 + 不倒挂**：loader/artifacts 不得 import 引擎文件；**artifacts 不得 import loader**（`_progress` 已改判 csv_common，此边不存在）；csv_common 只加常量与 `_progress`（纯函数），不加反向边。 |
| **N-R6** | minute→daily import **41 → 0**；并落**持久围栏**：新增 pytest 断言 `csv_minute_backtest` 的 AST 无 `csv_daily_backtest` import 节点（结构性回归锁）。 |
| **N-R7** | CLI 参数名、`--help` 文案、落盘路径与文件名、summary 字段**零变化**。 |
| **N-R8** | **搬移闭包完整性**（评审 🔴 同根锁）：每个被搬符号的模块内依赖必须同迁或已在目标模块——本 plan §1.1 已列全（find_daily_equity_csv/format_equity_compare/_read_one_daily/`_PERIOD_ENV_KEYS`/`REPO` 复算）；实施时若发现新依赖即停下回写本 plan，不得现场裁决。 |
| **N-R9** | **测试面保留清单**：daily 服务于测试的 pin/别名（§1.2 所列）保留；N-R4 只打被下沉符号的转发。 |
| **N-R10** | 新文件 UTF-8 无 BOM、NUL=0（D 片复核）；§6 验证命令一律 vanna312 全路径 python。 |

## 3. 人裁点

| # | 问题 | 建议（含评审改判） |
|---|------|----------|
| **P1** | 常量归属 | ✅ **已裁 2026-09-16**：DEFAULT_DAILY_QUOTA / WARMUP_DAYS / STRATEGY4_CALENDAR_SLACK_DAYS → csv_common；**MINUTE_LAKE_END 留 minute 自用**；`_PERIOD_ENV_KEYS` 随 loader |
| **P2** | 是否留兼容 re-export | ✅ **已裁 2026-09-16**：**不留**（N-R4；测试面 pin 清单 N-R9 保留） |
| **P3** | load_pool_days 处置 | ✅ **已裁 2026-09-16**：两引擎直呼 `load_pool_day_map(..., key="ymd", empty_in_map=False)`；wrapper 退役；csv_pool 不落 REPO 默认 |
| **P4** | 假绿通道焊死（评审新增） | ✅ **已裁 2026-09-16**：完成定义含三个 data-free 单测 + 两新模块 docstring 契约句 |

## 4. 非目标

| 不做 | 原因 |
|------|------|
| 合并日线↔分钟卖环 / 单引擎 | G 禁区 + 人裁方向 |
| 改任何函数体 / 语义 / E-R\* | N-R2 |
| 改 CLI / 落盘契约 / summary 字段 | N-R7 |
| version11 / band-as-data / compiled-scan 的**内容** | 另开；**宣称降级（评审 §三）**：NP3 对 version11 必要不充分、对 band-as-data 无直接交付、对 compiled scan 几乎无贡献（仅文件卫生便利） |
| 动 v7 / Rust / 复权链 / run 出处戳 | 无关（出处戳未来落点在 artifacts，NP3 只搬不建） |

## 5. 切片

从**当时 master** 开 `feat/np3-engine-layering`。每片一个 commit，片后全量 pytest + golden 必绿。

| 切片 | 做什么 | 完成定义 |
|------|--------|----------|
| **A · 改指真身（29 符号）** | minute import 块按 §1.1 改指 6 个既有模块 + load_pool_days 直呼（P3）；minute 自定义 `MINUTE_LAKE_END`（P1） | minute→daily import 41→10；pytest 全绿；golden 绿 |
| **B · 抽 `csv_artifacts.py`（6 符号）** | summarize / write_run_artifacts / maybe_compare_daily / **find_daily_equity_csv / format_equity_compare**（+`_progress` 迁 csv_common）；daily/minute/测试改指；**新单测**：maybe_compare_daily（tmp_path 对端目录）+ summarize 确定性全文本 golden | minute→daily import →6；无环；pytest 全绿（含新单测） |
| **C · 抽 `csv_daily_loader.py`（4 符号 + `_PERIOD_ENV_KEYS`）** | load_daily_bars / **`_read_one_daily`** / warmup_start / warn_stale_period_env（+REPO 复算；3 常量进 csv_common）；daily/minute/测试改指；**新单测**：warn_stale_period_env（monkeypatch env） | minute→daily import →0；`to_partition_key` 清理；全树 grep 无被下沉符号残余 import；pytest 全绿 |
| **D · 围栏与文档** | 持久围栏 pytest（minute AST 无 daily import 节点）；两新模块入 `_VECTORIZED_RESEARCH_FACE`；daily pin 注释改「仅测试」；README 引擎地图段更新（双入口 + 共享核分层）；本 plan 状态回写 | 围栏测试绿；NUL=0 复核；HELP_LOCK 文案不变 |

## 6. 验证命令

```bash
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
D:\anaconda3\envs\vanna312\python.exe - <<'EOF'
import ast, pathlib
t = ast.parse(pathlib.Path('backtest/research/csv_minute_backtest.py').read_text(encoding='utf-8'))
n = [x for x in t.body if isinstance(x, ast.ImportFrom) and x.module and x.module.endswith('csv_daily_backtest')]
print('minute→daily import 块数:', len(n), '| 符号数:', sum(len(x.names) for x in n))
EOF
# （可选宿主，非合入门）重构前后各跑一窗 daily+minute，trades.csv 逐字节对照
```

## 7. 代码落点

| 文件 | 动作 |
|------|------|
| `backtest/research/csv_minute_backtest.py` | import 块改指 + `MINUTE_LAKE_END` 自定义 + load_pool_day_map 直呼 |
| `backtest/research/csv_daily_backtest.py` | 删被抽出定义与转发；自用改指；`help_lock_for` wrapper / `_ = (...)` pin / `_limit_prices` 别名保留（N-R9）；删 `to_partition_key` unused import |
| `backtest/research/csv_artifacts.py` | **新建**（6 符号原体 + docstring 契约句：知晓两引擎工件命名约定=数据非依赖） |
| `backtest/research/csv_daily_loader.py` | **新建**（4 符号 + `_PERIOD_ENV_KEYS` + 本地 REPO + 三职责 docstring） |
| `backtest/research/csv_common.py` | +3 常量 + `_progress` |
| `tests/test_csv_daily_backtest.py`（:86/:108/:217/:733/:752/:764/:743/:787/:801/:814/:963/:964/:1020）、`tests/test_csv_minute_backtest.py:11`、`tests/test_csv_minute_backtest_v8.py:11`、`tests/test_csv_daily_backtest_v8.py:200`、`tests/test_csv_strategy_books.py:352` | import/属性改指 |
| `tests/test_research_face_imports.py` | 两新模块入 `_VECTORIZED_RESEARCH_FACE`；新增 minute-AST 无 daily-import 围栏断言 |
| `tests/test_np3_layering.py`（或并入现有） | 三个新单测（maybe_compare_daily / warn_stale_period_env / summarize 全文本 golden） |
| `docs/backtest/README.md` | 引擎地图段 |

禁止改：两条卖环、`simulate()`、`csv_ledger.py` 记账体、CLI 参数与落盘路径、v7、Rust。

## 8. 风险

- ~~隐性模块态~~（评审已逐函数核验：`resolve_period_root` 调用时读 env 无缓存；OSKH_\* 无 import 时序问题；唯一伴生依赖已入 §1.1 闭包清单）。
- **假绿通道**（maybe_compare_daily / warn_stale_period_env 零测试）：已由 P4 单测焊死；golden 只锁 simulate 注入路径属已知边界。
- 循环 import：N-R5 + 伴生同迁后无环（评审核验目标态依赖图）。
- bench monkeypatch：patch 目标在 minute 命名空间，不受影响（评审结案）。
- 消费者遗漏残留：C 片全树 grep 兜底 + ImportError 响亮失败模式。

## 9. 修订程序

改 N-R\* / 人裁结果须改本文并回写状态。后续 version11 / band-as-data / compiled scan 均另开 dated plan；本 plan 对它们的贡献限定见 §4 宣称降级。

## 10. Changelog

- **v1.2**（2026-09-16）：人裁 **P1–P4 GO 全采纳**（建议值）；A–D 落地；交接生效。
- **v1.2 closeout**（2026-09-16）：PR #78 合入 merge `71f0f3f`；状态 → ✅ 已实施并合入；Grok GO-WITH-NITS + nit `2951fca`；zcode 宿主 PASS（trades.csv 逐字节一致 / N-R6=0）；归档至 `_archive/plans/`。
- **v1.1**（2026-09-16，两路评审）：§1 重写为「符号处置总表 + 消费者闭包」（补 artifacts 两伴生、loader 闭包 `_read_one_daily`/`_PERIOD_ENV_KEYS`/REPO、3 个漏列测试文件、help_lock_for 双真身注记、load_pool_days=wrapper 勘误）；P1 改判 MINUTE_LAKE_END 留 minute、P3 改判直呼 load_pool_day_map、新增 P4（单测+docstring 契约）；`_progress` 改判 csv_common；新增 N-R8（搬移闭包）/N-R9（测试面保留清单）/N-R10（编码与解释器）；N-R6 升级持久围栏；§8 bench 风险行结案；§4 宣称降级。
- **v1.0**（2026-09-16）：初稿。

---

## 11. 实施记录（Codex 随本 PR 回写；closeout 补齐合入）

| 切片 | 状态 | commit | 备注 |
|------|------|--------|------|
| A · 改指真身（29 符号） | ✅ | `278bf6f` | minute→daily 41→10；P1–P4 GO 文档同提交 |
| B · 抽 `csv_artifacts.py`（6 符号） | ✅ | `d0adf54` | artifacts 6 + `_progress`→csv_common；minute→daily 10→6 |
| C · 抽 `csv_daily_loader.py` | ✅ | `8ec5bba` | loader + 3 常量→csv_common；minute→daily 6→0 |
| D · 围栏与文档 | ✅ | `b9b101e` | AST 围栏、`_VECTORIZED_RESEARCH_FACE`、pin「仅测试」、README 引擎地图 |
| nit + Grok review 落盘 | ✅ | `2951fca` | 删未用 `csv_common._limit_prices`；落 [grok-review.md](../../../architecture/reviews/2026-09-16/pr-78-np3-engine-layering/grok-review.md) |
| 合入 | ✅ | `71f0f3f` | PR #78 merge；zcode 宿主 D-smoke daily+minute trades.csv 逐字节一致；N-R6=0；结构性锁 OK |
