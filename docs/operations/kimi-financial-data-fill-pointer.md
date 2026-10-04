# Kimi 金融数据补缺指针

- A 股数据缺失时，不要寻找本地 Wind、iFinD 或同花顺桌面客户端，也不要因 QMT/xtquant 停机而停止补缺。
- ST 采集 SSOT 位于 OSkhQuant1.3 的 `docs/operations/st-data-channels-ssot.md`；Kimi 采集提示词为该仓 `docs/prompts/prompt-kimi-datasource-st-harvest.md`（commit `b1863731178e`，lesson 61）。
- 2026-09-14 人裁：OSkhQuant1.3 下载并写入湖，MyQuant 与 MyQuant-backtrader 只消费；不要把采集流程复制到本仓。
- 上述 ST 提示词的 Kimi Wind 调用口径：不要调用 `get_data_source_desc`；`data_source_name=wind`、`api_name=wind_get_financial_data`；每批 100。Wind 返回无数据时，用本地 write-empty 命令写仅含表头的空 CSV；不要重试空批次 `0027/0028`。
- 本仓另有 2026-10-01 instruments 佐证包：[`docs/backtest/b-l2-01-evidence-2026-09-30/kimi_instruments_fill_20261001/`](../backtest/b-l2-01-evidence-2026-09-30/kimi_instruments_fill_20261001/)（commit `38374f0f`，PR #287）。该包用 THS `stock_finance_data` 的 `get_price` 获取 `reference_price`，用 Wind 获取涨跌停价，且确实要求 Kimi 调用 `get_data_source_desc`；ST 采集以 1.3 提示词为准，不调用 `get_data_source_desc`。不要把 instruments 包视为写湖授权。
- 4090 上无头运行：`kimi -p`，不用 `--auto`，不用 `--yolo`。
- Wind 有 A 股分钟线。Kimi 插件接口是 `data_source_name=wind`、`api_name=wind_get_stock_quote`，不是 `wind_get_minute_data`，也不是 `wind_get_price`。2026-10-01 已用该接口补 002231.SZ、300379.SZ、600200.SH，报告在 `D:\exports\topk_s1_cap_cli_host_20261001\vendor_fill\FILL_REPORT.md`。`wind_get_minute_data` 的 `API_NOT_FOUND` 和 `wind_get_price` 只出日线，不能写成「Wind 没有分钟线」。
- Wind 分钟与 QMT 分钟对齐见 [`docs/backtest/ssot/vendor-bar-alignment-ssot.md`](../backtest/ssot/vendor-bar-alignment-ssot.md)。QMT 湖目标是 END；Wind `wind_get_stock_quote` 常见 START。禁止整表盲加一分钟；缺根不补零。
- 2026-10-04 事实：同花顺源名 `stock_finance_data`。`get_price` 的 interval 只有 D/W/M/Q/Y。`get_stock_realtime_price` 对 300344.SZ 在 2025-10-24 09:31、10:00、2025-10-28 14:30 以及对照 2026-09-18 10:00 均返回 `EMPTY_DATA`。iFinD 不在 kimi-datasource 枚举（有 stock_finance_data、wind、gildata、yahoo，无 ifind）。未写入 lake/qlib。
- 2026-10-04 300344.SZ 分钟已用 `wind_get_stock_quote` 写入。原始 936 行，入湖 928 行（去掉 09:30×4 与 15:00×4，无 11:30，其余连续分钟 +1，未整表平移，未补零量）。成交量股//100，5 根余数在 `D:\exports\kimi_300344_1m_wind_quote_20261004\remainder_audit.csv`。湖 `symbol=300344_SZ\data.parquet` 与 002231 分区时钟同为 END，首 2025-10-23 09:32:00，尾 2025-10-28 14:57:00。qlib `features\sz300344` 五个 1min.bin 各 3840 字节。
