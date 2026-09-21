# Grok review — fix/path-ssot-refresh-tr-store

**Verdict: PASS** (no blocking 🔴)

## Scope check
- Research-only / contract wiring after #146 merged `scripts/data/refresh_tr_store_window.py`.
- Touches: `scripts/gates/verify_data_path_ssot.py` `_ALLOWLIST` only (+ this review doc).
- Does **not** modify production fill / scan / fee / defaults / hot-path Python.
- Does **not** rewrite `refresh_tr_store_window.py` logic.

## Gate alignment
- CI red: `NEW_UNWIRED scripts/data/refresh_tr_store_window.py` (2 hits).
- Hits are docstring/help lake labels (`period=1d`, `turnover_resistance_daily.parquet`), not production path joins.
- Wired as `("RESEARCH_HOST_HELPER", 2)` — same classification intent as sibling research host helpers under `scripts/data/`.
- `tests/test_refresh_tr_store_window.py` is outside `_SCAN_DIRS` (no allowlist needed).

## Local verify
- `python3 scripts/gates/verify_data_path_ssot.py` → exit 0; `OK RESEARCH_HOST_HELPER ... (2/2)`.

## Nits (non-blocking)
- Optional later: route the two label strings through resolvers / AST-docstring skip to shrink allowlist to 0 — out of unblock scope.
