## Summary

H8 ships a **semantics-preserving** daily sell-loop index micro-opt (theme **A**, deferred from H5 Grok Issue 2): `day_bar_and_prev_closes(df, day)` in `csv_common` uses sorted `DatetimeIndex.searchsorted` + `iloc` instead of `day in index` / `.loc[day]` / `df.loc[df.index < day]` mask copies. Wired into `csv_daily_backtest.simulate` **sell** loop and the same-day **chase** / **pool** quote closures (identical lookup shape; risk-free shared helper). Fill/sell reasons, limit-down defer, strategy books, and public `simulate` API unchanged. Synthetic `scripts/research/bench_daily_sell_index.py`: naive vs fast ~**1.81×** (40 codes × 240 bar-days, 44 sample days → 1760 lookups/rep × 30 reps; values match). Pytest `/workspace/vanna312/bin/python`: **99 passed** (`test_daily_sell_index` + `csv_daily*` + `test_daily_mark_cache` + `test_research_face_imports`). Plan + backlog H8 ✓; soft-extend notes themes **A–F still open**. No push / CloudAgent. **No valid 🔴.**

## Issues

### Issue 1 -- Severity: suggestion
- File: backtest/research/csv_ledger.py:`market_close_mark`
- Description: Halt / missing-day mark path still builds `df.loc[df.index < day]` (H5 Grok Issue 1). H8 intentionally left mark alone to keep the sell-index slice small.
- Suggestion: Optional later reuse of searchsorted / shared prior-close helper once mark golden coverage is expanded.
- Status: open (deferred; out of H8 scope)

### Issue 2 -- Severity: nit
- File: backtest/research/csv_common.py:`day_bar_and_prev_closes`
- Description: Contract requires ascending unique index (documented). `load_daily_bars` already `sort_index` + drop duplicates; unsorted inject fixtures could disagree with naive `.loc` membership edge cases.
- Suggestion: Keep as documented precondition; do not add runtime monotonic checks on the hot path.
- Status: open (accepted)

### Issue 3 -- Severity: nit
- File: scripts/research/bench_daily_sell_index.py
- Description: Bench times helper lookups (sell/chase/pool pattern), not full `simulate()` wall-clock — same shape as H5 `bench_daily_mark`.
- Suggestion: Enough for H8 success criteria; optional later wrap of a synthetic held-day `simulate` if profiling still needs end-to-end proof.
- Status: open

## Checklist vs plan

| Plan item | Result |
|-----------|--------|
| Plan doc | `docs/backtest/plan-h8-daily-sell-index-2026-09-15.md` |
| `day_bar_and_prev_closes`; sell + shared chase/pool | `csv_common` + `csv_daily_backtest.simulate` |
| No fill/sell / 6/8 / limit-down change | Confirmed (helper swap only) |
| Microbench | `scripts/research/bench_daily_sell_index.py` (~1.81×) |
| Unit / golden | `tests/test_daily_sell_index.py` + existing `csv_daily*` |
| pytest csv_daily* + research_face | 99 passed |
| Backlog H8 ✓; A–F still open | Updated |
| Hotpath note | Updated |
| Push / CloudAgent | Not done |
