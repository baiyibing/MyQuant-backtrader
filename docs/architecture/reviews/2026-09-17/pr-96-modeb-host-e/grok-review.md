# PR #96 统一卖出规则网格 · 模式 B 切片 E 宿主业务 runbook — Grok 核评审

> 日期：2026-09-17
> 角色：MyQuant-backtrader Grok 核（独立 grok CLI；只审不合入）
> 对象：[PR #96](https://github.com/baiyibing/MyQuant-backtrader/pull/96) `docs/modeb-host-e`（tip `90b8b74` vs `origin/master`）
> 权威：[plan-unified-exit-modeb-2026-09-17.md](../../../../backtest/plan-unified-exit-modeb-2026-09-17.md) P1=A / P2=A / Q36–Q38 / cache · [unified_exit_modeb.py](../../../../../backtest/research/unified_exit_modeb.py) `iter_grid` / argparse / warmup · Mode A [host-runbook](../../../../backtest/host-runbook-unified-exit-modea-2026-09-17.md) / [host-note](../../../../backtest/unified-exit-modea-host-note-2026-09-17.md) · [分钟就绪短记](../../../../backtest/unified-exit-modeb-minute-ready-2026-09-17.md) cache key `minute_none_20251013_20260909`
> HEAD：`90b8b748bb01d765152206503da7c872141ee7e3`
> parent / merge-base：`8db98deef41404e4ddf3d59b4105afda6c85d0c0`（= `origin/master` = PR #95 merge）
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**（[run 35206679026](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35206679026)）
> 工作树：`/workspace/MyQuant-backtrader-modeb-e`（分支 `docs/modeb-host-e`）
> 本核 **未 merge**。本结论 **不是** Mode B 网格完成，也 **不是** 实现合入门。

---

## 结论

**GO-WITH-NITS**（**docs PR 可合**；nits 不阻断合入，不写 Mode B Python、不改引擎、不跑业务网格、不勾选 E。本核不 merge）。

这是合格的切片 E 施工图：相对已合 #95 只动 6 份 Markdown（+189/−15），零 Python / 零成交核。业务 runbook 把 P1=A 钉成 `iter_grid` 同构的 18 r2 + 四锚（20 项 / 22 标签 / 排名 19 行）；cache 沿用 warmup 超集 `minute_none_20251013_20260909`，禁止重建字面 `20251023`；E 标 host-only、短记保持 ⏳ TBD；Q36/Q37/Q38 与 P4 不混排写对；优先高配/4090、分钟 OHLCV 不用 Redis。剩余是 smoke 正文仍留旧 `20251023` 示例、handoff「可与编码并行」过期句——不挡合入。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#96 docs(backtest): Mode B slice E host runbook (narrow grid)](https://github.com/baiyibing/MyQuant-backtrader/pull/96) |
| 比较 | `8db98de..90b8b74`（6 files, +189 / −15） |
| 前置 | PR #95 **MERGED** @ `8db98de`（A–D 实现；E 未勾） |
| E | 本 PR：业务 runbook + 待回填短记模板；plan / handoff / smoke / README 入口 |
| 代码 | **零**。无 `.py` / `.rs` / CI YAML |

`git diff --name-status origin/master...HEAD`（评审对象 tip；不含本文件）：

```
M  docs/backtest/README.md
M  docs/backtest/handoff-unified-exit-modeb-codex-impl-2026-09-17.md
A  docs/backtest/host-runbook-unified-exit-modeb-2026-09-17.md
M  docs/backtest/host-runbook-unified-exit-modeb-smoke-2026-09-17.md
M  docs/backtest/plan-unified-exit-modeb-2026-09-17.md
A  docs/backtest/unified-exit-modeb-host-note-2026-09-17.md
```

禁区文件不在列。GitHub PR files 与 tip 一致。CI [`35206679026`](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35206679026) SUCCESS @ `90b8b74`：**739** passed, 5 skipped, 24 deselected（与 #95 合入后 master 同口径）。`backtest_output/` gitignored；数字产物未入库。

---

## 证据表

| 锁 / 裁点 | 结果 | 证据 |
|-----------|------|------|
| **1 范围** docs-only；无 Python / 测试 | **PASS** | 6 md +189/−15。无 `.py` / `.rs` / YAML。`unified_exit_modeb.py` / CLI / 四测 / `csv_ledger` / `csv_minute_backtest` / Mode A **未动**。`git merge-base --is-ancestor 8db98de HEAD` = 0。 |
| **2 无发明 B 指标** 短记全 TBD | **PASS** | 短记页眉 ⏳、全部实测格 TBD；明确「空白模板，不是 E 完成记录」。runbook 只引用 A 短记 +1.50% / −24.36% / +129.64% / 4167 / 904 lots 作**基线**，并钉「不是 B 预期值或通过门槛」。无伪造墙钟 / NAV / 覆盖率。 |
| **3 E host-only** 非 CI 合入门；短记 ⏳ | **PASS** | runbook §0「E = host-only，非 CI / 实现合入门；本 docs PR 不跑湖、不勾选 E」。plan 头部 ⏳ 宿主 E 未执行；handoff `[ ] E`；短记两勾未勾 + 「本 docs PR 不勾选」。README「宿主 E 待跑」。 |
| **4 cache key** `20251013` warmup 超集，不重建 `20251023` | **PASS** | 见下节。`WARMUP_DAYS=10` → `warmup_start("20251023")="20251013"`。`load_monitor_bars` 把 warmup 起点传进 `load_minute_bars`。runbook / 短记 / smoke §3 均钉现成 `minute_none_20251013_20260909`。 |
| **5 P1=A 网格** 18 r2 + 锚，与代码同构 | **PASS** | 本核 `iter_grid()` = 20：r2=18（X∈{5,7,10} × Y∈{5,10,None} × N∈{8,10}）+ `anchor_hold_end` + `r1_n1`。`run_modeb` 再挂 `oracle`/`delist_zero` → 22 标签；`ranked` 排除 hold/oracle/delist → **19**；stdout `n_strategies=len(ranked)`。runbook 表与此逐项对齐；明确不沿用 smoke「~24 组」、不套 A 的 280/233。 |
| **6 Q36/Q37/Q38 + P4** 不混排 | **PASS** | Q36：末 session 分钟 close；无 K 顺延；不回退日线（对照 `evaluate_exit_modeb` 空日 continue、成交只用 minute close）。Q37：不要求 r2 N=1 ≡ r1；默认窄网格不含 r2 N=1；勿抄 A 的 42/42。Q38：oracle 仅排除跌停分钟 close。P4：独立目录 `unified_exit_modeb/`；`_validate_out_dir` 拒 `unified_exit_modea`；A/B 不进同一 NAV/收益率表。 |
| **7 机器** 优先高配/4090；分钟 OHLCV 无 Redis | **PASS** | P2=A：业务网格优先 ~128G / 4090；40G 只用于已完成 smoke，不承诺业务耗时。4090 = 机器选择，CLI 无 GPU 开关（argparse 无 full-grid / GPU / rebuild-cache）。分钟走 `bar_cache` 驻留进程内存，**不用 Redis**。库源无 redis。 |
| **UTF-8 / 门禁** | **PASS** | 6 md BOM=false、NUL=0、CR=0、UTF-8、LF 结尾。`git diff --check` 空。相对链接均可解析（含 `../../backtest/research/unified_exit_modeb.py`）。 |

本核 **未**跑真湖分钟网格（无 F 湖，与 #91/#94 同）。数字核验走文档自洽 + 对照 plan / `iter_grid` / argparse / `warmup_start`，不冒充宿主复跑。

### P1=A 网格（本核手算 / 跑 `iter_grid`）

plan P1=A：`r2` × X∈{5,7,10} × Y∈{5,10,∞} × N∈{8,10} = **3×3×2 = 18**，另加四锚。

| 口径 | 代码 | runbook / 短记 |
|------|------|----------------|
| `iter_grid` | 20（hold_end + r1_n1 + 18 r2） | 20 项 |
| 运行矩阵 | + oracle + delist_zero = 22 标签 | 22 个标签 |
| 排名 | 18 r2 + r1_n1 = 19；hold 不进 ranked | stdout `n_strategies=19`；排名 19 行 |
| 四锚 | hold_end / r1_n1 / oracle / delist_zero | 同；r1_n1 兼排名与锚，不重复算新组 |
| CLI | `--start/--end/--pool-dir/--none-root/--cache-dir/--out-dir/--tol/--workers`（默认 8） | 命令与可选参数同构 |

∞ = `y is None` → 标签 `yinf`。不沿用 #94 nit-1 的「冠军族 ~24」。

### warmup cache key

```text
WARMUP_DAYS = 10
warmup_start("20251023") = "20251013"
load_monitor_bars(codes, start, end) → load_minute_bars(..., warmup_start(start, days=10), end, use_cache=True)
minute_cache_path → minute_none_{start}_{end}.parquet
```

故现成 `minute_none_20251013_20260909` 是 **引擎默认 warmup 口径**（#94 已核：窗口 ⊇ 业务窗）。runbook 热检查走 `load_monitor_bars(..., '20251023', '20260909')`，会命中该 key；**不要重建字面 `20251023`**。默认 CLI 不传 `--cache-dir` → `CACHE_ROOT=backtest_output/bar_cache`。

### 相对 Mode A 模板

| Mode A（#91 已填） | 本票 E |
|--------------------|--------|
| runbook 状态 ✅ 已完成 | ⏳ 宿主未跑 / 待切片 E |
| 短记填真实数字 | 模板全 TBD；完成勾未勾 |
| 四类产物（文案） | 三文件：`ranking.csv` / `instance_detail_top.csv`（含 `sell_hm`）/ `summary.json`（robustness 在内）——与 `write_reports` 一致 |
| N=1 42/42 等价 | B 明确不要 |

A 的 5061 / 4167 / 2080 / 795+99 写成比较基线，并声明 B 买入是 none close、不强制对齐 4167——符合价域差。

---

## 违规 / 风险

无 🔴。无合入阻断。硬边界未破。Mode B 网格 **未**跑、也未声称已跑。

### nit-1（卫生）smoke 正文仍写字面 `20251023` 产物

本票只改 smoke §3 时间线，正确钉「沿用 `minute_none_20251013_20260909`，不重建本篇旧示例的字面 `20251023`」。§0 / §1.2 完成表仍写 `minute_none_20251023_20260909.parquet`。E runbook 才是操作 SSOT，不挡。合入后把 smoke 产物行改成「现成 warmup 超集 20251013，见短记 §2」即可。**不要为改这一句重建 cache。**

### nit-2（过期句）handoff §5 仍写「可与编码并行」

本票已把 §5 第一枪改成链 E runbook / 待回填短记，第三枪仍是「数据就绪步骤见 smoke runbook（可与编码并行…）」。A–D 已合 #95，编码闸已关。不挡。

### nit-3（页眉债）plan 仍写「v1.1 docs-only；本 PR 不写 Mode B Python」

实施进度行已补「A–D 已合 #95；⏳ 宿主 E」。页眉第一句与 §0「本 PR：docs only（plan + handoff + 可选宿主分钟就绪 runbook）」未改——#95 nit-1 残留；对本 E 票碰巧仍是 docs-only，但「可选 smoke」已过时。不挡。

### 观察（不升格）

| 项 | 说明 |
|----|------|
| handoff 验证行仍「合成 77 / CI 739」 | #95 nit-4：Mode A+B 实为 80；Actions 原文 739。本票未改，正确不扩 scope。 |
| plan §3.1 Q38 两行 | #95 nit-3。不挡。 |
| P2=A 原文「窄网格可先宿主」 | runbook 收成「40G 只用于 smoke、业务优先 128G/4090」，比 plan 更严，符合「prefer 高配」硬条，不是违约。 |
| CLI `--workers` 默认 8 vs `load_monitor_bars` 签名默认 16 | 业务路径 `run_modeb` 传入 8；热检查 snippet 不传 workers → 16。只影响预检读线程，不改 cache key。 |
| README 命令块 | #95 已有 `run_unified_exit_modeb.py`；本票只改 SSOT 表一行。正确。 |

---

## 建议动作（是否可合）

**可以合。** 不要为 nit-1…3 改引擎，也不要在本票回填 TBD 或勾选 E。

合入后（宿主 / 另票，非本 PR）：

1. 按 E runbook 在高配/4090 跑默认窄网格；复用 `minute_none_20251013_20260909`；回填短记后再勾 E。
2. （可选）smoke §0/§1.2 产物行改成 20251013；handoff 去掉「可与编码并行」；plan 页眉去掉过期 docs-only 句。
3. 数字产物继续不入库。

本核 **未 merge、未改业务代码**；仅落本评审文件。

---

## 核验命令（本核已跑）

```text
git fetch origin
git rev-parse HEAD
# = 90b8b748bb01d765152206503da7c872141ee7e3
git merge-base origin/master HEAD
# = 8db98deef41404e4ddf3d59b4105afda6c85d0c0  (= origin/master = PR #95 merge)
git merge-base --is-ancestor 8db98de HEAD   # exit 0
git diff --name-status origin/master...HEAD
# 6 md；无 .py / .rs / YAML
gh pr view 96 --json mergeable,mergeStateStatus,headRefOid,statusCheckRollup
# MERGEABLE / CLEAN / head = 90b8b74 / pytest-and-gates SUCCESS
gh run view 35206679026
# SUCCESS @ 90b8b74；739 passed, 5 skipped, 24 deselected
# UTF-8：6 md BOM=false NUL=0 CR=0 LF 结尾；git diff --check 空
# warmup_start(20251023, days=10) = 20251013
# iter_grid() = 20；r2=18；X={5,7,10} Y={5,10,None} N={8,10}
# argparse：无 full-grid / GPU / rebuild-cache / Redis
# DEFAULT_START/END = 20251023/20260909；CASH_POOL=1.1e9；COMMISSION=0.001
```

真湖分钟业务网格 / 切片 E **未**跑（本 PR 无实现变更；非合入门复验项）。
