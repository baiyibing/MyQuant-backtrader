# B8 signal-bundle / BT provenance infra switch

BT's existing signal and run-manifest imports now delegate to MyQuant-infra.
The host keeps signal selection, strategies, training, research orchestration,
and execution policy. Provenance records supplied fee labels and inputs; it
never calculates fees or discovers training, signal, or market-data inputs.

Branch: `feat/b8-signal-bundle-infra-switch-20261105`.
Base: `origin/master` at `a13b0f2cf9142c36991e0de099ef238ebb382a56`
(includes B7 #571). GitHub `master` was independently confirmed at this SHA.
This is an independent draft PR against `master`, with no B3 #568, B4 #569,
B5 #570, or B6 #573 commits stacked. Open only; hotmail owns merging.

## Pin and facade boundary

`git ls-remote` confirmed infra `main` at
`3c377e9718e811112993579b6d91a603395db699` on 2026-11-06; it had not
moved from the requested tip. `requirements-infra.txt` bumps the optional pin
from `7d48c4e310f9636cad9c3e544db1766025db4e3c` to that SHA and retains
the D4/B2, K18, and B7 notes.

| Host facade | Existing infra implementation |
| --- | --- |
| `bt_contract.signal_bundle.SCHEMA` | Same literal `myquant.signal-bundle/1`, available without infra |
| `canonical_json_bytes`, `validate_signal_bundle`, `build_signal_bundle` | `myquant_infra.contracts.signal_bundle` |
| `build_bt_run_manifest`, `validate_bt_run_manifest`, `write_bt_run_manifest`, `write_run_identity_sidecar` | `myquant_infra.artifacts.provenance` BT dialect |
| `run_manifest.canonical_json_bytes` | Same signal-bundle facade; infra provenance reuses the same canonicalizer |
| Existing `_identity_mapping` compatibility helper | Existing infra helper, preserving the snapshot-provenance caller and its validation |
| `common.infra.pool_csv` primitives | Existing `myquant_infra.reference_data.pool_csv` twin when installed |

The manifest builder retains its signature and `git_commit="UNKNOWN"` default.
The writer passes `repo_root=Path(__file__).resolve().parents[1]` to infra so an
omitted commit still captures BT's repository, even from another working
directory. An explicit commit bypasses Git collection. Sidecar writing never
collects Git. BT still emits `myquant.bt-run/1`; infra's separate MQ
`SCHEMA_ID = "myquant.run-manifest/1"` is not substituted for it.

Pool CSV has an existing infra twin, verified to have the same executable AST
as the original host primitives. With infra installed the facade re-exports
all four original objects, including `PoolDuplicateCodeError`, preserving
exception identity across callers. Without infra it retains the existing
non-hashing parser so public pool readers remain usable. This fallback has no
canonical JSON or provenance hashing implementation. Code normalization,
same-day scope, filtering, ranking, and whether to reject duplicates stay in
the host callers. No pool API was invented in infra.

## v1 hash preservation evidence

Before replacing the host implementations, four bundles were signed and
validated by the original BT canonicalizer/validator; three manifests were
built by the original BT builder. Each matched infra's complete output and
canonical bytes. The executable AST of the manifest builder, config
normalizer, identity validators, and sidecar writer also matched infra.
Only the existing writer's source-repository choice needs a host adapter.

The captured inputs, expected dictionaries, bundle/calendar/config/identity
hashes, and complete-file digests live in
`tests/fixtures/b8_v1_contracts.json`. Its SHA-256 is
`f3487a57d395a69abfa92d05d4bb7895122b3bcfe323472342be18b2e6d30fea`.
New tests compare the switched facade and infra against these frozen values,
including writes, rather than merely comparing two aliases of the same code.

SHA-256 of the complete canonical JSON bytes, including final LF:

| Fixture | Original BT = infra = switched facade |
| --- | --- |
| Empty bundle | `faec92e983f9314d117e2fd998e0ef3f3b36cad2edfb92b0895eb3666adc8d0e` |
| Unproven bundle | `262ab82358cbed16ee03271ce813a0862aa0860cfe43dcb34a6fee27b72486be` |
| Declared multi-session bundle, reversed input order | `41a39e0f511148f682d222c2e766b945d52ac19ff9b37e08167ae31c1fc1d15f` |
| Identity-policy bundle | `d199a3e2cf0d6dde33200f5fe7c73c4953f02cd895128d89020c2b613e71d420` |
| Minimal BT manifest | `fa13aa3c5809317fac80ce47f57e9dfaee3cc4db0a7c8a25ebafd4c72fd540a5` |
| BT manifest with nested Paths/tuple, Unicode, artifact digests, QLIB fee label, cap, and identity | `c820d7d40faf03898cf37f9f84316a028c3af9ce3b6d6f167fe0431400259132` |
| BT manifest with empty identity maps and zero participation | `abd4b34b16863561c74885854c550f92c42d24b5ac9ac544beec7fa58925aed9` |

The v1 schema file is byte-for-byte unchanged and matches infra's copy:
`5464b038ac827969647f71d68041a732581e74859597f03d4b8b128cb1240f38`.
Sorted keys, compact separators, UTF-8 without BOM, non-finite-number rejection,
one final LF, config normalization, and existing digest fields are preserved.
There is no host canonicalization or hashing fallback. Infra additionally
rejects blank/nonexistent `files_root` explicitly before file verification;
this does not alter serialized data or hashes.

## Optional dependency and public CI

`bt_contract`, `bt_contract.signal_bundle`, and `bt_contract.run_manifest`
import without private infra. Canonicalization, bundle validation/building,
and manifest features lazily require it and raise an install hint naming
`requirements-infra.txt`. Missing submodules, missing symbols, and broken
transitive imports in installed infra propagate; they do not select a fallback.
The pool fallback likewise applies only to an absent top-level package.

Public requirements and CI still do not install private infra. Infra-dependent
contract/provenance tests use `pytest.importorskip`; public schema, import
fences, CLI help, default artifact output, manifest opt-out, and pool tests
continue executing. CLI defaults remain unchanged: default-on manifest
emission now requires the optional infra pin, while `--no-run-manifest` uses
the existing opt-out. Output-routing tests explicitly opt out; tests that
assert manifest contents require infra. No CLI/HELP_LOCK change is made.

## Validation

Interpreter: `/workspace/vanna312/bin/python` (Python 3.12.14, resolved from
`OSKH_MERGE_PYTHON`). With-infra runs use the clean, exact-tip source checkout
on `PYTHONPATH`; the shared installation is not changed. Tests use only
temporary synthetic files. A runner blocks socket connections in both modes
and blocks every `myquant_infra` import in public mode. New subprocess checks
also block infra and sockets explicitly, including daily/minute `--help`.

Focused command (with the pinned infra installed or on `PYTHONPATH`):

```bash
"$OSKH_MERGE_PYTHON" -m pytest -q -p no:cacheprovider \
  tests/test_bt_signal_bundle_contract.py tests/test_bt_run_manifest.py \
  tests/test_require_signal_bundle.py tests/test_b8_signal_bundle_infra_switch.py \
  tests/test_rb09_run_identity_manifest.py tests/test_rb14_snapshot_provenance.py \
  tests/test_csv_pool.py tests/test_pool_duplicate_codes.py \
  tests/test_stock_code_pool_duplicates.py tests/test_batch4_pool_duplicate_errors.py \
  tests/test_pool_file_compare.py tests/test_csv_daily_outdir.py \
  tests/test_csv_minute_participation.py tests/test_csv_analysis_identity_metadata.py
```

- Focused suite above: **229 passed with infra**;
  **156 passed, 73 skipped without infra**.
- Additional B2/K18/B7 compatibility suites
  (`test_oskh_data_bars_infra_switch`, `test_oskh_data_infra_switch`,
  `test_hithink_artifact_infra_switch`, `test_hithink_incremental`,
  `test_corp_actions_economics_gate`): **131 passed, 1 failed with infra**;
  **68 passed, 64 skipped without infra**.
- The additional failure is
  `test_cache_roundtrip_pointer_rotation_and_invalidation`: the unchanged
  host `oskh_data/cache_port.py:186` calls `setex`, but the unchanged test's
  `FakeRedis` only implements `get`, `set`, and `delete`.
  Exact failure: `AttributeError: 'FakeRedis' object has no attribute 'setex'`.
  Reproduced on an isolated archive of untouched host `a13b0f2` with the
  prior infra pin `7d48c4e`: **1 failed** identically. No Redis connection
  was attempted. This pre-existing test-double issue is outside B8.
- Ruff passed for `bt_contract` and the new B8 tests; `git diff --check` passed.
- All six pre-pip contract/path/economics/DuckDB gates passed, along with book
  admission, baseline admission, book capability classification, and minute
  classification. UTF-8 without BOM and zero NUL bytes verified for changes.
- Full repository pytest was not run. Remote public CI status is reported on
  the draft PR; local results above do not claim a full green CI run.

There are no infra source changes, lake rewrites, production cutovers, deploys,
training/live runs, trading-gate/outbox/broker changes, QMT operations,
production Redis access, or Cloud Agents.

## Rollback

Revert this PR's commit
`feat(contract): thin-wrap signal_bundle/run_manifest to myquant-infra (B8)`
and restore the prior optional pin
`7d48c4e310f9636cad9c3e544db1766025db4e3c` (the revert restores it).
Reinstall the reverted optional requirements only if rebuilding an environment.
This restores host signal/provenance implementations and the prior pool
facade behavior. No lake rewrite, Redis operation, deployment, or data
migration is needed. Do not merge as part of this task.
