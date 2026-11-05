# B3: L2 ingest / Phase3 / hive compact infra switch (2026-11-05)

The existing BT entry points now delegate offline L2 ingestion, persisted
aggregates and maintenance to MyQuant-infra. This branch started on D4
`e28e9e5f595cc6a78908f40e776bc0fe9711898f` (#566, still open at initial fetch).
B2 #567 is merged into master as `209100eb47fceb059d5147b24229d5ae658e95a4`;
B3 does not repeat B2. During validation hotmail merged D4 as
`4d33b40da517b2a897b29e2af04d1314912067ab` (short id `4d33b40`); B3 is
rebased onto that merged campaign tip. The draft PR targets master and contains
only B3. Only hotmail merges; this work does not merge any PR.

## Immutable optional pin

`requirements-infra.txt` retains the fetchable main SHA
`7d48c4e310f9636cad9c3e544db1766025db4e3c`. It contains
`myquant_infra.l2.ingest`, `myquant_infra.l2.aggregates` and
`myquant_infra.l2.maintenance`. Infra #59/#60 were open at initial fetch; no
unmerged branch or speculative SHA is pinned. Default `requirements.txt` and
the public CI installation remain unchanged.

Install the optional package using the configured Python interpreter:

```powershell
& D:\anaconda3\envs\vanna312\python.exe -m pip install -r requirements-infra.txt
# Only for the optional Polars backend:
& D:\anaconda3\envs\vanna312\python.exe -m pip install -r requirements-l2-polars.txt
```

Imports and CLI `--help` remain available without the private package. An actual
L2 operation then fails with the pin-install instruction before output creation.
Missing transitive dependencies retain their original errors. There is no local
fallback implementation or fake successful IO. Public CI runs fake boundary
tests; integration cases explicitly skip when the optional package is absent.

## Ownership

| Host entrance | Infra implementation | Host responsibility |
| --- | --- | --- |
| `l2_analytics/etl_day.py` | `l2.ingest.etl`, `l2.ingest.publish` | Existing signature, engine env, root resolver, default spill directory; compatibility helpers |
| `l2_analytics/etl_polars.py` | `l2.ingest.polars` | Import compatibility |
| `l2_analytics/paths.py` | `l2.ingest.paths` | Query glob helpers without an infra counterpart remain local |
| `l2_analytics/perf.py` | `l2.ingest.perf` | Import compatibility |
| `l2_analytics/aggregates.py` | `l2.aggregates` | Optional root selection and caller-owned connection forwarding |
| `scripts/misc/extract_stock_rar_data.py` | `l2.ingest.archives.unpack` | Existing flags, source/destination env and 7-Zip default |
| `scripts/misc/l2_phase3_pipeline.py` | `l2.ingest.pipeline.Pipeline` | Environment composition, interpreter selection, date/skip files, host progress/PID/summary filenames |
| `scripts/run/run_l2_merge_work_chunks.py` | `l2.ingest.recovery.recover_day` | Existing recovery CLI flags and default spill directory |
| `scripts/run/run_l2_migrate_hive_compact.py` | `l2.maintenance.migrate_hive_compact` | Existing explicit migration invocation applies; `--dry-run` selects planning |

Recovery is exported by infra's **ingest.recovery**, not maintenance. The host
does not recreate it in maintenance. No host SQL, chunk merger, archive scanner,
publisher or Phase3 worker implementation remains in the switched files.
The connection gate removes their eight retired call sites and now admits
13 calls in 10 exact files. `l2_analytics/db.py`, reference readers, dedup helpers
and research templates stay local for B4. Decision-price and trading paths are
outside B3.

## Phase3 configuration and compatibility

Set `OSKH_STOCK_RAR_SRC` and `OSKH_STOCK_CSV_DST` explicitly. The lake uses the
existing `resolve_l2_parquet_root()` contract: `OSKH_L2_PARQUET_ROOT`, or the
configured parquet container/authority marker. Missing configuration fails;
the former machine-specific source/CSV/lake defaults are removed.

`OSKH_L2_PARQUET_STAGING_ROOT` defaults to the CSV parent's
`l2_parquet_staging`; `OSKH_L2_ARCHIVE_SCRATCH` to its `l2_archive_scratch`.
`OSKH_L2_TEMP_DIRECTORY` defaults to the staging parent's `l2_temp`.
Infra checks source, CSV, staging, archive scratch, temp and lake for overlapping
trees before running. These are operator-supplied offline destinations, never
an implicit production-lake selection.

The existing `OSKH_L2_ETL_ENGINE` (duckdb default), `OSKH_L2_ETL_WORKERS` (2),
and `OSKH_L2_ETL_POLARS_WORKERS` (0) are passed explicitly. New
`OSKH_L2_ETL_THREADS` defaults to 1 per subprocess, matching the infra CLI's
bounded resource setting; tune it explicitly for the host. Infra owns queue
draining, three-failure stopping, lock, resume, publish and manifest verification.
The host entry re-executes through `resolve_oskh_python()` when needed; infra
ETL children use that interpreter with `-m myquant_infra.l2 ingest-day`.

`OSKH_L2_AGENT_TOOLS` retains the progress, date/skip, PID and summary filenames:
`l2_phase3_dates.txt`, `l2_skip_dates.txt`, `l2_batch_progress.md`,
`l2_batch_progress.jsonl`, `l2_phase3_pipeline.pid`, `l2_batch_summary.json`.
When unset it defaults to staging. Infra also writes `staging/summary.json`.
`--dates ...` overrides the date file; `--dry-run` produces a plan without PID,
progress, summary, staging or lake writes. Completion and exit status now include
infra's pending-day and manifest checks, so incomplete batches fail.

Unpack retains nonempty-directory resume and force-overlay semantics; infra
also maintains `_extract_ready`. A dry-run does not require a 7-Zip binary.
Unpack/recovery/migration now emit infra's structured JSON results rather than
the former host-only sample/profile fields. Recovery rejects incomplete or
corrupt source/chunk inventories before publication and retains failed work.
Date helpers reject malformed calendar dates. These checks are inherited from
the pinned implementation and covered by hermetic tests.

## Validation

Use the configured interpreter, no network or production data during tests:

```powershell
& D:\anaconda3\envs\vanna312\python.exe -m pytest -q -p no:cacheprovider tests/test_l2_etl.py tests/test_l2_aggregates.py tests/test_l2_consumer_dedup.py tests/test_l2_perf.py tests/test_l2_templates.py tests/test_l2_phase3_pipeline.py tests/test_l2_infra_switch.py tests/test_verify_no_host_duckdb_connect.py
```

Existing ETL/aggregate/dedup assertions exercise the installed pin over synthetic
CSV and tmp Parquet. Phase3 retains interruption, retry, concurrency, readonly
cleanup and validation-failure evidence checks with real tiny Parquet fixtures.
New tests cover option/root forwarding, default engine, missing configuration,
public imports/help without infra, truthful exit status, migration planning,
302 rebake, canonical order schema, and complete/corrupt work recovery.
Run the existing data-free path, contract, economics and connection gates too.
Final command output and counts are recorded in the requested external RUN.md.
The unchanged parent suite exposed a Redis fake missing the pinned cache API's
`setex`; this PR adds that method only to the test fake. Parent policy/IO
regressions then pass without using a Redis service.

## Rollback

Revert the B3 commit with subject
`feat(l2): thin-wrap L2 ingest/aggregates/maintenance to myquant-infra (B3)`
through an ordinary reviewed PR. Its parent is the merged campaign tip above. This
restores the original host implementations and the three removed connection
allowlist entries together. It does not undo B2 or D4.

The optional dependency pin is unchanged from D4: retain
`7d48c4e310f9636cad9c3e544db1766025db4e3c` for the existing lake readers.
Do not uninstall or downgrade it as an L2 rollback. No data migration, production
execution or lake write is performed by this PR, so code rollback requires no
lake restore. Before a later operator-run Phase3 job, retain its explicit paths
and inspect staged readiness/manifest evidence when resuming across versions.

## Pin bump after infra #60

Current pin: `3c377e9718e811112993579b6d91a603395db699` (merged origin/main after #60). Prior campaign pins superseded. Rollback: revert host wrappers for B3 and restore the prior pin SHA documented above.
