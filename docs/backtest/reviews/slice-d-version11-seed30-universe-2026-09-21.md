# Slice D review — version11 seed-30 / universe (2026-09-21)

- **PR**: [#152](https://github.com/baiyibing/MyQuant-backtrader/pull/152) `feat/version11-machip-csv` tip `c9b4380`
- **Target host**: `newtest_4090` machineId `6e8988e9-eaab-447c-ad5d-effde4604424`
- **Repo on host (intended)**: `D:\PycharmProjects\MyQuant-backtrader`
- **Status**: **STOPPED — D smoke not executed**. **Not claiming return/parity acceptance.** PR stays unmerged.

## Method (intended)

1. Sync `feat/version11-machip-csv` (incl. CI fix `c9b4380`) onto 4090 checkout without destroying unrelated local work.
2. Seed-30 (`export_strategy11_pool.py --sample 20240907`) same-universe vs each static archive under `backtest_output/ma_chip_edge_*` (7 dirs; ablation axes cyqk80 / cyqk90_nobb / nocyqk / nobb / …).
3. Classify diffs as fill price / fees / skip semantics; record signal/trade count OOM sanity bounds.
4. One full-universe sensitivity run (ST filter + exclude 688 per V9) on host lake `E:\stock_data` + real Rust pyd (record pyd `__file__` + version in manifest).
5. Out-of-tree run dirs on 4090 (e.g. `D:\exports\...` or `backtest_output\_scratch_v11_d\...`); no large numeric dumps committed.

## Blockers

### B1 — Executor cannot route to 4090

This run was dispatched as a **box-scoped** executor on the Grok Bot VM (`grok-bot-vm-344089598`).

- `Shell` / `Read` with `machineId=6e8988e9-eaab-447c-ad5d-effde4604424` still executed on the Linux box (bash); Windows paths / PowerShell were not interpreted on the host.
- MCP server `cursor` (CopyToBox / ListMachines) is **not available** in this executor context.
- Host lake `E:\stock_data`, `D:\anaconda3\envs\vanna312\python.exe`, and real Rust pyd were therefore **unreachable**.

**Need**: parent (or a non-box-scoped agent with local-exec) to run Slice D commands on machineId `6e8988e9-…` directly.

### B2 — Static archives not found on searchable surfaces

Per hard rule: do not invent numbers. Archives are expected at host `backtest_output/ma_chip_edge_*` (gitignored; see `.gitignore` `/backtest_output/`).

**Searched (box / git / docs) — all miss for the 7 archive dirs:**

| Path / surface | Result |
|---|---|
| `/workspace/wt-v11-impl/backtest_output/` | missing (dir absent) |
| `/workspace/MyQuant-backtrader/backtest_output/` | no `ma_chip_edge_*` dirs |
| `find /workspace -type d -iname 'ma_chip_edge*'` | none |
| `git ls-files 'backtest_output/**'` / `git log -- backtest_output/ma_chip_edge*` | empty (gitignored; never in tree) |
| `/workspace/uploads`, `/home/box/sand-data` `*ma_chip*` | none usable as the 7 archives |
| Docs refs only | `docs/backtest/handoff-…`, `plan-version11-…`, review F8 naming `ma_chip_edge_20240907_*` (+ cyqk80 / nobb / nocyqk variants) — **documentation, not data** |

**Not searched (blocked by B1):**

- `D:\PycharmProjects\MyQuant-backtrader\backtest_output\ma_chip_edge_*`
- `D:\exports\**`
- other 4090-local scratch / archive copies

## What did run on the box (prep only)

- Fast-forwarded `/workspace/wt-v11-impl` to `c9b4380` (`feat/version11-machip-csv`).
- Confirmed PR #152 OPEN, CI `pytest-and-gates` SUCCESS on `c9b4380`.
- No seed-30 export, no engine runs, no universe sensitivity, no pyd identity capture.

## Classification tables / sanity bounds

**Empty — not run.** Do not invent.

## Explicit non-claims

- Not claiming seed-30 parity vs Cerebro archives.
- Not claiming return acceptance / full-universe sensitivity results.
- Slice D remains **not smoke-complete** until B1+B2 cleared on 4090.
