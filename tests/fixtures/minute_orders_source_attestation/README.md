# B-L2-01 host-fillable templates

These are intentionally invalid, unfilled templates, not market facts. Unknown
values are `null`, proof refs are empty, and proof completeness is `false`.
Do not substitute 10% bands, lot guesses, or `false` halt flags to make them pass.

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
