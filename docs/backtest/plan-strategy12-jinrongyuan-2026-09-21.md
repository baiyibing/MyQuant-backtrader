# Plan: strategy 12 金榕元均线减仓书（2026-09-21）

> **Status**: **v0.2 · draft（未评审；P1 已预裁，其余 GO 前禁编码）**。风险档：**中高**——新增引擎级「部分减仓 + 买回」记账能力，触及股数/现金流不变量；书侧为全新策略书，无历史基线可对照。
> **业务源**：`E:\PycharmProjects\OSkhQuant1.3\docs\bucket_policy\金榕元交易回测策略--0921-策略12.docx`（金榕元系列第 4 版；前三版 0911/0913/0916 → 策略 8。原名"策略11"，2026-09-21 用户裁决改为 12，docx 已同步改名）。
> **Main ship / 单行范围**：策略 12 = 策略 8 买侧骨架（尾盘涨停 T+1 9:45 确认追买、名单全加、+20% 台阶、per_name 100 万）+ 全新均线出场（昨收 MA5 破线减仓 50% 且收复买回；昨收 MA10 下方 10% 止损且站回买回）。
> **前序**：[workflow-codex-handoff.md](workflow-codex-handoff.md)（本 plan 走 Codex 交接工作流）、[engine-ashare-correctness.md](engine-ashare-correctness.md)（成交核 SSOT）、[plan-v8-rules-v2-2026-09-16.md](_archive/plans/plan-v8-rules-v2-2026-09-16.md)（v8 书先例）。

---

## 0) One-line scope

新策略书 `version12`：买侧复用 v8 全套钩子；卖侧以昨收 MA5/MA10 为轴的部分减仓-止损-买回状态机；为引擎新增两个 opt-in 能力（share 级部分卖出、买回买因），默认关闭、现有书零行为变更。

## 1) 业务规则转录（docx 原文，189 字）

| # | 原文 | 工程语义（待 P\* 裁决细化） |
|---|---|---|
| 1 | 单个股票金额 100 万 | per_name 预算 100 万（v8 sizing 先例） |
| 2 | 已持有股再出现加仓一个基数，输赢都加 | 名单全加（v8 `ALLOW_ADD`，add_gate=None） |
| 3 | 个股每涨 20% 加仓一个基数 | +20% 独立台阶（v8 `step_add_due` / `is_step` lot） |
| 4 | 止损：十日线下方 10 个点 | 现价 < 昨收 MA10 × 0.90 → 止损（**均线基准**，非买价基准；P5） |
| 5 | 掉下五日线减仓 50%，重新站上五日线买回减仓股份；重新站上十日线买回止损筹码 | 部分减仓 + 双买回通道（P3/P4；引擎新能力） |
| 6 | T 日尾盘涨停不能买入股；T+1 9:45 市价>开盘价买入，<开盘弃买，涨停弃买 | 逐字对应既有 `chase_decision`（csv_ledger.py:115-122），零新增 |

## 2) Verified as-built anchors（HEAD `599a894`）

| 合同项 | 当前事实 | 锚点 |
|---|---|---|
| T+1 9:45 追买 | `chase_decision(open,px,limit_up)`：市价>开盘且非涨停→buy；否则 abandon/limit | `backtest/research/csv_ledger.py:115-122`；入队 `queue_limit_up_chase` `:124-137` |
| MA 数据通道 | 书钩子 `sell_gate(code, px, day, daily_closes_ending_yesterday)` / `buy_gate(...)` 已把截至昨收日线收盘序列喂给书；策略 4 先例 | `backtest/research/strategy4_rules.py:33-44`；消费点 `csv_daily_backtest.py:390-402`、`csv_minute_backtest.py:316-324` |
| sell_gate 语义 | 返回 reason 即走 take_profit 同一卖出路径 = **整仓卖出**；无部分卖 | `backtest/research/csv_daily_backtest.py:394-402` |
| lot 记账 | `Position` 每 lot 带 `shares:int`、`is_step`、`pending_exit`；share 级部分卖在结构上可表达（减 `lot.shares`） | `backtest/research/csv_ledger.py:73-87` |
| +20% 台阶 | `step_add_due(lots,px,step)` 相对 lot0 成本每满 +step 且 is_step 数不足则加 | `backtest/research/strategy8_rules.py:56-70` |
| 名单全加 | add_gate=None 且 allow_add=True → 输赢都加 | `backtest/research/csv_simulate_loop.py:179`、`:295` |
| per_name sizing | 书字段 `sizing="per_name"` + `name_budget=1_000_000.0` | `csv_strategy_books.py` version8 注册（本 HEAD 约 `:920-936`） |
| 买因全集 | pool 14:55 / chase 9:45 / step-add 三类；**无买回通道** | `csv_simulate_loop.py` `run_pool_buys_day` / chase / `run_step_adds_day` |
| 里程碑书先例 | 8.1/8.2/8.3 书（`599a894` 合入）：strategyN_rules + 别名注册 + HELP_LOCK + 冻结语义 pin | `tests/test_strategy8_milestones.py` |

## 3) 引擎缺口（本 plan 的真实工作量）

1. **部分减仓**：reason 目前总是整仓卖。需 share 级部分卖出路径（跨 lot FIFO 取整百股）+ 每码「已减仓股数」记忆。
2. **买回**：全新买因。需每码「减仓股数 / 止损股数」状态 + MA 收复判定驱动的买回单，走既有 T+1 / 涨跌停 / 费用 / 容量门。
3. **均线基准止损**：stop 线 = 昨收 MA10×0.90（v4 的 `STOP_PCT=None` + sell_gate 先例可表达，但需与部分减仓共存排序）。

## 4) R\* hard locks

| ID | 硬锁 |
|---|---|
| **R1** | 策略 1–10 及 8.1/8.2/8.3 书行为零变更；现有全量 pytest（1399+）绿且不放宽断言。 |
| **R2** | 部分减仓与买回为 **opt-in 书钩子**（默认 None 关闭）；引擎默认路径零 diff，用既有 pin 测试证明。 |
| **R3** | MA 输入只用截至昨收日线（PIT，v4 先例「刻意不含今日收盘」）；不引入当日未来信息。 |
| **R4** | 买回是普通买单：过 T+1 可卖、涨跌停拦截、佣金、容量 cap；不新增旁路。 |
| **R5** | 新增 reason / trades 标签须带 `ma12:` 前缀区分既有 reason；不改既有 trades schema 列。 |
| **R6** | 文本 UTF-8 无 BOM、NUL=0；新文件 ruff 零告警；数据一律走 resolvers（AGENTS.md 数据盘纪律）。 |
| **R7** | `version11` 编号维持 AGENTS.md 既有预留（ma_chip CSV 移植）；本书一律 `version12`，不占 11。 |

## 5) P\* 人裁点（评审重点；各附建议）

| ID | 问题 | 状态 / 建议 |
|---|---|---|
| **P1 编号** | ~~version11 与 ma_chip 预留冲突~~ | **✅ 已裁（2026-09-21 用户）**：金榕元 0921 = `version12`；docx 已改名；AGENTS.md 预留句不动（R7）。 |
| **P2 MA 口径与时点** | 昨收 MA（PIT）已定（R3）；剩余：判定线用昨收 MA 还是盘中实时 MA、评估/成交时点。 | 选项 P2-A：全昨收 MA 判定（v4 先例，跨引擎一致）。选项 P2-B（建议）：分钟书实时 MA = 昨收序列截 n−1 根 + 当前分钟价（盘中语义忠实，无未来信息），14:55 评估当根成交（v8 时钟先例）；日线近似引擎无盘中数据，退化为昨收 MA + 收盘评估、次日开盘成交（`pending_exit` 先例），HELP_LOCK 明示跨引擎口径差（v8 教训：以分钟为准）。 |
| **P3 减仓 50% 语义** | 按什么减：总持仓股数×50%？含不含台阶 lot？取整规则？ | 全部 lot（含 is_step）合计股数 ×50%，向下取整到 100 股倍数，跨 lot FIFO 卖；不足 100 股不减。 |
| **P4 买回语义** | 买回量、价格、上限、循环次数：MA5 收复买回「减仓股份」、MA10 收复买回「止损筹码」各买回多少？可否无限次减-买循环？ | 各自按记忆股数全额买回（同样取整百股）；买回后状态清零；允许无限次循环（文档无次数限制）；买回资金不足记 skip_cash。 |
| **P5 止损与减仓共存** | 同日同时触发止损线与减仓线时的顺序；止损后 MA5 减仓记忆是否保留。 | 先评止损（更严格线）后评减仓；止损清空该码全部 lot 与减仓记忆，仅留「止损股数」供 MA10 买回。 |
| **P6 加仓基数** | 「一个基数」= 100 万整笔？台阶与名单加仓并存上限？ | 同 v8：名单再现加一整笔 name_budget；+20% 台阶独立 lot；单码单日上限沿用引擎现状（chase+池买 2 笔 + 台阶）。 |
| **P7 上证十日线闸** | 文档未提；v8 有上证闸。 | 以文档为准：**无上证闸**（不接 index gate）；后续要加另开小刀。 |
| **P8 池来源** | 同 8 默认读可变 `stock_pool/`，还是 9/10 式强制 `--pool-dir`？ | 按 8 先例：默认 `stock_pool/`（同源信号族）。 |

## 6) 非目标

- 不动 8.x 里程碑书与 Mode A/B 统一卖出线。
- 不做实盘 / LEBS / MockQMT 接线；不改三仓分工。
- 不实现上证闸、参数化 MA 天数（5/10 写死，同 docx）。
- 不占 `version11`（ma_chip 移植预留，R7）。
- 对比回测数字不入库（除 exports/ 约定）。

## 7) 切片（各一 commit，带完成定义）

| 刀 | 内容 | 完成定义（DoD） |
|---|---|---|
| **A** | `backtest/research/strategy12_rules.py` 纯函数：`sma_asof` 复用、`stop_line(ma10)`、`de_risk_signal(px, closes)`、`reclaim_signal(px, closes)`、`take_profit_reason=None`、HELP_LOCK、record 函数；`tests/test_strategy12_rules.py` data-free pin | 纯函数无引擎 import；边界（历史不足 5/10 根、px≤0）返回 None 有 pin |
| **B** | 引擎 share 级部分卖出：书钩子 `partial_sell_gate(code, px, day, closes) -> Optional[tuple[str, float]]`（reason, fraction）；卖出路径支持按股数跨 lot FIFO；默认 None 时行为与 HEAD 逐字节等价 | 新 pin：部分卖后 lot.shares/cash/trades 正确、整百股取整、既有全量测试零变更全绿 |
| **C** | 买回引擎 + 注册：`buy_back_gate` 钩子 + 每码 reduced/stopped 股数状态 + 资金/T+1/涨跌停门接线；`version12` 注册（别名 `12/v12/version12`，per_name 100 万，HELP_LOCK 进 epilog）；AGENTS.md Research entries 增行 | 引擎级测试：减仓→收复→买回、止损→站回→买回、skip_cash、与 chase/pool/step 共存；`--strategy 12 --help` 冒烟 |
| **D** | 冒烟回测 runbook：daily + minute 各跑 20251023–20260909 窗，与 v8/8.1/8.2/8.3 五点对比；结果记 reviews 目录（数字不 commit，exports 约定除外） | runbook 文档 + data_gaps 清单；无生产代码 diff |

## 8) 验证命令

```powershell
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
D:\anaconda3\envs\vanna312\python.exe -m ruff check backtest/research/strategy12_rules.py <slice B/C 触及文件> tests/test_strategy12*.py
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py --strategy 12 --help
```

## 9) 代码落点

- 新：`backtest/research/strategy12_rules.py`、`tests/test_strategy12_rules.py`、（B/C）`tests/test_partial_sell.py`、`tests/test_strategy12_engine.py`
- 改：`backtest/research/csv_ledger.py`（部分卖 helper + 状态字段）、`csv_simulate_loop.py`（钩子消费）、`csv_daily_backtest.py` / `csv_minute_backtest.py`（钩子传递）、`csv_strategy_books.py`（注册）、`tests/test_csv_strategy_books.py`（清单 pin）、`AGENTS.md`（Research entries 增 version12 行）

## 10) 修订程序

v0.x 草稿 → 多路评审（`docs/architecture/reviews/2026-09-21/plan-strategy12-jinrongyuan/`，宿主机跑 `run_multi_ai_review.py`）→ P2–P8 逐条人裁 → 修订到 vN、状态改「✅ 已人裁 GO（commit hash）」→ 走 [Codex 交接工作流](workflow-codex-handoff.md) 第 4 步起（handoff 文档 → codex 无头实施 → 缺陷优先复核 → 回写）。
