# Industry rule profile

- Date: 2026-10-06
- Status: P06 no one-lot budget top-up delivered; later trade-rule slices pending
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

## Switch status

The values below are locked by `industry-fix/adopted-decisions.md`; pending
switches remain `false` until their behavior PR and opt-in baseline are admitted.

| Switch | Status | Adopted rule and source |
|---|---:|---|
| `special_no_limit_days` | pending / `false` | IPO, relist, and resumption facts must come from a PIT lifecycle provider; missing data fails closed and is never inferred from bars. |
| `exchange_quantity_rules` | pending / `false` | Main board/ChiNext buy lots are multiples of 100; STAR starts at 200 then permits one-share increments; BSE starts at 100 then permits one-share increments. Sources: SSE STAR special rules; BSE Rule 3.3.8 ([CSRC copy](https://www.csrc.gov.cn/shenzhen/c105632/c1562694/1562694/files/1638524949335_40064.pdf)). |
| `account_odd_lot_exit` | pending / `false` | An odd remainder below one board lot is sold in one account-level order, not stranded per source lot. |
| `supplementary_min_lot` | P06 delivered / `true` | B8-03: a budget below one valid lot buys zero and records `skip_min_lot_budget`; there is no 100-share top-up. Source: `industry-fix/adopted-decisions.md`, “B8-03: when budget buys < 1 valid lot → buy 0 (skip), no top-up to 100.” |
| `fee_aware_affordability` | pending / `false` | B8-04/B8-06/B8-12: choose the largest valid quantity affordable after fees, shrink on short cash, and pre-check the final declared quantity; B8-11 keeps legacy gate order. |
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
explicit per-side basis-point scenarios. P06 does not change slippage.

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
