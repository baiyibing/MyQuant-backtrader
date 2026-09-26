"""Build sealed 62-symbol twin inputs for K3 (research-only under k3 out)."""
from __future__ import annotations
import csv, json, shutil, sys, time
from pathlib import Path

BT = Path(r"D:\PycharmProjects\MyQuant-backtrader")
sys.path.insert(0, str(BT))
from backtest.research.joint_return_replay import canonical_bytes, content_hash, load_json_bytes

OUT = BT / "backtest_output" / "joint-return-v1-validate-v2-k3"
ART = OUT / "artifacts"
ART.mkdir(parents=True, exist_ok=True)

SUBSET_BARS = BT / "backtest_output" / "joint-return-v1-modeb-bars-format-bench" / "artifacts" / "subset_bars.json"
SIDECARS = BT / "backtest_output" / "joint-return-v1-modeb-bars-format-bench-qlib-bin-marks" / "oracle_sidecars.json"
PACK = Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_clock_20260922\portfolio\joint-return-control-only-50-5-narrow-clock-patch-614")

t0 = time.perf_counter()
print("LOAD subset bars...", flush=True)
bars_only = load_json_bytes(SUBSET_BARS.read_bytes())
bars = bars_only["bars"]
print(f"  rows={len(bars)} load_s={time.perf_counter()-t0:.2f}", flush=True)
syms = sorted({b["instrument"] for b in bars})
print(f"  n_syms={len(syms)} range={syms[0]}..{syms[-1]}", flush=True)
sym_set = set(syms)

sidecars = json.loads(SIDECARS.read_bytes())
meta = dict(sidecars["metadata"])
# filter initial_lots / reference_marks to subset when present
lots = meta.get("initial_lots") or []
if isinstance(lots, list) and lots:
    before = len(lots)
    meta["initial_lots"] = [x for x in lots if (x.get("instrument") in sym_set or x.get("execution_symbol") in sym_set)]
    print(f"  initial_lots {before} -> {len(meta['initial_lots'])}", flush=True)
marks = meta.get("reference_marks") or []
if isinstance(marks, list) and marks:
    before = len(marks)
    meta["reference_marks"] = [x for x in marks if (x.get("instrument") in sym_set or x.get("execution_symbol") in sym_set)]
    print(f"  reference_marks {before} -> {len(meta['reference_marks'])}", flush=True)

bundle = {
    "schema_version": sidecars["schema_version"],
    "kind": sidecars["kind"],
    "metadata": meta,
    "bars": bars,
    "corporate_actions": sidecars.get("corporate_actions") or [],
}
bundle["content_sha256"] = content_hash({k: v for k, v in bundle.items() if k != "content_sha256"})
sealed_path = ART / "subset62_sealed_bars.json"
print(f"WRITE sealed bars -> {sealed_path}", flush=True)
t1 = time.perf_counter()
raw = canonical_bytes(bundle)
sealed_path.write_bytes(raw)
print(f"  bytes={len(raw)} write_s={time.perf_counter()-t1:.2f} sha={bundle['content_sha256']}", flush=True)

# filter intents pack
pack_out = ART / "subset62_intents_pack"
if pack_out.exists():
    shutil.rmtree(pack_out)
pack_out.mkdir(parents=True)

def unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s

# intents
with (PACK / "intents.csv").open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = []
    for row in reader:
        inst = unquote(row.get("instrument") or "")
        if inst in sym_set:
            rows.append(row)
print(f"intents kept {len(rows)}", flush=True)

# write intents with same quoting style as source (fields already quoted in values)
# Prefer using joint_return_replay csv helpers if available — but source uses pre-quoted cells.
# Rebuild via load_bundle path: write unquoted and let runner parse, OR copy quoting.
# Inspect how load parses — typical CSV with quotechar. Values currently include literal quotes.
# Safer: strip quotes and write proper CSV.

from backtest.research import joint_return_replay as jr
clean_rows = []
for row in rows:
    clean = {k: unquote(v) if isinstance(v, str) else v for k, v in row.items()}
    clean_rows.append(clean)

# constraints
with (PACK / "constraints.csv").open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    cfields = reader.fieldnames
    crows_all = list(reader)
crows = []
for row in crows_all:
    inst = unquote(row.get("instrument") or row.get("execution_symbol") or "")
    # keep rows without instrument OR instrument in subset
    if not inst or inst in sym_set:
        crows.append({k: unquote(v) if isinstance(v, str) else v for k, v in row.items()})
print(f"constraints kept {len(crows)}/{len(crows_all)}", flush=True)

(pack_out / "intents.csv").write_bytes(jr.csv_bytes(clean_rows, list(fields)))
(pack_out / "constraints.csv").write_bytes(jr.csv_bytes(crows, list(cfields) if cfields else jr.CONSTRAINT_FIELDS))

# manifest: load, adjust run_id, rehash artifacts
m = json.loads((PACK / "manifest.json").read_bytes())
m = dict(m)
m["run_id"] = "joint-return-validate-v2-k3-subset62"
# update artifact hashes if present
arts = m.get("artifacts") or {}
# rewrite using content of written files
for name, payload_rows, fieldnames in (
    ("intents.csv", clean_rows, list(fields)),
    ("constraints.csv", crows, list(cfields) if cfields else jr.CONSTRAINT_FIELDS),
):
    raw = jr.csv_bytes(payload_rows, fieldnames)
    if name in arts and isinstance(arts[name], dict):
        arts[name] = dict(arts[name])
        arts[name]["raw_sha256"] = jr.raw_hash(raw)
        # some manifests also store content hash of parsed product
        if "content_sha256" in arts[name]:
            # best-effort: hash of parsed rows structure if used
            try:
                arts[name]["content_sha256"] = content_hash(payload_rows)
            except Exception:
                pass
m["artifacts"] = arts
# pref_check if present
if (PACK / "pref_check.json").exists():
    shutil.copy2(PACK / "pref_check.json", pack_out / "pref_check.json")
(pack_out / "manifest.json").write_bytes(jr.canonical_bytes(m) + b"\n")
# NARROW note
(pack_out / "NARROW_SUBSET62.md").write_text(
    f"K3 research subset: {len(syms)} symbols {syms[0]}..{syms[-1]}; intents={len(clean_rows)}\n",
    encoding="utf-8",
)

meta_out = {
    "n_symbols": len(syms),
    "symbols_first_last": [syms[0], syms[-1]],
    "n_bars": len(bars),
    "bars_content_sha256": bundle["content_sha256"],
    "n_intents": len(clean_rows),
    "sealed_bars": str(sealed_path),
    "intents_pack": str(pack_out),
    "contract_hash": meta.get("contract_hash"),
}
(ART / "subset62_meta.json").write_text(json.dumps(meta_out, indent=2), encoding="utf-8")
print("DONE", json.dumps(meta_out, indent=2), flush=True)
