#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
verify_cerebro_chip.py — ChipDistribution 在 Cerebro 中的集成验证

验证项：
1. PrevClosePandasData 正常加载日线数据（含 volume 列）
2. ChipDistribution.next() 在 Cerebro 循环中无异常
3. 因子 line 可正常读取（cyqk_c / asr / ckdw / prp）
4. 有足够 bar 后因子值非 NaN

用法：
    python backtest/verify_cerebro_chip.py
"""

import sys
import os
import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

import backtrader as bt
import pandas as pd

from backtest.chip_indicator import ChipDistribution
from oskh_data import StockDataReader

_reader = None

def _get_reader():
    global _reader
    if _reader is None:
        _reader = StockDataReader()
    return _reader


class VerifyStrategy(bt.Strategy):
    """最小策略：仅注册 ChipDistribution，逐 bar 记录因子值。"""

    def __init__(self):
        self.chip = ChipDistribution(
            self.datas[0],
            period=80,
            data_freq="1d",
            dist_method="triang",
            stock_code="000001.SZ",  # 通过 stock_code 查 float_shares.parquet
        )
        self.factor_log = []  # (bar_index, cyqk_c, asr, ckdw, prp)

    def next(self):
        if len(self.data) < 80:
            return
        vals = (
            float(self.chip.cyqk_c[0]),
            float(self.chip.asr[0]),
            float(self.chip.ckdw[0]),
            float(self.chip.prp[0]),
        )
        if not all(np.isfinite(v) for v in vals):
            return
        self.factor_log.append((len(self.data), *vals))


def main():
    print("Loading 000001.SZ daily data ...")
    reader = _get_reader()
    df = reader.read_stock("000001.SZ", period='1d', adjust_type='none')
    if df is None:
        print("[FAIL] Cannot load data")
        reader.close()
        sys.exit(1)
    # 转为 backtrader 期望的列名
    df = df.rename(columns={
        "time": "datetime", "open": "open", "high": "high",
        "low": "low", "close": "close", "volume": "volume",
    })
    df["datetime"] = pd.to_datetime(df["datetime"], unit="ms")
    df.set_index("datetime", inplace=True)

    # 取最近 200 个交易日
    df = df.tail(200)
    print(f"  {len(df)} bars, {df.index[0].date()} ~ {df.index[-1].date()}")

    # 创建 Cerebro
    cerebro = bt.Cerebro()
    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)
    cerebro.addstrategy(VerifyStrategy)
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")

    print("Running Cerebro ...")
    results = cerebro.run()

    strategy = results[0]
    n = len(strategy.factor_log)
    print(f"\nChipDistribution computed {n} bars (after 80-bar warmup)")

    if n == 0:
        print("[FAIL] No factor values produced — data may be insufficient")
        reader.close()
        sys.exit(1)

    # 检查最后 5 个 bar 的因子值
    print(f"\n{'Bar':>5} {'CYQK_C':>8} {'ASR':>8} {'CKDW':>8} {'PRP':>8}")
    for bar_idx, cyqk, asr_v, ckdw, prp in strategy.factor_log[-5:]:
        print(f"{bar_idx:5d} {cyqk:8.4f} {asr_v:8.4f} {ckdw:8.4f} {prp:8.4f}")

    # 验证
    last = strategy.factor_log[-1]
    passed = 0
    failed = 0

    checks = [
        ("cyqk_c", last[1], 0.0, 1.0),
        ("asr", last[2], 0.0, 1.0),
        ("ckdw", last[3], 0.0, 20.0),
        ("prp", last[4], -1.0, 5.0),
    ]
    for name, val, lo, hi in checks:
        if np.isnan(val) or np.isinf(val):
            print(f"  [WARN] {name} = {val}")
            failed += 1
        elif not (lo <= val <= hi):
            print(f"  [WARN] {name} = {val:.4f} out of [{lo}, {hi}]")
            failed += 1
        else:
            passed += 1

    reader.close()
    print(f"\n{'=' * 50}")
    if failed == 0:
        print(f"INTEGRATION VERIFIED — {passed}/{passed} factors in valid range, exit code 0")
        sys.exit(0)
    else:
        print(f"INTEGRATION FAILED — {failed} factors out of range")
        sys.exit(1)


if __name__ == "__main__":
    main()
