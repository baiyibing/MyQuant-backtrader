I'll review commit 831db35 on `feat/minute-simulate-profile` against the measure-only simulate() hotpath scope. Loading the review skill and inspecting the commit first.Reviewing commit `831db35` on `feat/minute-simulate-profile` (single-commit scope, not the whole branch). Loading the reviewer persona and collecting the diff.Setup is ready. Next I’ll confirm the commit, collect its diff, and launch the reviewer.Collected the commit diff (5 files, 267 insertions). Launching the reviewer against the measure-only simulate() checklist.I'll start by reading the diff, changed-file list, and the key source files so the review can verify the six required checks against the actual code.The diff is a measure-only bench plus a one-line `_previous_rows` extract. Next I’ll read `simulate()`, the scan dispatcher, and the new bench so the six checks can be verified against the call graph.I have the dispatcher and simulate() locations. Next I’ll read those functions plus the isolated bench, path-gate, and CI wiring.`run_chase_due_day` lives in `csv_simulate_loop.py`, so I need to confirm how `simulate()` binds it—setattr on the module only works if those names are looked up there.I need `_named_limits` and buy/trade accounting next, to confirm the 160/160/320 outcome and that synthetic `SYNTH-*` names don’t skip the board.I’ll confirm `simulate()` does global name lookup (so setattr intercepts), then run a tiny synthetic bench for the 160/160/320 accounting.Reviewer is running. I’ll gather CI and path-gate context so I can process findings as soon as it returns.Call graph and accounting check out. I’ll write the structured review notes next.Review written to `/tmp/grok-box/grok-review-9079f13d.md`.

Issue counts: 0 bug, 1 suggestion, 0 nit.

Verdict: **APPROVE**

The change is measure-only: real `simulate()` orchestration, setattr intercepts via `LOAD_GLOBAL`, numba correctly reported as rejected because every lot gets a non-`None` `reserve_state` plus version8 `take_profit`, and `_previous_rows` is an identity extract. 160/160/320 matches the engine. The one suggestion is that nested day-slice/prev-close on the sell loop sits in orchestration remainder, not inside `sell_scan`.Review complete. Processing findings…Found 1 issue (0 bugs, 1 suggestion, 0 nits). Wrote `/tmp/grok-box/grok-review-9079f13d.md` and `/tmp/grok-box/grok-review-summary-9079f13d.md`.

# Review: commit `831db35` on `feat/minute-simulate-profile`

**Verdict: APPROVE**

Measure-only profile of real `csv_minute_backtest.simulate()` orchestration. Production sell/buy/chase/ledger semantics are unchanged. No blocking 🔴.

**Target:** `831db35` (`bench: profile minute simulate hotpath`) vs parent `5ccfdd3`  
**Diff:** 5 files, +267 / −3

## Checklist

| Check | Result |
|---|---|
| 1. Real `simulate()` orchestration | **Pass.** Bench calls `sim.simulate(...)` (version8, multi-day/code/lot). `setattr` intercepts via `LOAD_GLOBAL`. Not the isolated `scan_held_day` kernel. |
| 2. Timings / backend / `reserve_state` | **Pass**, with one grouping caption issue. Backend report matches the dispatcher: Python because every lot gets non-`None` `reserve_state` and version8 supplies `take_profit`. Wrappers still call the real dispatcher. |
| 3. ≤2 candidates; opts not implemented | **Pass.** Two candidates only; no cache and no compiled reserve/take-profit kernel. |
| 4. Profiling seam / no sell drift | **Pass.** Sole production edit is `_previous_rows` = `df.loc[df.index < day]` at three `simulate()` sites. |
| 5. Tests / no lake / no CI | **Pass / adequate-as-absent.** Synthetic pandas only; not in pytest or `.github/workflows/python-tests.yml`. Path gate does not scan this doc host line. |
| 6. Blocking 🔴 | **None.** |

## Issues

No 🔴.

**[suggestion]** `scripts/research/bench_minute_simulate_hotpath.py:189` (also `docs/backtest/minute-simulate-profile-results-2026-09-15.md:30`)

The caption says nested day-slice / previous-close prep is already inside sell/chase/pool. That is true for chase and pool quote callbacks. It is false for the sell loop: `_slice_day` / `_previous_rows` run in `simulate()` at `csv_minute_backtest.py:833-836` *before* `scan_held_day` (`:852`), so those times sit in orchestration remainder, exclusive of `sell_scan`. Phase percentages and the two candidates remain valid.

**Fix:** Split the caption into “sell-loop (in orchestration remainder) vs chase/pool (inside those wrappers)”. Keep the “do not add nested rows to the top-level percentages” warning.

## Files reviewed

- `backtest/research/csv_minute_backtest.py`
- `scripts/research/bench_minute_simulate_hotpath.py`
- `docs/backtest/minute-simulate-profile-results-2026-09-15.md`
- `docs/backtest/README.md`
- `docs/backtest/plan-brainstorm-next-heavy-2026-09-15.md`

Full notes: `/tmp/grok-box/grok-review-9079f13d.md`  
Summary: `/tmp/grok-box/grok-review-summary-9079f13d.md`

**APPROVE**
