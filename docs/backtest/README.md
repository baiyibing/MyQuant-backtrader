# backtest/ 回测专题

本仓研究入口是**向量化**，不是 LEBS，也不是 Cerebro。

三件成交引擎（本仓向量化 / 1.3 LEBS / 1.3 MockQMT）怎么分工：见 **[engine-positioning-ssot.md](engine-positioning-ssot.md)**。Qlib `PortAnaRecord` 停用；Cerebro 观察退役。本仓没有 `backtest/lebs/`。

## 本仓研究入口（向量化）

名单：`YYYYMMDD.csv`，首列裸六位码，`parse_pool_csv` 补交易所后缀。缺日 / 空文件 = 当日不买。6/8 默认读本仓 `stock_pool/`；7 必须 `--pool-dir`（或 `OSKH_TURTLE_POOL_DIR`），不要回落 `stock_pool/`。

```text
# 策略 1 / 2 / 3 / 4 / 5 / 6 / 8：共用引擎，策略书换卖点与加仓。必须 --strategy，无缺省。
# 日线近似（收盘成交；分钟湖短于窗口时用这个接到今天）
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py ^
  --strategy version6 --start 20251023 --end 20260909 ^
  --pool-dir D:\path\to\version6_pool
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py ^
  --strategy version8 --start 20251023 --end 20260909

# 分钟（14:55 买入；湖 time 为中国交易时钟标成 UTC）
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest.py ^
  --strategy version6 --start 20251023 --end 20251104 ^
  --pool-dir D:\path\to\version6_pool
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest.py ^
  --strategy version8 --start 20251023 --end 20260909

# 策略 7 金榕元仓位机（独立，不进 1/2/3/4/5/6/8 策略书）。只吃海龟池。
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest_v7.py ^
  --start 20260804 --end 20260909 ^
  --pool-dir E:\PycharmProjects\OSkhQuant1.3\stock_pool_turtle
```

落盘：`backtest_output/csv_daily_{book}_{start}_{end}/`、`csv_minute_{book}_{start}_{end}/`、`csv_minute_v7_{start}_{end}/`（`summary.txt`、`daily_equity.csv`、`trades.csv`）。

规则与闸：策略 7 见 [plan-strategy7-turtle-csv-minute-2026-09-11.md](plan-strategy7-turtle-csv-minute-2026-09-11.md)。6/8 口径写在各自 CLI 的 help lock。成交核（档位 / 全卖因跌停 / Decimal 涨跌停价 / 停牌净值）见 [engine-ashare-correctness.md](engine-ashare-correctness.md)。名单 as-of 与 ST 名称列见 [pool-csv-contract.md](pool-csv-contract.md)。

数据：只读 F 湖 parquet（有 `F:\stock_data\.authority` 且勿残留 `OSKH_PERIOD_*`）。细则见根 `AGENTS.md`。

## 1.3：LEBS 与 MockQMT（不在本仓跑）

要和 Paper 同源的扫描、真栈验收，去 **OSkhQuant1.3**：

- 研究：`python -m backtest.lebs`（`--strategy turtle` 或 `csv_v1..csv_v5`）
- 验收：`run_mock_turtle_stack_scenario.py` + `--parity`
- SSOT：1.3 `docs/backtest/backtest-architecture-ssot.md`（只管辖 1.3，不描述本仓向量化）

本仓不复刻 LEBS / MockQMT，也不承诺和它们净值对齐。

## Cerebro（观察退役）

`backtest/backtest_main_full.py --allow-cerebro-fossil`、`ProfitStrategy`、chip / ma_chip 的 Cerebro 路径仍在树上，只做旧对照；主入口没有该显式旗标会立即退出。**新策略不写 `ProfitStrategy.StrategyN`，不扩 Rolling。**

## SSOT

| 主题 | 文档 |
|------|------|
| **★ 三件引擎定位（本仓 + 1.3）** | [engine-positioning-ssot.md](engine-positioning-ssot.md) |
| **★ 向量化成交核（A 股档位 / 跌停 / 停牌）** | [engine-ashare-correctness.md](engine-ashare-correctness.md) |
| 名单 CSV 契约（as-of = 买入日 T） | [pool-csv-contract.md](pool-csv-contract.md) |
| 策略 1–8 书契约（U-R\*；撮合句以 E-R\* 为准） | [plan-unify-csv-strategies-1-8-2026-09-12.md](plan-unify-csv-strategies-1-8-2026-09-12.md) |
| **策略 7 金榕元 CSV 分钟（A–D 已合；E 本机）** | [plan-strategy7-turtle-csv-minute-2026-09-11.md](plan-strategy7-turtle-csv-minute-2026-09-11.md) |
| 日线复权增量 | [data/daily-adjusted-update-ssot.md](data/daily-adjusted-update-ssot.md) |
| ma + 筹码边（Cerebro 对照，2026-09-07） | [plan-ma-chip-edge-strategy-2026-09-07.md](plan-ma-chip-edge-strategy-2026-09-07.md) |

下列链到本仓不存在的 1.3 迁仓文件，不要当本仓入口：`backtest-architecture-ssot.md`、`../handoff/mockqmt-lebs-homology-review-handoff-2026-08-27.md`、`../engineering/plan-lightweight-event-backtest-shell-2026-08-25.md`。

## 子目录

| 目录 | 说明 |
|------|------|
| [chip/](chip/) | Chip 因子与 cost-migration |
| [code-reviews/](code-reviews/) | 历史 Backtrader 代码审查（考古） |
| [data/](data/) | 回测数据方案（含 unified-daily-bars-plan） |

## 文件（考古）

| 文件 | 说明 |
|------|------|
| [backtrader-order-types.md](backtrader-order-types.md) | 历史 Backtrader 订单类型 |
| [部分成交处理逻辑分析.md](部分成交处理逻辑分析.md) | 部分成交 |
| [订单生命周期详解.md](订单生命周期详解.md) | 历史 Backtrader 订单生命周期 |
| [延期买入误检查.md](延期买入误检查.md) | 历史分析（A6b 已拆除） |
| [资金管理实现逻辑（含回滚机制）.md](资金管理实现逻辑（含回滚机制）.md) | 资金管理（延期段 A6b 已拆除） |
