# minute_orders_research_v1：L2-S3 Clock + BrokerCore + runner API

2026-09-29 · **L2-S3 / Human GO / in-memory research only** · 基线 `b3e5b16`（#252）。
Human「下一刀 GO」授权本片，依据仓外
`/workspace/handoffs/l1_l2_research_engine_l2s3_20260929/HUMAN_GO.md`，
对应 PLAN 的 L2-S3。PR 后 Human/Grok 评审；**未经 Human「合」不得合并**。
`production_C=frozen`；本片没有 writers、CLI、L1 注册、湖、vendor 或在线 StrategyPort。

后续状态：[L2-S4 artifacts + isolation](note-l2-s4-artifacts-isolation-2026-09-29.md) 已获独立 Human GO，新增显式 writer/采集 wrapper（本 PR，待 Human/Grok 评审）；默认 S3 API 保持纯内存，CLI/L1/lake 不在范围。

合同沿用 [S0](note-l2-s0-minute-orders-contract-2026-09-29.md)、
[手算 A–E](note-l2-s0-handcalc-oracle-sketches-2026-09-29.md)、
[S1 action-only](note-l2-s1-matchcore-2026-09-29.md) 与
[S2 Ledger/Fee](note-l2-s2-ledger-fee-2026-09-29.md)。MatchCore/Ledger 公共语义不变。

## API 与显式输入

```python
from backtest.research.minute_orders_backend.runner import run_minute_orders_research
from backtest.research.minute_orders_backend.types import RunInput

# request 是调用方构造的 RunInput；最小合成构造见 tests/test_minute_orders_runner.py。
# result = run_minute_orders_research(request)
```

runner 创建一次性 `BrokerCore`，纯内存返回不可变 `RunResult`。
包根仍保留 S1/S2 导出面，不 eager import 或导出 runner；调用方显式导入上述子模块。
所有集合使用 tuple；价格/金额为 Decimal，数量/sequence 为整数；不读取文件/env。

| 输入 | 要求 |
|---|---|
| `start_at/end_at` | 显式运行区间；使用命名 `Asia/Shanghai` 时区，不静默转换 naive/UTC |
| `commands` | `SubmitOrder` / `CancelOrder`；稳定 command/order ID、sequence、available/submitted/effective；LIMIT 还含 qty/limit/side/symbol/expiry |
| `calendar` | 有序唯一 trading_dates、精确 session_buckets、公司行动覆盖证明与空事件 tuple |
| `instruments` | 品种/日期、普通主板/raw、tick、lot_size、reference、上下限；不用固定百分比推断 |
| `buckets` | symbol/bucket ID、start/end、close、volume_shares，以及显式 missing/halted 布尔覆盖 |
| `initial_cash/initial_lots` | S2 格式；lot 带取得/可卖日期、整手单位，初始未预留且不能来自未来 |
| `buy_fees/sell_fees` | 显式 `FeeModelParams(rate,min_fee,rounding)`；不继承 production 费率 |
| `participation_rate` | 必填 Decimal；完成桶双侧共享容量，沿用 S1 的精确整手取整 |
| `marks/requires_marks` | 显式 marks tuple 与布尔政策；见下节 |

日历是调用方声明的**本次有限回放桶覆盖**，不是引擎生成的完整交易所日历。
每个 session bucket 必须为连续竞价的一分钟，端点整分，完整处于 09:30–11:30 或 13:00–14:57。
`[14:56,14:57)` 有效；14:57–15:00 为收盘集合竞价，其三个一分钟桶即使标为 continuous 也拒绝。
同一日上午/下午所列桶之间不得漏桶；跨午休/交易日可分段提供，不补未声明的窗口。
session_buckets 有序、无重复/重叠；市场桶按 `(start,symbol)` 严格排序。
固定品种全集 × 所列 session 必须逐项覆盖；缺根也须提供匹配日历的 `missing=True` 桶。
缺根时 close/volume 都为 None；有根（包括 halted）时二者均须合法，坏字段不能冒充停牌。
缺根/停牌登记零容量，订单继续存续；无量同样不成交。未用容量不跨桶累计。
品种事实须覆盖 submit、桶和 mark 的使用日；lot_size 不得跨日改变。
T+1 取显式 trading_dates 的下一项；初始 lot 的取得/可卖日也按此核验，缺覆盖失败。
公司行动无覆盖或非空事件均失败，不进入除权计算。

## 时钟与生命周期

全序键为 `(event_time, phase_rank, sell_before_buy, submitted_at, sequence, order_id)`。
同刻细分如下；BUCKET 是 match 的可见性/容量登记步骤，不产生订单或成交。

| rank | 动作 |
|---|---|
| 0 / 1 | expiry → cancel；B3 同刻只留下 Expired，释放一次 |
| 2 | 完成桶在 end 可见并向 Ledger 登记共享容量；非订单 tie 用 symbol |
| 3 | 全品种合格单统一 sell-first，再 submitted_at、sequence、order_id；逐笔入账 |
| 4 | 该刻新 submit 请求预留，只能使用已入账且未预留资源 |
| 5 | mark 观察上述步骤之后的账本；非订单 tie 用 mark_id |

Clock 只按时间安排候选事件；预检行情合法性不作成交或预留决策。
Broker 仅在桶 end 取得可见行情，要求
`available_at <= submitted_at < bucket_start`、`effective_at <= bucket_start`、`end < expires_at`。
因此桶尾新 submit 不能回填刚结束桶，也不能参与恰在该刻开始的下一桶。
submit 在 submitted_at 接受/拒绝，effective_at 只控制撮合资格；expiry 必须晚于 effective_at。
cancel 的 available≤submitted≤effective，且 effective 严格晚于目标订单的提交。
未知目标失败；终态后的不同 cancel 为 no-op。重复 command_id、order_id 或冲突全序键失败。

`Submitted → Accepted/Rejected`；活跃单只有在真成交后变 PartiallyFilled/Filled，
无成交保留原状态；cancel/expiry 仅释放残余预留。业务拒单不会缩量或因后来卖款复活。
BUY 预留 limit×qty+累计费上界，SELL 预留具体可卖 lots，均调用 S2 Ledger。
涨停不买/跌停不卖；余下合格单交 MatchCore 产生 action，再构造带费用差额、版本、
容量消费的 FillProposal，经 Ledger 原子提交后更新生命周期。
fill ID 由长度前缀 order_id/bucket_id 构造，重复运行稳定且不会因简单拼接歧义碰撞。
Ledger 是现金、lots、预留、费用和容量的唯一 owner；Broker 不持有第二套资金状态。

## 输出、marks 与失败

RunResult 含按 order_id 排序的最终订单状态、按入账顺序的 fills、LedgerSnapshot、
生命周期 transitions 和 mark observations。Rejected 保留资源拒绝原因及 required/available。
到 end_at 尚未到期的活跃残量及预留如实保留，不强制到期、强平或制造 SELL。

**S3 选择：`marks=()` 且 `requires_marks=False` 合法，用于只核现金/成交的 oracle。**
requires_marks=True 却无 marks 则失败。只要提供 marks，无论布尔政策如何都必须合法：
raw、非空来源、唯一 ID、合法 tick/价域、available_at=event_time、覆盖该刻全部持仓品种。
不拿旧价/lot cost 补 mark；mark 只保留显式价格及已提交账本观察，不产订单/fill 或 NAV 产品。

畸形输入/合同/算术错误向调用方传播，不返回成功 RunResult；业务 Rejected 是正常结果。
S2 成交原子性保持，Broker 失败后不能再次 run；可读取其 Ledger 最后已提交快照。
本片无磁盘成功标记、失败工件或输出根；这些属于 **L2-S4 artifacts + isolation**。

## 合成验证与边界

`tests/test_minute_orders_runner.py` 使用手算常数，未调用旧引擎生成 expected：
A 两买单共享容量与 expiry；B1–B6；C T+1/卖量预留；D 拒单不复活及 SELL→BUY；
E 累计最低费/cancel；跨品种排序、稳定 sequence 置换后的完整结果/hash、未来桶改动不影响过去；
缺根/halt/零量、方向涨跌停、坏行情/日历/命令/mark、无文件副作用和严格 import fence。
原 S1 MatchCore 与 S2 Ledger/Fee 测试保持不改并通过。

**绿C = synthetic integration oracle；不等于绿P/绿R/绿S、湖验证或全 PLAN 收官。**
磁盘 writers 经 Human GO 后已在 [L2-S4](note-l2-s4-artifacts-isolation-2026-09-29.md) 落地；CLI 产品化、L1 注册、湖、收益/NAV 比较仍在 S3 范围外。
旧 CSV/JR/v7/ModeB、L1/run_protocol、fees/exdiv/fill-gates、HELP_LOCK/CI/presets/golden 均不改。
按 Q4 自行实现，无 vendor 代码复制或 runtime 依赖；无新增策略版本或注册。
