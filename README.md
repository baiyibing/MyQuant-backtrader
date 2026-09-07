# MyQuant-backtrader

Standalone **backtrader** backtest + stock data download/read + chip / turnover-resistance (Python + Rust).

Seeded from OSkhQuant slim snapshot at commit `5d41252` (parent of RF-R0 package re-engineering). Live trading, Redis streams, executor, monitor, and most of `oskh_core` / `oskh_db` were removed.

## Layout

| Path | Role |
|------|------|
| `backtest/` | Cerebro strategies (`backtest_main_full`, rolling invest, chip tools) |
| `oskh_data/` | Parquet/DuckDB reader + QMT download / backfill |
| `qlib_cost/` | Chip distribution algorithms |
| `turnover-resist/` | Rust CLI for turnover resistance |
| `oskh_core/turnover_resist_bridge.py` | Python bridge (FFI / CLI) to the Rust binary |
| `trade_decision/presets.py` | Sell presets used by optional BT adapter |
| `common/infra/` | Slim infra (`timekeeping`, `quant_logger`, …) |
| `stock_pool/` | Daily buy-list CSVs for full BT |

## Environment

```text
D:\anaconda3\envs\vanna311\python.exe -m pip install -r requirements.txt
```

## Run full backtest

Dates / capital are hardcoded in `backtest/backtest_main_full.py`. Needs `../stock_pool` and `../stock_data` (legacy minute parquet via `qmt_utils_adv`).

```powershell
cd backtest
D:\anaconda3\envs\vanna311\python.exe backtest_main_full.py
```

## Download / rebuild market data

```powershell
D:\anaconda3\envs\vanna311\python.exe -m oskh_data.backfill --help
# or shim:
D:\anaconda3\envs\vanna311\python.exe backtest/backfill_daily_data.py download --start YYYYMMDD --end YYYYMMDD
```

Config: `config/reader.yaml` (`mode: parquet` by default). Env: `OSKH_DATA_ROOT`.

## Rust turnover-resist

Must build **inside** the crate directory (sccache):

```powershell
cd turnover-resist
cargo build --profile release-fast
```

Python entry: `from oskh_core.turnover_resist_bridge import compute_turnover_resist`.

## Tests

```powershell
D:\anaconda3\envs\vanna311\python.exe -m pytest -q
```

## Git

- Public: https://github.com/baiyibing/MyQuant-backtrader
- `master` tracks a private internal remote named `origin`. Do not publish that URL. Use `git push github` for the public mirror.
