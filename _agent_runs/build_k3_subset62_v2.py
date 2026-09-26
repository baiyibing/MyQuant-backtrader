"""K3 prep: local Mode-B pin + sealed subset62 twin with correct remanifest."""
from __future__ import annotations
import re, sys, time, json, shutil
from pathlib import Path

BT = Path(r"D:\PycharmProjects\MyQuant-backtrader")
sys.path.insert(0, str(BT))

# --- local-only pin (Mode B practice; do not commit) ---
replay_py = BT / "backtest" / "research" / "joint_return_replay.py"
text = replay_py.read_text(encoding="utf-8")
target = "c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7"
m = re.search(r'FROZEN_CONTRACT_HASH\s*=\s*"([0-9a-f]+)"', text)
assert m, "pin not found"
old = m.group(1)
if old != target:
    text2 = text[:m.start(1)] + target + text[m.end(1):]
    bak = BT / "_agent_runs" / f"joint_return_replay.py.bak_k3_pin_{time.strftime('%Y%m%d_%H%M%S')}"
    bak.write_text(text, encoding="utf-8")
    replay_py.write_text(text2, encoding="utf-8")
    print(f"PIN {old} -> {target}; bak={bak}")
else:
    print(f"PIN already {target}")

from backtest.research import joint_return_replay as jr
# force reload
import importlib
importlib.reload(jr)
print("runtime pin", jr.FROZEN_CONTRACT_HASH)
assert jr.FROZEN_CONTRACT_HASH == target

OUT = BT / "backtest_output" / "joint-return-v1-validate-v2-k3"
ART = OUT / "artifacts"
ART.mkdir(parents=True, exist_0=True) if False else ART.mkdir(parents=True, exist_ok=True)

SUBSET_BARS = BT / "backtest_output" / "joint-return-v1-modeb-bars-format-bench" / "artifacts" / "subset_bars.json"
SIDECARS = BT / "backtest_output" / "joint-return-v1-modeb-bars-format-bench-qlib-bin-marks" / "oracle_sidecars.json"
PACK = Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_clock_20260922\portfolio\joint-return-control-only-50-5-narrow-clock-patch-614")

t0 = time.perf_counter()
print("LOAD subset bars...")
bars_only = jr.load_json_bytes(SUBSET_BARS.read_bytes())
bars = bars_only["bars"]
syms = sorted({b["instrument"] for b in bars})
sym_set = set(syms)
print(f"  rows={len(bars)} n_syms={len(syms)} load_s={time.perf_counter()-t0:.2f}")

# filter original intents.csv lines by instrument (preserve bytes style)
intent_raw = (PACK / "intents.csv").read_bytes()
intent_text = intent_raw.decode("utf-8")
intent_lines = intent_text.splitlines(keepends=True)
header = intent_lines[0]
# parse header columns
import csv, io
hdr = next(csv.reader([header]))
inst_idx = hdr.index("instrument")
kept_intent_lines = [header]
kept_intent_ids = set()
id_idx = hdr.index("intent_id")
for line in intent_lines[1:]:
    if not line.strip():
        continue
    row = next(csv.reader([line]))
    inst = row[inst_idx].strip().strip('"')
    if inst in sym_set:
        kept_intent_lines.append(line if line.endswith("\n") or line.endswith("\r\n") else line + "\n")
        kept_intent_ids.add(row[id_idx].strip().strip('"'))
intents_bytes = "".join(kept_intent_lines).encode("utf-8")
print(f"intents kept lines={len(kept_intent_lines)-1} unique_intent_ids={len(kept_intent_ids)}")

# constraints: keep rows without instrument or instrument in subset
c_raw = (PACK / "constraints.csv").read_bytes()
c_text = c_raw.decode("utf-8")
c_lines = c_text.splitlines(keepends=True)
c_header = c_lines[0]
c_hdr = next(csv.reader([c_header]))
c_inst_idx = c_hdr.index("instrument") if "instrument" in c_hdr else None
kept_c = [c_header]
for line in c_lines[1:]:
    if not line.strip():
        continue
    row = next(csv.reader([line]))
    if c_inst_idx is None:
        kept_c.append(line if line.endswith(("\n","\r\n")) else line+"\n")
        continue
    inst = row[c_inst_idx].strip().strip('"')
    if not inst or inst in sym_set:
        kept_c.append(line if line.endswith(("\n","\r\n")) else line+"\n")
constraints_bytes = "".join(kept_c).encode("utf-8")
print(f"constraints kept lines={len(kept_c)-1}")

# pref_check copy
pref_bytes = (PACK / "pref_check.json").read_bytes()

# build pack dir
pack_out = ART / "subset62_intents_pack"
if pack_out.exists():
    shutil.rmtree(pack_out)
pack_out.mkdir(parents=True)
(pack_out / "intents.csv").write_bytes(intents_bytes)
(pack_out / "constraints.csv").write_bytes(constraints_bytes)
(pack_out / "pref_check.json").write_bytes(pref_bytes)

# remanifest with parsed product hashes
m = jr.load_json_bytes((PACK / "manifest.json").read_bytes())
m = dict(m)
m["run_id"] = "joint-return-validate-v2-k3-subset62"
# keep contract_hash as Mode B
assert m["contract_hash"] == target

def art_hashes(name, raw, columns):
    product = jr.read_csv(raw, columns, frozen=True) if columns else jr.load_json_bytes(raw)
    return {"raw_sha256": jr.raw_hash(raw), "content_sha256": jr.content_hash(product)}, product

arts = {}
arts["intents.csv"], intent_rows = art_hashes("intents.csv", intents_bytes, jr.INTENT_FIELDS)
arts["constraints.csv"], _ = art_hashes("constraints.csv", constraints_bytes, jr.CONSTRAINT_FIELDS)
arts["pref_check.json"], _ = art_hashes("pref_check.json", pref_bytes, None)
m["artifacts"] = arts
m["intent_hash"] = arts["intents.csv"]["content_sha256"]
if isinstance(m.get("arm_intent_hashes"), dict) and len(m["arm_intent_hashes"]) == 1:
    k = next(iter(m["arm_intent_hashes"]))
    m["arm_intent_hashes"][k] = m["intent_hash"]
# metadata contract already matches
(pack_out / "manifest.json").write_bytes(jr.canonical_bytes(m) + b"\n")
(pack_out / "NARROW_SUBSET62.md").write_text(
    f"K3 subset62: {len(syms)} syms {syms[0]}..{syms[-1]}; intents={len(intent_rows)}\n", encoding="utf-8")

# verify load_bundle
mm, rows, prov = jr.load_bundle(pack_out)
print("bundle OK", mm["run_id"], "n_intents", len(rows))

# sealed bars with filtered reference_marks
sidecars = json.loads(SIDECARS.read_bytes())
meta = dict(sidecars["metadata"])
marks = meta.get("reference_marks") or {}
if isinstance(marks, dict):
    kept_marks = {k: v for k, v in marks.items() if k in kept_intent_ids}
    # also keep marks whose nested instrument in subset (belt)
    if not kept_marks:
        # fallback: filter by instrument field inside value
        for k, v in marks.items():
            inst = None
            if isinstance(v, dict):
                inst = v.get("instrument") or v.get("execution_symbol")
            if inst in sym_set:
                kept_marks[k] = v
    print(f"reference_marks {len(marks)} -> {len(kept_marks)}")
    meta["reference_marks"] = kept_marks
# initial_lots empty dict OK
bundle = {
    "schema_version": sidecars["schema_version"],
    "kind": sidecars["kind"],
    "metadata": meta,
    "bars": bars,
    "corporate_actions": sidecars.get("corporate_actions") or [],
}
bundle["content_sha256"] = jr.content_hash({k: v for k, v in bundle.items() if k != "content_sha256"})
sealed_path = ART / "subset62_sealed_bars.json"
print("WRITE sealed...")
t1 = time.perf_counter()
sealed_path.write_bytes(jr.canonical_bytes(bundle))
print(f"  bytes={sealed_path.stat().st_size} write_s={time.perf_counter()-t1:.2f} sha={bundle['content_sha256']}")
print(f"  contract={meta.get('contract_hash')} pin_match={meta.get('contract_hash')==jr.FROZEN_CONTRACT_HASH}")
print(f"  n_marks={len(meta.get('reference_marks') or {})}")

meta_out = {
    "n_symbols": len(syms),
    "symbols": [syms[0], syms[-1]],
    "n_bars": len(bars),
    "bars_content_sha256": bundle["content_sha256"],
    "n_intents": len(rows),
    "n_reference_marks": len(meta.get("reference_marks") or {}),
    "sealed_bars": str(sealed_path),
    "intents_pack": str(pack_out),
    "contract_hash": meta.get("contract_hash"),
    "local_pin": jr.FROZEN_CONTRACT_HASH,
    "tip_pin_before": old,
}
(ART / "subset62_meta.json").write_text(json.dumps(meta_out, indent=2), encoding="utf-8")
print("DONE", json.dumps(meta_out, indent=2))
