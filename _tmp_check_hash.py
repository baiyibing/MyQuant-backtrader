from pathlib import Path
import re
p = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest\research\joint_return_replay.py")
t = p.read_text(encoding="utf-8")
m = re.search(r"FROZEN_CONTRACT_HASH\s*=\s*[\"']([0-9a-f]+)[\"']", t)
print("stock_current:", m.group(1) if m else "NOT_FOUND")
bak = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest\research\joint_return_replay.py.bak_spans182_pin_20260924")
tb = bak.read_text(encoding="utf-8")
mb = re.search(r"FROZEN_CONTRACT_HASH\s*=\s*[\"']([0-9a-f]+)[\"']", tb)
print("bak182:", mb.group(1) if mb else "NOT_FOUND")
stock_exp = "9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41"
pin_exp = "c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7"
print("match_stock:", bool(m) and m.group(1) == stock_exp)
print("pin_target:", pin_exp)
# also show if bak has stock or pin
print("bak_is_stock:", bool(mb) and mb.group(1) == stock_exp)
print("bak_is_pin:", bool(mb) and mb.group(1) == pin_exp)
