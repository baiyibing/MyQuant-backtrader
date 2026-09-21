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


## ModeB baseline re-run closed the DATA_GAP (2026-09-21)

4090 ModeB-only re-run at tip `a1e7dea` (EXIT=0, ~2026-09-21 08:14 +08) wrote stamp `batch4_fullstrat_modeb_rerun_20260921` under `backtest/research/exports/minute_sensitivity_b_20260920/`. Baseline cell `baseline_default_clock_fee` / strategy `livermore_l2_stale8_y10`: `final_equity=1099605762.3151746`, `total_return=-0.0003583978952958367` (−0.03584%), `max_drawdown=0.0006438975472074711` (0.06439% as harness emitted; do not flip sign), status OK, matrix ModeB FILLED, `modeb_ok=1`. Within-ModeB rank top3: livermore_l2_stale8_y10, r2_x5_yinf_n8 (tr=-0.0003656), r2_x5_yinf_n10 (tr=-0.0003739). Book/v7 were `engine_skipped` in this run — retain #142 Book/v7 numbers. Fullstrat clock/slip axes and v9/v10 pool remain DATA_GAP. Numbers filled in `results-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md` §4/§8; `production_C=frozen`.
