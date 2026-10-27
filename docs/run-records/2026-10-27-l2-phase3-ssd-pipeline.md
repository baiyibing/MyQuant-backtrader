# Phase3 SSD parquet pipeline — speed knife t1039u–t1042u

Implementation only; no deployment, live PID 20908 stop, or hotcut. Based on
`e8a3878` (last locally available origin/master); remote freshness could not be
verified in the development sandbox. The earlier Phase3 run record describes the
previous live implementation, not this change.

## Stages and readiness

One worker per stage, with capacity-one queues between stages:

1. Discover archives once; copy the day's RAR/7z to SSD archive scratch through
   a `.copying` file and size check, then rename it ready.
2. Extract that archive into the day's SSD CSV directory. Successful extraction
   plus at least one CSV commits `_extract_ready`. Remove the scratch archive.
3. Run the existing one-day ETL with its output root on SSD. Chunk parquet,
   compaction and DuckDB temp files consequently stay on SSD too. Persist the
   successful day's manifest record and timings/profile in `_ready.json`.
4. Copy the two final parquet files into lake `.publishing-YYYY-MM-DD`, check
   sizes, then rename the directory to `date=YYYY-MM-DD` on the lake volume.
   Atomically replace the lake manifest last. Delete CSV and staged parquet only
   after publish succeeds. A small `_pipeline_ready.json` in the lake directory
   identifies this publisher's pair when recovering an interrupted manifest commit.

Each stage consumes individual ready days; there is no batch readiness barrier.
RAR N+1 / extract N / ETL N-1 / publish N-2 can overlap. Queues apply backpressure
when downstream is slower; there is only one ETL and one publisher. Bounded day
counts are not a byte quota: reserve space for several CSV and parquet days.

## Environment and Windows paths

| Variable | Meaning / host default |
|---|---|
| `OSKH_STOCK_RAR_SRC` | Existing archive source, `J:\stock_data` |
| `OSKH_STOCK_CSV_DST` | CSV SSD scratch, now defaults to `E:\l2_csv_scratch` |
| `OSKH_L2_PARQUET_ROOT` | Final lake, unchanged `J:\l2_lake\l2_parquet` |
| `OSKH_L2_PARQUET_STAGING_ROOT` | New optional SSD staging; defaults to `l2_parquet_staging` beside CSV scratch |
| `OSKH_L2_AGENT_TOOLS` | Existing dates/skip/progress/PID directory |

Archive scratch is `l2_archive_scratch` beside CSV scratch. Keep all scratch and
lake trees distinct and non-nested. The SSD location follows configuration;
software does not infer the physical disk type. Only the ETL child's environment
maps `OSKH_L2_PARQUET_ROOT` to staging; the orchestrator retains the final lake.
Python still follows `resolve_oskh_python()`.

For a future isolated Windows trial, explicitly set CSV, staging, lake and
agent-tools to trial directories, with a short dates list and existing source.
Do not launch against live lake/progress while the old pipeline is running.
The new process lock prevents two instances sharing this staging root; it does
not coordinate with the older live implementation or unrelated lake writers.

## Resume and failures

- Completion requires both nonempty lake files and a lake manifest entry. Old
  progress `ok` records alone never suppress missing output.
- A ready SSD day can publish without the source archive or CSV. A ready CSV day
  resumes at ETL. Partial extraction without its readiness marker is removed and
  re-extracted; `--force` alone would otherwise overlay leftover files.
- A partial hidden lake copy is discarded and recopied. A crash after directory
  rename but before manifest commit retries the saved manifest, checking pair
  ownership and sizes. An existing incomplete or unowned lake directory fails
  closed for inspection; it is never overwritten.
- Manifest records retain relative parquet paths and existing row/fingerprint
  fields. One publisher preserves other dates and replaces this date's entry.
- As before, three consecutive observed failures stop admission. Workers drain
  queues and exit; failed artifacts remain for retry. Progress writes serialize
  across workers. A failed day is not sent downstream.
- `archive_s`, `extract_s`, `etl_s`, `publish_s`, `csv_delete_s` and ETL `profile`
  are retained in success JSONL. `prefetch_wait_s` was unused (always 0) and is removed by the
  observability follow-up because the old join no longer exists. Stage starts are logged to stdout. CSV deletion runs in publish.
- Abrupt exit after a successful manifest commit can leave scratch artifacts;
  the already committed day is skipped on restart. These may be removed during
  a later maintenance window after checking the lake manifest and pair.

## Expected speed and validation

Human baseline: about 11.3 days/hour, ETL about 300 s/day writing directly to HDD,
extract about 37 s/day after moving CSV to NVMe. This change removes HDD chunk
writes and compaction from ETL and publishes only the final pair sequentially.
The approximate steady-state interval is the slowest stage, subject to shared
SSD bandwidth and combined archive-read/final-write HDD bandwidth. A 240 s
bottleneck would mean 15 days/hour (+33%); 180 s would mean 20 (+77%). These are
conditional targets, not measurements or a promised speedup. Archive copy adds
traffic; compare `archive_s` and `publish_s` as well as ETL profile on 4090.

Data-free checks (explicit Linux interpreter for this sandbox):

```sh
OSKH_MERGE_PYTHON=/usr/bin/python3 /usr/bin/python3 -m unittest discover -s tests -p test_l2_phase3_pipeline.py -v
```

Tests cover overlapping extract/ETL/publish, ETL output routing and profile,
copy interruption, manifest interruption after rename, repeat publish,
incomplete lake preservation and staged-day resume without CSV/archive.
No Windows/7-Zip/real DuckDB lake benchmark was run here. Claude review follows
this PR separately.

## Human t1083u observability follow-up (not deployed)

Progress Markdown and OK stdout expose archive/extract/ETL/publish/CSV-delete
seconds, with the same precision as JSONL (extract/ETL: 1 decimal; others: 3).
Before using this schema, ops must rotate an existing progress Markdown file:
old eight-column headers/rows are historical and must not receive new eleven-column
rows. JSONL needs no rotation. No live progress file was changed here.
Failure JSONL and Markdown retain only timing keys already present on the job;
missing stages stay absent/blank, including archive/publish calls that raise before
returning a timing. No new elapsed-time measurement or synthetic failure zeros.
Success retains ETL profile and the five stage timings; prefetch_wait_s is removed.
No queue, locking, publish, RO retry, or environment-default semantics changed.
No hotcut, production/PID/lake access, or deployment performed.
