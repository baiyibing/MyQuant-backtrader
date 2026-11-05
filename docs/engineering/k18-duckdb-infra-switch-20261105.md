# Knife R2-18 / DuckDB host switch — MyQuant-backtrader (2026-11-05 Asia/Shanghai)

## Pin
```
myquant-infra @ git+https://github.com/baiyibing/MyQuant-infra.git@d32a68a2364a87e8d1b98d9c2b64a9bad7070130
```
- Infra library: MyQuant-infra **#55 MERGED** (lake readers) + **#56 OPEN** head `d32a68a2364a87e8d1b98d9c2b64a9bad7070130` (DuckDB maint + retired minute rebuild), rebased onto main.
- After hotmail merges #56, re-pin this host to the new `origin/main` tip SHA.

## What moved
- Lake reader / cache / ETF local bars / DuckDB daily-bars adapter IO → `myquant_infra.lake.*`
- Front DuckDB rebuild → `myquant_infra.bars.duckdb_build.rebuild_front_duckdb`
- Minute DuckDB rebuild → `rebuild_minute_duckdb(..., i_know_this_is_retired=True)` (retired; default refuses)
- Host keeps `_enforce_adjust_type_policy` / entry gates (S22 / #1290 or #563)

## Stays in host
Trading gates, 订单 outbox, strategy, orders, broker shim, decision-price sentinel, S20–S26, chip/adj_factor (S26).

## Rollback
1. Revert this host PR (or `git revert <sha>`).
2. `pip uninstall myquant-infra` (or re-pin previous SHA if any).
3. Do **not** reintroduce `duckdb.connect` into `oskh_data/reader.py` / rebuild_* without a new infra gap ticket.

## Known gap (RESULT_BLOCKER note)
Infra pin rebuilds **daily front** + **retired minute** only. Host requests for daily `none`/`back`/index artifact rebuilds must fail closed (no local SQL). Track follow-up infra builder if needed; not unblocked by re-adding host DuckDB management.

## Allowlist gate
`scripts/gates/verify_no_host_duckdb_connect_outside_allowlist.py` — lake-management scripts must stay at zero `duckdb.connect`.
