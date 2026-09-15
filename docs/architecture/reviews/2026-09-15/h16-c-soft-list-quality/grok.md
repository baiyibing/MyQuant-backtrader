## Summary

H16 is **Theme C soft+**: deepen in-repo pool list-quality on top of H9 — **not** MyQuant `run-manifest` hard integration (still deferred). Library `backtest.research.pool_list_quality` + CLI gain: `--format text|json|markdown`, `--top-n` frequent codes across days, day-over-day churn (added/removed), and stricter calendar stem reporting (`invalid_calendar_stems` / `valid_calendar_day_count`) addressing H9 Grok Issue 1. Still reuses `parse_pool_csv` + `validate_pool_dir` only; **no** lake writes, **no** qlib, **no** simulate/sell changes, **no** run-manifest consume. Pytest `tests/test_report_pool_list_quality.py` expanded (tmp_path) green with `test_csv_pool`. Plan + contract H9/H16 section + backlog **H16 ✓** + next-heavy C soft+ ✓ → next run-manifest hard (deferred). Push + PR → master. **No valid 🔴.**

## Issues

### Issue 1 -- Severity: nit
- File: backtest/research/pool_list_quality.py:`_report_to_dict`
- Description: JSON omits bulky `codes_by_day` (intentional for scripting); callers needing per-day sets still use the library API.
- Suggestion: Keep omit; document in contract (done via format flags).
- Status: accepted

### Issue 2 -- Severity: nit
- File: backtest/research/pool_list_quality.py:`day_over_day_churn`
- Description: Churn uses sorted eight-digit stems including invalid calendar keys; adjacent pairs may span non-trading gaps or bad stems.
- Suggestion: Acceptable for a quality CLI; filter to `valid_calendar` only in a later slice if needed.
- Status: open (accepted)

### Issue 3 -- Severity: nit
- File: docs/backtest/plan-h16-c-soft-list-quality-2026-09-15.md
- Description: Full MyQuant run-manifest consume remains explicitly out of scope (H9 Issue 3 carried forward).
- Suggestion: Separate slice when product chooses hard-wire; do not fold into H16.
- Status: open (deferred by design)

## Checklist vs plan

| Plan item | Result |
|-----------|--------|
| Plan doc | `docs/backtest/plan-h16-c-soft-list-quality-2026-09-15.md` |
| JSON / markdown / top-N / churn / calendar stems | Implemented |
| Pytest tmp_path | Expanded; green with csv_pool |
| Contract / README pointer | H9/H16 section + README row |
| Backlog H16 ✓; next-heavy C soft+ ✓; run-manifest deferred | Updated |
| No run-manifest / no simulate-sell | Confirmed |
| Push / PR → master | Pending this slice |
