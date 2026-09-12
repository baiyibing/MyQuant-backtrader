<!-- agent=cursor:kimi-k3-high cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.10-fd3934a\node.exe C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.10-fd3934a\index.js --model kimi-k3-high -p --output-format text --trust -f --mode ask --workspace E:\PycharmProjects\MyQuant-backtrader <prompt> -->
其他评审员（claude / codex / cursor-auto）的产出文件目前只有 prompt 头或占位 stub，无已完成意见可交叉核对，本轮独立完成。取证与实验完毕，以下为评审意见。

---

# 评审：plan-unify-csv-strategies-1-8 v1.1（cursor-kimi-k3-high）

## 🔴 必须修

**R1｜U-R10「行为字节级不变」被实验证伪：市场层 `_limit_prices` 算术未指定，两头必有一伤。**
v7 用 float 乘法 + `round_fen`：

```217:219:backtest/research/csv_minute_backtest_v7.py
def _limit_prices(symbol: str, previous_close: float) -> tuple[float, float]:
    pct = limit_pct(symbol)
    return round_fen(previous_close * (1 + pct)), round_fen(previous_close * (1 - pct))
```

6/8 日线引擎用 Decimal 算术（`csv_daily_backtest.py:277-285`，`Decimal(str(prev))*(1±Decimal(str(pct)))` quantize HALF_UP）。**实验**（脚本 `backtest_output/_review_limit_prices_exp.py`，pid=3648，进程正常退出；完整原始输出要点）：

```text
scanned 400000 (prev, pct) pairs; mismatches=1073
  prev=1.65 pct=0.1: v7=(1.82, 1.48) daily=(1.82, 1.49)
  prev=4.35 pct=0.1: v7=(4.79, 3.91) daily=(4.79, 3.92)
  prev=14.45 pct=0.1: v7=(15.9, 13.0) daily=(15.9, 13.01) raw_float=15.895000000000001
3-decimal probe mismatches=13
```

即 0.27% 的两位小数昨收上**跌停价差 1 分**（float `1.65*0.9=1.48499…` → 1.48；Decimal 精确 1.485 → HALF_UP 1.49；抽样前 20 例全部落在跌停侧）。后果：市场层若采 Decimal 版 → v7 改 import 后跌停 defer 边界变，违反 U-R10；若采 v7 float 版 → 6/8 跌停价变，违反「6/8 规则不改」且可能打破切片 A「6/8 旧单测绿」。且按交易所「昨收×(1±档) 四舍五入到分」口径，**Decimal 版才是对的**（float 版把 `x.x85` 错舍低 1 分）。修法：市场层锁定 Decimal 版，v7 侧二选一并写进 plan——(a) v7 接受 1 分差异，HELP_LOCK + 测试基线显式登记；(b) v7 保留本地 float 版不进市场层（则 U-R10 的 `_limit_prices` 从搬家清单剔除）。

**R2｜策略 4 的 `ma_signal` 卖装不进 plan 自锁的 4 参 `take_profit`，缺 sell 侧上下文通道。**
plan §4 / U-R2 锁死 `take_profit(px, cost, peak, n_days)`，§0 称 4 的 MA5 卖「槽名兼容 `take_profit`」。但 U-R7 的卖点「现价 < **截至昨收** SMA5」需要 code + day + 日线 closes 三样上下文，而书的 `apply` 调用点没有任何通道传入：

```385:392:backtest/research/csv_daily_backtest.py
    hooks = apply_csv_strategy(
        strategy,
        stop_pct=stop_pct,
        take_profit=take_profit,
        record_params=record_params,
        profit_base=profit_base,
        tiers=tier_default and tiers or tiers,
```

（分钟引擎 `csv_minute_backtest.py:520-528` 同构。）闭包在 simulate 开始前就绑定，拿不到 per-(code, day) 的 SMA5。实现者到此必卡或各自发明旁路。修法：加与 `buy_gate` 对称的 `sell_gate(code, px, day, daily_closes_ending_yesterday) -> Optional[str]`（U-R26 已有同形契约，扩展成本极低），或在 U-R2 明确引擎注入上下文的机制。注意「已持无 SMA5 → 冻仓不卖」（U-R7）也要走这条通道表达。

## 🟡 应修

**R3｜U-R9 vs U-R24 张力：6/8 到底调哪个池函数。** U-R9 说「`load_pool_days` 已有 `pool_dir` 形参，本轮只接线」（属实，`csv_daily_backtest.py:288-291`，但默认回落 `stock_pool/`）；U-R24 又要 6/8 走新的 `load_pool_day_map(pool_dir, …)`（必填无默认）。旧函数去留未写。建议：统一函数为唯一入口，`load_pool_days` 删除或降级为薄包装并写明。

**R4｜策略 3 需要的 `limit_up` 通道未点明。** 日线卖循环目前只算 `limit_down`（`csv_daily_backtest.py:416-417`）；分钟 `scan_held_day` 只收 `limit_down`（`csv_minute_backtest.py:406`）。U-R20 日线 reserved（开盘 vs 昨收涨停价）与 U-R6 分钟 `is_limit_up` 都需要 limit_up 传入。U-R2 允许扩签名，但 plan §3 改动清单应显式列出，否则易漏。

**R5｜U-R20 defer 语义不完整。** 「收盘开板但 `hit_limit_down(close)` → 不成交、defer」——defer 到哪、什么 reason、次日走哪条路径未写。建议明确：defer = 置 `pending_exit="open_board"`，次日开盘走现有 pending 路径（含开盘跌停再顺延，`csv_daily_backtest.py:421-426`）。

**R6｜U-R22 只改 `_sell` 计数，`summarize` 没跟上。** `csv_daily_backtest.py:747` 仍只打印 `sell_stop/sell_trail/sell_pos_trail` 三桶；新书的 `profit_take:target` / `ma_signal:MA5` / `force_sell:time` / `open_board` 在 summary 不可见，切片完成定义的 reason 断言只能翻 trades.csv。切片 A 完成定义应补「summarize 打印新桶」。

**R7｜策略 3 reserved 生命周期需写清。** `reserved` 是跨日持久的 Position 字段，U-R6「窗口内未涨停 → 清 reserved」隐含跨日 sticky。需写明：每交易日 09:30–09:40 窗口重估（涨停置位 / 未涨停清位）；「开板立即卖」的开板定义（当日曾封板且当前分钟非涨停？）与卖价（该分钟 close）。另：plan §3「`Position` 日线/分钟各加 `reserved`」措辞有误——两引擎共用同一个 `Position`（`csv_daily_backtest.py:122`，分钟经 `execute_buy` 复用），加一次即可。

**R8｜U-R13 化石门影响面未列清单。** `backtest_main_full.py` 仍被 `README.md`、`docs/backtest/README.md`、`tests/test_backtest_profit_strategy.py` 及多份历史文档引用。切片 E 无旗标非 0 退出会打破现存测试/文档命令，plan 应列出需同步加旗标或改道的调用点（至少该测试文件）。

## 🟢 可选

- **R9** U-R26 fail-closed 计 `skip_buy_gate` vs U-R21 计 `skip_sma_warmup`：同一失败两个桶名，建议明确子类关系或二选一。
- **R10** 策略 5 同一分钟同时满足 +2% 与 14:50 时 reason 优先级未定；建议把「stop → take_profit → force_time」顺序写进 U-R18。
- **R11** U-R21 替代机制未写：`warmup_start` 只减 10 日历日（`csv_daily_backtest.py:216-217`）≈6-8 交易日 < 11。建议写明「日历余量放大（如 20 天）+ 运行时校验 ≥10 交易日，不足计 `skip_sma_warmup`」。

## ✅ 做对的地方（保留）

- **T+1 / 隔日成交核对通过**：买入日 `n_days=0` 不可卖（daily `:429`，minute `:419-420`）；日线止盈 `pending_exit` 次日开（`:421-426`, `:451-452`）；U-R8 撤回「15:00=已过 14:50」正确，否则每个可卖收盘都 force、+2% 永不当选。buy_gate closes `index < day` 无未来 bar。
- **复权口径**：两引擎均 `dividend_type=none`（daily `:340`，minute `:324`），U-R26 同源 closes ✅；cyqk/chip 明确排除（非目标表 + U-R11 叶子禁 import）✅。
- **涨跌停档位**：U-R12 与代码一致（`ma_chip_edge_backtest.py:92-96`：300/301/688=0.20 否则 0.10），北交/ST 不建模写清 ✅。
- **U-R3 事实准确**：`stop_pct=None` 当前会在 `csv_daily_backtest.py:430` / `csv_minute_backtest.py:413,433` 直接 TypeError，§9.1#2 行号引用正确；`summarize` `:719/:727` 的 `:.0%` 确需 None 容忍。
- **U-R22 对 6/8 回归安全**：6/8 现有 reason 全部 `stop_loss*` / `trail:*` 前缀（`strategy6_rules.py:63`、`strategy8_rules.py:86-88`），新桶不影响旧计数。
- **U-R9/U-R10 池语义属实**：v7 空 CSV 仍进 map（`csv_minute_backtest_v7.py:462` 不过滤空）；`--pool-dir` 由 main() SystemExit 强制（`:498-500`）。
- **U-R21 的 11 交易日**与策略 7 指数闸 11-session warmup 对齐（`strategy7_rules.py:159-165`）✅。
- **U-R23/U-R28 实施序**与 `tests/test_csv_strategy_books.py:21` 硬断言 `== ("version6","version8")` 相容，且符合 `add_csv_strategy_arg` 动态 choices（`csv_strategy_books.py:82-89`）✅。

## 总评

事实基础扎实（行号、引擎行为、池语义、档位表均与代码核对无误），切片序与 HELP_LOCK 纪律符合小团队「激进一次到位」取向。但 **R1（涨跌停算术二选一，实验已证「字节级不变」不成立）与 R2（策略 4 卖信号无通道）会实质误导实现，必须修**；🟡 清单（R3–R8）多为契约补写，工作量小。**结论：修订 R1/R2 并吸收 🟡 后可进实现；当前 v1.1 不可直接授权。**

（附：实验脚本 `backtest_output/_review_limit_prices_exp.py` 为本次评审所建的可复现取证物，含 pid/正常退出标记；如需保持工作区洁净可在评审收口后删除。）
