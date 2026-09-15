## Summary

H9 ships a **Theme C soft slice**: read-only list-quality / pool-dir tooling — **not** MyQuant `run-manifest` integration (still deferred; progress-sync 「本仓暂不接」). Library `backtest.research.pool_list_quality` + CLI `scripts/research/report_pool_list_quality.py` report day count, empty days, code-count histogram, optional day-aligned overlap (intersection / Jaccard / only-A / only-B), and `validate_pool_dir` failures. Reuses `parse_pool_csv` + `validate_pool_dir` only; **no** lake writes, **no** `qlib`, **no** simulate/sell changes. Pytest `tests/test_report_pool_list_quality.py` (tmp_path) green with `test_csv_pool`. Plan + contract pointer + backlog H8✓/H9✓; themes **A–F still open**; run-manifest still deferred. No push / CloudAgent. **No valid 🔴.**

## Issues

### Issue 1 -- Severity: suggestion
- File: backtest/research/pool_list_quality.py:`load_pool_codes_by_day`
- Description: Eight-digit stems that fail calendar validation (e.g. `20260230.csv`) still enter the day map / histogram; they are also flagged by `validate_pool_dir` filename checks.
- Suggestion: Optional later filter to valid calendar dates for day_count only; current dual surface (map + validate errors) is acceptable for a quality CLI.
- Status: open (accepted)

### Issue 2 -- Severity: nit
- File: backtest/research/pool_list_quality.py:`main`
- Description: Process exit code is `1` when any `validate_pool_dir` error exists (else `0`; bad paths `2`). Useful as a gate; callers who only want stdout must check exit.
- Suggestion: Keep; document in CLI help if users confuse with argparse failures.
- Status: open (accepted)

### Issue 3 -- Severity: nit
- File: docs/backtest/plan-h9-list-quality-2026-09-15.md
- Description: Full MyQuant run-manifest / `csv_daily` consume path remains explicitly out of scope.
- Suggestion: Separate slice when this repo chooses to hard-wire manifests; do not fold into H9.
- Status: open (deferred by design)

## Checklist vs plan

| Plan item | Result |
|-----------|--------|
| Plan doc | `docs/backtest/plan-h9-list-quality-2026-09-15.md` |
| CLI / library | `scripts/research/report_pool_list_quality.py` + `backtest/research/pool_list_quality.py` |
| day / empty / histogram / overlap / validate | Implemented; no lake / qlib |
| Pytest tmp_path | `tests/test_report_pool_list_quality.py` (5) + csv_pool green |
| Contract / README pointer | `pool-csv-contract.md` H9 section; README SSOT row |
| Backlog H8✓ + H9; A–F open; run-manifest deferred | Updated |
| Push / CloudAgent | Not done |
