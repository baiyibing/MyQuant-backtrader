# PR #92 Mode A perf + r3 plateau — Grok 核评审

> 日期：2026-09-17
> 角色：MyQuant-backtrader Grok 核（独立 grok CLI；只审不合入）
> 对象：[PR #92](https://github.com/baiyibing/MyQuant-backtrader/pull/92) `feat/unified-exit-modea-perf`（`origin/feat/unified-exit-modea-perf` vs merge-base `origin/master` @ `835cc63`）
> 权威：[handoff-unified-exit-modea-perf-codex-impl-2026-09-17.md](../../../../backtest/handoff-unified-exit-modea-perf-codex-impl-2026-09-17.md) · 宿主短记 [`unified-exit-modea-host-note-2026-09-17.md`](../../../../backtest/unified-exit-modea-host-note-2026-09-17.md) §4（`origin/master` / PR #91）· **人裁**：plateau **只补 r3**，r1 继续跳过；**不改 handoff md**
> HEAD：`c087aec3db28a9da16194e69f1fd23fdde6de576`
> merge-base：`835cc63325c2a7cee62e285de237efb8e65fcff7`（PR 开出时的 master；现 `origin/master` = `b6f2a78` / #91，文件不相交）
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**（[run 35191778669](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35191778669)）
> 工作树：`/workspace/MyQuant-backtrader-modea-perf`
> 本核 **未 merge**。

---

## 结论

**GO-WITH-NITS**（**可合**；nits 不阻断合入，不改成交核 / 引擎 / 策略书 / Mode B。本核不 merge）。

对照交接硬边界、宿主短记 §4、人裁「只补 r3 / r1 仍跳过 / 不改 handoff」：这是一次 scoped 的 Mode A 报告侧补洞 + 热循环缓存。`de65151` 把 `neighborhood_plateau_flags` 的入口从 `r2_` 扩到 `r2_`/`r3_`，r3 按「无 X、有限 Y + N」走与 r2 同一套 endswith/`_y{}_`/`[:8]` 族；r1 仍 `continue`。`c087aec` 用 `DatetimeIndex.strftime` 一次建 close/prev/open 映射，运行内懒缓存、不写 DataFrame attrs、不留全局。合成路径 ranking / summary / instance_detail **逐字节**等于标量 `date_to_ymd` 对照。半窗仍重放净值（不复用全窗增量），浮点顺序保留。禁区文件不在 diff。handoff 在实施 commit 中零改。

剩余是死函数 `_prev_close_on` 与 open 映射未走同一 helper，不挡合入。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#92 fix/perf(modea): cover r3 plateau and cache vectorized bar maps](https://github.com/baiyibing/MyQuant-backtrader/pull/92) |
| 比较 | `origin/master...HEAD` 三-dot = merge-base `835cc63`..`c087aec`（3 files, +226 / −22） |
| 交接 docs | `05d2f5b` 新增 handoff（实施 commit **未再改**） |
| **A** `de65151` | plateau 覆盖 `r3_y*_n*`；r1 跳过；r2 规则保持 |
| **B** `c087aec` | 向量化 bar 日期 + 运行内 close/prev/open 缓存 |
| 相对现 `origin/master` | master 已合 #91 宿主短记；与本 PR **文件交集为空**，GitHub `MERGEABLE` |

新代码落点符合交接：`backtest/research/unified_exit_modea.py` + `tests/test_unified_exit_modea_aggregate.py`。CLI `scripts/research/run_unified_exit_modea.py` 零改。assemble / exit 单测文件未动（行为由既有 9+15 测钉住）。

---

## 证据表

| 锁 / 裁点 | 结果 | 证据 |
|-----------|------|------|
| **硬边界** 只动 Mode A 库 + 对应测试；禁区一行不碰 | **PASS** | vs master 3 文件：`unified_exit_modea.py` / `test_unified_exit_modea_aggregate.py` / handoff md。无 `csv_ledger.py` / `csv_simulate_loop.py` / `csv_daily_backtest.py` / `csv_minute_backtest.py` / `csv_minute_backtest_v7.py`（仅既有惰性日历 import）/ `*_rules.py` / `csv_strategy_books.py`。CLI 不在 diff。AST 顶层仍 `csv_daily_loader` / `csv_pool` / `market_layer` / `data_root`。无成交核 / Cerebro / Mode B。 |
| **人裁 / 宿主 §4** plateau **只补 r3**；r1 继续跳过 | **PASS** | `startswith(("r2_", "r3_"))`；注释与解析 `else: x_s="inf"`。`test_plateau_r3_top20_island_and_r1_skipped`：16 个 r1 占满 top16 → `[]`；默认 top20 才扫到 r3，且 `all(label startswith r3_)`。本核混合 ranked（含 `r1_n20`）→ r1 行数为 0。 |
| **r3 邻域与 r2 同构** | **PASS** | 见下节。族过滤 `startswith(parts[0]+"_")`：r2 仍只扫 r2。r3 无 X（`x is None`），有限 Y + 精确 N；`yinf` 不进 Y 族（与 r2 `xinf/yinf` 同一）。`endswith(_n{n})` 不吃 `_n10`。跨规则 r2/r3 隔离。`[:8]` 仍按 ranked 序截断。本核：旧 r2-only 算法 vs HEAD **逐字段同一**；r3 vs `r2_xinf_y*_n*` 孪生 **gap/island 同一**。 |
| **r2 既有规则不回归** | **PASS** | r2 解析分支原文：`x_s,y_s,n_s = parts[1:]`。单测 `r2_x5_y10_n1` 同 X / 同 Y / 同 N 三案。旧算法对照 5 个 r2 标签 island/gap 全等。 |
| **不改 handoff md** | **PASS** | `git diff 05d2f5b HEAD -- docs/backtest/handoff-unified-exit-modea-perf-codex-impl-2026-09-17.md` 空。落地说明在 PR body（「性能票落地；Mode B 仍另开」）。交接正文仍写 `r1_n*` 扩解析——人裁冻结原文，不升格。 |
| **向量化/缓存不改 ranking 语义** | **PASS** | `_bar_close_map`：`DatetimeIndex.strftime("%Y%m%d")` + `dict(zip)` 后写覆盖，与标量 `date_to_ymd` 后写同一。`previous()` = `sorted(closes)` 邻项，与旧 `evaluate_exit` / `_prev_close_on` 同构（跨停牌=序列上一根，非日历-1）。`test_vectorized_close_map_matches_scalar_dates`（datetime/date/tz、乱序重复、空表）。`test_run_cache_exact_outputs_and_freshness`：`ranking.csv` / `summary.json` / `instance_detail_top.csv` **逐字节**等于标量对照；源 frame 不变、`attrs=={}`；每 run 每票 close_map **一次**；就地改 close 后新 run 重建且 summary 变化。本核：naive/date/tz 键相等；halt+乱序+重复 last-wins 下 `previous()==_prev_close_on`。半窗仍 `aggregate_strategy` 重放子集净值，不复用全窗增量。 |
| **A/B 退出/装配语义** | **PASS（未改求值器正文）** | `evaluate_exit` / `iter_grid` / `StrategySpec.label` / 网格 8+252+20 不在 plateau 逻辑里。exit 只换 close/prev 取值来源。assemble 封板改走 `bars.previous`（算法同 `_prev_close_on`）。`test_prev_close_crosses_suspension` 仍绿。close-only 框 `evaluate_exit` r1_n1 → `n_expire 20251104 10.3`（opens 懒建，不碰缺 open 列）。 |
| **UTF-8 / 门禁 / pytest** | **PASS** | 本 diff 三文件 BOM=false、NUL=0；`git diff --check` 空。本核 vanna312：Mode A 三文件 **47 passed / 0.72s**。GitHub Actions [`35191778669`](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35191778669) @ `c087aec`：`705 passed, 5 skipped, 24 deselected, 3 warnings / 20.04s`。`verify_no_hardcoded_machine_paths` / `verify_data_path_ssot` / `verify_oskh_data_contract` OK。 |

### r3 ↔ r2 同构（本核）

`neighborhood_plateau_flags` 对 r3 设 `x_s="inf"`，因此：

| 族条件 | r2 | r3 |
|--------|----|----|
| 同规则前缀 | `r2_` | `r3_` |
| 精确 N | `endswith("_n{n}")` | 同 |
| 有限 X | `_x{_fmt_grid(x)}_` in label | **永不**（无 X） |
| 有限 Y | `_y{_fmt_grid(y)}_` | 同 |
| `inf` 不当轴 | `x/y is None` 跳过该轴 | 同（r3 的 X 恒 None） |
| 扫描帽 | ranked 族 `[:8]` | 同 |
| 孤峰 | `gap > 0.01` | 同 |
| 空族 | `island=False, gap=0.0` | 同 |

参数化单测钉：同 N、同有限 Y、`yinf` 不连、`_n1` 不吃 `_n10`、r2/r3 分家、r2 既有 X/Y/N。`test_plateau_scans_only_first_eight_ranked_family_members` 把更好的第 9 名放在帽外 → 仍 island（与 r2 启发式宽度同一，不是 1-step 网格邻接；#90 已接受）。

生产网格 r3 = 5 Y × 4 N = 20 格，全 280 ranked 下同 N 必有 4 个兄弟，空族不会在真跑出现。宿主 top20 #17 `r3_y10_n10` 现在会进 plateau 行。

### 缓存形状（HEAD）

```
run_modea
  └─ _prepare_bars(bar_map)          # 一次；isinstance 命中后不套娃
       ├─ assemble_instances.closes / previous
       ├─ evaluate_matrix → evaluate_exit.closes / previous
       ├─ build_daily_equity.closes     # 主网格 + 半窗 + 锚线
       ├─ oracle_exits.closes / previous
       └─ next_open_buy_instances.opens
```

`_PreparedBars` 是 run-local dict 子类：浅拷贝 frame 引用，映射按票懒建。新 `run_modea` 新 wrapper → 就地改输入可见。不写 `df.attrs`、无模块级 cache。`date_to_ymd` 仍服务日历注入，已离开价格热循环。

### 依赖（HEAD，无环，禁区未改）

```
run_unified_exit_modea.py → unified_exit_modea   # CLI 本 PR 零改
  ├→ csv_daily_loader._read_one_daily / warmup_start
  ├→ csv_pool.parse_pool_csv_entries
  ├→ market_layer.limit_pct / board_limit_pct
  ├→ common.infra.data_root.resolve_period_root
  └→ csv_minute_backtest_v7.load_index_daily   # 惰性，仅生产日历
```

---

## 违规 / 风险

无 🔴。无合入阻断。硬边界未破。人裁未破。

### nit-1（卫生）`_prev_close_on` 已无调用方

assemble 改走 `bars.previous(symbol).get(ymd)` 后，`_prev_close_on` 只剩定义。算法仍与 `previous()` 同构（本核 halt/乱序/重复 last-wins 对照相等），不改语义。合入后可删，避免两套入口日后分叉。**不必为此 BLOCK。**

### nit-2（缓存宽度）`opens()` 自己再 `strftime` 一遍，不走 `_bar_close_map`

close 映射有 monkeypatch 计数；open 映射同算法但独立建 ymd 键。`summary.json` 的次日开盘敏感性已在逐字节对照里，语义无分叉。真湖上每票多一次日期向量化，相对 72min 可忽略。可选：共享一次 ymd 数组。

### nit-3（交接原文）handoff 切片 A 仍写 `r1_n*` 扩解析

人裁明确不改该 md。实施按「只补 r3、r1 跳过」落地，PR body 已声明。后人读交接步骤 1 会看到 `r1_n*`——以人裁 / 本文件 / 代码为准。

### 观察（不升格）

| 项 | 说明 |
|----|------|
| 半窗净值 | 交接「若」复用主聚合增量；本票只复用行情映射、子集仍重放。对位级 `total_return`/`max_drawdown` 更稳，符合「遇语义分叉停下」。 |
| 空族 r3 | 若 ranked 里没有同 N/同有限 Y 的其他 r3，gap=0 且不报孤峰——与 r2 空族同一。全网格不会发生。 |
| 族是 OR 不是 1-step | 同 Y 的远 N 仍进 family。#90 已接受；本票未加宽也未收窄。 |
| PR 宣称 20.6× | 230 合成日 / 3 票 / 60 实例：10.33s→0.50s。本核未复跑该墙钟，也未跑真湖 72min（非合入门）。 |
| `_PreparedBars` 子类 dict | 替换 wrapper 内某 key 不会自动失效已建 map；`run_modea` 不做这种替换。测试钉的是新 run 新 wrapper。 |
| #91 宿主短记 | 本分支 merge-base 在 #91 之前；GitHub 对现 master `MERGEABLE`。本核从 `origin/master` 读 §4。 |

---

## 建议动作（是否可合）

**可以合入 master。** 不要为 nit-1…3 重开切片，也不要顺手改成交核 / 策略书 / Mode B。

合入后（非本 PR）：

1. 可删 `_prev_close_on`（nit-1）。
2. 真湖网格仍宿主-only；本票不承诺把 72min 压到分钟级，只把热点移出 Python 逐元素 `date_to_ymd`。
3. Mode B 另开。
4. 不要回头改 handoff 去补 `r1_n*` 或把 r1 加进 plateau。

本核 **未 merge、未改业务代码**；仅落本评审文件。

---

## 核验命令（本核已跑）

```text
git fetch origin
git merge-base origin/master HEAD
# = 835cc63325c2a7cee62e285de237efb8e65fcff7
git rev-parse HEAD
# = c087aec3db28a9da16194e69f1fd23fdde6de576
git diff --name-status origin/master...HEAD
# M unified_exit_modea.py
# A handoff-unified-exit-modea-perf-codex-impl-2026-09-17.md
# M test_unified_exit_modea_aggregate.py
git diff 05d2f5b HEAD -- docs/backtest/handoff-unified-exit-modea-perf-codex-impl-2026-09-17.md
# empty
gh pr view 92 --json mergeable,mergeStateStatus,headRefOid,statusCheckRollup
# MERGEABLE / CLEAN / head = c087aec / pytest-and-gates SUCCESS
gh run view 35191778669
# 705 passed, 5 skipped, 24 deselected, 3 warnings / 20.04s
/workspace/vanna312/bin/python -m pytest -q \
  tests/test_unified_exit_modea_assemble.py \
  tests/test_unified_exit_modea_exit.py \
  tests/test_unified_exit_modea_aggregate.py
# 47 passed in 0.72s
/workspace/vanna312/bin/python scripts/gates/verify_no_hardcoded_machine_paths.py
/workspace/vanna312/bin/python scripts/gates/verify_data_path_ssot.py
/workspace/vanna312/bin/python scripts/gates/verify_oskh_data_contract.py
# 旧 r2-only plateau vs HEAD r2 行：identical
# r3 vs r2_xinf 孪生：gap/island identical
# date_to_ymd vs DatetimeIndex.strftime：naive/date/tz 键相等
# previous() == _prev_close_on（halt + 乱序重复 last-wins）
```

真数据网格 / 72min 墙钟 **未**跑（非合入门，本环境无 F 湖）。
