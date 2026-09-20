# 分钟敏感对照 B · 第四批结果桩（全策略 NAV / DD / 引擎内排名 · 2026-09-20）

**状态：`STUB_AWAITING_4090`。** 本文件为结果容器；数值格在 4090 `--execute` 前保持 **DATA_GAP / 空白**。局部事件 bp（batch2/3）**禁止**粘贴进下表。

依据：[设计](design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md)；[计划](plan-minute-sensitivity-b-2026-09-20.md)；导出 [batch4_fullstrat/](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat/)。BASE tip ≈ `ac1fa97`。`production_C=frozen`。

---

## 0. 域锁定

| 项 | 取值 |
|---|---|
| 窗 | **提案** `20260825`–`20260909`（12 个 pool 交易日；相对 batch2 3 日扩展） |
| 符号 | 窗内 `stock_pool` 并集（≈69 码） |
| 访问 | 优先 `qlib_bin_1min` → `C:\Users\wangc\.qlib\qlib_data\my_data_1min` |
| bar 标签 | START 墙钟 |
| 费用 | `DEFAULT_SCHEDULE=BILATERAL_10BP`；Mode B 双边 10bp 线性 |
| Mode B 入场 | `aggregated_from_1min_none_lineage`（禁止 day.bin 后复权） |
| 报告 | Book / v7 / Mode B **分列**；禁止跨引擎优劣 |

---

## 1. 单轴矩阵（填数前）

| cell_id | clock | slip | Book | v7 | Mode B |
|---|---|---|---|---|---|
| `baseline_default_clock_fee` | 生产默认 | 0 | **待 4090 填** | **待 4090 填** | **待 4090 填** |
| `clock_next_open_fullstrat` | next-open | 0 | DATA_GAP | DATA_GAP | DATA_GAP |
| `slip_5bp_fullstrat` | 默认 | 5bp/边 | DATA_GAP | DATA_GAP | DATA_GAP |
| `slip_10bp_fullstrat` | 默认 | 10bp/边 | DATA_GAP | DATA_GAP | DATA_GAP |
| `slip_20bp_fullstrat` | 默认 | 20bp/边 | DATA_GAP | DATA_GAP | DATA_GAP |

证据：`batch4_fullstrat/matrix.csv`。

---

## 2. Book（默认时钟 · 分策略）

来源：`book_nav.csv`。排名仅在 Book 书内。

| strategy | final_equity | total_return | max_drawdown | within_engine_rank | status |
|---|---:|---:|---:|---:|---|
| version1 | — | — | — | — | DATA_GAP |
| version2 | — | — | — | — | DATA_GAP |
| version3 | — | — | — | — | DATA_GAP |
| version4 | — | — | — | — | DATA_GAP |
| version5 | — | — | — | — | DATA_GAP |
| version6 | — | — | — | — | DATA_GAP |
| version8 | — | — | — | — | DATA_GAP |
| version9 | — | — | — | — | DATA_GAP |
| version10 | — | — | — | — | DATA_GAP |

---

## 3. v7（默认时钟 · 单策略）

来源：`v7_nav.csv`。

| strategy | final_equity | total_return | max_drawdown | within_engine_rank | status |
|---|---:|---:|---:|---:|---|
| strategy7 | — | — | — | 1（自指） | DATA_GAP |

---

## 4. Mode B（默认时钟 · 网格内）

来源：`modeb_nav.csv`（及 runner `ranking.csv`）。入场必须为 1min none 聚合。

| strategy (grid label) | final_equity | total_return | max_drawdown | within_engine_rank | status |
|---|---:|---:|---:|---:|---|
| （4090 顶名） | — | — | — | — | DATA_GAP |

Oracle 若出现：标 `EX_POST_UPPER_BOUND_NOT_EXECUTABLE`，**不入**上表。

---

## 5. 证据缺口

见 `batch4_fullstrat/data_gaps.csv`。要点：

- 全策略 clock 交换 / slip 轴：无 research-only hook → DATA_GAP
- 跨引擎 NAV 比较：FORBIDDEN
- 名单发布时间 / 因子链：仍 DATA_GAP
- 缺 qlib bar：不发明价格 → 对应格 DATA_GAP

---

## 6. 4090 下一步

```powershell
$env:OSKH_SOURCE_PARQUET_ROOT='E:\stock_data'
$env:QLIB_1MIN_ROOT='C:\Users\wangc\.qlib\qlib_data\my_data_1min'
cd D:\PycharmProjects\MyQuant-backtrader
git fetch origin
git checkout research/minute-sensitivity-b-batch4-fullstrat-2026-09-20
D:\anaconda3\envs\vanna312\python.exe scripts\research\run_minute_sensitivity_b_batch4_fullstrat.py `
  --execute --force `
  --start 20260825 --end 20260909 `
  --qlib-1min-root C:\Users\wangc\.qlib\qlib_data\my_data_1min `
  --pool-dir stock_pool `
  --output-dir backtest\research\exports\minute_sensitivity_b_20260920\batch4_fullstrat
```

填数后：把本文件表格中的 `—` / DATA_GAP 换成 CSV 实值，更新 `manifest.json` 的 `status`，另开 docs PR 或同 PR 续推。**勿覆盖**已核实的 batch1/2/3 目录。

---

## 7. 边界

本批回答「扩展窗上，**默认时钟 + 钉死费用**的全策略 NAV/DD/引擎内排名能否诚实交付」；**不**回答全策略 clock/slip 敏感性，也**不**授权 production_C。
