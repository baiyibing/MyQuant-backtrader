# Plan：均线 + 盈筹率边缘买入试验（v3）

> **状态**：已吸收对抗 + classic fan-out（有效票 cursor:auto）；按本文实施  
> **日期**：2026-09-07  
> **范围**：Cerebro 日线研究回测。不做实盘。价格/量约束后续单开。  
> **对抗回填**：`docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/review-by-cursor.md`  
> **综合**：`docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/merge-consensus.md`

## 0. TL;DR

研究 CLI：T 日开盘买入，当且仅当 **T-1 四条件全真且可计算**，且 **T-2 四条件全可计算但非全真**。持有：买入日收盘 ≤ T-1 收盘则次日开盘出；否则拿到收盘 < SMA5 的次日开盘出。随机 10 深主板 + 10 沪主板 + 10 创业板，统计窗 2024-01-01 至今。

盈筹率 **不** 直接读 `ChipDistribution.cyqk_c[0]`（窗口不含当日、股本无 as_of）。策略内对 **含决策日 D 的 80 日窗口** 调 `chip_algorithm` / `oskh_factors.chip`，`as_of_date=D`。

## 1. 背景

用户口头规则（2026-09-07），**实现口径以 §2 为准**（等号已 fail-closed）：

1. **买入（T 日开盘）**：t-1 价格 > 20 日均线 and > 20 周均线 and > 60 日均线 and 盈筹率 > 70%；t-2 **不同时**满足（且 t-2 四输入有限）。
2. **持有**：T 收盘 **≤** t-1 收盘 → T+1 开盘卖；T 收盘 **>** T-1 收盘 → 持有到收盘 < 5 日均线，再下一根开盘卖。
3. 先 30 只试验；后续再加价格/量约束。

不改 `backtest_main_full.py` / `rolling_investment_strategy.py`。

## 2. 锁定口径

| 项 | 锁定 |
|----|------|
| 决策时点 | 在 **日 D 的 next()**（D 收盘已知）算 `cond[D]`；边缘成立则 `pending_buy=True`。**禁止** `bt.Order.Open`。成交用 `Cerebro(cheat_on_open=True, runonce=False)` + `next_open()` 下 Market（仅 `broker.set_coo` 不够，订单会落到下一根开盘）。可测行为：D+1 开盘买或 skip。T=D+1 |
| 价格 | 日线 `period=1d` **`adjust_type=front`**。禁止 `load_single_stock_data`（默认 1m + none） |
| 比均线 | 在日 D 评 `cond[D]` 时 SMA 输入止于 D（`sma` 含 D 合法）。**禁止在日 T 用含 T 的 sma 去判断 T-1**。对抗旧句「均线只用 [-1]」已由 v2/v3 重述，勿回退 |
| 20 周均线 | 按 `oskh_factors.weekly_macd_divergence._daily_to_weekly` 同构：`W-FRI` + `_last_day=max`。asof 键 = `_last_day`，**只 backward** 到 D。未完成周丢弃。不改 `oskh_factors` |
| 盈筹率 | 阈值 **0.70**（`get_cyqk_c` 为 0–1）。窗口 = 截至 D 的最近 80 根 **含 D** 的 OHLC；换手用 **D 日 asof 股本** 估全程窗口。NaN → 该日 cond 不可计算。实现可预计算股本 asof，避免逐日扫 parquet |
| 边缘 | `cond[D] is True` 且 `cond[D-1] is False`。**两边都必须有限**。D-1 为 NaN ≠ 边缘 |
| 等号 | 买入日收盘 **≤** T-1 收盘 → 次日开盘卖（fail-closed） |
| MA5 离场 | 持有期日 H：`close < sma5` → `pending_sell`，次日开卖。买入日 **禁止任何卖单** |
| T+1 | 买入日不挂卖；卖出一律下一根开盘。不接 `TPlus1QueueManager` |
| skip 后 FSM | 涨停买 / 跌停卖 / volume=0：**不成交、不进净值**，写 `events.csv`。**skip_sell 必须保留 `pending_sell` 与 `hold_mode`，下一交易日再试**，直到成交或样本结束。skip_buy 消耗该次信号（不无限挂买） |
| 仓位 | 单票最多 1 笔；已持仓忽略新开 |
| 涨跌停阈值 | 创业板 20%、主板 10%。昨收用 **front 昨收**，summary 声明偏差。ST 5% 本轮不做（无列表 SSOT） |
| 费用 | 自写 `bt.CommInfoBase`：佣金万 0.5、最低 5 元、卖出印花税 0.05%。不把 `trade_fee_policy` 当 Cerebro 插件 |
| 抽样 | seed=`20240907`；代码池 = hive `period=1d/dividend_type=front` ∩ `float_shares.parquet`（`resolve_source_parquet`，禁止 `from oskh_data.float_shares import`）。每板抽 10，预热不足则重抽 |
| 板块 | 沪主板 `60xxxx.SH` 排除 `688`；深主板 `000/001/002/003*.SZ`；创业板 `300/301*.SZ` |
| 区间 | **统计** 2024-01-01 → `--end`（默认今天）；加载从 **2022-07-01**。统计窗前最后一个交易日之前的 `edge` **置假**，禁止窗前成交污染净值 |
| 组合 | **单票独立 Cerebro + 等额本金**。事后报单票收益均值，不是多 feed 共享资金 |
| 文件 | `backtest/research/ma_chip_edge_backtest.py`（CLI + Strategy） |
| 输出 | `backtest_output/ma_chip_edge_{seed}_{end}/`：`universe.csv` `trades.csv` `events.csv` `per_stock_stats.csv` `summary.md` |
| 报表字段 | `summary.md`：每板只数、`names_with_buy`、`mean_single_name_return`、`median_single_name_return`、`mean_max_drawdown`、`skip_buy`/`skip_sell` 次数。**禁止**写策略/因子有效 |
| CLI | `--help` 必须带上本表要点（成交方式、等号、skip FSM、统计窗） |

## 3. 方案取舍

### 3.1 可行性

口径按 §2 补齐后可行。`ChipDistribution` warmup 单测只证明 NaN≠0，**不**证明本策略。周线 asof 本地复制。次新不够 20 周则重抽。

### 3.2 必要性

必须单独 research CLI。策略放 CLI 同文件，不进 `backtest/` 根。不并入 rolling。

对抗 dissent「先全市场扫描、先改 Indicator」：**驳回**。用户本轮要可下单的试验框架 + 30 只表现。

### 3.3 优缺点

- 优点：时间因果锁死；单测可覆盖边缘 / T+1 / MA5 / T-2 NaN / skip_sell 重试。
- 缺点：30 只不能代表全市场；`cyqk_c>0.70` 在仓内文档是抛压区，本轮只验证框架。
- 涨跌停用 front 昨收，可能与交易所涨跌停价有偏差。

## 4. 实施步骤

1. `backtest/research/ma_chip_edge_backtest.py`：抽样、加载、策略、报告。
2. `tests/test_ma_chip_edge_strategy.py`（合成数据，不依赖 F 盘）：
   - D 满足、D-1 不满足且有限 → D+1 开盘买
   - D 与 D-1 都满足 → 不买
   - D-1 为 NaN → 不买
   - 买入日收阴/收平 → 次日开盘卖
   - 买入日收阳 → 直到收盘 < SMA5 的次日开盘卖
   - 买入日 next() 内不得卖
   - skip_sell 后仍持仓，下一交易日再试卖
   - 统计窗前 edge 被抹掉
3. 跑 30 只试验。

```powershell
D:\anaconda3\envs\vanna312\python.exe backtest/research/ma_chip_edge_backtest.py --seed 20240907 --start 20240101
```

## 5. 本轮不做

- 价格约束、量约束
- 改 `ChipDistribution` / `oskh_factors` / `qlib_cost`
- 全市场扫描、分钟线、实盘、LEBS
- 精细涨跌停撮合（只 skip + 重试卖）
- ST 5% 阈值、none 未复权昨收
- classic fan-out 第二轮（kimi/claude 额度用尽，codex 超时）

## 6. 验证

- 单测全绿。
- 30 只 exit 0；打印每板只数、触发买入数、等权（单票）收益、回撤、skip 数。
- `scripts/gates/verify_oskh_data_contract.py` 绿。

## 7. 关闭条件

- §2 出现在 CLI `--help`。
- 同一 seed 的 `universe.csv` 可复现。
- fan-out 无未吸收的架构 🔴（本轮 R1–R3 已吸收）。
