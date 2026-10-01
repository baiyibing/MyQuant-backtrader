# DIAGNOSIS — B-L2 volume shares-scale (loader ×100 / v8)

Tip: `3fd48612fdcfd8341796517272c71b78735d50a7` (post-merge #283)
Date: 2026-10-01 CST
Handoff: `/workspace/handoffs/b_l2_volume_shares_scale_20261001/`
Human cue: 「改成股啊」

## What #283 left open

Living `units.proof.json` after #283:
- Target: `unit=shares`, `shares_per_unit=1`, `raw_shares_incremental`
- `complete=false`, `basis=human_target`
- Transform `bl2_source_transform_v7` (retired lots-only `cross_source_ratio` accept)
- Limitation explicitly blocked until **shares-scale lake bytes** OR a **separately
  authorized mapping contract**

Lake numeric scale is unchanged and still lots-like:
- Pinned lake daily `603196.SH` 2025-10-23: **volume=31780**
- Wind / Sina same day: **3177959** / **3177959**
- THS: **3177900**; Tencent ifzq documents 手: **31780**; daqmt 1d: **31780**
- Minute amount/(close×volume)≈100 under lots reading

So flipping `complete=true` while claiming lake ints *are* shares would invent.
That is forbidden.

## Path choice (fail-closed)

| Path | Status | Why |
|---|---|---|
| **L — loader transform ×100 (v8)** | **CHOSEN** | Explicit Human GO authorizes mapping from attested lots lake → shares-scale loaded volume; no parquet rewrite; uses historical lots evidence only for source-scale + factor 100; living binding becomes shares/1 honestly as *post-transform* contract. |
| H — host export shares-scale bytes | Deferred | Allowed in principle; needs host export of new tree (not rewrite-in-place). Not available inside this knife; prefer L. |
| Invent Wind/THS as lake-is-shares | **FORBIDDEN** | Contradicts pinned 31780 vs 3177959; invents vendor declaration. |
| Silent lots×100 relabel without GO / keep v7 incomplete forever | Rejected by cue 「改成股啊」 | Target alone does not make volume shares-scale. |

## Honesty model for path L

1. **At rest:** lake `volume` column integers remain lots-scale. No lake rewrite.
2. **Historical:** archived lots proof / `units_comparison` / ratio_table remain
   `historical_superseded` for living *ratio acceptance*, but stay valid as
   attestation that lake ints are 手 and factor=100.
3. **Living:** new Human GO authorizes loader mapping contract:
   `lots → ×100 → shares` with output binding `unit=shares`, `shares_per_unit=1`,
   contract `raw_shares_incremental`.
4. **Evidence basis:** must be a new accepted basis (e.g. `authorized_mapping`),
   **not** `human_target`, **not** revived living `cross_source_ratio`, **not** a
   fabricated vendor `source_declaration` that QMT K-line volume is 股.
5. **Wind/THS:** cite only as historical lots conflict / factor-100 disclosure.
   Never as proof lake raw volume is shares.
6. **Loader:** when living units proof completes under this mapping, apply ×100
   to lake volume ints before emitting `volume_shares`; recipe volume section
   lists `unit=shares`, `shares_per_unit=1`. Transform stamp **v8**.
7. **Synthetic fixtures** with explicit `source_declaration` shares/1 stay 1:1
   (no ×100). Mapping path is lake/host-attested lots only.
8. **`r4_authorized=false`**. No MatchCore/Fees/Clock. No 4090/R4. No merge.

## δ5 note (out of scope)

δ5 still needs its own `d5_evidence_pack_v1` units pack. Whether an authorized
B-L2 loader mapping counts as δ5 `raw_shares_incremental` is a separate decision;
do not fabricate δ5 packs or claim δ5 PASS.

## Pins / references

- Prior GO shares target: `HUMAN_GO_UNITS_SHARES.md` SHA-256
  `ff0a5f3bf74e775c66a692e7857eff22cc6d5f0fd0757d97abb38172c75613ab`
- Prior diagnosis: `DIAGNOSIS_UNITS_SHARES.md` SHA-256
  `c9629c96f4b8867ae82444962de675fcc7845d23a6e639cb80ccbeba0d170e4e`
- Historical lots GO: `bb287dfe9e2559e9fe05abb7401a636aa6596524cfb79ffa34a4f3ff884c2afe`
- Historical lots proof: `historical/units.lots.proof.json` SHA-256
  `1350ad54777bd4e96e62f1682e3e8003128628edc8ffbcea8a9f1ac11c8db320`
- New HUMAN_GO (this cut) SHA-256:
  `722632a9ff008715c277616004b0e2bfbfd5d380664574cc591a6276cce0435e`
- Loader: `backtest/research/minute_orders_backend/source_loader.py`
- Provenance: `source_provenance.py` currently `bl2_source_transform_v7`
- Ingress: `docs/backtest/note-l2-lake-source-ingress-b-l2-01-2026-09-29.md` §10.3
