# RB-03 baseline admission checklist (ZERO-DIFF)

Append-only admission for a new book or rule revision:

- Register the book through the registry (RB-02 alias/name guards apply).
- Explicitly extend the appropriate `*_BOOK_NAMES` / `*_CASES`, `BOOK_NAMES` / `CASES`, or wire a new scoped overlay. Do not regenerate coverage lists.
- New overlay JSON must carry `rule_revision`, `books`, `cases`, `captured_environment`, `contract`, `historical_raw_sha256`, and `historical_canonical_sha256`; `captured_environment.pandas` must be a string. Assign a new rule revision; never overwrite the historical eff77f3 golden or an existing overlay.
- `generate_off_byte_baseline.py` `--record-*` modes refuse overwrite of existing overlays. A new revision needs a new file and revision id; recording requires separate authorization.
- Canonical checks are always required; byte checks follow the `byte_skip_reason` contract. Requirements pin, CI pandas assertion, and historical/scoped golden pandas metadata currently agree on **3.0.6**. A pandas pin change requires a separate re-anchor ticket.
- Run `scripts/gates/verify_book_admission.py` and `scripts/gates/verify_baseline_admission.py`. Both are data-free; the baseline gate only reads manifests and anchors.

RB-03 changes admission diagnostics only: no simulation defaults, frozen baseline contents, HELP_LOCK, book order, or public signatures change.
