"""
Redis 版本化缓存门面。

设计：
- Key 含 run_id，原子发布时递增 current_run_id 指针，读侧先 GET 指针再拼 key。
- 同日重跑/补数据自动失效旧缓存（新 run_id 不同）。
- pyarrow parquet 序列化（完整保留 DataFrame dtype/index）。
- Redis 不可用时 fail-open 返回 None，调用方回退 DuckDB。
"""
from __future__ import annotations

import io
from typing import Optional

import pandas as pd

from common.infra.quant_logger import get_logger

logger = get_logger(__name__)

# Redis 客户端延迟导入（避免非 Redis 环境阻塞进程启动）
_redis_client = None
_redis_available: Optional[bool] = None

# Key 前缀常量
_KEY_PREFIX = "oskh_data"
_POINTER_KEY_FMT = f"{_KEY_PREFIX}:current_run_id:{{period}}"  # 版本指针
_BARS_KEY_FMT = (
    f"{_KEY_PREFIX}:{{period}}:{{run_id}}:{{trade_date}}:{{symbol}}:{{start}}:{{end}}:{{adjust}}"
)


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


# ------------------------------------------------------------------
# 版本指针管理（由回填流程在原子发布后调用）
# ------------------------------------------------------------------


def set_current_run_id(period: str, run_id: str) -> bool:
    """原子发布后更新版本指针。返回 True 表示成功。"""
    r = _get_redis()
    if r is None:
        return False
    try:
        key = _POINTER_KEY_FMT.format(period=period)
        r.set(key, run_id)
        logger.info("current_run_id updated: %s → %s", period, run_id)
        return True
    except Exception as _e:
        # Phase 2 P2: log error type so operators can distinguish transient
        # (ConnectionError, TimeoutError → retry next call) from permanent
        # (ValueError, TypeError → config issue, won't self-heal).
        logger.exception(
            "Failed to set current_run_id for %s [%s]",
            period, type(_e).__name__,
        )
        return False


def get_current_run_id(period: str) -> Optional[str]:
    """读侧获取当前版本指针。Redis 不可用时返回 None（调用方回退 DuckDB）。"""
    r = _get_redis()
    if r is None:
        return None
    try:
        key = _POINTER_KEY_FMT.format(period=period)
        val = r.get(key)
        if val is None:
            return None
        if isinstance(val, (bytes, bytearray)):
            return val.decode("utf-8")
        return str(val)
    except Exception:
        logger.exception("Failed to get current_run_id for %s", period)
        return None


# ------------------------------------------------------------------
# 缓存读写
# ------------------------------------------------------------------


def get_daily_bars_cached(
    symbol: str,
    start: str,
    end: str,
    *,
    period: str = "1d",
    adjust: str = "none",
    trade_date: str = "",
) -> Optional[pd.DataFrame]:
    """从 Redis 缓存读取日线数据。

    命中返回 DataFrame，未命中或 Redis 不可用返回 None（调用方应回退 DuckDB）。
    """
    r = _get_redis()
    if r is None:
        return None

    run_id = get_current_run_id(period)
    if run_id is None:
        return None  # 无版本指针，缓存未初始化

    key = _BARS_KEY_FMT.format(
        period=period,
        run_id=run_id,
        trade_date=trade_date,
        symbol=symbol,
        start=start,
        end=end,
        adjust=adjust,
    )

    try:
        raw = r.get(key)
        if raw is None:
            return None
        return pd.read_parquet(io.BytesIO(raw), engine="pyarrow")  # type: ignore[reportArgumentType]
    except Exception:
        logger.exception("Redis cache read failed for %s", symbol)
        return None


def set_daily_bars_cached(
    df: pd.DataFrame,
    symbol: str,
    start: str,
    end: str,
    *,
    period: str = "1d",
    adjust: str = "none",
    trade_date: str = "",
    ttl_seconds: int = 86400,
) -> bool:
    """将日线数据写入 Redis 缓存。返回 True 表示成功。"""
    r = _get_redis()
    if r is None:
        return False

    run_id = get_current_run_id(period)
    if run_id is None:
        return False

    key = _BARS_KEY_FMT.format(
        period=period,
        run_id=run_id,
        trade_date=trade_date,
        symbol=symbol,
        start=start,
        end=end,
        adjust=adjust,
    )

    try:
        buf = io.BytesIO()
        df.to_parquet(buf, engine="pyarrow", compression="snappy")
        r.setex(key, ttl_seconds, buf.getvalue())
        return True
    except Exception:
        logger.exception("Redis cache write failed for %s", symbol)
        return False


def invalidate_current_run_id(period: str) -> bool:
    """删除版本指针（强制下次全部穿透到 DuckDB，用于紧急回退）。"""
    r = _get_redis()
    if r is None:
        return False
    try:
        key = _POINTER_KEY_FMT.format(period=period)
        r.delete(key)
        logger.warning("current_run_id invalidated for %s (emergency fallback)", period)
        return True
    except Exception:
        return False
