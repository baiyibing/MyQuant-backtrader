# 分钟敏感对照 B · 第四批结果（全策略 NAV / DD / 引擎内排名 · 2026-09-20）

**状态：`EXECUTED_PARTIAL`（4090 `--execute` 已完成；ModeB 基线已于 2026-09-21 ModeB-only 重跑回填；Book **version9** 已于 2026-09-21 用 `export_strategy9_pool`→`s9_bvot` 池回填）。** Book version10 已于 2026-09-21 用 Source-B `s10_tr` 池回填（研究 universe=lake∩TR；见 §10）。Book、v7、ModeB 基线（`baseline_default_clock_fee`）已填；全策略 clock_next_open / slip_* 数值仍待合并后 4090；最新研究能力为 **FILLABLE（H2 + Q2）**，见下方 Slice B。局部事件 bp（batch2/3）**禁止**粘贴进下表；**禁止**跨引擎比 NAV 论优劣；`production_C=frozen`。

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
| pool | 原批 `stock_pool`（Book v1–v8 / v7 / ModeB）；**version9** 用 `export_strategy9_pool`→host `D:\exports\s9_bvot_20260825_20260909`（拒 `stock_pool/`）；**version10** 用 Source-B `resist_tr_bb_1000`→host `D:\exports\s10_tr_bb1000_20260825_20260909`（研究 lake∩TR 后 fail_closed；从未写 `stock_pool/`；见 §10） |

---

## 1. 单轴矩阵

| cell_id | clock | slip | Book | v7 | ModeB |
|---|---|---|---|---|---|
| `baseline_default_clock_fee` | 生产默认 | 0 | **FILLED**（引擎内 #1 = version8） | **FILLED** | **FILLED**（引擎内 #1 = livermore_l2_stale8_y10；`modeb_ok=1`） |
| `clock_next_open_fullstrat` | next-open | 0 | DATA_GAP | DATA_GAP | DATA_GAP |
| `slip_5bp_fullstrat` | 默认 | 5bp/边 | DATA_GAP | DATA_GAP | DATA_GAP |
| `slip_10bp_fullstrat` | 默认 | 10bp/边 | DATA_GAP | DATA_GAP | DATA_GAP |
| `slip_20bp_fullstrat` | 默认 | 20bp/边 | DATA_GAP | DATA_GAP | DATA_GAP |

证据：原执行戳 `matrix.csv` / `data_gaps.csv`。2026-09-21 **FULL HUMAN CUT 已齐（H2 + 卖单到期次日重评）**，取代此前 sell pending 桩，恢复 Slice B：全组合所有买卖 fill 换为研究 `next_tradable_open`；买卖严格同日到期；接受 `UNFILLED` / 全现金 NAV，绝不静默保留 baseline 入场；未成交卖单到期清除，下一交易日正常策略重新判断是否卖出，不保留退出意图等待。详见 [设计 §9](design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md#9-research-only-fullstrat-clockslip-hooks)。本次先提交完整裁定文档，再实施 hooks + pins；通过后能力状态转 `FILLABLE`，所有新增 clock/slip 数值继续留空，等待合并后的 4090 slice D。上表及既有导出是历史执行状态，不覆盖历史数字；`production_C=frozen`，不 merge。


**Slice B 按最新 Q2 恢复**：`40afca4` / `dde7a6f` 的 Q1 固定股数及停点叙述已被人裁覆盖。信号股数暂定，next-open / slip 成交价重定量；10,000 预算 / 10,050 现金 / 信号 10 → 暂定 1,000，open 10.1 → 900 股成交、现金 950.91。固定股数后 `cash_reject_terminal` 是必须排除的反例。H2 与卖单到期次日重评继续绑定；新增数值待合并后 4090。

历史验证（实现前）：本次 gates（显式 `/workspace/vanna312/bin/python3`；系统 python3 未装 pytest / ruff）：既有非 production / benchmark 测试 **1422 passed, 2 skipped, 24 deselected**（exit 0，24.78s），harness `--help` exit 0；新 hook pins 文件不存在，专项 pytest exit 4（未通过）。无 Python 改动，ruff 无 touched 目标。现有函数 sizing 复现、`git diff --check`、修改文档 UTF-8 / BOM=0 / NUL=0 通过。既有测试通过不代表尚未实现的 hooks 已验证。


### Slice B（2026-09-21 · Q2 + H2；data-free）

| cell | Book | v7 | ModeB | 新增 NAV / return / DD / rank |
|---|---|---|---|---|
| clock_next_open_fullstrat | FILLABLE | FILLABLE | FILLABLE | 空白，待合并后 4090 |
| slip_5bp_fullstrat | FILLABLE | FILLABLE | FILLABLE | 空白，待合并后 4090 |
| slip_10bp_fullstrat | FILLABLE | FILLABLE | FILLABLE | 空白，待合并后 4090 |
| slip_20bp_fullstrat | FILLABLE | FILLABLE | FILLABLE | 空白，待合并后 4090 |

Q2 已通过实际 adapter 对照：预算 10,000 / 现金 10,050，信号价 10 的暂定 1,000 股，在 open 10.1 重定量 900 股成交，余额 950.91；Q1 固定股数拒单不是 adapter 合同。H2 全部 fill 覆盖、START 14:55 当日到期、全现金 NAV、卖单到期清除与次日重评通过。零参数委托原引擎，production_C=frozen；#151/#152 contested files 和历史数字未改。

验证环境：显式 PATH 选 `/workspace/vanna312/bin/python3`。专项 **48 passed**（0.99s）；全套 `-m "not production and not benchmark" tests/` **1475 passed, 2 skipped, 24 deselected**（22.76s；既有 TR window warning 1 条）；ruff touched Python、harness `--help`、diff/UTF-8/BOM=0/NUL=0 均通过。Grok 结果待核后记录。没有执行 4090 数值跑批。

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
| `batch4_fullstrat_v9_s9bvot_20260921/data_gaps.csv` | v9 FILLED / 当时 v10 DATA_GAP 的历史登记（v10 后续回填见 §10） |
| `batch4_fullstrat_v9_s9bvot_20260921/README.md` | 池策略 + 数字 + tip |
| `batch4_fullstrat_v9_s9bvot_20260921/manifest.json` | tip/pool day counts / 数字元数据 |
| `batch4_fullstrat_v10_s10tr_20260921/book_nav.csv` | Book version10 基线（s10_tr；FILLED） |
| `batch4_fullstrat_v10_s10tr_20260921/matrix.csv` | v10-only 矩阵；clock/slip 仍 DATA_GAP |
| `batch4_fullstrat_v10_s10tr_20260921/data_gaps.csv` | v10 基线回填 / 剩余缺口 |
| `batch4_fullstrat_v10_s10tr_20260921/README.md` | 池策略、lake∩TR universe、主机产物引用 |
| `batch4_fullstrat_v10_s10tr_20260921/manifest.json` | pool day counts / 数字元数据；未提供运行 tip |
| 4090 runner 旁路 | `runner_artifacts/`（未全部入库；摘要 CSV 已入库） |

---

## 7. 下一步（建议）

1. ModeB 基线格已由 4090 ModeB-only 重跑回填（见 §4 / §8）；import 修复合入后无需再为同一 DATA_GAP 重跑。
2. Book **version9** 已由 `s9_bvot` 池回填（见 §2 / §9）；**version10** 已由 Source-B `s10_tr` 池回填（见 §2 / §10；研究 universe=lake∩TR 后 fail_closed）。
3. 全策略 clock_next_open / slip_* 轴：仅当存在**明确 research-only** 钩子时再开；否则保持 DATA_GAP。


---

## 8. ModeB 基线回填（2026-09-21 · `batch4_fullstrat_modeb_rerun_20260921`）

Import 根因与修见 [addendum](addendum-batch4-modeb-import-fix-2026-09-21.md)。4090 于 tip `a1e7dea` 以 ModeB-only 重跑关闭 ModeB 基线 DATA_GAP（EXIT=0，~2026-09-21 08:14 +08；导出戳 `batch4_fullstrat_modeb_rerun_20260921`）。

- 引擎 ModeB；策略 `livermore_l2_stale8_y10`；cell `baseline_default_clock_fee`
- `final_equity=1099605762.3151746`；`total_return=-0.0003583978952958367`（−0.03584%）；`max_drawdown=0.0006438975472074711`（0.06439%，harness 原样不翻号）；status OK；`modeb_ok=1`
- Book/v7 在本 ModeB-only 跑为 `engine_skipped`：**不空白** §1–§3 中来自 #142 的 Book/v7 数字
- 仍 DATA_GAP：全策略 `clock_next_open` / `slip_*`。version9 / version10 已另戳回填（§9 / §10）

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
- 全策略 `clock_next_open` / `slip_*` 仍 DATA_GAP

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

全策略 `clock_next_open` / `slip_*` 仍 **DATA_GAP**。
`production_C=frozen`（docs + research exports only；不改 production Python / fill / scan / fee / defaults / hot-path）。
