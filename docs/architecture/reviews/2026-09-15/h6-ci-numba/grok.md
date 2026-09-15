## Summary

H6 aligns CI with `requirements.txt` so **numba is present and parity runs**. `.github/workflows/python-tests.yml` documents that `numba>=0.60` is in requirements (so `tests/test_scan_held_day_numba_parity.py` must not silent-skip) and adds a post-install step `python -c "import numba; ..."`. **Simulate / `scan_held_day` default remains the Python reference** (`use_numba` / env opt-in only — unchanged). Local check: numba 0.65.1; parity **4 passed**. Plan + backlog H6 ✓. No push / CloudAgent. **No valid 🔴.**

## Issues

### Issue 1 -- Severity: suggestion
- File: tests/test_scan_held_day_numba_parity.py
- Description: Module still uses `pytest.mark.skipif(not _NUMBA_SCAN_AVAILABLE)`. Correct for local/dev without numba; CI now fails earlier at the import assert, so the skip path should not fire on the main workflow.
- Suggestion: Optional later: fail (not skip) when `CI=true` and numba missing — redundant with workflow assert; out of H6 scope.
- Status: open (deferred)

### Issue 2 -- Severity: nit
- File: .github/workflows/python-tests.yml
- Description: Assert only imports numba; does not compile the njit path. Parity tests exercise the JIT body after pytest starts.
- Suggestion: Sufficient for H6 “loud if missing”; no change needed.
- Status: open (accepted)

## Checklist vs plan

| Plan item | Result |
|-----------|--------|
| Plan doc | `docs/backtest/plan-h6-ci-numba-2026-09-15.md` |
| Workflow comment + `import numba` assert | Done |
| Do not force numba as simulate default | Confirmed (Python default) |
| Backlog H6 ✓ | Updated |
| Push / CloudAgent | Not done |
| Valid 🔴 | None |
