# backtest/ 回测专题

本目录存放回测相关文档（chip 因子、数据计划、历史 Backtrader 概念分析）。

## 研究主入口（LEBS）

两套产品，分目录，和 paper / live 一样——改一条策略只动一个目录：

1. **海龟**：现役 PAPER + MockQMT 单测 + MockQMT 真栈 + LEBS `--strategy turtle`。回测代码只在 `backtest/lebs/turtle/`（首仓+P20+分层止损 / `capital.py`）。PAPER 入口 `runtime.local.turtle.yaml` / `start_turtle_paper_stack.py`。
2. **旧 CSV（只回测，不恢复 live/paper）**：`--strategy csv_v1..csv_v5`，代码只在 `backtest/lebs/csv/`。CLI **没有** `preset_vN`。

加回 CSV 回测 **不会**改海龟 PAPER、海龟 LEBS、MockQMT 海龟单测、真栈（`run_mock_turtle_stack_scenario.py`）。它们不 import `lebs/csv/`。共享层（`runner.py` / `qmt_client_mock.py` / `capital.py` / prototype 卖核）才是改重面。

Cerebro 旧壳已拆除。`vendor/backtrader` 只读、不 import。

```text
# 海龟回测（与 PAPER 同源，不是 CSV）
python -m backtest.lebs --freq 1d --symbols 300139.SZ,300142.SZ \
  --start 20230101 --end 20251231 --cash 3000000 \
  --stop-loss-pct -0.04 --out docs/backtest/reports/

# 旧 CSV 隔夜短线回测（日期名单 + 尾盘均分；卖核 v1–v5）
python -m backtest.lebs --strategy csv_v1 --freq 1d \
  --pool-dir stock_pool --start 20260818 --end 20260826 \
  --daily-cap-yuan 1000000 --cash 3000000
python -m backtest.lebs --strategy csv_v2 --freq 1d --pool-dir stock_pool \
  --start 20260818 --end 20260826
python -m backtest.lebs --strategy csv_v3 --freq 1d --pool-dir stock_pool \
  --start 20260818 --end 20260826
python -m backtest.lebs --strategy csv_v4 --freq 1d --pool-dir stock_pool \
  --start 20260818 --end 20260826
python -m backtest.lebs --strategy csv_v5 --freq 1d --pool-dir stock_pool \
  --start 20260818 --end 20260826
```

`--strategy csv_*` 时 `--symbols` 只过滤宇宙，每日名单来自 `--pool-dir`（默认 `stock_pool/YYYYMMDD.csv`）。这是研究宇宙，**不是** PAPER 导入目录。PAPER 买名单只认 `stock_pool_turtle/`（`import_turtle_buy_list.py` 不回落 `stock_pool/`）。缺日文件 = 当日不买。1d 合成尾盘（先卖后买）；1m 买只在 `[14:30, 14:55)`。涨停 skip、不足一手 skip、无延期、无一手补额（不后补）。v4 均线仍是 `ma_source=lebs_qfq_close_sma` 研究近似。CSV 研究轨 **不是** live 回归，不恢复 `capital_pool` / 延期买。

CSV 隔夜短线首批（20260818–20260826 × 五卖核 × 双界）：[`reports/lebs-csv-overnight-20260827.md`](reports/lebs-csv-overnight-20260827.md)。

日线 v3/v5 会在 14:50 再评一次（否则默认 `force_sell_time` 在 09:31 桶打不中）。v4 均线用截至当日的收盘 SMA（qfq 研究近似，**非** live 复权比较价——manifest `ma_source` 在录），窗口不够则 fail-closed 不买卖。`holding_high` 为 postclose 语义：当日 high 次日开评前并入锚（live 同源），同一根 K 的高→低差不构成浮盈回撤——v1/v2 回撤止盈按此读。

`--freq 1m` 同一入口（`period=1m` 分钟线 × 日线复权因子；窄窗试用）。
默认仍是 `--freq 1d`（`bar_model=daily_synthetic`，全日 high/low 包络）。
`--freq 1m` 升级为 **`minute_bucket`**：触发价用**该分钟** OHLC（`bar_step`），
不再用当日截至该分钟的 running 包络（`bar_asof` 仍留给审计 / 持仓高点折叠 /
v4 日收盘 SMA）。覆盖闸（opt-in）：`--require-minute-coverage` 对照同窗口日线，
任一 symbol-day 零分钟 bar 即 fail-closed（不支持 `--bars-json`）。
**分钟数据在 F 盘**（数据盘分层定则见 AGENTS）：机器 env
`OSKH_PERIOD_1M_ROOT=F:\stock_data\period=1m`（已 setx），经
`resolve_period_root("1m")` 单源解析——无需 `--data-root`。池级实测：turtle 池
六标的分钟覆盖 2025-01-02..2026-05-25（2010 symbol-day 缺 4，≈99.8%）。
性能基线：单标的单月分钟 run ≈6.7 分钟——多标的/长窗会到小时级，维持窄窗试用。
研究层不做回测↔实盘 parity；after_fix 不单独建模（固定价时段成交价=收盘价，
日桶撮合已隐含该近似）。**撤单窗** opt-in：`--cancel-pending-eod` 在每个交易
日日界撤掉全部未成交单（≈live 14:55–14:57；默认 off = v1 语义，旧价单跨日续挂
——注意跌出价格笼子 ±2% 的旧价单会被引擎判废单 57 而非成交）。**ST ±5%**
opt-in：`--st-symbols 600xxx.SH,...`（研究层显式声明，仅压主板率 10%→5%，
创业/科创/北交维持板块率；live 侧由柜台真实涨跌停价兜底）。

## 研究结论质量件（2026-08-27）

每次 run 的 JSON/markdown 报告自动带三块（`backtest/lebs/report.py`）：

- **Benchmark**：同期同标的等权 buy&hold 对照（整百股、停牌前向填充、无费用），
  年化/波动/Sharpe/MaxDD + 超额列；
- **Trade attribution**：FIFO 逐笔归因（进出价/持有天数/胜率/盈亏比/最大单笔
  亏损 + 未平仓 lot 清单；**费用前口径**——逐笔费用不可分摊）；
- **状态化免责**：撤单窗 / ST / after_fix 按 run 配置如实标注。

参数扫描后跑聚合器（`backtest/lebs/scan_report.py`）：

```text
python -m backtest.lebs.scan_report <scan-workdir> [--metric sharpe]
```

产出网格表 + 全网格分布分位（mean/median/p10/p90）+ 单数值轴**邻域稳定性**
（双侧相对跳变 >25% 标 `spike` = 疑似过拟合尖峰；启发式报告口径，非 gate）。
单点最优必须对照分布与邻域阅读，勿把 argmax 当结论。

> **分层（2026-08-27 暂时收尾）**：**回测** = LEBS（研究，parity 免责）。**验收** = MockQMT true-stack + comparator（R1–R2c 已关；默认 matching on）。**复盘** = 事故包归档（R3，⏸ 回头再说）。三者不要混成一条线。见 [`backtest-architecture-ssot.md`](backtest-architecture-ssot.md) §6。

## SSOT

| 主题 | 文档 |
|------|------|
| **★ 架构（LEBS 唯一第一方引擎）** | [`backtest-architecture-ssot.md`](backtest-architecture-ssot.md) |
| **★ 同源线复核交接（2026-08-27）** | [`../handoff/mockqmt-lebs-homology-review-handoff-2026-08-27.md`](../handoff/mockqmt-lebs-homology-review-handoff-2026-08-27.md) |
| **★ LEBS 轻量事件驱动回测壳** | [`../engineering/plan-lightweight-event-backtest-shell-2026-08-25.md`](../engineering/plan-lightweight-event-backtest-shell-2026-08-25.md) |
| 日线复权增量 | [`data/daily-adjusted-update-ssot.md`](data/daily-adjusted-update-ssot.md) |
| **策略 7 金榕元 CSV 分钟（立项）** | [`plan-strategy7-turtle-csv-minute-2026-09-11.md`](plan-strategy7-turtle-csv-minute-2026-09-11.md) |
| **复权泄漏 / as_of_date（P1-7b）** | [`../operations/backtest/data-asof-leak-ssot.md`](../operations/backtest/data-asof-leak-ssot.md) |

历史 Cerebro 结算权威评审稿仍在本目录，仅作考古，不再约束实现。

## 子目录

| 目录 | 说明 |
|------|------|
| [chip/](chip/) | Chip 因子与 cost-migration |
| [code-reviews/](code-reviews/) | 历史 Backtrader 代码审查（考古） |
| [data/](data/) | 回测数据方案（含 unified-daily-bars-plan） |

## 文件

| 文件 | 说明 |
|------|------|
| [backtrader-order-types.md](backtrader-order-types.md) | 历史 Backtrader 订单类型指南（考古） |
| [部分成交处理逻辑分析.md](部分成交处理逻辑分析.md) | 部分成交处理逻辑分析 |
| [订单生命周期详解.md](订单生命周期详解.md) | 历史 Backtrader 订单生命周期（考古） |
| [延期买入误检查.md](延期买入误检查.md) | 历史分析（**A6b 2026-08-25 已拆除**，待业务重写） |
| [资金管理实现逻辑（含回滚机制）.md](资金管理实现逻辑（含回滚机制）.md) | 资金管理实现逻辑（延期段 **A6b 已拆除**） |
