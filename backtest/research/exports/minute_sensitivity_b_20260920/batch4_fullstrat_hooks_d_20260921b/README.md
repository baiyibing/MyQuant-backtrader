# Slice D · fullstrat clock/slip hooks (4090 · 2026-09-21)

Research-only NAV/DD backfill after #156 merge. **Not** a production change.
`production_C=frozen`. Forbid cross-engine NAV rank. Baseline cell intentionally
**not** in this D matrix (clock XOR slip only).

## Provenance

| field | value |
|---|---|
| window | `20260825`–`20260909` |
| cells | `clock_next_open_fullstrat`, `slip_5bp_fullstrat`, `slip_10bp_fullstrat`, `slip_20bp_fullstrat` |
| host export | `D:\\exports\\batch4_fullstrat_hooks_d_20260921b\\{core,v9,v10}\\` |
| git_head (manifest) | `3931dfd33ea7146f7dcf3ba5fa06a4bbc96b7c18` |
| base_tip | `32b78b1` |
| emitted_at | `2026-09-21T16:23:44+08:00` |
| counts | `book_ok=28`, `v7_ok=4`, `modeb_ok=4` (core) |

## Layout

- `core/` — Book v1–6,8 (28 OK) + ModeB (4) + v7 (4); `manifest.json`
- `v9/book_nav.csv` — Book version9 only (4 cells; pool=`s9_bvot` lineage)
- `v10/book_nav.csv` — Book version10 only (4 cells; pool=`s10_tr` lineage)

ModeB / v7 for v9 and v10 pool stamps: **N/A** (not supplied / not run on those pools).

Docs: `docs/backtest/reviews/results-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md` §11;
`docs/backtest/reviews/addendum-batch4-slice-d-fullstrat-hooks-2026-09-21.md`.
