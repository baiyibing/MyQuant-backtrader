# HOST_B_L2_01_R4J — 4090 live receipt

- Issued: `2026-10-01T11:03:02+08:00` Asia/Shanghai
- Host: **newtest_4090** · tip `6b6d0039b1f0177fbd9ae71388996ce6e022f4d0` · dirty=False
- Unit: **B-L2-01** · round **R4j** (tip #284 shares-scale loader ×100 / transform v8; Human「开 R4」) · window `20251023`–`20251104`
- Source: `OSKH_SOURCE_PARQUET_ROOT=E:\stock_data` (read-only)
- Label: 真实行情驱动的合成订单研究
- Transform: `bl2_source_transform_v8` · tip #281 cent-align + double_repr_cent_quantize_v1 · bars.time=`epoch_ms_wall_shanghai_as_utc` · intervals←trimmed status (~2133)
- **Verdict: `PASS`**

## Authorization (three distinct GOs)

1. **R4j run GO**: Human「开 R4」via bt — recorded as `Human「开 R4」via bt` (this run only).
2. **Remap units marker** `sources/human_go.json`: `r4_authorized=False` (must stay false; R4j authorized_mapping path); document sha `bb287dfe9e2559e9fe05abb7401a636aa6596524cfb79ffa34a4f3ff884c2afe`.
3. **Time encoding GO** `HUMAN_GO_TIME_ENCODING.md` sha `e605e3256be64943d8026e45c4ad3ce60c34663ad9ebb45ed99b5d3e86e66538` + `HOST_R4_TIME_ENCODING_APPROVAL_20260930.md` sha `bba1bf35212c49c7c1be10391e5eab5ff9914ac0e83236a4f7449fa4a9d83186`; binding encoding=`epoch_ms_wall_shanghai_as_utc` (implementation GO ≠ R4j run GO).

## Freeze outcome

1. **instruments**: gate **PASS** (host-fill #276).
2. **calendar/actions/marks**: gates calendar=PASS, actions=PASS, marks=PASS (host-fill #277 CAM packs; proofs complete=true).
3. **timing**: gate see cells; proof_timing subject=timing complete=True claim completed_bucket_available_at_end (host-fill #278).
4. **coverage_alignment**: status_rows=2133 intervals=18 (merged_contiguous_same_day_segments_from_status_rows) expanded=2133 equal=True.
5. **freeze_recipe_attestation**: attestation.complete=true attempted with CAM+#278+#279 wall encoding A + #280 status trim + #281 cent-align + #284 shares-scale v8; bars.time=`epoch_ms_wall_shanghai_as_utc` (FORBIDDEN bare epoch_ms / silent ±8h).

## Progress vs R3

- Tip advanced R4i `2685926` (#281 v6) → **`6b6d003`** (#284 shares-scale transform v8); transform **`bl2_source_transform_v8`** + authorized_mapping ×100.
- Prior R4/R4b/R4c/R4d/R4e/R4f/R4g/R4h/R4i roots left untouched; this receipt is R4j only (shares-scale v8 + intervals←trimmed status). R4i PASS not reused.
- Remapped attestation_packages bound from R3 evidence path; manifest sha `30ad169a0ffeb5e3067bd6913fafaad5d37cc35c36b5206209c84ef7cb281d2a` (MATCH).
- units: Human narrow exception `basis=cross_source_ratio` materials present (vendor-doc absence + 20251023 THS 100-share diff disclosed).
- status: 2133 canonical bindings with explicit suspendFlag; lake minute partition newly pinned as `minute_603196` sha `58879893f221bfe050b7a16029667c49fb65d8ec6f47592254e549374a577083`.
- instruments: gate **PASS** (sse/wind complete=True; fields_filled=True).
- Window bars still present: **2169** rows across `2025-10-23` … `2025-11-04` (9 sessions).

## Probe / bind notes

- Minute partition: `E:\stock_data\stock\period=1m\dividend_type=none\symbol=603196_SH\data.parquet` schema={"time": "int64", "open": "double", "high": "double", "low": "double", "close": "double", "volume": "int64", "amount": "double", "__index_level_0__": "timestamp[ns]"}
- Lake partition sha256: `58879893f221bfe050b7a16029667c49fb65d8ec6f47592254e549374a577083`
- Partition mode viable: **True** (has_symbol_column=False)
- Pack artifacts verified: **57** / mismatches=0 (expect 57 incl. volume_mapping_* + time_encoding_* + proof_timing)
- Intervals: count=18 derivation=merged_contiguous_same_day_segments_from_status_rows; expanded=2133; coverage_equal=True (status_rows=2133)
- Recipe attempt: `D:\exports\b_l2_01_4090_r4j_20261001\recipe_attempt\recipe.json` sha256=`18861ec3b22ac09370f11474dd1243d6474ae6a87cab94269e7a3ff3b2f572c9`
- attestation_scope: `ef819cc0e771fb0278cce62b581ae587d53899ddf297d2d881a8bbb4d1f615ca`
- timing.proof: subject=timing complete=True HUMAN_GO_TIMING_sha=b89d99fc0fabbad5dd1e6da4ff6f3368ab84d1c7afce71832ea9e405d7e270f7
- Wall encoding: bars.time=`epoch_ms_wall_shanghai_as_utc`; HUMAN_GO_TIME_ENCODING_sha=`e605e3256be64943d8026e45c4ad3ce60c34663ad9ebb45ed99b5d3e86e66538`; HOST approval sha=`bba1bf35212c49c7c1be10391e5eab5ff9914ac0e83236a4f7449fa4a9d83186`; wall_encoding_ok=True.
- Native API↔L1 and independent oracles: **see cells**.

## Per-cell table

| gate | source | parity | oracle | note |
|---|---|---|---|---|
| sync_tip | PASS | NOT_RUN | NOT_RUN | HEAD=6b6d0039b1f0177fbd9ae71388996ce6e022f4d0 dirty=False identity.code_sha=6b6d0039b1f0177fbd9ae71388996ce6e022f4d0 code_dirty=False transform=bl2_source_transform_v8 py='3.12.13 \| packaged by Anaconda, Inc. \| (main, Jul  9 2026, 14:26:47) [MSC v.1942 64 bit (AMD64)]' pyarrow=25.0.0 |
| pack_bind | PASS | NOT_RUN | NOT_RUN | packs=D:\exports\b_l2_01_4090_r4j_20261001\evidence\attestation_packages manifest_sha=30ad169a0ffeb5e3067bd6913fafaad5d37cc35c36b5206209c84ef7cb281d2a match=True HUMAN_GO_sha=bb287dfe9e2559e9fe05abb7401a636aa6596524cfb79ffa34a4f3ff884c2afe match=True daqmt_detail_sha=b73449791a2e1a81631b1f26060085a863971101de141d6c065302368034ea10 match=True artifacts=57 mismatches=0 manifest.r4_authorized=False transform=bl2_source_transform_v8 HUMAN_GO_TIME_ENCODING_sha=e605e3256be64943d8026e45c4ad3ce60c34663ad9ebb45ed99b5d3e86e66538 match=True HOST_TIME_ENCODING_APPROVAL_sha=bba1bf35212c49c7c1be10391e5eab5ff9914ac0e83236a4f7449fa4a9d83186 match=True time_encoding_approval_json_sha=8fedbb2833675a18c9d434f0c38592b2fd2f74e24cb08a283aeeeecb0b8f71b7 wall_encoding=epoch_ms_wall_shanghai_as_utc wall_encoding_ok=True unbound_minute={'id': 'minute_603196', 'sha256': None, 'requirement': 'Null sha256 means this catalog does not ship parquet bytes. The wall-encoding and volume-mapping pins live in time_encoding_approval.binding.source_sha256 and volume_mapping_approval.input_binding.source_sha256 (58879893f221bfe050b7a16029667c49fb65d8ec6f47592254e549374a577083), not in this field, and the loader enforces it. Host must still configure/resolve lake identity/coverage and freshly freeze; exports do not establish lake equivalence.'} RUN_GO=Human「开 R4」via bt |
| configured_source_root | PASS | NOT_RUN | NOT_RUN | OSKH_SOURCE_PARQUET_ROOT=E:\stock_data container_ok=True |
| proposed_window_bars_present | PASS | NOT_RUN | NOT_RUN | symbol=603196.SH window_rows=2169 days=9 lake_sha256=58879893f221bfe050b7a16029667c49fb65d8ec6f47592254e549374a577083 |
| minute_parquet_partition_symbol_mode | PASS | NOT_RUN | NOT_RUN | schema_matches_vendor=True has_symbol_column=False columns.symbol={'kind':'partition'} path=E:\stock_data\stock\period=1m\dividend_type=none\symbol=603196_SH\data.parquet |
| units | PASS | NOT_RUN | 未覆盖 | basis=authorized_mapping (expect authorized_mapping); binding unit=shares spu=1 kind=incremental; contract raw_shares_incremental per tip packs; lake ints lots-scale at rest; units.proof complete=True; summary='Authorized mapping complete: lake lots x100 -> loaded shares/1, raw_shares_incremental; lake NOT_RUN'; human_go marker r4_authorized=False; R4i cross_source_ratio lots SUPERSEDED; amount/(close*volume) heuristic NOT used; minute_603196 lake_sha=58879893f221bfe050b7a16029667c49fb65d8ec6f47592254e549374a577083; RUN_GO separate from remap marker |
| instruments | PASS | NOT_RUN | 未覆盖 | host-fill #276: sse.complete=True, wind.complete=True; nulls={'available_at_all_null': False, 'ordinary_listing_all_null': False, 'n_rows': 9}; gate=PASS; refusing to invent timestamps/listing/10% if incomplete |
| status | PASS | NOT_RUN | 未覆盖 | status rows=2133 (expect 2133 Clock-trim #280; no 14:57-15:00) with explicit suspendFlag bindings; status.proof complete=True; vendor export ≠ lake identity; fill_data=True disclosed; zero-volume ≠ halt-from-silence |
| calendar | PASS | NOT_RUN | 未覆盖 | host-fill #277: proof_calendar.complete=True; trading_dates=['2025-10-23', '2025-10-24', '2025-10-27', '2025-10-28', '2025-10-29', '2025-10-30', '2025-10-31', '2025-11-03', '2025-11-04', '2025-11-05']; n=10; gate=PASS |
| actions | PASS | NOT_RUN | 未覆盖 | host-fill #277: proof_actions.complete=True; actions.complete=True events=[]; gate=PASS; probe≠attestation not used |
| marks | PASS | NOT_RUN | 未覆盖 | host-fill #277: proof_marks.complete=True; mark_grid_n=2 ids=['spot_20251023_close', 'final']; lake abs_row spot-check deferred to freeze; gate=PASS; marks.json is host grid mapped into recipe.mark_grid (not a loader role) |
| timing | PASS | NOT_RUN | 未覆盖 | host-fill #278: proof_timing subject=timing complete=True summary='completed_bucket_available_at_end; independently pinned census END statement and boundary samples, map §1.1, vendor field corroboration and scoped approval; epoch_ms_wall_shanghai_as_utc bound to source/column/window and Human A HOST approval'; HUMAN_GO_TIMING_sha=b89d99fc0fabbad5dd1e6da4ff6f3368ab84d1c7afce71832ea9e405d7e270f7; R4j uses named encoding epoch_ms_wall_shanghai_as_utc (NOT bare epoch_ms); 1761211800000→09:30+08 via wall decode (zero arithmetic offset); gate=PASS |
| lake_identity | PASS | NOT_RUN | NOT_RUN | pinned minute_603196 -> E:\stock_data\stock\period=1m\dividend_type=none\symbol=603196_SH\data.parquet sha256=58879893f221bfe050b7a16029667c49fb65d8ec6f47592254e549374a577083 window_rows=2169; manifest previously unbound; vendor status export 2133 (Clock-trim #280) vs lake window 2169; exports do not establish lake equivalence — pin is configured lake bytes only |
| freeze_recipe_attestation | PASS | NOT_RUN | NOT_RUN | loader_attempted=True recipe=D:\exports\b_l2_01_4090_r4j_20261001\recipe_attempt\recipe.json recipe_sha256=18861ec3b22ac09370f11474dd1243d6474ae6a87cab94269e7a3ff3b2f572c9 attestation.complete=true attempted; CAM+#278+#279 wall encoding A + #280 status trim + #281 cent-align + #284 shares-scale v8 bound; bars.time=epoch_ms_wall_shanghai_as_utc; coverage_equal=True intervals=18 expanded=2133 derivation=merged_contiguous_same_day_segments_from_status_rows; error=None |
| native_api_vs_l1_api | NOT_RUN | NOT_RUN | NOT_RUN | freeze PASS but this GO stops at freeze; native↔L1 not auto-started (needs separate GO) |
| independent_spot_checks_capacity_expiry_t1_fee_mark | NOT_RUN | NOT_RUN | NOT_RUN | freeze PASS path reserved; this GO stops at freeze — oracles need separate GO |
| company_actions_empty_window_probe | PASS | NOT_RUN | 未覆盖 | ex_window_hits=0; probe only ≠ bl2_proof_v1; pack actions.proof complete used for actions gate |

## Artifacts

- Host root: `D:\exports\b_l2_01_4090_r4j_20261001`
- Host JSON: `D:\exports\b_l2_01_4090_r4j_20261001\probe_summary.json`
- Host MD: `D:\exports\b_l2_01_4090_r4j_20261001\HOST_B_L2_01_R4J.md`
- Bound packs: `D:\exports\b_l2_01_4090_r4j_20261001\evidence\attestation_packages` (copy of living attestation_packages after Phase1 tip-land; R3 living bak-then-overwrite)
- Recipe attempt: `D:\exports\b_l2_01_4090_r4j_20261001\recipe_attempt`
- Box mirror: `/workspace/handoffs/b_l2_4090_live_r4j_20261001/`
- No hybrid S4 outs written (NOT_RUN). Lake / SSOT / δ5 / JR G / merge untouched.

## Explicit non-claims

- Not lake PASS. Not fixture PASS reused as lake PASS.
- Not market executability. Not SSOT green R/S.
- Not invented available_at / ordinary_listing / 10% limits.
- Not halt-from-silence; status uses explicit suspendFlag bindings only.
- Not flipping human_go r4_authorized marker (remap field).
- Not native↔L1 parity; not independent oracle coverage.
- Catalog is not a ready recipe; account/commands + time-encoding reconciliation may still block.
- Bars.time uses named epoch_ms_wall_shanghai_as_utc only — FORBIDDEN bare epoch_ms / silent ±8h Clock rewrite.
- production_C=frozen; no δ5 / JR G / MatchCore / Fees / lake writes.
- Prior R4/R4b/R4c/R4d/R4e/R4f/R4g/R4h/R4i roots untouched; living packs bak-then-overwrite only.
- R4i freeze PASS / native / oracles NOT reused as this R4j PASS.
- This GO STOP AT FREEZE — native↔L1 and independent oracles NOT auto-run (need separate GO).
- No δ5 / JR G.

## Next ask

R4i harness: tip #281 cent-align transform v6 + double_repr_cent_quantize_v1 (intervals←trimmed status ~2133; no 14:57-15:00) + bars.time=epoch_ms_wall_shanghai_as_utc. This GO stops at freeze result — do NOT auto-start native↔L1/oracles. If freeze PASS → parent may authorize next. If BLOCKED: report gate/error verbatim; do NOT invent account/commands/10%/halt-from-silence; do NOT flip remap r4_authorized; do NOT silent ±8h Clock rewrite; do NOT overwrite prior R4/R4b/R4c/R4d/R4e/R4f/R4g/R4h; lake RO.


---

## Native <-> L1 (R4j GO native+oracles) — sidecar

- **Verdict: `PASS`** · issued 2026-10-01T11:12:24.356013+08:00
- memory asdict_equal=`True`
- hybrid status native=`success` L1=`success` api=`returned`
- artifact files=`12` · tree_sha256=`6ed13d1309696825b588ce4a7da5ad594893a21fa0de201bb3868c803af3007d` (byte-identical both sides)
- Sidecar: `native_l1/HOST_B_L2_01_R4J_NATIVE_L1.md` · probe `native_l1/native_l1_probe.json`
- Bound freeze pins unchanged (no re-freeze). R4i native NOT reused.

## Independent oracles (capacity / expiry / T+1 / fee / mark)

- **Verdict: `PASS`** · issued 2026-10-01T11:11:52.550342+08:00
- cells: {"capacity": "PASS", "expiry": "PASS", "t1": "PASS", "fee": "PASS", "mark": "PASS"}
- units scale: lake lots-at-rest x100 authorized_mapping disclosed (v8); recipe unit:shares
- uncovered: ["bilateral shared capacity with concurrent SELL in same bucket (only BUY R4-A present)", "end=expiry residual release path (order fully filled before expires_at; no Expired event)", "same-day BUY-then-SELL rejection (no SELL command in frozen batch)", "multi-fill cumulative fee differential path (only 1 fill)"]
- Sidecar: `oracles/HOST_B_L2_01_R4J_ORACLES.md` · probe `oracles/oracles_probe.json`
- R4i oracles NOT reused.

### Explicit non-claims (native+oracles GO)

- PASS != lake PASS / SSOT green / market executability
- No re-freeze; no delta5 / JR G; no MatchCore/Fees/Clock thaw; no lake writes
- r4_authorized stays false; no invented 10% / halt-from-silence
- Prior R4i tip 2685926/v6 native/oracles SUPERSEDED — not copied as this result
