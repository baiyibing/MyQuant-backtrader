from pathlib import Path
import csv, json
QLIB=Path(r"C:\Users\wangc\.qlib\qlib_data\my_data_1min")
INTENTS=Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\portfolio_joint-return-control-only-50-5\intents.csv")
rows=list(csv.DictReader(INTENTS.read_text(encoding="utf-8").splitlines()))
print("cols", list(rows[0].keys()))
for k in rows[0]:
    if any(s in k.lower() for s in ("inst","symbol","code","secu")):
        print("field", k, "examples", [r[k] for r in rows[:8]])
print("feat_sample", [p.name for p in list((QLIB/"features").iterdir())[:12]])
for cand in ["SH600000","sh600000","600000","SZ000001","sz000001"]:
    p=QLIB/"features"/cand.lower()
    print(cand, "dir", p.exists(), "close", (p/"close.1min.bin").exists() if p.exists() else None)
print("all0", (QLIB/"instruments"/"all.txt").read_text(encoding="utf-8").splitlines()[:5])
# also show how RESULT mapped names - check if BJ920680 folder exists under any case
for cand in ["BJ920680","bj920680","920680","SH600200","sh600200","600200"]:
    p=QLIB/"features"/cand.lower()
    print("absent_check", cand, p.exists())
