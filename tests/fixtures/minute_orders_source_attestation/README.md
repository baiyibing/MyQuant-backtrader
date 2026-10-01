# B-L2-01 host-fillable templates

These are intentionally invalid, unfilled templates, not market facts. Unknown
values are `null`, proof refs are empty, and proof completeness is `false`.
Do not substitute 10% bands, lot guesses, or `false` halt flags to make them pass.
Instrument `available_at` and `ordinary_listing` remain null in both consumer
alternatives and the proof binding; `complete=false` remains unloadable even
after re-pinning. See the [R4 host checklist](../../../docs/backtest/note-l2-lake-source-ingress-b-l2-01-2026-09-29.md#931-r4-instruments-宿主补证清单2026-09-30)
for per-date historical availability, authoritative ordinary-listing coverage,
archived SSE rule/approval review, and second-issuer verification. Do not turn
the daqmt snapshot's `OpenDate` into historical listing coverage or invent 09:00.

Post-R3 (2026-09-30): host-side raw material drafts for filling these live in
[docs/backtest/b-l2-01-evidence-2026-09-30/](../../../docs/backtest/b-l2-01-evidence-2026-09-30/)
(see its README + [sweep note](../../../docs/backtest/note-b-l2-01-r3-evidence-sweep-2026-09-30.md));
they are drafts, not proofs, and R3 stays BLOCKED/NOT_RUN.

2026-09-30 scoped Human GO and six remapped drafts:
[attestation_packages](../../../docs/backtest/b-l2-01-evidence-2026-09-30/attestation_packages/README.md).
The former `603196.SH`, `20251023–20251104` `cross_source_ratio` exception
is **historical_superseded** by Human GO 2026-10-01. Transform v7 rejects it;
the living shares target remains incomplete (option A). These templates are
still unfilled, not facts. In transform v4 a `source_declaration` proof must reference a raw row
with `basis="source_declaration"` and `unit_declaration` matching
`column/kind/unit/shares_per_unit`; a label without that declaration fails.
The derived instrument package replaces the source-fact alternative and uses
two proof files; unresolved historical metadata remains null and incomplete.

| Artifact | Package / use |
|---|---|
| `units.proof.template.json` | `bl2_proof_v1`, subject `units`; exact source/column/incremental/unit/factor declaration |
| `instruments.template.json` | `bl2_instruments_v1`, one `source_fact` row per symbol/trade_date |
| `instruments.derived.template.json` | Alternative `approved_derivation` row; pinned inputs, approved rule and independent proof refs |
| `instruments.proof.template.json` | `bl2_proof_v1`, subject `instruments`; exact facts and effective/availability metadata |
| `status.template.json` | `bl2_status_v1`, one row per symbol/session-minute |
| `status.proof.template.json` | `bl2_proof_v1`, subject `status`; exact booleans, interval, reason and issuer |

Copy and fill outside the repository and lake. Register every copied package,
proof and raw evidence source in the recipe with its own source ID, absolute
resolved path, exact schema and byte SHA-256. The filenames are suggestions;
source IDs are host-assigned and must agree in bindings, roles and claims.

For derived instruments, use `basis="approved_derivation"` in the instrument
proof, copy the full instrument row into `binding` except `proofs` and
`derivation.independent_verification`. Thus the binding includes
`derivation={"inputs":[...],"approved_rule_version":"..."}`. Create a second
instrument proof with a different issuer for independent verification. Both
proofs must cite all pinned inputs, bind the same result/rule, and appear in the
attestation instrument claim. Rule approval and source authority need host review.

Fill order, full field contracts, claim conclusions, validation API and R3 GO
boundary are in [ingress note §9](../../../docs/backtest/note-l2-lake-source-ingress-b-l2-01-2026-09-29.md#9-factsattestation-package-go2026-09-30).
Tests fill these shapes using fabricated values and verify rejection before
they are filled. Fixture PASS != lake PASS; no host certification or SSOT green.
The tests also re-pin otherwise filled packages with null/ill-typed/late
availability, non-true listing flags, incomplete proofs or mismatched bindings;
all remain rejected. Both derived proofs must be literally `complete=true` and
bind the same supplied metadata. Current remapped instrument packs remain BLOCKED.
