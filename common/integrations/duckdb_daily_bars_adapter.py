"""BT reader/configuration composition over myquant-infra daily bars.

BT supplies configured readers and a T-1 date; infra owns routing and serialization.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional


from myquant_infra.lake.duckdb_daily_bars import DuckDBDailyBarsProxy as _InfraDailyBarsProxy

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
        super().__init__(
            delegate, reader_factory=self._get_reader,
            previous_trading_day=self._previous_trading_day_str,
        )

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
    ) -> dict[str, Any]:
        """Preserve the host's explicit keyword-only compatibility signature."""
        return super().stock_daily_bars_cfg_only(
            symbol=symbol, start_date=start_date, end_date=end_date, adjust=adjust,
            trace_id=trace_id, timeout_sec=timeout_sec, poll_sec=poll_sec,
        )
