# version1 → 真核 · 第一本分钟书接线被挡住（2026-10-03）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-03（Asia/Shanghai / CST） |
| tip 基线 | `19b7be520a97157a9f2b41d7a6d7dc372a51e91e`（master · #317） |
| 本刀 | **docs-only**。点名第一本已接线分钟书，并写明它为什么还不能改走真核 |
| 选定策略 | **version1**（`BOOK-version1`） |
| 旧入口 | `csv_minute_backtest.py --strategy version1`（共享 CLI；#299 / #300 P2 shell 已接） |
| 硬约束 | 不造适配器；不改 MatchCore / Fees / `simulate`；不翻转任何书的默认路径；不删旧码；≠δ5≠R4；无写湖；无 4090；**勿合** |

> **旧路径不是终点，也不是永久默认。** 终点是：这本书的订单能被真核接住并真实跑通，然后**全部**分钟策略改走真核，旧入口退役删除。本刀做不到这一步，因为下面这个字段不接受 version1 的订单。所以本刀**不**把 version1 的默认调用改到真核，**不**删旧入口，**不**动其余书。

## 1. 为什么是 version1

#300 时代已经接上 P2 shell 的分钟入口里，共享 CSV 书按版本号从 version1 起。它是最小、已有文档的第一本（`strategy1_rules`：止损 2%、利润回撤 50% 止盈；不加仓）。v7 / APP / TopK / S8 变体 / version12 都更大。本刀只处理这一本。

其余已接线入口（version2–version12、topk_*、v7、APP、L2 `minute_orders`、敏感格、FLAG-*）**本刀不改默认、不接线**。

## 2. 挡住接线的字段

真核 v0 命令上的 **`SubmitOrder.order_type`**。

| 位置 | 字段 | 合同 |
|---|---|---|
| `minute_orders_backend/types.py` `SubmitOrder` | `order_type: Literal["LIMIT"] = "LIMIT"` | 只有 LIMIT |
| 同文件 `LimitOrderMatchInput.order_type` | 同上；`!= "LIMIT"` → `MatchContractError("only LIMIT orders are supported")` | 撮合快照同样只收 LIMIT |
| `minute_orders_intent_x1/builders.py` `LimitIntent.order_type` | `Literal["LIMIT"]`；其它值 → `IntentBuildError("only LIMIT intents are supported (no stop/market/replace/GTC)")` | 事前冻结批次也只收 LIMIT |

version1 不产生这个字段能接住的订单：

| 旧书实际发出的 | 落点 | 为什么塞不进 `order_type="LIMIT"` |
|---|---|---|
| 卖出 `reason` = `stop_loss:touch` / `stop_loss:gap_open` | `csv_minute_backtest` 持仓扫描 | 触发来自 `strategy1_rules.STOP_PCT = 0.02`，不是事前限价。`SubmitOrder` 上没有 `stop_pct` / 触发价字段 |
| 卖出 `reason` = `profit_take:drawdown:50` | `strategy1_rules.take_profit_reason` | 利润回撤 50%。同样不是 LIMIT，也没有对应命令字段 |
| 买入 `reason` = `pool` | 共享 `simulate` 核内按池下单 | 不是事前冻结的 `LimitIntent`。TC1 禁止把核内名单扫描写回 v0 |

把止损价写进 `SubmitOrder.limit` 会冒充 LIMIT，并把 `completed_bucket_close` 说成触价/跳空成交。那是假适配器，本刀不做。

价格模型也过不去：v0 只认 `completed_bucket_close`（LIMIT-only）。`stop_loss:touch` / `stop_loss:gap_open` 是另一套成交价。TC1 写明 stop / market / replace / GTC 每条都是**新 contract + 新 backend_id**，不得写回 v0。

## 3. 为什么不在本刀铸新合同

X2（更富订单：stop / market）在 #317 里只是菜单，草案标签 `draft-only/x2-richer-orders`，backend 槽 `UNMINTED_NOT_A_BACKEND_ID_x2` **不是** `backend_id`。#318 仍是 draft，且明确：H-TC5-ID 没点名 live `backend_id` 之前，禁止把该字符串写进代码、注册表或测试常量。本刀不发明 live id，也不把草案字符串写进 Python。

缺的不是湖 pin，也不是 4090 窗口。缺的是 `order_type` 无法表示 version1 的止损/止盈单。

## 4. 本刀不做 / 后续

| 本刀 | 后续（本书真能在新引擎上跑通之后，另开刀） |
|---|---|
| 不新增适配器、不改 `simulate` 分支、不把 version1 默认改到真核 | 那时才把 **这一本** 的运行路径改到真核 |
| 旧入口保持可调用。这是暂时的，**不是**永久默认 | **删除 / 退役该旧入口** |
| 不切换其余分钟书 | 第一本跑通后，**全部**分钟策略改走真核，并退役各自旧入口 |
| 不删旧码；不合 | 删除发生在真实跑通之后，不在本 PR |

在 `order_type` 仍只接受 LIMIT 时，把默认调用指到真核等于没跑却宣称已切换。所以本 PR 的 diff 只有这份说明。

## 5. 负面清单（diff 须空）

| 面 | 本 PR |
|---|---|
| `minute_orders_backend/match.py` | 空 |
| `minute_orders_backend/fees.py` | 空 |
| `csv_minute_backtest.py` `simulate` / `simulate_v7` | 空 |
| 任何新 `backend_id` / `contract_version` / X2 草案字符串进代码 | 不出现 |
| 写湖；4090；δ5 certified；R4 | 不做 |
| 删旧入口；翻转全部分钟书默认 | 不做 |

**≠δ5 certified ≠R4。无写湖。无 4090。空核。version1 被 `SubmitOrder.order_type = LIMIT` 挡住。旧入口不是永久默认；删除它是这本书真实跑通之后的后续。本刀 draft，勿合。**
