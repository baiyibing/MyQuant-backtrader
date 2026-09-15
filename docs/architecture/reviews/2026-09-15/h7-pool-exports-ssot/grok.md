## Summary

H7 is **docs-only SSOT** for pool lifecycle: `stock_pool/` = **mutable default** for strategies **1–6/8** (not a snapshot); `exports/` = **experimental / frozen** exporter trees via `--pool-dir`; **9/10 refuse** `stock_pool/` even if passed; **7** requires explicit `--pool-dir`. Landed in `docs/backtest/pool-csv-contract.md` (`## Lifecycle SSOT: stock_pool vs exports`) with pointers from root `README.md` and `docs/backtest/README.md`. **No Python behavior change.** Backlog H7 ✓ and **H1–H7 queue complete**. No push / CloudAgent. **No valid 🔴.**

## Issues

### Issue 1 -- Severity: nit
- File: docs/backtest/pool-csv-contract.md (pre-existing map paragraph)
- Description: Earlier prose still says “Strategies 6/8/9/10 omit an empty file…” for map shape, while defaults are “1–6/8”. Not contradictory (map vs default dir) but easy to skim wrong.
- Suggestion: Optional later tighten to “strategies that use the shared YYYYMMDD map…” — out of H7 scope.
- Status: open (deferred)

### Issue 2 -- Severity: suggestion
- File: README.md / docs/backtest/README.md fragment links
- Description: Anchors use `#lifecycle-ssot-stock_pool-vs-exports` matching the cleaned English heading. Some Markdown UIs slug differently (underscores / backticks).
- Suggestion: Heading kept punctuation-light for GitHub; if a viewer breaks, fall back to the file top link already present.
- Status: open (accepted)

## Checklist vs plan

| Plan item | Result |
|-----------|--------|
| Plan doc | `docs/backtest/plan-h7-pool-exports-ssot-2026-09-15.md` |
| SSOT in pool-csv-contract | Done |
| README / docs/backtest README pointers | Done |
| No Python behavior change | Confirmed |
| Backlog H7 ✓; queue H1–H7 complete | Updated |
| Push / CloudAgent | Not done |
| Valid 🔴 | None |
