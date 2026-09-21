# Plan: strategy 12 金榕元均线减仓书（2026-09-21）

> **Status**: **v0.4 · draft（已吸收主笔侧 3 路对抗评审；P1 已预裁，P2–P9 待外部四稿 + 人裁，GO 前禁编码）**。风险档：**中高**——部分减仓 + 买回记账触及股数/现金流不变量；书侧全新，无历史基线。
> **对抗回填（2026-09-21）**：3 路子代理评审吸收 F1–F8——部分卖改 **is_step 先卖、lot0 最后**（lot_id==0 台阶锚不变量）；「通用引擎钩子」降为 **γ 最小引擎面 + 书侧状态机**；R3 措辞修正（现价为探测值不入 MA 序列）；P5 改**双记忆并存**；新增 **P9 买回四锁**；锚点行号全套勘误。草案：[review-by-claude](../architecture/reviews/2026-09-21/plan-strategy12-jinrongyuan-2026-09-21-review-by-claude.md)。
> **业务源**：`E:\PycharmProjects\OSkhQuant1.3\docs\bucket_policy\金榕元交易回测策略--0921-策略12.docx`（金榕元系列第 4 版；前三版 0911/0913/0916 → 策略 8。原名"策略11"，2026-09-21 用户裁决改为 12，docx 已同步改名）。
> **Main ship / 单行范围**：策略 12 = 策略 8 买侧骨架（尾盘涨停 T+1 9:45 确认追买、名单全加、+20% 台阶、per_name 100 万）+ 全新均线出场（昨收 MA5 破线减仓 50% 且收复买回；昨收 MA10 下方 10% 止损且站回买回）。
> **前序**：[workflow-codex-handoff.md](workflow-codex-handoff.md)（本 plan 走 Codex 交接工作流）、[engine-ashare-correctness.md](engine-ashare-correctness.md)（成交核 SSOT）、[plan-ma-infra-shared-2026-09-21.md](plan-ma-infra-shared-2026-09-21.md)（**前置：共享均线基础设施，本 plan 实施时直接消费**）、[plan-v8-rules-v2-2026-09-16.md](_archive/plans/plan-v8-rules-v2-2026-09-16.md)（v8 书先例）。

---

## 0) One-line scope

新策略书 `version12`：买侧复用 v8 钩子（含其 wiring delta，见 §2 注）；卖侧以 MA5/MA10 为轴的部分减仓-止损-买回状态机；**γ 方案**——引擎只加最小面（`execute_buy` 可选 shares 覆写、卖出路径可选 wanted_shares），状态机与编排全在书侧，默认参数下现有书零行为变更。

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
| T+1 9:45 追买 | `chase_decision(open,px,limit_up)`：市价>开盘且非涨停→buy；否则 abandon/limit；**T 日尾盘涨停拦截在 `csv_simulate_loop.py:285-288`，规则 6 跨两处实现** | `backtest/research/csv_ledger.py:115-121`；入队 `queue_limit_up_chase` `:124-130` |
| MA 数据通道 | 书钩子 `sell_gate(code, px, day, daily_closes_ending_yesterday)` / `buy_gate(...)` 已把截至昨收日线收盘序列喂给书；策略 4 先例 | `backtest/research/strategy4_rules.py:30-41`；消费点 `csv_daily_backtest.py:390-402`、分钟喂数 `csv_minute_backtest.py:669` |
| sell_gate 语义 | 返回 reason 即走 take_profit 同一卖出路径 = **整仓卖出**；无部分卖 | `backtest/research/csv_daily_backtest.py:394-402` |
| lot 记账 | `Position` 每 lot 带 `shares:int`、`is_step`、`pending_exit`；share 级部分卖结构上可表达，**但 lot_id==0 是台阶锚，部分卖顺序受约束（见 P3）** | `backtest/research/csv_ledger.py:70-82` |
| +20% 台阶 | `step_add_due(lots,px,step)` 相对 lot0 成本每满 +step 且 is_step 数不足则加 | `backtest/research/strategy8_rules.py:57-69` |
| 名单全加 | v8 的 add_gate 实为 `may_add`（恒 True，csv_strategy_books.py:573）→ 输赢都加；引擎侧 `lots and callable(add_gate)` 判定 | `backtest/research/csv_simulate_loop.py:179`、`:295` |
| per_name sizing | 书字段 `sizing="per_name"` + `name_budget=1_000_000.0` | `csv_strategy_books.py` version8 注册 `:1018-1031` |
| 买因全集 | pool 14:55 / chase 9:45 / step-add 三类；**无买回通道** | `csv_simulate_loop.py` `run_pool_buys_day` / chase / `run_step_adds_day` |
| 里程碑书先例 | 8.1/8.2/8.3 书（`599a894` 合入）：strategyN_rules + 别名注册 + HELP_LOCK + 冻结语义 pin | `tests/test_strategy8_milestones.py` |

## 3) 引擎缺口（本 plan 的真实工作量）

1. **部分减仓**：reason 目前总是整仓卖。需 share 级部分卖出路径（跨 lot FIFO 取整百股）+ 每码「已减仓股数」记忆。
2. **买回**：全新买因。需每码「减仓股数 / 止损股数」状态 + MA 收复判定驱动的买回单，走既有 T+1 / 涨跌停 / 费用 / 容量门。
3. **均线基准止损**：stop 线 = 昨收 MA10×0.90（v4 的 `STOP_PCT=None` + sell_gate 先例可表达，但需与部分减仓共存排序）。

> **⚠️ 评审修正（2026-09-21 对抗层，草案 F1–F8）**：
> - 缺口 1 须并四锁：`execute_buy` 无 shares 覆写（csv_ledger.py:219-229）；减仓基数须=t1_sellable lots（`_sell` 本体无 T+1 检查，仅 volume_cap 分支 `:347`）；**送转不缩放记忆股数**（`:174-182` 增股入 lot、`:152-156` rescale 不动 shares；bonus 股可破坏整百股）；买回+池再买可破 per_name 100 万合计上限（`csv_simulate_loop.py:253-254` skip_held 仅挡持仓中）→ 全部并入 P9。
> - 缺口 1 不能复用 `pending_exit`（per-lot 字符串 `csv_ledger.py:79`，volume_cap 下全或无 `:333-336`）→ 需独立部分卖队列。
> - `ma12:` reason 会落错 stats 桶（`csv_ledger.py:384-397` 无分支）→ R5 扩 stats。
> - 落点采 **γ**：最小引擎面（shares 覆写 + wanted_shares）+ 书侧状态机，不做注册表级通用钩子。

## 4) R\* hard locks

| ID | 硬锁 |
|---|---|
| **R1** | 策略 1–10 及 8.1/8.2/8.3 书行为零变更；现有全量 pytest（1399+）绿且不放宽断言。 |
| **R2** | 部分减仓与买回为 **opt-in 书钩子**（默认 None 关闭）；引擎默认路径零 diff，用既有 pin 测试证明。 |
| **R3** | MA **序列**只用截至昨收日线（PIT，v4 先例）；现价仅作探测值、不入 MA 序列；不引入当日未来信息。 |
| **R4** | 买回是普通买单：过 T+1 可卖、涨跌停拦截、佣金、容量 cap；不新增旁路；且受 P9 四锁约束。 |
| **R5** | 新增 reason / trades 标签带 `ma12:` 前缀，**并在 stats 分派加 ma12 桶**（csv_ledger.py:384-397）；不改既有 trades schema 列。 |
| **R6** | 文本 UTF-8 无 BOM、NUL=0；新文件 ruff 零告警；数据一律走 resolvers（AGENTS.md 数据盘纪律）。 |
| **R7** | `version11` 编号维持 AGENTS.md 既有预留（ma_chip CSV 移植）；本书一律 `version12`，不占 11。 |
| **R8** | MA 一律消费共享基础设施 [ma_infra](plan-ma-infra-shared-2026-09-21.md)（`sma_asof`/`sma_live`）；书内不自写均线。 |

## 5) P\* 人裁点（评审重点；各附建议）

| ID | 问题 | 状态 / 建议 |
|---|---|---|
| **P1 编号** | ~~version11 与 ma_chip 预留冲突~~ | **✅ 已裁（2026-09-21 用户）**：金榕元 0921 = `version12`；docx 已改名；AGENTS.md 预留句不动（R7）。 |
| **P2 MA 口径与时点** | 昨收 MA（PIT）已定（R3）；剩余：判定线用昨收 MA 还是盘中实时 MA、评估/成交时点。 | 选项 P2-A：全昨收 MA 判定（v4 先例，跨引擎一致）。选项 P2-B（建议）：分钟书实时 MA = 昨收序列截 n−1 根 + 当前分钟价（盘中语义忠实，无未来信息），14:55 评估当根成交（v8 时钟先例）；日线近似引擎无盘中数据，退化为昨收 MA + 收盘评估、次日开盘成交（`pending_exit` 先例），HELP_LOCK 明示跨引擎口径差（v8 教训：以分钟为准）。 |
| **P3 减仓 50% 语义** | 按什么减：总持仓股数×50%？含不含台阶 lot？取整规则？卖哪些 lot？ | **t1_sellable** lot（含 is_step）合计股数 ×50%，向下取整到 100 股倍数；**is_step lot 先卖、lot_id==0 最后**（保台阶锚 `strategy8_rules.py:61-64`）；不足 100 股不减。 |
| **P4 买回语义** | 买回量、价格、上限、循环次数：MA5 收复买回「减仓股份」、MA10 收复买回「止损筹码」各买回多少？可否无限次减-买循环？ | 各自按记忆股数全额买回（同样取整百股）；买回后状态清零；允许无限次循环（文档无次数限制）；买回资金不足记 skip_cash。 |
| **P5 止损与减仓共存** | 同日同时触发止损线与减仓线时的顺序；止损后 MA5 减仓记忆是否保留。 | 先评止损（更严格线）后评减仓；止损清空该码全部 lot，**减仓与止损双记忆并存**（docx 规则 5 对减仓股份买回无作废条款；MA5 收复先于 MA10 时减仓筹码不被压到慢通道）。 |
| **P6 加仓基数** | 「一个基数」= 100 万整笔？台阶与名单加仓并存上限？ | 同 v8：名单再现加一整笔 name_budget；+20% 台阶独立 lot；单码单日上限沿用引擎现状（chase+池买 2 笔 + 台阶）。 |
| **P7 上证十日线闸** | 文档未提；v8 有上证闸。 | 以文档为准：**无上证闸**（不接 index gate）；后续要加另开小刀。 |
| **P8 池来源** | 同 8 默认读可变 `stock_pool/`，还是 9/10 式强制 `--pool-dir`？ | 按 8 先例：默认 `stock_pool/`（同源信号族）。 |
| **P9 买回四锁（对抗层新增）** | ① 买回下单需 shares 覆写（`execute_buy` 现由预算推导）；② 减仓基数 T+1 过滤；③ 送转日记忆股数按 k 缩放（bonus 破坏整百股时取整规则）；④ per_name 合计上限语义（持仓市值 vs 累计投入）。 | ① 引擎加 `shares_override=None`（γ 面）；② 见 P3；③ 按 k 比例缩放记忆股数、现金红利不动；④ 建议「当日该码市值+在途买回 ≤100 万」，人裁。 |

## 6) 非目标

- 不动 8.x 里程碑书与 Mode A/B 统一卖出线。
- 不做实盘 / LEBS / MockQMT 接线；不改三仓分工。
- 不实现上证闸、参数化 MA 天数（5/10 写死，同 docx）。
- 不占 `version11`（ma_chip 移植预留，R7）。
- 对比回测数字不入库（除 exports/ 约定）。

## 7) 切片（各一 commit，带完成定义）

| 刀 | 内容 | 完成定义（DoD） |
|---|---|---|
| **A** | `backtest/research/strategy12_rules.py` 纯函数：**消费 [ma_infra](plan-ma-infra-shared-2026-09-21.md) 的 `sma_asof`/`sma_live`**、`stop_line(ma10)`、`de_risk_signal(px, closes)`、`reclaim_signal(px, closes)`、`take_profit_reason=None`、HELP_LOCK、record 函数；`tests/test_strategy12_rules.py` data-free pin | 纯函数无引擎 import；边界（历史不足 5/10 根、px≤0）返回 None 有 pin |
| **B** | 引擎最小面（γ）：`execute_buy(..., shares_override=None)`；卖出路径可选 `wanted_shares`（t1_sellable 基数、is_step 先卖、整百股）；**独立部分卖队列**（不复用 pending_exit）；默认参数行为与 HEAD 逐字节等价 | 新 pin：部分卖后 lot.shares/cash/trades 正确、**lot0 保底最后**、整百股取整、`ma12:` stats 桶、既有全量测试零变更全绿 |
| **C** | 书侧状态机 + 买回 + 注册：每码 reduced/stopped 股数记忆（书侧 dict + 送转缩放回调）、买回编排走既有门（P9 四锁）、`version12` 注册（别名 `12/v12/version12`，per_name 100 万，HELP_LOCK 进 epilog）；AGENTS.md Research entries 增行 | 引擎级测试：减仓→收复→买回、止损→站回→买回、**送转日记忆缩放**、**当日买回当日不可再减（T+1）**、skip_cash、与 chase/pool/step 共存；`--strategy 12 --help` 冒烟 |
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

v0.x 草稿 → 主笔侧对抗层（✅ 2026-09-21 完成，见头部链接）→ 多路评审（`docs/architecture/reviews/2026-09-21/plan-strategy12-jinrongyuan/`，宿主机跑 `run_multi_ai_review.py`）→ P2–**P9** 逐条人裁 → 修订到 vN、状态改「✅ 已人裁 GO（commit hash）」→ 走 [Codex 交接工作流](workflow-codex-handoff.md) 第 4 步起（handoff 文档 → codex 无头实施 → 缺陷优先复核 → 回写）。
