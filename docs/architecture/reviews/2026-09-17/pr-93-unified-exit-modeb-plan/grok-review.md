# PR #93 统一卖出规则网格 · 模式 B plan + handoff（待人裁 GO）— Grok 核评审

> 日期：2026-09-17
> 角色：MyQuant-backtrader Grok 核（独立 grok CLI；只审不合入）
> 对象：[PR #93](https://github.com/baiyibing/MyQuant-backtrader/pull/93) `docs/unified-exit-modeb-plan-2026-09-17`（tip `0608e62` vs `origin/master`）
> 权威：[stock-backtest-unified-exit-proposal-2026-09-17.md](../../../../backtest/stock-backtest-unified-exit-proposal-2026-09-17.md)（Q2/Q3/Q8/Q20/Q21/Q29 锁）· Mode A 宿主短记 [unified-exit-modea-host-note-2026-09-17.md](../../../../backtest/unified-exit-modea-host-note-2026-09-17.md) §5 · [workflow-codex-handoff.md](../../../../backtest/workflow-codex-handoff.md)
> HEAD：`0608e6230306b7bc531ce8d0a7bd5ce626dbf6f2`
> merge-base / parent：`e018924b3088887cbaa0be690f2a731e1bfb348e`（= `origin/master`，含 Mode A + perf #92）
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**（[run 35193898759](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35193898759)）
> 工作树：`/workspace/MyQuant-backtrader`（分支 `docs/unified-exit-modeb-plan-2026-09-17`）
> 本核 **未 merge**。本结论 **不是** Mode B 实施 GO。

---

## 结论

**GO-WITH-NITS**（**docs PR 可合**；nits 不阻断合入，不改提案正文、不写 Mode B Python、不改引擎 `rescale_position`。本核不 merge）。

这是合格的 docs-only 施工图：状态行是 ⏳ **待人裁 GO**，plan / handoff / README 三处禁编码，smoke runbook 明确「无需 Mode B 代码 / 不是网格结果」。R1–R4 与提案 Q2/Q3/Q8/Q20/Q21/Q29 同构：none 日收买、1m high/low 触发、分钟 close 成交、同根先止损、E-R6+`shares/=k` 仅本网格、引擎 ledger 只读。P1–P5 建议默认合理；切片 A–D 合入门、E 宿主业务网格、分钟 smoke 三者分开。剩余是 4167 **实例**被写成「码」、跌停「或该分钟」未锁、P1=A 未点名冠军族——给人裁/开工时看，不挡本票合入。

**人裁 P1–P5 之前仍禁止编码。** 合本 PR ≠ 实施 GO。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#93 docs(backtest): Mode B unified-exit plan + handoff (awaiting human GO)](https://github.com/baiyibing/MyQuant-backtrader/pull/93) |
| 比较 | `e018924..0608e62`（4 files, +402 / −0） |
| plan | `docs/backtest/plan-unified-exit-modeb-2026-09-17.md` v1.0 |
| 交接草稿 | `handoff-unified-exit-modeb-codex-impl-2026-09-17.md`（开工闸：plan 未 ✅ 已人裁 GO 则勿开工） |
| 分钟就绪 | `host-runbook-unified-exit-modeb-smoke-2026-09-17.md`（数据就绪；非 Mode B 网格） |
| README | 入口注释 + SSOT 表一行；**无** `run_unified_exit_modeb.py` 命令 |
| 代码 | **零**。无 `.py` / `.rs` / CI YAML |

`git diff --name-status origin/master...HEAD`：

```
M  docs/backtest/README.md
A  docs/backtest/handoff-unified-exit-modeb-codex-impl-2026-09-17.md
A  docs/backtest/host-runbook-unified-exit-modeb-smoke-2026-09-17.md
A  docs/backtest/plan-unified-exit-modeb-2026-09-17.md
```

禁区文件不在列。GitHub PR files 与 tip 一致。CI [`35193898759`](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35193898759) SUCCESS @ `0608e62`。

---

## 证据表

| 锁 / 裁点 | 结果 | 证据 |
|-----------|------|------|
| **1 状态 / 禁编码** ⏳ 待人裁 GO；GO 前禁止写 Mode B Python | **PASS** | plan 头部「待人裁 GO（P1–P5 未裁；GO 前禁止编码）」；非目标末行「在本 docs PR 或未 GO 的 feat 分支写 Mode B Python」；handoff ⛔「do not start Codex coding until plan header says 已人裁 GO」+「随 docs PR 先合 master 仍禁止开工」；README「待人裁 GO — 见 plan，勿编码」。无 CLI 命令块。P\* 表「未裁 = 禁止编码」。 |
| **2 R\* = 提案价域** none 日买 + 1m high/low 触发 + 分钟 close 成交 | **PASS** | 见下节 Q2/Q3/Q20。plan 一句话 / R2 / §8 与提案 §一、§四 Mode B 行同构。禁止 front 日线与 none 分钟混用同一判定链。 |
| **2 同根先止损** Q8 | **PASS** | R3；handoff B.3；提案「只在模式 B 会发生」。Mode A close-only 标明死规则，不回写 A。 |
| **2 E-R6+shares/=k 仅本网格；不改 `rescale_position`** Q21/Q29 | **PASS** | R1/R4；非目标「改引擎 rescale 使 shares/=k」；切片 C「断言引擎未被改」；handoff 锚 `csv_ledger.py:157-166` docstring「shares untouched (X-R1)」。现函数只 `cost*=k; peak*=k`。 |
| **3 P\* 建议默认** | **PASS** | P1=A 窄网格（×240 先证盘中边际）；P2=A 宿主 smoke 再 4090（对齐宿主短记 §5）；P3=A 现成 `load_exdiv_ratios`（Q29=B）；P4 升格为锁（A/B 永不混排）；P5 烟测现在可做、业务网格等 GO+impl。 |
| **3 切片 A–E + 烟测 ≠ 全网格** | **PASS** | A 装载 / B 求值器 / C 除权 / D 聚合 CLI = 实现合入门；**E 宿主窄或全网格 = 非合入门**；smoke = cache+覆盖+墙钟，**不跑业务网格**。P1=B 全 280 只在 E 且须人裁。 |
| **4 分钟 smoke 不声称 Mode B 已实现** | **PASS** | 标题「无需 Mode B 代码」；§0「不跑 Mode B 业务网格；不写 `unified_exit_modeb.py`」；完成表「Mode B 网格排名 ❌ 不在本 runbook 范围」；§3 时间线：现在 smoke → 人裁 GO → 实现 A–D → 之后窄/全网格。 |
| **工作流骨架** plan 必含节 | **PASS** | 状态/风险档、业务源、现状锚点、R\*、P\*、非目标、切片+DoD、验证、落点、修订程序均在。交接为 GO 前预览，闸写清。 |
| **代码锚点（相对 `e018924`）** | **PASS** | 本核对照 HEAD 源：`MINUTE_LAKE_END:93`、`CACHE_ROOT:143`、`minute_cache_path:233-235`、湖根 `:376`、`load_minute_bars:399`、`assemble_instances:234`、`evaluate_exit:378`、`evaluate_matrix:502`、`write_reports:934`、`run_modea:1021`、`load_exdiv_ratios:220`、`rescale_position:157-166`。交接写「行号漂移以符号为准」。 |
| **UTF-8 / 范围 / CI** | **PASS** | 四文件 BOM=false、NUL=0、CR=0、LF 结尾。`git diff --check` 空。CI SUCCESS @ `0608e62`。 |

### R\* ↔ 提案锁（本核对照）

| 提案 | 锁定内容 | plan / handoff |
|------|----------|----------------|
| **Q2** | A/B 都用名单当日**日线收盘**（不是 14:55） | R2 买 = none 日线 close；handoff A.1 价域换成 none（Q20） |
| **Q3** | Mode B 成交 = 触发那根分钟 **close**（high/low 只判触） | R2 触发 = 1m high/low，成交 = 该分钟 close |
| **Q8** | 同根双触 **先止损** | R3；切片 B 向量「reason=stop、价=该分钟 close」 |
| **Q20** | Mode A 全日线复权；Mode B **买入和监控都用不复权** | R2 none 日 + none 1m；禁止 front/none 混链 |
| **Q21** | Mode A 不做 E-R6；Mode B 不复权 + E-R6 | R4；Mode A 代码列为尽量只读 |
| **Q29=B** | 除权日再 `shares/=k`；**不改**现 `rescale_position`；红利仍不入账 | R4 + 切片 C；现金红利不入账；除权后不再整百 |

规则 3 trailing：提案 Mode B「peak 用不复权 close」。handoff B.2「trailing 用分钟 close 更新 peak」是 close-only 的分钟适配，不是用 high 当 peak。N=1 r2≡r1 在 R5 保留。

### P\* 建议 vs 宿主短记 §5

短记 §5：oracle 129.6% vs 冠军 1.5% + 次日开盘买更优 → Mode B 有数据依据；重算迁 4090；前置性能票（#92 已合，plan 基线 `e018924`）。

| P | 建议 | 为何合理 |
|---|------|----------|
| P1=A | 冠军族 + 锚线，先于全 280 | 分钟成本 ≈ ×240；先证盘中边际再全扫。全量仍是选项 B，等人裁。 |
| P2=A | 宿主 F 湖 smoke → 再 4090 | 与 §5 / 提案资源注记同构；R6 全网格宿主-only。 |
| P3=A | `ex_date_index` + `load_exdiv_ratios` | Q29=B；湖已有；P3=B 是显式降级出口。 |
| P4 | 已锁：分目录、不混 NAV | Q21 复核「A/B 买入价可能不同、净值不能直接排名」。 |
| P5 | smoke 现在；业务网格 GO+impl 后 | 把数据就绪从实现 PR 拆出，避免伪完成。 |

切片分离：

```text
现在（可做，无 Mode B 代码） : smoke runbook = 湖可达 + bar_cache + 覆盖率 + 墙钟
人裁 GO                      : plan 头部 ✅（本 PR 之后，另一步）
实现 PR 合入门               : A–D（合成 pytest；CI data-free）
非合入门                     : E = 按 P1 窄或全网格 + 研究短记
```

### 工作流对照（`workflow-codex-handoff` 七步）

本 PR = 第 1 步 plan 起草 + 第 4 步交接**草稿**提前落盘。第 3 步人裁 GO **未做**，闸写明。交接头部未伪标「已 GO（hash）」——符合「待人裁」对象。第 2 步评审即本文件。

---

## 违规 / 风险

无 🔴。无合入阻断。硬边界未破。提案 Q 锁未破。Mode B **未**实现、也未声称已实现。

### nit-1（口径）「4167 码」应为 4167 **实例**

handoff 切片 A.3：「Mode A 宿主实开 **4167 码**」。宿主短记 §1：实开 **4167 实例**（5061 − 795 − 99）；提案 §9.7 名单并集 **2322 码**。覆盖率分母若用 4167 对 unique symbol ∩ 分钟键，会系统性偏。smoke §1.3 写「相对 4167 或并集」稍好，仍宜钉：unique 开仓码 vs 实例数两行都记。**不挡合入**；人裁/开工时改交接一句即可。

### nit-2（语义未锁）跌停「当日（或该分钟）」写进了步骤

handoff B.5：「用当日（或该分钟）相对昨收的跌停判定」。提案 Q7 是**日**口径：规则已触发也不卖，下一交易日再评。Mode B 盘中 low 触板、收盘收回，是否当跌停禁卖，提案未钉。B.7 对「到期末日分钟 close vs 日线 close」正确 **STOP → Q36**；B.5 的「或」却像已裁。Codex 若当锁执行会自裁。建议人裁时升一条 P 或开工遇此 **STOP Q36**，不要把「或该分钟」当默认。

### nit-3（P1=A 集合未点名）

建议 A =「冠军族 + 锚线」，未抄宿主短记族 `X∈{5,7,10}×Y∈{5,10,∞}×N∈{8,10}` 及 top20 的 r3 `#17 r3_y10_n10`。人裁勾 A 时若不枚举，实现会猜。合入后回写 plan 建议列即可。

### nit-4（卫生）smoke 头「可与编码并行」vs GO 前禁编码

smoke 正文正确：无 Mode B 代码、现在就能做。页眉「可与 Mode B **编码并行**」容易读成「编码已允许」。实际时间线是 **smoke ⊆ 现在；编码 ⊆ 人裁 GO 之后**（GO 后才可能并行）。改成「不依赖 Mode B 代码，可先于编码」更干净。不挡。

### 观察（不升格）

| 项 | 说明 |
|----|------|
| 交接早于工作流第 4 步 | 七步是 GO 后再写 handoff。本票当施工图预览，闸足够硬，不升格。GO 后须刷新 §0「pending」并填 plan hash。 |
| 提案 R5.6 A/B 对账标本 | 全网格前 10 大/10 中/10 无事件码。未进切片。合成 C fixture 覆盖除权形状，不是真湖对账。人裁 P1 时可并进窄船，非本 PR 必补。 |
| 到期成交口径 | handoff B.7 倾向「到期日最后一根 session 分钟 close」，并写明提案未钉则 STOP。正确。人裁可预裁进 P\*。 |
| 分钟引擎 14:55 | 提案 §9.3 对照行：现仓分钟买 14:55，本网格买日线 close。plan 非目标 / R2 已隔离，不改 `csv_minute_backtest` 成交核书。 |
| GPU | 非目标；提案「排期再评估」。R6 只 prefer 4090 跑矩阵，不引入 CuPy。 |
| AGENTS.md | 实现切片 D 才加入口；本 docs PR 只动 README。正确。 |
| smoke `codes = set()` | 示例 TODO，空集不会写出有用 cache。宿主须填 Mode A 开仓并集或 2322。 |

---

## 建议动作（是否可合）

**可以合入 master（docs-only）。** 不要为本票 nits 开 feat 写 Python，也不要把合入当成 Mode B 实施 GO。

合入后（确认人，非本核）：

1. 裁 P1–P5；回写 plan 建议列 →「已裁」，头部改为 ✅ 已人裁 GO（hash）。
2. 刷新 handoff §0（去掉待人裁等待句）；P1=A 则点名冠军族；4167 改「实例」；跌停 / 到期 close 要么预裁要么留给 Q36 STOP。
3. 宿主可按 smoke runbook 做分钟 cache（**仍不是** Mode B 网格）。
4. 仅在 plan 头部 ✅ 之后从当时 master 开 `feat/unified-exit-modeb`。

本核 **未 merge、未改业务代码**；仅落本评审文件。

---

## 核验命令（本核已跑）

```text
git fetch origin
git rev-parse HEAD
# = 0608e6230306b7bc531ce8d0a7bd5ce626dbf6f2
git merge-base origin/master HEAD
# = e018924b3088887cbaa0be690f2a731e1bfb348e  (= origin/master)
git diff --name-status origin/master...HEAD
# M README.md
# A handoff-unified-exit-modeb-codex-impl-2026-09-17.md
# A host-runbook-unified-exit-modeb-smoke-2026-09-17.md
# A plan-unified-exit-modeb-2026-09-17.md
# 无 .py / .rs / YAML
gh pr view 93 --json mergeable,mergeStateStatus,headRefOid,statusCheckRollup
# MERGEABLE / CLEAN / head = 0608e62 / pytest-and-gates SUCCESS
gh run view 35193898759
# SUCCESS @ 0608e62
# UTF-8：四 md BOM=false NUL=0 CR=0
# 锚点：MINUTE_LAKE_END:93 CACHE_ROOT:143 minute_cache_path:233
#        load_minute_bars:399 assemble:234 evaluate_exit:378
#        evaluate_matrix:502 write_reports:934 run_modea:1021
#        load_exdiv_ratios:220 rescale_position:157-166 shares untouched
```

Mode B Python / 真湖分钟网格 **未**跑（本 PR 无实现；非合入门）。
