# H-RB-06 / RB-11 synthetic profiling harness — 2026-10-06

ZERO-DIFF: this adds only an opt-in measurement tool, tests and documentation.
No simulate/scan implementation, default outputs, CLI help, HELP_LOCK, books,
fixtures, baselines or numba fallback behavior changes. No lake is read.

## Inventory and reuse

`csv_minute_backtest.main` already records `t_pool_s`, `t_daily_s`,
`t_minute_s`, `t_sim_s`. Those are real-loader orchestration timers; this
synthetic harness does not call main or duplicate its loaders.
`scan_held_day` defaults to Python and supports existing `use_numba` / environment
opt-in with eligibility/fallback checks. Public `simulate` has no `use_numba`
argument, so this harness has no numba flag. It temporarily selects Python via
the existing environment setting and restores the prior value on exit.

Existing scripts include `bench_scan_held_day.py`, `bench_daily_sell_index.py`,
`bench_daily_mark.py`, `bench_minute_chip_hotpath.py` and
`bench_minute_simulate_hotpath.py`; the latter already builds deterministic
in-memory daily/minute frames and calls public `simulate`, like synthetic CSV
minute tests. RB-11 reuses its analytic builder rather than adding another
fixture generator. No RNG is used, so there is no variable seed.
The existing benchmark's function-wrapping timer is not needed: cProfile observes
the unmodified call graph. Existing chip profiling and TR bridge benchmarks
measure other workloads and are not duplicated.

## Run and report boundaries

```sh
"$OSKH_MERGE_PYTHON" scripts/research/rb11_profile_synthetic.py \
  --out-dir "<out-dir>" --names 16 --days 30 --minutes 240 --top 20
```

`--out-dir` is required; choose a disposable directory outside tracked outputs,
never `backtest_output` or tracked artifact paths. Only `profile.json` and
`profile.txt` are written there, replacing prior reports with those names.
JSON contains scenario, backend, stages, outcome and cumulative top-N entries.
Text contains cProfile top-N by cumulative time.

Input build includes frame conversion because the reused builder combines them;
`frame_conversion_s` is null rather than a fabricated independent timer.
`simulate_wall_s` includes profiling overhead, without warmup; scan cumulative
profile time is nested within it. Output assembly measures report construction,
not engine ledger assembly. cProfile captures engine assembly inside simulate;
it is not cleanly exposed as an independent wall stage. Output file I/O and
imports are excluded. Names/days/minutes and top-N are configurable; short minute
prefixes may miss the buying window, so the smoke test uses a full session.

## Ranked candidates from this session

One version6 run of the command above produced the following **synthetic,
machine-local, not representative** shares of profiled simulate wall time.
These are candidate investigation sites, not speedups or optimisation promises.
Cumulative values overlap (especially cursor advance and its callees), and
pandas `astype` aggregates multiple callers. Do not add these percentages.

| Rank | Candidate | Relative cumulative share |
| --- | --- | --- |
| 1 | `advance` | 78.74% |
| 2 | `_close` | 14.47% |
| 3 | `blocked_bar` | 4.73% |
| 4 | `astype` | 3.71% |
| 5 | `run_pool_buys_day` | 2.43% |
| 6 | `_previous_rows` | 2.02% |

The parent `scan_held_day` accounts for 85.23% on this synthetic workload.
Investigate cursor dispatch/state checks and close-phase logic first; then
bar blocking checks, pandas conversion/indexing, and pool/previous-row preparation.
The table ranks candidate functions only, excluding parent wrappers and generic
indexing aggregates. The JSON/text retain the full top-N ranking for review.

The optimisation knife is deferred to separately authorised **real-data
measurement plus parity/default-byte acceptance**. This PR authorises no hotspot
optimisation, no RB-12+, and no inference about production performance.

## Verification

Fast unmarked harness tests run a tiny synthetic case into tmp_path, check report
keys and nonzero buys/scan time, required output and size validation, environment
restoration, direct lake-import/host-path source fences (including the reused
builder), and a backtest-wide text fence against importing the harness.
The fence concerns source dependencies; normal standard-library/dependency
imports are required, but no market-data reader is called.
