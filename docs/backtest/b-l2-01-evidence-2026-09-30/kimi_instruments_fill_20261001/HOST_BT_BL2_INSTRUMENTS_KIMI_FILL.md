# HOST — B-L2 instruments 四字段 Kimi Datasource 补证

- 导出: D:\exports\bt_bl2_instruments_kimi_fill_20261001\
- 时间: 2026-10-01 14:23:48 +0800 Asia/Shanghai
- Kimi: v2.1.1 + kimi-datasource 3.4.0
- 标的: 603196.SH · 窗口 2025-10-23…2025-11-04（9 交易日）
- FILL_STATUS=COMPLETE · gaps=[]

## 四字段 ← 厂商

| 字段 | 厂商 |
|------|------|
| reference_price | **THS**（stock_finance_data / get_price · adjust=none · T-1 close） |
| limit_up | **Wind**（analytics / 涨停价） |
| limit_down | **Wind**（analytics / 跌停价） |
| ordinary_listing | **Wind+THS**（证券简称「日播时尚」无 ST → true） |

## 产物 sha256
- INSTRUMENTS_FOUR_FIELDS.json: d3fbb9d088b62fafab315aa5d7f7c61fc8a66abc07482d5347693e96c3e5eb96
- KIMI_FILL_REPORT.md: f956734fd96d4b8af779794da4db448ebe84c90ecfeae8f2054f216cb7fdcfa3

## 残留 gap
- tick_size / lot_size：本轮 THS/Wind 未直接返回 → corroboration=null（living 0.01/100 仍为 approved_derivation 规则，非本包新发明）
- 四字段本身：无 gap

## Cut B（δ5）park
- practical-parity SSOT #285 已落地；#286 draft 待 Human「合」
- δ5 unit packs complete=false stubs 保留作 reference
- **未授权 / 未跑 δ5**

## 明确未做
未开 R4 · 未跑 δ5 · 未 merge 任何 PR · 未改 SSOT/MatchCore/Fees/lake · 未覆写 living attestation_packages · 未 invent
