Human GO 2026-10-01 ~09:32 CST (Asia/Shanghai)
Cue: Human cut (bt): **B-L2 lake volume unit → shares (raw_shares_incremental)**, not lots×100.
User prefers 股; OSkhQuant1.3 trading/execution code is 股; δ5 wants raw_shares_incremental.

Supersedes: prior units Human GO `b_l2_remap_r4_20260930` (SHA-256
`bb287dfe9e2559e9fe05abb7401a636aa6596524cfb79ffa34a4f3ff884c2afe`) that accepted
`basis=cross_source_ratio` with `unit=lots` / `shares_per_unit=100` for probe
`603196.SH` · `2025-10-23`–`2025-11-04`. That lots proof is now **historical** —
document supersession in packs/ingress; do not silently delete history.

Scope this knife:
- Open Codex PR on tip `eccc750215af7051ba85b4fab42415a7eecb35fe` (do NOT merge)
- Flip B-L2 units attestation toward **raw shares incremental** (`unit=shares`,
  `shares_per_unit=1`) with **honest** evidence rebind
- Wind/THS prior materials may be re-cited **only if still valid for shares**;
  **do not invent**
- Update packs, remap, loader pins, ingress note as needed
- Keep `r4_authorized=false`
- Transform bump v6→v7 if required, with honest reason
- No MatchCore/Fees/Clock economic loosen; no lake rewrite; no 4090/R4 until
  Human「合」then land+named「开 R4」
- Author baiyibing / Committer StockWork
- Handoff `/workspace/handoffs/b_l2_units_shares_20261001/`
