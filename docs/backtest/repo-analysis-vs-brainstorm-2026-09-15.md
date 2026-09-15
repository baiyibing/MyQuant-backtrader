# Repo analysis vs brainstorm（2026-09-15）

- **Status**: docs-only snapshot after H1–H16 landed on `master` (tip at branch cut ≈ `dd35fe9` / PR #51 overview).
- **Producer**: local backtest assistant (Grok Bot executor). **Opus Agent CLI auth failed** (Origin-scoped key / no Cloud Agent Pro); this document was written by reading the brainstorm stack + real paths in-tree — not a generic code review and not a CloudAgent run.
- **Scope**: map architecture to themes A–F / H1–H16; validate hot-path claims; recommend next 3–5 work packages. **No sell-semantics or runtime trading-code changes.**
- **Parents**: [brainstorm-overview-2026-09-15.md](brainstorm-overview-2026-09-15.md) · [plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md) · [plan-brainstorm-next-heavy-2026-09-15.md](plan-brainstorm-next-heavy-2026-09-15.md)

**G don't-dos (inherited, not contested):** change 6/8 sells; reopen `--asof`; PortAna as truth; fail-closed → skip; big-bang merge daily vs minute sells; physically delete Cerebro; reimplement MyQuant CYQ feeder here; clone LEBS / live stack here; CloudAgent as delivery path.

---

## 1. Architecture map

### 1.1 Research face entrypoints (vectorized CSV)

| Role | Path | Notes |
|------|------|-------|
| Daily engine | `backtest/research/csv_daily_backtest.py` | `simulate` / `run` / `main`; strategies 1–6/8/9/10 via `--strategy` |
| Minute engine | `backtest/research/csv_minute_backtest.py` | same books; sell via `scan_held_day` (+ optional numba trail) |
| Strategy 7 (turtle position machine) | `backtest/research/csv_minute_backtest_v7.py` | **not** in strategy-book choices; requires `--pool-dir` |
| Shared CLI / books | `backtest/research/csv_strategy_books.py` | `add_csv_backtest_common_args` (H2); `apply_csv_strategy`; pool resolve for 9/10 |
| Ledger / A-share fills | `backtest/research/csv_ledger.py` | buys, `_sell`, limit-up chase, `market_close_mark`, board limits |
| Pool parse | `backtest/research/csv_pool.py` | `parse_pool_csv` / `validate_pool_dir`; contract: [pool-csv-contract.md](pool-csv-contract.md) |
| Market facts | `backtest/research/market_layer.py` | lake-backed bar helpers |

There is **no** `backtest/lebs/` in this repo. Do not run `python -m backtest.lebs` here ([engine-positioning-ssot.md](engine-positioning-ssot.md)).

### 1.2 Simulate skeleton (shared buy/chase/mark; split sells)

```
csv_*_backtest.simulate()
  ├─ prepare_strategy_hooks / init_sim_state     ← csv_simulate_loop.py
  ├─ per day:
  │    ├─ SELL LOOP  (engine-local; intentionally split)
  │    │    daily:  day_bar_and_prev_closes + bar rules + _sell
  │    │    minute: scan_held_day(+numba trail) + _sell + limit-down defer
  │    ├─ run_chase_due_day(quotes_for=…)       ← shared
  │    ├─ run_pool_buys_day(buy_quote_for=…)    ← shared
  │    └─ append_equity_and_eod_marks(…)        ← shared (H5 per-code mark cache)
  └─ summarize / write_run_artifacts
```

Evidence:

- `csv_simulate_loop.py` docstring: *“Sell loops stay in each engine on purpose (daily bar rules vs `scan_held_day`).”*
- `csv_common.day_bar_and_prev_closes` — H8 `searchsorted` helper used by daily sell / chase / pool quote closures.
- Minute `scan_held_day` — Python reference default; numba trail only when no callables / `CSV_SCAN_HELD_DAY_BACKEND=numba` (PR #34 / hotpath plan).

**Do not big-bang merge** the two sell engines; residual Theme A work is micro-opts inside the minute sell ring, not a unify PR.

### 1.3 Strategy books

Registered in `csv_strategy_books.py` (`version1`…`version6`, `version8`, `version9`, `version10`). Sell books remain distinct (`sell_book` stats: v6/v8/v9/v10). Strategy **7** stays a separate minute entry. Strategies **9** / **10** refuse repo `stock_pool/` and require exporter-written `--pool-dir` (`exports/…`).

### 1.4 Pool CSV pipeline

| Layer | Path | Role |
|-------|------|------|
| Contract SSOT | [pool-csv-contract.md](pool-csv-contract.md) | `YYYYMMDD.csv`, bare 6-digit, as-of = buy day T; `stock_pool/` mutable vs `exports/` frozen (H7) |
| Quality library | `backtest/research/pool_list_quality.py` | H9 + H16: histogram, overlap, churn, invalid calendar stems, JSON/md |
| Quality CLI | `scripts/research/report_pool_list_quality.py` | thin entry |
| Exporters (upstream of books 9/10) | `scripts/data/export_strategy9_pool.py`, `export_ta_pool.py` | write contract CSVs; TR path reads Store, does not recompute PDF |

**run-manifest hard** (consume MyQuant `myquant.run-manifest/1`) remains **deferred** — soft list-quality does not replace it.

### 1.5 Chip / TR

| Bucket | Canonical path | Status |
|--------|----------------|--------|
| Production TR | `turnover-resist/` (Rust) → `oskh_factors/bridge/turnover_resist.py` → Store → strategy 10 / `tr_filter` / `export_ta_pool` | leave (inventory §A) |
| Minute chip research | `oskh_factors/chip/core.py` — `minute_chip_distribution` | optional numba (H15); Python default |
| Hybrid / short-window CYQ math | `hybrid_chip_distribution`, `qlib_cost/cyq.py` | leave / later (D1: hybrid ~1 ms) |
| Full-market daily `winner_ratio` | **sibling MyQuant** `my_scripts/build_winner_ratio.py` (numba) | **not** this tree (H13) |
| Cerebro chip Indicators | `backtest/chip_indicator.py`, `chip_backtest.py`, … | fossil (inventory §C) |

Inventory SSOT: [chip/chip-slowpath-inventory-2026-09-15.md](chip/chip-slowpath-inventory-2026-09-15.md).

### 1.6 Fossils

- Cerebro main gate: `backtest/backtest_main_full.py --allow-cerebro-fossil`.
- H1 moved archaeological order/fund docs to `docs/backtest/_archive/fossils/`.
- H4: research vectorized face must not import `backtrader` (`tests/test_research_face_imports.py`); chip Cerebro contrasts may still use bt.
- **Observe-retire, do not delete.**

### 1.7 CI (data-free)

`.github/workflows/python-tests.yml`:

1. **Contract gates** (pre-pip): `verify_oskh_data_contract.py`, `verify_data_path_ssot.py`, `verify_no_hardcoded_machine_paths.py`, `verify_tr_bridge_import_ssot.py` (H10 + H12).
2. Install `requirements.txt` (includes numba — H6).
3. Assert `import numba`.
4. `pytest -q -m "not production and not benchmark"`.

Lake-backed chip/TR/L2 gates stay **host-only** — do not add to CI.

---

## 2. Theme A–F scorecard vs H1–H16

Legend: **closed** = safe slice done on master · **residual** = still open but bounded · **next small slice** = candidate WP below · **leave alone** = deliberate non-work / don't-do.

### A — Performance (vectorized hot path; no Cerebro rewrite)

| Item | State | Real paths |
|------|-------|------------|
| Shared simulate skeleton | **closed** (#34) | `csv_simulate_loop.py` |
| Optional numba `scan_held_day` trail | **closed** (#34) | `csv_minute_backtest.scan_held_day` + `bench_scan_held_day.py` + parity tests |
| H5 daily mark per-code cache | **closed** | `append_equity_and_eod_marks` · `bench_daily_mark.py` |
| H8 daily sell/chase/pool `searchsorted` | **closed** | `csv_common.day_bar_and_prev_closes` · `bench_daily_sell_index.py` |
| Minute sell-ring deeper micro-opt | **residual / next small slice** | still inside `scan_held_day` / day-span helpers; **not** sell-book unify |
| Big-bang merge daily↔minute sells | **leave alone** | G don't-do |

### B — Strategy books / entrypoints

| Item | State | Real paths |
|------|-------|------------|
| Shared argparse | **closed** (H2) | `add_csv_backtest_common_args` |
| Books 1–6/8/9/10 + v7 split | **closed** (pre-H + unify plans) | `csv_strategy_books.py` · `csv_minute_backtest_v7.py` |
| Two sell engines remain split | **leave alone** (intentional) | daily bar rules vs `scan_held_day` |

### C — Pool / list pipeline

| Item | State | Real paths |
|------|-------|------------|
| `stock_pool/` vs `exports/` SSOT | **closed** (H7) | pool-csv-contract lifecycle section |
| List-quality CLI (soft) | **closed** (H9) | `pool_list_quality.py` · `report_pool_list_quality.py` |
| Soft+ deepen (JSON/md, top-N, churn, calendar stems) | **closed** (H16) | same modules |
| run-manifest hard consume | **leave alone / deferred** | needs product sign-off; see next-heavy queue head |

### D — Chip / TR compute & product boundary

| Item | State | Real paths |
|------|-------|------------|
| Slow-path inventory | **closed** (H11) | `chip/chip-slowpath-inventory-2026-09-15.md` |
| CYQ feeder vs Rust TR boundary | **closed** (H13) | inventory §E · CONTRIBUTING don't-do |
| D1 minute/hybrid profile | **closed** (H14) | `bench_minute_chip_hotpath.py` · [h14 results](chip/h14-d1-minute-chip-profile-results-2026-09-15.md) |
| D2 optional numba minute chip | **closed** (H15) | `core.minute_chip_distribution` · ~58× synth (Grok review) |
| hybrid / `calc_curpdf` later offload | **leave alone** (for now) | D1: hybrid ~1 ms; not production TR |
| Reimplement MyQuant CYQ here | **leave alone** | G / H13 don't-do |

### E — Data contracts / CI

| Item | State | Real paths |
|------|-------|------------|
| CI numba assert | **closed** (H6) | workflow + parity tests |
| Path-SSOT / machine-path gates | **closed** (H10) | `scripts/gates/verify_*` |
| TR bridge import gate in CI | **closed** (H12) | `verify_tr_bridge_import_ssot.py` |
| Lake-backed chip/TR gates in CI | **leave alone** | host-only by design |

### F — Engineering face

| Item | State | Real paths |
|------|-------|------------|
| Fossils archive + CONTRIBUTING | **closed** (H1) | `_archive/fossils/` · root `CONTRIBUTING.md` |
| L2 fence | **closed** (H3) | AGENTS / README; `l2_analytics/` offline only |
| Research face no bt import | **closed** (H4) | `test_research_face_imports` |
| Cerebro physical delete | **leave alone** | observe-retire only |
| This analysis doc + pointers | **this PR** | docs only |

---

## 3. Hot paths & performance — validate / challenge H8 · D1 · D2

### 3.1 H8 daily sell index — **validated as landed; scope was index, not sell logic**

- **Claim**: replace per-day `.loc` / `index < day` mask with `DatetimeIndex.searchsorted` + `iloc` for day row + prior closes.
- **Code**: `csv_common.day_bar_and_prev_closes` implements exact naive semantics (`day` missing → `None`; first bar → `None`; else row + strict-prior closes). Wired from daily `simulate` sell loop and chase/pool quote closures (`csv_daily_backtest.py` ~344–445).
- **Bench**: `scripts/research/bench_daily_sell_index.py` compares naive vs fast and prints `speedup naive/fast`.
- **Challenge / residual**: H8 does **not** claim end-to-end daily NAV speedup on F lake (no lake in CI). Speculative cross-day cursors / full calendar precompute remain deferred (plan-h8 §明确不做). Theme A residual is **minute** sell-ring, not another daily `.loc` pass.

### 3.2 H14 / D1 minute chip profile — **validated**

From [chip/h14-d1-minute-chip-profile-results-2026-09-15.md](chip/h14-d1-minute-chip-profile-results-2026-09-15.md) (80×240 synth, box Python 3.12):

| Kernel | ms/call | Verdict after D1 |
|--------|---------|------------------|
| `minute_chip_distribution` | ~50.7 | hottest → D2 numba |
| `hybrid_chip_distribution` | ~1.01 | leave |
| `calc_curpdf` × N | ~0.69 | leave (short window) |
| `calc_cumpdf` (already jit) | ~0.021 | leave |

cProfile: minute path dominated by Python `for` + per-bar `np.zeros` — matches the numba offload choice. **Challenge**: timings are synthetic; absolute ms will move on high-vol names / denser bins, but the **ordering** (minute ≫ hybrid ≫ cumpdf) is the decision input, not a production SLA.

### 3.3 H15 / D2 minute chip numba — **validated as optional offload; default still Python**

- **Code**: `minute_chip_distribution_python` (semantic lock) + `_minute_chip_distribution_numba` gated by `use_numba` / `MINUTE_CHIP_BACKEND` (`oskh_factors/chip/core.py`).
- **Evidence**: Grok review `docs/architecture/reviews/2026-09-15/h15-d2-minute-chip-numba/grok.md` records ~**58×** python vs numba on 80×240 synth @ vanna312; parity tests green when numba present.
- **Challenge**: (1) Python remains default — research callers must opt in; (2) speedup is box evidence, not a CI gate; (3) hybrid/curpdf intentionally untouched — do not treat D2 as license to Rust-rewrite chip or port MyQuant feeder.
- **Orthogonal**: minute **sell** numba (`scan_held_day` trail) is Theme A / #34, not D2. Do not conflate chip histogram offload with sell-book offload.

### 3.4 What is *not* hot enough to chase next

- Daily mark (H5) and sell index (H8) are already micro-optimized; next daily wins need stronger profiles.
- Production full-market TR is already Rust — Python `full_market_canonical_resist*` stays parity/research (inventory §D).
- Cerebro paths are fossils — optimizing them is out of scope.

---

## 4. Contracts & SSOT health

| Contract | Health | Gaps |
|----------|--------|------|
| Engine positioning (3 engines) | Strong — [engine-positioning-ssot.md](engine-positioning-ssot.md) + AGENTS + README aligned | Keep 1.3 `backtest-architecture-ssot` from being misread as three-repo master plan |
| Pool CSV + as-of = T | Strong — [pool-csv-contract.md](pool-csv-contract.md); soft quality tooling H9/H16 | Strict `validate_pool_dir` still not called by `run()` (by design); exporters must stay disciplined |
| `stock_pool/` vs `exports/` | Strong (H7) | Social/process: do not freeze experiments in `stock_pool/` |
| Path / machine-path SSOT | Strong in CI (H10) | Host scripts still need lake; CI correctly refuses lake gates |
| TR bridge import SSOT | Strong in CI (H12) | Shim `oskh_core.turnover_resist_bridge` must keep re-exporting factors bridge |
| CYQ vs TR product boundary | Strong (H13 + inventory §E + CONTRIBUTING) | New contributors may still mix “chip” / “CYQ” / “TR” vocabulary — point them at inventory §E |
| Presets cross-repo snapshot | Present — `tests/test_presets_cross_repo_snapshot.py` | Requires sibling 1.3 checkout for full meaning |
| A-share correctness | Documented — [engine-ashare-correctness.md](engine-ashare-correctness.md) | Limit-down = defer sell (incl. 6/8 trail); do not flip to skip |

**SSOT smell to watch:** multiple “full_market_*_resist” scripts under `scripts/data` and `scripts/research` (inventory lists both). They are leave/research duplicates — do not promote either to production TR SSOT.

---

## 5. Cross-repo boundaries

```
MyQuant                    MyQuant-backtrader (this)           OSkhQuant1.3
────────                   ─────────────────────────           ────────────
train / IC                 vectorized CSV research face        LEBS (MockQMT match)
export day-list CSV        chip research + optional numba      MockQMT true stack
numba full-market CYQ      Rust turnover-resist → Store        trade_decision + capital
  winner_ratio feeder      strategy books 1–6/8/9/10 + v7      Paper homology
run-manifest writer        consume lake read-only              downloads / vendor merges
(PortAna STOPPED)          Cerebro fossil (observe)            no first-party Cerebro
```

**Hard fences for this repo:**

1. Do **not** reimplement MyQuant `build_winner_ratio.py` / full-market daily CYQ here.
2. Do **not** clone LEBS / Redis / executor / live packages (`AGENTS` / `CONTRIBUTING`).
3. Do **not** treat vectorized NAV as Paper or PortAna truth.
4. Presets / pool dialect stay cross-checked with 1.3; sell books 6/8 stay locked here.
5. run-manifest **consume** is optional future product work — default stay deferred.

---

## 6. Risk register

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|------------|--------|------------|
| R1 | Accidental 6/8 sell-semantic drift while “unifying” loops | Med if big-bang attempted | High | Keep sell engines split; only micro-opts with golden + parity |
| R2 | Contributor reimplements CYQ feeder “for convenience” | Med | High (duplicate SSOT) | H13 docs + CONTRIBUTING don't-do; reject such PRs |
| R3 | Lake gates added to GitHub Actions | Low–Med | Med (red CI forever) | H10 comment block in workflow; host-only inventory |
| R4 | Numba set as default for minute chip or scan_held_day | Low | Med (subtle parity / env skew) | Keep Python default; env/kwarg opt-in |
| R5 | Cerebro deletion “cleanup” | Low | Med (lose fossil contrasts) | H1/H4/Fossil gate; observe-retire only |
| R6 | run-manifest hard without product contract | Med if rushed | Med (brittle cross-repo) | Keep deferred; soft list-quality covers local needs |
| R7 | Mixing `stock_pool/` mutable tree with frozen exports | Med | Med (irreproducible runs) | H7 SSOT; 9/10 refuse `stock_pool/` |
| R8 | Treating H14/H15 synth × as production SLA | Med | Low–Med | Document as research evidence; re-bench on real names before further offload |
| R9 | Fail-closed missing bars → skip (policy flip) | Low | High (silent holes) | Keep skip_no_bar / defer semantics; G don't-do |
| R10 | CloudAgent / Origin-key confusion as delivery path | Seen | Low (process) | Local Codex/Grok + Actions; this doc produced that way |

---

## 7. Recommended next 3–5 work packages

run-manifest hard stays **deferred** unless product explicitly requests it (no strong in-repo evidence it is blocking research right now — H16 soft quality already covers local pool hygiene).

### WP1 — Theme A: minute sell-ring micro-profile (no unify)

| | |
|--|--|
| **Goal** | Profile `scan_held_day` + day-span / `_slice_day` / quote helpers on synthetic sessions; list ≤2 safe micro-opts that do not touch sell reasons or 6/8 books. |
| **Files** | `csv_minute_backtest.py`, `scripts/research/bench_scan_held_day.py` (extend), new short plan under `docs/backtest/` |
| **Out of scope** | Merging with daily sell loop; changing trail/stop/gate reasons; Cerebro; lake NAV |
| **Acceptance** | Written profile note; any code change has Python↔numba parity green and golden minute tests green; Grok review no valid 🔴 |

### WP2 — Theme D residual: inventory “later” triage only (docs)

| | |
|--|--|
| **Goal** | Re-read inventory §D after H15; explicitly mark hybrid/`calc_curpdf` as **leave until product throughput need**; optional one-page “when to reopen” criteria. |
| **Files** | `chip/chip-slowpath-inventory-2026-09-15.md`, maybe `plan-brainstorm-next-heavy-*.md` |
| **Out of scope** | New numba/Rust kernels; MyQuant feeder moves |
| **Acceptance** | Docs PR; no algorithm change |

### WP3 — Theme E: host-only lake gate cookbook (docs + script index)

| | |
|--|--|
| **Goal** | Single README section listing which `scripts/gates/verify_*chip*` / TR alignment scripts are host-only, how to run them on F lake, and why they stay out of CI. |
| **Files** | `docs/backtest/README.md` or `docs/backtest/chip/README.md`; pointer from AGENTS |
| **Out of scope** | Wiring those gates into `python-tests.yml` |
| **Acceptance** | Contributor can find host gate list in ≤30s; CI workflow comments unchanged in spirit |

### WP4 — Theme C: list-quality “golden pool” fixture (soft, still not run-manifest)

| | |
|--|--|
| **Goal** | Tiny checked-in synthetic pool dir + pytest locking H16 reporters (churn / invalid stems / top-N) so regressions are CI-visible without MyQuant manifest. |
| **Files** | `tests/fixtures/…`, `tests/test_pool_list_quality*.py`, maybe `pool_list_quality.py` if gaps |
| **Out of scope** | Consuming `myquant.run-manifest/1`; changing simulate/sell |
| **Acceptance** | pytest green in data-free CI; contract doc one-line pointer |

### WP5 — Theme F: fossil import / entry smoke (optional small)

| | |
|--|--|
| **Goal** | Ensure `--allow-cerebro-fossil` still gates main entry; research face import test remains green after doc churn. |
| **Files** | existing `test_research_face_imports` / fossil gate tests; docs only if needed |
| **Out of scope** | Deleting fossil modules; new ProfitStrategy |
| **Acceptance** | CI green; no new bt imports on vectorized face |

**Default stance after this analysis:** stop expanding Hx soft hygiene; pick **WP1** only if minute sell latency bites a real research window; otherwise prefer **WP3** or **WP4** (docs/fixtures) over more offload.

---

## Appendix — H1–H16 → theme quick index

| Hx | Theme | One-liner |
|----|-------|-----------|
| H1 | F | Fossils archive + CONTRIBUTING |
| H2 | B | Shared argparse |
| H3 | F | L2 fence |
| H4 | F | Research face ≠ backtrader import |
| H5 | A | Daily mark cache |
| H6 | E | CI numba assert |
| H7 | C | stock_pool vs exports SSOT |
| H8 | A | Daily sell searchsorted |
| H9 | C | List-quality soft |
| H10 | E | Path / contract CI gates |
| H11 | D | Chip/TR inventory |
| H12 | E | TR bridge gate in CI |
| H13 | D | CYQ vs Rust TR boundary |
| H14 | D | D1 minute chip profile |
| H15 | D | D2 optional numba minute chip |
| H16 | C | List-quality soft+ |

PR index #34–#50: see [brainstorm-overview-2026-09-15.md](brainstorm-overview-2026-09-15.md).
