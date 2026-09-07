#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
update_adjusted_daily.py — 日线复权数据增量更新

核心策略：
- none（不复权）可以安全增量追加。
- front/back 的历史价格会因除权除息变化，不能直接增量。
- 每天用 "today_adj_factor = close_front / close_none" 检测是否发生除权。
- 无除权时只追加 1 天 front/back；除权时全量重下该股票的 front/back。

用法：
    python scripts/update_adjusted_daily.py
    python scripts/update_adjusted_daily.py --end 20260616 --threshold 0.005
    python scripts/update_adjusted_daily.py --dry-run  # 只检测不下载
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, cast

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

from common.infra.data_root import (
    resolve_e_stock_data_container,
    resolve_period_root,
    resolve_source_parquet,
)
from common.infra.quant_logger import get_logger
from oskh_data.downloader import DataDownloader, PeriodDataManager, StockDataManager

logger = get_logger(__name__)

DEFAULT_START = "19900101"
DEFAULT_BATCH = 100
DEFAULT_THRESHOLD = 0.005  # 0.5%
ADJ_FACTOR_PATH = "adj_factor.parquet"
PROGRESS_PATH = ".update_adjusted_daily_progress.json"


# xtquant 延迟导入
_xtdata = None
_QMT_AVAILABLE = None


def _get_xtdata():
    global _xtdata, _QMT_AVAILABLE
    if _xtdata is None and _QMT_AVAILABLE is None:
        try:
            from xtquant import xtdata as _xt
            _xtdata = _xt
            _QMT_AVAILABLE = True
        except ImportError:
            _QMT_AVAILABLE = False
            logger.warning("xtquant 未导入，无法从 QMT 获取股票列表")
    return _xtdata


def _qmt_available() -> bool:
    _get_xtdata()
    return bool(_QMT_AVAILABLE)


def _get_all_a_stock_codes() -> List[str]:
    """获取全市场 A 股代码列表。优先 QMT，备选本地 none 目录。"""
    if _qmt_available():
        xtdata = _get_xtdata()
        try:
            all_codes: set = set()
            sectors = ['沪深A股', '上海A股', '深圳A股', '北京A股', '科创板', '创业板', '北交所']
            for sector in sectors:
                try:
                    codes = xtdata.get_stock_list_in_sector(sector)
                    if codes:
                        valid = [c for c in codes if c.endswith(('.SH', '.SZ', '.BJ'))]
                        all_codes.update(valid)
                except Exception:
                    pass
            if len(all_codes) > 1000:
                logger.info(f"从 QMT 获取股票列表: {len(all_codes)} 只")
                return sorted(all_codes)
        except Exception as e:
            logger.warning(f"QMT 获取股票列表失败: {e}")

    # fallback: 本地 none 目录
    none_dir = str(resolve_period_root("1d") / "dividend_type=none")
    if os.path.exists(none_dir):
        codes = [
            d.replace("symbol=", "").replace("_", ".")
            for d in os.listdir(none_dir)
            if d.startswith("symbol=")
        ]
        logger.info(f"从本地 none 目录获取股票列表: {len(codes)} 只")
        return sorted(codes)

    raise RuntimeError("无法获取股票列表：QMT 不可用且本地 none 目录不存在")


def _load_codes_from_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def _load_adj_factor(base_dir: str) -> pd.DataFrame:
    """加载 adj_factor.parquet；不存在则返回空 DataFrame。

    保持与旧格式兼容：列名为 date, stock_code, close_front, close_none,
    cumulative_adj_factor（front 因子）。额外增加 adj_factor_back 列用于 back 因子。
    """
    path = str(resolve_source_parquet(ADJ_FACTOR_PATH))
    if not os.path.exists(path):
        return pd.DataFrame(columns=[
            "date", "stock_code", "close_front", "close_none",
            "cumulative_adj_factor", "adj_factor_back",
        ])
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])

    if "cumulative_adj_factor" in df.columns:
        # 旧格式可能没有 adj_factor_back；由于 QMT front 不可靠，
        # 统一用本地 back/none 重新计算 front/back 因子。
        if "adj_factor_back" not in df.columns:
            logger.info("检测到旧格式 adj_factor.parquet，将从 back/none 重新计算因子")
            df["adj_factor_back"] = np.nan
            for code in df["stock_code"].unique():
                df_back = _load_local_1d(code, "back", base_dir)
                df_none = _load_local_1d(code, "none", base_dir)
                if df_back is None or df_none is None:
                    continue
                merged = df_none[["close"]].merge(df_back[["close"]], left_index=True, right_index=True,
                                                   suffixes=("_none", "_back"))
                merged = merged.dropna()
                if merged.empty:
                    continue
                merged["af_back"] = merged["close_back"] / merged["close_none"]
                latest_af_back = merged["af_back"].iloc[-1]
                merged["af_front"] = merged["af_back"] / latest_af_back
                merged["close_front"] = merged["close_none"] * merged["af_front"]
                code_mask = df["stock_code"] == code
                date_to_row = merged.reset_index().set_index("date")
                df.loc[code_mask, "adj_factor_back"] = df.loc[code_mask, "date"].map(date_to_row["af_back"])
                df.loc[code_mask, "cumulative_adj_factor"] = df.loc[code_mask, "date"].map(date_to_row["af_front"])
                df.loc[code_mask, "close_front"] = df.loc[code_mask, "date"].map(date_to_row["close_front"])
    return df


def _save_adj_factor(df: pd.DataFrame, base_dir: str) -> None:
    _ = base_dir
    path = str(resolve_source_parquet(ADJ_FACTOR_PATH))
    df = df.sort_values(["stock_code", "date"]).reset_index(drop=True)
    before = len(df)
    df = df.drop_duplicates(subset=["date", "stock_code"], keep="last")
    if len(df) < before:
        logger.info(f"adj_factor 去重: {before} -> {len(df)} 行")
    df.to_parquet(path, index=False)
    logger.info(f"已保存 adj_factor.parquet: {len(df)} 行")


def _load_local_1d(code: str, adjust_type: str, base_dir: str) -> Optional[pd.DataFrame]:
    """读取本地日线 parquet。"""
    path = PeriodDataManager.get_file_path(
        Path(base_dir), "1d", adjust_type, code
    )
    if not path.exists():
        return None
    df = pd.read_parquet(path, engine="pyarrow")
    if "date" not in df.columns:
        df["date"] = pd.to_datetime(df["time"], unit="ms").dt.normalize()
    df = df.set_index("date").sort_index()
    return df


def _get_latest_adj_factor(adj_df: pd.DataFrame, code: str, as_of_date: pd.Timestamp,
                            max_stale_days: int = 7) -> Optional[Tuple[pd.Timestamp, float, float]]:
    """获取某股票截至 as_of_date 的最新 adj_factor。

    若最新记录与 as_of_date 相差超过 max_stale_days 天，视为数据断更，返回 None
    （避免断更后首次运行出现大量误判）。
    """
    sub = adj_df[(adj_df["stock_code"] == code) & (adj_df["date"] <= as_of_date)]
    if sub.empty:
        return None
    latest = sub.sort_values("date").iloc[-1]
    latest_date = cast(pd.Timestamp, pd.Timestamp(latest["date"]))
    if (as_of_date - latest_date).days > max_stale_days:
        return None
    return latest_date, latest["cumulative_adj_factor"], latest["adj_factor_back"]


def _compute_today_adj_factor(code: str, target_date: pd.Timestamp, base_dir: str) -> Optional[Tuple[float, float, float, float]]:
    """从本地 back/none 数据计算 target_date 当天的 adj_factor。

    QMT 返回的 front 数据与 none 相同（不可靠），因此 front_factor 由 back_factor
    推导：front_factor[t] = back_factor[t] / back_factor[latest]。
    返回值：(close_none, close_back, af_front, af_back)。
    """
    df_none = _load_local_1d(code, "none", base_dir)
    df_back = _load_local_1d(code, "back", base_dir)

    if df_none is None or df_back is None:
        return None

    if target_date not in df_none.index or target_date not in df_back.index:
        return None

    back_close = df_back.loc[target_date, "close"]
    none_close = df_none.loc[target_date, "close"]

    if pd.isna(back_close) or pd.isna(none_close):
        return None
    if none_close <= 0:
        return None

    af_back = back_close / none_close
    # front_factor 以最新日期为基准 1
    af_front = 1.0  # target_date 即 latest，front_factor=1

    return none_close, back_close, af_front, af_back


def _rebuild_adj_factor_for_codes(codes: List[str], base_dir: str) -> pd.DataFrame:
    """对指定股票，从本地 back/none 重新计算完整 adj_factor 历史。

    QMT front 数据不可靠，因此 front_factor 由 back_factor 推导：
    front_factor[t] = back_factor[t] / back_factor[latest]。
    """
    frames = []
    for code in codes:
        df_none = _load_local_1d(code, "none", base_dir)
        df_back = _load_local_1d(code, "back", base_dir)
        if df_none is None or df_back is None:
            logger.warning(f"[{code}] 缺少 none/back 之一，跳过 adj_factor 重建")
            continue

        merged = df_none[["close"]].merge(
            df_back[["close"]], left_index=True, right_index=True, suffixes=("_none", "_back"), how="outer"
        )
        merged.columns = ["close_none", "close_back"]
        merged = merged.sort_index()

        # 前向填充单侧缺失，复权因子在非除权日保持不变
        merged["close_none"] = merged["close_none"].ffill()
        merged["close_back"] = merged["close_back"].ffill()

        # 单侧仍缺失（如上市首日前）标记为 NaN
        _one_sided_na = merged["close_none"].isna() | merged["close_back"].isna()
        merged["adj_factor_back"] = merged["close_back"] / merged["close_none"]
        merged.loc[_one_sided_na, "adj_factor_back"] = np.nan

        latest_back_factor = merged["adj_factor_back"].iloc[-1]
        merged["cumulative_adj_factor"] = merged["adj_factor_back"] / latest_back_factor
        merged["close_front"] = merged["close_none"] * merged["cumulative_adj_factor"]
        merged = merged.reset_index()
        merged["stock_code"] = code
        merged = merged[["date", "stock_code", "close_front", "close_none", "cumulative_adj_factor", "adj_factor_back"]]
        frames.append(merged)

    if not frames:
        return pd.DataFrame(columns=[
            "date", "stock_code", "close_front", "close_none", "cumulative_adj_factor", "adj_factor_back"
        ])
    return pd.concat(frames, ignore_index=True)


def _write_adjusted_parquet(df: pd.DataFrame, base_dir: str, code: str, adjust_type: str) -> None:
    """将修正后的价格 DataFrame 写成与 DataDownloader 一致的 parquet。"""
    df = df.copy()
    if "date" in df.columns:
        df = df.drop(columns=["date"])
    df["time"] = (df.index.astype("int64") // 10**6).astype("int64")
    df = cast(pd.DataFrame, df[StockDataManager.STANDARD_COLUMNS])
    path = PeriodDataManager.get_file_path(
        Path(base_dir), "1d", adjust_type, code
    )
    df.to_parquet(path, engine="pyarrow", compression="snappy")


def _rebuild_from_adj_factor_history(code: str, base_dir: str, adj_df: pd.DataFrame) -> None:
    """用 adj_factor 历史从 none 重建 front/back 的 OHLC/close（用于 --init）。"""
    df_none = _load_local_1d(code, "none", base_dir)
    if df_none is None:
        logger.warning(f"[{code}] 重建失败：缺少 none")
        return

    code_adj = adj_df[adj_df["stock_code"] == code].set_index("date").sort_index()
    if code_adj.empty:
        logger.warning(f"[{code}] 重建失败：adj_factor 无记录")
        return

    # 对齐日期
    merged = df_none.join(code_adj[["cumulative_adj_factor", "adj_factor_back"]], how="inner")
    if merged.empty:
        logger.warning(f"[{code}] 重建失败：none 与 adj_factor 无交集")
        return

    price_cols = ["open", "high", "low", "close"]

    # front
    front = df_none.reindex(merged.index).copy()
    af_front = merged["cumulative_adj_factor"]
    for col in price_cols:
        front[col] = front[col] * af_front
    front = front.dropna(subset=["close"])
    _write_adjusted_parquet(front, base_dir, code, "front")

    # back
    back = df_none.reindex(merged.index).copy()
    af_back = merged["adj_factor_back"]
    for col in price_cols:
        back[col] = back[col] * af_back
    back = back.dropna(subset=["close"])
    _write_adjusted_parquet(back, base_dir, code, "back")

    logger.info(
        f"[{code}] 已从 adj_factor 历史重建 front/back ({len(merged)} 行)"
    )


def _rebuild_close_local(code: str, target_date: pd.Timestamp, base_dir: str,
                         af_front_old: float, af_front_new: float,
                         af_back_old: float, af_back_new: float) -> None:
    """除权后本地按比例缩放修正 front/back 的 OHLC/close（日常增量模式）。

    前复权/后复权数据在除权后，target_date 之前的历史价格会按同一比例缩放。
    我们已经知道昨日因子（af_old）和今日因子（af_new），因此缩放比例为
    scale = af_new / af_old。target_date 当天已经从 QMT 拿到最新价格，
    因此只缩放 < target_date 的历史数据，保留 target_date 当天不变。
    """
    df_front = _load_local_1d(code, "front", base_dir)
    df_back = _load_local_1d(code, "back", base_dir)
    if df_front is None or df_back is None:
        logger.warning(f"[{code}] 本地重算失败：缺少 front/back 之一")
        return

    scale_front = af_front_new / af_front_old if abs(af_front_old) > 1e-12 else 1.0
    scale_back = af_back_new / af_back_old if abs(af_back_old) > 1e-12 else 1.0

    price_cols = ["open", "high", "low", "close"]

    # 更新 front parquet：只缩放 target_date 之前的历史
    front_new = df_front.copy()
    mask_before = front_new.index < target_date
    if mask_before.any():
        for col in price_cols:
            front_new.loc[mask_before, col] = front_new.loc[mask_before, col] * scale_front
    front_new = front_new.dropna(subset=["close"])
    _write_adjusted_parquet(front_new, base_dir, code, "front")

    # 更新 back parquet
    back_new = df_back.copy()
    mask_before = back_new.index < target_date
    if mask_before.any():
        for col in price_cols:
            back_new.loc[mask_before, col] = back_new.loc[mask_before, col] * scale_back
    back_new = back_new.dropna(subset=["close"])
    _write_adjusted_parquet(back_new, base_dir, code, "back")

    logger.info(
        f"[{code}] 本地已缩放 front/back 历史 (scale front={scale_front:.6f} back={scale_back:.6f})"
    )


def _update_adj_factor(adj_df: pd.DataFrame, code: str, target_date: pd.Timestamp,
                       close_front: float, close_none: float,
                       af_front: float, af_back: float) -> pd.DataFrame:
    """追加/更新某股票某日的 adj_factor（兼容旧格式列名）。"""
    mask = (adj_df["stock_code"] == code) & (adj_df["date"] == target_date)
    if mask.any():
        adj_df.loc[mask, "close_front"] = close_front
        adj_df.loc[mask, "close_none"] = close_none
        adj_df.loc[mask, "cumulative_adj_factor"] = af_front
        adj_df.loc[mask, "adj_factor_back"] = af_back
    else:
        new_row = pd.DataFrame([{
            "date": target_date,
            "stock_code": code,
            "close_front": close_front,
            "close_none": close_none,
            "cumulative_adj_factor": af_front,
            "adj_factor_back": af_back,
        }])
        adj_df = pd.concat([adj_df, new_row], ignore_index=True)
    return adj_df


def _chunked(lst: List, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="日线复权数据增量更新")
    parser.add_argument(
        "--base-dir",
        default=str(resolve_e_stock_data_container()),
        help="E workspace / ops root (parquet hive follows path-SSOT)",
    )
    parser.add_argument("--start", default=DEFAULT_START, help="历史起始日期 YYYYMMDD")
    parser.add_argument("--end", default=None, help="目标日期 YYYYMMDD，默认今天")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="adj_factor 变化阈值")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH, help="每批下载数量")
    parser.add_argument("--codes", default=None, help="股票列表文件路径")
    parser.add_argument("--dry-run", action="store_true", help="只检测不下载")
    parser.add_argument("--rebuild-mode", default="local",
                        choices=["local", "download", "both"],
                        help="除权后重算策略: local=本地重算close, download=从QMT重下, both=先download失败则local")
    parser.add_argument("--rebuild-window-years", type=int, default=0,
                        help="download/both 模式下只重下最近 N 年(0=从--start开始)")
    parser.add_argument("--init", action="store_true",
                        help="重建所有股票的完整 adj_factor 历史(不检测变化)")
    parser.add_argument("--rebuild-duckdb", action="store_true", help="完成后重建 duckdb")
    return parser.parse_args()


def main():
    args = _parse_args()
    global BASE_DIR
    BASE_DIR = args.base_dir

    if args.end is None:
        target_date = pd.Timestamp.now().normalize()
    else:
        target_date = pd.to_datetime(args.end)

    target_str = target_date.strftime("%Y%m%d")
    yesterday = target_date - pd.Timedelta(days=1)

    logger.info("=" * 60)
    logger.info(f"日线复权增量更新: target={target_str}, threshold={args.threshold * 100:.2f}%, dry_run={args.dry_run}")
    logger.info("=" * 60)

    # 1. 获取股票列表
    if args.codes:
        all_codes = _load_codes_from_file(args.codes)
    else:
        all_codes = _get_all_a_stock_codes()
    logger.info(f"股票总数: {len(all_codes)}")

    # 2. 加载 adj_factor
    adj_df = _load_adj_factor(BASE_DIR)
    logger.info(f"已加载 adj_factor: {len(adj_df)} 行, {adj_df['stock_code'].nunique()} 只股票")

    downloader = DataDownloader(base_dir=BASE_DIR)

    if args.init:
        logger.info("--init 模式：跳过增量下载，直接从本地数据重建")
    elif not args.dry_run:
        # 3. 增量下载 none/back；front 由 back 推导（QMT front 数据不可靠）
        logger.info("步骤 1/2: 增量下载 none ...")
        downloader.download_data(
            stock_list=all_codes,
            start_time=args.start,
            end_time=target_str,
            period="1d",
            adjust_type="none",
            incrementally=True,
        )

        logger.info("步骤 2/2: 增量下载 back ...")
        downloader.download_data(
            stock_list=all_codes,
            start_time=args.start,
            end_time=target_str,
            period="1d",
            adjust_type="back",
            incrementally=True,
        )

    # 4. 检测 adj_factor 变化 / 计算今日因子
    logger.info("检测 adj_factor 变化 ...")
    needs_rebuild: List[str] = []
    today_factors: Dict[str, Tuple[float, float, float, float]] = {}
    appended_count = 0

    for code in all_codes:
        today_result = _compute_today_adj_factor(code, target_date, BASE_DIR)
        if today_result is None:
            logger.debug(f"[{code}] 无法计算今日 adj_factor")
            continue

        close_none_today, close_back_today, af_front_today, af_back_today = today_result
        # front close 由 back 推导：front = back / back_factor_latest = none * front_factor
        close_front_today = close_none_today * af_front_today
        today_factors[code] = today_result

        # 获取昨日 adj_factor
        yest_result = _get_latest_adj_factor(adj_df, code, yesterday)

        if yest_result is None:
            # 首次记录 或 数据断超过 max_stale_days
            adj_df = _update_adj_factor(adj_df, code, target_date,
                                        close_front_today, close_none_today,
                                        af_front_today, af_back_today)
            appended_count += 1
            continue

        _yest_date, af_front_yest, af_back_yest = yest_result

        # 检测变化：以 adj_factor_back 为准（真实累积复权因子）。
        # cumulative_adj_factor（front_factor）= back_factor / latest_back_factor，
        # 其变化可能仅由 latest_back_factor 变化引起，不代表真实除权。
        back_changed = abs(af_back_today - af_back_yest) / max(abs(af_back_yest), 1e-12) > args.threshold

        if back_changed:
            needs_rebuild.append(code)
            logger.info(f"[{code}] adj_factor 变化: front {af_front_yest:.6f}->{af_front_today:.6f}, back {af_back_yest:.6f}->{af_back_today:.6f}")

        # 更新 adj_factor
        adj_df = _update_adj_factor(adj_df, code, target_date,
                                    close_front_today, close_none_today,
                                    af_front_today, af_back_today)
        appended_count += 1

    # --init 模式：直接重建所有股票的完整 adj_factor 历史
    if args.init and not args.dry_run:
        logger.info(f"--init 模式：重建 {len(all_codes)} 只股票的完整 adj_factor 历史")
        needs_rebuild = list(all_codes)

    logger.info(f"今日可计算 adj_factor 的股票: {appended_count} 只")
    logger.info(f"触发重建的股票: {len(needs_rebuild)} 只")

    if needs_rebuild and not args.dry_run:
        # 4a. 从 QMT 重下（可选）
        if args.rebuild_mode in ("download", "both"):
            rebuild_start = args.start
            if args.rebuild_window_years > 0:
                rebuild_start_dt = target_date - pd.DateOffset(years=args.rebuild_window_years)
                rebuild_start = max(rebuild_start_dt, pd.to_datetime(args.start)).strftime("%Y%m%d")
                logger.info(f"download 模式：只重下最近 {args.rebuild_window_years} 年 ({rebuild_start} 起)")
            else:
                logger.info(f"download 模式：全量重下 front/back (共 {len(needs_rebuild)} 只) ...")

            for idx, batch in enumerate(_chunked(needs_rebuild, args.batch), start=1):
                logger.info(f"[Rebuild batch {idx}/{(len(needs_rebuild) + args.batch - 1) // args.batch}] {len(batch)} 只")
                downloader.download_data(
                    stock_list=batch,
                    start_time=rebuild_start,
                    end_time=target_str,
                    period="1d",
                    adjust_type="front",
                    incrementally=False,
                )
                downloader.download_data(
                    stock_list=batch,
                    start_time=rebuild_start,
                    end_time=target_str,
                    period="1d",
                    adjust_type="back",
                    incrementally=False,
                )
                if idx < (len(needs_rebuild) + args.batch - 1) // args.batch:
                    time.sleep(0.5)

        # 4b/4c. 本地重算 front/back 并重建 adj_factor 历史
        if args.rebuild_mode in ("local", "both"):
            mode_label = "both" if args.rebuild_mode == "both" else "local"
            if args.init:
                # --init：先重建 adj_factor，再从 adj_factor 历史重建 front/back
                logger.info(f"重建 {len(needs_rebuild)} 只股票的 adj_factor 历史 ...")
                rebuilt_df = _rebuild_adj_factor_for_codes(needs_rebuild, BASE_DIR)
                if not rebuilt_df.empty:
                    adj_df = adj_df[~adj_df["stock_code"].isin(needs_rebuild)]
                    adj_df = pd.concat([adj_df, rebuilt_df], ignore_index=True)
                logger.info(f"{mode_label} 模式：从 adj_factor 历史重建 front/back (共 {len(needs_rebuild)} 只) ...")
                for code in needs_rebuild:
                    _rebuild_from_adj_factor_history(code, BASE_DIR, adj_df)
            else:
                # 日常：先按比例缩放 front/back 历史，再基于新的 front/back 重建 adj_factor
                logger.info(f"{mode_label} 模式：按比例缩放修正 front/back 历史 (共 {len(needs_rebuild)} 只) ...")
                for code in needs_rebuild:
                    if code not in today_factors:
                        logger.warning(f"[{code}] 无今日因子，跳过本地重算")
                        continue
                    yest_result = _get_latest_adj_factor(adj_df, code, yesterday)
                    if yest_result is None:
                        logger.warning(f"[{code}] 无昨日因子，跳过本地重算")
                        continue
                    _yest_date, af_front_old, af_back_old = yest_result
                    _cfront, _cnone, af_front_new, af_back_new = today_factors[code]
                    _rebuild_close_local(
                        code, target_date, BASE_DIR,
                        af_front_old, af_front_new, af_back_old, af_back_new,
                    )
                logger.info(f"重建 {len(needs_rebuild)} 只股票的 adj_factor 历史 ...")
                rebuilt_df = _rebuild_adj_factor_for_codes(needs_rebuild, BASE_DIR)
                if not rebuilt_df.empty:
                    adj_df = adj_df[~adj_df["stock_code"].isin(needs_rebuild)]
                    adj_df = pd.concat([adj_df, rebuilt_df], ignore_index=True)

    # 5. 保存 adj_factor
    if not args.dry_run:
        _save_adj_factor(adj_df, BASE_DIR)

    # 6. 可选重建 duckdb
    if args.rebuild_duckdb and not args.dry_run:
        logger.info("重建 duckdb ...")
        try:
            from oskh_data.reader import StockDataReader
            for adjust in ["front", "none", "back"]:
                db_path, elapsed = StockDataReader.build_persistent_db(
                    base_dir=BASE_DIR, period="1d", adjust_type=adjust
                )
                logger.info(f"{db_path.name} rebuilt: {db_path.stat().st_size / (1024 * 1024):.1f} MB in {elapsed:.0f}s")
        except Exception as e:
            logger.warning(f"duckdb 重建失败: {e}")

    logger.info("=" * 60)
    logger.info(f"完成。target={target_str}, 触发重下={len(needs_rebuild)} 只")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
