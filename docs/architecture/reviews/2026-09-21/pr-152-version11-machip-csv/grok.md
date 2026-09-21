# Grok review — PR #152 version11 ma_chip CSV port (A–C)

> 日期：2026-09-21
> 角色：MyQuant-backtrader Grok 核（对抗复核；只审不合入）
> 对象：[PR #152](https://github.com/baiyibing/MyQuant-backtrader/pull/152) `feat/version11-machip-csv` → `master`
> 权威：[handoff-version11-codex-impl-2026-09-21.md](../../../../backtest/handoff-version11-codex-impl-2026-09-21.md) · [plan-version11-machip-csv-2026-09-21.md](../../../../backtest/plan-version11-machip-csv-2026-09-21.md) v1.0 GO · 人裁 [契约日/周线](https://github.com/baiyibing/MyQuant-backtrader/pull/152#issuecomment-5756447597) · [volume=A](https://github.com/baiyibing/MyQuant-backtrader/pull/152#issuecomment-5756590614)
> HEAD：`6c198eb8e24d8dac66a6f016650358cbef5a71ab`（A–C code tip `c9b4380` + D STOP note；本评审文件叠在其后）
> merge-base：`32b78b1`（= origin/master Merge #154 ma_infra）
> GitHub：`MERGEABLE` / `pytest-and-gates` **SUCCESS**（[run 35572119655](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35572119655) @ `c9b4380`：1477 passed, 5 skipped, 24 deselected）
> 先前 tip `f5a0dd9` 同 job **FAILURE**（[35571555382](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35571555382)：8 failed, 全在 `test_export_strategy11_pool.py`）
> 本核 **未 merge**。CI 绿 **不是** 合入条件。

---

## 结论

**Verdict: PASS_WITH_NITS**

Slices A–C encode the four locked human cuts and handoff §0. Shared-engine edits stay behind v11 opt-in hooks. Slice D is a recorded STOP (no 4090 route / archives not on the box) and is **not** a fail reason. The first reviewed tip (`f5a0dd9`) failed the data-free gate on CI pandas 3; `c9b4380` closed both failures with writable copies + `datetime64[ns]` asof keys, and CI is green. Remaining items are nits plus host Slice D.

Do not merge on this review. Tip bt for the human cut; D may continue in parallel.

---

## Scope

**PASS** (research v11 + handoff-allowed wiring). vs `origin/master` after `c9b4380`: the A–C set plus a two-file CI portability patch.

| Path | Role |
|---|---|
| `backtest/research/strategy11_rules.py` | new A: edge / two-stage FSM / HELP_LOCK |
| `scripts/data/export_strategy11_pool.py` | new B: front exporter (+ writable grid mask in `c9b4380`) |
| `tests/test_strategy11_{rules,engine}.py` `tests/test_export_strategy11_pool.py` | new data-free pins |
| `backtest/research/csv_strategy_books.py` `tests/test_csv_strategy_books.py` | register `11/v11/version11` + FORBIDDEN |
| `backtest/research/ma_infra.py` | keyword-only `prefix_equivalent=False` (cut 2) |
| `oskh_factors/bridge/turnover_resist.py` | V7 `circulating_capital_asof` (+ writable buffer / ns keys in `c9b4380`) |
| `csv_{daily,minute}_backtest.py` `csv_simulate_loop.py` `csv_ledger.py` `ashare_bars.py` | C wiring behind `minute_open` / `eod_exit` / `skip_sold_today` / `include_volume` / `execute_buy(at=)` |
| `AGENTS.md` + plan/handoff | A–C transplanted; D still pending |

Not in the diff: `strategy1`–`strategy10` / `8.x` rule modules, Mode A/B libraries or production defaults, `qlib_cost`, Cerebro, `stock_pool/` writes, live packages. `test_ashare_simulate_import_fence.py` still lists the same hot-path names; no new qlib / LEBS / fill-clock imports.

Shared-engine behavior for books 1–10 is opt-in:

- `run_eod_exits` returns immediately unless `eod_exit` is callable (only v11 apply returns it).
- `sold_today` is applied only when `hooks["skip_sold_today"]` is set.
- `execute_buy(..., at=None)` still clamps with `bucket_id` (bucket-close default).
- `read_lake_minute_ohlc` / `load_minute_ohlc` keep the volume-free cache path unless `include_volume=True`.
- `_empty_stats` only dropped **duplicate** `skip_add_loser` / `skip_index_gate` keys that already existed earlier in the same literal on master. Same zeros.

CLI side effect (nit, not a fill default): `add_csv_strategy_arg` now has `type=normalize_csv_strategy`, so `--strategy 11` (and `--strategy 1`, …) resolve. Needed for the v11 alias DoD.

`c9b4380` is research-only (exporter + V7 shell). It does not change cap defaults, books 1–10, or Mode A/B.

---

## Human cuts (locked on the PR)

| # | Cut | Encoded? | Evidence |
|---|---|---|---|
| 1 | T strictly after D; D→T ≤4 calendar days; stale from original D; exporter ≤T−1 written at T | **YES** | `contract_day` uses `bisect_right` (never D). `(boundary-D).days > 4` → `skip_buy(stale)` with `original_signal_day` / no pool row. Pin: D=`20240105` → T=`20240108`/`20240109` ok, `20240110` stale. Changing T OHLC does not change the pool row; changing D close does. |
| 2 | Weekly SMA A prefix-equivalent via explicit ma_infra opt-in; default full-history unchanged | **YES** | `weekly_sma_series(..., *, prefix_equivalent=False)`. Default still `[None, None, None, 17, 17, 27]` (same pin as `test_ma_infra.py`). Opt-in `[None, None, 16, 17, 26, 27]` and equals truncate-then-call; future perturbation of later closes leaves the prefix head unchanged. Exporter calls `prefix_equivalent=True` only. `weekly_sma_asof` still uses the default series. |
| 3 | Volume cut A: unfinished 09:30 bucket → buy skip / pending sell defer; `bucket<=at`; no same-minute completed-volume exception | **YES** | Minute v11: `bucket_id=570`, `volume_at=569`. `VolumeCap.clamp` still rejects `not bucket <= at` **before** lookup. Tests: lookup never called, cash / shares / `cap.used` unchanged, `skip_volume_unavailable:bucket_not_completed`. Missing/zero/NaN open: no later-minute retry. Cap-off still fills. Cap implementation / other-book defaults untouched. |
| 4 | `apply()` returns `limit_up_chase=False` explicitly + chase queue empty after limit-up block | **YES** | Raw `book.apply()["limit_up_chase"] is False` **before** `setdefault(..., True)`. Both engines: actual `pending_chase == {}`, `chase_pending_eod==0`, `skip_limit_up==1`. `take_profit` / `record_params` present. |

Process: STOP comments for the contract-day/weekly fork and the volume fork; no self-adjudication. Docs-first `4729628` then A `e560a44` / B `9133ca8` / C `f5a0dd9` / CI fix `c9b4380`.

---

## Handoff §0 hard boundaries

| # | Boundary | Verdict |
|---|---|---|
| 1 | Signal price domain = front; execution stays engine none + `mapped_prev_close`; manifest `adjust_type` | **PASS.** Loader reads `dividend_type=front`. Manifest pins `adjust_type=front`. Engines unchanged on the fill side. |
| 2 | Contract T (cut 1) | **PASS.** See cut 1. Right-censored `awaiting_contract_bar` (≤4 days, no T yet) is counted, not written; stale from original D when the observed horizon exceeds 4. |
| 3 | `compute_cyqk_series(window=200)` live; two-layer failure; grid precheck 250k; no store `cyqk_t` | **PASS.** No store columns. Grid `span > 250_000` (equality allowed). Window-local NaN vs per-symbol `ValueError` have distinct counters. Rust length mismatch is `PyValueError` (`lib.rs:109-112`); exporter catches `ValueError` per code. Grid mask is now a writable copy (`c9b4380`). |
| 4 | Asof circulating_capital; public thin shell; forbid `date=None` | **PASS.** Raises on `dates is None`; missing file is visible; daily backward asof; non-positive → NaN. `c9b4380` copies the value buffer and unifies both merge keys to `datetime64[ns]`. |
| 5 | MA / BB / weekly = ma_infra series; no per-day `*_asof`; weekly explicit prefix | **PASS.** Exporter uses `bb_series` / `weekly_sma_series(..., prefix_equivalent=True)` / `sma_series`. `_weekly_sma_prefix_series` is private. `_daily_to_weekly` not newly exported (`daily_to_weekly` was already public from #150). |
| 6 | R9 `limit_up_chase=False` + take_profit / record_params | **PASS.** Cut 4. |
| 7 | Universe: filter ST + drop 688; seed-30 no ST filter | **PASS.** `board_of` keeps 60 / 000-003 / 300-301 only (688/689/BJ out). Universe requires names and uses `is_st_name`; seed-30 keeps `*ST`. |
| 8 | Drop volume==0 bars before T; stats-window edges masked | **PASS.** `prepare_frame` drops volume==0 so a zero-volume day cannot be T (falls through to stale in the pin). `day < max(start, 2024-01-01)` skips export. |
| 9 | Daily `pending_exit` as-is; minute 09:30 first open, limit-down defer | **PASS.** Daily still sells pending at open via `t1_sellable`. Minute v11 only sells at exact `hm==570` open; missing open does not borrow 09:31/14:55; limit-down / zero-volume / unfinished bucket keep pending. |
| 10 | Pool CSV contract + refuse `stock_pool/` | **PASS.** `YYYYMMDD.csv`, bare six-digit, LF, no BOM/NUL; `rejected.csv` + `manifest.json` live in `out-dir`, not `pool/`; non-empty pool refuses overwrite; `FORBIDDEN_DEFAULT_STOCK_POOL` includes `version11`. |
| 11 | `--help` prints P0 positioning, contract-day, skip names, pyd `__file__` | **PASS (engines).** Dual CLI `--strategy 11 --help` pins `非已验证多头` and `volume=A`. Exporter uses `HELP_LOCK` as epilog and writes `pyd_file` into the manifest. Exporter `--help` itself is not unit-pinned. |
| 12 | Do not change books 1–10 / 8.x / 12 / Mode A/B; full pytest green; new-file ruff | **PASS on pytest green @ `c9b4380`.** Book rule modules and Mode A/B are untouched. Ruff is not a separate CI step; implementer reported local ruff green. This VM has no vanna312 to re-check ruff. |

Other §0 / slice notes that hold:

- P0 copy is in `HELP_LOCK` (`cyqk>0.70` 抛压区 / 框架验证非已验证多头).
- P1 a/b: daily fill at T close (`9.8`); minute at 09:30 open (`10.2`).
- EOD after sells → buys → step-adds; v11 `ALLOW_ADD=False` so step-adds are inert. SMA5 includes T (`15.8` pin). Buy-day `t1_sellable` blocks same-day sell. sold-today blocks re-entry (`skip_sold_today==1`).
- qlib_1min rejected when `volume_required`; lake volume opt-in bypasses the old cache (`cache=off:volume_required`); missing file/column fails visible. Other books keep the old loader.
- No Cerebro import; no hardcoded drive letters; resolvers only.

---

## Number / pin integrity

**PASS** at `c9b4380` (CI executed the pins that were dark on `f5a0dd9`).

| Pin | Value |
|---|---|
| SMA5 includes today | `[20, 20, 20, 9, 10]` → `15.8` (not yesterday-only 17.25) |
| Default weekly SMA2 | `[None, None, None, 17, 17, 27]` (unchanged vs `test_ma_infra`) |
| Prefix weekly SMA2 | `[None, None, 16, 17, 26, 27]` = truncate-then-call |
| Contract boundary | D=`20240105`; T+3/`20240108` and T+4/`20240109` accept; T+5/`20240110` stale |
| Dual clock | daily BUY `9.8` (T close); minute BUY `10.2` (T open); next-day SELL `10.1` |
| Grid equality | `(max−min)/0.01 == 250000` is allowed (`>` not `>=`) |
| Window-local NaN | `shares[2]=nan` → `cyqk[199:202]` NaN, finite from 202 |
| Stale audit | `date == original_signal_day == 20240208`, `contract_day == 20240220`, no pool row |
| Pool bytes | `b"000001\n600001\n"`; no NUL/CR/BOM |
| Chase | raw flag `False`; live chase dict `{}` after 一字涨停 |

CI @ `c9b4380`: **1477 passed** = the previous 1469 + the eight exporter tests that failed on `f5a0dd9`. Implementer vanna312 claim was **1480 passed, 2 skipped**; CI skip count is 5 (pre-existing env delta, not a v11 pin miss).

This reviewer VM has no `vanna312` / pandas / pytest. Execution evidence is the GitHub job.

New sources: UTF-8, no BOM, NUL=0; `git diff --check` clean.

---

## Slice D

**STOP recorded, honest, not a fail reason.**

`6c198eb` + [slice-d-version11-seed30-universe-2026-09-21.md](../../../../backtest/reviews/slice-d-version11-seed30-universe-2026-09-21.md): box-scoped executor cannot route to `newtest_4090`; `backtest_output/ma_chip_edge_*` is absent on the searchable box/git surfaces (gitignored, never in tree). No seed-30 export, no engine run, no universe sensitivity, no pyd identity. Plan/handoff now say **D 尝试 STOP**, not smoke-complete, no return/parity claim.

That matches the review bar: do not FAIL solely for missing Slice D when A–C are complete and D is honest.

Host risk once D starts: `circulating_capital_asof` matches `stock_code` exactly with no `to_canonical_symbol`. If `free_float_shares.parquet` uses a different code shape than the front lake, every window goes NaN.

---

## Closed on this tip (were blockers at `f5a0dd9`)

`c9b4380` is the right patch and is research-scoped.

1. **Read-only `to_numpy()` writes (pandas 3 CoW).** `grid` is now `np.array(..., dtype=bool, copy=True)` before `grid[:window-1] = False`. Asof values use `to_numpy(dtype=float, copy=True)` before the NaN mask. CI no longer raises `assignment destination is read-only`.
2. **`merge_asof` ms vs us.** Both asof keys are `.astype("datetime64[ns]")` before merge. `test_front_loader_and_cli_manifest` is in the 1477-pass set.

No remaining data-free execution blocker on the current tip.

---

## Nits

1. Shared `import x as x` / unused-import churn in `csv_daily_backtest.py` / `csv_minute_backtest.py` / `csv_ledger.py` is review noise. Behavior-neutral.
2. `_empty_stats` de-duplicated two repeated keys. Harmless; belongs in a janitor commit, not a v11 slice.
3. `add_csv_strategy_arg(type=normalize_csv_strategy)` makes `--strategy 1` work for every book. Needed for `--strategy 11`; not a fill/scan/fee change.
4. Prefix-weekly pins live in `tests/test_export_strategy11_pool.py` rather than `tests/test_ma_infra.py`. The default pin is duplicated in both; fine, just easy to miss.
5. Exporter `--help` is a handoff gate and is not unit-pinned (engine help is).
6. Plan text says `--sample seed=20240907`; CLI is `--sample [int]` with default `20240907`.
7. Universe ST without a name column **raises** instead of running and letting unnamed ST walk the 10% band. Fail-closed; stricter than the V9 warning. Acceptable.
8. `board_of` also drops 689 (with 688). Slightly tighter than 「排 688」.
9. `sma_series(closes[-5:], 5)` on a holding with fewer than five daily closes cannot fire the SMA5 exit (returns None → HOLD). Production warmup is 200+ bars; only a short synthetic window would hit it.
10. AGENTS 1–10 one-liners still omit `version11`; the dedicated bullet is enough.
11. `c9b4380` copies the CoW buffer rather than computing the warmup grid with `min_periods=window` (which would make the first 199 flags false without a write). Equivalent; the copy is enough.
12. Handoff / plan still quote vanna312 **1480 passed, 2 skipped**. CI @ `c9b4380` is **1477 passed, 5 skipped**. Same eight exporter tests now pass; skip-count delta is pre-existing, but the page header should not keep the local count as the gate SSOT.

---

## What is solid (do not regress)

- Edge: D true and previous observed bar false; both finite; `cyqk > 0.70` and all MA/BB compares strict; D−1 NaN ≠ edge; staying-true does not re-fire.
- Exit FSM: entry close `<=` prev → next-open pending; green → HOLD and do not re-test red; SMA5 includes T; pending persists; `take_profit` is None (no intraday sell).
- EOD hook uses `day_bar_and_prev_closes` (prior closes only) then appends T close; `mapped_prev_close` sees T−1. Buy-day cannot sell.
- Volume A: `clamp` `bucket<=at` is unchanged and is invoked with `at=569` only on the v11 open path; lookup is not consulted; no 09:31/EOD borrow; cap-off path unchanged.
- Chase: explicit `False` in the apply dict beats `setdefault(True)`; both engines pin the live queue object, not just a stat.
- Pool fence; UTF-8 / LF / NUL=0 on new sources.

---

## CI

| Gate | Status |
|---|---|
| `pytest-and-gates` @ `f5a0dd9` | **FAILURE** ([35571555382](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35571555382)) — 8 exporter tests, pandas 3 CoW + merge_asof units |
| `pytest-and-gates` @ `c9b4380` | **SUCCESS** ([35572119655](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35572119655)) — **1477 passed**, 5 skipped, 24 deselected |
| Contract path / TR-bridge gates | Succeeded on the green job (they run before pytest) |
| Ruff / exporter `--help` / dual `--strategy 11 --help` | Not a separate CI step; implementer reported local green |

---

## Verdict

**PASS_WITH_NITS.** Human cuts 1–4 and handoff §0 A–C wiring are encoded. Slice D STOP is honest. The `f5a0dd9` data-free CI red was real and is closed at `c9b4380`. Nits are non-blocking.

Do not merge on this review.
