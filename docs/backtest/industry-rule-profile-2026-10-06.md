# Industry rule profile

- Date: 2026-10-06
- Status: P10 account-level odd-lot exits delivered; later trade-rule slices pending
- Principle SSOT: [backtest-rule-principles-ssot.md](ssot/backtest-rule-principles-ssot.md)

## Purpose

`rule_profile` provides one named opt-in boundary for adopting mainstream
A-share backtester conventions. It is not a collection of public fee, lot, or
lifecycle flags. The default remains `legacy`; omitted and explicit
`rule_profile="legacy"` runs keep the existing behavior and output bytes.

P01 carries the frozen profile through the daily, shared-minute, and
standalone-v7 paths. P02 enables the zero-trade `s12_domain_stamp` metadata
switch. P03 enables the commission component of `account_fee_schedule`:
0.0003 on buys and sells with a CNY 5 minimum per strategy order. P04 adds
sell-side stamp duty to the same strategy-order identity: 0.001 before
2023-08-28 and 0.0005 from 2023-08-28. P05 adds bilateral transfer fees by
fill notional: SH/SZ A-shares use 0.00002 before 2022-04-29 and 0.00001 from
that date; BSE uses 0.000025 before the cutover and 0.00001 from it. P06's
`supplementary_min_lot` switch applies adopted decision B8-03: when a
budget cannot buy one valid lot, the order is skipped instead of receiving
supplementary funds for 100 shares. The default `legacy` profile, including
omitted profile arguments, retains its
original per-call fee formula and output bytes.

P07 enables `fee_aware_affordability` for adopted decision B8-04. Each buy is
sized to the largest quantity valid under the currently active lot rules whose
notional plus industry buy commission (including the CNY 5 per-order minimum)
and bilateral transfer fee fits both the strategy budget and available cash.
This uses the already-adopted P03/P05 fee schedule; legacy nominal-only sizing
is unchanged.

P08 enables `shrink_on_short_cash` for adopted decision B8-06. After the
fee-aware intended declaration is known, insufficient available cash shrinks it
to the largest currently valid quantity whose notional plus all buy fees can be
paid; zero affordable quantity is skipped, and industry mode never raises
`InsufficientCashError`. The helper is the same binary-search affordability
primitive introduced by P07. Cash is still evaluated before the capacity gate,
preserving the adopted B8-11 legacy gate order.

P09 enables `exchange_quantity_rules` and adopted decision B8-12. Main-board
and ChiNext buy declarations remain multiples of 100 shares. STAR symbols
`688`/`689` require at least 200 shares and then permit one-share increments;
BSE symbols classified by `market_layer` require at least 100 shares and then
permit one-share increments. Shared daily/minute and native/standalone-v7 use
the same quantity rule. A volume cap may partially fill an already-valid
declaration and is not treated as a new declaration. Loop cash pre-checks now
preview the same final fee-aware declared quantity that the ledger submits.

P10 enables `account_odd_lot_exit`. The adopted
JoinQuant/RQAlpha-style convention is a whole-remainder sell order: when a
partial exit would leave fewer than 100 shares, or fewer than 200 shares for
STAR, that remainder is added to the same strategy order. The calculation is
made once against the account/group position before FIFO lot-row allocation;
it is never applied independently to each source lot. S8 group exits retain
P03's one-order identity, and each 9_2/12 or S8 scale-out tranche remains one
order. T+1 and volume capacity remain fill constraints and are not bypassed.

## Switch status

The values below are locked by `industry-fix/adopted-decisions.md`; pending
switches remain `false` until their behavior PR and opt-in baseline are admitted.

| Switch | Status | Adopted rule and source |
|---|---:|---|
| `special_no_limit_days` | pending / `false` | IPO, relist, and resumption facts must come from a PIT lifecycle provider; missing data fails closed and is never inferred from bars. |
| `exchange_quantity_rules` | P09 delivered / `true` | Main board/ChiNext buy declarations are multiples of 100; STAR (`688`/`689`) starts at 200 and then permits one-share increments; BSE, classified through `market_layer`, starts at 100 and then permits one-share increments. Source locked in `industry-fix/adopted-decisions.md`: 上交所《科创板股票交易特别规定》 (200 起、1 股递增) and 北交所交易规则 3.3.8 ([CSRC copy](https://www.csrc.gov.cn/shenzhen/c105632/c1562694/1562694/files/1638524949335_40064.pdf)). The same adopted file locks B8-12: “loop cash pre-check uses the final declared quantity (incl. STAR rule).” Volume-cap partial fills remain fills of the accepted declaration, not new declarations. |
| `account_odd_lot_exit` | P10 delivered / `true` | A partial sell that would leave an account/group remainder below one board lot includes that whole remainder in the same order: 100 shares generally and 200 for STAR. Source locked in `industry-fix/adopted-decisions.md`: “Sell quantity: an odd remainder below one board lot (100; STAR 200) must be sold in ONE order together (no stranded per-lot residues).” That file also locks P03 order boundaries: S8 whole-group exit is one order and each scale-out tranche is one order. The implementation uses the mainstream JoinQuant/RQAlpha-style whole-remainder order convention rather than rounding a tranche down and stranding dust; FIFO lot rows are allocations of that order. |
| `supplementary_min_lot` | P06 delivered / `true` | B8-03: a budget below one valid lot buys zero and records `skip_min_lot_budget`; there is no 100-share top-up. Source: `industry-fix/adopted-decisions.md`, “B8-03: when budget buys < 1 valid lot → buy 0 (skip), no top-up to 100.” |
| `fee_aware_affordability` | P07 delivered / `true` | B8-04: choose the largest currently valid buy quantity for which notional plus all buy fees is no greater than both budget and available cash. Source: `industry-fix/adopted-decisions.md`, “B8-04: size including fees: the largest valid quantity with notional + all buy fees <= budget (and <= cash).” Buy fees reuse that file's adopted JoinQuant-style commission (0.0003 each side, CNY 5 minimum per order; [example](https://www.cnblogs.com/henry2019/p/11700075.html), [reference](https://easyquant.ai/e/joinquant/set-trading-costs-slippage)) and bilateral transfer-fee decision sourced to 中国结算 2022-04-28 ([contemporaneous copy](https://finance.sina.com.cn/roll/2022-04-28/doc-imcwiwst4557332.shtml)) plus the 2015 change ([People.cn](http://m.people.cn/n4/2022/0429/c125-20026334.html)). B8-11 retains legacy cash-vs-capacity gate order. |
| `shrink_on_short_cash` | P08 delivered / `true` | B8-06: when cash cannot pay the intended buy, choose the largest currently valid quantity whose notional plus all buy fees is affordable; skip if that quantity is zero and never raise. Source: `industry-fix/adopted-decisions.md`, “B8-06: short cash → shrink to the largest affordable valid quantity (fees included); skip if 0. (qlib-style clip; never raise.)” The same source locks B8-11 to the legacy cash-before-capacity gate order. |
| `account_fee_schedule` | P05 commission + stamp duty + transfer fee delivered / `true` | Commission is 0.0003 each side with a CNY 5 minimum per strategy order. Source locked in `industry-fix/adopted-decisions.md`: JoinQuant stock `OrderCost` default (`open_commission=close_commission=0.0003`, `min_commission=5`), with [example](https://www.cnblogs.com/henry2019/p/11700075.html) and [reference](https://easyquant.ai/e/joinquant/set-trading-costs-slippage). Stamp duty is sell-side only: 0.001 before 2023-08-28 and 0.0005 from that date, sourced there to 财政部、税务总局公告 2023 年第 39 号（减半征收证券交易印花税）. Transfer fee is bilateral with no minimum and charged by fill notional: SH/SZ A-shares are 0.00002 before 2022-04-29 (the adopted decision uses the 2015-08-01 rate for earlier dates as a documented simplification) and 0.00001 from 2022-04-29; BSE is 0.000025 before and 0.00001 from that date. The adopted sources are 中国结算《关于降低股票交易过户费收费标准的通知》2022-04-28 ([contemporaneous copy](https://finance.sina.com.cn/roll/2022-04-28/doc-imcwiwst4557332.shtml)) and the 2015 change ([People.cn](http://m.people.cn/n4/2022/0429/c125-20026334.html)). Board classification reuses `market_layer`. One strategy order is one fee order: S8 whole-group exit is one order; each scale-out tranche and each tail/TWAP minute child is a separate order; capacity continuation retains its order identity. Fill-row commission, stamp, and transfer components retain that order identity and are recorded separately. Explicit legacy cost schedules such as `--qlib-cost` / `QLIB_PORTANA` conflict and fail fast. |
| `chronological_v7` | pending / `false` | Industry mode will select the existing `fix_minute_cash_order` chronological behavior; same-clock tie-breaking is unchanged. |
| `s12_domain_stamp` | delivered / `true` | S12 records its actual valuation source: daily=`front`; minute with X-01 off=`front`; minute with X-01 on=`none`. This is metadata only and does not change fills. |
| `slippage_bp` | documented `0` | Mainstream backtester default adopted as zero; sensitivity research continues through the existing research fill configuration. |

Corporate-action cash and bonus accounting follows the same adopted
DATA-MISSING rule as lifecycle facts: real industry runs must use explicit
per-event facts and must not derive entitlements from adjustment-factor ratios.

## Slippage

The industry profile keeps slippage at `0`, the default in qlib, RQAlpha, and
JoinQuant unless explicitly configured. This follows the adopted
“Slippage: 0 (most backtesters' default); document only” decision; it does not
claim that realized execution has zero market impact. Sensitivity analysis
continues through the existing
`fullstrat_research_hooks.ResearchFillConfig` research hook, including its
explicit per-side basis-point scenarios. P07 does not change slippage.

## Use

CLI:

```text
--rule-profile legacy
--rule-profile industry
```

Accordingly, argparse `--help` gains one additive
`--rule-profile {legacy,industry}` option line. This is intended. The minute
`HELP_LOCK` is unchanged; the daily `HELP_LOCK` changed only through P02's ST
text fix. The existing shared-minute guarded source hashes remain unchanged.

Python APIs accept `"legacy"`, `"industry"`, or a resolved frozen
`RuleProfile` object. Invalid names fail with `ValueError`.

B7 remains a hooks-only internal policy and this programme does not register a
public `--on-short-cash` CLI option; argparse therefore rejects that spelling.
If an adapter supplies explicit `on_short_cash`, industry accepts only the
book's existing default (`raise` for S8-bound books, `skip` otherwise). An
explicit non-default mode conflicts with P08 and fails fast instead of silently
overriding shrink-or-skip.

Defaults are unchanged. Existing goldens, fixtures, off-byte baselines,
overlays, book order, output files, and stats keys are never refreshed or
moved. P03's
`tests/fixtures/off_byte_baseline_industry_p03_order_commission_20261006.json`
remains immutable. P04 adds
`tests/fixtures/off_byte_baseline_industry_p04_stamp_duty_20261006.json` from
the data-free `tests/fixtures/industry/stamp_duty.json` cases. It covers shared
daily/minute, native and standalone v7, a multi-lot S8 group exit, and sells
on both sides of the 2023-08-28 rate boundary.

P05 keeps those files immutable and adds
`tests/fixtures/off_byte_baseline_industry_p05_transfer_fee_20261006.json`
from `tests/fixtures/industry/transfer_fee.json`. Its synthetic trades span
both sides of 2022-04-29 and cover shared daily/minute, native and standalone
v7, BSE and SH/SZ classification, and the S8 one-order allocation path.

P06 keeps all prior files immutable and adds
`tests/fixtures/off_byte_baseline_industry_p06_no_topup_20261006.json` from
the data-free `tests/fixtures/industry/no_topup.json`. Shared daily and minute
cases each contain one normally funded BUY/SELL and one order whose CNY 1,000
budget is below its CNY 2,000 board lot: legacy tops that order up, while
industry records `skip_min_lot_budget` and buys zero. Native/standalone v7 and
fixed-slice paths already round down without a supplementary-lot fallback, so
P06 leaves them unchanged.

P07 keeps every earlier baseline immutable and adds
`tests/fixtures/off_byte_baseline_industry_p07_fee_aware_sizing_20261006.json`
from the data-free `tests/fixtures/industry/fee_aware_sizing.json`. Its shared
daily/minute and native/standalone-v7 cases each contain a BUY and SELL. The
legacy buy consumes the full nominal budget and therefore exceeds that budget
after commission; industry sizes exactly one 100-share lot lower so notional,
minimum commission, and transfer fee fit the budget and cash.

P08 keeps every earlier baseline immutable and adds
`tests/fixtures/off_byte_baseline_industry_p08_shrink_on_short_cash_20261006.json`
from the data-free `tests/fixtures/industry/shrink_on_short_cash.json`. Its S8
daily and minute cases intend a CNY 20,000 buy with only CNY 15,000 cash.
Legacy reaches B7's `raise` mode and throws `InsufficientCashError`; industry
shrinks to 1,400 shares, pays commission and transfer fee without negative
cash, and later sells the position. Both recorded industry cases contain a BUY
and SELL.

P09 keeps every earlier baseline immutable and adds
`tests/fixtures/off_byte_baseline_industry_p09_quantity_rules_20261006.json`
from the data-free `tests/fixtures/industry/quantity_rules.json`. Its eight
cases cover STAR and BSE synthetic names in shared daily/minute and
native/standalone-v7. Each industry case contains one BUY and SELL, uses a
non-round-hundred valid declaration (2014 shares in shared version6; 1999 in
v7), and differs from the corresponding legacy 2000-share declaration.

P10 keeps every earlier baseline immutable and adds
`tests/fixtures/off_byte_baseline_industry_p10_odd_lot_exit_20261006.json`
from the data-free `tests/fixtures/industry/odd_lot_exit.json`. Its STAR
version9_2 scale-out starts from the same synthetic 200-share buy in both
profiles. Legacy sells 100 and strands a 100-share STAR residue; industry adds
that remainder to the same scale-out order, sells 200, and closes the position.
