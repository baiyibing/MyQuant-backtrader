# 真核大票 · C-New · X2 更富订单 · 提议合同 id 冻结（2026-10-03）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-03（Asia/Shanghai / CST） |
| tip 基线 | `19b7be52`（master · #317 MERGED · X2–X5 菜单） |
| 方案锚 | PLAN §3.2 X2、§3.3、§4 TC5；[X2–X5 菜单](note-true-core-x2-x5-contract-draft-2026-10-03.md)（#317）；[TC1](note-true-core-c-new-tc1-contract-2026-10-02.md)；[S0](note-l2-s0-minute-orders-contract-2026-09-29.md) |
| 本刀 | **docs-only**。把菜单里的 X2 提议合同 id 冻成下一刀的名字。**不**铸 `backend_id`，**不**把该字符串写入代码 |
| 触发 | #317 合入后的 Human「GO」。菜单写明该 PR **不是**四轴实施 GO。本刀把这次 GO **收窄为 X2 合同冻结**，不开 X3/X4/X5，不实现订单引擎 |
| 硬约束 | 码之前仍须 Human **点名** live `backend_id`（H-TC5-ID）。触及 S0 排除则**禁止复用 v0**。≠δ5≠R4；无 4090；无写湖；空核 |

> **本 note = X2 提议合同 id 的冻结草案。不是 mint，不是订单引擎，不是已铸 `backend_id`，不是绿 R。**
> #317 只登记了四轴菜单。Human 随后的「GO」在这里只覆盖 **X2**。X3 / X4 / X5 仍是 **NOT implemented**，本刀零句实施许可。
> 菜单写明：未裁 `backend_id` 之前，禁止把草案字符串写进注册表、artifact 根或测试常量。因此本刀 **没有代码**，也没有「拒绝生产使用」的 stub 模块——stub 仍是码，会把身份带进仓库。
> **≠δ5 certified ≠R4；无 4090；无写湖；空核**（MatchCore / Fees / `simulate` / `source_loader` / CLI / `views._FAMILIES` 本刀零 diff）。

## 1. 本刀冻结什么

只冻结 **一个提议合同 id**，而且只在文档里：

| 项 | 字符串 | 身份 |
|---|---|---|
| X2 提议合同 id | `draft-only/x2-richer-orders` | **本刀冻结的提议名**。沿用 #317 菜单，不另造经济 `contract_version`。不是 at-rest 合同字符串，不是已批准身份，**禁止**复制进 Python / 测试 / CI / HELP / 注册表 / artifact 根 |
| X2 backend 槽 | `UNMINTED_NOT_A_BACKEND_ID_x2` | **不是** `backend_id`。占位短语，表示「还没铸」。本刀 **不**发明、**不**占用任何 live id |
| X3 / X4 / X5 | 菜单原标签不动 | 本 GO **不**冻结它们，**不**开工 |

`draft-only/x2-richer-orders` 从「四轴菜单里的未批准标签」收成「X2 下一刀将使用的提议合同 id」。收成提议名 **≠** 铸成 live `contract_version`。

## 2. 还缺的那一刀 Human 裁断

码仍然禁止。菜单与 PLAN H-TC2 要求：经济语义变化必须 **新 contract + 新 backend_id**。本刀只冻了提议合同 id。还缺的 **唯一**裁断：

| ID | 裁断 | 本刀状态 |
|---|---|---|
| **H-TC5-ID（X2）** | Human **点名**一个 live `backend_id` 字符串，并书面确认「这就是 X2 的 backend_id，可以铸」 | **未裁**。本 PR 不提案、不占用、不写入代码。在该字符串被点名之前，禁止任何 X2 模块、常量、测试、CLI、注册 |

这次 GO **没有**提供该名字。不得把 `UNMINTED_NOT_A_BACKEND_ID_x2` 或任何本 note 未出现的新字符串当成已经授权的 `backend_id`。

点名之后的码刀（**不是本 PR**）还须同时满足、且本刀不预做：

- 新模块名（H-TC5）。X2 是 stop / market-on-bucket / 日内模板，整轴落在 S0「Lifecycle LIMIT-only；无 stop / market / replace / GTC」之外。**不得**改写 `match_candidates` / `compute_bucket_capacity` / Fees / `simulate` 的现语义，也不得写回 `research contract v0 (L2-S0)` / `minute_orders_research_v1` 的 oracle 或 golden。
- 不翻转默认 backend。现有三支 L1 entry 与 v0 旁路冻结。永 opt-in。不以 BOOKS 默认为验收。
- 不声称交易所队列。不 undo 旧 hl / Q39。对照仍是红标签，不是绿 R。

## 3. 能力边界（登记，不实现）

PLAN §3.2 的 X2 原句能力仍是：stop / market-on-bucket / 日内模板（研究近似）。本刀只给这句一个冻结的提议合同名，**不**定义字段、撮合顺序、费用或工件 schema。那些属于 backend_id 裁完之后的码刀，另 GO。

明确不做：

| 不做 | 原因 |
|---|---|
| 订单引擎 / stub 模块 / 测试常量 | 菜单：`backend_id` 未裁前出现新身份常量 = 越权 mint |
| 改 MatchCore / Fees / `simulate` | H-TC4 / H-TC5；破坏现语义须新模块名，且仍须独立 GO。本刀连新模块也不建 |
| X3 报价路径、X4 多账户、X5 向量/批 | 本次 GO 只收窄到 X2。H-TC3：第二种价格模型不是默认下一刀 |
| 4090 / 生产写湖 / 绿 R / BOOKS 默认 | 仍锁 |

## 4. 冻结对象（本刀不改）

| 对象 | 现字符串 | 本刀 |
|---|---|---|
| 经济合同 | `research contract v0 (L2-S0)` | 继续冻结。X2 **不得**写回其 oracle / golden |
| backend | `minute_orders_research_v1` | 继续冻结。上表占位 **不是**它的别名，也不是新 id |
| 现有三支 L1 entry | 永 opt-in | 不改委托语义，不改默认 backend |

## 5. 负面清单（本 PR diff 须空）

| 路径 | 本刀 |
|---|---|
| `backtest/research/minute_orders_backend/match.py` | 空 |
| `backtest/research/minute_orders_backend/fees.py` | 空 |
| `csv_minute_backtest.py`（含 `simulate`）/ `csv_minute_backtest_v7.py` | 空 |
| `backtest/research/minute_orders_backend/source_loader.py` | 空 |
| `backtest/research/minute_orders_backend/cli.py` | 空 |
| `backtest/research/run_protocol/views.py` | 空；`_FAMILIES` 不塞新族 |
| 任何新 `backend_id` / `contract_version` 常量，含 stub | **不出现** |
| 4090bot / 生产写湖 / `--write-lake` | 不派、不写 |
| X3 / X4 / X5 的码或新合同正文 | 不出现 |

## 6. 指针

- PLAN（本机，仓外）：`/workspace/handoffs/minute_engine_true_core_new_20261002/PLAN.md` §3.2 X2、§3.3、§4 TC5
- 菜单（#317）：[note-true-core-x2-x5-contract-draft-2026-10-03.md](note-true-core-x2-x5-contract-draft-2026-10-03.md)
- TC1：[note-true-core-c-new-tc1-contract-2026-10-02.md](note-true-core-c-new-tc1-contract-2026-10-02.md)
- S0：[note-l2-s0-minute-orders-contract-2026-09-29.md](note-l2-s0-minute-orders-contract-2026-09-29.md)
- industry §7：[industry-state-acceptance-index-2026-09-28.md](industry-state-acceptance-index-2026-09-28.md)

**≠δ5 certified ≠R4；无 4090；无写湖；空核。无代码落地。X2 提议合同 id 冻结为 `draft-only/x2-richer-orders`，不是 live `contract_version`。仍缺 Human 点名 live `backend_id`（H-TC5-ID）。X3/X4/X5 不开。本刀 draft，勿合，直至 Human「合」。**
