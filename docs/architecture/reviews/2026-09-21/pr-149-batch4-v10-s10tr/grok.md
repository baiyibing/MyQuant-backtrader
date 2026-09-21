# Grok review — PR #149 docs batch4 Book version10 / s10_tr

**CI:** pytest-and-gates SUCCESS (https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35565970973)

**Verdict: PASS_WITH_NITS**

Draft PR #149 (`docs/batch4-v10-s10tr-fill`, `8b9b20c` vs parent `4adad96`) transcribes a Book version10 baseline from verified 4090 numbers. Hard rules hold: headline figures match, scope is docs + research exports, lake∩TR is documented as a research restriction, v9 is a same-window reference only, and clock/slip stay `DATA_GAP`. Leave the PR draft; do not merge.

## Scope check

**PASS.** Seven files vs parent; `7 files changed, 264 insertions(+), 7 deletions(-)`. Matches the #145 seven-file set (v10 stamp README / `book_nav.csv` / `data_gaps.csv` / `manifest.json` / `matrix.csv` + addendum + results).

| Path | Role |
|---|---|
| `backtest/research/exports/.../batch4_fullstrat_v10_s10tr_20260921/{README.md,book_nav.csv,data_gaps.csv,manifest.json,matrix.csv}` | new v10 stamp |
| `docs/backtest/reviews/addendum-batch4-v10-s10tr-fill-2026-09-21.md` | new addendum |
| `docs/backtest/reviews/results-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md` | results update |

No production Python, fill/scan/fee/defaults/hot-path, `stock_pool/` writes, or live pool CSVs. Original `batch4_fullstrat/` and v9 stamp files are untouched (v9 `data_gaps.csv` still records then-current v10 `DATA_GAP`; results §6 labels that as historical). CSV headers match #145; row widths parse (book_nav 18/18, matrix 11×6, data_gaps 3×7). UTF-8, no BOM/NUL; `git diff --check` clean.

## Number integrity

**PASS.** Canonical values appear in `book_nav.csv`, `matrix.csv`, `manifest.json`, README, addendum, and results §10:

| field | value |
|---|---|
| `final_equity` | `21025809.91` |
| `total_return` | `0.0012` (+0.12%) |
| `max_drawdown` | `-0.0006` (−0.06%) |
| status / rank | OK / 1 (v10-only stamp) |

Results §2 display form `21,025,809.91` / `+0.12%` / `−0.06%` is the same triple. Day counts `19+16+6+7+8+9+3+4+10+5+13+15 = 115` with 12 day CSVs, matching `pool_name_occurrences_total` / `pool_day_csv_count`. `base_tip: null` and `csv_source=recreated_from_verified_4090_numbers_zip_unavailable_on_vm` are stated.

Preserved (not re-ranked): v8 `21,104,115.65`; v9 `21053316.65` / `0.0025` / `-0.0019`; v7 `20,895,023.51`; ModeB `1099605762.3151746`. Same-window v9 cite is labeled separate pool/stamp, not a combined ranking.

## Constraints

**PASS.**

- **`production_C=frozen`:** docs + research exports only. Manifest `production_C: "frozen"`. No production C / fill / scan / fee / defaults / hot-path files in the diff. Workaround is documentation only (“No workaround implementation is committed here”).
- **No `stock_pool/`:** host path is citation-only (`D:\exports\s10_tr_bb1000_20260825_20260909`). `data_gaps.csv` row `stock_pool_for_version10,FORBIDDEN`. Mentions are refusals/history, not writes.
- **lake∩TR honesty:** full-lake `export_strategy10_pool.py` failed closed because lake ⊃ TR (e.g. missing `000001.SZ` on `20260825`); research one-shot used **lake ∩ TR** then `fail_closed`. Stated as provenance, not full-lake CLI success, not a production fix. Repeated in README, addendum, results §10, `book_nav` note, `matrix` note, `manifest.pool_policy`.
- **Clock/slip stay `DATA_GAP`:** v10 `matrix.csv` clock/slip rows empty; `data_gaps.csv` `fullstrat_clock_swap` / `fullstrat_slip_axis`; results §1 matrix, §7.3, §8, §9, §10. Status remains `EXECUTED_PARTIAL`.
- **Cross-engine / cross-pool rank forbidden:** `within_engine_rank=1` is v10-only; §2 uses `1‡` with “不跨池/戳重排”; `forbid_cross_engine_nav_rank: true`.

## Nits

1. Results **依据** line still cites the v9 stamp and not the new v10 stamp (v10 is in §6 / §10). #145 added the v9 stamp there; this fill did not do the analogue.
2. `data_gaps.csv` FILLED evidence cites `final_equity=21025809.91` only; return/DD live in the other artifacts.
3. Cosmetic: decimal `max_drawdown` uses ASCII `-0.0006` while the percent gloss uses unicode minus `−0.06%` (v9 used unicode on both).
