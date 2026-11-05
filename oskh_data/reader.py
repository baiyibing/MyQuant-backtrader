"""BT policy/configuration facade over the pinned MyQuant-infra lake reader.

IO, SQL, connections and result normalization belong to infra. BT retains its
adjustment gate, path resolvers, freshness policy and stock/ETF API boundary.
See docs/engineering/k18-duckdb-infra-switch-20261105.md.
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from time import perf_counter
from typing import List, Literal, Optional

import pandas as pd
from myquant_infra.bars.duckdb_build import rebuild_front_duckdb as _rebuild_front_duckdb
from myquant_infra.lake.paths import asset_period_root as _asset_period_root
from myquant_infra.lake.readers import MINUTE_PERIODS, StockDataReader as _InfraStockDataReader

from common.infra.quant_logger import get_logger
from common.infra.data_root import resolve_data_root as _resolve_data_root
from common.infra.data_root import resolve_e_stock_data_container as _resolve_e_stock_data_container
from common.infra.data_root import resolve_parquet_container as _resolve_parquet_container
from common.infra.data_root import resolve_etf_daily_root as _resolve_etf_daily_root
from common.infra.data_root import resolve_period_root as _resolve_period_root
from oskh_data.pandas_typing import index_normalize_series, normalize_timestamp, timestamp_strftime
from oskh_data.symbol_format import to_partition_key

logger = get_logger(__name__)

# 需要复权防误用校验的模块前缀
_RESTRICTED_MODULE_PREFIXES = ('live_trading.', 'trade_decision.')
# 允许使用非 none 复权类型的白名单模块
_ADJUST_WHITELIST_MODULES: tuple[str, ...] = (
    'live_trading.indicators.ma_provider',
)

def _resolve_default_mode() -> str:
    """按优先级解析默认 mode: 环境变量 > config/reader.yaml > parquet."""
    from common.infra.constants import EnvVarKeys

    env_val = os.environ.get(EnvVarKeys.OSKH_DATA_READER_MODE) or os.environ.get("STOCK_DATA_READER_MODE")
    if env_val:
        return env_val
    try:
        import yaml

        config_path = _resolve_data_root() / "config" / "reader.yaml"
        if config_path.exists():
            with open(config_path, "r") as f:
                cfg = yaml.safe_load(f) or {}
            yaml_val = cfg.get("mode")
            if yaml_val:
                return yaml_val
    except Exception as _yml_exc:
        # Phase 2 P2: log YAML config error instead of silent fallback
        logger.warning(
            "reader.yaml load failed, falling back to parquet mode",
            context={"error": str(_yml_exc)[:200]},
        )
    return "parquet"


DEFAULT_READER_MODE = _resolve_default_mode()


def _get_caller_module() -> str:
    """向上遍历调用栈，跳过 host / infra 中间层，
    返回第一个业务层模块名。找不到返回空字符串。"""
    for i in range(1, 11):  # max_depth=10
        try:
            frame = sys._getframe(i)
        except ValueError:
            break
        mod = frame.f_globals.get('__name__', '')
        if mod.startswith(('oskh_data.', 'common.integrations.', 'myquant_infra.lake.')):
            continue
        return mod
    return ''


def _enforce_adjust_type_policy(adjust_type: str) -> None:
    """复权防误用运行时校验。

    交易热路径（live_trading.* / trade_decision.*）必须使用 adjust_type="none"，
    白名单模块（如 MA 指标提供者）除外。若调用方未找到且 adjust_type != "none"，
    保守拒绝。
    """
    if adjust_type == 'none':
        return
    caller = _get_caller_module()
    if not caller:
        raise RuntimeError(
            "DataAccessPolicyError: cannot verify caller module "
            f"for non-none adjust_type='{adjust_type}'"
        )
    for prefix in _RESTRICTED_MODULE_PREFIXES:
        if caller.startswith(prefix) and caller not in _ADJUST_WHITELIST_MODULES:
            logger.error(
                "adjust_type_policy_violation",
                context={
                    "caller_module": caller,
                    "adjust_type": adjust_type,
                    "policy": "交易热路径必须使用 adjust_type='none'",
                },
            )
            raise RuntimeError(
                f"DataAccessPolicyError: live_trading/trade_decision modules "
                f"must use adjust_type='none', got '{adjust_type}' "
                f"from caller '{caller}'"
            )


class StockDataReader(_InfraStockDataReader):
    """Host gates and paths; every storage operation is inherited from infra."""

    def __init__(
        self,
        base_dir: Optional[str] = None,
        mode: Optional[str] = None,
        db_path: Optional[str] = None,
        project_root: Optional[str] = None,
        asset_type: Literal["stock", "etf"] = "stock",
    ) -> None:
        if asset_type not in ("stock", "etf"):
            raise ValueError("asset_type must be stock or etf")
        self._project_root = _resolve_data_root(explicit_root=project_root)
        self._explicit_base_dir = Path(base_dir) if base_dir else None
        self._e_container = self._explicit_base_dir if base_dir else _resolve_e_stock_data_container(
            explicit_root=project_root,
        )
        self._parquet_container = self._explicit_base_dir if base_dir else _resolve_parquet_container()
        super().__init__(
            base_dir=self._parquet_container, db_dir=self._e_container,
            mode=mode or DEFAULT_READER_MODE, db_path=db_path, asset_type=asset_type,
        )

    def _lake_period_root(self, period: str) -> Path:
        """Keep BT resolver precedence and the ETF tree's isolation from stocks."""
        if self._asset_type == "etf":
            if self._explicit_base_dir is not None or period != "1d":
                return _asset_period_root(self._parquet_container, "etf", period)
            return _resolve_etf_daily_root()
        if self._explicit_base_dir is not None:
            return _resolve_period_root(period, base=self._explicit_base_dir)
        return _resolve_period_root(period)

    def _period_dir(self, period: str, adjust: str) -> Path:
        # Infra's path hook; no IO or SQL in this host facade.
        return self._lake_period_root(period) / f"dividend_type={adjust}"

    def _make_path(self, stock_code: str, period: str, adjust_type: str) -> Path:
        return self._period_dir(period, adjust_type) / f"symbol={to_partition_key(stock_code)}" / "data.parquet"

    def read_stock(
        self, stock_code: str, start_time: Optional[str] = None,
        end_time: Optional[str] = None, period: str = "1d",
        adjust_type: str = "front", columns: Optional[List[str]] = None,
        as_of_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        if as_of_date is not None:
            raise NotImplementedError("StockDataReader.read_stock(as_of_date=...) is not implemented; latest factors can introduce look-ahead bias")
        # #563: enforce the requested adjustment BEFORE infra coerces minutes.
        _enforce_adjust_type_policy(adjust_type)
        return super().read_stock(stock_code, start_time, end_time, period, adjust_type, columns)

    def scan_stocks(
        self, stock_codes: Optional[List[str]] = None,
        start_time: Optional[str] = None, end_time: Optional[str] = None,
        period: str = "1d", adjust_type: str = "front",
        columns: Optional[List[str]] = None, as_of_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        if as_of_date is not None:
            raise NotImplementedError("StockDataReader.scan_stocks(as_of_date=...) is not implemented; latest factors can introduce look-ahead bias")
        _enforce_adjust_type_policy(adjust_type)
        return super().scan_stocks(stock_codes, start_time, end_time, period, adjust_type, columns)

    @staticmethod
    def build_persistent_db(
        base_dir: Optional[str] = None, db_path: Optional[str] = None,
        period: str = "1d", adjust_type: str = "front", max_backups: int = 2,
        asset_type: Literal["stock", "etf"] = "stock",
    ):
        """Explicit daily-front rebuild; infra owns validation/atomic publication.

        The legacy default max_backups argument is accepted for call compatibility;
        infra retains the previous DB on failure and does not create .bak files.
        """
        if period != "1d" or adjust_type != "front" or asset_type not in ("stock", "etf"):
            raise ValueError("only daily stock/ETF front rebuild is supported; minute persistent rebuild is retired")
        if max_backups != 2:
            raise ValueError("max_backups retention is not supported by the infra builder")
        with StockDataReader(base_dir=base_dir, mode="parquet", asset_type=asset_type) as reader:
            output = Path(db_path) if db_path else reader._e_container / (
                "stock_data_etf_front.duckdb" if asset_type == "etf" else "stock_data_front.duckdb"
            )
            started = perf_counter()
            _rebuild_front_duckdb(reader._lake_period_root(period), output)
            return output, perf_counter() - started

    def validate_freshness(
        self,
        stock_code: str,
        target_date: str,
        period: str = '1d',
        adjust_type: str = 'front',
        min_trading_days: int = 1,
    ) -> tuple[bool, str]:
        """检查指定股票在目标日期的数据是否可用。

        在计算任何依赖数据的指标前必须先调用此方法。
        不会静默返回过时数据——数据不覆盖目标日期时返回 False。

        Args:
            stock_code: 股票代码
            target_date: 目标日期 YYYYMMDD
            period: 数据周期
            adjust_type: 复权类型
            min_trading_days: 最少需要的交易日数（如 80 天窗口需要 >= 80）

        Returns:
            (is_fresh, message): True 表示数据可用，False 表示数据缺失或不足
        """
        target_ts = pd.Timestamp(target_date)
        df = self.read_stock(
            stock_code,
            start_time=timestamp_strftime(target_ts - pd.Timedelta(days=400), '%Y%m%d'),
            end_time=target_date,
            period=period,
            adjust_type=adjust_type,
        )

        if df is None or df.empty:
            return False, f"{stock_code}: {period}/{adjust_type} 返回空数据"

        df = df.sort_index()
        max_date = normalize_timestamp(df.index.max())

        if max_date < target_ts:
            return False, (
                f"{stock_code}: {period}/{adjust_type} 最新日期为 {timestamp_strftime(max_date, '%Y-%m-%d')}，"
                f"不覆盖目标日期 {target_date}"
            )

        window_start = timestamp_strftime(target_ts - pd.Timedelta(days=400), '%Y-%m-%d')
        window_end = timestamp_strftime(min(target_ts, max_date), '%Y-%m-%d')
        try:
            from common.infra.trading_calendar_pmc import get_trade_days_sse

            since_s = timestamp_strftime(window_start, "%Y%m%d")
            until_s = timestamp_strftime(window_end, "%Y%m%d")
            cal_df = get_trade_days_sse(since=since_s, until=until_s)
            expected_trading_days = 0 if cal_df is None else int(len(cal_df))
        except Exception as exc:
            logger.warning(
                "validate_freshness: SSE calendar fallback to index unique_days",
                context={"error": str(exc)[:200]},
            )
            expected_trading_days = len(index_normalize_series(df.index).unique())

        if expected_trading_days < min_trading_days:
            return False, (
                f"{stock_code}: {period}/{adjust_type} 窗口内仅 {expected_trading_days} 个 SSE 交易日，"
                f"不足最小要求 {min_trading_days} 天"
            )

        return True, (
            f"{stock_code}: {period}/{adjust_type} 覆盖 {target_date}"
            f"（{expected_trading_days} 个 SSE 交易日）"
        )

_LAZY_PREV_CLOSE_READER: Optional[StockDataReader] = None
_LAZY_PREV_CLOSE_ETF_READER: Optional[StockDataReader] = None
_LAZY_PREV_CLOSE_READER_LOCK = threading.Lock()


def lazy_prev_close_reader(asset_type: str = "stock") -> Optional[StockDataReader]:
    """Thread-safe singleton for limit_info / gap_down DuckDB ``none`` reads.

    Phase 2 P0 fix: accepts ``asset_type`` to route ETF codes to
    ``stock_data_etf_none.duckdb`` (separate from stock DuckDB).
    """
    if asset_type not in ("stock", "etf"):
        raise ValueError("asset_type must be stock or etf")
    global _LAZY_PREV_CLOSE_READER, _LAZY_PREV_CLOSE_ETF_READER
    if asset_type == "etf":
        if _LAZY_PREV_CLOSE_ETF_READER is not None:
            return _LAZY_PREV_CLOSE_ETF_READER
        with _LAZY_PREV_CLOSE_READER_LOCK:
            if _LAZY_PREV_CLOSE_ETF_READER is None:
                try:
                    _LAZY_PREV_CLOSE_ETF_READER = StockDataReader(
                        mode="duckdb_persistent", asset_type="etf",
                    )
                except FileNotFoundError:
                    # ETF DuckDB may not exist if etf_backfill hasn't been run.
                    # Return None to signal "no ETF data available" — callers
                    # should handle this gracefully (e.g., skip ETF prev_close).
                    return None
        return _LAZY_PREV_CLOSE_ETF_READER
    if _LAZY_PREV_CLOSE_READER is not None:
        return _LAZY_PREV_CLOSE_READER
    with _LAZY_PREV_CLOSE_READER_LOCK:
        if _LAZY_PREV_CLOSE_READER is None:
            _LAZY_PREV_CLOSE_READER = StockDataReader(mode="duckdb_persistent")
    return _LAZY_PREV_CLOSE_READER


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="StockDataReader CLI — daily front rebuild via MyQuant-infra")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--period", default="1d", choices=["1d", "1m", "all"])
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--adjust-type", default="front", choices=["none", "front", "back"])
    args = parser.parse_args()
    if args.build:
        output, elapsed = StockDataReader.build_persistent_db(
            base_dir=args.data_dir, db_path=args.db_path,
            period=args.period, adjust_type=args.adjust_type,
        )
        print(f"{output}: {output.stat().st_size / (1024 * 1024):.0f} MB in {elapsed:.1f}s")
    else:
        parser.print_help()
