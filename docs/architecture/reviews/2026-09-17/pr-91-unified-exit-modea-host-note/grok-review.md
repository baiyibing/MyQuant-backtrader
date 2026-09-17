# PR #91 统一卖出规则网格 · 模式 A 宿主短记（切片 D）— Grok 核评审

> 日期：2026-09-17
> 角色：MyQuant-backtrader Grok 核（独立 grok CLI；只审不合入）
> 对象：[PR #91](https://github.com/baiyibing/MyQuant-backtrader/pull/91) `docs/unified-exit-modea-host-note`（tip `6eebc8d` vs 已合 PR #90）
> 权威：[host-runbook-unified-exit-modea-2026-09-17.md](../../../../backtest/host-runbook-unified-exit-modea-2026-09-17.md) · [stock-backtest-unified-exit-proposal-2026-09-17.md](../../../../backtest/stock-backtest-unified-exit-proposal-2026-09-17.md)（§9.7 / Q30–Q35）· [handoff-unified-exit-modea-codex-impl-2026-09-17.md](../../../../backtest/handoff-unified-exit-modea-codex-impl-2026-09-17.md) · [PR #90 Grok 复核](../pr-90-unified-exit-modea/grok-review.md)（`c1c2caf` **GO-WITH-NITS**，已合）
> HEAD：`6eebc8d562dc320e900ae8105c762e41e538ba41`
> parent / merge-base：`8032fc7efdd4e9130127382bbc4bf3715c113b73`（= PR #90 merge commit）
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**
> 工作树：`/workspace/MyQuant-backtrader-pr91`（detached @ `6eebc8d` = `origin/docs/unified-exit-modea-host-note`）

---

## 结论

**GO-WITH-NITS**（**可合**；nits 不阻断合入，不改引擎 / 不改提案正文 / 不实施 Mode B。本核不 merge）。

这是合格的 docs-only 切片 D 回收：相对已合 PR #90 只动 runbook 状态行 + 新短记 53 行，零 Python / 零成交核。Sanity 与 §9.7 预检自洽（5061 / 795+99 / 4167、峰值 904 lots、N=1 42/42、delist −0.79pp、冠军 +1.50%、oracle +129.64%），短记数字内部也对得上 11 亿分母。完成声明是真跑数回收，不是 #90 的伪勾选；nits / Mode B 只记建议、未越权改代码。剩余是同文件 §2 旧句与提案/交接页眉未回写，不挡合入。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#91 docs(unified-exit): Mode A host run note - slice D complete](https://github.com/baiyibing/MyQuant-backtrader/pull/91) |
| 比较 | `8032fc7..6eebc8d`（2 files, +54 / −1） |
| 前置 | PR #90 **MERGED** @ `2026-09-17T05:20:36Z`，merge commit `8032fc7` |
| D | 本 PR：runbook 状态行 📋 host-only → ✅ 宿主已完成；新短记 `unified-exit-modea-host-note-2026-09-17.md` |
| 代码 | **零**。无 `.py` / `.rs` / CI YAML |

`git diff --name-status 8032fc7..6eebc8d`：

```
M  docs/backtest/host-runbook-unified-exit-modea-2026-09-17.md
A  docs/backtest/unified-exit-modea-host-note-2026-09-17.md
```

禁区文件不在列。GitHub PR files 与 tip 一致。CI [`35191016999`](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35191016999) SUCCESS @ `6eebc8d`。

---

## 证据表

| 锁 / 裁点 | 结果 | 证据 |
|-----------|------|------|
| **范围** 仅 runbook 状态行 + 新短记；无引擎/Python | **PASS** | 2 文件 +54/−1；tip 无 `.py`。runbook 只改页眉状态一行（链到短记）。提案 / 交接 / AGENTS / README / `unified_exit_modea.py` **未动**——符合本 PR 范围，不是漏改成交核。 |
| **Sanity 自洽** 5061 / 795+99 / 4167 | **PASS** | 见下节。`5061 − 795 − 99 = 4167`。预检 §9.7 封板 795 与超幅度 99 是互斥桶；引擎 `_is_limit_up`（`pct >= lp − tol`）把两桶一并跳过，故实开不是 runbook 预估的 4266。 |
| **峰值 904** ≤1053 / ≤11 亿 | **PASS** | 全 280 组 max **904 lots = 9.04 亿** < N=20 无早退出上界 1053 / 10.53 亿，未触 11 亿，无需显著标记。 |
| **N=1 42/42** | **PASS** | 提案 §三 / R2.2：规则 2 `X∈7 × Y∈6 × N=1 = 42`。短记 42/42 逐位相等。网格常量 `RULE2_XS` 7 值、`RULE2_YS` 6 值与此同构。 |
| **delist −0.79pp** | **PASS** | 锚线 −25.15% − (−24.36%) = **−0.79pp**。`0.79pp × 11 亿 = 869 万 ≈ 870 万`；`9 × ≈97 万 ≈ 873 万`。落在 Q33 上限 900 万 ≈ 0.8% 内。 |
| **冠军 +1.50% / oracle +129.64%** | **PASS** | Top1 +1.50%；oracle 表 +129.64%。提取率 `1.50 / 129.64 ≈ 1.157% ≈ 1.2%`。年化 `(1.015)^(365/322)−1 ≈ +1.70%`，短记 ≈ +1.7%。 |
| **切片 D 非伪完成** | **PASS** | 见下节。真跑数痕迹（72m21s、4167 对 4266 的修正、四件套填满）；不是 #90 把 runbook 勾成 done。nits / Mode B 未实施。 |
| **UTF-8 无 BOM** | **PASS** | 短记 4690 B、runbook 2308 B：BOM=false、NUL=0、CR=0、UTF-8、LF 结尾。 |
| **硬边界** 不改湖 / 不改 `*_rules.py` / 成交核 | **PASS** | diff 无业务代码。Mode B 只在短记 §5「供确认人」。 |

本核 **未**重跑 72 分钟真数据网格（无 F 湖，与 #90 评审同环境）。数字核验走文档自洽 + 对照 §9.7 / 已合实现，不冒充宿主复跑。

### Sanity 算术（本核手算）

预检 §9.7 涨停边界是**互斥**桶：`p ≥ lp+tol` → way_above 99；`elif p ≥ lp−tol` → 封板 795。装配层 `_is_limit_up` 用 `pct >= lp − tol`，99 笔超幅度也会被标 `limit_up` 跳过。故：

| 式 | 值 |
|----|----|
| 名单实例 | 5061（装配层 = §9.7 解析口径） |
| 跳过 | 795 + 99 = 894 |
| 实开 | 5061 − 894 = **4167**（不是 5061−795=4266） |
| 其它 skip | 若 `no_bar` / `unknown_board` / `shares_zero` 非 0，实开会 <4167；短记写 4167 ⇒ 与 §9.7「名单日无 K = 0 / missing=0」一致 |

11 亿分母 × 每实例 100 万：`mean × 4167 / 1100` 应等于总收益率。

| 锚 | 总收益率 | 每实例均值 | `mean × 4167/1100` |
|----|---------|-----------|---------------------|
| hold_end | −24.36% | −6.43% | −24.36% |
| delist_zero | −25.15% | −6.64% | −25.15% |
| oracle | +129.64% | +34.23% | +129.66%（0.02pp 四舍五入） |
| N=1 | −0.70% | −0.19% | −0.72%（−0.185% 会收成 −0.70%；显示一位小数） |

delta −0.79pp × 11 亿 = 869 万，短记 ≈870 万。峰值 904×100 万=9.04 亿。网格 8+252+20=280。全部闭合。

4167 vs runbook 步骤 3「实开 ≈ 4266」不是实现 bug：4266 是交接/runbook 按「只减封板 795」的预检下界，未计入超幅度 99。短记把偏差写清并与 `way_above_limit` 对上，符合 runbook「偏差大 = 先查再报」。

### 切片 D 完成声明（非伪勾选）

#90 权威口径：合入门只含 A/B/C；runbook 当时是 `host-only — NOT done in PR`。本 PR 才是宿主回收票。

对照 runbook §1.5 / §2 完成定义：

| 要求 | 本 PR |
|------|--------|
| 短记落盘 `unified-exit-modea-host-note-YYYY-MM-DD.md` | **有**（2026-09-17） |
| 实际数字 vs §9.7 | **有**（§1 表，含 4167 解释） |
| top 组摘要 | **有**（Top 5 全 r2，#17 r3） |
| 峰值并发 | **有**（904 lots / 9.04 亿，未触顶） |
| 异常 / STOP | **无 STOP**；nits 单列 |
| 实现指针 | PR #90 / master `8032fc7`（= 本 commit parent，已核） |
| 数据版本 | 声称与 §9.7 同版 front（09-15 后未刷新）；未摘抄 `meta_sha256` / `body_sha256`（Q35=D 可选留痕，见 nit-2） |
| `backtest_output/unified_exit_modea/` 四类产物 | **未入库（正确）**；PR body 写对照过 artifacts。短记未点名四文件路径（nit-2） |
| 稳健性四件套（Q34） | 半窗交集 0 但冠军族前排；r2 无孤峰；分层；次日开盘买更优 |

伪完成会照抄 4266、不解释 99、不填四件套。本短记改了预估、给出 72m21s / 42/42 / −0.79pp，像真跑。

nits / Mode B **未越权实施**：

- plateau 只解析 `r2_*`（`neighborhood_plateau_flags:811` `if not m.label.startswith("r2_"): continue`）——短记记下 #17 r3 缺口，**未改函数**。
- 性能：`date_to_ymd` / `_bar_close_map` 确在热路径；建议向量化，**未改循环**。
- 99 笔：§十一待办在短记里降为存档，**未改提案正文、未改跳过语义**。
- Mode B：§5「供确认人」+ 4090（提案资源注记已有），**无分钟路径代码**。

---

## 违规 / 风险

无 🔴。无合入阻断。

### nit-1（卫生）runbook §2 末句与新状态行打架

状态行已是 ✅ 宿主已完成，§2 仍写「**本 PR / CI 不得勾选本切片为完成。**」——这是 #90 写给代码 PR 的禁勾句，本票只翻了页眉、没改完成定义。读者会以为 #91 也不该勾 D。

合入后改一句即可，例如「切片 D 已由宿主短记勾完；CI / 无 F 湖环境仍不跑真数据。」**不要为改这一句重切引擎。** 本 PR 按「只动状态行」的范围可合。

### nit-2（完成定义松一点）短记未点名四类产物路径、未摘 sha256

runbook §2：短记 + `backtest_output/unified_exit_modea/` 排名 / 明细 / 汇总 / 稳健性。产物不应入库；短记写一句路径（或「四文件已落、未入库」）更干净。Q35=D 指纹可选；提案已有 `meta_sha256=9c7799cb…` / `body_sha256=6f2e00d8…`，短记只说「逐位一致」不摘哈希，复跑核对要回提案。不挡。

### nit-3（交叉页眉，本 PR 范围外）提案 / 交接仍写「切片 D 仍宿主-only」

handoff §5：「完成后回写本交接状态与提案 §状态行。」本 PR **按核重点 1 正确未改这两份**。合入后确认人另票回写页眉，避免三份文档长期分叉。不要求本 PR 扩 scope。

### 观察（不升格）

| 项 | 说明 |
|----|------|
| 冠军族下沿 +0.93% | 只在 PR body / commit；短记写族 `X∈{5,7,10}×Y∈{5,10,∞}×N∈{8,10}` 与 Top 5 +1.50…+1.28%，未写 +0.93。 |
| 次日开盘 vs Top 5 | 「收盘 +1.3%~+1.5%」相对 Top 5 最低 +1.28% 略收。方向不变。 |
| 冠军回撤小于 2.5% / 胜率 ~51% | 锚线表无冠军行，无法用表内数字闭合；像宿主读 ranking CSV 的摘要。 |
| plateau OR 族 | 与 #90 nit 同一启发式（同 N 或同 X 或同 Y，非 1-step 邻接）。本票只记录 r3 缺口，未改。 |
| 提案 §十一 99 笔 | 短记降档为存档；若确认人仍要「核对是否新股/复牌」应另票，不在本 PR 改提案。 |

---

## 建议动作（是否可合）

**可以合。** 不要为 nit-1…3 改引擎，也不要在本票实施 plateau / 向量化 / Mode B。

合入后（另票，非本 PR）：

1. runbook §2 末句改成「D 已由短记勾完；CI 仍不跑真数据」。
2. 提案页眉 + 交接状态行：宿主-only → 已完成，链到本短记。
3. （可选）短记补四产物路径 + 摘抄 §9.7 两个 sha256。
4. plateau r3 覆盖与 `date_to_ymd` 预转缓存：Mode B 之前的 Codex 票，不是 D 的合入门。

本核 **未 merge、未改业务代码**；仅落本评审文件。

---

## 核验命令（本核已跑）

```text
git fetch origin master docs/unified-exit-modea-host-note feat/unified-exit-modea
# HEAD 6eebc8d == origin/docs/unified-exit-modea-host-note
# parent 8032fc7 == PR #90 merge
git diff --name-status 8032fc7..6eebc8d
# M host-runbook… / A unified-exit-modea-host-note…  （无 .py）
gh pr view 91 --json mergeable,mergeStateStatus,statusCheckRollup,headRefOid,files
# MERGEABLE / CLEAN / head = 6eebc8d / 2 files +54/−1
gh pr view 90 --json state,mergeCommit
# MERGED / 8032fc7
gh run view 35191016999          # SUCCESS @ 6eebc8d
# UTF-8：两 md BOM=false NUL=0 CR=0
# 算术：5061-795-99=4167；-25.15-(-24.36)=-0.79；1.50/129.64≈1.2%
```

真数据网格 **未**重跑（非本核环境、非合入门复验项）。
