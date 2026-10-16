# S1.1 minute cold-load probe scaffolding — 2026-10-16

Implements the first knife of [r2 + cut A](plan-bar-cache-cold-load-2026-10-16.md),
after [Codex GO-WITH-NITS](../architecture/reviews/2026-10-16/pr-481-bar-cache-cold-load-r2/codex-r2.md)
on [#481](https://github.com/baiyibing/MyQuant-backtrader/pull/481).
Human「通过就实施」2026-10-16 authorizes this encode. Grok review pending; do not merge.

This PR delivers **S1.1 scaffolding only**. It does not change `ashare_bars`,
callers, cache files, memory namespaces, cache status or any strategy. The
runtime remains monolithic. `OSKH_MINUTE_CACHE_SHARD` is not installed here;
future S1 must default OFF: unset/0 = unchanged monolith, 1 = only
`bar_cache/shards/`, illegal values fail closed, no mixed layout. No S2 or S3.

## Run on the configured frozen host

Use the selected repository Python. Example arguments for the topk loader
window (codes are an explicit sample, not a replacement for its full codeset):

```sh
"$OSKH_MERGE_PYTHON" scripts/diagnostics/probe_minute_cache_cold_load.py \
  --codes 600000.SH 600036.SH --start 20251227 --end 20260914 \
  --request-codes 5575 --workers 16 --open-repeats 20 \
  --output /existing/evidence-dir/minute-cold-load-probe.json
```

The root is resolved through `resolve_period_root("1m") / dividend_type=none`.
No root guessing or fallback. Missing configured root or requested sample
file fails. Output creation is exclusive; choose a new file for each run.
`--start/--end` are the actual loader parameter window including warmup;
the script does not guess the caller's warmup. Optional `--source-snapshot`
preserves explicit G2 token semantics. Lake files are never written.

The JSON records G2 identity, size/nanosecond source stamps, full-month
bounds, one full-window scan versus a scan per month, frame equality,
mean Parquet open/close overhead, time ratios, and file-count/fd projections
for the explicit full-request count. The probe is serial (one Parquet handle
at a time); projected concurrent handles assume one per worker. Total shard
files and opening all files simultaneously are separate projections, not
claims about current live descriptors. No frame or price data is exported.

These are ordered observations: the OS page cache is **not evicted**. Repeat
with controlled ordering/cache state on the host before making cold-time
claims. Stable size/mtime and G2 identity are checked before/after; this
cannot detect a concurrent writer that preserves metadata. Freeze the source.

## Evidence status and next knife

No configured source/authority root is available in the implementation
environment. Real-host numbers remain **PENDING**. Synthetic parquet tests
exercise actual scan equivalence, month coverage, absence errors and source
mutation rejection; they do not establish host performance or alpha.

`cut_a_modeled_counts` reports expected whole-file invalidation separately
for same-month and cross-month +1. It is **not** a measurement of rebuilt
files (`actual_rebuilt_shards` is null). Same-month means all existing covered
months; cross-month includes all historical covered months plus the new one.
No digest manifests, frozen stamps or incremental-only promise.

Before S1: collect representative host scan/open data and monolith versus
candidate shard write/read costs, choose grain from those measurements,
and record actual rebuilt-file counts with local append/repair fixtures
without mutating the consumed lake. Then run the plan's same-commit
unset/0 versus 1 CSV byte comparisons, monthly boundary/window-memory/span
checks, G2 mutation checks and bypass tests. S1 cold must not regress against
monolith; <=5min is not a solo S1 gate. Warm must be second hit/mem with zero
lake reads. Source freeze and F7 unique tmp/complete atomic publication and
F8 enabled no-monolithic-partial rewriting remain required.

S2 codeset owns its own reconciliation and parking-code audit. S3 Arrow
requires a separate GO/PR and the existing frame contract; no mmap. No P1
infra, P2 DB/sqlite, CI allowlist changes, cleanup script or lake changes.
