# 分钟策略接到真核扫线（2026-10-03）

**RETIRED (2026-10-05, step 3):** Bar-scan / true-core-wire / host round-trip probes removed; production fills use `csv_minute_backtest.simulate` / `HeldMinuteCursor` / `FillConfig`, classification uses registry `minute_classification` (#384). History retained below.

旧分钟入口保留。`csv_minute_backtest.py`、`csv_minute_backtest_v7.py`、`csv_minute_backtest_topk_app_dropout.py` 都不删、不关。

本分支从 `master` `19b7be5` 拉出，并带上未合的当根扫线与 `same_bar` / `next_bar`（#320 / #321 的规则，基线不再是 `6a4e6d7`）。

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-03（Asia/Shanghai） |
| 接线 | `backtest/research/minute_true_core_wire.py` |
| 已接 | `version1`（止损 2%，回撤 50%）、`version2`（止损 2%，回撤按持仓日） |
| 未接 | 其余分钟书各缺一个扫线没有的字段，见测试。不造适配器 |
| 调用 | 合成一根可卖 K。`n_days < 1` 拒绝，不在买入日发明成交 |

明确不是：

- 不是挂单簿，不是交易所规则，不改 Fees，不改 MatchCore，不改 `simulate`
- 不删旧入口，不改旧入口默认
- 无 4090。无写湖
- ≠δ5≠R4
- 合成测试只。不读行情湖
