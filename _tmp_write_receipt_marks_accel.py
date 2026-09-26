# -*- coding: utf-8 -*-
from pathlib import Path
import json
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
now = datetime.now(CST)
root = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest_output\joint-return-v1-replay-panel-phase")
dump = json.loads(Path(r"D:\PycharmProjects\MyQuant-backtrader\_tmp_marks_accel_dump.json").read_text(encoding="utf-8"))
flat = dump["flat"]
top15 = dump["top15"]
top3 = dump["top3"]
counts = dump["counts"]
cmp_ = dump["comparisons"]

# forbidden mtime check
forbidden_paths = [
    root / "out-v2-pack-spans-182" / "joint-return-control-only-50-5-narrow-clock-patch-614" / "fills.csv",
    root / "out-v2-pack-spans-182" / "joint-return-control-only-50-5-narrow-clock-patch-614" / "daily_nav.csv",
    root / "phase_timings_B_182.json",
    root / "phase_timings_B.json",
]
# also check dirs exist and weren't our write target
for p in [root / "out-v2-pack-spans-181", root / "out-v2-pack-spans-182"]:
    forbidden_paths.append(p)

lines = []
def L(s=""):
    lines.append(s)

L("# RECEIPT_REPLAY_PANEL_SPANS_MARKS_ACCEL — Knife #183 follow-up: B-only after marks universe restrict")
L()
L(f"- written_at: {now.isoformat()} (CST / Asia/Shanghai)")
L("- host: newtest_4090 (HEADLESS)")
L("- STATUS: done (BT_RESEARCH_REPLAY_PASS)")
L(f"- tip SHA: `{dump['tip']}` (detached HEAD @ github/master #183 restrict replay marks to fixed run universe; >= required `710687e`)")
L("- entry: `scripts/research/run_joint_return_replay.py`")
L("- flags: `--arm P-BASE --fill-mode all --validate-version v2 --profile-timings --profile-timings-json`")
L("- local pin: FROZEN_CONTRACT_HASH temporarily -> `c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7` for run; **restored** to stock `9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41` after (bak=`joint_return_replay.py.bak_marks_accel_pin_20260924`); **not committed**; business file clean after restore (`git checkout --` + porcelain empty)")
L(f"- wrapper wall: {dump['wall_s']} s (exit=0); profile total_seconds: {dump['a_total']}")
L()
L("## Inputs")
L()
L("| role | path |")
L("| --- | --- |")
L("| intents (Mode B cash-1e9) | `D:\\PycharmProjects\\MyQuant\\runs\\joint_return_4090_20260920_pr95\\handoff_bt_20260922\\narrow_clock_20260922\\portfolio\\joint-return-control-only-50-5-narrow-clock-patch-614-cash-1e9` |")
L("| pack (B sealed) | `D:\\PycharmProjects\\MyQuant-backtrader\\backtest_output\\joint-return-v1-dense-panel-bench\\packs\\clock-patch-614-qlib-bin-FULL-sealed\\` |")
L()
L("## Command")
L()
L("```")
L("python -u scripts/research/run_joint_return_replay.py \\")
L("  --intents <cash-1e9 intents above> \\")
L("  --bars <FULL-sealed pack above> \\")
L("  --arm P-BASE --fill-mode all --validate-version v2 \\")
L("  --profile-timings --profile-timings-json ...\\phase_timings_B_marks_accel.json \\")
L("  --out ...\\out-v2-pack-spans-marks-accel\\joint-return-control-only-50-5-narrow-clock-patch-614")
L("```")
L()
L("Interpreter: `D:\\ProgramData\\anaconda3\\envs\\vanna312\\python.exe`")
L()
L("## Outputs")
L()
L("| artifact | path |")
L("| --- | --- |")
L("| out | `...\\joint-return-v1-replay-panel-phase\\out-v2-pack-spans-marks-accel\\joint-return-control-only-50-5-narrow-clock-patch-614\\` |")
L("| phase_timings_B_marks_accel.json | `...\\joint-return-v1-replay-panel-phase\\phase_timings_B_marks_accel.json` |")
L("| RECEIPT | `...\\joint-return-v1-replay-panel-phase\\RECEIPT_REPLAY_PANEL_SPANS_MARKS_ACCEL.md` |")
L("| logs | `...\\logs\\B_marks_accel.stdout.log`, `B_marks_accel.stderr.log`, `B_marks_accel_wall.txt`, `B_marks_accel_run.ps1` |")
L()
L("Forbidden untouched (not overwritten this run): `joint-return-v1-modeb\\`, `joint-return-v1-modeb-cash-1e9\\`, knife1 `out-v1-json\\` / `out-v2-pack\\`, knife1.5 `out-v2-pack-spans-181\\`, `out-v2-pack-spans-182\\`, `phase_timings_B.json` (181), `phase_timings_B_182.json`, FULL-sealed pack.")
L()
L("## Top-level phase seconds (desc)")
L()
L("| phase | seconds |")
L("| --- | ---: |")
# top-level = no dot
tops = [(k, v) for k, v in flat.items() if "." not in k and k != "total_seconds" and not k.startswith("counts")]
tops.sort(key=lambda x: -x[1])
for k, v in tops:
    L(f"| `{k}` | {v:.6f} |")
L(f"| **total_seconds** | **{dump['a_total']:.6f}** |")
L()
L("## Nested parent.child under replay_*/write_* (top 15 by seconds desc)")
L()
L("| span | seconds |")
L("| --- | ---: |")
for k, v in top15:
    L(f"| `{k}` | {v:.6f} |")
L()
L("## Required compare: marks vs #182 baseline (tip 8cd01e7)")
L()
L("| arm | before (182) | after (marks-accel/#183) | delta (s) | delta % |")
L("| --- | ---: | ---: | ---: | ---: |")
L(f"| `replay_M-LAG_P-BASE.marks` | 135.671305 | {dump['a_marks_lag']:.6f} | {dump['d_lag']:+.6f} | {dump['pct_lag']:+.3f}% |")
L(f"| `replay_M-REF_P-BASE.marks` | 133.646755 | {dump['a_marks_ref']:.6f} | {dump['d_ref']:+.6f} | {dump['pct_ref']:+.3f}% |")
L()
L("## eligible_scan (confirm still ~11s)")
L()
L("| arm | #182 | after |")
L("| --- | ---: | ---: |")
L(f"| `replay_M-LAG_P-BASE.eligible_scan` | 11.384202 | {dump['a_elig_lag']:.6f} |")
L(f"| `replay_M-REF_P-BASE.eligible_scan` | 10.944708 | {dump['a_elig_ref']:.6f} |")
L()
L("## marks + total one-line compare")
L()
L(f"marks M-LAG 135.671305->{dump['a_marks_lag']:.6f} (d={dump['d_lag']:+.6f} / {dump['pct_lag']:+.3f}%); M-REF 133.646755->{dump['a_marks_ref']:.6f} (d={dump['d_ref']:+.6f} / {dump['pct_ref']:+.3f}%); total_seconds 789.156721->{dump['a_total']:.6f} (d={dump['a_total']-789.156721:+.6f} / wall ~790.7->{dump['wall_s']}).")
L()
L("## Top 3 child spans now")
L()
L("| rank | span | seconds |")
L("| ---: | --- | ---: |")
for i, (k, v) in enumerate(top3, 1):
    L(f"| {i} | `{k}` | {v:.6f} |")
L()
L("## counts.* (vs #182 — same)")
L()
L("| key | value |")
L("| --- | ---: |")
# order like 182 receipt
order = [
    "counts.bundle_load.intent_rows",
    "counts.bundle_load.validate_manifest.bound_intents",
    "counts.bundle_load.validate_manifest.reference_arm_days",
    "counts.replay_M-LAG_P-BASE.attempts",
    "counts.replay_M-LAG_P-BASE.fills",
    "counts.replay_M-LAG_P-BASE.orders",
    "counts.replay_M-LAG_P-BASE.timeline_points",
    "counts.replay_M-REF_P-BASE.attempts",
    "counts.replay_M-REF_P-BASE.fills",
    "counts.replay_M-REF_P-BASE.orders",
    "counts.replay_M-REF_P-BASE.timeline_points",
    "counts.validate_manifest.bound_intents",
    "counts.validate_manifest.reference_arm_days",
    "counts.validate_metadata.bar_metadata.session_minutes",
    "counts.validate_panel_load.decoded_instruments",
    "counts.validate_panel_scan.panel_cells",
]
for k in order:
    if k in counts:
        v = counts[k]
        L(f"| `{k}` | {int(v) if float(v)==int(v) else v} |")
for k in sorted(counts):
    if k not in order:
        v = counts[k]
        L(f"| `{k}` | {int(v) if float(v)==int(v) else v} |")
L()
L("Counts match #182 exactly (1891 intents/orders; LAG fills 63527 / attempts 70531; REF fills 376 / attempts 1881; panel_cells 35957682; decoded_instruments 614).")
L()
L("## Optional coarse identity vs #182 out")
L()
fills = cmp_["fills.csv"]
nav = cmp_["daily_nav.csv"]
L(f"- `fills.csv`: **byte-identical** vs `out-v2-pack-spans-182` (size={fills['size_new']}; sha256=`{fills['sha_new']}`)")
L(f"- `daily_nav.csv`: **byte-identical** vs `out-v2-pack-spans-182` (size={nav['size_new']}; sha256=`{nav['sha_new']}`)")
L(f"- paths new: `{fills['new_path']}` / `{nav['new_path']}`")
L(f"- paths 182: `{fills['old_path']}` / `{nav['old_path']}`")
L()
L("## Next cut (one sentence)")
L()
L("Marks dropped only ~0.7% (~1.0s LAG / ~0.9s REF) vs #182 while eligible_scan stayed ~11s and fills/nav stayed byte-identical — next cut should target the still-dominant `marks`+`lifecycle` pair (now ~134s / ~117s LAG) or `attempts` (~96s LAG), not further marks-universe filtering.")
L()

receipt = root / "RECEIPT_REPLAY_PANEL_SPANS_MARKS_ACCEL.md"
# write UTF-8 clean, LF only — pathlib write_text
text = "\n".join(lines) + "\n"
# guard against \r eating replay_
assert "\r" not in text
receipt.write_text(text, encoding="utf-8", newline="\n")
print("RECEIPT written:", receipt)
print("RECEIPT bytes:", receipt.stat().st_size)
# verify no CR
raw = receipt.read_bytes()
print("contains_CR:", b"\r" in raw)
print("contains_replay_marks:", b"replay_M-LAG_P-BASE.marks" in raw)

# forbidden untouched: compare 182 fills mtime vs our new out (should be different trees)
import os
p182_fills = root / "out-v2-pack-spans-182" / "joint-return-control-only-50-5-narrow-clock-patch-614" / "fills.csv"
p182_timings = root / "phase_timings_B_182.json"
p_new_timings = root / "phase_timings_B_marks_accel.json"
print("182 fills mtime:", datetime.fromtimestamp(p182_fills.stat().st_mtime, CST).isoformat())
print("182 timings mtime:", datetime.fromtimestamp(p182_timings.stat().st_mtime, CST).isoformat())
print("new timings mtime:", datetime.fromtimestamp(p_new_timings.stat().st_mtime, CST).isoformat())
print("phase_timings_B.json exists:", (root / "phase_timings_B.json").exists())
if (root / "phase_timings_B.json").exists():
    print("phase_timings_B.json mtime:", datetime.fromtimestamp((root / "phase_timings_B.json").stat().st_mtime, CST).isoformat())
