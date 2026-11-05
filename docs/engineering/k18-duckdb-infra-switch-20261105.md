# Knife R2-18: BT DuckDB/lake call-site switch (2026-11-05)

Human GO: MyQuant-backtrader consumes MyQuant-infra for lake reader, DuckDB IO,
versioned cache and daily adapter behavior. BT retains its adjustment policy and
configuration composition. The BT reader/proxy API accepts **stock | etf only**;
infra's index support is not admitted here.

Branch: `feat/k18-duckdb-infra-switch-20261105`, based on
`385d213d9f8d410571b9990f4e776c38204825cf` (`origin/master` at implementation).
Local commit only; no merge, push or PR. No production lake rebuild was run.

## Dependency pin

Infra PR #56, rebased on main after #55 merged:
`d32a68a2364a87e8d1b98d9c2b64a9bad7070130`.
The same immutable VCS requirement is in `requirements.txt`.

```sh
/workspace/vanna312/bin/python -m pip install -q "myquant-infra @ git+https://github.com/baiyibing/MyQuant-infra.git@d32a68a2364a87e8d1b98d9c2b64a9bad7070130"
```

Installed `direct_url.json` was checked against that exact commit. This work
uses `/workspace/vanna312/bin/python` throughout.

## Ownership and compatibility

- `oskh_data/reader.py` subclasses `myquant_infra.lake.readers.StockDataReader`.
  Local `read_stock` / `scan_stocks` enforce `_enforce_adjust_type_policy` before
  forwarding to infra, including before minute adjustment coercion. The #563
  entrance matrix remains intact; its spies now sit at the infra boundary.
  Caller discovery skips infra forwarding frames so restricted business callers
  remain visible. `as_of_date` remains fail-closed.
- BT's root/mode resolvers, per-period overrides, explicit-base semantics and
  ETF isolation stay in the facade. Parquet and daily DB roots remain separate.
  ETF minutes use the ETF minute tree instead of a daily-tree fallback.
  Freshness validation and the freshness session/calendar module remain local.
- `oskh_data/cache_port.py` supplies its lazy Redis client to
  `myquant_infra.lake.cache`; infra owns keys, pointers, codecs and TTL writes.
  The #563 adjustment gate runs before any Redis/pointer/cache access. The
  existing `oskh_data:*` wire namespace is unchanged; Redis failures remain soft.
- `oskh_data/etf_local_bars.py` retains reader reuse and locks, and supplies the
  local gated reader factory to `myquant_infra.lake.etf_bars` for reading/shaping.
- `common/integrations/duckdb_daily_bars_adapter.py` supplies the local gated
  reader factory, layered configuration and BT previous-trading-day provider to
  `myquant_infra.lake.duckdb_daily_bars.DuckDBDailyBarsProxy`. Infra owns date
  validation, routing, shaping and ordinary storage failure fallback. Policy
  rejection still propagates without delegate fallback.
- `scripts/tr/rebuild_front_duckdb_standalone.py` calls infra's explicit
  `bars.duckdb_build.rebuild_front_duckdb` with resolver-provided paths. Import
  does not resolve roots or touch artifacts. The reader's build facade calls
  that same infra builder. No local SQL, connection, staging or publication code
  remains in either entrance.
- The remaining front-management DuckDB scan in `daily_parquet_write._path_b_batch`
  now calls the gated infra-backed reader. Symbol selection, day bounds, null
  close filtering, normalized output time and the existing PyArrow merge policy
  remain local. Chip/adj_factor S26, economics, orders and strategy rules are
  outside this switch.

At this pin, the active rebuild supports daily stock/ETF **front** only. Existing
none/back daily artifacts remain readable. `1m`, `all`, none/back builds and
unsupported asset types fail before root resolution or IO. Persistent minute
rebuilds stay retired. Infra validates canonical schemas and atomically replaces
the output, retaining the old DB on failure. It creates no legacy `.bak.*` files;
the legacy default `max_backups=2` argument is accepted for call compatibility,
and nondefault retention requests fail explicitly. Operators needing historical
artifact retention must snapshot the DB before an explicit rebuild.

## Connection allowlist

`scripts/gates/verify_no_host_duckdb_connect_outside_allowlist.py` runs in CI
before dependency installation. It scans tracked and nonignored new Python files
using AST, including aliased imports/connectors and simple assignment aliases.
Strings/comments/mock patch targets do not open connections. Every exception is
an exact file with a fixed call-site count; new calls and stale entries fail.
No reader, rebuild or front/minute lake-management file is allowlisted.

| Exact file | Calls | Remaining purpose |
| --- | ---: | --- |
| `l2_analytics/db.py` | 1 | Offline L2 query views |
| `l2_analytics/etl_day.py` | 4 | Offline L2 ETL/aggregation |
| `scripts/run/run_l2_merge_work_chunks.py` | 2 | Offline L2 work-chunk merge |
| `scripts/run/run_l2_migrate_hive_compact.py` | 2 | Offline L2 compaction |
| `scripts/gates/verify_l2_manifest.py` | 1 | Offline L2 manifest validation |
| `scripts/tr/backfill_turnover_resistance_bands.py` | 1 | TR/Store research date enumeration |
| `scripts/data/full_market_canonical_resist.py` | 1 | TR research capital-map query |
| `scripts/research/full_market_canonical_resist.py` | 1 | TR research capital-map query |
| `scripts/gates/verify_single_stock_turnover_resist.py` | 1 | TR audit capital-map query |
| `scripts/research/verify_single_stock_turnover_resist.py` | 1 | TR audit capital-map query |
| `tests/test_l2_templates.py` | 2 | Synthetic L2 query fixtures |
| `tests/test_l2_etl.py` | 3 | Synthetic L2 ETL fixtures |
| `tests/test_oskh_data_integration.py` | 1 | Synthetic legacy daily DB fixture |

Total: **21 calls in 13 files**. The TR entries query analytical inputs or
trading dates; they do not create/manage front or minute DuckDB artifacts. These
exceptions do not authorize vendor downloads, live packages or new lake writes.
No broad directory/test/mock exception is granted.

## Validation

Run the #563 entrances and switch checks with vanna312:

```sh
/workspace/vanna312/bin/python -m pytest -q tests/test_oskh_data_adjust_type_entry_gate.py tests/test_oskh_data_adjust_type_policy.py tests/test_oskh_data_infra_switch.py tests/test_verify_no_host_duckdb_connect.py tests/test_hive_lake_kind_and_roots.py tests/test_data_path_ssot_write_symmetry.py tests/test_oskh_data_freshness_session_policy.py
/workspace/vanna312/bin/python scripts/gates/verify_no_host_duckdb_connect_outside_allowlist.py
```

Synthetic tests exercise real temporary Parquet and DuckDB for stock/ETF daily
and minute reads, every mode, root overrides, missing roots/artifacts,
as-of/index rejection, retired rebuild rejection, Redis roundtrip/TTL/pointer
rotation, real restricted-module caller discovery across forwarding frames,
standalone path injection and path-B filtering/merge behavior. No market lake,
QMT, network Redis or production artifact is required.

Final counts and gate results are recorded below after validation.

## Rollback

1. Revert the local commit titled
   `feat(oskh_data): switch DuckDB lake IO to myquant-infra (Knife R2-18 switch)`
   with `git revert <switch-commit>`. This restores the pre-switch host reader,
   cache, adapter, rebuild, requirements and CI gate together. The pre-switch
   reference is `385d213d9f8d410571b9990f4e776c38204825cf`; do not reset away
   unrelated work.
2. Reinstall the reverted requirements using vanna312:
   `/workspace/vanna312/bin/python -m pip install -r requirements.txt`.
   The installed infra package may remain unused; uninstall it only in an
   isolated BT environment where no sibling consumers depend on it.
3. Rerun the adjustment entrance/policy, freshness/session and path-SSOT gates.
   Mode/environment changes alone do not undo the switch: every reader mode
   delegates to infra. Restore a separately retained pre-rebuild DB snapshot
   only if an operator actually rebuilt a production artifact and needs an
   artifact rollback. This implementation changed no production artifacts.
