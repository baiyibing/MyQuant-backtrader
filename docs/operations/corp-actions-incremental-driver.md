# Wind/Kimi corp-actions incremental export (4090)

Human GO: 2026-10-24 ~21:52 CST, Grok/hostbot-4090 widget t1513s6048, Owner qt/bt.
This GO permits the incremental driver, export, assembly and **merge preparation only**.
It is the narrow exception to the repo's usual consume-only vendor policy; it does
not authorize a lake publisher, market-bar writes or changes to research economics.
Implementation is left for Claude/Kimi review alongside CI; do not merge yet.

Entry: [`scripts/data/pull_corp_actions_incremental.py`](../../scripts/data/pull_corp_actions_incremental.py).
One workflow: `init` → `pending` / `pull` → `assemble` → `prepare-merge`.
There is **no apply/merge/publish command**, no scheduler, and no trading hook.

## Baseline and boundaries

The blocker inventory supplied for this task reports the untouched lake as
`E:\stock_data\corp_actions`, revision `r20261023_01`, snapshot
`bt_corp_actions_20261006`, 21,779 events, `coverage_window.ask_end=2026-10-06`.
Those are handoff facts, not a fresh Bot VM observation of the 4090 disk.
The complete source is `D:\exports\bt_corp_actions_20261006`; its
[`README`](../../data/corp_actions/bt_corp_actions_20261006/README.md) and archived
`work/driver.py` / `work/assemble.py` supply the Wind protocol and field contracts.

Runtime output for this task: **`D:\exports\bt_corp_actions_incr_20261024`**.
Keep it separate from both the lake and full-pull directory. Never run the archived
`driver.py all`, and leave `corp-actions-reconnect-resume` paused. Do not re-pull
2014 → 2026-10-06. No CNINFO extract overwrite, no Cloud Agents, no lake write.

`init` requires an existing manifest and all three Parquet tables. It derives
start from **ask_end + 1 natural day**, never from the maximum actual event date.
For this baseline that is **2026-10-07**; end defaults to today in Asia/Shanghai
and is frozen at init. `--end 2026-10-24` makes this run reproducible. An explicit
`--start` must equal ask_end + 1; overlap, gaps, future end, backward windows and
bases predating 2026-10-06 fail. A resume cannot silently change dates or model.

Use prior `universe.txt` for the **2774-code strategy-pool lineage**, including
`000001.SZ` even if outside a current pool. No current-pool or full-market expansion
is performed. Explicit listing CSV/Parquet is also accepted (`code` column);
omitting `--universe` uses the lake's listing table, which the handoff reports has
only **2762** codes. That fallback does not recover the missing 12; check the frozen
code count in `run.json` before pulling. Codes must already have Wind suffixes.

## 4090 commands

PowerShell, from the reviewed branch checkout. Resolve the interpreter with the
repo helper (OSKH_MERGE_PYTHON → VANNA312_PYTHON → VANNA311_PYTHON → vanna312
fallback); do not invoke system Python/pip implicitly. Example using the explicit
4090 environment:

```powershell
$btPython = 'D:\anaconda3\envs\vanna312\python.exe'
$btDriver = '.\scripts\data\pull_corp_actions_incremental.py'
$btOut = 'D:\exports\bt_corp_actions_incr_20261024'
$btPriorUniverse = 'D:\exports\bt_corp_actions_20261006\universe.txt'
# This is a read-only input, not a publication destination.
$btLake = 'E:\stock_data\corp_actions'

& $btPython $btDriver init --out-dir $btOut --lake-dir $btLake `
  --universe $btPriorUniverse --end 2026-10-24
if ($LASTEXITCODE -ne 0) { throw 'init failed; inspect error before continuing' }
& $btPython $btDriver pending --out-dir $btOut
& $btPython $btDriver pull --out-dir $btOut
if ($LASTEXITCODE -ne 0) { throw 'pull incomplete/stopped; inspect pending and logs' }
& $btPython $btDriver assemble --out-dir $btOut
if ($LASTEXITCODE -ne 0) { throw 'assembly incomplete; do not prepare merge' }
& $btPython $btDriver prepare-merge --out-dir $btOut
```

`--lake-dir` is an explicit read-only directory. Without it, the existing
`resolve_source_parquet("corp_actions")` uses configured `OSKH_SOURCE_PARQUET_ROOT`
or authority hints; missing configuration/files fail, with no drive probing.
No Windows data path is hardcoded in executable code.

Default runtime model: **`kimi-code/kimi-for-coding-highspeed`**. The only other
accepted `init --model` is `kimi-code/kimi-for-coding`. **No K3** and no fallback
to a more expensive model; inherited `KIMI_MODEL` does not override the frozen
choice. `kimi` resolves on PATH; `pull --kimi-bin <explicit-kimi.exe>` is available
when needed. The command uses `-m <frozen-model> -p <prompt> --output-format text
--add-dir <new-outdir>`; it does not use `--auto` or `--yolo`. Credentials stay in
the existing host client configuration and are never embedded in this workflow.

## Resume, pending and quota

Sessions run serially under an exclusive `work/runner.lock`, preventing parallel
drivers on the same outdir. Default six calls per session, six codes per initial
call. `--calls-per-session 1..12`, `--max-attempts` (default 3) and `--timeout`
(default 1800 seconds) affect pull scheduling only. No background runner is created.

```powershell
& $btPython $btDriver pending --out-dir $btOut
& $btPython $btDriver pull --out-dir $btOut  # resumes only unfinished tasks
# Only after the quota window has reset, explicitly resume this incremental run:
& $btPython $btDriver pull --out-dir $btOut --resume-quota
```

Quota/usage-limit/403/429 stops the runner, writes `work/QUOTA_STOP.json`, returns
exit **3**, and launches no later session. A plain `pull` stays stopped while that
marker exists. `--resume-quota` archives it and retries; quota/startup credential
failures do not consume vendor attempts. Startup errors and timeouts return **2**
without sleeping/spinning. Failed/interrupted vendor attempts are bounded; raising
`--max-attempts` explicitly permits additional attempts. Exit **0** means command
success, **2** means invalid input, unresolved work or other failure. `pending`
returns 0 for a readable status even when work is unresolved; inspect its counts.

The task journal is atomically replaced before and after each session. Completed
task evidence is reused; every new attempt has fresh raw and log paths. A killed
process can leave `runner.lock`: first verify no driver/Kimi process is active for
this outdir, then remove **only this run's** stale lock and resume. Do not touch
the full-pull routine or its markers. The pending count is tasks, including
follow-ups, rather than a count of distinct unqueried codes.

Success requires both a valid `RESULT_JSON` task entry and a validated raw CSV
with matching row count. A file's existence alone is insufficient. Responses
with >=100 rows split into single-code follow-ups; a capped singleton blocks
preparation. Missing batch codes also receive single-code queries. Header-only
singletons, generic errors and missing entries remain unresolved. Only the
singleton vendor error containing `API_CALL_ERROR` and `没找到数据` records
vendor no-data; batch no-data is followed up. No partial file from a quota,
startup failure or nonzero session is accepted.

## Evidence and normalization

```text
<outdir>/run.json                         frozen base hashes/window/model/universe
         universe.txt                    frozen codes (no new universe scan)
         raw_events/<task>/<session>.csv  original vendor files, unique per attempt
         work/tasks.json                 journal, attempts, evidence hashes
         work/kimi_logs/*                 prompts, stdout and stderr
         work/QUOTA_STOP*.json            stop marker and explicit-resume archives
         assembled/corp_actions.csv      incremental events only
         assembled/events.parquet        date32 / decimal128(24,12), matching base schema
         assembled/rejected.json         raw rows excluded with reasons
         assembled/summary.json          pending/quality/provenance, not lake validation
         merge-prep/events.parquet        base + delta candidate, never installed
         merge-prep/listing.parquet       unchanged base bytes
         merge-prep/failures.parquet      unchanged base bytes (old failures retained)
         merge-prep/manifest-patch-plan.json
```

Assembly keeps `实施完毕` rows with ex_date inside the incremental window. Raw
out-of-window/unimplemented/missing-ex-date rows remain in evidence and the reject
report. Unexpected columns/codes, ragged CSV, invalid dates, negative/nonfinite or
overprecision numbers, missing implemented record_date and contradictory date
ordering fail closed. Wind cash is pre-tax CNY/share; bonus/transfer are already
new shares per original share (**0.3 stays 0.3**, no division by 10). Blanks remain
NULL, distinct from zero; no pay/list dates or cash values are inferred.

The natural event key is `(code, ex_date, cash, bonus, transfer)`, matching the
full-pull dedup convention. Exact duplicates collapse, complementary blank dates
may fill, conflicting nonblank fields stop assembly. Different economics on the
same code/day remain separate events for review. Incremental event IDs use a
stable key hash with `_incr_`; existing base event IDs are preserved verbatim.
This is storage preparation, not PIT signals or economics-engine admission.

**Vendor-window limitation:** the full-pull README records missing ex-dates when
Wind's question started too late, apparently because the vendor filters by
report/announcement period. This driver deliberately does not widen the query
back into the completed history. Therefore an empty incremental query is **not
proof of no ex-date events**. Old ex-date payment/list-date updates, historical
corrections, cancellations and new listings are outside this knife. Have the
owner review date-filter semantics/evidence before advancing lake coverage;
otherwise keep the existing ask_end and treat the delta as provisional evidence.

## Merge-prep versus lake publication

`prepare-merge` first assembles under the same lock and refuses unresolved tasks,
incomplete universe evidence, input/hash drift, incompatible base schema or ID
collisions. It writes to a new temporary directory **inside the outdir**, checks
the candidate round trip and base hashes again, and renames that directory to
`merge-prep`. An existing candidate is immutable and cannot be overwritten.

The plan pins all base SHA256s, base revision/snapshot, delta provenance and
candidate hashes/counts. It proposes an ask_end patch but explicitly sets
`lake_write_authorized=false`, `automatically_applicable=false` and requires
vendor-window review. It deliberately does **not** emit a replacement lake
`manifest.json`. Listing and prior failure rows are copied, not refreshed or
silently resolved. Python only reads the base; all writes are confined to the
outdir. Overlap with the input lake, configured lake container or prior input
directory, and output symlink escapes, are rejected. Kimi's prompt permits only
the listed vendor `file_path` writes under that outdir, with no shell/other source.

**Stop here.** A separate Human GO and owner-side publication step must choose a
new revision/snapshot, recheck the exact base hashes, review missing economics and
date coverage, and publish any approved candidate. This PR supplies no publisher,
does not touch `E:\stock_data\corp_actions` and does not change its `ask_end`.

## Bot VM verification and review handoff

Use the explicitly selected environment, with no live Wind/Kimi calls:

```bash
/workspace/vanna312/bin/python -m pytest -p no:cacheprovider -q tests/test_corp_actions_incremental_driver.py
/workspace/vanna312/bin/python -m ruff check scripts/data/pull_corp_actions_incremental.py tests/test_corp_actions_incremental_driver.py
```

Fixtures cover bounded resume, quota stop/explicit resume, malformed/missing
results, caps, singleton no-data, date/Decimal validation, unchanged lake hashes,
candidate preservation, protected paths and subprocess CLI smoke. The existing
`python-tests` workflow includes these data-free tests; no additional workflow or
vendor dependency is required. Claude/Kimi reviewers should focus on the query
coverage limitation, evidence acceptance and absence of any publication path.
