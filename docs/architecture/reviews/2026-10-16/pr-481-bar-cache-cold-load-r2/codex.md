# Codex review — PR #481 cold-load r2

Verdict: **HOLD**

Date: 2026-10-16. Reviewed docs tip `4b2eb2a459031080cee92b6a35945fdafb4f0918`.
Scope: full [r2 plan](../../../../backtest/plan-bar-cache-cold-load-2026-10-16.md),
full [#479 Grok review](../pr-479-bar-cache-cold-load/grok.md), G2 contract,
`ashare_bars.py` lake reader, identity, cache writer/decoder and loader,
`bar_store.py`, and minute loading in `csv_minute_backtest.py` and
`fullstrat_research_runners.py`. `bar_cache` is the disk cache; there is no
`backtest/research/bar_cache.py` module at this tip.

The 2026-10-16 chat instruction Human「通过就实施」makes this review the encode
gate and conditionally authorizes suggested defaults. The plan's old
「待裁 / 非 impl GO」labels are **not** the reason for HOLD. The remaining issue
is the interaction of the suggested identity defaults below. No implementation
branch or PR is opened under this verdict.

## Blocking finding — P1/P3 do not yet define one reusable shard identity

Plan §4 P1 (line 216) suggests **month-byte identity + `st_mtime_ns`**; P3
(line 218) retains all seven G2 fields, including `source_snapshot`, in the
authenticated identity and filename. These are individually safe ingredients,
but their roles together are not specified:

1. If the symbol's whole-file mtime participates in each month identity, an
   append changes every month identity, even where month bytes are unchanged.
   If mtime instead only triggers recomputation of month digests, unchanged
   month files can survive. These produce different rebuilt-shard counts in
   the mandatory S1.1 +1-day experiments. The suggested default does not say
   which interpretation is binding.
2. The default G2 `source_snapshot` is a **lake-wide shallow snapshot**.
   Replacing one symbol file can change its parent directory mtime and hence
   this token for every symbol. Retaining that token as an equality field in
   every shard invalidates unchanged symbols and months too. A month digest
   alone cannot make those shards reusable. Keeping only an explicit override
   and redefining the default snapshot would change G2 semantics, and must be
   stated rather than silently inferred from “seven fields all retained”.
3. Month bytes are not separately addressable source files here. The current
   reader opens the full symbol table before filtering. Define how a later
   process obtains/verifies month digests: rescan source data on every lookup,
   or authenticate a derived digest manifest against the file stamp. The
   former has lake reads even for an otherwise warm disk hit; the latter needs
   a manifest contract. Neither is prohibited in principle, but they have
   materially different P6 zero-lake-read behavior and S1.1 timings.

This is an identity-contract ambiguity, not a claim that month sharding is
impossible. F1 explicitly permits conservative whole-file invalidation if no
incremental promise is made. A minimal repair is to select that fallback
explicitly (and accept all historical-month rebuilds and shallow-token global
misses). Alternatively specify the month-digest verification contract and the
precise default/explicit snapshot roles. Add expected invalidation results for
same-month append, cross-month append, old-month correction, unrelated-symbol
replacement, explicit-token change, and preserved-metadata replacement.
Do not freeze old month stamps or weaken full sidecar authentication.

Until that repair, choosing an implementation would also choose a missing
semantic cut, rather than just encode the authorized suggested defaults.

## F1–F8 coherence assessment

| Constraint | Assessment |
| --- | --- |
| F1 | Correctly rejects frozen old-month stamps and false +1-day promises; P1/P3 interaction above still blocks a concrete shard identity. |
| F2 | Coherent: cover loader parameter months, build full months once per symbol scan, use nonoverlapping month rows, clip `request_start <= ymd <= request_end`, key memory by request window, derive spans from clipped frames. |
| F3 | Full typed authentication, root pinning, explicit snapshot escape hatch, no monolith migration and bypasses are coherent. Relationship to P1 needs the repair above. |
| F4 | Coherent with P4 selected: narrow minute pool plus strategy extras, retain broad daily scores, omit missing bars, no hint parameter, reconcile in S2 itself. |
| F5 | Correct budget placement and S3 frame contract. Real probe results remain a prerequisite to choosing shard grain; no cold-time claim follows from this review. |
| F6 | Coherent: default OFF, exact `0`/`1` parsing, invalid values exit, existing cache enum preserved. |
| F7 | Coherent safety limits: frozen source, last atomic replace wins, complete shard membership, unique tmp names, no automatic deletion. Batch membership must be defined independently of the requested subset. |
| F8 | Coherent: keep monolithic partial rewrite only with switch OFF; enabled shards must never call the monolithic merge/write path. |

Thus the constraints are substantially improved, but **not collectively
precise enough to encode the selected P1/P3 defaults yet**.

## Defaults binding on a subsequent passing review

These record the requested suggested-default interpretation; HOLD means no
cut is activated by this artifact.

| Cut | Default to bind |
| --- | --- |
| P1 | Month-byte identity plus nanosecond stamp; no frozen months or +1-day-only-new-month promise. Resolve the blocking stamp/snapshot roles first. Do not silently substitute whole-file identity. |
| P2 | F2 closed `ymd` interval; full parameter-window month coverage; one scan per symbol builds covered months; request start/end in `mem_key.extra`; spans rebuilt on clipped frames; no old monolith reads. |
| P3 | Retain `identity_version`, `start`, `end`, `dividend_type`, `schema`, `resolver_identity`, `source_snapshot`; full typed sidecar equality, no unauthenticated merge, retain explicit token. Specify month-aligned shard bounds separately from request bounds and resolve snapshot scope first. |
| P4 | Minute = pool union plus `extra_load_codes_for_strategy`; daily retains score universe. Keep `600036.SH` for version6_53. An identified minute score-only consumer requires explicit inclusion. Missing bars omitted, no `codes_hint`. |
| P5 | Unset or exact `0` = old monolith; exact `1` = shards; empty/false/off/no/other values exit. Default OFF. Preserve OFF status values and partial behavior. |
| P6 | No standalone S1 five-minute gate. S1 cold no slower than monolith until P4; warm = second hit/mem with zero lake reads. Report same-month and cross-month +1-day rebuilds separately. |
| P7 | No engine cleanup. Script deletion only for stale source identity and age over explicitly supplied N days; tmp only if owning pid is gone. Stable full-member batch hashing if batches selected; complete write before replace. |
| P8 | ns timezone-naive DatetimeIndex, float64 OHLC, int64 hm, identical ymd; preserve memory frame type and cache enum, add shard_hit/shard_miss/shard_rebuild counts. S3 requires separate GO/PR; no mmap. |

## Knife order and rollback check

After a passing revised review: **S1.1 probe → S1 shards (default OFF) → S2
codeset → S3 Arrow**. Follow plan §7's separate-PR requirement; it explicitly
forbids combining Arrow and sharding, so the user's preference for one PR
does not override that conditional restriction. Each knife owns its tests and
CSV reconciliation. S1.1 must establish measured grain and report scan/open
costs and fd exposure before S1 chooses single-symbol versus stable batches.
S3 remains separately gated under P8.

Rollback contract is sound as written:

- Unset/`0`: today's monolithic identity, file path, partial rewrite and status.
- `1`: only writes `bar_cache/shards/`, never reads/writes/migrates monoliths.
- `1 → 0`: leave shards on disk; monolith independently hits/misses. No third
  layout assembled from half shards and half monoliths. Keep memory namespaces
  separate too, so a process-local hit cannot bypass the selected layout.

## Must-fix with implementation versus deferred nits

Must-fix with implementation after the identity blocker is resolved:

- Test OFF behavior including partial/identity mismatch and every bypass;
  enabled missing-shard writes must not rewrite other symbols.
- Test both orders of short/long same-process windows, end-day inclusion,
  clipped spans, month boundaries, old-month corrections and root/token changes.
- Audit P4 at both callers: `run_book_data` currently lacks the main CLI's
  explicit `extra_load_codes_for_strategy` union. Do not assume its existing
  broad score set guarantees parking coverage. Keep daily/exdiv sets broad.
- If batches are selected, use stable code-key intervals rather than chunks of
  the current request or rank positions that shift on membership changes.
- Require N explicitly for cleanup instead of inventing an authorized retention
  default; missing source must not be interpreted as proof that data is stale.
- Record actual lake/pred prerequisites and both CSV comparisons. No configured
  lake roots were present in this review environment; synthetic tests cannot
  substitute for the plan's frozen-data performance/reconciliation gates.

Deferred: optional atomic spans JSON improvement (bad JSON already rebuilds),
log presentation beyond aggregate counts, and any daily-cache follow-up.

Explicitly out of scope: P1 infrastructure (`common/__init__.py`,
`common/infra/`), P2 DB/sqlite persistence, lake ingestion/layout changes,
alpha claims, mmap, strategy rules, execution kernel/NAV changes, CI allowlist
expansion, Cloud Agents, Grok execution, merging, or messaging the human.

## Validation and stop

Python: `/workspace/vanna312/bin/python`.

- `pytest -q tests/test_minute_cache_identity.py`: **27 passed**.
- `pytest -q tests/test_ashare_bars.py tests/test_bar_store.py tests/test_ashare_minute_frame_migration.py`: **22 passed**.

These are baseline data-free checks, not validation of an implementation.
Only this review artifact is changed. Per the user's HOLD branch, push the
review on #481 and stop; implementation PR **SKIPPED**.
