# 换手阻力布林带（TR-Bollinger，Canonical TR_1000）

> 实现方案：[`rfc-turnover-resistance-bands.md`](rfc-turnover-resistance-bands.md)（v9 已批准）

## 概述

在 **1000 日 Canonical 换手阻力**时序上计算 20 日布林带（Python `pandas rolling`，ddof=1），持久化到：

`stock_data/turnover_resistance_daily.parquet`

环境变量 `TURNOVER_RESIST_BANDS_PATH` 可覆盖路径。

## Canonical vs Legacy

| 来源 | 窗口 | 用途 |
|------|------|------|
| `turnover_resistance_daily.parquet` | **1000** | 生产持久化 + TR BB + 盘后信号 |
| `chip_factor_analysis.py` / `daily_chip_logger.py` | **80** | Legacy 回测（`resist_bb` 规则） |

**纪律**：引用换手阻力须标注 `TR_1000` / `TR_80`。`|阻力|>20` 阈值仅适用于 Legacy TR_80，**禁止**直接套用于 TR_1000。

## 数据流

1. Rust PyO3 `compute_turnover_resist(date, window=1000)` → 全市场截面
2. `TurnoverResistanceStore.upsert_daily()` → Parquet
3. `compute_tr_bb_columns()` + `store.compute_and_update_bands()` → 写 `tr_bb_*` / `tr_bb_free_*`
4. 策略 / 回测 `store.load_series()` / `load_cross_section()`

`bands_computed_at IS NULL` → **跳过 TR BB 信号**（不用 position=0.5 假中性）。

## MVP 信号

- `TR_BREAKOUT`：`turnover_resistance > tr_bb_upper`
- `TR_BREAKDOWN`：`turnover_resistance < tr_bb_lower`

## 运维命令

```bash
# 单日增量（TR 截面 + TR BB）
D:/anaconda3/envs/vanna311/python.exe scripts/data/compute_turnover_resistance_bands.py --date YYYYMMDD

# 仅补算 TR BB（Step 1-2 已完成）
D:/anaconda3/envs/vanna311/python.exe scripts/data/compute_turnover_resistance_bands.py --date YYYYMMDD --backfill-bands-only

# 历史回填（默认 60 日历日 walk-back，再批量 TR BB）
D:/anaconda3/envs/vanna311/python.exe scripts/data/backfill_turnover_resistance_bands.py --end-date YYYYMMDD --days 60 --skip-existing
```

## 源码

| 模块 | 作用 |
|------|------|
| `oskh_data/turnover_resistance_store.py` | Parquet UPSERT + 查询 + 批量 TR BB 写回 |
| `backtest/chip_turnover_resistance_bands.py` | `tr_bollinger_bands()` / `compute_tr_bb_columns()` |
| `scripts/data/compute_turnover_resistance_bands.py` | 盘后单日流水线 |
| `scripts/data/backfill_turnover_resistance_bands.py` | 历史回填 |
