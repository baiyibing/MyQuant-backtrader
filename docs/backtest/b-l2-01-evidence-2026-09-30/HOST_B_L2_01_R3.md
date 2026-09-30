# HOST_B_L2_01_R3 — 4090 live receipt

- Issued: `2026-09-30T10:57:56+08:00` Asia/Shanghai
- Host: **newtest_4090** · tip `a268e11bc682cd1ae5a6672ab89091cea1abe937` · dirty=False
- Unit: **B-L2-01** · round **R3** · proposed window `20251023`–`20251104`
- Source: `OSKH_SOURCE_PARQUET_ROOT=E:\stock_data` (read-only)
- Label: 真实行情驱动的合成订单研究
- Transform: `bl2_source_transform_v3` · PR **#270**
- **Verdict: `BLOCKED/NOT_RUN`**

## Why blocked

1. volume_units_attestation: no independently pinned vendor field-semantics / named-authority source_declaration for minute volume units; bars themselves cannot be source_refs; amount/(close*volume)≈100 remains non-attestation heuristic; refusing to invent units attestation or rename heuristic to source_declaration
2. instrument_limits_facts: no independent tick/lot/reference/limit_up/limit_down fact table on host or nearby vendor dirs; 1d bars lack limit cols; float_shares lacks tick/lot/limits; ST vendors are ST-name lists not instrument facts; refusing to invent bare 10% limits or approved_derivation without pinned inputs+approved_rule_version+two issuers
3. halt_missing_facts_source: no bl2_status_v1 full symbol×session-minute grid with explicit missing/halted + proofs; ST vendor dirs (cninfo/qmt/wind) are ST status/names not halt/missing minute grids; zero-volume bars ≠ halted; absent source row ≠ auto-missing; refusing to invent halt-from-silence or false/false without explicit_status binding
4. freeze_recipe_attestation: blocked by prior gates; no lake RunInput frozen

## Progress vs R2

- Tip advanced `47abe4d` (#269) → `a268e11` (#270); transform `v2` → **`bl2_source_transform_v3`**.
- #270 registered volume/instrument/status packages + empty templates + tightened basis/binding; templates intentionally fail until filled.
- Host still cannot fill or freeze: no independent units declaration, no instrument tick/lot/limit facts, no halt/missing minute grid. Fail-closed (no invented facts).
- Window bars still present: **2169** rows across days `2025-10-23` … `2025-11-04` (9 sessions).

## Probe notes (not attestation)

- Minute partition: `E:\stock_data\stock\period=1m\dividend_type=none\symbol=603196_SH\data.parquet` schema={"time": "int64", "open": "double", "high": "double", "low": "double", "close": "double", "volume": "int64", "amount": "double", "__index_level_0__": "timestamp[ns]"}
- Partition mode viable: **True** (has_symbol_column=False)
- Volume heuristic amount/(close×volume): mean=99.9767 median=99.9987 frac≈100(±0.5)=1.00 — **not** attested; not source_declaration.
- Keyword search under lake (depth≤3): units=0 instrument=0 status=0 (all empty of usable materials).
- Instrument-like lake names: []; status-like: []; ST vendors: ['vendor_cninfo_st_status', 'vendor_qmt_st_names', 'vendor_wind_st_status']
- Daily limit-like columns for probe symbol: []
- float_shares schema: {'stock_code': 'string', 'FloatVolume': 'double', 'TotalVolume': 'double', 'name': 'string', 'updated_at': 'string'}
- ST schemas (not minute halt grids): {"vendor_wind_st_status/st_daily.parquet": {"trade_date": "timestamp[ns]", "code": "string", "is_st": "bool", "st_kind": "string", "name": "string"}, "vendor_wind_st_status/st_intervals.parquet": {"code": "string", "name": "string", "st_kind": "string", "start_date": "timestamp[ns]", "end_date": "timestamp[ns]", "reason": "string", "end_status": "string"}}
- Nearby vendor roots present: none
- Company-action probe ex_date_index hits in window: **0**
- Small interval proposal (doc only): `{"day": "2025-10-23", "proposed_intervals": [{"start": "2025-10-23T09:30:00+08:00", "end": "2025-10-23T09:32:00+08:00"}], "note": "2 continuous START minutes on one session; calendar still needs acquire/sellable/next BUY dates"}`
- 14:59 START candidate: `{"index": "2025-10-23 14:59:00", "time_ms": 1761231540000, "close": 23.830000000000002, "volume": 0, "note": "15:00 mark via START row at 14:59 if bars use START"}`
- Native API↔L1 and independent oracles: **NOT_RUN** (no frozen RunInput).

## Packages / evidence

- **No packages filled** from real host evidence. `evidence/` holds UNFILLED #270 template copies only:
  - `units.proof.template.json` → `D:\exports\b_l2_01_4090_r3_20260930\evidence\units.proof.template.json` sha256=`e7eba2e41daca2df…` filled=False
  - `instruments.template.json` → `D:\exports\b_l2_01_4090_r3_20260930\evidence\instruments.template.json` sha256=`5a36fbbf54067104…` filled=False
  - `instruments.derived.template.json` → `D:\exports\b_l2_01_4090_r3_20260930\evidence\instruments.derived.template.json` sha256=`c246a336f81bffbb…` filled=False
  - `instruments.proof.template.json` → `D:\exports\b_l2_01_4090_r3_20260930\evidence\instruments.proof.template.json` sha256=`8fee068c095ea1b7…` filled=False
  - `status.template.json` → `D:\exports\b_l2_01_4090_r3_20260930\evidence\status.template.json` sha256=`ad69a75790a069f9…` filled=False
  - `status.proof.template.json` → `D:\exports\b_l2_01_4090_r3_20260930\evidence\status.proof.template.json` sha256=`c172a9342ece4b25…` filled=False
- packages_filled: volume_units=null, instruments=null, status=null

## Per-cell table

| gate | source | parity | oracle | note |
|---|---|---|---|---|
| sync_tip | PASS | NOT_RUN | NOT_RUN | HEAD=a268e11bc682cd1ae5a6672ab89091cea1abe937 dirty=False identity.code_sha=a268e11bc682cd1ae5a6672ab89091cea1abe937 transform=bl2_source_transform_v3 |
| configured_source_root | PASS | NOT_RUN | NOT_RUN | OSKH_SOURCE_PARQUET_ROOT=E:\stock_data container_ok=True |
| proposed_window_bars_present | PASS | NOT_RUN | NOT_RUN | symbol=603196.SH window_rows=2169 days=9 |
| minute_parquet_partition_symbol_mode | PASS | NOT_RUN | NOT_RUN | vendor schema matches #269/#270 partition-mode expectation; columns.symbol={'kind':'partition'} would bind identity; has_symbol_column=False schema_matches_vendor=True |
| volume_units_attestation | BLOCKED | NOT_RUN | 未覆盖 | no independently pinned vendor field-semantics / named-authority source_declaration for minute volume units; bars themselves cannot be source_refs; amount/(close*volume)≈100 remains non-attestation heuristic; refusing to invent units attestation or rename heuristic to source_declaration |
| instrument_limits_facts | BLOCKED | NOT_RUN | 未覆盖 | no independent tick/lot/reference/limit_up/limit_down fact table on host or nearby vendor dirs; 1d bars lack limit cols; float_shares lacks tick/lot/limits; ST vendors are ST-name lists not instrument facts; refusing to invent bare 10% limits or approved_derivation without pinned inputs+approved_rule_version+two issuers |
| halt_missing_facts_source | BLOCKED | NOT_RUN | 未覆盖 | no bl2_status_v1 full symbol×session-minute grid with explicit missing/halted + proofs; ST vendor dirs (cninfo/qmt/wind) are ST status/names not halt/missing minute grids; zero-volume bars ≠ halted; absent source row ≠ auto-missing; refusing to invent halt-from-silence or false/false without explicit_status binding |
| freeze_recipe_attestation | BLOCKED | NOT_RUN | NOT_RUN | fail-closed: cannot freeze lake recipe/attestation without honest volume units + instrument facts + status grid + scope_hash=attestation_scope(recipe); TRANSFORM_VERSION=bl2_source_transform_v3; packages remain UNFILLED templates only |
| native_api_vs_l1_api | NOT_RUN | NOT_RUN | NOT_RUN | no frozen RunInput (recipe/attestation BLOCKED); hybrid S4 not attempted |
| independent_spot_checks_capacity_expiry_t1_fee_mark | NOT_RUN | NOT_RUN | NOT_RUN | no frozen source rows; oracles require frozen source not MatchCore |
| company_actions_empty_window_probe | PASS | NOT_RUN | 未覆盖 | ex_window_hits=0; probe only ≠ bl2_proof_v1 complete_no_company_actions |
| attestation_packages_fill | BLOCKED | NOT_RUN | NOT_RUN | evidence/ holds UNFILLED #270 templates only; packages_filled={'volume_units': None, 'instruments': None, 'status': None}; no real source materials to review |

## Artifacts

- Host root: `D:\exports\b_l2_01_4090_r3_20260930`
- Host JSON: `D:\exports\b_l2_01_4090_r3_20260930\probe_summary.json`
- Host MD: `D:\exports\b_l2_01_4090_r3_20260930\HOST_B_L2_01_R3.md`
- Host evidence (unfilled templates): `D:\exports\b_l2_01_4090_r3_20260930\evidence`
- Box mirror: `/workspace/handoffs/b_l2_4090_live_r3_20260930/`
- No recipe/sidecars frozen; no hybrid S4 outs written (NOT_RUN).
- Lake / SSOT / δ5 / JR G / merge untouched; R1/R2 export roots preserved.

## Explicit non-claims

- Not lake PASS. Not fixture PASS reused as lake PASS.
- Not market executability. Not SSOT green R/S.
- Not volume-units attestation from amount/close heuristic or renamed source_declaration.
- Not invented 10% limit bands or approved_derivation without pinned inputs.
- Not halt-from-silence status grid; not false/false without explicit_status.
- Not native↔L1 parity; not independent oracle coverage.

## Next ask

Human/bt: supply independently reviewable (1) vendor volume-units source_declaration for 1m bars, (2) daily tick/lot/reference/limit fact table or approved_derivation materials with two issuers, (3) full symbol×session-minute halt/missing status grid with proofs — then re-GO R4 fill/pin/freeze; do not invent 10%/halt-from-silence/lots-heuristic.
