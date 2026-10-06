# RB-04 per-purpose book capability truth table

ZERO-DIFF for every book registered at tip `9dd59b0`. Both purposes require
`sizing == "per_name"`.

| Purpose | Explicit membership | Consumers |
| --- | --- | --- |
| Price-add eligibility (51) | `version6_1` through `version6_47`, `version8`, `version8_3`, `version8_4`, `version8_5` | Daily price adds; minute split group scan |
| S8 independent binding (53) | Price-add names plus `version8_2`, `version8_6` | Independent position binding and short-cash default |

MC-5: price-add ≠ independent. `version8_2` and `version8_6` are
independent-only. `version6`, `version8_1`, and minute-only `version7`
have neither capability. None/empty names and non-per-name sizing return false.

The source of truth is
[`book_capabilities.py`](../../backtest/research/book_capabilities.py).
New books must be explicitly added to the relevant frozenset(s); no
`startswith`, regex, or automatic family inheritance. The ledger retains its
public helper signature through a thin delegate. Registered-book equivalence
and admission guards live in `tests/test_rb04_book_capabilities.py`.

RB-04 adds no other capabilities, module split, CI gate, or lake backtest.
