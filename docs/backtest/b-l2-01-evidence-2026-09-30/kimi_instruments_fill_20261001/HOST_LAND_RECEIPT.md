# HOST LAND RECEIPT — B-L2 instruments Kimi fill → evidence

- at_cst: 2026-10-01 14:27:14 +0800 Asia/Shanghai
- machineId: `6e8988e9-eaab-447c-ad5d-effde4604424` (newtest_4090)
- GO: land Kimi THS/Wind corroboration pack as evidence (pack #276 spirit, reverse direction)
- LAND_STATUS=COMPLETE

## Tip pin

- master after #285 squash: `f8efed23472a7603422d0707843f97e2c4ec87ad`
- verified: GitHub PR #285 `merge_commit_sha` + local `github-master` = `f8efed23472a7603422d0707843f97e2c4ec87ad`
- host checkout at land time was on branch `docs/bt-practical-parity-limits-tick-ssot` @ `676b2e01…` (PR head); tip pin is master merge SHA above (not a checkout switch)

## Source pack

- path: `D:\exports\bt_bl2_instruments_kimi_fill_20261001\`
- INSTRUMENTS_FOUR_FIELDS.json sha256: `d3fbb9d088b62fafab315aa5d7f7c61fc8a66abc07482d5347693e96c3e5eb96`
- Kimi: v2.1.1 + kimi-datasource 3.4.0
- symbol / window: `603196.SH` · `2025-10-23`…`2025-11-04` (9 sessions)

## Dest path(s)

| role | path | note |
|------|------|------|
| **primary (R4j evidence)** | `D:\exports\b_l2_01_4090_r4j_20261001\evidence\kimi_instruments_fill_20261001\` | full pack + raw + materials |
| **R4j sources** | `D:\exports\b_l2_01_4090_r4j_20261001\evidence\attestation_packages\sources\kimi_*` | structured corroboration sources (no name collide with living ths_daily/wind_limits) |
| **tip docs sibling** | `D:\PycharmProjects\MyQuant-backtrader\docs\backtest\b-l2-01-evidence-2026-09-30\kimi_instruments_fill_20261001\` | file copy only; **not committed / no PR** |
| **tip docs sources** | `D:\PycharmProjects\MyQuant-backtrader\docs\backtest\b-l2-01-evidence-2026-09-30\attestation_packages\sources\kimi_*` | file copy only; **not committed / no PR** |
| **land export** | `D:\exports\bt_bl2_instruments_kimi_land_20261001\` | receipt + RUN_META + primary_mirror |

## Bak path(s)

- none — all dest paths were new (no overwrite). bak root reserved: `D:\exports\bt_bl2_instruments_kimi_land_20261001\_bak_*` (empty / unused)

## Vendor map

| field | vendor |
|-------|--------|
| reference_price | **THS** (stock_finance_data / get_price · adjust=none · T-1 close) |
| limit_up | **Wind** |
| limit_down | **Wind** |
| ordinary_listing | **Wind+THS** (证券简称无 ST → true × 9) |

## Living instruments verify (read-only)

- living path (R4j): `…\attestation_packages\instruments.json` sha256 `ffe8cdf3a1a57270d7e729c3504ee3eae88be7d267c622e404720a429ddb8320`
- tip docs living: same sha256 `ffe8cdf3a1a57270d7e729c3504ee3eae88be7d267c622e404720a429ddb8320`
- **NOT rewritten** (prefer evidence land; fill report already said 9/9 match)
- value_match (decimal): **true** for all 9 days × four fields (reference_price, limit_up, limit_down, ordinary_listing)
- string_exact: false on 3 rows due to trailing-zero scale only (`25.7` vs `25.70`, `21.5` vs `21.50`); values equal
- residual: `tick_size` / `lot_size` corroboration still **null** in fill (living 0.01/100 remains `approved_derivation` / sse_rule — not vendor-direct this pack)

## Key landed sha256

| file | sha256 |
|------|--------|
| INSTRUMENTS_FOUR_FIELDS.json | d3fbb9d088b62fafab315aa5d7f7c61fc8a66abc07482d5347693e96c3e5eb96 |
| KIMI_FILL_REPORT.md | f956734fd96d4b8af779794da4db448ebe84c90ecfeae8f2054f216cb7fdcfa3 |
| raw/ths_603196_daily.csv | 8a269c0587155cb9e6e14f0189235afad4a61b1df3f23ce6c0ebeaa65f7b9e80 |
| raw/wind_603196_limits.csv | 16220da0f6b532018e582d4e3b92ddd2eabada42e1e8d7600b5f38b0d563823b |
| raw/wind_603196_info.csv | 82f23b9e8ea57bbd7c4b2b55effc91f549afe771f112b5a139bed0bbe556f526 |
| sources/kimi_instruments_four_fields.json | d3fbb9d088b62fafab315aa5d7f7c61fc8a66abc07482d5347693e96c3e5eb96 |
| sources/kimi_fill_report.md | f956734fd96d4b8af779794da4db448ebe84c90ecfeae8f2054f216cb7fdcfa3 |
| sources/kimi_ths_603196_daily.csv | 8a269c0587155cb9e6e14f0189235afad4a61b1df3f23ce6c0ebeaa65f7b9e80 |
| sources/kimi_wind_603196_limits.csv | 16220da0f6b532018e582d4e3b92ddd2eabada42e1e8d7600b5f38b0d563823b |
| sources/kimi_wind_603196_info.csv | 82f23b9e8ea57bbd7c4b2b55effc91f549afe771f112b5a139bed0bbe556f526 |

## Explicit non-runs / locks held

- **no R4** opened
- **no δ5** run
- **no merge** of #286 or any PR
- **r4_authorized** still **false** (manifest probes unchanged; not flipped)
- **no invent**
- **no change** to MatchCore / Fees / lake / SSOT JSON packs / living `instruments.json`

## Box mirror

- `/workspace/handoffs/bt_bl2_instruments_kimi_land_20261001/` (receipt + RUN_META + key landed copies)