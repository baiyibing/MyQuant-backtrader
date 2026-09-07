#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
fetch_free_float_shares.py — 从 QMT 财务数据 Capital 表获取自由流通股本

自由流通股本 = circulating_capital - restrict_circulating_capital

数据源：xtdata.get_financial_data(table_list=['Capital'])
每个报告期一行，通过 m_timetag（报告截止日）定位历史时点。

用法：
    # 下载财务数据到本地（首次或增量）
    python -m oskh_data.free_float_shares --download --start 20200101 --end 20260530

    # 从本地缓存读取并导出 parquet
    python -m oskh_data.free_float_shares --export --output stock_data/free_float_shares.parquet

    # 全量更新（下载 + 导出，收盘后定期运行）
    python -m oskh_data.free_float_shares --update

输出：stock_data/free_float_shares.parquet
    columns: stock_code, m_timetag, freeFloatCapital, circulating_capital, restrict_circulating_capital, total_capital

与 float_shares.parquet 的关系：
    float_shares.parquet = FloatVolume（流通股本，QMT 实时接口，仅当前值）
    free_float_shares.parquet = 自由流通股本（财务数据，历史各期）
    两者互补：实时交易用 float_shares，回测用 free_float_shares

环境依赖：需要 QMT 客户端运行中（xtdata 连接到本地 xtquant 服务）。
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

from common.infra.timekeeping import shanghai_date_yyyymmdd
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

DEFAULT_OUTPUT = os.path.join(REPO, "stock_data", "free_float_shares.parquet")


def _ensure_xtdata():
    """确保 xtdata 可用并已连接（兼容国金 miniQMT 无 init/connect，使用 reconnect）。"""
    from xtquant import xtdata

    init_fn = getattr(xtdata, "init", None)
    if callable(init_fn):
        init_fn()
        return xtdata
    connect_fn = getattr(xtdata, "connect", None)
    if callable(connect_fn):
        connect_fn()
        return xtdata
    reconnect_fn = getattr(xtdata, "reconnect", None)
    if callable(reconnect_fn):
        reconnect_fn()
        return xtdata
    raise RuntimeError("xtdata 无 init/connect/reconnect 方法，请确认 xtquant 已安装")
    return xtdata


def download_capital_structure(
    stock_codes: List[str],
    start_time: str = "20200101",
    end_time: str = "",
    *,
    sleep_s: float = 0.0,
    batch_size: int = 50,
) -> None:
    """
    下载 Capital 财务数据到 QMT 本地缓存。

    参数：
        stock_codes: 股票代码列表
        start_time: 起始日期 YYYYMMDD
        end_time: 结束日期 YYYYMMDD（空=今天）
        sleep_s: 每批间隔秒数（避免 QMT 过载）
        batch_size: 每批下载股票数
    """
    xtdata = _ensure_xtdata()
    end_time = end_time or shanghai_date_yyyymmdd()
    total = len(stock_codes)

    for i in range(0, total, batch_size):
        batch = stock_codes[i : i + batch_size]
        try:
            xtdata.download_financial_data2(
                batch,
                table_list=["Capital"],
                start_time=start_time,
                end_time=end_time,
            )
        except Exception as exc:
            print(f"[WARN] download batch {i}-{i + len(batch)} failed: {exc}")

        if (i + batch_size) % 500 == 0:
            print(f"  ... {min(i + batch_size, total)}/{total}")
        if sleep_s > 0:
            time.sleep(sleep_s)


def fetch_capital_structure(
    stock_codes: List[str],
    start_time: str = "20200101",
    end_time: str = "",
) -> pd.DataFrame:
    """
    从 QMT 本地缓存读取 Capital 数据。

    返回 DataFrame，列：
        stock_code, m_timetag, circulating_capital, restrict_circulating_capital, total_capital
    """
    xtdata = _ensure_xtdata()
    end_time = end_time or shanghai_date_yyyymmdd()

    rows: List[Dict] = []
    for i, code in enumerate(stock_codes):
        try:
            data = xtdata.get_financial_data(
                [code],
                table_list=["Capital"],
                start_time=start_time,
                end_time=end_time,
                report_type="report_time",
            )
        except Exception as exc:
            if (i + 1) % 500 == 0:
                print(f"  ... {i + 1}/{len(stock_codes)} (last error: {exc})")
            continue

        if not data or code not in data:
            continue
        cap_data = data[code].get("Capital")
        if cap_data is None or (hasattr(cap_data, "empty") and cap_data.empty):
            continue

        for _, row in cap_data.iterrows():
            # Phase 2 P0 fix: `or 0` collapses None, NaN, and missing data into 0.0 —
            # indistinguishable from genuine zero free-float. Use explicit NaN detection
            # so downstream code can distinguish "data missing" from "truly zero".
            _raw_ff = row.get("freeFloatCapital")
            if _raw_ff is None or (isinstance(_raw_ff, float) and (_raw_ff != _raw_ff)):
                continue  # NaN or None → skip, don't fabricate 0.0
            free_float = float(_raw_ff or 0)
            if free_float <= 0:
                continue
            timetag = row.get("m_timetag")
            if timetag is None:
                continue
            date_val = pd.Timestamp(timetag).normalize()
            rows.append({
                "stock_code": code,
                "m_timetag": date_val,
                "freeFloatCapital": free_float,
                "circulating_capital": float(row.get("circulating_capital", 0) or 0),
                "restrict_circulating_capital": float(row.get("restrict_circulating_capital", 0) or 0),
                "total_capital": float(row.get("total_capital", 0) or 0),
            })

        if (i + 1) % 500 == 0:
            print(f"  ... {i + 1}/{len(stock_codes)} (rows={len(rows)})")

    if not rows:
        return pd.DataFrame(columns=[
            "stock_code", "m_timetag", "freeFloatCapital",
            "circulating_capital", "restrict_circulating_capital", "total_capital",
        ])
    df = pd.DataFrame(rows)
    df["m_timetag"] = pd.to_datetime(df["m_timetag"]).dt.normalize()
    df = df.sort_values(["stock_code", "m_timetag"]).reset_index(drop=True)
    return df


def merge_existing(existing_path: str, incoming: pd.DataFrame) -> pd.DataFrame:
    """与现有 parquet 合并，按 (stock_code, date) 去重（保留最新值）。"""
    if os.path.exists(existing_path):
        existing = pd.read_parquet(existing_path)
        existing["date"] = pd.to_datetime(existing["date"]).dt.normalize()
        merged = pd.concat([existing, incoming], ignore_index=True)
    else:
        merged = incoming.copy()
    merged = merged.drop_duplicates(subset=["stock_code", "m_timetag"], keep="last")
    merged = merged.sort_values(["stock_code", "m_timetag"]).reset_index(drop=True)
    return merged


def get_stock_list() -> List[str]:
    """获取全市场 A 股代码列表（从现有 float_shares 或 xtdata）。"""
    float_path = os.path.join(REPO, "stock_data", "float_shares.parquet")
    if os.path.exists(float_path):
        df = pd.read_parquet(float_path)
        return sorted(df["stock_code"].astype(str).tolist())

    xtdata = _ensure_xtdata()
    codes = []
    for sector in ["沪深A股", "创业板", "科创板"]:
        try:
            codes.extend(xtdata.get_stock_list_in_sector(sector))
        except Exception:
            pass
    return sorted(set(codes))


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch free-float shares from QMT Capital")
    parser.add_argument("--download", action="store_true", help="download Capital data to QMT cache")
    parser.add_argument("--export", action="store_true", help="read from cache and export parquet")
    parser.add_argument("--update", action="store_true", help="download + export (full update)")
    parser.add_argument("--start", default="20200101", help="start date YYYYMMDD")
    parser.add_argument("--end", default="", help="end date YYYYMMDD (default: today)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="output parquet path")
    parser.add_argument("--sleep-s", type=float, default=0.0, help="batch sleep seconds")
    parser.add_argument("--batch-size", type=int, default=50, help="download batch size")
    parser.add_argument("--codes", default="", help="comma-separated stock codes (default: all)")
    args = parser.parse_args()

    if not args.download and not args.export and not args.update:
        parser.print_help()
        return

    if args.codes:
        stock_codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        stock_codes = get_stock_list()

    if not stock_codes:
        print("[ERROR] no stock codes found")
        sys.exit(1)

    start_time = args.start
    end_time = args.end or shanghai_date_yyyymmdd()

    if args.download or args.update:
        print(f"Downloading Capital for {len(stock_codes)} stocks ({start_time}~{end_time})")
        download_capital_structure(
            stock_codes, start_time, end_time,
            sleep_s=args.sleep_s, batch_size=args.batch_size,
        )

    if args.export or args.update:
        print(f"Fetching Capital from cache ({start_time}~{end_time})")
        df = fetch_capital_structure(stock_codes, start_time, end_time)
        if df.empty:
            print("[ERROR] no data fetched")
            sys.exit(1)

        df = merge_existing(args.output, df)
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(str(out), index=False)

        date_range = f"{df['m_timetag'].min().date()} ~ {df['m_timetag'].max().date()}"
        print(f"rows={len(df)} stocks={df['stock_code'].nunique()} date_range={date_range}")
        print(f"saved: {args.output}")


if __name__ == "__main__":
    main()
