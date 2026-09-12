<!-- agent=cursor:auto cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.10-fd3934a\node.exe C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.10-fd3934a\index.js --model auto -p --output-format text --trust -f --mode ask --workspace E:\PycharmProjects\MyQuant-backtrader <prompt> -->
# 评审：`plan-unify-csv-strategies-1-8-2026-09-12.md` v1.1

并行目录里 claude / kimi / codex / cursor-auto 目前只有 prompt 壳，无已完成意见可交叉；下文独立取证。本 plan **无** timeout/budget/并发安全阀新设计，跳过该类实验。

---

## 🔴 必须修

### R1. U-R1「跌停禁卖」过度承诺，会 silently 改 6/8
U-R1 把「跌停禁卖 / 开盘跌停 defer」写成 1/2/3/5/6/8 同构事实；现分钟引擎**只**对 `stop_loss*` 做开盘跌停 defer，`trail` / 未来的 `profit_take*` / `force_sell*` / `open_board` / `ma_signal*` 仍会成交：

```586:591:backtest/research/csv_minute_backtest.py
                    if hit_limit_down(float(o[idx]), limit_down) and reason.startswith(
                        "stop_loss"
                    ):
                        st.stats["defer_sell_limit_down"] += 1
                        continue
                    _sell(st, code, pos, px, day, reason)
```

日线对 `pending_exit` / 止损有 defer（`csv_daily_backtest.py:422-426`），与「全 reason 跌停禁卖」仍不等价。  
U-R9 / U-R27 又锁「6/8 本轮不改」。若实现者按 U-R1 字面给所有卖因加跌停闸 → 改热路径。  
**修法**：U-R1 改成「沿用现 defer 范围：日线 pending/止损；分钟仅 `stop_loss*`；3 的日线 `open_board` 另按 U-R20」；或显式升格为本轮要改 6/8（与 U-R27 二选一）。

### R2. 1 / 2 / 4 日线离场时点未锁，与「共用 simulate 热路径」打架
日线热路径里，凡 `take_profit` 有值一律进 `pending_exit`（次日开），无当日收盘卖：

```448:452:backtest/research/csv_daily_backtest.py
                    pos.peak = max(pos.peak, float(row["high"]))
                    close = float(row["close"])
                    reason = take_profit(close, pos.cost, pos.peak, n_days)
                    if reason:
                        pos.pending_exit = reason
```

U-R8 / U-R19 精心锁了 5（+2%→pending）与 3（`open_board`→当日收盘）；U-R4 / U-R5 / U-R7 **未写** 1/2/4。化石 Cerebro 是同 bar `should_sell` 即卖。实现者极易给 1/2/4 开「当日收盘 `_sell`」旁路，拆掉 U-R2 热路径。  
**修法**：显式锁——1/2/4 日线 `take_profit` / `ma_signal` **一律** `pending_exit` 次日开；仅 3 的 `open_board*` 走当日收盘；并写进各书 HELP_LOCK。

### R3. 引擎如何识别 3/5 特殊钟未契约化（会复制 `if strategy==`）
U-R2 / U-R6 / U-R8 / U-R18 要求保留扫描、第三钟、14:50 时钟，但未规定挂载面：

- `buy_gate`：U-R26 有签名，可从 `apply()` 透传（`apply_csv_strategy` 已 `dict(book.apply(...))`，可行）。
- `force_hm` / `enable_reserve` / 日线 `exit_mode`：**无** hooks 键名。

`CsvStrategyBook` 目前只有 `allow_add` / `peak_gap_min` / `apply`（`csv_strategy_books.py:19-28`）。实现者会在 `simulate` 里硬编码 `version3`/`version5`，和「书驱动」叙事冲突，也难测默认 no-op。  
**修法**：锁 hooks，例如 `buy_gate`、`force_sell_hm: Optional[int]`、`reserve_limit_up: bool`、`daily_same_bar_prefixes: tuple[str,...]=("open_board",)`；缺省对 6/8 为 no-op。

---

## 🟡 应修

### Y1. U-R19「不得改 6/8 pending」缺 discriminator
应写死：`reason.startswith("open_board")` → 当日收盘 `_sell` + 跌停 defer；其余 `take_profit*` → 仍 `pending_exit`。避免改 pending 状态机本身。

### Y2. `_sell` 统计桶与 U-R22：现 else 全进 `sell_pos_trail`
```682:688:backtest/research/csv_daily_backtest.py
    if reason.startswith("stop_loss"):
        st.stats["sell_stop"] += 1
    elif reason.startswith("trail"):
        st.stats["sell_trail"] += 1
    else:
        st.stats["sell_pos_trail"] += 1
```
U-R22 方向对，但须同时规定：`profit_take*` 独立桶；`open_board*` / `force_sell*` / `ma_signal*` **不得**进 `sell_pos_trail`（也勿进 `sell_trail`）。切片 A「U-R22 统计桶」完成定义应带这四类合成用例。

### Y3. 策略 3 向量化 reason=`open_board` ≠ 化石中文串
化石开板原因是「开盘10分钟后开板，卖出…」（`ProfitStrategy.py:304-308`），不以 `open_board` 开头。与 U-R22「1/2 只比前缀家族」不冲突，但若有人写 3 的化石对照会误红。HELP_LOCK / 完成定义写明：3 **不**做整串化石对照，只验行为。

### Y4. `run()` 仍无 `--pool-dir`；`warmup_start` 仍是日历日
- `load_pool_days` **已有** `pool_dir`（`csv_daily_backtest.py:288-292`），但 `run()` / CLI **未传**（`:562`、`:885+`）；U-R9 正确，实施时须改 `SystemExit` 文案里写死的 `stock_pool/`。
- `warmup_start` = 日历减 10 天（`:216-217`）。U-R21 交易日预载 11 正确，须写清：全局抬预载 vs 仅 version4；禁止只改书不改 `run()`。

### Y5. `stop_pct is None` 短接点必须在算术前（行号勘误仍成立）
§9.1 引用 `csv_daily_backtest.py:430`、`csv_minute_backtest.py:413,433` **属实**（`1.0 - stop_pct`）。分钟若把 `None` 传入 `scan_held_day` 仍炸。锁：**短接在调用方**，或 `scan_held_day` 入口 `stop_pct is None` 跳过止损块；禁止只改 daily。

### Y6. CLI `--stop-pct` 与 4/5 的 `None`
`add_strategy6_ratio_args` 全局挂 `--stop-pct`（`csv_strategy_books.py:106-110`）。1–5 若误走 `strategy6_kwargs_from_args`（`None→0.06`）会毁 U-R3。plan 已禁；再锁：4/5 的 `run_kwargs` **忽略或拒绝** `--stop-pct`；1/2/3 是否允许覆盖也写一句。

---

## 🟢 可选

- G1. 化石 `ma_signal` / `force_sell time`（空格）vs 向量化 `ma_signal:MA5` / `force_sell:time`——统一「前缀家族」对照表到 HELP_LOCK。  
- G2. `csv_pool.load_pool_day_map` 落地后，旧 `load_pool_days(..., pool_dir=None)` 标 deprecated，避免双 API。  
- G3. `peak_gap_min=0` 时 `peak_gap_blocks` 恒假（`:265-267`）；3「开板不受 peak_gap」对 1–5 冗余，可留作防御。

---

## ✅ 做对的地方

- 引擎定位与禁改：不进 LEBS/MockQMT、不改 `presets.py`、7 不进 BOOKS、Cerebro 仅 E——对齐 `engine-positioning-ssot.md`。  
- 复权：湖路径已是 `dividend_type=none`（`csv_daily_backtest.py:339-340`）；禁筹码 front / `cyqk` 进 1–8 书——正确。  
- T+1：`n_days = i - entry_idx`，卖侧 `n_days >= 1`（日线 `:420-429`；分钟 `:418-420,:572`）；U-R8 买入日不挂 pending / 不 force——正确。  
- U-R3 / U-R23：先 None 止损短接再 register——必要（现算术无守卫）。  
- U-R8 / U-R18 / U-R25：撤回日线「15:00=已过 14:50」——与 B′ 自洽。  
- U-R12 / U-R27：`limit_pct` 只搬家、北交/ST 不建模；停牌追买 / 净值标成本只声明——务实。  
- U-R24：7 空 CSV 仍进 map（`csv_minute_backtest_v7.py:452-464` + `if pools`）护指数日历——正确。  
- U-R21：对齐 7 的 11 根交易日预载（`v7.py:419-422`），不靠日历 `WARMUP_DAYS=10`。  
- U-R17：`peak_gap_min=0` 避免 1–5 被策略 6 的 15 分钟峰间隔误伤。

---

## 盲区核对（摘要）

| 盲区 | 结论 |
|------|------|
| T+1 / `n_days=0` | 引擎已挡卖；plan 对 5 额外锁 pending/force |
| 日线止盈时点 | 6 热路径=pending；**1/2/4 未锁 → R2** |
| 未来 bar | 均线 `index < day`、成交用当日价——OK |
| 复权 none | 已然；禁 chip front——OK |
| cyqk | 声明不适用——OK |
| 涨跌停 | 涨停禁买可卖 OK；**跌停叙述过度 → R1**；北交/ST 声明 OK |
| 包边界 | research CLI / 7 独立 / Cerebro 化石——OK |

---

**总评**：v1.1 对抗回填方向对，6/8/7/5/池/复权/T+1 主线可实施；但 U-R1 跌停范围、1/2/4 日线离场时点、3/5 钩子挂载面三处仍会误导实现。  
**是否可进实现**：**否**——清掉 R1–R3（并最好收紧 Y1–Y2）后再进切片 A。
