from pathlib import Path
import shutil
biz = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest\research\joint_return_replay.py")
bak = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest\research\joint_return_replay.py.bak_arc_close_pin_20260924")
stock = "9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41"
pin = "c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7"
knives = ("backfill_scan_steps", "cannot rewrite history")
text = biz.read_text(encoding="utf-8")
for knife in knives:
    if knife not in text:
        raise SystemExit(f"knife marker missing: {knife}")
if stock not in text:
    if pin in text:
        print("already pinned")
    else:
        raise SystemExit("stock hash not found in business file")
else:
    shutil.copy2(biz, bak)
    text2 = text.replace(stock, pin, 1)
    if text2.count(pin) != 1:
        raise SystemExit("pin replace failed")
    biz.write_text(text2, encoding="utf-8", newline="\n")
    print("pinned ok; bak=", bak)
t = biz.read_text(encoding="utf-8")
print("after:", "PINNED" if pin in t else "NOT_PINNED", "; stock_present=", stock in t,
      "; knives=", all(k in t for k in knives))
print("HEAD:", open(r"D:\PycharmProjects\MyQuant-backtrader\.git\HEAD").read().strip())
