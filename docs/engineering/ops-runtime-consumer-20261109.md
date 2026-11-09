# Ops runtime consumer and boundary review (2026-11-09)

Human requires the generic review/publication code in this repo to move to
[grok-bot-ops #187](https://github.com/baiyibing/grok-bot-ops/pull/187).
Receiver merged revision: `dd88773d76dcb6703db541cd877dcbfb6088e100`
(runtime API v1; ops CI passed). The old S4 source-copy rule is
superseded for BT. This change does not modify OSkh standalone consumers.

| Former BT implementation | Current ownership |
| --- | --- |
| `scripts/run/multi_ai_common.py` | Deleted. Ops owns model catalog, command construction, retries, output collection and runner. |
| `scripts/run/run_multi_ai_review.py` | Thin call to the ops entry; [BT review profile](../../config/ops/bt-review.json) retains the exact framework and role text. |
| `scripts/run/run_codex_adversarial_lanes.py` | Thin call to the ops entry; [BT adversarial profile](../../config/ops/bt-adversarial.json) retains the three stances and prompt. |
| `scripts/ops/push_github_pr_via_api.py` | Thin call to the ops Git Data / PR helper. Parser/producer tests move to ops. |

Configure an absolute source checkout with `MYQUANT_OPS_ROOT`, or pass
`--ops-root` to a retained BT CLI. It must contain ops runtime API v1 and the
entrypoint. The same interpreter starts a separate ops process; BT supplies
its repo root and domain profile. Overrides of those two injected options are
refused. Missing/old ops fails explicitly. There is no local implementation,
vendor archive, default sibling search or fallback catalog.

```text
<configured-python> scripts/run/run_multi_ai_review.py --ops-root <absolute-ops-checkout> --plan docs/<plan>.md --dry-run
<configured-python> scripts/run/run_codex_adversarial_lanes.py --ops-root <absolute-ops-checkout> --plan docs/<plan>.md --out-dir docs/<review-dir> --dry-run
<configured-python> scripts/ops/push_github_pr_via_api.py --ops-root <absolute-ops-checkout> --dry-run
```

The shared [runtime contract](https://github.com/baiyibing/grok-bot-ops/blob/master/docs/multi-ai/shared-runtime-20261109.md)
describes explicit roots, profiles and CLI behavior. Ops owns the current
model catalog; BT's old snapshot is removed. Research/backtest imports and
normal pytest do not require an ops checkout. The new data-free
`verify_ops_consumer_boundary.py` gate rejects the retired common module,
local runner/publisher functions, model assignments and heavy imports in the
three thin entries. CI runs it alongside the existing infra boundary gate.

## Infra verification and remaining ownership questions

The infra pin stays at `af27dd08c6b5e3653fa686c6f60e541afd1a4941` in all install
entrypoints. Vendor processing, CNINFO producers, lake write/repair, L2
processing, storage IO and shared contracts have already moved. BT's public
reader/cache/TR/calendar/industry/symbol/manifest facades call installed
`myquant_infra` APIs; missing infra does not restore source implementations.
Private read credentials and pandas 3.0.6 were exercised by the merged #587
Linux CI (9,979 passed, 88 skipped, 21 deselected).

This review checked executable imports and storage/network entrypoints in
`scripts/`, `oskh_data/`, `common/infra/` and `qlib_cost/`, plus their research
callers against the [four-repo boundary](https://github.com/baiyibing/MyQuant-infra/blob/af27dd08c6b5e3653fa686c6f60e541afd1a4941/docs/architecture/boundary.md).
It found no additional demonstrated copy of an already migrated infra
producer in those surfaces. This is not a claim that every production data
source or every line of the repository has been exercised.

- Strategy-specific pool exports, factor analyses, TR numerical producers,
  fee/execution rules and economics gates stay here. Host clock/configuration,
  logger/trace/security and optional Redis client lifecycle also remain host
  policy under the explicit infra boundary exclusions.
- `minute_orders_write_lake_staging` is a research contract/report planner;
  inspection confirms that it does not process or write production lake bars.
  Its name alone is not evidence of duplicate infra ETL.
- **A separate MyQuant ownership candidate remains:** `qlib_cost/qlib_workflow.py`
  and `factor_expr.py` implement an older Qlib training/handler example, called
  by the historical chip notebook (`scr.*` paths). They are not runtime
  consumers of the vectorized CLI. They are not infra or ops utilities and
  have not been migrated by this change. Do not describe the migration audit
  as having no remaining candidates, or enable their PortAna path here.

No real agent, Git Data publication, data collection, lake write or backtest
experiment is performed by the migration validation. Host consumer tests use
synthetic ops entries; ops tests exercise the shared runner with mocked ports.
