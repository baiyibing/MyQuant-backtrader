# L2 Phase3 pipeline (rar → csv → parquet) — run record

- Date: 2026-10-27 Asia/Shanghai
- Machine: newtest_4090
- **SSOT home: this repo (`MyQuant-backtrader`)** — extract + ETL + orchestrator together
- Status: SSOT in this repo; ops retarget starts pipeline from `scripts/misc/l2_phase3_pipeline.py` (EXTRACT/ETL via repo-relative + `resolve_oskh_python()`)

## Layout in this repo

| Piece | Path |
|---|---|
| Orchestrator | `scripts/misc/l2_phase3_pipeline.py` |
| Extract | `scripts/misc/extract_stock_rar_data.py` |
| ETL CLI | `scripts/run/run_l2_etl_day.py` |
| ETL core | `l2_analytics/etl_day.py` |
| Watch helper | `scripts/misc/l2_phase3_watch_check.ps1` |

OSkhQuant1.3 must **not** keep a second copy (see closed/redirected OSkh PR #1225).

## What is running on 4090 (at land)

```text
python scripts\misc\l2_phase3_pipeline.py   # from MyQuant-backtrader checkout; use resolve_oskh_python env
```

EXTRACT/ETL resolve from this checkout; Python via `resolve_oskh_python()` / `VANNA312_PYTHON`. Host SRC/CSV/lake/agent-tools paths remain env-overridable defaults for newtest_4090.

## Paths (newtest_4090 defaults baked into pipeline)

| Role | Path |
|---|---|
| RAR/7z SRC | `J:\stock_data` |
| CSV staging | `J:\l2_work\stock_csv_data\<YYYY-MM-DD>\` (deleted after OK day) |
| Lake | `J:\l2_lake\l2_parquet\date=<YYYY-MM-DD>\{main,order}.parquet` |
| Dates list | `C:\Users\wangc\agent-tools\l2_phase3_dates.txt` (~1391 days) |
| Skip dates | `C:\Users\wangc\agent-tools\l2_skip_dates.txt` |
| Progress md / jsonl | `C:\Users\wangc\agent-tools\l2_batch_progress.md` / `.jsonl` |
| PID / logs | `C:\Users\wangc\agent-tools\l2_phase3_pipeline.pid` + `.out.log` / `.err.log` |
| 7-Zip | `C:\Program Files\7-Zip\7z.exe` |
| Python | `D:\anaconda3\envs\vanna312\python.exe` |

Env on ETL child: `OSKH_L2_PARQUET_ROOT=J:\l2_lake\l2_parquet`.

## Concurrency model

- **One ETL day** + **one extract prefetch** for the next day (thread overlap).
- Not multi-day parallel ETL.
- Wall time ≈ `max(extract_s, etl_s)` when quiet (~8–9 ok-days/h observed).
- Extract spikes when other USB jobs contend on the same J: DAS.

## ETL knobs

Pipeline calls ETL with `--gap-free-sample 50`. Defaults in CLI/core:

- `--memory-limit 18GB`, `--threads 0` (= cpu_count-1), `--chunk-files 400`
- Parquet **ZSTD**, `ROW_GROUP_SIZE = 122880` in `l2_analytics/etl_day.py`

## How to start / resume

Resume-safe via lake presence + progress jsonl + skip file. Example start:

```bat
cmd /c >> C:\Users\wangc\agent-tools\l2_phase3_pipeline.out.log 2>> C:\Users\wangc\agent-tools\l2_phase3_pipeline.err.log python D:\PycharmProjects\MyQuant-backtrader\scripts\misc\l2_phase3_pipeline.py
```

Stop policy: **Human GO only**. Auto-stop after 3 consecutive extract/etl failures.

## Post-Phase3 queue (not while PID busy)

- 2026 Baidu delta ETL (~109 days) — SRC `J:\stock_data\2026年`
- Force ETL `2024-02-19`
- UTF-8 skip retry (5 days) after encoding fallback

## Accel research

- Do not mutate live PID / lake while researching.
- Prefer this branch/PR over ad-hoc `/workspace/l2-phase3-research/` copies.

## Knife #3 observability (local patch; not deployed)

Successful ETL JSONL records retain the existing fields and four-field `parsed` subset,
and add top-level `profile`: the full ETL profile, including per-chunk details
(null when absent). `prefetch_wait_s` measures only the post-ETL join for the next
day (seconds, 1 decimal; 0.0 without a join). `csv_delete_s` measures the CSV delete
attempt, including failures (seconds, 3 decimals); existing delete notes remain.
`already_in_lake` records use 0.0 for both timings because neither operation runs.
The Markdown table and tail-only watch helper remain unchanged. No runtime knobs
or ETL behavior changed; no 4090/live PID/lake access or deployment performed.
