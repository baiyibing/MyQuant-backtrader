# Joint-return research replay: two explicit input paths

Synthetic green ≠ real return. The original synthetic path and its 10/3,
P-BASE/P-CHASE, M-REF/M-LAG semantics stay unchanged. Its contract pin remains
`dfa020d2c01e6cfe6612f09be2d569294ff94d82fd1ede5cea61a41d74a81737`.

Frozen control-only 50/5 packs use the separate pin
`9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41`.
Manifest and metadata must match that pin; explicit price metadata must also
carry it. BT checks artifact bytes/content, intent identities, reference chains
and plan bindings without changing quantities or reference prices. CSV accepts
one additional JSON quoting layer, then verifies decoded content hashes.
`--intents` accepts intents.csv, its directory, or adjacent manifest.json.
The adjacent constraints.csv and pref_check.json remain mandatory.

This minimal adapter implements **`--bars` only**, not a Qlib reader.
Frozen prices use the existing minute JSON schema in the module docstring,
with `kind=frozen_explicit`, `metadata.contract_hash` set to the frozen pin,
nonempty `metadata.source` provenance and `content_sha256` equal to SHA256 of
canonical JSON excluding that field (UTF-8, sorted keys, compact separators).
Include explicit raw open/close, price limits, suspension, executable capacity,
session endpoints, initial lot marks/acquisition evidence and complete corporate
actions. Hashes bind the supplied evidence; they do not certify source truth.
No source URI is dereferenced. There is no lake search or bar fabrication.

Frozen replay permits **P-BASE / M-LAG only**. M-REF is INPUT_BLOCKED: the host
sessions.json contains market-wide reference_price=1.0 placeholders and cannot
supply market reference prices. P-CHASE, weak and Mode B stay INPUT_BLOCKED.
Missing explicit prices or any missing symbol/minute in the declared calendar
for the intent/initial universe fails closed; the coverage error reports
expected, observed and missing symbol-minute counts. This conservative coverage
rule also requires explicit suspension evidence and may block a sparse host
export. Do not fill those gaps with fabricated bars.

4090 Windows cmd recipe (the price JSON must first be supplied on that host):

```bat
set "HANDOFF=D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922"
set "PRICES=D:\path\to\verified-frozen-explicit-bars.json"
"%OSKH_MERGE_PYTHON%" scripts\research\run_joint_return_replay.py ^
  --intents "%HANDOFF%\portfolio_joint-return-control-only-50-5\intents.csv" ^
  --bars "%PRICES%" --arm P-BASE --fill-mode M-LAG ^
  --out backtest_output\joint-return-v1\joint-return-control-only-50-5
```

Use the configured interpreter (or the explicit vanna312 interpreter).
The pack has about 2470 intents, window 2025-01-02..2025-12-31,
price_domain=none and valuation=research-none-mark-v1. These host facts do not
replace validation. The authorized host source is `QLIB_1MIN_ROOT`, for example
`C:\Users\wangc\.qlib\qlib_data\my_data_1min`; preparing a verified JSON export
from it is a remaining host task. This CLI does not read that environment variable.
No explicit price → INPUT_BLOCKED. Real 4090 files are not needed by CI.

Outputs retain orders.csv, fills.csv, daily_nav.csv and summary.json under the
specified run directory; an existing directory is never overwritten. Frozen
success is BT_RESEARCH_REPLAY_PASS / RESEARCH_RUN, preserves MQ's INPUT_BLOCKED
provenance status, and leaves real_execution_status=INPUT_BLOCKED and
return_status=待实测. The fixture tests prove adapter behavior, not real returns,
raw-source verification, PIT, full trading costs or corporate-action economics.
Production_C and all production paths remain frozen. Do not merge without
bt/human review: CI green first, then bt merges.
