import json, hashlib
from pathlib import Path

phase = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest_output\joint-return-v1-replay-panel-phase")
pj = json.loads((phase / "phase_timings_B_capacity_sparse.json").read_text(encoding="utf-8"))

# dump structure keys
print("TOP_KEYS", list(pj.keys())[:40])
print("total_seconds", pj.get("total_seconds") or pj.get("total") or pj.get("wall_seconds"))

# find spans - adapt to actual schema used by #186
def walk(obj, prefix=""):
    if isinstance(obj, dict):
        # common shapes: {"name":..,"seconds":..} or nested dict of name->seconds or name->{seconds,children}
        if "seconds" in obj and ("name" in obj or prefix):
            name = obj.get("name", prefix)
            yield name, float(obj["seconds"])
        if "children" in obj and isinstance(obj["children"], (list, dict)):
            ch = obj["children"]
            if isinstance(ch, list):
                for c in ch:
                    yield from walk(c, prefix)
            else:
                for k,v in ch.items():
                    yield from walk(v, f"{prefix}.{k}" if prefix else k)
        for k,v in obj.items():
            if k in ("seconds","name","children","total_seconds"):
                continue
            if isinstance(v, (dict, list)):
                yield from walk(v, f"{prefix}.{k}" if prefix else k)
            elif isinstance(v, (int, float)) and k not in ("count","n","calls"):
                # leaf numeric under known span keys
                pass
    elif isinstance(obj, list):
        for c in obj:
            yield from walk(c, prefix)

# Also try phases/spans/timings keys
for key in ("phases","spans","timings","profile","by_span","records"):
    if key in pj:
        print("HAS", key, type(pj[key]))

# print raw compact sample
raw = json.dumps(pj, ensure_ascii=False)[:2000]
print("RAW_SAMPLE", raw)

spans = list(walk(pj))
# dedup keep max
agg = {}
for n,s in spans:
    agg[n] = max(s, agg.get(n, 0))
items = sorted(agg.items(), key=lambda x: -x[1])
print("SPAN_COUNT", len(items))
for n,s in items[:40]:
    print(f"{s:.6f}\t{n}")
