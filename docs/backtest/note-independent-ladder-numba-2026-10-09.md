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

宿主早晨与 `post_group` 已不再调用 `skip_quiet_independent_bar`。`minute_cash_order` 里仍留着跳过辅助和 `drive_independent_exit_bars`，只给单元测试用；`OSKH_SKIP_QUIET_INDEPENDENT` 默认仍是开，但宿主读不到它。

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
- 前缀 bar 计入 `held_quiet_bars`（含义变成「核已扫过、Python 未评」，不再是启发式跳过）。

`write_profile_sim` 补了 `mkdir`。首次 Numba 全窗跑完后写 profile 时目录还不存在，当时只保住了主机打印数字。

---

## 3. 结果

对照同一配方、分钟缓存命中、`PYTHONHASHSEED=0`。跳过两列只作过程记录，**不是锁定比分**。

| 路径 | 墙钟 | 模拟 | held_scan | post_group | Python 评估 bar | 成交 | 全资金收益 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 不跳 hash0（`skipoff_h0`） | 380.6s | 329.9s | 256.9s | 12.5s | 4,516,255 | 9493 | +65.72% |
| 启发式跳过 hash0（`skipon_h0`，已弃） | 260.8s | 211.1s | 140.4s | 11.5s | 712,359 | 9428 | +65.11% |
| Numba 前缀 hash0（本次） | 145.9s | 100.2s | 46.4s | 0.4s | 548,468 | 9497 | +65.25% |

本次 Numba 额外计数：`held_numba_slices=33299`，`held_quiet_bars=281354`，`held_codes=20113`。期末净值 44,616,440.23 / 27,000,000。叶子占比上 held_scan 从约 76% 降到约 43%；下一刀时间在日切片（约 24s）和名单买入（约 22s）。

相对上次不跳 hash0：持仓扫描约 5.5×，模拟约 3.3×，墙钟约 2.6×。规则未改。

单元测试：`tests/test_independent_numba_ladder.py` + `tests/test_independent_held_skip.py`，19 passed。对照包括 T+0 不写峰值、300017 止损、000422 回撤、减仓动作，以及 Numba 前缀对完整 Python 的成交/峰值/闩锁对齐。

适用范围：`st.stats` 带 `ladder_band_width` / `ladder_give_base` / `ladder_give_step` 的独立持仓书（6.x 梯子族）。旧 trail 核仍只服务无回调 lot。非独立持仓、`sell_gate`、自定义成交配置不走这条核。

---

## 4. 遗留问题

1. **全窗宿主成交未锁。** 本次 +65.25% / 9497 笔，对不上上次不跳 hash0 的 +65.72% / 9493。跌停顺延计数也差一截（1203 vs 4151）。不跳路径自己也不稳，不能把任一 NAV 写成 golden。原因未拆清：字典顺序、缓存、并行读湖、还是核与 Python 谓词在极限价上的差。
2. **首次 Numba 跑没有 `trades.csv` / `daily_equity.csv`。** 只有主机打印和补写的 `summary.txt`。要比成交必须再跑一遍落盘。
3. **跳过代码还在。** `skip_quiet_independent_bar` / `_independent_bar_needed` / `drive_independent_exit_bars` 仍在 `minute_cash_order.py`，宿主不用。删掉要另批，并改/删 `tests/test_independent_held_skip.py`。
4. **真回调仍走 Python。** `sell_gate`、`exit_plan`、`force_sell_hm`、`close_clear`、pending、自定义 `fill_config`、`session_volume` 失败则 `python_from=0`。不要对它们 `objmode`。
5. **6.53 仍在 `PENDING_BOOK_NAMES`。** 行业默认 off-byte 未授权。本刀不录 golden。
6. **`held_quiet_bars` 语义变了。** 旧义是启发式跳过；现义是 Numba 前缀未评 Python 的 bar。比历史 skip 跑的这个计数没有意义。
7. **HELP_LOCK / CLI 未动。** 分钟 `main()` 字节冻结。埋点仍走 `run()` + 默认 `OSKH_PROFILE_SIM`。
8. **held_scan 之后。** 日切片和名单买入变成大头。共享分钟文件缓存还在；日线湖仍按码扫。未做 mmap/Redis。

未授权：开新策略版本、改 6.53 卖点、把跳过重新接回宿主、把账本编进 Numba、用本次 NAV 覆盖 `_opt` / `_prof` 比分。
