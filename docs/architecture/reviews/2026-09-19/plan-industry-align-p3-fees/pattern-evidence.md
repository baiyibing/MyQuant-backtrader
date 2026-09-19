# pattern-evidence adversarial lane review

## Conclusion

**Conditional accept with one blocking erratum.**  
§3 is mostly evidence-grounded, but §8 drifts from in-repo gate reality and the stamp-tax phrasing risks doc drift beyond the research implementation.

## Findings (`file:line`)

1. **Blocking: §8 uses non-existent bundle scripts while claiming "real scripts only".**
   - Plan text and commands (`docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:138`, `:160`, `:163`).
   - Files absent in repo; existing gate scripts are under `scripts/gates/` and are used in CI (`.github/workflows/python-tests.yml:40-43`).

2. **Stamp-tax wording is ahead of the as-built research contract.**
   - Plan language: "fee / stamp-tax explicit contract" (`docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:4`, `:66`).
   - As-built research path: commission-only trade records (`backtest/research/csv_ledger.py:229`, `:254`), with stamp/transfer boundary explicitly outside (`backtest/research/ashare_fees.py:9-10`).

3. **Known asymmetry claim is accurate and should be preserved (not normalized).**
   - Daily override knobs (`backtest/research/csv_daily_backtest.py:230-232`, `:683-685`).
   - Minute no in-file fee override knobs (`backtest/research/csv_minute_backtest.py:520`, `:549`).
   - v7 explicit fee object default (`backtest/research/csv_minute_backtest_v7.py:24`, `:279`).

4. **IMPLEMENTATION_BASE value itself is currently grounded.**
   - Plan lock value is full 40-char SHA (`docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:5`).
   - Fresh `git fetch origin master` in this review resolves the same SHA: `c65b10dd6d26342bd9ec1cbed5465d875f82470f`.

## Independent verdict on §3

**Accept structure, require wording and acceptance-script corrections.**  
Keep delta1 selected and delta2-5 deferred; fix §8 command realism and tighten fee/stamp wording to match anchored implementation.

## Unverified

- No claim that all acceptance commands currently pass, since commands were not executed.
- No assessment of external runbook docs outside this repository tree.
