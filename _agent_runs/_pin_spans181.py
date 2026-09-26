from pathlib import Path
import re, shutil

src = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest\research\joint_return_replay.py")
bak = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest\research\joint_return_replay.py.bak_spans181_pin_20260924")
stock = "9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41"
pin = "c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7"
shutil.copy2(src, bak)
t = src.read_text(encoding="utf-8")
if stock not in t:
    raise SystemExit("stock hash not found")
# replace only the FROZEN assignment line's hash
def repl(m):
    return m.group(0).replace(stock, pin)
t2, n = re.subn(
    r'(FROZEN_CONTRACT_HASH\s*=\s*")' + stock + r'(")',
    r"\1" + pin + r"\2",
    t,
    count=1,
)
if n != 1:
    raise SystemExit(f"expected 1 FROZEN replace, got {n}")
src.write_text(t2, encoding="utf-8")
m = re.search(r'FROZEN_CONTRACT_HASH\s*=\s*"([0-9a-f]+)"', t2)
print("FROZEN=", m.group(1) if m else None)
print("pin_count", t2.count(pin))
print("stock_left", t2.count(stock))
print("bak", bak)
