# 向量化成交核（A 股正确性 · as-built）

- 日期：2026-09-12（E-R5 人裁回写 2026-09-16；E-R6 落地 2026-09-16）
- 状态：已落地。卖点/书契约仍以 [plan-unify-csv-strategies-1-8-2026-09-12.md](_archive/plans/plan-unify-csv-strategies-1-8-2026-09-12.md) 的 U-R\* 为准；下表 **E-R\*** 重开了其中撮合锁（含 E-R5 除权已知边界）。
- 定位：[engine-positioning-ssot.md](engine-positioning-ssot.md)。名单：[pool-csv-contract.md](pool-csv-contract.md)。

## 1. 模块

```
market_layer.py     叶子：时间 / limit_pct / limit_prices(Decimal HALF_UP) / round_fen
ashare_session.py   日线/分钟共用微结构：ST 档、官方 none 昨收+E-R6、涨跌停命中、T+1
ashare_bars.py      日线/分钟共用行情：湖统一 load_minute_ohlc 书帧；qlib bin 保留私有 compact 链（不 import qlib）
ashare_fees.py      日线/分钟共用费率 SSOT：默认双边 10bp；qlib PortAna 5/15bp+最低5（见 §1.1）
csv_pool.py         名单 + 名称列（ST）
csv_ledger.py       Position / SimState / execute_buy / _sell / 追买桶（命中函数转调 ashare_session）
csv_daily_backtest  simulate + 日线加载 + CLI（可选 `--qlib-cost` → SimState 费率覆写）
csv_minute_backtest scan_held_day + CLI；分钟/日线加载转调 ashare_bars（继承 SimState 默认费率）
csv_minute_backtest_v7  独立仓位机；显式 `FeeSchedule`；微结构只走 ashare_session；_day_frame_records 按 (b) 切书帧/compact
ashare_fill_clock.py    命名叶子：SessionPhase / FillPriceRule；不接线、不选价
```

7 不进 BOOKS，不 import 6/8 `SimState`。

### 1.1 研究费率合同（P3 δ1 as-built；docs/tests only）

计划 SSOT：[plan-industry-align-p3-fees-2026-09-19.md](plan-industry-align-p3-fees-2026-09-19.md)（人裁 P3.1/P3.2/P3.3=A/A/A）。接线测：`tests/test_ashare_fee_wiring.py`（MC-1）；公式测：`tests/test_ashare_fees.py`；fence：`tests/test_ashare_simulate_import_fence.py`（旁证，非接线闭合）。

| 合同项 | As-built |
|---|---|
| 公式 | `ashare_fees.trade_commission(notional, rate, min_cost)`；`min_cost>0` 时 `max(fee, floor)` |
| 模块默认指针 | `DEFAULT_SCHEDULE is BILATERAL_10BP`（双边 10bp，`min_cost=0`） |
| 书/分钟默认指针 | `SimState()` 三 float：`(buy_cost_rate, sell_cost_rate, min_cost) == (COMMISSION, COMMISSION, 0.0)`；**不**读 `FeeSchedule` 对象 |
| qlib PortAna | `QLIB_PORTANA` = 买 5bp / 卖 15bp / min 5；日线 CLI `--qlib-cost` 经 `simulate(..., buy_cost_rate=..., sell_cost_rate=..., min_cost=...)` 写入 `SimState`（opt-in） |
| 分钟路径 | `csv_minute_backtest.simulate` **无**费率 kwargs；继承 `SimState` 默认 |
| v7 路径 | `_buy` / `_sell_lots` / `simulate_v7(..., fee=FeeSchedule=DEFAULT_SCHEDULE)` 显式透传 |
| 扣费粒度 | **每次函数调用**（非按标的/按日）。书 `_sell`×2 lot 可两次触 floor；v7 一次 `_sell_lots` 聚合名义后一次 `credit_sell`（§2.4 两 lot oracle：PortAna 下书 10/+1990 vs v7 一次 5/+1995） |
| 印花/过户边界 | 研究热路径 **仅佣金记账**（代理口径，≠ 现行印花税账单）；禁止未来在 ledger 再加印花行造成双重计入。真券商印花+过户留在 live `trade_fee_policy`，**不得** import 进 simulate 热路径 |
| 产物列 | 书 `trades[].commission` 已有且写入 `trades.csv`；v7 `_event` **无** commission 列。δ1 不改 schema、不给 v7 补列。`EOD_MARK` 的 `commission:0` 不是卖出扣费 |
| 非 CSV 接线证据 | `unified_exit_modea` 线性近似与 `research/engine.py` 占位 **不是** 书/v7 费率接线证据（parked） |

`bars_from_pool` → `load_session_bars` 保留：湖源整窗调用 `load_minute_ohlc(use_cache=False)`，
v7 / topk 共用 `_load_cli_bars`，只将所需日切片转成 records。帧契约 **(b)**：书帧 `ymd` /
DatetimeIndex，qlib_1min 的私有 `_load_minute_compact` 链仍用 `date`；compact 湖分支仅留作冻结对照，
生产调用归零。新策略复用加载、涨跌停与费率模块，不另写实现。

读取器字节级冻结；保留书帧新成交，七类预期迁移与其余漂移的 STOP 边界见
[plan §5.1](plan-ashare-engine-refactor-2026-09-18.md#51-切片-a-预期迁移人裁-2026-09-18)。
已知限制仍在：书引擎 cache 无新鲜度守卫，加载线程池无 timeout；v7 小名单窗不读写共享 cache。

T+1 在书引擎原调用点将 `calendar[entry_idx]` 映射为日期后调用 `t1_sellable`；卖点仍用
联合日历下标差 `n_days`，分钟扫描器仅收到布尔 `can_sell`，两个扫描内核保持冻结。
买卖门复用 `skip_buy_at_limit` / `defer_sell_at_limit`；双账本及填单函数契约保留。
已知分叉继续记录：书侧无昨收/未知板块先冻仓；v7 卖侧这两支 `limits=None` 仍放行，
加仓侧同样保留现状，ST 名称仍按窗末名平铺而非 PIT。日线 `stop_loss:gap_open` = 触发当日 open；`daily_stop_touch_at_trigger` = 触发当日 trigger；命中 `daily_same_bar_prefixes` 且通过涨跌停门才按当日 close；只有确实写入 `pending_exit` 的 reason 才下一可卖日 open。不在本轮改变时点或参考价之外的股数。

### 2.1 fill-gates retained fork（as-built 合同，不做行为统一）

| 主题 | 书引擎（daily/minute + shared loop） | v7 路径 |
|---|---|---|
| `limits is None`（未知板块/无昨收） | 早拒：持仓循环直接 `skip_unknown_board` 并 `continue`（`csv_daily_backtest.py:321-323`，`csv_minute_backtest.py:601-603`）；共享买侧/追买环同样早拒（`csv_simulate_loop.py:155-157`, `:260-261`）。 | 首开仓分支会拒绝未知板块（`csv_minute_backtest_v7.py:389-391`）；但已持仓卖/加仓门函数是 fail-open（`ashare_session.py:73-78` + v7 调用点 `csv_minute_backtest_v7.py:342-373`）。 |
| “门未拦截” vs “真实成交” | 明确区分；例如持仓门后仍可能不成交。 | 同样明确区分：加仓门未拦截时仍可能在 `_buy` 里 `skip_cash` 不成交（`csv_minute_backtest_v7.py:209-210`）。 |
| ST 名称跨日语义 | 书引擎按日 as-of 单调更新（`csv_common.py:85-107`；消费点 `csv_daily_backtest.py:291` / `csv_minute_backtest.py:565`）。 | v7 使用窗口扁平名（`ashare_session.py:81-85`, `:97`；消费点 `csv_minute_backtest_v7.py:324`）。 |
| 零量/缺 bar 语义 | loader 先过滤零量占位，再进入“无 bar 不交易/按 last close 估值”路径（`csv_daily_loader.py:83-84` + `tests/test_csv_daily_backtest.py:990+`）。 | 缺关键分钟记录走 no-fill（如 `skip_no_1455`），不代表交易被门拦截。 |

注意：
- 上表是 **as-built fork 合同**，用于防止静默漂移，不代表本轮引入新成交模型。
- 有 fail-open 的地方保持 fail-open；不得在未开新人裁切片时擅自改成 fail-closed。
- OSS 只可类比术语，不可作为本仓行为证据；行为证据必须来自本仓锚点与测试。
- #112 延后项：14:57 行为（P1）、trades 新列（P2）、ST PIT（δ3）、touch↔mark 耦合（P4）继续延后。费率 **行为** 冻结（P3.1/2/3=A）；δ1 只做合同文档 + data-free 接线测，不改生产扣费。

现状成交时钟（只命名，不改价）。限定：扫描窗口标签 / 非全量 / 不含 v7。`closing_call`（14:57–15:00，含端点）是当前扫描窗口标签：`_in_session` 接受这些 bar，扫描若到达仍按旧分支处理；不是交易所忠实集合竞价撮合，也不证明所有路径在该段成交。下表不是全量选价器：same-bar 前缀不只有 `open_board`（还可含 `topk_drop` / `model_exit`），策略 9 的证明夹具不能单独证明 open/close。v7 另有首 bar open / 严格 14:55 / 最后一根 close，未纳入本表。读取器、两个分钟扫描内核、双账本、E-R1–E-R6 与价格数字未变。

| 符号 | 现行为 |
|------|--------|
| 池买·日线 | 文件名日 T 的 close，不是 T+1 open |
| 池买·分钟 | T 日 14:55 close；缺 14:55 才用 `[14:30, 14:55]` 最后一根 close；不是 T+1 open |
| 追买·日线 | 通过持仓门与指数门后，可报价日 close；`quoted is None` 保留 pending；reason 仍为 `chase:T+1` |
| 追买·分钟 | 可报价日 09:45 close；缺 bar 才用既有 `≤09:45` fallback；reason 仍为 `chase:T+1` |
| `continuous` / `closing_call` | 扫描窗口标签，不是过滤器，不是交易所忠实 closing-call 撮合 |
| `daily_open_board_same_close` | 命中 `daily_same_bar_prefixes` 且通过涨跌停门才按当日 close |
| `daily_stop_gap_open` | 日线 `stop_loss:gap_open` = 触发当日 open |
| `daily_stop_touch_at_trigger` | 触发当日 trigger |
| `daily_pending_next_open` | 只有确实写入 `pending_exit` 的 reason 才下一可卖日 open |
| `minute_gap_open` | 分钟 gap-stop 用该 bar open |
| `minute_trigger_bar_close` | 分钟其余触价用该 bar close |

## 2. 现锁（E-R\*）

| ID | 现行为 | 作废的旧锁 |
|----|--------|------------|
| **E-R1** | 日线+分钟：**任何卖因**成交前 `hit_limit_down` → defer、不成交（含 6/8 trail、`stop_loss:touch`、`profit_take`、`force_sell`、`ma_signal`、`open_board`）。reason 前缀不改。 | U-R1「分钟仅 `stop_loss*` defer」 |
| **E-R2** | `limit_pct`：`300/301/302/688/689=20%`；`430/83/87/88/920=30%`；`600/601/603/605/000/001/002/003=10%`；名称列 `ST`/`*ST`=5%；其余 **`None` → `skip_unknown_board`，不默认 10%**。 | U-R12「原样搬家 / 不建模北交 ST 689」 |
| **E-R3** | 市场层只留 Decimal `limit_prices`。v7 改 import。`1.65×10%` 跌停 = **1.49**。禁止 `round()` 银行家舍入。 | U-R10/U-R30「v7 留本地 float」 |
| **E-R4** | 停牌仍冻仓。加载侧丢弃零量占位 K（日线 `volume==0`；分钟整日 `sum(volume)==0`），**等价于当日无 K**，复用同一条冻仓 / pending / `last_close_mark` 路径，不建第二套停牌状态机。净值用最近有 K 的 close，不用 `pos.cost`。追买日无 K **保留 pending** 到下一有 K 日（有 K 后仍只评一次）。 | U-R27「追买 pop 作废 / 净值标成本」 |
| **E-R5（收窄 2026-09-16）** | csv 日线/分钟链成交与估值全程 `dividend_type=none`；**除权日**（事件判定见 E-R6）的 cost/peak/涨跌停参考价已按 E-R6 修正。残留近似三句：①跳变 ≤0.5% 的小额分红（窗内约 1,372 起）不修正——止损触发距离/止盈地板偏移 ≤0.5pp，低价股档位边缘可差 1 分；②跨除权持有 lot 的成交与净值按原始价×原始股数记账（送转不增股、分红不入账），trades pnl 与净值含 (1−k) 结构性失真（见 E-R6 残留声明）；③v4 SMA 门用截至昨收的原始 closes，除权日不换域（假 ma_signal/buy_gate 拒，历史行为保留）。21M 口径历史数字（命中 daily 8.1% / minute 2.0%）与 5 亿口径 149 笔止损为**修正前口径**。证据：[np2-exdiv-hold-hits-host-note-2026-09-16.md](np2-exdiv-hold-hits-host-note-2026-09-16.md) + [survey-exdiv-adj-data-prep-2026-09-16.md](survey-exdiv-adj-data-prep-2026-09-16.md) + [plan-exdiv-refprice-2026-09-16.md](plan-exdiv-refprice-2026-09-16.md)。 | 无（E-R5 原「不对除权调整」整条收窄；非 U-R 重开） |
| **E-R6** | **除权日参考价修正**（v1–v10、v7）：事件= `ex_date_index` 主 ∪ 因子跳变 >1e-2 兜底；k=因子行比 LAG；除权日一次性缩放 open lot 的 cost/peak，并将当日 prev_close→档位换算点映射到 D 域。成交价、净值估值、shares、佣金、T+1、chase 判定逻辑、现金红利入账均不动。残留声明：①跨除权 lot 的 trades pnl/净值含 (1−k) 结构性失真——本片只修触发参考，**不回收**历史假止损已实现亏损（5 笔 −196 万的回收上界仅 +35~125 万 ≈ 0.01–0.025pp，切片 D 宿主验证）；②v4 SMA 门除权日不换域；③噪声带 ≤0.5% 不修正。日线/分钟共用 `ashare_session`；书引擎 `simulate(..., exdiv=None)`，仅 `run()` 加载。 | 无（新人裁锁；承接 E-R5 选项 B） |

不重开：费率 0.1% 双边、7 不进书、不改 `presets.py`。Cerebro / Rolling **已退场**（见 [engine-positioning-ssot.md](engine-positioning-ssot.md)），禁止复活——旧稿「不删 Cerebro」作废。

**E-R5 重开条件**（噪声带/残留面；触发即重跑 NP2 探针再裁）：①止损档收紧至 <10% 或 trail 地板整体上调；②名单池切到高分红/高送转风格；③分钟链成为主研究面；④任何 NAV 对比结论差距落在 <1% 量级时。见 host-note §3。**E-R6 切片 D**（宿主 5 亿重跑）完成后放行 v8 规则 v2 切片 D。

## 3. 对照货币

6/8 历史净值会因 E-R1 变少卖。对照看 **reason / 可卖 / 涨跌停**，不是旧 `daily_equity.csv`。改前合成窗快照：`tests/fixtures/csv_engine_pre_er1/`。
