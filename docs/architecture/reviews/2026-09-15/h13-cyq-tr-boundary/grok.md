## Summary

H13 is a **docs-only Theme D boundary** slice: record that MyQuant’s numba full-market daily `winner_ratio` / CYQ feeder (`build_winner_ratio.py`, aligned with this repo’s `qlib_cost.cyq` SSOT) is a **separate product path** from this repo’s Rust `turnover-resist` TR/cyqk audit & Store path. Inventory gains §E comparison table + §F non-goals; README / chip README / AGENTS / CONTRIBUTING don’t-do point at the boundary; hygiene backlog marks **H13 ✓** and refreshes next-heavy (D1 minute/hybrid profile → C soft list-quality deepen → run-manifest hard still deferred). No algorithm / sell-book / Rust rewrite / CloudAgent. Absolute `/workspace/MyQuant/...` evidence paths in draft docs were corrected to sibling-relative names (valid 🔴 fixed). Duplicate `---` before inventory §E removed (nit fixed). **No remaining valid 🔴.**

## Issues

### Issue 1 -- Severity: 🔴 (fixed)
- File: docs/backtest/chip/chip-slowpath-inventory-2026-09-15.md · plan-h13-cyq-tr-boundary-2026-09-15.md
- Description: Evidence pointers used absolute box path `/workspace/MyQuant/...`, which is host-layout-specific and conflicts with the repo’s “no hardcoded machine paths” hygiene habit for durable docs.
- Suggestion: Cite sibling checkout paths `MyQuant/my_scripts/build_winner_ratio.py` and `MyQuant/docs/winner-ratio-cyq-parity-2026-09-14.md` (read-only, not vendored).
- Status: **fixed**

### Issue 2 -- Severity: nit (fixed)
- File: docs/backtest/chip/chip-slowpath-inventory-2026-09-15.md
- Description: Double horizontal rule (`---` twice) immediately before §E after insert.
- Suggestion: Keep a single `---` separator.
- Status: **fixed**

### Issue 3 -- Severity: suggestion
- File: docs/backtest/chip/chip-slowpath-inventory-2026-09-15.md
- Description: User-confirmed ~53s full-market timing differs from MyQuant parity doc’s ~101s figure for a similar 5569×166 window — both can be true across hardware/workers; inventory correctly labels “用户确认”.
- Suggestion: If a later slice re-benches, add one footnote; out of H13 scope to reconcile clocks.
- Status: open (accepted)

### Issue 4 -- Severity: suggestion
- File: docs/backtest/plan-hygiene-backlog-2026-09-15.md
- Description: Soft themes A–F remain open while H1–H13 soft slices are covered — correct framing; next-heavy list is the right handoff.
- Suggestion: Keep run-manifest hard out of soft hygiene; open D1 / C soft as dedicated plans when starting work.
- Status: open (accepted)

## Checklist vs plan

| Plan item | Result |
|-----------|--------|
| Plan `plan-h13-cyq-tr-boundary-2026-09-15.md` | Done |
| Inventory §E MyQuant CYQ vs Rust TR + §F non-goals | Done |
| README / chip README / AGENTS pointers | Done |
| CONTRIBUTING don’t-do (no MyQuant CYQ reimplement) | Done |
| Backlog H13 ✓ + next-heavy refresh | Done |
| Grok review + fix valid 🔴 | Done (Issue 1) |
| Algorithm / Rust rewrite / CloudAgent | Not done |
| Push + PR → master | In delivery |
| `plan-brainstorm-next-heavy-2026-09-15.md` | Done (same branch) |
| Remaining valid 🔴 | None |
