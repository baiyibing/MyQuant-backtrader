#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
chip_backtest.py — COST 筹码分布因子回测脚本

演示 ChipDistribution 在 backtrader 中的集成使用模式。不修改现有策略文件。

功能：
- 从 stock_pool CSV 读取股票池
- 加载日线 Parquet 数据，注册 ChipDistribution 指标
- 每 bar 记录 4 个 chip 因子值 → 输出 chip_factors.csv
- 可选：基于 chip 因子的简单择时逻辑

用法：
    python backtest/research/chip_backtest.py                          # 默认日期最近的 stock_pool，日线
    python backtest/research/chip_backtest.py --date 20260513          # 指定日期，日线
    python backtest/research/chip_backtest.py --freq 1m                # 分钟线
    python backtest/research/chip_backtest.py --freq 1m --stocks 000001.SZ,000002.SZ
    python backtest/research/chip_backtest.py --date 20260513 --top 20 # 限前 20 只

输出：
    backtest_output/chip_factors_YYYYMMDD.csv   — 每 bar 每只股票的 chip 因子
    backtest_output/chip_summary_YYYYMMDD.csv   — 最新 bar 截面摘要
"""

import argparse
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)

import backtrader as bt

from backtest.chip_indicator import ChipDistribution
from backtest.chip_algorithm import adapt_columns, daily_chip_distribution, minute_chip_distribution, cyq
from oskh_data import StockDataReader

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
STOCK_POOL_DIR = os.path.join(REPO, "stock_pool")
OUTPUT_DIR = os.path.join(REPO, "backtest_output")
WINDOW_DAYS = 80  # chip 因子回看窗口（交易日数）


# ---------------------------------------------------------------------------
# 策略
# ---------------------------------------------------------------------------
class ChipFactorStrategy(bt.Strategy):
    """
    最小 chip 因子记录策略。
    每 bar 记录 4 因子值，不做实际买卖——仅演示因子可用性。

    可选 --trade 参数启用 chip-based 择时：
    - CYQK_C > 0.8（80% 筹码获利）→ 卖出信号（获利盘抛压）
    - CYQK_C < 0.2（80% 筹码亏损）→ 买入信号（抄底机会）
    """

    params = (
        ("trade", False),
        ("data_freq", "1d"),
        ("window_days", WINDOW_DAYS),
    )

    def __init__(self):
        # 每个 data feed 创建独立的 ChipDistribution
        # 分钟线模式：加载的是 N 个交易日的分钟 bar，period 设为实际 bar 数
        self._chips = []
        for d in self.datas:
            code = d._name or ""
            period = len(d) if self.p.data_freq == "1m" else self.p.window_days
            chip = ChipDistribution(
                d, period=period, data_freq=self.p.data_freq,
                dist_method="triang", stock_code=code,
            )
            self._chips.append((d, chip, code))
        self.records = []  # (date, stock_code, cyqk_c, asr, ckdw, prp)
        self.factor_samples_checked = 0
        self.factor_samples_valid = 0

    def next(self):
        dt = self.data.datetime.date(0)
        for d, chip, code in self._chips:
            min_bars = self.p.window_days if self.p.data_freq == "1d" else self.p.window_days * 200
            if len(d) < min_bars:
                continue
            self.factor_samples_checked += 1
            cyqk = float(chip.cyqk_c[0])
            asr_v = float(chip.asr[0])
            ckdw_v = float(chip.ckdw[0])
            prp_v = float(chip.prp[0])
            if not all(np.isfinite(v) for v in (cyqk, asr_v, ckdw_v, prp_v)):
                continue
            self.factor_samples_valid += 1
            self.records.append((dt, code, cyqk, asr_v, ckdw_v, prp_v))


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------
_reader = None

def _get_reader():
    global _reader
    if _reader is None:
        _reader = StockDataReader()
    return _reader


def code_to_data(code: str, freq: str = "1d", reader=None) -> pd.DataFrame:
    """加载 parquet，转 backtrader 格式。"""
    if reader is None:
        reader = _get_reader()

    df = reader.read_stock(code, start_time='20000101', period=freq, adjust_type='none')
    if df is None:
        return None

    min_rows = WINDOW_DAYS if freq == "1d" else WINDOW_DAYS * 200
    if len(df) < min_rows:
        return None

    df["datetime"] = pd.to_datetime(df["time"], unit="ms")

    if freq == "1m":
        # 分钟线：截取最后 WINDOW_DAYS 个交易日
        last_date = df["datetime"].dt.date.max()
        first_date = last_date - pd.Timedelta(days=WINDOW_DAYS * 2)  # 留余量覆盖非交易日
        df = df[df["datetime"].dt.date >= first_date]
        # 精确到 WINDOW_DAYS 个交易日
        trading_dates = sorted(df["datetime"].dt.date.unique())
        if len(trading_dates) > WINDOW_DAYS:
            cutoff = trading_dates[-WINDOW_DAYS]
            df = df[df["datetime"].dt.date >= cutoff]

    df.set_index("datetime", inplace=True)
    return df


def load_stock_pool(date_str: str) -> list:
    """从 stock_pool CSV 读取标的列表。"""
    path = os.path.join(STOCK_POOL_DIR, f"{date_str}.csv")
    if not os.path.exists(path):
        return []
    codes = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            code = line.strip().split(",")[0].strip()
            if code.isdigit() and len(code) == 6:
                # 推断交易所
                if code.startswith(("60", "68")):
                    codes.append(f"{code}.SH")
                elif code.startswith(("00", "30")):
                    codes.append(f"{code}.SZ")
                else:
                    codes.append(f"{code}.SZ")
    return codes


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="COST chip factor backtest")
    parser.add_argument("--date", help="stock_pool 日期 YYYYMMDD，默认最新")
    parser.add_argument("--stocks", help="逗号分隔标的列表，如 000001.SZ,000002.SZ")
    parser.add_argument("--top", type=int, default=0, help="限制前 N 只")
    parser.add_argument("--freq", default="1d", choices=["1d", "1m"],
                        help="数据频率：1d（日线，默认）或 1m（分钟线）")
    parser.add_argument("--trade", action="store_true", help="启用 chip-based 择时（默认仅记录因子）")
    args = parser.parse_args()
    freq = args.freq

    # 确定标的列表
    if args.stocks:
        stock_list = [s.strip() for s in args.stocks.split(",") if s.strip()]
    else:
        # 找最新 stock_pool CSV
        if args.date:
            date_str = args.date
        else:
            csv_files = sorted(
                [f for f in os.listdir(STOCK_POOL_DIR) if f.endswith(".csv")],
                reverse=True,
            )
            date_str = csv_files[0].replace(".csv", "") if csv_files else datetime.now().strftime("%Y%m%d")
        stock_list = load_stock_pool(date_str)
        print(f"Stock pool: {date_str} → {len(stock_list)} stocks")

    if not stock_list:
        print("[FAIL] No stocks to backtest")
        sys.exit(1)

    if args.top:
        stock_list = stock_list[: args.top]

    # 过滤有缓存的标的
    reader = _get_reader()
    available = []
    for code in stock_list:
        df = code_to_data(code, freq=freq, reader=reader)
        if df is not None:
            available.append((code, df))
    min_label = f"{WINDOW_DAYS} days" if freq == "1d" else f"{WINDOW_DAYS}d × ~240min"
    print(f"Available (has {freq} parquet + >= {min_label}): {len(available)}/{len(stock_list)}")

    if not available:
        print("[FAIL] No stocks have sufficient data")
        sys.exit(1)

    if freq == "1m":
        # 分钟线模式：直接批量计算（绕开 Cerebro Indicator 的 warmup 问题）
        print(f"Computing minute chip factors for {len(available)} stocks ...")
        records = []
        for i, (code, df) in enumerate(available):
            try:
                arr = adapt_columns(df, stock_code=code)
                dist = minute_chip_distribution(arr)
                close_price = float(arr[-1, 0])
                cf = cyq.ChipFactor(close_price, dist)
                records.append({
                    "date": df.index[-1].date() if hasattr(df.index[-1], 'date') else str(df.index[-1])[:10],
                    "stock_code": code,
                    "cyqk_c": cf.get_cyqk_c(),
                    "asr": cf.get_asr(),
                    "ckdw": cf.get_ckdw(),
                    "prp": cf.get_prp(),
                })
            except Exception as e:
                print(f"  [WARN] {code}: {e}")
        df_records = pd.DataFrame(records)
    else:
        # 日线模式：Cerebro 回测
        cerebro = bt.Cerebro(stdstats=False)
        cerebro.broker.setcash(1_000_000.0)

        for code, df in available:
            data = bt.feeds.PandasData(dataname=df, name=code)
            cerebro.adddata(data)

        cerebro.addstrategy(ChipFactorStrategy, trade=args.trade, data_freq=freq)

        print(f"Running Cerebro with {len(available)} stocks ({freq}) ...")
        results = cerebro.run()
        strategy = results[0]
        checked = int(getattr(strategy, "factor_samples_checked", 0))
        valid = int(getattr(strategy, "factor_samples_valid", 0))

        if not strategy.records:
            print("[FAIL] No factor records produced")
            sys.exit(1)

        if checked > 0:
            valid_ratio = valid / checked
            print(
                f"Factor readiness (post-len-guard): "
                f"{valid}/{checked} = {valid_ratio:.2%}"
            )

        df_records = pd.DataFrame(
            strategy.records,
            columns=["date", "stock_code", "cyqk_c", "asr", "ckdw", "prp"],
        )

    if df_records.empty:
        print("[FAIL] No factor records produced")
        sys.exit(1)

    # 汇总输出
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tag = args.date or datetime.now().strftime("%Y%m%d")

    # 每只股票最新 bar 的因子截面
    df_latest = df_records.sort_values("date").groupby("stock_code").last().reset_index()
    df_latest = df_latest.sort_values("cyqk_c", ascending=False)

    print(f"\n{'Stock':<14} {'CYQK_C':>8} {'ASR':>8} {'CKDW':>8} {'PRP':>8}")
    print("-" * 50)
    for _, row in df_latest.iterrows():
        cyqk = row["cyqk_c"]
        flag = ""
        if cyqk > 0.8:
            flag = " ← 高位"
        elif cyqk < 0.2:
            flag = " ← 低位"
        print(f"{row['stock_code']:<14} {cyqk:8.4f} {row['asr']:8.4f} "
              f"{row['ckdw']:8.4f} {row['prp']:8.4f}{flag}")

    print(f"\nChip factor summary ({len(df_latest)} stocks):")
    for col in ["cyqk_c", "asr", "ckdw", "prp"]:
        vals = df_latest[col].dropna()
        print(f"  {col}: median={vals.median():.4f}, "
              f"mean={vals.mean():.4f}, std={vals.std():.4f}, "
              f"min={vals.min():.4f}, max={vals.max():.4f}")

    # 保存
    freq_suffix = f"_{freq}" if freq != "1d" else ""
    records_path = os.path.join(OUTPUT_DIR, f"chip_factors_{tag}{freq_suffix}.csv")
    summary_path = os.path.join(OUTPUT_DIR, f"chip_summary_{tag}{freq_suffix}.csv")
    df_records.to_csv(records_path, index=False)
    df_latest.to_csv(summary_path, index=False)
    print(f"\nSaved: {records_path}")
    print(f"Saved: {summary_path}")
    reader.close()
    print("Chip factor backtest complete.")


if __name__ == "__main__":
    main()
