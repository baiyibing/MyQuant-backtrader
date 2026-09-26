import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

base = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest_output\joint-return-v1-replay-panel-phase")
timings = json.loads((base / "phase_timings_B.json").read_text(encoding="utf-8"))

# top-level seconds (no dots, not counts.*, not total_seconds)
top = {k:v for k,v in timings.items() if isinstance(v,(int,float)) and "." not in k and not k.startswith("counts.") and k != "total_seconds"}
# parent.child under replay_*/write_artifacts (exactly one dot? or nested with dots - brief says parent.child keys)
# "ALL parent.child keys under replay_*/write_artifacts sorted by seconds desc top 15"
child = []
for k,v in timings.items():
    if not isinstance(v,(int,float)):
        continue
    if k.startswith("counts.") or k == "total_seconds":
        continue
    if k.startswith("replay_") or k.startswith("write_artifacts"):
        if "." in k:
            child.append((k,v))
child.sort(key=lambda x: -x[1])
top15 = child[:15]

counts = {k:v for k,v in timings.items() if k.startswith("counts.")}

# top-level sorted
top_sorted = sorted(top.items(), key=lambda x: -x[1])

print("TOTAL", timings.get("total_seconds"))
print("===TOP_LEVEL===")
for k,v in top_sorted:
    print(f"{k}\t{v}")
print("===TOP15_CHILD===")
for k,v in top15:
    print(f"{k}\t{v}")
print("===COUNTS===")
for k,v in sorted(counts.items()):
    print(f"{k}\t{v}")

# recommendation: biggest child under replay
print("===NEXT===")
print(top15[0][0], top15[0][1])

# write receipt
sha = "9b35d2318e528c875fdef36ba978250373d5a9f8"
cst = timezone(timedelta(hours=8))
now = datetime.now(cst).strftime("%Y-%m-%dT%H:%M:%S%z")
# prettier offset
now = datetime.now(cst).isoformat(timespec="seconds")

cmd = (
    "python -u scripts/research/run_joint_return_replay.py "
    "--intents D:\\PycharmProjects\\MyQuant\\runs\\joint_return_4090_20260920_pr95\\handoff_bt_20260922\\narrow_clock_20260922\\portfolio\\joint-return-control-only-50-5-narrow-clock-patch-614-cash-1e9 "
    "--bars D:\\PycharmProjects\\MyQuant-backtrader\\backtest_output\\joint-return-v1-dense-panel-bench\\packs\\clock-patch-614-qlib-bin-FULL-sealed "
    "--arm P-BASE --fill-mode all --validate-version v2 --profile-timings "
    "--profile-timings-json ...\\joint-return-v1-replay-panel-phase\\phase_timings_B.json "
    "--out ...\\joint-return-v1-replay-panel-phase\\out-v2-pack-spans-181\\joint-return-control-only-50-5-narrow-clock-patch-614"
)

lines = []
lines.append("# RECEIPT_REPLAY_PANEL_SPANS_181 — Knife 1.5: B-only fine-grained nested spans (#181)")
lines.append("")
lines.append(f"- written_at: {now} (CST / Asia/Shanghai)")
lines.append("- host: newtest_4090 (HEADLESS)")
lines.append("- STATUS: done (BT_RESEARCH_REPLAY_PASS)")
lines.append(f"- tip SHA: `{sha}` (detached HEAD @ github/master #181 finer phase/spans; ≥ required `9b35d23`)")
lines.append("- entry: `scripts/research/run_joint_return_replay.py`")
lines.append("- flags: `--arm P-BASE --fill-mode all --validate-version v2 --profile-timings --profile-timings-json`")
lines.append("- local pin: FROZEN_CONTRACT_HASH temporarily → `c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7` for run; **restored** to stock `9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41` after (bak=`joint_return_replay.py.bak_spans181_pin_20260924`); **not committed**; `git diff` empty on business file after restore")
lines.append("- note: first attempt used `--out ...\\out-v2-pack-spans-181` and failed post-replay with INPUT_BLOCKED (run_id dirname required); r2 used run_id leaf and PASS. Wrapper wall r2: 1327.6 s")
lines.append("")
lines.append("## Inputs")
lines.append("")
lines.append("| role | path |")
lines.append("| --- | --- |")
lines.append("| intents (Mode B cash-1e9) | `D:\\PycharmProjects\\MyQuant\\runs\\joint_return_4090_20260920_pr95\\handoff_bt_20260922\\narrow_clock_20260922\\portfolio\\joint-return-control-only-50-5-narrow-clock-patch-614-cash-1e9` |")
lines.append("| pack (B sealed) | `D:\\PycharmProjects\\MyQuant-backtrader\\backtest_output\\joint-return-v1-dense-panel-bench\\packs\\clock-patch-614-qlib-bin-FULL-sealed\\` |")
lines.append("")
lines.append("## Command")
lines.append("")
lines.append("```")
lines.append(cmd)
lines.append("```")
lines.append("")
lines.append("## Outputs")
lines.append("")
lines.append("| artifact | path |")
lines.append("| --- | --- |")
lines.append("| out | `...\\joint-return-v1-replay-panel-phase\\out-v2-pack-spans-181\\joint-return-control-only-50-5-narrow-clock-patch-614\\` |")
lines.append("| phase_timings_B.json | `...\\joint-return-v1-replay-panel-phase\\phase_timings_B.json` |")
lines.append("| logs | `...\\logs\\B_spans181.stderr.log`, `B_spans181.stdout.log`, `B_spans181_wall.txt` |")
lines.append("")
lines.append("Forbidden untouched (mtimes unchanged vs pre-run): `joint-return-v1-modeb\\`, `joint-return-v1-modeb-cash-1e9\\`, `packs\\clock-patch-614-qlib-bin-FULL\\`, knife1 `out-v1-json\\` / `out-v2-pack\\`.")
lines.append("")
lines.append("## Top-level phase seconds (desc)")
lines.append("")
lines.append("| phase | seconds |")
lines.append("| --- | ---: |")
for k,v in top_sorted:
    lines.append(f"| `{k}` | {v} |")
lines.append(f"| **total_seconds** | **{timings['total_seconds']}** |")
lines.append("")
lines.append("## Nested parent.child under replay_*/write_artifacts (top 15 by seconds desc)")
lines.append("")
lines.append("| span | seconds |")
lines.append("| --- | ---: |")
for k,v in top15:
    lines.append(f"| `{k}` | {v} |")
lines.append("")
lines.append("## counts.*")
lines.append("")
lines.append("| key | value |")
lines.append("| --- | ---: |")
for k,v in sorted(counts.items()):
    lines.append(f"| `{k}` | {v} |")
lines.append("")
lines.append("## Next cut (one sentence)")
lines.append("")
nxt_k, nxt_v = top15[0]
# also mention top3 for parent report
top3 = top15[:3]
lines.append(
    f"**Cut next: `{nxt_k}` ({nxt_v:.1f}s)** — largest child under B replay (~{nxt_v/timings['total_seconds']*100:.0f}% of total / ~{nxt_v/timings['replay_M-LAG_P-BASE']*100:.0f}% of M-LAG replay); same family dominates M-REF (`replay_M-REF_P-BASE.eligible_scan`={timings['replay_M-REF_P-BASE.eligible_scan']:.1f}s)."
)
lines.append("")
lines.append("### Top 3 child spans")
for k,v in top3:
    lines.append(f"- `{k}` = **{v:.6f} s**")
lines.append("")
lines.append("## Success checklist")
lines.append("- [x] tip ≥ 9b35d23 (#181)")
lines.append("- [x] B-only completed BT_RESEARCH_REPLAY_PASS")
lines.append("- [x] phase_timings_B.json written (sibling outside --out)")
lines.append("- [x] RECEIPT written")
lines.append("- [x] modeb / cash-1e9 / FULL timing pack / knife1 A/B outs untouched")
lines.append("- [x] FROZEN_CONTRACT_HASH pin restored; business code not otherwise modified")

receipt = base / "RECEIPT_REPLAY_PANEL_SPANS_181.md"
receipt.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("WROTE", receipt)
print("bytes", receipt.stat().st_size)
