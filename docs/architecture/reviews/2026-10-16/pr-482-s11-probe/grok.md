# Grok review — PR #482 S1.1 minute cold-load probe

VERDICT=GO-WITH-NITS

Verdict: **GO-WITH-NITS**

Date: 2026-10-16 (Asia/Shanghai). Reviewed tip `b7115ac`
(`feat/bar-cache-cold-load-20261016`, PR
[#482](https://github.com/baiyibing/MyQuant-backtrader/pull/482)).
Scope: S1.1 **probe scaffolding only** against Human cut A + Codex r2
GO-WITH-NITS on [#481](https://github.com/baiyibing/MyQuant-backtrader/pull/481).

Sources: `scripts/diagnostics/probe_minute_cache_cold_load.py`,
`tests/test_minute_cache_cold_load_probe.py`,
`docs/backtest/note-minute-cache-cold-load-s11-2026-10-16.md`, plan
`docs/backtest/plan-bar-cache-cold-load-2026-10-16.md` (§4.2 / §7 / §11),
`../pr-481-bar-cache-cold-load-r2/{cut-a,codex-r2,grok}.md`, and
`git diff --name-only origin/master...HEAD`.

`grok` CLI hung (~5 min, no artifact); this review was completed
in-process. No merge. No further knives.

## 1. Checks (brief)

| Check | Result |
| --- | --- |
| Probe read-only / no production `bar_cache` mutation | **Pass.** Only exclusive JSON `--output` (`open("x")`). No `to_parquet` / cache writes / mkdir under cache. |
| Runtime loader unchanged | **Pass.** `ashare_bars.py` and other loader paths absent from diff vs `origin/master`. No `OSKH_MINUTE_CACHE_SHARD`. |
| Cut A whole-file invalidation in metrics | **Pass.** `cut_a_modeled_counts` same-month / cross-month both rebuild **all** covered months of the changed symbol; `actual_rebuilt_shards` is explicitly `null`. Note forbids “only new month”. |
| No drive-letter / path-SSOT leaks | **Pass.** Root via `minute_cache_identity` → `resolve_period_root("1m")/dividend_type=none` (or explicit `lake_root`). No hardcoded `D:`/`E:`/host paths in probe/tests/note. |
| Data-free CI tests / no lake required | **Pass.** Synthetic `tmp_path` parquet; 6/6 pytest green under `/workspace/vanna312/bin/python`. Missing configured root / sample file fail loudly. |
| Honest pending before S1 | **Pass.** JSON `pending[]` + note: host scan/open/fd, grain, actual rebuild fixtures, same-commit CSV, cold/warm budgets. Timings labeled non-cold (page cache not evicted). |
| Diff scoped | **Pass for encode knife.** Code = probe + tests (+ self-contained plan/review docs from #481). No accidental loader rewrite. |

## 2. Cut A / Codex r2 alignment

Codex r2 authorized S1.1 alone as the first ship: read-only probe +
data-free tests; no unvalidated runtime shard path; no switch install.

This PR matches that gate:

- Month windows are full calendar months covering the loader parameter
  window (`month_windows`), not CLI warmup guesses.
- G2 identity for freeze uses month-aligned `[windows[0][0],
  windows[-1][1]]` while `loader_request` keeps the raw start/end —
  consistent with cut A P3 (sidecar bounds ≠ request window).
- One full covering-window scan vs per-month rescans with
  `assert_frame_equal`; ratios + fd projections for `--request-codes`.
- Source stamp + identity checked before/after; mid-run change →
  `RuntimeError`. Metadata-preserving replacement honesty preserved
  (note + `source_assumption`).

No HOLD-worthy identity regression relative to cut A.

## 3. Nits (non-blocking)

1. **`fd_extrapolation.single_symbol_month_total_files` is misnamed.**
   Value is `request_codes * len(windows)` (full-request shard-file
   projection), not a single-symbol count. Rename in a follow-up (e.g.
   `projected_shard_files`) so grain/fd readers do not under-count by
   5575× when skimming JSON keys. Projection math itself is fine;
   `one_handle_per_worker_projection` / `all_shards_open_projection`
   labels are clearer.

2. **`cut_a_counts` synthesizes `same_month_plus_one` from an in-month
   day when `end` is already month-end** (`day = last-1`). Correct for
   demonstrating cut A (comment documents it), but `base_end` /
   `extended_end` can be misread as the live loader request ends.
   Prefer a one-line report field such as
   `modeled_not_measured_request_ends: true` or rename keys to
   `scenario_base_end` so host operators do not paste them into CLI
   `--end`.

3. **Evidence JSON embeds absolute `resolver_identity`.** Expected for a
   host run; do **not** commit probe output into git (path-SSOT /
   machine-local). Note already points output at an external evidence
   dir — keep that discipline.

4. **Namespace packages:** no `scripts/__init__.py` /
   `scripts/diagnostics/__init__.py`. Works as a namespace under repo-root
   `sys.path` (tests passed). Optional tiny inits only if import fragility
   shows up on Windows runners — not a merge blocker.

None of these reopen P1/P3 or authorize S1 encode.

## 4. Still blocked before S1 (not this PR)

Unchanged from Codex r2 / note:

- Frozen-host scan/open/fd numbers and page-cache-controlled ordering
- Actual same-month / cross-month rebuilt-file counts on local fixtures
  (without mutating the consumed lake)
- Grain choice from those measurements
- Same-commit unset/0 vs 1 CSV byte compare, span/window/G2 mutation /
  bypass tests when S1 lands
- `OSKH_MINUTE_CACHE_SHARD` default OFF; enabled path never monolithic
  partial rewrite (F8); F7 tmp/atomic rules

## 5. Decision

**GO-WITH-NITS** for merging **S1.1 scaffolding** after Human gate.
Does **not** authorize S1 shard encode, switch install, S2, or S3.
Do not merge from this review alone; Human still owns the merge button.
Nits may land as drive-by on a later docs/probe polish PR — not required
to unblock Human merge of #482 if scope stays scaffolding-only.

## 6. Nits addressed (post-review polish)

Human asked to land nits before merge (2026-10-16). Applied on this branch:

1. Renamed `fd_extrapolation.single_symbol_month_total_files` →
   `projected_shard_files` (value remains `request_codes * months`).
2. `cut_a_modeled_counts` now nests scenarios under `scenarios` with
   `scenario_base_end` / `scenario_extended_end` and top-level
   `modeled_not_measured_request_ends: true`.
3. No probe evidence JSON was committed; `.gitignore` now keeps host
   `minute-cold-load-probe*.json` / evidence dir out of git.
4. Skipped optional `scripts/` package inits (namespace import already green).

Verdict for scaffolding merge remains **GO-WITH-NITS** (nits cleared).
Still does not authorize S1 encode.
