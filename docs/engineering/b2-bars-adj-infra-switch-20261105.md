# B2 bars/adjustment host switch (2026-11-05)

B2 switches the matching adjustment-factor metadata facade and daily schema
constants to `myquant_infra.bars`. **The writer/repair/factor/seed switch is
partial and RESULT_BLOCKER remains for the symbols below.** Their existing
implementations are retained; this PR does not claim full A1a parity.

Branch: `feat/b2-bars-adj-infra-switch-20261105`, stacked on D4
[#566](https://github.com/baiyibing/MyQuant-backtrader/pull/566), parent
`82a552097f35535d3164112c1a9a4b6d66ab3551`. Open only; hotmail owns merging.
The remote has no `main` ref; its actual default/PR base is `master`.

## Pin and optional imports

The immutable requirement remains in **optional `requirements-infra.txt` only**:

```text
myquant-infra @ git+https://github.com/baiyibing/MyQuant-infra.git@7d48c4e310f9636cad9c3e544db1766025db4e3c
```

This is already D4's pin. Public requirements and public CI do not install the
private package. Hosts needing the switched metadata IO install explicitly:

```sh
/workspace/vanna312/bin/python -m pip install -r requirements-infra.txt
```

`oskh_data.adj_factor_meta` keeps its three public names/signatures and delegates
path naming, JSON read/write and freshness-date parsing to
`myquant_infra.bars.adj_factor_meta`. The sidecar's keys, source argument,
stock count and date semantics stay the same; infra additionally stages JSON
publication atomically. Import uses D4's `try/except ImportError` pattern with
patchable named stubs. Importing the host without infra works; invoking the
metadata path without infra raises an actionable `ImportError` naming
`requirements-infra.txt`.

`daily_parquet_write.STANDARD_COLUMNS` and `CANONICAL_ARROW_TYPES` import the
matching infra schema constants. Their static fallback keeps retained host
writers and public-CI path tests usable without private dependencies. There is
no fallback metadata publisher or private dependency in `requirements.txt`.

## Retained symbols and RESULT_BLOCKER evidence

All comparisons used the exact pinned source, not infra's moving main tip.

| Host symbol / caller family | Infra mismatch at the pin | Disposition |
| --- | --- | --- |
| `daily_parquet_write.merge_write_one_daily`, `_legacy_merge_write` | `bars.writer.merge_write_one` canonicalizes the complete old frame before merging. An untouched Shanghai-day row stored at prior-day 16:00 UTC is rewritten to UTC midnight. BT preserves untouched historical timestamps and replaces only incoming days. | **RESULT_BLOCKER: daily merge history preserve.** Keep both kernels, their parallel writer, mirror and Path B callers. |
| `daily_parquet_write.canonicalize_arrow_daily_table` / `_normalize_new_frame` | Infra's similarly named canonicalizer also normalizes timestamps, drops invalid rows and deduplicates; BT's helper casts columns without a full content/time cleanup. | **RESULT_BLOCKER: schema conversion is not equivalent.** Keep the local helpers; share constants only. |
| `repair_daily_parquet_schema.repair_parquet_file` | Infra returns `quarantine` for schema drift with legacy CST timestamps, asking for daily-time repair first. BT repairs the dtype while preserving time/content. | **RESULT_BLOCKER: schema-repair legacy CST.** Keep scanner, repair and aggregate return contracts. |
| `adj_factor.build_for_symbol` | Infra builds factors only on same-date inner joins and fails for missing inputs; BT keeps an outer date union, forward fills prices and returns an empty frame for missing front/none. | **RESULT_BLOCKER: factor alignment parity.** Retain builder and path composition; no silent change to research factor inputs. |
| `adj_factor.main` | Infra's table builder uses an all-symbol list comprehension; BT catches per-symbol errors and publishes successful frames. | **RESULT_BLOCKER: partial factor-build salvage.** Keep CLI orchestration and use the switched metadata facade after publication. |
| `seed_missing_front.seed_missing_front_from_none` | Infra canonicalizes and republishes the none frame rather than copying bytes. It also requires a minimum date, defaults to dry-run and returns different counters. | **RESULT_BLOCKER: seed history/result parity.** Keep byte-copy, optional freshness threshold and existing `SeedStats`/coverage wrappers. |

`write_processed_data`'s successful-symbol salvage remains tested in all three
modes (`legacy`, `parallel`, `batch`). Its merge dependency is blocked; no partial
daily batch is rerouted to a different orchestrator. There is no minute writer
or minute HHMMSS-window call site among these five BT modules, so no minute
implementation is removed or switched. A1a must land separately before a later
reviewed re-pin and additional deletions. Landing A1a alone does not authorize
changing the factor outer-join/forward-fill or seed API contracts.

The related historical `scripts/data/build_adj_factor_table.py`,
`repair_daily_parquet_schema.py`, `run_daily_adjusted_fast.py` and
`finish_adj_factor_duckdb.py` are absent in this research fork. No vendor/download
entry is reintroduced. Existing diagnostics, D4 rebuild and chip/S26 adjustment
consumers stay as they are.

BT's adjust-type gate wrappers, stock/ETF reader boundary, economics gate,
decision-price paths, trading modules and `oskh_factors/chip/adj_factor.py` remain
outside this change. Existing index file routing is preserved; the reader API
is not expanded to `asset_type="index"`.

## Hermetic validation

Interpreter: `/workspace/vanna312/bin/python`. The shared environment contained
a different infra revision, so tests used an isolated, detached checkout of
`7d48c4e310f9636cad9c3e544db1766025db4e3c` on `PYTHONPATH`; the shared installation
was not modified. All market-bar fixtures are temporary files. No live lake,
production Redis, QMT, vendor session, orders, CloudAgent or secret access was
used.

Pinned-infra run: **546 passed, 1 skipped**:

```sh
PYTHONPATH=<isolated-checkout-at-7d48c4e> /workspace/vanna312/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_oskh_data_bars_infra_switch.py \
  tests/test_data_path_ssot_write_symmetry.py \
  tests/test_hive_lake_kind_and_roots.py \
  tests/test_oskh_data_infra_switch.py \
  tests/test_oskh_data_adjust_type_entry_gate.py \
  tests/test_oskh_data_adjust_type_policy.py \
  tests/test_oskh_data_freshness_session_policy.py \
  tests/test_corp_actions_economics_gate.py \
  tests/test_signal_price_domain.py \
  tests/test_signal_price_domain_tick.py \
  tests/test_rb17_retired_modules.py \
  tests/test_minute_bar_scan_host.py
```

Public-CI simulation with a subprocess import finder blocking every
`myquant_infra` import: **19 passed, 7 skipped** for
`test_oskh_data_bars_infra_switch.py` + `test_data_path_ssot_write_symmetry.py`.
The seven skips require real infra; patchable forwarding, missing-package
imports and all retained host compatibility tests execute without it.

Six data-free gates passed: oskh-data contract, path SSOT, machine-path fence,
TR bridge, corp-action economics fence and host DuckDB connection allowlist.
Changed Python/Markdown files were checked for UTF-8 without BOM and zero NUL
bytes; `git diff --check` passed.

## Rollback

Revert the B2 commit from this PR with `git revert <B2-commit-sha>` through the
normal review flow. This restores the local metadata implementation and schema
constants while retaining the underlying D4 switch. There is no dependency
rollback to invent: D4 and B2 use the same `7d48c4e310f9636cad9c3e544db1766025db4e3c`
pin. If restoring the environment, reinstall `requirements-infra.txt` from the
reverted tree. Reverting B2 requires no lake rebuild, data migration, Redis
operation or QMT access. No merge is performed by this task.
