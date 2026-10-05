# 当根 K 扫持仓 · 成交或跳过（2026-10-03）

**RETIRED (2026-10-05, step 3):** Bar-scan / true-core-wire / host round-trip probes removed; production fills use `csv_minute_backtest.simulate` / `HeldMinuteCursor` / `FillConfig`, classification uses registry `minute_classification` (#384). History retained below.

这是研究路径上的**一根 K、一个持仓**成交规则，不是交易系统。

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-03（Asia/Shanghai） |
| 基线 | `master` |
| 人裁 | 不建挂单簿、不建交易系统。用旧分钟引擎的简单规则：当根扫持仓，成交或跳过 |
| 止损成交价 | 与旧引擎 `hl` 以及 Backtrader Stop 相同：跳空按开盘价，触及按止损价 |
| 回撤止盈 | 与 version1 相同：收盘利润回撤达到给定比例才按收盘价成交。low 穿过但收盘收回来则跳过 |
| 同一根顺序 | 先用 high 抬峰值，再止损，再止盈。止损优先 |
| 范围 | `backtest/research/bar_scan_exit.py` + 合成测试。不接任何策略书 |

明确不是：

- 不是 `SubmitOrder` 类型扩展，不是挂单，不是事件总线，不是经纪商队列
- 不删 `csv_minute_backtest.py`，不改旧入口默认
- 空 Fees。不改 MatchCore，不改 `simulate`
- 无 4090。无写湖
- ≠δ5≠R4
- 合成测试只。不读行情湖

旧引擎仍是当根扫描、没有挂单簿。本函数只把 version1 用到的止损（2% 由调用方传入 `stop_pct`）和利润回撤止盈收成一个纯函数。T+1、跌停、手续费都不在这里。
