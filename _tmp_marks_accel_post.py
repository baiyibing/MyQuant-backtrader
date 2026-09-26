# -*- coding: utf-8 -*-
from pathlib import Path
import json, hashlib, re, shutil
from datetime import datetime, timezone, timedelta

root = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest_output\joint-return-v1-replay-panel-phase")
timings_path = root / "phase_timings_B_marks_accel.json"
out_new = root / "out-v2-pack-spans-marks-accel" / "joint-return-control-only-50-5-narrow-clock-patch-614"
out_182 = root / "out-v2-pack-spans-182" / "joint-return-control-only-50-5-narrow-clock-patch-614"
biz = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest\research\joint_return_replay.py")
stock = "9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41"
pin = "c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7"
tip = "710687e434d443522fbd5182f2f5811ab4aab646"
wall_s = 772.378

# --- parse timings ---
t = json.loads(timings_path.read_text(encoding="utf-8"))
# may be nested or flat
if isinstance(t, dict) and "phases" in t:
    phases = t["phases"]
elif isinstance(t, dict) and "seconds" in t:
    phases = t["seconds"]
else:
    phases = t

# flatten helper: collect all numeric leaf keys with dotted names if nested
def collect(d, prefix=""):
    out = {}
    if not isinstance(d, dict):
        return out
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[key] = float(v)
        elif isinstance(v, dict):
            out.update(collect(v, key))
    return out

flat = collect(phases) if any(isinstance(v, dict) for v in phases.values()) else {k: float(v) for k, v in phases.items() if isinstance(v, (int, float))}
# Also try reading from stderr-style if keys look wrong
if "total_seconds" not in flat and "total_seconds" in phases:
    flat = {k: float(v) for k, v in phases.items() if isinstance(v, (int, float))}

# Prefer direct read of known structure from stderr dump - re-read file raw
raw = timings_path.read_text(encoding="utf-8")
print("timings_keys_sample:", list(flat.keys())[:8] if flat else "EMPTY")
print("total_seconds:", flat.get("total_seconds"))
print("marks LAG:", flat.get("replay_M-LAG_P-BASE.marks"))
print("marks REF:", flat.get("replay_M-REF_P-BASE.marks"))
print("elig LAG:", flat.get("replay_M-LAG_P-BASE.eligible_scan"))
print("elig REF:", flat.get("replay_M-REF_P-BASE.eligible_scan"))

# baseline #182
b_marks_lag = 135.671305
b_marks_ref = 133.646755
b_elig_lag = 11.384202
b_elig_ref = 10.944708
b_total = 789.156721

a_marks_lag = flat.get("replay_M-LAG_P-BASE.marks")
a_marks_ref = flat.get("replay_M-REF_P-BASE.marks")
a_elig_lag = flat.get("replay_M-LAG_P-BASE.eligible_scan")
a_elig_ref = flat.get("replay_M-REF_P-BASE.eligible_scan")
a_total = flat.get("total_seconds")

def pct(delta, base):
    return (delta / base) * 100.0 if base else float("nan")

d_lag = a_marks_lag - b_marks_lag
d_ref = a_marks_ref - b_marks_ref
print(f"DELTA marks LAG: {d_lag:+.6f} ({pct(d_lag,b_marks_lag):+.3f}%)")
print(f"DELTA marks REF: {d_ref:+.6f} ({pct(d_ref,b_marks_ref):+.3f}%)")

# top 15 child spans under replay_*/write_*
child_keys = [k for k in flat if (
    (k.startswith("replay_") or k.startswith("write_artifacts."))
    and k.count(".") == 1
    and not k.endswith("_P-BASE")  # parent only has one segment after? actually replay_M-LAG_P-BASE.marks has 1 dot
)]
# parents look like replay_M-LAG_P-BASE (no child), children have one dot
children = [(k, flat[k]) for k in flat if k.count(".") == 1 and (k.startswith("replay_") or k.startswith("write_"))]
children.sort(key=lambda x: -x[1])
top15 = children[:15]
top3 = children[:3]
print("TOP3:")
for k, v in top3:
    print(f"  {k}: {v}")

# counts
count_keys = sorted([k for k in flat if k.startswith("counts.")])
counts = {k: int(flat[k]) if flat[k] == int(flat[k]) else flat[k] for k in count_keys}
print("counts_n:", len(counts))

# --- sha256 byte compare ---
def sha256_file(p: Path):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

comparisons = {}
for name in ("fills.csv", "daily_nav.csv"):
    p_new = out_new / name
    p_old = out_182 / name
    s_new = p_new.stat().st_size
    s_old = p_old.stat().st_size
    h_new = sha256_file(p_new)
    h_old = sha256_file(p_old)
    identical = (s_new == s_old) and (h_new == h_old)
    comparisons[name] = {
        "new_path": str(p_new),
        "old_path": str(p_old),
        "size_new": s_new,
        "size_old": s_old,
        "sha_new": h_new,
        "sha_old": h_old,
        "identical": identical,
    }
    print(f"{name}: identical={identical} size={s_new} sha_new={h_new[:16]}... sha_old={h_old[:16]}...")

# --- restore pin ---
text = biz.read_text(encoding="utf-8")
if pin in text:
    text2 = text.replace(pin, stock, 1)
    biz.write_text(text2, encoding="utf-8", newline="\n")
    print("pin restored to stock")
elif stock in text:
    print("already stock")
else:
    print("WARNING: neither pin nor stock found")
tcheck = biz.read_text(encoding="utf-8")
print("biz_hash_state:", "STOCK" if stock in tcheck else ("PIN" if pin in tcheck else "UNKNOWN"))

# git checkout business file to be clean
import subprocess
r = subprocess.run(
    ["git", "checkout", "--", "backtest/research/joint_return_replay.py"],
    cwd=r"D:\PycharmProjects\MyQuant-backtrader",
    capture_output=True, text=True,
)
print("git_checkout_exit:", r.returncode, r.stdout, r.stderr)
r2 = subprocess.run(
    ["git", "status", "--porcelain", "backtest/research/joint_return_replay.py"],
    cwd=r"D:\PycharmProjects\MyQuant-backtrader",
    capture_output=True, text=True,
)
print("biz_git_status:", repr(r2.stdout))
r3 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=r"D:\PycharmProjects\MyQuant-backtrader", capture_output=True, text=True)
print("HEAD:", r3.stdout.strip())

# forbidden outs mtimes / existence check - record sizes so we can say untouched
forbidden = [
    root.parent / "joint-return-v1-modeb",
    root.parent / "joint-return-v1-modeb-cash-1e9",
    root / "out-v2-pack-spans-181",
    root / "out-v2-pack-spans-182",
    root / "phase_timings_B.json",
    root / "phase_timings_B_182.json",
]
# also knife1 outs if present
for name in ("out-v1-json", "out-v2-pack"):
    p = root / name
    if p.exists():
        forbidden.append(p)
# dense panel full timing pack
pack = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest_output\joint-return-v1-dense-panel-bench\packs\clock-patch-614-qlib-bin-FULL-sealed")
forbidden.append(pack)

# save analysis dump for receipt writer
dump = {
    "flat": flat,
    "top15": top15,
    "top3": top3,
    "counts": counts,
    "comparisons": comparisons,
    "a_marks_lag": a_marks_lag,
    "a_marks_ref": a_marks_ref,
    "a_elig_lag": a_elig_lag,
    "a_elig_ref": a_elig_ref,
    "a_total": a_total,
    "d_lag": d_lag,
    "d_ref": d_ref,
    "pct_lag": pct(d_lag, b_marks_lag),
    "pct_ref": pct(d_ref, b_marks_ref),
    "wall_s": wall_s,
    "tip": tip,
}
(Path(r"D:\PycharmProjects\MyQuant-backtrader\_tmp_marks_accel_dump.json")).write_text(
    json.dumps(dump, indent=2), encoding="utf-8"
)
print("dump written")
