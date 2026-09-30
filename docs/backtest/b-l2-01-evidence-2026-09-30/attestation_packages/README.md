# B-L2 remapped drafts — 2026-09-30

The original six consumer/proof files remap saved evidence from
[OSkhQuant1.3 #1111](https://github.com/baiyibing/OSkhQuant1.3/pull/1111), fixed commit
[`ec19fd6f69a52f93aa9870ad582f0173df8963f4`](https://github.com/baiyibing/OSkhQuant1.3/tree/ec19fd6f69a52f93aa9870ad582f0173df8963f4/docs/evidence/b_l2_01_4090_r3_20260930),
against research tip `cff5ad619b284141668dcebb4bb86c713a848bfa`.
They are drafts for a later, separately authorized 4090 copy into
`D:\exports\b_l2_01_4090_r3_20260930\evidence\`; this PR does not perform that copy.
**R3 stays BLOCKED/NOT_RUN; R4 needs separate Human「开 R4」; production_C=frozen.**
No lake writes, MatchCore/Fees/SSOT changes, execution, or host certification.

R4 fix update (Human「开修」, 2026-09-30): the separately authorized R4 host run
on tip `5b4ef3e` returned **BLOCKED/NOT_RUN**. Its original receipt is unchanged.
This fix removes bare JSON floats from remapped sources and tests the host-fill
contract; it does not authorize another host run or 4090/R5. The stored remap
marker and manifest retain `r4_authorized=false`; `production_C=frozen`.

R4 instruments host fill (2026-09-30, Human-selected available_at convention (a)):
the four §9.3.1 evidence groups are now supplied and pinned — the archived SSE
trading rules fulltext and clause excerpts (OSkhQuant1.3 PR #1112, commit
`d0edd384e9bd7fc0029b380e8850920539c46a95`, directory
`docs/evidence/b_l2_r4_host_materials_draft_20260930`), the Human decision record
[HOST_R4_INSTRUMENTS_APPROVAL_20260930.md](HOST_R4_INSTRUMENTS_APPROVAL_20260930.md)
(pinned by bytes SHA-256 in [inputs.json](inputs.json)), per-day `available_at`
under the approved T-1 post-close archive convention, and approved
`ordinary_listing=true`. Both instruments proofs are `complete=true` with
bindings identical to the consumer rows. **The approval record awaits baiyibing
countersign before merge. `r4_authorized` stays `false`; the host recipe,
configured lake identity/coverage and a fresh freeze remain separate prerequisites.**
The subsequent CAM fill below supplies the calendar/actions/marks evidence.

R4 calendar/actions/marks host fill (2026-09-30, Human **「四格全批，开 packs」**):
this packs knife builds on #276 baseline `c69f4bcc487608e8ff75e090526e50d116a4bc0a`
and pins [OSkhQuant1.3 #1114](https://github.com/baiyibing/OSkhQuant1.3/pull/1114)
at `42d066b81a083be49881f0dd8c5ab53ed4f422f6`, directory
`docs/evidence/b_l2_r4_cam_host_materials_draft_20260930/`.
The [CAM approval record](HOST_R4_CAM_APPROVAL_20260930.md) records the four-cell
decision and awaits baiyibing countersign before merge. The supplied
[HUMAN_GO_CAM.md](HUMAN_GO_CAM.md) is byte-preserved, SHA-256
`e15c79acde154bd7163208f2bf0a156737a9f908ed3fb9f41b87b64d42c13feb`;
it does not overwrite the units GO. Instruments/status/units consumer and proof
bytes, and all their existing source excerpts, remain unchanged from #276.
**`r4_authorized=false`; this approval is packs only, not「开 R4」.**

## Human exception and units

The byte-preserved [HUMAN_GO.md](HUMAN_GO.md) was supplied at
`/workspace/handoffs/b_l2_remap_r4_20260930/HUMAN_GO.md`:

> 人裁：①量单位接受直接对账（basis=cross_source_ratio），然后 remap

The user scopes that exception to `603196.SH`, inclusive `20251023–20251104`,
unit **手**, **100 shares per unit**, **incremental**. Its structured marker is
[sources/human_go.json](sources/human_go.json); the original document SHA-256 is
`bb287dfe9e2559e9fe05abb7401a636aa6596524cfb79ffa34a4f3ff884c2afe`.
The marker records the user-scoped exception; it is not a vendor declaration or
R4 authorization. The original #1111 `source_declaration` label is deliberately
corrected to `cross_source_ratio`. Vendor-doc absence remains quoted in limitations.

Eight daily ratios equal 100. On 2025-10-23, THS is **100 shares lower** than
daqmt daily volume ×100 (ratio 99.99685336689743). This difference is preserved.
All nine full-day minute sums equal daily volume, **including the 09:30 bars**.
The proof binding uses the existing loader enum `unit="lots"` for 手; factor 100
is explicit. No amount/close/volume inference is used.

## Consumer/proof artifacts and source IDs

| Artifact | Schema / intended source ID | Template mapping |
|---|---|---|
| [units.proof.json](units.proof.json) | `bl2_proof_v1` / `proof_units` | units proof; explicit ratio exception |
| [instruments.json](instruments.json) | `bl2_instruments_v1` / `instruments` | **derived** template; 9 supplied daily rows |
| [instruments.proof.json](instruments.proof.json) | `bl2_proof_v1` / `proof_instruments_sse` | instrument proof; SSE rule source |
| [instruments.wind.proof.json](instruments.wind.proof.json) | `bl2_proof_v1` / `proof_instruments_wind` | second instrument proof; Wind daily limit source |
| [status.json](status.json) | `bl2_status_v1` / `status` | canonical 240 × 9 minute rows |
| [status.proof.json](status.proof.json) | `bl2_proof_v1` / `proof_status` | exact per-minute bindings |
| [calendar.json](calendar.json) | `bl2_calendar_v1` / `calendar` | PMC subset; only `trading_dates` |
| [calendar.proof.json](calendar.proof.json) | `bl2_proof_v1` / `proof_calendar` | calendar; `complete_trading_calendar` |
| [actions.json](actions.json) | `bl2_actions_v1` / `actions` | approved coverage; `events=[]`, `complete=true` |
| [actions.proof.json](actions.proof.json) | `bl2_proof_v1` / `proof_actions` | actions; `complete_no_company_actions`; `result.rows=[]` |
| [marks.json](marks.json) | `bl2_marks_grid_v1` / `marks` | host-facing approved grid document; **not a loader role** |
| [marks.proof.json](marks.proof.json) | `bl2_proof_v1` / `proof_marks` | marks; `raw_contemporaneous_grid` |

The source-fact instrument template is an alternative, not another required
package: these inputs are explicitly an `approved_derivation`. Both instrument
proofs bind the same inputs, rule version and output values; the Wind proof is
listed in `independent_verification`. The source issuer labels identify material,
not signatures by SSE/Wind on these remapped JSONs. Wind's nine daily rows verify
18/18 supplied limit values; its CSV hash is
`31f8461a4ae7aca352db35648c0d7c60e476597b259bfecc03c9807c9f3a048b`.
The 2026-09-30 daqmt instrument-detail snapshot is corroboration only.
No default 10% calculation is performed by this remapper or the loader.

**Instrument blockers filled 2026-09-30 (host fill):** #1111 did not supply a
historical `available_at`, authoritative ordinary-listing coverage, or an
archived SSE rule plus approval. Those four groups are now pinned and bound:
`sse_rule` is re-pointed from the #1111 URL/paraphrase to the archived rules
fulltext (292 line rows); `clause_excerpts` carries the clause excerpts and
effective-interval delimitation; `host_approval` carries the Human decision
record. `available_at` follows the Human-selected convention (a): `T-1` trading
day `15:30:00+08:00` post-close archive, anchored to the pinned daily archive
rows (daqmt preClose chain; first row's T-1 = 2025-10-22 close 23.36 in the
pinned kimi daily CSV, now also a derivation input via `ths_daily`). The
2026-07-06 after-hours rule change postdates the window and is not an anchor.
`ordinary_listing=true` is the Human-approved window coverage (non-ST, zero
corporate actions, no 3.4.13 first-day exception). `approved_rule_version`
keeps its string and now has an approval record behind it. Both proofs bind all
seven derivation inputs plus the `daqmt_detail` corroboration, and remain
distinct issuers. The CAM evidence is now filled below; the host recipe, lake
identity/coverage and the fresh freeze are **still** separate prerequisites —
follow the [host checklist in ingress §9.3.1](../../note-l2-lake-source-ingress-b-l2-01-2026-09-29.md#931-r4-instruments-宿主补证清单2026-09-30)
for what remained, and §9.5 for the freeze order. **Fixture PASS ≠ lake PASS;
`r4_authorized` stays `false`.**

## Calendar/actions/marks four-cell host fill

The [ingress contract](../../note-l2-lake-source-ingress-b-l2-01-2026-09-29.md)
§§3 / 3.2 / 3.3 / 9 govern this fill. All three proofs use the existing §9.1
six-field envelope, `complete=true`; calendar/marks have non-empty observations
with exact excerpt row indexes. Actions retains the required empty result rows.
Instruments-only binding and second-issuer requirements are not added to CAM.

1. **Calendar + first_day approved:** `first_day=2025-10-23`, with no earlier
   initial-lot acquisition. Ten ordered unique PMC dates cover the nine execution
   days and next possible BUY day **2025-11-05**. The two archived SSE notices
   anchor the calendar; the census is corroboration only, never an inference
   that presence of a bar makes a trading date.
2. **Actions coverage + events=[] approved:** the economic coverage statement
   is `[2025-10-23,2025-11-04]`. Four sources support it: ex_date_index zero
   matches, cninfo 77 announcement titles, the preClose chain without adjustment,
   and constant adj_factor. cninfo's wider **search** window is
   `2025-06-01..2025-12-31`, not a wider no-events assertion. Contract §3.2 says
   “`ex_date_index/adj_factor` 的 hash 只证明身份；无行、因子未变或源缺失均不单独证明无事件。”
   The saved multi-source coverage statement and Human approval support the
   empty events; observations belong in source excerpts, not actions proof rows.
3. **Mark grid + row maps approved:** choose the first-day close as the independent
   spot-check and retain the mandatory final close, both explicitly priced in
   the CAM substrate table. `available_at=event_time` for each point.
4. **Packs knife only approved:** manifest/remap/evidence updates; no recipe
   freeze or R4 authorization. `r4_authorized` remains false.

| mark_id | event_time = available_at | zero-based absolute parquet row | raw close |
|---|---|---|---|
| `spot_20251023_close` | `2025-10-23T15:00:00+08:00` | `46753` | `23.89` |
| `final` | `2025-11-04T15:00:00+08:00` | `48681` | `22.96` |

[marks.json](marks.json) is a document schema emitted by the remapper and listed
in the manifest; the loader has no marks role. It records `time`/`close` columns,
prices, absolute rows and zero-based substrate excerpt lines. The host must
translate this grid into the existing recipe `mark_grid`, preserving the minute
source's symbol/time/close mapping and matching final `end_at`; no new loader
schema or price fallback is introduced. A 15:00 mark adds no execution bucket.

Parquet SHA-256 `58879893f221bfe050b7a16029667c49fb65d8ec6f47592254e549374a577083`
is a **saved identity note** from #1114. The substrate describes the parquet pin,
row table and census agreement supporting legal 15:00 marks. This remap does not
read parquet or census bytes: the manifest's `unbound_minute_source.sha256` stays
null, and exports do not establish configured lake equivalence. No lake PASS.

Source limitations are retained: ex_date_index's local `e8fe70ce…` snapshot is
different from R3's `93c264ed…` pin; unchanged preClose/adj_factor are supporting
observations only. cninfo analysis reviewed titles, not all PDFs. Three archived
responses preserve `totalpages=2` even though rows reconcile as 30+30+17 = 77
unique IDs and the last response has `hasMore=false`. Compact page excerpts
retain original array indexes and selected title/identity/time/URL fields; all
raw response bytes remain vendored and pinned. The archived materials keep their
DRAFT wording; approval is a separate record, not an edit of upstream evidence.
Name correction: **603196.SH 日播时尚 → 璞源材料**, not 亚士创能 (603378).

## Status and lake boundary

`start/end` are Shanghai `+08:00` one-minute buckets with END labels
09:31–11:30 and 13:01–15:00. Closing auction labels remain in this canonical
source grid; this is not approval of continuous-auction fill semantics there.
The nine 09:30 records are retained in
[sources/opening_auction.json](sources/opening_auction.json), outside the
2,160 status rows. Zero volume does not mean missing or halted: all 62 such rows
have explicit vendor `suspendFlag=0`, and their exact raw row indices are bound.
Semantics copied from #1111: 0 normal, 1 suspended, -1 resumption day.
The generator rejects absent minutes, duplicate labels and any changed flag;
it never derives a halt or non-halt from silence or announcement counts.

The vendor export used `fill_data=True`. Presence proves an exported record,
not an actual trade, an unfilled feed, or presence in the configured lake.
#1111 reports its local lake covers only 20251023, while exports cover nine days.
Host lake identity/coverage remains a separate gate. The units binding uses
intended minute source ID `minute_603196`; its actual resolver path/schema/hash
is deliberately **unbound** in this catalog. Do not substitute an export for lake
data or relabel this bundle as a ready recipe.

## Pins, reconstruction and later host registration

[inputs.json](inputs.json) pins twelve saved #1111 inputs, plus two host
materials from OSkhQuant1.3 PR #1112 (commit
`d0edd384e9bd7fc0029b380e8850920539c46a95`, directory
`docs/evidence/b_l2_r4_host_materials_draft_20260930`) under `host_materials`,
plus the bytes SHA-256 of the host approval record under `host_approval_sha256`.
`cam_host_materials` additionally pins all thirteen #1114 files, including its
manifest, three raw cninfo responses, seven calendar/actions/marks text sources,
README and host-fill form. `host_cam_approval_sha256` pins the CAM approval;
`human_go_cam_sha256` pins the supplied four-cell GO separately. None of the
#1111/#1112 pins or the existing units GO/approval hashes is replaced.
Git LF bytes differ
from original Windows CRLF bytes for daqmt artifacts. Both verified hashes are
recorded explicitly; `read_inputs` accepts only one of those exact hashes and
verifies newline-only equivalence. It does not accept arbitrary normalized data.
The two host-material markdown files are pinned by exact LF bytes only.

| Raw input | #1111 host SHA-256 | Git LF SHA-256 |
|---|---|---|
| daqmt 1m | `0404c9deddd777297d7c1258bea196854d0ff93560736ddeba1c182a6a8b84b0` | `2402104c7a02381c634257934ae31bd613d0bcdec537b4c226e1ae9a57bc703b` |
| daqmt 1d | `7f87dbcee6baaa8ebfb3e6b75940ccc821adc417735ff1b972609ecf899d367b` | `2630292798ad475678d09fb63e5ff7d0d8fcb3c66ab7e6b9cbd5f6ade2a1594d` |
| ratio table | `ccb1bd575f5e4fe7f8846a8e753933a2e08281ebc15d0509d79e658a4ad762ba` | `07591611041c21561d67c4908e64f8713b82dd67e7c0a404311749eb1b9a66f6` |
| zero-volume rows | `e974fa22d58c6596b61f3a765f798419a3ffc39bd45acb877f4478190cdc8643` | `992e00c523ca0479f70ff6fc9caa171ec062e0b95c94aace97ac53b12974d405` |
| THS daily | `6a7effd00a0d1d3533b5adb820644d57f19605c7d9cf9b9276c82f207a5fbf05` | same |

Git LF inputs are vendored under `tests/fixtures/bl2_attestation_remap_upstream/` for pytest `remap.py --check` (including the two
`sse_rule_archive/*.md` host materials and `cam_host_materials/` from #1114);
host originals remain with #1111 / #1112 / #1114 / the host. `sources/*.json` are pinned row
excerpts with original paths, commit, hashes, and extraction descriptions. CSV
values remain strings and row indices are zero-based excluding the header.
JSON fractional numbers are parsed as Decimal from the pinned source text and
recursively emitted as finite Decimal strings, including nested metadata in
`daqmt_detail` and `upstream_instruments`. No two-decimal quantization is applied
to these excerpts; integers, booleans and nulls retain their types. Upstream
input bytes/pins are unchanged; the regenerated excerpt hashes are in the manifest.
All package JSON is checked with the loader's `strict_json`. Fixing its Decimal
parse error does not make incomplete instrument proofs or attestations loadable.
The minute excerpt keeps only datetime/time/volume/suspendFlag, preserving all
2,169 row positions. The loader accepts JSON/Parquet, so proof `source_refs`
point to these JSON excerpts, not unsupported CSV descriptors. Each excerpt has
its own schema and byte hash in [manifest.json](manifest.json). Markdown
excerpts (`sse_rule`, `clause_excerpts`, `host_approval`) keep one UTF-8 line
per row with zero-based line indices.

With explicit approved Python and local copies of the pinned inputs:

```bash
"$OSKH_MERGE_PYTHON" docs/backtest/b-l2-01-evidence-2026-09-30/attestation_packages/remap.py \
  --source-dir tests/fixtures/bl2_attestation_remap_upstream \
  --human-go docs/backtest/b-l2-01-evidence-2026-09-30/attestation_packages/HUMAN_GO.md --check
```

`--host-approval` pins the approval record and defaults to the checked-in
[HOST_R4_INSTRUMENTS_APPROVAL_20260930.md](HOST_R4_INSTRUMENTS_APPROVAL_20260930.md).
`--host-cam-approval` separately pins the CAM record and defaults to
[HOST_R4_CAM_APPROVAL_20260930.md](HOST_R4_CAM_APPROVAL_20260930.md); its approval_id
marker is also required. An external `--source-dir` must stage the original
#1111 tree plus #1112 `sse_rule_archive/` plus #1114 `cam_host_materials/`.
`--output-dir /new/offline/directory` writes a new directory instead of checking;
existing destinations are rejected. No network, market download, resolver, lake
write, or research runner is called. Checked-in compact JSON retains every
minute row, so no generator execution is necessary just to review the bundle.

Later, after separate authorization, the host must review the countersigned
approval record, copy the files, and translate catalog paths into resolved
absolute sidecar paths.
Register every artifact's exact schema/hash/source ID. `claims.units.proofs` uses
`proof_units`; instruments uses both `proof_instruments_sse` and
`proof_instruments_wind`; status uses `proof_status`. Keep any source-ID changes
synchronized across bindings, inputs and claims, then re-pin. Register the actual
minute partition separately through the existing resolver. Calendar/actions roles
and claims now use `calendar`/`actions` and `proof_calendar`/`proof_actions`;
the marks claim uses `proof_marks`, with the approved document translated into
recipe `mark_grid`. Remaining claims (including timing), account, commands and
full recipe/attestation freeze still need host review and registration; this
catalog is not a recipe or a scoped attestation.

The validator change is `bl2_source_transform_v4` (package IDs remain v1).
The 2026-09-30 instruments and CAM host fills change evidence bytes only — the v4
validator/contract is unchanged, so the transform version is deliberately not
bumped (v3/v4 bumps tracked validator changes, not evidence fills).
Ratio evidence requires the explicit basis, pinned structured Human marker,
exact approved symbol/window/volume column/factor and four distinct raw sources.
For `source_declaration`, the referenced raw observation must now contain
`basis="source_declaration"` and a `unit_declaration` object matching
`column/kind/unit/shares_per_unit`. A label alone or this ratio evidence relabeled
as a declaration fails. Existing bar-alias independence checks remain active.
Saved statement checks do not certify authenticity or confer lake PASS.

Do not merge this PR without Human「合」. Merge does not authorize R4.
Remaining Human steps: **Grok review → Human「合」→ land packs on 4090 → Human「开 R4」**.
