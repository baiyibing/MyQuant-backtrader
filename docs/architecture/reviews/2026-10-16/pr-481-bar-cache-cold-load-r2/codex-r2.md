# Codex re-review — #481 r2, Human cut A

Verdict: **GO-WITH-NITS**

2026-10-16. Reviewed plan tip `d4df2fc`, the full plan, prior `codex.md`
HOLD, `grok.md`, `cut-a.md`, and live `ashare_bars` reader, identity and loader.
The prior review is preserved. Human「通过就实施」(2026-10-16) makes this
review the encode gate and authorizes the suggested defaults below.

## Identity blocker closed

Section 4.2, F1/F3 and P1/P3 now select one executable contract: every
month carries the symbol's whole-file nanosecond stamp (with size), all seven
G2 fields remain authenticated, and start/end are month-aligned bounds.
Request bounds belong to clipping and memory keys. No +1-day-only-new-month
promise, no frozen old months, no digest manifest. Default lake-wide shallow
snapshot broad misses are intentional conservatism. Explicit tokens remain.

The matrix covers same-month append, cross-month append, old-month repair
(all covered symbol months miss), unrelated-symbol replacement (own stamp
plus potentially global shallow miss), explicit-token change (all miss), and
metadata-preserving replacement (may evade stamps; change explicit token).
This directly resolves the prior HOLD; it does not establish performance.

## F1–F8 and binding defaults

F1–F8 are coherent enough to encode in the stated order. F2 requires full
loader-parameter month coverage, closed-interval clip, nonoverlapping months,
request-keyed memory and spans over clipped frames. F3 preserves typed G2
checks and bypasses. F4 keeps missing bars omitted and reconciliation in S2.
F5 separates budgets from unmeasured scan costs. F6 preserves rollback and
status. F7 assumes frozen sources, unique pid/uuid tmp and complete atomic
publication; F8 forbids enabled monolithic partial rewriting.

| Cut | Binding default under this GO |
| --- | --- |
| P2 | F2 closed ymd interval; one symbol scan builds all covered full months; request start/end in mem_key.extra; spans on clipped frames; no old monolith reads. Probe also measures per-month rescan multiplier. |
| P4 | Minute = pool union plus strategy extras; score universe remains daily unless an identified minute consumer needs it. Preserve version6_53 parking 600036.SH, audit both CLI and run_book_data; no codes_hint; missing bars omitted. S2 owns reconciliation. |
| P5 | Unset or exact 0 = unchanged monolith including partial/status; exact 1 = shards only; empty/false/off/no/other values fail closed. Default OFF. |
| P6 | No standalone S1 five-minute gate; S1 cold no slower than monolith pending P4. Warm = second hit/mem with zero lake reads. Separate same-month and cross-month rebuilt counts. |
| P7 | No engine deletion; cleanup script only stale current-source stamp plus age over explicitly supplied N days; tmp only with dead owning pid. If batching, stable code intervals and all-member stamp hash; publish complete identity only. No retention N invented here. |
| P8 | Preserve timezone-naive DatetimeIndex(ns), float64 OHLC, int64 hm, ymd values and memory object type; freeze cache enums, add shard_hit/shard_miss/shard_rebuild counts. S3 needs separate GO/PR; no mmap. |

## Authorized first delivery and remaining gates

Knife order: **S1.1 → S1 shards (default OFF) → S2 codeset → S3 Arrow separate PR**.
The user's option to ship S1.1 alone is the honest first delivery: this
environment has no configured source/authority root. Ship a read-only probe
and data-free tests, with actual host measurements explicitly pending. Do not
choose single-symbol versus stable batches without scan/open/fd evidence.
Do not add an unvalidated runtime shard path to make this PR look complete.

Rollback remains unset/0 = monolith; 1 = only bar_cache/shards/; no
half-shard third layout, including memory namespaces. S1.1 does not install
the switch or change the runtime loader. Any later shard path must default OFF.

Must-fix with implementation: probe reports scan vs per-month multiplier,
open vs scan ratio and fd exposure extrapolated to requested codes, plus
same-month/cross-month counts under cut A. Label modeled invalidations versus
actual rebuilt files honestly. Fail on absent configured lake or requested
probe source; never silently substitute empty data. Record source freeze
assumption and reject detected stamp changes during measurement. S1 still
needs frozen-host performance and same-commit CSV byte comparisons, both
window orders, clipped spans, identity mutations, bypasses and OFF partial
tests. These are later S1 acceptance gates, not satisfied by synthetic tests.

Deferred nits: atomic spans JSON improvement, log styling, cleanup tooling
until shards exist, daily cache follow-up. Historical “未裁” headings remain
historical prose; the table defaults above are bound by this chat's GO gate.

Out of scope: P1 infra (`common/__init__.py`, `common/infra/`), P2 DB/sqlite,
lake ingestion/layout or alpha claims, execution/NAV/rule changes, mmap,
CI allowlist expansion, Cloud Agents, Grok execution, human messaging, merge.
