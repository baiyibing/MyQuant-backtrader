## Summary

H11 is a **Theme D soft slice**: **chip / TR slow-path inventory only** (not a full Rust rewrite, not algorithm / sell-semantics changes). Delivered (1) plan `docs/backtest/plan-h11-chip-slowpath-inventory-2026-09-15.md`, (2) SSOT `docs/backtest/chip/chip-slowpath-inventory-2026-09-15.md` with four buckets — **Rust SSOT** (`turnover-resist` + `oskh_factors.bridge.turnover_resist` + Store / export_ta_pool / tr_filter), **Python research consumers** (`oskh_factors.chip` / `qlib_cost` / full_market_* / research chip IC·filter·verify), **Cerebro Indicator fossils** (`chip_indicator`, chip/ma_chip backtests, `--allow-cerebro-fossil`; **not deleted**), **hot Python loops** (`cyq.calc_*`, minute/hybrid `for` loops, canonical numba batch as parity) with recommendations **leave / later offload / fossil**. (3) Data-free gate `scripts/gates/verify_tr_bridge_import_ssot.py` + `tests/test_tr_bridge_import_ssot.py` assert `oskh_core.turnover_resist_bridge` still ImportFrom `oskh_factors.bridge.turnover_resist` and known `scripts/tr/*` consumers import `compute_turnover_resist` only from that SSOT or the shim — **no lake**. (4) Pointers in `docs/backtest/README.md` (SSOT table + chip/ row + hygiene backlog H1–H11), `docs/backtest/chip/README.md`, backlog **H10✓ H11✓**; themes **A–F still open**; **no L2 expansion**; **no Cerebro delete**. Local: gate exit 0; pytest 3 passed. No simulate/sell edits. No push / CloudAgent. **No valid 🔴.**

## Issues

### Issue 1 -- Severity: suggestion
- File: docs/backtest/chip/chip-slowpath-inventory-2026-09-15.md
- Description: `scripts/data/full_market_*` and `scripts/research/full_market_*` are listed as parallel research entries; inventory does not pick a single CLI SSOT between the two trees.
- Suggestion: Optional later hygiene: mark one tree canonical and demote the other to shim/re-export. Out of H11 soft scope.
- Status: open (accepted)

### Issue 2 -- Severity: nit
- File: scripts/gates/verify_tr_bridge_import_ssot.py
- Description: Known-consumer list is only the two `scripts/tr/*bands*.py` Importers; `backfill_turnover_resistance_yearly.py` orchestrates via subprocess and is not AST-checked for `compute_turnover_resist`.
- Suggestion: Sufficient for “bridge import path still points at factors”; extend allowlist if yearly gains a direct import later.
- Status: open (accepted)

### Issue 3 -- Severity: nit
- File: tests/test_tr_bridge_import_ssot.py
- Description: Object-identity shim check overlaps `tests/test_turnover_resist_bridge.py::TestOskhCoreShim`; AST gate is the H11-new signal.
- Suggestion: Harmless redundancy; keep both (runtime identity + static ImportFrom).
- Status: open (accepted)

## Checklist vs plan

| Plan item | Result |
|-----------|--------|
| Plan | `docs/backtest/plan-h11-chip-slowpath-inventory-2026-09-15.md` |
| SSOT inventory tables + leave/later offload/fossil | `docs/backtest/chip/chip-slowpath-inventory-2026-09-15.md` |
| Data-free TR bridge import gate + pytest | `verify_tr_bridge_import_ssot.py` + `test_tr_bridge_import_ssot.py` green |
| README chip section + backlog H10✓ H11✓; A–F open; no L2 / no Cerebro delete | Done |
| Sell / algorithm rewrite | Not done (correct) |
| Push / CloudAgent | Not done |
| Valid 🔴 | None |
