## Summary

H2 correctly extracts `add_csv_backtest_common_args` into `csv_strategy_books.py` and rewires `csv_daily_backtest.main` / `csv_minute_backtest.main` without changing public flag names, dests, types, defaults, or per-flag help vs `9b52100^`. Reconstructing pre-H2 parsers and comparing argparse Action attributes plus `parse_args(["--strategy", "version6"])` namespaces showed **zero attribute diffs**; parse-after logic, `run(...)` kwargs, and artifact paths are unchanged, and `git diff 9b52100^..9b52100` does not touch simulate / sell / fill. Pytest with `/workspace/vanna312/bin/python` is green: **102 passed** in 0.86s. Remaining risk is coverage: the new smoke locks the helper in isolation, not the wired daily/minute parsers, so a future main-level wiring slip would not fail tests.

## Issues

### Issue 1 -- Severity: suggestion
- File: tests/test_csv_strategy_books.py:127
- Description: `test_add_csv_backtest_common_args_defaults_and_end_help` only exercises the helper with synthetic kwargs. It locks dest defaults for `--start/--end/--cash-total/--daily-quota/--workers/--pool-dir` and that *some* `--end` help string can be injected, but it does not inspect the parsers actually built by `csv_daily_backtest.main` / `csv_minute_backtest.main`. Gaps that would miss a real CLI drift: option strings vs dest-only asserts; `type=float`/`type=int`/`type=Path`; ratio flags (`--stop-pct`, `--profit-base`, `--trail-t*`) still registered; daily `--end` has no custom help while minute help is `f"minute lake last day is {MINUTE_LAKE_END}; ..."` (the test hardcodes `20260909` instead of `MINUTE_LAKE_END`); daily still has `--out-dir` and must not gain `--no-cache`/`--rebuild-cache`; minute still has the cache flags and must not gain `--out-dir`. `parse_args([])` exiting because `--strategy` is required is covered.
- Suggestion: Add a smoke that builds (or extracts) the real daily and minute mains' parsers and asserts Action `option_strings`/`dest`/`type`/`default`/`help` for every public flag, plus dest set difference for unique flags. Point the minute `--end` help assertion at `MINUTE_LAKE_END` as wired in `csv_minute_backtest.main`.
- Status: open

### Issue 2 -- Severity: nit
- File: backtest/research/csv_minute_backtest.py:44
- Description: After the helper swallowed `add_csv_strategy_arg` / `add_strategy6_ratio_args`, those two names are still imported from `csv_daily_backtest` and unused in this module (only `add_csv_backtest_common_args` is called). Daily must keep the re-exports because `tests/test_csv_daily_backtest.py` uses `sim.add_csv_strategy_arg`.
- Suggestion: Drop the unused `add_csv_strategy_arg` and `add_strategy6_ratio_args` imports from `csv_minute_backtest.py`.
- Status: open

## Parity table

Reconstructed from `git show 9b52100^` vs HEAD. Action attributes (option strings, dest, type, default, help, nargs, required, metavar) are bit-identical to pre-H2 for every flag. Unique flags moved after strategy/ratio args because the helper registers those internally; dests and parse results are unchanged. `csv_minute_backtest_v7.py` was not modified.

| Flag | Dest | Daily | Minute | Pre-H2 vs H2 |
|---|---|---|---|---|
| `--start` | `start` | default `"20251023"`, help `None`, no type | same | identical; shared |
| `--end` | `end` | default `"20260909"` (literal), help `None`, no type | default `MINUTE_LAKE_END` (`"20260909"` today), help `minute lake last day is {MINUTE_LAKE_END}; short parity window: 20251104` | identical to each pre-H2 side; **intended help/default divergence** |
| `--cash-total` | `cash_total` | `type=float`, default `DEFAULT_TOTAL_CASH` (`21000000.0`) | same | identical; shared |
| `--daily-quota` | `daily_quota` | `type=float`, default `DEFAULT_DAILY_QUOTA` (`1000000.0`) | same | identical; shared |
| `--workers` | `workers` | `type=int`, default `16` | same | identical; shared |
| `--pool-dir` | `pool_dir` | `type=Path`, default `Path(REPO)/"stock_pool"` | same | identical; shared |
| `--strategy` | `strategy` | required, `choices=csv_strategy_names()` | same | identical; helper still calls `add_csv_strategy_arg` |
| `--stop-pct` … `--trail-t5` | `stop_pct` … `trail_t5` | same ratio block | same | identical; helper still calls `add_strategy6_ratio_args` |
| `--out-dir` | `out_dir` | `type=Path`, default `None`, help `artifact directory; default backtest_output/csv_daily_{book}_{start}_{end}/` | **absent** | daily-only; same attrs; now registered *after* strategy/ratio (was before) |
| `--no-cache` | `no_cache` | **absent** | `store_true`, help `skip minute window cache` | minute-only; same attrs; now after strategy/ratio |
| `--rebuild-cache` | `rebuild_cache` | **absent** | `store_true`, help `reload lake and rewrite cache` | minute-only; same attrs; now after strategy/ratio |

Parse-after (unchanged on both sides): `resolve_research_pool_dir` → `run(...)` kwargs (`start`/`end`/`total_cash=args.cash_total`/`daily_quota`/`workers`/`pool_dir` + `csv_run_kwargs_from_args`; minute also `use_cache=not args.no_cache`, `rebuild_cache=args.rebuild_cache`) → `write_run_artifacts` (`resolve_csv_daily_out_dir(...)` vs `Path(REPO)/"backtest_output"/tag`).
