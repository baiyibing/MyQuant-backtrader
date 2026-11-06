# B6: host TR store/IO switch (D8=A)

Branch: `feat/b6-tr-store-infra-switch-20261105`, based on merged `master`
`971936f74d5cf62aff572171ff1093265e5f547f`, including B2 #567.
This is an independent, open-only draft against `master`; hotmail owns merging.
No B3–B5/B7 stack commits are included.

## Immutable optional pin

`requirements-infra.txt` now pins the merged infra main commit including #63:

```text
myquant-infra @ git+https://github.com/baiyibing/MyQuant-infra.git@4dad4c5d11bad0f001715248ee354f34a547e4f8
```

The prior D4/B2 pin was `7d48c4e310f9636cad9c3e544db1766025db4e3c`.
Neither an unmerged #59/#60 head nor a moving branch is used. The infra
`myquant_infra/bars` and `myquant_infra/lake` trees are unchanged between these
two pins. Public `requirements.txt` and CI workflows remain unchanged; CI does
not install the private dependency. Configured hosts install it explicitly:

```powershell
& D:/anaconda3/envs/vanna312/python.exe -m pip install -r requirements-infra.txt
```

## Call-site boundary

`oskh_data.turnover_resistance_store.TurnoverResistanceStore` is a compatibility
facade over `myquant_infra.derived_data.turnover_resistance.store`.
All reads, locking, atomic parquet writes, schema normalization, session caching,
FFI-row normalization and staging merge operations delegate to that module.
Public store methods keep their arguments, return values and defaults. Cache
counters remain readable/resettable through the facade. No local IO fallback
is retained.

Host environment/root policy stays in the host: explicit paths override
`TURNOVER_RESIST_BANDS_PATH` / `TURNOVER_RESIST_STAGING_DIR`; otherwise existing
`resolve_source_parquet` / `resolve_tr_staging_dir` select the configured lake.
Canonical and staging root composition remains usable without private infra.
The facade passes complete paths into infra, whose own path API deliberately
accepts only explicit paths. Yearly filenames delegate to infra's
`resolve_year_staging_path`; canonical merges delegate to
`merge_parquet_into_canonical`. Host schema/audit constants stay importable and
are checked against the pinned infra exports.

The facade supplies the existing host `oskh_factors.chip.bands.compute_tr_bb_columns`
through infra's `BandsProducer` port. Callers can explicitly override it with
`bands_producer=`. Both daily and backfill scripts inject the host callable
explicitly. Existing consumers, including `refresh_tr_store_window` and the
Source-B pool reader, keep working through the default host injection.
No production producer is imported or discovered by infra.

The three `scripts/tr/*turnover_resistance*` entry points retain host scheduling,
Rust-bridge calls, date enumeration, subprocess bootstrap, progress JSON and
console reports. They use the facade for store/merge IO. The pinned infra CLI
offers inspection and explicit merge only; it has no compute/backfill CLI.
No nonexistent infra pipeline API is invented. The existing bridge import gate
and DuckDB date-enumeration allowlist remain intact.

The backfill parser now declares `--all-trading-days`, already referenced by
its help and `_resolve_dates`. Previously the non-year paths accessed an
undefined namespace field. Its default is false; year mode still implies it.
The yearly wrapper resolves the canonical filename once before passing it
through staging merges and the final full-history recompute.

Infra's documented IO safeguards apply: reads isolate cached frames, external
replacement detection uses file identity/stat fields, writes invalidate caches,
and producer results are validated/aligned by keys before publication. Producer
failure leaves canonical bytes and cached rows intact. These are store/IO
changes; numerical bands, TR core/constants/Rust, share inputs, signal rules
and decision-price paths stay host-owned and unchanged.

## Validation

Interpreter: available `D:/anaconda3/envs/vanna312/python.exe` (Python 3.12.13,
pandas 2.3.3). Public CI retains its pandas 3.0.6 pin; this host run does not
claim validation on that pandas version. Tests used a separate export of the
exact infra commit on `PYTHONPATH`; the shared installation was not modified.
All TR parquet, staging, progress JSON and bar fixtures use temporary paths.
New wrapper tests reject socket connections and replace Rust computation with
synthetic host callables. No real lake, production Redis, QMT, orders, secrets,
CloudAgent or live job was accessed.

Pinned-infra command (results recorded below):

```powershell
$env:PYTHONPATH = '<isolated-export-of-4dad4c5>'
& D:/anaconda3/envs/vanna312/python.exe -m pytest -q -p no:cacheprovider `
  tests/test_turnover_resistance_infra_switch.py `
  tests/test_turnover_resistance_store.py `
  tests/test_refresh_tr_store_window.py `
  tests/test_data_path_authority_marker.py `
  tests/test_oskh_data_bars_infra_switch.py `
  tests/test_oskh_data_infra_switch.py `
  -k 'not test_cache_roundtrip_pointer_rotation_and_invalidation'
```

The wider D4 suite has one pre-existing failure:
`test_cache_roundtrip_pointer_rotation_and_invalidation` supplies a `FakeRedis`
without `setex` to the unchanged host `oskh_data.cache_port`. It fails on both
the previous `7d48c4e` pin and the requested `4dad4c5` pin. That test and cache
implementation are outside B6 and remain unchanged. The exclusion above is
only for this local diagnostic run; no CI selection or test is changed.

The same six files are also run without exclusions in a public-CI simulation
whose subprocess import finder blocks every `myquant_infra` import. Only real
private-infra IO tests skip; host forwarding, path policy, help, missing-package
errors and mocked refresh behavior still execute. Store imports and all three
CLI help paths remain usable without infra; actual IO raises an actionable
`ImportError` naming `requirements-infra.txt` before touching files.

Results: **110 passed, 1 deselected** against the exact pin; public-CI
simulation **73 passed, 38 skipped** with no test-selection exclusion.
Coverage includes cross-year staging/merge/final bands, skip-existing,
bands-only/recompute modes, custom producer parameters, producer failure
isolation, schema/audit compatibility, cache isolation and missing-package help.
Six data-free gates pass: oskh-data contract, path SSOT, machine paths, TR bridge,
economics fence and DuckDB connection allowlist. Changed Python/Markdown files
are UTF-8 without BOM and contain zero NUL bytes; `git diff --check` passes.
Linux Fast Lane is the merge gate; this task does not merge.

## Rollback

Revert the B6 commit through normal review:

```text
git revert <B6-commit-sha>
```

Revert host wrappers and the optional requirement together. This restores the
local store and the prior `7d48c4e310f9636cad9c3e544db1766025db4e3c` pin while
keeping merged B2/D4. Reinstall `requirements-infra.txt` from the reverted tree
if restoring an environment. The 33-column parquet contract and file names
are unchanged; rollback needs no lake rewrite, migration, Redis operation or
QMT access. No production switch or merge is performed by this task.

## Unified infra pin bump after #60 (2026-11-06)

After MyQuant-infra #60 merged, re-pin the optional requirement from
`4dad4c5d11bad0f001715248ee354f34a547e4f8` to
`3c377e9718e811112993579b6d91a603395db699` (merged `origin/main`).
This supersedes the earlier pin and #60 status above; earlier test results
remain evidence for the previous pin. Verified the exact new requirement
SHA and `git diff --check`; no full suite was run for this pin-only update.


## Pin bump after infra #60

Current pin: `3c377e9718e811112993579b6d91a603395db699` (merged origin/main after #60). Prior campaign pin `4dad4c5` superseded. Rollback: revert B6 wrappers and restore prior pin SHA documented above.
