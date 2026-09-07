#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
构建日线复权因子表。

由于 QMT 返回的 front 复权数据不可靠（与 none 相同），本脚本改为从 back/none
推导前复权因子：
    adj_factor_back[t] = close_back[t] / close_none[t]
    cumulative_adj_factor[t] = adj_factor_back[t] / adj_factor_back[latest]

其中 latest 为该股票在本地数据中的最新交易日，cumulative_adj_factor[latest] = 1.0。

用法：
    python backtest/build_adj_factor_table.py
    python backtest/build_adj_factor_table.py --stocks 500

输出：
    stock_data/adj_factor.parquet
        columns: date, stock_code, close_front, close_none,
                 cumulative_adj_factor, adj_factor_back
        sorted by stock_code, date

用途：
    分钟线未复权价格 × cumulative_adj_factor = 等效前复权分钟价格
    用于 §10.4.2 方案 B 的分钟级复权校正。

注意：
    日常增量更新推荐使用 scripts/update_adjusted_daily.py；
    本脚本更适合一次性全量重建或首次初始化。
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

from common.infra.quant_logger import get_logger

logger = get_logger(__name__)

BACK_DIR = os.path.join(REPO, "stock_data", "period=1d", "dividend_type=back")
NONE_DIR = os.path.join(REPO, "stock_data", "period=1d", "dividend_type=none")


def _common_symbols(limit=None) -> list:  # type: ignore[reportArgumentType]
    """获取同时有 back 和 none 数据的标的。"""
    back_syms = set(d.replace("symbol=", "") for d in os.listdir(BACK_DIR)
                    if d.startswith("symbol="))
    none_syms = set(d.replace("symbol=", "") for d in os.listdir(NONE_DIR)
                    if d.startswith("symbol="))
    common = sorted(back_syms & none_syms)
    if limit:
        common = common[:limit]
    return common


def build_for_symbol(sym: str) -> pd.DataFrame:
    """为单只标的构建复权因子序列。"""
    back_path = os.path.join(BACK_DIR, f"symbol={sym}", "data.parquet")
    none_path = os.path.join(NONE_DIR, f"symbol={sym}", "data.parquet")

    df_b = pd.read_parquet(back_path)
    df_n = pd.read_parquet(none_path)

    # 若 parquet 已带 DatetimeIndex，先 reset 避免与 date 列冲突
    if isinstance(df_b.index, pd.DatetimeIndex):
        df_b = df_b.reset_index()
    if isinstance(df_n.index, pd.DatetimeIndex):
        df_n = df_n.reset_index()

    # 对齐日期
    df_b["date"] = pd.to_datetime(df_b["time"], unit="ms").dt.normalize()
    df_n["date"] = pd.to_datetime(df_n["time"], unit="ms").dt.normalize()

    # outer join 防止静默丢弃只在单侧存在的日期
    merged = df_b[["date", "close"]].merge(
        df_n[["date", "close"]],
        on="date", suffixes=("_back", "_none"), how="outer"
    ).sort_values("date").reset_index(drop=True)

    # 前向填充单侧缺失
    merged["close_back"] = merged["close_back"].ffill()
    merged["close_none"] = merged["close_none"].ffill()

    # Phase 2 P2: validate symbol format
    code = sym.replace("_SZ", ".SZ").replace("_SH", ".SH").replace("_BJ", ".BJ")
    if "." not in code or len(code.split(".")[0]) != 6:
        logger.warning("adj_factor: unrecognized symbol format, skipping: %s", sym)
        return pd.DataFrame(columns=[
            "date", "stock_code", "close_front", "close_none",
            "cumulative_adj_factor", "adj_factor_back",
        ])

    # 单侧缺失标记为 NaN
    _one_sided_na = (
        merged["close_back"].isna() | merged["close_none"].isna()
    )
    merged["adj_factor_back"] = np.where(
        _one_sided_na,
        np.nan,
        np.where(
            merged["close_none"] > 0,
            merged["close_back"] / merged["close_none"],
            np.nan,
        ),
    )

    # 前复权因子：以最新日期为基准 1
    latest_back_factor = merged["adj_factor_back"].iloc[-1]
    merged["cumulative_adj_factor"] = np.where(
        pd.isna(merged["adj_factor_back"]) | (latest_back_factor == 0),
        np.nan,
        merged["adj_factor_back"] / latest_back_factor,
    )

    # 推导 front close（与 update_adjusted_daily.py 一致）
    merged["close_front"] = np.where(
        pd.isna(merged["cumulative_adj_factor"]),
        np.nan,
        merged["close_none"] * merged["cumulative_adj_factor"],
    )

    merged["stock_code"] = code

    return merged[[
        "date", "stock_code", "close_front", "close_none",
        "cumulative_adj_factor", "adj_factor_back",
    ]]


def main():
    parser = argparse.ArgumentParser(description="构建日线复权因子表")
    parser.add_argument("--stocks", type=int, default=0,
                        help="限制标的数（0=全部）")
    parser.add_argument("--output", default=os.path.join(REPO, "stock_data", "adj_factor.parquet"))
    args = parser.parse_args()

    syms = _common_symbols(limit=args.stocks if args.stocks > 0 else None)
    print(f"共有所属: {len(syms)}")

    frames = []
    gap_symbols = []
    for i, sym in enumerate(syms):
        if (i + 1) % 200 == 0:
            print(f"  ... {i + 1}/{len(syms)}")
        try:
            df = build_for_symbol(sym)
            if len(df) > 0:
                both_na = df[["close_front", "close_none"]].isna().all(axis=1)
                one_sided_na = df[["close_front", "close_none"]].isna().any(axis=1) & ~both_na
                unfillable = int(both_na.sum()) + int(one_sided_na.sum())
                if unfillable > 0:
                    gap_symbols.append((sym.replace("_SZ", ".SZ").replace("_SH", ".SH").replace("_BJ", ".BJ"), unfillable))
                frames.append(df)
        except Exception as e:
            print(f"  [WARN] {sym}: {e}")

    if not frames:
        print("No data")
        return

    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values(["stock_code", "date"]).reset_index(drop=True)

    if gap_symbols:
        total_gap_dates = sum(g for _, g in gap_symbols)
        print(f"\n[数据缺口] {len(gap_symbols)} 只标的存在不可前向填充的空行，共 {total_gap_dates} 天")
        if len(gap_symbols) <= 20:
            for code, days in gap_symbols:
                print(f"  {code}: {days} 天")
        else:
            for code, days in gap_symbols[:10]:
                print(f"  {code}: {days} 天")
            print(f"  ... 共 {len(gap_symbols)} 只")

    nan_factors = result[result["cumulative_adj_factor"].isna()]
    if len(nan_factors) > 0:
        nan_dates = sorted(nan_factors["date"].dt.strftime("%Y-%m-%d").unique())
        nan_stocks = nan_factors["stock_code"].nunique()
        print(f"\n[NaN 因子] {len(nan_factors)} 行 NaN 因子, 涉及 {nan_stocks} 只标的")
        if len(nan_dates) <= 10:
            print(f"  日期: {', '.join(nan_dates)}")
        else:
            print(f"  日期范围: {nan_dates[0]} ~ {nan_dates[-1]}")

    print(f"\n总行数: {len(result):,}")
    print(f"标的数: {result['stock_code'].nunique()}")
    print(f"日期范围: {result['date'].min().date()} ~ {result['date'].max().date()}")

    af = result["cumulative_adj_factor"]
    print(f"前复权因子: mean={af.mean():.4f}, std={af.std():.4f}, "
          f"min={af.min():.4f}, max={af.max():.4f}")

    bf = result["adj_factor_back"]
    print(f"后复权因子: mean={bf.mean():.4f}, std={bf.std():.4f}, "
          f"min={bf.min():.4f}, max={bf.max():.4f}")

    # 检测除权日（back 因子突变 >1% 的日期）
    result["factor_change"] = result.groupby("stock_code")["adj_factor_back"].pct_change(fill_method=None).abs()
    events = result[result["factor_change"] > 0.01]
    print(f"除权事件（back 因子变化>1%）: {len(events):,} 条, "
          f"覆盖 {events['stock_code'].nunique()} 只标的")

    result = result.drop(columns=["factor_change"])

    output = args.output
    os.makedirs(os.path.dirname(output), exist_ok=True)
    result.to_parquet(output, index=False)
    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()
