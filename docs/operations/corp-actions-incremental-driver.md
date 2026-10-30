# Wind/Kimi corp-actions incremental export (4090)

Human GO: 2026-10-24 ~21:52 CST, Grok/hostbot-4090 widget t1513s6048, Owner qt/bt.
This GO permits the incremental driver, export, assembly and **merge preparation only**.
It is the narrow exception to the repo's usual consume-only vendor policy; it does
not authorize a lake publisher, market-bar writes or changes to research economics.
Implementation is left for Claude/Kimi review alongside CI; do not merge yet.

Entry: [`scripts/data/pull_corp_actions_incremental.py`](../../scripts/data/pull_corp_actions_incremental.py).
One workflow: `init` → `pending` / `pull` → `assemble` → `prepare-merge`.
There is **no apply/merge/publish command**, no scheduler, and no trading hook.

## Hithink frozen artifact intake (2026-10-30 implementation)

The 2026-10-30 Human GO adds an explicit `--channel hithink`. Wind is still the
default; old run.json files without `channel` retain Wind semantics. Hithink has
no model, Kimi process, network access or key requirement in this repository.
The producer lives in OSkhQuant1.3 at `scripts/data/export_hithink_corp_actions.py`.
The [implementation/review record](hithink-artifact-implementation-2026-10-30.md)
records the v6 contract, review corrections, tests and current real-data blockers.

In 1.3, use the canonical Python executable explicitly through a configured
`OSKH_MERGE_PYTHON`. Load `HITHINK_FINANCE_API_KEY` into that process environment
from the operator's secret store; do not put the key in command arguments or logs.
Key rotation is at <https://fuyao.aicubes.cn/admin>.

```powershell
& $env:OSKH_MERGE_PYTHON scripts/data/export_hithink_corp_actions.py --universe <original-universe-file> --start 2026-10-07 --end 2026-10-28 --out-dir <new-snapshot-directory>
```

The artifact contains `hithink_dump.parquet`, `probes.json`, `manifest.json` and
`COMMITTED.json`. The marker binds the manifest, which binds file hashes, the
original universe bytes, normalized codes, window and original fetched_at.
An incomplete output directory must be inspected and replaced by a new output
directory; it is never resumed as a successful snapshot. Probe failures are
recorded but do not prove no events. C classification requires successful exact
identity and explicitly empty event probes, with response hashes and request IDs.
`3002` remains D/unexplained.

In this repository, use the **same original universe file**, not an independently
regenerated text file whose bytes may differ. The base must be an existing,
reviewed corp-actions snapshot with all four required files; a CSV archive alone
is not a lake revision. Output directories must be separate from the configured
lake and inputs.

```powershell
& $env:OSKH_MERGE_PYTHON scripts/data/pull_corp_actions_incremental.py init --channel hithink --universe <original-universe-file> --lake-dir <reviewed-base-directory> --end 2026-10-28 --out-dir <new-run-directory>
& $env:OSKH_MERGE_PYTHON scripts/data/pull_corp_actions_incremental.py pull --out-dir <run-directory> --artifact-dir <snapshot-directory>
& $env:OSKH_MERGE_PYTHON scripts/data/pull_corp_actions_incremental.py assemble --out-dir <run-directory>
& $env:OSKH_MERGE_PYTHON scripts/gates/verify_corp_actions_hithink_parity.py --run-dir <run-directory>
& $env:OSKH_MERGE_PYTHON scripts/data/pull_corp_actions_incremental.py prepare-merge --out-dir <run-directory>
```

Imported files occupy `raw_events/`; original fetch time and import time are
separate in `work/hithink_state.json`. The local commit marker binds that state
and all imported files. `pull --refresh` imports a complete new bundle and keeps
the superseded files for inspection; it is forbidden once `assembled/` exists.
After `merge-prep/` exists, both assemble and prepare-merge reject overwrites.

The default exclusions file has **no manual approvals**. An explicitly reviewed
D exception must record code, classification, reason, evidence, approved_by,
approved_at, review_after, scope_start and scope_end in the run's copied
`hithink_exclusions.json`. The latter dates delimit event applicability; the
former use the actual CST evaluation date. Approvals may follow fetched_at.
Changes to a non-D classification or missing/expired evidence are rejected.
Historical parity uses the base ask_start/ask_end and the same coverage evaluator.
The reviewed diagnostic baseline now has 47 exact keys (the original 46 plus
the source-verified Decimal boundary key); new or missing keys fail. Existing
runs keep their copied config. Use a new run for the updated baseline.

`assembled/hithink_allotments.json` preserves rights issues. Pure rights are
excluded from candidate events; mixed rights/dividends block candidate preparation.
Different raw records with the same projected natural key require identity review.
Dates stay NULL; amounts use exact decimal conversion without ROUND4 or field
stitching. Candidate plans explicitly state `economics_ready=false`.

The future economics entry is `load_corp_actions_for_economics()` in
`backtest/research/corp_actions_econ_gate.py`. It checks manifest revision and
events SHA, optional evidence revision/file/field hashes, then returns accepted,
blocked and per-event reasons. Evidence records reviewer/date, economic basis,
shareholder class, policy, event identity and a continuous announcement revision
chain with document hashes. Missing pay/list dates block all sources; Hithink
requires reviewed basis even with complete dates. Multiple same-day rows stay
blocked until a separately reviewed revision resolves their applicable identity.
No existing economics consumer is connected by this change. The CI fence guards
seven registered consumer files and the two existing non-corp-actions reads;
new consumers/readers require an explicit inventory review.

**Current real-data status:** following the 2026-10-30 continuation GO, the
producer supports explicit `--quarantine-outside-window`. This creates v2 with a
hash-bound `quarantine.json`; without this flag v1 still rejects every negative
amount. Only negative amounts outside the closed requested window can be
isolated. Invalid identities, timestamps, currency, nonfinite amounts and precision
loss still fail the whole run. The raw parquet remains unchanged. BT independently
reconstructs the sidecar and reports both usable and isolated rows. Codes found
only in isolated history still count as vendor-present. Historical parity fails
if isolated rows intersect its comparison universe/window.

The real v2 download and BT import succeeded: 57,709 raw rows, 2 isolated historical
negative bonus rows, 162 assembled incremental events. Source review confirmed
the 47th exact diagnostic key (`300708.SZ`, 2020-06-02, cash 0.0199 vs 0.02),
so the diagnostic set now has 47 keys; the threshold remains 1e-4. All 47 keys
reproduced. Coverage still has 11 unexplained codes, and prepare-merge remains
blocked. See the [continuation record](hithink-artifact-v2-2026-10-30.md), including
the per-code review table. No economic approval or lake publication follows
from these acquisition and diagnostic results.

## Baseline and boundaries

CNINFO backup planning lives in the [2026-10-29 C0 plan](corp-actions-cninfo-backup-incremental-plan-20261029.md): independent sandbox outdir, no Wind lake overwrite, C1+ needs separate Human GO. The primary path remains Wind/Kimi when available; this docs-only knife makes no driver/vendor switch and does not fix the upstream 401. See that plan and the [10-28 status](corp-actions-incremental-20261028-status.md) for Wind resume on a tip including #523 (k3 + skipped accounting).

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
without sleeping/spinning. Calls the model skipped under the prompt stop policy
(e.g. after a mid-session vendor 401; `skipped:`/empty-error entries) made no
vendor request: they are journaled as `skipped`, do not consume attempts, and a
session in which every call was skipped returns **2** instead of spinning.
Failed/interrupted vendor attempts are bounded; raising
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
