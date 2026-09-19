# domain-safety adversarial lane review

## Conclusion

**BLOCKING until acceptance contract is fail-closed.**  
§3 scope isolation is good, but §8 acceptance currently contains non-runnable steps and does not fully pin fee-path asymmetry at test entrypoints.

## Findings (`file:line`)

1. **Acceptance path has a hard fail point (ghost script).**
   - Required command: `python3 scripts/run_common_package_contract_gates.py` (`docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:160`).
   - File absent in repository; CI instead runs existing `scripts/gates/verify_*.py` (`.github/workflows/python-tests.yml:40-43`).

2. **Research path is commission-only booking; no explicit stamp line.**
   - Buy/sell bookings write `"commission"` only (`backtest/research/csv_ledger.py:229`, `:254`).
   - Fee debit/credit uses `trade_commission` (`backtest/research/csv_ledger.py:211`, `:244`).
   - `ashare_fees` boundary text keeps stamp/transfer out of research hot path (`backtest/research/ashare_fees.py:9-10`).

3. **Asymmetry (daily override vs minute/v7 defaults) is real and should be explicitly validated in quick-test set.**
   - Daily override wiring exists (`backtest/research/csv_daily_backtest.py:230-232`, `:272-280`, `:683-685`).
   - Minute uses default-initialized `SimState` from shared loop (`backtest/research/csv_minute_backtest.py:549`, `backtest/research/csv_simulate_loop.py:102`).
   - v7 default fee injection via `FeeSchedule` (`backtest/research/csv_minute_backtest_v7.py:24`, `:279`).
   - Current quick tests do not include predicate/asymmetry surface (`docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:149-151`).

4. **F-R8 tip-lock text and shell checks are not equivalent.**
   - Lock text requires fetched tip provenance (`docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:85`).
   - Shell checks prove only ancestor relation (`:146`), not equality with `origin/master`.

## Independent verdict on §3

**Pass intent / fail execution.**  
delta1-only split is acceptable, but the acceptance workflow must be made runnable and safety wording must mirror current as-built accounting.

## Unverified

- No dynamic verification of T+1/limit branches beyond static source reading.
- No test execution in this docs-only review pass.
