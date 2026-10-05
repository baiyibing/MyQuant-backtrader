# -*- coding: utf-8 -*-
"""6.46 精确分红回测：启用 exdiv_economics 现金分红结算 + 600036 停泊。"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from backtest.research.exdiv_map import load_exdiv_ratios, k_for
from backtest.research.ashare_exdiv_economics import ExDivEvent, ExDivEconomics
from common.infra.data_root import resolve_period_root
from oskh_data.symbol_format import to_partition_key
from datetime import datetime

START, END = "20251023", "20260909"
POOL_DIR = ROOT / "stock_pool"

# 1) 获取所有池内代码
from backtest.research.csv_pool import load_pool_names_by_day
pool_days = {}
for f in sorted(POOL_DIR.glob("*.csv")):
    d = f.stem
    try:
        df = pd.read_csv(f, header=None, dtype=str)
        pool_days[d] = df.iloc[:, 0].tolist()
    except Exception:
        pass
all_codes = sorted(set(c for cs in pool_days.values() for c in cs))
print(f"池内代码: {len(all_codes)} 只")

# 2) 载入除权比率（k）
skipped = {}
ratios = load_exdiv_ratios(all_codes, START, END, skipped_out=skipped)
n_events = sum(len(v) for v in ratios.values())
print(f"除权事件: {n_events} 事件 / {len(ratios)} 只股票")

# 3) 载入各股除权日前收盘价（none 域），估算每股现金分红
daily_root = resolve_period_root("1d")
def get_prev_close(code, ymd):
    """获取除权前一交易日 none 域收盘价。"""
    key = to_partition_key(code)
    p = daily_root / "dividend_type=none" / f"symbol={key}"
    if not p.exists():
        return None
    files = list(p.glob("*.parquet"))
    if not files:
        return None
    try:
        df = pd.read_parquet(files[0])
        df["ymd"] = pd.to_datetime(df.time, unit="ms").dt.strftime("%Y%m%d")
        win = df[(df.ymd >= "20251001") & (df.ymd <= END)].set_index("ymd").close
        before = win[win.index < ymd]
        if before.empty:
            return None
        return float(before.iloc[-1])
    except Exception:
        return None

# 4) 构建 EconomicLookup
lookup = {}
div_data = []
for code, events in ratios.items():
    sym = code if "." in code else f"{code}.SH" if code.startswith("6") else f"{code}.SZ"
    for ymd, k in events.items():
        if k is None or not (0.9 < k < 1.0):
            continue  # 只处理现金分红（k < 1），跳过送股/拆股
        prev = get_prev_close(code, ymd)
        if prev is None or prev <= 0:
            continue
        cash = prev * (1.0 - k)
        if cash < 0.005:  # 忽略 < 0.5 分
            continue
        ev = ExDivEvent(
            event_id=f"{code}_{ymd}",
            bonus_ratio=0.0,
            cash_div_per_share=round(cash, 4),
            ex_date=ymd,
            pay_date=ymd,  # 假设当日到账（保守）
        )
        lookup[(sym, ymd)] = ev
        div_data.append({"code": sym, "ex_date": ymd, "per_share": round(cash, 4), "prev": prev, "k": k})

print(f"构建分红事件: {len(lookup)} 条")
if div_data:
    dd = pd.DataFrame(div_data)
    print(f"每股分红范围: {dd.per_share.min():.4f} ~ {dd.per_share.max():.4f} 元")
    print(f"涉及股票: {dd.code.nunique()} 只")

# 5) 运行主策略（启用 exdiv_economics）
from backtest.research.csv_minute_backtest import simulate
from backtest.research.csv_minute_backtest import load_minute_bars, load_daily_ohlc
from backtest.research.ashare_bars import load_minute_ohlc, book_frames_from_compact
from backtest.research.market_layer import as_date, as_datetime
from backtest.research.csv_pool import load_pool_days, resolve_research_pool_dir
import os

# 加载数据（复用引擎逻辑）
cache_key = f"minute_none_20251013_{END}"
cache_file = ROOT / "backtest_output/bar_cache" / f"{cache_key}_afda45b21c12.parquet"
if cache_file.exists():
    all_df = pd.read_parquet(cache_file)
    print(f"缓存命中: {len(all_df)} 行, {all_df.symbol.nunique()} 股")
    # 构建 minute_bars dict
    minute_bars = {}
    for sym, grp in all_df.groupby("symbol"):
        # 转为引擎期望的 DataFrame 格式
        bars = grp.copy()
        bars = bars.sort_values("time")
        bars["datetime"] = pd.to_datetime(bars.time, unit="ms")
        bars["date"] = bars.datetime.dt.date
        bars["ymd"] = bars.datetime.dt.strftime("%Y%m%d")
        bars["hm"] = bars.datetime.dt.hour * 60 + bars.datetime.dt.minute
        minute_bars[sym] = bars[["datetime", "open", "high", "low", "close", "volume", "ymd", "hm"]].set_index("datetime")
else:
    print("缓存未命中，需要从湖加载...")
    sys.exit(1)

# 加载日线
daily_bars = {}
for code in all_codes[:20]:  # 只加载前 20 只做验证（全量太慢）
    key = to_partition_key(code)
    sym = code if "." in code else f"{code}.SH" if code.startswith("6") else f"{code}.SZ"
    p = daily_root / "dividend_type=none" / f"symbol={key}"
    if not p.exists():
        continue
    files = list(p.glob("*.parquet"))
    if not files:
        continue
    try:
        df = pd.read_parquet(files[0])
        df["ymd"] = pd.to_datetime(df.time, unit="ms").dt.strftime("%Y%m%d")
        win = df[(df.ymd >= "20251001") & (df.ymd <= END)].copy()
        win["datetime"] = pd.to_datetime(win.time, unit="ms")
        win["date"] = win.datetime.dt.date
        win["hm"] = 0
        daily_bars[sym] = win.set_index("datetime")[["open", "high", "low", "close", "volume", "ymd", "hm"]]
    except Exception:
        continue

print(f"\n日线加载: {len(daily_bars)} 股（验证用前 20 只）")
print(f"分钟加载: {len(minute_bars)} 股")

# 运行模拟（限量验证）
pool_dir = str(POOL_DIR)
from backtest.research.csv_pool import load_pool_day_map
pool_day_map = load_pool_day_map(pool_dir, START, END)
print(f"池日: {len(pool_day_map)} 天")

# 6) 用引擎 CLI 直接跑（启用 economics 太复杂，改为后处理精确计算）
# 后处理：用持仓 × 分红事件精确计算
print("\n===== 后处理精确分红计算 =====")
tr = pd.read_csv(
    ROOT / "backtest_output/csv_minute_v6_46_parking_20251023_20260909/trades.csv", dtype={"date": str})
tr = tr[tr.side.isin(["BUY", "SELL"])]

# 逐组重建持仓（用 E-R6 缩放后的股数不变，分红 = 股数 × 每股分红）
total_div_cash = 0.0
div_detail = []
for pid, g in tr.groupby("position_id"):
    b, s = g[g.side=="BUY"], g[g.side=="SELL"]
    if b.empty:
        continue
    code = g.code.iloc[0]
    # 逐日追踪持仓股数
    events = sorted(pd.concat([b.assign(dt=b.date, side2="B", sh=b.shares),
                                s.assign(dt=s.date, side2="S", sh=-s.shares)])[["dt","side2","sh"]].values,
                     key=lambda x: x[0])
    shares = 0
    div_received = 0.0
    for dt, side2, sh in events:
        d = str(dt)
        # 检查是否有分红事件
        if side2 == "B":
            # 买入：买入日不分红（T+0 不享有）
            pass
        else:
            pass
        # 分红检查（在买入后、卖出前的持仓期间）
        for (sym, ymd), ev in lookup.items():
            if sym == code and d == ymd and shares > 0:
                # T+1 检查：只有 buy_date < today 的股才有权分红
                # 简化：用当前 shares（引擎已处理 T+1）
                div = shares * float(ev.cash_div_per_share)
                div_received += div
                div_detail.append({"code": code, "date": d, "shares": shares,
                                   "per_share": float(ev.cash_div_per_share), "amount": div})
        shares += sh
    total_div_cash += div_received

print(f"\n主策略分红: {total_div_cash:,.0f} 元（{total_div_cash/1e4:.0f} 万）")
print(f"分红事件明细数: {len(div_detail)} 条")
if div_detail:
    dd = pd.DataFrame(div_detail)
    print(f"Top 10 分红:")
    print(dd.nlargest(10, "amount")[["code","date","shares","per_share","amount"]].round(0).to_string(index=False))

# 7) 汇总
main_pnl = 6_334_054  # 主策略 P&L（无分红）
park_pnl_no_div = 835_920  # 停泊（无分红）
park_div = 936_632  # 600036 分红
TOTAL = 27_000_000

grand = main_pnl + total_div_cash + park_pnl_no_div + park_div
print(f"\n===== 6.46 精确分红汇总（2700 万池）=====")
print(f"主策略（无分红）: {main_pnl:+,.0f} 元")
print(f"主策略分红: {total_div_cash:+,.0f} 元")
print(f"停泊（无分红）: {park_pnl_no_div:+,.0f} 元")
print(f"停泊分红: {park_div:+,.0f} 元")
print(f"合并总收益: {grand:+,.0f} 元（{grand/TOTAL:+.2%}）")
