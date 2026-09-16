# 向量化成交核（A 股正确性 · as-built）

- 日期：2026-09-12（E-R5 人裁回写 2026-09-16）
- 状态：已落地。卖点/书契约仍以 [plan-unify-csv-strategies-1-8-2026-09-12.md](_archive/plans/plan-unify-csv-strategies-1-8-2026-09-12.md) 的 U-R\* 为准；下表 **E-R\*** 重开了其中撮合锁（含 E-R5 除权已知边界）。
- 定位：[engine-positioning-ssot.md](engine-positioning-ssot.md)。名单：[pool-csv-contract.md](pool-csv-contract.md)。

## 1. 模块

```
market_layer.py     叶子：时间 / limit_pct / limit_prices(Decimal HALF_UP) / round_fen
csv_pool.py         名单 + 名称列（ST）
csv_ledger.py       Position / SimState / execute_buy / _sell / 追买桶
csv_daily_backtest  simulate + 日线加载 + CLI
csv_minute_backtest scan_held_day + 分钟加载 + CLI
csv_minute_backtest_v7  独立仓位机；涨跌停走同一 Decimal limit_prices
```

7 不进 BOOKS，不 import 6/8 `SimState`。

## 2. 现锁（E-R\*）

| ID | 现行为 | 作废的旧锁 |
|----|--------|------------|
| **E-R1** | 日线+分钟：**任何卖因**成交前 `hit_limit_down` → defer、不成交（含 6/8 trail、`stop_loss:touch`、`profit_take`、`force_sell`、`ma_signal`、`open_board`）。reason 前缀不改。 | U-R1「分钟仅 `stop_loss*` defer」 |
| **E-R2** | `limit_pct`：`300/301/302/688/689=20%`；`430/83/87/88/920=30%`；`600/601/603/605/000/001/002/003=10%`；名称列 `ST`/`*ST`=5%；其余 **`None` → `skip_unknown_board`，不默认 10%**。 | U-R12「原样搬家 / 不建模北交 ST 689」 |
| **E-R3** | 市场层只留 Decimal `limit_prices`。v7 改 import。`1.65×10%` 跌停 = **1.49**。禁止 `round()` 银行家舍入。 | U-R10/U-R30「v7 留本地 float」 |
| **E-R4** | 停牌仍冻仓。加载侧丢弃零量占位 K（日线 `volume==0`；分钟整日 `sum(volume)==0`），**等价于当日无 K**，复用同一条冻仓 / pending / `last_close_mark` 路径，不建第二套停牌状态机。净值用最近有 K 的 close，不用 `pos.cost`。追买日无 K **保留 pending** 到下一有 K 日（有 K 后仍只评一次）。 | U-R27「追买 pop 作废 / 净值标成本」 |
| **E-R5** | csv 日线/分钟链全程 `dividend_type=none`；cost / peak / 涨跌停参考价**不对除权调整**（不复权链的已知边界）。宿主证据 20251023–20260909、v8 per_name：持仓期除权命中 daily **8.1%** / minute **2.0%**；可信假触发 ≤**6** lots / 1,136 ≈ **≤0.5%**；`gap_open` 仅 **2**（分钟）、`defer_limit_down` **0**。证据：[np2-exdiv-hold-hits-host-note-2026-09-16.md](np2-exdiv-hold-hits-host-note-2026-09-16.md) + [survey-exdiv-adj-data-prep-2026-09-16.md](survey-exdiv-adj-data-prep-2026-09-16.md)。**暂不开复权实施片**。 | 无（新人裁锁；非 U-R 重开） |

不重开：费率 0.1% 双边、7 不进书、不改 `presets.py`。Cerebro / Rolling **已退场**（见 [engine-positioning-ssot.md](engine-positioning-ssot.md)），禁止复活——旧稿「不删 Cerebro」作废。

**E-R5 重开条件**（触发即重跑 NP2 探针再裁；满足任一条）：①止损档收紧至 <10% 或 trail 地板整体上调；②名单池切到高分红/高送转风格；③分钟链成为主研究面（`gap_open` 集中地）；④任何 NAV 对比结论差距落在 <1% 量级时。见 host-note §3。

## 3. 对照货币

6/8 历史净值会因 E-R1 变少卖。对照看 **reason / 可卖 / 涨跌停**，不是旧 `daily_equity.csv`。改前合成窗快照：`tests/fixtures/csv_engine_pre_er1/`。
