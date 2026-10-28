# Phase3 bounded dual ETL (2026-10-28)

Based on master `961e03f` (#519). Code change only; no restart or hotcut of
newtest_4090 live PID 43980. Grok review skipped per Human; Claude review is deferred.

`OSKH_L2_ETL_WORKERS` accepts a positive integer, defaults to **2**; set **1**
for serial ETL on the next launch. Invalid values fail before pipeline work.
Archive, extract and lake publish each retain one worker. Queue capacities are
1 / 1 / N / 1 (input / archive→extract / extract→ETL / ETL→publish).
The last ETL worker forwards publisher termination only after all ETL jobs drain.
Publication may complete out of date order; the lake manifest remains single writer.

Each ETL subprocess writes to `<staging>/_etl/<day>/`, including its own manifest,
manifest temporary file and DuckDB spill directory. Its normal `date=<day>` child
holds parquet and `_ready.json`. This prevents shared manifest replacement races
and spill contention between subprocesses. Existing committed
`<staging>/date=<day>/_ready.json` stages remain resumable. Successful publication
cleans only that day's staging and CSV; interrupted or failed stages remain retryable.
The lake publish copy/verify/rename/manifest commit and three consecutive failures
stop rule remain in place. Existing #517 stage timing fields and parsed profiles
continue into progress JSONL / Markdown as before; stdout records pool size.

Human's #517 2022-day sample: ETL ~191s (chunk sum ~81s, DuckDB merge ~87s),
extract ~45s and lake publish ~24s, CPU load ~13%. Dual ETL targets **1.5–1.8×**
throughput on ETL-bound stretches; this is an expectation, not a measured result.
No host benchmark or runtime configuration change is included. Compare subsequent
progress records for days/hour, ETL/merge inflation and publish lag before tuning.

Risks: each ETL retains its existing 18GB DuckDB memory limit and automatic thread
count, so two processes can increase aggregate memory, CPU and SSD pressure.
Bounded queues cap queued days, not bytes; heavy days still need adequate SSD space.
Use N=1 on a future launch if contention outweighs overlap. No extra thread/chunk
knobs or machine path changes are introduced.

Validation covers parallel ETL with reversed completion order, publisher drain,
queue capacities, worker configuration, per-day output paths, profile retention,
legacy staging resume, interrupted/idempotent publication and failure-stop draining.
