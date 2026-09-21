# Plan: version11 ma_chip CSV 移植（2026-09-21）

> **Status**: **v0.1 · draft（未评审、未人裁，GO 前禁编码）**。风险档：**中**——信号侧复用既有 chip/均线件；主要风险在成交时点语义重裁与 200 日筹码窗的数据装载。
> **业务源**：[归档 plan-ma-chip-edge-strategy-2026-09-07.md](_archive/plans/plan-ma-chip-edge-strategy-2026-09-07.md) §2 锁定口径（Cerebro 原实现已随 2026-09-16 Cerebro 退场删除；对照产物为静态档案）；用户 2026-09-21 指示「把 ma_chip 移植也做完」。
> **Main ship / 单行范围**：把 ma_chip_edge（均线+盈筹率边缘买入）移植到 CSV 向量化引擎为 `version11`：信号池导出器 + 卖点书 + 成交时点语义重裁；不复活 Cerebro。
> **前序**：[workflow-codex-handoff.md](workflow-codex-handoff.md)、[engine-ashare-correctness.md](engine-ashare-correctness.md)、[strategy12 plan](plan-strategy12-jinrongyuan-2026-09-21.md)（同日另一书，互不依赖）。

---

## 0) One-line scope

`version11` = ma_chip_edge 移植：`export_strategy11_pool.py` 按「T-1 四条件边缘 + 盈筹率>0.70」写契约日池 CSV（9/10 导出器先例），引擎按名单买；卖点书实现「买入日收阴→次日开盘卖 / 收阳→破 SMA5 次日开盘卖」；D+1 开盘成交语义在 CSV 时钟上重裁（P1）。

## 1) 规则转录（归档 plan §2，已锁定口径）

| 项 | 口径（源：§2 锁定表） |
|---|---|
| 买入信号（D 收盘评估） | `cond[D]`：D 收盘 > SMA20 日线 且 > 20 周均线（W-FRI+last_day=max，只 backward）且 > SMA60 日线 且 D `high` > 布林上轨（SMA20+2σ，σ=std ddof=1，含 D）；盈筹率 `cyqk_c[D] > 0.70`（含 D 的 200 日 OHLC 窗、窗内每日 asof 流通股本，优先 Rust `compute_cyqk_series`）。**边缘** = `cond[D]` 真且 `cond[D-1]` 假，**两边都必须有限**（NaN≠边缘） |
| 买入成交 | 信号 D 的次一交易日开盘（原 Cerebro `cheat_on_open` + `next_open`；**本仓须重裁**，见 P1） |
| 卖出 | 买入日 T 收盘 ≤ T-1 收盘 → T+1 开盘卖（fail-closed 含等号）；T 收盘 > T-1 收盘 → 持有至首个收盘 < SMA5（含 T 当日评）的次日开盘卖。买入日禁止任何卖单 |
| skip FSM | 涨停买/跌停卖/volume=0 不成交不进净值，记 events；skip_sell 保留 pending_sell 下一日再试；skip_buy 消耗信号。信号后 >4 自然日无 bar → `skip_buy(stale)` 并消耗 |
| 仓位 | 单票 1 笔；已持忽略新开；卖出日不重入 |
| 原费用/涨跌停 | 自写 CommInfo（万 0.5/最低 5/印花 0.05%）+ front 昨收阈值 → **移植后一律用 CSV 引擎现行**（P4 已对齐的行业口径，优于原实现） |

## 2) Verified as-built anchors（HEAD `599a894`）

| 合同项 | 当前事实 | 锚点 |
|---|---|---|
| 池导出器先例 | `export_strategy9_pool.py` / `export_strategy10_pool.py`（源 B）写契约日 CSV；书侧「买点不在本模块」 | `scripts/data/export_strategy9_pool.py`、`:54` 拒绝 `stock_pool/` |
| 卖点书先例 | `strategyN_rules` 纯函数 + `pending_exit`（收盘评估次日开盘离场）机制 | `backtest/research/csv_ledger.py:81`；消费 `csv_daily_backtest.py` |
| 开盘成交先例 | 引擎买钟：日线近似=收盘成交、分钟=14:55 / chase 9:45；**无「次日开盘买」** | `csv_simulate_loop.py` `run_pool_buys_day`；`README.md` 引擎入口说明 |
| chip 计算 SSOT | `turnover_resist.compute_cyqk_series`（Rust 每窗独立网格）+ `oskh_factors.chip`；TR store 刷新工具（PR #146/#147/#148） | `turnover-resist/`、`oskh_factors/`、`scripts/data/refresh_tr_store_window.py` |
| 周线换算先例 | `oskh_factors.weekly_macd_divergence._daily_to_weekly`（W-FRI + last_day=max） | 归档 plan §2 明示同构引用 |
| 编号预留 | AGENTS.md「ma_chip 默认归档；version11 CSV 移植须另开计划并重裁成交时点语义」——即本文件 | `AGENTS.md` Research entries 节 |
| 静态档案 | Cerebro 对照产物 `backtest_output/ma_chip_edge_*` 为静态档案，不参与 CI | AGENTS.md「chip / ma_chip 对照产物为静态档案」 |

## 3) 移植缺口

1. **成交时点**：原 D+1 开盘买 / 卖次日开盘，CSV 引擎无「次日开盘买」买钟（P1 重裁）。
2. **信号数据装载**：200 日筹码窗 + 每日 asof 股本 + 周线 MA——导出器需装载与缓存（TR store 生态可复用，P3）。
3. **skip FSM 映射**：原 events.csv 语义 → CSV 引擎 skip reason 体系（stale/chase/涨停拦截已有对应物）。

## 4) R\* hard locks

| ID | 硬锁 |
|---|---|
| **R1** | 不复活 Cerebro/Rolling；不 import 已删路径；静态档案只读对照。 |
| **R2** | 策略 1–10/8.x/12 书零变更；全量 pytest 绿不放宽。 |
| **R3** | chip/周线计算**复用** `turnover_resist` / `oskh_factors` 既有件，不改其公共 API（归档 plan 同款硬锁）。 |
| **R4** | 费用/涨跌停/除权/T+1 一律用 CSV 引擎现行口径（P1–P4 industry-align 成果），不自写费率。 |
| **R5** | 池导出器拒绝默认 `stock_pool/`（9/10 先例）；数据走 resolvers，禁写死盘符。 |
| **R6** | 时间因果：信号只含截至 D 的数据（PIT）；D-1 NaN ≠ 边缘，等号 fail-closed 沿用。 |
| **R7** | UTF-8 无 BOM、NUL=0；新文件 ruff 零告警。 |

## 5) P\* 人裁点（评审重点；各附建议）

| ID | 问题 | 建议 |
|---|---|---|
| **P1 成交时点重裁** | D+1 开盘买怎么落 CSV 时钟： 买钟加「次日开盘」事件；日线近似=信号次日收盘成交（偏差入 HELP_LOCK）。| 建议 a/b 双跑对照，以分钟 b 为准（v8 跨引擎先例）。 |
| **P2 卖出时点** | 次日开盘卖可直接用 `pending_exit`（现成）？分钟引擎是否也开盘卖？ | 日线 `pending_exit` 原样；分钟书在 09:30 首根按开盘价评 pending 卖（与买钟对称）。 |
| **P3 导出器形态** | 独立 `export_strategy11_pool.py`（9/10 先例）还是引擎内信号？ | 独立导出器：契约日 CSV、可审计、复用 TR store 缓存；`--start/--end/--sample/--universe`。 |
| **P4 抽样 vs 全市场** | 保留原 30 只 seed 抽样，还是全市场池？ | 导出器两种模式都留：`--sample seed=20240907`（对照静态档案）与全市场（研究用）；默认全市场。 |
| **P5 统计窗与预热** | 加载从 2022-07-01 起覆盖 200 日窗+20 周线；统计窗 2024-01-01 起，窗前 edge 置假。 | 沿用归档口径；导出器 manifest 记录窗与预热深度。 |
| **P6 对照验收** | 与 Cerebro 静态档案怎么比？ | 不求 byte parity（引擎/费用/档位已换）；出差异清单（成交价差、费差、skip 语义差）入 reviews；30 只 seed 模式跑同 universe 对照。 |
| **P7 布林/周线细节漂移** | std ddof=1、周线 asof 只 backward、末端未完成周可参与——沿用？ | 逐条沿用（归档 plan 对抗评审已锁），不重开。 |

## 6) 非目标

- 不做分钟级 chip、实盘、LEBS 接线。
- 不改 `oskh_factors` / `turnover_resist` / `qlib_cost` 公共 API。
- 不重跑 classic 对抗（归档 r1/r2 已锁口径；本 plan 评审走现行 fan-out）。
- 不求与静态档案数值一致（P6 差异清单即可）。

## 7) 切片（各一 commit，带完成定义）

| 刀 | 内容 | 完成定义（DoD） |
|---|---|---|
| **A** | `backtest/research/strategy11_rules.py` 纯函数：`edge_condition(closes, high, bb_upper, cyqk, weekly_ma)`、`exit_signal(t_close, prev_close, sma5)`、record/HELP_LOCK；`tests/test_strategy11_rules.py`（边缘/D-1 NaN/等号 fail-closed/买入日禁卖 pin） | 无引擎/chip import；归档 §2 逐条有 pin |
| **B** | `scripts/data/export_strategy11_pool.py`：日线+周线+cyqk 200 日窗装载（复用 Rust `compute_cyqk_series` 与 TR store 缓存）、契约日 CSV、`--sample/--universe`、manifest | data-free 单测（合成 OHLC+股本）；拒绝 `stock_pool/`；`--help` 带 §2 要点 |
| **C** | 引擎接线：买钟（按 P1 裁决）+ 卖书注册 `version11`（别名 `11/v11/version11`，`FORBIDDEN_DEFAULT_STOCK_POOL` 增项）+ AGENTS.md Research entries 增行、预留句改为「已移植（PR #N）」 | 引擎级测试：D+1 成交、skip FSM 映射、卖出日不重入；`--strategy 11 --help` 冒烟 |
| **D** | 对照冒烟：seed=20240907 30 只同 universe vs 静态档案差异清单 + 全市场池一跑；结果记 reviews（数字不入库） | 差异清单三分类（成交价/费用/skip 语义）成文 |

## 8) 验证命令

```powershell
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
D:\anaconda3\envs\vanna312\python.exe -m ruff check backtest/research/strategy11_rules.py scripts/data/export_strategy11_pool.py tests/test_strategy11*.py
D:\anaconda3\envs\vanna312\python.exe scripts/data/export_strategy11_pool.py --help
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest.py --strategy 11 --help
```

## 9) 代码落点

- 新：`backtest/research/strategy11_rules.py`、`scripts/data/export_strategy11_pool.py`、`tests/test_strategy11_rules.py`、`tests/test_export_strategy11_pool.py`、（C）`tests/test_strategy11_engine.py`
- 改：`csv_strategy_books.py`（注册 + FORBIDDEN 清单）、（按 P1）`csv_minute_backtest.py` 买钟、`tests/test_csv_strategy_books.py`（清单 pin）、`AGENTS.md`（Research entries + 预留句回写）

## 10) 修订程序

v0.x 草稿 → 多路评审（`docs/architecture/reviews/2026-09-21/plan-version11-machip-csv/`，宿主机跑 `run_multi_ai_review.py`）→ P1–P7 逐条人裁 → 修订到 vN、状态改「✅ 已人裁 GO（commit hash）」→ 走 [Codex 交接工作流](workflow-codex-handoff.md) 第 4 步起。

> 与 strategy12 plan 的顺序建议：两书互不依赖可并行评审；实施建议 12 先（引擎部分减仓能力独立）或 11 先（导出器复用 PR #146 TR store 刚落地的刷新链）皆可，人裁时定。
