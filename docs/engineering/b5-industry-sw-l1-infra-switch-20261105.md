# B5 industry SW-L1 reader host switch (2026-11-05)

`oskh_data/industry_sw_l1.py` now delegates the existing industry map reads,
Wind CSV parsing, normalization and lookup helpers to MyQuant-infra. BT keeps
its public signatures, root authority and missing-file diagnostics. Collection
and publication remain owned by OSkhQuant1.3; this facade only reads.

Branch: `feat/b5-industry-sw-l1-infra-switch-20261105`, stacked on B3
`8351bcd980f2769cc042729414557fc8519494b8`
([#568](https://github.com/baiyibing/MyQuant-backtrader/pull/568)). The draft PR
targets `master` and depends on B3. Open only; hotmail owns merging. B4 L2
research, B8 signal bundles, A*/MQ work and decision-price paths are outside B5.

## Verified API and immutable optional pin

Inspected the committed source and imported these exact symbols at
`7d48c4e310f9636cad9c3e544db1766025db4e3c` before changing the host:

| Infra module under `myquant_infra.reference_data.industry` | Used symbols |
| --- | --- |
| `readers` | `load_sw_l1_map(path=None, *, container=None)`, `load_wind_l1_map(path=None, *, container=None)`, `load_industry_map(root=None, *, container=None)`, `lookup_industry(stock, mapping)`, `industry_bucket_for_stock(stock, mapping)` |
| `vendor_wind_sw_l1` | `normalize_industry(name)`, `normalize_wind_code(code)`, `load_wind_csv(path)` |

All eight symbols exist at the pin; no API was invented. Infra #59 and #60
were still open when checked, so the optional requirement retains B3's pin:

```text
myquant-infra @ git+https://github.com/baiyibing/MyQuant-infra.git@7d48c4e310f9636cad9c3e544db1766025db4e3c
```

Install explicitly on an authorized host:

```sh
/workspace/vanna312/bin/python -m pip install -r requirements-infra.txt
```

The private package stays exclusively in `requirements-infra.txt`.
`requirements.txt` and public CI installation are unchanged. Imports and
Mode A/B `--help` work without infra. Industry operations load infra lazily
through `oskh_data._infra.require_infra`; absence raises an actionable
`ImportError` pointing to `requirements-infra.txt`. There is no local reader
fallback. Public tests exercise delegation with mocks; real infra cases skip
explicitly when the optional package is absent.

## BT authority and failure behavior

`resolve_sw_l1_root()` still calls
`resolve_source_parquet("vendor_wind_sw_l1")`. `OSKH_SOURCE_PARQUET_ROOT`
wins; an explicit `OSKH_AUTHORITY_HINT_ROOT` with `.authority` is the existing
fallback. An unconfigured lake raises `UnconfiguredDataRootError` before
infra is loaded. Workspace roots and bar-period overrides do not supply the
industry root.

Individual loaders forward their explicit CSV path, or the host-resolved
default filename, to infra. Explicit paths bypass host root resolution. The
combined loader checks both required files and passes the resolved product
directory as `root`, rather than mistaking it for a lake container.

The host's `_require_map_file` stays in place: absent files or directories in
place of files raise `FileNotFoundError` with the target and configuration
instruction before infra is invoked. Missing Wind never falls back to 聚源.
Infra applies the 聚源 base then Wind overlay, preserves stored industry text,
the last nonempty duplicate row, bare-code/partition-key rules and BT's lookup
precedence. Unknown industries retain `_UNMAPPED_` bucket behavior. These maps
remain current reference data; this switch introduces no PIT interpretation.

## Hermetic validation

Run the focused tests with the exact pinned source/package on the import path:

```sh
/workspace/vanna312/bin/python -m pytest -q -p no:cacheprovider tests/test_industry_sw_l1.py tests/test_industry_sw_l1_infra_switch.py
```

Validation uses synthetic CSVs in pytest temporary directories, with no network
or live lake access. A local archive of the immutable infra commit is placed
first on `PYTHONPATH`, because the shared interpreter may have a different
installed revision. Tests cover verified-module forwarding, explicit paths,
source-env/authority-marker precedence, missing/unconfigured roots, required
Wind overlay, CSV key and duplicate rules, lookup precedence, input bytes and
mtime preservation, and Mode A industry stratification. A fresh interpreter
blocks every private import to verify import/help availability and actionable
runtime failures. The focused pytest suite is also run with that import blocker
to check public-CI defaults. Relevant Mode A/B regressions and data-free CI gates
run separately; no research or decision-price implementation is changed.

Results on the exact pin: **36 focused tests passed**; **201 Mode A/B, path
authority and matching-kernel import-fence regressions passed**. With all
private imports blocked, the focused suite had **23 passed, 13 explicit skips**.
All nine data-free gates passed: oskh-data contract, path SSOT, machine paths,
TR bridge imports, economics fence, host DuckDB connections, book admission,
baseline admission and book capability classification. UTF-8/no-BOM and zero
NUL checks passed for every changed text file; `git diff --check` passed.

## Rollback

Revert only the B5 commit with `git revert <B5-head-SHA>`. That restores the
host reader and its tests at B3 without undoing B3, B2 or D4. The infra pin is
unchanged by B5, so rollback needs no package downgrade or configuration flip.
For an explicit file-only recovery, restore `oskh_data/industry_sw_l1.py` and
the affected tests from parent `8351bcd980f2769cc042729414557fc8519494b8` in a
reviewed rollback commit. No data migration, lake write or live-system action
is needed. Unsetting `OSKH_SOURCE_PARQUET_ROOT` is not a code rollback and can
still select the configured authority marker.

## Pin bump after infra #60

Current pin: `3c377e9718e811112993579b6d91a603395db699` (merged origin/main after #60). Prior campaign pins superseded. Rollback: revert host wrappers for B5 and restore the prior pin SHA documented above.
