"""BT cache client configuration and adjustment gate; storage belongs to infra."""
from __future__ import annotations

from typing import Optional
import pandas as pd
from myquant_infra.lake import cache as _infra
from common.infra.quant_logger import get_logger

logger = get_logger(__name__)
_redis_client = None
_redis_available: Optional[bool] = None


def _get_redis():
    global _redis_client, _redis_available
    if _redis_available is False:
        return None
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.Redis(
                decode_responses=False, socket_connect_timeout=3.0, socket_timeout=5.0,
            )
            _redis_client.ping()
            _redis_available = True
        except Exception:
            _redis_available = False
            _redis_client = None
            logger.warning("Redis unavailable, cache disabled")
    return _redis_client


def set_current_run_id(period: str, run_id: str) -> bool:
    return _infra.set_current_run_id(period, run_id, client=_get_redis())


def get_current_run_id(period: str) -> Optional[str]:
    return _infra.get_current_run_id(period, client=_get_redis())


def invalidate_current_run_id(period: str) -> bool:
    return _infra.invalidate_current_run_id(period, client=_get_redis())


def get_daily_bars_cached(symbol: str, start: str, end: str, *,
                          period: str = "1d", adjust: str = "none",
                          trade_date: str = "") -> Optional[pd.DataFrame]:
    normalized = str(adjust or "none").strip().lower() or "none"
    if normalized != "none":
        from oskh_data.reader import _enforce_adjust_type_policy
        _enforce_adjust_type_policy(normalized)
    return _infra.get_daily_bars_cached(
        symbol, start, end, period=period, adjust=adjust, trade_date=trade_date,
        client=_get_redis(),
    )


def set_daily_bars_cached(df: pd.DataFrame, symbol: str, start: str, end: str, *,
                          period: str = "1d", adjust: str = "none",
                          trade_date: str = "", ttl_seconds: int = 86400) -> bool:
    return _infra.set_daily_bars_cached(
        df, symbol, start, end, period=period, adjust=adjust, trade_date=trade_date,
        ttl_seconds=ttl_seconds, client=_get_redis(),
    )
