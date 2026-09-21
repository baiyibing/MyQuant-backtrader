# batch4_fullstrat_v9_s9bvot_20260921

Book **version9** baseline fill for minute-sensitivity-B batch4 (4090 `--execute`).

| item | value |
|---|---|
| tip | `51e019580d8e0b18abeb8e3ac18e21c3feed1585` (post #144 ModeB docs) |
| engine / strategy | Book / version9 |
| cell | `baseline_default_clock_fee` |
| clock / slip / fee | `production_default` / 0 / `DEFAULT_SCHEDULE=BILATERAL_10BP` |
| access | `qlib_bin_1min` |
| window | `20260825`–`20260909` |
| pool | host-local `D:\exports\s9_bvot_20260825_20260909` from `export_strategy9_pool.py` (**never** `stock_pool/`) |
| final_equity | **21053316.65** |
| total_return | **0.0025** (+0.25%) |
| max_drawdown | **−0.0019** (−0.19%) |
| status | OK; within_engine_rank 1 (version9-only run) |

## Pool export (4090)

```
python scripts/data/export_strategy9_pool.py \
  --start 20260825 --end 20260909 \
  --out-dir D:\exports\s9_bvot_20260825_20260909 --workers 16
```

EXIT=0; 12 day CSVs; 79 name-occurrences total. Day name counts: 20260825=3, 26=4, 27=5, 28=6, 31=5, 0901=5, 02=9, 03=10, 04=8, 07=8, 08=9, 09=7.

Path is **host-local outside the repo** (`/exports/` gitignored; no lake secrets or live day CSVs committed). Pool policy + day counts are documented in this README / the addendum.

## Execute (4090)

```
python scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py \
  --execute --engines book --strategies version9 \
  --start 20260825 --end 20260909 \
  --pool-dir D:\exports\s9_bvot_20260825_20260909 \
  --output-dir backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat_v9_s9bvot_20260921 \
  --force
```

## Policy

- `production_C=frozen` — docs + research exports only; no fill/scan/fee/defaults/hot-path.
- **version10 ≠ s9**: v10 needs `export_strategy10_pool.py` (TR pool); leave DATA_GAP / out of scope.
- Forbid cross-engine NAV rank; do not re-rank #142 stock_pool Book rows against this s9 pool stamp.
- CSVs here recreated from verified 4090 numbers (zip unavailable on VM via CopyToBox).

Results: `docs/backtest/reviews/results-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md` §2/§9; addendum `addendum-batch4-v9-s9bvot-fill-2026-09-21.md`.
