# NP2 宿主跑数 runbook（ex-div hold hits）

> **日期**：2026-09-16（Asia/Shanghai）。  
> **关联**：[plan-exdiv-hold-hits-np2-2026-09-16.md](plan-exdiv-hold-hits-np2-2026-09-16.md)；survey [survey-exdiv-adj-data-prep-2026-09-16.md](survey-exdiv-adj-data-prep-2026-09-16.md) §3 三锁。  
> **环境**：VM **无** F 湖 / D 烟测 `trades.csv` → 本页仅宿主 CLI；**结果节 awaiting host run**（禁止编造命中数字）。

---

## 设计锁（跑前核对）

1. **主源** `F:\stock_data\ex_date_index.parquet`；`--adj-factor` 仅 parity 副证（ε=5e-3）。  
2. 窗 **20251023–20260909**；命中 = `entry < ex_date ≤ exit`（T+1，买入日不计）。  
3. 看 ①命中计数 ② `stop_loss:gap_open` / `defer_sell_limit_down` / `trail:band:*` 分桶 ③ 样例行。  
4. **裁决人裁**：数字出来后再写 E-R5 或新复权 plan；脚本不自动落锁。  
5. 幅度先验（survey）：>5% 送转主嫌疑假止损；≤0.5% 大概率可归 E-R5——写稿用，非自动阈值。

---

## Windows 命令（宿主）

仓库典型路径：`E:\PycharmProjects\MyQuant-backtrader`。先 `git fetch && git checkout feat/exdiv-hold-hits-np2`（或合入后的 master）。

```bat
cd /d E:\PycharmProjects\MyQuant-backtrader

D:\anaconda3\envs\vanna312\python.exe scripts\research\report_exdiv_hold_hits.py ^
  --trades backtest_output\csv_daily_v8_20251023_20260909\trades.csv ^
  --ex-date-index F:\stock_data\ex_date_index.parquet ^
  --adj-factor F:\stock_data\adj_factor.parquet ^
  --start 20251023 --end 20260909 ^
  --format markdown --sample-limit 30 > docs\backtest\exdiv-hold-hits-np2-host-results-2026-09-16.md
```

分钟链对照（可选，战略默认先日线）：

```bat
D:\anaconda3\envs\vanna312\python.exe scripts\research\report_exdiv_hold_hits.py ^
  --trades backtest_output\csv_minute_v8_20251023_20260909\trades.csv ^
  --ex-date-index F:\stock_data\ex_date_index.parquet ^
  --start 20251023 --end 20260909 --format text
```

`trades.csv` 列需含：`date,code,side,reason,lot`（与 csv 引擎落盘一致）。若 D 烟测目录名不同，以宿主实际 `backtest_output/csv_*_v8_20251023_20260909/` 为准（见 [money-modes-v8-pername-smoke-2026-09-16.md](money-modes-v8-pername-smoke-2026-09-16.md)）。

---

## 结果（切片 B）

**Status: awaiting host run.**

| 项 | 值 |
|----|-----|
| hold_exdiv_hit_events | _TBD_ |
| hold_exdiv_hit_lots | _TBD_ |
| among_hits_sell_gap_open | _TBD_ |
| among_hits_sell_defer_limit_down | _TBD_（trades reason 可能恒 0；对照 summary 计数器另注） |
| among_hits_sell_band_trail | _TBD_ |
| samples | _TBD_ |
| parity (optional) | _TBD_ |
| suggested wording (E-R5 vs 显著) | _HUMAN after numbers — do not fill until host run_ |

G2 / G4 由 CLI `--adj-factor` 路径写入 `parity.skip_parity_no_factor` / `g4_*`；宿主结果短记中抄出即可。

---

## 明确不要

- 不要改 `dividend_type` / cost / peak / golden。  
- 不要在无数字时写 E-R5。  
- 不要把本探针并进 NP1 `--ration` 或费率片。
