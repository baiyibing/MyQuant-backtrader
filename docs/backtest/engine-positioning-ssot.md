# SSOT：三件成交引擎怎么分工

- 日期：2026-09-12
- 状态：v1。定位文档，不是排期。路线图见 MyQuant `docs/plan-three-repo-roadmap-2026-09-12.md`。本仓入口命令：同目录 `README.md`（U1，2026-09-12）。
- 涉及：MyQuant / MyQuant-backtrader（本仓）/ OSkhQuant1.3

Qlib `PortAnaRecord` 停用。Cerebro / Rolling 观察退役（对照化石，不接新策略）。留下三件，问的不是同一个问题，不要合成一台，也不要互相当对照净值。

---

## 1. 一句话

| 件 | 仓 | 回答的问题 | 不当什么 |
|---|---|---|---|
| **向量化** | 本仓 | 这份日名单，按规则在日线/分钟上怎么成交 | 不当 Paper 同源，不当柜台验收 |
| **LEBS** | 1.3 | 同一套 `trade_decision` + 资金核，用 MockQMT 撮合扫参，会怎样 | 不当实盘 parity，不当全市场选股 |
| **MockQMT 真栈** | 1.3 | 同一套决策核过 Redis / executor / 报单回报，验收过不过 | 不当快速研究扫描 |

本仓没有 `backtest/lebs/`。入口命令以同目录 `README.md` 为准，不要跑 `python -m backtest.lebs`。

1.3 的 [`backtest-architecture-ssot.md`](https://github.com/baiyibing/OSkhQuant1.3/blob/master/docs/backtest/backtest-architecture-ssot.md) 只管辖 1.3 第一方：那里第一方回测只有 LEBS，验收只有真栈。它不描述本仓向量化，也不应被改成「三仓总纲」。

---

## 2. 已停用 / 观察退役

| 件 | 仓 | 状态 | 还许做什么 |
|---|---|---|---|
| Qlib PortAnaRecord / Exchange | MyQuant | **停用**。不当产品，不当对照基准 | 训练、IC、导出日名单 CSV |
| Cerebro / Rolling / vendor Backtrader 第一方策略 | 本仓 | **观察退役**。不接新策略 | 已有 chip / ma_chip 对照可跑；新工作不写 `ProfitStrategy.StrategyN` |
| 1.3 第一方 Cerebro | 1.3 | **已拆** | `vendor/backtrader` 只读不 import |

「弃用 backtrader」指框架，不是弃用本仓。本仓留下向量化，以及技术分析选股（chip / TR / 手工名单）。

---

## 3. 三件各自是什么

### 3.1 向量化（本仓）

- **入口**：`backtest/research/csv_daily_backtest.py`、`csv_minute_backtest.py`（`--strategy version1|version2|version6|version8`）；`csv_minute_backtest_v7.py`（金榕元仓位机，独立，不进策略书）。
- **输入**：日名单 CSV（`parse_pool_csv`）。来源可以是 Qlib 导出、本仓技术分析、手工，下游不认来源。
- **成交模型**：当根 close / 分钟触价；自写账本；T+1、涨跌停、整手在引擎里。
- **用途**：锁规则、扫参、名单质量对照。快。
- **禁**：复刻 Redis / live；把 7 注册进 6/8；用 `simulate_v7` 跑 Alpha158。

### 3.2 LEBS（1.3）

- **入口**：`python -m backtest.lebs`（`--strategy turtle` 或 `csv_v1..csv_v5`）。
- **输入**：海龟吃 `stock_pool_turtle/`；CSV 研究吃 `stock_pool/`。决策核是 `trade_decision` + `capital.py`。
- **成交模型**：bar 环 + **import MockQMT 撮合本体**（订单、笼子、整手），不是向量化那套当根 close。
- **用途**：只服务「要和 Paper 同源」的产品。扫完进真栈，不进 paper。**parity 免责**。
- **禁**：在 LEBS 里重写 6/8/7；复刻执行栈；承诺和实盘净值对齐。

策略 7（本仓金榕元分钟机）≠ 1.3 LEBS turtle / Paper 海龟。名字都像海龟，池和仓位机不是一份。

### 3.3 MockQMT 真栈（1.3）

- **入口**：`run_mock_turtle_stack_scenario.py` + `--parity`。默认 matching on。
- **输入**：与 Paper 同一套进程拓扑（Bridge / executor / 结算流），柜台换成 Mock。
- **成交模型**：报单回报，不是回测账本。
- **用途**：验收唯一入口。改资金/卖核/调度，单测 + 真栈 baseline。
- **禁**：用 LEBS 或向量化净值代替真栈签字；把事故复盘（R3）先当回测做。

---

## 4. 怎么串

```
名单源 A  MyQuant / Qlib     打分 → 日 CSV
名单源 B  本仓               技术分析 / chip / TR / 手工
              ↓  同一契约（YYYYMMDD.csv，裸六位码）
本仓向量化
  1/2/6/8 策略书锁规则；7 只吃海龟池
       ↓  要上 Paper 才走
1.3 trade_decision 纯函数 → LEBS 扫描 → MockQMT 真栈
```

净值三套对不上是预期：向量化当根 close ≠ LEBS/MockQMT 报单回报 ≠ 已停用的 Qlib 日频组合。能比的是名单、reason、可卖股、涨跌停。

---

## 5. 选哪一件

| 你要做的事 | 用 |
|---|---|
| 新名单、新卖点、扫窗、问「这规则赚不赚」 | 本仓向量化 |
| 规则已锁，且产品要和 Paper 同一决策核 | 1.3 LEBS |
| 改了资金 / 卖核 / 调度，问「栈过不过」 | 1.3 MockQMT 真栈 |
| 模型打分、IC、出 CSV | MyQuant（不跑 PortAnaRecord） |
| 对照「下一开盘才成交」的旧结果 | 本仓已有 Cerebro 产物，不新开 |

---

## 6. 修订

改「留下哪三件 / 停用哪两件」须改本文，并同步根 `README.md`、`AGENTS.md`、`docs/backtest/README.md` 入口段。不要只改其中一个。
