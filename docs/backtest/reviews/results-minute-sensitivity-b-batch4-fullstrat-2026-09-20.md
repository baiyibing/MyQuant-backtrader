# 分钟敏感对照 B · 第四批结果（全策略 NAV / DD / 引擎内排名 · 2026-09-20）

**状态：`EXECUTED_PARTIAL`（4090 `--execute` 已完成；ModeB 基线已于 2026-09-21 ModeB-only 重跑回填；Book **version9** 已于 2026-09-21 用 `export_strategy9_pool`→`s9_bvot` 池回填）。** Book 8/9（含 v9）、v7、ModeB 基线（`baseline_default_clock_fee`）已填；**version10** 与全策略 clock_next_open / slip_* 轴仍为 **DATA_GAP**。局部事件 bp（batch2/3）**禁止**粘贴进下表；**禁止**跨引擎比 NAV 论优劣；`production_C=frozen`。

依据：[设计](design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md)；[计划](plan-minute-sensitivity-b-2026-09-20.md)；导出 [batch4_fullstrat/](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat/)（Book v1–v8 / v7）；ModeB 基线重跑戳 `batch4_fullstrat_modeb_rerun_20260921`（4090 @ tip `a1e7dea`）；Book version9 戳 [`batch4_fullstrat_v9_s9bvot_20260921`](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat_v9_s9bvot_20260921/)（4090 @ tip `51e0195`，pool=`s9_bvot` **非** `stock_pool`；见 [addendum](addendum-batch4-v9-s9bvot-fill-2026-09-21.md)）。

| 项 | 取值 |
|---|---|
| 跑批 | 4090，2026-09-20 20:49:32–20:50:19 (+08)，**EXIT=0**，~47s |
| git HEAD | `93406f357e6c3e5ca695a15d43af106f8ee5e558` |
| BASE tip | ≈ `ac1fa97`（#140） |
| 窗 | `20260825`–`20260909`（pool∩分钟湖） |
| access | `qlib_bin_1min` @ `C:\Users\wangc\.qlib\qlib_data\my_data_1min` |
| bar 标签 | `lake_index_is_bar_start_wallclock` |
| 费用 | `DEFAULT_SCHEDULE=BILATERAL_10BP` |
| pool | 原批 `stock_pool`（Book v1–v8 / v7 / ModeB）；**version9** 用 `export_strategy9_pool`→host `D:\exports\s9_bvot_20260825_20260909`（拒 `stock_pool/`）；version10 仍需 `export_strategy10_pool`（本批 DATA_GAP） |

---

## 1. 单轴矩阵

| cell_id | clock | slip | Book | v7 | ModeB |
|---|---|---|---|---|---|
| `baseline_default_clock_fee` | 生产默认 | 0 | **FILLED**（引擎内 #1 = version8） | **FILLED** | **FILLED**（引擎内 #1 = livermore_l2_stale8_y10；`modeb_ok=1`） |
| `clock_next_open_fullstrat` | next-open | 0 | DATA_GAP | DATA_GAP | DATA_GAP |
| `slip_5bp_fullstrat` | 默认 | 5bp/边 | DATA_GAP | DATA_GAP | DATA_GAP |
| `slip_10bp_fullstrat` | 默认 | 10bp/边 | DATA_GAP | DATA_GAP | DATA_GAP |
| `slip_20bp_fullstrat` | 默认 | 20bp/边 | DATA_GAP | DATA_GAP | DATA_GAP |

证据：`matrix.csv` / `data_gaps.csv`。clock/slip 全策略轴无 research-only 钩子；不改生产 C。

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
| version10 | — | — | — | — | **DATA_GAP** / out of scope：需 `export_strategy10_pool.py`（TR pool）；**≠** s9；勿声称 v10 已填 |

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
2. Book / v7 / ModeB **分列**；禁止用本批 NAV 宣称引擎优劣。
3. 全策略 clock 交换 / slip 轴无钩子 → DATA_GAP；不得为填格改生产 fill/scan/fee。
4. `production_C=frozen`。

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
| `batch4_fullstrat_v9_s9bvot_20260921/README.md` | 池策略 + 数字 + tip |
| `batch4_fullstrat_v9_s9bvot_20260921/manifest.json` | tip/pool day counts / 数字元数据 |
| 4090 runner 旁路 | `runner_artifacts/`（未全部入库；摘要 CSV 已入库） |

---

## 7. 下一步（建议）

1. ModeB 基线格已由 4090 ModeB-only 重跑回填（见 §4 / §8）；import 修复合入后无需再为同一 DATA_GAP 重跑。
2. Book **version9** 已由 `s9_bvot` 池回填（见 §2 / §9）；**version10** 仍 DATA_GAP（需 `export_strategy10_pool`，≠ s9）。
3. 全策略 clock_next_open / slip_* 轴：仅当存在**明确 research-only** 钩子时再开；否则保持 DATA_GAP。


---

## 8. ModeB 基线回填（2026-09-21 · `batch4_fullstrat_modeb_rerun_20260921`）

Import 根因与修见 [addendum](addendum-batch4-modeb-import-fix-2026-09-21.md)。4090 于 tip `a1e7dea` 以 ModeB-only 重跑关闭 ModeB 基线 DATA_GAP（EXIT=0，~2026-09-21 08:14 +08；导出戳 `batch4_fullstrat_modeb_rerun_20260921`）。

- 引擎 ModeB；策略 `livermore_l2_stale8_y10`；cell `baseline_default_clock_fee`
- `final_equity=1099605762.3151746`；`total_return=-0.0003583978952958367`（−0.03584%）；`max_drawdown=0.0006438975472074711`（0.06439%，harness 原样不翻号）；status OK；`modeb_ok=1`
- Book/v7 在本 ModeB-only 跑为 `engine_skipped`：**不空白** §1–§3 中来自 #142 的 Book/v7 数字
- 仍 DATA_GAP：全策略 `clock_next_open` / `slip_*`；**version10**（需 strategy10 TR pool）。version9 已另戳回填（§9）

`production_C=frozen`（本回填 docs-only；不改 fill/scan/fee/defaults/hot-path）。


---

## 9. Book version9 回填（2026-09-21 · `batch4_fullstrat_v9_s9bvot_20260921`）

池与数字见 [addendum](addendum-batch4-v9-s9bvot-fill-2026-09-21.md)。4090 于 tip `51e0195` 先跑 `export_strategy9_pool.py`→`D:\exports\s9_bvot_20260825_20260909`（EXIT=0；12 日 CSV；79 name-occurrences；**从未写入 stock_pool/**），再 Book-only `--strategies version9` 关闭 version9 基线 DATA_GAP。

- 引擎 Book；策略 `version9`；cell `baseline_default_clock_fee`
- clock=`production_default`；slip=0；fee=`DEFAULT_SCHEDULE=BILATERAL_10BP`；access=`qlib_bin_1min`
- `final_equity=21053316.65`；`total_return=0.0025`（+0.25%）；`max_drawdown=-0.0019`（−0.19%）；status OK；within_engine_rank 1（本戳仅 version9）
- pool = **s9_bvot 导出**，**不是** `stock_pool`；主机路径在仓外（`/exports/` gitignore）；策略与 day counts 写在本戳 README / addendum，不提交 live CSV
- **保留** §2 中 #142 stock_pool Book v1–v8 与 §4 ModeB 数字，不空白、不跨池重排、**禁止跨引擎排名**
- **version10 ≠ s9**：仍 DATA_GAP / out of scope（需 `export_strategy10_pool.py`）
- 全策略 `clock_next_open` / `slip_*` 仍 DATA_GAP

`production_C=frozen`（本回填 docs + research exports only；不改 fill/scan/fee/defaults/hot-path）。
