Human GO 2026-10-01 ~10:25 CST (Asia/Shanghai)
Cue: Human「改成股啊」— after #283 tip `3fd4861`, shares *target* alone is not enough;
make B-L2 volume **actually shares-scale** so living `units.proof` can honestly
complete as `raw_shares_incremental` / `unit=shares` / `shares_per_unit=1`.

Chosen path (this knife): **loader transform ×100** from the attested lots-scale
lake column, under this explicit mapping GO; bump transform **v7→v8**.
Alternative deferred: host export of shares-scale bytes (no lake rewrite in place).

Mapping contract (authorized, not silent):
- Lake/daqmt/Tencent `volume` integers remain **lots-scale** at rest (no parquet
  rewrite in place). Historical lots GO/`cross_source_ratio` materials stay
  historical evidence that lake ints are 手 and the factor is 100.
- Loader v8 applies an explicit **×100** lots→shares conversion when the living
  units proof completes under this mapping GO.
- Living binding after transform: `kind=incremental`, `unit=shares`,
  `shares_per_unit=1`, contract `raw_shares_incremental`.
- Wind/THS/Sina may be cited only as historical lots-scale conflict / factor-100
  disclosure (lake×100 ≈ Wind). **Do not invent** a vendor declaration that lake
  K-line `volume` *is* 股. **Do not** re-label Wind as living shares proof of lake.

Supersedes for the living path: option-A incomplete `human_target` from
`HUMAN_GO_UNITS_SHARES.md` (SHA-256
`ff0a5f3bf74e775c66a692e7857eff22cc6d5f0fd0757d97abb38172c75613ab`) — that target
remains historically true as the preference; this GO supplies the separately
authorized mapping contract that #283 left open.
Prior lots ratio GO `bb287dfe…` remains **historical_superseded** (bytes kept).

Scope this knife:
- Open Codex PR on tip `3fd48612fdcfd8341796517272c71b78735d50a7` (do NOT merge)
- Implement loader/transform v8 + packs/remap/ingress for the mapping; allow
  living `units.proof` `complete=true` only via the authorized mapping path
- Keep `r4_authorized=false`; no MatchCore/Fees/Clock; no lake rewrite; no 4090/R4
  until Human「合」then land + named「开 R4」
- Author baiyibing / Committer StockWork
- Handoff `/workspace/handoffs/b_l2_volume_shares_scale_20261001/`
