# Plan:策略 13(version13)北斗监测·放量启动中线——实施计划

- 日期:2026-10-17
- 状态:**已人裁可实施**(本文记录裁定点;实现仍按切片独立 PR)
- 规则源:[source-strategy13-beidou-manual-2026-10-11.md](source-strategy13-beidou-manual-2026-10-11.md)(docx V2.0 忠实转换)
- 定位:新导出器(买点)+ 新书 `version13`(卖点/仓位,复用 6.55 栈部件)。沿用 s9/s10 模式:`exports/` 名单树 + 显式 `--pool-dir`,拒绝 `stock_pool/`,注册进 BOOKS。

## 0. 三项人裁(2026-10-17,Human:按建议+行业惯例)

| # | 待裁项 | **裁定** |
|---|---|---|
| 1 | sizing 三选一 | **底仓 + 金字塔加仓为主体;单只硬帽 = `--cash-total × 20%`(per_name `name_budget`,引擎整笔 skip_cash 不缩量);放弃 2% 风险公式**(不实现) |
| 2 | 42×/35× 加仓倍数 | **照手册**:首加(×1.6 价位)股数 = 底仓×42;后续每 +10% 档 = 底仓×35;上限 10 次。安全性由裁定 1 的 20% 帽保证:满配 ≈ 底仓×353 ≈ 总资金 16.8%(@2100 万),超帽整笔拒买(fail-closed) |
| 3 | 第一版范围 | **砍主题共振(§3.3)与监管函/年报非标清单(§3.5 部分)**;负面清单用「非 ST + 上市 ≥60 交易日 + 流动性门槛」承载;筹码单峰(§3.4)做可选开关默认关;B 类信号第一版不启用(A 类单独触发),后续 `--beidou-b-class` 开关再加 |

## 1. S1 导出器 `scripts/data/export_beidou_pool.py`

A 类信号(全满足,日频,写 `exports/` 的 `YYYYMMDD.csv`):

1. 量比 ≥1.5:当日成交量 / 过去 20 日均量(不含当日?——**含前 20 根、不含当日**,与手册「达到过去 20 日均量」口径一致)
2. 放量阳线突破关键位:收盘 > 前 N 日高点(箱体上沿,N=60 默认可调)或 > max(MA60, MA120),当日收阳(close>open)
3. 均线多头:MA5>MA10>MA20 且三线各自向上(MA_t > MA_{t-1})
4. 换手率 >3%:成交量 / 流动股本(`oskh_data/float_shares_history`)
5. 非涨停:当日涨幅 < 板块涨停档(引擎同款 9.5% 近似 + 板块档)

池筛(信号前置):流通市值 30–300 亿;日均成交额 ≥5000 万(20 日均);非 ST;上市 ≥60 交易日。可选 `--chip-single-peak`:90% 筹码集中度 ≤20% 且价在峰上方(oskh_factors chip bands;默认关)。

**明确不做**:主题/概念共振、监管函清单、B 类(第一版)。

## 2. S2 书 `backtest/research/strategy13_rules.py`(tag `v13`)

- **止盈(升级核心)**:浮盈档 20/40/60/80/100/150/200% → 卖**当前持仓**的 15/20/20/25/25/30/30%;每笔交易累计卖出不使持仓低于**底仓 10%**(以买入股数计);档位只触发一次(按到达顺序)
- **清仓**:波段高点回撤 ≥25% → 全清(含底仓)
- **止损**(任一):硬止损 收盘 < 买价×0.85;破 MA20 且 3 个交易日未收回;持有 ≤30 天且浮亏 ≥5%
- **加仓**:首次 价 ≥ 买价×1.6 → 加 底仓股数×42;此后每较上次加仓价 +10% → 加 底仓股数×35;≤10 次;`sizing=per_name`,`name_budget = cash_total×0.20`
- **招行锁仓(升级核心)**:策略累计已实现收益每达总投入 20% → 抽离**全部**该增量收益买 600036(复用 6.55 `profit_skim_to_parking`/`cash_div_events`,比例 100%、阈值改累计口径);600036 现金分红 → 再买 600036(现成)
- 涨停/跌停/T+1/费用:走引擎统一成交核,不另设

## 3. S3 大盘闸(复用现成件)

HS300(000300.SH)收盘 < MA60 → 总仓位 ≤50%;< MA120 → ≤30%。复用 `load_book_index_gate`(6.45+ loader)换指数与双阈值;只挡新开+加仓,不强卖(与手册一致)。

## 4. S4 对账与验收

- 单测:止盈档/底仓保留、25% 清仓、加仓档与 20% 帽 fail-closed、锁仓触发;data-free
- 烟测:导出器小窗跑通 + `version13` 日/分钟各一窗三件套落盘
- 对账:同池同窗 vs 手册第十章——**预期胜率/收益远低于手册**(其口径为按未来涨幅选样);差异如实记录进本页,不改默认参数迁就
- off-byte:`version13` 进 `PENDING_BOOK_NAMES`

## 5. 风险与不做清单

- 手册绩效不可当验收标准(源文档头注钉死);本策略第一版**不做**:2% 公式、单行业 30% 帽、组合熔断/月度止损、备兑期权、B 类、主题共振
- 参数全部进 `strategy13_rules` 常量 + CLI 显式覆盖;HELP_LOCK 冻结口径

## 6. Implementation evidence (2026-10-17)

Human 2026-10-17 authorize encode: base+pyramid, cash×20% name cap,
42/35 multipliers with ten-add maximum; no 2% risk formula; A-only,
chip default off; no theme/regulatory/B-class approximation.

S1: `scripts/data/export_beidou_pool.py --start YYYYMMDD --end YYYYMMDD
--pool-dir exports/beidou_run` consumes raw daily bars, amount, backward-asof
`float_shares_history.parquet` and the vendor ST membership table. Missing
required inputs fail. A signal observed at D close is written for the next
observed session T (never D open/14:55). The final observed bar without T
produces no pool entry. Optional chip uses the existing chip distribution's
90% cost band and price above its mode. No market data is written.

Data-free S1 verification: `tests/test_strategy13_exporter.py` (9 passed).
Host lake smoke and manual chapter-10 comparison remain unrun; the manual's
future-selected performance is not an acceptance target. Claude review pending; do not merge.

S2/S3: registered `version13` / `v13`, per-name budget bound at simulation
initialization to `min(--name-budget, --cash-total × 0.20)` (omission means
cash×20%). Base is the manual's fixed ¥10,000, minimum 100 shares; rejected
orders never shrink for cash. Adds anchor to the actual successful fill price,
with 42/35 base-share multipliers and maximum ten. Shared fee/quantity helpers,
ledger, T+1, limit checks, minute cursor and parking/dividend paths remain the
fill authority. Daily close exits queue for the next available open; minute
price exits use the shared FillConfig. Close-only stops count once per session.
The book records net realized trading PnL after allocated buy fees and actual
sell cash debits. Cumulative skim entitlements are monotone, with whole-lot
unpaid residuals retried; parking mark-to-market never triggers the skim.
`profit_skim_frac=0.20` is the existing stack's **fraction of initial capital
per rung**, equal to **100% of the 20% realized-profit increment**; the book
also records `profit_skim_ratio=1.0`. No idle parking sleeve is opened.

HS300 gate is dispatched through `load_book_index_gate` and reads only the
configured index tree. It requires 120 preload sessions and uses completed
T−1 closes/MA60/MA120 for T's 50%/30% cap. It checks post-order exposure,
including parking, and never schedules a forced sale. Direct data-free
`simulate()` callers can inject the gate; product `run()` loads it fail-closed.

CLI examples (configured lake required):

```bash
scripts/data/export_beidou_pool.py --start 20260105 --end 20260930 --pool-dir exports/beidou_2026
backtest/research/csv_daily_backtest.py --strategy version13 --start 20260105 --end 20260930 --pool-dir exports/beidou_2026 --cash-total 21000000
backtest/research/csv_minute_backtest.py --strategy version13 --start 20260105 --end 20260930 --pool-dir exports/beidou_2026 --cash-total 21000000
```

Use the configured Python interpreter before each script. `--beidou-params`
is a JSON object over `strategy13_rules.Params`, for example
`'{"base_budget": 20000, "max_adds": 5}'`. Unknown/non-finite parameters and
more than ten adds fail; the 20% hard cap cannot be raised by overrides.
The exporter separately exposes `--volume-ratio`, `--breakout-days`, and
`--chip-single-peak` (OFF). No B-class stub is exposed.

S4: `version13` is pending (no golden regenerated); existing HELP_LOCKs and
baseline bytes are unchanged. Synthetic exporter-lake, daily/minute legacy
and industry, tier/floor/T+1, cash-cap, dual-index and dividend-reinvestment
tests are data-free. Host-market smoke/comparison is unavailable in this
worktree: both `OSKH_SOURCE_PARQUET_ROOT` and `OSKH_AUTHORITY_HINT_ROOT` are
unset. No drive probing or substitute market data was used. Claude review
pending; do not merge.

Local verification: strategy13-specific tests **37 passed**; admission/shared
contracts **1,241 passed**; full CI marker on pandas 3.0.6 **9,391 passed,
67 skipped, 24 deselected** (before final added smoke regressions). All path,
book/baseline/capability/minute-classification gates and contract ruff pass.
600036 may also have an A-signal position: exits allocate only its strategy
lots, preserving separately tagged locked parking principal.
