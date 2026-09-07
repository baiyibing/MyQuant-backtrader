#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
构建日线复权因子表。

2026-07-09 起：front 以 QMT 下载落盘为 ground truth（见
``docs/engineering/plan-front-adj-factor-dr-based-2026-07-09.md``）。
本模块从已落盘的 front/none/back 计算因子，**禁止**再用 back/none 推导 front：

    cumulative_adj_factor[t] = close_front[t] / close_none[t]
    adj_factor_back[t]       = close_back[t]  / close_none[t]   # 观测列，可含噪声

用法：
    python scripts/data/build_adj_factor_table.py
    python scripts/data/build_adj_factor_table.py --stocks 500

输出：
    stock_data/adj_factor.parquet
        columns: date, stock_code, close_front, close_none,
                 cumulative_adj_factor, adj_factor_back
        sorted by stock_code, date

用途：
    分钟线未复权价格 × cumulative_adj_factor = 等效前复权分钟价格
    用于 §10.4.2 方案 B 的分钟级复权校正。

注意：
    日常增量更新推荐使用 scripts/data/run_daily_adjusted_fast.py；
    本脚本更适合一次性全量重建或首次初始化。
"""

import argparse
from typing import Any, cast
from oskh_data.pandas_typing import as_series
from .symbol_format import to_canonical_symbol
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

from common.infra.quant_logger import get_logger

logger = get_logger(__name__)

def _period_dirs() -> tuple:
    """周期分区单源（plan-data-path-ssot）：honors OSKH_PERIOD_1D_ROOT。"""
    from common.infra.data_root import resolve_period_root

    base = resolve_period_root("1d")
    return (
        str(base / "dividend_type=front"),
        str(base / "dividend_type=back"),
        str(base / "dividend_type=none"),
    )


FRONT_DIR, BACK_DIR, NONE_DIR = _period_dirs()


def _common_symbols(limit=None) -> list:  # type: ignore[reportArgumentType]
    """获取同时有 front 和 none 数据的标的（back 可选）。"""
    front_syms = set(
        d.replace("symbol=", "")
        for d in os.listdir(FRONT_DIR)
        if d.startswith("symbol=")
    ) if os.path.isdir(FRONT_DIR) else set()
    none_syms = set(
        d.replace("symbol=", "")
        for d in os.listdir(NONE_DIR)
        if d.startswith("symbol=")
    ) if os.path.isdir(NONE_DIR) else set()
    common = sorted(front_syms & none_syms)
    if limit:
        common = common[:limit]
    return common


def build_for_symbol(sym: str) -> pd.DataFrame:
    """为单只标的构建复权因子序列（读已下载 front/none/back）。"""
    front_path = os.path.join(FRONT_DIR, f"symbol={sym}", "data.parquet")
    none_path = os.path.join(NONE_DIR, f"symbol={sym}", "data.parquet")
    back_path = os.path.join(BACK_DIR, f"symbol={sym}", "data.parquet")

    if not os.path.isfile(front_path) or not os.path.isfile(none_path):
        return pd.DataFrame(columns=cast(Any, [
            "date", "stock_code", "close_front", "close_none",
            "cumulative_adj_factor", "adj_factor_back",
        ]))

    df_f = pd.read_parquet(front_path)
    df_n = pd.read_parquet(none_path)
    df_b = pd.read_parquet(back_path) if os.path.isfile(back_path) else None

    if isinstance(df_f.index, pd.DatetimeIndex):
        df_f = df_f.reset_index()
    if isinstance(df_n.index, pd.DatetimeIndex):
        df_n = df_n.reset_index()
    if df_b is not None and isinstance(df_b.index, pd.DatetimeIndex):
        df_b = df_b.reset_index()

    df_f["date"] = pd.to_datetime(df_f["time"], unit="ms").dt.normalize()
    df_n["date"] = pd.to_datetime(df_n["time"], unit="ms").dt.normalize()

    merged = df_f[["date", "close"]].merge(
        df_n[["date", "close"]],
        on="date", suffixes=("_front", "_none"), how="outer",
    ).sort_values("date").reset_index(drop=True)

    if df_b is not None and "close" in df_b.columns:
        df_b["date"] = pd.to_datetime(df_b["time"], unit="ms").dt.normalize()
        back_close = cast(pd.DataFrame, df_b[["date", "close"]]).copy()
        back_close.columns = pd.Index(["date", "close_back"])
        merged = merged.merge(
            back_close,
            on="date",
            how="left",
        )
    else:
        merged["close_back"] = np.nan

    merged["close_front"] = merged["close_front"].ffill()
    merged["close_none"] = merged["close_none"].ffill()
    merged["close_back"] = merged["close_back"].ffill()

    code = to_canonical_symbol(sym)
    if "." not in code or len(code.split(".")[0]) != 6:
        logger.warning("adj_factor: unrecognized symbol format, skipping: %s", sym)
        return pd.DataFrame(columns=cast(Any, [
            "date", "stock_code", "close_front", "close_none",
            "cumulative_adj_factor", "adj_factor_back",
        ]))

    _one_sided_na = merged["close_front"].isna() | merged["close_none"].isna()
    merged["cumulative_adj_factor"] = np.where(
        _one_sided_na,
        np.nan,
        np.where(
            merged["close_none"] > 0,
            merged["close_front"] / merged["close_none"],
            np.nan,
        ),
    )
    merged["adj_factor_back"] = np.where(
        merged["close_back"].isna() | merged["close_none"].isna(),
        np.nan,
        np.where(
            merged["close_none"] > 0,
            merged["close_back"] / merged["close_none"],
            np.nan,
        ),
    )

    merged["stock_code"] = code

    return pd.DataFrame(merged[[
        "date", "stock_code", "close_front", "close_none",
        "cumulative_adj_factor", "adj_factor_back",
    ]])


def main():
    parser = argparse.ArgumentParser(description="构建日线复权因子表")
    parser.add_argument("--stocks", type=int, default=0,
                        help="限制标的数（0=全部）")
    from common.infra.data_root import resolve_source_parquet

    parser.add_argument(
        "--output", default=str(resolve_source_parquet("adj_factor.parquet"))
    )
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
                both_na = as_series(df[["close_front", "close_none"]].isna().all(axis=1))
                one_sided_na = as_series(df[["close_front", "close_none"]].isna().any(axis=1) & ~both_na)
                unfillable = int(both_na.sum()) + int(one_sided_na.sum())
                if unfillable > 0:
                    gap_symbols.append((to_canonical_symbol(sym), unfillable))
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
        nan_dates = sorted(as_series(nan_factors["date"]).dt.strftime("%Y-%m-%d").unique())
        nan_stocks = int(as_series(nan_factors["stock_code"]).nunique())
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

    result["factor_change"] = result.groupby("stock_code")["adj_factor_back"].pct_change(fill_method=None).abs()
    events = result[result["factor_change"] > 0.01]
    print(f"除权事件（back 因子变化>1%）: {len(events):,} 条, "
          f"覆盖 {int(as_series(events['stock_code']).nunique())} 只标的")

    result = result.drop(columns=["factor_change"])

    output = args.output
    os.makedirs(os.path.dirname(output), exist_ok=True)
    result.to_parquet(output, index=False)
    from oskh_data.adj_factor_meta import write_adj_factor_meta

    write_adj_factor_meta(output, result, source="oskh_data.adj_factor.main")
    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()
