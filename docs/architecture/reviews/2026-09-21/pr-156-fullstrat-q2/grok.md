# PR #156 · Grok review · Q2 + H2

Implementation: `9a1a609` (`research/batch4-fullstrat-clock-slip-hooks`).
Human cut: Q2 replaces Q1, H2 swaps every clock-cell fill, strict same-day expiry,
UNFILLED/all-cash accepted, expired sells reevaluate next session. `production_C=frozen`.
No merge; new numerical results await post-merge 4090.

Grok CLI was available. The initial tool-driven attempt ended without findings;
a full supplied-source review then returned “request changes”. Its only blocker
assumed same-day ModeB exits. Canonical `unified_exit_modeb._instance_path` starts
at `buy_i + 1`; the two-name T+1 cash-recycling pin disproves that premise.
No T+0 workaround was added. The same follow-up also confirms rule 0 was already
excluded from production ranked metrics.

The added cash-recycling fixture exposed a separate real defect: ModeB's native
entry mark equals its native fill, but slip requires a distinct market mark.
The research replay now uses the unslipped entry close, carries it across missing
minutes, and applies E-R6 to shares and marks. Entry-only mark_end PnL is corrected
as well. Book/v7 direct zero-impact economic replay and ModeB ranking parity pins
supplement the default-adapter byte comparisons.

Other review notes resolved: expired buys are distinct from cash rejects;
ModeB rankings remain inside each cell directory; stub base is `32b78b1`;
NAV metrics use the simulation's recorded initial cash.

Final gates (explicit PATH `/workspace/vanna312/bin`, no lake run):

- `python3 -m pytest -q tests/test_fullstrat_research_hooks.py`: **48 passed** (0.99s).
- `python3 -m pytest -q -m "not production and not benchmark" tests/ || true`:
  **1475 passed, 2 skipped, 24 deselected**, one existing TR-window warning (22.76s).
- `python3 -m ruff check <all 7 touched Python files>`: pass.
- `python3 scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py --help`: pass.
- diff / UTF-8 without BOM / NUL=0 and no #151/#152 contested-file overlap: pass.

The focused follow-up ran after the final gates, with canonical T+1 source,
current research accounting, and the new pins supplied directly (`--no-subagents
--disable-web-search --tools '' --verbatim --max-turns 1 --prompt-file ...`).
Its final response is preserved below. This is review evidence, not merge authorization.

## Focused follow-up verdict

**Approve.** The T+1 blocker does not hold. Canonical `_instance_path` walks `range(buy_i + 1, …)`, and `evaluate_exit_modeb` never sees list-date minutes, so it cannot fill that day or write `pending_proceeds[list_date]`. Default research exits call that engine and only slip a later fill. `run` credits pending cash at the start of the sell date, before close-entry buys, which matches production “sells before daily-close buys.” The two-name test is the right pin: A fills day0, B is cash-rejected day0, A sells day1, B admits on that recycle. No T+0 credit was added.

Skipping `rule == 0` is the same ranking cut as production’s drop of `oracle` / `delist_zero` / `anchor_hold_end`. The zero-impact ranking pin plus `anchor_hold_end` absent from baseline ranked labels is enough.

The slip mark fix is a real research-only defect, and the new accounting is the right shape. Production `build_daily_equity` may seed a new lot at `buy_price` because the native buy is the daily close. With slip those diverge, so the replay marks the entry session at the unslipped last close, freezes that mark across missing later minutes, applies E-R6 to shares and that mark, and uses the same unslipped mark for entry-only `mark_end` PnL. Native trade stats stay; portfolio return/drawdown come from the full cash/holding replay. The missing-minute + factor test (`qty * (10 - 10.01 * 1.001)`, flat equity) is the check that belongs here. Production files stay frozen.

The other prior notes are addressed: expiry is not `skip_cash`; ModeB artifacts are per cell; stub `base_tip` is `32b78b1`; `initial_cash` is the simulated pool; Book/v7 economic trade+equity pins and ModeB full ranking pins exist. Q2 lot-from-fill, H2, expiry, and Q33 `mark_end_zero` (only on the last session, and not in ranked cells) stay in their existing bounds. Research `build_daily_equity` omits the Q33 last-day drop; that is not a new experimental-loop hole while rule 0 / `delist_zero` stay out of rank.

Keep `production_C` frozen, do not merge, and do not publish numbers until post-merge 4090. 48 hook tests plus the post-fix gate are the merge bar for this research path.

