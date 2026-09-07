#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票数据完整性检查脚本（从股票池文件加载股票列表）
检查指定日期的分钟线数据是否完整（包含15:00，且全天分钟数据无明显缺失），以及日线数据是否存在。
"""

import os
import sys
from datetime import datetime, time
from pathlib import Path
from typing import List

import pandas as pd

from common.infra.quant_logger import get_logger

# 项目根目录
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 过渡期导入（工具函数保留在 backtest，后续迁入 common/infra）。
# Phase 2 P1 TODO: get_stock_data_from_cache() uses the OLD DataDownloader path
# which bypasses StockDataReader validation (normalize_schema, NaN/Inf detection,
# timezone normalization, dtype validation).  Corrupted minute/ETF parquet files
# may pass integrity checks undetected.  Migrate to StockDataReader.read_stock()
# when the backtest→oskh_data migration is complete.
from backtest.qmt_utils_adv import (  # type: ignore[reportUnusedImport]
    SSE_CALENDAR,
    batch_format_stock_codes,
    get_stock_data_from_cache,
    read_stock_codes,
)

logger = get_logger(__name__)


def collect_stock_codes(pool_dir: str, start_date: str, end_date: str) -> set:
    """从股票池目录中读取指定日期范围内的所有股票代码，返回格式化后的集合。"""
    path = Path(pool_dir)
    csv_files = list(path.rglob('*.csv'))
    stock_set = set()

    for file_path in csv_files:
        filename = file_path.stem
        if not (start_date <= filename <= end_date):
            continue

        df = read_stock_codes(str(file_path))
        if df is None or df.empty:
            logger.warning(f"无法读取文件或文件为空: {file_path}")
            continue

        raw_list = df['stock_code'].tolist()
        formatted = batch_format_stock_codes(raw_list)
        stock_set.update(formatted)
        logger.debug(f"文件 {filename} 添加 {len(formatted)} 只股票")

    logger.info(f"共收集到 {len(stock_set)} 只股票")
    return stock_set


def is_trading_day(date_obj):
    """判断给定日期是否为交易日（复用 qmt_utils_adv 中的函数）"""
    if isinstance(date_obj, str):
        date_obj = datetime.strptime(date_obj, '%Y%m%d').date()
    trading_days = SSE_CALENDAR.valid_days(start_date=date_obj, end_date=date_obj)
    return len(trading_days) > 0


def check_minute_data_integrity(stock_code, target_date):
    """
    全面检查分钟线数据完整性。
    返回 (status, details)：
        status: 'OK' / 'WARNING' / 'ERROR'
        details: 描述字符串
    """
    # 构建完整交易时段起止时间
    start_dt = f"{target_date}093000"
    end_dt   = f"{target_date}150000"

    df = get_stock_data_from_cache(
        stock_code=stock_code,
        start_time=start_dt,
        end_time=end_dt,
        period='1m',
        adjust_type='none'
    )

    if df is None or df.empty:
        return 'ERROR', "数据为空（可能未下载或超出范围）"

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    target_date_dt = datetime.strptime(target_date, '%Y%m%d').date()
    day_data = df[df.index.date == target_date_dt]

    if day_data.empty:
        return 'ERROR', f"当天无数据"

    # 1. 检查是否有15:00之后的数据（收盘）
    target_time = time(15, 0, 0)
    has_15 = (day_data.index.time >= target_time).any()
    if not has_15:
        return 'ERROR', f"缺少15:00之后的数据，最后一条时间为 {day_data.index.max().strftime('%H:%M:%S')}"

    # 2. 计算预期分钟数（交易日且非节假日）
    if not is_trading_day(target_date_dt):
        return 'WARNING', f"非交易日，但存在数据（可能数据异常）"

    # 生成当天完整的分钟索引（9:31-11:30, 13:01-15:00）
    # 注意：9:30 是开盘集合竞价，通常没有K线，实际K线从9:31开始
    # 我们使用标准交易时段：9:30-11:30（120分钟），13:00-15:00（120分钟），共240分钟
    # 但9:30 和 13:00 的第一分钟是集合竞价？通常1分钟K线包含9:30:00 和 13:00:00
    # 更稳妥：生成从 09:30:00 到 11:30:00 每隔1分钟，以及 13:00:00 到 15:00:00 每隔1分钟
    morning = pd.date_range(
        start=f"{target_date} 09:30:00",
        end=f"{target_date} 11:30:00",
        freq='1min'
    )
    afternoon = pd.date_range(
        start=f"{target_date} 13:00:00",
        end=f"{target_date} 15:00:00",
        freq='1min'
    )
    expected_times = morning.union(afternoon)
    expected_count = len(expected_times)

    actual_times = day_data.index
    actual_count = len(actual_times)

    # 找出缺失的时间点
    missing_times = expected_times.difference(actual_times)
    missing_count = len(missing_times)

    # 计算缺失比例
    missing_ratio = missing_count / expected_count * 100

    # 判断标准（可调）
    if missing_count == 0:
        integrity = "完整"
    elif missing_ratio < 5:
        integrity = "基本完整"
    elif missing_ratio < 20:
        integrity = "部分缺失"
    else:
        integrity = "严重缺失"

    details = (f"共{actual_count}/{expected_count}分钟，缺失{missing_count}条({missing_ratio:.1f}%)，"
               f"最后时间{actual_times.max().strftime('%H:%M:%S')}，完整性评级：{integrity}")

    # 3. Phase 2 P2: price/volume sanity checks
    sanity_warnings: List[str] = []
    # 3a. Negative prices (data corruption)
    for col in ("open", "high", "low", "close"):
        if col in day_data.columns:
            neg = int((day_data[col] < 0).sum())
            if neg > 0:
                sanity_warnings.append(f"negative_{col}={neg}")
    # 3b. Zero volume with non-zero amount (impossible bar)
    if "volume" in day_data.columns and "amount" in day_data.columns:
        zv_na = int(((day_data["volume"] == 0) & (day_data["amount"] > 0)).sum())
        if zv_na > 0:
            sanity_warnings.append(f"zero_vol_nonzero_amount={zv_na}")
    # 3c. Price spike >20% within a single minute (likely data error)
    if "close" in day_data.columns and len(day_data) > 1:
        # Phase 2 P2: sort index before pct_change (ensures consecutive diffs
        # are between chronologically adjacent bars, not arbitrary index order)
        sorted_data = day_data.sort_index()
        pct_chg = sorted_data["close"].pct_change().abs()
        spikes = int((pct_chg > 0.2).sum())
        if spikes > 0:
            sanity_warnings.append(f"minute_spike_gt20pct={spikes}")

    if sanity_warnings:
        warn_str = "; ".join(sanity_warnings)
        details = f"{details} [价格异常: {warn_str}]"
        return 'WARNING', details

    # 如果有15:00数据，但整体缺失过多，仍可视为警告
    if missing_ratio > 20:
        return 'WARNING', details
    elif missing_ratio > 0:
        return 'OK', details   # 轻微缺失仍可接受
    else:
        return 'OK', details


def check_daily_data(stock_code, target_date):
    """
    检查日线数据是否包含目标日期。
    返回 bool
    """
    start_dt = f"{target_date}000000"
    end_dt   = f"{target_date}235959"

    df = get_stock_data_from_cache(
        stock_code=stock_code,
        start_time=start_dt,
        end_time=end_dt,
        period='1d',
        adjust_type='none'
    )

    if df is None or df.empty:
        return False

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    target_date_dt = datetime.strptime(target_date, '%Y%m%d').date()
    return any(df.index.date == target_date_dt)


def main():
    # 配置参数（与回测保持一致）
    pool_dir = "../stock_pool"
    start_date = "20260113"
    end_date   = "20260119"
    target_date = "20260116"   # 要检查的日期

    logger.info(f"从目录 '{pool_dir}' 收集日期范围 {start_date}~{end_date} 的股票代码")
    stock_set = collect_stock_codes(pool_dir, start_date, end_date)
    if not stock_set:
        logger.error("未收集到任何股票代码，退出")
        return

    logger.info(f"开始检查日期 {target_date} 的数据完整性，共 {len(stock_set)} 只股票")

    results = []
    minute_ok_count = 0
    minute_warning_count = 0
    minute_error_count = 0
    daily_missing_count = 0

    for stock in sorted(stock_set):
        logger.info(f"正在检查 {stock} ...")

        minute_status, minute_details = check_minute_data_integrity(stock, target_date)
        daily_ok = check_daily_data(stock, target_date)

        if minute_status == 'OK':
            minute_ok_count += 1
        elif minute_status == 'WARNING':
            minute_warning_count += 1
        else:
            minute_error_count += 1

        if not daily_ok:
            daily_missing_count += 1

        results.append({
            'stock': stock,
            'minute_status': minute_status,
            'minute_details': minute_details,
            'daily_ok': daily_ok
        })

    # 汇总输出
    print("\n" + "="*80)
    print(f"数据完整性检查报告 - {target_date}")
    print("="*80)
    print(f"分钟线: ✅ OK: {minute_ok_count}, ⚠️ 警告: {minute_warning_count}, ❌ 错误: {minute_error_count}")
    print(f"日线:   ✅ 存在: {len(stock_set)-daily_missing_count}, ❌ 缺失: {daily_missing_count}")
    print("-"*80)

    for r in results:
        minute_symbol = "✅" if r['minute_status'] == 'OK' else ("⚠️" if r['minute_status'] == 'WARNING' else "❌")
        daily_symbol = "✅" if r['daily_ok'] else "❌"
        print(f"{r['stock']:12s}: 分钟线 {minute_symbol} ({r['minute_details']}), 日线 {daily_symbol}")

    print("="*80)

    if minute_error_count == 0:
        logger.info("所有股票的分钟线均包含15:00数据，且无明显缺失。")
    else:
        logger.error(f"有 {minute_error_count} 只股票分钟线缺失15:00数据，可能导致收盘处理未触发。")
    if minute_warning_count > 0:
        logger.warning(f"有 {minute_warning_count} 只股票分钟线存在部分缺失（但仍包含15:00）。")
    if daily_missing_count > 0:
        logger.warning(f"有 {daily_missing_count} 只股票日线数据缺失，可能影响指标计算。")


if __name__ == "__main__":
    main()