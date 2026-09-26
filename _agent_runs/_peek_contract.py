import re
from pathlib import Path
p = Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_clock_20260922\portfolio\joint-return-control-only-50-5-narrow-clock-patch-614-cash-1e9\manifest.json")
pat = re.compile(rb"contract_hash\"?\s*:\s*\"([0-9a-f]+)\"")
with p.open("rb") as f:
    head = f.read(2_000_000)
    f.seek(max(0, p.stat().st_size - 1_000_000))
    tail = f.read()
for label, blob in [("head", head), ("tail", tail)]:
    for m in pat.finditer(blob):
        print(label, m.group(1).decode())
