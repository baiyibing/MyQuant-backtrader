"""BT reader/configuration composition over optional myquant-infra daily bars.

Public CI has no private pin: host owns T-1 routing + adjust_type gate via
StockDataReader. Infra subclass is used only when the package is installed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Literal, Optional

import pandas as pd

try:
    from myquant_infra.lake.duckdb_daily_bars import DuckDBDailyBarsProxy as _InfraDailyBarsProxy
    _INFRA_PROXY = True
except ImportError:  # CI without private pin
    _INFRA_PROXY = False

    class _InfraDailyBarsProxy:  # type: ignore[no-redef]
        """Patchable stub; host subclass must construct without infra."""

        def __init__(self, *args, **kwargs) -> None:
            pass

from common.infra.constants import EnvVarKeys
from common.infra.quant_logger import get_logger
from common.infra.runtime_config import config_value_source, get_raw as _cfg_raw

logger = get_logger(__name__)


class DuckDBDailyBarsProxy(_InfraDailyBarsProxy):
    """BT owns T-1 routing and policy; lake IO goes through StockDataReader."""

    def __init__(
        self, delegate: Any, *, asset_type: Literal["stock", "etf"] = "stock",
        db_path: Optional[str] = None,
    ) -> None:
        if asset_type not in ("stock", "etf"):
            raise ValueError("asset_type must be stock or etf")
        self._delegate = delegate
        self._reader = None
        self._asset_type = asset_type
        self._db_path_override = (db_path or "").strip() or None
        # Keep infra ctor wired when present (reader_factory / previous_trading_day).
        if _INFRA_PROXY:
            super().__init__(
                delegate, reader_factory=self._get_reader,
                previous_trading_day=self._previous_trading_day_str,
            )
        else:
            super().__init__()

    @staticmethod
    def _previous_trading_day_str() -> str:
        from oskh_data.freshness import get_previous_trading_day
        return get_previous_trading_day()

    def _get_reader(self):
        if self._reader is None:
            from oskh_data.reader import StockDataReader

            if self._db_path_override and Path(self._db_path_override).is_file():
                self._reader = StockDataReader(
                    mode="duckdb_persistent",
                    db_path=self._db_path_override,
                    asset_type=self._asset_type,
                )
                cfg_src = "ctor_db_path"
                db_path = self._db_path_override
            else:
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
        try:
            from oskh_data.freshness import get_previous_trading_day
            prev = get_previous_trading_day()
            return date_str <= prev
        except Exception as _fresh_exc:
            logger.warning(
                "get_previous_trading_day failed; conservatively assuming T-1 or earlier",
                context={"error": repr(_fresh_exc)},
            )
            return True

    def _df_to_bars_response(self, df: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        # Slim-fork BT has no oskh_core.fund_daily_bars_serialize; keep a local
        # YYYYMMDD bar list compatible with decision-market responses.
        if df is None or df.empty:
            return {"ok": True, "data": {"bars": [], "symbol": symbol}}

        frame = df.copy()
        if "time" in frame.columns:
            frame["_date"] = pd.to_datetime(frame["time"], unit="ms").dt.strftime("%Y%m%d")
            frame = frame.set_index("_date")
        elif not isinstance(frame.index, pd.Index) or frame.index.dtype == object:
            try:
                frame.index = pd.to_datetime(frame.index).strftime("%Y%m%d")
            except (TypeError, ValueError):
                frame.index = pd.Index([str(x) for x in frame.index])
        if "symbol" in frame.columns:
            frame = frame.drop(columns=["symbol"])

        bars = []
        for idx, row in frame.iterrows():
            lab = "".join(c for c in str(idx) if c.isdigit())[:8]
            if len(lab) != 8:
                continue
            try:
                close_v = float(row["close"])
            except (KeyError, TypeError, ValueError):
                continue
            bar = {"date": lab, "close": close_v}
            for key in ("open", "high", "low", "volume", "amount"):
                if key not in frame.columns:
                    continue
                try:
                    bar[key] = int(row[key]) if key == "volume" else float(row[key])
                except (TypeError, ValueError):
                    continue
            bars.append(bar)
        return {"ok": True, "data": {"bars": bars, "symbol": symbol}}

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
            except Exception as exc:
                if "DataAccessPolicyError" in str(exc):
                    raise
                logger.exception(
                    "DuckDB query failed for %s, falling back to QMT",
                    symbol,
                    context={"symbol": symbol, "start": start_date, "end": end_date},
                )
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
        return self.stock_daily_bars(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            trace_id=trace_id,
            timeout_sec=timeout_sec,
            poll_sec=poll_sec,
        )

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)
