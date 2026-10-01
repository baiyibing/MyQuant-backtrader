# SOURCES — bt_practical_parity_limits_tick_20261001

Dated export filling research-BT **practical parity** gaps:
(a) board_% limit bands 0.10 / 0.20 / 0.30
(b) pricetick rounding for limit prices (0.01 fen, Decimal HALF_UP)
(c) **ST time-segmented regimes** (main 5%→10% cutover; ChiNext/STAR/BJ retain board tier)

查阅禁 import of vendor trees — rules copied into `config/*.json` and optional `helpers/board_limit_pricetick.py`.

## Engineering SSOT (preferred over inventing public dates)

| Cite | Value |
|------|-------|
| PR | [#225](https://github.com/baiyibing/MyQuant-backtrader/pull/225) `feat(research): X-07 ST limit tiers + TopK --topk-limit-rule real (P4)` |
| Merge SHA | `5a3e6e20a20ac0b398e76ff82e9f30bca9510e65` |
| Merged (CST+8) | 2026-09-27 12:51:54 +0800 |
| Constant | `ST_MAIN_LIMIT_PCT_SWITCH = date(2026, 7, 6)` in `backtest/research/market_layer.py` |
| Frozen table | `docs/backtest/topk-exec-p4-2026-09-27.md` (X-07 table) |
| Plan | `docs/backtest/plan-topk-exec-model-2026-09-26.md` §5 P4 / X-07 |

PR #225 body excerpt: *non-ST board tiers unchanged; ChiNext/STAR ST = 20%; BJ ST = 30%; main/SME ST = 5% before 2026-07-06 and 10% from that day inclusive. Undated main-ST and unknown-prefix named ST retain 5%; unknown non-ST stays None.*

## Cited files (box paths + sha256)

| Path | sha256 (box, 2026-10-01) |
|------|--------------------------|
| `/workspace/OSkhQuant1.3/oskh_core/board_limit.py` | `72c72b9a89004ce35567978672d9b5b744f4df253533af3e74f4618e793be529` |
| `/workspace/MyQuant-backtrader/backtest/research/market_layer.py` | `b26eb06a6655253ff6fa234ca9c794c304172accc97dac368d2eff25b6c47658` |
| `/workspace/MyQuant-backtrader/backtest/research/ashare_session.py` | `b4279cc9c13a40f74814630bac04817b3d7ab4c1077a133fd01136a088f91ae8` |
| `/workspace/MyQuant-backtrader/backtest/research/signal_price_domain.py` | `67dc3522b15c618e5c5fa4b0a40e313d818c995469f7c90a4d4463bd985afb9a` |
| `/workspace/MyQuant-backtrader/docs/backtest/engine-ashare-correctness.md` | `06e373763a34e7de37dd83d76762764209bf920023d8a95d141f761244561e8b` |
| `/workspace/MyQuant-backtrader/docs/backtest/topk-exec-p4-2026-09-27.md` | `b0a9c380d5e9b2a7db2ad2770c184508c3d8c4d53624268f28f67940c949ab3b` |
| `/workspace/MyQuant-backtrader/docs/backtest/plan-topk-exec-model-2026-09-26.md` | `c80c31588e4856f3dc078fcf4a70259e54555e7ccc71ea3cdc0fd46a0cde594f` |

## Host 4090 cross-check

| Item | Value |
|------|-------|
| machineId | `6e8988e9-eaab-447c-ad5d-effde4604424` (newtest_4090) |
| BT tip | `6b6d0039b1f0177fbd9ae71388996ce6e022f4d0` (2026-10-01 10:58:19 +0800) `B-L2: authorized lots-to-shares loader ×100 (v8) (#284)` |
| PR #225 ancestor of tip | yes (`git merge-base --is-ancestor 5a3e6e2 HEAD`) |
| Host `market_layer.py` sha256 | `6588c1f30582f4dbdbb85f0bfedf1c96161fbfced96fb72bd81b78149326b71a` |
| Host `topk-exec-p4-2026-09-27.md` sha256 | `f15e594550521a5fef6dd951b7bb3ce5ecfac60c0935c411f398c4957164ee51` |
| Host `ashare_session.py` sha256 | `52c8da5f425000a78fd6cbafca3c554a6efcb7e603d0d1c547c7d7a0835a7a91` |
| Host `signal_price_domain.py` sha256 | `3b99b10e25ded025fd9f295fd7f6324cafa3f9b87527d93d9c7c9f0cfcdb667a` |
| Host `OSkhQuant1.3/oskh_core/board_limit.py` sha256 | `eae297c9476e74a19821421dc6e6f9bf2b183465ad997e869e759da9fb3c8cd8` |

Box MyQuant-backtrader tip at export time: `2eeef36be95b4bf05e4e151017353ae5c241513b` (2026-09-27 20:36:51 +0800). Board/%, ST cutover, and fen HALF_UP verified on both tips; prefer **host tip** as operational BT HEAD.

## Public policy cites (supporting; cutover date matches engineering SSOT)

| Doc | URL | Date | Role |
|-----|-----|------|------|
| 《上海证券交易所交易规则（2026年修订）》上证发〔2026〕41号 | https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml | 2026-04-24 publish; **effective 2026-07-06** | Official SSE rule effective date |
| 上交所新闻：交易规则修订（含主板风险警示涨跌幅 5%→10%） | https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20260424_10816474.shtml | 2026-04-24 | Official SSE news |
| 证监会上海监管局转载：A股交易新规7月6日起施行；主板 ST 5%→10%；创业板/科创板 ST 仍 20%；北交所 ST 30% | https://www.csrc.gov.cn/shanghai/c105566/c7643909/content.shtml | 2026-07-06 | Official bureau reprint |
| 上交所征求意见：拟调整主板风险警示股票涨跌幅至 10% | https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20250627_10783267.shtml | 2025-06-27 | Solicitation precursor |

**Uncertainty:** Engineering SSOT for the as_of cutover remains MyQuant PR #225 / `ST_MAIN_LIMIT_PCT_SWITCH`. Public SSE/CSRC cites corroborate **2026-07-06**; do not invent alternate cutover dates.

## Rule excerpts (copied, not imported)

### oskh_core `board_limit_pct` (coarse)

- `300/301/302` → 0.20
- `688/689` → 0.20
- `8/4/9` → 0.30 (BJ coarse)
- `11/12` → 0.20 (convertible)
- else → 0.10
- **ST not modeled** (no name feed)

### MyQuant E-R2 + X-07 ST regimes (BT-preferred)

From `engine-ashare-correctness.md` E-R2 + `market_layer.py` + PR #225 frozen note:

- `300/301/302/688/689` → 0.20 (non-ST and ST)
- `430/83/87/88/920` → 0.30 (non-ST and ST)
- `600/601/603/605/000/001/002/003` → 0.10 non-ST; ST → **0.05 before 2026-07-06**, **0.10 on/after** (inclusive); undated ST → 0.05
- unknown prefix → **None** if non-ST; **0.05** if named ST
- Static export: `config/st_limit_regimes.json` + `config/board_limit_bands.json` (`st_name_overlay.in_static_board_table=true`)

### Pricetick

- `signal_price_domain.PRICE_TICK = Decimal("0.01")`
- `market_layer.round_fen` / `limit_prices`: `prev_close * (1±pct)` then `.quantize(Decimal("0.01"), ROUND_HALF_UP)`

## Survey reference (keep; do not discard)

`/workspace/handoffs/d5_kimi_bt_evidence_bar_survey_20261001/` — Human accepted research-BT practical parity; gaps ① board_% and ② pricetick filled by this export; ③ ST static regimes extended 2026-10-01.

## Explicit non-touch

- K4-04 / knife5 / knife6 issuer stubs — not filled
- δ5 4090 — NOT RUN
- MatchCore / Fees / SSOT / lake RO / units C — untouched
- No vendor import from `/workspace/OSkhQuant1.3/vendor/*`
- No Cloud Agent / merge PR
