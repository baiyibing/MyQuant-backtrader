# Kimi 金融数据补缺指针

- A 股数据缺失时，不要寻找本地 Wind、iFinD 或同花顺桌面客户端，也不要因 QMT/xtquant 停机而停止补缺。
- ST 采集 SSOT 位于 OSkhQuant1.3 的 `docs/operations/st-data-channels-ssot.md`；Kimi 采集提示词为该仓 `docs/prompts/prompt-kimi-datasource-st-harvest.md`（commit `b1863731178e`，lesson 61）。
- 2026-09-14 人裁：OSkhQuant1.3 下载并写入湖，MyQuant 与 MyQuant-backtrader 只消费；不要把采集流程复制到本仓。
- 上述 ST 提示词的 Kimi Wind 调用口径：不要调用 `get_data_source_desc`；`data_source_name=wind`、`api_name=wind_get_financial_data`；每批 100。Wind 返回无数据时，用本地 write-empty 命令写仅含表头的空 CSV；不要重试空批次 `0027/0028`。
- 本仓另有 2026-10-01 instruments 佐证包：[`docs/backtest/b-l2-01-evidence-2026-09-30/kimi_instruments_fill_20261001/`](../backtest/b-l2-01-evidence-2026-09-30/kimi_instruments_fill_20261001/)（commit `38374f0f`，PR #287）。该包用 THS `stock_finance_data` 的 `get_price` 获取 `reference_price`，用 Wind 获取涨跌停价，且确实要求 Kimi 调用 `get_data_source_desc`；ST 采集以 1.3 提示词为准，不调用 `get_data_source_desc`。不要把 instruments 包视为写湖授权。
- 4090 上无头运行：`kimi -p`，不用 `--auto`，不用 `--yolo`。
- 2026-10-04 事实：Kimi wind 插件没有分钟线 API；`wind_get_minute_data` 返回 `API_NOT_FOUND`；`wind_get_price` 只返回日线，拒绝盘中时间戳。不要把这些日线行写入分钟湖。
