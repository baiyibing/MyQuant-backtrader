# RB-05 registry module split

Base tip: `b1c1080`. This is a ZERO-DIFF mechanical split for H-RB-01 / RB-05.

The 94 `_apply_version6_<n>` and `_run_kwargs_version6_<n>` helpers
(n = 1..47) moved verbatim to `csv_strategy_books_v6_family.py`, with their
rule-module and typing imports. The registry explicitly imports each helper,
preserving imports from `csv_strategy_books`.

Bare version6, all other family helpers, the public API, HELP_LOCK strings,
capability frozensets, and every registration remain in `csv_strategy_books.py`.
All registration calls retain their exact relative order from tip, including
version7's minute-only registration; the sibling module registers nothing.
Fixtures, baselines, and simulation engines are unchanged. Validation uses
focused data-free tests and checks helper source and registry identity.
