# -*- coding: utf-8 -*-
"""6.46 停泊运行器：先跑 6.45 主策略，再用逐日现金余额模拟 600036 停泊。

停泊规则：
  每日收盘后：闲置现金 = cash - 200万缓冲；买入 600036 = 闲置 × 60%
  策略买入前：如 cash < 需求 → 卖 600036 补足
  T+1：当日买入的 600036 当日不可卖
  600036 按当日 14:55 close 成交、整百股、佣金 0.1%
"""
import sys, json
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# 1) 跑主策略 6.45
PY = "D:/anaconda3/envs/vanna312/python.exe"
import subprocess
out_dir = ROOT / "backtest_output/csv_minute_v6_46_parking_20251023_20260909"
out_dir.mkdir(parents=True, exist_ok=True)
r = subprocess.run(
    [PY, "backtest/research/csv_minute_backtest.py",
     "--strategy", "version6_45",
     "--start", "20251023", "--end", "20260909",
     "--cash-total", "27000000", "--name-budget", "10000",
     "--out-dir", str(out_dir)],
    capture_output=True, text=True, timeout=600)
print("主策略 6.45:", r.stdout[-200:] if len(r.stdout) > 200 else r.stdout)
if r.returncode != 0:
    print("ERROR:", r.stderr[-500:])
    sys.exit(1)

# 2) 读取主策略逐日现金（从 trades 重建）
tr = pd.read_csv(out_dir / "trades.csv", dtype={"date": str})
tr = tr[tr.side.isin(["BUY", "SELL"])]
eq = pd.read_csv(out_dir / "daily_equity.csv", dtype={"date": str})
total_cash = 27_000_000

# 逐日净流
tr_sorted = tr.sort_values("date")
daily_flow = tr_sorted.groupby("date").apply(
    lambda g: g[g.side == "SELL"].notional.sum() - g[g.side == "BUY"].notional.sum() - g.commission.sum()
)
# 逐日累计现金
dates = eq.date.tolist()
cash_series = {}
cum_cash = total_cash
for d in dates:
    if d in daily_flow.index:
        cum_cash += daily_flow[d]
    cash_series[d] = cum_cash

# 3) 载入 600036 分钟数据（从 bar_cache 或直接用日线近似）
# 先用日线 14:55 近似（简化：用日收盘价）
# 尝试从主策略 trades 中提取 600036 的价格；否则用 lake
cmb_daily = None
try:
    # 尝试从 lake 读取 600036 日线
    from backtest.research.ashare_bars import load_daily_bars
    bars = load_daily_bars("600036.SH", "20251013", "20260909", dividend_type="none")
    if bars is not None and not bars.empty:
        cmb_daily = bars[["close"]].copy()
        cmb_daily.index = cmb_daily.index.strftime("%Y%m%d")
except Exception as e:
    print(f"lake load failed: {e}")

if cmb_daily is None:
    print("无法载入 600036 数据，停泊模拟中止")
    sys.exit(1)

# 4) 模拟停泊
PARKING_FRAC = 0.60
BUFFER = 2_000_000
COMMISSION = 0.001

parking_shares = 0
parking_cost = 0.0  # 总成本
parking_buy_date = None  # 最近买入日（T+1）
parking_pnl = 0.0  # 已实现盈亏
parking_trades = []  # 停泊交易记录

for d in dates:
    px = cmb_daily.loc[d, "close"] if d in cmb_daily.index else None
    if px is None or px <= 0:
        continue
    cash = cash_series[d]

    # 策略买入前：如现金不足，卖 600036
    # 近似：检查当日是否有策略买入且现金紧张
    day_buys = tr[(tr.date == d) & (tr.side == "BUY")]
    day_buy_amt = day_buys.notional.sum() if not day_buys.empty else 0
    if day_buy_amt > 0 and cash < BUFFER + day_buy_amt * 0.5:
        # 需要卖 600036
        needed = BUFFER + day_buy_amt - cash
        if parking_shares > 0 and (parking_buy_date is None or parking_buy_date < d):
            sell_shares = min(parking_shares, int(needed / px / 100) * 100)
            if sell_shares > 0:
                sell_amt = sell_shares * px
                comm = sell_amt * COMMISSION
                avg_cost = parking_cost / parking_shares
                realized = (px - avg_cost) * sell_shares - comm
                parking_pnl += realized
                parking_shares -= sell_shares
                parking_cost -= avg_cost * sell_shares
                cash += sell_amt - comm
                cash_series[d] = cash
                parking_trades.append({"date": d, "side": "SELL", "shares": sell_shares,
                                       "px": px, "amt": sell_amt, "pnl": realized})

    # 收盘后：闲置现金买 600036
    idle = cash - BUFFER
    if idle > 100_000:  # 至少 10 万才买
        buy_amt = idle * PARKING_FRAC
        buy_shares = int(buy_amt / px / 100) * 100  # 整百股
        if buy_shares > 0:
            buy_cost = buy_shares * px * (1 + COMMISSION)
            if buy_cost <= idle:
                parking_shares += buy_shares
                parking_cost += buy_shares * px
                parking_buy_date = d
                cash -= buy_cost
                cash_series[d] = cash
                parking_trades.append({"date": d, "side": "BUY", "shares": buy_shares,
                                       "px": px, "amt": buy_shares * px, "pnl": 0})

# 期末估值
if parking_shares > 0 and dates:
    last_date = dates[-1]
    if last_date in cmb_daily.index:
        last_px = cmb_daily.loc[last_date, "close"]
        mkt_val = parking_shares * last_px
        unrealized = mkt_val - parking_cost
    else:
        mkt_val = parking_cost  # 无价则按成本
        unrealized = 0
else:
    mkt_val = 0
    unrealized = 0

# 5) 结果
main_pnl = eq.equity.iloc[-1] - total_cash
parking_total = parking_pnl + unrealized
print(f"\n===== 6.46 停泊结果（2700 万池 + 600036 停泊）=====")
print(f"主策略（6.45）净值: {eq.equity.iloc[-1]:,.0f} / {total_cash:,}")
print(f"主策略收益: {main_pnl:+,.0f} 元（{main_pnl/total_cash:+.2%}）")
print(f"停泊 600036: {len(parking_trades)} 笔 | 已实现 {parking_pnl:+,.0f} 元 | 浮动 {unrealized:+,.0f} 元")
print(f"停泊期末: {parking_shares:,} 股 @ 市值 {mkt_val:,.0f} 元")
print(f"停泊总盈亏: {parking_total:+,.0f} 元")
print(f"合并总收益: {(main_pnl + parking_total):+,.0f} 元（{(main_pnl + parking_total)/total_cash:+.2%}）")
print(f"\n停泊交易前 10 笔:")
for t in parking_trades[:10]:
    print(f"  {t['date']} {t['side']:4s} {t['shares']:>6,} 股 @ {t['px']:.2f} = {t['amt']:>10,.0f} 元")
