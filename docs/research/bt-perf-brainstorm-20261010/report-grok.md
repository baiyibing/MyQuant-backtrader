DONE

# MyQuant-backtrader 回测性能头脑风暴 · Grok 独立意见

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-10 |
| 作者 | Grok（只读；未改代码、未开 PR） |
| 仓库 | `/workspace/MyQuant-backtrader` |
| 已 `git fetch` | 是 |
| 当前 HEAD | `7ca63b5` `perf/v653-numba-resume`（detached） |
| master tip | `96927c5` Merge `#450` |
| PR | [#456](https://github.com/baiyibing/MyQuant-backtrader/pull/456) · `MERGEABLE` · 相对 master `+439/−109` · 4 文件 |
| 配方锚 | `--strategy version6_53 --start 20251023 --end 20260909 --cash-total 27000000 --name-budget 10000 --rule-profile industry` |
| 过程日记 | `docs/backtest/note-independent-ladder-numba-2026-10-09.md` §2.8 |
| 交接摘要 | `docs/backtest/note-v653-host-perf-summary-2026-10-10.md` |

本意见只谈扫描/装载加速。6.53 仍在 `PENDING_BOOK_NAMES`（`scripts/research/generate_off_byte_baseline.py` / `tests/test_off_byte_baseline.py`），净值 `44,341,528.00 / +64.23% / 9621` 成交是宿主观测，不是锁定比分。

---

## 1. 现状：热路径瓶颈假设

数字来自过程日记与 #456 说明，都是单机全窗，**不是锁定 SLA**。比较请用 `profile_sim.json` 分相（`backtest/research/csv_sim_profile.py::SimPhaseClock`），冷缓存墙钟和热缓存墙钟不要直接比。

### 1.1 时间分层（6.53 全窗，#456 之后）

| 层 | 热缓存（`industry_resume_h0`） | 冷缓存（`industry_baseline_h0`） | 符号 / 文件 |
|---|---:|---:|---|
| 墙钟 | 36.1s | 786.8s | `csv_minute_backtest.run` → `ashare_bars.load_minute_ohlc` |
| 分钟装载 | 14.9s（文件命中） | 725.7s（写缓存） | `ashare_bars.read_minute_cache` / `write_minute_cache` |
| 模拟 | 16.6s | 46.1s | `csv_minute_backtest.simulate` |
| `held_scan` | 8.8s（49%） | 30.4s（62%） | `simulate` 日环 + `_drive_independent_window` |
| `pool_buy` | 3.4s | 6.7s | `csv_simulate_loop.run_pool_buys_day` + `DayBuyQuotes` |
| `post_group` | 0.9s | 0.4s | 14:55 后独立仓扫描 |
| Python 评估 bar | 16,270 | 542,018 | `held_eval_bars` |
| Numba 再覆盖 bar | 525,763 | 0 | `held_numba_resume_bars` |

缓存文件：`backtest_output/bar_cache/minute_none_20251013_20260909_61efabfabb98.parquet`（约 1.67 GB，125,781,274 行）。同进程第二次 `run()` 走 `bar_store` 内存，分钟解码约 0.1s。

### 1.2 分钟回测编排

入口：`backtest/research/csv_minute_backtest.py::simulate`。6.53 默认路径是「先持仓扫描、再 14:55 池买、再 `post_group`」，`allows_price_add` 把上午/下午拆开（`split_group_scan`）。时序路径 `run_chronological_day`（`minute_cash_order.py`）要 `--fix-minute-cash-order` 或 TopK 非 close，默认 6.53 不走。

每个持仓日仍做一次 Python 装配，再决定进核还是逐 bar：

- `_slice_day`（`csv_minute_backtest.py`）用 `day_spans` iloc 切 DataFrame。
- `open/high/low/close/hm` 每天 `to_numpy`。
- `_previous_rows`：`df.loc[df.index < day]` 全日线帧。
- `mapped_prev_close` / `k_for`（`exdiv_map.py`）+ `book_limit_prices`（`csv_common.py`）。
- 独立仓构造 `HeldMinuteCursor`（`minute_held_scan_core.py`），卖出走 `advance_independent_exit`（`minute_cash_order.py`）进 `csv_ledger._sell`。

假设：**#456 之后，held_scan 的大头已经从「安静 bar 的 Python 解释」变成「真动作 bar 的账本 + 每次再进核的 Python 包装 + 每码每日的 DataFrame 切片」。** 16,270 根动作 bar 必须留在 Python；525,763 根安静 bar 已经在 Numba 里。再抠模拟，优先削包装，其次削每码每日装配。

### 1.3 Numba 梯子核

核：`csv_minute_backtest.py::_scan_independent_ladder_first`（`@_njit(cache=True)`）。包装：`independent_ladder_first_bar` → `_independent_numba_prefix` → `_drive_independent_window`。

合同（`note-independent-ladder-numba-2026-10-09.md` §2.2）：

1. 带宽 / 让利 / 止损比例以 `float64` 进核。
2. 核只返回第一根必须交给 Python 的 bar，以及该 bar **之前**的峰值。
3. 账本、T+1、跌停顺延、一手/零股、费用留在 `advance_independent_exit` / `execute_buy` / `_sell`。
4. 热循环不用 `objmode`。

失败则整段 Python：`_independent_numba_blocked`（`OSKH_INDEPENDENT_NUMBA=0`、`sell_gate` / `exit_plan` / `force_sell_hm` / `close_clear` / pending / `side_pending` / 自定义 `FillConfig` / `session_volume`）。旧 trail 核 `_scan_held_day_numba_trail` 仍只服务无回调 lot；6.x `take_profit_reason` 是回调外形、公式身子，所以走梯子核。

启发式跳 bar（`skip_quiet_independent_bar`）已删：全窗成交漂移。人裁不再跳。

每次进核，`independent_ladder_first_bar` 对 `cursor.o/h/c/hm` 做 `np.asarray(..., dtype=...)`。宿主里这些列已经是 `day_m[...].to_numpy` 的 `float64`/`int64`，`asarray` 多半是视图。真正贵的是：

- `_independent_numba_prefix` 每次重扫 `st.positions` 拼 `step_costs`、加权 `scale_anchor`。
- nopython 调用开销 ×（动作 bar 数 + 安静切片数）。
- `_drive_independent_window.count_quiet` 用 Python `for` 扫 hm 只为埋点。

`post_group` 从 0.4s 升到 0.9s：下午动作更密，再进核的包装盖过少掉的 Python bar。这是 #456 自己写明的回归。

### 1.4 `bar_store` / 湖缓存

`backtest/research/bar_store.py`：进程内 `_MEM`，`OSKH_BAR_MEM` 默认开。帧只读。跨进程真源仍是 parquet 文件缓存。

分钟：`ashare_bars.load_minute_ohlc` → 身份 `minute_cache_identity`（G2，`docs/backtest/g2-minute-cache-identity-2026-09-28.md`）→ `read_minute_cache`。读路径已经是 `pq.ParquetFile.read_row_group`；14.9s 里含随后的 `table.to_pandas()` 和 `_frame_from_cache_group` 的 `DatetimeIndex`。模拟热路径用的是当天 numpy 列，DatetimeIndex 只服务切片/标记。

日切片 sidecar：`{minute_cache_stem}.spans.json`，指纹 `[n, first_ymd, last_ymd]`。`run()` 把 `status["day_spans"]` 注入 `simulate()`，命中后 `day_spans` 分相接近 0。

日线：`csv_daily_loader.load_daily_bars`，文件缓存由 `ashare_bars.load_daily_ohlc(use_cache=True)` 打开；测试湖默认 `use_cache=False`。

假设：**新进程墙钟的第一大头是分钟文件解码（热 14.9s），大于模拟（16.6s）。** mmap 压缩块省不掉解码；未压缩 OHLC+hm+ymd 约 5.2 GB，还要改日循环不再 `to_numpy` 拷一份。Mode B mmap 包没有 high/low。同进程第二次已经走内存，不必为墙钟再做 Redis。

### 1.5 ST

`backtest/research/st_status.py`：`bind_st_gate` 在产品 `run()` 打开（`csv_minute_backtest.simulate(..., st_gate=True)` 由 `run()` 传入）。库 `simulate()` 默认关，避免单测读 Wind 表。表：`vendor_wind_st_status/st_daily.parquet`，`lru_cache` 按路径。买侧闸在 `csv_ledger.execute_buy` → `st_blocks_buy`（集合查找）。

6.53 quotes 全窗：`skip_st=5`，净值从宿主锁的 `44,594,778.35` 落到 `44,341,528.00`。这是规则生效，不是性能回归。热路径上 ST 已经是 O(1) 成员判断，**不是模拟瓶颈**。缺文件是 waiver，不是空表假装没数据。

### 1.6 除权 / exdiv

- **参考价图（E-R6）**：`exdiv_map.load_exdiv_ratios` / `k_for` / `mapped_prev_close`。`dec3a0b` 已按列下推，分相 `exdiv`。热循环里 `k_for` 是 `dict[code][ymd]`。
- **经济除权**：`ashare_exdiv_economics.ExDivEconomics`。6.53 默认 `exdiv_economics=None`，`apply_exdiv_economics` 立刻返回。`bonus_locks` 已改对象身份（`is`），与停泊标签同一类 CPython 地址回收问题。
- **默认经济除权仍关。** 打开会改成交与 NAV，未授权。

除权图装载已从「未计时的 adj_factor 全表扫描」收口。默认 6.53 上，exdiv **不是** held_scan 叶子。

### 1.7 买侧报价

`csv_simulate_loop.DayBuyQuotes`（`79de799`）：按日缓存买价、昨收、涨跌停带。现金循环仍走 `execute_buy`。有 `day_spans` 时 14:55 走 `_buy_px_from_arrays`（numpy），不再对池里每只股票 DataFrame `.loc`。`quotes.prefetch(planned)` 在 `run_pool_buys_day` 里已调用。

热缓存下 `pool_buy` 3.4s，主要是现金/手数/涨跌停门的 Python 循环。把 `execute_buy` 编进 Numba 的 ROI 不够（交接摘要 §4 已否）。

时序买入的 `minute_cash_order.pool_quote` 仍是 DataFrame；默认 6.53 不走。

### 1.8 已提交的性能刀（master，供对照）

| 提交 | 作用 |
|---|---|
| `89d917e` | 默认埋点，`OSKH_PROFILE_SIM=0` 关掉 |
| `dec3a0b` | 除权图按列下推 |
| `c8d3021` | 6.x 独立梯子进 Numba（一次前缀） |
| `7c1f71f` | 停泊/红股锁对象身份；`day_spans` sidecar；日线文件缓存；`bar_store` |
| `79de799` | `DayBuyQuotes`；买侧 ST；开盘跌停仍让收盘谓词计数 |

#456 是在这一串之后，把「第一根动作之后的安静尾巴」从 Python 拉回 Numba。

---

## 2. 评价 PR #456

### 2.1 改了什么

单提交 `7ca63b5`。核心：

- `_scan_independent_ladder_first` 增加 `start` / `bar_start`，可从切片中部接着扫。
- 新 `_drive_independent_window`：每根 Python 动作 bar 结算后，用更新过的峰值 / `scale_steps` / 加仓成本再进同一核。
- `OSKH_INDEPENDENT_RESUME=0` 恢复一次前缀 + Python 尾巴。
- 整段留在 Python：核关掉、pending / `side_pending`、`cursor.first_exit_attempted`（峰值冻结后禁止把后面的高点写进峰值）。
- 步数 lot > 32 返回 `-2`，从 `bar_start` 走 Python。
- 埋点：`held_numba_resume_bars`。
- 测试：`tests/test_independent_numba_ladder.py` 补两档减仓之间的安静段、关恢复、跌停顺延后峰值冻结。
- CLI / `HELP_LOCK` 未动。

### 2.2 收益

算法证据硬：`held_eval_bars` 542,018 → 16,270，安静段 525,763 根改由核覆盖。6.53 减仓档之间确实有大段安静 bar，这个切口和书匹配。

模拟分相：46.1s → 16.6s（约 2.8×），`held_scan` 30.4s → 8.8s。产物声明 `trades.csv` / `daily_equity.csv` / `pending_sells.csv` 与基线逐字节相同，净值 `44,341,528.00`、成交 9621。

有回退开关，默认开核、默认恢复，失败路径 fail-closed 回 Python。这比再发明跳 bar 启发式干净。

### 2.3 风险

1. **峰值冻结是正确性铰链。** `HeldMinuteCursor.first_exit_attempted` 在跌停顺延后必须挡住再进核。测试 `test_resume_freezes_peak_after_deferred_exit` 覆盖了合成路径；全窗字节相同是宿主证据。以后改 `advance_independent_exit` 若漏设该旗，会把冻结后的高点写进 peak。
2. **测量混了冷/热缓存。** 基线 `industry_baseline_h0` 是冷缓存墙钟 786.8s；恢复跑是文件命中 36.1s。模拟分相理论上不含解码，但首次触碰 1.67 GB 帧会有缺页/CPU 缓存效应。`pool_buy` 6.7s → 3.4s 作者已归因缓存热度。16.6s **不要当锁定比分**。合入门应用同一热缓存、同一进程或连着两次 `run()`，`OSKH_INDEPENDENT_RESUME=0` vs `1`。
3. **`post_group` 变慢（0.4s → 0.9s）。** 下午窗口动作密，nopython 往返盖过少掉的 Python bar。净值不变，墙钟有小回归。下一刀包装变轻后应回到 ≤0.4s。
4. **包装每次重造参数。** `step_costs` 扫 lot、`scale_anchor` 加权、闭包 `exec_bar`/`count_quiet` 每个窗口重建。动作越密越亏。这是作者自己点名的下一刀。
5. **覆盖面。** 只服务 `st.stats` 带 `ladder_band_width` / `ladder_give_base` / `ladder_give_step` 的独立持仓书（6.x 梯子族）。v8 独立仓、v9、v7、自定义 `FillConfig`、`sell_gate` 仍整段 Python。
6. **CI 不跑全窗字节对照。** PR test plan 里 CI 仍空。单测是合成 OHLC。合入后全窗对照仍是宿主责任。
7. **6.53 PENDING。** 本刀不录 golden，也不能用这次 NAV 覆盖 `_opt` / `_prof`。

### 2.4 是否值得合

**值得合。** 理由：卖点未改、有字节级宿主对照、有单测、有环境回退、切口对准真实安静段、模拟侧约 2.8×。风险集中在测量口径和包装开销，可用合入后同一热缓存 A/B 锁住，不必挡合。

合入条件（建议，仍由人裁）：

- 同一文件缓存、`PYTHONHASHSEED=0`，`OSKH_INDEPENDENT_RESUME=0` 与默认恢复各跑一窗，三份 CSV 逐字节相同。
- `profile_sim.json`：`held_scan` 下降；`post_group` 记录在案，允许暂时高于 0.4s。
- 单测 `tests/test_independent_numba_ladder.py` + `test_independent_held_order.py` + `test_day_buy_quotes.py` 绿。
- 不把 6.53 推进 `BOOK_NAMES`，不改 `HELP_LOCK`，不改默认经济除权。

### 2.5 测量建议

```text
set PYTHONHASHSEED=0
# 先保证分钟/日线文件缓存命中，再比算法
set OSKH_INDEPENDENT_RESUME=0
... --out-dir ..._resume_off_h0
set OSKH_INDEPENDENT_RESUME=1
... --out-dir ..._resume_on_h0
```

比：`trades.csv` / `daily_equity.csv` / `pending_sells.csv`；`profile_sim.json` 的 `held_scan` / `post_group` / `pool_buy` / `held_eval_bars` / `held_numba_resume_bars`。墙钟只在 `status["cache"]=="hit"`（或同进程第二次 `cache=mem`）时并列。关核对照用 `OSKH_INDEPENDENT_NUMBA=0`，预期模拟回到一次前缀之前的量级（约 30s+ held_scan），成交仍应字节相同。

合成微基准：把 `test_resume_matches_python_across_quiet_scale_gaps` 的 38 根 bar 扩成「2 次减仓 + 200 根安静」，对 `_drive_independent_window` 计 `held_eval_bars` 与墙钟，不读湖。

---

## 3. 下一刀（5–10 条，可落地）

原则：模拟刀和装载刀分开提交。验收同一配方成交键 + `daily_equity.csv` 不变。6.53 继续 PENDING。

### P0-1 合 #456 后同一热缓存 A/B（测，几乎不改代码）

- **改哪里：** 宿主复跑脚本 / 过程日记补一行。可选：`write_profile_sim` 把 `cache` / `OSKH_INDEPENDENT_RESUME` 写入 JSON。
- **预期收益：** 把 16.6s 从「混了冷热」收成可引用的模拟比分；发现 `post_group` 是否稳定多 0.5s。
- **风险：** 低。
- **改结果字节：** 否。
- **怎么测：** §2.5。`held_numba_resume_bars>0` 当且仅当恢复开。

### P0-2 减轻每次再进核的 Python 包装

交接摘要 §5 的模拟下一刀。

- **改哪里：** `independent_ladder_first_bar`、`_independent_numba_prefix`、`_drive_independent_window`（均在 `csv_minute_backtest.py`）。窗口开始时把 `cursor.o/h/c/hm` 钉成 typed ndarray 一次；`step_costs` / `scale_anchor` / `scale_steps` 只在 `exec_bar` 之后重算；`_ladder_numba_params` / 环境旗在窗口入口读一次。
- **预期收益：** `held_scan` 从 8.8s 再削一截；目标把 `post_group` 拉回 ≤0.4s。量级估计 10–30% 模拟（约 1–4s），取决于 nopython 往返占比。
- **风险：** 缓存的 `step_costs` 若在减仓后漏刷新，加仓止损会用旧成本。必须在 `scale_out_exits` / `step_stop_exits` / `_sell` 之后失效。
- **改结果字节：** 否（目标）。任何 DIFF 都是 bug。
- **怎么测：** 合成 `test_resume_matches_python_across_quiet_scale_gaps` + 全窗 `RESUME=0` vs `1` 字节相同；`profile_sim.json` 的 `post_group`、`held_scan`。

### P1-3 把 `count_quiet` 移出成交热路径

- **改哪里：** `_drive_independent_window.count_quiet`。埋点关（`OSKH_PROFILE_SIM=0`）时直接不算；开埋点时用 `hm` 的 numpy 窗口计数（`(hm>=lo)&(hm<=hi)` 的 `sum` 或已排序 hm 的 `searchsorted`）。
- **预期收益：** 525,763 次 Python `int(hm[i])` 循环消失。可能 0.3–1.0s，主要改善 `held_scan` 计数噪音。
- **风险：** 计数与真实跳过 bar 对不齐只影响 profile，仍应用合成窗口钉住 `resumed`/`prefix` 与 `in_window` 一致。
- **改结果字节：** 否。
- **怎么测：** `OSKH_PROFILE_SIM=0` 全窗字节相同；开埋点时 `held_numba_resume_bars` 与现网同量级。

### P1-4 分钟缓存：Arrow 列 → numpy，少做 `to_pandas` + `DatetimeIndex`

交接摘要 §5 的墙钟下一刀。

- **改哪里：** `ashare_bars.read_minute_cache` / `_frame_from_cache_group`。`read_row_group` 后对 `open/high/low/close/hm/ymd` 取 `column.to_numpy()`，按 symbol 分组。DatetimeIndex 只在仍需要 `.index` 的标记/日线对齐处惰性建。
- **预期收益：** 热装载 14.9s 的一部分（可能 3–8s）。parquet 仍是跨进程真源。同进程第二次继续 `bar_store`。
- **风险：** G2 身份 / schema 必须保持；`ymd`/`hm` dtypes 与 `_slice_day`、`build_day_spans` 对齐。书帧契约「DatetimeIndex + ymd/hm」若有外部调用方依赖 `.index`，要保留兼容视图。
- **改结果字节：** 否（OHLC 数值相同）。
- **怎么测：** `tests/test_minute_cache_identity.py`、`tests/test_bar_store.py`；热缓存两次 `run()` 的成交字节；装载分相（需在 `run()` 里把读缓存时间打进 status，现有 `cache=hit` 打印不够细）。

### P1-5 按码预切 numpy 日窗，simulate 不再每天 `to_numpy`

- **改哪里：** `bar_store` 或 `simulate` 初始化：对每个 code 持有 `o/h/l/c/hm` 全窗 ndarray + 已有 `day_spans`。日环用 `lo:hi` 视图交给 `HeldMinuteCursor`。`_previous_rows` 改成日线 close 的 numpy 前缀，避免 `df.loc[df.index < day]`。
- **预期收益：** 每持仓日 4 次 `to_numpy` + DataFrame iloc 视图开销。`held_codes` 量级约 2 万次/全窗，估计 0.5–2s，属于 held_scan 里「真动作之外」的装配。
- **风险：** 视图别名——核或 Python 若 in-place 改数组会污染后续日。保持只读。日线 index 与 calendar 对齐要有单测。
- **改结果字节：** 否。
- **怎么测：** 现有 `test_simulate_uses_day_spans_same_as_loc` 扩成 numpy span；全窗字节。

### P1-6 下午密动作窗口自适应：短尾巴留 Python

- **改哪里：** `_drive_independent_window`。若本次核返回的 `python_from == start_idx`（当前根就是动作），连续 N 根（例如 2–4）直接 `exec_bar`，再进核。目标专治 `post_group` 0.9s。
- **预期收益：** 密动作下午少一半 nopython 往返；稀疏上午仍恢复。`post_group` 回到 0.4s 附近。
- **风险：** N 选错只影响速度。实现必须在 pending / `first_exit_attempted` 出现时立刻切 Python 尾巴。
- **改结果字节：** 否。
- **怎么测：** 合成「每隔 1 根就减仓」与「200 根安静 + 2 次减仓」两条；全窗 `RESUME=0` 字节相同。

### P2-7 持仓日涨跌停 / 昨收按码缓存

- **改哪里：** `simulate` 持仓环。`book_limit_prices` + `mapped_prev_close` 对同码同日只算一次，多仓复用 `limits`（代码已按码切 `day_m`，limits 已在仓循环外——核对此）。真正能收的是 `exit_positions` 多仓时 cursor 重复字段、以及 `apply_exdiv_economics` 在 `exdiv_economics is None` 时的属性查找（已廉价）。更有价值的是把 `t1_sellable(calendar[pos.entry_idx].date(), day.date())` 做成 entry_idx→bool 表。
- **预期收益：** 小（可能 <0.5s）。在 P0-2 / P1-5 之后再测。
- **风险：** T+1 表若用错 calendar 会改可卖日。
- **改结果字节：** 否。
- **怎么测：** `tests/test_independent_held_order.py` 的 T+1 用例 + 全窗。

### P2-8 时序路径的 `pool_quote` numpy 化

- **改哪里：** `minute_cash_order.py` 里仍走 DataFrame 的 `pool_quote`。仅当 `--fix-minute-cash-order` 或 TopK 非 close。
- **预期收益：** 默认 6.53 为 0。X-02 / TopK open 网格才会看见。
- **风险：** 14:55 回退窗 `[14:30,14:55]` 与 `_buy_px_from_arrays` 必须同口径。
- **改结果字节：** 否（目标）。
- **怎么测：** 现有 X-02 / TopK exec 单测 + 一条短窗宿主。

### P2-9 多仓同日核批处理（研究原型，默认关）

- **改哪里：** 新函数，把同日、同 `hm_lo/hm_hi`、无 pending 的独立仓堆成 jagged 或 padded 数组，一次 nopython 扫完，返回每仓 first-bar。仍按原 `held_codes(st)` 排序把动作交回 Python，**现金顺序不变**。
- **预期收益：** 进一步摊销 nopython 启动。有现金竞争时收益有上限（动作仍串行）。
- **风险：** 高。排序/峰值写回一旦错，同日加仓与指数减半会分叉（§2.4 宿主锁的前车）。必须默认关，环境旗打开。
- **改结果字节：** 目标否；任一 DIFF 即废案。
- **怎么测：** 先合成 100 仓同日；再短窗三次同进程对齐（净值/成交键/`index_cut` 股数）。

### 明确后置 / 本轮不做

| 方向 | 理由 |
|---|---|
| GPU / 4090 | 剩下 16,270 根是有现金顺序的 Python 成交；安静 bar 已在 CPU Numba。见 `docs/backtest/perf-4090-context-brief-2026-09-16.md` |
| 现有 parquet mmap | 压缩块仍要解码；Mode B mmap 包无 high/low |
| `execute_buy` 进 Numba | `pool_buy` 热缓存 3.4s，账本/一手/ST/费用全在 Python |
| 安静 bar 启发式跳过 | `c8d3021` 已删，全窗漂移 |
| 默认打开经济除权 | 改成交，未授权 |
| 把 6.53 锁成 golden | `PENDING_BOOK_NAMES` |

P0-2 与 P1-4 不要写进同一个 PR。

---

## 4. 绝不动

正确性、行业规则、决策价。加速只能改「谁先找到那根 bar」，不能改「找到之后怎么成交」。

### 4.1 成交核与决策价

权威：`docs/backtest/engine-ashare-correctness.md`、`docs/backtest/minute-fill-policy-ssot.md`、`docs/backtest/ssot/backtest-rule-principles-ssot.md`。

- 默认分钟：池买 T 日 **14:55 close**（缺根才 `[14:30,14:55]` 最后 close）；止损默认 **close 判、close 成**；跳空止损 **open 穿、open 成**。峰值可用 high，不等于 H/L 触价。
- `FillConfig` 非默认（`bar_low` / `next_bar_open` / `fill_at=line`）Numba **拒绝**，整段 Python。禁止前视组合（按本根 high 成交、收盘判定却按本根 open 成交）。
- 涨跌停价：`market_layer.limit_prices` Decimal HALF_UP；`defer_sell_limit_down` / `skip_buy_at_limit` 语义。开盘跌停时缺口止损可跳过，收盘谓词仍计数（`79de799` 已收口）。
- T+1：`ashare_session.t1_sellable`；独立仓整体退出 + `|t1_deferred`（`docs/backtest/s8-independent-positions-2026-09-26.md`）。
- 一手/零股、费用感知 sizing、行业档 `rule_profile=industry`：改结果必须新 opt-in baseline，旧 baseline 永不覆盖。
- 研究热路径只记佣金（`ashare_fees`），禁止在 ledger 再加印花造成双重计入。

### 4.2 独立持仓梯子语义

- `position_id=代码@信号日`；退出用持仓加权成本；加仓不重置 peak。
- T+0：`can_sell` 假或 `n_days < 1` 时核 **不写峰值、不离场**（`_scan_independent_ladder_first` 的 `allowed`）。
- `first_exit_attempted` 之后峰值冻结。再进核若更新冻结后的 high，trail 线会漂。
- 现金竞争遍历序：`held_codes(st)` 按代码；`s8_open_groups` / 指数买回按 `position_id`；抽离按 `(code, entry_idx, lot_id)`。只锁遍历。停泊/红股锁继续对象身份（`is`），禁止回到 `id(pos)`。

### 4.3 数据域与身份

- 分钟成交域默认 `dividend_type=none`；日线信号 front 与分钟 raw 禁止静默双重调整。
- G2 分钟缓存身份：`minute_cache_identity` 缺认证视为不可复用。
- 湖路径走 resolver，禁止写死盘符、禁止缺失返回空表。
- ST：产品 `run()` 买侧闸开；库调用默认关。PIT 名称平铺合同保持；ST 闸改历史成交是预期（`skip_st`）。

### 4.4 产品边界与冻结面

- 本仓向量化；LEBS / MockQMT 在 1.3。禁止复活 Cerebro / `python -m backtest.lebs`。
- `HELP_LOCK` / 分钟 `main()` 字节冻结。埋点走 `run()` + `OSKH_PROFILE_SIM`，改 CLI 帮助即破锁。
- 6.53 留在 `PENDING_BOOK_NAMES`。未人裁前：不开新策略版本、不改 6.53 卖点、不用本次 NAV 覆盖 `_opt` / `_prof`、不默认打开经济除权。
- 热路径 import fence：`tests/test_ashare_simulate_import_fence.py`，禁止扩成 research 全目录扫描。
- 账本 / `execute_buy` 不进 Numba；核不用 `objmode` 调 Python 回调。

---

## 5. 结论

当前 6.53 分钟全窗的结构已经清楚：

1. **新进程墙钟** ≈ 分钟文件解码（热 ~15s）+ 模拟（#456 后 ~17s）。
2. **模拟** ≈ 真动作账本（`held_eval_bars=16270`）+ 再进核包装 + 池买现金循环。
3. **ST / 默认 exdiv** 已从叶子时间里消失；ST 改的是成交集合，exdiv 经济路径默认关。

#456 把一次前缀改成「动作后再进核」，切口正确，宿主字节相同，**建议合**。合入后第一件事是同一热缓存 `RESUME=0/1` 把模拟比分锁干净，紧接着 P0-2 把包装变轻，把 `post_group` 的 0.5s 回归吃回来。装载走 Arrow→numpy 另开一刀。

跳 bar、GPU、mmap、账本进核、默认经济除权、6.53 golden，这几条继续关着。
