# MyQuant-backtrader

Standalone **backtrader** backtest + local stock-data read + chip / turnover-resistance (Python + Rust). Market **download** lives in the original repo; this fork only reads path-SSOT parquet.

Seeded from OSkhQuant slim snapshot at commit `5d41252` (parent of RF-R0 package re-engineering). Live trading, Redis streams, executor, monitor, and most of `oskh_core` / `oskh_db` were removed. Since migration S2 (2026-09-09) this repo owns the full research face absorbed from OSkhQuant1.3 (`l2_analytics`, `strategies`, research scripts/gates/tests); the trading stack upstream keeps only the `oskh_factors` chip/bridge micropackage.

## Layout

| Path | Role |
|------|------|
| `backtest/` | Cerebro engine at root (`backtest_main_full`, rolling invest, chip indicator) |
| `backtest/research/` | Chip research CLIs (`chip_backtest`, factor analysis, verify scripts) |
| `backtest/research/chip/` | Chip factor consumers (qlib_cost / factors evaluation CLIs) |
| `backtest/tools/` | One-off local utilities |
| `backtest/legacy/` | Non-Cerebro bar-replay / mock engines |
| `oskh_data/` | Parquet/DuckDB reader (no QMT download; three-tree hive roots) |
| `l2_analytics/` | L2 offline aggregates / ETL templates (duckdb, SQL) |
| `qlib_cost/` | Chip distribution algorithms |
| `turnover-resist/` | Rust CLI for turnover resistance (Rust SSOT) |
| `oskh_factors/bridge/turnover_resist.py` | Python bridge (FFI / CLI) to the Rust binary |
| `strategies/tr_filter.py` | Turnover-resistance selector filter (decoupled from upstream common) |
| `oskh_core/` | TR bridge re-export + `a_share_symbol_normalize` |
| `trade_decision/presets.py` | Sell presets used by optional BT adapter |
| `common/infra/` | Slim infra (`timekeeping`, `quant_logger`, …) |
| `scripts/gates/` | Contract / path-SSOT gates |
| `scripts/research/` | Full-market chip / TR research CLIs |
| `scripts/data/` | Chip / resist research CLIs (absorbed from upstream) |
| `scripts/run/` | L2 ETL entry points (`run_l2_etl_day`, `run_l2_build_aggregates`, …) |
| `scripts/tr/` | Turnover-resistance backfill and DuckDB rebuild |
| `stock_pool/` | Daily buy-list CSVs for full BT |

## Environment

```text
D:\anaconda3\envs\vanna312\python.exe -m pip install -r requirements.txt
```

## Run full backtest

Dates / capital are hardcoded in `backtest/backtest_main_full.py`. Needs `../stock_pool`. Minute/daily bars load via `oskh_data.StockDataReader` (path-SSOT; F parquet when `.authority` is present).

```powershell
cd backtest
D:\anaconda3\envs\vanna312\python.exe backtest_main_full.py
```

## Market data (read-only)

Bars, adj factors, and float-share sidecars are produced by the original repo and consumed here via `oskh_data.StockDataReader` (path-SSOT; F parquet when `.authority` is present). This fork does not ship QMT / xtquant download.

Config: `config/reader.yaml` (`mode: parquet` by default). Env: `OSKH_DATA_ROOT`.

## Rust turnover-resist

Must build **inside** the crate directory (sccache):

```powershell
cd turnover-resist
cargo build --profile release-fast
```

Python entry: `from oskh_factors.bridge.turnover_resist import compute_turnover_resist` (also re-exported from `oskh_core.turnover_resist_bridge`).

## Tests

```powershell
D:\anaconda3\envs\vanna312\python.exe -m pytest -q
```

## Git

- Public: https://github.com/baiyibing/MyQuant-backtrader
- `master` tracks a private internal remote named `origin`. Do not publish that URL. Use `git push github` for the public mirror.
