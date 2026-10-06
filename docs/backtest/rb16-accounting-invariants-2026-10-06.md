# RB-16 accounting invariants and semantic localization (ZERO-DIFF)

RB-16 is opt-in post-run verification only. It does not change a simulator,
ledger, artifact schema, baseline, fixture, HELP_LOCK, or book registration.
The production-operation inventory is the existing
[RB-12 ledger operation matrix](rb12-ledger-operation-matrix-2026-10-06.md);
RB-16 states the conservation laws over those operations rather than creating a
second matching/fill oracle.

## 1. Production events and invariants

Current cash events are:

`cash_t = cash_(t-1) - buy notional - buy fees + sell notional - sell fees + posted receivables`

The shared daily/minute ledger debits a buy at
`backtest/research/csv_ledger.py:644-645` and credits a sell at
`backtest/research/csv_ledger.py:799-802`. Its fee is recorded on each fill at
`csv_ledger.py:688-706` and `csv_ledger.py:809-825`. Native v7 performs the
corresponding operations at `strategy7_engine.py:223-232` and
`strategy7_engine.py:263-265`. Current bilateral and qlib schedules include
their sell-side charge in `commission`; there is no separately exported tax
event, as recorded by the RB-12 matrix. Therefore “fees/taxes” are one exported
charge today and must not be split by this checker.

Cash dividends become receivables at
`ashare_exdiv_economics.py:106-124`, leave the receivable account exactly once
at `ashare_exdiv_economics.py:130-137`, and are credited to shared cash at
`csv_ledger.py:487-496` or native-v7 cash at `strategy7_engine.py:180-190`.
Entitlement is not cash; settlement is.

The invariant set is:

1. **Cash conservation.** Every observable fill transition obeys the equation
   above. Reported cash never goes negative. Receivable settlement is included
   only when the output frame explicitly exports it.
2. **Share conservation per name.** For each code, buys and corporate-action
   additions increase held shares and sells decrease them. A sell cannot exceed
   held shares. Share quantities are exact integers, with no float tolerance.
   Shared sells decrement the booked lot at `csv_ledger.py:841-849`; native v7
   removes sold quantities at `strategy7_engine.py:252-269`.
3. **T+1 availability.** Sellable shares are a subset of held shares and only
   lots acquired on an earlier session are sellable. The predicate is
   `ashare_session.py:39-41`; shared capped exits apply it at
   `csv_ledger.py:783-786`, and native v7 applies it at
   `strategy7_engine.py:240-258`.
4. **Non-negative accounts.** Cash, held shares, notional, and fees cannot be
   negative. Zero-share SKIP/DEFER/diagnostic rows are not fills.
5. **Equity identity.** `equity = cash + marked holdings + receivable`. Shared
   valuation adds cash, open lots, and receivables at
   `csv_simulate_loop.py:840-853`; native v7 does the same at
   `strategy7_engine.py:519-528`.

## 2. Path applicability

| Invariant | Daily shared | Minute shared | Native v7 | S8 independent positions |
| --- | --- | --- | --- | --- |
| Fill cash conservation / non-negative cash | Yes; same `csv_ledger` operations | Yes; same operations; execution audit can expose before/after cash | Yes; native operations; execution audit can expose before/after cash | Yes, per fill; no separate group cash account |
| Per-name share conservation | Yes, shared `Position` lots | Yes, shared `Position` lots | Yes, native dated `Lot` list | Yes; additionally partition by exported `position_id` so one signal group cannot fund another |
| T+1 sellable ≤ held | Yes | Yes | Yes | Yes per `position_id`; deferred group lots remain held |
| Non-negative shares/fees | Yes | Yes | Yes when fee-bearing audit rows are supplied | Yes |
| Equity identity | Yes in engine | Yes in engine | Yes; output has cash/holdings/equity | Same shared identity after summing all independent lots |
| Receivable identity | Yes in engine | Yes in engine | Yes in engine | Yes; receivable remains account-level, not per group |

The checker in `backtest/research/accounting_invariants.py` consumes existing
frames and returns `list[InvariantViolation]`. It performs no I/O and does not
raise for detected violations. It recognizes shared `code`/uppercase sides,
v7 `symbol`/lowercase sides, and fill-style `qty` or `executed_quantity`.
`position_id` activates S8 partitioning.

Float checks use absolute tolerances: cash `1e-6`, fee `1e-12`, notional
`1e-8`, and valuation `1e-6`. Shares and T+1 dates are exact. If
`receivable` is absent from a rich equity row, a non-negative
`equity - cash - holdings` is treated as an unexported receivable; it is not
silently treated as cash.

## 3. Existing baseline blind spots

The OFF baseline remains unchanged. It freezes canonical CSVs, final cash, full
structured state, and fill counts at
`scripts/research/generate_off_byte_baseline.py:430-440` and
`:480-513`. That is a drift detector, not an accounting proof: a consistently
recorded defect can match its golden state.

Observable gaps are:

- Shared daily/minute `daily_equity.csv` exports only `date,equity`
  (`csv_artifacts.py:359-360`), so standard run directories do not expose daily
  cash, holdings, or receivables for a full equation.
- Shared `trades.csv` has per-fill commission but no default before/after cash.
  Those fields exist only in the opt-in minute audit
  (`minute_audit.py:24-38`).
- Native v7 exports rich daily cash/holdings/equity, but its standard trade
  columns omit notional and commission
  (`csv_minute_backtest_v7.py:200-210`). Its equity also folds receivables into
  `equity` without a separate receivable column.
- Shared position snapshots are represented by final-day `EOD_MARK` rows only
  (`csv_simulate_loop.py:854-872`), not by a daily held/sellable ledger.
- Bonus-share entitlement and list-date locks are not trade rows. A checker
  using only trades cannot independently reconstruct those additions; this
  remains an explicit blind spot rather than an invented corporate-action
  oracle.
- Per-lot shared minimum fees and native-v7 aggregate fees are both legitimate
  existing semantics (RB-12 matrix). RB-16 checks each path's own exported
  conservation and never requires the paths to be equivalent.
- Golden comparison reports the artifact that changed, not the first economic
  component/date that changed. It does not distinguish cash, shares,
  receivable, fees, and valuation.

RB-16 synthetic tests cover a minimum-fee floor, next-session T+1 sale, partial
sale, S8 independent identities, and native-v7 output. No real lake is read.

## 4. Semantic diff

`scripts/research/rb16_semantic_diff.py LEFT_RUN RIGHT_RUN --out REPORT.json`
reads only each supplied directory's `daily_equity.csv` and `trades.csv`, then
writes only the required report path. It reports the first normalized date and
all divergent accounting components. When several components diverge on that
date, the primary localization priority is fees, per-name shares, receivable,
cash, then valuation; the report retains the complete component list.

For shared outputs, cash is reconstructed as cumulative exported fill cash
movement and valuation is the residual from equity. For v7, reported daily cash
and holdings are used directly. This is localization of existing output
semantics, not a fill oracle and not a claim that different strategies should
produce equivalent portfolios.

## 5. Findings

The data-free production-engine vectors added by RB-16 produce zero violations.
No real-lake run was performed. There is therefore no engine finding or
`xfail(strict=True)` in this slice. Any future real-engine violation must be
documented here and pinned as strict xfail; engine behavior and checker
tolerances must not be changed to conceal it.
