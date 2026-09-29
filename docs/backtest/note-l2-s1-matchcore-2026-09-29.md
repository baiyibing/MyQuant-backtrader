# L2-S1：minute_orders_research_v1 types + MatchCore

2026-09-29 · **L2-S1 / Human GO / action-only** · 实施基线 `9f4e5be`（#250 后）。

Human widget「开干 L2-S1 types+MatchCore」；授权记录为工作站外部文件
`/workspace/handoffs/l1_l2_research_engine_l2s1_20260929/HUMAN_GO.md`。
本片仅实现动作核，合入仍须 Human「合」；`production_C=frozen`。

语义依据：[L2-S0 research contract v0](note-l2-s0-minute-orders-contract-2026-09-29.md)
§2–3、[独立手算草图](note-l2-s0-handcalc-oracle-sketches-2026-09-29.md)
及外部 PLAN §4.3 / §4.6 / L2-S1 行。Q2=A：`completed_bucket_close`。
按 [Q4 来源决定](note-l2-s0-source-license-decision-2026-09-29.md)自行实现，未复制
vendor 源码，未 import/build/install vendor runtime。

## 最小 API 与边界

包：[`backtest.research.minute_orders_backend`](../../backtest/research/minute_orders_backend/__init__.py)。

| 项目 | 本片合同 |
|---|---|
| `Side` | 显式 `Side.BUY` / `Side.SELL`，不从字符串猜测方向 |
| `LimitOrderMatchInput` | 冻结 order_id / symbol / side / Decimal limit / remaining_qty / lot_size；类型固定 LIMIT，其他类型报错 |
| `BucketQuote` | 冻结 symbol / bucket_id / 带时区 start、end / Decimal close；调用方提供已完成且可见的桶 |
| `match_candidates(order, quote, capacity_remaining=...)` | 单快照输入，返回一个 `CandidateMatch` 或 `NoMatch`；无内部状态 |
| `CandidateMatch` | order ID、symbol/side、close 原值、proposed_qty、bucket ID/start/end、`price_crossed`；**动作不是 Fill** |
| `NoMatch` | order ID、symbol/bucket ID、`price_not_crossed` 或 `zero_after_lot`；有效业务结果 |
| `MatchContractError` | 坏输入失败；不伪装成业务无匹配，不补价格/容量 |

BUY `close <= limit`、SELL `close >= limit`，等号含在内；候选价仅为 close，
不读 open/H/L。价格须为有限、正值、到分对齐的 Decimal，不转 float、不静默舍入。
ID 不可空，start/end 必须带时区且递增，order/quote 的 symbol 必须一致。
调用方负责活跃状态、完成/可得时点、连续竞价日历、raw/tick/涨跌停及资源资格；
本片不凭桶时间字段宣称已验证这些门。

`lot_size` 必填正整数；`remaining_qty` 按 S0 合同须为非负整手整数，非整手失败。
`capacity_remaining` 为调用方提供的该 symbol+bucket **双侧共享剩余股数**，非负整数，
允许未整手对齐；提案为 `L * floor(min(remaining_qty, capacity_remaining) / L)`。
先检查输入有效性，再判断触价，再算数量；未触价优先返回 `price_not_crossed`，
触价但提案为 0 返回 `zero_after_lot`。布尔值不视为股数。

纯函数 `compute_bucket_capacity(lot_size, volume_shares, participation_rate)` 实现
`C = L * floor(p * V / L)`；V 为显式非负整数股数，p 为显式 Decimal 且 `0 <= p <= 1`。
缺量/坏值失败，V=0 或 p=0 返回 0；无默认参与率。用 Decimal 精确整数比计算，
不因调用方 Decimal 精度不足将接近整手边界的容量向上舍入。
matcher 不根据每单重复计算整桶容量，不持有/扣减容量；重复相同输入会重复给出相同动作。
调用方必须提供此前提交消耗后的余量，后续 Ledger 才能唯一原子提交并去重。

## 验证与后续门禁

[`test_minute_orders_matchcore.py`](../../tests/test_minute_orders_matchcore.py) 使用独立常数
expected：双侧触价/等号、close 原值与桶证据、整手/容量边界、S0 A/D 的动作投影、
S0 A/E 的容量手算、低精度边界、不可变输入、坏值 fail-closed，以及隔离进程 import fence。
import 仅允许标准库与本片三个模块，不加载 L1/CSV/v7/JR/ModeB、数据加载器或 vendor。

**本片绿C仅指合成 action oracle；不是完整 PLAN §4.6 通过，不授予绿R/绿S，不产生 NAV。**
未验证真实湖、交易所队列、冲击或可执行收益，不声称交易所精确撮合。

范围外：Ledger、BrokerCore、费用/预留/现金/lots/T+1 副作用、fill 提交/容量扣减、
cancel/expiry 相位与生命周期、Clock/日历/缺根/停牌/方向资格门、stops/OHLC 路径、
mark/NAV、runner、writers/CLI、湖读取和 L1 注册。本片均未实现。
资源守恒、费用、幂等/原子性留 L2-S2；全序、可得性、撤单到期及完整回放留 L2-S3；
工件与失败隔离留 L2-S4，各片仍须 GO。未替换 CSV，Cerebro 禁令保持。
