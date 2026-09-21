# Addendum: batch4 Slice D fullstrat clock/slip hooks NAV/DD (2026-09-21)

After [#156](https://github.com/baiyibing/MyQuant-backtrader/pull/156) merged
the research-only fullstrat clock/slip hooks, 4090 executed Slice D
(clock XOR slip; **baseline intentionally not** in this D matrix) and exported
host stamp `D:\exports\batch4_fullstrat_hooks_d_20260921b\{core,v9,v10}\`.

This addendum + results §11 + research export stamp are a **docs / research
exports backfill only**. Numbers are transcribed from the attached authoritative
CSVs / `core/manifest.json`. **Do not invent NAV/DD.** Research-only; forbid
cross-engine NAV rank; `production_C=frozen`; **do not merge without human/bt tip**.

## Provenance

| field | value |
|---|---|
| window | `20260825`–`20260909` |
| cells | `clock_next_open_fullstrat`, `slip_5bp_fullstrat`, `slip_10bp_fullstrat`, `slip_20bp_fullstrat` |
| host export | `D:\exports\batch4_fullstrat_hooks_d_20260921b\{core,v9,v10}\` |
| repo stamp | [`batch4_fullstrat_hooks_d_20260921b`](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat_hooks_d_20260921b/) |
| `git_head` (manifest) | `3931dfd33ea7146f7dcf3ba5fa06a4bbc96b7c18` |
| `base_tip` | `32b78b1` |
| `emitted_at` | `2026-09-21T16:23:44+08:00` |
| contract | Q2 sizing · H2 all fills · same-day expiry · sell expiry = next-session reevaluate |
| fee / access | `DEFAULT_SCHEDULE=BILATERAL_10BP` · `qlib_bin_1min` |
| counts (core) | `book_ok=28`, `v7_ok=4`, `modeb_ok=4` |

## What filled

| surface | cells | note |
|---|---|---|
| Book v1–6,8 (`stock_pool` core) | 4 × 7 = **28 OK** | ranks within each cell only |
| ModeB (core) | **4 OK** | one top-by-`total_return` row per cell (oracle excluded) |
| v7 (core) | **4 OK** | strategy7 only |
| Book version9 (`s9_bvot` lineage) | **4 OK** | v9-only; **do not** re-rank vs stock_pool Book |
| Book version10 (`s10_tr` lineage) | **4 OK** | v10-only; lake∩TR research universe; **do not** re-rank across pools |
| ModeB / v7 on v9 or v10 pools | **N/A** | not supplied (book-only pool stamps); do not fabricate |

Baseline `baseline_default_clock_fee` numbers in results §1–§4 / §8–§10 are
**unchanged** by this slice (D matrix excludes baseline by design).

## Hard rules (restate)

1. Research-only hooks (H2 + Q2); not production fill/scan/fee/defaults.
2. Book / v7 / ModeB stay in separate tables; **forbid cross-engine NAV rank**.
3. v9 / v10 keep separate pool stamps; no cross-pool re-rank.
4. `production_C=frozen`. No production Python behavior change in this PR.
5. Draft PR only — **do not merge without human/bt tip**.

Full tables: [batch4 results §11](results-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md#11-slice-d--fullstrat-clockslip-hooks-4090--2026-09-21).
