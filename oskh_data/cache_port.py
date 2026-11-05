"""BT Redis client composition and #563 read gate over infra's versioned cache."""
from __future__ import annotations

from typing import Optional

import pandas as pd
try:
    from myquant_infra.lake import cache as _infra_cache
except ImportError:  # CI without private pin
    class _InfraCacheStub:
        @staticmethod
        def set_current_run_id(*a, **k):
            raise ImportError("myquant-infra required for cache")

        @staticmethod
        def get_current_run_id(*a, **k):
            raise ImportError("myquant-infra required for cache")

        @staticmethod
        def invalidate_current_run_id(*a, **k):
            raise ImportError("myquant-infra required for cache")

        @staticmethod
        def get_daily_bars_cached(*a, **k):
            raise ImportError("myquant-infra required for cache")

    _infra_cache = _InfraCacheStub()  # type: ignore[assignment]
from common.infra.quant_logger import get_logger

logger = get_logger(__name__)
_redis_client = None
_redis_available: Optional[bool] = None

def _get_redis():
    """延迟导入 + 懒连接 Redis。不可用时返回 None。"""
    global _redis_client, _redis_available
    if _redis_available is False:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        import redis as _r

        _redis_client = _r.Redis(
            decode_responses=False,
            socket_connect_timeout=3.0,
            socket_timeout=5.0,
        )
        _redis_client.ping()
        _redis_available = True
        return _redis_client
    except Exception:
        _redis_available = False
        logger.warning("Redis unavailable, cache disabled (fail-open to DuckDB)")
        return None


def set_current_run_id(period: str, run_id: str) -> bool:
    return _infra_cache.set_current_run_id(period, run_id, client=_get_redis())


def get_current_run_id(period: str) -> Optional[str]:
    return _infra_cache.get_current_run_id(period, client=_get_redis())


def invalidate_current_run_id(period: str) -> bool:
    return _infra_cache.invalidate_current_run_id(period, client=_get_redis())


def get_daily_bars_cached(
    symbol: str, start: str, end: str, *, period: str = "1d",
    adjust: str = "none", trade_date: str = "",
) -> Optional[pd.DataFrame]:
    normalized_adjust = str(adjust or "none").strip().lower() or "none"
    if normalized_adjust != "none":
        from oskh_data.reader import _enforce_adjust_type_policy

        _enforce_adjust_type_policy(normalized_adjust)
    # #563: policy runs before Redis connection, pointer lookup or cache hit.
    return _infra_cache.get_daily_bars_cached(
        symbol, start, end, client=_get_redis(), period=period,
        adjust=adjust, trade_date=trade_date,
    )


def set_daily_bars_cached(
    df: pd.DataFrame, symbol: str, start: str, end: str, *,
    period: str = "1d", adjust: str = "none", trade_date: str = "",
    ttl_seconds: int = 86400,
) -> bool:
    return _infra_cache.set_daily_bars_cached(
        df, symbol, start, end, client=_get_redis(), period=period,
        adjust=adjust, trade_date=trade_date, ttl_seconds=ttl_seconds,
    )
