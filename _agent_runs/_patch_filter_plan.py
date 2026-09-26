from pathlib import Path
p = Path(r"D:\PycharmProjects\MyQuant-backtrader\_agent_runs\run_pbase_narrow_20260922.py")
t = p.read_text(encoding="utf-8")
start = t.find("def filter_plan(")
if start < 0:
    raise SystemExit("filter_plan not found")
end = t.find("\ndef ", start + 1)
if end < 0:
    end = t.find("\n\ndef ", start + 1)
old = t[start:end]
print("OLD LEN", len(old))
print(old[:400])
new = '''def filter_plan(plan: dict, drop: set) -> dict:
    p = json.loads(json.dumps(plan))
    for k in ("sells", "buy_candidates", "buys"):
        if not isinstance(p.get(k), list):
            continue
        kept = []
        for c in p[k]:
            if isinstance(c, dict):
                if c.get("instrument") not in drop:
                    kept.append(c)
            else:
                if c not in drop:
                    kept.append(c)
        p[k] = kept
    if isinstance(p.get("marks"), dict):
        p["marks"] = {k: v for k, v in p["marks"].items() if k not in drop}
    return p
'''
t2 = t[:start] + new + t[end:]
p.write_text(t2, encoding="utf-8")
print("patched ok")
