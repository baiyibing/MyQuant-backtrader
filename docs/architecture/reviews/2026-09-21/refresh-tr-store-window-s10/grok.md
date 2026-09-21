# Grok review — research/refresh-tr-store-window-s10-2026-09-21

**Verdict: PASS** (no blocking 🔴)

## Scope check
- Research-only host helper + docs + data-free tests.
- Touches: `scripts/data/refresh_tr_store_window.py`, `docs/backtest/chip/turnover_resistance_tr_bollinger.md`, `tests/test_refresh_tr_store_window.py`.
- Does **not** modify production fill / scan / fee / defaults / hot-path Python.

## API alignment
- Reuses `compute_turnover_resist`, `TurnoverResistanceStore.upsert_daily`, `compute_and_update_bands`, `load_cross_section(..., require_bands=...)`, `list_trading_dates`.
- Fail-closed: exit ≠ 0 when window still has 0 banded days.
- Never writes `stock_pool/`.

## Nits (non-blocking)
- `--workers` is logged only (Rust/FFI path is sequential per day) — documented in help.
- Forward-slash Windows paths in docs (`E:/...`) are intentional (valid on Win Python; avoid docstring `\s` escape warnings).
- For BB quality across the Jun→Aug coverage gap, parent may also refresh missing days before `20260825` (period=20); helper documents this.

## Tests
- `tests/test_refresh_tr_store_window.py`: 4 passed (upsert+bands, fail-closed empty, bands-only, skip-existing-tr).
