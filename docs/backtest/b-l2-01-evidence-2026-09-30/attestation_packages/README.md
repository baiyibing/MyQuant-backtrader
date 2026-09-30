# B-L2 remapped drafts — 2026-09-30

These six consumer/proof files remap saved evidence from
[OSkhQuant1.3 #1111](https://github.com/baiyibing/OSkhQuant1.3/pull/1111), fixed commit
[`ec19fd6f69a52f93aa9870ad582f0173df8963f4`](https://github.com/baiyibing/OSkhQuant1.3/tree/ec19fd6f69a52f93aa9870ad582f0173df8963f4/docs/evidence/b_l2_01_4090_r3_20260930),
against research tip `cff5ad619b284141668dcebb4bb86c713a848bfa`.
They are drafts for a later, separately authorized 4090 copy into
`D:\exports\b_l2_01_4090_r3_20260930\evidence\`; this PR does not perform that copy.
**R3 stays BLOCKED/NOT_RUN; R4 needs separate Human「开 R4」; production_C=frozen.**
No lake writes, MatchCore/Fees/SSOT changes, execution, or host certification.

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

## Six artifacts and source IDs

| Artifact | Schema / intended source ID | Template mapping |
|---|---|---|
| [units.proof.json](units.proof.json) | `bl2_proof_v1` / `proof_units` | units proof; explicit ratio exception |
| [instruments.json](instruments.json) | `bl2_instruments_v1` / `instruments` | **derived** template; 9 supplied daily rows |
| [instruments.proof.json](instruments.proof.json) | `bl2_proof_v1` / `proof_instruments_sse` | instrument proof; SSE rule source |
| [instruments.wind.proof.json](instruments.wind.proof.json) | `bl2_proof_v1` / `proof_instruments_wind` | second instrument proof; Wind daily limit source |
| [status.json](status.json) | `bl2_status_v1` / `status` | canonical 240 × 9 minute rows |
| [status.proof.json](status.proof.json) | `bl2_proof_v1` / `proof_status` | exact per-minute bindings |

The source-fact instrument template is an alternative, not another required
package: these inputs are explicitly an `approved_derivation`. Both instrument
proofs bind the same inputs, rule version and output values; the Wind proof is
listed in `independent_verification`. The source issuer labels identify material,
not signatures by SSE/Wind on these remapped JSONs. Wind's nine daily rows verify
18/18 supplied limit values; its CSV hash is
`31f8461a4ae7aca352db35648c0d7c60e476597b259bfecc03c9807c9f3a048b`.
The 2026-09-30 daqmt instrument-detail snapshot is corroboration only.
No default 10% calculation is performed by this remapper or the loader.

**Instrument blockers remain explicit:** #1111 does not supply a historical
`available_at`, authoritative ordinary-listing coverage, or an archived SSE rule
plus approved applicability/rounding/exception review. `available_at` and
`ordinary_listing` stay `null`; both instrument proofs stay `complete=false`.
The rule-version string is copied without inventing an approval. These drafts
therefore intentionally fail the loader's completeness/availability gates.
The remaining fields are mapped from the supplied daily rows; effective dates
are each row's trade date, not evidence collection dates. A pre-open timestamp
must not be fabricated to obtain PASS. The host must supply the missing evidence,
update both bindings and freshly pin all changed bytes before any future load.

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

[inputs.json](inputs.json) pins twelve saved #1111 inputs. Git LF bytes differ
from original Windows CRLF bytes for daqmt artifacts. Both verified hashes are
recorded explicitly; `read_inputs` accepts only one of those exact hashes and
verifies newline-only equivalence. It does not accept arbitrary normalized data.

| Raw input | #1111 host SHA-256 | Git LF SHA-256 |
|---|---|---|
| daqmt 1m | `0404c9deddd777297d7c1258bea196854d0ff93560736ddeba1c182a6a8b84b0` | `2402104c7a02381c634257934ae31bd613d0bcdec537b4c226e1ae9a57bc703b` |
| daqmt 1d | `7f87dbcee6baaa8ebfb3e6b75940ccc821adc417735ff1b972609ecf899d367b` | `2630292798ad475678d09fb63e5ff7d0d8fcb3c66ab7e6b9cbd5f6ade2a1594d` |
| ratio table | `ccb1bd575f5e4fe7f8846a8e753933a2e08281ebc15d0509d79e658a4ad762ba` | `07591611041c21561d67c4908e64f8713b82dd67e7c0a404311749eb1b9a66f6` |
| zero-volume rows | `e974fa22d58c6596b61f3a765f798419a3ffc39bd45acb877f4478190cdc8643` | `992e00c523ca0479f70ff6fc9caa171ec062e0b95c94aace97ac53b12974d405` |
| THS daily | `6a7effd00a0d1d3533b5adb820644d57f19605c7d9cf9b9276c82f207a5fbf05` | same |

Raw originals remain with #1111 / the host. `sources/*.json` are pinned row
excerpts with original paths, commit, hashes, and extraction descriptions. CSV
values remain strings and row indices are zero-based excluding the header.
The minute excerpt keeps only datetime/time/volume/suspendFlag, preserving all
2,169 row positions. The loader accepts JSON/Parquet, so proof `source_refs`
point to these JSON excerpts, not unsupported CSV descriptors. Each excerpt has
its own schema and byte hash in [manifest.json](manifest.json).

With explicit approved Python and local copies of the pinned inputs:

```bash
"$OSKH_MERGE_PYTHON" docs/backtest/b-l2-01-evidence-2026-09-30/attestation_packages/remap.py \
  --source-dir /path/to/saved/src1111_tree --human-go /path/to/HUMAN_GO.md --check
```

`--output-dir /new/offline/directory` writes a new directory instead of checking;
existing destinations are rejected. No network, market download, resolver, lake
write, or research runner is called. Checked-in compact JSON retains every
minute row, so no generator execution is necessary just to review the bundle.

Later, after separate authorization, the host must review and fill the blockers,
copy the files, and translate catalog paths into resolved absolute sidecar paths.
Register every artifact's exact schema/hash/source ID. `claims.units.proofs` uses
`proof_units`; instruments uses both `proof_instruments_sse` and
`proof_instruments_wind`; status uses `proof_status`. Keep any source-ID changes
synchronized across bindings, inputs and claims, then re-pin. Register the actual
minute partition separately through the existing resolver. Other claims,
calendar, marks, actions, account, commands and full recipe/attestation freeze
are still required; this catalog is not a recipe or an attestation.

The validator change is `bl2_source_transform_v4` (package IDs remain v1).
Ratio evidence requires the explicit basis, pinned structured Human marker,
exact approved symbol/window/volume column/factor and four distinct raw sources.
For `source_declaration`, the referenced raw observation must now contain
`basis="source_declaration"` and a `unit_declaration` object matching
`column/kind/unit/shares_per_unit`. A label alone or this ratio evidence relabeled
as a declaration fails. Existing bar-alias independence checks remain active.
Saved statement checks do not certify authenticity or confer lake PASS.

Do not merge this PR without Human「合」. Merge does not authorize R4.
