# L2 one-day DuckDB / Polars comparison

Opt-in research switch for Human t1119u on newtest_4090. Phase3 defaults stay
DuckDB. No hotcut or lake migration is part of this change.

Using your configured interpreter (`OSKH_MERGE_PYTHON`, or the repo interpreter),
install core requirements and `-m pip install -r requirements-l2-polars.txt`.
Polars is optional locally; CI installs it. Missing Polars skips its tests and
raises an actionable import error when selected, before output work.

Set `OSKH_L2_ETL_ENGINE=polars` for the existing one-day CLI or inherited
Phase3 `run_etl` subprocess environment. Unset means `duckdb`; all other values
fail before scanning/creating output. Python callers can pass `engine=` explicitly.
Do not set this globally on live Phase3. Selection changes chunk conversion and
compaction only; gap-free validation still uses the shared DuckDB positional reader.
Manifest, hive paths, idempotent skip, row checks and readiness ownership stay shared.
Engine is recorded in result JSON and nonempty execution profiles.

Run a compare with a **new scratch directory**, outside the source and live lake:

```powershell
& $env:OSKH_MERGE_PYTHON scripts/misc/compare_l2_etl_engines.py --source <CSV-YYYY-MM-DD> --out-root <NEW-SCRATCH-DIR> --threads 4 --chunk-files 400
```

The script runs fresh subprocesses, DuckDB then Polars, writes separate engine
outdirs, logs and result JSON, and prints wall/chunk/main-merge/order-merge times.
It refuses an existing scratch root. Keep both engine JSON files as evidence.
Wall includes process startup; profile fields preserve #517 phase definitions.
The current DuckDB default merge is actually PyArrow ordered batch concat;
Polars uses an ordered lazy concat and streaming Parquet sink. There is no
measured speedup claim here: run representative heavy 2022 days on newtest_4090.
Sequential order warms the filesystem cache; repeat with reversed engine order
using separate CLI processes/outdirs before drawing performance conclusions.

CSV strategy: skip the exchange header, read 11 positional string fields with
UTF-8 lossy decoding, and truncate extra watermark fields. GBK watermark/header
bytes may become replacement characters but are discarded; ASCII B/S, IDs,
prices, volume and time are preserved. Malformed numeric fields still fail;
positive out-of-range Price becomes NULL with its row retained. Output columns,
SQL types, decimal precision/scale, UTC timestamps, microsecond trade time and
row order match the default. Arrow string offset widths/nullability metadata
can differ between writers; downstream SQL logical schemas are tested.

Risks: CSV conversion materializes one chunk in memory; `memory_limit` is a
DuckDB setting and **does not cap Polars memory**. Lower `--chunk-files` if needed.
Polars threads are process-wide: `--threads` configures `POLARS_MAX_THREADS`
before import; a different thread count after initialization fails explicitly.
The compare uses fresh processes and the same requested threads for each engine.
RSS metrics remain sampled phase observations, not a continuous high-water mark.
No live lake was used in local validation.

## Human t1120u mixed fleet amendment

For play runs after Human GO, set `OSKH_L2_ETL_WORKERS=3` and
`OSKH_L2_ETL_POLARS_WORKERS=1` with engine unset/default DuckDB. The first
worker slot uses Polars and the next two DuckDB; scheduling determines which
slot takes each day. Every child receives an explicit engine environment.
`OSKH_L2_ETL_POLARS_WORKERS` defaults to 0 and must be an integer between 0
and total workers, validated before pipeline work. `OSKH_L2_ETL_ENGINE=polars`
selects Polars for all slots (the worker-count knob must still be valid).
Queue capacities remain 1/1/N/1; live total-worker default remains 2.
Completed-day progress JSON includes the selected engine and existing profile.
Resumed ready days retain the engine recorded by their original execution.
