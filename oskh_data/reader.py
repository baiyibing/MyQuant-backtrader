"""
统一股票数据读取层，支持三种模式：
  parquet          — pd.read_parquet() 逐文件读取（默认，兼容回退）
  duckdb           — DuckDB :memory: + read_parquet(glob) 批量扫描
  duckdb_persistent — DuckDB 连接 .duckdb 持久化文件 + 查表

  配置优先级: 环境变量 STOCK_DATA_READER_MODE > config/reader.yaml > 默认 parquet

  复权类型按物理分文件隔离:
  stock_data_none.duckdb / stock_data_front.duckdb / stock_data_back.duckdb
"""
from __future__ import annotations
from .symbol_format import to_partition_key, to_canonical_symbol

import os
import sys
import threading
import time
from pathlib import Path
from typing import List, Literal, Optional

import duckdb
import pandas as pd

from oskh_data.pandas_typing import as_timestamp, index_normalize_series, normalize_timestamp, timestamp_strftime

from common.infra.quant_logger import get_logger
from common.infra.data_root import resolve_data_root as _resolve_data_root
from common.infra.data_root import resolve_e_stock_data_container as _resolve_e_stock_data_container
from common.infra.data_root import resolve_parquet_container as _resolve_parquet_container
from common.infra.data_root import resolve_period_root as _resolve_period_root

logger = get_logger(__name__)

MINUTE_PERIODS = frozenset({'1m', '5m', '10m', '15m', '30m', '1h'})

# 核心 ETF 代码段正则（防呆用，避免 asset_type="stock" 时误读 ETF 数据）
# Phase 2 P1 fix: added missing Shanghai ETF prefixes 516, 517, 520, 562, 589
_ETF_CODE_PATTERN = (
    r'^(510|511|512|513|515|516|517|518|520|560|561|562|563|588|589|159)\d{3}$'
)

# 复权类型 → DuckDB 文件后缀映射
_ADJUST_DB_SUFFIX: dict[str, str] = {
    'none': '_none',
    'front': '_front',
    'back': '_back',
}

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


def _parse_time(t: str) -> int:
    """将 '20240101' 或 '20240101093000' 转为毫秒 epoch."""
    ts = as_timestamp(t)
    if pd.isna(ts):
        raise ValueError(f"Cannot parse time: {t}")
    return int(ts.timestamp() * 1000)


def _get_caller_module() -> str:
    """向上遍历调用栈，跳过 oskh_data.* / common.integrations.* 中间层，
    返回第一个业务层模块名。找不到返回空字符串。"""
    for i in range(1, 11):  # max_depth=10
        try:
            frame = sys._getframe(i)
        except ValueError:
            break
        mod = frame.f_globals.get('__name__', '')
        if mod.startswith('oskh_data.') or mod.startswith('common.integrations.'):
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


class StockDataReader:
    """统一股票数据读取层."""

    def __init__(
        self,
        base_dir: Optional[str] = None,
        mode: Optional[str] = None,
        db_path: Optional[str] = None,
        project_root: Optional[str] = None,
        asset_type: Literal["stock", "etf"] = "stock",
    ) -> None:
        self._project_root = _resolve_data_root(explicit_root=project_root)
        if base_dir:
            self._e_container = Path(base_dir)
            self._parquet_container = Path(base_dir)
        else:
            self._e_container = _resolve_e_stock_data_container(
                explicit_root=project_root
            )
            self._parquet_container = _resolve_parquet_container()
        # DuckDB 与运营文件仍在 E 容器；parquet hive 经 _parquet_container + resolver。
        self._base_dir = self._e_container
        self._etf_parquet_dir = (
            self._parquet_container / "etf" if asset_type == "etf" else None
        )
        self._mode: str = mode or DEFAULT_READER_MODE
        if self._mode not in ('parquet', 'duckdb', 'duckdb_persistent'):
            raise ValueError(f"Invalid mode: {self._mode}. Use parquet | duckdb | duckdb_persistent")

        self._asset_type: Literal["stock", "etf"] = asset_type
        self._con = None
        self._con_minute = None
        self._style = None
        self._closed = False
        self._last_query_error: Optional[str] = None  # Phase 2 P1

        if self._mode == 'duckdb':
            self._con = duckdb.connect(':memory:')
        elif self._mode == 'duckdb_persistent':
            self._db_path = self._resolve_db_path(db_path)
            if not self._db_path.exists():
                # Phase 2 P1 fix: duckdb_persistent mode must fail fast when
                # the DB file is missing.  Silent fallback to :memory: (old
                # behavior) caused all queries to return empty results —
                # indistinguishable from "stock has no data", leading to
                # silent data incompleteness in backtest / strategy validation.
                raise FileNotFoundError(
                    f"DuckDB persistent file not found: {self._db_path}. "
                    f"Run oskh_data backfill first, or use mode='duckdb' for "
                    f"in-memory exploratory queries."
                )
            self._con = duckdb.connect(str(self._db_path), read_only=True)

    def _ensure_connection(self) -> bool:
        """检测 DuckDB 连接活性，失效时自动重建。

        多进程场景（fork 后）连接对象可能失效，需要检测并重建。
        返回 True 表示连接可用。
        """
        if self._mode not in ('duckdb', 'duckdb_persistent'):
            return True  # parquet 模式不需要连接
        if self._con is None:
            return False

        try:
            # 轻量心跳检测
            self._con.execute("SELECT 1")
            return True
        except Exception:
            logger.warning("DuckDB connection stale, reconnecting...")
            try:
                if not self._closed:
                    try:
                        self._con.close()
                    except Exception:
                        pass
                self._closed = False
                if self._mode == 'duckdb_persistent' and hasattr(self, '_db_path'):
                    if self._db_path.exists():
                        self._con = duckdb.connect(str(self._db_path), read_only=True)
                    else:
                        # Phase 2 P1 fix: persistent DB file vanished mid-session
                        # (e.g., external deletion, mount unmount).  Fail fast
                        # instead of silently downgrading to :memory: — an empty
                        # in-memory DB returns results indistinguishable from
                        # "stock has no data".
                        raise FileNotFoundError(
                            f"DuckDB persistent file disappeared: {self._db_path}. "
                            f"Restart the process or restore the DB file."
                        )
                else:
                    self._con = duckdb.connect(':memory:')
                self._con.execute("SELECT 1")
                return True
            except Exception:
                logger.exception("DuckDB reconnection failed")
                self._con = None
                return False

    def _resolve_db_path(self, db_path: Optional[str]) -> Path:
        """根据 asset_type 和 adjust_type 返回 DuckDB 文件路径。

        ETF: stock_data_etf_none.duckdb（默认探测）/ stock_data_etf_front.duckdb
        个股: stock_data_front.duckdb（默认优先）> stock_data.duckdb > stock_data_none.duckdb
        默认（无 adjust_type 上下文时）: 自动探测可用的 DuckDB，避免因 stock_data.duckdb
        不存在而静默降级到 :memory: 模式读取可能过期的 Parquet 文件。
        """
        if db_path:
            return Path(db_path)
        if self._asset_type == 'etf':
            # Align with etf_backfill + _adjust_db_path (never stock_data_etf.duckdb typo).
            for name in (
                'stock_data_etf_none.duckdb',
                'stock_data_etf_front.duckdb',
            ):
                candidate = self._base_dir / name
                if candidate.exists():
                    return candidate
            return self._base_dir / 'stock_data_etf_none.duckdb'
        # 自动探测：优先 front（最常用），其次兼容旧名，再次 none
        candidates = [
            self._base_dir / 'stock_data_front.duckdb',
            self._base_dir / 'stock_data.duckdb',
            self._base_dir / 'stock_data_none.duckdb',
        ]
        for c in candidates:
            if c.exists():
                return c
        return self._base_dir / 'stock_data.duckdb'  # 都不存在时保持兼容，由调用方处理

    def _adjust_db_path(self, adjust_type: str) -> Optional[Path]:
        """按复权类型返回对应 DuckDB 文件路径。

        ETF: none → stock_data_etf_none.duckdb；front → stock_data_etf_front.duckdb。
        个股按 none/front/back 分文件：stock_data_none.duckdb / stock_data_front.duckdb / ...
        """
        if self._asset_type == 'etf':
            adj = str(adjust_type or 'none').strip().lower()
            if adj == 'front':
                return self._base_dir / 'stock_data_etf_front.duckdb'
            return self._base_dir / 'stock_data_etf_none.duckdb'
        suffix = _ADJUST_DB_SUFFIX.get(adjust_type, '_none')
        return self._base_dir / f'stock_data{suffix}.duckdb'

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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

    def read_stock(
        self,
        stock_code: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        period: str = '1d',
        adjust_type: str = 'front',
        columns: Optional[List[str]] = None,
        as_of_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """读取单只股票数据。

        Args:
            as_of_date: 可选，YYYYMMDD 格式。指定时仅使用该日期前已生效的复权因子，
                       防止回测中的前瞻性偏差（look-ahead bias）。
                       None 时使用最新复权因子（live trading 模式）。
        """
        if as_of_date is not None:
            raise NotImplementedError(
                "StockDataReader.read_stock(as_of_date=...) is not implemented yet; "
                "using it would silently assume latest-adjusted data and can introduce look-ahead bias."
            )
        if self._asset_type == 'stock':
            _enforce_adjust_type_policy(adjust_type)
        if period in MINUTE_PERIODS:
            adjust_type = 'none'

        if self._mode == 'duckdb_persistent':
            if not self._ensure_connection():
                return self._read_stock_parquet(stock_code, start_time, end_time,
                                                period, adjust_type, columns)
            con = self._get_persistent_con(period, adjust_type)
            if con is None:
                return self._read_stock_parquet(stock_code, start_time, end_time,
                                                period, adjust_type, columns)
            return self._read_stock_persistent(stock_code, start_time, end_time, columns, con)
        else:
            return self._read_stock_parquet(stock_code, start_time, end_time,
                                            period, adjust_type, columns)

    def scan_stocks(
        self,
        stock_codes: Optional[List[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        period: str = '1d',
        adjust_type: str = 'front',
        columns: Optional[List[str]] = None,
        as_of_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """批量读取多只股票数据。stock_codes=None 时扫描全市场。

        Args:
            as_of_date: 可选，YYYYMMDD 格式。指定时仅使用该日期前已生效的复权因子。
        """
        if as_of_date is not None:
            raise NotImplementedError(
                "StockDataReader.scan_stocks(as_of_date=...) is not implemented yet; "
                "using it would silently assume latest-adjusted data and can introduce look-ahead bias."
            )
        if period in MINUTE_PERIODS:
            adjust_type = 'none'

        if self._mode == 'parquet':
            return self._scan_parquet(stock_codes, start_time, end_time,
                                      period, adjust_type, columns)
        elif self._mode == 'duckdb':
            if period in MINUTE_PERIODS:
                return self._scan_parquet(stock_codes, start_time, end_time,
                                          period, adjust_type, columns)
            return self._scan_duckdb(stock_codes, start_time, end_time,
                                     period, adjust_type, columns)
        elif self._mode == 'duckdb_persistent':
            if not self._ensure_connection():
                return self._scan_parquet(stock_codes, start_time, end_time,
                                          period, adjust_type, columns)
            con = self._get_persistent_con(period, adjust_type)
            if con is None:
                return self._scan_parquet(stock_codes, start_time, end_time,
                                          period, adjust_type, columns)
            return self._scan_persistent(stock_codes, start_time, end_time, columns, con)
        return None

    @staticmethod
    def build_persistent_db(
        base_dir: Optional[str] = None,
        db_path: Optional[str] = None,
        period: str = '1d',
        adjust_type: str = 'front',
        max_backups: int = 2,
    ):
        """原子发布构建 .duckdb 文件。

        流程: staging → validate → os.replace 原子切换 → 旧版本备份。

        period='1d':
          - none → stock_data_none.duckdb
          - front → stock_data_front.duckdb
          - back → stock_data_back.duckdb
        period='1m' → :memory: + read_parquet(glob) 视图（不再使用持久化 .duckdb）
        """
        project_root = _resolve_data_root()
        base = (
            Path(base_dir)
            if base_dir
            else _resolve_parquet_container(explicit_root=project_root)
        )
        suffix = _ADJUST_DB_SUFFIX.get(adjust_type, '_none')
        db = Path(db_path) if db_path else (
            base / f'stock_data{"_minute" if period == "1m" else ""}{suffix if period != "1m" else ""}.duckdb'
        )
        staging = db.with_name(db.stem + '_staging' + db.suffix)

        # ── 磁盘水位检查 ──
        _check_disk_watermark(db.parent)

        style = _detect_style(base, period, adjust_type)
        period_dir = _resolve_period_root(period, base=base) / f'dividend_type={adjust_type}'
        glob_pattern = str(period_dir / '*' / 'data.parquet').replace('\\', '/')
        _validate_parquet_schema_consistency(base, period=period, adjust_type=adjust_type)

        t0 = time.perf_counter()

        # ── 1. 构建到 staging ──
        if staging.exists():
            staging.unlink()
        con = duckdb.connect(str(staging))
        # Pandas leftover __index_level_0__ may be absent (post CST→UTC repair writes
        # preserve_index=False) or present with drifting types (BIGINT vs TIMESTAMP_NS).
        # SELECT * + union_by_name=True fails to cast conflicting types during union;
        # EXCLUDE avoids that, but EXCLUDE errors when the column is missing from ALL
        # files — so probe the schema and conditionally exclude.
        import pyarrow.parquet as _pq
        _sample_files = sorted(period_dir.glob("symbol=*/data.parquet"))
        _has_index_col = any(
            "__index_level_0__" in _pq.read_schema(_p).names for _p in _sample_files
        )
        _select_clause = "SELECT * EXCLUDE (__index_level_0__)" if _has_index_col else "SELECT *"
        con.execute(f"""
            CREATE TABLE stock_data AS
            {_select_clause}
            FROM read_parquet(
                '{glob_pattern}',
                hive_partitioning=1,
                union_by_name=True
            )
        """)
        col_names = {
            str(r[0]) for r in con.execute("DESCRIBE stock_data").fetchall()
        }
        if "__index_level_0__" in col_names:
            con.execute('ALTER TABLE stock_data DROP COLUMN "__index_level_0__"')
        if style == 'underscore':
            con.execute("UPDATE stock_data SET symbol = REPLACE(symbol, '_', '.')")
        con.execute("CREATE INDEX idx_symbol ON stock_data(symbol)")

        # ── 2. 校验 staging ──
        result = con.execute("SELECT COUNT(*) FROM stock_data").fetchone()
        row_count = result[0] if result else 0
        con.close()
        if row_count == 0:
            staging.unlink()
            raise RuntimeError(f"Staging validation failed: {staging} has 0 rows")

        # ── Schema 版本检查（log warning，不强阻断） ──
        _check_schema_version(staging)

        # ── 3. 备份旧版本 ──
        if db.exists():
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            backup = db.with_name(f'{db.stem}.bak.{timestamp}{db.suffix}')
            db.rename(backup)
            logger.info(f"Backed up previous version: {backup.name}")

        # ── 4. 原子切换（同卷 os.replace） ──
        os.replace(str(staging), str(db))
        elapsed = time.perf_counter() - t0

        size_mb = db.stat().st_size / (1024 * 1024)
        logger.info(
            f"Atomic publish OK: {db} ({size_mb:.0f} MB, {row_count} rows) in {elapsed:.1f}s"
        )

        # ── 5. 清理旧备份（保留最近 max_backups 个） ──
        _prune_backups(db, max_backups)

        return db, elapsed

    def close(self) -> None:
        """关闭 DuckDB 连接."""
        if self._con is not None and not self._closed:
            self._con.close()
        if self._con_minute is not None:
            self._con_minute.close()
        self._closed = True

    # ------------------------------------------------------------------
    # Internal: connection routing
    # ------------------------------------------------------------------

    def _get_persistent_con(self, period: str, adjust_type: str = 'front'):
        """返回 period 对应的持久化连接。分钟线使用 :memory: + read_parquet(glob) 视图。"""
        if period in MINUTE_PERIODS:
            if self._con_minute is None:
                import time as _time
                _t0 = _time.perf_counter()
                con = duckdb.connect(':memory:')
                base = self._etf_parquet_dir if self._etf_parquet_dir is not None else self._parquet_container
                glob_pattern = str(
                    _resolve_period_root('1m', base=base) / 'dividend_type=none' / 'symbol=*' / 'data.parquet'
                ).replace('\\', '/')
                con.execute(f"""
                    CREATE VIEW stock_data AS
                    SELECT REPLACE(symbol, '_', '.') AS symbol,
                           time, open, high, low, close, volume, amount
                    FROM read_parquet('{glob_pattern}',
                                      hive_partitioning=1, union_by_name=True)
                """)
                _elapsed = _time.perf_counter() - _t0
                _row = con.execute('SELECT COUNT(*) FROM stock_data').fetchone()
                _cnt = _row[0] if _row else 0
                logger.info(
                    f"Minute :memory: view created: {_cnt:,} rows, {_elapsed:.1f}s"
                )
                self._con_minute = con
            return self._con_minute
        # 日线：按复权类型选择文件
        adjust_db = self._adjust_db_path(adjust_type)
        if adjust_db is None:
            return self._con
        if not adjust_db.exists():
            logger.warning(
                f"Persistent DB not found for adjust_type={adjust_type} ({adjust_db}); falling back to parquet for correctness"
            )
            return None
        if adjust_db == self._db_path:
            return self._con
        return duckdb.connect(str(adjust_db), read_only=True)

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal: parquet mode
    # ------------------------------------------------------------------

    def _read_stock_parquet(self, stock_code, start_time, end_time,
                            period, adjust_type, columns):
        path = self._make_path(stock_code, period, adjust_type)
        if not path.exists():
            return None
        df = pd.read_parquet(path, columns=columns)
        if start_time and end_time:
            df = self._filter_time_parquet(df, start_time, end_time)
        df['symbol'] = stock_code
        return self._normalize_result_df(df)

    def _scan_parquet(self, stock_codes, start_time, end_time,
                      period, adjust_type, columns):
        if stock_codes is None:
            stock_codes = _load_all_codes(self._parquet_container)
        frames = []
        for code in stock_codes:
            path = self._make_path(code, period, adjust_type)
            if not path.exists():
                continue
            df = pd.read_parquet(path, columns=columns)
            if start_time and end_time:
                df = self._filter_time_parquet(df, start_time, end_time)
            if df is not None and len(df) > 0:
                df['symbol'] = code
                frames.append(df)
        if not frames:
            return None
        # P2-52: 轻量 schema 一致性校验 — pd.concat 前检查关键列 dtype，
        # 防止 dtype 漂移导致 time 列比较静默失效（与 P1-4 同根因）。
        if len(frames) > 1:
            _key_cols = ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']
            ref = frames[0]
            for i, df in enumerate(frames[1:], 1):
                for col in _key_cols:
                    if col in ref.columns and col in df.columns:
                        if ref[col].dtype != df[col].dtype:
                            raise ValueError(
                                f"Parquet schema drift in scan_stocks: column '{col}' "
                                f"dtype mismatch (ref={ref[col].dtype} vs "
                                f"frame[{i}]={df[col].dtype}). "
                                f"Run build_persistent_db or re-download affected stocks."
                            )
        return self._normalize_result_df(pd.concat(frames, ignore_index=False))

    # ------------------------------------------------------------------
    # Internal: duckdb mode (read_parquet glob)
    # ------------------------------------------------------------------

    def _scan_duckdb(self, stock_codes, start_time, end_time,
                     period, adjust_type, columns):
        self._ensure_style(period, adjust_type)
        base = self._etf_parquet_dir if self._etf_parquet_dir is not None else self._parquet_container
        glob = str(_resolve_period_root(period, base=base) /
                   f'dividend_type={adjust_type}' / '*' / 'data.parquet').replace('\\', '/')

        symbol_expr = self._symbol_expr()

        parts = [f"SELECT {symbol_expr} AS symbol, time"]
        if columns:
            for c in columns:
                if c != 'symbol':
                    parts.append(c)
        else:
            parts.append("open, high, low, close, volume, amount")
        select_clause = ", ".join(parts)

        sql = f"{select_clause} FROM read_parquet('{glob}', hive_partitioning=1)"
        conditions = []
        if start_time and end_time:
            conditions.append(f"time BETWEEN {_parse_time(start_time)} AND {_parse_time(end_time)}")
        if stock_codes:
            quoted = ", ".join(f"'{c}'" for c in stock_codes)
            conditions.append(f"{symbol_expr} IN ({quoted})")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        return self._execute_df(sql)

    # ------------------------------------------------------------------
    # Internal: duckdb_persistent mode
    # ------------------------------------------------------------------

    _CORE_COLS = "symbol, time, open, high, low, close, volume, amount"

    def _read_stock_persistent(self, stock_code, start_time, end_time, columns, con):
        col_list = self._CORE_COLS
        if columns:
            col_list = ", ".join(c for c in columns if c in self._CORE_COLS)

        sql = f"SELECT {col_list} FROM stock_data WHERE symbol = '{stock_code}'"
        if start_time and end_time:
            sql += f" AND time BETWEEN {_parse_time(start_time)} AND {_parse_time(end_time)}"
        return self._execute_df(sql, con)

    def _scan_persistent(self, stock_codes, start_time, end_time, columns, con):
        col_list = self._CORE_COLS
        if columns:
            col_list = ", ".join(c for c in columns if c in self._CORE_COLS)

        sql = f"SELECT {col_list} FROM stock_data"
        conditions = []
        if start_time and end_time:
            conditions.append(f"time BETWEEN {_parse_time(start_time)} AND {_parse_time(end_time)}")
        if stock_codes:
            quoted = ", ".join(f"'{c}'" for c in stock_codes)
            conditions.append(f"symbol IN ({quoted})")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        return self._execute_df(sql, con)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_path(self, stock_code, period, adjust_type):
        safe = to_partition_key(stock_code)
        # Phase 2 P0 fix: ETF parquet data is stored under stock_data/etf/
        # (aligned with etf_backfill.py). Stock data uses stock_data/ directly.
        base = self._etf_parquet_dir if self._etf_parquet_dir is not None else self._parquet_container
        return (_resolve_period_root(period, base=base) /
                f'dividend_type={adjust_type}' / f'symbol={safe}' / 'data.parquet')

    def _filter_time_parquet(self, df, start_time, end_time):
        t_min = _parse_time(start_time)
        t_max = _parse_time(end_time)
        mask = (df['time'] >= t_min) & (df['time'] <= t_max)
        return df.loc[mask]

    def _ensure_style(self, period, adjust_type):
        if self._style is None:
            base = self._etf_parquet_dir if self._etf_parquet_dir is not None else self._parquet_container
            self._style = _detect_style(base, period, adjust_type)

    def _symbol_expr(self):
        self._ensure_style('1d', 'front')
        if self._style == 'underscore':
            return "REPLACE(symbol, '_', '.')"
        return 'symbol'

    @staticmethod
    def _build_column_list(columns):
        if not columns:
            return "symbol, time, open, high, low, close, volume, amount"
        return ", ".join(c for c in columns)

    def _execute_df(self, sql, con=None) -> Optional[pd.DataFrame]:
        try:
            if con is None and not self._ensure_connection():
                logger.warning("No DuckDB connection available for query")
                return None
            c = con or self._con
            if c is None:
                logger.warning("No DuckDB connection available for query")
                return None
            result = c.execute(sql).fetchdf()
            if len(result) <= 0:
                return None
            return self._normalize_result_df(result)
        except Exception as _query_exc:
            # Phase 2 P1 fix: store last error so callers can distinguish
            # "query returned empty" from "query failed".  Previously both
            # returned None — callers could not tell if the stock truly has
            # no data or if the DB is corrupted.
            self._last_query_error = f"{type(_query_exc).__name__}: {str(_query_exc)[:200]}"
            logger.exception(
                "DuckDB query failed",
                context={
                    "sql_preview": str(sql)[:200],
                    "error_type": type(_query_exc).__name__,
                },
            )
            return None

    @staticmethod
    def _normalize_result_df(df: pd.DataFrame) -> pd.DataFrame:
        """统一 Reader 输出契约：若存在 time 列，则输出 DatetimeIndex。

        P1-1 fix: 时间戳损坏比例 ≥5% 时抛异常（原 99%），防止残缺数据污染回测。
        任何非零丢弃均记录 warning，确保数据质量可观测。
        """
        if df is None or len(df) <= 0:
            return df
        out = df.copy()
        if "time" in out.columns:
            n_before = len(out)
            ts = pd.to_datetime(out["time"], unit="ms", errors="coerce", utc=True).dt.tz_localize(None)
            valid = ts.notna()
            n_dropped = n_before - valid.sum()
            if n_dropped > 0:
                ratio = n_dropped / n_before
                symbol = str(out.get("symbol", "unknown"))
                # P1-1: 任何非零丢弃都记录 warning（可观测性）
                logger.warning(
                    f"时间戳解析丢弃 {n_dropped}/{n_before} 行 ({ratio * 100:.1f}%)，symbol={symbol}"
                )
                # P1-1: 阈值从 99% 降到 5%
                if ratio >= 0.05:
                    raise ValueError(
                        f"时间戳解析失败: {n_dropped}/{n_before} 行 time 列为无效值 "
                        f"({ratio*100:.1f}%, threshold=5%)，"
                        f"symbol={symbol}，请检查数据源 time 列是否损坏"
                    )
            out = out.loc[valid].copy()
            if len(out) <= 0:
                return out
            out.index = pd.DatetimeIndex(ts.loc[valid], name="datetime")
            out.sort_index(inplace=True)
        return out


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

_DISK_WATERMARK_PCT = 80  # 磁盘水位告警阈值（百分比）
_SCHEMA_VERSION = 1       # 当前支持的 schema 版本


def _check_disk_watermark(parent: Path) -> None:
    """磁盘水位检查（80% 阈值告警，不阻断）。"""
    try:
        import shutil
        usage = shutil.disk_usage(parent)
        pct = (usage.used / usage.total) * 100 if usage.total > 0 else 0
        if pct >= _DISK_WATERMARK_PCT:
            logger.warning(
                f"Disk watermark alert: {pct:.1f}% used on {parent} (threshold {_DISK_WATERMARK_PCT}%)"
            )
    except Exception:
        logger.exception("Disk watermark check failed")


def _check_schema_version(db_path: Path) -> None:
    """Schema 版本检查（log warning，不强阻断）。"""
    try:
        con = duckdb.connect(str(db_path), read_only=True)
        result = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_meta'"
        ).fetchone()
        if result:
            vr = con.execute("SELECT MAX(version) FROM _meta").fetchone()
            version = vr[0] if vr else None
            if version is not None and version < _SCHEMA_VERSION:
                logger.warning(
                    f"Schema version mismatch: DB={version}, supported={_SCHEMA_VERSION}. "
                    "Consider running rebuild_duckdb."
                )
        con.close()
    except Exception:
        logger.exception("Schema version check failed, continuing")


def _prune_backups(db: Path, max_backups: int) -> None:
    """清理旧备份，保留最近 max_backups 个。"""
    stem = db.stem
    parent = db.parent
    backups = sorted(
        parent.glob(f'{stem}.bak.*{db.suffix}'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[max_backups:]:
        try:
            old.unlink()
            logger.info(f"Pruned old backup: {old.name}")
        except OSError:
            pass


def _detect_style(base_dir: Path, period: str, adjust_type: str) -> str:
    full_dir = _resolve_period_root(period) / f'dividend_type={adjust_type}'
    if not full_dir.is_dir():
        return 'underscore'
    all_dirs = [d for d in os.listdir(full_dir) if d.startswith('symbol=')]
    if not all_dirs:
        return 'underscore'
    has_underscore = any('_' in d for d in all_dirs)
    has_dot = any('.' in d and '_' not in d for d in all_dirs)
    if has_underscore and has_dot:
        raise RuntimeError(f"Mixed symbol naming in {full_dir}: "
                           f"{sum(1 for d in all_dirs if '_' in d)} underscore + "
                           f"{sum(1 for d in all_dirs if '.' in d and '_' not in d)} dot")
    return 'underscore' if has_underscore else 'dot'


def _validate_parquet_schema_consistency(base_dir: Path, *, period: str, adjust_type: str) -> None:
    """Fail-close when parquet partition schemas drift vs canonical 1d types.

    Canonical contract (same as ``oskh_data.daily_parquet_write``):
    ``time/volume=int64``, OHLC/amount=float64(``double``).

    Historically compared partitions to the *first* file alphabetically, so a
    single drifted ``symbol=000001_SH`` (volume=double) poisoned the whole
    rebuild with a useless ``data.parquet`` path in the error (2026-08-02).
    """
    import pyarrow.parquet as pq

    from oskh_data.daily_parquet_write import CANONICAL_ARROW_TYPES

    period_dir = _resolve_period_root(period) / f"dividend_type={adjust_type}"
    if not period_dir.is_dir():
        raise RuntimeError(f"Data directory not found for schema validation: {period_dir}")

    files = sorted(period_dir.glob("symbol=*/data.parquet"))
    if not files:
        raise RuntimeError(f"No parquet files found for schema validation: {period_dir}")

    required_cols = ("time", "open", "high", "low", "close", "volume")
    expected = {col: str(CANONICAL_ARROW_TYPES[col]) for col in required_cols}
    drifted: list[str] = []
    for p in files:
        schema = pq.read_schema(p)
        names = set(schema.names)
        missing = set(required_cols) - names
        label = p.parent.name  # symbol=XXXXXX_XX
        if missing:
            raise RuntimeError(
                f"Schema validation failed: required columns missing in {label}: "
                f"{sorted(missing)}"
            )
        current_types = {col: str(schema.field(col).type) for col in required_cols}
        mismatched = {
            col: (expected[col], current_types[col])
            for col in required_cols
            if expected[col] != current_types[col]
        }
        if mismatched:
            drifted.append(f"{label}: {mismatched}")
            if len(drifted) >= 8:
                break
    if drifted:
        sample = "; ".join(drifted)
        raise RuntimeError(
            "Schema validation failed: column type drift vs canonical "
            f"(time/volume=int64, OHLC=double) in {period}/{adjust_type}: {sample}. "
            "Repair: "
            "scripts/data/repair_daily_parquet_schema.py "
            f"--period {period} --adjust-type {adjust_type} --apply "
            "then rebuild --period 1d / --resume"
        )


def _load_all_codes(base_dir: Path) -> List[str]:
    from common.infra.data_root import resolve_period_root, resolve_source_parquet

    fs_path = resolve_source_parquet('float_shares.parquet')
    if fs_path.exists():
        return pd.read_parquet(fs_path)['stock_code'].tolist()
    period_dir = resolve_period_root('1d') / 'dividend_type=front'
    if period_dir.is_dir():
        codes = []
        for d in os.listdir(period_dir):
            if d.startswith('symbol='):
                code = to_canonical_symbol(d[len('symbol='):])
                codes.append(code)
        return codes
    return []


_LAZY_PREV_CLOSE_READER: Optional[StockDataReader] = None
_LAZY_PREV_CLOSE_ETF_READER: Optional[StockDataReader] = None
_LAZY_PREV_CLOSE_READER_LOCK = threading.Lock()


def lazy_prev_close_reader(asset_type: str = "stock") -> Optional[StockDataReader]:
    """Thread-safe singleton for limit_info / gap_down DuckDB ``none`` reads.

    Phase 2 P0 fix: accepts ``asset_type`` to route ETF codes to
    ``stock_data_etf_none.duckdb`` (separate from stock DuckDB).
    """
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


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='StockDataReader CLI — 建库 / 查询')
    parser.add_argument('--build', action='store_true',
                        help='构建持久化 .duckdb 文件')
    parser.add_argument('--period', default='1d', choices=['1d', '1m', 'all'],
                        help='数据周期 (default 1d)')
    parser.add_argument('--data-dir', default=None,
                        help='stock_data 目录路径（默认自动探测）')
    parser.add_argument('--db-path', default=None,
                        help='.duckdb 输出路径（默认 stock_data 目录）')
    parser.add_argument('--adjust-type', default='front', choices=['none', 'front', 'back'],
                        help='复权类型 (default front)')
    args = parser.parse_args()

    if args.build:
        periods = []
        if args.period == 'all':
            periods = [('1d', 'front'), ('1d', 'none'), ('1d', 'back'), ('1m', 'none')]
        elif args.period == '1d':
            periods = [('1d', args.adjust_type)]
        else:
            periods = [('1m', 'none')]

        for period, adjust in periods:
            print(f'Building {period}/{adjust} ...')
            db_path, elapsed = StockDataReader.build_persistent_db(
                base_dir=args.data_dir, db_path=args.db_path,
                period=period, adjust_type=adjust)
            size_mb = db_path.stat().st_size / (1024 * 1024)
            print(f'  {db_path.name}: {size_mb:.0f} MB in {elapsed:.0f}s')
        print('Done.')
    else:
        parser.print_help()
