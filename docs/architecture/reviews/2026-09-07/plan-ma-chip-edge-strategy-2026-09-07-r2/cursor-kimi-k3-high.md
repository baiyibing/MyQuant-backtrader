<!-- agent=cursor:kimi-k3-high cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.02-c22c1a3\node.exe C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.02-c22c1a3\index.js --model kimi-k3-high -p --output-format text --trust -f --mode plan --workspace E:\PycharmProjects\MyQuant-backtrader <prompt> -->
评审完成，已写入 `docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07-r2/_parallel/cursor-kimi-k3-high/cursor-kimi-k3-high.md`（UTF-8 无 BOM 已验证）。其他三位评审员文件截至写入时均为 stub，无可交叉核对的已完成意见。

核心结论：

**实验验证（3 组最小实验，均附可复现脚本+原始输出）**
- E1：`Cerebro(cheat_on_open=True, runonce=False)` + `next_open()` 下 Market → 信号日 D 的 `next()` 置 pending，**D+1 开盘价成交**，plan §2 设计正确；仅 `broker.set_coo(True)` 时 `next_open` 根本不被调用（cerebro.py:1622 门控），plan 括注结论对、机理措辞小疵。
- E2：直接跑已实现的真实策略 `MaChipEdgeStrategy`，fail-closed 等号、MA5 离场、skip_buy 消耗、skip_sell 重试 5 个 case 全部与 §2 锁定口径吻合。
- E3：**停牌缺口实验发现实质缺陷**——edge 于 01-03，停牌 3 周无 bar，复牌日 01-24 仍按旧信号买入且无 skip 日志。

**🔴 R1（唯一必须修）**：`pending_buy` 无过期机制，停牌时 volume=0/涨停检查不触发，旧信号在复牌日静默成交，与 §2「D+1 开盘买或 skip」二值锁定直接矛盾。修复一行级：记录信号 bar 的 `len(self.data)`，仅下一根 bar 允许买，否则记 skip_buy(stale)。

**🟡**：R2「未完成周丢弃」字面与实现不符（数据末端 partial week 实际参与，因果安全但口径需改一字）；R3 禁令 `oskh_data.float_shares` 模块不存在（实为 `float_shares_history.py`），禁令落空需改写；R4 events.csv 未按统计窗过滤。

**✅**：cyqk_c 0–1 尺度（cyq.py:229-244）、ChipDistribution 窗口不含当日（chip_indicator.py:104）、20 周均线同构 `_daily_to_weekly`（weekly_macd_divergence.py:86-103）、front 复权统一、包边界、费用口径、统计窗防污染——全部取证为真。

**总评**：修掉 R1（含对应单测）后可进实现；已存在的实现应回补该修复。
p.cheat_on_open and self.p.broker_coo: ... set_coo(True)`，故实现里再调 `set_coo(True)` 属冗余但无害。

### 实验 E2：真实策略 FSM（直接跑 `MaChipEdgeStrategy` + 合成 feed）

```python
from backtest.research.ma_chip_edge_backtest import MaChipEdgeStrategy, SignalPandasData, AShareCommInfo
# feed 含 sma5/edge 线；edge=1 于 01-03；bt.Cerebro(cheat_on_open=True, runonce=False)
```

原始输出：

```
case1 fail-closed: trades= [('2024-01-04', 'BUY', 11.2), ('2024-01-05', 'SELL', 10.9)] events= []
case2 ma5-exit  : trades= [('2024-01-04', 'BUY', 11.2), ('2024-01-09', 'SELL', 10.9)] events= []
case3 limit-skip: trades= [] events= [('2024-01-04', 'skip_buy')]
case4 skip_sell-retry: trades= [('2024-01-04', 'BUY', 11.2), ('2024-01-08', 'SELL', 9.85)] events= [('2024-01-05', 'skip_sell')]
case5 equal-close   : trades= [('2024-01-04', 'BUY', 11.2), ('2024-01-05', 'SELL', 11.1)] events= []
```

结论：买入日收阴次日开卖（case1）、收阳持有至 close<sma5 次日开卖（case2）、涨停开 skip_buy 且消耗信号（case3）、跌停开 skip_sell 保留 pending 下一交易日再试（case4）、等号 fail-closed（case5，close==ref 仍卖）——**与 §2 锁定口径逐条吻合**；买入日无卖单（T+1 成立）。

### 实验 E3：pending_buy 跨停牌缺口（🔴 R1 的证据）

```python
# bar 序列：01-01,01-02,01-03(edge=1)，随后直接跳到 01-24..01-26（模拟停牌无 bar）
idx = list(pd.bdate_range('2024-01-01', periods=3)) + list(pd.bdate_range('2024-01-24', periods=3))
```

原始输出：

```
suspension-gap: [('2024-01-24', 'BUY', 15.0)] []
```

结论：edge 于 01-03，股票停牌约 3 周，**复牌日 01-24 开盘仍按 3 周前的旧信号买入**，且无 skip_buy 事件。plan §2 锁定「可测行为：D+1 开盘买或 skip」是二值口径，实际存在第三条路径「D+n 开盘买（n=停牌长度）」。

## 🔴 必须修

### R1（🔴）pending_buy 无过期机制：停牌后旧信号仍成交，违反 §2 锁定口径

- plan 锁定：§2「决策时点」行「可测行为：D+1 开盘买或 skip」；「skip 后 FSM」行「skip_buy 消耗该次信号（不无限挂买）」。
- 实测（E3）：停牌期间无 bar → `next_open` 不触发 → volume=0 / 涨停检查根本不会执行 → `pending_buy` 一直挂到复牌日成交。这不是「skip」，是**延迟成交的 stale 信号**，且 events.csv 无痕迹，会静默污染 30 只样本统计。
- 证据：`backtest/research/ma_chip_edge_backtest.py:387-394`（pending_buy 仅在 next_open 内消费；无 bar 则不消费）。
- 修法（一行级）：置 pending 时记录 `self._sig_len = len(self.data)`；next_open 中仅当 `len(self.data) == self._sig_len + 1` 才允许买，否则记 `skip_buy`（reason=stale）并消费。plan §2「skip 后 FSM」行应补一句：「pending_buy 仅对信号日的下一根 bar 有效；跨 bar（停牌缺口）一律 skip_buy 并消耗」。
- 注：pending_sell 不需要对称修复——卖出重试本就是 plan 想要的行为（skip_sell 保留 pending 直到成交），且持仓是真仓不是 stale 信号。

## 🟡 应修

### R2（🟡）「未完成周丢弃」与可实现行为不符（plan 内部口径 vs 实测路径）

- plan §2「20 周均线」行：「asof 键 = _last_day，只 backward 到 D。未完成周丢弃」。
- 实现 `week_ma20_asof`（ma_chip_edge_backtest.py:100-114）：resample W-FRI 会把**加载数据末端的未完成周**也聚合成一行；当 D == 加载数据最后一日时，`w_last[wi] <= d` 成立，该未完成周的 ma20 会被使用（其周收盘 = D 当日收盘，无未来数据，因果安全）。
- 影响面：仅统计窗最末端 1–5 个交易日的 cond 判定；且末端买入多半成为 names_still_open。量级小，但 plan 字面「丢弃」与行为不一致，多轮评审中易被当成 bug 反复提。建议二选一：改口径为「未完成周仅在其 _last_day <= D 时参与（即数据末端部分周可用但无未来价）」，或在实现里显式 drop 最后一行 partial week。**推荐前者**（改文档一字，不动代码）。

### R3（🟡）§2 禁令字面落空：`oskh_data.float_shares` 模块不存在

- plan §2「抽样」行：「禁止 `from oskh_data.float_shares import`」。
- 仓内实际只有 `oskh_data/float_shares_history.py:18,30`（且其内部已走 `resolve_source_parquet` / `resolve_parquet_container`）。禁令指向一个**不存在的模块**，实现者无从遵守也无法违反。
- 建议改写为可执行口径：「禁止绕过 `resolve_source_parquet('float_shares.parquet')` 裸写盘符路径；禁止把快照股本当 as_of 历史用（须 merge_asof 或 `_load_free_float_shares` 时间维）」。

### R4（🟡）events.csv 未按统计窗过滤，与「统计窗」口径轻微不一致

- trades 过滤了 `stats_start`（ma_chip_edge_backtest.py:506 `trades = [t for t in strat.trades if ... >= stats_start]`），events 未过滤（:511 `events=list(strat.events)`）。
- feed 从 `warmup_from = stats_start - 14d` 开始（:491），warmup 内若发生 skip（理论上 edge 已抹除、无持仓，概率极低但非零——如 order_rejected 事件）会进 events.csv。建议 events 同样按 stats_start 过滤，或在 plan §2「输出」行声明 events 含 warmup。

## 🟢 可选

- O1：§2 括注「仅 broker.set_coo 不够，订单会落到下一根开盘」机理不准——实测（E1-C）是 `next_open` 根本不被调用（cerebro.py:1622），一单都不会有；「落到下一根开盘」是 next() 下 Market 的行为。建议改为「仅 set_coo 不够：next_open 由 cerebro.p.cheat_on_open 门控」。
- O2：涨跌停判定在 front 复权空间做 `round(prev_close*(1+pct),2) ± 0.01`（ma_chip_edge_backtest.py:91-97）。复权价不对齐交易所 0.01 最小价位，深度复权低价股可能误判近涨停开盘。plan 已声明偏差（§2「涨跌停阈值」行、§3.3），建议 summary.md 再带一句「skip 判定于复权空间，容差 0.01」即可，不必改算法。
- O3：`mean_single_name_return` 含期末未平仓市值（equity_end mark-to-market），summary 已有 names_still_open 兜底；可在 §2「报表字段」行注明「ret 含浮盈浮亏」。
- O4：等额本金数值（实现 DEFAULT_CASH=1e6/票）未写进 §2「组合」行；可复现性建议锁定进 plan。
- O5：最低 5 元佣金在 1e6 本金、低价股小仓位下占比可忽略，但若后续降本金试验需注意 min_commission 扭曲小票收益（affordable_size 已预留佣金，实现 OK）。

## ✅ 做对的地方（保留）

- A1（T+1 / 成交链路）：`Cerebro(cheat_on_open=True, runonce=False)` + `next_open()` 下 Market 的设计**实验验证正确**（E1-A/B）；禁用 `bt.Order.Open` 与 COO 语义自洽。信号→成交全程无未来 bar：cond[D] 在 D 的 next()（D 收盘已知），成交在 D+1 开盘。
- A2（等号 fail-closed / MA5 / skip FSM）：E2 case1/2/4/5 与 §2 逐条吻合；skip_sell 保留 pending 重试、skip_buy 消耗信号，方向正确。
- A3（盈筹率尺度）：`get_cyqk_c` 确为 0–1——qlib_cost/cyq.py:229-244 `get_winner` 返回 `cumpdf/tot_cnt` 的累计比例（:243-244），:254 明确 `winner_ratio in [0,1]`。阈值 0.70 无单位错误。
- A4（不读 `ChipDistribution.cyqk_c[0]` 的判断正确）：backtest/chip_indicator.py:104 窗口为 `range(-self.p.period, 0)`（**不含当日**），:123 `adapt_columns(df, stock_code=...)` 未传 `as_of_date`（股本无 as_of）。plan §0/§2 的事实描述准确。
- A5（20 周均线定义）：与 `oskh_factors/weekly_macd_divergence.py:86-103` `_daily_to_weekly` 同构——W-FRI、`close:last`、`_last_day:max`；是真周线 SMA(20)，非 100 日近似。实现本地复制、不改 oskh_factors，符合包边界。
- A6（复权口径统一 front）：§2 锁定 `period=1d adjust_type=front`，均线与盈筹率同一份 OHLC；禁用 `load_single_stock_data` 有据——backtest/qmt_utils_adv.py:62-63 默认 `adjust_type="none"` 且载 1m。
- A7（包边界）：策略+CLI 同文件置 `backtest/research/`，与 README.md:11-12 布局一致；算法复用 `oskh_factors.chip` / `qlib_cost`，筹码 Cerebro 包装留 `backtest/`；不改 `backtest_main_full.py` / rolling（git status 佐证未动）。
- A8（费用）：万 0.5 + 最低 5 元 + 卖出印花税 0.05%（2023-08-28 起口径，覆盖 2024+ 统计窗正确）；自写 `CommInfoBase`（percabs 绝对值 + size<0 加印花税）而非硬套 `trade_fee_policy`，与 Cerebro 插件模型匹配。
- A9（统计窗污染防护）：窗前 edge 置假 + 加载自 2022-07-01（20 周 + 80 日窗口预热充足）+ `ready_for_stats` 预热不足重抽，闭环。
- A10（数据 SSOT）：抽样池走 `resolve_period_root('1d')/dividend_type=front` ∩ `resolve_source_parquet('float_shares.parquet')`（common/infra/data_root.py:189,220），无 cwd 裸路径。

## 总评

方案口径锁定质量高，核心成交链路（COO/next_open/T+1/等号/skip FSM）经最小实验逐条验证为真；唯一实质缺口是 **R1：pending_buy 跨停牌缺口无过期**，与 §2「D+1 开盘买或 skip」二值锁定直接矛盾且静默无日志，属必须修（一行级修复 + plan 补一句）。R2/R3 为口径字面与现实的偏差，建议同轮修掉以免后续评审空转。**修掉 R1 后可进实现/已进入实现的应回补该修复与对应单测（停牌缺口 → skip_buy(stale)）。**
