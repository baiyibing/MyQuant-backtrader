# DIAGNOSIS — B-L2 units: lots×100 vs shares (raw_shares_incremental)

Tip: `eccc750215af7051ba85b4fab42415a7eecb35fe`
Date: 2026-10-01 CST
Handoff: `/workspace/handoffs/b_l2_units_shares_20261001/`

## Current tip attestation (lots)

`docs/backtest/b-l2-01-evidence-2026-09-30/attestation_packages/units.proof.json`
- schema `bl2_proof_v1`, subject `units`
- basis `cross_source_ratio`
- binding: `column=volume`, `kind=incremental`, `unit=lots`, `shares_per_unit=100`
- Human GO marker: `approval_id=b_l2_remap_r4_20260930`, cue 人裁接受直接对账
- Prior GO SHA-256 `bb287dfe9e2559e9fe05abb7401a636aa6596524cfb79ffa34a4f3ff884c2afe`
- `manifest.json`: `transform_version=bl2_source_transform_v6`, `r4_authorized=false`

Loader gate (`source_loader._units_evidence`): the only accepted `cross_source_ratio`
path hard-requires `unit=lots` + `shares_per_unit=100` for this exact probe window.

## Lake / vendor numeric scale (honest)

Pinned lake daily `603196.SH` 2025-10-23: **volume=31780**  
Wind MCP / Sina shares same day: **3177959** / **3177959**  
THS `stock_finance_data`: **3177900**  
Tencent ifzq field order documents volume as **手**: **31780**  
daqmt 1d: **31780**; ratio table labels daqmt as lots, THS as shares; 8/9 days ratio exactly 100.

Minute census sample 2025-10-23 09:31: lake `volume=380`, `close≈23.1`, `amount≈879429`  
→ `amount/(close×volume)≈100.19` (lots-scale; shares-scale would imply amount≈8778).

Minute lake pin: path `E:\stock_data\...\period=1m\...\603196_SH\data.parquet`  
sha256 `58879893f221bfe050b7a16029667c49fb65d8ec6f47592254e549374a577083`  
Daily lake pin sha256 `d96f2ed8903a5140d4154969d9faa7ddc66a885e1bbc2b7350901784c625155e`

**Conclusion:** as-shipped lake `volume` integers are **lots-scale** (手), not share-scale.
Wind/THS prior materials remain valid for the **historical lots** claim (lake×100 ≈ shares vendors).
They are **not** valid evidence that the lake volume column *is* shares.

OSkhQuant1.3: K-line lake write path is zero-conversion from QMT; trading/execution
`volume` fields are 股. User prefers 股; δ5 `UNIT=raw_shares_incremental` rejects lots×100.

## What must not be invented

- Do **not** re-label Wind/THS/ratio_table as proving lake `volume` is shares.
- Do **not** invent a vendor `source_declaration` that QMT K-line volume is 股
  (four official carriers still have no K-line unit note — vendor_units_absence stands).
- Do **not** rewrite lake parquet (lock).
- Do **not** loosen MatchCore/Fees/Clock; do **not** set `r4_authorized=true`;
  do **not** dispatch 4090/R4; do **not** merge without Human「合」.

## Honest flip options (Codex choose + document)

**A (preferred fail-closed / incomplete):** Supersede lots GO historically; target
`unit=shares` / `shares_per_unit=1` / raw_shares_incremental; leave units
`complete=false` or equivalent fail-closed until lake bytes are shares-scale or a
separately authorized mapping contract exists. Update ingress + README supersession.
Transform v7 only if loader/gate must stop accepting the superseded lots exception.

**B (Human-preference override, still r4_authorized=false):** Implement living
binding `unit=shares`, `shares_per_unit=1` under a **new** Human GO marker for this
cut, with transform **v7** rewriting `_units_evidence` so the old lots-only
`cross_source_ratio` exception is **historical_superseded** and no longer accepted
as the living path. Limitations **must** state: lake numeric scale remains lots-like
per Wind/THS/daqmt pins; those materials are cited only as historical lots proof /
conflict disclosure, **not** as shares proof; economic PASS / R4 still blocked.
Do not invent vendor shares declaration.

**C (forbidden):** Claim lake volume is shares by reusing ratio/Wind/THS as if
ratio were 1; or keep lots×100 while labeling `raw_shares_incremental`.

δ5 alignment note: even after B-L2 packs prefer shares, δ5 still needs its own
`d5_evidence_pack_v1` units pack; B-L2 PASS labels must not be reused as δ5 PASS.

## Pins / references

- Ingress: `docs/backtest/note-l2-lake-source-ingress-b-l2-01-2026-09-29.md` §9–§10.2
- Packs: `docs/backtest/b-l2-01-evidence-2026-09-30/attestation_packages/`
- Remap: `.../remap.py` (`GO_CUE`, units builders, human_go source)
- Loader: `backtest/research/minute_orders_backend/source_loader.py`
- Provenance: `source_provenance.py` `TRANSFORM_VERSION` currently `bl2_source_transform_v6`
- δ5 conflict handoff: `/workspace/handoffs/d5_kimi_units_advice_20261001/materials/`
- New HUMAN_GO SHA-256: `ff0a5f3bf74e775c66a692e7857eff22cc6d5f0fd0757d97abb38172c75613ab`
