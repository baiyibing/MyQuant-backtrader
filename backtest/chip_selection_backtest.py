#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
chip_selection_backtest.py — chip 因子选股回测对比

流程：
1. 从 float_shares.parquet 获取全市场标的（2,079 只）作为原始池
2. 对每只标的计算日线 chip 因子
3. 按 chip 规则过滤/排序，生成筛选池
4. 原始池 vs 筛选池分别等权回测，对比收益指标

用法：
    # 日线（默认），全市场 2,079 只，对比全部规则
    python backtest/chip_selection_backtest.py --all

    # 分钟线模式
    python backtest/chip_selection_backtest.py --all --freq 1m

    # 抽样 200 只
    python backtest/chip_selection_backtest.py --sample 200 --freq 1m

    # 全量 2,079 只
    python backtest/chip_selection_backtest.py --all

    # 指定 chip CSV
    python backtest/chip_selection_backtest.py --chip-csv backtest_output/chip_daily_20260513.csv

chip 选股规则：
    all        — 无过滤（基准）
    mid        — 中间区间 [0.2, 0.8]：趋势中段，安全边际最好
    trend      — 中期趋势 [0.5, 1.0]：趋势做多（20 日动量视角）
    avoid_high — 排除 >0.8：避免短期反转风险
    avoid_low  — 排除 <0.2：避免底部停滞

输出：
    backtest_output/chip_backtest_compare_{tag}.csv  — 各规则收益对比
"""

import argparse
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

import backtrader as bt

from backtest.chip_algorithm import adapt_columns, daily_chip_distribution, minute_chip_distribution, cyq
from common.infra.data_root import resolve_source_parquet
from backtest.stock_data_reader import StockDataReader

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
FLOAT_SHARES_PATH = str(resolve_source_parquet("float_shares.parquet"))

_reader = None

def _get_reader():
    global _reader
    if _reader is None:
        _reader = StockDataReader()
    return _reader
OUTPUT_DIR = os.path.join(REPO, "backtest_output")

INITIAL_CASH = 1_000_000.0
COMMISSION = 0.0005
WINDOW_DAYS = 80
TOP_N = 50  # 过滤后取前 N 只

# chip 选股规则
RULES = {
    "all": {
        "label": "基准（无过滤）",
        "filter": lambda df: df,
    },
    "mid": {
        "label": "中间区间 [0.2, 0.8]",
        "filter": lambda df: df[(df["cyqk_c"] >= 0.2) & (df["cyqk_c"] <= 0.8)],
    },
    "trend": {
        "label": "中期趋势 [0.5, 1.0]",
        "filter": lambda df: df[(df["cyqk_c"] >= 0.5) & (df["cyqk_c"] <= 1.0)],
    },
    "avoid_high": {
        "label": "排除高位 >0.8",
        "filter": lambda df: df[df["cyqk_c"] <= 0.8],
    },
    "avoid_low": {
        "label": "排除低位 <0.2",
        "filter": lambda df: df[df["cyqk_c"] >= 0.2],
    },
}


# ---------------------------------------------------------------------------
# 策略
# ---------------------------------------------------------------------------
class EqualWeightStrategy(bt.Strategy):
    """等权买入持有。"""

    def __init__(self):
        self._bought = False

    def next(self):
        if self._bought:
            return
        n = len([d for d in self.datas if len(d) >= 1])
        if n == 0:
            return
        cash_per = self.broker.getcash() / n
        for d in self.datas:
            if len(d) < 1:
                continue
            size = int(cash_per / d.close[0] / 100) * 100
            if size >= 100:
                self.buy(data=d, size=size)
        self._bought = True


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------
def load_data(code: str, bars: int = 120, reader=None) -> pd.DataFrame:
    if reader is None:
        reader = _get_reader()
    df = reader.read_stock(code, period='1d', adjust_type='none')
    if df is None:
        return None
    df = df.rename(columns={"time": "datetime"})
    df["datetime"] = pd.to_datetime(df["datetime"], unit="ms")
    df.set_index("datetime", inplace=True)
    return df.tail(bars)


def compute_chip_factor(code: str, freq: str = "1d", reader=None) -> dict:
    """计算单只标的的 chip 因子。"""
    if reader is None:
        reader = _get_reader()
    if freq == "1m":
        df = reader.read_stock(code, period='1m', adjust_type='none')
        if df is None:
            return None
        df["dt"] = pd.to_datetime(df["time"], unit="ms")
        dates = sorted(df["dt"].dt.date.unique())
        if len(dates) < WINDOW_DAYS:
            return None
        df = df[df["dt"].dt.date >= dates[-WINDOW_DAYS]]
        if len(df) < 1000:
            return None
    else:
        df = load_data(code, bars=WINDOW_DAYS, reader=reader)
        if df is None or len(df) < WINDOW_DAYS:
            return None

    try:
        arr = adapt_columns(df, stock_code=code)
        if freq == "1m":
            dist = minute_chip_distribution(arr)
        else:
            dist = daily_chip_distribution(arr, method="triang")
        ct = float(arr[-1, 0])
        cf = cyq.ChipFactor(ct, dist)
        return {
            "stock_code": code,
            "cyqk_c": cf.get_cyqk_c(),
            "asr": cf.get_asr(),
            "ckdw": cf.get_ckdw(),
            "prp": cf.get_prp(),
        }
    except Exception:
        return None


def run_backtest(codes: list, label: str, bars: int = 60, reader=None) -> dict:
    """等权回测。"""
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.setcash(INITIAL_CASH)
    cerebro.broker.setcommission(commission=COMMISSION)

    added = 0
    for code in codes:
        df = load_data(code, bars=bars, reader=reader)
        if df is not None and len(df) >= bars:
            cerebro.adddata(bt.feeds.PandasData(dataname=df, name=code))
            added += 1

    if added == 0:
        return {"label": label, "n_stocks": 0, "total_return": 0, "max_drawdown": 0, "sharpe": 0}

    cerebro.addstrategy(EqualWeightStrategy)
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe",
                        timeframe=bt.TimeFrame.Days, annualize=True)

    results = cerebro.run()
    strat = results[0]
    ret = strat.analyzers.returns.get_analysis()
    dd = strat.analyzers.drawdown.get_analysis()
    sr = strat.analyzers.sharpe.get_analysis()

    return {
        "label": label,
        "n_stocks": added,
        "total_return": round((ret.get("rtot", 0) or 0) * 100, 2),
        "max_drawdown": round(dd.get("max", {}).get("drawdown", 0) or 0, 2),
        "sharpe": round(sr.get("sharperatio", 0) or 0, 2),
    }


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="chip 因子选股回测对比")
    parser.add_argument("--chip-csv", help="已有的 chip 截面 CSV（跳过因子计算）")
    parser.add_argument("--sample", type=int, default=0, help="随机抽样 N 只计算 chip 因子")
    parser.add_argument("--all", action="store_true", help="全量 2,079 只")
    parser.add_argument("--top", type=int, default=TOP_N, help=f"过滤后取前 N 只（默认 {TOP_N}）")
    parser.add_argument("--bars", type=int, default=60, help="回测 bar 数（默认 60）")
    parser.add_argument("--freq", default="1d", choices=["1d", "1m"],
                        help="数据频率：1d（日线，默认）或 1m（分钟线）")
    parser.add_argument("--rule", default="all", choices=list(RULES.keys()),
                        help="chip 选股规则（对比模式默认跑全部规则）")
    args = parser.parse_args()
    freq = args.freq

    # 获取 chip 截面
    reader = _get_reader()

    if args.chip_csv:
        chip_df = pd.read_csv(args.chip_csv)
        print(f"Loaded chip CSV: {len(chip_df)} stocks")
    elif args.sample > 0 or args.all:
        fs_df = pd.read_parquet(FLOAT_SHARES_PATH)
        codes = fs_df["stock_code"].tolist()
        if args.sample > 0:
            rng = np.random.default_rng(42)
            codes = sorted(rng.choice(codes, size=min(args.sample, len(codes)), replace=False))
        print(f"Computing chip factors for {len(codes)} stocks ({WINDOW_DAYS}d window) ...")
        results = []
        for i, code in enumerate(codes):
            r = compute_chip_factor(code, freq=freq, reader=reader)
            if r:
                results.append(r)
            if (i + 1) % 200 == 0:
                print(f"  ... {i + 1}/{len(codes)}")
        chip_df = pd.DataFrame(results).sort_values("cyqk_c", ascending=False)
        print(f"  Done: {len(chip_df)} stocks computed")
    else:
        # 默认：抽样 200
        fs_df = pd.read_parquet(FLOAT_SHARES_PATH)
        codes = fs_df["stock_code"].tolist()
        rng = np.random.default_rng(42)
        codes = sorted(rng.choice(codes, size=200, replace=False))
        print(f"Computing chip factors for 200 sampled stocks ...")
        results = []
        for i, code in enumerate(codes):
            r = compute_chip_factor(code, freq=freq, reader=reader)
            if r:
                results.append(r)
        chip_df = pd.DataFrame(results).sort_values("cyqk_c", ascending=False)
        print(f"  Done: {len(chip_df)} stocks")

    if chip_df.empty:
        print("[FAIL] No chip factors computed")
        reader.close()
        sys.exit(1)

    # 因子分布
    print(f"\n  cyqk_c: median={chip_df['cyqk_c'].median():.3f}  "
          f"HIGH(>0.8)={(chip_df['cyqk_c']>0.8).sum()}  "
          f"LOW(<0.2)={(chip_df['cyqk_c']<0.2).sum()}  "
          f"MID[0.2-0.8]={((chip_df['cyqk_c']>=0.2)&(chip_df['cyqk_c']<=0.8)).sum()}")

    # 回测
    tag = datetime.now().strftime("%Y%m%d_%H%M")
    print(f"\n  Backtest: {args.top} stocks per rule, {args.bars} bars\n")
    print(f"  {'Rule':<25} {'N':>5} {'Return':>10} {'MaxDD':>8} {'Sharpe':>8}")
    print(f"  {'-'*25} {'-'*5} {'-'*10} {'-'*8} {'-'*8}")

    # 各规则从过滤池中随机抽样（同等条件对比，不受排序影响）
    rng_bt = np.random.default_rng(123)
    results = []
    for name, rule in RULES.items():
        filtered = rule["filter"](chip_df)
        codes = filtered["stock_code"].tolist()
        if len(codes) > args.top:
            codes = sorted(rng_bt.choice(codes, size=args.top, replace=False))
        r = run_backtest(codes, rule["label"], bars=args.bars, reader=reader)
        results.append(r)
        print(f"  {r['label']:<25} {r['n_stocks']:>5} {r['total_return']:>+9.2f}% "
              f"{r['max_drawdown']:>7.2f}% {r['sharpe']:>7.2f}")

    # 对比
    base = results[0]
    print(f"\n  vs 基准:")
    for r in results[1:]:
        if r["n_stocks"] == 0:
            continue
        d_ret = r["total_return"] - base["total_return"]
        d_dd = r["max_drawdown"] - base["max_drawdown"]
        d_sr = r["sharpe"] - base["sharpe"]
        print(f"  {r['label']:<25} ΔRet={d_ret:+.1f}%  ΔDD={d_dd:+.1f}%  ΔSharpe={d_sr:+.2f}")

    # 保存
    reader.close()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out = os.path.join(OUTPUT_DIR, f"chip_backtest_compare_{tag}.csv")
    pd.DataFrame(results).to_csv(out, index=False)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
