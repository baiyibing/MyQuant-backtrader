## Summary

The H1 docs slice is correct: all six Backtrader fossils are R100 `git mv`s (blob-identical to `origin/master`), live docs (`engine-*.md`, `pool-csv-contract.md`, `docs/backtest/README.md`, reports, hotpath plan) stayed put, the 「文件（考古）」 table now points at `_archive/fossils/`, `_archive/fossils/README.md` correctly labels them as observation-retired archaeology, and `CONTRIBUTING.md` accurately describes a research-face vectorized fork with F-lake read-only, a don't-do list aligned with AGENTS/engine-positioning, GitHub Actions for PRs, and a CloudAgent one-liner. No leftover old-path fossil links; no accidental rewrite of fossil body text. The blocking problem is 🔴 scope creep: this H1-named branch vs `origin/master` also contains unrelated engine/hotpath/code (csv_common extract, numba `scan_held_day` offload, simulate-loop refactor, presets snapshot test, microbench) that edits modules `engine-ashare-correctness.md` lists as 成交核, violating H1 不要「不改成交核」and mixing non-H1 work onto the PR. Cerebro was not deleted, strategy books (`csv_strategy_books.py`) and L2 were not expanded. Extra completed-plan archive is hygiene-adjacent (🟡), not a 不要 violation.

## Issues

### Issue 1 -- Severity: bug
- File: backtest/research/csv_minute_backtest.py:425
- Description: Branch `feat/hygiene-h1-fossils-contributing` is not an H1-only PR. Besides the H1 commit (`dba3c42`), it includes `40c5504` / `b1357f8` / `846c7ea`, which add and edit vectorized-engine code: `backtest/research/csv_common.py`, `backtest/research/csv_simulate_loop.py`, `backtest/research/csv_daily_backtest.py`, `backtest/research/csv_minute_backtest.py` (numba-gated `scan_held_day` starting at this line), `scripts/research/bench_scan_held_day.py`, `tests/test_scan_held_day_numba_parity.py`, `tests/test_presets_cross_repo_snapshot.py`, and `docs/backtest/plan-vectorized-hotpath-offload-2026-09-15.md`. H1 deliverables are only fossil archive + fossils README + README table + root CONTRIBUTING + broken-link fixes. `docs/backtest/engine-ashare-correctness.md` names `csv_daily_backtest.simulate` and `csv_minute_backtest.scan_held_day` as 成交核 modules, so these commits also violate H1 不要「不改成交核 / 策略书」even if framed as semantic-preserving refactors. They do **not** delete Cerebro, edit `csv_strategy_books.py` / `csv_ledger.py` / `market_layer.py`, or expand L2. Hygiene backlog already lists this work as a prior PR (#34) / H5, not H1.
- Suggestion: Split the engine/hotpath/presets commits onto their own PR (or rebase this branch onto that merge). Leave this H1 PR as `dba3c42` plus the H1 plan docs: fossil `git mv`, `_archive/fossils/README.md`, `docs/backtest/README.md` table, `CONTRIBUTING.md`, and fossil-link fixes.
- Status: open

### Issue 2 -- Severity: suggestion
- File: docs/backtest/_archive/plans/plan-strategy7-turtle-csv-minute-2026-09-11.md:8
- Description: Completed-plan archive (`20fc35e`) is hygiene-adjacent extra work, not an H1 deliverable. Live README/AGENTS/report links were retargeted, but this R100-moved plan still uses `(../architecture/reviews/...)`, which now resolves to the missing `docs/backtest/_archive/architecture/reviews/...` (404). Frozen `docs/architecture/reviews/**` prompts still cite pre-archive `docs/backtest/plan-*.md` paths as historical review titles (not live hrefs).
- Suggestion: Keep plan archive off the H1 PR. If it stays, retarget the strategy7 relative href to `../../../architecture/reviews/2026-09-11/plan-strategy7-turtle-csv-minute-2026-09-11/review-by-cursor.md` (or a root-relative link). Do not rewrite frozen review artifacts.
- Status: open

---

## Executor note (2026-09-15)

Grok 🔴 about engine/hotpath commits on the branch vs `origin/master` is **not treated as an H1 implementation defect**. Hygiene backlog lists PR #34 (hotpath / presets / simulate skeleton / plan archive) as **前置**; H1 commit `dba3c42` is docs-only (fossils `git mv` + CONTRIBUTING + README links). No follow-up fix for that 🔴. Plan-archive leftover relative link (🟡) is also outside H1 scope and left alone.
