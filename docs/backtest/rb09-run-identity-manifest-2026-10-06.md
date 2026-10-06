# RB-09 run identity sidecar — 2026-10-06

H-RB-05 / RB-09 is **MIXED(a)**: opt-in audit metadata with **ZERO-DIFF economics**.
It extends `bt_contract/run_manifest.py`; there is no parallel manifest system.
Default simulation outputs, fixtures, baselines, HELP_LOCK, book order and cache
behavior remain unchanged. No simulator or CLI integration is added.

`build_bt_run_manifest` accepts optional keyword fields `book_rule_revision`,
`pool_identity`, `price_domain`, `input_tokens` and `environment`. All default to
`None`. Only supplied fields appear in the nested `run_identity` object; when
all are absent, the previous manifest shape and hashes are preserved, including
schema `myquant.bt-run/1`. An explicitly supplied empty mapping is recorded.

`run_identity_sha256` hashes that object using the existing canonical JSON bytes
(sorted keys, UTF-8). Mapping insertion order does not affect the digest.
`config_sha256` retains its existing config-only meaning. Identity values and
mapping keys must be non-empty strings; Path objects are rejected, not converted.
Use caller-provided POSIX relative identities or resolver identity strings, not
absolute host paths (POSIX, Windows and UNC absolute paths are rejected).
No lake, pool, cache or environment is auto-discovered.

```python
from bt_contract.run_manifest import build_bt_run_manifest, write_run_identity_sidecar

manifest = build_bt_run_manifest(
    strategy="version6", dividend_type="none", config={"flag": True},
    book_rule_revision="version6:rules-v1",
    pool_identity="pool/sha256:abc", price_domain="raw",
    input_tokens={"source_snapshot": "resolver:stock/period=1m:snapshot-abc"},
    environment={"python": "3.12", "pandas": "2.2"},
)
write_run_identity_sidecar("outputs/run-identity.json", manifest)
```

The caller chooses an existing output directory and explicitly invokes the
helper. It writes the supplied manifest as canonical JSON, without inspecting
inputs or changing output economics. `write_bt_run_manifest` also accepts the
new builder keywords through its existing forwarding interface.

These are caller assertions and opaque tokens, **not PIT proof or certification**.
A stable digest establishes recorded identity equality, not data availability at
signal time or reproducibility. Strict reproduce mode is future work; RB-10+
is outside this change.
