# 分钟敏感对照 B · 第四批设计（全策略 NAV / DD / 引擎内排名 · 2026-09-20）

**范围**：只读研究路径，用既有全策略 runner 在**扩展窗口**上诚实填补 batch1–3 留下的全策略净收益 / 最大回撤 / 引擎内排名 `DATA_GAP`（能填则填，不能填则空白）。**不**改 production_C（fill / scan / fee / default clock）；**不**在 VM 跑多日湖回测；4090 由 parent 执行。

依据：[计划 SSOT](plan-minute-sensitivity-b-2026-09-20.md)；[batch1](results-minute-sensitivity-b-batch1-2026-09-20.md) / [batch2](results-minute-sensitivity-b-batch2-2026-09-20.md) / [batch3 Mode B](results-minute-sensitivity-b-batch3-modeb-2026-09-20.md)；产物目录 `backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat/`。

BASE tip：`ac1fa97`（Merge #140 / `origin/master`）。

---

## 1. 能算 vs 必须 DATA_GAP

| 指标 / 轴 | Book（csv_minute_backtest） | v7（csv_minute_backtest_v7） | Mode B（unified_exit_modeb） |
|---|---|---|---|
| **默认时钟 + DEFAULT_SCHEDULE** 全策略 NAV / return / maxDD | **可填**（既有 CLI，`--minute-source qlib_1min`） | **可填**（同上） | **可填**（研究 harness 库调用：入场=同 1min none 聚合日收；分钟=同一 qlib_1min；**禁止** `my_data` day.bin 后复权入场） |
| **引擎内排名** | **可填**（同窗口多卖点书 version1–6,8–10 按 return 排序；不含 topk_*） | N/A（单策略；`within_engine_rank=1` 仅自指） | **可填**（`ranking.csv` / 网格 `StrategyMetrics.total_return`） |
| **全策略 clock 交换**（next-open 等） | **DATA_GAP** | **DATA_GAP** | **DATA_GAP** |
| **全策略 slip 轴**（每边 5/10/20bp） | **DATA_GAP** | **DATA_GAP** | **DATA_GAP** |
| 跨引擎 NAV 优劣比较 | **禁止** | **禁止** | **禁止** |
| 把 batch2/3 局部事件 bp Δ 贴进 NAV 格 | **禁止** | **禁止** | **禁止** |

### 为何 clock / slip 全策略轴为 DATA_GAP

- Book / v7 / Mode B 生产默认成交时钟与费率写死在引擎路径；CLI **无** research-only「全策略 clock 交换」或「全策略滑点」开关。
- 若为填格而改 `ashare_fill_clock` / 默认 fee / 静默 fork 生产路径 → 触犯 **production_C frozen**。
- batch2/3 的 local-event clock / cost 叠层**仅局部**，不得冒充组合 NAV。本批对这两轴显式留空，并仍交付**默认时钟**基线全策略 NAV（诚实填）。

---

## 2. 扩展窗口 / 符号提案（相对 batch2：3 日 × 5 标的）

| 项 | batch2（局部事件） | **batch4 提案（全策略）** | 依据 |
|---|---|---|---|
| 日历窗 | `20260916`–`20260918` | **`20260825`–`20260909`** | 仓内 `stock_pool/*.csv` 在该闭区间有 **12** 个交易日文件；`MINUTE_LAKE_END=20260909`；batch2 的 09-16..18 **无** pool CSV，不能支撑 Book/v7 全策略名单驱动 |
| 符号 | 固定 5：`000021.SZ,…` | **窗内 pool 并集**（约 **69** 个六位码；runner 会规范为 `.SH/.SZ`） | 自然扩容；不手工挑「好看」子集 |
| 分钟访问 | `qlib_bin_1min` | **优先** `qlib_bin_1min` → `C:\Users\wangc\.qlib\qlib_data\my_data_1min`；回退同血缘 `E:\stock_data` parquet | 与 batch2/3 一致；`source=parquet_lineage` |
| bar 标签 | START 墙钟 | **START**（`lake_index_is_bar_start_wallclock`） | 同 batch2 |
| Mode B 入场 | 局部：1min 聚合 | **全策略同样**：`daily_entry_source=aggregated_from_1min_none_lineage` | 禁止 qlib day.bin 后复权 |

**缺数规则**：某码/某日在 qlib_1min 无 bar → 该引擎该次 run 的 coverage / `data_gaps.csv` 记 `DATA_GAP`，**不**发明价格；若整窗无法加载 → 对应 NAV 格留空。

**可选收缩**（4090 超时）：同一 fee/clock 基线，把窗缩为 `20260901`–`20260909`（7 日）并在 manifest 注明 `window_contracted=true`；仍须大于 batch2 的 3 日。

---

## 3. 费用基线钉死

| 引擎 | 费用 | 滑点 | 说明 |
|---|---|---|---|
| Book | `DEFAULT_SCHEDULE` = `BILATERAL_10BP`（每边 10bp，min=0） | **0**（无 CLI slip；本批不叠） | `backtest/research/ashare_fees.py` |
| v7 | 同上 `DEFAULT_SCHEDULE` | **0** | `csv_minute_backtest_v7` 默认 `fee=DEFAULT_SCHEDULE` |
| Mode B | `modea.COMMISSION` 双边 10bp 线性 | **0** | 与 batch3 研究叠层一致；不改生产 Mode B 合同 |

**禁止**在本批引入 `REPLACE_COMMISSION_3BP_…` 或 QLIB_PORTANA 作为 NAV 主表费用（那些属 batch1/2 局部/替换情景）。

---

## 4. 单轴矩阵（clock XOR slip；永不同格）

| cell_id | clock | slip | Book NAV/DD/rank | v7 NAV/DD | Mode B NAV/DD/rank |
|---|---|---|---|---|---|
| `baseline_default_clock_fee` | 生产默认 | 0 / DEFAULT_SCHEDULE | **4090 可填** | **4090 可填** | **4090 可填** |
| `clock_next_open_fullstrat` | next-open 研究交换 | 0 | **DATA_GAP** | **DATA_GAP** | **DATA_GAP** |
| `slip_5bp_fullstrat` | 生产默认 | 5bp/边 | **DATA_GAP** | **DATA_GAP** | **DATA_GAP** |
| `slip_10bp_fullstrat` | 生产默认 | 10bp/边 | **DATA_GAP** | **DATA_GAP** | **DATA_GAP** |
| `slip_20bp_fullstrat` | 生产默认 | 20bp/边 | **DATA_GAP** | **DATA_GAP** | **DATA_GAP** |

同一 `cell_id` 内不得同时改 clock 与 slip。局部事件 Δbp **不得**写入上表数值列。

---

## 5. Book / v7 / Mode B 分列报告规则

1. **分文件、分表**：`book_nav.csv` / `v7_nav.csv` / `modeb_nav.csv`（及各自 rank）；禁止合成「三引擎总排名」或「谁更优」表。
2. **引擎内排名**：Book 仅在 Book 书之间；Mode B 仅在 Mode B 网格标签之间；v7 无跨书对比。
3. **口径声明**：每行带 `engine`、`cell_id`、`fee_schedule`、`clock`、`access`、`window`、`daily_entry_source`（Mode B）。
4. **oracle**（若 Mode B 报告含）：继续标 `EX_POST_UPPER_BOUND_NOT_EXECUTABLE`，不入可执行 NAV/rank。

---

## 6. 既有表面（不重造）

| 用途 | 入口 |
|---|---|
| Book 全策略 | `backtest/research/csv_minute_backtest.py --strategy versionN --minute-source qlib_1min --qlib-1min-root …` |
| v7 全策略 | `backtest/research/csv_minute_backtest_v7.py --qlib-1min-root …` |
| Mode B 网格 | `scripts/research/run_unified_exit_modeb.py`（湖默认）**或** batch4 harness 库路径注入 1min 聚合入场 |
| 局部事件（勿混入 NAV） | `scripts/research/run_minute_sensitivity_b.py` + batch1/2/3 导出 |
| 1min 读 + 日收聚合 | `backtest/research/qlib_bin_1min.py`（`load_qlib_bin_1min_bars` / `daily_closes_from_minutes`） |

---

## 7. 4090 命令配方（路径占位）

```powershell
$env:OSKH_SOURCE_PARQUET_ROOT='E:\stock_data'
$env:QLIB_1MIN_ROOT='C:\Users\wangc\.qlib\qlib_data\my_data_1min'
cd D:\PycharmProjects\MyQuant-backtrader
git fetch origin
git checkout research/minute-sensitivity-b-batch4-fullstrat-2026-09-20
git pull origin research/minute-sensitivity-b-batch4-fullstrat-2026-09-20

# 薄封装：解析已有 runner 产物 → batch4_fullstrat CSV/JSON（勿覆盖已填目录则换 stamp）
D:\anaconda3\envs\vanna312\python.exe scripts\research\run_minute_sensitivity_b_batch4_fullstrat.py `
  --execute `
  --start 20260825 --end 20260909 `
  --qlib-1min-root C:\Users\wangc\.qlib\qlib_data\my_data_1min `
  --pool-dir stock_pool `
  --output-dir backtest\research\exports\minute_sensitivity_b_20260920\batch4_fullstrat

# 或逐步手工 Book 一例（version1）：
D:\anaconda3\envs\vanna312\python.exe backtest\research\csv_minute_backtest.py `
  --strategy version1 --start 20260825 --end 20260909 `
  --minute-source qlib_1min `
  --qlib-1min-root C:\Users\wangc\.qlib\qlib_data\my_data_1min `
  --pool-dir stock_pool `
  --out-dir backtest_output\batch4_book_v1_20260825_20260909

# v7：
D:\anaconda3\envs\vanna312\python.exe backtest\research\csv_minute_backtest_v7.py `
  --start 20260825 --end 20260909 `
  --pool-dir stock_pool `
  --minute-source qlib_1min `
  --qlib-1min-root C:\Users\wangc\.qlib\qlib_data\my_data_1min `
  --output-dir backtest_output\batch4_v7_20260825_20260909
```

VM 无湖：`--dry-run` / `--emit-stubs` / `--help` 即可；不要求本地 qlib。

---

## 8. 产物清单

| 路径 | 说明 |
|---|---|
| 本设计 | `docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md` |
| 结果桩 | `docs/backtest/reviews/results-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md` |
| harness | `scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py` |
| 导出 | `backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat/`（matrix / stubs / manifest） |

生产 Python **零行为变更**；仅 docs + research harness + 导出桩。
