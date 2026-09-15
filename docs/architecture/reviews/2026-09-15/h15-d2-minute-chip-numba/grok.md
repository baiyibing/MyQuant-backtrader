## Summary

H15 = **D2 Theme D offload** for this repo’s `minute_chip_distribution` (not MyQuant CYQ feeder; not Rust). Delivered: plan, Python reference (`minute_chip_distribution_python`) + optional numba kernel gated like `scan_held_day` (`use_numba=` / `MINUTE_CHIP_BACKEND=numba|jit`; Python default), `tests/test_minute_chip_numba_parity.py` (skip if no numba), bench compares python vs numba when available (~**58×** on 80×240 synth @ vanna312), backlog **H15 ✓**, next-heavy D2 ✓ → **C soft+**, inventory §D minute → **optional numba** (hybrid leave). Semantic lock preserved; hybrid/curpdf/cumpdf untouched. No CloudAgent. **No remaining valid 🔴.**

## Issues

### Issue 1 -- Severity: suggestion
- File: oskh_factors/chip/core.py
- Description: Numba in-place `*=` / `+=` vs NumPy `cumpdf * diff + curpdf` can differ by ~1 ULP; normalize uses NumPy `.sum()` to stay close. Parity tests use 1e-15 atol/rtol (bit-close for chip mass, not `memcmp`).
- Suggestion: Accept ULP-tight bar; do not bake ms thresholds into CI.
- Status: open (accepted)

### Issue 2 -- Severity: suggestion
- File: scripts/research/bench_minute_chip_hotpath.py
- Description: Speedup ~58× is single-machine box evidence under vanna312; bin counts stay modest on synth random-walk.
- Suggestion: Keep as research evidence; real high-vol names may change absolute ms but not the python≫numba order.
- Status: open (accepted)

### Issue 3 -- Severity: nit
- File: oskh_factors/chip/core.py
- Description: Empty / flat-price path still logs via shared `_minute_chip_empty_series`; both backends agree on empty Series.
- Suggestion: None required for D2.
- Status: open (accepted)

### Issue 4 -- Severity: nit
- File: docs (plan / README)
- Description: Run snippets use portable `python scripts/...` with vanna312 tip (H14 hygiene); no absolute `/workspace/...` baked into plans.
- Suggestion: Keep that hygiene on future Hx docs.
- Status: open (accepted)

## Checklist vs plan

| Plan item | Result |
|-----------|--------|
| Plan `plan-h15-d2-minute-chip-numba-2026-09-15.md` | Done |
| Optional numba path + Python default / env-kwarg gate | Done |
| Parity tests (skip if no numba) | Done (5 passed) |
| Bench python vs numba | Done (~58×) |
| Backlog H15 ✓ + next-heavy D2 ✓ → C soft+ | Done |
| Inventory / README / chip README | Done |
| Grok review + fix valid 🔴 | Done (none valid) |
| Sell-semantics / CYQ feeder / Rust / CloudAgent | Not done |
| Push + PR → master | In delivery |
| Remaining valid 🔴 | None |
