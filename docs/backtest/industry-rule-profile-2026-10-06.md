# Industry rule profile

- Date: 2026-10-06
- Status: P01 plumbing delivered; all behavior switches pending
- Principle SSOT: [backtest-rule-principles-ssot.md](ssot/backtest-rule-principles-ssot.md)

## Purpose

`rule_profile` provides one named opt-in boundary for adopting mainstream
A-share backtester conventions. It is not a collection of public fee, lot, or
lifecycle flags. The default remains `legacy`; omitted and explicit
`rule_profile="legacy"` runs keep the existing behavior and output bytes.

P01 only carries the frozen profile through the daily, shared-minute, and
standalone-v7 paths. No switch is read by trading behavior yet. An `industry`
run therefore has the same trades as `legacy`, while its in-memory stats add
`rule_profile` and `rule_profile_revision`.

## Switch status

The values below are locked by `industry-fix/adopted-decisions.md`; each switch
remains `false` until its own behavior PR and opt-in baseline are admitted.

| Switch | P01 | Adopted rule and source |
|---|---:|---|
| `special_no_limit_days` | pending / `false` | IPO, relist, and resumption facts must come from a PIT lifecycle provider; missing data fails closed and is never inferred from bars. |
| `exchange_quantity_rules` | pending / `false` | Main board/ChiNext buy lots are multiples of 100; STAR starts at 200 then permits one-share increments; BSE starts at 100 then permits one-share increments. Sources: SSE STAR special rules; BSE Rule 3.3.8 ([CSRC copy](https://www.csrc.gov.cn/shenzhen/c105632/c1562694/1562694/files/1638524949335_40064.pdf)). |
| `account_odd_lot_exit` | pending / `false` | An odd remainder below one board lot is sold in one account-level order, not stranded per source lot. |
| `supplementary_min_lot` | pending / `false` | B8-03: a budget below one valid lot buys zero; there is no 100-share top-up. |
| `fee_aware_affordability` | pending / `false` | B8-04/B8-06/B8-12: choose the largest valid quantity affordable after fees, shrink on short cash, and pre-check the final declared quantity; B8-11 keeps legacy gate order. |
| `account_fee_schedule` | pending / `false` | Commission is 0.0003 each side with a CNY 5 minimum per strategy order (JoinQuant `OrderCost`: [example](https://www.cnblogs.com/henry2019/p/11700075.html), [reference](https://easyquant.ai/e/joinquant/set-trading-costs-slippage)); sell stamp duty is 0.001 before 2023-08-28 and 0.0005 from that date (财政部、税务总局公告 2023 年第 39 号); transfer fees follow the adopted SH/SZ/BSE date table ([2022 notice report](https://finance.sina.com.cn/roll/2022-04-28/doc-imcwiwst4557332.shtml), [2015/2022 summary](http://m.people.cn/n4/2022/0429/c125-20026334.html)). One strategy order is one fee order; S8 group exits aggregate, scale-out tranches and TWAP children remain separate, and capacity continuation retains its order identity. |
| `chronological_v7` | pending / `false` | Industry mode will select the existing `fix_minute_cash_order` chronological behavior; same-clock tie-breaking is unchanged. |
| `s12_domain_stamp` | pending / `false` | A later zero-trade PR records the actual S12 valuation domain without changing fills. |
| `slippage_bp` | documented `0` | Mainstream backtester default adopted as zero; sensitivity research continues through the existing research fill configuration. |

Corporate-action cash and bonus accounting follows the same adopted
DATA-MISSING rule as lifecycle facts: real industry runs must use explicit
per-event facts and must not derive entitlements from adjustment-factor ratios.

## Use

CLI:

```text
--rule-profile legacy
--rule-profile industry
```

Python APIs accept `"legacy"`, `"industry"`, or a resolved frozen
`RuleProfile` object. Invalid names fail with `ValueError`.

Defaults are unchanged. Existing goldens, fixtures, off-byte baselines,
overlays, book order, output files, and stats keys are never refreshed or
moved. Every later PR that changes results must add its own synthetic,
opt-in industry baseline; old baselines remain immutable.
