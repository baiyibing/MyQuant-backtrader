# Minute `simulate()` hotpath profile（2026-09-15）

This is a measure-first synthetic profile of the real
`backtest.research.csv_minute_backtest.simulate()` orchestration path. It does
not read the F lake and does not change sell rules or backend defaults.

## Reproduce

```bash
python scripts/research/bench_minute_simulate_hotpath.py
CSV_SCAN_HELD_DAY_BACKEND=numba python scripts/research/bench_minute_simulate_hotpath.py
```

Scenario: version8, 30 trading days, 16 codes, 240 minute bars/day, pool buys
on 10 days (10 lots/code), three measured repetitions after warm-up. Host:
`/workspace/vanna312/bin/python`, 2026-09-15. Synthetic figures are research
evidence, not a production SLA.

| phase | default request | numba request |
|---|---:|---:|
| `simulate()` / run | 1,218.48 ms | 1,230.32 ms |
| sell scan | 75.51% | 75.25% |
| chase | 0.01% | 0.01% |
| pool buy | 4.99% | 4.83% |
| ledger / mark | 0.88% | 0.89% |
| orchestration remainder | 18.61% | 19.02% |
| nested day slice | 1.17% | 1.22% |
| nested previous-close prep | 4.76% | 5.03% |

Nested rows are already included in sell/chase/pool and must not be added to
the top-level percentages. Both runs ended with 160 live lots, 160 buys and
320 records including EOD marks.

## Backend finding

The scan backend actually used by `simulate()` is **Python** in both runs.
The dispatcher rejects the optional numba trail kernel because `simulate()`
passes a non-`None` `reserve_state` for every lot; version8 also supplies a
`take_profit` callable. Therefore setting `CSV_SCAN_HELD_DAY_BACKEND=numba`
alone cannot accelerate this real scenario. The standalone
`bench_scan_held_day.py` numba result does not represent this orchestration.

## At most two follow-up candidates

1. Cache each code/day's previous close and close-history list once, then reuse
   them across lots and sell/chase/pool quote paths. Measure parity before and
   after; current nested preparation is about 5% here.
2. Prototype an optional compiled scan for explicitly supported built-in book
   contracts (including reserve/take-profit behavior), guarded by existing
   Python parity tests. Do not make it default until real-`simulate()` parity
   and representative profiles pass; sell scan is about 75% here.

No optimization is implemented in this slice.
