# Addendum: batch4 ModeB DATA_GAP was import path (2026-09-21)

ModeB baseline in batch4 reported `DATA_GAP` with
`import_failed: cannot import name 'load_pool_day_map' from 'backtest.research.csv_common'`.
Root cause: `load_pool_day_map` lives in `backtest.research.csv_pool` (as
`csv_minute_backtest_v7` already imports); the batch4 harness
`run_modeb_library` wrongly imported it from `csv_common`, which does not
re-export it. Research-only one-line fix in
`scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py`; production
fill/scan/fee/defaults untouched. **No fabricated ModeB NAV** — parent re-runs
ModeB-only baseline on 4090 after merge (`--execute --engines modeb`, new
output stamp so existing `batch4_fullstrat/` is not overwritten).
