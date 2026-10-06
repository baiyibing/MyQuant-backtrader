# RB-12 ledger operation matrix (ZERO-DIFF)

Evidence is code reading only. Paths below are relative to `backtest/research/`;
line numbers refer to this RB-12 revision. D = daily, M = shared minute, V = native
v7 selected at `csv_minute_backtest.py:682` (native `SimResult` constructed at :697).
D imports the ledger at `csv_daily_backtest.py:63`; M at `csv_minute_backtest.py:44`.
“Same” means the same expression through the same implementation, not numerical
similarity. No independent duplicate implementation is invented for D/M.

| Operation | Daily csv_ledger (Position :80 / IndependentPosition :95) | Minute shared books | v7 native |
| --- | --- | --- | --- |
| Buy fill cash debit | `csv_ledger.py:645`: `st.cash -= notional + comm`; same as M | `csv_ledger.py:645`; same as D | `strategy7_engine.py:224,293`, `ashare_fees.py:37–38`: `float(notional) + self.buy_fee(notional)`; not equivalent / not wired (conversion and charging boundary) |
| Sell fill cash credit | `csv_ledger.py:802`: `st.cash += notional - comm`; same as M | `csv_ledger.py:802`; same as D | `strategy7_engine.py:264`, `ashare_fees.py:40–41`: `float(notional) - self.sell_fee(notional)`; not equivalent / not wired (aggregate sold quantity and conversion) |
| Fee computation | `csv_ledger.py:625,640,800` → `ashare_fees.py:17` → `ledger_math.py:6`; same as M and V | Same D call sites and expression; fee estimates at `csv_simulate_loop.py:426,528,732` and `minute_cash_order.py:571` | `ashare_fees.py:31–35` → same leaf; literally identical fee body; existing aggregate invocation unchanged |
| Stamp / transfer tax | `ashare_fees.py:4–10,19–22`: bilateral or qlib schedule only, no separate tax expression; same as M | Same schedule; no separate tax expression | `strategy7_engine.py:209,240`, `ashare_fees.py:44–46`: same schedules; no separate tax expression; no tax wiring |
| Lot open | `csv_ledger.py:650–675`: Position/IndependentPosition constructor and append; same as M | Same implementation as D | `strategy7_engine.py:225–230,295–307`: native Lot and weighted cost/merge; not equivalent / not wired |
| T+1 sellable rollover | `csv_daily_backtest.py:403,411` → `ashare_session.py:39–41`: `buy_date < session`; same predicate as V; shared capped exits also gate `csv_ledger.py:784` | `csv_minute_backtest.py:974,1046` → same predicate; same as D/V; caller schedules retained | `strategy7_engine.py:242,254` → same predicate; native dated lots retained; no new wiring |
| Receivable / settlement | `ashare_exdiv_economics.py:108,121,130–137`; `csv_daily_backtest.py:348`, `csv_ledger.py:496`; same account math as M/V | Same account; `csv_minute_backtest.py:875`, `csv_ledger.py:496`; same arithmetic, distinct scheduling | Same account; `strategy7_engine.py:190,519`; same account arithmetic, distinct scheduling; no new wiring |
| Position close | `csv_ledger.py:844–860`: decrement, filter identity, delete empty code; same as M | Same implementation as D | `strategy7_engine.py:255–273`: kept native lots, recompute cost/pop; not equivalent / not wired |
| Independent position (S8) open / close | `csv_ledger.py:653–675,854–860`: identity, group construction / closed flag; same as M | Same implementation as D | `strategy7_engine.py:36–65,225–230,273`: no S8 independent group operation; not equivalent / not wired |
| Cash check (:272) | `csv_ledger.py:272–283`: `needed > available`, policy resolution then raise/False; same as M | Same implementation as D | `strategy7_engine.py:212–216`: `shares <= 0 or cost > state.cash`, skip event; not equivalent / not wired |

## Extraction boundary

Only `trade_commission` moved, verbatim, from the pre-RB-12
`ashare_fees.py:23–31` into `ledger_math.py:6–14`. It is an existing common
expression used by D/M fill calls and both FeeSchedule fee methods. Its guard,
float conversions, multiplication order, floor conversion and `max` order are
unchanged. `ashare_fees.trade_commission` remains an explicit re-export, including
its existing `__all__` entry. No direct engine call site changed. Native v7 reaches
the same function through its existing fee methods; no native cash/lot call site
was wired and aggregate sell fees remain aggregate.

All other rows stay at their call sites. The shared D/M state operations are
already common implementations; they are not pure leaves. Existing pure T+1
and account settlement contracts stay in their existing modules. Buy debit and
sell credit are not extracted across V because conversions and aggregate fee
boundaries prevent a verbatim extraction. Weighted lot updates and independent
position behavior are not equivalent / not wired. Cash checks retain exception
and short-circuit order. No day/minute schedule, default, fixture, HELP_LOCK,
book order or output contract is changed; no RB-13 work is included.
