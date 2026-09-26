"""Post-run checks for marks-hotset plain parity run: SHA parity, forbidden mtimes, knife tree intact."""
import hashlib
import json
from pathlib import Path

root = Path(r"D:\PycharmProjects\MyQuant-backtrader")
phase = root / "backtest_output" / "joint-return-v1-replay-panel-phase"
new = phase / "out-v2-pack-spans-marks-hotset" / "joint-return-control-only-50-5-narrow-clock-patch-614"
prev = phase / "out-v2-pack-spans-capacity-sparse" / "joint-return-control-only-50-5-narrow-clock-patch-614"
targets = {
    "fills.csv": "d6d40bc4979d462582a8c53c34591cdcca6fafd123857da9d7053aa598fe3376",
    "daily_nav.csv": "2cf88d08b7f50c6c54cdcb8ba64a4fb96024262f988c18d8b025259d1c572685",
}
print("=== SHA256 new vs target vs #187 file ===")
ok_parity = True
for name in ["fills.csv", "daily_nav.csv", "orders.csv", "summary.json"]:
    np = new / name
    op = prev / name
    nh = hashlib.sha256(np.read_bytes()).hexdigest() if np.exists() else None
    oh = hashlib.sha256(op.read_bytes()).hexdigest() if op.exists() else None
    tgt = targets.get(name)
    print(f"{name}:")
    print(f"  new={nh}")
    if tgt:
        print(f"  tgt={tgt}  new==tgt: {nh == tgt}")
        ok_parity = ok_parity and nh == tgt
    if name != "summary.json":
        print(f"  prev={oh}  new==prev: {nh == oh and nh is not None}")
        ok_parity = ok_parity and nh == oh

snap = json.loads((phase / "_tmp_forbidden_mtime_snapshot_marks_hotset.json").read_text(encoding="utf-8"))
changed, missing = [], []
for s, meta in snap["paths"].items():
    p = Path(s)
    if not p.exists():
        if not meta.get("is_dir", False):
            missing.append(s)
        continue
    st = p.stat()
    if st.st_mtime_ns != meta["mtime_ns"] or st.st_size != meta["size"]:
        changed.append(s)
print(f"\n=== forbidden mtime: changed={len(changed)} missing={len(missing)} of {snap['present_count']} ===")
for s in changed[:10]:
    print("CHANGED:", s)
for s in missing[:10]:
    print("MISSING:", s)

biz = root / "backtest" / "research" / "joint_return_replay.py"
text = biz.read_text(encoding="utf-8")
stock = "9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41"
pin = "c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7"
print("\n=== business file (knife tree) ===")
print("stock_ok:", stock in text, "| pin_gone:", pin not in text,
      "| knife_ok:", "backfill_scan_steps" in text)
print("PARITY_OK:", ok_parity, "| FORBIDDEN_OK:", not changed and not missing,
      "| PIN_RESTORED:", stock in text and pin not in text)
