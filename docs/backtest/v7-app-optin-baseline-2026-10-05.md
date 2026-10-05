# V7 / APP frozen opt-in baselines (2026-10-05)

Step 1 only: freeze standalone execution before the minute-engine migration.
Production code and all older fixtures remain untouched. The fixture is
`tests/fixtures/v7_app_optin_baseline_20261005.json`; migration PRs must never
regenerate, replace, or move it. A result change requires separate Human approval.

The separate `scripts/research/generate_v7_app_baseline.py --record` generator
refuses an existing fixture, including exclusive creation at write time. It uses
only synthetic frames and temporary CSV inputs. No lake or network data is read.
Host/APP market-data loaders are substituted in scoped contexts; their real pool
loaders, APP ranking/intersection, simulators and artifact writers execute.

| Cases | Exercised contract |
| --- | --- |
| default, chronological | Symbol-major versus X02 clocks; multiple symbols; +4/+8/+12/+16 adds; all five stage stops; first-row gap stop; ten-session timer; limit-up rejection, silent limit-down trial rejection, sell deferral at limit-down; partial T+1 sell with locked adds; cleared_today; missing quotes and persistent marks |
| short_cash | Fee-inclusive insufficient cash skips |
| tail_default, tail_none, tail_shares, tail_lots | X04 under X02; omitted/None/shares/lots accepted units; actual 14:30 child fills and staged adds; lots explicitly converted |
| participation | Completed raw-share BucketVolume lookup; buy/sell cap consumption, partial quantities and unavailable opening buckets |
| exdiv, economics | Explicit price rescaling; separate cash-dividend entitlement, receivable NAV and subsequent settlement |
| index_gate, frame_calendar | Mapping with eleven-session warmup and actual blocked trial; observed frame calendar without index_days |
| names, names_by_day | Static and dated ST names affecting ladder limits (synthetic June 2026, before the July ST-band switch) |
| audit | Deterministic execution audit rows, fees/cash and phase ordering |
| host_version7 | Real host run_version7, real temp pool loading and captured actual simulator result; host summary plus production writer artifacts |
| sell_fill_only | Limit-down opening rejection followed by legal close-price sell despite that later row's limit-down open |
| app_pred_minus_one, app_identity | Real standalone CLI, default 500m cash/default TopK, prediction CSV ranking and APP intersection/order; shifted versus identity membership differs; real APP summary header and v7 writers |

Each case freezes SHA256 of raw `trades.csv`, `daily_equity.csv` and `summary.txt`;
audit also freezes `audit.json`. CSV headers and row/column order are part of the
contract. Canonical CSV values use the existing off-byte Decimal 1e-8 half-even
normalization, preserving empty optional cells and text. JSON floats are similarly
normalized; summaries remain exact text. Reasons, ending cash/positions and APP
pool membership are also recorded. Generator assertions require real buys/sells
and specific path evidence rather than merely recording empty output.

Check with the configured interpreter (`OSKH_MERGE_PYTHON`, following AGENTS):

```sh
"$OSKH_MERGE_PYTHON" -m pytest -q tests/test_v7_app_optin_baseline.py
"$OSKH_MERGE_PYTHON" -m pytest -q -m "not production and not benchmark"
```

Canonical and account evidence comparisons always run first. Raw hashes compare
when runtime pandas major.minor matches the fixture (recorded with pandas 3.0.6).
A different pandas version skips only the final raw-byte phase, with its reason.
The targeted suite has 19 case tests plus one overwrite-refusal test, takes about
3 seconds, and carries no production/benchmark mark.

Validation in the local pandas 3.0.6 environment: targeted tests passed twice
(20 passed, 2.36s / 2.45s); ruff passed. Full unmarked suite: 7,857 passed,
5 skipped, 24 deselected, 2 failed in 179.25s. Both failures are existing registry
expectations for version6_42–44 (`test_registered_books_are_explicit` and
`test_off_byte_baseline_covers_current_registry_and_standalone_v7`); both reproduce
in a temporary archive of unchanged HEAD (2 failed in 1.30s). Resolving that
registry discrepancy is outside this baseline-only change.
