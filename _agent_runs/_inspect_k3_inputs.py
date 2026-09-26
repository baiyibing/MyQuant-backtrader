from pathlib import Path
import json
root = Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_clock_20260922")
pack = root / "portfolio" / "joint-return-control-only-50-5-narrow-clock-patch-614"
print("pack exists", pack.is_dir())
print("pack files", [p.name for p in pack.iterdir()])
# intents symbols
import csv
syms = set()
with open(pack / "intents.csv", newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    print("intent cols", r.fieldnames)
    for i, row in enumerate(r):
        for k in ("instrument", "symbol", "execution_symbol", "code"):
            if k in row and row[k]:
                syms.add(row[k])
        if i < 2:
            print("sample intent", row)
print("n_intent_rows_approx done; unique_syms", len(syms))
print("sample_syms", sorted(list(syms))[:10], "...", sorted(list(syms))[-5:])
# sidecar
sc = Path(r"backtest_output/joint-return-v1-modeb-bars-format-bench-qlib-bin-marks/oracle_sidecars.json")
print("sidecar exists", sc.exists(), "size", sc.stat().st_size if sc.exists() else None)
if sc.exists():
    data = json.loads(sc.read_bytes())
    print("sidecar keys", list(data.keys()))
    meta = data.get("metadata") or {}
    print("metadata keys", list(meta.keys())[:30])
    print("contract_hash", meta.get("contract_hash"))
    print("kind", data.get("kind"), "schema", data.get("schema_version") or data.get("schema"))
# profile receipt
pr = root / "RECEIPT_PROFILE_TIMINGS.md"
print("profile receipt exists", pr.exists())
if pr.exists():
    print(pr.read_text(encoding="utf-8", errors="replace")[:3000])
