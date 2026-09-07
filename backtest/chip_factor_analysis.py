#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
chip_factor_analysis.py — chip 因子稳健性分析

1. 多轮回测：N 轮随机抽样，每轮对比 chip 规则，输出均值 ± 标准差
2. 滚动 IC：多时间点截面，输出 IC 时间序列和汇总统计

用法：
    python backtest/chip_factor_analysis.py --sample 500 --rounds 10

输出：
    backtest_output/chip_multiround_{tag}.csv   — 多轮回测汇总
    backtest_output/chip_rolling_ic_{tag}.csv   — 滚动 IC 时间序列
"""

import argparse
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

import backtrader as bt

from backtest.chip_algorithm import (
    adapt_columns, bb_position, daily_chip_distribution, turnover_chip_factors,
    derived_chip_factors, _estimate_turnover, cyq,
)
from backtest.chip_indicator import ChipDistribution
from backtest.stock_data_reader import StockDataReader

_reader = None

def _get_reader():
    global _reader
    if _reader is None:
        _reader = StockDataReader()
    return _reader
FLOAT_SHARES_PATH = os.path.join(REPO, "stock_data", "float_shares.parquet")
OUTPUT_DIR = os.path.join(REPO, "backtest_output")

# A股交易日历
import pandas_market_calendars as mcal  # noqa: E402
_SSE_CALENDAR = mcal.get_calendar("SSE")
_TRADING_SESSIONS = None  # 延迟初始化


def _trading_days(start: str, end: str):
    """获取 start~end 之间的 A 股交易日列表。"""
    global _TRADING_SESSIONS
    if _TRADING_SESSIONS is None:
        _TRADING_SESSIONS = _SSE_CALENDAR.schedule(
            start_date="2024-01-01", end_date="2026-12-31"
        ).index
    return _TRADING_SESSIONS[
        (_TRADING_SESSIONS >= pd.Timestamp(start))
        & (_TRADING_SESSIONS <= pd.Timestamp(end))
    ]

WINDOW_DAYS = 80
BACKTEST_START = "2026-03-01"  # 回测起点（chip 因子从 2025-01 起预热 80 天）
INITIAL_CASH = 1_000_000.0
COMMISSION = 0.0005


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------
def load_data(reader, code: str, bars: int = 120, from_date: str = None) -> pd.DataFrame:
    """加载日线数据。from_date 不为 None 时，从该日期起截取（含预热窗口）。"""
    df = reader.read_stock(code, period='1d', adjust_type='front')
    if df is None:
        return None
    df = df.rename(columns={"time": "datetime"})
    df["datetime"] = pd.to_datetime(df["datetime"], unit="ms")
    df.set_index("datetime", inplace=True)
    # 过滤到交易日（排除周末和节假日）
    trading = _trading_days("2024-01-01", "2026-12-31")
    df = df[df.index.normalize().isin(trading.normalize())]

    if from_date is not None:
        start_ts = pd.Timestamp(from_date)
        pre_start = df[df.index < start_ts]
        post_start = df[df.index >= start_ts]
        warmup = pre_start.tail(WINDOW_DAYS) if len(pre_start) >= WINDOW_DAYS else pre_start
        df = pd.concat([warmup, post_start])
    if bars and len(df) > bars:
        df = df.tail(bars)
    return df


# ---------------------------------------------------------------------------
# 回测
# ---------------------------------------------------------------------------
class ChipSellStrategy(bt.Strategy):
    """
    chip 因子选股 + 固定止盈/持仓期卖出 + 循环再买入。

    买入：chip 因子预热完成后等权全仓，卖出后现金重新分配到可用标的
    卖出：
    1. 盈利 ≥ 5% 止盈
    2. 持有 5 天强制卖出
    3. 无止損
    再买入：卖出次日，现金等权分配到未持仓标的
    """

    params = (
        ("take_profit", 0.05),   # 止盈 5%
        ("max_hold", 5),         # 最大持有天数
        ("t1_buy", False),       # T+1 open 买入
    )

    def __init__(self):
        self._entry_price = {}
        self._hold_days = {}
        self._prev_cyqk = {}   # data → 上一日 cyqk_c
        self.trades = []

        self._chips = {}
        for d in self.datas:
            if d._name == BENCHMARK_CODE:
                continue
            self._entry_price[d] = None
            self._hold_days[d] = 0
            self._prev_cyqk[d] = None
            code = d._name or ""
            self._chips[d] = ChipDistribution(
                d, period=WINDOW_DAYS, data_freq="1d",
                dist_method="triang", stock_code=code,
            )

    def _available_stocks(self):
        """当前可买入的标的（排除基准）。"""
        return [d for d in self.datas
                if d._name != BENCHMARK_CODE
                and len(d) >= WINDOW_DAYS
                and self.getposition(d).size == 0]

    def _log_trade(self, action, d, price, size, reason=""):
        """打印并记录交易。"""
        code = d._name or "?"
        dt = d.datetime.date(0)
        self.trades.append({
            "date": dt, "action": action, "code": code,
            "price": round(price, 2), "size": size, "reason": str(reason),
        })

    def _is_limit_up(self, d) -> bool:
        """检查当前 bar 是否为涨停（10% 主板 / 20% 创业板/科创板）。"""
        if len(d) < 2:
            return False
        prev_close = d.close[-1]
        if prev_close <= 0:
            return False
        current = d.close[0]
        change = (current - prev_close) / prev_close
        code = d._name or ""
        limit = 0.20 if code.startswith(("300", "301", "688")) else 0.098
        return change >= limit

    def _distribute_cash(self):
        """将可用现金等权分配到可买入标的（T+1 open 买入，涨停跳过）。"""
        available = self._available_stocks()
        if not available:
            return
        cash = self.broker.getcash()
        if cash < 10000:
            return
        # 排除涨停标的
        buyable = [d for d in available if not self._is_limit_up(d)]
        if not buyable:
            return
        cash_per = cash / len(buyable)
        for d in buyable:
            if len(d) < 1:
                continue
            price = d.close[0]  # 当前收盘价，用作参考
            if price <= 0:
                continue
            size = int(cash_per / price / 100) * 100
            if size >= 100:
                # 计算当前阻力值
                resist_str = ""
                try:
                    cyqk_now = float(self._chips[d].cyqk_c[0])
                    cyqk_prev = self._prev_cyqk.get(d)
                    if cyqk_prev is not None and not np.isnan(cyqk_now) and not np.isnan(cyqk_prev):
                        diff = cyqk_now - cyqk_prev
                        try:
                            tr_val = float(d.volume[0])
                            tr_est = float(_estimate_turnover(np.array([tr_val]))[0])
                            if tr_est > 0:
                                resist = diff / tr_est
                                resist_str = f"|resist|={abs(resist):.1f}"
                        except Exception:
                            pass
                    self._prev_cyqk[d] = cyqk_now
                except Exception:
                    pass

                # T+1 open 或当前 close
                if self.p.t1_buy:
                    self.buy(data=d, size=size, exectype=bt.Order.Close)
                    self._log_trade("BUY", d, price, size, resist_str)  # Close order
                else:
                    self.buy(data=d, size=size)
                    self._log_trade("BUY", d, price, size, f"NextOpen {resist_str}")  # T+1 open
                self._entry_price[d] = price
                self._hold_days[d] = 0

    def next(self):
        # 检查卖出（跳过基准）
        for d in self.datas:
            if d._name == BENCHMARK_CODE:
                continue
            pos = self.getposition(d)
            if pos.size == 0:
                continue
            self._hold_days[d] = self._hold_days.get(d, 0) + 1
            current = d.close[0]
            entry = self._entry_price.get(d)

            sell = False
            if entry is not None and entry > 0 and (current - entry) / entry >= self.p.take_profit:
                sell = True
            elif self._hold_days[d] >= self.p.max_hold:
                sell = True

            if sell:
                self.sell(data=d, size=pos.size)
                self._log_trade("SELL", d, current, pos.size,
                                f"hold={self._hold_days[d]}d, "
                                f"pnl={((current-entry)/entry*100):+.1f}%" if entry else "")
                self._entry_price[d] = None
                self._hold_days[d] = 0

        # 检查再买入：卖出后现金回来了，分配
        self._distribute_cash()


BENCHMARK_CODE = "000300.SH"
BB_PERIOD = 20  # 布林带窗口
BB_STD = 2.0    # 布林带标准差倍数


def run_backtest(reader, codes: list, bars: int = 60, t1_buy: bool = False) -> dict:
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.setcash(INITIAL_CASH)
    cerebro.broker.setcommission(commission=COMMISSION)

    # 股票池（含预热 bar，ChipDistribution 需要 80 根 bar warmup）
    added = 0
    for code in codes:
        df = load_data(reader, code, bars=None, from_date=BACKTEST_START)
        if df is not None:
            start_ts = pd.Timestamp(BACKTEST_START)
            # 包含预热 bar，Cerebro 中 Indicator 可以 warmup
            warmup = df[df.index < start_ts].tail(WINDOW_DAYS)
            post = df[df.index >= start_ts]
            df_bt = pd.concat([warmup, post])
            if len(post) >= 5:
                cerebro.adddata(bt.feeds.PandasData(dataname=df_bt, name=code))
                added += 1

    # 沪深 300 基准
    bench_df = load_data(reader, BENCHMARK_CODE, bars=None, from_date=BACKTEST_START)
    bench_added = False
    bench_ret = 0.0
    if bench_df is not None:
        start_ts = pd.Timestamp(BACKTEST_START)
        post = bench_df[bench_df.index >= start_ts]
        if len(post) >= 5:
            warmup = bench_df[bench_df.index < start_ts].tail(WINDOW_DAYS)
            bench_bt = pd.concat([warmup, post])
            cerebro.adddata(bt.feeds.PandasData(dataname=bench_bt, name=BENCHMARK_CODE))
            bench_added = True
            bench_start = float(post["close"].iloc[0])
            bench_end = float(post["close"].iloc[-1])
            bench_ret = round((bench_end / bench_start - 1) * 100, 2)

    if added == 0:
        return {"n_stocks": 0, "total_return": 0, "max_drawdown": 0, "sharpe": 0,
                "bench_return": 0}

    cerebro.addstrategy(ChipSellStrategy, t1_buy=t1_buy)
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe",
                        timeframe=bt.TimeFrame.Days, annualize=True)
    results = cerebro.run()
    strat = results[0]
    ret = strat.analyzers.returns.get_analysis()
    dd = strat.analyzers.drawdown.get_analysis()
    sr = strat.analyzers.sharpe.get_analysis()

    # 保存交易记录
    trades_df = pd.DataFrame(strat.trades) if strat.trades else pd.DataFrame()

    return {
        "n_stocks": added,
        "total_return": round((ret.get("rtot", 0) or 0) * 100, 2),
        "max_drawdown": round(dd.get("max", {}).get("drawdown", 0) or 0, 2),
        "sharpe": round(sr.get("sharperatio", 0) or 0, 2),
        "bench_return": bench_ret,
        "trades": trades_df,
    }


# ---------------------------------------------------------------------------
# chip 选股规则
# ---------------------------------------------------------------------------
RULES = {
    "all":         {"label": "基准（无过滤）",        "filter": lambda df: df},
    "resist_bb":   {"label": "|阻力|>20 & BB中轨↑",  "filter": lambda df: df[(df["turnover_resistance"].abs() > 20) & (df["bb_position"] >= 0.5)]},
    "resist_bb10": {"label": "|阻力|>10 & BB中轨↑",  "filter": lambda df: df[(df["turnover_resistance"].abs() > 10) & (df["bb_position"] >= 0.5)]},
}


# ---------------------------------------------------------------------------
# Part 1: 多轮回测
# ---------------------------------------------------------------------------
def multiround_backtest(reader, codes: list, top_n: int, rounds: int, bars: int, t1_buy: bool = False) -> pd.DataFrame:
    """N 轮随机抽样回测，返回每轮每规则的结果。"""
    print(f"\n=== Multi-Round Backtest ({rounds} rounds, top {top_n}, {bars} bars) ===")
    all_results = []

    for rnd in range(rounds):
        rng = np.random.default_rng(rnd * 100 + 42)
        # 对传入的 codes 全量计算截面因子（不做二次抽样）
        # --sample 200 在 main() 入口一次性抽样后传入
        pool = sorted(codes)
        # 对每只计算 chip 因子
        pool_factors = []
        for code in pool:
            # 加载数据：从 BACKTEST_START 之前 80 天到最新
            df = load_data(reader, code, bars=None, from_date=BACKTEST_START)
            if df is None:
                continue
            start_ts = pd.Timestamp(BACKTEST_START)
            post = df[df.index >= start_ts]
            pre = df[df.index < start_ts]
            if len(pre) < WINDOW_DAYS or len(post) < 2:
                continue
            try:
                # 今日因子：回测起点后第一根 bar（使用 pre + post[0] 作为窗口）
                today_end = post.index[0]
                today_win = df[df.index <= today_end].tail(WINDOW_DAYS)
                as_of_t = pd.Timestamp(today_end).normalize()
                arr_t = adapt_columns(today_win, stock_code=code, as_of_date=as_of_t)
                dist_t = daily_chip_distribution(arr_t, method="triang")
                ct_t = float(arr_t[-1, 0])
                cf_t = cyq.ChipFactor(ct_t, dist_t)

                # 昨日因子：回测起点前最后 WINDOW_DAYS 根（pre 末尾）
                yest_win = pre.tail(WINDOW_DAYS)
                as_of_y = pd.Timestamp(yest_win.index[-1]).normalize()
                arr_y = adapt_columns(yest_win, stock_code=code, as_of_date=as_of_y)
                dist_y = daily_chip_distribution(arr_y, method="triang")
                ct_y = float(arr_y[-1, 0])
                cf_y = cyq.ChipFactor(ct_y, dist_y)

                derived = derived_chip_factors(
                    cf_t.get_cyqk_c(), cf_y.get_cyqk_c(), float(arr_t[-1, 4]))
                pool_factors.append({
                    "stock_code": code,
                    "cyqk_c": cf_t.get_cyqk_c(),
                    "asr": cf_t.get_asr(), "ckdw": cf_t.get_ckdw(), "prp": cf_t.get_prp(),
                    "profit_chip_diff": derived["profit_chip_diff"],
                    "turnover_ratio": derived["turnover_ratio"],
                    "turnover_resistance": derived["turnover_resistance"],
                    # 布林带位置：close 在布林带中的相对位置（0=下轨, 0.5=中轨, 1=上轨）
                    "bb_position": bb_position(today_win["close"].values),
                })
            except Exception:
                continue

        pool_df = pd.DataFrame(pool_factors)

        for rule_name, rule_info in RULES.items():
            filtered = rule_info["filter"](pool_df)
            fc = filtered["stock_code"].tolist()
            if len(fc) > top_n:
                fc = sorted(rng.choice(fc, size=top_n, replace=False))
            r = run_backtest(reader, fc, bars=bars, t1_buy=t1_buy)
            r["round"] = rnd + 1
            r["rule"] = rule_info["label"]
            all_results.append(r)
        print(f"  Round {rnd+1}/{rounds} done")

    # 收集交易记录
    all_trades = []
    for ar in all_results:
        tdf = ar.pop("trades", None)
        if tdf is not None and isinstance(tdf, pd.DataFrame) and not tdf.empty:
            tdf = tdf.copy()
            tdf["round"] = ar["round"]
            tdf["rule"] = ar["rule"]
            all_trades.append(tdf)
    trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()

    return pd.DataFrame(all_results), trades_df


# ---------------------------------------------------------------------------
# Part 2: 滚动 IC
# ---------------------------------------------------------------------------
def rolling_ic(reader, codes: list, lookback: int = 365, step_days: int = 20) -> pd.DataFrame:
    """多时间点截面 IC。每 step_days 个交易日取一次截面，计算 IC。"""
    print(f"\n=== Rolling IC (lookback={lookback}d, step={step_days}d) ===")
    # 找一个有足够长数据的标的来确定日期锚点
    anchor = None
    for code in codes:
        df = load_data(reader, code, bars=lookback + 20)
        if df is not None and len(df) >= lookback:
            anchor = df
            break
    if anchor is None:
        print("  No anchor data found")
        return pd.DataFrame()

    all_dates = anchor.index
    # 从 lookback 天前开始，每隔 step_days 取一个截面
    ic_rows = []
    for t in range(lookback, len(all_dates), step_days):
        target_date = all_dates[t]
        ic_row = {"date": target_date.date(), "n_stocks": 0}

        # 对每只标的取窗口 [t-lookback, t]
        factors = {"cyqk_c": [], "asr": [], "ckdw": [], "prp": [], "arc": [], "vrc": [], "src": [], "krc": [], "fwd": []}
        for code in codes:
            df = load_data(reader, code, bars=t + 25)
            if df is None or len(df) < t + 5:
                continue
            try:
                win = df.iloc[t - WINDOW_DAYS : t]
                arr = adapt_columns(win, stock_code=code)
                dist = daily_chip_distribution(arr, method="triang")
                ct = float(arr[-1, 0])
                cf = cyq.ChipFactor(ct, dist)
                tr_arr = arr[:, 4]
                cl_arr = arr[:, 0]
                tcf = turnover_chip_factors(tr_arr, cl_arr, window=min(60, len(tr_arr)))
                # 20-day forward return
                idx_t = df.index.get_indexer([target_date], method="ffill")[0]
                if idx_t + 20 < len(df):
                    fwd20 = (float(df.iloc[idx_t + 20]["close"]) - ct) / ct
                else:
                    fwd20 = np.nan
                if np.isnan(fwd20):
                    continue
                factors["cyqk_c"].append(cf.get_cyqk_c())
                factors["asr"].append(cf.get_asr())
                factors["ckdw"].append(cf.get_ckdw())
                factors["prp"].append(cf.get_prp())
                factors["arc"].append(tcf["arc"])
                factors["vrc"].append(tcf["vrc"])
                factors["src"].append(tcf["src"])
                factors["krc"].append(tcf["krc"])
                factors["fwd"].append(fwd20)
            except Exception:
                continue

        for fname in ["cyqk_c", "asr", "ckdw", "prp", "arc", "vrc", "src", "krc"]:
            if len(factors[fname]) >= 30:
                ic, p = spearmanr(factors[fname], factors["fwd"])
                ic_row[f"ic_{fname}"] = round(ic, 4)
                ic_row[f"p_{fname}"] = round(p, 4)
            else:
                ic_row[f"ic_{fname}"] = np.nan
                ic_row[f"p_{fname}"] = np.nan
        ic_row["n_stocks"] = len(factors["fwd"])
        ic_rows.append(ic_row)

    return pd.DataFrame(ic_rows)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="chip 因子稳健性分析")
    parser.add_argument("--sample", type=int, default=200, help="抽样数量")
    parser.add_argument("--rounds", type=int, default=10, help="多轮回测轮数")
    parser.add_argument("--top", type=int, default=50, help="每轮选股数量")
    parser.add_argument("--bars", type=int, default=60, help="回测 bar 数")
    parser.add_argument("--skip-backtest", action="store_true", help="跳过多轮回测")
    parser.add_argument("--skip-ic", action="store_true", help="跳过滚动 IC")
    parser.add_argument("--t1", action="store_true", help="T+1 open 买入（默认当前 close）")
    args = parser.parse_args()
    t1_buy = args.t1

    reader = StockDataReader()

    # 加载全市场标的
    fs_df = pd.read_parquet(FLOAT_SHARES_PATH)
    codes = fs_df["stock_code"].tolist()
    if args.sample < len(codes):
        rng = np.random.default_rng(42)
        sample = sorted(rng.choice(codes, size=args.sample, replace=False))
    else:
        sample = sorted(codes)
    print(f"Sample: {len(sample)} stocks from {len(codes)} total")
    tag = datetime.now().strftime("%Y%m%d_%H%M")

    # Part 1: 多轮回测
    if not args.skip_backtest:
        df_mr, trades_df = multiround_backtest(reader, sample, args.top, args.rounds, args.bars, t1_buy=t1_buy)

        # 汇总
        print(f"\n  {'Rule':<25} {'Return':>12} {'MaxDD':>10} {'Sharpe':>8} {'vs CSI300':>10}")
        print(f"  {'-'*25} {'-'*12} {'-'*10} {'-'*8} {'-'*10}")
        bench_ret_mean = df_mr["bench_return"].mean()
        for rule_label in df_mr["rule"].unique():
            sub = df_mr[df_mr["rule"] == rule_label]
            r_mean = sub["total_return"].mean()
            r_std = sub["total_return"].std()
            dd_mean = sub["max_drawdown"].mean()
            sr_mean = sub["sharpe"].mean()
            vs_bench = r_mean - bench_ret_mean
            print(f"  {rule_label:<25} {r_mean:+6.1f}%±{r_std:.1f}%  "
                  f"{dd_mean:5.1f}%    {sr_mean:5.2f}  {vs_bench:+8.1f}%")

        # vs 基准 and vs CSI300
        base = df_mr[df_mr["rule"] == "基准（无过滤）"]
        base_ret_mean = base["total_return"].mean()
        print(f"\n  CSI 300 同期收益: {bench_ret_mean:+.1f}%")
        print(f"  vs 随机基准 (return={base_ret_mean:+.1f}%):")
        for rule_label in df_mr["rule"].unique():
            if rule_label == "基准（无过滤）":
                continue
            sub = df_mr[df_mr["rule"] == rule_label]
            d_ret = sub["total_return"].mean() - base_ret_mean
            d_bench = sub["total_return"].mean() - bench_ret_mean
            star = " ★" if d_bench > 0 else ""
            print(f"  {rule_label:<25} ΔRet={d_ret:+.1f}%  ΔCSI300={d_bench:+.1f}%{star}")

        mr_path = os.path.join(OUTPUT_DIR, f"chip_multiround_{tag}.csv")
        df_mr.to_csv(mr_path, index=False)
        print(f"\nSaved: {mr_path}")

        # 保存交易记录
        if not trades_df.empty:
            trades_path = os.path.join(OUTPUT_DIR, f"chip_trades_{tag}.csv")
            trades_df.to_csv(trades_path, index=False)
            print(f"Saved trades: {trades_path}")

    # Part 2: 滚动 IC
    if not args.skip_ic:
        df_ic = rolling_ic(reader, sample)
        if not df_ic.empty:
            # 汇总
            print(f"\n  Rolling IC summary ({len(df_ic)} cross-sections, "
                  f"median n={df_ic['n_stocks'].median():.0f} stocks):")
            print(f"  {'Factor':<8} {'IC Mean':>10} {'IC Std':>8} {'ICIR':>8} {'>0%':>6}")
            print(f"  {'-'*8} {'-'*10} {'-'*8} {'-'*8} {'-'*6}")
            for fname in ["cyqk_c", "asr", "ckdw", "prp", "arc", "vrc", "src", "krc"]:
                col = f"ic_{fname}"
                if col in df_ic.columns and df_ic[col].notna().sum() > 1:
                    vals = df_ic[col].dropna()
                    ic_mean = vals.mean()
                    ic_std = vals.std()
                    icir = ic_mean / ic_std if ic_std > 0 else 0
                    pos_pct = (vals > 0).mean() * 100
                    star = " *" if abs(icir) > 0.5 else ""
                    print(f"  {fname:<8} {ic_mean:+10.4f} {ic_std:8.4f} {icir:+8.2f}{star} {pos_pct:5.0f}%")

            ic_path = os.path.join(OUTPUT_DIR, f"chip_rolling_ic_{tag}.csv")
            df_ic.to_csv(ic_path, index=False)
            print(f"\nSaved: {ic_path}")

    reader.close()


if __name__ == "__main__":
    main()
