# MyQuant-backtrader

研究脸：日名单 CSV + **向量化**回测，以及筹码 / 换手阻力（Python + Rust）。行情只读 path-SSOT parquet；下载在原仓。成交验收（LEBS / MockQMT）在 [OSkhQuant1.3](https://github.com/baiyibing/OSkhQuant1.3)。

三件引擎怎么分工：[`docs/backtest/engine-positioning-ssot.md`](docs/backtest/engine-positioning-ssot.md)。成交核（档位 / 全卖因跌停 / Decimal 涨跌停价）：[`docs/backtest/engine-ashare-correctness.md`](docs/backtest/engine-ashare-correctness.md)。名单 CSV 契约：[`docs/backtest/pool-csv-contract.md`](docs/backtest/pool-csv-contract.md)。Qlib 回测停用；Cerebro 观察退役。本仓没有 `backtest/lebs/`。

Seeded from OSkhQuant slim snapshot at `5d41252`。S2（2026-09-09）之后本仓收研究面；交易栈只留 `oskh_factors` chip/bridge 微包。

## Layout

| Path | Role |
|------|------|
| `backtest/research/csv_daily_backtest.py` | 向量化日线（策略 1/2/3/4/5/6/8 策略书） |
| `backtest/research/csv_minute_backtest.py` | 向量化分钟（策略 1/2/3/4/5/6/8） |
| `backtest/research/csv_minute_backtest_v7.py` | 策略 7 金榕元仓位机（独立） |
| `backtest/research/csv_ledger.py` | 6/8 共用账本（Position / 买卖 / 追买桶） |
| `backtest/research/market_layer.py` | 涨跌停档位与 Decimal 涨跌停价 |
| `backtest/research/csv_pool.py` | 名单 CSV：裸六位码 → canonical |
| `backtest/research/csv_strategy_books.py` | 1/2/3/4/5/6/8 策略书 |
| `backtest/research/chip/` | Chip 因子消费者 |
| `backtest/` 根上 Cerebro | 观察退役（`backtest_main_full`、Rolling、chip indicator） |
| `backtest/legacy/` | 非 Cerebro 旧回放 |
| `oskh_data/` | Parquet/DuckDB 只读（三树 hive） |
| `l2_analytics/` | L2 离线聚合 / ETL |
| `qlib_cost/` | 筹码分布算法 |
| `turnover-resist/` | 换手阻力 Rust SSOT |
| `oskh_factors/bridge/turnover_resist.py` | Rust 的 Python 桥 |
| `strategies/tr_filter.py` | 换手阻力选股过滤 |
| `oskh_core/` | TR 再导出 + `a_share_symbol_normalize` |
| `trade_decision/presets.py` | 卖点 presets（研究副本，不改 1.3 交易核） |
| `common/infra/` | 薄基建（timekeeping、path-SSOT） |
| `scripts/gates/` | 契约 / path-SSOT gates |
| `scripts/research/` `scripts/data/` `scripts/tr/` | chip / TR / L2 研究 CLI |
| `stock_pool/` | 6/8 默认日名单（不是海龟池） |

## Environment

```text
D:\anaconda3\envs\vanna312\python.exe -m pip install -r requirements.txt
```

## Run research backtest

必须 `--strategy version1|version2|version3|version4|version5|version6|version8`。7 不在 choices，必须走独立入口并传 `--pool-dir`。数据经 `oskh_data` / `resolve_period_root`（有 `F:\stock_data\.authority` 时跟 F 盘）。

```powershell
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py --strategy version6 --start 20251023 --end 20260909
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest.py --strategy version8 --start 20251023 --end 20260909
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest_v7.py --start 20260804 --end 20260909 --pool-dir E:\PycharmProjects\OSkhQuant1.3\stock_pool_turtle
```

R5（仅做 pred TopN 管道检查）：

```powershell
# MyQuant 仓导出（不要使用 holdings 口径的 exports/r0_*）
D:\anaconda3\envs\vanna312\python.exe my_scripts/export_daily_pool.py --pred my_scripts\预测结果.csv --topk 10 --asof pred_minus_one --out-dir exports/r2_pred_topn_20260302_20260323
# 本仓；<first>/<last> 是导出目录内首末 CSV 的文件名 stem
D:\anaconda3\envs\vanna312\python.exe -c "from pathlib import Path; from backtest.research.csv_pool import validate_pool_dir; err=validate_pool_dir(Path(r'<r2 out>')); assert err == [], err"
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py --strategy version6 --pool-dir <r2 out> --start <first> --end <last>
```

`--start/--end` 跟导出文件名走：H0 / `pred_minus_one` 常没有 `20260302.csv`，最后一个 pred 日也不写文件。无名称的 ST 按代码前缀使用 10% / 20% / 30% 档，不按 5%；本例只检查管道，不能把 NAV 或涨跌停桶当作模型结论。详见 [R2/R5 计划](docs/backtest/plan-pool-pipeline-r2r5-2026-09-12.md)与[名单 CSV 契约](docs/backtest/pool-csv-contract.md)。

细则与 1.3 入口：[`docs/backtest/README.md`](docs/backtest/README.md)。

Cerebro 全市场滚动（`backtest/backtest_main_full.py --allow-cerebro-fossil`）只做旧对照，不接新策略；无该显式旗标会立即退出。

## Market data (read-only)

Bars、复权、流通股本由原仓生产，这里用 `oskh_data.StockDataReader` 读。无 QMT / xtquant 下载。

Config: `config/reader.yaml`（默认 `mode: parquet`）。盘符分层见 `AGENTS.md`。

## Rust turnover-resist

Must build **inside** the crate directory (sccache):

```powershell
cd turnover-resist
cargo build --profile release-fast
```

Python: `from oskh_factors.bridge.turnover_resist import compute_turnover_resist`（也从 `oskh_core.turnover_resist_bridge` 再导出）。

## Tests

```powershell
D:\anaconda3\envs\vanna312\python.exe -m pytest -q
```

## Git

- Public: https://github.com/baiyibing/MyQuant-backtrader
- `master` tracks a private internal remote named `origin`. Do not publish that URL. Use `git push github` for the public mirror.
