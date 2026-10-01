# KIMI FILL 报告 — B-L2 instruments 四字段补证

- 标的：`603196.SH`（璞源材料）
- 窗口：`2025-10-23` … `2025-11-04`（9 个交易日）
- schema：`bl2_instruments_kimi_fill_v1`
- 执行日期：2026-10-01（本轮 datasource 新拉取为准）

## 一、每字段来源

| 字段 | 来源 | 拉取方式 |
| --- | --- | --- |
| reference_price（前收/参考价） | **THS**（stock_finance_data） | `get_price` 日线（adjust=none，2025-10-17 起拉以覆盖 10-22 前收），取前一交易日 close |
| limit_up（涨停价） | **Wind** | `wind_get_financial_data` 逐日涨停价 |
| limit_down（跌停价） | **Wind** | 同上，逐日跌停价 |
| ordinary_listing（普通上市） | **Wind + THS 名称交叉** | Wind `get_stock_info` 证券简称「璞源材料」、THS `thsname_cn`「璞源材料」，均不含 ST/特别处理标记 → 全部 9 日 `true` |

原始落盘：`raw/ths_603196_daily.csv`（THS 日线 13 行）、`raw/wind_603196_limits.csv`（Wind 涨跌停/前收 9 行）、`raw/wind_603196_info.csv`（Wind 基本信息）。

取值规则备注：`wind_get_price` 不支持自选 fields（只回 close），故涨跌停改走 Wind analytics 自然语言接口；THS 取不复权价，与涨跌停基准口径一致。9/9 日 Wind「前收盘价」与 THS 前一日 close 完全一致（交叉验证通过）；涨跌停 ≈ 前收 ±10%（如 23.36×1.1=25.696→25.7）口径自洽。

## 二、与 prior（R3 摘录）对照

| 对照项 | 结果 |
| --- | --- |
| THS 日线 vs `materials/prior_ths_daily.json` | 重叠日（10-20…11-04）OHLCV 逐值一致，无差异；本轮多拉 10-17，窗口外 11-05…11-07 未拉 |
| Wind 涨跌停 vs `materials/prior_wind_limits.json` | 9 日涨停/跌停逐值一致，无差异 |
| vs `materials/living_instruments.json`（living，只读对照未改） | reference_price / limit_up / limit_down / ordinary_listing 四字段 9 日全部一致 |

## 三、残留 gap

- 四字段 × 9 日：无 gap，`gaps: []`。
- corroboration：`tick_size` / `lot_size` 本轮 THS/Wind 均未返回，诚实置 `null`（living 中 0.01/100 为 approved_derivation 派生，非厂商直出，未采信为本轮厂商值）。

## 四、边界声明

- **未重开 R4**（R4j freeze PASS @ `6b6d0039…` 维持，本 GO 仅做 Kimi Datasource 补证 pack）
- **未跑 δ5**
- **未 merge PR**（#286 draft 仍 pending Human「合」）
- **未改** MatchCore / Fees / lake / living attestation_packages / SSOT JSON packs
- 未发明任何数据；所有取值均可回溯至 `raw/` 本轮 CSV

FILL_STATUS=COMPLETE
