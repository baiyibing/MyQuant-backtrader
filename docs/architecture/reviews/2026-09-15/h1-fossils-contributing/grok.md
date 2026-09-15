I'll review the H1 change against the plan doc: first load the review skill and the H1 plan, then inspect the branch diff for moves, links, CONTRIBUTING accuracy, and scope.Reviewing branch `feat/hygiene-h1-fossils-contributing` against its merge-base. Loading the reviewer persona and collecting the H1 plan plus branch diff.Collected the setup IDs. Next I’ll compute the merge-base and persist the H1 branch diff.Collected the branch diff (37 files vs `origin/master`). Launching the reviewer against the H1 plan checks.I'll start by reading the H1 plan, the diff, and the required docs so the review is grounded in the actual files.Next I’ll pull git history, the full diff, AGENTS/SSOT, and search for leftover fossil paths.Fossils look like 100% git mv; I’ll now verify leftover links and whether extra commits actually touch the fill engine.I'll inspect relative links inside the fossils and scan the rest of the repo for leftover old-path references.I have enough to write the review: H1 docs look correct, but the branch still carries unrelated engine/hotpath commits.Review written to `/tmp/grok-box/grok-review-8508d17d.md`.

**Verdict:** H1 docs are correct — six fossils are true R100 moves, links and CONTRIBUTING check out, no H1-doc semantic rewrite. **Blocking 🔴:** this H1-named branch also carries unrelated engine/hotpath code (`csv_common`, numba `scan_held_day`, simulate-loop), which is out of H1 scope and edits 成交核 modules. Cerebro/L2/strategy books were not touched. Completed-plan archive is extra (🟡), including one leftover relative 404.Review complete. Processing findings: I’ll read the review notes, tally severities, and write the summary.Found 2 issues (1 bug, 1 suggestion, 0 nits). Wrote `/tmp/grok-box/grok-review-8508d17d.md` and `/tmp/grok-box/grok-review-summary-8508d17d.md`.

## Review: `feat/hygiene-h1-fossils-contributing` vs `origin/master`

H1 docs work is correct. The blocking problem is that this H1-named branch is not H1-only.

| Check | Result |
|---|---|
| Six fossils moved correctly | Yes — R100 `git mv`, blob-identical; live `engine-*.md`, `pool-csv-contract.md`, README, reports, hotpath plan stayed put |
| Links fixed | Yes for the six fossils; 「文件（考古）」 table points at `_archive/fossils/`; fossils README labels them retired archaeology. One leftover 404 is in the extra plan-archive commit, not the fossil moves |
| CONTRIBUTING accurate | Yes — research-face vectorized fork, F-lake read-only, don't-do list aligned with AGENTS / engine-positioning, GitHub Actions, CloudAgent one-liner. No live-trading / LEBS-as-this-repo / Cerebro-as-live-engine claims |
| Accidental H1 semantic/code change | No — fossil bodies unchanged |
| 🔴 scope creep | Yes — engine/hotpath/成交核 commits are on this branch |

**Files reviewed:** 37 (37 files changed, 1092 insertions, 293 deletions)

**Issue counts:** 1 bug, 1 suggestion, 0 nits

### Issue 1 — bug (🔴)

- **File:** `backtest/research/csv_minute_backtest.py:425`
- **What:** Branch is not an H1-only PR. Besides `dba3c42` (fossils + CONTRIBUTING), it includes `40c5504` / `b1357f8` / `846c7ea`: `csv_common.py`, `csv_simulate_loop.py`, daily/minute backtests (numba-gated `scan_held_day`), microbench, presets snapshot test, hotpath plan. H1 deliverables are only fossil archive + fossils README + README table + root CONTRIBUTING + link fixes. `engine-ashare-correctness.md` names `csv_daily_backtest.simulate` and `csv_minute_backtest.scan_held_day` as 成交核, so this also violates H1 不要「不改成交核」. Cerebro was not deleted; strategy books and L2 were not expanded. Hygiene backlog already lists this as a prior PR / H5, not H1.
- **Fix:** Split engine/hotpath/presets onto their own PR (or rebase this branch onto that merge). Keep H1 as the fossil `git mv`, fossils README, README table, CONTRIBUTING, and fossil-link fixes.

### Issue 2 — suggestion (🟡)

- **File:** `docs/backtest/_archive/plans/plan-strategy7-turtle-csv-minute-2026-09-11.md:8`
- **What:** Completed-plan archive (`20fc35e`) is extra, not an H1 deliverable. One R100-moved plan still uses `(../architecture/reviews/...)`, which now 404s at `docs/backtest/_archive/architecture/reviews/...`.
- **Fix:** Keep plan archive off the H1 PR. If it stays, retarget that href to `../../../architecture/reviews/2026-09-11/plan-strategy7-turtle-csv-minute-2026-09-11/review-by-cursor.md` (or a root-relative link). Do not rewrite frozen review artifacts.

Full review: `/tmp/grok-box/grok-review-8508d17d.md`  
Summary: `/tmp/grok-box/grok-review-summary-8508d17d.md`

---

## Executor note (2026-09-15)

Grok 🔴 about engine/hotpath commits on the branch vs `origin/master` is **not treated as an H1 implementation defect**. Hygiene backlog lists PR #34 (hotpath / presets / simulate skeleton / plan archive) as **前置**; H1 commit `dba3c42` is docs-only (fossils `git mv` + CONTRIBUTING + README links). No follow-up fix for that 🔴. Plan-archive leftover relative link (🟡) is also outside H1 scope and left alone.
