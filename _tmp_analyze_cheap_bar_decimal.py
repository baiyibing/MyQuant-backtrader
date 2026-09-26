from pathlib import Path
import json
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
base = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest_output\joint-return-v1-replay-panel-phase")
logs = base / "logs"
phase = json.loads((base / "phase_timings_B_cheap_bar_decimal.json").read_text(encoding="utf-8"))
summary = json.loads((base / "out-v2-pack-spans-cheap-bar-decimal/joint-return-control-only-50-5-narrow-clock-patch-614/summary.json").read_text(encoding="utf-8"))

start_txt = (logs / "B_cheap_bar_decimal_start.txt").read_text(encoding="utf-8")
start_s = start_txt.split("start=")[1].split()[0].strip()
if "." in start_s:
    main, rest = start_s.split(".", 1)
    frac = "".join(ch for ch in rest if ch.isdigit())
    tz = rest[len(frac):]
    frac = (frac + "000000")[:6]
    start_s = f"{main}.{frac}{tz}"
t0 = datetime.fromisoformat(start_s)
if t0.tzinfo is None:
    t0 = t0.replace(tzinfo=CST)
t1 = datetime.fromtimestamp((logs / "B_cheap_bar_decimal.stdout.log").stat().st_mtime, tz=CST)
wall = (t1 - t0).total_seconds()
(logs / "B_cheap_bar_decimal_wall.txt").write_text(
    f"wall_s={wall:.3f}\nstart={t0.isoformat()}\nend={t1.isoformat()}\n", encoding="utf-8"
)
print(f"wall_s={wall:.3f}")
print(f"total_seconds={phase.get('total_seconds')}")

keys = [
  "replay_M-LAG_P-BASE.marks", "replay_M-REF_P-BASE.marks",
  "replay_M-LAG_P-BASE.lifecycle", "replay_M-REF_P-BASE.lifecycle",
  "replay_M-LAG_P-BASE.attempts", "replay_M-REF_P-BASE.attempts",
  "replay_M-LAG_P-BASE.eligible_scan", "replay_M-REF_P-BASE.eligible_scan",
  "replay_M-LAG_P-BASE.snapshot_orders", "replay_M-REF_P-BASE.snapshot_orders",
  "replay_M-LAG_P-BASE", "replay_M-REF_P-BASE",
  "write_artifacts", "plain_output", "bundle_load",
]
for k in keys:
    print(f"{k}={phase.get(k)}")

nested = []
for k,v in phase.items():
    if not isinstance(v, (int, float)): continue
    if k.startswith("counts.") or k == "total_seconds": continue
    if "." in k and (k.startswith("replay_") or k.startswith("write_")):
        nested.append((k, float(v)))
nested.sort(key=lambda x: -x[1])
print("TOP15:")
for i,(k,v) in enumerate(nested[:15], 1):
    print(f"  {i}. {k}={v}")

sites = phase["counts.replay_M-LAG_P-BASE.marks.mark_sites"]
lag_samp = phase["counts.replay_M-LAG_P-BASE.marks.mark_universe_samples"]
ref_samp = phase["counts.replay_M-REF_P-BASE.marks.mark_universe_samples"]
print(f"M-LAG mean={lag_samp/sites:.6f} max={phase['counts.replay_M-LAG_P-BASE.mark_universe_max']}")
print(f"M-REF mean={ref_samp/sites:.6f} max={phase['counts.replay_M-REF_P-BASE.mark_universe_max']}")

def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj: return obj[key]
        for v in obj.values():
            r = find_key(v, key)
            if r is not None: return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_key(v, key)
            if r is not None: return r
    return None
print("replay_source=", find_key(summary, "replay_source_sha256"))
print("summary_status=", summary.get("status"))