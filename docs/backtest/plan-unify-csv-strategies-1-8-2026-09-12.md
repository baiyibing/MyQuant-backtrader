# Plan：本仓回测统一（策略 1–8 + 市场层 + Cerebro 化石）

> **落盘**：2026-09-12。
> **状态**：📄 **v1.2 · classic fan-out 已吸收 · 可进切片 A**。未授权实施（等人说「按 plan 实施」）。
> **fan-out**：2026-09-12 classic，四家 rc=0（codex 293s / kimi 263s / auto 234s / claude 500s）。综合：`docs/architecture/reviews/2026-09-12/plan-unify-csv-strategies-1-8-2026-09-12/merge-consensus.md`。
> **风险档**：**L2**（策略书扩面 + 引擎原语 + Cerebro 入口冻结；不进实盘 / 不改 `presets.py`）。
> **范围**：MyQuant-backtrader。1.3 只读对照。LEBS / MockQMT 不搬进本仓。
> **定位 SSOT**：[engine-positioning-ssot.md](engine-positioning-ssot.md)。
> **上游**：2026-09-12 三仓讨论；人裁「1–8 一次性都改完」「Cerebro 和 1–5 这轮也动」。
> **对抗**：dissent-steelman / domain-safety / pattern-evidence（不计票）。勘误 §9。

---

## 0. 一句话

本仓第一方回测只留 **向量化**。不是「1–8 同一套 `simulate` 叙事」：

| 组 | 落法 |
|----|------|
| **1 / 2** | 同构书：引擎止损 + `take_profit` 回撤。 |
| **6 / 8** | 已有书。只接线市场层 + `--pool-dir`。规则不改。 |
| **5** | +2% 进书；**14:50 是引擎时钟**，不进四参 `take_profit`。日线 **不做** 强制卖。 |
| **3** | **独立保留扫描 / 日线第三成交钟**，不是默认空钩子。 |
| **4** | `buy_gate` + **`sell_gate`**（均线卖，`ma_signal:MA5`）。四参 `take_profit` 看不见昨收序列，禁止再假装兼容。不改 6/8 `Position`。 |
| **7** | 不进 BOOKS。独立仓位机。只改叶子 import。 |

Cerebro / Rolling **观察退役**（可对照，默认不跑）。市场层只抽市场事实，不抽撮合。

---

## 1. 非目标 / 禁改

| 不做 | 原因 |
|------|------|
| `register(version7)` 进 `csv_strategy_books` | 7 是金榕元仓位机，不是 TopN/隔夜书 |
| 7 import 6/8 的 `SimState` / `Position` / `execute_buy` / `_sell` / `scan_held_day` / chase | H-R3 / F-R7 仍有效 |
| 把 7 的 lots / 分档卖塞进 6/8 `simulate()` | 同上 |
| 改 `trade_decision/presets.py` | 与 1.3 共享卖核；本仓研究副本住 `strategyN_rules.py` |
| 新写 `ProfitStrategy.StrategyN` / 改 Rolling 本体 | Cerebro 不接新策略 |
| 删除 Cerebro / chip / ma_chip 代码 | 观察退役，不是物理拆除 |
| 拷 LEBS / MockQMT 进本仓 | 验收在 1.3 |
| 用 Qlib `PortAnaRecord` 或 Cerebro 净值验收新书 | 已停用 / 化石 |
| 策略 4 全市场无名单扫 | 宇宙仍是日 CSV；均线只过滤能不能买 |
| 策略 3/5 日线引擎假装有 09:30–09:40 / 14:50 逐分钟 | 日线必须写清近似 |
| `load_pool_days(..., pool_dir=None)` 给 7 用 / 回落 `stock_pool/` | 策略 7 F-R5 |
| 本轮改 `limit_pct` 北交/ST 档 | 会改 6/8/7 热路径；只搬家、档位另锁 |
| 本轮改 6/8 停牌日追买 `pop` / 净值标成本 | 已知失真，写入 HELP_LOCK，不顺手「修好」 |
| 1–5 书 / 市场层引入 `cyqk` / `chip_indicator` / `chip_algorithm` | 盈筹率本 plan **不适用** |
| 6/8 湖索引改走 v7 `_as_datetime` | 日历契约不同 |

---

## 2. 已锁裁决（实施不得改口）

### 2.1 买侧与书契约

| ID | 锁 |
|----|----|
| **U-R1** | 买侧同构（1/2/3/5/6/8）：名单日 14:55（日线=收盘）、涨停当日不买、T+1 09:45 追买一次、T+1 可卖、涨停禁买可卖。**跌停 defer 本轮沿用现范围，不升格**：日线 = `pending_exit` + 止损开盘；分钟 = **仅** `stop_loss*`（`csv_minute_backtest.py:586-591`）；3 的日线 `open_board` 另按 U-R20。禁止按「全 reason 跌停禁卖」改 6/8 的 trail 成交。4 = 同构名单 **再** 过 `buy_gate`。**追买与名单买走同一 `buy_gate`**。7 买侧仍是自己的 14:55 + 指数闸，不接追买。 |
| **U-R2** | 6/8 热路径保持：`take_profit(px, cost, peak, n_days)` 四参不变 + `record_params` + `allow_add` + `peak_gap_min`。书 hooks **具名键**（禁止 `if strategy=="version3"`）：`buy_gate`（默认恒真）、`sell_gate`（默认 None）、`force_sell_hm: Optional[int]`（5=`14*60+50`，其余 None）、`reserve_limit_up: bool`（仅 3 为 True）、`daily_same_bar_prefixes: tuple[str,...]=("open_board",)`。引擎级 `stop_pct is None` 短路。禁止为 1/2/4/6/8 各复制一套 `simulate`。**3 允许独立分钟分支**（`scan_held_day` 只加带默认的可选 kwarg，**返回仍是 5 元组**；`pos.reserved` 由调用方 `reserve_step` 回写）。 |
| **U-R3** | `stop_pct is None` = 不止损（4、5）。引擎 **仅当** `isinstance(stop_pct, float) and 0 < stop_pct < 1` 才算止损。禁止 `or 0` / `or 1.0` / `stop_pct=1.0` 假装无止损。4/5 的 `apply` **原样返回 None**，禁止走 6/8 的 `None → 书默认`。`record_params` / `summarize` 不得对 `None` 做 `%` 格式化。 |
| **U-R14** | **port 源 = `backtest/ProfitStrategy.py::StrategyN`**（Cerebro 化石）。`presets.py` 只读对照，差异入 HELP_LOCK。禁止为「对齐 presets」改书。已知差：策略 3 涨停留 vs presets 先卖 20%；策略 5 不读 `force_sell_mode`。 |
| **U-R15** | 名单契约：`YYYYMMDD.csv`、首列裸六位、utf-8-sig、可表头；空/缺日=不买。6/8 默认 `stock_pool/`；7 禁止回落。文档 30 行挂在 `csv_pool.py` 旁。 |
| **U-R17** | 1/2/3/4/5 的 `peak_gap_min=0`、`allow_add=False`。禁止默抄策略 6 的 15 分钟峰间隔。 |
| **U-R23** | 实施序：先引擎短接（None 止损、时钟、3 的第三钟）且 6/8 旧单测绿 → 再 `register` → 再改 `csv_strategy_names()` 元组。禁止在引擎能跑该书之前把它放进 `--strategy` choices。`register` 顺序锁成 `version1`…`version6`,`version8`。禁止 A–E 单 commit。 |
| **U-R26** | `buy_gate(code, px, day, daily_closes_ending_yesterday)`。`closes` 必须 `index < day`、与成交同一份 none 日线。长度不足 → fail-closed 不买（计 `skip_buy_gate`）。 |

### 2.2 策略 1 / 2

| ID | 锁 |
|----|----|
| **U-R4** | 策略 1：止损 2%；止盈 = 峰值相对成本的利润回撤 ≥ 50%。**前置**：`px >= cost` 且 `peak > cost`，否则不评（对齐化石 `ProfitStrategy.py:130-134` 与策略 6 `trail_hits`）。`drawdown = (peak-px)/(peak-cost)`。reason **必须** `profit_take:drawdown` 前缀（可接 `:50`）。禁止 `drawdown:50` 光杆前缀。**日线离场 = `pending_exit` 次日开**（与 6 同路径）。 |
| **U-R5** | 策略 2：止损 2%；回撤阈值按 `n_days`（引擎 `i - entry_idx`，买入日=0，T+1=1）：`{1:0.50,2:0.40,3:0.30,4:0.20,5:0.10}`，缺键用最大键。同样要求 `px >= cost` 且 `peak > cost`。reason `profit_take:drawdown`（可接 `:T+N`）。`n_days < 1` 不评止盈。**日线离场 = `pending_exit` 次日开**。 |
| **U-R22** | `_sell` 具名桶：`sell_profit_take`（`profit_take*`）、`sell_open_board`（`open_board*`）、`sell_force`（`force_sell*`）、`sell_ma`（`ma_signal*`）。四者 **不得** 进 `sell_pos_trail` / `sell_trail`。`summarize` 必须打印新桶。新书禁止写 `trail_t1`（避免 `:726` 误入 v6 格式化）。对照对象 = `ProfitStrategy.py`；只比前缀家族。`open_board` / `ma_signal:MA5` / `force_sell:time` 相对化石中文/空格串是 **新 token、同族不逐字**。策略 3 **不做** 整串化石对照。 |

### 2.3 策略 3（超出可选钩子）

| ID | 锁 |
|----|----|
| **U-R6** | 止损 4%；目标 +20%（`profit_take:target`）。顺序与 **ProfitStrategy** 对齐：**先止损，再保留**。**分钟**：每个交易日 09:30–09:40 重估——涨停 → `pos.reserved=True`；窗口内未涨停 → **清 reserved**，允许 20% 就卖。窗口后仍涨停 → 留。开板 = `reserved and not is_limit_up` → 立即卖（`open_board`，该分钟 close），**不受** `peak_gap` 挡。`reserved and is_limit_up` 时引擎 **跳过** `take_profit`（创业板/科创 +20% 板 = 目标，必须短路）。`reserved` 跨日 sticky，直到窗口清位或卖出。 |
| **U-R19** | **日线第三成交钟**（仅 3，且 **`n_days >= 1`**，插在 `:429` 止损之后）：`reason.startswith("open_board")` → 当日收盘 `_sell`。其余 `take_profit*` 仍 `pending_exit`。判定用 `hooks["reserve_limit_up"]` / `daily_same_bar_prefixes`，禁止 `if strategy==`。6/8 pending 状态机本身不改。 |
| **U-R20** | 日线 reserved = **开盘 vs 昨收涨停价**，≠ 分钟窗口。reserved 且收盘仍涨停 → 不卖 20%。reserved 且收盘开板 → 当日收盘卖；`hit_limit_down(close)` → **不成交**，改挂 `pending_exit="open_board"`，次日开盘走现有 pending（含开盘跌停再顺延）。HELP_LOCK 写三行近似。 |

### 2.4 策略 4

| ID | 锁 |
|----|----|
| **U-R7** | 无止损。`buy_gate`：14:55/收盘价 ≥ **截至昨收** SMA10。卖走 **`sell_gate`**（不是四参 `take_profit`）：现价 < **截至昨收** SMA5 → `ma_signal:MA5`。`apply_csv_strategy`：有 `sell_gate` 则 `take_profit` 可为恒 `None` 的占位。历史不足 10 根 → 不买（`skip_sma_warmup`，算 `skip_buy_gate` 子类）；已持无 SMA5 → **冻仓不卖**。禁止今日 K。禁止 `chip_indicator` / front / `StockDataReader`。均线唯一输入 = 引擎已持 none 日线 `index < day`。**日线离场 = `pending_exit` 次日开**。 |
| **U-R21** | **日线与分钟** `run()` 在 `--strategy version4` 时股票日线都预载 `--start` 之前 ≥10 个交易日（实现 11）。日历源 = **已加载 none 日线 index**（不是 `pandas_market_calendars`，也不是只减 `WARMUP_DAYS=10`）。实现：日历余量放大（≥22 自然日）+ 运行时数交易日，不足则该票 `skip_sma_warmup`。禁止用饿死的 warmup 充绿。与 Cerebro `SMA[0]` 含当棒 **刻意偏离**。信号价可以是当日 14:55/收盘；均线窗口右端是昨收。追买日的「昨收」含信号日收盘（HELP_LOCK 写明，不是 bug）。 |

### 2.5 策略 5（改写 v1 的日线强制卖）

| ID | 锁 |
|----|----|
| **U-R8** | 无止损。目标 +2%（`profit_take:target`）。`force_sell_policy=time_only`，`force_sell_time=14:50`。**分钟**：引擎时钟 `hm>=14:50 and n_days>=1` → `force_sell:time`；禁止把强制卖放进无 `hm` 的 `take_profit`（否则 T+1 09:30 就卖）。**日线：不把 15:00 当成已过 14:50，日线不做强制卖**；只评 +2% → `pending_exit` 次日开（与 6 同失真）。买入日 `n_days=0` 不得挂 pending、不得强制卖。v1 **不做** `days_and_time` / 涨停保留。 |
| **U-R18** | 14:50 是 `force_sell_hm` 时钟，不是四参 `take_profit`。分钟顺序：**止损 → `take_profit`（+2%）→ force**。同一根 14:50 若已 +2%，reason 用 `profit_take:target`。T+1 当天 14:50 可卖；T+1 09:31 不强制卖。force 必须在「开盘跌停 `continue`」**之后**；`hit_limit_down(px_close)` 则 defer、不成交。现有 6/8 `stop_loss:touch` 在跌停收盘仍成交是已知乐观失真，本轮不改。 |
| **U-R25** | 切片 B 日线完成定义只测 **+2% → 次日开**。分钟完成定义测 **14:50 强制卖**。禁止用「日线每天 force」假装覆盖 U-R8。 |

### 2.6 6 / 8 / 7 / 市场层 / 池

| ID | 锁 |
|----|----|
| **U-R9** | 策略 6/8：规则不改。`load_pool_days(start, end, pool_dir=None)` **保留为薄壳**，委托 `load_pool_day_map`；旧单测签名不变。`run()` / CLI 接 `--pool-dir`（默认 `stock_pool/`）。`SystemExit` 文案带实际目录，禁止写死 `stock_pool/`。 |
| **U-R10** | 策略 7：不进 BOOKS。只改 import：`as_datetime` / `as_date` / `round_fen` / `limit_pct`。**`_limit_prices` 留在 v7 本地**（float 乘后 `round_fen`）。CLI `--pool-dir` 必填不变。**空 CSV 仍进 map**。禁止 `pool_dir=None`。禁止 6/8 import `as_datetime` 建日历。策略 7 旧 plan 的 import allowlist 以本条为准。 |
| **U-R11** | `market_layer.py` 是 **叶子**：`utc_ms_range`、`limit_pct`（现表）、**Decimal** `limit_prices`（供 6/8）、`round_fen`、供 **7** 用的 `as_datetime` / `as_date`。禁止 import `ma_chip_edge` / 日线分钟引擎 / Cerebro / `StockDataReader` / `chip_indicator`。6/8 索引继续 pandas utc ms（日线 `normalize()`）。**刻意不统一** v7 与 6/8 的涨跌停价算术。 |
| **U-R12** | `limit_pct` **原样搬家**（`300/301/688=0.20`，否则 `0.10`）。`ma_chip_edge` **再导出**。本轮不改北交 30% / ST 5% / **689**。HELP_LOCK：不建模北交/ST/689；验收宇宙禁 BJ/ST/689；**不是 8%**。 |
| **U-R24** | `csv_pool.load_pool_day_map(pool_dir, start, end, *, key="ymd"|"date", empty_in_map=...)`：`pool_dir` **必填、无默认**。6/8 薄壳：`key="ymd"`，`empty_in_map=False`。7：`key="date", empty_in_map=True` 或本地适配器。6/8 无 CSV → `SystemExit`；7 空目录 → 合法 0 笔。 |

### 2.7 Cerebro / 文档 / 停牌（声明）

| ID | 锁 |
|----|----|
| **U-R13** | `backtest_main_full.py` 无 `--allow-cerebro-fossil` → 打印向量化入口后 **非 0 退出**。加上该旗标才跑旧 Rolling。chip / ma_chip CLI 暂不改。禁止新 `StrategyN`。**仅切片 E、单独 commit**。 |
| **U-R27** | 停牌 / 当日无 K：现行为 = 冻仓（不评卖、保留 pending）、名单 `skip_no_bar`、追买 `pop` 后 `chase_no_bar`（一次机会作废）、净值用 `pos.cost`。本轮 **不改** 6/8 这些分支；HELP_LOCK 写明。 |
| **U-R28** | README / SSOT / AGENTS 书单 **随 register 切片改，不得在切片 A 先改**。`test_csv_strategy_books` 的 names 元组跟当次 `register`，不等 E。切片 E 只补化石门 + 收口总表。化石门同步：`tests/test_backtest_profit_strategy.py` 及 README 里的 `backtest_main_full` 命令须加旗标或改道。 |
| **U-R29** | **`sell_gate(code, px, day, daily_closes_ending_yesterday) -> Optional[str]`**。6/8/1/2/3/5 为 None，引擎走 `take_profit`。仅 4 实现。禁止给 `take_profit` 加第 5 参（会炸 6/8 闭包）。 |
| **U-R30** | 主持裁实验复现：v7 float `_limit_prices` vs 日线 Decimal，399802 组中 **1073** 组跌停差 1 分（`prev=1.65, pct=0.10 → 1.48 vs 1.49`）。故 U-R10 不搬 `_limit_prices`。 |
| **U-R31** | CLI：`--stop-pct` 对 version4/5 **显式传入 → SystemExit**；1/2/3 允许覆盖各自默认止损；6/8 保持现语义。1–5 的 `run_kwargs` 不得走 `strategy6_kwargs_from_args`。 |
| **U-R32** | `Position.reserved` **只加在** `csv_daily_backtest.Position`（分钟已 import 同一份）。7 的 `Position` 不加。 |
| **U-R33** | `run()` / `simulate()` 新增 kwarg 只从 `hooks` 读（`buy_gate`/`sell_gate`/`force_sell_hm`/`reserve_limit_up`），缺省 no-op。`apply_csv_strategy` **不**对 `buy_gate`/`sell_gate` 硬 raise。 |

---

## 3. 代码落点

| 文件 | 动作 |
|------|------|
| `backtest/research/market_layer.py` | **新建**（叶子，见 U-R11） |
| `backtest/research/csv_pool.py` | 加 `load_pool_day_map`（U-R24）；空文件语义分叉 |
| `backtest/research/strategy1_rules.py` … `strategy5_rules.py` | **新建**纯函数 + HELP_LOCK |
| `backtest/research/csv_strategy_books.py` | 按 U-R23 **源码插入序** register（v1…v6,v8，不是追加）；`stop_pct` 允许 None；透传 U-R2 具名键；1–5 的 `run_kwargs` **不得**走 `strategy6_kwargs_from_args`；U-R31 |
| `backtest/research/csv_daily_backtest.py` | None 止损短接（算术前）；`buy_gate`/`sell_gate`；3 的当日收盘开板+跌停→pending；`--pool-dir`；`limit_pct`/`limit_prices` 改市场层 Decimal；`summarize` 容忍 None + 新桶；`Position.reserved` |
| `backtest/research/csv_minute_backtest.py` | None 止损短接；`force_sell_hm`；`reserve_step` + `scan_held_day` 可选 kwarg（返回 5 元组不变）；`buy_gate`/`sell_gate`；`--pool-dir`；version4 日线预载同 U-R21 |
| `backtest/research/csv_minute_backtest_v7.py` | 只改 `as_datetime`/`as_date`/`round_fen`/`limit_pct` 的 import；**不改** `_limit_prices` |
| `backtest/research/ma_chip_edge_backtest.py` | `limit_pct` 再导出 |
| `backtest/backtest_main_full.py` | 化石门（仅 E） |
| `docs/backtest/pool-csv-contract.md` | **新建**（写清 6/8 vs 7 空文件） |
| `docs/backtest/README.md` / `engine-positioning-ssot.md` | 书单随 register，见 U-R28 |
| `tests/test_market_layer.py` `test_strategy{1-5}_rules.py` `test_csv_strategy_books.py` | 扩 |

`Position.reserved` 只加在 `csv_daily_backtest.py`（U-R32）。7 的 `Position` **不加**。

---

## 4. 引擎钩子与时钟

```
buy_gate(code, px, day, daily_closes_ending_yesterday) -> bool   # 默认恒真
sell_gate(code, px, day, daily_closes_ending_yesterday) -> Optional[str]  # 仅 4
take_profit(px, cost, peak, n_days) -> Optional[str]  # 1/2/3/5/6/8；看不见 hm
force_sell_hm: Optional[int]   # 5=890；None=关闭
reserve_limit_up: bool         # 仅 3
daily_same_bar_prefixes = ("open_board",)
# 分钟顺序：止损 → take_profit/sell_gate → force
# 3: 调用方 reserve_step 后，reserved+涨停跳过 take_profit；开板不受 peak_gap
```

日线买入前（名单与追买）：`if not buy_gate: skip`。
日线卖：`sell_gate` 有值则用它，否则 `take_profit`；命中后除 `open_board*` 外一律 `pending_exit`。
分钟：14:55 买前同样过 `buy_gate`。

均线：`sma_asof(closes: list[float], n) -> Optional[float]`，closes **不含当日**。放 `strategy4_rules.py`。

---

## 5. 切片

| 切片 | 内容 | 完成定义 |
|------|------|----------|
| **A** | 市场层叶子（Decimal `limit_prices` + v7 不搬 `_limit_prices`）；6/8 `--pool-dir` + 薄壳；7 只改时间/`limit_pct`/`round_fen` import；`stop_pct is None` 短接；U-R22 四新桶 + summarize | 湖毫秒；6/8 与 v7 涨跌停价 **各自**回归；空 CSV 分叉；6/8/7 旧单测绿（含 `test_csv_*_v8.py`）；`stop_pct=None` 不炸、腰斩无 `stop_loss:*` |
| **B** | 策略 1/2 书 + register + names | 1：`px>=cost` 才回撤 50%，reason `profit_take:drawdown`，日线次日开；2：T+1 vs T+5 阈值不同；亏损收盘不进 `profit_take` 桶；6/8 仍绿 |
| **B′** | 策略 5 + `force_sell_hm` | 分钟：T+0 不卖、T+1 09:31 不强制、T+1 14:50 卖、14:50 且 +2% → `profit_take`、跌停 close 不成交；日线：+2% 次日开、**无**每日 force；`--stop-pct` 显式 → SystemExit |
| **C** | 策略 3 + `reserve_step` | 分钟：09:35 涨停不卖、09:41 开板卖、开板不受 peak_gap、创业板一字 20% 板不卖；日线：`n_days>=1`、开盘涨停+收盘涨停不卖 20%、开板当日卖、收盘跌停 → pending 次日开；6/8 pending 回归 |
| **D** | 策略 4 + `sell_gate` + 两引擎交易日预载 | 昨收 SMA10 以下不买；跌破昨收 SMA5 → pending 次日开；不足 10 交易日 `skip_sma_warmup`；追买也过 gate；断言前 10 根昨收齐 |
| **E** | Cerebro 化石门 + 文档收口 | 无旗标非 0；有旗标仍能进；`test_backtest_profit_strategy` / README 命令同步；书单 1–8；7 不在 choices |

禁止把 A–E 合成一个不可回滚的巨型 commit。允许同一 PR 多 commit。

---

## 6. 验收

```text
D:\anaconda3\envs\vanna312\python.exe -m pytest -q `
  tests/test_market_layer.py tests/test_csv_pool.py `
  tests/test_strategy1_rules.py tests/test_strategy2_rules.py `
  tests/test_strategy3_rules.py tests/test_strategy4_rules.py `
  tests/test_strategy5_rules.py tests/test_csv_strategy_books.py `
  tests/test_csv_daily_backtest.py tests/test_csv_daily_backtest_v8.py `
  tests/test_csv_minute_backtest.py tests/test_csv_minute_backtest_v8.py `
  tests/test_csv_minute_backtest_v7.py tests/test_strategy7_rules.py
```

全部切片完成后：`csv_strategy_names() == ("version1","version2","version3","version4","version5","version6","version8")`。
`--strategy version7` → 现有 `unsupported`。

不要求本机真名单长窗。禁止虚拟机跑策略 7 E。
禁止用 Cerebro 净值当 gate。

---

## 7. 风险 / 已知失真

- 1–5 向量化净值 **不会** 等于旧 Cerebro（成交时点不同）。
- 策略 3 日线近似 ≠ 分钟窗口 ≠ presets。HELP_LOCK 三行（U-R20）。
- 策略 5 日线无 14:50，强制卖只在分钟。HELP_LOCK 必须写。
- 策略 4 均线排除今日 K，比 Cerebro `SMA[0]` 更严。
- `limit_pct` 北交/ST 未建模（U-R12）。
- 停牌：冻仓、追买一次作废、净值标成本（U-R27）。
- `add_csv_strategy_arg` 的 `choices=` 随书变长；旧脚本写死 version6/8 仍合法。

---

## 8. 修订程序

改 U-R1–U-R33 须改本文。v1.2 已吸收 classic 🔴，不另开第二轮，除非实施中发现新的事实互斥。综合见 `merge-consensus.md`。

---

## 9. 对抗勘误（v1 → v1.1）

主持裁让步必须落笔。对抗草案不计独立票。

### 9.1 主笔让步

1. **U-R2「只加两只钩子就接完 3/5」作废。** 3 要独立保留扫描 + 日线第三钟；5 要引擎时钟。
2. **U-R3 必须先改引擎算术**（`csv_daily_backtest.py:430`、`csv_minute_backtest.py:413,433`），再 register 4/5。
3. **U-R4/U-R5 reason 改回 `profit_take:drawdown` 家族**（化石/Rolling/SSOT 对照货币）。
4. **U-R8 日线「15:00=已过 14:50」撤回。** 日线不做强制卖，只留 +2% pending。否则每个可卖收盘都 force，+2% 永不当选，且买入日挂 pending 会冲破 T+1。
5. **U-R7 卖点仍走卖槽，但禁止把它叙述成止盈公式。** 不新开引擎、不改 6/8 `Position`。
6. **SMA 预载按交易日 ≥10（实现 11），不靠 `WARMUP_DAYS=10` 日历。**
7. **`csv_pool` 统一函数不得带 `pool_dir=None` 默认 `stock_pool/`。** 7 空 CSV 仍进 map。
8. **6/8 不换用 v7 `_as_datetime` 建索引。** 市场层是叶子。
9. **`limit_pct` 本轮只搬家，不改档。** 北交/ST 写进「不建模」。
10. **实施序 U-R23**：先引擎、后 register、后 names 元组。文档书单不随切片 A 漂。
11. **1–5 `peak_gap_min=0`。** 追买过 `buy_gate`。
12. **开板收盘必须查跌停。** `reserved` 必须压过 20% 目标。

### 9.2 未让步

- 人裁：1–8 这轮都接到向量化（不是只做 6/8/7）。
- 不把 7 注册进 BOOKS；不拷 LEBS/MockQMT。
- 不改 `presets.py`。
- 不删除 Cerebro 代码；化石门留切片 E。
- 本轮不改 6/8 停牌追买 / 净值标成本（只声明）。
- 本轮不把北交改成 30%（避免 6/8/7 热路径 silently 变买/卖阈值）。

### 9.3 条目对照

| 对抗 ID | 动作 |
|---------|------|
| D-F1 / S-F1 / P-F1 | 吸收 → U-R3 引擎短接 |
| D-F2 / S-F2 / S-F10 / P-F1 | 吸收 → U-R8/U-R18/U-R25 时钟与日线不做 force |
| D-F3 / S-F3 / P-F2 | 吸收 → U-R6/U-R19/U-R20 |
| D-F4 / P-F3 | 吸收 → U-R21 交易日预载；U-R7 卖槽叙事 |
| D-F5 / P-F1 | 吸收 → U-R22 / U-R4 reason 前缀 |
| D-F6 / P-F7 | 吸收 → U-R23 / U-R28 |
| D-F7 / S-F9 / P-F4 / P-F9 | 吸收 → U-R24 / U-R10 |
| D-F8 | 吸收 → U-R25（改完成定义，不是改成天天 force） |
| D-F9 / U-R26 | 吸收 → 追买过 gate |
| S-F4 | 部分吸收：档位不改，声明不建模（U-R12） |
| S-F5 | 声明不改（U-R27） |
| S-F6 / S-F7 | 吸收 → U-R7/U-R21 none 同源、排除今日 |
| S-F8 | 确认不适用盈筹 |
| S-F9 / P-F5 / P-F6 | 吸收 → 市场层叶子；6/8 不换日历解析器 |
| P-F10 / S-F10 | 吸收 → U-R17 `peak_gap_min=0` |
| P-F8 | 吸收 → 化石仅 E |

### 9.4 classic fan-out（v1.1 → v1.2）

四家 rc=0。主持裁复现涨跌停实验：`compared 399802 mismatches 1073`。

| 票 | 原 ID | host |
|----|-------|------|
| 三家 | 策略 4 卖无数据通路 | **吸收** → U-R29 `sell_gate`；不给 `take_profit` 加第 5 参 |
| codex / kimi | U-R10「字节级不变」被证伪 | **吸收** → U-R10/U-R30：v7 保留本地 `_limit_prices` |
| codex | 1/2 缺 `px>=cost` | **吸收** → U-R4/U-R5 |
| codex | port 源未指定 | **吸收** → U-R14 = ProfitStrategy |
| auto | U-R1 跌停过度承诺 | **吸收** → U-R1 收窄为现 defer 范围 |
| auto | 1/2/4 日线离场未锁 | **吸收** → pending 次日开 |
| auto | 3/5 挂载面未契约化 | **吸收** → U-R2 具名键 |
| kimi / claude | 开板跌停 defer 次日语义 | **吸收** → pending `open_board` |
| claude | 14:50 跌停守卫 / 分钟预载 / 689 / `--stop-pct` / 桶名 | **吸收** → U-R18/U-R21/U-R12/U-R31/U-R22 |
| 多家 | Position 两份 / load_pool 薄壳 / 验收漏 v8 | **吸收** → U-R32/U-R9/§6 |

驳回 / 降级：

- 不把 6/8 分钟 trail 升格为全 reason 跌停禁卖（会改热路径）。
- 不把 v7 涨跌停改成 Decimal（接受 1 分差，留本地函数）。
- 不另开 classic 第二轮：🔴 都是契约补锁，不是架构互斥。
