"""
QMT 数据下载与本地缓存管理。

xtquant 通过延迟导入（仅在 download_data 首次调用时加载），
无 QMT 环境的进程可安全 import 本模块而不触发 xtquant 依赖。

1d 落盘（``_process_downloaded_data``「写入文件」）：走
``oskh_data.daily_parquet_write.write_processed_data``，模式由
``OSKH_DAILY_PARQUET_WRITE_MODE``（默认 ``duckdb``）决定；日志
``写入文件 (mode): N stocks``。分钟线仍用模块内串行 pandas 写盘。
"""
# pyright: reportUnusedImport=false
# （B3c 迁移 re-export 供 tests patch 面使用，见下方 noqa: F401 块）

from __future__ import annotations
from oskh_data.pandas_typing import normalize_timestamp
from .symbol_format import to_partition_key

import os
import warnings
from datetime import timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, cast

import numpy as np
import pandas as pd
from tqdm import tqdm

from common.infra.quant_logger import get_logger
from common.infra.timekeeping import parse_qmt_time
from common.infra.constants import EnvVarKeys, StreamObservabilityEvent
from common.infra.data_root import (
    resolve_e_stock_data_container,
    resolve_parquet_container,
    resolve_period_root,
)

logger = get_logger(__name__)

from oskh_data.download_transport import (  # noqa: F401 — B3c 迁移后 re-export
    DailyBarsTransport,
    _chunks,
    _resolve_download_watchdog_timeouts,
    resolve_download_transport,
)


def _is_latest_bar_placeholder(file_path: Path, target_date: pd.Timestamp) -> bool:
    """检查 parquet 中 target_date 对应最新 bar 是否为 QMT 占位符（volume=0）。

    场景：盘后市场数据未 finalize 时，QMT 可能对目标交易日返回一条 OHLC=前收、
    volume=0 的占位 bar。该 bar 会被写成 target_date，导致增量过滤认为数据已
    最新而跳过真实数据下载。本函数通过读取 time/volume（及存在时的 amount）
    判断最新 bar 是否为占位符。
    """
    try:
        cols = ["time", "volume"]
        has_amount = False
        # 轻量检查列存在性：none 有 amount，front/back 无 amount
        import pyarrow.parquet as pq

        schema = pq.read_schema(file_path)
        if "amount" in schema.names:
            cols.append("amount")
            has_amount = True
        df = pd.read_parquet(file_path, engine="pyarrow", columns=cols)
        if df.empty:
            return False
        latest = df.loc[df["time"].idxmax()]
        # 存储口径 = UTC 零点毫秒（本模块写入路径由 tz-naive 日线索引物化，
        # 见 download_data 的 time 列物化注释）。tz-naive 的 .value 直接给出
        # 「naive 当 UTC」的 ns，与存储口径一致；此前用 naive .timestamp()
        # （本机时区，+08 机 = 北京零点毫秒 = CST-as-UTC）比对 → 恒不等 →
        # 占位检测静默失效（2026-07-20 实证：002677.SZ 停牌占位窗口）。
        target_ts = int(pd.Timestamp(target_date).value // 10**6)
        if int(latest["time"]) != target_ts:
            return False
        if float(latest["volume"]) != 0:
            return False
        if has_amount and float(latest.get("amount", 1)) != 0:
            return False
        return True
    except Exception:
        return False


def _get_parquet_latest_date(file_path: Path) -> Optional[pd.Timestamp]:
    """使用 pyarrow 元数据快速获取 parquet 文件最新日期，失败时返回 None。"""
    try:
        import pyarrow.parquet as pq

        meta = pq.read_metadata(file_path)
        max_ts: Optional[pd.Timestamp] = None
        for rg_idx in range(meta.num_row_groups):
            rg = meta.row_group(rg_idx)
            for col_idx in range(rg.num_columns):
                col = rg.column(col_idx)
                stats = col.statistics
                if stats is None or stats.max is None:
                    continue
                col_name = col.path_in_schema
                # 优先使用 DatetimeIndex 列（DuckDB/旧版写入的 __index_level_0__）
                if "index_level" in col_name:
                    max_val = stats.max
                    if max_val is not None:
                        candidate = pd.Timestamp(max_val)
                        if not bool(pd.isna(candidate)) and (
                            max_ts is None or candidate > max_ts
                        ):
                            max_ts = cast(pd.Timestamp, candidate)
                # 次选 time 列（毫秒 epoch），需要转为 Timestamp
                elif col_name == "time":
                    max_val = stats.max
                    if max_val is not None:
                        ts = pd.Timestamp(max_val, unit="ms")
                        if not bool(pd.isna(ts)) and (max_ts is None or ts > max_ts):
                            max_ts = cast(pd.Timestamp, ts)
        if max_ts is not None:
            return max_ts.normalize()
    except Exception:
        pass
    return None


# ------------------------------------------------------------------
# StockDataManager — 常量/配置
# ------------------------------------------------------------------


class StockDataManager:
    """股票数据管理器（常量和配置）"""

    EXCHANGE_MAPPING = {
        "SH": ["600", "601", "603", "605", "688"],
        "SZ": ["000", "001", "002", "003", "300", "301"],
        "BJ": ["43", "82", "83", "84", "87", "88", "920"],
    }

    ADJUST_MAPPING = {
        "none": "none",
        "front": "front",
        "back": "back",
    }

    # miniQMT xtdata.get_market_data_ex 返回的标准字段（小写）
    STANDARD_COLUMNS = ["time", "open", "high", "low", "close", "volume", "amount"]
    STANDARD_DTYPES = {"time": "int64", "volume": "int64", "amount": "float64"}

    @classmethod
    def normalize_schema(cls, df: pd.DataFrame) -> pd.DataFrame:
        """将 DataFrame 归一化为标准 schema，修复旧版遗留的大小写/DType 问题。"""
        # Phase 2 P1 fix: warn when QMT returns columns not in STANDARD_COLUMNS.
        # Silent column dropping is the same failure class as "settlement SELECT
        # missing columns" (Phase 1) — data truncation without error.
        dropped = [c for c in df.columns if c not in cls.STANDARD_COLUMNS]
        if dropped:
            logger.warning(
                "normalize_schema dropping unknown columns from QMT response; "
                "update STANDARD_COLUMNS if these fields are needed",
                context={
                    "dropped_columns": dropped,
                    "standard_columns": cls.STANDARD_COLUMNS,
                },
            )
        # 只保留标准小写列，丢弃任何大写/重复列
        available = [c for c in cls.STANDARD_COLUMNS if c in df.columns]
        df = df.loc[:, available].copy()
        # 修正 dtype
        for col, dtype in cls.STANDARD_DTYPES.items():
            if col in df.columns and df[col].dtype != dtype:
                df[col] = df[col].astype(dtype)
        return df

    PERIOD_MAPPING = {
        "1m": ("1分钟", True),
        "5m": ("5分钟", True),
        "10m": ("10分钟", True),
        "15m": ("15分钟", True),
        "30m": ("30分钟", True),
        "1h": ("60分钟", True),
        "1d": ("日线", False),
        "1w": ("周线", False),
        "1M": ("月线", False),
    }

    def __init__(self, base_dir: str | None = None):
        if base_dir:
            self._ops_base = Path(base_dir)
            self.base_dir = Path(base_dir)
        else:
            self._ops_base = resolve_e_stock_data_container()
            self.base_dir = resolve_parquet_container()
        self._ensure_directories()

    def _ensure_directories(self):
        self._ops_base.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate_period(cls, period: str) -> bool:
        return period in cls.PERIOD_MAPPING

    @classmethod
    def is_minute_period(cls, period: str) -> bool:
        return cls.PERIOD_MAPPING.get(period, (None, False))[1]

    @classmethod
    def get_period_name(cls, period: str) -> str:
        return cls.PERIOD_MAPPING.get(period, ("未知周期", False))[0]

    @classmethod
    def get_recommended_adjust_type(cls, period: str) -> str:
        return "none" if cls.is_minute_period(period) else "front"


# ------------------------------------------------------------------
# PeriodDataManager — 周期数据管理
# ------------------------------------------------------------------


class PeriodDataManager:
    """周期数据管理器"""

    @staticmethod
    def validate_time_range(
        period: str, start_time: str, end_time: str
    ) -> Tuple[bool, str]:
        try:
            start_dt = pd.to_datetime(start_time)
            end_dt = pd.to_datetime(end_time)
            if start_dt > end_dt:
                return False, "开始时间不能晚于结束时间"
            if StockDataManager.is_minute_period(period):
                time_diff = end_dt - start_dt
                max_days = {
                    "1m": 7,
                    "5m": 30,
                    "10m": 30,
                    "15m": 90,
                    "30m": 180,
                    "1h": 365,
                }.get(period, 30)
                if time_diff.days > max_days:
                    pass
            return True, "时间范围有效"
        except Exception as e:
            return False, f"时间格式错误: {e}"

    @staticmethod
    def get_file_path(
        base_dir: Path | None, period: str, adjust_type: str, stock_code: str
    ) -> Path:
        _ = base_dir  # legacy param; parquet hive 经 resolve_period_root SSOT
        safe_stock_code = to_partition_key(stock_code)
        path = (
            resolve_period_root(period)
            / f"dividend_type={adjust_type}"
            / f"symbol={safe_stock_code}"
        )
        path.mkdir(parents=True, exist_ok=True)
        return path / "data.parquet"

    @staticmethod
    def process_minute_data(df: pd.DataFrame) -> pd.DataFrame:
        """处理分钟数据：过滤非交易时间"""
        if df.empty:
            return df
        if not isinstance(df.index, pd.DatetimeIndex):
            df = df.copy()
            # QMT minute index is integer YYYYMMDDHHMMSS.
            df.index = pd.to_datetime(df.index, format="%Y%m%d%H%M%S")
        if not df.index.is_unique:
            df = df.reset_index(drop=True)

        from common.infra.trading_calendar_pmc import get_trade_days_sse

        min_date = cast(pd.Timestamp, df.index.min())
        max_date = cast(pd.Timestamp, df.index.max())
        cal_df = get_trade_days_sse(
            since=min_date.strftime("%Y%m%d"),
            until=max_date.strftime("%Y%m%d"),
        )
        if cal_df is None or cal_df.empty:
            trading_days_date = np.array([], dtype="datetime64[D]")
        else:
            trading_days_date = pd.to_datetime(
                cal_df["cal_date"].astype(str), format="%Y%m%d"
            ).dt.date.to_numpy()
        mask_date = np.isin(df.index.date.astype("datetime64[D]"), trading_days_date)  # type: ignore[reportAttributeAccessIssue]

        minutes = df.index.hour * 60 + df.index.minute  # type: ignore[reportAttributeAccessIssue]
        mask_time = ((minutes >= 570) & (minutes <= 690)) | (
            (minutes >= 780) & (minutes <= 900)
        )
        mask = mask_date & mask_time
        return cast(pd.DataFrame, df.loc[mask])


# ------------------------------------------------------------------
# DataDownloader — QMT 数据下载器
# ------------------------------------------------------------------


class DataDownloader:
    """数据下载器（xtquant 延迟导入）"""

    def __init__(
        self,
        base_dir: str | None = None,
        transport: Optional[DailyBarsTransport] = None,
    ):
        if base_dir:
            self._ops_base = Path(base_dir)
            self.base_dir = Path(base_dir)
        else:
            self._ops_base = resolve_e_stock_data_container()
            self.base_dir = resolve_parquet_container()
        self._ops_base.mkdir(parents=True, exist_ok=True)
        # B3c/A2：xtdata 调用面经 transport；默认按旋钮解析（repo 默认 daqmt；
        # mini host 须显式 xtdata；daqmt 工厂由 oskh_core 惰性注册）。
        self._transport = transport if transport is not None else resolve_download_transport()

    def download_data(
        self,
        stock_list: List[str],
        start_time: str,
        end_time: str,
        period: str = "1d",
        adjust_type: str = "front",
        incrementally: bool = False,
        callback: Optional[Callable] = None,
        # 默认 10s 节流：未显式传时按 ~10 秒一行采样，避免大批量下载每只一行
        # 撑爆日志（5559 只 → 14 万+ tokens）。传 None/0 关闭节流（旧行为）。
        progress_log_interval_sec: Optional[float] = 10.0,
    ) -> Dict[str, pd.DataFrame]:
        if not StockDataManager.validate_period(period):
            logger.error(f"不支持的周期: {period}")
            return {}

        is_valid, msg = PeriodDataManager.validate_time_range(
            period, start_time, end_time
        )
        if not is_valid:
            logger.error(f"时间范围无效: {msg}")
            return {}

        if StockDataManager.is_minute_period(period):
            adjust_type = "none"
            # P1-3: 分钟线下载要求 end_time 可被 parse_qmt_time 解析（+1min 修正依赖此格式）
            try:
                parse_qmt_time(end_time)
            except Exception as e:
                raise ValueError(
                    f"分钟线下载要求 end_time 为 YYYYMMDDHHmmss 格式，"
                    f"当前 end_time={end_time!r}: {e}"
                ) from e
        elif adjust_type not in StockDataManager.ADJUST_MAPPING:
            adjust_type = StockDataManager.get_recommended_adjust_type(period)

        logger.info(
            f"开始下载{StockDataManager.get_period_name(period)}数据: {len(stock_list)}只股票, {start_time}至{end_time} (复权: {adjust_type})"
        )

        if incrementally:
            actual_download_list = self._filter_incremental(
                stock_list, period, adjust_type, end_time
            )
        else:
            actual_download_list = stock_list

        if not actual_download_list:
            logger.info("所有股票数据均已最新，无需下载")
            return {}

        adjusted_end_time = end_time
        if period == "1m":
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    end_dt = parse_qmt_time(end_time)
                adjusted_end_time = (end_dt + timedelta(minutes=1)).strftime(
                    "%Y%m%d%H%M%S"
                )
            except Exception as e:
                # P1-3 FIX: +1min 修正失败必须阻断，禁止静默回退导致最后一根 bar 丢失
                raise ValueError(
                    f"1m period requires valid end_time for +1min correction, "
                    f"got end_time={end_time!r}: {e}"
                ) from e

        try:
            outcome = self._transport.download_bulk(
                actual_download_list,
                start_time,
                adjusted_end_time,
                period=period,
                adjust_type=adjust_type,
                incrementally=incrementally,
                callback=callback,
                progress_log_interval_sec=progress_log_interval_sec,
            )
            # 剔除超时批，避免 _process_downloaded_data 的 per-stock "QMT returned None" 噪音
            process_list = [
                s for s in actual_download_list if s not in outcome.timeout_stock_set
            ]
            raw_data = outcome.frames
            result = self._process_downloaded_data(
                raw_data, process_list, period, adjust_type, start_time, end_time
            )

            FAIL_RATE_THRESHOLD = float(
                os.environ.get(
                    EnvVarKeys.OSKH_FASTPATH_READ_FAIL_RATE_THRESHOLD, "0.05"
                )
            )
            # 失败率检查（M8b 已删：必需股概念属盘中主路径，不属下载；只留 fail_rate 兜底）
            # 小批量（<40）：单只失败即可超过 5%（如 1/19≈5.26%），要求至少 2 只失败才升为
            # _download_error，避免残差重试被误杀（2026-07-13）。
            success_count = len(result)
            fail_count = (
                len(actual_download_list) - success_count
            )  # 分母=actual_download_list（含超时批）
            fail_rate = (
                fail_count / len(actual_download_list) if actual_download_list else 0.0
            )
            failed_codes = [s for fb in outcome.failed_batches for s in fb["stocks"]]
            min_fails_for_error = 2 if len(actual_download_list) < 40 else 1
            if fail_rate > FAIL_RATE_THRESHOLD and fail_count >= min_fails_for_error:
                logger.warning(
                    f"fastpath_read 失败率 {fail_rate:.2%} > {FAIL_RATE_THRESHOLD:.0%}（{fail_count}/{len(actual_download_list)}），返回 _download_error",
                    context={
                        "event": StreamObservabilityEvent.FASTPATH_READ_BATCH_TIMEOUT,
                        "fail_rate": fail_rate,
                        "fail_count": fail_count,
                        "total": len(actual_download_list),
                        "min_fails_for_error": min_fails_for_error,
                    },
                )
                return cast(
                    Dict[str, pd.DataFrame],
                    {
                        **result,  # 已成功批 parquet 已 salvage，调用方可据此 retry 失败批
                        "_download_error": f"fastpath_read fail_rate={fail_rate:.2%}",
                        "_failed_batch_codes": failed_codes,
                    },
                )
            if fail_count and fail_rate > FAIL_RATE_THRESHOLD:
                logger.warning(
                    f"fastpath_read 失败率 {fail_rate:.2%} 超阈值但 fail_count={fail_count} "
                    f"< min_fails_for_error={min_fails_for_error}（小批量豁免），继续返回已成功数据",
                    context={
                        "fail_rate": fail_rate,
                        "fail_count": fail_count,
                        "total": len(actual_download_list),
                    },
                )
            return result
        except (ValueError, TypeError) as structural_exc:
            # 结构性错误（schema 不匹配、参数错误等）— 不应重试，需人工介入
            logger.error(f"数据下载结构性错误，中止下载: {structural_exc}")
            raise
        except Exception as e:
            # 瞬态错误（网络、QMT 内部超时等）— 可重试
            # Phase 2 P1 fix: return structured error instead of silent {} so
            # callers (backfill / etf_backfill) can detect download failure vs
            # "no data needed".  Incremental callers that receive _download_error
            # should retry on next run.
            logger.error(f"数据下载瞬态失败: {e}")
            try:
                from oskh_data.qmt_download_channel import maybe_write_stale_marker

                maybe_write_stale_marker(self._ops_base, end_time, str(e))
            except Exception as mark_exc:  # noqa: BLE001 — marker is best-effort
                logger.warning(f"写入 QMT 通道腐坏标记失败: {mark_exc}")
            return cast(
                Dict[str, pd.DataFrame],
                {
                    "_download_error": type(e).__name__,
                    "_download_error_detail": str(e)[:500],
                    "_failed_stock_count": len(actual_download_list),
                },
            )

    def _filter_incremental(self, stock_list, period, adjust_type, end_time):
        need_update_stocks = []
        end_dt = pd.to_datetime(end_time).normalize()
        placeholder_count = 0
        for stock_code in stock_list:
            file_path = PeriodDataManager.get_file_path(
                self.base_dir, period, adjust_type, stock_code
            )
            if os.path.exists(file_path):
                # Phase 2 P3: 先用 pyarrow 元数据快速判断最新日期，避免全量读取
                latest_date = _get_parquet_latest_date(file_path)
                if latest_date is not None:
                    if latest_date < end_dt:
                        need_update_stocks.append(stock_code)
                    elif latest_date == end_dt and _is_latest_bar_placeholder(
                        file_path, end_dt
                    ):
                        # 2026-07-07 fix: target_date 是占位 bar（volume/amount=0）时
                        # 不认为数据已最新，须重新下载以获取真实收盘
                        need_update_stocks.append(stock_code)
                        placeholder_count += 1
                    continue

                # 元数据不可用或解析失败时回退到完整读取
                try:
                    existing_data = pd.read_parquet(file_path, engine="pyarrow")
                except Exception as _pe:
                    # Phase 2 P2: corrupt parquet → re-download instead of crash
                    logger.warning(
                        "corrupt parquet in incremental filter, will re-download: %s",
                        file_path,
                        context={"error": str(_pe)[:200]},
                    )
                    need_update_stocks.append(stock_code)
                    continue
                if not existing_data.empty and isinstance(
                    existing_data.index, pd.DatetimeIndex
                ):
                    latest_date = normalize_timestamp(existing_data.index.max())
                    if latest_date < end_dt:
                        need_update_stocks.append(stock_code)
                    elif latest_date == end_dt:
                        # 回退路径同样检查占位 bar
                        try:
                            if _is_latest_bar_placeholder(file_path, end_dt):
                                need_update_stocks.append(stock_code)
                                placeholder_count += 1
                        except Exception:
                            pass
                else:
                    need_update_stocks.append(stock_code)
            else:
                need_update_stocks.append(stock_code)
        if need_update_stocks:
            logger.info(f"实际需要下载: {len(need_update_stocks)}/{len(stock_list)}")
        if placeholder_count:
            logger.info(
                f"其中 {placeholder_count} 只因 target_date 占位 bar（volume/amount=0）需要重新下载"
            )
        return need_update_stocks

    def _process_downloaded_data(
        self,
        raw_data: Dict,
        stock_list: List[str],
        period: str,
        adjust_type: str,
        start_time: str,
        end_time: str,
    ) -> Dict[str, pd.DataFrame]:
        start_dt = pd.Timestamp(pd.to_datetime(start_time))
        end_dt = pd.Timestamp(pd.to_datetime(end_time))
        if StockDataManager.is_minute_period(period):
            end_dt += pd.Timedelta(minutes=1)

        numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
        processed_data: Dict[str, pd.DataFrame] = {}
        failed_stocks: list = []

        for stock_code in tqdm(stock_list, desc="处理股票数据"):
            try:
                if stock_code not in raw_data or raw_data[stock_code] is None:
                    # Phase 2 P1: log per-stock QMT omission so callers can
                    # distinguish "no data returned" from "download succeeded for 0 rows"
                    logger.warning(
                        "QMT returned None for stock in batch; data may be missing",
                        context={"stock_code": stock_code},
                    )
                    continue
                stock_df = raw_data[stock_code]
                if not isinstance(stock_df, pd.DataFrame) or stock_df.empty:
                    logger.warning(f"Silent failure (empty data): {stock_code}")
                    continue

                # 静默失败检测：下载后校验 shape（QMT 网络抖动可能返回空）
                if stock_df.shape[0] == 0:
                    logger.warning(f"Silent failure (zero rows): {stock_code}")
                    continue

                _rows_before = len(stock_df)
                for col in numeric_cols:
                    if col in stock_df.columns:
                        stock_df[col] = pd.to_numeric(stock_df[col], errors="coerce")
                stock_df = stock_df.dropna(subset=numeric_cols)
                _rows_dropped = _rows_before - len(stock_df)
                if _rows_dropped > 0:
                    # Phase 2 P1: log rows silently dropped by coerce→NaN→dropna.
                    # Corrupted QMT data (network truncation, encoding errors) can
                    # cause entire bars to disappear without any error signal.
                    logger.warning(
                        f"coerce/dropna dropped {_rows_dropped}/{_rows_before} rows "
                        f"for {stock_code}; possible data corruption in QMT response",
                        context={
                            "stock_code": stock_code,
                            "rows_before": _rows_before,
                            "rows_dropped": _rows_dropped,
                        },
                    )
                if stock_df.empty:
                    continue

                if not isinstance(stock_df.index, pd.DatetimeIndex):
                    # QMT returns daily index as integer YYYYMMDD and minute index as
                    # integer YYYYMMDDHHMMSS. Default pd.to_datetime(int) treats them
                    # as nanoseconds since epoch, so we must use the matching format.
                    _date_fmt = (
                        "%Y%m%d%H%M%S"
                        if StockDataManager.is_minute_period(period)
                        else "%Y%m%d"
                    )
                    stock_df.index = pd.to_datetime(stock_df.index, format=_date_fmt)
                stock_df = stock_df.sort_index()
                filtered_df = stock_df.loc[start_dt:end_dt]
                if filtered_df.empty:
                    continue

                if StockDataManager.is_minute_period(period):
                    if isinstance(filtered_df, pd.DataFrame):
                        filtered_df = PeriodDataManager.process_minute_data(filtered_df)

                processed_data[stock_code] = filtered_df
            except Exception:
                logger.exception(f"处理股票数据失败: {stock_code}")
                failed_stocks.append(stock_code)

        if failed_stocks:
            logger.warning(
                f"Batch processing: {len(failed_stocks)}/{len(stock_list)} stocks FAILED due to exception",
                context={"failed_stocks": failed_stocks[:20]},
            )
        # tqdm here only materializes time column — NOT the real parquet write
        # (lesson 43: Agents mistook this bar for disk write completion).
        for stock_code, df_new in tqdm(processed_data.items(), desc="物化time列"):
            # Materialize time column from index as ms (encoding unchanged).
            # Do NOT rewrite timezone/calendar (no +8h / full-history UTC-midnight unify);
            # that caused CST-as-UTC + UTC-midnight double rows (2026-07-17).
            if "time" in df_new.columns:
                df_new["time"] = (
                    pd.to_datetime(df_new.index).astype("int64") // 10**6
                ).astype("int64")

        if period == "1d":
            from oskh_data.daily_parquet_write import (
                resolve_write_mode,
                write_processed_data,
            )

            mode = resolve_write_mode()
            logger.info(
                f"写入文件 ({mode}): 开始真实写盘 {len(processed_data)} stocks "
                f"(OSKH_DAILY_PARQUET_WRITE_MODE；进度见 parquet write 心跳)"
            )
            ok_n, write_errs = write_processed_data(
                self.base_dir,
                adjust_type,
                processed_data,
                mode=mode,
            )
            if write_errs:
                logger.warning(
                    f"parquet write errors: {len(write_errs)}/{len(processed_data)}",
                    context={"sample": write_errs[:10]},
                )
            logger.info(f"成功处理 {ok_n} 只股票数据 (write_mode={mode})")
            return processed_data

        # 分钟线并行写盘（复用 daily_parquet_write 的 ThreadPool 模式）
        from concurrent.futures import ThreadPoolExecutor, as_completed

        _MINUTE_WRITE_WORKERS = max(4, min(16, (os.cpu_count() or 8)))

        def _merge_write_one_minute(args):
            stock_code, df_new = args
            try:
                file_path = PeriodDataManager.get_file_path(
                    self.base_dir, period, adjust_type, stock_code
                )
                if file_path.exists():
                    df_existing = pd.read_parquet(file_path, engine="pyarrow")
                    df_existing = StockDataManager.normalize_schema(df_existing)
                    df_merged = pd.concat([df_existing, df_new])
                    df_merged = df_merged[~df_merged.index.duplicated(keep="last")]
                    df_merged = df_merged.sort_index()
                    df_merged.to_parquet(
                        file_path, engine="pyarrow", compression="snappy"
                    )
                else:
                    df_new.to_parquet(file_path, engine="pyarrow", compression="snappy")
                return None
            except Exception as exc:
                return f"{stock_code}: {type(exc).__name__}: {exc}"

        ok_n = 0
        write_errs = []
        with ThreadPoolExecutor(max_workers=_MINUTE_WRITE_WORKERS) as pool:
            futs = {
                pool.submit(_merge_write_one_minute, (code, df)): code
                for code, df in processed_data.items()
            }
            for fut in tqdm(as_completed(futs), total=len(futs), desc="写入文件(并行)"):
                err = fut.result()
                if err is None:
                    ok_n += 1
                else:
                    write_errs.append(err)
        if write_errs:
            logger.warning(
                f"minute parquet write errors: {len(write_errs)}/{len(processed_data)}",
                context={"sample": write_errs[:10]},
            )
        logger.info(
            f"成功处理 {ok_n} 只股票数据 (minute parallel write, workers={_MINUTE_WRITE_WORKERS})"
        )
        return processed_data

    def get_stock_data(
        self,
        stock_code: str,
        start_time: str,
        end_time: str,
        period: str = "1d",
        adjust_type: str = "front",
    ) -> Optional[pd.DataFrame]:
        if not StockDataManager.validate_period(period):
            return None
        if StockDataManager.is_minute_period(period):
            adjust_type = "none"

        file_path = PeriodDataManager.get_file_path(
            self.base_dir, period, adjust_type, stock_code
        )
        if not file_path.exists():
            return None
        try:
            df = pd.read_parquet(file_path, engine="pyarrow")
            start_dt = pd.to_datetime(start_time)
            end_dt = pd.to_datetime(end_time)
            mask = (df.index >= start_dt) & (df.index <= end_dt)
            return df.loc[mask]
        except Exception:
            logger.exception("加载数据失败: %s", stock_code)
            return None

    def get_available_periods(self) -> List[str]:
        periods_dir = resolve_period_root("1d")
        if periods_dir.exists():
            return list(StockDataManager.PERIOD_MAPPING.keys())
        return []
