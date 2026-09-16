# Survey · 复权 / adj_factor 数据准备（宿主本机只读调研）

> **日期**：2026-09-16（Asia/Shanghai）。
> **执行**：宿主本机 agent（zcode）；环境 `D:\anaconda3\envs\vanna312\python.exe`，湖 = `F:\stock_data`（.authority → F），全程只读（未写湖、未改引擎、未重生 fixture、未开 GPU）。
> **服务对象**：[handoff-exdiv-adj-data-prep-intro-2026-09-16.md](handoff-exdiv-adj-data-prep-intro-2026-09-16.md) §4 checklist → 战略 [NP2](strategic-analysis-opus5-next-2026-09-16.md) 前置。
> **代码基线**：master `aec5abe`。
> **性质**：survey only；NP2 计数与裁决不在本文内完成。

---

## 0. 结论速览

1. **GO**：NP2 只读计数的数据前提全部具备，可直接开。
2. **主源必须用 `ex_date_index.parquet`**，因子跳变只配当副证——`cumulative_adj_factor` 的日际变化被 **0.01 元价格栅格舍入噪声**污染（|Δf/f| p90=3e-4，低价股 >1e-2），0.5% 以内的现金分红（窗内 1,372 起）整体淹没在噪声带，任何纯阈值法都不干净。
3. **冲击面不小，NP2 预期非零**：D 烟测同窗全市场 **4,389 起除权 / 3,743 码**（≈67% 市场），**D 烟测交易过的 251 码中 170 码命中 199 起**——「持仓期命中」计数有充足样本。
4. 跳变**记在除权当日**（2,988/2,989 可检事件当日发生），NP2 计「持仓区间 ∩ ex_date」直接可用。

---

## 1. 湖上检查结果（对应启动令 ①–④）

### ① adj_factor.parquet（`F:\stock_data\adj_factor.parquet` + `adj_factor.meta.json`）

| 项 | 值 |
|----|----|
| schema | `date, stock_code, close_front, close_none, cumulative_adj_factor, adj_factor_back`（**与 SSOT 完全一致**；date 为 date 对象） |
| 行数 / 码数 | 17,970,813 行 / 5,591 码 |
| 日期范围 | 1990-12-19 → 2026-09-15 |
| `stock_code` 格式 | `^\d{6}\.(SH|SZ|BJ)$` 违例 **0**（无 Windows 路径污染） |
| meta | `build_time 2026-09-15T17:07+08:00`，`data_max_date 2026-09-15`，`source scripts.data.finish_adj_factor_duckdb`，`stock_count 5591` |
| cum 因子 NaN | 全史 568,067 行（3.2%）；**窗内仅 1,676 行（0.14%）** |
| 脏段提示 | 全史 `cumulative_adj_factor` min=**-15.09**（早期脏数据）；窗内 ≤0 行数 **0** |

### ② 窗内（20251023–20260909）因子日际跳变 × ex 真值交叉

跳变分布（|Δf/f|，n≈119.5 万窗内行）：median **2.2e-16**（机器精度，真恒定段）但 p90=3.0e-4、p99=1.3e-3——**舍入噪声**（front/none 各自 0.01 元取整，随价格水平放大）。

阈值扫描（jumps = |Δf/f|>ε 的 (code,date)；真值 = ex_date_index 窗内 4,389 事件）：

| ε | jumps | 命中 ex | precision | recall |
|---|------:|------:|--------:|-------:|
| 1e-3 | 19,440 | 4,151 | 21.4% | 94.6% |
| 2e-3 | 6,427 | 3,835 | 59.7% | 87.4% |
| **5e-3** | 3,133 | 2,988 | **95.4%** | 68.1% |
| 1e-2 | 2,111 | 2,078 | 98.4% | 47.3% |

无 ε 同时干净 → **跳变只配副证**（推荐 ε=5e-3 作 parity 检查）。

### ③ period=1d 分区对齐

- symbol 目录数：none **5,621** / front 5,597 / back 5,544；**front ⊆ none 成立**（差集空；24 码 none 有 front 无——因子 NaN 行来源之一，多为边缘/退市码）。
- 抽样 40 码最新交易日：none/front **0 不一致**（`time` 列同为 1789430400 ≈ 2026-09-15；分区 schema 为 `time,open,high,low,close,volume,amount`）。

### ④ ex_date_index.parquet（`F:\stock_data\ex_date_index.parquet`）

57,761 行，1991-03-11 → 2026-09-15，5,445 码；列 `stock_code, ex_date, dr, fetched_at`；`fetched_at` 持续增量（尾部 09-08/09/10/09-14/09-15 均有批次）——**新鲜**。与跳变交叉见②。

---

## 2. 引子 §4 checklist 逐条

### A. Schema / 权威源

- **A1 ✅** 见①：schema/格式与 SSOT 一致，零违例。
- **A2 ✅** 见③：front⊆none 成立，抽样最新日全对齐。
- **A3 ✅** 本仓 **已无生产脚本**（`scripts/data/` 无 run_daily_adjusted_fast / update_adjusted_daily / detect_ex_date / finish_adj_factor_duckdb；仅 `oskh_data/adj_factor.py`（计算模块）+ `adj_factor_meta.py` 留存）。权威生产者 = 1.3（meta `source` 指 1.3 侧脚本），本仓纯消费——与 SSOT「本仓不再下载行情」一致。

### B. 更新节奏与覆盖

- **B1 ✅** 每日更新实证：adj meta 为 2026-09-15 盘后 build；ex index fetched_at 增量到 09-15。除权股 front 重下频率 = 除权事件频率（B3）。
- **B2 ✅** 无滞后：`adj_factor.data_max_date`=2026-09-15 = none/front 分区最新日；烟测窗（止 20260909）覆盖满，`max_stale_days` 未触发。
- **B3 ✅** 窗内全市场 **4,389 起 / 3,743 码**；月度：10月104 · 11月172 · 12月148 · 1月102 · 2月60 · 3月15 · 4月128 · **5月895 · 6月1742 · 7月779** · 8月157 · 9月87（**5–7 月分红季占 86%**）。D 烟测 daily 251 交易码中 **170 码 / 199 起**命中。

### C. 累计因子定义与除权检测

- **C1 ✅** 定义即 `close_front/close_none`（`oskh_data/adj_factor.py` 模块头；数据验证：无除权段 |Δf/f| 中位 = 机器精度）。但「近似恒定」须打折：舍入噪声见②。无 back 推导参与 cum 列。
- **C2 ✅ 裁决：主源 = `ex_date_index.parquet`**（QMT `get_divid_factors` 检测产物，小额分红全覆盖，`dr` 仅检测用不参与推导）；**副证 = 因子跳变 ε=5e-3**（P95.4%/R68.1%）。纯阈值法否决：1,372 起真事件幅度 ≤5e-3 淹没于噪声带。
- **C3 ✅ 跳变记在除权当日**：4,389 起中当日跳（>5e-3）2,988、前一交易日 1、噪声带内 1,372、无因子行 28。NP2「持仓区间 ∩ ex_date」按当日计。

### D. front 可用性边界

- **D1 ✅** 非除权日 front≈none（路径 B，因子≈1 段成立）；除权后 front 历史被整段重写，且**湖上只有单份"最新版 front"，无按日落盘版本**——若做对照实验必须先固定 as-of 口径（缺口，见 §3）。
- **D2 ✅** 三档成本确认（数据前提齐备，本文不选型）：①front 喂成交核 = 改写全部历史 NAV+golden（禁，须独立片）；②因子修 limit/cost/peak = E-R5 级裁决 + 局部 fixture；③事后归因 = NP2 本体，零引擎改动。

### E. 语义陷阱

- **E1 认可**：计数 = 持仓区间 ∩ ex_date，仅 D+1 起仍持仓的 lot（买入日当日不评）。
- **E2 认可**：交易所按除权参考价定档；`l2_analytics/ref_data.py` 的 `prev_close × cum[D-1]/cum[D]`（即 `close_front[D-1]/cum[D]`）为候选算法，数据前提已证（因子当日跳变）；是否足够接近交易所档留给裁决。
- **E3 ✅ 幅度分层**（2,988 起当日跳，**全部正跳** = 除权方向无一反例）：|Δ|>5% **493 起**（送转主导，样例 +150%：300125.SZ/300093.SZ 等）；1–5% 1,585 起；0.5–1% 910 起；另 1,372 起 ≤0.5%（小额分红，噪声带）。→ **「假 -30% 止损」叙事主要由 >5% 送转段贡献**；≤0.5% 档只可能造成涨跌停模板边缘误差。
- **E4 认可**：分钟链同为 none，先日线同窗，分钟后置。
- **E5 认可**：NP2 与 NP1（配给）/费率严格分离。

---

## 3. Go / No-Go 与缺口

**GO——NP2 只读计数可直接开**，设计锁三条：

1. **主源 `ex_date_index.parquet`**；因子跳变（ε=5e-3）仅作 parity 副证（防 ex index 漏检大额事件）；
2. 计数窗 = D 烟测同窗 **20251023–20260909**；命中 = **持仓区间 ∩ ex_date**（D+1 起持仓的 lot）；
3. 输出对齐引子 §7：①持仓期内命中除权日数；②其中触发 `stop_loss:gap_open` / `defer_sell_limit_down` / band trail 的笔数；③对应 `trades.csv` 行（工件：`backtest_output/csv_daily_v8_20251023_20260909/`）。

**缺口（不阻塞 NP2，后续片处理）**：

| # | 缺口 | 影响 | 归属 |
|---|------|------|------|
| G1 | 湖上仅单份"最新版 front"，无按日落盘版本 | 若裁决走 D2①/② 须先定 as-of 口径或重建当日快照 | 复权实施片 |
| G2 | 24 码 none 有 front 无（因子 NaN） | NP2 计数按「无因子=不修正」跳过并记数 | NP2 计数规则 |
| G3 | adj_factor 早期 cum≤0 脏段（全史 min -15.09；窗内 0 行） | NP2 限窗即可；全史用途前须清洗 | 1.3 生产侧 |
| G4 | ex index 5,445 码 vs adj 5,591 码（差 146） | NP2 时核对差集是否全为新股/退市 | NP2 计数时 |

**给 NP2 的幅度先验**（可直接用于「影响可忽略 vs 显著」的预判标尺）：>5% 送转段 493 起（占可检 16.5%）是假止损主嫌疑；0.5–1% 段 910 起主要威胁涨跌停模板边缘；≤0.5% 段 1,372 起大概率可归 E-R5「已知边界」。

---

## 附：复现要点（本 survey 全部数字的生成方式）

`pandas.read_parquet('F:/stock_data/adj_factor.parquet')` → 窗过滤（date 列为 date 对象，先 `astype(str)`）→ `groupby('stock_code').shift(1)` 得 prev_f → `chg=f/prev_f-1` → 阈值扫描与 `set(zip(stock_code, ymd))` 交集对 `ex_date_index.parquet` 窗内事件；分区对齐用 `pyarrow.ParquetFile.read_row_group(last, columns=['time'])`（注意分区列名为 `time` 非 `date`）。
