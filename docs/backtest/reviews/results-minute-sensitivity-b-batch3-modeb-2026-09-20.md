# 分钟敏感对照 B · 第三批结果（Mode B clock · 2026-09-20）

**Human GO B 第三批已完成：Mode B 局部退出时钟（Q39 基线 vs `next_tradable_open`）只读敏感性，非完整策略重放。** BASE `f2fe15124ffbc62d3c0526fc90fed78d014b1bb1`。跑批 git HEAD `0d348720e52bdfcd76e298a2d0c161246fff5406`（Mode B clock harness）。`lake_read_status=READ_OK`，`access=qlib_bin_1min`，`daily_entry_source=aggregated_from_1min_none_lineage`，`production_C=frozen`。全策略净收益、最大回撤、策略排名均为 **DATA_GAP**，数值空白。下述数值仅属于独立 Mode B 实例的局部退出时钟对照；**禁止**把 Mode B 总 NAV 与 Book/v7 比引擎优劣；oracle 标 `EX_POST_UPPER_BOUND_NOT_EXECUTABLE`，**不得**并入可执行汇总。

依据：[计划 §7](plan-minute-sensitivity-b-2026-09-20.md)；[第二批](results-minute-sensitivity-b-batch2-2026-09-20.md)（Mode B 当时为 `NOT_RUN`，历史口径保留）；[复跑 README](../../../backtest/research/exports/minute_sensitivity_b_20260920/README.md)；[manifest](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch3_modeb/manifest.json)。本轮仅研究脚本/文档与独立 CSV/JSON；生产 fill/scan/fee/defaults/CLI **未改**。

## 0. 域锁定

| 项 | 取值 |
|---|---|
| 引擎 | Mode B only（`unified_exit_modeb.evaluate_exit_modeb`） |
| 入场 | none 日收；**聚合自同一 1min none 帧**（末分钟 close）；禁止 `my_data` day.bin |
| 规格 | `StrategySpec(rule=2, n=10, x=5, y=5)` → `modeb_spec=r2_x5_y5_n10` |
| Q39 | open-gap then close；high/low 永不触发；同分钟 trigger≈fill（close 路径） |
| Q38 oracle | 事后上界；标签 `EX_POST_UPPER_BOUND_NOT_EXECUTABLE`；**不入**可执行汇总 |
| 符号 | `000021.SZ,002025.SZ,600000.SH,600007.SH,600276.SH`（与 batch2 manifest 一致） |
| 窗口 | `20260916`–`20260918` |
| bar 标签 | **START** 墙钟（同 batch2：`lake_index_is_bar_start_wallclock`） |
| 入场日规则 | 窗口内每个有后续 session 的覆盖交易日各建一 `Instance`（T+1+ 退出路径） |
| next_open | 同日历日连续竞价 `bar.start >= submit`；`submit=decision_at+1ms`；当日结束过期（batch2 精神） |
| decision_at | open_gap＝成交 bar START；close＝START+1m |
| 费用 | Mode A `COMMISSION` 双边 10bp；Mode B 生产线性费率（研究叠层不改生产） |
| `access` | `qlib_bin_1min` → `C:\Users\wangc\.qlib\qlib_data\my_data_1min` |
| 血缘 | `source=parquet_lineage`（qlib bin 为物化，非对立宇宙） |

## 1. 产物

目录：[batch3_modeb/](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch3_modeb/)（4090 已写入；勿覆盖）

| 文件 | 用途 |
|---|---|
| `modeb_clock_trades.csv` | 基线 Q39 + next_tradable_open 局部对照（10 行） |
| `modeb_clock_summary.csv` | Mode B 可执行 clock 汇总（无 Book/v7 混入） |
| `modeb_oracle.csv` | Q38 事后上界（10 行，均标非可执行） |
| `modeb_data_gaps.csv` | 证据缺口（6 类） |
| `manifest.json` | `batch=3` / `mode=modeb` / `daily_entry_source=aggregated_from_1min_none_lineage` / `production_C=frozen` / `git_head=0d34872…` |

全策略 NAV/DD/rank：**DATA_GAP**（数值空白）。**禁止**把 Mode B 总 NAV 与 Book/v7 比引擎优劣。

## 2. Clock 汇总（来自 `modeb_clock_summary.csv`）

独立 Mode B 实例：入场价聚合自同一 none 1min 帧；基线走 Q39；next 轴为 `next_tradable_open`。费用双边 10bp；数量冻结自基线。`clock_status=LOCAL_EVENTS_COMPLETE`。**不是** 1–10 策略书全量回测，也不是生产 Mode B 闭环重放（`production_replay=DATA_GAP`）。

| 项 | 核实 |
|---|---:|
| 请求 / 评估实例 | 10 / 10 |
| 基线成交 | 2 |
| next 成交 | 2 |
| 共同成交 | 2 |
| `status_match_rate` | 1.0 |
| `matched_fill_rate` | 1.0 |
| `same_price_rate`（仅共同成交） | 0.0 |
| `mean_local_return_delta_bp`（共同成交等权） | ≈−8.59 |
| `trigger_path` open_gap / close / other / none | 0 / 2 / 0 / 8 |
| oracle | 独立 CSV；`EX_POST_UPPER_BOUND_NOT_EXECUTABLE` |
| 全策略 NAV / return / max DD / rank | DATA_GAP（空白） |

状态匹配含“两边都不成交”；同价率仅在共同成交集合。`local_return_delta_bp` 为 next 相对基线的局部收益差（bp），**禁止**当成组合收益。

### 两笔 close 路径共同成交（来自 `modeb_clock_trades.csv`）

| case_id | 基线 reason | trigger_path | 基线 fill | next fill | `local_return_delta_bp` | 说明 |
|---|---|---|---|---|---:|---|
| `000021.SZ_20260917` | take_profit | close | 37.29 @ hm688 / 20260918 | 37.35 @ 13:01 START | ≈+16.86 | decision_at=11:29:00；submit+1ms；午休后首根连续竞价 open |
| `002025.SZ_20260916` | take_profit | close | 74.35 @ hm574 / 20260917 | 74.11 @ 09:36 START | ≈−34.04 | decision_at=09:35:00；下一分钟 open |

其余 8 例基线 `mark_end` / `trigger_path=none`，`next_status=NO_FILL`（`no_baseline_trade`），`status_match=True`（两边均无成交）。

### 局部净收益差与全策略

| 对象 | 共同成交局部收益差均值 | 全策略净收益 | 最大回撤 | 策略排名 |
|---|---|---|---|---|
| Mode B clock | ≈−8.59bp（n=2） | DATA_GAP | DATA_GAP | DATA_GAP |

## 3. Oracle（`modeb_oracle.csv` · 不可执行）

10 行均 `label=EX_POST_UPPER_BOUND_NOT_EXECUTABLE`，`executable=NEVER`，`reason=oracle`。事后上界仅供对照上沿；**禁止**折入 `modeb_clock_summary` 的可执行均值或声称可执行收益。全策略列仍为 DATA_GAP 空白。

## 4. 证据缺口（`modeb_data_gaps.csv`）

| item | status | 要点 |
|---|---|---|
| `pool_availability` | DATA_GAP | 仓内 `stock_pool/*.csv` 仅代码/名称两列抽样；无经核验发布时间链 |
| `factor_availability` | DATA_GAP | 无 audited generated_at/available_at |
| `qlib_my_data_day_bin_entry` | DATA_GAP | 入场禁止 day.bin；只用 `aggregated_from_1min_none_lineage` |
| `official_limit_reference_and_corporate_actions` | DATA_GAP | prev refs 来自聚合 1min 日收；无官方日线/ST/除权核验 |
| `closed_cash_path_daily_marks_corporate_actions` | DATA_GAP | 独立实例；无策略 NAV/DD/rank；不与 Book/v7 比 |
| `production_C` | DATA_GAP | frozen；仅研究 harness |

## 5. Manifest 关键字段（已核对）

`batch3_modeb/manifest.json`：`batch=3`、`mode=modeb`、`status=DATA_GAP`（全策略层）、`lake_read_status=READ_OK`、`access=qlib_bin_1min`、`daily_entry_source=aggregated_from_1min_none_lineage`、`production_C=frozen`、`bar_label_semantics=lake_index_is_bar_start_wallclock`、`oracle_label=EX_POST_UPPER_BOUND_NOT_EXECUTABLE`、`base=f2fe15124ffbc62d3c0526fc90fed78d014b1bb1`、`git_head=0d348720e52bdfcd76e298a2d0c161246fff5406`、`checked_sources_match_base=true`（before/after 生产哈希一致）、符号与窗口同上、Python 3.12.13 / pandas 2.3.3 / numpy 2.3.5（4090）。

## 6. 4090 PowerShell RUNBOOK（复跑须新目录）

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
  --output-dir backtest\research\exports\minute_sensitivity_b_20260920\batch3_modeb-rerun
```

别名：`--batch 3` ↔ `--mode modeb`（二者冲突则报错）。**勿覆盖**已提交的 `batch3_modeb/`。

验证（可选，数据无关）：

```powershell
D:\anaconda3\envs\vanna312\python.exe -m pytest -q backtest\research\exports\minute_sensitivity_b_20260920\verify_harness.py
```

## 7. 边界与后续

本批回答的是「真实 START 标签分钟序列上，Mode B Q39 基线 vs `next_tradable_open` 的局部退出价差」；**未**回答全策略 NAV/DD/rank，也未改变生产成交时钟。batch2 文档里 Mode B 的 `NOT_RUN` 仍是该批发运时的历史事实；clock 结果以本文件与 `batch3_modeb/` 为准。生产 fill/scan/fee/defaults/CLI 任何改变仍属 C，需另开计划和人裁。
