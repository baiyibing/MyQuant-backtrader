# dissent-steelman adversarial lane review

## Conclusion

**BLOCKING as written.**  
The delta split in §3 is reasonable, but §§2/4/5/8 still allow non-executable acceptance and ambiguous fee/stamp wording.

## Findings (`file:line`)

1. **Ghost acceptance scripts in §8 conflict with "real scripts only".**
   - Plan invokes `scripts/run_common_package_contract_gates.py` and `scripts/run_stream_execution_contract_bundle.py` (`docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:160`, `:163`).
   - Neither file exists in this branch (workspace glob check: 0 matches).
   - Actual CI contract-gate path uses existing `scripts/gates/verify_*.py` (`.github/workflows/python-tests.yml:40-43`).

2. **"stamp-tax explicit contract" overstates research as-built behavior.**
   - Plan framing uses fee/stamp language (`docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:4`, `:66`, `:94`).
   - Research ledger books only `commission` at buy/sell charge points (`backtest/research/csv_ledger.py:211`, `:229`, `:244`, `:254`).
   - Research fee SSOT explicitly keeps stamp/transfer in live policy module (`backtest/research/ashare_fees.py:9-10`).

3. **Daily override vs minute/v7 asymmetry is true but under-locked by §8 quick tests.**
   - Daily has explicit override knobs (`backtest/research/csv_daily_backtest.py:230-232`, `:272-280`, `:683-685`).
   - Minute simulate does not expose override knobs; state inherits defaults (`backtest/research/csv_minute_backtest.py:520`, `backtest/research/csv_simulate_loop.py:102`, `backtest/research/csv_ledger.py:87-89`).
   - v7 uses explicit `FeeSchedule` default injection (`backtest/research/csv_minute_backtest_v7.py:204`, `:225`, `:279`).
   - §8 quick tests currently list only fees + import-fence (`docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:149-151`).

4. **IMPLEMENTATION_BASE enforcement in §8 is weaker than F-R8 intent.**
   - F-R8 requires fetched `origin/master` tip semantics (`docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:85`).
   - Commands only validate shape/existence/ancestor (`:144-146`) and do not compare against current `origin/master`.

## Independent verdict on §3

**Conditional pass only after errata.**  
Keep delta1-only scope, but §8 must be executable, fee/stamp wording must match as-built commission booking, and asymmetry checks must be explicitly pinned.

## Unverified

- No command execution from §8 in this review (docs-only pass).
- No claim on runtime pass/fail; static evidence only.
