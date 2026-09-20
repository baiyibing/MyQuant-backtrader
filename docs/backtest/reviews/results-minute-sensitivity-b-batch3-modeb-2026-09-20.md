# 分钟敏感对照 B · 第三批结果（Mode B clock · 2026-09-20）

**状态：`PENDING_4090_RUN`。** 本文件为 harness / 文档落地后的占位；数值与 `lake_read_status` 须等 4090 跑批产物写入 `batch3_modeb/` 后再填。BASE `f2fe15124ffbc62d3c0526fc90fed78d014b1bb1`。生产 fill/scan/fee/defaults/CLI **未改**（`production_C=frozen`）。

依据：[计划 §7](plan-minute-sensitivity-b-2026-09-20.md)；[第二批](results-minute-sensitivity-b-batch2-2026-09-20.md)；[复跑 README](../../../backtest/research/exports/minute_sensitivity_b_20260920/README.md)。

## 0. 域锁定

| 项 | 取值 |
|---|---|
| 引擎 | Mode B only（`unified_exit_modeb.evaluate_exit_modeb`） |
| 入场 | none 日收；**聚合自同一 1min none 帧**（末分钟 close）；禁止 `my_data` day.bin |
| 规格 | `StrategySpec(rule=2, n=10, x=5, y=5)` |
| Q39 | open-gap then close；high/low 永不触发；同分钟 trigger≈fill（close 路径） |
| Q38 oracle | 事后上界；标签 `EX_POST_UPPER_BOUND_NOT_EXECUTABLE`；**不入**可执行汇总 |
| 符号 | `000021.SZ,002025.SZ,600000.SH,600007.SH,600276.SH`（与 batch2 manifest 一致） |
| 窗口 | `20260916`–`20260918` |
| bar 标签 | **START** 墙钟（同 batch2） |
| 入场日规则 | 窗口内每个有后续 session 的覆盖交易日各建一 `Instance`（T+1+ 退出路径） |
| next_open | 同日历日连续竞价 `bar.start >= submit`；`submit=decision_at+1ms`；当日结束过期（batch2 精神） |
| decision_at | open_gap＝成交 bar START；close＝START+1m |

## 1. 产物（跑批后）

目录：[batch3_modeb/](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch3_modeb/)（须新建；已存在则拒绝覆盖）

| 文件 | 用途 |
|---|---|
| `modeb_clock_trades.csv` | 基线 Q39 + next_tradable_open 局部对照 |
| `modeb_clock_summary.csv` | Mode B 可执行 clock 汇总（无 Book/v7 混入） |
| `modeb_oracle.csv` | Q38 事后上界行或 DATA_GAP 桩 |
| `modeb_data_gaps.csv` | 证据缺口 |
| `manifest.json` | `batch=3` / `mode=modeb` / `daily_entry_source=aggregated_from_1min_none_lineage` / `production_C=frozen` |

全策略 NAV/DD/rank：**DATA_GAP**（数值空白）。**禁止**把 Mode B 总 NAV 与 Book/v7 比引擎优劣。

## 2. 4090 PowerShell RUNBOOK

```powershell
$env:OSKH_SOURCE_PARQUET_ROOT='E:\stock_data'
$env:QLIB_1MIN_ROOT='C:\Users\wangc\.qlib\qlib_data\my_data_1min'
cd D:\PycharmProjects\MyQuant-backtrader
git fetch github
git checkout research/minute-sensitivity-b-batch2-lake
git pull github research/minute-sensitivity-b-batch2-lake
D:\anaconda3\envs\vanna312\python.exe scripts\research\run_minute_sensitivity_b.py `
  --batch 3 `
  --mode modeb `
  --symbols 000021.SZ,002025.SZ,600000.SH,600007.SH,600276.SH `
  --start 20260916 --end 20260918 `
  --output-dir backtest\research\exports\minute_sensitivity_b_20260920\batch3_modeb
```

别名：`--batch 3` ↔ `--mode modeb`（二者冲突则报错）。输出目录必须不存在。

验证（可选，数据无关）：

```powershell
D:\anaconda3\envs\vanna312\python.exe -m pytest -q backtest\research\exports\minute_sensitivity_b_20260920\verify_harness.py
```

## 3. 跑批后待填

| 项 | 状态 |
|---|---|
| `lake_read_status` / `access` | PENDING_4090_RUN |
| 实例数 / 基线成交 / next 成交 / 共同成交 | PENDING_4090_RUN |
| `trigger_path` 分布（open_gap / close / other / none） | PENDING_4090_RUN |
| 共同成交 `mean_local_return_delta_bp` | PENDING_4090_RUN |
| oracle 行数（均标非可执行） | PENDING_4090_RUN |
| git HEAD / manifest hashes | PENDING_4090_RUN |
