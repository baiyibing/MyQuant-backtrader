from common.infra.quant_logger import get_logger
import math
import os
import re
import shutil
from datetime import datetime, date

from common.infra.timekeeping import CN_TZ, parse_qmt_time
from common.infra.data_root import resolve_data_root
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple, cast
import chardet
import pandas as pd

# 配置日志
logger = get_logger(__name__)


# RF-R0/PR-B: resolve via data_root SSOT (M-003b); not cwd-relative ../stock_data.
_DEFAULT_STOCK_DATA_DIR = str(resolve_data_root() / "stock_data")

# RF-R2: lazy StockDataReader instances keyed by base_dir (parquet mode, same hive as legacy).
_oskh_reader_cache: Dict[str, object] = {}


def resolve_use_oskh_data_reader(explicit: Optional[bool] = None) -> bool:
    """Resolve backtest cache read path (RF-R2).

    Priority: explicit > env ``BACKTEST_USE_OSKH_DATA_READER`` > default True（E2 日线绿 + 1m prevclose 索引契约已对齐）。
    回滚: ``BACKTEST_USE_OSKH_DATA_READER=0``。
    """
    if explicit is not None:
        return bool(explicit)
    raw = os.environ.get("BACKTEST_USE_OSKH_DATA_READER", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    return True


def _qmt_compact_range_string(time_val) -> str:
    """QMT 紧凑区间字符串（``YYYYMMDD`` / ``YYYYMMDDHHMMSS``），解析走 ``parse_qmt_time`` SSOT。"""
    if isinstance(time_val, str):
        s = time_val.strip().replace("-", "").replace(":", "").replace(" ", "")
        if s.isdigit() and len(s) in (8, 14):
            parse_qmt_time(s, warn_on_naive=False)
            return s
        dt = parse_qmt_time(time_val, warn_on_naive=False)
    else:
        ts = pd.Timestamp(time_val)
        if bool(pd.isna(ts)):
            raise ValueError(f"Cannot parse time for reader: {time_val!r}")
        ts_ok = cast(pd.Timestamp, ts)
        dt = ts_ok.to_pydatetime()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=CN_TZ)
        else:
            dt = dt.astimezone(CN_TZ)
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        return dt.strftime("%Y%m%d")
    return dt.strftime("%Y%m%d%H%M%S")


def _normalize_reader_adjust_type(adjust_type: str) -> str:
    adj = str(adjust_type or "front").strip().lower()
    if adj in {"qfq", "front"}:
        return "front"
    if adj in {"hfq", "back"}:
        return "back"
    return "none"


def _get_oskh_data_reader(base_dir: str) -> Any:
    from oskh_data import StockDataReader

    key = str(base_dir)
    if key not in _oskh_reader_cache:
        _oskh_reader_cache[key] = StockDataReader(mode="parquet", base_dir=key)
    return _oskh_reader_cache[key]


def _get_stock_data_via_oskh_reader(
    stock_code: str,
    start_time,
    end_time,
    period: str,
    base_dir: str,
    adjust_type: str,
) -> Optional[pd.DataFrame]:
    reader = _get_oskh_data_reader(base_dir)
    return reader.read_stock(
        stock_code,
        start_time=_qmt_compact_range_string(start_time),
        end_time=_qmt_compact_range_string(end_time),
        period=period,
        adjust_type=_normalize_reader_adjust_type(adjust_type),
    )

# ---------------------------------------------------------------------------
# Data I/O SSOT (RF-R2 / M-003a): read path only; download/update → oskh_data + scripts/.
# ---------------------------------------------------------------------------


class DataCleaner:
    """数据清理器"""

    @staticmethod
    def clear_data(base_dir: str = _DEFAULT_STOCK_DATA_DIR, period: Optional[str] = None,
                   adjust_type: Optional[str] = None, stock_code: Optional[str] = None):
        """清理数据"""
        base_path = Path(base_dir)
        if not base_path.exists():
            logger.info("目录不存在，无需清理")
            return

        try:
            if period is None:
                # 清理所有数据
                shutil.rmtree(base_path)
                logger.info("清理所有数据")
            else:
                period_path = base_path / f"period={period}"
                if adjust_type is None:
                    # 清理特定周期所有数据
                    if period_path.exists():
                        shutil.rmtree(period_path)
                        logger.info(f"清理周期 {period} 所有数据")
                else:
                    adjust_path = period_path / f"dividend_type={adjust_type}"
                    if stock_code is None:
                        # 清理特定周期和复权类型数据
                        if adjust_path.exists():
                            shutil.rmtree(adjust_path)
                            logger.info(f"清理周期 {period} 复权 {adjust_type} 数据")
                    else:
                        # 清理特定股票数据
                        stock_path = adjust_path / f"symbol={stock_code.replace('.', '_')}"
                        if stock_path.exists():
                            shutil.rmtree(stock_path)
                            logger.info(f"清理股票 {stock_code} 数据")
        except Exception as e:
            logger.error(f"清理数据失败: {e}")


def _check_bom(file_path: str) -> str:
    """Detect encoding via BOM markers."""
    try:
        with open(file_path, "rb") as file:
            raw_data = file.read(4)
        if raw_data.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        if raw_data.startswith(b"\xff\xfe"):
            return "utf-16le"
        if raw_data.startswith(b"\xfe\xff"):
            return "utf-16be"
        if raw_data.startswith(b"\xff\xfe\x00\x00"):
            return "utf-32le"
        if raw_data.startswith(b"\x00\x00\xfe\xff"):
            return "utf-32be"
        return "unknown"
    except OSError:
        return "unknown"


def _detect_encoding(file_path: str) -> Tuple[str, float]:
    with open(file_path, "rb") as file:
        raw_data = file.read()
    result = chardet.detect(raw_data)
    encoding = str(result.get("encoding") or "utf-8")
    confidence = float(result.get("confidence") or 0.0)
    return encoding, confidence


class _StockExchangeMapping:
    """Exchange prefix mapping for ``StockCodeProcessor``."""

    EXCHANGE_MAPPING = {
        "SH": ["600", "601", "603", "605", "688"],
        "SZ": ["000", "001", "002", "003", "300", "301"],
        "BJ": ["43", "82", "83", "84", "87", "88", "920"],
    }


class StockCodeProcessor:
    """Stock pool CSV reader + code normalizer (M-003 read-path SSOT)."""

    @staticmethod
    def read_stock_codes(file_path: str) -> Optional[pd.DataFrame]:
        try:
            encoding = _check_bom(file_path)
            if encoding == "unknown":
                encoding, _confidence = _detect_encoding(file_path)
            if encoding in {"GB2312", "gb2312"}:
                encoding = "GBK"
            df = pd.read_csv(
                file_path,
                header=None,
                dtype={0: str, 1: str},
                encoding=encoding,
                skip_blank_lines=True,
            )

            def _extract_second_element(value: object) -> object:
                if isinstance(value, tuple):
                    return value[1] if len(value) > 1 else (value[0] if len(value) > 0 else "")
                return value

            df[0] = df[0].apply(_extract_second_element)
            df.rename(columns={0: "stock_code", 1: "stock_name"}, inplace=True)
            logger.info("read %s stock codes from %s", len(df), file_path)
            return df
        except Exception as exc:
            logger.error("read_stock_codes failed for %s: %s", file_path, exc)
            return None

    @staticmethod
    def format_stock_code(input_str: str) -> str:
        if not isinstance(input_str, str):
            raise ValueError("input must be str")
        digits = re.findall(r"\d+", input_str)
        if not digits:
            raise ValueError(f"no digits in {input_str!r}")
        code_str = "".join(digits).zfill(6)
        if len(code_str) != 6:
            raise ValueError(f"stock code must be 6 digits: {code_str}")
        mapping = _StockExchangeMapping.EXCHANGE_MAPPING
        if any(code_str.startswith(prefix) for prefix in mapping["SH"]):
            return f"{code_str}.SH"
        if any(code_str.startswith(prefix) for prefix in mapping["SZ"]):
            return f"{code_str}.SZ"
        if any(code_str.startswith(prefix) for prefix in mapping["BJ"]):
            return f"{code_str}.BJ"
        raise ValueError(f"unknown exchange for {code_str}")

    @staticmethod
    def batch_format_stock_codes(stock_list: List[str]) -> List[str]:
        formatted: List[str] = []
        errors: List[str] = []
        for code in stock_list:
            try:
                formatted.append(StockCodeProcessor.format_stock_code(code))
            except ValueError as exc:
                logger.warning("format_stock_code failed for %s: %s", code, exc)
                errors.append(code)
        if errors:
            logger.warning("%s stock codes failed formatting", len(errors))
        return formatted


# 兼容性接口函数
def read_stock_codes(file_path: str) -> Optional[pd.DataFrame]:
    return StockCodeProcessor.read_stock_codes(file_path)


def format_stock_code(input_str: str) -> str:
    return StockCodeProcessor.format_stock_code(input_str)


def batch_format_stock_codes(stock_list: List[str]) -> List[str]:
    return StockCodeProcessor.batch_format_stock_codes(stock_list)


def get_stock_data_from_cache(stock_code: str, start_time: str, end_time: str, period: str = '1d',
                              base_dir: str = _DEFAULT_STOCK_DATA_DIR, adjust_type: str = 'front',
                              *, use_oskh_data_reader: Optional[bool] = None) -> Optional[pd.DataFrame]:
    """Load OHLCV from local hive. RF-R2: default routes through ``oskh_data.StockDataReader``."""
    if not resolve_use_oskh_data_reader(use_oskh_data_reader):
        raise ValueError(
            "BACKTEST_USE_OSKH_DATA_READER=0 removed (RF-R2 SSOT); "
            "local OHLCV must load via oskh_data.StockDataReader"
        )
    return _get_stock_data_via_oskh_reader(
        stock_code, start_time, end_time, period, base_dir, adjust_type
    )


# ==================== 日期处理工具函数 ====================
def to_datetime(date_obj):
    """统一转换为datetime对象"""
    if isinstance(date_obj, str):
        return pd.to_datetime(date_obj)
    elif isinstance(date_obj, (date, datetime)):
        return pd.Timestamp(date_obj)
    else:
        return pd.Timestamp(date_obj)


def _timestamp_to_date(ts: Any) -> date:
    """Convert pandas Timestamp to ``date``; reject NaT."""
    stamp = pd.Timestamp(ts)
    if bool(pd.isna(stamp)):
        raise ValueError(f"invalid timestamp: {ts!r}")
    py_dt = stamp.to_pydatetime()
    return date(int(py_dt.year), int(py_dt.month), int(py_dt.day))


def is_close(a, b, abs_tol=0.001):
    """安全的浮点数比较"""
    try:
        return math.isclose(float(a), float(b), abs_tol=abs_tol)
    except (TypeError, ValueError):
        return False


def is_trading_day(check_date):
    """
    检查指定日期是否是A股交易日

    参数:
    check_date: datetime.date 或 datetime.datetime 对象

    返回:
    bool: 如果是交易日返回True，否则返回False
    """
    from common.infra.trading_calendar_pmc import get_trade_days_sse

    if isinstance(check_date, date):
        ymd = check_date.strftime("%Y%m%d")
    else:
        ymd = check_date.strftime("%Y%m%d")
    df = get_trade_days_sse(since=ymd, until=ymd)
    return df is not None and not df.empty

# ==================== 辅助函数 ====================
def check_date_in_data(df, target_date):
    """增强日期检查的安全性"""
    if df is None or df.empty:
        return False
    if not isinstance(df.index, pd.DatetimeIndex):
        df = ensure_datetime_index(df)
    if df is None or df.empty:
        return False

    # 使用统一的日期转换
    target_d = _timestamp_to_date(to_datetime(target_date))
    min_d = _timestamp_to_date(df.index.min())
    max_d = _timestamp_to_date(df.index.max())

    return min_d <= target_d <= max_d


def add_prev_close_data(df, stock_code, start_date, end_date, adjust_type: str = 'none'):
    """为分钟数据添加前收字段 - 增强日期处理版"""
    try:
        # 使用统一的日期转换
        start_date = to_datetime(start_date)
        end_date = to_datetime(end_date)
        if bool(pd.isna(start_date)) or bool(pd.isna(end_date)):
            raise ValueError(f"invalid date range for {stock_code}: {start_date!r}..{end_date!r}")

        start_ts = cast(pd.Timestamp, start_date)
        end_ts = cast(pd.Timestamp, end_date)
        start_date_prev_month = start_ts - pd.DateOffset(months=1)
        df = df.sort_index()

        daily_df = get_stock_data_from_cache(
            base_dir=_DEFAULT_STOCK_DATA_DIR,
            stock_code=stock_code,
            period='1d',
            adjust_type=adjust_type,
            start_time=_qmt_compact_range_string(start_date_prev_month),
            end_time=_qmt_compact_range_string(end_ts),
        )

        if daily_df is None or daily_df.empty:
            logger.warning(f"无法获取{stock_code}的日线数据，使用前一根K线作为前收")
            df['prevclose'] = df['close'].shift(1)
            return df

        daily_df = daily_df.sort_index()
        daily_df['prevclose'] = daily_df['close'].shift(1)

        df['trade_date'] = cast(pd.DatetimeIndex, pd.to_datetime(df.index)).normalize()  # pyright: ignore[reportAttributeAccessIssue]
        daily_df['trade_date'] = cast(pd.DatetimeIndex, pd.to_datetime(daily_df.index)).normalize()  # pyright: ignore[reportAttributeAccessIssue]

        merged_df = pd.merge(
            df.reset_index(),
            daily_df[['trade_date', 'prevclose']].drop_duplicates(),
            on='trade_date',
            how='left'
        )

        # RF-R2: reader 索引名为 ``datetime``；legacy parquet 无名索引 → ``index`` 列。
        idx_candidates: List[str] = []
        if df.index.name:
            idx_candidates.append(str(df.index.name))
        idx_candidates.extend(["index", "datetime"])
        index_col = next((c for c in idx_candidates if c in merged_df.columns), None)
        if index_col is not None:
            merged_df = merged_df.set_index(index_col)
            merged_df.index.name = None

        merged_df['prevclose'] = merged_df['prevclose'].ffill()
        merged_df['prevclose'] = merged_df['prevclose'].fillna(merged_df['close'])
        merged_df['prevclose'] = merged_df['prevclose'].clip(lower=0.01)

        return merged_df.drop('trade_date', axis=1)

    except Exception as e:
        logger.error(f"添加前收数据失败 {stock_code}: {e}")
        df['prevclose'] = df['close'].shift(1).fillna(df['close'])
        return df


def ensure_datetime_index(df):
    """确保数据框索引是datetime格式"""
    if df is None or df.empty:
        return df

    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index)
        except Exception as e:
            logger.warning(f"无法将索引转换为datetime: {e}")
            if 'date' in df.columns:
                df.index = pd.to_datetime(df['date'])
                df = df.drop('date', axis=1)

    return df


def detect_encoding(file_path):
    """检测文件的编码方式[1,5](@ref)"""
    with open(file_path, 'rb') as file:  # 以二进制模式打开文件
        raw_data = file.read()  # 读取原始字节数据
        result = chardet.detect(raw_data)  # 使用chardet检测编码
        encoding = result['encoding']
        confidence = result['confidence']  # 获取检测结果的可信度
        print(f"检测到编码: {encoding} (可信度: {confidence:.2%})")
        return encoding, confidence


def check_bom(file_path):
    """
    通过检查BOM标记判断编码格式
    """
    try:
        with open(file_path, 'rb') as file:
            raw_data = file.read(4)

        if raw_data.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
        elif raw_data.startswith(b'\xff\xfe'):
            return 'utf-16le'
        elif raw_data.startswith(b'\xfe\xff'):
            return 'utf-16be'
        elif raw_data.startswith(b'\xff\xfe\x00\x00'):
            return 'utf-32le'
        elif raw_data.startswith(b'\x00\x00\xfe\xff'):
            return 'utf-32be'
        else:
            return 'unknown'
    except:
        return 'unknown'


# 测试代码（只读缓存；下载/更新见 scripts/data/backfill_daily_data.py）
if __name__ == "__main__":
    from oskh_data.downloader import PeriodDataManager, StockDataManager

    def run_period_support():
        print("=== 周期支持测试 ===")
        test_periods = ['1m', '5m', '10m', '15m', '30m', '1h', '1d', '1w', '1M', 'invalid']
        for period in test_periods:
            is_valid = StockDataManager.validate_period(period)
            is_minute = StockDataManager.is_minute_period(period)
            period_name = StockDataManager.get_period_name(period)
            adjust_type = StockDataManager.get_recommended_adjust_type(period)
            print(f"{period}: 有效={is_valid}, 分钟={is_minute}, 名称={period_name}, 推荐复权={adjust_type}")

        test_cases = [
            ('1m', '20250101093000', '20260109150000'),
            ('1h', '20250101', '20260109'),
            ('1d', '20250101', '20260109'),
        ]
        for period, start, end in test_cases:
            is_valid, msg = PeriodDataManager.validate_time_range(period, start, end)
            print(f"{period} {start}~{end}: 有效={is_valid}, 消息={msg}")

    run_period_support()
    print("下载/回填请使用: python scripts/data/backfill_daily_data.py 或 python -m oskh_data.backfill")
