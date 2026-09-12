# merge-consensus：plan-unify-csv-strategies-1-8-2026-09-12

> **主持裁**：cursor-desktop（本对话）
> **plan**：`docs/backtest/plan-unify-csv-strategies-1-8-2026-09-12.md` **v1.2**
> **fan-out**：classic 2026-09-12，四家 rc=0（codex 293s / kimi 263s / cursor:auto 234s / claude 500s）
> **对抗层**：`review-by-cursor.md`（不计票，已回填 v1.1）

## 1. 票源

| 来源 | 结果 | 计入 |
|------|------|------|
| 对抗三路 | 回填 v1.1（U-R1–R28 骨架） | 取舍已定，不重开 |
| claude | rc=0，完整 | **计入** |
| codex | rc=0，完整 + 涨跌停实验 | **计入** |
| cursor:kimi-k3-high | rc=0，完整 + 同构实验 | **计入** |
| cursor:auto | rc=0，完整 | **计入** |
| cursor-desktop 空槽 | 综合，不重复打分 | host |

有效独立票 = 4。主持裁复现 codex/kimi 涨跌停实验：`compared 399802 mismatches 1073`（`1.65×0.9` → v7 1.48 / Decimal 1.49）。无新的架构级互斥需要再开 classic。v1.2 吸收下方必修后 **可进切片 A**。

## 2. 必查盲区

| 盲区 | 裁决 |
|------|------|
| T+1 | `n_days>=1` 才卖；买入日不挂 pending。3 的开板也要 `n_days>=1`。 |
| 复权 | 成交与均线同一 `none`。禁 chip / front。 |
| 盈筹率 | **不适用**。 |
| 涨跌停 | 本轮沿用现 defer：日线 pending+止损；分钟仅 `stop_loss*`；3 开板另锁。北交/ST/689 不建模。v7 与 6/8 涨跌停算术 **刻意不统一**。 |
| 包边界 | `backtest/research/`；不改 `presets.py`；7 不进 BOOKS；Cerebro 仅 E。 |
| port 源 | `ProfitStrategy.StrategyN`。 |

## 3. 🔴 裁决（已写入 v1.2）

| 票 | 原 ID | host |
|----|-------|------|
| 三家 | 策略 4 的 MA5 卖装不进四参 `take_profit` | **吸收**：`sell_gate(code, px, day, closes)`；不给 `take_profit` 加第 5 参 |
| codex R2 / kimi R1 | U-R10「字节级不变」证伪 | **吸收**：`_limit_prices` 留 v7；市场层 Decimal 只给 6/8 |
| codex R3 | 1/2 止盈缺 `px>=cost` | **吸收** |
| codex R4 | port 源 ProfitStrategy vs presets | **吸收**：port = ProfitStrategy |
| auto R1 | U-R1 跌停过度承诺 | **吸收**：不升格 6/8 trail |
| auto R2 | 1/2/4 日线离场未锁 | **吸收**：一律 `pending_exit` |
| auto R3 | 3/5 挂载面未契约化 | **吸收**：具名 hooks，禁 `if strategy==` |
| kimi R5 / claude Y1 | 开板跌停 defer 次日语义 | **吸收**：改挂 `pending_exit="open_board"` |
| claude Y2 | 14:50 须在开盘跌停跳过之后 | **吸收** |
| claude Y3–Y5 | 分钟预载 / 689 / `--stop-pct` | **吸收** |

驳回 / 降级：

- 不把分钟全 reason 改成跌停禁卖（改 6/8 热路径，与 U-R9 冲突）。
- 不把 v7 涨跌停改成 Decimal（1 分差异登记为已知，不改撮合阈值）。
- `scan_held_day` **返回仍是 5 元组**（不改 13 处解包）；`reserved` 由调用方 `reserve_step` 回写。

## 4. 🟡 已顺手锁进 v1.2

`load_pool_days` 薄壳；`Position.reserved` 只加日线那一份；`summarize` 四新桶；`--stop-pct` 对 4/5 显式即退出；验收补 v8 测试；化石门同步测试/README；分钟顺序止损→止盈→force；追买 gate 的「昨收」含信号日。

## 5. 结论

v1.1 骨架（None 止损、5 不做日线 force、3 第三钟、7 不进书、实施序）四家取证后站得住。卡住编码的是策略 4 卖通道、涨跌停搬家、1/2 亏损止盈、跌停叙述、hooks 挂载——均已写进 v1.2。

**按 v1.2 实施。从切片 A 开工。** 不另开 classic 第二轮。等人说「按 plan 实施」再改业务代码。
