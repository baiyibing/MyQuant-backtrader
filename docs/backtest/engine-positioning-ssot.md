# SSOT：研究回测与成交验收怎么分工

2026-11-09 归属更新：因子数值核与通用因子研究先迁到 MyQuant，BT 只留消费适配；原文中的 BT Rust/因子实现归属为历史记录。数据处理和正式因子数据供应归 infra；MyQuant 不反向依赖 BT。见[当前迁移记录](../engineering/factor-owner-migration-20261109.md)。

- 日期：2026-09-16；2026-11-08 按用户澄清恢复完整 Qlib 研究定位
- 状态：v3（完整 Qlib 研究定位澄清；BT Cerebro 继续退场）。定位文档，不是排期。路线图见 MyQuant `docs/plan-three-repo-roadmap-2026-09-12.md`。本仓入口命令：同目录 `README.md`（U1，2026-09-12）。研究问题地图：同目录 `research-backtest-entry.md`。
- 涉及：MyQuant / MyQuant-backtrader（本仓）/ OSkhQuant1.3

MyQuant 是基于 Qlib 的完整量化研究仓库，可使用全部组件，包括 `PortAnaRecord`、`Exchange`、executor、费用与收益分析和 replay。2026-11-08 用户澄清后，旧“Qlib 停用”表述不再作为其边界约束。BT 维护自身向量化研究；1.3 维护 LEBS 与 MockQMT 真栈。BT 的 Cerebro / Rolling 继续保持 2026-09-16 退场状态，历史 chip / ma_chip 对照产物仍为静态档案。

---

## 1. 一句话

| 件 | 仓 | 回答的问题 | 不当什么 |
|---|---|---|---|
| **Qlib 研究回测** | MyQuant | 特征/策略、训练打分、Qlib 回测、费用/收益分析与信号导出 | 不替代 1.3 真栈验收 |
| **向量化** | 本仓 | 这份日名单，按规则在日线/分钟上怎么成交 | 不当 Paper 同源，不当柜台验收 |
| **LEBS** | 1.3 | 同一套 `trade_decision` + 资金核，用 MockQMT 撮合扫参，会怎样 | 不当实盘 parity，不当全市场选股 |
| **MockQMT 真栈** | 1.3 | 同一套决策核过 Redis / executor / 报单回报，验收过不过 | 不当快速研究扫描 |

本仓没有 `backtest/lebs/`。入口命令以同目录 `README.md` 为准，不要跑 `python -m backtest.lebs`。

1.3 的 [`backtest-architecture-ssot.md`](https://github.com/baiyibing/OSkhQuant1.3/blob/master/docs/backtest/backtest-architecture-ssot.md) 只管辖 1.3 第一方：那里第一方回测只有 LEBS，验收只有真栈。它不描述本仓向量化，也不应被改成「三仓总纲」。

---

## 2. 已停用 / 已退场

| 件 | 仓 | 状态 | 还许做什么 |
|---|---|---|---|
| Cerebro / Rolling 第一方策略及 chip / ma_chip 宿主壳 | 本仓 | **已退场（2026-09-16）**，禁止复活 | 对照产物为静态档案，代码路径已删；纯逻辑保留。ma_chip 默认归档，version11 CSV 移植另开计划并重裁成交时点 |
| 1.3 第一方 Cerebro | 1.3 | **已拆** | `vendor/backtrader` 只读不 import |

「弃用 backtrader」指框架，不是弃用本仓。本仓留下向量化，以及技术分析选股（chip / TR / 手工名单）。

---

## 3. 各研究与验收引擎是什么

### 3.0 Qlib（MyQuant）

MyQuant 自主维护基于 Qlib 的训练、打分、PortAna/Exchange 回测、费用敏感性、收益分析和 replay。是否使用这些组件由具体研究目标决定。通用量化数据产制复用 infra，研究实现保留在 MyQuant。

### 3.1 向量化（本仓）

- **入口**：`backtest/research/csv_daily_backtest.py`、`csv_minute_backtest.py`（`--strategy version1|…|version6|version8|version9|version10`）；`csv_minute_backtest_v7.py`（金榕元仓位机，独立，不进策略书）；`csv_minute_backtest_topk_app_dropout.py`（新策略，不改策略 7）。账本：`csv_ledger.py`。市场事实：`market_layer.py`。
- **输入**：日名单 CSV（`parse_pool_csv`）。来源可以是 Qlib 导出、本仓技术分析、手工，下游不认来源。
- **成交模型**：当根 close / 分钟触价；自写账本；T+1、涨跌停、整手在引擎里。细则见 [engine-ashare-correctness.md](engine-ashare-correctness.md)。**向量化跌停 = 全卖因 defer**（含 6/8 trail），不成交。档位：主板 10% / 创科 20% / 北交 30%；ST **时间分段**（主板/中小 ST：2026-07-06 前 5%、当日及之后 10%；创科 ST 20%；北交 ST 30%；见 [engine-ashare-correctness.md](engine-ashare-correctness.md) E-R2 与 [`ssot/st_limit_regimes.json`](ssot/st_limit_regimes.json)）；未知板块 skip。
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

### 3.4 L1 / L2（tip 已交付薄层；统一上限已锁）

> 历史措辞「规划中 / 尚未交付」以 P0 当时为准；**不以之倒退 tip**。

L1 已是 native CSV / v7 / JR / grid Mode B / L2-research 完整 run 的薄 facade（精确白名单委托，不是共享调度 / 定价核）。L2 `minute_orders` 为独立身份、**永 opt-in** 的可选研究后端，不进 BOOKS 默认，也不替换共享 CSV。二者不改变三件引擎分工；Cerebro 继续禁止复活，L2 ≠ `l2_analytics/` ≠ LEBS ≠ 1.3 MockQMT。

2026-10-02 Human 锁定统一运行上限 = 现有 Thin adapter（档 B）；旧入口不碰 MatchCore / Fees / `simulate`。见 [统一上限 + U1 对账](note-minute-engine-unify-ceiling-u1-2026-10-02.md)；产品边界见 [L1/L2 产品边界](note-l1-l2-research-engine-boundary-2026-09-28.md)。同日另开真核 **C-New**（H-U6=New；H-TC1=C docs-only）：旁路冻结 L2 v0，增量用新 contract + 新 backend_id；**不**要求旧入口 byte-compat；本阶段仍无 MatchCore/`simulate` 重写。见 [真核 C-New TC1](note-true-core-c-new-tc1-contract-2026-10-02.md)。

---

## 4. 怎么串

下图描述名单交接的一条流程；MyQuant 同时可在本仓独立运行完整 Qlib 研究回测。

```
名单源 A  MyQuant / Qlib     打分 → 日 CSV
名单源 B  本仓               技术分析 / chip / TR / 手工
              ↓  同一契约（YYYYMMDD.csv，裸六位码）
本仓向量化
  1/2/3/4/5/6/8/9/10 策略书锁规则；7 只吃海龟池且不进 choices；9/10 必须 --pool-dir
       ↓  要上 Paper 才走
1.3 trade_decision 纯函数 → LEBS 扫描 → MockQMT 真栈
```

Qlib、向量化、LEBS 与 MockQMT 使用各自的成交、费用和时点假设，结果应标明所用引擎与实验配置。跨引擎对比根据明确合同检查名单、reason、可卖股、涨跌停及相关研究指标。

---

## 5. 选哪一件

| 你要做的事 | 用 |
|---|---|
| 新名单、新卖点、扫窗、问「这规则赚不赚」 | 按研究目标选 MyQuant/Qlib 或本仓向量化 |
| 规则已锁，且产品要和 Paper 同一决策核 | 1.3 LEBS |
| 改了资金 / 卖核 / 调度，问「栈过不过」 | 1.3 MockQMT 真栈 |
| 模型打分、IC、Qlib 回测、费用/收益研究、出 CSV | MyQuant；研究与信号导出由该仓维护 |
| 对照「下一开盘才成交」的旧结果 | Cerebro / Rolling 已退场（2026-09-16）；chip / ma_chip 对照产物为静态档案，代码路径已删。保留 backtest_output/、历史报告与 fixtures |

---

## 6. 修订

改研究/执行能力归属或停用/退场范围须改本文，并同步根 `README.md`、`AGENTS.md`、`docs/backtest/README.md` 入口段。不要只改其中一个。
