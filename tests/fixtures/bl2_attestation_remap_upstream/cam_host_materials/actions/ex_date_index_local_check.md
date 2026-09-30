# ex_date_index 本机复核（DRAFT）

> 用途：actions claim 的除权除息执行数据源复核。仓内草稿 `raw_corporate_actions_603196SH_window.json`（pin `E:\stock_data\ex_date_index.parquet`，sha256 `93c264ed…`，57867 行，2025-09-01..2025-12-31 零命中）为 R3 host 侧产物；本文件为 2026-09-30 在 win11 数据盘（F:，hive 三树同型）上的独立复核。

## 复核对象

- 文件：`F:\stock_data\ex_date_index.parquet`
- 本机 sha256：`e8fe70ce856a37228c14c40067b94b1f5793da3cff32b0d699515e53b96cbedc`（57846 行，列 `stock_code/ex_date/dr/fetched_at`，fetched_at=2026-07-09）
- ⚠️ 与 pin 的 `93c264ed…`（57867 行）**不是同一字节版本**——湖文件 2026-07-09 重抓过。pin 版本的零命中结论以 R3 草稿为准；本复核在**更新版本**上独立重跑，结论一致（见下），属加强证据而非替代。

## 复核结果（2026-09-30，vanna312 + pyarrow）

603196.SH 全历史命中 8 行，全部在窗口之前：

| ex_date | dr（复权因子） |
|---|---|
| 20180615 | 1.009416 |
| 20190614 | 1.011376 |
| 20200612 | 1.026595 |
| 20210610 | 1.010938 |
| 20220610 | 1.029032 |
| 20221207 | 1.019946 |
| 20230613 | 1.003508 |
| 20240614 | 1.002547 |

- **2025 全年命中 = 0**（含经济覆盖区间 [2025-10-23, 2025-11-04]）——历史规律为每年 6 月现金分红除息，2025 年无记录，窗口必然无事件。
- 与仓内草稿（pin 版本、2025-09-01..2025-12-31 零命中）结论一致；两版本快照横跨 2026-07 重抓，结论稳定。

## adj_factor 交叉（2026-09-30 补入，duckdb 谓词下推）

`F:\stock_data\adj_factor.parquet`（列 `date/stock_code/close_front/close_none/cumulative_adj_factor/adj_factor_back`）603196.SH 切片 2025-10-20..2025-11-06（14 个交易日）：

- `cumulative_adj_factor` 全切片恒等于 **1.0**（distinct = [1.0]）——窗口及前后复权因子无任何跳变，无事件的量化旁证 ✓
- `close_none` 与 daqmt/kimi 日线收盘价 14/14 一致（10-22=23.36、10-23=23.89 … 11-04=22.96、11-05=22.55）——第四源价格交叉 ✓

四源互证齐备：ex_date_index 零命中 × cninfo 77 公告零行动 × preClose 链无调整 × adj_factor 恒 1.0。
