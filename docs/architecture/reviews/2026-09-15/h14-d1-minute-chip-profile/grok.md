## Summary

H14 = **D1 Theme D profile** for this repo’s minute/hybrid chip hot paths (not MyQuant CYQ feeder). Delivered: plan, synthetic `bench_minute_chip_hotpath.py` (no F lake), results note with ranked timings + **D2 = numba `minute_chip_distribution` first** (hybrid/curpdf leave; `calc_cumpdf` already numba; Rust deferred), backlog **H14 ✓**, next-heavy refreshed (D1✓ → D2 → C soft → run-manifest deferred), inventory §D pointer, README/chip README links. No algorithm semantic changes; no CloudAgent; no full-market lake run. Absolute `/workspace/vanna312/...` run snippets in draft docs were corrected to portable `python scripts/...` (valid 🔴 fixed). **No remaining valid 🔴.**

## Issues

### Issue 1 -- Severity: 🔴 (fixed)
- File: docs/backtest/plan-h14-d1-minute-chip-profile-2026-09-15.md · h14-d1-minute-chip-profile-results-2026-09-15.md
- Description: Draft run snippets used absolute `/workspace/vanna312/bin/python`, host-layout-specific (same class of hygiene as H13 machine-path nit).
- Suggestion: Document portable `python scripts/...` plus a non-absolute “prefer vanna312” tip.
- Status: **fixed**

### Issue 2 -- Severity: suggestion
- File: scripts/research/bench_minute_chip_hotpath.py
- Description: Synthetic random-walk prices keep bin counts modest (~200–400); real high-volatility names may widen grids and raise per-call cost. Rank order (minute ≫ hybrid ≫ cumpdf) is still robust for D2 triage.
- Suggestion: Optional `--seed` / wider `--step` knobs already exist via args; D2 can add a one-line “real parquet smoke” later without blocking this slice.
- Status: open (accepted)

### Issue 3 -- Severity: suggestion
- File: docs/backtest/chip/h14-d1-minute-chip-profile-results-2026-09-15.md
- Description: ms/call numbers are single-machine box timings under vanna312; do not treat as CI gate thresholds.
- Suggestion: Keep results as research evidence; D2 should add parity tests, not bake these ms into CI.
- Status: open (accepted)

### Issue 4 -- Severity: nit
- File: oskh_factors/chip/core.py (unchanged)
- Description: Profile confirms per-bar `np.zeros` allocation inside `minute_chip_distribution` — expected hotspot; out of H14 scope to rewrite.
- Suggestion: D2 should reuse one buffer / accumulate without reallocating each bar.
- Status: open (accepted; D2)

## Checklist vs plan

| Plan item | Result |
|-----------|--------|
| Plan `plan-h14-d1-minute-chip-profile-2026-09-15.md` | Done |
| `bench_minute_chip_hotpath.py` + timings / optional cProfile | Done |
| Results note + D2 recommendation | Done (numba minute; leave hybrid/cumpdf; no Rust yet) |
| Backlog H14 ✓ + next-heavy refresh | Done |
| Inventory / README / chip README pointers | Done |
| Grok review + fix valid 🔴 | Done (Issue 1 path hygiene) |
| Algorithm / lake / MyQuant feeder / CloudAgent | Not done |
| Push + PR → master | In delivery |
| Remaining valid 🔴 | None |
