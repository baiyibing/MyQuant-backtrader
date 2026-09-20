# 分钟敏感对照 B · 第二批结果（2026-09-20）

**Human GO B 第二批：真实分钟序列只读局部事件敏感性（非完整策略重放）。** BASE `f2fe15124ffbc62d3c0526fc90fed78d014b1bb1`（Merge #136）。本批 **PENDING_4090_RUN**：VM 无生产分钟源，下列指标表在 4090 跑完前保持占位，**禁止把空白当成零**。

依据：[SSOT §C](eval-minute-pitfall-vs-asbuilt-2026-09-20.md#c-收束与人裁选项)；[计划](plan-minute-sensitivity-b-2026-09-20.md)；[第一批](results-minute-sensitivity-b-batch1-2026-09-20.md)；[复跑 README](../../../backtest/research/exports/minute_sensitivity_b_20260920/README.md)。生产 fill/scan/fee/defaults/CLI **未改**。

## 0. 数据血缘（同一分钟序列，两层访问）

| 字段 | 取值 |
|---|---|
| `source` / lineage | `parquet_lineage`（none 复权 1m 湖为真相源） |
| `access`（优先） | `qlib_bin_1min` → 默认 `C:\Users\wangc\.qlib\qlib_data\my_data_1min`（bin 由 parquet 物化，加速） |
| `access`（回退） | `oskh_parquet_1m` → `OSKH_SOURCE_PARQUET_ROOT=E:\stock_data`，`resolve_period_root('1m')/'dividend_type=none'` |
| 日频 bin | `my_data` / `cn_data` 仅 day.bin — **不用于分钟轴** |
| F: 湖 | **不存在**；禁止声称 |

**不是** lake-vs-qlib 两套宇宙；同一 bars，不同 I/O。

## 1. Bar 标签语义（相对 batch1 的诚实差异）

| 批次 | 标签 | 含义 |
|---|---|---|
| batch1 合成 | `hm` = bar **END** | 人工构造；close 在 end 可得 |
| batch2 真实 | index / `hm` = bar **START** 墙钟 | 4090 核实：hm=585 → 09:45:00；close 在 start+1min 可得 |

batch2：`close_available = bar.start + 1min`，`submit = close_available + 1ms`；候选 open 要求 `bar.start >= submit`。因此 09:45 START bar 的 close 在 09:46 可得后，**09:46 START open 会被 `before_submit` 拒绝**，最早下一 open 为 09:47。**禁止**把 batch1 END 语义套到本批。

## 2. RUNBOOK（4090）

```powershell
$env:OSKH_SOURCE_PARQUET_ROOT='E:\stock_data'
# 可选显式分钟 bin 根（默认已是 my_data_1min）
# $env:QLIB_1MIN_ROOT='C:\Users\wangc\.qlib\qlib_data\my_data_1min'
cd D:\PycharmProjects\MyQuant-backtrader
git fetch github
git checkout research/minute-sensitivity-b-batch2-lake
D:\anaconda3\envs\vanna312\python.exe scripts\research\run_minute_sensitivity_b.py `
  --mode lake `
  --output-dir backtest\research\exports\minute_sensitivity_b_20260920\batch2
```

`--output-dir` 必须是**不存在的新目录**。缺源时仍写出 DATA_GAP CSV/manifest（不探测盘符）。正式 `batch2/` 留给本机首次成功跑。

## 3. 样本与缺口（跑前预期）

| 项 | 预期 |
|---|---|
| 符号 | 默认 `600000.SH`（可扩展短列表） |
| 窗口 | `20260916`..`20260918`（YYYYMMDD） |
| Book chase @09:45 | same-close vs next-open |
| v7 add | 独立阶段；信号 hm∈{884,885,895} |
| fee·slip | 0/5/10/20bp；费用替换情景 |
| volume-cap | 独立轴；无 attested volume → DATA_GAP |
| Mode B clock | `NOT_RUN` |
| 全策略 NAV/DD/rank | **DATA_GAP（数值空白）** |
| 名单/因子发布时间 | 仓内 CSV 头探测；无 publication timestamp → DATA_GAP |

## 4. 指标表（PENDING_4090_RUN）

### 4.1 Clock 汇总

| 独立基线 | 事件数 | 基线成交 | next 成交 | 状态匹配率 | 共同成交同价率 | 状态 |
|---|---:|---:|---:|---:|---:|---|
| Book chase | PENDING_4090_RUN | — | — | — | — | PENDING_4090_RUN |
| v7 add | PENDING_4090_RUN | — | — | — | — | PENDING_4090_RUN |
| Mode B | — | — | — | — | — | NOT_RUN |

### 4.2 成本 / 容量

| 轴 | 状态 |
|---|---|
| slippage 0/5/10/20bp | PENDING_4090_RUN |
| fee replace 情景 | PENDING_4090_RUN |
| volume-cap off/on | PENDING_4090_RUN（量证据不足则 DATA_GAP） |

### 4.3 全策略

| 指标 | 状态 |
|---|---|
| NAV / 最大回撤 / 策略排名 | DATA_GAP |

## 5. Manifest 关键字段

跑后检查 `batch2/manifest.json`：`source=parquet_lineage`、`access=qlib_bin_1min|oskh_parquet_1m`、`bar_label_semantics=lake_index_is_bar_start_wallclock`、`production_replay=DATA_GAP`、`base=f2fe151...`、source-hash fence、`OSKH_SOURCE_PARQUET_ROOT` / `QLIB_1MIN_ROOT` 实值或 `unset`。

