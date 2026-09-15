## Summary

H5 ships a **semantics-preserving** daily equity mark micro-opt: `market_close_mark(df, day) -> Optional[float]` in `csv_ledger`, and `append_equity_and_eod_marks` caches that close **once per code** for multi-lot equity + EOD_MARK reuse (per-lot `pos.cost` only when no on/prior bar). Sell/fill path and strategy books untouched. Synthetic `scripts/research/bench_daily_mark.py`: naive vs cached ~**2.78×** (40 codes × 3 lots × 240 days, 300 reps; values match). Pytest `/workspace/vanna312/bin/python`: **96 passed** (`test_daily_mark_cache` + `csv_daily*` + `test_research_face_imports`). Plan + backlog H5 ✓ + hotpath note. No push / CloudAgent. **No valid 🔴.**

## Issues

### Issue 1 -- Severity: suggestion
- File: backtest/research/csv_ledger.py:`market_close_mark`
- Description: Halt / missing-day path still builds `df.loc[df.index < day]` (boolean mask copy). Correct and unchanged vs pre-H5 `last_close_mark`; per-code cache only cuts *repeat* work across lots/EOD.
- Suggestion: Later optional `searchsorted` / precomputed calendar index if profiling still shows mark-bound; needs golden tests — out of H5 scope.
- Status: open (deferred)

### Issue 2 -- Severity: nit
- File: backtest/research/csv_daily_backtest.py:`simulate` sell / chase / pool quote closures
- Description: Day loop still does per-code `.loc[day]` and `index < day` for sells and quotes. Explicitly deferred by H5 plan (sell-semantics risk).
- Suggestion: Separate slice with golden NAV fixtures before any prev_close precompute.
- Status: open (deferred; backlog/hotpath already note)

### Issue 3 -- Severity: nit
- File: scripts/research/bench_daily_mark.py
- Description: Bench compares naive `last_close_mark`-per-lot vs cache logic inlined in the script (mirrors production), not a wall-clock of full `simulate()`.
- Suggestion: Enough for H5 success criteria; optional later wrap of `append_equity_and_eod_marks` with fake SimState if desired.
- Status: open

## Checklist vs plan

| Plan item | Result |
|-----------|--------|
| Plan doc | `docs/backtest/plan-h5-daily-mark-micro-2026-09-15.md` |
| Per-code mark cache; no fill/sell change | `market_close_mark` + `append_equity_and_eod_marks` |
| Microbench | `scripts/research/bench_daily_mark.py` (~2.78×) |
| Unit / golden | `tests/test_daily_mark_cache.py` + existing halt/zero-vol equity tests |
| pytest csv_daily* + research_face | 96 passed |
| Backlog H5 ✓ / hotpath note | Updated |
| No sell engine / strategy book rewrite | Confirmed |
| Push / CloudAgent | Not done |
