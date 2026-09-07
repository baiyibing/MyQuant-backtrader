# MyQuant-backtrader

Standalone **backtrader** backtest + local stock-data read + chip / turnover-resistance (Python + Rust). Market **download** lives in the original repo; this fork only reads path-SSOT parquet.

Seeded from OSkhQuant slim snapshot at commit `5d41252` (parent of RF-R0 package re-engineering). Live trading, Redis streams, executor, monitor, and most of `oskh_core` / `oskh_db` were removed.

## Layout

| Path | Role |
|------|------|
| `backtest/` | Cerebro engine at root (`backtest_main_full`, rolling invest, chip indicator) |
| `backtest/research/` | Chip research CLIs (`chip_backtest`, factor analysis, verify scripts) |
| `backtest/tools/` | One-off local utilities |
| `backtest/legacy/` | Non-Cerebro bar-replay / mock engines |
| `oskh_data/` | Parquet/DuckDB reader (no QMT download) |
| `qlib_cost/` | Chip distribution algorithms |
| `turnover-resist/` | Rust CLI for turnover resistance |
| `oskh_factors/bridge/turnover_resist.py` | Python bridge (FFI / CLI) to the Rust binary |
| `oskh_core/turnover_resist_bridge.py` | Compatibility re-export of the factors bridge |
| `trade_decision/presets.py` | Sell presets used by optional BT adapter |
| `common/infra/` | Slim infra (`timekeeping`, `quant_logger`, …) |
| `scripts/gates/` | Contract / path-SSOT gates |
| `scripts/research/` | Full-market chip / TR research CLIs |
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
