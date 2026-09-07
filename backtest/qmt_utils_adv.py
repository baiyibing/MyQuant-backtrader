import gc
import logging
import warnings
import math
import os
import re
import shutil
import time
from datetime import datetime, timedelta, date

from common.infra.timekeeping import parse_qmt_time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pandas_market_calendars as mcal
import backtrader as bt
import chardet
import pandas as pd
import numpy as np  # 确保已导入numpy
from tqdm import tqdm
from xtquant import xtdata

# 配置日志
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 全局缓存交易日历（模块级别缓存，避免重复获取）
# XSHG_CALENDAR = mcal.get_calendar('XSHG')

# 获取A股交易日历（使用上海证券交易所）
SSE_CALENDAR = mcal.get_calendar('SSE')

# ---------------------------------------------------------------------------
# oskh_data 重构通知：
# StockDataManager, PeriodDataManager, DataDownloader 的规范版本已迁移至
# oskh_data.downloader。新代码请用: from oskh_data import DataDownloader
# 本文件保留原实现用于向后兼容，后续大版本将移除重复定义。
# ---------------------------------------------------------------------------

class StockDataManager:
    """股票数据管理器"""
    # 交易所映射配置
    EXCHANGE_MAPPING = {
        'SH': ['600', '601', '603', '605', '688'],  # 上交所
        'SZ': ['000', '001', '002', '003', '300', '301'],  # 深交所
        'BJ': ['43', '82', '83', '84', '87', '88', '920']  # 北交所
    }

    # 复权类型映射 - 修正：分钟K线只支持none
    ADJUST_MAPPING = {
        'none': 'none',
        'front': 'front',  # 仅日线及以上支持
        'back': 'back'  # 仅日线及以上支持
    }

    # 支持的K线周期映射
    PERIOD_MAPPING = {
        # 分钟级别
        '1m': ('1分钟', True),
        '5m': ('5分钟', True),
        '10m': ('10分钟', True),
        '15m': ('15分钟', True),
        '30m': ('30分钟', True),
        '1h': ('60分钟', True),
        # 日级别及以上
        '1d': ('日线', False),
        '1w': ('周线', False),
        '1M': ('月线', False)
    }

    def __init__(self, base_dir: str = "../stock_data"):
        self.base_dir = Path(base_dir)
        self._ensure_directories()

    def _ensure_directories(self):
        """确保必要的目录存在"""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate_period(cls, period: str) -> bool:
        """验证周期参数是否有效"""
        return period in cls.PERIOD_MAPPING

    @classmethod
    def is_minute_period(cls, period: str) -> bool:
        """判断是否为分钟级别周期"""
        return cls.PERIOD_MAPPING.get(period, (None, False))[1]

    @classmethod
    def get_period_name(cls, period: str) -> str:
        """获取周期名称"""
        return cls.PERIOD_MAPPING.get(period, ('未知周期', False))[0]

    @classmethod
    def get_recommended_adjust_type(cls, period: str) -> str:
        """获取推荐的复权类型 - 修正：分钟线返回none"""
        # 分钟K线只能使用none
        return 'none' if cls.is_minute_period(period) else 'front'


class StockCodeProcessor:
    """股票代码处理器"""

    @staticmethod
    def read_stock_codes(file_path: str) -> Optional[pd.DataFrame]:
        """读取股票代码文件"""
        try:
            # 方法1: 检查BOM（字节顺序标记）
            encoding = check_bom(file_path)
            confidence = 1.0
            if encoding != 'unknown':
                pass
            else:
                # 方法2: 检查BOM（字节顺序标记）
                encoding, confidence = detect_encoding(file_path)

            if encoding in ['GB2312', 'gb2312']:
                encoding = 'GBK'

            # 尝试读取CSV文件
            df = pd.read_csv(file_path, header=None, dtype={0: str, 1: str}, encoding=encoding, skip_blank_lines=True)

            print("处理前的第一列数据:")
            print(df[0])

            # 处理第一列：如果值是元组，则提取第二个值
            def extract_second_element(value):
                if isinstance(value, tuple):
                    # 如果元组有至少两个元素，返回第二个元素；否则返回第一个元素或空字符串
                    return value[1] if len(value) > 1 else (value[0] if len(value) > 0 else '')
                else:
                    # 如果不是元组，保持原值
                    return value

            # 应用处理函数到第一列
            df[0] = df[0].apply(extract_second_element)

            print("处理后的第一列数据:")
            print(df[0])

            df.rename(columns={0: 'stock_code', 1: 'stock_name'}, inplace=True)

            logger.info(f"成功读取 {len(df)} 条股票代码记录")
            return df
        except Exception as e:
            logger.error(f"读取文件失败: {e}")
            return None

    @staticmethod
    def format_stock_code(input_str: str) -> str:
        """格式化股票代码，添加交易所后缀"""
        if not isinstance(input_str, str):
            raise ValueError("输入必须是字符串")
        # 提取数字部分
        digits = re.findall(r'\d+', input_str)
        if not digits:
            raise ValueError(f"输入中未找到数字: {input_str}")
        code_str = ''.join(digits).zfill(6)
        if len(code_str) != 6:
            raise ValueError(f"股票代码必须是6位数字: {code_str}")
        # 判断交易所
        sh_prefixes = StockDataManager.EXCHANGE_MAPPING['SH']
        sz_prefixes = StockDataManager.EXCHANGE_MAPPING['SZ']
        bj_prefixes = StockDataManager.EXCHANGE_MAPPING['BJ']
        if any(code_str.startswith(prefix) for prefix in sh_prefixes):
            return f"{code_str}.SH"
        elif any(code_str.startswith(prefix) for prefix in sz_prefixes):
            return f"{code_str}.SZ"
        elif any(code_str.startswith(prefix) for prefix in bj_prefixes):
            return f"{code_str}.BJ"
        else:
            raise ValueError(f"无法识别交易所: {code_str}")

    @staticmethod
    def batch_format_stock_codes(stock_list: List[str]) -> List[str]:
        """批量格式化股票代码"""
        formatted_codes = []
        errors = []
        for code in stock_list:
            try:
                formatted_code = StockCodeProcessor.format_stock_code(code)
                formatted_codes.append(formatted_code)
            except ValueError as e:
                logger.warning(f"股票代码格式化失败 {code}: {e}")
                errors.append(code)
        if errors:
            logger.warning(f"共 {len(errors)} 个代码格式化失败")
        return formatted_codes

class PeriodDataManager:
    """周期数据管理器"""

    @staticmethod
    def validate_time_range(period: str, start_time: str, end_time: str) -> Tuple[bool, str]:
        """验证时间范围是否合理"""
        try:
            start_dt = pd.to_datetime(start_time)
            end_dt = pd.to_datetime(end_time)
            if start_dt > end_dt:
                return False, "开始时间不能晚于结束时间"
            # 分钟数据的时间范围限制
            if StockDataManager.is_minute_period(period):
                time_diff = end_dt - start_dt
                max_days = {
                    '1m': 7,  # 1分钟数据最多7天
                    '5m': 30,  # 5分钟数据最多30天
                    '10m': 30,  # 5分钟数据最多30天
                    '15m': 90,  # 15分钟数据最多90天
                    '30m': 180,  # 30分钟数据最多180天
                    '1h': 365  # 60分钟数据最多1年
                }.get(period, 30)
                if time_diff.days > max_days:
                    pass
                    # return False, f"{period}数据最多下载{max_days}天"
            return True, "时间范围有效"
        except Exception as e:
            return False, f"时间格式错误: {e}"

    @staticmethod
    def get_file_path(base_dir: Path, period: str, adjust_type: str, stock_code: str) -> Path:
        """获取数据文件路径"""
        safe_stock_code = stock_code.replace('.', '_')
        path = (base_dir / f"period={period}" / f"dividend_type={adjust_type}" / f"symbol={safe_stock_code}")
        path.mkdir(parents=True, exist_ok=True)
        return path / "data.parquet"



    @staticmethod
    def process_minute_data(df: pd.DataFrame) -> pd.DataFrame:
        """处理分钟数据：过滤非交易时间（包含节假日和交易时段）- 修复索引问题"""
        if df.empty:
            return df

        # 预防性检查索引类型
        if not isinstance(df.index, pd.DatetimeIndex):
            logger.warning(f"索引类型异常: 期望 DatetimeIndex, 实际: {type(df.index)}")
            df = df.copy()
            df.index = pd.to_datetime(df.index)

        # 确保索引唯一
        if not df.index.is_unique:
            logger.warning("索引不唯一，将重置索引")
            df = df.reset_index(drop=True)

        calendar = SSE_CALENDAR

        min_date = df.index.min()
        max_date = df.index.max()
        trading_days = calendar.schedule(
            min_date.strftime('%Y-%m-%d'),
            max_date.strftime('%Y-%m-%d')
        ).index
        trading_days_date = trading_days.date  # numpy array of dates

        # 修复1: 使用 np.isin 替代 Series.isin
        # 正确：使用 np.isin 处理 NumPy 数组
        mask_date = np.isin(df.index.date.astype('datetime64[D]'), trading_days_date)

        # 修复2: 确保 mask_time 是布尔数组
        minutes = df.index.hour * 60 + df.index.minute
        mask_time = (
                ((minutes >= 570) & (minutes <= 690)) |  # 09:30-11:30 (570-690分钟)
                ((minutes >= 780) & (minutes <= 900))  # 13:00-15:00 (780-900分钟)
        )

        # 修复3: 合并为布尔数组
        mask = mask_date & mask_time

        return df[mask]
    # def process_minute_data(df: pd.DataFrame) -> pd.DataFrame:
    #     """处理分钟数据：过滤非交易时间"""
    #     if df.empty:
    #         return df
    #
    #     def is_trading_time(ts):
    #         time_val = ts.time()
    #         weekday = ts.weekday()
    #         # 排除周末
    #         if weekday >= 5:
    #             return False
    #         # 交易时间段
    #         # 放宽边界条件，包含15:00:00
    #         return ((pd.Timestamp('09:30:00').time() <= time_val <= pd.Timestamp('11:30:00').time()) or
    #                 (pd.Timestamp('13:00:00').time() <= time_val <= pd.Timestamp('15:00:00').time()) or
    #                 (time_val == pd.Timestamp('15:00:00').time()))  # 明确包含15:00
    #
    #     mask = df.index.map(is_trading_time)
    #     return df[mask]


class DataDownloader:
    """数据下载器"""

    def __init__(self, base_dir: str = "../stock_data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def download_data(self, stock_list: List[str], start_time: str, end_time: str, period: str = '1d',
                      adjust_type: str = 'front', incrementally: bool = False, callback: Optional[callable] = None) -> Dict[str, pd.DataFrame]:
        """下载股票数据（完全支持分钟和日K线，支持增量下载）"""
        # 参数验证
        if not StockDataManager.validate_period(period):
            logger.error(f"不支持的周期: {period}")
            return {}

        is_valid, msg = PeriodDataManager.validate_time_range(period, start_time, end_time)
        if not is_valid:
            logger.error(f"时间范围无效: {msg}")
            return {}

        # 修正：分钟K线强制使用none复权
        if StockDataManager.is_minute_period(period):
            adjust_type = 'none'
            logger.info(f"分钟周期 {period} 强制使用复权类型 'none'")
        else:
            if adjust_type not in StockDataManager.ADJUST_MAPPING:
                logger.warning(f"无效复权类型: {adjust_type}, 使用默认值")
                adjust_type = StockDataManager.get_recommended_adjust_type(period)

        logger.info(f"开始下载{StockDataManager.get_period_name(period)}数据: "
                    f"{len(stock_list)}只股票, {start_time}至{end_time} (复权: {adjust_type})")

        # 增量下载逻辑：检查本地数据状态
        if incrementally:
            logger.info("检查本地数据状态，筛选需要更新的股票...")
            need_update_stocks = []
            for stock_code in stock_list:
                # 构建文件路径
                file_path = PeriodDataManager.get_file_path(
                    self.base_dir, period, adjust_type, stock_code
                )
                if os.path.exists(file_path):
                    try:
                        # 读取本地数据的最新日期
                        existing_data = pd.read_parquet(file_path, engine='pyarrow')
                        if not existing_data.empty and isinstance(existing_data.index, pd.DatetimeIndex):
                            latest_date = existing_data.index.max()
                            end_dt = pd.to_datetime(end_time)

                            # 修正：处理分钟线边界条件
                            # if period == '1m' and latest_date == end_dt:
                            #     # 本地最新日期等于请求结束时间，但XTQuant不包含结束时间点
                            #     # 需要下载下一分钟（14:59:00 -> 15:00:00）
                            #     logger.info(
                            #         f"⚠️ 本地数据最新日期 {latest_date} 等于请求结束时间 {end_dt}, 需要下载下一分钟")
                            #     need_update_stocks.append(stock_code)
                            # el
                            if latest_date < end_dt:
                                logger.info(
                                    f"🔁 {stock_code} {period}需要更新，本地最新日期: {latest_date.strftime('%Y-%m-%d %H:%M:%S')}"
                                )
                                need_update_stocks.append(stock_code)
                            else:
                                logger.info(
                                    f"✅ {stock_code} {period}数据已是最新，跳过下载 (本地最新: {latest_date.strftime('%Y-%m-%d %H:%M:%S')}, 请求结束: {end_dt.strftime('%Y-%m-%d %H:%M:%S')})"
                                )

                        else:
                            need_update_stocks.append(stock_code)
                    except Exception as e:
                        logger.warning(f"检查 {stock_code} {period}本地数据时出错: {e}，将重新下载")
                        need_update_stocks.append(stock_code)
                else:
                    need_update_stocks.append(stock_code)
                    logger.info(f"📥 {stock_code} {period}本地无数据，需要下载")

            # 更新需要下载的股票列表，优先下载需要更新的股票，如果没有指定哪些需要更新，则下载全部股票。
            if need_update_stocks:  # 列表非空时才需要下载
                actual_download_list = need_update_stocks
                logger.info(f"实际需要下载的股票数量: {len(actual_download_list)}/{len(stock_list)}")
            else:
                actual_download_list = []
                logger.info("所有股票数据均已最新，无需下载")

            # logger.info(f"📥 {need_update_stocks} {period}本地无数据，需要下载")
            # actual_download_list = need_update_stocks if (need_update_stocks is not None and len(need_update_stocks) >= 0)  else stock_list
            # logger.info(f"实际需要下载的股票数量: {len(actual_download_list)}/{len(stock_list)}")
        else:
            actual_download_list = stock_list

        # 如果没有需要下载的股票，直接返回
        if not actual_download_list:
            logger.info("所有股票数据均已最新，无需下载")
            return {}

        # 优化1: 解决分钟线最后一分钟BUG
        # 为分钟线自动调整结束时间（增加1分钟），确保包含最后一分钟
        adjusted_end_time = end_time
        if period == '1m':
            try:
                # 转换为datetime对象
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    end_dt = parse_qmt_time(end_time)
                # 增加1分钟
                adjusted_end_time = (end_dt + timedelta(minutes=1)).strftime('%Y%m%d%H%M%S')
                logger.info(f"分钟线自动调整结束时间: {end_time} -> {adjusted_end_time} (确保包含最后一分钟)")
            except Exception as e:
                logger.error(f"调整分钟线结束时间失败: {e}")
                # 保持原始时间，避免失败
                adjusted_end_time = end_time

        try:
            # 创建进度条
            # progress_bar = tqdm(total=len(actual_download_list), desc="下载进度", unit="股票")

            # 优化2: 使用回调函数实现精确等待
            total_stocks = len(actual_download_list)
            downloaded_set = set()
            download_complete = False

            # 默认回调函数（如果未提供自定义回调）
            # if callback is None:
            def on_progress(data):
                nonlocal downloaded_set, download_complete
                # print(data)
                # {'finished': 1, 'total': 312, 'stockcode': '', 'message': '600346.SH'}
                # {'finished': 2, 'total': 312, 'stockcode': '', 'message': '600346.SH'}
                # {'finished': 3, 'total': 312, 'stockcode': '', 'message': '600346.SH'}
                # {'finished': 4, 'total': 312, 'stockcode': '', 'message': '600346.SH'}
                # {'finished': 5, 'total': 312, 'stockcode': '', 'message': '600346.SH'}
                # ...
                # {'finished': 308, 'total': 312, 'stockcode': '', 'message': '000001.SZ'}
                # {'finished': 309, 'total': 312, 'stockcode': '', 'message': '000001.SZ'}
                # {'finished': 310, 'total': 312, 'stockcode': '', 'message': '000001.SZ'}
                # {'finished': 311, 'total': 312, 'stockcode': '', 'message': '000001.SZ'}
                # {'finished': 312, 'total': 312, 'stockcode': '', 'message': '000001.SZ'}
                finished = data.get('finished', 0)
                total = data.get('total', 0)
                stock_code = data.get('message', 'N/A')
                downloaded_set.add(stock_code)
                if finished > 0 and total > 0:
                    progress = (finished / total) * 100
                    logger.info(f"下载进度: {finished}/{total} ({progress:.2f}%) - 当前股票: {stock_code}")
                    # 添加这一行更新tqdm进度条
                    # progress_bar.update()  # 这是关键修复
                if finished == total:
                    download_complete = True

            # 在调用xtdata.download_history_data2之前
            logger.info(f"开始下载，将使用回调函数: {on_progress}")

            # 下载数据
            xtdata.download_history_data2(
                stock_list=actual_download_list,
                period=period,
                start_time=start_time,
                end_time=adjusted_end_time,  # 使用调整后的结束时间
                incrementally=incrementally,  # 使用传入的incrementally参数
                callback=on_progress
            )

            # 动态等待时间
            # wait_time = self._calculate_wait_time(len(actual_download_list), period)
            # logger.info(f"等待数据下载完成: {wait_time}秒")
            # time.sleep(wait_time)

            # 优化3: 精确等待下载完成（基于回调函数）
            logger.info(f"等待{total_stocks}只股票下载完成...")
            while not download_complete:
                time.sleep(0.05)
                downloaded_count = len(downloaded_set)
                if downloaded_count > 0:
                    logger.info(f"下载中: {downloaded_count}/{total_stocks} 已完成")
                else:
                    logger.info(f"下载中: {downloaded_count}/{total_stocks} ")

            # 关闭进度条
            # progress_bar.close()
            logger.info(f"✅ 下载完成！共 {total_stocks} 个股票")

            # 获取数据
            raw_data = xtdata.get_market_data_ex(
                field_list=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'],
                stock_list=stock_list,
                period=period,
                start_time=start_time,
                end_time=adjusted_end_time,  # 使用调整后的结束时间
                count=-1,
                dividend_type=adjust_type,
                fill_data=True
            )

            return self._process_downloaded_data(raw_data, stock_list, period, adjust_type, start_time, end_time)
        except Exception as e:
            logger.error(f"数据下载失败: {e}")
            return {}

    def _calculate_wait_time(self, stock_count: int, period: str) -> float:
        """计算等待时间"""
        base_time = 3.0
        stock_factor = 0.1
        period_factor = 2.0 if StockDataManager.is_minute_period(period) else 0.5
        return base_time + stock_count * stock_factor * period_factor

    def _process_downloaded_data(self, raw_data: Dict, stock_list: List[str], period: str, adjust_type: str,
                                 start_time: str, end_time: str) -> Dict[str, pd.DataFrame]:
        """优化后的处理下载数据方法 - 速度提升显著"""
        result_data = {}
        start_dt = pd.to_datetime(start_time)
        end_dt = pd.to_datetime(end_time)

        # 为分钟数据额外延长1分钟边界
        if StockDataManager.is_minute_period(period):
            end_dt += pd.Timedelta(minutes=1)

        # 优化1: 预先转换时间范围
        start_dt = pd.Timestamp(start_dt)
        end_dt = pd.Timestamp(end_dt)

        # 优化2: 批量处理数据，避免频繁I/O
        processed_data = {}

        # 优化3: 避免在循环内创建新对象
        required_cols = ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']

        for stock_code in tqdm(stock_list, desc="处理股票数据"):
            try:
                # 检查原始数据存在性
                if stock_code not in raw_data or raw_data[stock_code] is None:
                    logger.warning(f"股票数据为空: {stock_code} (原始数据检查)")
                    continue

                stock_df = raw_data[stock_code]
                logger.debug(f"原始数据检查: {stock_code} - 类型: {type(stock_df)}, 长度: {len(stock_df)}")

                # 检查数据类型
                if not isinstance(stock_df, pd.DataFrame):
                    logger.error(f"数据类型错误: {stock_code} - 期望DataFrame, 实际类型: {type(stock_df)}")
                    continue

                if stock_df.empty:
                    logger.warning(f"空DataFrame: {stock_code}")
                    continue

                # 优化4: 避免重复转换，使用更高效的列转换
                for col in numeric_cols:
                    if col in stock_df.columns:
                        stock_df[col] = pd.to_numeric(stock_df[col], errors='coerce')

                # 添加转换后类型检查
                logger.debug(f"列转换后: {stock_code} - 类型: {type(stock_df)}, 列: {list(stock_df.columns)}")

                # 优化5: 直接过滤空值
                stock_df = stock_df.dropna(subset=numeric_cols)
                logger.debug(f"空值过滤后: {stock_code} - 行数: {len(stock_df)}, 有效列: {numeric_cols}")
                if stock_df.empty:
                    logger.warning(f"过滤后为空: {stock_code}")
                    continue

                # 优化6: 确保索引是datetime格式
                if not isinstance(stock_df.index, pd.DatetimeIndex):
                    stock_df.index = pd.to_datetime(stock_df.index)
                    logger.debug(f"索引转换: {stock_code} - 新索引类型: {type(stock_df.index)}")

                # 优化7: 确保索引是排序的
                stock_df = stock_df.sort_index()
                logger.debug(f"排序后: {stock_code} - 索引范围: {stock_df.index.min()} to {stock_df.index.max()}")

                # 优化8: 使用loc进行时间范围过滤
                filtered_df = stock_df.loc[start_dt:end_dt]
                logger.debug(
                    f"时间过滤: {stock_code} - 原始行: {len(stock_df)}, 过滤后: {len(filtered_df)}, 范围: {start_dt} to {end_dt}")
                if filtered_df.empty:
                    logger.warning(f"时间过滤后为空: {stock_code}")
                    continue

                # 优化9: 分钟数据特殊处理（添加类型预检查）
                if StockDataManager.is_minute_period(period):
                    # 关键：在调用前检查数据类型
                    if not isinstance(filtered_df, pd.DataFrame):
                        logger.error(f"分钟数据处理错误: {stock_code} - 期望DataFrame, 实际类型: {type(filtered_df)}")
                        continue
                    logger.debug(
                        f"分钟数据处理前: {stock_code} - 类型: {type(filtered_df)}, 前3行: {filtered_df.head(3).to_markdown()}")
                    filtered_df = PeriodDataManager.process_minute_data(filtered_df)
                    logger.debug(
                        f"分钟数据处理后: {stock_code} - 行数: {len(filtered_df)}, 前3行: {filtered_df.head(3).to_markdown()}")

                processed_data[stock_code] = filtered_df

            except Exception as e:
                # 详细异常日志：包含上下文状态
                logger.error(f"处理股票数据失败 {stock_code}: {type(e).__name__} - {str(e)}", exc_info=True)
                logger.error(f"异常上下文: {stock_code} - 当前状态:")
                logger.error(
                    f"  stock_df 类型: {type(stock_df) if 'stock_df' in locals() else 'N/A'}, 行数: {len(stock_df) if 'stock_df' in locals() else 'N/A'}")
                logger.error(
                    f"  filtered_df 类型: {type(filtered_df) if 'filtered_df' in locals() else 'N/A'}, 行数: {len(filtered_df) if 'filtered_df' in locals() else 'N/A'}")
                logger.error(f"  numeric_cols: {numeric_cols}")
                if 'filtered_df' in locals() and not filtered_df.empty:
                    logger.error(f"  filtered_df 前3行: {filtered_df.head(3).to_markdown()}")
                continue

        # 优化10: 批量写入文件，支持合并已有数据（向前补录场景）
        for stock_code, df_new in tqdm(processed_data.items(), desc="写入文件"):
            file_path = PeriodDataManager.get_file_path(
                self.base_dir, period, adjust_type, stock_code)
            if file_path.exists():
                df_existing = pd.read_parquet(file_path, engine='pyarrow')
                df_merged = pd.concat([df_existing, df_new])
                df_merged = df_merged[~df_merged.index.duplicated(keep='last')]
                df_merged = df_merged.sort_index()
                df_merged.to_parquet(file_path, engine='pyarrow', compression='snappy')
            else:
                df_new.to_parquet(file_path, engine='pyarrow', compression='snappy')

        result_data = processed_data
        logger.info(f"成功处理 {len(result_data)} 只股票数据")
        return result_data

    def get_stock_data(self, stock_code: str, start_time: str, end_time: str, period: str = '1d',
                       adjust_type: str = 'front') -> Optional[pd.DataFrame]:
        """获取单只股票数据"""
        if not StockDataManager.validate_period(period):
            logger.error(f"不支持的周期: {period}")
            return None

        # 修正：分钟K线强制使用none复权
        if StockDataManager.is_minute_period(period):
            adjust_type = 'none'
            logger.info(f"分钟周期 {period} 强制使用复权类型 'none' (获取数据时)")

        file_path = PeriodDataManager.get_file_path(
            self.base_dir, period, adjust_type, stock_code
        )
        if not file_path.exists():
            return None

        try:
            df = pd.read_parquet(file_path, engine='pyarrow')
            # 时间过滤
            start_dt = pd.to_datetime(start_time)
            end_dt = pd.to_datetime(end_time)
            mask = (df.index >= start_dt) & (df.index <= end_dt)
            filtered_df = df.loc[mask]
            logger.info(f"加载成功: {stock_code}, 数据量: {len(filtered_df)}")
            return filtered_df
        except Exception as e:
            logger.error(f"加载数据失败 {stock_code}: {e}")
            return None

    def get_available_periods(self) -> List[str]:
        """获取可用的数据周期"""
        periods_dir = self.base_dir / "period=1d"  # 检查默认目录
        if periods_dir.exists():
            return list(StockDataManager.PERIOD_MAPPING.keys())
        return []


class DataCleaner:
    """数据清理器"""

    @staticmethod
    def clear_data(base_dir: str = "../stock_data", period: Optional[str] = None,
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


# 兼容性接口函数
def read_stock_codes(file_path: str) -> Optional[pd.DataFrame]:
    return StockCodeProcessor.read_stock_codes(file_path)


def format_stock_code(input_str: str) -> str:
    return StockCodeProcessor.format_stock_code(input_str)


def batch_format_stock_codes(stock_list: List[str]) -> List[str]:
    return StockCodeProcessor.batch_format_stock_codes(stock_list)


def get_miniqmt_data(stock_list: List[str], start_time: str, end_time: str, period: str = '1d',
                     base_dir: str = "../stock_data", adjust_type: str = 'front',
                     incrementally: bool = False) -> Dict[str, pd.DataFrame]:
    downloader = DataDownloader(base_dir)
    return downloader.download_data(
        stock_list, start_time, end_time, period, adjust_type, incrementally
    )


def get_stock_data_from_cache(stock_code: str, start_time: str, end_time: str, period: str = '1d',
                              base_dir: str = "../stock_data", adjust_type: str = 'front') -> Optional[pd.DataFrame]:
    downloader = DataDownloader(base_dir)
    return downloader.get_stock_data(stock_code, start_time, end_time, period, adjust_type)


def clear_stock_data(base_dir: str = "../stock_data", period: Optional[str] = None,
                     adjust_type: Optional[str] = None, stock_code: Optional[str] = None):
    DataCleaner.clear_data(base_dir, period, adjust_type, stock_code)


# ==================== 日期处理工具函数 ====================
def to_datetime(date_obj):
    """统一转换为datetime对象"""
    if isinstance(date_obj, str):
        return pd.to_datetime(date_obj)
    elif isinstance(date_obj, (date, datetime)):
        return pd.Timestamp(date_obj)
    else:
        return pd.Timestamp(date_obj)


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
    # 转换为datetime格式
    if isinstance(check_date, date):
        check_date = datetime.combine(check_date, datetime.min.time())

    # 检查是否为交易日
    trading_days = SSE_CALENDAR.valid_days(start_date=check_date, end_date=check_date)

    return len(trading_days) > 0

# ==================== 自定义数据类 ====================
class PrevClosePandasData(bt.feeds.PandasData):
    """包含前收字段的自定义数据类"""
    lines = ('prev_close', 'turnover_rate')  # 前收 + 换手率
    params = (
        ('datetime', None),
        ('open', -1),
        ('high', -1),
        ('low', -1),
        ('close', -1),
        ('volume', -1),
        ('prev_close', -1),
        ('turnover_rate', -1),
    )


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
    target_date = to_datetime(target_date).date()
    min_date = to_datetime(df.index.min()).date()
    max_date = to_datetime(df.index.max()).date()

    return min_date <= target_date <= max_date


def add_prev_close_data(df, stock_code, start_date, end_date, adjust_type: str = 'none'):
    """为分钟数据添加前收字段 - 增强日期处理版"""
    try:
        # 使用统一的日期转换
        start_date = to_datetime(start_date)
        end_date = to_datetime(end_date)

        start_date_prev_month = start_date - pd.DateOffset(months=1)
        df = df.sort_index()

        daily_df = get_stock_data_from_cache(
            base_dir="../stock_data",
            stock_code=stock_code,
            period='1d',
            adjust_type=adjust_type,
            start_time=start_date_prev_month,
            end_time=end_date
        )

        if daily_df is None or daily_df.empty:
            logger.warning(f"无法获取{stock_code}的日线数据，使用前一根K线作为前收")
            df['prevclose'] = df['close'].shift(1)
            return df

        daily_df = daily_df.sort_index()
        daily_df['prevclose'] = daily_df['close'].shift(1)

        df['trade_date'] = pd.to_datetime(df.index).normalize()
        daily_df['trade_date'] = pd.to_datetime(daily_df.index).normalize()

        merged_df = pd.merge(
            df.reset_index(),
            daily_df[['trade_date', 'prevclose']].drop_duplicates(),
            on='trade_date',
            how='left'
        )

        if 'index' in merged_df.columns:
            merged_df = merged_df.set_index('index')
            merged_df.index.name = df.index.name

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


def load_single_stock_data(code, start_dt, end_dt, buy_date, adjust_type: str = 'none'):
    """加载单个股票的数据 - 拆分后的函数"""
    try:
        df = get_stock_data_from_cache(
            base_dir="../stock_data",
            stock_code=code,
            period='1m',
            adjust_type=adjust_type,
            start_time=start_dt,
            end_time=end_dt
        )
        # if df is not None:
        #     print(f"{code}股票1m数据{start_dt} -》{end_dt}示例(后5行):")
        #     print(df.tail())
        #     print(f"数据形状: {df.shape}")
        df = ensure_datetime_index(df)

        if not df.empty:
            print(f"📅 {code} 数据日期范围: {df.index.min()} 到 {df.index.max()}")

        df = add_prev_close_data(df, code, start_dt, end_dt)
        df = ensure_datetime_index(df)

        data_contains_buy_date = check_date_in_data(df, buy_date)
        if not data_contains_buy_date:
            print(f"⚠️ {code} 缺少买入日期 {buy_date} 的1m数据")
            return None, False

        df = df.copy()
        df = df.sort_index()

        # Backtrader内部字段名必须小写
        # 参数映射是：backtrader字段 → DataFrame列名
        # 最佳实践：统一DataFrame列名为小写标准
        # datetime通常使用索引，不需要显式列
        # MiniQMT字段名：全部小写 (open, high, low, close, volume, amount)

        data = PrevClosePandasData(
            dataname=df,
            open='open',
            high='high',
            low='low',
            close='close',
            volume='volume',
            prev_close='prevclose',
            timeframe=bt.TimeFrame.Minutes,
            compression=1,
            fromdate=pd.to_datetime(start_dt),
            todate=pd.to_datetime(end_dt)
        )

        return data, True

    except Exception as e:
        print(f"❌ {code} 数据加载失败: {e}")
        import traceback
        print(traceback.format_exc())
        return None, False

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


# 测试代码
if __name__ == "__main__":
    def read_stock_data(period: str = '1d'):
        file_path = r"E:\PycharmProjects\OSkhQuant1.3\stock_pool\20260130.csv"  # 请替换为实际文件路径
        stock_df = read_stock_codes(file_path)

        if stock_df is None:
            print("无法读取股票代码文件，请检查路径")
            return

        stock_list = stock_df['stock_code'].tolist()
        processed_list = batch_format_stock_codes(stock_list)

        for original, processed in zip(stock_list, processed_list):
            print(f"{original} -> {processed}")

        processed_list.append('000001.SZ')
        for stock_code in processed_list:
            # 4. 从缓存中获取单个股票数据
            print("\n=== 从缓存获取单个股票数据 ===")
            single_stock_data = get_stock_data_from_cache(
                base_dir="../stock_data",
                stock_code=stock_code,
                period=period,
                adjust_type='front',
                start_time='20260101',
                end_time='20261231'
            )
            if single_stock_data is not None:
                print(f"{stock_code}股票{period}数据示例(后5行):")
                print(single_stock_data.tail())
                print(f"数据形状: {single_stock_data.shape}")

    def run_period_support():
        """测试周期支持功能"""
        print("=== 周期支持测试 ===")
        # 测试周期验证
        test_periods = ['1m', '5m', '10m', '15m', '30m', '1h', '1d', '1w', '1M', 'invalid']
        for period in test_periods:
            is_valid = StockDataManager.validate_period(period)
            is_minute = StockDataManager.is_minute_period(period)
            period_name = StockDataManager.get_period_name(period)
            adjust_type = StockDataManager.get_recommended_adjust_type(period)
            print(f"{period}: 有效={is_valid}, 分钟={is_minute}, 名称={period_name}, 推荐复权={adjust_type}")

        # 测试时间范围验证
        test_cases = [
            ('1m', '20250101093000', '20260109150000'),  # 有效：7天
            ('1h', '20250101', '20260109'),  # 无效：超过31天
            ('1d', '20250101', '20260109'),  # 有效：日线无限制
        ]
        for period, start, end in test_cases:
            is_valid, msg = PeriodDataManager.validate_time_range(period, start, end)
            print(f"{period} {start}~{end}: 有效={is_valid}, 消息={msg}")


    def run_download_example():
        """测试下载示例"""
        print("\n=== 下载示例测试 ===")
        from pathlib import Path
        path = Path('../stock_pool')
        # 递归查找所有 .csv 文件
        csv_files = list(path.rglob('*.csv'))

        for file_path in csv_files:
            # 示例股票列表
            # file_path = r"../stock_pool/20251219.csv"
            print(file_path)
            stock_df = read_stock_codes(file_path)

            if stock_df is None:
                print("无法读取股票代码文件，请检查路径")
                return

            stock_list = stock_df['stock_code'].tolist()

            # stock_list = []
            # stock_list.append('000421')
            # stock_list.append('000662')
            # stock_list.append('000665')
            # stock_list.append('000777')
            # stock_list.append('001335')
            # stock_list.append('002309')
            # stock_list.append('301629')
            # stock_list.append('603014')
            # stock_list.append('301329')

            processed_list = batch_format_stock_codes(stock_list)

            for original, processed in zip(stock_list, processed_list):
                print(f"{original} -> {processed}")

            processed_list.append('000001.SZ')

            # 创建下载器
            downloader = DataDownloader()

            # 测试不同周期的下载
            test_cases = [
                ('1d', '20250101', '20260514', 'front', True), # 日线，增量下载
                ('1d', '20250101', '20260514', 'none', True),  # 日线，增量下载
                ('1d', '20250101', '20260514', 'back', True),  # 日线，增量下载
                # ('1m', '20250101093000', '20260109150000', 'none', True),  # 分钟线，增量下载（注意：会强制转为none）
            ]

            for period, start, end, adjust_type, incrementally in test_cases:
                print(
                    f"\n下载{StockDataManager.get_period_name(period)}数据 ({adjust_type})... (增量下载: {incrementally})")
                data = get_miniqmt_data(
                    stock_list=processed_list,
                    start_time=start,
                    end_time=end,
                    period=period,
                    adjust_type=adjust_type,
                    incrementally=incrementally
                )
                print(f"成功下载 {len(data)} 只股票数据")

                # 显示数据信息
                for stock, df in data.items():
                    if df is not None and not df.empty:
                        print(f" {period} {stock}: {len(df)} 条记录, 时间范围: {df.index.min()} ~ {df.index.max()}")

            # if file_path=='../stock_pool/20251219.csv':
            #     break
            # break


    # 运行测试
    run_period_support()
    run_download_example()
    # read_stock_data('1d')
