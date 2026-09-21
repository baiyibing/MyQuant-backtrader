# Grok review — PR #149 docs batch4 Book version10 / s10_tr

**Independent re-review** of the files on `docs/batch4-v10-s10tr-fill` (not a rubber-stamp of the earlier on-branch note). Adversarial docs/research-only audit. **Do not merge.**

**CI:** pytest-and-gates SUCCESS (https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35566576324). Content still verified below; CI does not prove number integrity.

**Verdict: PASS_WITH_NITS**

The earlier on-branch `PASS_WITH_NITS` **holds on content**. Two claims in that note are stale/wrong and are corrected here: (1) it called #149 a Draft PR — GitHub now has `isDraft=false` (ready); (2) it cited CI run `35565970973` — the check on the PR after that review commit is `35566576324`. Neither changes the content verdict.

Fill commit `8b9b20c` vs parent `4adad96` transcribes a Book version10 baseline from verified 4090 numbers (window `20260825`–`20260909`). Hard rules hold: headline figures match across artifacts, scope is docs + research exports, lake∩TR is documented as a research restriction, v9 is a same-window reference only, clock/slip stay `DATA_GAP`. This re-review is research-only; no production Python / fill / scan / fee / defaults / `stock_pool/` writes.

## Scope check

**PASS.** Fill commit: `7 files changed, 264 insertions(+), 7 deletions(-)` — the #145 seven-file set. Plus this review path vs `master`: 8 files.

| Path | Role |
|---|---|
| `backtest/research/exports/.../batch4_fullstrat_v10_s10tr_20260921/{README.md,book_nav.csv,data_gaps.csv,manifest.json,matrix.csv}` | new v10 stamp |
| `docs/backtest/reviews/addendum-batch4-v10-s10tr-fill-2026-09-21.md` | new addendum |
| `docs/backtest/reviews/results-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md` | results update |
| `docs/architecture/reviews/2026-09-21/pr-149-batch4-v10-s10tr/grok.md` | this review (research-only) |

No production Python, fill/scan/fee/defaults/hot-path, `stock_pool/` writes, or live pool CSVs. Original `batch4_fullstrat/` and v9 stamp files are untouched (v9 `data_gaps.csv` still records then-current v10 `DATA_GAP`; results §6 labels that as historical). CSV headers match #145 (`book_nav` / `matrix` / `data_gaps`). Parsed widths: book_nav 18/18 (1 data row), matrix 11 cols × 5 data rows, data_gaps 3 cols × 6 data rows. Manifest JSON parses; `final_equity` / `total_return` / `max_drawdown` round-trip exactly. UTF-8, no BOM/NUL; `git diff --check` clean.

`export_strategy10_pool.py` is the documented alias of `export_ta_pool.py` (same `main`); citing that path is not a wrong-exporter claim.

## Number integrity

**PASS.** Canonical triple in `book_nav.csv`, `matrix.csv` FILLED row, `manifest.json`, stamp README, addendum, and results §10:

| field | value |
|---|---|
| `final_equity` | `21025809.91` |
| `total_return` | `0.0012` (+0.12%) |
| `max_drawdown` | `-0.0006` (−0.06%) |
| status / rank | OK / 1 (v10-only stamp) |

Results §2 display form `21,025,809.91` / `+0.12%` / `−0.06%` is the same triple. Day counts `19+16+6+7+8+9+3+4+10+5+13+15 = 115` with 12 day CSVs (trading days `20260825`–`28`, `31`, `0901`–`04`, `07`–`09`), matching `pool_name_occurrences_total` / `pool_day_csv_count`. `base_tip: null` and `csv_source=recreated_from_verified_4090_numbers_zip_unavailable_on_vm` are stated. Return vs ≈21e6 start is `0.001229…` → 4-dp `0.0012` / `+0.12%`, same rounding as v9 (`0.002538…` → `0.0025` / `+0.25%`).

Preserved (not re-ranked): v8 `21,104,115.65`; v9 `21053316.65` / `0.0025` / `-0.0019`; v7 `20,895,023.51`; ModeB `1099605762.3151746`. Same-window v9 cite is labeled separate pool/stamp, not a combined ranking. §1 Book engine-internal #1 remains version8 (stock_pool stamp). §2 uses `1†` / `1‡` with “不跨池/戳重排”. No 优于/好于 language.

Host zip was not on this VM; this review does not re-derive DD from bars. Integrity check is cross-artifact consistency + constraint honesty, not a 4090 replay.

## Constraints

**PASS.**

- **`production_C=frozen`:** docs + research exports only. Manifest `production_C: "frozen"`. No production C / fill / scan / fee / defaults / hot-path files in the diff. Workaround is documentation only (“No workaround implementation is committed here”).
- **No `stock_pool/`:** host path is citation-only (`D:\exports\s10_tr_bb1000_20260825_20260909`). `data_gaps.csv` row `stock_pool_for_version10,FORBIDDEN`. Mentions are refusals/history, not writes.
- **lake∩TR honesty:** stock CLI `export_strategy10_pool.py` / `export_ta_pool.py` default universe is lake period=1d names with a bar on T (`fail_closed=True`). Lake ⊃ TR fail-closed (e.g. missing `000001.SZ` on `20260825`) matches designed `ConfigurationError` / missing cross-section-row behavior (see also `docs/backtest/s9-s10-host-smoke-2026-09-13.md`). Research one-shot used **lake ∩ TR** then `fail_closed`. Stated as provenance, not full-lake CLI success, not a production fix. Repeated in README, addendum, results §10, `book_nav` note, `matrix` note, `manifest.pool_policy`.
- **Clock/slip stay `DATA_GAP`:** v10 `matrix.csv` clock/slip rows empty; `data_gaps.csv` `fullstrat_clock_swap` / `fullstrat_slip_axis`; results §1 matrix, §7 item 3, §8, §9, §10. Status remains `EXECUTED_PARTIAL`.
- **Cross-engine / cross-pool rank forbidden:** `within_engine_rank=1` is v10-only; `forbid_cross_engine_nav_rank: true`.

## Nits (non-blocking)

1. Results **依据** line still cites the v9 stamp and not the new v10 stamp (v10 is in §6 / §10). #145 added the v9 stamp there; this fill did not do the analogue.
2. `data_gaps.csv` FILLED evidence cites `final_equity=21025809.91` only; return/DD live in the other artifacts.
3. Cosmetic: decimal `max_drawdown` uses ASCII `-0.0006` while the percent gloss uses unicode minus `−0.06%` (v9 used unicode on both).
4. Results §2 / §6 / §7 abbreviate the pool as `s10_tr`; stamp / addendum / host path use `s10_tr_bb1000`. Same pool, not a second universe.

## Process

GitHub PR #149 is **ready** (`isDraft=false`) even though the fill constraint and PR body say leave draft. This re-review does not merge and does not mark ready. Converting ready→draft is not available from this reviewer path. **Do not merge.**

## Out of scope (not charged)

- Original `batch4_fullstrat/book_nav.csv` still has version10 `DATA_GAP` (and a pre-existing stderr that names `export_strategy9_pool.py` for version10). Leaving that stamp untouched is the #145 pattern.
- No 4090 execute/export command or tip in the v10 README (unlike v9). Consistent with `base_tip: null` / zip unavailable / no local rerun.
