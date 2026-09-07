# cursor 对抗综合（host，不计独立票）

评审对象：`docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md` v1  
三路：dissent-steelman / domain-safety / pattern-evidence（2026-09-07）

## 1. 主笔让步（立场修正）

1. **不把 `ChipDistribution[0]` 当 T-1 盈筹率 SSOT。** Indicator 窗口不含当日 OHLC、却用 `close[0]`；且 `adapt_columns` 不传 `as_of_date` 会吃最新股本。v2 改为策略内用含 T-1 的 80 日窗口 + `as_of_date=T-1`。
2. **策略文件不放 `backtest/` 根。** 与现有 research CLI 内嵌 Strategy 的模式对齐。
3. **T-2 必须有限。** NaN 不得当「边缘成立」。
4. **均线只用 `[-1]` 已完成值。** 禁止 `sma[0]`（含当日）。
5. **涨跌停/停牌成交不进净值。** 只记事件。
6. **费用不假装 `trade_fee_policy` 即插 Cerebro。** 自写买卖不对称佣金+印花+最低 5 元，或文档化 `setcommission` 占位。

**未让步：** 用户明确要 30 只抽样试验 + 基本策略框架。不改为「先全市场扫描、不写策略」。不并入 `rolling_investment_strategy`。盈筹率方向本轮仍不论证，但 `summary.md` 禁止写成因子有效。

## 2. 勘误表（已回填 v2）

| ID | 来源 | 动作 |
|----|------|------|
| D-F1 / S-F1 / P-F9 | 筹码窗口与股本时点 | v2 §2 重锁计算路径 |
| S-F2 | SMA 含 T | 锁 `close[-1] > sma[-1]` |
| S-F3 | 周线 asof | 锁 `_last_day` + backward asof |
| S-F6 | Cerebro 同日卖 | 锁「买入日禁卖、卖出一律次日 Open」 |
| S-F7 | 涨跌停仍成交 | 改为 skip，不进净值 |
| S-F8 | T-2 NaN | 要求 T-2 四条件有限 |
| S-F9 / P-F7 | 费率 | 自写 CommInfo，含 min_commission |
| P-F4 | 策略落点 | 移入 `backtest/research/` |
| P-F5 | 抽样源 | float_shares ∩ hive，不用 scan_stocks 抽代码 |
| P-F11 | gate | 新文件禁 `oskh_data.float_shares` 等下载模块 |
| D-F2 / D-F3 / D-F4 | 先全市场 / 不写 CLI | **驳回**（与用户指令冲突）；报告披露偏差即可 |

## 3. 对 §3 的 host 裁决

- §3.1：口径补齐后可实施。
- §3.2：独立 research CLI 必要；根目录策略文件不必要。
- §3.3：30 只是用户指定的试验，不是全市场结论。
