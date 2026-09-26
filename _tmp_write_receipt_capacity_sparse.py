from pathlib import Path
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
now = datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S%z")
# format +08:00
now = datetime.now(CST).isoformat(timespec="seconds")

phase = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest_output\joint-return-v1-replay-panel-phase")
receipt = phase / "RECEIPT_REPLAY_CAPACITY_SPARSE.md"

# metrics
wall = 384.5407071
total = 382.806535
b_wall = 448.570609
b_total = 446.792279
att_lag = 49.174504
att_ref = 0.072774
b_att_lag = 81.804854
b_att_ref = 33.078746
marks_lag, marks_ref = 80.637692, 73.08924
b_marks_lag, b_marks_ref = 80.300479, 74.356544
life_lag, life_ref = 26.051706, 24.442456
b_life_lag, b_life_ref = 25.549136, 24.646879
elig_lag, elig_ref = 11.408306, 11.043347
b_elig_lag, b_elig_ref = 11.240214, 10.934369

def dlt(a, b):
    ds = a - b
    pct = (ds / b * 100.0) if b else float("nan")
    return ds, pct

dw, dwp = dlt(wall, b_wall)
dt, dtp = dlt(total, b_total)
dal, dalp = dlt(att_lag, b_att_lag)
dar, darp = dlt(att_ref, b_att_ref)

text = f"""# RECEIPT_REPLAY_CAPACITY_SPARSE — post-merge #187 B-only capacity sparse rebench

- written_at: {now} (CST / Asia/Shanghai)
- host: newtest_4090 (HEADLESS)
- STATUS: **PASS** (BT_RESEARCH_REPLAY_PASS)
- tip SHA: `e827529966ed4f465322524503e79ef828f9b6dd` (detached HEAD @ github/master #187 perf(research): read capacity only for eligible instruments)
- entry: `scripts/research/run_joint_return_replay.py`
- flags: `--arm P-BASE --fill-mode all --validate-version v2 --profile-timings --profile-timings-json`
- local pin: FROZEN_CONTRACT_HASH temporarily -> `c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7` for run; **restored** to stock `9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41` after (bak=`joint_return_replay.py.bak_capacity_sparse_pin_20260924`); **not committed**; business file clean after restore (`git checkout --` + porcelain empty on business)
- wrapper wall: {wall:.6f} s (exit=0 via BT_RESEARCH_REPLAY_PASS; Start-Process ExitCode field was null quirk — stdout status authoritative); profile total_seconds: {total:.6f}
- out leaf (MQ run_id): `.../out-v2-pack-spans-capacity-sparse/joint-return-control-only-50-5-narrow-clock-patch-614`

## Inputs

| role | path |
| --- | --- |
| intents (Mode B cash-1e9) | `D:\\PycharmProjects\\MyQuant\\runs\\joint_return_4090_20260920_pr95\\handoff_bt_20260922\\narrow_clock_20260922\\portfolio\\joint-return-control-only-50-5-narrow-clock-patch-614-cash-1e9` |
| pack (B sealed) | `D:\\PycharmProjects\\MyQuant-backtrader\\backtest_output\\joint-return-v1-dense-panel-bench\\packs\\clock-patch-614-qlib-bin-FULL-sealed\\` |

## Command

```
D:\\ProgramData\\anaconda3\\envs\\vanna312\\python.exe -u scripts/research/run_joint_return_replay.py \\
  --intents <cash-1e9 intents above> \\
  --bars <FULL-sealed pack above> \\
  --validate-version v2 --arm P-BASE --fill-mode all \\
  --profile-timings --profile-timings-json ...\\phase_timings_B_capacity_sparse.json \\
  --out ...\\out-v2-pack-spans-capacity-sparse\\joint-return-control-only-50-5-narrow-clock-patch-614
```

Exact run.ps1: `...\\logs\\B_capacity_sparse_run.ps1`

## Env / identity

| item | value |
| --- | --- |
| interpreter | `D:\\ProgramData\\anaconda3\\envs\\vanna312\\python.exe` |
| repo | `D:\\PycharmProjects\\MyQuant-backtrader` |
| HEAD | `e827529966ed4f465322524503e79ef828f9b6dd` |
| validate-version | v2 (explicit; default stays v1) |
| seal | qlib_bin FULL sealed pack (CLOCK_PATCH-614) |
| profile mode | plain `--profile-timings` only (NO cProfile) |
| out | `...\\joint-return-v1-replay-panel-phase\\out-v2-pack-spans-capacity-sparse\\joint-return-control-only-50-5-narrow-clock-patch-614\\` |
| phase JSON | `...\\phase_timings_B_capacity_sparse.json` |
| logs | `...\\logs\\B_capacity_sparse.stdout.log`, `B_capacity_sparse.stderr.log`, `B_capacity_sparse_wall.txt`, `B_capacity_sparse_run.ps1` |

## Pin restore proof

- Before run: stock `9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41` -> pin `c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7` via Python UTF-8 (NOT PowerShell Set-Content); bak written (`bak_capacity_sparse_pin_20260924`).
- After run (finally trap on success): restored to stock `9ee8cc3c...` via Python UTF-8 from bak + `git checkout -- backtest/research/joint_return_replay.py`.
- `git status --porcelain -- backtest/research/joint_return_replay.py` empty; FROZEN line matches tip stock; **not committed**.

## Forbidden outs untouched (mtime proof)

Pre-run snapshot: `_tmp_forbidden_mtime_snapshot_capacity_sparse.json` (92 present paths).
Post-run compare: **forbidden_ok_count=92 changed_count=0 missing_now=0**.
Untouched include: `out-v2-pack-spans-181`, `out-v2-pack-spans-182`, `out-v2-pack-spans-marks-accel`, `out-v2-pack-spans-710687e-cprofile`, `out-v2-pack-spans-live-universe`, `out-v2-pack-spans-cheap-bar-decimal`, `out-v2-pack-spans-4e8fddb-cprofile`, `out-v2-pack-spans-lifecycle-clock-cache`, their phase_timings JSON / RECEIPTs / pstats, plus sealed FULL pack and related outs. Fresh artifacts only under capacity-sparse leaf + phase JSON + this RECEIPT + logs.

## Primary compare vs #186 plain (AUTHORITATIVE)

| metric | #186 lifecycle-clock-cache | #187 capacity-sparse | Δ s | Δ % |
| --- | ---: | ---: | ---: | ---: |
| wrapper wall | {b_wall:.6f} | {wall:.6f} | {dw:.6f} | {dwp:.3f}% |
| total_seconds | {b_total:.6f} | {total:.6f} | {dt:.6f} | {dtp:.3f}% |
| `replay_M-LAG_P-BASE.attempts` | {b_att_lag:.6f} | {att_lag:.6f} | {dal:.6f} | {dalp:.3f}% |
| `replay_M-REF_P-BASE.attempts` | {b_att_ref:.6f} | {att_ref:.6f} | {dar:.6f} | {darp:.3f}% |
| `replay_M-LAG_P-BASE.lifecycle` | {b_life_lag:.6f} | {life_lag:.6f} | {life_lag-b_life_lag:.6f} | {(life_lag-b_life_lag)/b_life_lag*100:.3f}% |
| `replay_M-REF_P-BASE.lifecycle` | {b_life_ref:.6f} | {life_ref:.6f} | {life_ref-b_life_ref:.6f} | {(life_ref-b_life_ref)/b_life_ref*100:.3f}% |
| `replay_M-LAG_P-BASE.marks` | {b_marks_lag:.6f} | {marks_lag:.6f} | {marks_lag-b_marks_lag:.6f} | {(marks_lag-b_marks_lag)/b_marks_lag*100:.3f}% |
| `replay_M-REF_P-BASE.marks` | {b_marks_ref:.6f} | {marks_ref:.6f} | {marks_ref-b_marks_ref:.6f} | {(marks_ref-b_marks_ref)/b_marks_ref*100:.3f}% |
| `replay_M-LAG_P-BASE.eligible_scan` | {b_elig_lag:.6f} | {elig_lag:.6f} | {elig_lag-b_elig_lag:.6f} | {(elig_lag-b_elig_lag)/b_elig_lag*100:.3f}% |
| `replay_M-REF_P-BASE.eligible_scan` | {b_elig_ref:.6f} | {elig_ref:.6f} | {elig_ref-b_elig_ref:.6f} | {(elig_ref-b_elig_ref)/b_elig_ref*100:.3f}% |

**Noise judgment:** Not near measurement noise. Wall −64.0 s (−14.3%) and attempts LAG −32.6 s (−39.9%) / REF −33.0 s (−99.8%) are a **real win**. H-cap evidence was PARTIAL — do **not** claim the entire ~81.8 s LAG attempts span is gone; ~49.2 s LAG attempts remain. REF attempts essentially collapsed (~33.1 → ~0.07 s).

## Top-level phase seconds (desc)

| span | seconds |
| --- | ---: |
| `replay_M-LAG_P-BASE` | 182.800760 |
| `replay_M-REF_P-BASE` | 109.570486 |
| `write_artifacts` | 31.242116 |
| `plain_output` | 26.974660 |
| `bundle_load` | 19.991390 |
| `validate_manifest` | 4.225671 |
| `validate_panel_load` | 3.247851 |
| `validate_seal` | 3.107980 |
| `validate_panel_scan` | 0.551054 |
| `validate_metadata` | 0.057377 |
| `summary_M-LAG_P-BASE` | 0.026146 |
| `validate_reference_marks` | 0.015451 |
| `summary_M-REF_P-BASE` | 0.007477 |
| `bars_read` | 0.000330 |
| **total_seconds** | **{total:.6f}** |

## Nested parent.child under replay_*/write_* (by seconds desc)

| span | seconds |
| --- | ---: |
| `replay_M-LAG_P-BASE.marks` | 80.637692 |
| `replay_M-REF_P-BASE.marks` | 73.089240 |
| `replay_M-LAG_P-BASE.attempts` | 49.174504 |
| `replay_M-LAG_P-BASE.lifecycle` | 26.051706 |
| `replay_M-REF_P-BASE.lifecycle` | 24.442456 |
| `write_artifacts.serialize_tables` | 20.475994 |
| `replay_M-LAG_P-BASE.daily_mark` | 14.721581 |
| `replay_M-LAG_P-BASE.eligible_scan` | 11.408306 |
| `replay_M-REF_P-BASE.eligible_scan` | 11.043347 |
| `write_artifacts.summary_hashes` | 10.044860 |
| `write_artifacts.write_files` | 0.721227 |
| `replay_M-REF_P-BASE.daily_mark` | 0.284011 |
| `replay_M-LAG_P-BASE.init_orders` | 0.108894 |
| `replay_M-LAG_P-BASE.timeline_build` | 0.103383 |
| `replay_M-REF_P-BASE.timeline_build` | 0.102529 |
| `replay_M-REF_P-BASE.attempts` | 0.072774 |
| `replay_M-REF_P-BASE.init_orders` | 0.050465 |
| `replay_M-LAG_P-BASE.snapshot_orders` | 0.016337 |
| `replay_M-REF_P-BASE.snapshot_orders` | 0.010471 |

## Top 3 child spans now

| rank | span | seconds |
| --- | --- | ---: |
| 1 | `replay_M-LAG_P-BASE.marks` | 80.637692 |
| 2 | `replay_M-REF_P-BASE.marks` | 73.089240 |
| 3 | `replay_M-LAG_P-BASE.attempts` | 49.174504 |

(Attempts LAG no longer #1; marks both arms dominate. REF attempts dropped off the top list.)

## Counts / live-universe (both arms)

| count key | value |
| --- | ---: |
| `counts.replay_M-LAG_P-BASE.attempts` | 70531 |
| `counts.replay_M-REF_P-BASE.attempts` | 1881 |
| `counts.replay_M-LAG_P-BASE.fills` | 63527 |
| `counts.replay_M-REF_P-BASE.fills` | 376 |
| `counts.replay_M-LAG_P-BASE.mark_universe_max` | 614 |
| `counts.replay_M-REF_P-BASE.mark_universe_max` | 614 |
| `counts.replay_M-LAG_P-BASE.marks.mark_universe_samples` | 50306219 |
| `counts.replay_M-REF_P-BASE.marks.mark_universe_samples` | 47078816 |
| `counts.validate_panel_load.decoded_instruments` | 614 |

No separate live-universe span beyond mark_universe_* counts (same as #186 schema).

## Parity vs #186 targets (byte / SHA-256)

| artifact | sha256 | vs target | vs #186 out file |
| --- | --- | --- | --- |
| fills.csv | `d6d40bc4979d462582a8c53c34591cdcca6fafd123857da9d7053aa598fe3376` | **identical** | **identical** (direct hash equality) |
| daily_nav.csv | `2cf88d08b7f50c6c54cdcb8ba64a4fb96024262f988c18d8b025259d1c572685` | **identical** | **identical** |
| orders.csv | `aad1596b2389c20775d584525f53223aca3419c09e2b4f46ba52670118185c6d` | (no target SHA) | **identical** to #186 |
| summary.json | `923760d87f5d9fee10a1b14ca385b09b2103e50b81317d37734b4952a2f1e487` | (no target SHA) | **differs** from #186 (`2b792a7194d7967f93152d554de6b4381e7ee3737e5442e78f2f120c7d8755e9`) — expected run metadata / timing fields; fills+nav authority for PASS |

Evidence: hash equality against preserved #186 out leaf files (not hash-only).

## PASS/FAIL + remaining hotspots

- **STATUS: PASS** — tip correct (`e827529` #187), exit 0 / BT_RESEARCH_REPLAY_PASS, fills+daily_nav byte-identical to #186 SHAs, pin restored, forbidden untouched (0 changed), RECEIPT written, business porcelain clean, never committed.
- Remaining hotspots (post-#187): **marks** LAG/REF ≈80.6/73.1 s (now top-1/2), **attempts LAG** still ≈49.2 s (partial H-cap — not fully removed), lifecycle ≈26.1/24.4 s, write_artifacts/plain_output/eligible_scan/daily_mark LAG.
- Speedup vs #186 is a **real win** (wall −14.3%, attempts LAG −39.9%, REF attempts ≈−99.8%), **not** near measurement noise. Do not promise the entire prior ~81.8 s attempts LAG span is removable; ~49 s remains.

## Business clean

- `backtest/research/joint_return_replay.py` porcelain empty after restore.
- Temporary pin **not** committed.
- Tip remains detached at `e827529966ed4f465322524503e79ef828f9b6dd`.
"""

receipt.write_text(text, encoding="utf-8", newline="\n")
print("wrote", receipt, "bytes", receipt.stat().st_size)
