## Summary

H3 is docs-only and meets the fence: `AGENTS.md` Scope now states `l2_analytics/` and `scripts/run/run_l2_*` are offline research analytics (CSV→Parquet ETL / aggregates / DuckDB), explicitly not LEBS / MockQMT / trading stack, not for wiring new CSV strategy books, and not a path to grow live packages. Root `README.md` Layout row and `docs/backtest/README.md` Hygiene line reinforce the same boundary. `plan-hygiene-backlog` marks H1/H2/H3 ✓; `plan-h3` status is 已实施. `git diff` for the implement commit touches only those markdown files — no `l2_analytics/` or `run_l2_*` code. Spot-check: no strategy-book / LEBS / MockQMT / `live_trading` imports under `l2_analytics/` or `scripts/run/run_l2_*.py`. No valid 🔴 (no scope ambiguity that would imply L2 can become a trading/strategy surface).

## Issues

### Issue 1 -- Severity: suggestion
- File: README.md:33
- Description: Layout still groups `scripts/research/` `scripts/data/` `scripts/tr/` as 「chip / TR / L2 研究 CLI」, while the H3 fence and `run_l2_*` live under `scripts/run/`. Mild path blur for newcomers; does not override the AGENTS fence.
- Suggestion: Optionally retarget the L2 CLI mention to `scripts/run/` (or add `scripts/run/` to the Path cell) so Layout matches the fence wording.
- Status: open

### Issue 2 -- Severity: nit
- File: README.md:24
- Description: Role cell mixes CN/EN (`离线分析 only`). Clear enough; style only.
- Suggestion: Prefer all-CN, e.g. `L2 仅离线分析（ETL / 聚合；不扩交易核 / 策略书 / LEBS）`.
- Status: open

## Checklist vs plan

| Plan item | Result |
|-----------|--------|
| AGENTS Scope fence | Present; covers offline-only + not LEBS/MockQMT + no new CSV books + no live growth |
| README `l2_analytics/` row | Updated |
| Optional hygiene line | Present in `docs/backtest/README.md` |
| Backlog H1/H2 done, H3 done | ✓ marks on H1–H3 |
| No L2 code / strategy / Cerebro / fill-engine edits | Confirmed |
| Push / CloudAgent | Not done |
