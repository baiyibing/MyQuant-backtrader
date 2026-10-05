# 真核大票 · C-New · X2–X5 合同菜单草案（2026-10-03）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-03（Asia/Shanghai / CST） |
| tip 基线 | `e8c6bd37`（master · #316 MERGED · R3 边界登记） |
| 方案锚 | PLAN §3.2 / §3.3 / §4 TC5；[TC5 GO/scope](note-true-core-tc5-go-scope-2026-10-02.md)（#308）；[TC1](note-true-core-c-new-tc1-contract-2026-10-02.md) |
| 本刀 | **docs-only 菜单**。登记 X2–X5 为**尚未实现**的新合同轴。**不**铸 `backend_id`，**不**把草案字符串写入代码 |
| 硬约束 | 码之前须 **新 contract + 新 backend_id + 独立 GO**；触及 S0 排除则**禁止复用 v0**；≠δ5≠R4；无 4090；无写湖；空核 |

> **本 note = X2–X5 的菜单草案：只登记身份名与排除项，不是 mint，不是实施 GO，不是已铸 `backend_id`，不是绿 R。**
> 这四条轴在任何代码之前都需要 **新 contract + 新 backend_id + 独立 GO**。
> 一条轴一旦触及 S0 排除，**复用 v0 禁止**（不得写回 `research contract v0 (L2-S0)` / `minute_orders_research_v1` 的 oracle 或 golden）。
> **≠δ5 certified ≠R4；无 4090；无写湖；空核**（MatchCore / Fees / `simulate` / `source_loader` / CLI 本刀零 diff）。

## 1. 本刀是什么

PLAN §4 的 TC5 把扩展包写成「每包新 contract + 新 backend_id + oracle；每包独立 GO；禁止静默改 v0；禁止复用 v0 golden 改名充数」。#308 只开了裁断单，没有点名开工 X2–X5。引擎主体（TC1–TC4、X1、X6 读路径、CLI 读湖、写湖 staging、A·X7）已在 tip 上。本刀不补引擎零件，只把还没做的四条轴收成一份**可点名的合同菜单**。

| 本刀交付 | 明确不做 |
|---|---|
| 四轴身份名草案 + 各自触及的 S0 排除 | 在 Python / 测试 / CI / HELP 里出现任何新 `backend_id` 或 `contract_version` |
| industry-index §7 一行指针 | 改 MatchCore / Fees / `simulate` / `source_loader` / CLI / `views._FAMILIES` |
| 写明：未实现；菜单 ≠ 铸身份 | 4090 / host PASS；生产写湖；绿 R；BOOKS 默认 |

下表草案标签**不是**已批准身份。H-TC5-ID 仍未裁：未裁前禁止把这些字符串当成仓库里已占用的 `backend_id`。复制进注册表、artifact 根或测试常量 = 越权 mint。

## 2. 轴菜单（均未实现）

名称与 PLAN §3.2 对齐。状态列全部是 **NOT implemented**。

| 轴 | 状态 | PLAN 原句能力 | 草案合同标签（未批准） | 草案 backend 槽（未铸） | 触及的 S0 排除 | 本菜单规则 |
|---|---|---|---|---|---|---|
| **X2 · 更富订单类型** | **NOT implemented** | stop / market-on-bucket / 日内模板（研究近似） | `draft-only/x2-richer-orders` | `UNMINTED_NOT_A_BACKEND_ID_x2` | Lifecycle **LIMIT-only**；无 stop / market / replace / GTC | 新 contract + 新 backend_id + 独立 GO 之后才有码。不声称交易所队列。不 undo 旧 hl / Q39。不得写回 v0 oracle |
| **X3 · 报价路径策略包** | **NOT implemented** | 新身份下可选 OHLC 路径或 next-open | `draft-only/x3-quote-path` | `UNMINTED_NOT_A_BACKEND_ID_x3` | 排除 **B（next-open）**；无 A·B·C flags | 同上。**禁止**声称修复 Q39≠hl。H-TC3：首包默认不做；本菜单不把 X3 提升为下一刀 |
| **X4 · 多账户 / 组合层** | **NOT implemented** | 显式多组合现金隔离 | `draft-only/x4-multi-account` | `UNMINTED_NOT_A_BACKEND_ID_x4` | 输入范围 **单账户** | 同上。不做净额轧差 OMS。不是 live 柜台 |
| **X5 · 向量 / 批实例** | **NOT implemented** | 多 symbol 批跑（吞吐）；PLAN 参照 Mode B fast/ref **同合同**先例 | `draft-only/x5-vector-batch` | `UNMINTED_NOT_A_BACKEND_ID_x5` | 不自动改撮合语义；**若**批跑设计触及任一 S0 排除或改变经济语义，则与 X2–X4 相同 | 本菜单仍把它登记为新合同轴：**码之前同样要新 contract + 新 backend_id + 独立 GO**。不强迫旧网格改事件核。性能须另证，不在本刀 |

### 2.1 X5 与 PLAN「同合同」句

PLAN §3.2 把 X5 写成「同合同 + oracle」。那一句**不是**本 PR 的实施许可，也不是对 v0 的开工授权。本菜单把 X5 与 X2–X4 一并登记为新合同轴：在 Human 另一次裁断把 X5 **显式收窄**回「同合同、不碰 S0、不改经济语义」之前，禁止用 `research contract v0 (L2-S0)` / `minute_orders_research_v1` 做批跑。即便将来裁回同合同，**一旦该设计触及 S0 排除，复用 v0 仍然禁止**。两种读法本 PR 都不铸身份。

## 3. 冻结对象与禁止复用

旁路冻结、本菜单**不改**的现身份：

| 对象 | 现字符串 | 本菜单 |
|---|---|---|
| 经济合同 | `research contract v0 (L2-S0)` | 继续冻结。X2–X5 **不得**写回其 oracle / golden |
| backend | `minute_orders_research_v1` | 继续冻结。上表 `UNMINTED_NOT_A_BACKEND_ID_*` **不是**它的别名，也不是新 id |
| 现有三支 L1 entry | 永 opt-in | 不改委托语义 |

复用 v0 的禁止条件（PLAN §3.3，本菜单照录）：轴一旦碰到下面任一排除，就不能把增量塞进 v0。

- 无 stop / market / replace / GTC（X2 整轴在此）
- next-open，以及不存在的 A·B·C 价格旗标（X3 整轴在此）
- 多账户（X4 整轴在此）
- 公司行动、集合竞价、StrategyPort、静默补根：仍在四轴之外，本菜单不把它们收进 X2–X5
- 连续竞价桶：上午 `≤11:30`、下午 `≤14:57`。涨停不买 / 跌停不卖是 v0 的门，不是待修 bug，不借 X2/X3 拆掉

旧轴差异（Q39 first-hit ≠ hl、三个 `close` 参数名、JR 冻结意图 ≠ CSV 反馈 sizing、两个 Mode B 名空间、shared `floor(pV)` 与 L2 `L×floor(pV/L)`、费用粒度）留在旧世界。新合同选定自己的一行之后，对照仍是红标签，不是绿 R。

## 4. 仍锁（不因本菜单松开）

| 锁 | 含义 |
|---|---|
| H-TC2 | 经济语义变化必须新 contract 字符串 + 新 backend_id。禁止未限定的「v1/v2」混指。本菜单的草案标签不是该字符串 |
| H-TC3 | 未另裁前，第二种价格模型不是默认下一刀 |
| H-TC4 | 默认不改 `simulate` |
| H-TC5 | MatchCore / Fees 旁路复用；破坏现语义 → 新模块名，且仍须独立 GO |
| H-TC9 | 永 opt-in；不以 BOOKS 默认为验收 |
| 命名 | 菜单标签 / `tool_id` / `comparison_id` ≠ 经济 `backend_id` |
| 产品 | 回测研究系统 ≠ 交易系统；≠δ5 certified ≠R4；绿 R 仍禁；无 4090；无写湖（写方仍是 host/1.3，见 cut A） |

## 5. 负面清单（本 PR diff 须空）

| 路径 | 本刀 |
|---|---|
| `backtest/research/minute_orders_backend/match.py` | 空 |
| `backtest/research/minute_orders_backend/fees.py` | 空 |
| `csv_minute_backtest.py`（含 `simulate`）/ `csv_minute_backtest_v7.py` | 空 |
| `backtest/research/minute_orders_backend/source_loader.py` | 空 |
| `backtest/research/minute_orders_backend/cli.py` | 空 |
| `backtest/research/run_protocol/views.py` | 空；`_FAMILIES` 不塞新族 |
| 任何新 `backend_id` / `contract_version` 常量 | **不出现** |
| 4090bot / 生产写湖 / `--write-lake` | 不派、不写 |

## 6. 指针

- PLAN（本机，仓外）：`/workspace/handoffs/minute_engine_true_core_new_20261002/PLAN.md` §3.2–§3.3、§4 TC5
- TC1：[note-true-core-c-new-tc1-contract-2026-10-02.md](note-true-core-c-new-tc1-contract-2026-10-02.md)
- TC5 裁断单：[note-true-core-tc5-go-scope-2026-10-02.md](note-true-core-tc5-go-scope-2026-10-02.md)
- S0：[note-l2-s0-minute-orders-contract-2026-09-29.md](note-l2-s0-minute-orders-contract-2026-09-29.md)
- R3 边界（本菜单不派 4090）：[note-true-core-r3-host-attestation-boundary-2026-10-03.md](note-true-core-r3-host-attestation-boundary-2026-10-03.md)
- 写湖 cut A（本菜单不写湖）：[note-true-core-write-lake-must-cuts-register-2026-10-03.md](note-true-core-write-lake-must-cuts-register-2026-10-03.md)
- industry §7：[industry-state-acceptance-index-2026-09-28.md](industry-state-acceptance-index-2026-09-28.md)

**≠δ5 certified ≠R4；无 4090；无写湖；空核。X2–X5 未实现。本 PR 是身份名与排除项的菜单草案，不是 mint。码之前须新 contract + 新 backend_id + 独立 GO。触及 S0 排除则禁止复用 v0。本刀 draft，勿合，直至 Human「合」。**
