# RB-14 snapshot provenance consume / ops contract (MIXED-a)

RB-14 is opt-in audit provenance only. It changes no inputs, economics, G2 cache
identity, keys, sidecars, hit/miss rules, CLI defaults or default outputs.

## As-built consumer contract

[G2](g2-minute-cache-identity-2026-09-28.md) and
`backtest/research/ashare_bars.py:minute_cache_identity` define the existing
`source_snapshot` field. `write_minute_cache` records it at the top level of the
cache's same-stem `.json` sidecar, alongside the complete identity fields and
cache metadata. The caller supplies a non-empty string via `source_snapshot=`;
otherwise G2 computes `shallow-v1:<sha256>` from root and immediate-child stat
records `[name, st_mode, st_size, st_mtime_ns]`, with children sorted by name.
The hash uses UTF-8 canonical JSON (sorted keys, compact separators, non-ASCII
preserved). It does not read bar content or traverse deeper partitions.

**Upstream producer contract: STUB.** No producer-side specification for the G2
caller token is present in this repository. G2 defines consumption, not an
upstream issuance protocol. RB-09's example token is illustrative. Explicit
caller/upstream tokens are opaque, self-reported provenance: no prescribed
prefix, revision syntax, issuer verification or content seal. Never fabricate
a token when absent. Neither explicit tokens nor shallow-v1 prove PIT
correctness, content equality, complete coverage, or an atomic frozen source.
Deep in-place repairs and metadata-preserving replacements can be undetectable
under shallow-v1, per G2. Token authenticity remains the caller's responsibility.

`backtest.research.snapshot_provenance.snapshot_provenance_tokens` accepts an
already-computed identity mapping or an explicitly selected existing JSON
sidecar path. It reads only that path, extracts only `source_snapshot`, and
reuses RB-09 identity mapping validation. Missing/null/blank tokens return `{}`
(unavailable). Invalid JSON, missing files, non-object input and invalid token
types raise; absolute host-path tokens are rejected under RB-09's existing
policy rather than rewritten. `resolver_identity` is a host path, not a snapshot
token, and is excluded. Unknown fields are ignored; extraction does not validate
full G2 identity or certify that a sidecar describes the bars consumed.

```python
from backtest.research.snapshot_provenance import snapshot_provenance_tokens
from bt_contract.run_manifest import build_bt_run_manifest

tokens = snapshot_provenance_tokens(selected_existing_sidecar)
manifest = build_bt_run_manifest(
    strategy="version6", dividend_type="none", config=config,
    input_tokens=tokens or None,
)
```

Select the sidecar belonging to the actual consumed cache, or retain the actual
identity mapping from the calling operation. Do not construct a new identity
just to populate provenance. No helper is imported or called by the simulate
hot path. No manifest or side artifact is written unless explicitly requested.
For absent tokens, omit `input_tokens` if preserving the default manifest shape
is required (RB-09 accepts `{}` but records an empty opt-in mapping).

## Operator runbook: upstream re-cuts

1. Obtain and retain upstream release/repair evidence, affected scope and a new
   opaque token. Producer issuance details remain STUB; do not invent certification.
2. Keep the source frozen for the run. For deep repairs, follow G2's existing
   requirement: change the caller's `source_snapshot=` token (never reuse across
   repairs), or have the upstream publication process update immediate partition
   directory mtime. Do not rely on shallow-v1 detecting deep content changes.
3. Use the existing caller API and existing `--rebuild-cache` / `--no-cache`
   procedures as appropriate. RB-14 adds no wiring or cache invalidation. Do not
   edit existing sidecars to make old cached data appear current. Keep prior run
   artifacts and their identities for audit; RB-14 performs no deletion/migration.
4. Explicitly extract provenance from the identity/sidecar actually used and pass
   it into RB-09's manifest. If unavailable, report unavailable; do not substitute
   a date, git revision, path, or freshly computed guess for a snapshot token.
5. Record the upstream evidence separately. A changed run identity proves only
   that recorded tokens differ, not that inputs were verified or PIT-correct.

## Stronger snapshot = MIXED(b), separate ticket

Content-addressed/frozen input selection, recursive lake hashing, producer seals,
verified immutable snapshots, new lake reads, input rewiring and stronger cache
invalidation would change the input contract. These require a separate MIXED(b)
ticket and authorization. This section is documentation only; RB-14 implements
none of them and no RB-15+ work.

## Validation boundary

Tests use tmp_path synthetic sidecars and in-memory identities only; no real
lake. They cover extraction, unavailable and invalid inputs, unchanged source,
RB-09 composition, the fixed simulate import fence and AST traversal bans.
