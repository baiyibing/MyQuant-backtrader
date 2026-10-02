# Frozen master-close anchor for #208 P1

Generated **before engine edits**, from master
`82abaaba2752f34e05b3f5b81d2099f00c17ba52`, using
`tests/test_topk_minute_exec.py`'s `close_case` / `write_close_products` helpers.
Do not regenerate these products to accommodate implementation changes.

`manifest.json` records SHA-256 hashes and the available interpreter/dependency
versions (Python 3.12.13, pandas 2.3.3, NumPy 2.3.5). This host's environment
differs from the repository's pandas 3.0.6 requirement; no dependency pin changed.

Each fixture has two trading days, a fixed 10.0 daily reference/mark, 100,000
initial cash and daily quota, TopK=1, n_drop=1, no stop, and default fees.
A outranks B on day one; B outranks A on day two, exercising the existing
dropout sell and cash loop as well as the buy quote.

- `exact`: 14:55 **close 10.4**, distinct from its open and morning prices.
- `fallback`: no 14:55; last close in 14:30–14:55 is **14:52 close 10.3**.
- `empty`: only 09:30, 14:29 and 14:56 on entry day; **no entry**.

Tests compare all bytes of `trades.csv`, `daily_equity.csv`, `summary.txt`
(including the existing HELP_LOCK), and `stats.json` for both omitted and
explicit `topk_exec="close"`. No fields or assertions are dropped for parity.

These are synthetic anchors, not 2025 stag15 products. That full run's
input/dependency registration and product-hash re-registration remain a host
follow-up; no NAV claim is inferred from these fixtures.
