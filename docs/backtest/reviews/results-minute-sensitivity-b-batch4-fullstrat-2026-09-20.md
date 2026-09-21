# 分钟敏感对照 B · 第四批结果（全策略 NAV / DD / 引擎内排名 · 2026-09-20）

**状态：`EXECUTED_PARTIAL` → Slice D clock/slip 已于 2026-09-21 4090 回填。** ModeB 基线、Book version9（`s9_bvot`）、Book version10（`s10_tr`）基线此前已填；**Slice D**（`clock_next_open_fullstrat` / `slip_{5,10,20}bp_fullstrat`；**基线故意不在本 D 矩阵**）已由 host 戳 `batch4_fullstrat_hooks_d_20260921b` 回填（见 §11 / [addendum](addendum-batch4-slice-d-fullstrat-hooks-2026-09-21.md)）。Research-only（H2+Q2）；局部事件 bp（batch2/3）**禁止**粘贴进下表；**禁止**跨引擎比 NAV 论优劣；`production_C=frozen`；**无 human/bt tip 勿 merge**。

依据：[设计](design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md)；[计划](plan-minute-sensitivity-b-2026-09-20.md)；导出 [batch4_fullstrat/](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat/)（Book v1–v8 / v7）；ModeB 基线重跑戳 `batch4_fullstrat_modeb_rerun_20260921`（4090 @ tip `a1e7dea`）；Book version9 戳 [`batch4_fullstrat_v9_s9bvot_20260921`](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat_v9_s9bvot_20260921/)（4090 @ tip `51e0195`，pool=`s9_bvot` **非** `stock_pool`；见 [addendum](addendum-batch4-v9-s9bvot-fill-2026-09-21.md)）；Slice D 戳 [`batch4_fullstrat_hooks_d_20260921b`](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat_hooks_d_20260921b/)（manifest `git_head=3931dfd`）。

| 项 | 取值 |
|---|---|
| 跑批 | 4090，2026-09-20 20:49:32–20:50:19 (+08)，**EXIT=0**，~47s |
| git HEAD | `93406f357e6c3e5ca695a15d43af106f8ee5e558` |
| BASE tip | ≈ `ac1fa97`（#140） |
| 窗 | `20260825`–`20260909`（pool∩分钟湖） |
| access | `qlib_bin_1min` @ `C:\Users\wangc\.qlib\qlib_data\my_data_1min` |
| bar 标签 | `lake_index_is_bar_start_wallclock` |
| 费用 | `DEFAULT_SCHEDULE=BILATERAL_10BP` |
| pool | 原批 `stock_pool`（Book v1–v8 / v7 / ModeB）；**version9** 用 `export_strategy9_pool`→host `D:\exports\s9_bvot_20260825_20260909`（拒 `stock_pool/`）；**version10** 用 Source-B `resist_tr_bb_1000`→host `D:\exports\s10_tr_bb1000_20260825_20260909`（研究 lake∩TR 后 fail_closed；从未写 `stock_pool/`；见 §10） |

---

## 1. 单轴矩阵

| cell_id | clock | slip | Book | v7 | ModeB |
|---|---|---|---|---|---|
| `baseline_default_clock_fee` | 生产默认 | 0 | **FILLED**（引擎内 #1 = version8） | **FILLED** | **FILLED**（引擎内 #1 = livermore_l2_stale8_y10；`modeb_ok=1`） |
| `clock_next_open_fullstrat` | next-open | 0 | **FILLED**（Slice D · §11；core `book_ok` 内 #1 = version8） | **FILLED**（§11；全现金 NAV 合法） | **FILLED**（§11；顶行 `r1_n1`，全现金） |
| `slip_5bp_fullstrat` | 默认 | 5bp/边 | **FILLED**（§11；#1 = version8） | **FILLED**（§11） | **FILLED**（§11；顶行 `livermore_l2_stale8_y10`） |
| `slip_10bp_fullstrat` | 默认 | 10bp/边 | **FILLED**（§11；#1 = version8） | **FILLED**（§11） | **FILLED**（§11；顶行 `r2_x5_yinf_n8`） |
| `slip_20bp_fullstrat` | 默认 | 20bp/边 | **FILLED**（§11；#1 = version5） | **FILLED**（§11） | **FILLED**（§11；顶行 `r2_x10_yinf_n10`） |

证据：基线仍见原执行戳 `matrix.csv` / `data_gaps.csv`。Slice D 数字见 host `D:\exports\batch4_fullstrat_hooks_d_20260921b\` 与仓内 [`batch4_fullstrat_hooks_d_20260921b`](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat_hooks_d_20260921b/)（manifest `git_head=3931dfd33ea7146f7dcf3ba5fa06a4bbc96b7c18`，`emitted_at=2026-09-21T16:23:44+08:00`；`book_ok=28` / `v7_ok=4` / `modeb_ok=4`）。2026-09-21 **FULL HUMAN CUT（H2 + 卖单到期次日重评）** 与 #156 hooks 已合并；本表 clock/slip 列为 Slice D 回填，**不覆盖**基线 NAV。Research-only；`production_C=frozen`；**无 human/bt tip 勿 merge**。


**Slice B 按最新 Q2 恢复**：`40afca4` / `dde7a6f` 的 Q1 固定股数及停点叙述已被人裁覆盖。信号股数暂定，next-open / slip 成交价重定量；10,000 预算 / 10,050 现金 / 信号 10 → 暂定 1,000，open 10.1 → 900 股成交、现金 950.91。固定股数后 `cash_reject_terminal` 是必须排除的反例。H2 与卖单到期次日重评继续绑定；新增数值待合并后 4090。

历史验证（实现前）：本次 gates（显式 `/workspace/vanna312/bin/python3`；系统 python3 未装 pytest / ruff）：既有非 production / benchmark 测试 **1422 passed, 2 skipped, 24 deselected**（exit 0，24.78s），harness `--help` exit 0；新 hook pins 文件不存在，专项 pytest exit 4（未通过）。无 Python 改动，ruff 无 touched 目标。现有函数 sizing 复现、`git diff --check`、修改文档 UTF-8 / BOM=0 / NUL=0 通过。既有测试通过不代表尚未实现的 hooks 已验证。


### Slice B（2026-09-21 · Q2 + H2；data-free）

| cell | Book | v7 | ModeB | 新增 NAV / return / DD / rank |
|---|---|---|---|---|
| clock_next_open_fullstrat | FILLED（§11） | FILLED（§11） | FILLED（§11） | Slice D 4090 已回填 |
| slip_5bp_fullstrat | FILLED（§11） | FILLED（§11） | FILLED（§11） | Slice D 4090 已回填 |
| slip_10bp_fullstrat | FILLED（§11） | FILLED（§11） | FILLED（§11） | Slice D 4090 已回填 |
| slip_20bp_fullstrat | FILLED（§11） | FILLED（§11） | FILLED（§11） | Slice D 4090 已回填 |

Q2 已通过实际 adapter 对照：预算 10,000 / 现金 10,050，信号价 10 的暂定 1,000 股，在 open 10.1 重定量 900 股成交，余额 950.91；Q1 固定股数拒单不是 adapter 合同。H2 全部 fill 覆盖、START 14:55 当日到期、全现金 NAV、卖单到期清除与次日重评通过。零参数委托原引擎，production_C=frozen；#151/#152 contested files 和历史数字未改。

验证环境：显式 PATH 选 `/workspace/vanna312/bin/python3`。专项 **48 passed**（0.99s）；全套 `-m "not production and not benchmark" tests/` **1475 passed, 2 skipped, 24 deselected**（22.76s；既有 TR window warning 1 条）；ruff touched Python、harness `--help`、diff/UTF-8/BOM=0/NUL=0 均通过。[Grok 复核通过](../../architecture/reviews/2026-09-21/pr-156-fullstrat-q2/grok.md)：初核 ModeB 同日卖出假设被原 T+1 路径与两名单现金回收 pin 排除；补齐无冲击市场 mark 后 focused follow-up **Approve**。没有执行 4090 数值跑批。

### 基线矩阵摘要行（默认时钟）

| 引擎 | fill | NAV | total_return | max_drawdown | within_engine_rank |
|---|---|---:|---:|---:|---:|
| Book（version8） | FILLED | 21,104,115.65 | +0.50% | −1.39% | 1 |
| v7（strategy7） | FILLED | 20,895,023.51 | −0.50% | −0.87% | 1 |
| ModeB（livermore_l2_stale8_y10） | FILLED | 1,099,605,762.32 | −0.03584% | 0.06439% | 1 |

---

## 2. Book（默认时钟 · 分策略）

来源：`book_nav.csv`。排名仅在 Book 内。初始资金口径与 runner 一致（≈21,000,000）。

| strategy | final_equity | total_return | max_drawdown | rank | status |
|---|---:|---:|---:|---:|---|
| version8 | 21,104,115.65 | +0.50% | −1.39% | 1 | OK |
| version5 | 20,956,592.18 | −0.21% | −0.29% | 2 | OK |
| version3 | 20,913,096.26 | −0.41% | −0.51% | 3 | OK |
| version2 | 20,898,334.86 | −0.48% | −0.51% | 4 | OK |
| version1 | 20,893,163.02 | −0.51% | −0.52% | 5 | OK |
| version6 | 20,879,046.33 | −0.58% | −0.57% | 6 | OK |
| version4 | 20,842,364.89 | −0.75% | −0.89% | 7 | OK |
| version9 | 21,053,316.65 | +0.25% | −0.19% | 1† | OK（† v9-only 戳 `batch4_fullstrat_v9_s9bvot_20260921`；pool=`s9_bvot` **非** `stock_pool`；**不**与上表 stock_pool Book 行重排；禁止跨引擎排名） |
| version10 | 21,025,809.91 | +0.12% | −0.06% | 1‡ | OK（‡ v10-only 戳 `batch4_fullstrat_v10_s10tr_20260921`；pool=`s10_tr`；研究 lake∩TR 后 fail_closed；不跨池/戳重排；禁止跨引擎排名） |

---

## 3. v7（默认时钟）

来源：`v7_nav.csv`。

| strategy | final_equity | total_return | max_drawdown | rank | status |
|---|---:|---:|---:|---:|---|
| strategy7 | 20,895,023.51 | −0.50% | −0.87% | 1 | OK |

---

## 4. ModeB（默认时钟）

来源：`batch4_fullstrat_modeb_rerun_20260921/modeb_nav.csv` + `matrix.csv`（4090 ModeB-only 重跑，tip `a1e7dea`，EXIT=0，~2026-09-21 08:14 +08）。cell=`baseline_default_clock_fee`；窗 `20260825`–`20260909`；access=`qlib_bin_1min`；fee=`DEFAULT_SCHEDULE=BILATERAL_10BP`；`daily_entry_source=aggregated_from_1min_none_lineage`。本跑 Book/v7 为 `engine_skipped`——**保留上表 #142 Book/v7 数字，不空白**。排名仅在 ModeB 内；**禁止跨引擎排名**。

| strategy | final_equity | total_return | max_drawdown | rank | status |
|---|---:|---:|---:|---:|---|
| livermore_l2_stale8_y10 | 1,099,605,762.3151746 | −0.0003583978952958367（−0.03584%） | 0.0006438975472074711（0.06439%；harness 原样，不翻号） | 1 | OK |
| r2_x5_yinf_n8 | — | −0.0003656 | 0.0005486 | 2 | OK |
| r2_x5_yinf_n10 | — | −0.0003739 | 0.0005569 | 3 | OK |

矩阵：ModeB baseline **FILLED**；`modeb_ok=1`。入场意图仍为 `aggregated_from_1min_none_lineage`（禁止 qlib day.bin 后复权）。`production_C=frozen`。

---

## 5. 硬禁令（本批重申）

1. 局部事件 bp ≠ 组合 NAV；batch2/3 数字不得填入上表。
2. Book / v7 / ModeB **分列**；禁止用本批 NAV 宣称引擎优劣（**forbid cross-engine NAV rank**）。
3. Slice D clock/slip 数字仅来自 research-only hooks（#156 · H2+Q2）；不得为填格改生产 fill/scan/fee；基线格与 D 格分列，禁止混排论优劣。
4. `production_C=frozen`；docs/research-exports 回填 **无 human/bt tip 勿 merge**。

---

## 6. 产物清单

| 路径 | 说明 |
|---|---|
| `batch4_fullstrat/matrix.csv` | 矩阵填数 |
| `batch4_fullstrat/book_nav.csv` | Book 分策略 |
| `batch4_fullstrat/v7_nav.csv` | v7 |
| `batch4_fullstrat/modeb_nav.csv` | ModeB（原批 DATA_GAP/import） |
| `batch4_fullstrat_modeb_rerun_20260921/modeb_nav.csv` | ModeB 基线重跑（FILLED；可能未入库） |
| `batch4_fullstrat_modeb_rerun_20260921/matrix.csv` | ModeB 基线重跑矩阵 |
| `batch4_fullstrat/data_gaps.csv` | 缺口登记 |
| `batch4_fullstrat/manifest.json` | 跑批元数据 |
| `batch4_fullstrat_v9_s9bvot_20260921/book_nav.csv` | Book version9 基线（s9_bvot 池；FILLED） |
| `batch4_fullstrat_v9_s9bvot_20260921/matrix.csv` | v9-only 矩阵 |
| `batch4_fullstrat_v9_s9bvot_20260921/data_gaps.csv` | v9 FILLED / 当时 v10 DATA_GAP 的历史登记（v10 后续回填见 §10） |
| `batch4_fullstrat_v9_s9bvot_20260921/README.md` | 池策略 + 数字 + tip |
| `batch4_fullstrat_v9_s9bvot_20260921/manifest.json` | tip/pool day counts / 数字元数据 |
| `batch4_fullstrat_v10_s10tr_20260921/book_nav.csv` | Book version10 基线（s10_tr；FILLED） |
| `batch4_fullstrat_v10_s10tr_20260921/matrix.csv` | v10-only 矩阵；clock/slip 仍 DATA_GAP |
| `batch4_fullstrat_v10_s10tr_20260921/data_gaps.csv` | v10 基线回填 / 剩余缺口 |
| `batch4_fullstrat_v10_s10tr_20260921/README.md` | 池策略、lake∩TR universe、主机产物引用 |
| `batch4_fullstrat_v10_s10tr_20260921/manifest.json` | pool day counts / 数字元数据；未提供运行 tip |
| `batch4_fullstrat_hooks_d_20260921b/core/{book,modeb,v7}_nav.csv` | Slice D core（28+4+4 OK） |
| `batch4_fullstrat_hooks_d_20260921b/core/manifest.json` | Slice D tip / cells / counts |
| `batch4_fullstrat_hooks_d_20260921b/v9/book_nav.csv` | Slice D Book version9（4 OK） |
| `batch4_fullstrat_hooks_d_20260921b/v10/book_nav.csv` | Slice D Book version10（4 OK） |
| `batch4_fullstrat_hooks_d_20260921b/README.md` | Slice D 戳说明 |
| 4090 runner 旁路 | `runner_artifacts/`（未全部入库；摘要 CSV 已入库） |

---

## 7. 下一步（建议）

1. ModeB 基线格已由 4090 ModeB-only 重跑回填（见 §4 / §8）；import 修复合入后无需再为同一 DATA_GAP 重跑。
2. Book **version9** 已由 `s9_bvot` 池回填（见 §2 / §9）；**version10** 已由 Source-B `s10_tr` 池回填（见 §2 / §10；研究 universe=lake∩TR 后 fail_closed）。
3. 全策略 clock_next_open / slip_* 轴：**Slice D 已回填**（§11）；v9/v10 池上 ModeB/v7 仍为 **N/A**（未跑，勿编造）。人裁是否采纳研究钩子进生产 **不在本 docs PR 范围**；`production_C=frozen`。


---

## 8. ModeB 基线回填（2026-09-21 · `batch4_fullstrat_modeb_rerun_20260921`）

Import 根因与修见 [addendum](addendum-batch4-modeb-import-fix-2026-09-21.md)。4090 于 tip `a1e7dea` 以 ModeB-only 重跑关闭 ModeB 基线 DATA_GAP（EXIT=0，~2026-09-21 08:14 +08；导出戳 `batch4_fullstrat_modeb_rerun_20260921`）。

- 引擎 ModeB；策略 `livermore_l2_stale8_y10`；cell `baseline_default_clock_fee`
- `final_equity=1099605762.3151746`；`total_return=-0.0003583978952958367`（−0.03584%）；`max_drawdown=0.0006438975472074711`（0.06439%，harness 原样不翻号）；status OK；`modeb_ok=1`
- Book/v7 在本 ModeB-only 跑为 `engine_skipped`：**不空白** §1–§3 中来自 #142 的 Book/v7 数字
- 仍 DATA_GAP（历史句）：当时全策略 `clock_next_open` / `slip_*` 未跑。**现已由 Slice D §11 回填**（不含本 ModeB-only 戳）。version9 / version10 基线已另戳回填（§9 / §10）

`production_C=frozen`（本回填 docs-only；不改 fill/scan/fee/defaults/hot-path）。

---

## 9. Book version9 回填（2026-09-21 · `batch4_fullstrat_v9_s9bvot_20260921`）

池与数字见 [addendum](addendum-batch4-v9-s9bvot-fill-2026-09-21.md)。4090 于 tip `51e0195` 先跑 `export_strategy9_pool.py`→`D:\exports\s9_bvot_20260825_20260909`（EXIT=0；12 日 CSV；79 name-occurrences；**从未写入 stock_pool/**），再 Book-only `--strategies version9` 关闭 version9 基线 DATA_GAP。

- 引擎 Book；策略 `version9`；cell `baseline_default_clock_fee`
- clock=`production_default`；slip=0；fee=`DEFAULT_SCHEDULE=BILATERAL_10BP`；access=`qlib_bin_1min`
- `final_equity=21053316.65`；`total_return=0.0025`（+0.25%）；`max_drawdown=-0.0019`（−0.19%）；status OK；within_engine_rank 1（本戳仅 version9）
- pool = **s9_bvot 导出**，**不是** `stock_pool`；主机路径在仓外（`/exports/` gitignore）；策略与 day counts 写在本戳 README / addendum，不提交 live CSV
- **保留** §2 中 #142 stock_pool Book v1–v8 与 §4 ModeB 数字，不空白、不跨池重排、**禁止跨引擎排名**
- **version10 ≠ s9**：不属于本 v9 戳；现已由独立 Source-B `s10_tr` 戳回填（§10）
- 全策略 `clock_next_open` / `slip_*`：本 v9 基线戳当时仍 DATA_GAP；**Slice D 已用独立戳回填 Book v9（§11）**；本戳 ModeB/v7 仍 N/A

`production_C=frozen`（本回填 docs + research exports only；不改 fill/scan/fee/defaults/hot-path）。

---

## 10. Book version10 回填（2026-09-21 · `batch4_fullstrat_v10_s10tr_20260921`）

池与数字见 [addendum](addendum-batch4-v10-s10tr-fill-2026-09-21.md)；
导出 [batch4_fullstrat_v10_s10tr_20260921](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat_v10_s10tr_20260921/)。

| field | value |
|---|---|
| engine / strategy | Book / version10 |
| window | `20260825`–`20260909` |
| cell | `baseline_default_clock_fee` |
| clock / slip / fee | `production_default` / 0 / `DEFAULT_SCHEDULE=BILATERAL_10BP` |
| access | `qlib_bin_1min` |
| final_equity | **21025809.91** |
| total_return | **0.0012** (+0.12%) |
| max_drawdown | **-0.0006** (−0.06%) |
| status | OK |
| within_engine_rank | 1 (v10-only stamp; forbid cross-engine rank) |

Pool host path (citation only): `D:\exports\s10_tr_bb1000_20260825_20260909`.
Rule: `resist_tr_bb_1000` via Source-B / `export_strategy10_pool.py` path.
**12 day CSVs; 115 name-occurrences; never `stock_pool/`.**

Day name counts: 20260825=19, 20260826=16, 20260827=6, 20260828=7,
20260831=8, 20260901=9, 20260902=3, 20260903=4, 20260904=10,
20260907=5, 20260908=13, 20260909=15.

**Universe limitation:** the stock CLI `export_strategy10_pool.py` with the
full lake universe failed closed: lake ⊃ TR cross-section (e.g. missing
`000001.SZ` on `20260825`). The research one-shot used **lake ∩ TR
cross-section** as its universe, then applied the `fail_closed` filter.
This restricted research universe is part of the result's provenance;
it does not demonstrate a successful full-lake CLI export and is **not a
production change**. No workaround implementation is committed here.

同窗 v9（#145）参考：pool=`s9_bvot`；final_equity=21053316.65 / +0.25% / DD −0.19%。
保留 v8/v9/v7/ModeB 原数值；不跨池/戳重排，禁止跨引擎排名。

These summary exports are recreated from the user-supplied verified 4090
numbers; the host zip is unavailable on this VM. No backtest or pool export
was rerun here. The exact 4090 run tip was not supplied (`base_tip: null`).
CSV column schemas and Book lineage labels follow the #145 v9 stamp.

4090 host artifact (citation only):
`D:\PycharmProjects\MyQuant-backtrader\backtest\research\exports\minute_sensitivity_b_20260920\batch4_fullstrat_v10_s10tr_20260921`.

TR context already merged: [#146 refresh_tr_store_window](https://github.com/baiyibing/MyQuant-backtrader/pull/146),
[#147 path-ssot allowlist](https://github.com/baiyibing/MyQuant-backtrader/pull/147),
[#148 utf-8-sig BOM](https://github.com/baiyibing/MyQuant-backtrader/pull/148).
4090 TR store through `20260909`; bands via vectorized path. Context only;
these changes are not repeated here.

全策略 `clock_next_open` / `slip_*`：本 v10 基线戳当时仍 **DATA_GAP**；**Slice D 已用独立戳回填 Book v10（§11）**；本戳 ModeB/v7 仍 N/A。
`production_C=frozen`（docs + research exports only；不改 production Python / fill / scan / fee / defaults / hot-path）。


## 11. Slice D · fullstrat clock/slip hooks（4090 · 2026-09-21）

依据：[addendum](addendum-batch4-slice-d-fullstrat-hooks-2026-09-21.md)；仓内戳 [`batch4_fullstrat_hooks_d_20260921b`](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat_hooks_d_20260921b/)；host `D:\exports\batch4_fullstrat_hooks_d_20260921b\{core,v9,v10}\`。

| field | value |
|---|---|
| window | `20260825`–`20260909` |
| cells（D 矩阵；**不含** baseline） | `clock_next_open_fullstrat`, `slip_5bp_fullstrat`, `slip_10bp_fullstrat`, `slip_20bp_fullstrat` |
| `git_head` | `3931dfd33ea7146f7dcf3ba5fa06a4bbc96b7c18` |
| `base_tip` | `32b78b1` |
| `emitted_at` | `2026-09-21T16:23:44+08:00` |
| contract | Q2 · H2 all fills · same-day expiry · sell = next-session reevaluate |
| fee / access / bar | `DEFAULT_SCHEDULE=BILATERAL_10BP` · `qlib_bin_1min` · `lake_index_is_bar_start_wallclock` |
| core counts | `book_ok=28`, `v7_ok=4`, `modeb_ok=4` |

Research-only；**禁止跨引擎 NAV 排名**；`production_C=frozen`；**无 human/bt tip 勿 merge**。基线 §1–§4 数字保持不动。ModeB / v7 在 v9、v10 池戳上为 **N/A**（未提供，勿编造）。

显示用 ±% 仅为阅读辅助；**权威数字以 CSV raw 为准**（下列 raw 与仓内/附件 CSV 逐字一致）。

### 11.1 Book core（v1–6,8 · `stock_pool`）

来源：`core/book_nav.csv`。排名仅在**同一 cell** 的 Book 内。初始资金口径 ≈21,000,000。

#### `clock_next_open_fullstrat`（next_tradable_open_research · slip=0）

| strategy | final_equity | total_return | max_drawdown | rank | status |
|---|---:|---:|---:|---:|---|
| version8 | 21,071,791.04 | +0.34% | −0.36% | 1 | OK |
| version5 | 21,013,776.85 | +0.07% | −0.09% | 2 | OK |
| version4 | 20,994,909.75 | −0.02% | −0.07% | 3 | OK |
| version6 | 20,981,349.32 | −0.09% | −0.19% | 4 | OK |
| version1 | 20,972,310.38 | −0.13% | −0.19% | 5 | OK |
| version2 | 20,972,310.38 | −0.13% | −0.19% | 6 | OK |
| version3 | 20,967,799.93 | −0.15% | −0.20% | 7 | OK |

CSV raw (`final_equity` / `total_return` / `max_drawdown`):

- `version8`: `21071791.042886786` / `0.0034186210898470293` / `-0.0035541350767059887`
- `version5`: `21013776.850259136` / `0.0006560404885302962` / `-0.0008749628257169739`
- `version4`: `20994909.748654984` / `-0.00024239292119121458` / `-0.0007417137360712367`
- `version6`: `20981349.319986414` / `-0.0008881276196945898` / `-0.0018538758828717805`
- `version1`: `20972310.38213241` / `-0.0013185532317899762` / `-0.0018538758828717805`
- `version2`: `20972310.38213241` / `-0.0013185532317899762` / `-0.0018538758828717805`
- `version3`: `20967799.92921054` / `-0.0015333367042600354` / `-0.002041862955380558`

#### `slip_5bp_fullstrat`（production_default · 5bp/边）

| strategy | final_equity | total_return | max_drawdown | rank | status |
|---|---:|---:|---:|---:|---|
| version8 | 21,012,239.08 | +0.06% | −1.44% | 1 | OK |
| version5 | 20,946,338.31 | −0.26% | −0.33% | 2 | OK |
| version3 | 20,908,508.71 | −0.44% | −0.52% | 3 | OK |
| version2 | 20,878,927.14 | −0.58% | −0.58% | 4 | OK |
| version1 | 20,873,867.74 | −0.60% | −0.60% | 5 | OK |
| version6 | 20,867,190.97 | −0.63% | −0.63% | 6 | OK |
| version4 | 20,834,182.57 | −0.79% | −0.91% | 7 | OK |

CSV raw (`final_equity` / `total_return` / `max_drawdown`):

- `version8`: `21012239.076016523` / `0.0005828131436440565` / `-0.014362400711979695`
- `version5`: `20946338.31381574` / `-0.0025553183897266685` / `-0.0032524375984869236`
- `version3`: `20908508.711721376` / `-0.004356728013267808` / `-0.00522249076826975`
- `version2`: `20878927.143883403` / `-0.005765374100790366` / `-0.005765374100790366`
- `version1`: `20873867.739176` / `-0.0060062981344761734` / `-0.0060062981344761734`
- `version6`: `20867190.9720343` / `-0.00632423942693805` / `-0.00632423942693805`
- `version4`: `20834182.566045094` / `-0.007896068283566926` / `-0.009136966173710848`

#### `slip_10bp_fullstrat`（production_default · 10bp/边）

| strategy | final_equity | total_return | max_drawdown | rank | status |
|---|---:|---:|---:|---:|---|
| version8 | 20,978,705.14 | −0.10% | −1.55% | 1 | OK |
| version5 | 20,938,235.83 | −0.29% | −0.36% | 2 | OK |
| version3 | 20,902,966.38 | −0.46% | −0.55% | 3 | OK |
| version2 | 20,881,537.25 | −0.56% | −0.58% | 4 | OK |
| version1 | 20,876,348.64 | −0.59% | −0.59% | 5 | OK |
| version6 | 20,859,550.63 | −0.67% | −0.67% | 6 | OK |
| version4 | 20,825,902.80 | −0.83% | −0.94% | 7 | OK |

CSV raw (`final_equity` / `total_return` / `max_drawdown`):

- `version8`: `20978705.140148398` / `-0.0010140409453144317` / `-0.015502953642770656`
- `version5`: `20938235.831498545` / `-0.002941150881021648` / `-0.003553149141185541`
- `version3`: `20902966.381140105` / `-0.0046206485171378375` / `-0.0054583809928409055`
- `version2`: `20881537.2487978` / `-0.005641083390580892` / `-0.00578401490240521`
- `version1`: `20876348.644286595` / `-0.005888159795876424` / `-0.005888159795876424`
- `version6`: `20859550.62560806` / `-0.006688065447235214` / `-0.006688065447235214`
- `version4`: `20825902.797022957` / `-0.008290342998906741` / `-0.009377059009711974`

#### `slip_20bp_fullstrat`（production_default · 20bp/边）

| strategy | final_equity | total_return | max_drawdown | rank | status |
|---|---:|---:|---:|---:|---|
| version5 | 20,921,101.68 | −0.38% | −0.42% | 1 | OK |
| version8 | 20,917,861.14 | −0.39% | −1.75% | 2 | OK |
| version3 | 20,887,369.43 | −0.54% | −0.60% | 3 | OK |
| version2 | 20,861,301.07 | −0.66% | −0.66% | 4 | OK |
| version1 | 20,856,183.45 | −0.68% | −0.68% | 5 | OK |
| version6 | 20,837,218.69 | −0.78% | −0.78% | 6 | OK |
| version4 | 20,809,652.69 | −0.91% | −0.98% | 7 | OK |

CSV raw (`final_equity` / `total_return` / `max_drawdown`):

- `version5`: `20921101.680346306` / `-0.0037570628406520257` / `-0.004163294174819643`
- `version8`: `20917861.14228833` / `-0.003911374176746141` / `-0.017485629018997195`
- `version3`: `20887369.43167953` / `-0.0053633603962129905` / `-0.0060342215384124875`
- `version2`: `20861301.06601609` / `-0.0066047111420910465` / `-0.006614210276836285`
- `version1`: `20856183.454757694` / `-0.006848406916300287` / `-0.006848406916300287`
- `version6`: `20837218.68677925` / `-0.007751491105750019` / `-0.007751491105750019`
- `version4`: `20809652.69445548` / `-0.009064157406881934` / `-0.009844053655299723`

### 11.2 v7 core（strategy7）

来源：`core/v7_nav.csv`。`clock_next_open` 全现金 NAV（H2：UNFILLED / all-cash 合法）。下表为 CSV **raw**（勿改写）。

| cell_id | strategy | final_equity | total_return | max_drawdown | rank | status |
|---|---|---:|---:|---:|---:|---|
| clock_next_open_fullstrat | strategy7 | 21000000.0 | 0.0 | 0.0 | 1 | OK |
| slip_5bp_fullstrat | strategy7 | 20888926.133852407 | -0.005289231721313903 | -0.008953602946315087 | 1 | OK |
| slip_10bp_fullstrat | strategy7 | 20882857.42749297 | -0.005578217738430036 | -0.009217363990877359 | 1 | OK |
| slip_20bp_fullstrat | strategy7 | 20883082.720336474 | -0.00556748950778696 | -0.008826469560831107 | 1 | OK |

### 11.3 ModeB core

来源：`core/modeb_nav.csv`。每格一行 = 网格内 `total_return` 最高（oracle 排除）；`daily_entry_source=aggregated_from_1min_none_lineage`。DD 按 harness 原样（不翻号）。**禁止**与 Book/v7 比 NAV。下表为 CSV **raw**。

| cell_id | strategy | final_equity | total_return | max_drawdown | rank | status |
|---|---|---:|---:|---:|---:|---|
| clock_next_open_fullstrat | r1_n1 | 1100000000.0 | 0.0 | 0.0 | 1 | OK |
| slip_5bp_fullstrat | livermore_l2_stale8_y10 | 1099568890.0783827 | -0.0003919181105611541 | 0.0006548533980148803 | 1 | OK |
| slip_10bp_fullstrat | r2_x5_yinf_n8 | 1099544407.5191047 | -0.0004141749826320735 | 0.0005723236028580957 | 1 | OK |
| slip_20bp_fullstrat | r2_x10_yinf_n10 | 1099473750.7751617 | -0.0004784083862165971 | 0.0007887034726634252 | 1 | OK |

### 11.4 Book version9（`s9_bvot` 池戳 · 不与 stock_pool 重排）

来源：`v9/book_nav.csv`。ModeB/v7：**N/A**。下表为 CSV **raw**（`clock_next_open` 全现金合法）。

| cell_id | strategy | final_equity | total_return | max_drawdown | rank | status |
|---|---|---:|---:|---:|---:|---|
| clock_next_open_fullstrat | version9 | 21000000.0 | 0.0 | 0.0 | 1 | OK |
| slip_5bp_fullstrat | version9 | 21051530.530446403 | 0.002453834783161968 | -0.001964193052529928 | 1 | OK |
| slip_10bp_fullstrat | version9 | 21049802.365745895 | 0.002371541225995033 | -0.0019968267374191884 | 1 | OK |
| slip_20bp_fullstrat | version9 | 21046420.56548216 | 0.0022105031181980372 | -0.0020598449692958987 | 1 | OK |

### 11.5 Book version10（`s10_tr` 池戳 · lake∩TR · 不与 stock_pool/v9 重排）

来源：`v10/book_nav.csv`。ModeB/v7：**N/A**。下表为 CSV **raw**。

| cell_id | strategy | final_equity | total_return | max_drawdown | rank | status |
|---|---|---:|---:|---:|---:|---|
| clock_next_open_fullstrat | version10 | 21000193.269587517 | 9.203313691363846e-06 | -3.2660913105164724e-06 | 1 | OK |
| slip_5bp_fullstrat | version10 | 21015696.33937717 | 0.0007474447322461941 | -0.0014266530880640005 | 1 | OK |
| slip_10bp_fullstrat | version10 | 21008914.105951127 | 0.00042448123576788177 | -0.0015216375303468421 | 1 | OK |
| slip_20bp_fullstrat | version10 | 20997829.485809036 | -0.0001033578186173667 | -0.0017479036136753834 | 1 | OK |

### 11.6 范围声明

- 本 PR：**docs + research exports only**；无 production Python / fill / scan / fee / defaults / hot-path 改动。
- 数字仅转录权威 CSV；未在本 VM 重跑回测。
- Draft only — **do not merge without human/bt tip**.
