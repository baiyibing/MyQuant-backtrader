# B4: offline L2 research queries/templates infra switch (2026-11-05)

B4 starts from clean B3 commit
`8351bcd980f2769cc042729414557fc8519494b8` (#568). At initial fetch, B3 is
open and master is `4d33b40da517b2a897b29e2af04d1314912067ab`. The B4 draft
targets master and is stacked on B3; its master diff includes B3 until hotmail
merges that prerequisite. B4 does not rework B3 ingest, aggregates, maintenance,
or Phase3. Only hotmail merges; this change is open-only.

## Optional immutable pin

`requirements-infra.txt` retains
`7d48c4e310f9636cad9c3e544db1766025db4e3c`, the fetched infra main tip.
Infra #59 and #60 are still open at implementation time. No unmerged branch
is used. Default `requirements.txt` and public CI installation are unchanged.

Install through the configured interpreter (the checkout used Windows vanna312):

```powershell
& D:\anaconda3\envs\vanna312\python.exe -m pip install -r requirements-infra.txt
```

All host modules and both research CLI `--help` paths import without infra or
DuckDB. Calls requiring infra fail through the existing B3 lazy loader with an
explicit `requirements-infra.txt` instruction. There is no local implementation
fallback. Constants such as `TEMPLATE_FILES` and `MAIN_EXACT_DUP_COLS` resolve
lazily on access, so CI tests import their modules before optional-test skips.
Missing transitive dependencies keep their original errors.

## Ownership and compatibility

The correct package is **`myquant_infra.l2.research.queries`**; these commands
are separate from `myquant_infra.l2.research` CSV/hypothesis experiments.

| Host entrance | Infra owner | Host responsibility |
| --- | --- | --- |
| `l2_analytics/templates.py` | `research.queries.templates` | Existing function signatures and lazy template map |
| `l2_analytics/sql/` | `research.queries/sql/*.sql` | Importable shim exposing `sql_dir()` and `load_template()` |
| `l2_analytics/board_limit.py` | `research.queries.board_limit` | Function and SQL-expression compatibility |
| `l2_analytics/ref_data.py` | `research.queries.ref_data` | Resolve default `adj_factor.parquet` via the host resolver |
| `l2_analytics/db.py` | `research.queries.db` | Resolve optional root/reference paths, forward session options |
| `l2_analytics/consumer_dedup.py` | `research.queries.consumer_dedup` | Existing helpers, audit keys, and lazy identity constants |
| `scripts/run/run_l2_net_inflow_by_price.py` | `research.queries.net_inflow_by_price.main` | Bootstrap, argument parsing, default host root |
| `scripts/run/run_l2_p0b_baseline.py` | `research.queries.p0b_baseline.main` | Bootstrap, argument parsing, default root/report filename |

The twelve host SQL files are removed. Their packaged texts match the B3 files
exactly after newline normalization; tests freeze all twelve SHA-256 digests.
Resource consumers should use `l2_analytics.templates.sql_dir()` (also exported
by `l2_analytics.sql`) for the installed directory, rather than a repo-relative
`l2_analytics/sql/*.sql` path. No SQL/formula copy remains in the host wrappers.

`run_template` keeps trusted internal `extra_where`, named bound `params`, the
identifier-only `order_by` policy, and tuple rows. Templates still read raw
views; dedup helpers add separate exact-row views, preserving distinct prints
with the same TranID. Board rules remain offline approximations, including
302, with no ST/name feed. No decision-price or trading-rule wiring changes.

`connect` keeps its signature, 18GB default, thread and spill options, and host
`resolve_l2_parquet_root()` selection. Infra owns the in-memory connection,
hive/legacy union, aggregate registration, reference SQL, and failure cleanup.
The retired host connection allowlist entry is removed: 12 calls in 9 exact
files remain. No new connection exception is added.

Reference requests now follow the repository's fail-visible path rule:
`register_adj=True` (the existing library default) resolves an omitted reference
through `resolve_source_parquet("adj_factor.parquet")`; unconfigured roots and
missing requested files fail. `register_ref_views` follows the same policy.
Raw-only callers must pass `register_adj=False`. Previous silent missing-ref
returns are removed. Raw aggregate/template fixtures explicitly disable refs
so tests never discover or read a real configured reference lake.

Both CLIs retain the optional `--parquet-root` host resolver, 18GB memory default,
existing date defaults, and output schemas. The per-price CLI retains binning,
sort, row-limit, JSON and CSV options. Infra fixes the former exact-price default
sort typo, binds date/symbol values, validates dates and finite bin widths, and
closes connections on failure. Full-day totals remain independent of row limits.

The baseline retains `--raw-bc` and the default output filename
`<root>/p0b_baseline_<date>.json`. It adds `--adj-factor-path` for an explicit
reference request; without it, reference-dependent samples record `skipped`
with a reason. It no longer discovers reference input implicitly. A supplied
missing reference fails. The host resolves paths and forwards arguments to
infra, returning its exit status without recreating queries or report logic.

All of this is manual offline research. No job is enabled; no CloudAgent,
Redis service, QMT login, orders, external download, market-bar write, or real
L2 hive is involved. Operator-invoked queries may write requested reports and
DuckDB spill files; tests use only temporary synthetic CSV/Parquet fixtures.

## Validation

The configured Windows interpreter is
`D:\anaconda3\envs\vanna312\python.exe`; `/workspace/vanna312/bin/python`
does not apply to this checkout. Tests use `-q -p no:cacheprovider`.
The installed optional package's 364 Python/SQL source files were compared
against the immutable pin with no drift before running integration tests.

```powershell
& D:\anaconda3\envs\vanna312\python.exe -m pytest -q -p no:cacheprovider tests/test_l2_research_infra_switch.py tests/test_l2_templates.py tests/test_l2_consumer_dedup.py tests/test_l2_aggregates.py tests/test_l2_infra_switch.py tests/test_verify_no_host_duckdb_connect.py tests/test_config_bootstrap_isolation.py
# 95 passed
& D:\anaconda3\envs\vanna312\python.exe -m pytest -q -p no:cacheprovider tests/test_l2_etl.py tests/test_l2_perf.py tests/test_l2_phase3_pipeline.py tests/test_oskh_data_infra_switch.py tests/test_oskh_data_bars_infra_switch.py
# 134 passed, 54 skipped (optional Polars unavailable)
```

The first selection was also run with a meta-path finder blocking all
`myquant_infra` imports: **47 passed, 48 skipped**. Public boundary tests still
execute; optional integrations skip explicitly. A separate subprocess blocks
both infra and DuckDB, proving module imports/help work and actual operations
fail with the install instruction.

New cases cover explicit/default root and reference forwarding, raw-only
sessions, missing configuration/files, option and exit-status forwarding,
installed SQL resources, and hive/legacy/mixed layouts. Integration checks
raw-versus-dedup quantities, full-day totals despite a report limit, baseline
report fields, and unchanged source Parquet/manifest bytes. Existing reference
tests retain ex-dividend D-day-domain and adjusted VWAP assertions.

Nine contract gates passed: data contract, path SSOT, hardcoded paths, TR bridge,
corporate-action economics, host DuckDB connection fence, book admission,
baseline admission, and capability classification. The minute classification
gate also passed (89 strategies). Changed Python/Markdown
files are UTF-8 without BOM and have NUL count zero.

## Rollback

Revert only the B4 commit with subject
`feat(l2): thin-wrap L2 research queries/templates to myquant-infra (B4)`
through a reviewed PR. Its parent is B3
`8351bcd980f2769cc042729414557fc8519494b8`. This restores the local research
helpers, twelve SQL files, CLI implementations, and the removed connection
allowlist entry together; it leaves B3 ingest/aggregates/maintenance intact.

Retain optional infra pin `7d48c4e310f9636cad9c3e544db1766025db4e3c` for
B3/B2/D4 consumers; do not uninstall or downgrade it as a B4 rollback. The
switch performs no data migration and requires no lake restore. Existing
reports remain research artifacts and are not rewritten during rollback.
