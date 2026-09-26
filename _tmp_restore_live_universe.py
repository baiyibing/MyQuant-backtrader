from pathlib import Path
import shutil
biz = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest\research\joint_return_replay.py")
bak = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest\research\joint_return_replay.py.bak_live_universe_pin_20260924")
stock = "9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41"
pin = "c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7"
text = biz.read_text(encoding="utf-8")
if pin not in text:
    raise SystemExit("pin not found; unexpected state")
# Prefer bak restore if available
if bak.exists():
    shutil.copy2(bak, biz)
    print("restored from bak")
else:
    text2 = text.replace(pin, stock, 1)
    biz.write_text(text2, encoding="utf-8", newline="\n")
    print("restored via replace")
t = biz.read_text(encoding="utf-8")
print("after:", "STOCK" if stock in t and pin not in t else "BAD")
print("pin_present=", pin in t, "stock_present=", stock in t)
