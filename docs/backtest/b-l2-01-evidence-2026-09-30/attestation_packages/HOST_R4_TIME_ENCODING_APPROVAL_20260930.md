# HOST R4 time encoding approval — 2026-09-30

- approval_id: `host_r4_time_encoding_approval_20260930`
- Decision: Human「开修」+ confirm「按 Kimi A 开 Codex」, 2026-09-30 Asia/Shanghai.
- Authority: byte-preserved `HUMAN_GO_TIME_ENCODING.md`, SHA-256
  `e605e3256be64943d8026e45c4ad3ce60c34663ad9ebb45ed99b5d3e86e66538`.
- This records the supplied Human implementation decision; it is not a new
  host run, independent lake verification, or a merge countersign.

## Approved source, column and window

Only `minute_603196`, raw minute partition `603196.SH`, column `time:int64`,
inclusive Shanghai dates `2025-10-23`–`2025-11-04`, with partition SHA-256
`58879893f221bfe050b7a16029667c49fb65d8ec6f47592254e549374a577083`.
The hash is the saved R4f host identity, not a local read or proof of lake PASS.
The host must verify these configured bytes again before a fresh freeze.

Encoding: **`epoch_ms_wall_shanghai_as_utc`**; timezone `Asia/Shanghai`;
label `END`; availability `bucket_end`. The existing END rule still maps
label t to `[t-1min,t)`; a 15:00 mark does not add an execution bucket.

Construct a UTC datetime from the integer milliseconds using integer
microseconds, read its wall components, then
`replace(tzinfo=None).replace(tzinfo=ZoneInfo("Asia/Shanghai"))`.
There is **no numeric offset correction**. For example, `1761211800000`
decodes to `2025-10-23T09:30:00+08:00`. The old `epoch_ms` instant decoder
continues to give `2025-10-23T17:30:00+08:00` for the same integer.

## Evidence and fail-closed binding

The separately pinned #278 timing census and materials map §1.1 establish
the END labels and Shanghai wall intent. The supplied Kimi advice reports
2169 window rows satisfying `time_ms == __index_level_0__` interpreted as
UTC wall, with zero violations. Its separately labeled host probe records
the 09:30 integer and partition identity. The R4f receipt records the
09:30–09:31 coverage failure under the old decode. These are saved reports,
not a probe run by this implementation.

`sources/time_encoding_approval.json` binds this decision, the original GO,
the census/map, Kimi advice and R4f receipt by individual byte hashes. Its
own byte hash is pinned in the loader. The timing claim must cite its saved
row, and the recipe must match its source ID/hash, column/type, symbol,
encoding/timezone/label/availability and covered window. Missing, replaced,
out-of-window or differently pinned evidence is rejected. Merely naming the
encoding is insufficient; other partitions/columns need another approval.

## Boundaries and follow-up

Transform **`bl2_source_transform_v5`** requires fresh implementation code SHA,
recipe, mark mappings and `attestation_scope` pins. R4f remains
`BLOCKED/NOT_RUN`; account/commands and other freeze gates still need host
review. Status/instruments/units/CAM proofs retain their existing meaning.
The 240-cell status grid and the 237-cell continuous execution grid remain
distinct; this approval does not authorize auction execution or grid changes.

**`r4_authorized=false`.** No R4g dispatch, lake rewrite, merge, Clock,
MatchCore, Fees, SSOT or production_C change is authorized. Review sequence:
Grok → Human「合」→ land → separate named Human「开 R4g」→ fresh host freeze.
No lake PASS, native↔L1 parity, oracle coverage or market executability claim.
