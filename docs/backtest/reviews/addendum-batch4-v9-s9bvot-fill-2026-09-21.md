# Addendum: batch4 Book version9 DATA_GAP filled via s9_bvot pool (2026-09-21)

Book **version9** in batch4 originally reported `DATA_GAP` because the harness
refuses `stock_pool/` for version9 and requires `--pool-dir` from
`scripts/data/export_strategy9_pool.py`. That pool **was generated on
newtest_4090** (EXIT=0); this addendum documents the pool policy and the
verified Book baseline numbers. **No Codex script fix** — research harness
already accepted `--pool-dir`. Docs + research exports only;
`production_C=frozen` (no fill/scan/fee/defaults/hot-path).

## Pool export (4090 @ tip `51e0195`)

```
python scripts/data/export_strategy9_pool.py \
  --start 20260825 --end 20260909 \
  --out-dir D:\exports\s9_bvot_20260825_20260909 --workers 16
```

- EXIT=0; wrote **12** day CSVs; **79** name-occurrences total
- **Never wrote `stock_pool/`** (script refuses)
- Day name counts: 20260825=3, 26=4, 27=5, 28=6, 31=5, 0901=5, 02=9, 03=10, 04=8, 07=8, 08=9, 09=7
- Path is **host-local outside the repo** (`/exports/` is gitignored); pool policy + day counts live in the stamp README / this addendum (no live lake CSVs or secrets committed)

## Book version9 baseline execute (4090 @ tip `51e0195`)

```
python scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py \
  --execute --engines book --strategies version9 \
  --start 20260825 --end 20260909 \
  --pool-dir D:\exports\s9_bvot_20260825_20260909 \
  --output-dir backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat_v9_s9bvot_20260921 \
  --force
```

From `book_nav.csv` (recreated on VM from verified 4090 numbers; zip CopyToBox blocked):

| field | value |
|---|---|
| engine / strategy | Book / version9 |
| cell | `baseline_default_clock_fee` |
| clock / slip / fee | `production_default` / 0 / `DEFAULT_SCHEDULE=BILATERAL_10BP` |
| access | `qlib_bin_1min` |
| final_equity | **21053316.65** |
| total_return | **0.0025** (+0.25%) |
| max_drawdown | **−0.0019** (−0.19%) |
| status | OK |
| within_engine_rank | 1 (version9-only run) |

Stamp path:
`backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat_v9_s9bvot_20260921/`

## Scope / hard bans

- **version10 ≠ s9**: do **not** claim v10 filled; v10 needs
  `export_strategy10_pool.py` (TR pool). Leave DATA_GAP / out of scope.
- Keep #142 Book v8/other and #144 ModeB numbers; do not blank them.
- **Forbid cross-engine rank**; do not re-rank stock_pool Book rows against this
  s9-pool stamp as if they shared one matrix.
- Fullstrat `clock_next_open` / `slip_*` axes remain DATA_GAP.

Numbers filled in
`results-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md` §2 / §9.
