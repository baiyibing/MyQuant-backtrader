#!/usr/bin/env python3
"""A股大单净量(bigvalue)CSV → parquet,附均线与金叉/死叉列。

- 输入两列 ``date, bigvalue``(全市场日频聚合,无代码列;列名可 ``--value-col`` 覆盖)。
- 每次全量重建:CSV 更新(含次日追加)后重跑本脚本即可,幂等。
- 均线 = 简单移动平均 ``rolling(window, min_periods=window).mean()``,窗口不满为 NaN
  (同 oskh_factors/chip/bands.py 口径;价格侧同类:topk with_ma5_gate / Alpha158 MA%d)。
- 金叉/死叉 = 快线相对慢线穿越:前一日 diff<=0 且当日 diff>0 记 +1;
  前一日 diff>=0 且当日 diff<0 记 -1;其余 0,暖区 NA。列名 ``cross_{f}_{s}``。
- 尾部占位剔除(默认开):从末尾向前连续剔除 value==0 的行——盘中/未收盘日源数据常写 0,
  会污染最近窗口的均线;``--keep-zeros`` 关闭。
- 重复日期、空输入直接报错退出(fail-closed)。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

DEFAULT_CSV = Path("E:/stock_data/bigdata.csv")


def load_bigvalue(csv_path: Path, value_col: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in ("date", value_col) if c not in df.columns]
    if missing:
        raise SystemExit(f"missing column(s) {missing} in {csv_path}: {list(df.columns)}")
    df["date"] = df["date"].astype("int64")
    df[value_col] = df[value_col].astype("float64")
    df = df.sort_values("date").reset_index(drop=True)
    if df.empty:
        raise SystemExit(f"empty csv: {csv_path}")
    if df["date"].duplicated().any():
        dup = df.loc[df["date"].duplicated(), "date"].head(3).tolist()
        raise SystemExit(f"duplicate dates in {csv_path}: {dup}")
    return df[["date", value_col]]


def drop_trailing_zeros(df: pd.DataFrame, value_col: str) -> tuple[pd.DataFrame, list[int]]:
    """从末尾向前剔除连续的 0 值占位行,返回 (新表, 被剔除的日期)。"""
    keep = len(df)
    while keep > 0 and df[value_col].iloc[keep - 1] == 0.0:
        keep -= 1
    dropped = df["date"].iloc[keep:].astype(int).tolist()
    return df.iloc[:keep].reset_index(drop=True), dropped


def add_ma(df: pd.DataFrame, value_col: str, windows: Sequence[int]) -> None:
    for w in windows:
        df[f"ma{w}"] = df[value_col].rolling(window=w, min_periods=w).mean()


def add_cross(df: pd.DataFrame, pairs: Sequence[tuple[int, int]]) -> None:
    for fast, slow in pairs:
        diff = df[f"ma{fast}"] - df[f"ma{slow}"]
        prev = diff.shift(1)
        golden = (prev <= 0) & (diff > 0)
        death = (prev >= 0) & (diff < 0)
        df[f"cross_{fast}_{slow}"] = (
            pd.Series(pd.NA, index=df.index, dtype="Int8").mask(golden, 1).mask(death, -1)
        )


def parse_pairs(spec: str | None, windows: Sequence[int]) -> list[tuple[int, int]]:
    if not spec:
        ws = sorted(windows)
        return [(ws[i], ws[j]) for i in range(len(ws)) for j in range(i + 1, len(ws))]
    pairs = []
    for token in spec.replace(",", " ").split():
        fast_s, _, slow_s = token.partition(":")
        fast, slow = int(fast_s), int(slow_s)
        if fast not in windows or slow not in windows:
            raise SystemExit(f"cross pair {token} must use ma windows {sorted(windows)}")
        pairs.append((fast, slow))
    return pairs


def main(argv: Sequence[str] | None = None) -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="源 CSV(date, bigvalue)")
    ap.add_argument("--out", type=Path, default=None,
                    help="输出 parquet;默认取 --csv 同名 .parquet")
    ap.add_argument("--value-col", default="bigvalue", help="数值列名(默认 bigvalue)")
    ap.add_argument("--ma-windows", type=int, nargs="+", default=[3, 5, 10],
                    help="均线窗口(默认 3 5 10)")
    ap.add_argument("--cross-pairs", default=None,
                    help='显式判叉对,如 "3:5 5:10";默认窗口两两全配')
    ap.add_argument("--keep-zeros", action="store_true",
                    help="保留尾部 0 值占位行(默认剔除)")
    args = ap.parse_args(argv)

    windows = sorted(set(args.ma_windows))
    if len(windows) < 2:
        raise SystemExit("--ma-windows needs at least two distinct windows for cross")
    pairs = parse_pairs(args.cross_pairs, windows)

    df = load_bigvalue(args.csv, args.value_col)
    dropped: list[int] = []
    if not args.keep_zeros:
        df, dropped = drop_trailing_zeros(df, args.value_col)
    add_ma(df, args.value_col, windows)
    add_cross(df, pairs)

    out = args.out or args.csv.with_suffix(".parquet")
    df.to_parquet(out, engine="pyarrow", compression="snappy", index=False)

    unit = 1e8
    print(f"rows {len(df)} | {df['date'].iloc[0]} -> {df['date'].iloc[-1]} | {out}")
    if dropped:
        print(f"dropped trailing-zero placeholder: {dropped}")
    for fast, slow in pairs:
        col = f"cross_{fast}_{slow}"
        s = df[col].fillna(0).astype(int)
        sig = df.loc[s != 0, ["date", col]]
        tags = ", ".join(
            f"{int(d)}{'金叉' if int(v) == 1 else '死叉'}"
            for d, v in sig.tail(5).itertuples(index=False, name=None)
        )
        n_days = max(len(df) // max((s != 0).sum(), 1), 1)
        print(f"MA{fast}xMA{slow}: 金叉{(s == 1).sum()} / 死叉{(s == -1).sum()}"
              f" (~{n_days}日/信号) | 最近: {tags or '无'}")
        d_last = df[f"ma{fast}"].iloc[-1] - df[f"ma{slow}"].iloc[-1]
        print(f"  截至{df['date'].iloc[-1]}: MA{fast}-MA{slow} = {d_last / unit:+.1f}亿"
              f" ({'金叉态' if d_last > 0 else '死叉态'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
