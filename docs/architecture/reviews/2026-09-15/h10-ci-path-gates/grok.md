## Summary

H10 is a **Theme E soft slice**: expand CI **path-SSOT / contract gates that run without the F lake** (repo-only). Inventory of `scripts/gates/*.py` documents two pre-existing data-free gates already in CI (`verify_oskh_data_contract.py`, `verify_data_path_ssot.py`), one new data-free gate (`verify_no_hardcoded_machine_paths.py`), and nine lake-backed / L2 gates that must **not** enter CI (would fail or noop-SKIP without `F:\stock_data`). `verify_data_path_ssot` now also scans `common/` with allowlisted resolver joins. Workflow Contract gates step runs all three data-free scripts before pip. Docs pointers in `docs/backtest/README.md` + `AGENTS.md`; backlog H9✓/H10✓; themes **A–F still open**; run-manifest still deferred. Local: three gates exit 0; related path/research pytest **passed**. No simulate/sell changes. No push / CloudAgent. **No valid 🔴.**

## Issues

### Issue 1 -- Severity: suggestion
- File: scripts/gates/verify_data_path_ssot.py
- Description: Line scanner still counts docstring lines that mention `period={period}` inside `common/infra/data_root.py` (5 allowlisted hits mix docs + real joins).
- Suggestion: Optional later: ignore AST docstring line ranges like the machine-paths gate; shrink allowlist. Out of H10 soft scope.
- Status: open (accepted)

### Issue 2 -- Severity: nit
- File: scripts/gates/verify_l2_manifest.py
- Description: Exits 0 with SKIP when parquet root / manifest absent — technically “does not fail without lake”, but CI would always SKIP with no signal.
- Suggestion: Keep out of CI (as plan); host-only when L2 tree present.
- Status: open (accepted)

### Issue 3 -- Severity: nit
- File: backtest/tools/read_app_data.py
- Description: `__main__` demo no longer hardcodes `E:\PycharmProjects\...`; requires argv path.
- Suggestion: Sufficient for the machine-paths gate; no further change.
- Status: open (accepted)

## Checklist vs plan

| Plan item | Result |
|-----------|--------|
| Plan + inventory table | `docs/backtest/plan-h10-ci-path-gates-2026-09-15.md` |
| Expand path-ssot → `common/` | Done + allowlist |
| New data-free machine-paths gate | `scripts/gates/verify_no_hardcoded_machine_paths.py` |
| Workflow Contract gates | + `verify_no_hardcoded_machine_paths.py`; lake gates excluded |
| README / AGENTS pointers | Done |
| Backlog H9✓ + H10; A–F open; run-manifest deferred | Updated |
| Push / CloudAgent | Not done |
| Valid 🔴 | None |
