# PR #95 统一卖出规则网格 · 模式 B 实施 A–D — Grok 核评审（复核）

> 日期：2026-09-17（复核；上一轮 BLOCK 于 session hm 单位 / `580cca5`）
> 角色：MyQuant-backtrader Grok 核（独立 grok CLI；只审不合入）
> 对象：[PR #95](https://github.com/baiyibing/MyQuant-backtrader/pull/95) `feat/unified-exit-modeb`（tip `9c39c90` vs `origin/master`）
> 权威：[plan-unified-exit-modeb-2026-09-17.md](../../../../backtest/plan-unified-exit-modeb-2026-09-17.md) v1.1（P1=A / Q36=A / Q37=A / Q38=A / warmup cache key）· [handoff-unified-exit-modeb-codex-impl-2026-09-17.md](../../../../backtest/handoff-unified-exit-modeb-codex-impl-2026-09-17.md) · 提案 [stock-backtest-unified-exit-proposal-2026-09-17.md](../../../../backtest/stock-backtest-unified-exit-proposal-2026-09-17.md) Mode B 锁（Q2/Q3/Q7/Q8/Q20/Q21/Q29 + Q36–Q38）· 上一轮本文件（`580cca5` 对象、结论 **BLOCK**）
> HEAD：`9c39c90d3567565a8f6c092426499316b42aa981`
> merge-base：`55bfe4a3cb3219c11baa95d9c314206fad52ecd2`（= Merge #93 plan；其后 `origin/master` 另合 #94 分钟就绪 docs）
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**（[run 35202921314](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35202921314) @ `9c39c90`）
> 工作树：`/workspace/MyQuant-backtrader-modeb`（分支 `feat/unified-exit-modeb`）
> 本核 **未 merge**。CI 绿 **不是** 合入条件。

---

## 结论

**GO-WITH-NITS**（**可合**；nits 不阻断合入，不改成交核 / 策略书 / Mode A 语义 / 湖钟。本核不 merge）。

上一轮 🔴（`session_minutes` 把湖 SSOT 的 `hm`（分钟从 0 点，09:30=570）当成 HHMM 930/1500 过滤，生产 cache / 1m none 湖的全部 session K 被丢光）已在 `9c39c90` 关掉：`session_minutes` 改用 `csv_minute_backtest` 的 `AM_OPEN/AM_CLOSE/PM_OPEN/PM_CLOSE`（570–690 ∪ 780–900），无 `divmod` 双钟兼容。本核用上一轮同一合成复现：湖 `hm=600/900` → `take_profit` @103、`sell_hm=600`；HHMM `1000/1459` → `mark_end` @100、`sell_hm=None`（假绿路径已死）。湖单位回归 + HHMM 防回退均在仓。

硬边界、Q36–Q38、P1=A、切片 E 未勾，上一轮 PASS 仍成立；价域链现在能走到生产单位。剩余是文档页眉/标题与计数口径 nits，不挡合入。

---

## 复核对照（相对 `580cca5` BLOCK）

| 项 | 上一轮 `580cca5` | 本轮 `9c39c90` |
|----|------------------|----------------|
| 结论 | **BLOCK** | **GO-WITH-NITS** |
| 🔴 bug-1 `session_minutes` 单位 | `hm.between(930, 1130) \| hm.between(1300, 1500)`；湖 570/900 → 0 行 | **关闭**。`AM_OPEN..AM_CLOSE` ∪ `PM_OPEN..PM_CLOSE`；湖 570/600/690/780/900 保留；HHMM 930/1000/1459/1500 空 |
| 合成测假绿 | fixture 写 1000/1459，77 绿、生产空转 | **关闭**。fixture 改湖单位；`test_legacy_hhmm_fixture_is_not_a_session_clock` 钉 empty；旧 HHMM 向量现在应 `mark_end` |
| 湖单位回归 | 缺 | **有**：`test_lake_minutes_have_coverage_and_take_profit`；`test_session_minutes_matches_production_annotation` 对 `_annotate` |
| 硬边界 | PASS | **仍 PASS**（fix 只动 modeb 库 + 四测文件） |
| Q36=A / Q37=A / Q38=A | 合成 PASS / 生产 FAIL | **合成+生产单位 PASS**（滤与求值同一套钟） |
| P1=A 18 格 / 目录隔离 | PASS | **仍 PASS** |
| 切片 E 未伪完成 | PASS | **仍 PASS**（handoff `[ ] E`） |
| CI | [35198836728](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35198836728) @ `580cca5`：**736** passed, 5 skipped, 24 deselected（上一轮文档写 739，Actions 原文 736） | [35202921314](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35202921314) @ `9c39c90`：**739** passed, 5 skipped, 24 deselected（+3 = 新增三测） |

`git diff 7950865..9c39c90`（BLOCK 评审落盘之后的修复）：

```
M  backtest/research/unified_exit_modeb.py
M  tests/test_unified_exit_modeb_aggregate.py
M  tests/test_unified_exit_modeb_exdiv.py
M  tests/test_unified_exit_modeb_exit.py
M  tests/test_unified_exit_modeb_load.py
```

禁区文件不在列。无 `divmod`、无两套钟并集。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#95 feat(modeb): implement minute exit grid, anchors, robustness and CLI (A–D)](https://github.com/baiyibing/MyQuant-backtrader/pull/95) |
| 比较 | `origin/master...HEAD`（12 files, +1077 / −13；含本评审文件） |
| A | `2482072` none 日线 + warmup cache `minute_none_20251013_20260909` |
| B | `3550c38` 分钟退出；Q36 末分钟；Q37 反例 |
| C | `c3506bc` 局部 E-R6 + `shares/=k`；ledger 行为测 |
| D | `580cca5` 窄网格 / 四锚 / Q34 / CLI / 目录隔离 |
| Q 人裁 | `d65442b` Q36=A Q37=A + cache；`a8f619f` Q38=A |
| 评审 | `7950865` 上一轮 Grok BLOCK |
| B′ | `9c39c90` session `hm` 对齐湖分钟单位 + 湖回归 / HHMM 防回退 |
| E | **未做、未勾**（handoff `[ ] E`；plan「宿主 E 未执行」；PR body 同） |

`git diff --name-status origin/master...HEAD`：

```
M  AGENTS.md
A  backtest/research/unified_exit_modeb.py
A  docs/architecture/reviews/2026-09-17/pr-95-unified-exit-modeb/grok-review.md
M  docs/backtest/README.md
M  docs/backtest/handoff-unified-exit-modeb-codex-impl-2026-09-17.md
M  docs/backtest/plan-unified-exit-modeb-2026-09-17.md
M  docs/backtest/stock-backtest-unified-exit-proposal-2026-09-17.md
A  scripts/research/run_unified_exit_modeb.py
A  tests/test_unified_exit_modeb_aggregate.py
A  tests/test_unified_exit_modeb_exdiv.py
A  tests/test_unified_exit_modeb_exit.py
A  tests/test_unified_exit_modeb_load.py
```

禁区文件相对 master **diff 空**：`csv_ledger.py` / `csv_simulate_loop.py` / `csv_daily_backtest.py` / `csv_minute_backtest.py` / `csv_minute_backtest_v7.py` / `unified_exit_modea.py` / `*_rules.py` / Mode A 三测。GitHub head = `9c39c90`。

---

## 证据表

| 锁 / 裁点 | 结果 | 证据 |
|-----------|------|------|
| **1 硬边界** 只动 Mode B 模块/CLI/测/相关 docs；不改 `rescale_position` shares；不改 Mode A 语义 | **PASS**（仍成立） | 12 文件如上。fix 五文件不含禁区。`inspect.getsource(csv_ledger.rescale_position)` 仍只 `cost*=k; peak*=k`（shares untouched X-R1）；行为测 k=0.5 下 shares=10000。Mode A 三测零改；`test_v01_n1_equals_rule2_n1_regardless_of_tp_sl` 仍在。库 AST import 无 qlib / backtrader / Cerebro。 |
| **2 价域** 买 none 日线 close；触发 1m high/low；成交分钟 close；同根先止损 | **PASS**（生产单位可触发） | `load_none_bars` → `dividend_type=none`。rule 2 先 `low` 再 `high`；fill=`close`。上一轮生产路径被 `session_minutes` 丢光；本轮湖 `600/900` 走到 TP。向量表仍绿。 |
| **3 Q36=A** 到期 = 当日最后一根 session 分钟 close；无 K 顺延；不回退日线 | **PASS** | `j == len(rows)-1` 才 `n_expire`；空日不卖。`test_expiry_no_daily_fallback_and_off_session_ignored` 现用 565/690/720/901：盘外丢、690=11:30 成交。无日线 fill 分支。 |
| **3 Q37=A** Mode B 不测 N=1 等价；盘中先触发反例；Mode A 不动 | **PASS** | `test_n1_intraday_counterexample`：r2 N=1 @600 close=103 vs r1_n1 @899 close=100。Mode A v01 仍在。 |
| **3 Q38=A** oracle 只排除跌停**分钟** close；同日其他分钟可候选；不模拟更早失败卖出 | **PASS** | `oracle_exits` 逐分钟 continue 跌停 close，不设全日 blocked。测：110 在 600 或 660 都能入选。同一 `PreparedMinutes` 滤。 |
| **4 P1=A** 默认窄网格 18 r2 + 四锚；报告目录隔离；CI data-free；切片 E 未伪完成 | **PASS**（仍成立） | `iter_grid`：X∈{5,7,10}×Y∈{5,10,None}×N∈{8,10} = 18；全 grid 20（+ hold_end + r1_n1）；ranked=19。锚 hold_end / r1_n1 / oracle / delist_zero。`DEFAULT_OUT_DIR=backtest_output/unified_exit_modeb`；path part `unified_exit_modea` 抛错。handoff `[ ] E`。 |
| **5 单测覆盖关键向量** | **PASS**（不再假绿） | 见下节。Mode A+B 本核 **80 passed / 1.58s**（上一轮 77 + 湖回归/注解对齐/HHMM 防回退）。全套本核 **742 passed, 2 skipped, 24 deselected**。CI 739 @ `9c39c90`（相对 `580cca5` 的 736 +3）。 |
| **Cache key** warmup `20251013` 超集 | **PASS** | `load_monitor_bars` → `warmup_start(start, days=10)`；测仍断言 `("20251013","20260909")`。cache 内 570/895 现与滤同单位，不再丢光。 |
| **UTF-8 / 门禁** | **PASS** | 本 diff 12 文件 BOM=false、NUL=0、CR=0、UTF-8、LF 结尾。`git diff --check` 空。四门禁 OK。 |

### 🔴 bug-1 关闭（本核复现）

`csv_minute_backtest` SSOT（未改）：

```text
hm = utc.hour * 60 + utc.minute    # 09:30 → 570, 14:55 → 895, 15:00 → 900
AM_OPEN, AM_CLOSE = 570, 690       # 9*60+30, 11*60+30
PM_OPEN, PM_CLOSE = 780, 900       # 13*60, 15*60
```

Mode B 现导入同一组常量：

```49:57:backtest/research/unified_exit_modeb.py
def session_minutes(df):
    """Return session rows with lake/cache hm in minutes since midnight, not HHMM."""
    if df.empty:
        return df
    hm = df["hm"]
    mask = hm.between(AM_OPEN, AM_CLOSE) | hm.between(PM_OPEN, PM_CLOSE)
    out = df.loc[mask].copy()
    out["ymd"] = out["ymd"].astype(str)
    return out.sort_values(["ymd", "hm"], kind="stable")
```

`PreparedMinutes` / `minute_coverage` / `evaluate_exit_modeb` / `oracle_exits` / `build_daily_equity` 仍走这条滤。pandas `between` 闭区间，与 `_in_session` 的 `>= AM_OPEN & <= AM_CLOSE` 同构。源中无 `930`/`1500`/`divmod`。

本核复现（同一实例买 100，T+1 10:00 high=106 close=103，末分钟 close=100；r2 N=1 X=5 Y=5）：

| 输入 `hm` | 含义 | `session_minutes` 行数 | 退出 |
|-----------|------|------------------------|------|
| 570 / 600 / 690 / 780 / 900 | 湖 09:30 / 10:00 / 11:30 / 13:00 / 15:00 | 1 | （单根）保留 |
| 565 / 691 / 720 / 901 | 盘外 | **0** | — |
| 930 / 1000 / 1130 / 1300 / 1459 / 1500 | 旧 HHMM | **0** | — |
| 600 / 900 | 湖 10:00 / 15:00 | 2 | **`take_profit` @103，`sell_hm=600`** |
| 1000 / 1459 | 测试用 HHMM | **0** | **`mark_end` @100，`sell_hm=None`，`is_trade=False`** |
| coverage 570+900 | 湖开收 | | `covered_codes=1` |
| coverage 930+1500 | HHMM | | `covered_codes=0` |

与上一轮表对调：生产单位成交，HHMM 不再假绿。`test_session_minutes_matches_production_annotation` 用时钟推 `hour*60+minute`，`assert_frame_equal` 对 `csv_minute_backtest._annotate`，got=`[570, 600, 690, 780, 900]`。`test_legacy_hhmm_fixture_is_not_a_session_clock` 钉 `930/1000/1459/1500` → empty（双钟并集或 `divmod`「兼容」会红）。`test_lake_minutes_have_coverage_and_take_profit` 钉 `hm=600` 必须 TP、coverage counted。

其余 Mode B 向量（阈值/trailing/跌停/除权/净值/pipeline）已把 1000/1130/1459/1500 改成 600/660/690/840/890/899/900。仓内 `*modeb*` 仅防回退测仍出现 HHMM 字面量。

### 价域 / Q 锁（`hm` 已是 session 行）

| 场景 | 实现 | 单测 |
|------|------|------|
| 买 = none 日线 close | `load_none_bars` 把 `front_root` 指到 `dividend_type=none` | `test_none_root_and_pool` buy=10.5 |
| 同根 TP&SL → 先止损，成交=该分钟 close | rule2 先 `low<=cost*(1−Y%)` 再 `high>=cost*(1+X%)` | `(106,94,102)→stop_loss` @600 |
| 仅 TP / 仅 SL / 精确 5% | 同上 | `(106,99,102)` / `(102,94,97)` / `(105,99,101)` / `(101,95,98)` |
| trailing 用 close 不是 high；halt 冻 peak | 买日跳过；`peak=max(peak,close)`；缺分钟日不更新 | high=200/close=104 不在当日 trailing |
| T+1 买日整日不触发、不入 peak | 循环从 `buy_i+1` | `test_buy_day_unavailable_to_trigger_or_peak` |
| Q36 到期末日分钟；盘外忽略；无 K 顺延 | 最后一根 session 行；空日 continue | 565/720/901 忽略，690 到期 |
| Q36 不回退日线 close | 成交只用 minute close | 无日线 fill 分支 |
| Q7 触发分钟 close 跌停 → 当日 blocked，次日重评 | `_is_limit_down(close, prev)` 后 `blocked=True` | 10:00 跌停、14:00=840 收回仍不卖，次日 TP |
| 到期日末分钟跌停顺延 | n_expire 后跌停检查 | `test_limit_down_expiry_postpones`（900 跌停 → 890 到期） |
| Q37 反例 | r2 盘中 103 vs r1 末分钟 100 | 600 vs 899 |
| Q38 同日跌停分钟剔除、前后非跌停可候选 | oracle 不套全日 blocked | 110 在 600 或 660 |
| Q29=B 局部 shares/=k，不再整百 | 日初 `cost/peak/shares/mark` 缩放 | k=0.5/0.98/0.73；0.73 后 `shares%100 != 0` |
| Q33 只改期末 MTM | `mark_end_zero` 跳过末日 mtm | 历史 equity 逐日相等；`is_trade=False` |
| 引擎 ledger 只读 | 不调用改 shares | dummy pos shares 仍 10000 |

Mode A close-only 先 TP 后 SL。Mode B 先 SL 是 R3，没有回写 A。

### P1 / 报告 / E

- 窄网格：18 r2 + r1_n1 进排名，hold_end 不进 ranked，oracle/delist 锚线另挂。与 plan P1=A 点名族一致。本核 `iter_grid()` = 20 条、r2=18。
- `_validate_out_dir` 拒绝任何 path part `unified_exit_modea`。pipeline 测断言未创建 Mode A 目录；`sell_hm` 列存在且成交为 900。
- CLI HELP 含「模式 B」「窄网格」；默认目录 `backtest_output/unified_exit_modeb`。
- 切片 E：handoff `[ ] E · 宿主网格`；plan 头部「宿主 E 未执行」；PR body「不列为实现合入门」。未伪完成。

### 依赖（HEAD，无环，禁区未改）

```
run_unified_exit_modeb.py → unified_exit_modeb
  ├→ unified_exit_modea          # 装配/网格/报告形状/涨跌停；不改其文件
  ├→ csv_daily_loader.warmup_start
  ├→ csv_minute_backtest.load_minute_bars / MINUTE_LAKE_END
  │                         AM_OPEN/AM_CLOSE/PM_OPEN/PM_CLOSE   # 钟 SSOT
  ├→ exdiv_map.load_exdiv_ratios
  └→ data_root.resolve_period_root
csv_ledger.rescale_position      # 仅测试 import；生产路径不调用
```

---

## 违规 / 风险

### 上一轮 🔴 bug-1 — **关闭**

见上。生产 `hm=570–900` 可触发；HHMM 不再保绿。

### nit-1（文档）plan 页眉仍写「v1.1 docs-only；本 PR 不写 Mode B Python」

实现票已写 Python。实施进度行已补「A–D 已实现」，页眉第一句与 §0 代码块「本 PR：docs only」未改。不挡。

### nit-2（文档）提案 Q36/Q37 标题仍「实施 STOP，待人裁」

正文回答已是 **A**。标题与状态句不一致，后人会以为还要 STOP。不挡。

### nit-3（卫生）plan §3.1 Q38 写了两行；handoff 硬边界编号 9→12→13→10→11

重复与乱序。不挡。

### nit-4（计数）handoff 验证行仍写「合成 77 passed / CI 739」

本轮 Mode A+B 为 **80**；`580cca5` 的 Actions 原文是 **736** passed（不是 739）。不挡，合入后可顺手改。

### 观察（不升格）

| 项 | 说明 |
|----|------|
| 跌停用**触发分钟 close** 相对昨收，不是 low 触板 | 与 Q38「排除跌停分钟 close」同构。若要改用 low，须新开 Q。 |
| `ExitResult` 子类把 `shares: int` 覆成 `float` | 字段序仍对；除权后允许非整百。 |
| 半窗仍用 Mode A 写死的 20251023–20260404 / 20260407–20260909 | 与 Mode A 同；#90 nit，不重复升格。 |
| `load_minute_bars` 已 `_in_session`，Mode B 再用同一常量滤一次 | 冗余，防御旧 HHMM fixture / 脏 cache；不是双钟。 |
| 合成测 0 真实 symbol | 符合 R6。湖**单位**契约已补，不是真码。 |

---

## 建议动作（是否可合）

**可以合入 master。** nits 不阻断。不要让本核 merge。

合入后可顺手（非门）：

1. plan 页眉去掉 docs-only / 「不写 Mode B Python」；§0 代码块改成「本 PR：A–D 已实现」。
2. 提案 Q36/Q37 标题去掉「待人裁」。
3. handoff 验证行改 80 / 以 Actions 原文为准；编号理顺。
4. 切片 E 继续空着，直到用真 cache 跑通覆盖率 ≠ 0。

本核 **未 merge、未改业务代码**；仅覆盖落本评审文件。

---

## 核验命令（本核已跑）

```text
git fetch origin
git rev-parse HEAD
# = 9c39c90d3567565a8f6c092426499316b42aa981
git merge-base origin/master HEAD
# = 55bfe4a3cb3219c11baa95d9c314206fad52ecd2
git diff --name-status origin/master...HEAD
# 12 files；无 csv_ledger / unified_exit_modea / csv_minute_backtest
git diff --name-status 7950865..9c39c90
# 5 files：modeb.py + 四测
gh pr view 95 --json mergeable,mergeStateStatus,headRefOid,statusCheckRollup
# MERGEABLE / CLEAN / head = 9c39c90 / pytest-and-gates SUCCESS
# Actions 35202921314 @ 9c39c90：739 passed, 5 skipped, 24 deselected
# Actions 35198836728 @ 580cca5：736 passed, 5 skipped, 24 deselected
# 本核 vanna312 = /workspace/vanna312/bin/python：
#   AM_OPEN,AM_CLOSE,PM_OPEN,PM_CLOSE = (570, 690, 780, 900)
#   session_minutes(hm=570/600/690/780/900) → 1 行
#   session_minutes(hm=930/1000/1130/1300/1459/1500) → 0 行
#   evaluate_exit_modeb hm=600/900 → take_profit 103 sell_hm=600
#   evaluate_exit_modeb hm=1000/1459 → mark_end 100 sell_hm=None
#   minute_coverage 570+900 → 1；930+1500 → 0
#   session_minutes 源无 930/1500/divmod；与 _annotate 帧相等
#   Mode A + Mode B 合成 80 passed / 1.58s
#   全套 -m "not production and not benchmark"：742 passed, 2 skipped, 24 deselected
#   四门禁 OK
# UTF-8：12 文件 BOM=false NUL=0 CR=0
# rescale_position：shares untouched (X-R1)
# iter_grid：20 条 / r2=18
```

真湖分钟网格 / 切片 E **未**跑（非合入门）。
