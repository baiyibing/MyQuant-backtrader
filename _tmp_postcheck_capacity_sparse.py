import hashlib, json
from pathlib import Path

phase = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest_output\joint-return-v1-replay-panel-phase")
new = phase / "out-v2-pack-spans-capacity-sparse" / "joint-return-control-only-50-5-narrow-clock-patch-614"
old = phase / "out-v2-pack-spans-lifecycle-clock-cache" / "joint-return-control-only-50-5-narrow-clock-patch-614"
targets = {
    "fills.csv": "d6d40bc4979d462582a8c53c34591cdcca6fafd123857da9d7053aa598fe3376",
    "daily_nav.csv": "2cf88d08b7f50c6c54cdcb8ba64a4fb96024262f988c18d8b025259d1c572685",
}
print("=== SHA256 new vs target vs #186 file ===")
for name in ["fills.csv", "daily_nav.csv", "orders.csv", "summary.json"]:
    np = new / name
    op = old / name
    nh = hashlib.sha256(np.read_bytes()).hexdigest() if np.exists() else None
    oh = hashlib.sha256(op.read_bytes()).hexdigest() if op.exists() else None
    tgt = targets.get(name)
    print(f"{name}:")
    print(f"  new={nh}")
    print(f"  old={oh}")
    if tgt:
        print(f"  tgt={tgt}")
        print(f"  new==tgt: {nh==tgt}")
    print(f"  new==old: {nh==oh and nh is not None}")
    print(f"  new_size={np.stat().st_size if np.exists() else None} old_size={op.stat().st_size if op.exists() else None}")

# forbidden mtime compare
snap = json.loads((phase / "_tmp_forbidden_mtime_snapshot_capacity_sparse.json").read_text(encoding="utf-8"))
changed = []
missing = []
ok = 0
for path, meta in snap["paths"].items():
    p = Path(path)
    if not p.exists():
        missing.append(path)
        continue
    st = p.stat()
    if st.st_mtime_ns != meta["mtime_ns"] or st.st_size != meta["size"]:
        changed.append({
            "path": path,
            "before_mtime_ns": meta["mtime_ns"],
            "after_mtime_ns": st.st_mtime_ns,
            "before_size": meta["size"],
            "after_size": st.st_size,
        })
    else:
        ok += 1
print("=== forbidden mtime ===")
print(f"present_snapshot={snap['present_count']} ok={ok} changed={len(changed)} missing_now={len(missing)}")
for c in changed[:20]:
    print("CHANGED", c)
if missing:
    print("MISSING sample", missing[:5])

# write exit fix note
print("=== pin check ===")
biz = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest\research\joint_return_replay.py").read_text(encoding="utf-8")
stock = "9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41"
pin = "c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7"
print("stock_present", stock in biz, "pin_absent", pin not in biz)
