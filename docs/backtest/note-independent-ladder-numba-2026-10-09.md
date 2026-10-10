# 独立持仓梯子：放弃跳 bar，改走 Numba 全扫描（2026-10-09）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-09（Asia/Shanghai） |
| 分支 | `feat/v6-50-53-parking-skim-index` |
| 配方 | `--strategy version6_53 --start 20251023 --end 20260909 --cash-total 27000000 --name-budget 10000 --rule-profile industry` |
| 分钟缓存 | `backtest_output/bar_cache/minute_none_20251013_20260909_afda45b21c12.parquet` |
| 性质 | 引擎扫描加速。规则书未改，未开新版本号 |

本文记录 held_scan 下一刀的过程、数字和未锁事项。成交核、档位、除权仍见 [engine-ashare-correctness.md](engine-ashare-correctness.md)。分钟成交假设见 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。

---

## 1. 要解决的问题

6.53 industry 默认埋点里，持仓扫描占叶子时间约 75%。独立持仓（`per_name` / `position_id=代码@信号日`）走 `HeldMinuteCursor` + `advance_independent_exit`，每根 bar 的 open/close 都在 Python 里跑，再加减仓 / 峰值回撤 / 加仓止损侧钩。

仓库里已有 `_scan_held_day_numba_trail`。它只服务无回调的 `trail_hits`，且 `scan_held_day` 在 `take_profit is not None` 时拒绝卸载。6.x 的 `take_profit_reason` 是回调，独立持仓也不走 `scan_held_day`，所以那条核帮不上 6.53。

---

## 2. 过程

### 2.1 静默 bar 跳过（已放弃）

先做启发式 `skip_quiet_independent_bar`：用 `_independent_bar_needed` 判断本根会不会离场，安静根只回写峰值 / 回撤闩。

- 单元测试能对上（含 300017 14.85 止损、000422 16.47 回撤、002556 / 301265 / 002291）。
- 接到分钟 industry 宿主后成交漂移。同会话短窗有时能对齐，全窗不能锁。
- `PYTHONHASHSEED=0` 也锁不住 skip 与 skipoff 的 NAV。skipoff 自身两次全窗也曾从 +66.78% 跳到 +63.87%。

人裁：别再跳。跳来跳去总有漂移。

宿主早晨与 `post_group` 已不再调用跳过。`skip_quiet_independent_bar` / `drive_independent_exit_bars` 已从 `minute_cash_order.py` 删除。关核用 `OSKH_INDEPENDENT_NUMBA=0`（默认开）。

### 2.2 回调怎么进 Numba

Numba `nopython` 核调不了任意 Python 回调（闭包、`Optional[str]`、lot 对象、Decimal 成交）。行业做法是把策略收成数据，核只扫数字条件：

1. 带宽 / 让利 / 止损比例当 `float64` 参数进核。
2. 核返回第一根必须交给 Python 的 bar，以及该 bar 之前的峰值。
3. 账本、T+1、跌停顺延、一手/零股、费用留在原来的 Python 成交核。
4. 热循环里不用 `objmode`。

6.53 的 `take_profit_reason` 看起来是回调，身子是纯公式：`exit_line = peak - cost * (0.05 + 0.03 * band)`。减仓、峰值回撤闩锁/清除/离场、加仓止损同样是数字谓词。这些可以编进核；`sell_gate` / `exit_plan` / 自定义 `fill_config` 不行，失败则整段走 Python。

### 2.3 落地路径

`_scan_independent_ladder_first`（`csv_minute_backtest.py`）按切片扫：

- T+0（`can_sell` 假或 `n_days < 1`）：不写峰值、不离场。
- 可卖：更新峰值 → 跳空止损 → 收盘止损 → 梯子（含 `peak_gap_min`）→ 减仓档 → 峰值回撤闩/清/出 → 加仓 lot 止损。
- 返回 `(idx, peak, peak_hm)`。`idx < 0` 表示本切片没有 Python 动作，峰值是终值。

宿主：

- 早晨：`hm_lo=0`，`hm_hi=BUY_HM`（若 `allows_price_add` 拆上午/下午）。
- `post_group`：`hm_lo=BUY_HM+1`，`side_hooks=None`（下午本来就不跑减仓/回撤/加仓止损）。
- `python_from >= 0`：从该 bar 起走原来的 `advance_independent_exit` + 侧钩。
- `python_from < 0`：只计 `held_numba_slices`，不再逐根 Python。
- 前缀 bar 计入 `held_numba_prefix_bars`（核已扫过、Python 未评）。

`write_profile_sim` 补了 `mkdir`。首次 Numba 全窗跑完后写 profile 时目录还不存在，当时只保住了主机打印数字。

---

## 3. 结果

对照同一配方、分钟缓存命中、`PYTHONHASHSEED=0`。跳过两列只作过程记录，**不是锁定比分**。

| 路径 | 墙钟 | 模拟 | held_scan | post_group | Python 评估 bar | 成交 | 全资金收益 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 不跳 hash0（`skipoff_h0`） | 380.6s | 329.9s | 256.9s | 12.5s | 4,516,255 | 9493 | +65.72% |
| 启发式跳过 hash0（`skipon_h0`，已弃） | 260.8s | 211.1s | 140.4s | 11.5s | 712,359 | 9428 | +65.11% |
| Numba 前缀 hash0（本次） | 145.9s | 100.2s | 46.4s | 0.4s | 548,468 | 9497 | +65.25% |

本次 Numba 额外计数：`held_numba_slices=33299`，前缀 bar 281354（当时计数名仍是 `held_quiet_bars`），`held_codes=20113`。期末净值 44,616,440.23 / 27,000,000。叶子占比上 held_scan 从约 76% 降到约 43%；下一刀时间在日切片（约 24s）和名单买入（约 22s）。

相对上次不跳 hash0：持仓扫描约 5.5×，模拟约 3.3×，墙钟约 2.6×。规则未改。

单元测试：`tests/test_independent_numba_ladder.py`。对照包括 T+0 不写峰值、300017 / 002291 止损、000422 / 002556 / 301265 回撤、减仓，以及 Numba 前缀对完整 Python 的成交/峰值/闩锁对齐。`OSKH_INDEPENDENT_NUMBA=0` 强制整段 Python。

适用范围：`st.stats` 带 `ladder_band_width` / `ladder_give_base` / `ladder_give_step` 的独立持仓书（6.x 梯子族）。旧 trail 核仍只服务无回调 lot。非独立持仓、`sell_gate`、自定义成交配置不走这条核。

---

### 2.4 宿主确定性（本刀）

同一进程两次开核仍 DIFF：成交键集合不同，`held_eval_bars` 也对不上。根因不是梯子核。

1. **现金竞争跟插入序。** `st.positions` 是先买先到；全卖再买会把该码插到队尾。同日加仓 / 指数减半 / 抽离谁先拿到现金，就会分叉。现已收口：`held_codes(st)` 按代码排序；`s8_open_groups` 按 `position_id` 排序；指数买回按 `position_id`；抽离可卖 lot 按 `(code, entry_idx, lot_id)`。只锁遍历，不改 6.53 卖点。
2. **停泊标签用了会回收的 `id(pos)`。** `register_parking_lot` 把整数地址放进 set。lot 卖掉被回收后，CPython 会把同一地址给新的策略 `Position`。`index_cut` / 抽离把误标的策略仓当停泊跳过，组内 `held` 变了，减半股数就漂。现改为按对象身份登记（列表 + `is`）。`Position` 是 dataclass，不能放进 set。

短窗 20251023–20260206、`PYTHONHASHSEED=0`、分钟缓存命中、同一进程连开三次核：净值 25,983,138.16，成交 5572，`index_cut` 716000 股 / 518 次，成交键与权益曲线三次对齐。排序单独上时计数已经对齐，但 20260203 的 `index_cut` lot 仍三分叉；换掉 `id(pos)` 后才 MATCH。

全窗 20251023–20260909 同一配方、`python,numba`：净值 44,594,778.35（+65.17%），成交 9662，成交键与权益对齐。产物 `backtest_output/csv_minute_v6_53_20251023_20260909_industry_hostdet_h0/`。关核墙钟 334.4s / 模拟 282.5s / held_scan 216.2s；开核墙钟 150.9s / 模拟 101.6s / held_scan 45.8s。不是锁定比分（宿主锁会改历史成交；6.53 仍 PENDING）。

对照：`tests/test_independent_held_order.py`。关核：`OSKH_INDEPENDENT_NUMBA=0`。转储：`OSKH_DUMP_CODE` / `OSKH_DUMP_DAY` / `OSKH_DUMP_PATH`。

---

### 2.5 引擎装载栈（本刀）

宿主锁住之后，全窗开核大头变成装载：日切片 26.3s、分钟缓存解码 26.8s、日线湖 13.2s。这刀不改 6.53 卖点，只给日线/分钟引擎共用：

1. **`bonus_locks` 改对象身份。** 与停泊标签同一类 CPython 地址回收。`ExDivEconomics.peek_locks` / `locks_for` / `pop_locks` 用 `is`，不再 `id(pos)`。6.53 默认仍 `exdiv_economics=None`。
2. **分钟 `day_spans` sidecar。** 写在 `{minute_cache_stem}.spans.json`，指纹是 `[n, first_ymd, last_ymd]`。`run()` 把 `status["day_spans"]` 交给 `simulate()`，命中后日切片接近 0。
3. **日线文件缓存。** `daily_{div}_{start}_{end}_{hash12}.parquet`，身份与分钟同款浅湖戳。`load_daily_bars` 默认 `use_cache=False`（测试湖不写仓库 cache）；`load_daily_ohlc` 打开。
4. **进程内 `bar_store`。** `OSKH_BAR_MEM` 默认开。同一进程第二次 `run()` 分钟/日线/spans 不再解码。帧只读，文件缓存仍是跨进程真源。未做 mmap/Redis。

关：`OSKH_BAR_MEM=0`。对照：`tests/test_bar_store.py`、`tests/test_independent_held_order.py`。

短窗 20251023–20260206 同进程两次开核：成交键/净值 MATCH（25,983,138.16 / 5572）。第一次分钟文件命中 18.2s、日线文件命中 4.5s；第二次 `cache=mem` / `daily_cache=mem`，分钟 0.1s、日线 0.3s。日切片两次都是 0.0s（sidecar + `run()` 预注入）。墙钟 77.1s → 53.5s，省下的是解码，不是 held_scan。

---

### 2.6 名单报价预计算、同日身份、跌停计数（本刀）

装载复用之后，全窗叶子还剩 `pool_buy` ~22s，以及两处同日 `id(pos)`。本刀不动账本、不把 `execute_buy` 编进 Numba、不锁 6.53 golden。

1. **`DayBuyQuotes`。** 按日缓存买价、昨收、涨跌停带。现金循环仍走 `execute_buy` 和一手取整。日线 / 默认分钟 / 时序买入共用同一张表；突破钩子走 `as_quote_fn()`。分钟有 `day_spans` 时用 numpy 切片取 14:55，不再对池里每只股票做 DataFrame `.loc`。
2. **同日身份收尾。** 8.3 确认峰值改挂 `pos._session_confirm_peak`。分钟排队键与 pending 诊断改 `lot_identity(pos)`（对象自带 token），不再用会回收的 `id(pos)`。
3. **`defer_sell_limit_down`。** Numba 不再在开盘跌停时 `continue` 整根 bar。缺口止损仍只在 `not blocked_open` 时返回。收盘谓词（减仓 / 台阶止损 / 峰值回撤）仍交给 Python 计数。成交本来就对齐；这只修埋点。
4. **6.53 不录 golden。** 仍在 `PENDING_BOOK_NAMES`。行业默认 off-byte 未授权。不要用宿主锁之后的 +65.17% 覆盖 `_opt` / `_prof`。

对照：`tests/test_day_buy_quotes.py`、`tests/test_independent_held_order.py`、`tests/test_independent_numba_ladder.py`。

---

### 2.7 全窗重测（DayBuyQuotes 之后）

同一配方、`PYTHONHASHSEED=0`、默认分钟（不开 `--fix-minute-cash-order`）、产品 `run()`（ST 闸开）。产物 `backtest_output/csv_minute_v6_53_20251023_20260909_industry_quotes_h0/`。

对照上一刀宿主锁全窗（`industry_hostdet_h0`，模拟 101.6s，当时还没有 ST 闸、日切片 sidecar 未打进该次全窗）：

| 项 | hostdet | 本次 quotes | 说明 |
|---|---|---|---|
| 模拟 | 101.6s | 66.4s | 叶子合计下降 |
| held_scan | 45.8s (42%) | 43.4s (59%) | 仍是模拟大头 |
| pool_buy | 21.6s (20%) | 9.7s (13%) | 报价预计算削掉约 12s |
| day_spans | 26.3s | 0.0s | sidecar 命中 |
| 墙钟 | 150.9s | 199.9s | 本次日线 cache miss、分钟文件解码 91.2s；不是模拟变慢 |
| 净值 | 44,594,778.35 / +65.17% | 44,341,528.00 / +64.23% | `skip_st=5`；不是报价缓存改成交 |
| 成交 | 9662 | 9621 | 买入 4479→4459，加仓 1280→1268 |
| defer_sell_limit_down | 1433 | 4147 | 开盘跌停漏计已收口；关核旧数 4382 |

下一刀如果还要动引擎：只剩持仓扫描的 Python 评估段（`held_eval_bars=542018`）。名单买入的现金循环还在 Python，但 9.7s 不值得再把 `execute_buy` 编进 Numba。时序买入的 DataFrame `pool_quote` 仍未动——默认 6.53 不走那条路。

6.53 仍 PENDING。这次净值更不是锁定比分（ST 闸改了成交）。

---

### 2.8 开盘跌停侧钩顺延（本刀）

`held_eval_bars=542018` 的根因：核一旦在开盘跌停 bar 上看到收盘谓词，就把该 bar 交给 Python，Python 再把当天剩下的 bar 全部评完。本刀让核自己跨过「只会顺延、不成交」的开盘跌停 bar，只把第一根能成交的 bar 交出去。

核里现在这样走：

1. **侧钩**（减仓 / 加仓止损 / 峰值回撤卖出）在开盘跌停时计 `defer_sell_limit_down`，继续扫。
2. **峰值回撤闩**（首次触线 / 收复）在核里写回 `peak_dd_start`，不再为了闩本身交棒。
3. **`cursor.advance` 的止损 / 梯子**在开盘跌停时不算、不闩。Python 的 `_close` 在 `blocked_bar` 时根本不会跑，不能把这次当成 `first_exit_attempted`。第一次全窗把回撤记成已消费，下午切片又当新离场，净值漂到 44,642,343.84 / +65.34%。收回这条之后对齐。
4. 前缀回写峰值、顺延次数、回撤闩；已消费的 `advance` 写回 `cursor.first_exit_attempted`。

返回值是 `(idx, peak, peak_hm, defer, dd_start, advance_latched)`。账本、`execute_buy`、跳 bar 都没动。

对照：`tests/test_independent_numba_ladder.py`（开盘跌停减仓不交棒、跌停后再减仓、开盘跌停不消费梯子、回撤闩对齐）。

同一配方、`PYTHONHASHSEED=0`、缓存命中、产品 `run()`（ST 闸开）。产物 `backtest_output/csv_minute_v6_53_20251023_20260909_industry_defercont2_h0/`。

| 项 | quotes_h0 | 本次 defercont2 | 说明 |
|---|---|---|---|
| 模拟 | 66.4s | 59.7s | 缓存命中后的叶子 |
| held_scan | 43.4s (59%) | 38.7s (61%) | 少走一段只会顺延的 Python |
| pool_buy | 9.7s | 9.6s | 未再动 |
| held_eval_bars | 542018 | 488862 | 少评约 5.3 万根 |
| 墙钟 | 199.9s | 106.8s | 上次日线/分钟 cache miss；这次 hit |
| 净值 | 44,341,528.00 / +64.23% | 44,341,528.00 / +64.23% | 成交对齐 |
| 成交 | 9621 | 9621 | 买入 4459，加仓 1268 |
| defer_sell_limit_down | 4147 | 4147 | 与 quotes 对齐 |
| skip_st | 5 | 5 | |

6.53 仍 PENDING。本刀不录 golden。

---

## 4. 遗留问题

1. **模拟大头还是 held_scan。** 全窗开核 38.7s / 61%。第一根真正能成交的 bar 之后，当天剩下的 Python 评估还在（减仓后继续找下一档）。不要对回调 `objmode`，不要把账本编进 Numba。
2. **真回调仍走 Python。** `sell_gate`、`exit_plan`、`force_sell_hm`、`close_clear`、pending、自定义 `fill_config`、`session_volume` 失败则 `python_from=0`。
3. **6.53 仍在 `PENDING_BOOK_NAMES`。** 行业默认 off-byte 未授权。经济除权默认仍关。本刀不录 golden。ST 闸会改历史成交，预期如此。
4. **HELP_LOCK / CLI 未动。** 分钟 `main()` 字节冻结。埋点仍走 `run()` + 默认 `OSKH_PROFILE_SIM`。
5. **时序买入报价未动。** `minute_cash_order.pool_quote` 仍是 DataFrame。只有开了 `--fix-minute-cash-order` 才值得改。
6. **装载仍吃墙钟。** 同进程第二次 `run()` 走 `bar_store`；跨进程仍是文件缓存。未做 mmap/Redis。开盘跌停顺延的 pending 事件少记（只记计数，不写每根 `record_limit`）。

未授权：开新策略版本、改 6.53 卖点、把跳过重新接回宿主、把账本编进 Numba、用本次 NAV 覆盖 `_opt` / `_prof` 比分、把 6.53 锁成 golden、打开默认经济除权。
