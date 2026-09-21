# Addendum: batch4 Book version10 filled via s10_tr (2026-09-21)

Book **version10** baseline is now filled from verified 4090 numbers for
`20260825`–`20260909`. This follows [#145](https://github.com/baiyibing/MyQuant-backtrader/pull/145)'s
docs + research exports file set.

## Pool export and research universe

Pool host path (citation only): `D:\exports\s10_tr_bb1000_20260825_20260909`.
Rule: `resist_tr_bb_1000` via Source-B / `export_strategy10_pool.py` path.
**12 day CSVs; 115 name-occurrences; never `stock_pool/`.**

Day name counts: 20260825=19, 20260826=16, 20260827=6, 20260828=7,
20260831=8, 20260901=9, 20260902=3, 20260903=4, 20260904=10,
20260907=5, 20260908=13, 20260909=15.

**Universe limitation:** the stock CLI `export_strategy10_pool.py` with the
full lake universe failed closed: lake ⊃ TR cross-section (e.g. missing
`000001.SZ` on `20260825`). The research one-shot used **lake ∩ TR
cross-section** as its universe, then applied the `fail_closed` filter.
This restricted research universe is part of the result's provenance;
it does not demonstrate a successful full-lake CLI export and is **not a
production change**. No workaround implementation is committed here.

## Book version10 baseline

| field | value |
|---|---|
| engine / strategy | Book / version10 |
| window | `20260825`–`20260909` |
| cell | `baseline_default_clock_fee` |
| clock / slip / fee | `production_default` / 0 / `DEFAULT_SCHEDULE=BILATERAL_10BP` |
| access | `qlib_bin_1min` |
| final_equity | **21025809.91** |
| total_return | **0.0012** (+0.12%) |
| max_drawdown | **-0.0006** (−0.06%) |
| status | OK |
| within_engine_rank | 1 (v10-only stamp; forbid cross-engine rank) |

Stamp: [batch4_fullstrat_v10_s10tr_20260921](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat_v10_s10tr_20260921/).

Same-window v9 reference from #145: pool `s9_bvot`,
`final_equity=21053316.65`, +0.25%, DD −0.19%. These are separate pool
stamps, not a combined ranking or a cross-engine comparison.

## Provenance and existing TR context

These summary exports are recreated from the user-supplied verified 4090
numbers; the host zip is unavailable on this VM. No backtest or pool export
was rerun here. The exact 4090 run tip was not supplied (`base_tip: null`).
CSV column schemas and Book lineage labels follow the #145 v9 stamp.

4090 host artifact (citation only):
`D:\PycharmProjects\MyQuant-backtrader\backtest\research\exports\minute_sensitivity_b_20260920\batch4_fullstrat_v10_s10tr_20260921`.

TR context already merged: [#146 refresh_tr_store_window](https://github.com/baiyibing/MyQuant-backtrader/pull/146),
[#147 path-ssot allowlist](https://github.com/baiyibing/MyQuant-backtrader/pull/147),
[#148 utf-8-sig BOM](https://github.com/baiyibing/MyQuant-backtrader/pull/148).
4090 TR store through `20260909`; bands via vectorized path. Context only;
these changes are not repeated here.

## Scope

- `production_C=frozen`: docs + research exports only; no production Python / fill / scan / fee / defaults / hot-path changes.
- Keep v8/v9/v7/ModeB results intact. Do not re-rank across stamps or pools; **forbid cross-engine rank**.
- Fullstrat `clock_next_open` / `slip_*` cells remain **DATA_GAP**.
- Host paths are citations only; no live pool CSVs are committed and `stock_pool/` is never written.

Results updated in [batch4 results](results-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md) §2 / §10.
