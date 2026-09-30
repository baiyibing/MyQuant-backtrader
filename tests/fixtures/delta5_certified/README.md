# δ5 certified-real host shapes (unfilled)

These are interface templates, not market facts or attestation. The adjacent
`delta5_certified.py` builder creates **fabricated test data only**; never use its
assertions as host facts. B-L2 package IDs describe related evidence shapes, not
δ5 certification or B-L2 PASS. No host export is included here.

The independent CLI accepts `--recipe <absolute.json> --recipe-sha256 <hash>
--human-go <absolute.md> --human-go-sha256 <hash> --external-parent <absolute-dir>
--run-id <new-id> --participation-rate <explicit-rate|none|omitted>`.
It performs mapping preflight only. No engine run, N/H comparison, or lake PASS
is produced. Host certification and a separate 4090 Human re-GO remain required.

Recipe envelope (unfilled; loading this must fail):

```json
{
  "schema": "d5_certified_recipe_v1",
  "source": {
    "kind": "certified-real",
    "schema": "d5_certified_real_source_v1",
    "publisher": null,
    "snapshot_id": null,
    "evidence_id": null,
    "evidence_origin": null,
    "pool_origin": null,
    "raw_sources": [],
    "materials": [],
    "packs": {"units": null, "availability": null, "no_events": null,
              "halt": null, "context": null}
  },
  "parameters": null
}
```

The manifest also explicitly supplies the contract's unit/price/incremental/
float-representation, time label/encoding/interval/publication rule, full window/
reference/calendar/sessions, no_events, instruments, status and pool fields.
There are no inline minute/daily frames, native inputs, or fill oracles.
`evidence_origin` is `host_supplied` or `fabricated_test`; it must match every
evidence document and pack. Software checks structure and pins, not issuer
authority or whether a narrative is true. Relabeling a heuristic is not attestation.

Every raw source, material and pack has this pin (unfilled):

```json
{"path": null, "schema": null, "size": null, "sha256": null}
```

Raw sources additionally require a unique `id`, `period` (`1m`/`1d`), `format`,
`representation=raw_source_records`, `transformations=[]`, and explicit one-to-one
`columns`. Minute columns are symbol/timestamp/volume/open/high/low/close; daily
columns are symbol/day/open/high/low/close (`day` is YYYYMMDD text). ISO timestamp
text or physical datetime columns support local_wall/utc_instant/utc_wall; other
encodings fail closed. Paths must be in configured resolver `dividend_type=none`
partitions. Parquet `schema` is the exact column-name→Arrow-type mapping; reads
use pinned bytes before any cleaning. JSON raw records use `d5_raw_records_v1`
with publisher, snapshot_id, origin and rows. All files are checked before/after
reading and again after mapping. Out-of-window records are selected by physical
close; in-window duplicates, disorder, missing buckets and unexpected days fail.

Evidence package template (unfilled; every subject needs an independent file):

```json
{
  "schema": "d5_evidence_pack_v1",
  "package_id": null, "subject": null, "origin": null,
  "issuer": null, "issued_at": null, "summary": null,
  "complete": false, "limitations": [], "scope_hash": null,
  "basis": null, "binding": null, "refs": []
}
```

`scope_hash` pins the manifest excluding materials/packs. Refs are material ID
plus zero-based row. Each `d5_source_document_v1` material contains origin,
document_type, issuer, original_reference, extraction_method, and nonempty rows
with subject/basis/scope_hash/observation/binding. Host retains and audits the
originals; pinned excerpts must match concrete pack bindings exactly. A bar file
or same-byte alias cannot serve as independent evidence. Missing/null/unfilled
fields, empty refs, stale scopes or incomplete packages fail.

| Subject | Basis / source document type | Concrete binding |
|---|---|---|
| units | source_units_declaration / publisher_field_semantics | Every minute file/hash/physical column; raw incremental shares; exact representation, no conversion |
| availability | publication_records / publication_log_or_contract | Every selected raw source/row/symbol/timestamp → explicit begin/end/publication/zero-or-positive state; close or mtime alone is insufficient |
| no_events | corporate_action_coverage / corporate_action_registry_coverage | Exact symbols, reference→end, empty events and evidence ID |
| halt | explicit_halt_missing_grid / halt_and_missing_registry | Full symbol×session×240-close-key grid; missing/halted booleans, reason and explicit missing rule; no silence/ST inference |
| context | calendar_instrument_and_mapping_facts / calendar_listing_mapping_coverage | Calendar, lifecycle/name/ordinary/non-ST facts, pool origin, raw daily identity/reference/marks, clock/interval mapping and existing book_limit_prices parameters |

No default rate, limit percentage, lot size, volume conversion, availability or
halt fact is supplied. `source_certification=verified` means only
`certification_scope=structure_and_pins_only`. `real_lake_run=NOT_RUN`, all N/H
cells `NOT_RUN`, and `no_ssot_compare_authorization` remain unchanged.
