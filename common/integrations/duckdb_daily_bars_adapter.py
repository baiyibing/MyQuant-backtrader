"""
DuckDB 日线代理 — 拦截 stock_daily_bars 调用，T-1 及以前走 DuckDB，T+0 走 QMT。

设计：
  - 代理 DefaultDecisionMarketDataReadPort，仅接管日线查询，其余透传。
  - 路由矩阵：start/end 全部 ≤ T-1 → DuckDB；否则 → delegate QMT。
  - DuckDB 失败 → fallback delegate。
  - 数据格式转换：StockDataReader(time ms) → YYYYMMDD 索引 → fund_daily_bars_records_from_df。

集成：在 resolve_decision_market_data_read_port_for_lt() 中，
当 DAILY_BARS_SOURCE=duckdb 时自动包装。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Literal, Optional

import pandas as pd

from common.infra.constants import EnvVarKeys
from common.infra.quant_logger import get_logger
from common.infra.runtime_config import config_value_source, get_raw as _cfg_raw

logger = get_logger(__name__)


class DuckDBDailyBarsProxy:
    """代理 DefaultDecisionMarketDataReadPort，仅接管日线查询，其余透传。"""

    def __init__(
        self,
        delegate: Any,
        *,
        asset_type: str = "stock",
        db_path: Optional[str] = None,
    ) -> None:
        self._delegate = delegate
        self._reader = None  # StockDataReader 延迟初始化
        self._asset_type: Literal["stock", "etf"] = (
            "etf" if str(asset_type or "stock").strip().lower() == "etf" else "stock"
        )
        self._db_path_override = (db_path or "").strip() or None

    def _get_reader(self):
        if self._reader is None:
            from oskh_data.reader import StockDataReader  # 函数内延迟导入，避免 import common.integrations 时强制加载 duckdb

            # Explicit db_path injection wins (ETF composition root / tests).
            if self._db_path_override and Path(self._db_path_override).is_file():
                self._reader = StockDataReader(
                    mode="duckdb_persistent",
                    db_path=self._db_path_override,
                    asset_type=self._asset_type,
                )
                cfg_src = "ctor_db_path"
                db_path = self._db_path_override
            else:
                # P1-08: use get_raw() for correct env+YAML layering.
                # ETF path must NOT rely on global DAILY_BARS_SOURCE / stock OSKH_DATA_DUCKDB_PATH.
                db_path = (_cfg_raw(EnvVarKeys.OSKH_DATA_DUCKDB_PATH) or "").strip()
                if self._asset_type == "etf":
                    self._reader = StockDataReader(
                        mode="duckdb_persistent",
                        asset_type="etf",
                        db_path=db_path if db_path and Path(db_path).is_file() else None,
                    )
                    cfg_src = config_value_source(EnvVarKeys.OSKH_DATA_DUCKDB_PATH) if db_path else "etf_auto"
                elif db_path and Path(db_path).is_file():
                    self._reader = StockDataReader(mode="duckdb_persistent", db_path=db_path)
                    cfg_src = config_value_source(EnvVarKeys.OSKH_DATA_DUCKDB_PATH)
                else:
                    # P1-08 Phase B: inside DuckDBDailyBarsProxy, default to duckdb_persistent
                    # with auto-detection rather than silently falling back to parquet.
                    self._reader = StockDataReader(mode="duckdb_persistent")
                    cfg_src = "default"
                    if db_path:
                        get_logger("DuckDBDailyBarsAdapter", "proxy-init").warning(
                            "OSKH_DATA_DUCKDB_PATH configured but file missing; using auto-detection",
                            context={"configured_path": db_path, "config_source": cfg_src},
                        )
            resolved_path = getattr(self._reader, "db_path", None) or db_path or "auto"
            get_logger("DuckDBDailyBarsAdapter", "proxy-init").info(
                "DuckDB proxy reader initialized",
                context={
                    "mode": getattr(self._reader, "mode", "?"),
                    "db_path": str(resolved_path),
                    "config_source": cfg_src,
                    "asset_type": self._asset_type,
                },
            )
        return self._reader

    def _is_t_minus_1_or_earlier(self, date_str: str) -> bool:
        """判断日期是否 ≤ 上一个交易日。"""
        try:
            from oskh_data.freshness import get_previous_trading_day

            prev = get_previous_trading_day()
            return date_str <= prev
        except Exception as _fresh_exc:
            logger.warning(
                "get_previous_trading_day failed; conservatively assuming T-1 or earlier",
                context={"error": repr(_fresh_exc)},
            )
            return True  # 保守：fallback 到 DuckDB

    def _df_to_bars_response(self, df: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """将 StockDataReader 返回的 DataFrame 转换为 bars 响应格式。"""
        from oskh_core.fund_daily_bars_serialize import fund_daily_bars_records_from_df

        if df is None or df.empty:
            return {"ok": True, "data": {"bars": [], "symbol": symbol}}

        df = df.copy()
        if "time" in df.columns:
            df["_date"] = pd.to_datetime(df["time"], unit="ms").dt.strftime("%Y%m%d")
            df = df.set_index("_date")
        if "symbol" in df.columns:
            df = df.drop(columns=["symbol"])

        bars = fund_daily_bars_records_from_df(df)
        return {"ok": True, "data": {"bars": bars, "symbol": symbol}}

    # ── 拦截：日线查询 ──

    def stock_daily_bars(
        self,
        *,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "none",
        trace_id: str = "",
        timeout_sec: Optional[float] = None,
        poll_sec: Optional[float] = None,
    ) -> Dict[str, Any]:
        if self._is_t_minus_1_or_earlier(end_date):
            try:
                reader = self._get_reader()
                df = reader.read_stock(
                    symbol, start_time=start_date, end_time=end_date,
                    period="1d", adjust_type=adjust,
                )
                if df is not None and not df.empty:
                    return self._df_to_bars_response(df, symbol)
                logger.debug(
                    "DuckDB miss for %s (%s→%s), falling back to QMT",
                    symbol, start_date, end_date,
                )
            except Exception:
                logger.exception(
                    "DuckDB query failed for %s, falling back to QMT",
                    symbol,
                    context={"symbol": symbol, "start": start_date, "end": end_date},
                )
        # T+0 或 DuckDB miss → delegate to QMT
        return self._delegate.stock_daily_bars(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            trace_id=trace_id,
            timeout_sec=timeout_sec,
            poll_sec=poll_sec,
        )

    def stock_daily_bars_cfg_only(
        self,
        *,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "none",
        trace_id: str = "",
        timeout_sec: Optional[float] = None,
        poll_sec: Optional[float] = None,
    ) -> Dict[str, Any]:
        # cfg_only 路径使用相同逻辑
        return self.stock_daily_bars(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            trace_id=trace_id,
            timeout_sec=timeout_sec,
            poll_sec=poll_sec,
        )

    # ── 透传：所有其他方法委托给原 port ──

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)
