import backtrader as bt
from datetime import datetime, date, timedelta
import pandas as pd
from qmt_utils_adv import read_stock_codes, batch_format_stock_codes, get_stock_data_from_cache,to_datetime,is_close
import logging
import os
import psutil
import gc
import re
import numpy as np
from collections import deque
import copy
import pandas_market_calendars as mcal
import bisect  # 新增导入，用于二分查找

# 设置日志
logger = logging.getLogger(__name__)

# ==================== 增强的股票状态类 ====================
class StockStatus:
    """增强的股票状态管理类"""

    def __init__(self, stock_code):
        self.stock_code = stock_code
        self.cost_price = 0.0       # 成本价
        self.current_price = 0.0    # 当前价格
        self.current_high = 0.0     # 当前最高价
        self.holding_high = 0.0     # 持仓期间最高价 初始化为0，买入后通过update_high_price更新
        self.limit_up_price = 0.0   # 涨停价
        self.limit_down_price = 0.0 # 跌停价
        self.hold_days = 0          # 持仓天数
        self.need_buy_next_day = False  # 是否需要次日买入
        self.has_buy_order = False      # 是否有买入订单
        self.has_sell_order = False     # 是否有卖出订单
        self.sell_reason = None         # 卖出原因
        self.last_signal = None         # 最后信号
        self.first_buy_date = None      # 首次买入日期
        self.last_buy_date = None       # 最近买入日期
        self.last_sell_date = None      # 最近卖出日期
        self.trade_history = []         # 交易记录列表
        # 新增属性：记录最高价更新的日期和时间
        self.last_high_update_date = None
        self.last_high_update_time = None
        # 新增属性：标记是否因开盘涨停而保留
        self._reserved_for_limit_up = False  # 开盘涨停保留标记

    def update_high_price(self, current_date, current_time, current_high):
        """
        更新最高价，并记录更新日期和时间

        参数:
        current_date (str): 当前日期
        current_time (str): 当前时间
        current_high (float): 当前最高价

        返回:
        bool: 是否成功更新最高价（True表示更新了最高价）
        """
        # 如果是首次更新或者当前最高价大于历史最高价，则更新
        if self.holding_high == 0 or current_high > self.holding_high:
            self.holding_high = current_high
            # 记录更新最高价的日期和时间
            self.last_high_update_date = current_date
            self.last_high_update_time = current_time
            return True
        return False

    def reset_after_sell(self):
        """
        卖出后重置状态 - 增强版本
        重置所有持仓相关状态，为下一次买入做准备
        """
        self.cost_price = 0.0
        self.holding_high = 0.0
        self.hold_days = 0
        self.need_buy_next_day = False
        self.has_sell_order = False
        self.sell_reason = None
        self.last_sell_date = None
        # 重置最高价更新记录
        self.last_high_update_date = None
        self.last_high_update_time = None
        # 重置开盘涨停保留标记（策略3使用）
        self._reserved_for_limit_up = False
        # 可选：重置买入日期记录（根据业务需求决定）
        # self.first_buy_date = None
        # self.last_buy_date = None

    def add_trade_record(self, action, price, size, date, reason=""):
        """
        添加交易记录

        参数:
        action (str): 交易动作（BUY/SELL）
        price (float): 交易价格
        size (int): 交易数量
        date (str): 交易日期
        reason (str): 交易原因
        """
        self.trade_history.append({
            'date': date,
            'action': action,
            'price': price,
            'size': size,
            'reason': reason
        })

    def get_last_high_update_info(self):
        """
        获取最高价更新的信息

        返回:
        str: 最高价更新信息（如果已更新）或"最高价尚未更新过"
        """
        if self.last_high_update_date and self.last_high_update_time:
            return f"最高价 {self.holding_high:.2f} 更新于 {self.last_high_update_date} {self.last_high_update_time}"
        else:
            return "最高价尚未更新过"

    def __str__(self):
        """
        字符串表示，用于打印股票状态信息

        返回:
        str: 股票状态的字符串表示
        """
        high_info = self.get_last_high_update_info()
        return (f"StockStatus({self.stock_code}): cost={self.cost_price:.2f}, "
                f"high={self.holding_high:.2f}, hold_days={self.hold_days}, "
                f"limit_up={self.limit_up_price:.2f}, limit_down={self.limit_down_price:.2f}, "
                f"{high_info}")

    def validate_hold_days(self, current_date):
        """
        验证持仓天数计算的合理性

        参数:
        current_date (str): 当前日期

        返回:
        int: 修正后的持仓天数
        """
        if self.first_buy_date is None:
            return 0

        try:
            buy_date = to_datetime(self.first_buy_date).date()
            current_date_dt = to_datetime(current_date).date()

            # 持仓天数不能为负，且不能超过实际天数
            natural_days = (current_date_dt - buy_date).days
            if self.hold_days < 0 or self.hold_days > natural_days + 5:  # 允许5天缓冲
                logger.warning(f"{self.stock_code} 持仓天数异常: {self.hold_days}, 自然日差: {natural_days}")
                # 自动修正
                self.hold_days = max(0, natural_days - 1)

        except Exception as e:
            logger.warning(f"验证持仓天数失败: {e}")