from pathlib import Path
import re, subprocess
src = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest\research\joint_return_replay.py")
stock = "9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41"
pin = "c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7"
t = src.read_text(encoding="utf-8")
old = f'FROZEN_CONTRACT_HASH = "{pin}"'
new = f'FROZEN_CONTRACT_HASH = "{stock}"'
if old not in t:
    raise SystemExit(f"pin assignment not found; current={t[t.find(chr(70)+'ROZEN'):t.find(chr(70)+'ROZEN')+90]!r}")
t2 = t.replace(old, new, 1)
src.write_text(t2, encoding="utf-8")
m = re.search(r'FROZEN_CONTRACT_HASH\s*=\s*"([0-9a-f]+)"', t2)
print("restored FROZEN=", m.group(1))
r = subprocess.run(["git","diff","--","backtest/research/joint_return_replay.py"], capture_output=True, text=True)
print("git_diff_empty=", (r.stdout.strip()=="" and r.stderr.strip()==""))
if r.stdout.strip():
    print(r.stdout[:800])
print("HEAD=", subprocess.check_output(["git","rev-parse","HEAD"], text=True).strip())
