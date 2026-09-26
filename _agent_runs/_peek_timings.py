from pathlib import Path
p = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest\research\joint_return_replay.py")
t = p.read_text(encoding="utf-8")
keys = ["profile_timings", "phase_timings", "INPUT_BLOCKED", "run_id", "final directory", "must be the final"]
for i,l in enumerate(t.splitlines(),1):
    low=l.lower()
    if any(k.lower() in l for k in keys) or "profile-timings" in l:
        if "timings" in low or "INPUT_BLOCKED" in l or "run_id" in low or "final directory" in low:
            print(f"{i}:{l[:200]}")
