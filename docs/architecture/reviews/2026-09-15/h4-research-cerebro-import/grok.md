## Summary

H4 fences the vectorized research face against accidental `backtrader` / Cerebro coupling without deleting fossil modules. `tests/test_research_face_imports.py` now (1) import-smokes the five main-path modules (`csv_daily_backtest`, `csv_minute_backtest`, `csv_simulate_loop`, `csv_common`, `csv_strategy_books`), (2) subprocess-isolates each import and asserts `backtrader` never enters `sys.modules` (covers transitive graph; fails if `backtrader` is missing and required), and (3) AST-scans those five sources for direct `backtrader` / `bt` roots. Chip / ma_chip / `verify_cerebro_*` remain free to import bt. Plan + backlog H4 ✓; no production code / Cerebro deletions. Pytest with `/workspace/vanna312/bin/python`: **38 passed** in ~3s (`test_research_face_imports` + `test_csv_strategy_books`). No valid 🔴.

## Issues

### Issue 1 -- Severity: suggestion
- File: tests/test_research_face_imports.py (AST helper)
- Description: `test_vectorized_research_face_ast_no_backtrader` only inspects the five leaf files' import nodes. A future `importlib.import_module("backtrader")` or a new first-party helper under `backtest.research` that pulls bt would still be caught by the subprocess graph test, but not by AST alone.
- Suggestion: Keep subprocess as the SSOT for "dependency graph"; optionally extend AST to a closed walk of `backtest.research.*` imports rooted at the five modules if static CI without spawn is desired later.
- Status: open

### Issue 2 -- Severity: nit
- File: tests/test_research_face_imports.py:_VECTORIZED_RESEARCH_FACE
- Description: `csv_minute_backtest_v7` (金榕元独立入口) is outside the five-module fence listed in the backlog/plan. Spot-check: it imports through the same vectorized stack and currently pulls no bt; not required by H4 wording.
- Suggestion: Optionally add `csv_minute_backtest_v7` in a follow-up if v7 should share the same import contract explicitly.
- Status: open

## Checklist vs plan

| Plan item | Result |
|-----------|--------|
| Plan doc | `docs/backtest/plan-h4-research-cerebro-import-2026-09-15.md` |
| Strengthen `test_research_face_imports` (import + no bt) | Subprocess graph + AST direct + importable smokes |
| Prefer pytest over new gate | No new `scripts/gates` snippet |
| Backlog H4 ✓ | Marked |
| Pytest green | 38 passed |
| Cerebro modules not deleted | Confirmed (chip/ma_chip/verify still present) |
| Push / CloudAgent | Not done |
