# minute_orders_research_v1：L2-S2 ledger + fee

2026-09-29 · **L2-S2 / Human GO** · 基线 `0c8fe2c`（#251）· `production_C=frozen`。

Human「L2-S2 ledger+fee====GO」「codex开最高档来做，grok核」授权本片；
冻结记录：`/workspace/handoffs/l1_l2_research_engine_l2s2_20260929/HUMAN_GO.md`。
本片仅实现 ledger、reservation 与 fee；PR 交 Grok 审查，未经 Human「合」不得合并。

依据 [L2-S0 合同 §2–3](note-l2-s0-minute-orders-contract-2026-09-29.md) 的
Fill/Fee、Cash/reservation、Lot/T+1、Ledger/Mark 行及累计费公式，
和 [A–E 独立手算](note-l2-s0-handcalc-oracle-sketches-2026-09-29.md)。
**Q2=A 不变**：completed-bucket close；[MatchCore](note-l2-s1-matchcore-2026-09-29.md)
仍只产动作，`CandidateMatch` 不是 fill，不能直接交给 `apply_fill`。

## 费用与精度

`FeeModel(buy=FeeModelParams(...), sell=FeeModelParams(...))` 两侧均须显式配置
Decimal `rate`、到分 `min_fee`、`rounding`；不继承生产费率，无全税费声明。
`cumulative_fee(side, N)` 为 `F(0)=0`，正 N 时
`quantize(max(min_fee, N*rate), 0.01, rounding)`。
`fee_delta(side, before, after)=F(after)-F(before)`，累计名义额不可倒退。
零费模式须显式 `rate=0, min_fee=0`；E 为 `0.001 / 5.00 / ROUND_HALF_UP`。

支持 HALF_UP/HALF_DOWN/HALF_EVEN/UP/DOWN/CEILING/FLOOR；其他模式与任意外部
fee model 拒绝，不能伪称可提供有效上界。BUY `buy_fee_upper_bound(N, limit, remaining)`
返回 `F(N+limit*remaining)-F(N)`；非负参数及单调舍入确保 close≤limit 时界有效。
模型不改现金；Ledger 核验提案费用与配置累计差额相等后才入账。
只在累计费处到分舍入；价/限价/现金/名义额非分对齐失败，float 不接受。
内部金额加减采用精确整数分，返回 Decimal；费率乘法与 quantize 使用局部 Decimal
context，避免调用方低精度或 Inexact trap 改写账页，不修改全局 context。

## Ledger API 与唯一 owner

`Ledger(initial_cash, initial_lots, fee_model=...)` 初始持仓用不可变 `LotPosition`，
含 lot ID、symbol、acquire/sellable 日期、qty、lot_size；初始全部未预留。
数量必须正整手，空持仓用空列表；日期必须为 date，sellable 必须晚于 acquire。
同 symbol 整手单位一致；初始 lot ID 不重复。Ledger 不发明交易日历。

| 命令 / 值 | 行为与边界 |
|---|---|
| `reserve_buy(order_id, symbol, limit, remaining_qty, lot_size, fee_upper)` | 参数除 ID 外为 keyword；界须等于配置模型计算值；预留 limit×qty+界，不缩量 |
| `reserve_sell(order_id, symbol, limit, qty, lot_size, trade_date)` | 参数除 ID 外为 keyword；仅选 sellable_date≤trade_date 的 free lots；按 acquire_date、lot_id 分配具体 lot |
| `ReservationRejected` | 现金/可卖量不足的业务结果，含 required/available；不扣资源，不变成 pending |
| `release_buy/release_sell(order_id)` | 释放该单全部剩余预留；不生 fill、不加费、不退已付费；重复释放是 LedgerError |
| `register_bucket(symbol, bucket_id, trade_date, lot_size, capacity)` | 全 keyword，显式安装 symbol+bucket 双侧容量；相同事实重复登记不重置剩余量，冲突失败；无时钟/跨桶累积 |
| `FillProposal` | 显式 fill/order/symbol/side、qty、price、fee_delta、bucket、capacity_consumed、lot_size、trade_date、BUY sellable_date 与 expected_version |
| `apply_fill(proposal)` | 验证整手、限价、桶身份/余量、预留/现金/可卖 lot 与累计费；capacity_consumed 必须等于 qty；原子提交并返回 FillApplied |
| `snapshot()` | 不可变 LedgerSnapshot；含 cash/reserved/free、lots、reservations、累计名义额/费用、桶余量、已用 order ID、已提交 fills 与版本 |

每次成功状态更新版本加一；业务 Rejected 也登记已用 order ID 并加一，资源数值不变。
同 order ID 不可重复 reserve；拒绝、释放或全成后再次 submit 必须新 ID。
这只是身份与资源防重，不维护 Submitted/Expired 等 Broker 生命周期。
畸形输入、资源不足的 fill、陈旧版本或 ID 冲突抛 `LedgerError`；
费用输入错误为其子类 `FeeContractError`。失败不改变已提交快照。

同 fill ID、相同有效载荷重放为 no-op，优先于版本/活跃预留检查；
`FillApplied.duplicate=True`，保留**首次入账版本**。同 ID 不同载荷失败，
包括篡改 expected_version；其他订单不能误用同一个 fill ID。

BUY 扣名义额+本次费，按新累计额和残量重算剩余预留，释放价格改善及多余费用界；
每笔新增 `lot_id="fill:"+fill_id`，若碰撞初始 lot ID 则整笔失败。
BUY lot 的 sellable_date 由调用方给出下一显式交易日，Ledger 只验证晚于 trade_date，
不以自然日+1 推算，也不宣称验证了日历；SELL 入账再检查已分配 lot 的可卖日期。
SELL 只消耗自己的具体 lot 预留，入账名义额−费用，不能动用其他 BUY 的预留现金。
各分量先生成候选不可变快照，全部计算成功才单次替换提交状态；只支持单进程串行调用。

## 本片验证与范围外

`tests/test_minute_orders_ledger_fees.py` expected 为手算常数，未调用旧引擎生成。
A 两买单/跨桶共享/残量释放；B 由调用方先释放，再拒绝迟到 fill（**非时钟验收**）；
C/D 当日锁定、下一交易日可卖、重复预留拒绝、拒单不复活、SELL→BUY 共用容量；
E 部分成交最低费只收一次、cancel 无加费/退款、预留含费用不足拒绝。
另测真实舍入差额、卖侧费、价格改善释放、周五→周一显式解锁、陈旧版本/重放/冲突、
提交前故障注入无半笔状态、快照不可变、分桶分品种隔离及低 Decimal 精度。
原 MatchCore 测试保持，import fence 只增加 fees/ledger 两个本包模块；
仍仅允许标准库和本包，不导入 L1/run_protocol、CSV/JR/v7/ModeB、loader 或 vendor。

**本片绿C = ledger+fee 独立手算 oracle；不是完整 PLAN §4.6、runner 或 NAV 验收。**
不授予绿R/绿S，不称交易所精确撮合，无湖、实盘/冲击或收益证据。

范围外：BrokerCore、Clock、cancel/expiry/submit 相位及资格策略、runner、writers、CLI、
L1 注册、mark/NAV、公司行动、stops/OHLC、湖和 vendor runtime。
按 Q4 冻结合同自行实现，无 vendor 源码复制、移植、import 或构建。
旧 production fees/exdiv/fill-gates、CSV/v7/JR/ModeB、HELP_LOCK、presets/golden 不改；
Cerebro 禁令保持。Broker/Clock/runner 仍须后续 Human GO；本 PR 勿合。
