# 成交时点可配 · same_bar / next_bar（2026-10-03）

**RETIRED (2026-10-05, step 3):** Bar-scan / true-core-wire / host round-trip probes removed; production fills use `csv_minute_backtest.simulate` / `HeldMinuteCursor` / `FillConfig`, classification uses registry `minute_classification` (#384). History retained below.

研究路径纯函数 `scan_bar_exit` 上的一个开关。不是挂单簿，不是交易系统。

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-03（Asia/Shanghai） |
| 基线 | `origin/master` `6a4e6d7`，并带上未合的当根扫线（#320 的规则） |
| 默认 | `timing="same_bar"`。与 #320 的 `scan_bar_exit` 相同：跳空按开盘价，触及按止损价，回撤止盈按收盘价 |
| `next_bar` | 触发仍看传入的这根 K。要成交时，成交价改为下一根开盘，不在下一根上重判止损或止盈 |
| 跳过 | 本根不触发时直接跳过，不需要下一根 |
| 范围 | `backtest/research/bar_scan_exit.py` + 合成测试 |

明确不是：

- 不是挂单簿，不是交易所规则，不改 Fees，不改 MatchCore，不改 `simulate`
- 不删 `csv_minute_backtest.py`，不改旧入口默认
- 无 4090。无写湖
- ≠δ5≠R4
- 合成测试只。不读行情湖
