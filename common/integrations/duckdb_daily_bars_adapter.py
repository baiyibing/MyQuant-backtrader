"""BT reader/configuration composition over infra's daily bars proxy."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

from myquant_infra.lake.duckdb_daily_bars import DuckDBDailyBarsProxy as _InfraDailyBarsProxy
from common.infra.constants import EnvVarKeys
from common.infra.quant_logger import get_logger
from common.infra.runtime_config import config_value_source, get_raw as _cfg_raw

logger = get_logger(__name__)


def _previous_trading_day() -> str:
    # Session/calendar policy remains BT-owned and is resolved at call time.
    from oskh_data.freshness import get_previous_trading_day

    return get_previous_trading_day()


class DuckDBDailyBarsProxy(_InfraDailyBarsProxy):
    def __init__(
        self, delegate: Any, *, asset_type: Literal["stock", "etf"] = "stock",
        db_path: Optional[str] = None,
    ) -> None:
        if asset_type not in ("stock", "etf"):
            raise ValueError("asset_type must be stock or etf")
        self._asset_type = asset_type
        self._db_path_override = (db_path or "").strip() or None
        super().__init__(
            delegate, reader_factory=self._create_reader,
            previous_trading_day=_previous_trading_day,
        )

    def _create_reader(self):
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
