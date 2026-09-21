# Plan: strategy 12 金榕元均线减仓书（2026-09-21）

> **Status**: **v1.0 · ✅ 已人裁 GO（2026-09-21，Asia/Shanghai）**——用户裁定 P2–P13 **全按共识建议**；四个二选一由主持按评审倾向定案：P6 不加闸（P11 latch 天然限流，HELP_LOCK 声明理论上限）、P8 默认 `stock_pool/`（8 先例）、P9④ 新买入（池/chase）**清零**该码双记忆（防双重仓位）、P13 减仓保留 lot0 ≥100 股（保台阶锚）。
> **后续人裁 A（2026-09-21）**：P11 的每日 latch 表述已废止；只有下方周期锁，成功收复并买回后立即再武装，同日可再次减仓，不叠加日锁。以 [handoff §0](handoff-strategy12-codex-impl-2026-09-21.md#0-硬边界人裁已定勿越) 为准。
> **评审链**：主笔对抗层（F1–F8）→ 四稿 fan-out（codex/kimi/cursor/claude 全 rc=0，2 组实验）→ [merge-consensus S1–S19](../architecture/reviews/2026-09-21/plan-strategy12-jinrongyuan/merge-consensus.md)。关键修正：默认路径部分卖静默丢股、v8 wiring 三键绕过 sell_gate、P9④ 改记忆股数上限、价域 front、减仓 latch、台阶单调记忆、14:55 假先例。实施走 [Codex 交接工作流](workflow-codex-handoff.md)（门槛：ma_infra PR #150 已合入；实施 PR 交 VM codex）。
> **业务源**：`E:\PycharmProjects\OSkhQuant1.3\docs\bucket_policy\金榕元交易回测策略--0921-策略12.docx`（金榕元系列第 4 版；前三版 0911/0913/0916 → 策略 8。原名"策略11"，2026-09-21 用户裁决改为 12，docx 已同步改名）。
> **Main ship / 单行范围**：策略 12 = 策略 8 买侧骨架（尾盘涨停 T+1 9:45 确认追买、名单全加、+20% 台阶、per_name 100 万）+ 全新均线出场（昨收 MA5 破线减仓 50% 且收复买回；昨收 MA10 下方 10% 止损且站回买回）。
> **前序**：[workflow-codex-handoff.md](workflow-codex-handoff.md)（本 plan 走 Codex 交接工作流）、[engine-ashare-correctness.md](engine-ashare-correctness.md)（成交核 SSOT，含 E-R5③/E-R6② 价域条款）、[plan-ma-infra-shared-2026-09-21.md](plan-ma-infra-shared-2026-09-21.md)（**前置：v1.0 已 GO、PR #150**；本书切片 A 开工门槛=ma_infra 已合入）、[plan-v8-rules-v2-2026-09-16.md](plan-v8-rules-v2-2026-09-16.md)（v8 书先例）。

---

## 0) One-line scope

新策略书 `version12`：买侧复用 v8 钩子（wiring 四键按 P12 逐键裁决，非整体继承）；卖侧以 MA5/MA10 为轴的部分减仓-止损-买回状态机；**γ 方案（v0.5 扩为三触点）**——① `execute_buy(..., shares_override=None)`（记账 `per=notional`）；② 卖出路径重构支持 `wanted_shares`（默认路径下部分卖现状会**静默丢股**，S1 实验实锤，必须重构 `csv_ledger.py:400-411` 分支）；③ 书侧送转缩放回调（opt-in exdiv hook）。状态机与编排全在书侧，默认参数下现有书 **trades/equity 输出**逐字节等价。

## 1) 业务规则转录（docx 原文，189 字）

| # | 原文 | 工程语义（待 P\* 裁决细化） |
|---|---|---|
| 1 | 单个股票金额 100 万 | per_name 预算 100 万（v8 sizing 先例） |
| 2 | 已持有股再出现加仓一个基数，输赢都加 | 名单全加（v8 `ALLOW_ADD`，add_gate=None） |
| 3 | 个股每涨 20% 加仓一个基数 | +20% 独立台阶（v8 `step_add_due` / `is_step` lot） |
| 4 | 止损：十日线下方 10 个点 | 现价 < 昨收 MA10 × 0.90 → 止损（**均线基准**，非买价基准；P5） |
| 5 | 掉下五日线减仓 50%，重新站上五日线买回减仓股份；重新站上十日线买回止损筹码 | 部分减仓 + 双买回通道（P3/P4/P11；引擎新能力）。**注（kimi 核 docx）：规则 5 在原文标「止盈」** |
| 6 | T 日尾盘涨停不能买入股；T+1 9:45 市价>开盘价买入，<开盘弃买，涨停弃买 | 对应 `chase_decision`（csv_ledger.py:115-121，等值 `px==open→abandon` 属解释性行为入 HELP_LOCK）；T 日拦截在 `csv_simulate_loop.py:285-288`，跨两处 |

## 2) Verified as-built anchors（HEAD `599a894`）

| 合同项 | 当前事实 | 锚点 |
|---|---|---|
| T+1 9:45 追买 | `chase_decision(open,px,limit_up)`：市价>开盘且非涨停→buy；否则 abandon/limit；**T 日尾盘涨停拦截在 `csv_simulate_loop.py:285-288`，规则 6 跨两处实现** | `backtest/research/csv_ledger.py:115-121`；入队 `queue_limit_up_chase` `:124-130` |
| MA 数据通道 | 书钩子 `sell_gate(code, px, day, daily_closes_ending_yesterday)` / `buy_gate(...)` 已把截至昨收日线收盘序列喂给书；策略 4 先例 | `backtest/research/strategy4_rules.py:30-41`；消费点 `csv_daily_backtest.py:390-402`、分钟喂数 `csv_minute_backtest.py:669` |
| sell_gate 语义 | 返回 reason 即走 take_profit 同一卖出路径 = **整仓卖出**；无部分卖 | `backtest/research/csv_daily_backtest.py:394-402` |
| lot 记账 | `Position` 每 lot 带 `shares:int`、`is_step`、`pending_exit`；share 级部分卖结构上可表达，**但 lot_id==0 是台阶锚，部分卖顺序受约束（见 P3）** | `backtest/research/csv_ledger.py:70-82` |
| +20% 台阶 | `step_add_due(lots,px,step)` 相对 lot0 成本每满 +step 且 is_step 数不足则加 | `backtest/research/strategy8_rules.py:57-69` |
| 名单全加 | v8 的 add_gate 实为 `may_add`（`bool(lots) and px>0`，`strategy8_rules.py:52-54`；接线 `csv_strategy_books.py:573`）→ 输赢都加；引擎侧 `lots and callable(add_gate)` 判定 | `backtest/research/csv_simulate_loop.py:179`、`:295` |
| per_name sizing | 书字段 `sizing="per_name"` + `name_budget=1_000_000.0` | `csv_strategy_books.py` version8 注册 `:1018-1031` |
| 买因全集 | pool 14:55 / chase 9:45 / step-add 三类；**无买回通道** | `csv_simulate_loop.py` `run_pool_buys_day` / chase / `run_step_adds_day` |
| 里程碑书先例 | 8.1/8.2/8.3 书（`599a894` 合入）：strategyN_rules + 别名注册 + 冻结语义 pin；**HELP_LOCK 内容 pin 在 `tests/test_csv_strategy_books.py:176-179`**（milestones 文件无 HELP_LOCK 断言） | `tests/test_strategy8_milestones.py` |

## 3) 引擎缺口（本 plan 的真实工作量）

1. **部分减仓**：reason 目前总是整仓卖。需 share 级部分卖出路径（**is_step 先卖、中间层按 lot_id 升序、lot0 最后**，取整百股）+ 每码「已减仓股数」记忆。**S1（实验实锤）：默认路径下部分卖会静默丢股**——`pos.shares -= shares` 仅在 volume_cap/exdiv 分支可达（`csv_ledger.py:400-411`），默认=部分现金入账+整 lot 删除；必须重构该分支。
2. **买回**：全新买因（第四买因）。需每码「减仓/止损股数」状态 + MA 收复判定驱动的买回单，走既有 T+1 / 涨跌停 / 费用 / 容量门。**S2：三签名契约见切片 B**；模板= `run_step_adds_day`（`csv_simulate_loop.py:322-395`）。
3. **均线基准止损**：stop 线 = MA10×0.90（P12 裁 wiring 键后经书侧编排表达；STOP_PCT 路径先于 sell_gate 整笔触发 `csv_daily_backtest.py:353-378`，不可直接继承）。

> **⚠️ 评审修正（对抗层 F1–F8 + 四稿 S1–S19）**：
> - 四锁：`execute_buy`（`:232-248`）无 shares 覆写（`_buy_size:219-229` 由预算推导）；减仓基数=t1_sellable lots 且**扣 locked bonus**（`_sell` 本体无 T+1，仅 volume_cap 分支 `:347`；`:332` 锁定送转股静默缩减）；送转不缩放记忆股数（`:174-182` 入 lot、`:152-156` rescale 不动 shares）；买回上限=**记忆股数**（S4，市值帽已否决）。
> - 不可复用 `pending_exit`（per-lot 字符串 `csv_ledger.py:79`；锁定送转股整笔延期 `:326-336`、容量 atomic 全或无在 `:354`）→ 独立部分卖队列（**日线**的次日开盘通道是主要载体；分钟可当根成交）。
> - 台阶计数须改**单调记忆**（S9：`strategy8_rules.py:67-69` 只数活着 的 is_step lot，减仓卖掉即重加 → 换手循环）。
> - 记忆挂 `st`（S11：模块级 dict 跨 run/pytest 串味；out-param 先例 `reserve_state` `csv_minute_backtest.py:648,677`）；记忆按**实际成交量**更新（S10：cap 部分分配 `:359`）。
> - stats 桶：**复用既有 `ma_signal:` 前缀**（`:394` 已有分支；S19，弃 `ma12:` 新前缀）。
> - scan_held_day 5-tuple 有 24 个测试调用点（S12）→ 部分卖走 out-param，勿扩元组。

## 4) R\* hard locks

| ID | 硬锁 |
|---|---|
| **R1** | 策略 1–10 及 8.1/8.2/8.3 书行为零变更；现有全量 pytest（**collect-only 钉死 1401**，kimi 实测）绿且不放宽断言。 |
| **R2** | 部分减仓与买回为 **opt-in 书钩子**（默认 None 关闭）；引擎默认路径零 diff，用既有 pin 测试证明。 |
| **R3** | MA **序列**只用截至昨收日线（PIT，v4 先例）；现价仅作探测值、不入 MA 序列；不引入当日未来信息。 |
| **R4** | 买回是普通买单：过 T+1 可卖、涨跌停拦截、佣金、容量 cap；不新增旁路；且受 P9 四锁约束。 |
| **R5** | 新增 reason / trades 标签**复用既有 `ma_signal:` 前缀**（如 `ma_signal:MA5-derisk` / `ma_signal:MA10-stop`，`csv_ledger.py:394` 已有分支，S19 弃 `ma12:` 新前缀）；不改既有 trades schema 列。 |
| **R6** | 文本 UTF-8 无 BOM、NUL=0；新文件 ruff 零告警；数据一律走 resolvers（AGENTS.md 数据盘纪律）。 |
| **R7** | `version11` 编号维持 AGENTS.md 既有预留（ma_chip CSV 移植）；本书一律 `version12`，不占 11。 |
| **R8** | MA 一律消费共享基础设施 [ma_infra](plan-ma-infra-shared-2026-09-21.md)（`sma_asof`/`sma_live`）；书内不自写均线。 |

## 5) P\* 人裁点（评审重点；各附建议）

| ID | 问题 | 状态 / 建议 |
|---|---|---|
| **P1 编号** | ~~version11 与 ma_chip 预留冲突~~ | **✅ 已裁（2026-09-21 用户）**：金榕元 0921 = `version12`；docx 已改名；AGENTS.md 预留句不动（R7）。 |
| **P2 MA 口径与时点（S8 改写）** | 昨收 MA（PIT）已定（R3）；分钟卖侧评估口径：**「14:55 评估」是假先例**（kimi K2 实证：卖侧是逐分钟扫描首触即发 `csv_minute_backtest.py:285-329`，14:55 是买侧时钟）。 | 选项 a：**逐分钟口径**（sell_gate 天然通道，破线当根成交，语义最忠实）；选项 b：**日内 latch**（全新机制，每日单次评估，防盘中来回打脸，须自立论据）。日线两选项下都=昨收 MA + 收盘评估、次日开盘成交。建议 a + P11 latch 防打脸，人裁。 |
| **P3 减仓 50% 语义** | 按什么减：总持仓股数×50%？含不含台阶 lot？取整规则？卖哪些 lot？ | **t1_sellable** lot（含 is_step）合计股数 ×50%，向下取整到 100 股倍数；**is_step lot 先卖、lot_id==0 最后**（保台阶锚 `strategy8_rules.py:61-64`）；不足 100 股不减。 |
| **P4 买回语义** | 买回量、价格、上限、循环次数：MA5 收复买回「减仓股份」、MA10 收复买回「止损筹码」各买回多少？可否无限次减-买循环？ | 各自按记忆股数全额买回（同样取整百股）；买回后状态清零；允许无限次循环（文档无次数限制）；买回资金不足记 skip_cash。 |
| **P5 止损与减仓共存** | 同日同时触发止损线与减仓线时的顺序；止损后 MA5 减仓记忆是否保留；止损当日同时 MA10 站回（旧记忆）的共存。 | 先评止损（更严格线）后评减仓；止损清空该码全部 lot，**减仓与止损双记忆并存**（docx 规则 5 无作废条款）；止损当日 MA10 站回买回照常评估（**同日先卖后买**）；P4 清零=各清各的（MA5 收复只清减仓记忆、MA10 只清止损记忆）。 |
| **P6 加仓基数（S18 改写）** | 「一个基数」=100 万整笔；单码单日买向上限——**引擎无任何闸**（「2 笔」是调度涌现非机制；加买回后日买向=池 1+chase 1+台阶 N+买回 2）。 | 名单再现加一整笔 name_budget（同 v8）；台阶=单调记忆（S9）；是否加单码单日买向闸（≤N 笔或 notional 上限）**交人裁**（不加=接受理论 5+ 笔/日）。 |
| **P7 上证十日线闸** | 文档未提；v8 有上证闸。 | 以文档为准：**无上证闸**（不接 index gate）；后续要加另开小刀。 |
| **P8 池来源** | 同 8 默认读可变 `stock_pool/`，还是 9/10 式强制 `--pool-dir`？**同族反例：v7（金榕元）是 `--pool-dir` 必填不回落**（AGENTS.md:13）。 | 8 先例（默认 `stock_pool/`）vs v7 先例（强制）都上桌，人裁；v12 与 v7 的分工/入口差异写进 AGENTS.md 增行。 |
| **P9 买回四锁（对抗层新增，④ 按共识 S4 改写）** | ① 买回下单需 shares 覆写（`execute_buy:232-248` 无）；② 减仓基数 T+1 过滤+扣 locked bonus；③ 送转日记忆按 k 缩放（floor100+残余记 stats）；④ 买回上限。 | ① `shares_override=None`（γ 面，`per=notional` 记账）；② 见 P3；③ 按 k 缩放、现金红利不动；④ **上限=该通道记忆股数**（市值帽已三票否决——会饿死买回）；新买入与记忆的**冲抵规则**两选项：池/chase 新买入时清零记忆 vs 新买股数先冲抵记忆，人裁。 |
| **P10 价域（S5 新增）** | MA 序列用 none（默认）还是 front？none 域下 10 送 10 会使 MA5/10 跳变 → **假整仓止损**（codex 算例）；E-R5③ 的 none 是 v4 历史噪声保留，不能为 MA10×0.90 止损背书。 | 建议 **front**（日线 `dividend_type=front` 同时关 E-R6 remap，二选一可执行 `csv_daily_backtest.py:600-604`；分钟侧需 `--daily-source qlib_day` 或新增参数）；写进切片 D runbook、HELP_LOCK、data_gaps；v4 同源问题注明不悄悄分叉。人裁。 |
| **P11 减仓重入（S6 新增）** | 连续多日收在 MA5 下方：每日再减 50%（几何衰减+累加买回脉冲）还是只减一次？逐分钟口径下日内反复穿越？ | 建议**同一「下方周期」只减一次（latch），收复清零后再武装**；逐分钟口径下每通道每日一次 latch 防打脸；入切片 C pin（连续 N 日 MA5 下方场景）。人裁。 |
| **P12 wiring 四键（S3 新增）** | `reserve_limit_up` / `defer_limit_up` / `daily_same_bar_prefixes` / `STOP_PCT` + MA 通道 `peak_gap_min`：v8 的 `("open_board",)` 路径整仓卖**绕过 sell_gate 与双记忆**；STOP_PCT 路径先于 sell_gate 整笔触发；`PEAK_GAP_MIN=15` 继承会压后 MA 闸 15 分钟。 | 建议 v12：`reserve_limit_up=False`、`defer_limit_up=False`、`daily_same_bar_prefixes=()`、书侧自管止损（不用引擎 STOP_PCT 路径）、MA 通道 `peak_gap_min=0`——全部走书侧状态机单一入口，记忆不漏。人裁确认。 |
| **P13 lot0 保底（kimi K5 新增）** | 减仓可能耗尽 lot0 → `step_add_due` 的 `parent is None` → 台阶永久停加。 | 两选项：减仓**保留 lot0 ≥100 股**（减额缩水）vs 明示接受台阶终止（HELP_LOCK 声明），人裁。 |

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
| **B** | 引擎最小面（γ 三触点）：① `execute_buy(..., shares_override=None)`（记账 `per=notional`）；② **重构 `csv_ledger.py:400-411` 卖出分支**（`pos.shares -= shares` 提到条件外、非零余股保留 lot、空 lot 才删——S1 丢股修复）；③ 书侧 exdiv 缩放回调（opt-in）。契约签名（S2）：`exit_plan(code,px,day,closes,lots)->(reason,shares)|None`、`buyback_plan(...)->int`、`run_buybacks_day` 照 `run_step_adds_day` 模板；hooks setdefault 同步登记 | 新 pin：**部分卖后 Σlot.shares 与 cash 守恒**、lot0 保底最后、整百股、**记忆按实际成交量更新**（cap 部分分配 `:359`）、台阶**单调记忆**（减仓后同段不重加）、默认参数下 trades/equity **输出**逐字节等价、既有 1401 零变更全绿 |
| **C** | 书侧状态机 + 买回 + 注册：记忆挂 `st`（S11，勿模块级 dict）；scan_held_day 走 **out-param**（S12，勿扩 5-tuple）；**exdiv 测试显式开启** `exdiv_economics`（S15）；减仓 latch（P11）；`version12` 注册（别名 `12/v12/version12`，per_name 100 万，HELP_LOCK 进 epilog，含费用偏差/chase 等值/容量不整百声明）；AGENTS.md Research entries 增行（含 v7 分工） | 引擎级测试：减仓→收复→买回、止损→站回→买回（同日先卖后买）、**连续 N 日 MA5 下方只减一次**、送转日记忆缩放（exdiv 开启）、当日买回当日不可再减（T+1）、skip_cash、与 chase/pool/step 共存、单日买向笔数（按 P6 裁决）；`--strategy 12 --help` 冒烟 |
| **D** | 冒烟回测 runbook：daily + minute 各跑 20251023–20260909 窗（**价域按 P10 裁决写进命令**，分钟侧 `--daily-source qlib_day` 或新参数）；与 v8/8.1/8.2/8.3 五点对比；结果记 reviews 目录（数字不 commit，exports 约定除外） | runbook 文档 + data_gaps 清单（含价域声明）；无生产代码 diff |

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

v0.x 草稿 → 主笔侧对抗层（✅ 2026-09-21）→ 四稿 fan-out + merge-consensus（✅ 2026-09-21，S1–S19）→ **P2–P13 逐条人裁** → 修订到 vN、状态改「✅ 已人裁 GO（commit hash）」→ 走 [Codex 交接工作流](workflow-codex-handoff.md)（**门槛：ma_infra（PR #150）已合入；实施 PR 交 grok bot VM codex**）。
