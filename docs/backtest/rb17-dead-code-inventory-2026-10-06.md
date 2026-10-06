# RB-17 dead-code inventory (ZERO-DIFF, 2026-10-06)

## Decision

No file in this inventory is proven dead. RB-17 therefore retires **nothing**.
The apparent dead engines are test-pinned, the v7 compatibility entry remains a
documented CLI and import surface, and each shim/alias has a current consumer or
documented command. Deleting tests or documentation to manufacture zero
references would violate H-RB-11.

Verdicts:

| Candidate | Verdict | Reason |
|---|---|---|
| `backtest/legacy/engine.py` | KEEP | Static test import; README layout entry; historical contract references |
| `backtest/research/engine.py` | KEEP | Dynamic-import test and symbol assertion; parked explicitly by engine docs |
| `backtest/research/csv_minute_backtest_v7.py` | KEEP | Current CLI, loaders/parser/writers and compatibility re-exports are consumed |
| `backtest/research/strategy7_engine.py` | KEEP | Native v7 owner imported by main, facade, tests and migration guards |
| `oskh_core/turnover_resist_bridge.py` | KEEP | Compatibility re-export used by three scripts and two tests |
| `backtest/chip_algorithm.py` | KEEP | Compatibility re-export used by 17 Python consumers and documented commands |
| `scripts/data/export_strategy10_pool.py` | KEEP | Documented executable alias; `main` identity is part of the alias contract |
| `backtest/research/ashare_fees.py` | KEEP | Active fee owner with an intentional `ledger_math` identity re-export |
| `backtest/research/run_protocol/adapters/*.py` | KEEP | Five distinct lazy family adapters, dispatched by `facade.py` and tested separately |
| `backtest/research/verify_*.py` vs `scripts/gates/verify_*.py` | UNSURE | Similar names/copies, but research tools and gate entries both have references |
| `backtest/tools/parse_log.py` | KEEP | Orphan-like, but two docs explicitly inventory it; not zero-reference |
| `backtest/tools/read_app_data.py` | KEEP | Manual CLI with three path-gate/review references; not zero-reference |

`DEAD-CANDIDATE`: none. `UNSURE`: none among the files above. No directory was
treated as dead merely because its name contains `legacy`.

## Search method and dynamic-import checks

The repository root was searched, including `scripts/`, `tests/`, `.github/`,
`.githooks/`, `docs/`, Python and config/manifest formats. For each candidate
the probes covered its basename, repository path, dotted module path and public
symbols. Dynamic mechanisms were searched separately:

```text
import_module|__import__|spec_from_file_location|runpy|sys.modules|
python -m|python.exe -m
```

The exact candidate union also returned no match in `.github/` or `.githooks/`.
JSON/YAML/TOML/INI matches were limited to v7 executable paths in frozen
research manifests/recipes and `export_strategy10_pool` provenance. Those
references are listed below. Searches excluded only `.git/`; this inventory
file did not exist during the search.

Dynamic-import risk is **high unless disproved per file**. In particular,
`backtest.research.engine` is loaded by a string passed to
`importlib.import_module`, the run-protocol facade lazily imports one adapter at
dispatch, and several v7 consumers retain module aliases and private
attributes. A basename-only search is therefore insufficient.

## Candidate details and reference ledger

### `backtest/legacy/engine.py` — KEEP

Public definitions: `StrategyLike`, `BacktestConfig`,
`estimate_backtest_trade_fee`, `SimulatedFill`, `BarReplayEngine`.

References found:

- Static import and symbol use:
  `tests/test_backtest_engine_smoke.py`.
- Current inventory/layout:
  `README.md`.
- Explicit historical/parked references:
  `tests/test_research_face_imports.py`,
  `docs/backtest/strategic-analysis-opus5-next-2026-09-16.md`,
  `docs/backtest/plan-ashare-engine-refactor-2026-09-18.md`,
  `docs/reviews/2026-09-25-minute-engine-review/raw/crosscheck-grok.md`,
  `docs/reviews/2026-09-25-minute-engine-review/raw/report-grok.md`,
  `docs/architecture/reviews/2026-09-18/plan-ashare-engine-refactor/adversarial-errata.md`,
  `docs/architecture/reviews/2026-09-18/plan-ashare-engine-refactor/grok-review.md`.

No dynamic import was found, but the static test import alone forbids removal.
The README entry is not changed because the path remains present.

### `backtest/research/engine.py` — KEEP

Public definitions are the same five names as the legacy engine.

References found:

- Dynamic module string and `BacktestConfig` assertion:
  `tests/test_research_face_imports.py`.
- Current parked-boundary references:
  `docs/backtest/engine-ashare-correctness.md`,
  `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md`,
  `docs/backtest/plan-ashare-engine-refactor-2026-09-18.md`.
- Analysis/review references:
  `docs/backtest/strategic-analysis-opus5-next-2026-09-16.md`,
  `docs/reviews/2026-09-25-minute-engine-review/raw/report-codex.md`,
  `docs/architecture/reviews/2026-09-19/plan-industry-align-p3-fees-codex-adv-r2/pattern-evidence.md`,
  `docs/architecture/reviews/2026-09-19/plan-industry-align-p3-fees-r1/grok.md`,
  `docs/architecture/reviews/2026-09-19/plan-industry-align-p3-fees-r1/merge-consensus.md`,
  `docs/architecture/reviews/2026-09-18/plan-ashare-engine-refactor/adversarial-errata.md`,
  `docs/architecture/reviews/2026-09-18/plan-ashare-engine-refactor/grok-review.md`,
  `docs/architecture/reviews/2026-09-18/plan-ashare-engine-refactor-2026-09-18/cursor-composer-2.5-fast.md`,
  `docs/architecture/reviews/2026-09-18/plan-ashare-engine-refactor-2026-09-18/cursor-cursor-grok-4.6-xhigh-fast.md`.

Its production usefulness may be doubtful, but “dead” is unproved while the
dynamic-import contract test intentionally owns it.

### v7 facade and native owner — KEEP

`backtest/research/csv_minute_backtest_v7.py` owns `simulate_v7`,
`load_index_daily`, `summarize_v7`, `write_run_artifacts`, `load_pool_days`,
`_load_cli_bars`, `build_parser`, `write_run_config`, and `main`. It also
re-exports imported fee/rule/session/native-engine objects. It has no
`__all__`, so existing attribute access remains a public compatibility fact.

The retained native exports from `strategy7_engine.py` are `NAME_BUDGET`,
`Lot`, `Position`, `SimResult`, record/frame conversion helpers,
`MinuteSession`, `AccountingPolicy`, `prepare_calendar`, `prepare_main_inputs`,
minute hooks/chronological handlers, and `simulate_native`.

Production/code consumers found:

- `backtest/research/csv_minute_backtest.py`
- `backtest/research/csv_minute_backtest_topk_app_dropout.py`
- `backtest/research/fullstrat_research_hooks.py`
- `backtest/research/fullstrat_research_runners.py`
- `backtest/research/fullstrat_research_v7.py`
- `backtest/research/lot_rounding.py`
- `backtest/research/minute_bar_scan_host.py`
- `backtest/research/minute_cash_order.py`
- `backtest/research/minute_classification.py`
- `backtest/research/strategy_book_helpers.py`
- `backtest/research/unified_exit_modea.py`
- `backtest/research/unified_exit_modeb.py`
- `backtest/research/unified_exit_precheck.py`
- `backtest/research/run_protocol/adapters/v7.py`
- `backtest/research/run_protocol/facade.py`
- `backtest/research/exports/minute_sensitivity_b_20260920/verify_harness.py`

Script consumers found:

- `scripts/research/generate_off_byte_baseline.py`
- `scripts/research/generate_v7_app_baseline.py`
- `scripts/research/report_minute_cash_order.py`
- `scripts/research/run_minute_sensitivity_b.py`
- `scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py`
- `scripts/research/verify_run_protocol_lake_parity.py`

Test references found:

- `tests/test_ashare_bars.py`
- `tests/test_ashare_fee_wiring.py`
- `tests/test_ashare_minute_frame_migration.py`
- `tests/test_ashare_simulate_import_fence.py`
- `tests/test_ashare_simulate_predicates.py`
- `tests/test_ashare_volume_cap.py`
- `tests/test_b7_on_short_cash.py`
- `tests/test_csv_minute_backtest_v7.py`
- `tests/test_exdiv_ref_fen.py`
- `tests/test_exdiv_refprice_engines.py`
- `tests/test_fullstrat_research_hooks.py`
- `tests/test_minute_bar_scan_host_topk_app_dropout.py`
- `tests/test_minute_bar_scan_host_v7.py`
- `tests/test_minute_cash_audit.py`
- `tests/test_minute_orders_cli.py`
- `tests/test_minute_stop_trigger.py`
- `tests/test_participation_rate_precheck_remaining.py`
- `tests/test_pool_duplicate_codes.py`
- `tests/test_rb16_accounting_invariants.py`
- `tests/test_research_run_protocol_csv_minute.py`
- `tests/test_research_run_protocol_grid_modeb.py`
- `tests/test_research_run_protocol_joint_return.py`
- `tests/test_research_run_protocol_minute_orders.py`
- `tests/test_research_run_protocol_types.py`
- `tests/test_research_run_protocol_v7.py`
- `tests/test_research_run_protocol_views.py`
- `tests/test_tail_window_lake_regressions.py`
- `tests/test_tail_window_peak_audit_regressions.py`
- `tests/test_tail_window_v7.py`
- `tests/test_topk_app_dropout.py`
- `tests/test_v7_cash_chronology.py`
- `tests/test_v7_frame_calendar.py`
- `tests/test_v7_minute_fold.py`

Current entry/contract documentation found:

- `README.md`, `AGENTS.md`, `CONTRIBUTING.md`
- `docs/backtest/README.md`
- `docs/backtest/research-backtest-entry.md`
- `docs/backtest/v7-main-engine-migration-2026-10-06.md`
- `docs/backtest/note-minute-scan-status-2026-10-05.md`
- `docs/backtest/note-minute-strategies-bar-scan-wire-2026-10-03.md`
- `docs/backtest/note-minute-engine-unify-ceiling-u1-2026-10-02.md`
- `docs/backtest/minute-fill-policy-ssot.md`
- `docs/backtest/engine-ashare-correctness.md`
- `docs/backtest/rb12-ledger-operation-matrix-2026-10-06.md`
- `docs/backtest/rb16-accounting-invariants-2026-10-06.md`
- `docs/backtest/plan-v7-minute-host-wire-2026-10-04.md`
- `docs/backtest/plan-topk-app-dropout-minute-host-wire-2026-10-04.md`

Additional matches are historical provenance, not deletion permission:
`docs/backtest/{s2c-*,s2e-*,plan-*,note-*,handoff-*,reviews/**,_archive/**}`,
`docs/reviews/2026-09-25-minute-engine-review/**`, and
`docs/architecture/reviews/**`. Frozen config references are
`backtest/research/exports/minute_sensitivity_b_20260920/batch{1,2,3_modeb}/manifest.json`
and `batch4_fullstrat/recipes.json`.

Dynamic risk is confirmed: module aliases (`v7.<name>`), lazy facade imports,
script paths and manifest command strings all exist. The migration note's
deleted `_DayCursor` / `_run_chronological_day` are symbols, not surviving
files; no RB-17 deletion is available there.

### `oskh_core/turnover_resist_bridge.py` — KEEP

Public `__all__`: `compute_turnover_resist`, `is_ffi_available`, `bridge_mode`;
all are identity re-exports from `oskh_factors.bridge.turnover_resist`.

Python references found:
`scripts/data/refresh_tr_store_window.py`,
`scripts/tr/backfill_turnover_resistance_bands.py`,
`scripts/tr/compute_turnover_resistance_bands.py`,
`scripts/gates/verify_tr_bridge_import_ssot.py`,
`tests/test_tr_bridge_import_ssot.py`,
`tests/test_turnover_resist_bridge.py`.

Documentation references found:
`README.md`,
`docs/prompts/prompt-rust-turnover-resistance.md`,
`docs/backtest/repo-analysis-vs-brainstorm-2026-09-15.md`,
`docs/backtest/plan-h11-chip-slowpath-inventory-2026-09-15.md`,
`docs/backtest/chip/chip-slowpath-inventory-2026-09-15.md`,
`docs/backtest/chip/rfc-turnover-resistance-bands.md`,
`docs/backtest/chip/turnover-resist-bridge-selection.md`,
`docs/backtest/chip/turnover_resistance.md`, and the associated architecture
review records. The existing AST gate makes the target path contractual.

### `backtest/chip_algorithm.py` — KEEP

Public `__all__`: `adapt_columns`, `adj_minute_chip_distribution`,
`adj_minute_prices`, `bb_position`, `compute_chip_factors`,
`compute_crossday_turnover_resistance`, `compute_equal_weight_cyqk`, `cyq`,
`daily_chip_distribution`, `derived_chip_factors`, `get_adj_factor`,
`hybrid_chip_distribution`, `minute_chip_distribution`,
`turnover_chip_factors`, plus the five underscored shares helpers.

Every Python import found:
`scripts/research/spot_check_chip_factors.py`,
`scripts/research/full_market_equal_weight_resist.py`,
`scripts/research/full_market_canonical_resist.py`,
`scripts/research/full_market_equal_weight_resist_v2.py`,
`scripts/research/chip_window_sensitivity.py`,
`scripts/research/full_market_chip_resist.py`,
`backtest/research/verify_mvp_min.py`,
`backtest/research/verify_chip_pool_enhancement.py`,
`backtest/research/verify_minute_chip.py`,
`backtest/research/verify_chip_factor_consistency.py`,
`backtest/research/verify_adj_minute_chip.py`,
`backtest/research/verify_float_shares_time_dimension_baseline.py`,
`backtest/research/rolling_ic_chip_factors.py`,
`backtest/research/filter_stock_pool_by_chip.py`,
`backtest/research/filter_chip_stocks.py`,
`backtest/research/evaluate_turnover_chip_factors.py`,
`backtest/research/daily_chip_logger.py`.

The path is also referenced by Rust parity comments and the chip/TR docs under
`docs/backtest/chip/`, `docs/prompts/`, `docs/knowledge/incidents/`, and
`docs/architecture/reviews/`. This is a compatibility hub, not a duplicate
implementation.

### `scripts/data/export_strategy10_pool.py` — KEEP

Public names: `REPO_ROOT`, `main`; `main` is an identity alias of
`scripts.data.export_ta_pool.main`.

References found:
`scripts/data/refresh_tr_store_window.py`,
`backtest/research/strategy10_rules.py`,
`docs/backtest/chip/turnover_resistance_tr_bollinger.md`,
`docs/backtest/plan-version11-machip-csv-2026-09-21.md`,
`docs/backtest/_archive/plans/plan-source-b-ta-pool-2026-09-13.md`,
`docs/backtest/reviews/addendum-batch4-v10-s10tr-fill-2026-09-21.md`,
`docs/backtest/reviews/results-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md`,
`docs/backtest/reviews/addendum-batch4-v9-s9bvot-fill-2026-09-21.md`,
`docs/architecture/reviews/2026-09-21/pr-149-batch4-v10-s10tr/grok.md`,
and the checked-in batch4 v9/v10 README/manifest/CSV provenance files.

It remains a documented executable path even though current top-level guidance
prefers `export_ta_pool.py`; removing it would break documented commands.

### Run-protocol adapters — KEEP

Candidates:

- `adapters/csv_minute.py`: `simulate`, `run`, `run_cli`
- `adapters/v7.py`: `simulate_v7`, `run_cli`
- `adapters/joint_return.py`: `replay`, `run_replay`, `run_cli`
- `adapters/grid_modeb.py`: `run_modeb`, `run_cli`
- `adapters/minute_orders.py`: `run_minute_orders_research`,
  `run_minute_orders_research_with_artifacts`, `run_cli`

`backtest/research/run_protocol/facade.py` lazily imports every listed entry.
References/tests found in `backtest/research/research_family_tags.py`,
`tests/test_research_run_protocol_{csv_minute,v7,joint_return,grid_modeb,minute_orders}.py`
and `docs/backtest/note-minute-engine-p2-adapters-2026-10-02.md`. Repeated
function names are protocol slots for different native families, not duplicate
adapters.

### Fee compatibility re-export — KEEP

`backtest/research/ashare_fees.py` publicly owns `FeeSchedule`,
`BILATERAL_10BP`, `QLIB_PORTANA`, `DEFAULT_SCHEDULE` and the fee constants. Its
`trade_commission` name is intentionally the same object as
`backtest.research.ledger_math.trade_commission`.

References found in production code:
`backtest/research/{csv_ledger,csv_simulate_loop,csv_minute_backtest,csv_minute_backtest_v7,minute_cash_order,strategy7_engine,unified_exit_modea}.py`.
References found in tests:
`tests/test_{ashare_fees,ashare_fee_wiring,ashare_volume_cap,bt_run_manifest,qlib_bin_daily,rb12_ledger_math,rb16_accounting_invariants,tail_window_primitives,tail_window_v7,topk_app_dropout,v7_minute_fold}.py`
and `tests/test_tail_window_peak_audit_regressions.py`. The re-export is also
documented by `docs/backtest/rb12-ledger-operation-matrix-2026-10-06.md` and
the fee/engine plans and reviews. It is not removable or duplicative.

### Similar verification copies — UNSURE, no retirement

The following basename pairs were checked rather than assumed dead:

- `backtest/research/verify_mvp_min.py` /
  `scripts/gates/verify_mvp_min.py`
- `backtest/research/verify_chip_pool_enhancement.py` /
  `scripts/gates/verify_chip_pool_enhancement.py`
- `backtest/research/verify_chip_factor_consistency.py` /
  `scripts/gates/verify_chip_factor_consistency.py`
- `backtest/research/verify_adj_minute_chip.py` /
  `scripts/gates/verify_adj_minute_chip.py`
- `backtest/research/verify_float_shares_time_dimension_baseline.py` /
  `scripts/gates/verify_float_shares_time_dimension_baseline.py`
- `backtest/research/verify_minute_chip.py` /
  `scripts/gates/verify_minute_chip.py`
- `scripts/research/verify_turnover_resistance_alignment.py` /
  `scripts/gates/verify_turnover_resistance_alignment.py`

These are not byte-identical shims. Gate-side paths are runbook/CI-facing;
research-side paths are host tools and import the chip compatibility surface.
References occur in `tests/test_b8_lot_rounding_guard.py`,
`tests/test_turnover_resistance_alignment_gate.py`,
`scripts/_write_chip_readme_once.py`, the host-lake gate cookbook, chip
runbooks/plans/incidents and architecture reviews. Selecting an SSOT and
migrating those references is a separate semantic task, so RB-17 marks the
group UNSURE and changes none of them.

### Orphan-looking tools — KEEP because zero references was not proved

`backtest/tools/parse_log.py` exports `parse_backtest_log_advanced` and
`print_daily_summary_advanced`, and has a direct `__main__` path. No Python
import consumer was found, but
`docs/backtest/strategic-analysis-opus5-next-2026-09-16.md` explicitly
inventories it and
`docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/codex.md`
also names the path. It therefore fails RB-17's “zero references of any kind”
retirement threshold.

`backtest/tools/read_app_data.py` exports `read_special_excel_format` and
`read_simple_method`, with a direct argv-based `__main__` path. No Python
import consumer was found, but it is referenced by
`docs/backtest/plan-h10-ci-path-gates-2026-09-15.md`,
`docs/architecture/reviews/2026-09-15/h10-ci-path-gates/grok.md`, and
`docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/codex.md`.
It is retained.

## Guard and ZERO-DIFF boundary

`tests/test_rb17_retired_modules.py` records an empty retired-path tuple, checks
absence/reference invariants for any future one-item addition, and locks object
identity for the v7, turnover-resist, chip-algorithm, fee and strategy-10
compatibility surfaces. No runtime module, fixture, baseline, HELP_LOCK, book
order, CLI parser/help or output writer changed.
