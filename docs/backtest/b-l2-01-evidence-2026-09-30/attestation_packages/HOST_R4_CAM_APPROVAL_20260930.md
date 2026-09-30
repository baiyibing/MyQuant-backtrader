# B-L2 R4 calendar/actions/marks — Human decision record (2026-09-30)

> This records Human's four-cell decision in the 2026-09-30 session. Merge
> awaits baiyibing countersign / Human「合」. This record is not an R4 run GO.

- approval_id: `host_r4_cam_approval_20260930`
- Human cue: **「四格全批，开 packs」**
- Original record: [HUMAN_GO_CAM.md](HUMAN_GO_CAM.md), copied byte-for-byte from
  `/workspace/handoffs/b_l2_cam_packs_20260930/HUMAN_GO.md`.
- Original bytes SHA-256: `e15c79acde154bd7163208f2bf0a156737a9f908ed3fb9f41b87b64d42c13feb`.
- Upstream: `baiyibing/OSkhQuant1.3` #1114 at
  `42d066b81a083be49881f0dd8c5ab53ed4f422f6`, directory
  `docs/evidence/b_l2_r4_cam_host_materials_draft_20260930/`.
- Baseline: MyQuant-backtrader #276, `c69f4bcc487608e8ff75e090526e50d116a4bc0a`.
- Contract: ingress note §§3 / 3.2 / 3.3 / 9, including §9.1 six-field proofs.
- Scope: `603196.SH`, `20251023–20251104`, `basis=cross_source_ratio`.
  窗口名称日播时尚，后更名璞源材料；不是亚士创能（603378）。

## §1 Calendar and first_day — approved

`first_day=2025-10-23`: no initial holding acquired before the window.
Use the pinned PMC/SSE calendar subset covering `[2025-10-23, 2025-11-05]`,
ordered and unique, including next possible BUY trading day **2025-11-05**.
SSE official holiday notices anchor the calendar; PMC supplies the dates;
the census cross-check is corroboration only, not a calendar inferred from bars.

## §2 Actions coverage and empty events — approved

For `603196.SH` over `[first_day, end]=[2025-10-23, 2025-11-04]`, Human approves
the four-source completeness statement: ex_date_index zero matches, cninfo
77 archived announcement titles reviewed with zero action-keyword matches,
the nine-day preClose chain without adjustment, and adj_factor constant 1.0.
Consumer `events=[]`, `complete=true`; proof `result.rows=[]`, `complete=true`.
The cninfo search spans `2025-06-01..2025-12-31`; the approved economic coverage
and empty-events claim remain the narrower window above.

Contract §3.2: “`ex_date_index/adj_factor` 的 hash 只证明身份；无行、因子未变或源缺失均不单独证明无事件。”
An empty filter alone does not prove no events. This is a multi-source coverage
statement, with the archived title-level analysis and version limitations retained.
The local ex_date_index snapshot differs from the R3 pin; it corroborates rather
than replaces that version. No PDF full-text review or local lake run is claimed.

## §3 Mark grid and row maps — approved

Human approves the CAM candidates: final plus at least one independent spot-check
selected from the pinned nine-day table. This implementation selects the first
day's explicit 15:00 observation as the distinct spot-check:

| mark_id | event_time = available_at | absolute parquet row (zero-based) | close (raw) |
|---|---|---|---|
| spot_20251023_close | 2025-10-23T15:00:00+08:00 | 46753 | 23.89 |
| final | 2025-11-04T15:00:00+08:00 | 48681 | 22.96 |

Each price is transcribed from `marks/minute_lake_marks_substrate.md` and linked
to its zero-based excerpt line; `available_at=event_time`. The substrate records
the parquet pin + row table + census agreement as the independent legal 15:00
source account. Pin: `58879893f221bfe050b7a16029667c49fb65d8ec6f47592254e549374a577083`.
This is a saved identity note, not a resolver binding or local verification of
census/parquet bytes. Exports do not establish lake equivalence;
`minute_603196` remains unbound. No last-value or synthetic price substitution
is permitted. A 15:00 mark does not add a 15:00 execution bucket.

## §4 Packs knife only — approved

Create calendar/actions consumers, the host-facing marks grid document, three
complete proofs, pinned excerpts and deterministic remap/manifest updates.
Keep instruments/status/units consumer and proof bytes from #276 intact.
Keep `bl2_source_transform_v4`: evidence fill only, loader/validator unchanged.
The original units-ratio `HUMAN_GO.md` remains byte-preserved and separately pinned.

## §5 Explicit stop: no「开 R4」authorization

`r4_authorized=false`; `production_C=frozen`. No R4 / 4090 / R5 dispatch,
recipe/freeze GO, lake PASS, SSOT green, or MatchCore/Ledger/Fees/Clock change.
Host recipe, configured lake identity/coverage and fresh freeze remain pending.
Do not merge without Human「合」; merge does not authorize R4.
Remaining steps: Grok review → Human「合」→ land packs on 4090 → Human「开 R4」.
