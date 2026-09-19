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
| **E-R6** | **除权日参考价修正**（v1–v10、v7）：事件= `ex_date_index` 主 ∪ 因子跳变 >1e-2 兜底；k=因子行比 LAG；在事件落日与行情域一致且可处理时，扫描前缩放当时已持有参考价（书 cost/peak；v7 字段见 §2.1），并将对应 prev_close→档位换算点映射到 D 域；缺 bar/因子恢复残留见 §2.1。成交价、净值估值、shares、佣金、T+1、chase 判定逻辑、现金红利入账均不动。残留声明：①跨除权 lot 的 trades pnl/净值含 (1−k) 结构性失真——本片只修触发参考，**不回收**历史假止损已实现亏损（5 笔 −196 万的回收上界仅 +35~125 万 ≈ 0.01–0.025pp，切片 D 宿主验证）；②v4 SMA 门除权日不换域；③噪声带 ≤0.5% 不修正。日线/分钟共用 `ashare_session`；内存引擎默认 `exdiv=None`；书由 `run()` 加载，v7 由 `main()` 经 context 加载；daily 连续域跳过与 minute/v7 差异见 §2.1。 | 无（新人裁锁；承接 E-R5 选项 B） |

不重开：费率 0.1% 双边、7 不进书、不改 `presets.py`。Cerebro / Rolling **已退场**（见 [engine-positioning-ssot.md](engine-positioning-ssot.md)），禁止复活——旧稿「不删 Cerebro」作废。

**E-R5 重开条件**（噪声带/残留面；触发即重跑 NP2 探针再裁）：①止损档收紧至 <10% 或 trail 地板整体上调；②名单池切到高分红/高送转风格；③分钟链成为主研究面；④任何 NAV 对比结论差距落在 <1% 量级时。见 host-note §3。**E-R6 切片 D**（宿主 5 亿重跑）完成后放行 v8 规则 v2 切片 D。

## 2.1 P3 δ2 除权参考价契约（Human GO A/A/A/A/A）

实施基线为 `7c049c63ed441a17156b4476f3974bb86ab57fa9`（post #122）。本节细化 E-R6 的 as-built 适用条件；生产行为不变。计划、评审映射与 data-free 验收命令见 [δ2 plan §7–8](plan-industry-align-p3-d2-exdiv-2026-09-19.md)。原 E-R6 人裁不含 v7；v7 接线来自后续 shared-session 改造，本节记录当前分叉，不改写历史授权（E-d2-09）。

**事件门与 k。** 真实加载符号是 `exdiv_map.load_exdiv_ratios`（MC-1，无 rates/factors 别名）。读窗向前 10 个自然日；过滤非正数、NaN、Inf，按日期取前一有效因子行 `F_prev`，不是日历 D−1。令 `j=abs(F_D-F_prev)/F_prev`，有限有效的 `k=F_prev/F_D` 可小于或大于 1：

| 当日 ex 行 | 因子相对跳变 j | 是否输出 k |
|---|---|---|
| 有 | `j <= 0.005` | 否（噪声带含等号） |
| 有 | `j > 0.005` | 是 |
| 无 | `j <= 0.01` | 否（含 0.5%–1%） |
| 无 | `j > 0.01` | 是（因子跳变兜底） |

噪声带衡量 j，不是 `abs(1-k)`；比较保留现有 float，无新增容差。事件枚举不保证有可用因子/LAG。双路径都显式指向临时夹具才隔离 resolver（MC-2）；根路径解析错误仍会抛出。路径解析后缺 adj 才警告并返回空 map，缺 ex index 降为跳变兜底，不能外推成未配置根也静默无数据。`exdiv_skipped_no_factor` 不是完整审计计数。

**字段与顺序。** 正常逐日循环在扫描前缩放当时已持有的参考字段，然后映射昨收、计算档位、执行卖出/买入；不是 helper 幂等性。重复调 helper 会重复相乘，多事件累计 `k1×k2`。书路径当日新买/step lot 和 v7 当日新开/加仓在这次 pass 后建立，不再乘当天 k。

| 路径 | 缩放字段 | 保留字段 / 前置条件 |
|---|---|---|
| 书 daily/minute | 各 lot `cost`、`peak` | shares、entry_idx、peak_hm、lot_id、pending_exit、reserved、ride_with、is_step；daily 要当日 K 与先前 closes，minute 还要当日分钟切片 |
| v7 | `entry_A`、`avg_cost`、`peak`、非空 `add1_A1`、各 `Lot.price` | shares、buy_date、kind、stage、last_add_date；有当日 records 才缩放 |

v7 非空 `add1_A1` 仅由人工 Position 验证兼容分支，公开自然加仓不赋值（E-d2-03）；公开路径另证可达字段、混持 T+1、加仓后同日 stop 仅卖老 lot（E-d2-07）。pending_exit 先经缩放与新档位，再按 raw 开盘价成交或跌停续 defer（MC-5）。held/chase/pool/**step** 均消费映射昨收（E-d2-05）；真实 Decimal 链须用主板 `600000.SH`：`10×0.5→5→(5.50,4.50)`、`3.30×0.5→1.65→(1.82,1.49)`，不可用 float 自算档位替代（E-d2-04/MC-6）。

**已关闭面与未关闭面。** 事件落日与行情域一致、且作用于事件日存量 lot / 对应昨收时，E-R6 修正触发参考错域；不复权整条行情。缺 bar 分支在缩放前、map 只查当日键，停牌日事件没有通用补缩放队列。因子缺行/无效后恢复可能把 k 落到行情已经换域的恢复日，重乘新域昨收及缺行日新 lot；恢复前真实 SELL 也不会被撤销（E-d2-01）。日期 LAG 与合成前缀一致性不证明当日因子在决策时刻可得，原始因子 as-of/版本 PIT 仍**未证 / 历史观测近似**（E-d2-02）。

送转不增股、分红不入现金、raw mark 不获经济补偿：隔离其它交易，100 股、cost=10、peak=12、cash=2000、k=0.5 后，cost=5、peak=6，仍 100 股和 cash=2000；raw close 10→5 时权益 3000→2500。500 是该特例差额，`1-k` 不是所有组合收益误差的固定百分比。公开 v7 无 Position 注入，小数值 oracle 只用于书/helper；v7 用事件前快照核对股数/现金及 raw mark 差额（MC-4）。EOD_MARK 不是 SELL。经济残留、v4 SMA 原始序列和原有噪声带继续 deferred；P1/P2/P4、δ3+ 不在本刀。

**价格域只保证到具体入口（E-d2-08/MC-3/MC-7）。**

| 入口 | as-built exdiv 接线 |
|---|---|
| daily `run()` lake none | 加载 map |
| daily `run()` front/back 或 `--qlib-data-root`（`qlib_day`） | `exdiv=None`，跳过加载 |
| book minute `run()` | daily=lake/qlib_day × minute=lake/qlib_1min 四组合均加载、传 map |
| v7 `main()` | 同四组合经真实 `load_limit_context` 加载、传 map；helper 无 source 参数 |
| 内存 `simulate` / `simulate_v7` | 默认 exdiv=None；不认证行情复权域，调用方负责域与 map 一致 |

> **🔴 CLI 域风险：日线 `--qlib-data-root` 跳过 E-R6，不等于分钟 `--qlib-day-root` 跳过。minute/v7 的 `daily=qlib_day` × map 仍是危险组合，pins 证明现状传参，不证明混域安全。** `qlib_day` 的后复权声明与 `qlib_1min` 的 none 声明不同，读取器不认证真实 dump 域；`--qlib-cost` 仅是费率开关。Human GO A 保持这些入口差异，统一跳过或拒绝混域须另案。

验收仅扩展 plan §7 的四个既有测试文件。B1–B6 分别覆盖事件门、书顺序、v7 分叉、昨收档位、经济残留、入口矩阵；既有混域 v7 trial-stop 向量只作为布线证据，新增同域 held 向量独立验证缩放/档位/成交（E-d2-06）。入口测仅 pytest 内完全 stub 的 `run()`/`main(argv)`，没有 CLI 回测、湖访问或产物回测；book writer 位于 main，v7 writer/index/bars 全 stub，非空 pool 保留 context 加载链。

## 2.2 P3 δ3 ST name as-of / v7 flatten fork（Human GO A/A/A）

实施基线为 `cce17f319ead5c64a202632c3665b4eeb3e3e7a5`（post #124）。P3δ3.1/3.2/3.3=A/A/A 只授权本节契约与 data-free pins，**生产行为不变**。真实测试映射、验收与生产冻结证明见 [δ3 plan §7.1 / §8.4 / §9](plan-industry-align-p3-d3-st-pit-2026-09-19.md)。以下是源码 as-built，不是交易所规则认证。

| 消费层 | 固定合同 | 已复核 file:line |
|---|---|---|
| CSV 输入 | 名称取第二列；同文件代码去重保留首次。`load_pool_names_by_day` 只读闭区间 start/end 内文件，只输出非空名；不预载窗口前历史 | `backtest/research/csv_pool.py:53-68`、`:161-182` |
| 书 daily/minute | `pool_names_by_day is None` 才用 flat map；即使 `{}` 也优先于 flat。从空 `last_seen` 起步，按日期排序，消费 `date <= ds` 的非空名，缺名继承 | `backtest/research/csv_common.py:85-108` |
| 书接线 | shared loop 创建 resolver；daily/minute 每会话取名；两个 `run()` 均加载并传 by-day 名称 | `backtest/research/csv_simulate_loop.py:96-109`；`csv_daily_backtest.py:291-293`、`:537`、`:617`；`csv_minute_backtest.py:577-579`、`:821`、`:913`（均在 `backtest/research/`） |
| v7 保留分叉 | `flatten_pool_names` 按日期排序后 `dict.update`；context 平铺 start/end 窗口。`simulate_v7(names=...)` 无 by-day 参数，各会话使用同一 map | `backtest/research/ashare_session.py:81-100`；`backtest/research/csv_minute_backtest_v7.py:277-282`、`:327-329`、`:571`、`:583-584` |
| 名字→档位 | 正则识别 ST / *ST，忽略大小写；命中 **先返回 5%**，再考虑板块回退。已知板块缺名可回落板块档位，未知板块非 ST 为 None；ST 命中甚至先于未知板块。价格以 Decimal HALF_UP 到分 | `backtest/research/market_layer.py:15`、`:34-36`、`:57-84` |
| 书例外 | 显式 `qlib_limit_pct` 使用固定 band，绕过 named limits。δ3 书 ST pins 使用默认 `qlib_limit_pct=None` 路径 | `backtest/research/csv_common.py:73-82` |

ST 正则为 `(?:\*ST|(?<![A-Za-z])ST)`（`re.IGNORECASE`）；`WEST` 这样的拉丁词不命中。

书 resolver 的游标只向前，适用于现有递增会话循环；它不是任意日期回查 API，返回的可变字典也不是独立历史快照。v7 的“窗口末名”是**该代码在输入窗口内最后一次出现的名称**，不要求代码在窗口末日出现；**窗口末名 ≠ 全历史最新名称**。真实 loader 会过滤空名，空白行不发出摘帽/退市/清空事件；直接向 `flatten_pool_names` 传含 `""` 的字典则会覆盖旧名，两种输入边界保持原样。

| 合成主板：昨收 100，早日买价 105 | 书默认 named-band | v7 窗口平铺 |
|---|---|---|
| 早日普通名，晚日 *ST | 早日 110/90，资金等其它门满足可买 | 早日 105/95，`skip_limit_up` |
| 早日 *ST，晚日普通名 | 早日仍 105/95，首买被拦 | 早日 110/90，其它门满足可买 |
| 晚日缺名/空名（真实 loader） | 继承早日非空名 | 保留窗口内最后非空名 |

相同初态与名称前缀下，书侧追加未来名不改早日 BUY/SELL 与权益；窗口末 `EOD_MARK` 是报告记录，不作为真实成交比较。v7 延长窗口则可改变早日名字、档位与成交。持仓卖出/加仓也消费这条名称链；pins 观察真实档位调用，并把拦截与 fill 分开断言，明确资金充足、卖出 lot 满足 T+1。未知名称、未知板块和 ST 命中分别设例；`limits=None` 的 predicate 放行本身不能证明会成交。

**日期 as-of ≠ 决策时刻可得性 PIT 证明。** 名单日期不证明该文件在当日决策前已发布；当前输入没有 `available_at` / 修订版本过滤，供应方完整历史 PIT 仍未证。δ3 不修 v7 ST PIT，也不替 δ2 关闭因子可得性或经济残留。P1/P2/P4 继续 deferred；δ4–δ6 不随本刀自动获授权，生产改造须各自独立人裁。

## 2.3 P3 δ4 v7 limits=None contract（Human GO A/A/A）

实施基线为 `844919481f12a220fdf3c411d9be09583b2d7984`（post #125，含 δ3）。P3δ4.1/4.2/4.3=A/A/A 只授权现状契约与 data-free pins，**生产 Python 零 diff**。测试映射与验收/冻结证明见 [δ4 plan §7–9](plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md)。本 GO **不授权 fail-closed、显式 policy 开关或生产 gate 改造**；政策变更必须另立 P3δ4.1=C 的生产案。Slice C 验收不是人裁选项 C。

`limits=None` 表示没有可用档位，不能推断标的依法无涨跌幅限制。两个来源分别是：没有 today 之前的 close；有昨收但未知板块且名称未命中 ST。ST 名称先返回 5%，所以未知代码不必然得到 None；NaN/Inf、零/负昨收不由本刀扩展分类。以下 file:line 已按固定基线重新阅读核实：

| 路径 / 前提 | as-built 合同 | 源码锚点（均在 `backtest/research/`） |
|---|---|---|
| None 来源 / 门函数 | 无昨收返回 None；未知非 ST 板块返回 None。`skip_buy_at_limit` / `defer_sell_at_limit` 遇 None 都是 False，仅表示此门不拦截；有档位时仍用 Decimal HALF_UP 到分并拦截上下限 | `ashare_session.py:44-78`；`market_layer.py:43-84` |
| 书 held daily/minute，默认 named-band | 缺昨收在档位计算前退出；有昨收但档位 None 在 lot 卖出循环前 `skip_unknown_board`。这不保证全会话字段不变 | `csv_common.py:22-45`；`csv_daily_backtest.py:300-327`；`csv_minute_backtest.py:586-618` |
| named-band 前提 / MC-1 | `qlib_limit_pct is None` 才按名称/板块计算；显式固定 band 绕过该判断，未知非 ST 前缀仍可有档位。本刀书侧 pins 断言真实 hooks 的值为 None，不能把早拒结论泛化到固定 band | `csv_common.py:73-82`；消费点 `csv_daily_backtest.py:320-321`、`csv_minute_backtest.py:612-614`；接线 `csv_strategy_books.py:127`、`:713`、`:788` |
| 书 chase / pool / step | 有报价/昨收，且到达各自档位分支后，None 均早拒。step 无昨收先退，不能记成已触发 None gate；step 的未知板块计数与 held 扫描计数须分开 | `csv_simulate_loop.py:143-160`、`:249-267`、`:333-350` |
| v7 14:55 首开 | index gate 在前；缺昨收 `skip_no_prev_close`；有昨收而档位 None 为 `skip_unknown_board`，均不建立 trial lot | `csv_minute_backtest_v7.py:384-400` |
| v7 held stop | 策略 stop 满足后，None 不 defer，继续尝试卖出；仍受 lot 的 T+1 约束 | `csv_minute_backtest_v7.py:341-357`、`:226-251` |
| v7 held add | 时窗/ladder 满足后，None 不触发两道档位拦截；整百股、含费现金足够才买入并更新 stage / last_add_date，现金不足仅记 `skip_cash` | `csv_minute_backtest_v7.py:361-383`、`:205-223` |
| v7 timer | 最后一根 record 且真实 `timer_due=True` 时，None 不 defer；T+1 可卖才有 `exit:timer10` 和现金流，无可卖 lot 则无卖单、现金/lot 不变 | `csv_minute_backtest_v7.py:401-409`、`:226-251` |
| 无 records / mark | v7 无 records 在档位和 timer 前退出，池内可记 `skip_no_1455`；末日估值仍执行。书有昨收时可先缩放参考价再拒绝未知板块，随后仍按行情 mark | `csv_minute_backtest_v7.py:316-329`、`:416-418`；`csv_daily_backtest.py:307-325`；`csv_minute_backtest.py:597-617`；`csv_simulate_loop.py:381-420` |

门未拦截、尝试交易、实际 fill 分层验收。fill 以真实 BUY/SELL、股数、lot 与含费现金变化为证据；`EOD_MARK`、peak/last_prices、参考价缩放均不能冒充成交。None 首开拒绝与 held stop/add/timer 的 fail-open 分叉保持；无 records 也不会因门放行产生 bar。

测试只用内存或 tmp_path，通过公开 `simulate` / `simulate_v7` 进入目标分支。held 初态由测试注入，未知板块持仓、旧 timer anchor 配同日 lot 都是构造向量，不宣称自然首开可达。timer 向量避开 stop/add，用 session list 隔离 index gate；spy 透传真实 timer/档位门。书 step 用真实 version8 hooks、空 pool，分别观察 held 与 step 的拒绝计数；已知板块对照锁住 100 股 × 12、5 元 floor、1205 元精确成交 / 少一分钱拒绝。δ1/δ2/δ3 生产合同、P1/P2/P4 与其它 δ 的独立授权边界保持。

## 3. 对照货币

6/8 历史净值会因 E-R1 变少卖。对照看 **reason / 可卖 / 涨跌停**，不是旧 `daily_equity.csv`。改前合成窗快照：`tests/fixtures/csv_engine_pre_er1/`。
