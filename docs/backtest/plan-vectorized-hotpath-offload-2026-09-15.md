# Plan: vectorized hot-path operator offload

> **状态**：📄 **v0.1 · 进行中**（2026-09-15）。无 F 湖本机不可跑全市场湖回测；先锁静态热点 + microbench。
>
> **定位**：[engine-positioning-ssot.md](engine-positioning-ssot.md)。主引擎：`csv_daily_backtest.py` / `csv_minute_backtest.py`。**禁止 Cerebro 重写。**

## 1. Measured / static hotspots

| Site | Shape | Evidence |
|------|--------|----------|
| `csv_minute_backtest.scan_held_day` | Pure Python `for i in range(n)` over numpy OHLC(+hm) | Static: called once per held lot per day inside `simulate()`; bar count ≈ session minutes (~240). Microbench: `scripts/research/bench_scan_held_day.py` |
| `csv_daily_backtest.simulate` | pandas `.loc` per day × position | Static: day loop + per-code bar lookup; lower bar cardinality than minute but Python-heavy |
| Lake load / pool parse | I/O + threads | Out of scope for this plan (no F lake on some hosts) |

Success for this slice does **not** require a full-lake NAV run.

## 2. Ranked offload candidates

1. **numba on `scan_held_day` trail path (first)** — already in `requirements.txt`. Gate with `use_numba=` or `CSV_SCAN_HELD_DAY_BACKEND=numba`. Python reference remains default. Callables (`sell_gate` / `take_profit`) and `reserve_limit_up` stay on Python (no sell-semantics change for 6/8 books that inject `take_profit`).
2. **Daily mark micro-opt (H5)** — done: per-code `market_close_mark` cache in `append_equity_and_eod_marks`; sell-loop `.loc` still later; do not merge daily+minute `simulate()` in the same PR.
3. **Rust extension** — only if numba plateaus and profiles still show scan-bound; prefer thin `pyo3` kernel matching the Python reference fixtures.

## 3. Success criteria

- Microbench prints Python (and numba when available) timings on synthetic sessions.
- Unit test: numba vs Python agree on a few fixtures; skip gracefully if numba missing.
- Default engine path unchanged (Python); no Cerebro edits; no strategy 6/8 sell-book changes; no download reintroduction.

## 4. What NOT to do

- Do **not** rewrite or resurrect Cerebro / Rolling as the research engine.
- Do **not** delete Cerebro modules — fossil gate / docs / archive only.
- Do **not** change sell semantics of strategies 6 / 8.
- Do **not** big-bang merge the two `simulate()` functions here.
- Do **not** reintroduce market-data downloads in this fork.

## 5. Delivered with this plan

- This document
- `scripts/research/bench_scan_held_day.py`
- Optional numba trail offload behind env/kwarg + `tests/test_scan_held_day_numba_parity.py`
- H5: `market_close_mark` + per-code cache in `append_equity_and_eod_marks`; `scripts/research/bench_daily_mark.py`; `tests/test_daily_mark_cache.py`
