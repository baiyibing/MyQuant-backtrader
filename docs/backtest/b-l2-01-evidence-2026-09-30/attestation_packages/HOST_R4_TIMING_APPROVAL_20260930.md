# B-L2 R4 timing — Human decision record (2026-09-30)

> Timing packs-only approval records Human「开修」. Merge awaits baiyibing
> countersign / Human「合」. This record is not an R4 run GO.

- approval_id: `host_r4_timing_approval_20260930`
- Human cue: **「开修」**, 2026-09-30 (Asia/Shanghai).
- Original record: [HUMAN_GO_TIMING.md](HUMAN_GO_TIMING.md), copied byte-for-byte
  from `/workspace/handoffs/b_l2_r4_timing_20260930/HUMAN_GO.md`.
- Original bytes SHA-256: `b89d99fc0fabbad5dd1e6da4ff6f3368ab84d1c7afce71832ea9e405d7e270f7`.
- Baseline: MyQuant-backtrader #277, `55f27f7967bc98a30146dc2474b91f1ac69f46f0`.
- R4d blocker: `SourceContractError: timing: unknown proof source ref`;
  `claims.timing.proofs=["proof_timing"]` referenced an absent source.
- Contract: ingress §3.1 and §9/§9.1; timing keeps observation rows without
  instruments-style basis/binding requirements.
- Scope: `603196.SH`, bars/marks `2025-10-23..2025-11-04`.

## §1 Pinned independent materials

These are existing **MyQuant-backtrader** evidence bytes at the baseline above,
under `docs/backtest/b-l2-01-evidence-2026-09-30/`; they are not new OSkhQuant exports.

| Original file | Full-file SHA-256 |
|---|---|
| `raw_materials/raw_lake_minute_census_603196SH_20251023_20251104.json` | `b4ee473bcf7d224d635ce0f788d0d64dde8a2e421034420c2c292e9c632b7188` |
| `raw_materials/raw_excerpt_xtquant_docs.json` | `3884f478256f96c7938cb5f0f40075ceb03f8064665be1193e2d445612bc8a12` |
| `HOST_MATERIALS_MAP_R4.md` | `b2487a9ba20f66b8e211b22536fb92d5dc60b0c2edb8eb2427c8d4c93e0e2fba` |

Compact LF excerpts preserve the census semantics/counters and selected cells,
vendor timestamp/fill_data lines, and map header through §1.1. Source excerpt
row indexes are zero-based; census `row_idx` remains the separate absolute
parquet row index. Existing `opening_auction` is corroboration only.

## §2 END label and completed-bucket availability — approved

Approve **END** and **`completed_bucket_available_at_end`** for this historical
bar model based on the pinned census `time_semantics`, map §1.1 and contract
§3.1: label t covers `[t-1min,t)`, and completed close/volume become available
at `bucket.end=t`, never at bucket.start. The approved declaration is END with
`availability=bucket_end`. R4d declared
`time={encoding:epoch_ms,timezone:Asia/Shanghai,label:END}`; its encoding portion
has the unresolved discrepancy below and is not certified by this approval.

Map §1.1 gives `1761211800000 → 2025-10-23 09:30` Shanghai. The existing loader's
UTC-epoch-to-Asia/Shanghai decoder instead gives **`2025-10-23T17:30:00+08:00`**.
Preserve the original “上海墙钟按 UTC epoch 毫秒编码” / “不是真 UTC” wording as
evidence. The pinned #1111 vendor export uses `1761183000000` for Shanghai
09:30, a difference of 28800000 ms; it cannot stand in for lake time identity.
**Host time/index/label reconciliation is a remaining freeze blocker.**
This approval does not authorize a silent eight-hour shift, START relabel,
Clock change, or certification of the contradictory R4d epoch mapping.

Census coverage is 2169 rows, 2133 tradable cells, zero missing and zero duplicate
cells. Each day has 241 labels; 237 are tradable END labels 09:31–11:30 and
13:01–14:57. 09:30/14:58/14:59/15:00 remain off-grid; 15:00 is mark-legal.
Boundary samples include 2025-10-23 09:30/09:31/14:57/15:00 at absolute rows
46513/46514/46750/46753 and final 2025-11-04 15:00 at row 48681.

This approves historical completed-bar availability, not measured live feed
arrival latency. A source known to arrive after end must be rejected, not
backfilled to end. File collection time is not event time. Vendor docs call
`time` a timestamp; they do not independently declare END. `fill_data=True`
zero-fill is a limitation/corroboration, not event-time or actual-trade proof.

## §3 Packs and host registration — approved

Add `proof_timing` and its independent raw/approval/GO sources to the manifest.
R4d-style hosts registering every `manifest.artifacts` entry pick up the exact
id; `claims.timing.conclusion=completed_bucket_available_at_end` uses
`proofs=["proof_timing"]`. There is no timing consumer role. Do not create a
partial local recipe or reuse the R4d scope hash; host registration and fresh
scoped attestation remain separate work after authorization.

The proof covers the bars/marks window through 2025-11-04; the calendar's
2025-11-05 next BUY date does not assert minute data on that date. Any wider
execution/mark window needs fresh coverage. Keep transform
`bl2_source_transform_v4`: evidence fill only, loader/validator unchanged.
Keep #1111/#1112/#1114 pins, instruments/status/units/CAM consumer and proof
bytes, and the original units/CAM Human GO documents intact.

## §4 Explicit stop: no「开 R4」authorization

`r4_authorized=false`; `production_C=frozen`. No 4090/R4/R5 dispatch, merge,
lake PASS, SSOT green, or MatchCore/Ledger/Fees/Clock/lake change is authorized.
Vendor export does not establish lake identity. Saved census identity does
not bind the configured minute partition; host recipe/account/commands,
lake identity/coverage and fresh freeze remain pending. Original R3/R4/R4d
receipts retain their verdicts. Merge does not authorize R4.

Remaining Human steps: **Grok review → Human「合」→ land packs on 4090 → Human「开 R4」**.
