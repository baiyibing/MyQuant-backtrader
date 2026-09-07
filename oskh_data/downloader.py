"""
QMT 数据下载与本地缓存管理。

xtquant 通过延迟导入（仅在 download_data 首次调用时加载），
无 QMT 环境的进程可安全 import 本模块而不触发 xtquant 依赖。
"""
from __future__ import annotations

import os
import time
import warnings
from datetime import timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from tqdm import tqdm

from common.infra.quant_logger import get_logger
from common.infra.timekeeping import mono_now, parse_qmt_time

logger = get_logger(__name__)

# 全局缓存交易日历（延迟导入，避免 pandas_market_calendars 无安装时阻塞）
_SSE_CALENDAR = None


def _get_sse_calendar():
    global _SSE_CALENDAR
    if _SSE_CALENDAR is None:
        import pandas_market_calendars as mcal

        _SSE_CALENDAR = mcal.get_calendar('SSE')
    return _SSE_CALENDAR


# xtquant 延迟导入
_xtdata = None


def _get_xtdata():
    global _xtdata
    if _xtdata is None:
        from xtquant import xtdata as _xt

        _xtdata = _xt
    return _xtdata


# ------------------------------------------------------------------
# StockDataManager — 常量/配置
# ------------------------------------------------------------------


class StockDataManager:
    """股票数据管理器（常量和配置）"""

    EXCHANGE_MAPPING = {
        'SH': ['600', '601', '603', '605', '688'],
        'SZ': ['000', '001', '002', '003', '300', '301'],
        'BJ': ['43', '82', '83', '84', '87', '88', '920'],
    }

    ADJUST_MAPPING = {
        'none': 'none',
        'front': 'front',
        'back': 'back',
    }

    # miniQMT xtdata.get_market_data_ex 返回的标准字段（小写）
    STANDARD_COLUMNS = ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']
    STANDARD_DTYPES = {'time': 'int64', 'volume': 'int64', 'amount': 'float64'}

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
                context={"dropped_columns": dropped, "standard_columns": cls.STANDARD_COLUMNS},
            )
        # 只保留标准小写列，丢弃任何大写/重复列
        available = [c for c in cls.STANDARD_COLUMNS if c in df.columns]
        df = df[available].copy()
        # 修正 dtype
        for col, dtype in cls.STANDARD_DTYPES.items():
            if col in df.columns and df[col].dtype != dtype:
                df[col] = df[col].astype(dtype)
        return df

    PERIOD_MAPPING = {
        '1m': ('1分钟', True),
        '5m': ('5分钟', True),
        '10m': ('10分钟', True),
        '15m': ('15分钟', True),
        '30m': ('30分钟', True),
        '1h': ('60分钟', True),
        '1d': ('日线', False),
        '1w': ('周线', False),
        '1M': ('月线', False),
    }

    def __init__(self, base_dir: str = "../stock_data"):
        self.base_dir = Path(base_dir)
        self._ensure_directories()

    def _ensure_directories(self):
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate_period(cls, period: str) -> bool:
        return period in cls.PERIOD_MAPPING

    @classmethod
    def is_minute_period(cls, period: str) -> bool:
        return cls.PERIOD_MAPPING.get(period, (None, False))[1]

    @classmethod
    def get_period_name(cls, period: str) -> str:
        return cls.PERIOD_MAPPING.get(period, ('未知周期', False))[0]

    @classmethod
    def get_recommended_adjust_type(cls, period: str) -> str:
        return 'none' if cls.is_minute_period(period) else 'front'


# ------------------------------------------------------------------
# PeriodDataManager — 周期数据管理
# ------------------------------------------------------------------


class PeriodDataManager:
    """周期数据管理器"""

    @staticmethod
    def validate_time_range(period: str, start_time: str, end_time: str) -> Tuple[bool, str]:
        try:
            start_dt = pd.to_datetime(start_time)
            end_dt = pd.to_datetime(end_time)
            if start_dt > end_dt:
                return False, "开始时间不能晚于结束时间"
            if StockDataManager.is_minute_period(period):
                time_diff = end_dt - start_dt
                max_days = {
                    '1m': 7, '5m': 30, '10m': 30,
                    '15m': 90, '30m': 180, '1h': 365,
                }.get(period, 30)
                if time_diff.days > max_days:
                    pass
            return True, "时间范围有效"
        except Exception as e:
            return False, f"时间格式错误: {e}"

    @staticmethod
    def get_file_path(base_dir: Path, period: str, adjust_type: str, stock_code: str) -> Path:
        safe_stock_code = stock_code.replace('.', '_')
        path = base_dir / f"period={period}" / f"dividend_type={adjust_type}" / f"symbol={safe_stock_code}"
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

        calendar = _get_sse_calendar()
        min_date = df.index.min()
        max_date = df.index.max()
        trading_days = calendar.schedule(
            min_date.strftime('%Y-%m-%d'),
            max_date.strftime('%Y-%m-%d'),
        ).index
        trading_days_date = trading_days.date  # type: ignore[reportAttributeAccessIssue]
        mask_date = np.isin(df.index.date.astype('datetime64[D]'), trading_days_date)  # type: ignore[reportAttributeAccessIssue]

        minutes = df.index.hour * 60 + df.index.minute  # type: ignore[reportAttributeAccessIssue]
        mask_time = (
            ((minutes >= 570) & (minutes <= 690))
            | ((minutes >= 780) & (minutes <= 900))
        )
        mask = mask_date & mask_time
        return df[mask]


# ------------------------------------------------------------------
# DataDownloader — QMT 数据下载器
# ------------------------------------------------------------------


class DataDownloader:
    """数据下载器（xtquant 延迟导入）"""

    def __init__(self, base_dir: str = "../stock_data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def download_data(
        self,
        stock_list: List[str],
        start_time: str,
        end_time: str,
        period: str = '1d',
        adjust_type: str = 'front',
        incrementally: bool = False,
        callback: Optional[Callable] = None,
    ) -> Dict[str, pd.DataFrame]:
        xtdata = _get_xtdata()

        if not StockDataManager.validate_period(period):
            logger.error(f"不支持的周期: {period}")
            return {}

        is_valid, msg = PeriodDataManager.validate_time_range(period, start_time, end_time)
        if not is_valid:
            logger.error(f"时间范围无效: {msg}")
            return {}

        if StockDataManager.is_minute_period(period):
            adjust_type = 'none'
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
            actual_download_list = self._filter_incremental(stock_list, period, adjust_type, end_time)
        else:
            actual_download_list = stock_list

        if not actual_download_list:
            logger.info("所有股票数据均已最新，无需下载")
            return {}

        adjusted_end_time = end_time
        if period == '1m':
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    end_dt = parse_qmt_time(end_time)
                adjusted_end_time = (end_dt + timedelta(minutes=1)).strftime('%Y%m%d%H%M%S')
            except Exception as e:
                # P1-3 FIX: +1min 修正失败必须阻断，禁止静默回退导致最后一根 bar 丢失
                raise ValueError(
                    f"1m period requires valid end_time for +1min correction, "
                    f"got end_time={end_time!r}: {e}"
                ) from e

        _DOWNLOAD_START_TIMEOUT_SEC = 30.0
        _DOWNLOAD_TOTAL_TIMEOUT_SEC = 300.0
        _DOWNLOAD_STALL_TIMEOUT_SEC = 60.0

        try:
            total_stocks = len(actual_download_list)
            downloaded_set: set = set()
            download_complete = False
            download_started = False
            last_progress_time = mono_now()
            external_callback = callback

            def on_progress(data):
                nonlocal downloaded_set, download_complete, download_started, last_progress_time
                download_started = True
                last_progress_time = mono_now()
                finished = data.get('finished', 0)
                total = data.get('total', 0)
                stock_code = data.get('message', 'N/A')
                if stock_code and stock_code != 'N/A':
                    downloaded_set.add(stock_code)
                if finished > 0 and total > 0:
                    logger.info(
                        f"下载进度: {finished}/{total} ({(finished / total) * 100:.2f}%) - 当前: {stock_code}"
                    )
                if total > 0 and finished == total:
                    download_complete = True
                if external_callback is not None:
                    try:
                        external_callback(data)
                    except Exception as _cb_exc:
                        # Phase 2 P1 fix: log callback failures instead of
                        # silently swallowing them.  Callback side effects
                        # (audit records, progress updates) must not fail
                        # invisibly.
                        logger.warning(
                            "download progress callback failed; download continues "
                            "but caller side effects may be lost",
                            context={
                                "error_type": type(_cb_exc).__name__,
                                "error": str(_cb_exc)[:200],
                            },
                        )

            # NOTE: xtquant.download_history_data2 signature does not accept
            # an `incrementally` keyword. The incremental logic is handled above
            # by `_filter_incremental`; here we simply request the target range
            # for the stocks that actually need updating.
            xtdata.download_history_data2(
                stock_list=actual_download_list,
                period=period,
                start_time=start_time,
                end_time=adjusted_end_time,
                callback=on_progress,
            )

            logger.info(f"等待{total_stocks}只股票下载完成...")
            t0 = mono_now()
            while not download_complete:
                now = mono_now()
                elapsed = now - t0

                if not download_started and elapsed > _DOWNLOAD_START_TIMEOUT_SEC:
                    raise TimeoutError(
                        f"数据下载未在 {_DOWNLOAD_START_TIMEOUT_SEC:.0f}s 内启动，"
                        f"可能 QMT 未连接或回调未注册 (stock_count={total_stocks})"
                    )

                if elapsed > _DOWNLOAD_TOTAL_TIMEOUT_SEC:
                    raise TimeoutError(
                        f"数据下载总超时 {_DOWNLOAD_TOTAL_TIMEOUT_SEC:.0f}s，"
                        f"已完成 {len(downloaded_set)}/{total_stocks}"
                    )

                if download_started and (now - last_progress_time) > _DOWNLOAD_STALL_TIMEOUT_SEC:
                    raise TimeoutError(
                        f"数据下载停滞 {_DOWNLOAD_STALL_TIMEOUT_SEC:.0f}s 无新进度，"
                        f"已完成 {len(downloaded_set)}/{total_stocks}"
                    )

                time.sleep(0.05)

            logger.info(f"下载完成！共 {total_stocks} 个股票")

            raw_data = xtdata.get_market_data_ex(
                field_list=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'],
                stock_list=stock_list,
                period=period,
                start_time=start_time,
                end_time=adjusted_end_time,
                count=-1,
                dividend_type=adjust_type,
                fill_data=True,
            )

            result = self._process_downloaded_data(raw_data, stock_list, period, adjust_type, start_time, end_time)
            success_count = len(result)
            fail_count = len(stock_list) - success_count
            if fail_count > 0:
                logger.warning(
                    f"Batch download: {success_count}/{len(stock_list)} succeeded ({(success_count / len(stock_list) * 100 if stock_list else 0):.1f}%)"
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
            return {
                "_download_error": type(e).__name__,
                "_download_error_detail": str(e)[:500],
                "_failed_stock_count": len(actual_download_list),
            }

    def _filter_incremental(self, stock_list, period, adjust_type, end_time):
        need_update_stocks = []
        for stock_code in stock_list:
            file_path = PeriodDataManager.get_file_path(self.base_dir, period, adjust_type, stock_code)
            if os.path.exists(file_path):
                try:
                    existing_data = pd.read_parquet(file_path, engine='pyarrow')
                except Exception as _pe:
                    # Phase 2 P2: corrupt parquet → re-download instead of crash
                    logger.warning(
                        "corrupt parquet in incremental filter, will re-download: %s",
                        file_path,
                        context={"error": str(_pe)[:200]},
                    )
                    need_update_stocks.append(stock_code)
                    continue
                if not existing_data.empty and isinstance(existing_data.index, pd.DatetimeIndex):
                    latest_date = existing_data.index.max()
                    end_dt = pd.to_datetime(end_time)
                    if latest_date < end_dt:
                        need_update_stocks.append(stock_code)
                else:
                    need_update_stocks.append(stock_code)
            else:
                need_update_stocks.append(stock_code)
        if need_update_stocks:
            logger.info(f"实际需要下载: {len(need_update_stocks)}/{len(stock_list)}")
        return need_update_stocks

    def _process_downloaded_data(
        self, raw_data: Dict, stock_list: List[str], period: str, adjust_type: str,
        start_time: str, end_time: str,
    ) -> Dict[str, pd.DataFrame]:
        result_data: Dict[str, pd.DataFrame] = {}
        start_dt = pd.Timestamp(pd.to_datetime(start_time))
        end_dt = pd.Timestamp(pd.to_datetime(end_time))
        if StockDataManager.is_minute_period(period):
            end_dt += pd.Timedelta(minutes=1)

        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
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
                        stock_df[col] = pd.to_numeric(stock_df[col], errors='coerce')
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
        for stock_code, df_new in tqdm(processed_data.items(), desc="写入文件"):
            # 统一 time 列为 UTC 午夜毫秒（修复 QMT CST 偏移 bug）
            if 'time' in df_new.columns:
                df_new['time'] = (pd.to_datetime(df_new.index).astype('int64') // 10**6).astype('int64')

            file_path = PeriodDataManager.get_file_path(self.base_dir, period, adjust_type, stock_code)
            if file_path.exists():
                df_existing = pd.read_parquet(file_path, engine='pyarrow')
                # 归一化旧文件 schema，修复大小写/dtype 遗留问题
                df_existing = StockDataManager.normalize_schema(df_existing)
                # P1-4: Schema 一致性门闸 — pd.concat 静默提升 dtype 会导致 reader 查询异常
                _schema_errors = []
                if set(df_existing.columns) != set(df_new.columns):
                    _schema_errors.append(
                        f"columns mismatch: existing={sorted(df_existing.columns)} "
                        f"vs new={sorted(df_new.columns)}"
                    )
                _key_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
                for col in _key_cols:
                    if col in df_existing.columns and col in df_new.columns:
                        if df_existing[col].dtype != df_new[col].dtype:
                            _schema_errors.append(
                                f"{col} dtype mismatch: "
                                f"existing={df_existing[col].dtype} vs new={df_new[col].dtype}"
                            )
                if type(df_existing.index) != type(df_new.index):
                    _schema_errors.append(
                        f"index type mismatch: "
                        f"existing={type(df_existing.index).__name__} "
                        f"vs new={type(df_new.index).__name__}"
                    )
                if _schema_errors:
                    logger.warning(
                        f"Schema mismatch for {stock_code} (period={period}, adjust={adjust_type}): "
                        f"{'; '.join(_schema_errors)}. Overwriting corrupted local file with new data."
                    )
                    df_new.to_parquet(file_path, engine='pyarrow', compression='snappy')
                else:
                    df_merged = pd.concat([df_existing, df_new])
                    df_merged = df_merged[~df_merged.index.duplicated(keep='last')]
                    df_merged = df_merged.sort_index()
                    df_merged.to_parquet(file_path, engine='pyarrow', compression='snappy')
            else:
                df_new.to_parquet(file_path, engine='pyarrow', compression='snappy')

        logger.info(f"成功处理 {len(processed_data)} 只股票数据")
        return processed_data

    def get_stock_data(
        self, stock_code: str, start_time: str, end_time: str,
        period: str = '1d', adjust_type: str = 'front',
    ) -> Optional[pd.DataFrame]:
        if not StockDataManager.validate_period(period):
            return None
        if StockDataManager.is_minute_period(period):
            adjust_type = 'none'

        file_path = PeriodDataManager.get_file_path(self.base_dir, period, adjust_type, stock_code)
        if not file_path.exists():
            return None
        try:
            df = pd.read_parquet(file_path, engine='pyarrow')
            start_dt = pd.to_datetime(start_time)
            end_dt = pd.to_datetime(end_time)
            mask = (df.index >= start_dt) & (df.index <= end_dt)
            return df.loc[mask]
        except Exception:
            logger.exception("加载数据失败: %s", stock_code)
            return None

    def get_available_periods(self) -> List[str]:
        periods_dir = self.base_dir / "period=1d"
        if periods_dir.exists():
            return list(StockDataManager.PERIOD_MAPPING.keys())
        return []
