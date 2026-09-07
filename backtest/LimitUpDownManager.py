import backtrader as bt
from datetime import datetime, date, timedelta
import pandas as pd
import re
import logging
import numpy as np
from collections import deque
import copy
import pandas_market_calendars as mcal
import bisect

from qmt_utils_adv import is_close, to_datetime

# 设置日志
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LimitUpDownManager:
    """涨跌停限制管理器

    该类负责管理股票的涨跌停价格计算和判断，确保交易符合A股市场的涨跌停规则。
    A股市场涨跌幅限制根据股票类型（主板、创业板、科创板、北交所等）有所不同。
    """

    def __init__(self):
        # 字典，键为股票代码，值为涨停价
        self.limit_up_prices = {}
        # 字典，键为股票代码，值为跌停价
        self.limit_down_prices = {}
        # 已弃用，保留此属性仅为避免兼容性问题
        self.limit_status = {}
        # 股票代码前缀与对应涨跌幅比例的映射
        self._prefix_map = {
            '30': 0.20,   # 创业板（300开头）
            '68': 0.20,   # 科创板（688开头）
            '4': 0.30,    # 北交所（43、83、87、88开头）
            '8': 0.30,    # 北交所（43、83、87、88开头）
            '92': 0.30,   # 北交所（920开头，自2025年10月9日起统一使用）
            '00': 0.10,   # 深交所主板（000、001、002、003等）
            '60': 0.10    # 上交所主板（600、601、603等）
        }

    def _calculate_limit_price(self, stock_code, prev_close, direction):
        """统一的涨跌停价格计算函数

        参数:
        stock_code (str): 股票代码
        prev_close (float): 前一日收盘价
        direction (str): 价格方向 ('UP'表示涨停, 'DOWN'表示跌停)

        返回:
        float: 计算得到的涨停价或跌停价（保留两位小数）
        """
        limit_pct = self._get_limit_percentage(stock_code)  # 获取涨跌幅比例
        if direction == 'UP':
            return round(prev_close * (1 + limit_pct), 2)   # 计算涨停价
        else:
            return round(prev_close * (1 - limit_pct), 2)   # 计算跌停价

    def _get_limit_percentage(self, stock_code):
        """根据股票代码确定涨跌幅比例

        优先检查ST标记（5%），然后根据代码前缀匹配相应板块的涨跌幅比例。
        若无法识别则返回默认值10%。

        参数:
        stock_code (str): 股票代码

        返回:
        float: 涨跌幅比例（0.05表示5%）
        """
        if not stock_code:                     # 空值返回默认10%
            return 0.10
        code_str = str(stock_code)
        if re.search(r'\b\*?ST\b', code_str):  # ST/*ST 股票涨跌幅为5%
            return 0.05
        numbers = re.findall(r'\d+', code_str) # 提取数字部分
        if not numbers:                          # 无数字，返回默认10%
            return 0.10
        for prefix, pct in self._prefix_map.items():  # 根据前缀匹配
            if numbers[0].startswith(prefix):
                return pct
        return 0.10                               # 默认主板10%

    def calculate_limit_prices(self, stock_code, prev_close):
        """计算涨停价和跌停价

        参数:
        stock_code (str): 股票代码
        prev_close (float): 前一日收盘价

        返回:
        tuple: (涨停价, 跌停价)
        """
        limit_up = self._calculate_limit_price(stock_code, prev_close, 'UP')
        limit_down = self._calculate_limit_price(stock_code, prev_close, 'DOWN')
        return limit_up, limit_down

    def update_limit_prices(self, stock_code, prev_close):
        """更新并存储股票的涨跌停价格

        参数:
        stock_code (str): 股票代码
        prev_close (float): 前一日收盘价

        返回:
        tuple: (涨停价, 跌停价)
        """
        limit_up, limit_down = self.calculate_limit_prices(stock_code, prev_close)
        self.limit_up_prices[stock_code] = limit_up
        self.limit_down_prices[stock_code] = limit_down
        return limit_up, limit_down

    def is_limit_up(self, stock_code, current_price):
        """判断当前价格是否触及涨停

        使用安全的浮点数比较，考虑精度问题。

        参数:
        stock_code (str): 股票代码
        current_price (float): 当前价格

        返回:
        bool: 是否涨停
        """
        if stock_code not in self.limit_up_prices:
            return False                     # 未记录涨停价，默认不涨停
        limit_up = self.limit_up_prices[stock_code]
        # 使用安全比较（等于或超过涨停价均视为涨停）
        return is_close(current_price, limit_up) or current_price >= limit_up

    def is_limit_down(self, stock_code, current_price):
        """判断当前价格是否触及跌停

        使用安全的浮点数比较，考虑精度问题。

        参数:
        stock_code (str): 股票代码
        current_price (float): 当前价格

        返回:
        bool: 是否跌停
        """
        if stock_code not in self.limit_down_prices:
            return False                     # 未记录跌停价，默认不跌停
        limit_down = self.limit_down_prices[stock_code]
        # 使用安全比较（等于或低于跌停价均视为跌停）
        return is_close(current_price, limit_down) or current_price <= limit_down

    def is_near_limit_up(self, stock_code, current_price, threshold_pct=0.01):
        """判断当前价格是否接近涨停价（未涨停但距离涨停价小于阈值）

        参数:
        stock_code (str): 股票代码
        current_price (float): 当前价格
        threshold_pct (float): 阈值百分比，如 0.01 表示距离涨停 1% 以内

        返回:
        bool: True 表示接近涨停（未涨停且距离小于阈值），False 表示不接近或已涨停
        """
        if stock_code not in self.limit_up_prices:
            return False                     # 未记录涨停价，默认不接近
        limit_up = self.limit_up_prices[stock_code]

        # 如果已经涨停，由 is_limit_up 处理，此处不视为“接近”
        if current_price >= limit_up:
            return False

        # 计算距离涨停的百分比（相对于当前价）
        # 注意：当前价必须大于0，否则视为不接近
        if current_price <= 0:
            return False

        diff_pct = (limit_up - current_price) / current_price
        return diff_pct < threshold_pct

    def can_trade_at_limit(self, stock_code, direction, current_price):
        """在涨跌停时判断是否可以执行交易

        买入操作不允许在涨停价进行，卖出操作不允许在跌停价进行。

        参数:
        stock_code (str): 股票代码
        direction (str): 交易方向 ('BUY'或'SELL')
        current_price (float): 当前价格

        返回:
        bool: 是否可以交易
        """
        if direction == 'BUY':
            # 买入时不能在涨停价
            return not self.is_limit_up(stock_code, current_price)
        elif direction == 'SELL':
            # 卖出时不能在跌停价
            return not self.is_limit_down(stock_code, current_price)
        return True