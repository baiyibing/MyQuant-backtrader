import json, sys
from pathlib import Path
sys.path.insert(0, ".")
from backtest.research import joint_return_replay as jr

pack = Path("backtest_output/joint-return-v1-validate-v2-k3/artifacts/subset62_intents_pack")
bars = Path("backtest_output/joint-return-v1-validate-v2-k3/artifacts/subset62_sealed_bars.json")

print("FROZEN_CONTRACT_HASH", jr.FROZEN_CONTRACT_HASH)
try:
    m, rows, prov = jr.load_bundle(pack)
    print("bundle OK", "run_id", m.get("run_id"), "n_intents", len(rows), "arms", sorted({r.get("arm_id") for r in rows})[:5])
except Exception as e:
    print("bundle FAIL", type(e).__name__, e)

# peek sealed metadata marks/lots
raw_head_meta = None
import orjson
# stream just metadata via full load is heavy; use already-known sidecar + our write notes
sc = json.loads(Path("backtest_output/joint-return-v1-modeb-bars-format-bench-qlib-bin-marks/oracle_sidecars.json").read_bytes())
meta = sc["metadata"]
lots = meta.get("initial_lots")
marks = meta.get("reference_marks")
print("lots type", type(lots).__name__, "len", len(lots) if hasattr(lots, "__len__") else None)
print("marks type", type(marks).__name__, "len", len(marks) if hasattr(marks, "__len__") else None)
if isinstance(lots, list) and lots:
    print("lot0 keys", list(lots[0].keys()) if isinstance(lots[0], dict) else lots[0])
if isinstance(marks, list) and marks:
    print("mark0 keys", list(marks[0].keys()) if isinstance(marks[0], dict) else type(marks[0]))
elif isinstance(marks, dict):
    print("marks dict keys sample", list(marks.keys())[:5], "n", len(marks))

# verify seal quickly without loading bars list fully: recompute from file via jr load
print("loading sealed for seal check (heavy)...")
b = jr.load_json_bytes(bars.read_bytes())
body = {k:v for k,v in b.items() if k != "content_sha256"}
ok = b["content_sha256"] == jr.content_hash(body)
print("seal_ok", ok, "kind", b.get("kind"), "n_bars", len(b["bars"]))
print("meta contract", b["metadata"].get("contract_hash"))
print("n_ref_marks_in_sealed", len(b["metadata"].get("reference_marks") or []))
print("n_lots_in_sealed", len(b["metadata"].get("initial_lots") or []))
