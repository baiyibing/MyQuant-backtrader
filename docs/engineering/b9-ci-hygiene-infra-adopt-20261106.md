# B9 optional infra CI hygiene (2026-11-06)

> 2026-11-09 invocation update: use the current pin in `requirements-infra.txt`
> (`af27dd08c6b5e3653fa686c6f60e541afd1a4941`) and the matching entrypoint.
> The three CI script blobs and their hashes are unchanged. On Windows,
> `git archive` also applies `core.autocrlf`; pass `-c core.autocrlf=false`
> to preserve the verified bytes. The original delivery record below is historical.

BT adds a manual, read-only entrypoint for the pinned infra encoding, secrets
and relative Markdown link helpers. This is the research-face twin of
[OSkh A17 #1316](https://github.com/baiyibing/OSkhQuant1.3/pull/1316).
Existing CI and hooks do not invoke it. It imports no scanned application code,
downloads nothing, writes no fixes and installs no hooks.

Branch: `feat/b9-ci-hygiene-infra-adopt-20261106`; base:
`3cb707e95948af66514df53f17227668df476135` (rebase onto master after
#576/#577). Independent of open B5 #570 / B8 #574. Draft PR only; no merge,
CloudAgent, QMT, lake access or production cutover.

## Pin and invocation

The existing optional [requirements-infra.txt](../../requirements-infra.txt)
already pins `myquant-infra` to `3c377e9718e811112993579b6d91a603395db699` (unified tip after infra #60;
B2/K18/B7/B6 comments retained on master). This PR does not advance the pin.
Default requirements and public CI remain unchanged.

The wheel does not contain `scripts/ci`. Use `git archive` of the exact pin
from an existing local MyQuant-infra clone and extract it outside BT; no network
or installation is needed. For example, with explicit local paths:

```bash
git -c core.autocrlf=false -C "$INFRA_LOCAL_CLONE" archive --format=tar \
  --output="$INFRA_PIN_TAR" af27dd08c6b5e3653fa686c6f60e541afd1a4941
mkdir -p "$B9_INFRA_ARCHIVE"
tar -xf "$INFRA_PIN_TAR" -C "$B9_INFRA_ARCHIVE"
"$OSKH_MERGE_PYTHON" scripts/gates/run_infra_ci_hygiene.py \
  --root "$BT_CHECKOUT" --infra-root "$B9_INFRA_ARCHIVE"
```

The [entrypoint](../../scripts/gates/run_infra_ci_hygiene.py) accepts repeated
`--check encoding|secrets|links` selections; omission runs all three. `--root`
defaults to the BT checkout containing the entrypoint, independently of cwd;
an explicit target must be a Git checkout root, including a worktree with a
`.git` file. All three script SHA-256 hashes are validated before any script
loads. Every invocation uses fresh modules without importing `myquant_infra`
or creating archive bytecode. An installed wheel alone cannot enable it.

| Check | Actual pinned surface and BT binding |
| --- | --- |
| Encoding | `check_repo_hygiene.repo_files`, `TEXT_EXTS`, `TEXT_NAMES`, `encoding_rule`; tracked and untracked nonignored files, strict UTF-8/no BOM/no NUL. |
| Secrets | `scan_secrets.scan` with `staged=False`, `verbose=False`; `REPO`, `ALLOWLIST`, and `tracked_files` bound to BT. Only tracked files; findings show paths, line numbers and rule names, never values. |
| Links | `check_md_links.main`; `ROOT` and `iter_md` bound to BT. Pinned root README/docs/module README/CI README scope; external URLs are skipped without network access. |

The latter two pinned scripts have no `--root` CLI. The adapter binds their
existing globals and wraps their actual enumerators to exclude any path
containing a `live_trading` or `trade_decision` component before reading it.
No live_trading scans occur, and no trade_decision policy is transferred.
Symlinked files/directories and paths escaping the selected root fail before
file contents are read. No OSkh vendor/GBK exemptions are copied into BT.

The consolidated infra semantic `scan`/`main`, counted
`hygiene_allowlist.json`, forbidden/reverse-import rules, machine/data-path
policy and except-pass policy are not applied to BT. Its allowlist only admits
infra-owned paths; BT's research imports and path contracts remain host-owned.
The secrets helper uses only BT's optional `scripts/ci/scan_secrets_allow.txt`
if present; infra's unrelated exemptions are never copied. No new allowlist
is introduced to suppress existing findings.

Exit codes: **0** = selected checks pass; **1** = findings;
**2** = unavailable/mismatched tooling, invalid target or unsafe path.
Missing source reports the exact pin, optional requirements file and local
`git archive` / `--infra-root` remedy. `--help` and module import work without
infra source or the optional package.

## MUST STAY host

- `verify_data_path_ssot.py`, `verify_no_hardcoded_machine_paths.py`,
  `verify_tr_bridge_import_ssot.py`: source, CLIs and allowlists unchanged.
- Economics: `verify_corp_actions_economics_fence.py` unchanged
  (`corp_actions_econ_gate.py` already removed on master by #576).
- Any trading, decision-price or clock gates, research execution and pricing
  contracts; no infra semantic replacement for live_trading/trade_decision.
- `scripts/install-git-hooks.sh` and `.ps1`, existing hooks and CI workflows
  unchanged. Installers are never run by this entrypoint or its tests.

## Validation

Interpreter: `/workspace/vanna312/bin/python`. The
[focused suite](../../tests/test_b9_ci_hygiene_infra_adopt.py) runs on tiny
temporary Git checkouts; network/socket/DNS calls and non-read-only Git
subprocesses are rejected during adapter execution. Tests also block optional
package and application imports and assert that trading-tree fixtures are
never read. Fixtures contain only constructed synthetic token shapes.

```bash
B9_TEST_INFRA_ROOT="$B9_INFRA_ARCHIVE" "$OSKH_MERGE_PYTHON" -m pytest \
  tests/test_b9_ci_hygiene_infra_adopt.py -q -p no:cacheprovider
env -u B9_TEST_INFRA_ROOT "$OSKH_MERGE_PYTHON" -m pytest \
  tests/test_b9_ci_hygiene_infra_adopt.py -q -p no:cacheprovider
```

| Environment | Result |
| --- | --- |
| Pinned source archive supplied | 27 passed |
| No optional source supplied | 10 passed, 17 skipped (real-source cases) |

The suite verifies all three helpers, UTF-8/BOM/NUL failures, value redaction,
BT allowlist/tracked-file scope, missing relative links, skipped external URLs,
source pin/target failures, path safety, fresh bindings, repeated selections,
and no target changes or new archive bytecode. Host public entrypoints remain
independent. Seven frozen BT source fingerprints cover the three selected
gates, economics fence, both hook installers and public CI workflow;
no Git history or OSkh trading fingerprints are needed by public CI.

All six pre-pip host contract gates pass. A byte comparison against the base
also confirms all 24 pre-existing host gate/workflow/installer/economics/hook
files are unchanged. Focused Ruff and whitespace checks pass; changed text is
UTF-8 without BOM and has zero NUL bytes.

Additional B2/K18/B7, economics, TR bridge and path regressions with the new
archive: **96 passed, 2 failed**. Both failures reproduce on the clean BT base
with that archive. The cache test's `FakeRedis` lacks the host's `setex` method;
it also fails with the previous pin. The B2 negative witness
`test_pin_witness_daily_history_and_cst_repair_mismatches` passes with the old
pin but fails with `3c377e9`: it expects the old infra writer to change legacy
CST history, while the new pin preserves it and makes schema repair type-only.
The BT paths using those former mismatches remain blocked and unchanged.
This draft leaves the old witness and unrelated cache fixture untouched;
the broader suite is not claimed green with the new pin.

The optional full-checkout diagnostic exits **1**: 3 encoding findings in 2,238
files, 5 possible-secret finding lines and 105 link findings. All 49 finding
source paths match the base byte-for-byte; none are B9 additions. Findings are
diagnostics under infra rules, not confirmed credentials. No host allowlist or
gate was changed to suppress them. Detailed logs and baseline reproductions
are retained under the B9 receipt's export directory.

CI pending is not Fast Lane acceptance. Full-repository diagnostic findings
under infra rules do not change host policy or imply a host baseline failure.

## Rollback

Revert this PR. The optional pin is unchanged by B9 (already at master tip
`3c377e9718e811112993579b6d91a603395db699`), so no pin restore is needed. No data migration, hook removal,
lake rebuild or production setting change is required.
