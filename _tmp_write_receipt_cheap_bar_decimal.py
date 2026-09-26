from pathlib import Path
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
now = datetime.now(CST)
receipt_path = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest_output\joint-return-v1-replay-panel-phase\RECEIPT_REPLAY_PANEL_SPANS_CHEAP_BAR_DECIMAL.md")

# deltas vs #184
lag184, ref184 = 95.448377, 88.850439
lag, ref = 79.306526, 73.288
d_lag, d_ref = lag - lag184, ref - ref184
pct_lag = 100.0 * d_lag / lag184
pct_ref = 100.0 * d_ref / ref184
tot184, tot = 685.293996, 631.665881
d_tot = tot - tot184
wall184, wall = 686.914, 633.354

# cumulative vs #183 marks-accel
lag183, ref183 = 134.669213, 132.756900

md = f"""# RECEIPT_REPLAY_PANEL_SPANS_CHEAP_BAR_DECIMAL — post-merge #185 B-only cheap-bar_decimal rebench

- written_at: {now.isoformat(timespec='seconds')} (CST / Asia/Shanghai)
- host: newtest_4090 (HEADLESS)
- STATUS: PASS (BT_RESEARCH_REPLAY_PASS)
- tip SHA: `4e8fddb32ea607b565d661790391529f24003728` (detached HEAD @ github/master #185 cheapen trusted panel Decimal reads; starts with required `4e8fddb`)
- entry: `scripts/research/run_joint_return_replay.py`
- flags: `--arm P-BASE --fill-mode all --validate-version v2 --profile-timings --profile-timings-json`
- local pin: FROZEN_CONTRACT_HASH temporarily -> `c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7` for run; **restored** to stock `9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41` after (bak=`joint_return_replay.py.bak_cheap_bar_decimal_pin_20260924`); **not committed**; business file clean after restore (`git checkout --` + porcelain empty on business)
- wrapper wall: {wall:.3f} s (exit=0); profile total_seconds: {tot}
- out leaf (MQ run_id): `.../out-v2-pack-spans-cheap-bar-decimal/joint-return-control-only-50-5-narrow-clock-patch-614` (same pattern as #184 live-universe)

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
  --profile-timings --profile-timings-json ...\\phase_timings_B_cheap_bar_decimal.json \\
  --out ...\\out-v2-pack-spans-cheap-bar-decimal\\joint-return-control-only-50-5-narrow-clock-patch-614
```

Interpreter: `D:\\ProgramData\\anaconda3\\envs\\vanna312\\python.exe` (same as #184)

## Outputs

| artifact | path |
| --- | --- |
| out | `...\\joint-return-v1-replay-panel-phase\\out-v2-pack-spans-cheap-bar-decimal\\joint-return-control-only-50-5-narrow-clock-patch-614\\` |
| phase_timings_B_cheap_bar_decimal.json | `...\\joint-return-v1-replay-panel-phase\\phase_timings_B_cheap_bar_decimal.json` |
| RECEIPT | `...\\joint-return-v1-replay-panel-phase\\RECEIPT_REPLAY_PANEL_SPANS_CHEAP_BAR_DECIMAL.md` |
| logs | `...\\logs\\B_cheap_bar_decimal.stdout.log`, `B_cheap_bar_decimal.stderr.log`, `B_cheap_bar_decimal_wall.txt`, `B_cheap_bar_decimal_run.ps1` |

Forbidden untouched (mtimes unchanged vs pre-run snapshot): `out-v2-pack-spans-181`, `out-v2-pack-spans-182`, `out-v2-pack-spans-marks-accel`, `out-v2-pack-spans-710687e-cprofile` / marks-hotspot outs, `out-v2-pack-spans-live-universe`, modeb/cash-1e9/FULL timing pack (`out-v2-pack`), their phase_timings JSON (`phase_timings_B.json`, `phase_timings_B_182.json`, `phase_timings_B_marks_accel.json`, `phase_timings_B_710687e_cprofile.json`, `phase_timings_B_live_universe.json`).

## Top-level phase seconds (desc)

| phase | seconds |
| --- | ---: |
| `replay_M-LAG_P-BASE` | 306.486060 |
| `replay_M-REF_P-BASE` | 234.750777 |
| `write_artifacts` | 30.988420 |
| `plain_output` | 27.378919 |
| `bundle_load` | 20.053323 |
| `validate_manifest` | 4.259047 |
| `validate_seal` | 3.053620 |
| `validate_panel_load` | 3.029406 |
| `validate_panel_scan` | 0.591644 |
| `validate_metadata` | 0.057891 |
| `summary_M-LAG_P-BASE` | 0.023811 |
| `validate_reference_marks` | 0.015125 |
| `summary_M-REF_P-BASE` | 0.007680 |
| `bars_read` | 0.000293 |
| **total_seconds** | **{tot}** |

## Nested parent.child under replay_*/write_* (top 15 by seconds desc)

| span | seconds |
| --- | ---: |
| `replay_M-LAG_P-BASE.lifecycle` | 118.125110 |
| `replay_M-REF_P-BASE.lifecycle` | 116.582888 |
| `replay_M-LAG_P-BASE.attempts` | 81.565264 |
| `replay_M-LAG_P-BASE.marks` | 79.306526 |
| `replay_M-REF_P-BASE.marks` | 73.288000 |
| `replay_M-REF_P-BASE.attempts` | 32.603696 |
| `write_artifacts.serialize_tables` | 20.388690 |
| `replay_M-LAG_P-BASE.daily_mark` | 15.059848 |
| `replay_M-LAG_P-BASE.eligible_scan` | 11.527367 |
| `replay_M-REF_P-BASE.eligible_scan` | 11.223485 |
| `write_artifacts.summary_hashes` | 9.907692 |
| `write_artifacts.write_files` | 0.692010 |
| `replay_M-REF_P-BASE.daily_mark` | 0.289287 |
| `replay_M-LAG_P-BASE.init_orders` | 0.114522 |
| `replay_M-REF_P-BASE.timeline_build` | 0.114280 |

Also: `replay_M-LAG_P-BASE.snapshot_orders`=0.017179; `replay_M-REF_P-BASE.snapshot_orders`=0.010814.

## Primary compare: marks vs #184 live-universe (tip 0df7697)

| arm | before (#184 live-universe) | after (#185 cheap-bar_decimal) | delta (s) | delta % |
| --- | ---: | ---: | ---: | ---: |
| `replay_M-LAG_P-BASE.marks` | 95.448377 | 79.306526 | {d_lag:.6f} | {pct_lag:.3f}% |
| `replay_M-REF_P-BASE.marks` | 88.850439 | 73.288000 | {d_ref:.6f} | {pct_ref:.3f}% |

## Optional cumulative note vs #183 marks-accel (134.67 / 132.76) — label as cumulative, not primary

| arm | #183 marks-accel | #184 live-universe | #185 cheap-bar_decimal |
| --- | ---: | ---: | ---: |
| `replay_M-LAG_P-BASE.marks` | 134.669213 | 95.448377 | 79.306526 |
| `replay_M-REF_P-BASE.marks` | 132.756900 | 88.850439 | 73.288000 |

Cumulative M-LAG 134.669213→79.306526 (d={79.306526-134.669213:.6f} / {(100.0*(79.306526-134.669213)/134.669213):.3f}%); M-REF 132.756900→73.288000 (d={73.288-132.756900:.6f} / {(100.0*(73.288-132.756900)/132.756900):.3f}%).

## eligible_scan (confirm still ~11s class / #182 gain retained)

| arm | #184 live-universe | after (#185) |
| --- | ---: | ---: |
| `replay_M-LAG_P-BASE.eligible_scan` | 11.333379 | 11.527367 |
| `replay_M-REF_P-BASE.eligible_scan` | 10.989928 | 11.223485 |

## marks + total one-line compare (primary = vs #184)

marks M-LAG 95.448377→79.306526 (d={d_lag:.6f} / {pct_lag:.3f}%); M-REF 88.850439→73.288000 (d={d_ref:.6f} / {pct_ref:.3f}%); total_seconds {tot184}→{tot} (d={d_tot:.6f} / wall ~{wall184}→{wall:.3f}). Material marks improvement both modes (~1.20× faster on marks e2e). **Local 1.565× per-cell microbench is NOT an e2e promise** — observed e2e marks speedup ≈95.448/79.307≈1.204× (LAG) and ≈88.850/73.288≈1.212× (REF).

## Top 3 child spans now

| rank | span | seconds |
| ---: | --- | ---: |
| 1 | `replay_M-LAG_P-BASE.lifecycle` | 118.125110 |
| 2 | `replay_M-REF_P-BASE.lifecycle` | 116.582888 |
| 3 | `replay_M-LAG_P-BASE.attempts` | 81.565264 |

(Marks no longer occupy top-3; LAG marks is rank 4 at 79.307s.)

## Remaining hotspots (after #185)

- lifecycle both arms ~116–118s (largest)
- attempts M-LAG ~81.6s (now #3)
- marks still ~73–79s (improved but material)
- eligible_scan still ~11s class
- daily_mark M-LAG ~15.1s
- write_artifacts.serialize_tables ~20.4s + summary_hashes ~9.9s

## counts.* (vs #184; shared counts match; mark-universe counters unchanged)

| key | value |
| --- | ---: |
| `counts.bundle_load.intent_rows` | 1891 |
| `counts.bundle_load.validate_manifest.bound_intents` | 1891 |
| `counts.bundle_load.validate_manifest.reference_arm_days` | 243 |
| `counts.replay_M-LAG_P-BASE.attempts` | 70531 |
| `counts.replay_M-LAG_P-BASE.fills` | 63527 |
| `counts.replay_M-LAG_P-BASE.orders` | 1891 |
| `counts.replay_M-LAG_P-BASE.timeline_points` | 59049 |
| `counts.replay_M-LAG_P-BASE.mark_universe_max` | 614 |
| `counts.replay_M-LAG_P-BASE.marks.mark_sites` | 117612 |
| `counts.replay_M-LAG_P-BASE.marks.mark_universe_samples` | 50306219 |
| `counts.replay_M-LAG_P-BASE.marks.mark_updates` | 50097908 |
| `counts.replay_M-REF_P-BASE.attempts` | 1881 |
| `counts.replay_M-REF_P-BASE.fills` | 376 |
| `counts.replay_M-REF_P-BASE.orders` | 1891 |
| `counts.replay_M-REF_P-BASE.timeline_points` | 59049 |
| `counts.replay_M-REF_P-BASE.mark_universe_max` | 614 |
| `counts.replay_M-REF_P-BASE.marks.mark_sites` | 117612 |
| `counts.replay_M-REF_P-BASE.marks.mark_universe_samples` | 47078816 |
| `counts.replay_M-REF_P-BASE.marks.mark_updates` | 46883728 |
| `counts.validate_manifest.bound_intents` | 1891 |
| `counts.validate_manifest.reference_arm_days` | 243 |
| `counts.validate_metadata.bar_metadata.session_minutes` | 58563 |
| `counts.validate_panel_load.decoded_instruments` | 614 |
| `counts.validate_panel_scan.panel_cells` | 35957682 |

Mean live size = `mark_universe_samples / mark_sites`:
- M-LAG mean = 50306219 / 117612 = **427.730** (max still 614; mark_updates=50097908)
- M-REF mean = 47078816 / 117612 = **400.289** (max still 614; mark_updates=46883728)

Shared identity counts match #184 live-universe exactly (1891 intents/orders; LAG fills 63527 / attempts 70531; REF fills 376 / attempts 1881; panel_cells 35957682; decoded_instruments 614; mark_universe max/mean identical).

## fills / daily_nav identity

- `fills.csv`: sha256=`d6d40bc4979d462582a8c53c34591cdcca6fafd123857da9d7053aa598fe3376` (**matches required**); **byte-identical** vs #184 live-universe (size=1213834431)
- `daily_nav.csv`: sha256=`2cf88d08b7f50c6c54cdcb8ba64a4fb96024262f988c18d8b025259d1c572685` (**matches required**); **byte-identical** vs #184 live-universe (size=144653728)
- CLI / summary `replay_source_sha256` this run=`80b4600fab579ef11ef26e28213ed1499f064fcb933862fbd30ed7d322596838` (same value as #184 live-universe; may change with tip — here unchanged)
- peak memory: **not available** in phase_timings JSON / summary top-level

## Success checklist

- [x] tip `4e8fddb32ea607b565d661790391529f24003728` (#185)
- [x] B-only completed BT_RESEARCH_REPLAY_PASS
- [x] `--validate-version v2` explicit; seal stays qlib_bin FULL pack
- [x] phase_timings_B_cheap_bar_decimal.json written (sibling outside --out)
- [x] RECEIPT written
- [x] forbidden outs / phase JSONs untouched
- [x] FROZEN_CONTRACT_HASH pin restored; business porcelain clean
- [x] marks improved materially both modes vs #184; fills/nav byte-identical to required digests
- [x] no new knives / Option A implementation this run (rebench only)
"""
receipt_path.write_text(md, encoding="utf-8", newline="\n")
print("wrote", receipt_path)
print("bytes", receipt_path.stat().st_size)