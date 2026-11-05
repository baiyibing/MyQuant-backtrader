# B7 Hithink artifact consumer switch (2026-11-05)

BT now consumes the offline artifact implementation from MyQuant-infra through
`oskh_data.hithink_artifact`. The BT run object, import/refresh transaction,
assembly, coverage classification and manual exclusions remain in
`scripts/data/hithink_incremental.py`, which still imports the host facade.
`myquant_infra.corp_actions.incremental` has a different orchestration API and
is not used.

Branch: `feat/b7-hithink-artifact-infra-switch-20261105`; parent:
`4d33b40da517b2a897b29e2af04d1314912067ab` (GitHub `master` after fetching).
The `origin` mirror was fetched first but trails GitHub at `a213177`; the branch
already matched fetched `github/master`. No B3/B4/B5 commits are stacked.
Open only: draft PR against `master`; hotmail owns merging.

## Pin and public API

The existing optional `requirements-infra.txt` requirement is unchanged:

```text
myquant-infra @ git+https://github.com/baiyibing/MyQuant-infra.git@7d48c4e310f9636cad9c3e544db1766025db4e3c
```

Only a B7 rollback comment is appended to that file. Hosts performing artifact
imports explicitly install it with their project interpreter:

```powershell
& 'D:/anaconda3/envs/vanna312/python.exe' -m pip install -r requirements-infra.txt
```

The exact pin was inspected before removing the local artifact implementation;
every required public symbol exists there.

| Host exports | Pinned implementation |
| --- | --- |
| `read_artifact`, `request_identity`, `validate_probes`, `proves_empty`, `read_json`, `canonical_json`, `ERRORS`, `FILES` | `myquant_infra.hithink.artifacts` |
| `SOURCE`, endpoints, `NUMBERS`, `QUARANTINE_POLICY`, `SHANGHAI`, `code`, `day`, `digest`, `number`, `present_codes` | `myquant_infra.hithink.export` |
| `PAYLOAD_FILES` | `myquant_infra.hithink.export.FILES` (two payload files) |
| `parse_dump`, `inspect_dump` | `myquant_infra.hithink.export.inspect_dump` (same callable as infra artifacts' `parse_dump`) |

Host `FILES` keeps all four v1 artifact names, including the manifest and commit
marker; it must not be confused with the exporter's two payload names. Infra
retains v1/v2 hashes, commit/request binding, probe validation and v2 quarantine
recomputation. No download/client/export entry point is exposed by the facade.

## Optional imports and ownership

Public requirements and CI do not install private infra. When the top-level
`myquant_infra` package is absent, the facade retains the existing small
code/date/Decimal/hash/JSON helpers and wire constants so BT economics and
non-artifact host tests still execute. Decimal precision/scale validation is
unchanged. Artifact operations instead raise an actionable `ImportError` naming
`requirements-infra.txt`; there is no fallback parser or artifact validator.
Missing symbols, missing submodules and broken transitive imports in an
installed package propagate rather than silently using the public fallback.

The existing Hithink fixture builder skips only tests that require real infra
artifact IO when the optional dependency is absent. Host channel/missing-input
and base-date rejection tests still run, as does the entire economics suite.
New facade tests check forwarding identity, public helper parity, missing-package
errors and incomplete-package rejection.

`backtest/research/corp_actions_econ_gate.py` and
`scripts/data/hithink_incremental.py` are byte-for-byte unchanged. Decision-price
paths and economic eligibility rules remain BT-owned. This switch performs no
live acquisition, lake publication, CloudAgent operation, production Redis
access, QMT login or orders. All artifact fixtures and candidate outputs used in
validation are temporary; no live lake or vendor credentials are needed.

## Validation

Interpreter: `D:/anaconda3/envs/vanna312/python.exe`. Tests used an isolated source
archive of exact commit `7d48c4e310f9636cad9c3e544db1766025db4e3c`
on `PYTHONPATH`; the shared installation was not changed.

- Requested Hithink + economics suites and new facade tests: **83 passed**.
- Those suites plus OP06 conversion and the incremental-driver suite:
  **152 passed, 1 deselected**. The deselected unchanged symlink test
  `test_output_symlink_escape_and_single_runner` fails on this Windows host with
  `WinError 1314` (symlink privilege unavailable). The initial broader public
  simulation exposed this environmental failure; no unrelated test was changed.
- Public-CI simulation blocking every `myquant_infra` import: the requested
  suites, facade tests and OP06 gave **50 passed, 44 skipped**. Skips cover real
  infra artifact IO and real-infra facade comparisons; economics tests execute.
- Economics import fence, machine-path fence and data-path SSOT gates passed.
- UTF-8 without BOM, zero NUL bytes and `git diff --check` verified.

Focused test command (set `PYTHONPATH` to the isolated pinned source if needed):

```powershell
& 'D:/anaconda3/envs/vanna312/python.exe' -m pytest -q -p no:cacheprovider tests/test_hithink_incremental.py tests/test_corp_actions_economics_gate.py tests/test_hithink_artifact_infra_switch.py
```

## Rollback

Revert the B7 commit titled
`feat(hithink): thin-wrap artifact consumer to myquant-infra (B7)` through the
normal review flow: `git revert <B7-commit-sha>`. This restores the local
artifact consumer and its fixture setup. The infra pin remains
`7d48c4e310f9636cad9c3e544db1766025db4e3c`, shared with existing D4/B2 work;
there is no B7 dependency downgrade or shared-environment uninstall.
If rebuilding a host environment, reinstall the optional requirements from
the reverted tree. No lake rebuild, data migration, Redis operation or QMT
access is needed. This task does not merge the PR.
