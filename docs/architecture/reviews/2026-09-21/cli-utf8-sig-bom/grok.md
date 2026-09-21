# Grok review — fix/refresh-tr-store-cli-utf8-csv

**Verdict: PASS** (no blocking 🔴)

## Scope check
- Research-only bridge CLI fallback fix after #146 / #147.
- Touches: `oskh_factors/bridge/turnover_resist.py` `_cli_compute` + `tests/test_turnover_resist_bridge.py` + this review.
- Does **not** modify production fill / scan / fee / defaults / hot-path.
- Does **not** write `stock_pool/`.

## Root cause
- Rust `turnover-resist.exe` writes UTF-8 **BOM** CSV via `--output`.
- Bridge opened with `encoding="utf-8"` → DictReader fieldnames `'\ufeffstock_code'` → `normalize_ffi_row` raises `FFI row missing stock_code`.

## Fix
- Open CSV with `encoding="utf-8-sig"` (+ strip residual BOM keys).
- Force `encoding="utf-8", errors="replace"` on `subprocess.run` pipes (Windows gbk LocaleDecode risk).
- Prefer existing `--output` CSV parse path (already primary); no stdout-JSON change needed.

## Tests
- `TestCliBomCsv.test_cli_compute_reads_utf8_bom_stock_code` — BOM fixture → `stock_code` present.
- `tests/test_turnover_resist_bridge.py`: 6 passed, 1 skipped (win32 exe).
