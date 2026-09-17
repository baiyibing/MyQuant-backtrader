# PR #89 v8 利弗莫尔宿主包（master-first 最小重放）— Grok 核评审

> 日期：2026-09-17
> 角色：MyQuant-backtrader Grok 核（独立 grok CLI；只审不合入）
> 对象：[PR #89](https://github.com/baiyibing/MyQuant-backtrader/pull/89) `feat/v8-livermore-host`（tip `d484147` vs base master `5659eb4`）
> 权威：[v8-livermore-note-2026-09-16.md](../../../../backtest/v8-livermore-note-2026-09-16.md)（现锁）· [strategy8_rules.py](../../../../../backtest/research/strategy8_rules.py) HELP_LOCK / 常量 · [v8-sse-ma10-gate-note-2026-09-16.md](../../../../backtest/v8-sse-ma10-gate-note-2026-09-16.md) / [v8-stop-tp-opt-note-2026-09-16.md](../../../../backtest/v8-stop-tp-opt-note-2026-09-16.md)（过程短记，非现锁）· [#81 v2 评审](../../2026-09-16/pr-81-v8-rules-v2/grok-review.md)（master 上 v2 = 止损 30% / T+1 豁免 / `PEAK_GAP_MIN=0`）
> HEAD：`d484147f7f4c3736908b92fdd3c75d03ca5009c2`
> parent / merge-base：`5659eb44c72d40cbde668d2249255b2f1f12c583`（= `origin/master` = Merge #96）
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**（[run 35208288174](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35208288174)）
> 工作树：`/workspace/MyQuant-backtrader-pr89`（分支 `feat/v8-livermore-host`）
> 本核 **未 merge**。本结论 **不是** 探针/SSE 钩子已接到共享引擎，也 **不是** 宿主 509,597,988.60 可在本 tip 默认 CLI 复现。

---

## 结论

**GO-WITH-NITS**（**可合**；nits 不阻断合入，不改成交核 / Mode B / #81 引擎语义。本核不 merge）。

这是合格的 **master-first 最小重放**：相对 Merge #96 只动 20 文件（+889/−148），共享引擎（`csv_simulate_loop` / `csv_ledger` / `csv_daily_backtest` / `csv_minute_backtest` / `csv_artifacts`）与 Mode A/B **字节级未动**。Livermore 锁数字在 `strategy8_rules` 常量、HELP_LOCK、README、利弗莫尔短记之间对齐：止损 10%、0–6% 死区、试探 50 万、+3% 加仓、SSE MA10 helpers、8 日僵持、15 分钟峰差。

**今日生产路径实际吃到的子集**（引擎已有钩子）：`stop_pct=0.10`、`take_profit_reason`（死区 / 8 日 stale / T+1 起评止盈 / 新开闭档）、`peak_gap_min=15`、`allow_add=True` + `per_name` 100 万。**尚未生产**（书已接线、引擎未读）：`add_gate=may_add`、`name_lot_budget=lot_budget`、`allow_new_name`（且 `_run_kwargs_version8` 不装上证、默认 `None`）。9 个 skip 带原因，不是默默删断言。宿主短记在场；代码未写入 509M 等宿主净值。剩余是共享 HELP/summarize 仍写「T+1 止盈豁免」、HELP 描述全锁但探针/SSE 要等引擎重接——不挡合入。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#89 feat(research): v8 Livermore host package and host notes](https://github.com/baiyibing/MyQuant-backtrader/pull/89) |
| 比较 | `5659eb4...d484147`（20 files, +889 / −148） |
| 单提交 | `d484147` rebase-free master-first replay |
| 规则 | `strategy8_rules.py`：10% 止损、死区、T+1 trail、stale 8、probe/add helpers、SSE helpers、`PEAK_GAP_MIN=15` |
| 书 | `csv_strategy_books.py`：`setdefault(add_gate/allow_new_name/name_lot_budget)` + `_apply_version8` 注入；`--stop-pct` help `v8 0.10` |
| 短记 | 11 份 2026-09-16 宿主笔记（现锁 = livermore；其余为扫参档案） |
| 测试 | rules 向量对齐；v8 日线/分钟 9 skip；books `peak_gap_min==15`；daily 共享断言 `stop_pct==0.10` |
| 引擎 | **零**。`csv_*` 成交核 / 日线 / 分钟 / artifacts / Mode A/B **未动** |

`git diff --name-status 5659eb4...HEAD`（评审对象 tip；不含本文件）：

```
M  backtest/research/csv_strategy_books.py
M  backtest/research/strategy8_rules.py
M  docs/backtest/README.md
A  docs/backtest/v8-3-lowband-note-2026-09-16.md
A  docs/backtest/v8-arm15-dead3-note-2026-09-16.md
A  docs/backtest/v8-band-opt-note-2026-09-16.md
A  docs/backtest/v8-host-patch-stale20-note-2026-09-16.md
A  docs/backtest/v8-livermore-note-2026-09-16.md
A  docs/backtest/v8-rules-v2-slice-d-host-note-2026-09-16.md
A  docs/backtest/v8-sse-ma10-gate-note-2026-09-16.md
A  docs/backtest/v8-stop-tp-opt-note-2026-09-16.md
A  docs/backtest/v8-stop20-tp10-note-2026-09-16.md
A  docs/backtest/v8-stop20-tp15-arm20-note-2026-09-16.md
A  docs/backtest/v8-stop30-arm5-20-60-note-2026-09-16.md
A  docs/backtest/v8-stop30-hybrid-floors-note-2026-09-16.md
M  tests/test_csv_daily_backtest.py
M  tests/test_csv_daily_backtest_v8.py
M  tests/test_csv_minute_backtest_v8.py
M  tests/test_csv_strategy_books.py
M  tests/test_strategy8_rules.py
```

禁区文件不在列。GitHub PR files 与 tip 一致（20 / +889/−148）。CI [`35208288174`](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35208288174) SUCCESS @ `d484147`：**728** passed, **14** skipped, 24 deselected（基线 5 skip + 本票 9 skip）。`backtest_output/` gitignored；数字产物未入库。

---

## 证据表

| 锁 / 裁点 | 结果 | 证据 |
|-----------|------|------|
| **1 共享引擎相对 master 未动** | **PASS** | `git diff --stat 5659eb4 HEAD -- csv_simulate_loop.py csv_ledger.py csv_daily_backtest.py csv_minute_backtest.py csv_artifacts.py csv_common.py unified_exit_modea.py unified_exit_modeb.py` 全空。`git merge-base --is-ancestor 5659eb4 HEAD` = 0。diff 20 文件 = strategy8 / books / docs / tests，与宣称一致。 |
| **2 Livermore 锁数字 = 短记 / HELP** | **PASS** | 见下节对照表。本核直调：`STOP_PCT=0.10`、`PEAK_GAP_MIN=15`、`STALE_DAYS=8`、`PROBE_FRAC=0.50`、`ADD_PEAK_MULT=1.03`、`BAND_TRAIL_MIN_MULT=1.06`、`BAND2_ABS_MULT=1.02`、`BAND3_GLOBAL_MULT=1.15`、keep 60/70/80、`INDEX_SYMBOL=000001.SH` / `INDEX_MA=10` / `INDEX_BELOW_SESSIONS=2` / `INDEX_BLOCKS_ADD=True`。HELP_LOCK / README / livermore 短记逐项同文。 |
| **3 不践踏 Mode B / unified-exit / #81 引擎语义** | **PASS** | Mode A/B `.py` 不在 diff 且与 `5659eb4` 相同。v6 书 `stop_pct=0.06` / `allow_add=False` / `daily_quota` 未改；`strategy{1–7,9,10}_rules.py` 不在 diff。`apply_csv_strategy` 仅 `setdefault` 三个新键为 `None`，其它书 no-op。#81 成交核（档位 / 全卖因跌停 / Decimal 板 / T+1 买日不可卖）仍在未改引擎里。本票改的是 **v8 规则书**，不是 #81 引擎。 |
| **4 skipped 测试诚实说明缺钩子 / v2 夹具** | **PASS** | 9 skip，原因非空。日线 7：`Livermore host lock on master engines: v2 behavioral fixture; covered by test_strategy8_rules`。分钟 2：`Livermore T+1 trail on; master fixture expects T+1 exempt`。未删测试体。仍跑：T+0 不卖、追买/弃买、分钟加仓 lot、分钟 #21 跨 15%、`summarize` 10%。本核 `231 passed, 9 skipped`。不是默默削弱生产断言。 |
| **5 宿主短记在场；代码未伪造宿主指标** | **PASS** | 11 份 `docs/backtest/v8-*-note-2026-09-16.md` 入库；README 指针 livermore / sse-ma10 / stop-tp-opt。全树 `.py` 无 `509,597,988` / `514,788,283`。短记自报目录 `backtest_output/csv_minute_v8_20251023_20260909_v8_livermore/`（gitignored）。未把宿主净值写进 stats / golden。 |
| **6 UTF-8 无 BOM** | **PASS** | 20 文件 BOM=false、NUL=0、CR=0、UTF-8、LF 结尾。`git diff --check` 空。 |

本核 **未**跑真湖 5 亿分钟（无 F 湖）。数字核验走常量 / HELP / 短记自洽 + 合成单测，不冒充宿主复跑 509M。

### 锁数字对照（本核直调）

| 项 | `strategy8_rules` | HELP_LOCK / README | livermore 短记 |
|----|-------------------|--------------------|----------------|
| 止损 | `STOP_PCT=0.10`；`stop_hits(8.989,10)` True / `9.011` False | 止损 10 个点（T+1 起） | 止损 **10%** |
| 死区 | `BAND_TRAIL_MIN_MULT=1.06`；`peak≤cost×1.06` 不评档 | `(0,6%]→不评档位回撤` | 0–6% 不评档位回撤 |
| 档2 | `BAND2_ABS_MULT=1.02`；`[6%,15%)` | 买价 ×1.02 | 档2 底 +2% |
| 档3 | `max(×1.15, 保留 60%)`；`<50%` | `[15%,50%)` max(×1.15, 60%) | 档3 全局底 +15% |
| 档4/5 | keep 70% / 80%；`≥50%` / `≥100%` | `[50%,100%)` / `[100%,∞)` | 保留 70% / 80% |
| T+1 trail | `n_days<1` 才挡；`n_days=1` 可 `trail:band:5` | T+1 起评止盈 | T+1 起评止盈 |
| 15m 峰差 | `PEAK_GAP_MIN=15` → 书 `hooks["peak_gap_min"]` | ≥15 分钟（隔夜/午休视为满足） | 分钟回撤须距峰值 ≥15 分钟 |
| 8 日陈旧 | `STALE_DAYS=8` → `force_sell:stale`（ledger 已认 `force_sell:`） | 满 8 个交易日且从未到 +6% | 同 |
| 试探 50 万 | `PROBE_FRAC=0.50`；`lot_budget(1e6,[])=5e5` | 首笔 50 万试探 | 同 |
| +3% 加仓 | `ADD_PEAK_MULT=1.03`；`may_add` 只加赢家 | 现价≥成本且峰值已到 +3% | 同 |
| SSE MA10 | `build_sse_ma10_block_new` = `strategy7_rules.build_index_gate`（MA10、两日下方、滞后一日） | 000001.SH 连续两日收下，第三日起停新开且已持不可加 | 「上证十日线两日下方停开新仓且已持不可加」 |

相对 #81 v2 的档位开闭：v2 是 `[15%,50%] / (50%,100%]`（`<=`）；本包改为 `[15%,50%) / [50%,100%)`（`<`）。单测 `band_of(10,15.00)==4`、`band_of(10,20.00)==5` 与 HELP 一致，不是漏改。

### 生产路径 vs helpers（master 引擎）

引擎只读已知键（`stop_pct` / `take_profit` / `peak_gap_min` / `allow_add` / `buy_gate` / `sell_gate` / …）。本核 `rg`：`csv_daily_backtest.py` / `csv_minute_backtest.py` / `csv_simulate_loop.py` / `csv_ledger.py` **零** `add_gate` / `name_lot_budget` / `allow_new_name`。

| 钩子 | 书接线 | 引擎消费 | 本 tip 默认 CLI |
|------|--------|----------|-----------------|
| `stop_pct=0.10` | 是 | 是 | **活** |
| `take_profit_reason`（死区 / stale 8 / T+1 trail / 新档） | 是 | 是 | **活** |
| `peak_gap_min=15` | 是（#81 为 0） | 是 | **活** |
| `allow_add=True` + `name_budget=1e6` | 是 | 是 | **活**（仍按整笔 100 万，**不是** 50 万试探） |
| `add_gate=may_add` | `_apply_version8` 注入 | **否** | 死 |
| `name_lot_budget=lot_budget` | 注入 | **否** | 死 |
| `allow_new_name` / SSE 装载 | `allow_new_name_from_gate(index_block_new)`；`_run_kwargs_version8` **不传** `index_block_new` → **None** | **否** | 死 |

`force_sell:stale` 不需要新引擎键：`csv_ledger.py:283-284` 已 `reason.startswith("force_sell")` → `sell_force`。CLI epilog 的策略书段走 `HELP_LOCK_V8 = strategy8_rules.HELP_LOCK`（books 再导出），**不必改引擎文件**即可更新书 HELP。

### skip(9) 清单

| 测试 | 为何相对 v2 会红 | 是否因缺探针/SSE |
|------|------------------|------------------|
| `test_gap_open_stop_30pct` | 夹具按 30% 止损推卖日；现 10% 更早触 | 否（止损已活） |
| `test_band_tp_exits_next_open` | T+1 现评止盈，卖日/档会变 | 否（T+1 trail 已活） |
| `test_small_band_tp_exits_next_open` | 同上 + 死区/档 | 否 |
| `test_disarmed_tp_when_peak_only_1pct` | v2 档1 保本退出；现死区不评 | 否 |
| `test_no_tp_when_small_band_still_above_2pct` | T+1 现评 | 否 |
| `test_held_name_adds_second_lot`（日线） | D3 low=8.50 会触 10% 止损，持仓断言破 | 部分（加仓仍走 `allow_add`；探针门未接） |
| `test_peak_cross_15pct_*`（日线） | T+1 豁免假设 | 否 |
| `test_scan_band_tp_on_close` | 分钟 T+1 现可 `trail:band:3` | 否 |
| `test_scan_peak_dd` | 同上，深档 T+1 可触 | 否 |

分钟 `test_simulate_held_name_adds_second_lot` **未 skip**，仍钉 master 引擎 `allow_add` 加 lot（无 +3% 门）。rules 单测覆盖止损 10%、死区、stale 8、probe/add 纯函数、SSE 滞后映射。

### 相对 #81 / Mode B

| | #81 v2（已在 master） | 本票 Livermore |
|--|----------------------|----------------|
| 止损 | 30% | 10%（规则常量） |
| T+1 止盈 | `n_days<2` 豁免 | `n_days<1`；T+1 起评 |
| 峰差 | `PEAK_GAP_MIN=0` | 15 |
| 档开闭 | 50%/100% 闭区间归下档 | 半开，50% 起归上档 |
| 引擎 | 未改成交核 | **仍未改** |
| Mode B | 其后 #90–#96 已合 | 本 diff 不相交 |

---

## 违规 / 风险

无 🔴。无合入阻断。硬边界未破。探针/SSE **未**声称已接到共享引擎。宿主 509M **未**当作本 tip 回归闸。

### nit-1（文案债）共享引擎 HELP 仍写「v8：T+1 只评止损不评止盈」

`csv_daily_backtest.py:171`、`csv_minute_backtest.py:125` 与 `5659eb4` 相同（本票刻意不改引擎）。`--help` 会先印共享段（T+1 豁免）再拼书 HELP（T+1 起评）。以书 HELP_LOCK 为准。合入后另票改引擎 HELP 一行即可，**不要为本句开引擎切片**。

### nit-2（文案债）`summarize` 硬编码 `| T+1止盈豁免`

`csv_artifacts.py:58` 对所有 `sell_book==v8` 写死豁免句。`record_strategy8_params` 已写 `t1_trail=True`，artifacts 不读。`test_summarize_v8_params` 仍断言 `"T+1止盈豁免"`——与 artifacts 现状一致，与规则相反。同 nit-1：另票用 `t1_trail` 开关，本票不要动 artifacts。

### nit-3（范围）HELP/README 描述全锁；默认 CLI 复现不了短记 509M

书已注入 `add_gate` / `name_lot_budget`，但引擎不读；SSE 连 `index_block_new` 都没装，`allow_new_name is None`。默认

```text
csv_minute_backtest.py --strategy version8 --start 20251023 --end 20260909 --cash-total 500000000
```

会跑 **10% + 死区 + stale 8 + T+1 trail + 15m 峰差 + 100 万/lot 无 +3% 门、无上证闸**，不是短记里的 3,099 买 / 260 加仓 / skip_index_gate 1,545。短记是 2026-09-16 全包宿主档案，不是本 tip 的复现契约。合入后另票把三钩接到日线/分钟买环，并在 `_run_kwargs_version8` 装 `load_sse_ma10_block_new`。

### nit-4（覆盖）若干 **已活** 行为被 skip 而不是翻转夹具

分钟 `test_scan_band_tp_on_close` / `test_scan_peak_dd` 的 T+1 trail **已经**走 `take_profit_reason`；skip 原因诚实，但本可改期望为触价而非 skip。日线 30% 跳空止损夹具也可改成 10% 口径。不挡；rules 向量已覆盖。`test_scan_small_band_tp_on_close` 仍注释「T+1 止盈豁免」，实际靠死区 `peak=10.60≤10.60` 才 `idx==-1`。

### nit-5（档案）SSE 过程短记与现锁「已持不可加」不一致

[v8-sse-ma10-gate-note](../../../../backtest/v8-sse-ma10-gate-note-2026-09-16.md) 写「不买新票；**已持仍可加仓**」，`skip_index_gate=1,459`。现锁 `INDEX_BLOCKS_ADD=True` + HELP「已持不可加」+ livermore `skip_index_gate=1,545`。这是扫参序列 vs 最终包，不是代码自相矛盾。读者容易拿错短记当 SSOT。现锁以 livermore 短记 + HELP_LOCK 为准。

### 观察（不升格）

| 项 | 说明 |
|----|------|
| `GIVEBACK_MULT=0` / `BAND1_MIN_MULT=0` | 死分支，扫参残留。`take_profit_reason` 短路不触发。 |
| `INDEX_MA` / `INDEX_BELOW_SESSIONS` | 只进 stats；`build_index_gate` 写死 MA10 + 两日。与策略 7 同构，未参数化。 |
| `test_np3_layering` golden | 仍注入止损 30% + keep 30/60/70/80 + T+1 豁免，测的是 artifacts 格式，不是 live v8。正确未改。 |
| CI 728 vs #96 的 739 | −9 skip 的原通过用例，再减去 rules 向量表净删若干条。14 skipped = 5 基线 + 9 本票。 |
| 策略 8 依赖 `strategy7_rules.build_index_gate` | 纯函数、无引擎 import。可接受的复用。 |

---

## 建议动作（是否可合）

**可以合入 master。** 不要为 nit-1…5 改成交核或重开 Livermore 规则切片。合入后（另票，非本 PR）：

1. 日线 / 分钟买环读取 `add_gate` / `name_lot_budget` / `allow_new_name`；`_run_kwargs_version8` 装上证停买表。未接钩子前，不要用本 tip 默认 CLI 对短记 509M。
2. （可选）引擎 HELP 与 `summarize` 改读 `t1_trail`，去掉「T+1 止盈豁免」。
3. （可选）把已活路径的 skip 夹具改成 Livermore 期望，而不是长期 skip。
4. 数字产物继续不入库。

本核 **未 merge、未改业务代码**；仅落本评审文件。

---

## 核验命令（本核已跑）

```text
git rev-parse HEAD
# = d484147f7f4c3736908b92fdd3c75d03ca5009c2
git merge-base origin/master HEAD
# = 5659eb44c72d40cbde668d2249255b2f1f12c583  (= origin/master = Merge #96)
git merge-base --is-ancestor 5659eb4 HEAD   # exit 0
git diff --name-status 5659eb4...HEAD
# 20 files；无 csv_simulate_loop / csv_ledger / csv_daily_backtest.py
#   / csv_minute_backtest.py / csv_artifacts / unified_exit_mode{a,b}
gh pr view 89 --json mergeable,mergeStateStatus,headRefOid,statusCheckRollup
# MERGEABLE / CLEAN / head = d484147 / pytest-and-gates SUCCESS
gh run view 35208288174
# SUCCESS @ d484147；728 passed, 14 skipped, 24 deselected
/workspace/vanna312/bin/python -m pytest -q \
  tests/test_strategy8_rules.py tests/test_csv_strategy_books.py \
  tests/test_csv_daily_backtest_v8.py tests/test_csv_minute_backtest_v8.py \
  tests/test_csv_daily_backtest.py tests/test_np3_layering.py \
  tests/test_research_face_imports.py tests/test_csv_minute_backtest.py -rs
# 231 passed, 9 skipped in 10.37s
# UTF-8：20 文件 BOM=false NUL=0 CR=0 LF 结尾；git diff --check 空
# 直调：STOP_PCT=0.10 PEAK_GAP_MIN=15 STALE_DAYS=8 PROBE_FRAC=0.50
#   ADD_PEAK_MULT=1.03 BAND_TRAIL_MIN_MULT=1.06
# apply_csv_strategy(version8): add_gate=may_add, name_lot_budget=lot_budget,
#   allow_new_name=None；version6 stop=0.06 add_gate=None
# 引擎 rg add_gate|name_lot_budget|allow_new_name → 空
```

真湖 5 亿分钟 / 短记 509M **未**复跑（本 PR 声明 master-first；非合入门复验项）。
