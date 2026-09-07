"""
数据新鲜度门闸。

开盘前检查持仓/候选标的的日线覆盖率，不足时 fail-close 阻断交易。
交易日历驱动：比较上一交易日数据，非自然日（避免周末/节假日误阻断）。
"""
from __future__ import annotations
from .symbol_format import to_partition_key

import os
from dataclasses import dataclass
from datetime import time
from typing import List, Optional, cast

import pandas as pd

from oskh_data.pandas_typing import as_timestamp, normalize_timestamp, timestamp_strftime

from common.infra.quant_logger import get_logger

logger = get_logger(__name__)

from common.infra.constants import EnvVarKeys

# 默认阈值（EnvVarKeys 收敛，可通过环境变量覆盖）
# Phase 2 P2: validate env var values — float("NaN")/float("Inf") would silently
# disable freshness gating (NaN >= 0.95 is False, Inf >= 0.95 is True).
_raw_cov = os.environ.get(EnvVarKeys.OSKH_DATA_MIN_COVERAGE_RATIO, "0.95")
try:
    _cov = float(_raw_cov)
    if _cov != _cov or _cov == float('inf') or _cov == float('-inf'):  # NaN or Inf
        raise ValueError(f"invalid coverage ratio: {_raw_cov}")
    DEFAULT_MIN_COVERAGE_RATIO = max(0.0, min(1.0, _cov))
except (ValueError, TypeError):
    logger.warning("invalid OSKH_DATA_MIN_COVERAGE_RATIO=%s, using default 0.95", _raw_cov)
    DEFAULT_MIN_COVERAGE_RATIO = 0.95
_raw_stale = os.environ.get(EnvVarKeys.OSKH_DATA_MAX_STALENESS_DAYS, "2")
try:
    DEFAULT_MAX_STALENESS_DAYS = max(0, int(_raw_stale))
except (ValueError, TypeError):
    logger.warning("invalid OSKH_DATA_MAX_STALENESS_DAYS=%s, using default 2", _raw_stale)
    DEFAULT_MAX_STALENESS_DAYS = 2

# 交易时段（盘中 fail-close 窗口）
_TRADING_START = time(9, 15)
_TRADING_END = time(15, 0)

# 交易日历：common SSE cache（零副作用）


@dataclass
class FreshnessResult:
    """新鲜度检查结果。"""

    ok: bool
    coverage_ratio: float          # 0.0 ~ 1.0
    expected_count: int            # 期望的标的数
    loaded_count: int               # 实际可读取的标的数
    missing_symbols: List[str]      # 缺失的标的列表
    last_data_date: str             # 实际最新数据日期（YYYYMMDD）
    expected_date: str              # 期望数据日期（YYYYMMDD）
    action: str                     # "block" | "warn" | "pass"


def get_previous_trading_day(date: Optional[pd.Timestamp] = None) -> str:
    """返回给定日期的上一个交易日（YYYYMMDD）。

    date 为 None 时使用今天。
    """
    from common.infra.trading_calendar_pmc import get_trade_days_sse

    if date is None:
        date = pd.Timestamp.now()
    until = timestamp_strftime(date, "%Y%m%d")
    since = timestamp_strftime(date - pd.Timedelta(days=30), "%Y%m%d")
    df = get_trade_days_sse(since=since, until=until)
    if df is None or df.empty:
        return until
    return str(df.iloc[-1]["cal_date"])


def _trading_days_count(since_yyyymmdd: str, until_yyyymmdd: str) -> int:
    from common.infra.trading_calendar_pmc import get_trade_days_sse

    df = get_trade_days_sse(since=since_yyyymmdd, until=until_yyyymmdd)
    return 0 if df is None else int(len(df))


def _is_trading_session() -> bool:
    """判断当前是否在交易时段（09:15-15:00）。"""
    now = pd.Timestamp.now().time()
    return _TRADING_START <= now <= _TRADING_END


def _check_adj_factor_table_freshness(expected_date: str) -> tuple[bool, str]:
    """Return (ok, last_data_date) for adj_factor.parquet sidecar / date column."""
    from oskh_data.adj_factor_meta import read_adj_factor_data_max_date

    from common.infra.data_root import resolve_source_parquet

    parquet_path = resolve_source_parquet("adj_factor.parquet")
    if not parquet_path.is_file():
        return False, ""
    max_ts = read_adj_factor_data_max_date(parquet_path)
    if max_ts is None:
        try:
            df = pd.read_parquet(parquet_path, columns=["date"])
            if df.empty:
                return False, ""
            max_ts = pd.to_datetime(df["date"], errors="coerce").max()
            if pd.isna(max_ts):
                return False, ""
            max_ts = normalize_timestamp(max_ts)
        except Exception:
            return False, ""
    _adj_anchor = cast(
        pd.Timestamp,
        pd.Timestamp(str(expected_date)) - pd.Timedelta(days=1),
    )
    expected_prev = normalize_timestamp(get_previous_trading_day(_adj_anchor))
    last_str = timestamp_strftime(max_ts, "%Y%m%d")
    return normalize_timestamp(max_ts) >= expected_prev, last_str


def check_data_freshness(
    symbols: List[str],
    *,
    expected_date: Optional[str] = None,
    min_coverage_ratio: Optional[float] = None,
    max_staleness_days: Optional[int] = None,
) -> FreshnessResult:
    """检查持仓/候选标的的日线数据覆盖率。

    Args:
        symbols: 需要检查的标的列表
        expected_date: 期望的数据日期（YYYYMMDD），None 时自动取上一个交易日
        min_coverage_ratio: 最小覆盖率阈值，默认 0.95
        max_staleness_days: 最大数据滞后天数，默认 2

    Returns:
        FreshnessResult with action: "block" | "warn" | "pass"
    """
    min_cov = min_coverage_ratio or DEFAULT_MIN_COVERAGE_RATIO
    max_stale = max_staleness_days or DEFAULT_MAX_STALENESS_DAYS

    if expected_date is None:
        expected_date = get_previous_trading_day()

    expected_count = len(symbols)

    # adj_factor 表新鲜度（除权日 stale 防护）— 与 symbols 循环解耦；空列表仍查表
    adj_ok, adj_last = _check_adj_factor_table_freshness(expected_date)
    if not adj_ok:
        action = "block" if _is_trading_session() else "warn"
        _adj_anchor = cast(
            pd.Timestamp,
            pd.Timestamp(str(expected_date)) - pd.Timedelta(days=1),
        )
        logger.error(
            "adj_factor freshness FAIL-CLOSE: last_data_date=%s, expected_prev_trading_day>=%s, action=%s",
            adj_last or "N/A",
            get_previous_trading_day(_adj_anchor),
            action,
        )
        return FreshnessResult(
            ok=(action != "block"),
            coverage_ratio=0.0,
            expected_count=expected_count,
            loaded_count=0,
            missing_symbols=["adj_factor.parquet"],
            last_data_date=adj_last,
            expected_date=expected_date,
            action=action,
        )

    if expected_count == 0:
        return FreshnessResult(
            ok=True,
            coverage_ratio=1.0,
            expected_count=0,
            loaded_count=0,
            missing_symbols=[],
            last_data_date=adj_last or expected_date,
            expected_date=expected_date,
            action="pass",
        )

    # 逐标检查本地 Parquet 文件是否存在
    from oskh_data.reader import _resolve_data_root

    data_root = _resolve_data_root()
    loaded_count = 0
    missing_symbols: List[str] = []
    loaded_last_dates: List[pd.Timestamp] = []

    for sym in symbols:
        safe = to_partition_key(sym)
        from common.infra.data_root import resolve_period_root

        path = (
            resolve_period_root('1d') / 'dividend_type=none' /
            f'symbol={safe}' / 'data.parquet'
        )
        if path.exists():
            try:
                df = pd.read_parquet(path, columns=['time'], engine='pyarrow')
                if not df.empty:
                    ts = pd.to_datetime(df["time"], unit="ms", errors="coerce", utc=True)
                    ts = ts[ts.notna()]
                    if len(ts) <= 0:
                        missing_symbols.append(sym)
                        continue
                    loaded_count += 1
                    loaded_last_dates.append(normalize_timestamp(as_timestamp(ts.max()).tz_localize(None)))
                else:
                    missing_symbols.append(sym)
            except Exception:
                missing_symbols.append(sym)
        else:
            missing_symbols.append(sym)

    coverage_ratio = loaded_count / expected_count if expected_count > 0 else 1.0

    expected_ts = normalize_timestamp(pd.Timestamp(expected_date))
    if loaded_last_dates:
        last_data_ts = max(loaded_last_dates)
        if last_data_ts >= expected_ts:
            stale_trading_days = 0
        else:
            since_s = timestamp_strftime(last_data_ts + pd.Timedelta(days=1), "%Y%m%d")
            until_s = timestamp_strftime(expected_ts, "%Y%m%d")
            stale_trading_days = _trading_days_count(since_s, until_s)
        last_data_date = timestamp_strftime(last_data_ts, "%Y%m%d")
    else:
        stale_trading_days = max_stale + 1
        last_data_date = ""

    # 判定 action
    is_stale = stale_trading_days > max_stale
    below_threshold = coverage_ratio < min_cov

    if below_threshold or is_stale:
        if _is_trading_session():
            action = "block"
            logger.error(
                "Data freshness FAIL-CLOSE: coverage=%.1f%% (%d/%d), "
                "last_data_date=%s, expected_date=%s, stale_trading_days=%d, action=BLOCK",
                coverage_ratio * 100, loaded_count, expected_count,
                last_data_date or "N/A",
                expected_date,
                stale_trading_days,
                context={"missing_symbols": missing_symbols[:20]},
            )
        else:
            action = "warn"
            logger.warning(
                "Data freshness degraded: coverage=%.1f%% (%d/%d), "
                "last_data_date=%s, expected_date=%s, stale_trading_days=%d, action=WARN (non-trading session)",
                coverage_ratio * 100, loaded_count, expected_count,
                last_data_date or "N/A",
                expected_date,
                stale_trading_days,
                context={"missing_symbols": missing_symbols[:20]},
            )
    else:
        action = "pass"

    return FreshnessResult(
        ok=(action != "block"),
        coverage_ratio=coverage_ratio,
        expected_count=expected_count,
        loaded_count=loaded_count,
        missing_symbols=missing_symbols,
        last_data_date=last_data_date,
        expected_date=expected_date,
        action=action,
    )
