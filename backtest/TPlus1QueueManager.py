# TPlus1QueueManager.py
import backtrader as bt
from datetime import datetime, date, timedelta
import pandas as pd
import re
import logging
import numpy as np
from collections import deque
from typing import Dict, List, Tuple, Optional, Any
import copy
import pandas_market_calendars as mcal
import bisect
from qmt_utils_adv import is_close, to_datetime

# 设置日志
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TPlus1QueueManager:
    """基于队列的T+1交易管理器 - 专注于交易记录管理和T+1合规检查"""

    def __init__(self, start_date=None, end_date=None):
        """初始化T+1交易管理器

        参数:
        start_date (str, optional): 开始日期（格式YYYYMMDD），用于交易日历
        end_date (str, optional): 结束日期（格式YYYYMMDD）
        """
        # 获取上海证券交易所的交易日历
        self.market_calendar = mcal.get_calendar('SSE')
        if start_date is None:
            start_date = '20000101'
        if end_date is None:
            end_date = '20301231'

        # 预加载交易日：从 start_date 到 end_date + 1年，确保回测期间及T+1所需的下一个交易日都在范围内
        extended_end = (datetime.strptime(end_date, '%Y%m%d') + timedelta(days=365)).strftime('%Y%m%d')
        self._ensure_trading_days(start_date, extended_end)

        # 队列定义
        self.buy_queues = {}  # 买入记录队列 {stock_code: deque of buy_records}
        self.sell_queues = {}  # 卖出记录队列 {stock_code: deque of sell_records}
        self.position_queues = {}  # 持仓队列

        # 全局记录ID计数器，用于生成唯一标识
        self._next_record_id = 0

    def _ensure_trading_days(self, start, end):
        """确保交易日缓存覆盖指定区间"""
        trading_days = self.market_calendar.valid_days(start_date=start, end_date=end)
        self._trading_days = sorted(pd.to_datetime(trading_days).date)

    def _get_next_trading_day(self, current_date):
        """获取指定日期的下一个交易日（使用二分查找）"""
        current_date = to_datetime(current_date).date()
        idx = bisect.bisect_right(self._trading_days, current_date)
        if idx < len(self._trading_days):
            return self._trading_days[idx]
        # 理论上不会发生，因为已预加载足够长的区间
        raise ValueError(f"无法找到 {current_date} 之后的交易日（当前交易日列表范围 {self._trading_days[0]} 至 {self._trading_days[-1]}）")

    def _calculate_can_sell_date(self, buy_date):
        """计算可以卖出的日期（T+1）"""
        buy_date = to_datetime(buy_date).date()
        return self._get_next_trading_day(buy_date)

    def add_buy_record(self, stock_code, executed_time, quantity, price):
        """添加买入记录到队列，并返回该记录的唯一ID"""
        buy_date = executed_time.date()
        if stock_code not in self.buy_queues:
            self.buy_queues[stock_code] = deque()
        if stock_code not in self.position_queues:
            self.position_queues[stock_code] = deque()

        can_sell_date = self._calculate_can_sell_date(buy_date)

        # 生成唯一记录ID
        self._next_record_id += 1
        record_id = self._next_record_id

        # 添加到买入队列
        buy_record = {
            'record_id': record_id,                # 记录ID
            'date': buy_date,
            'datetime': executed_time,
            'quantity': quantity,
            'price': price,
            'amount': quantity * price
        }
        self.buy_queues[stock_code].append(buy_record)

        # 添加到持仓队列（保存record_id以便关联）
        self.position_queues[stock_code].append({
            'record_id': record_id,                # 关联ID
            'buy_date': buy_date,
            'quantity': quantity,
            'price': price,
            'can_sell_date': can_sell_date
        })

        logger.debug(f"记录买入: {stock_code}, 数量: {quantity}, 价格: {price:.2f}, 记录ID: {record_id}")
        return record_id

    def add_sell_record(self, stock_code, sell_datetime, quantity, price, sell_type="normal"):
        """添加卖出记录到sell_queues"""
        if stock_code not in self.sell_queues:
            self.sell_queues[stock_code] = deque()

        sell_record = {
            'date': sell_datetime.date(),
            'datetime': sell_datetime,
            'quantity': quantity,
            'price': price,
            'type': sell_type,
            'amount': quantity * price
        }
        self.sell_queues[stock_code].append(sell_record)
        logger.debug(f"记录卖出: {stock_code}, 数量: {quantity}, 价格: {price:.2f}, 类型: {sell_type}")

    def get_all_buy_records(self, stock_code=None):
        """获取所有买入记录，若指定股票代码则返回该股票的记录"""
        if stock_code:
            if stock_code in self.buy_queues:
                records = list(self.buy_queues[stock_code])
                for record in records:
                    record['stock_code'] = stock_code
                return records
            return []
        else:
            # 返回所有股票的买入记录
            all_records = []
            for code, records_queue in self.buy_queues.items():
                for record in list(records_queue):
                    record_copy = record.copy()
                    record_copy['stock_code'] = code
                    all_records.append(record_copy)
            return all_records

    def get_all_sell_records(self, stock_code=None):
        """获取所有卖出记录，若指定股票代码则返回该股票的记录"""
        if stock_code:
            if stock_code in self.sell_queues:
                records = list(self.sell_queues[stock_code])
                for record in records:
                    record['stock_code'] = stock_code
                return records
            return []
        else:
            # 返回所有股票的卖出记录
            all_records = []
            for code, records_queue in self.sell_queues.items():
                for record in list(records_queue):
                    record_copy = record.copy()
                    record_copy['stock_code'] = code
                    all_records.append(record_copy)
            return all_records

    def get_buy_records_by_date(self, target_date_str: str) -> List[Dict]:
        """获取指定日期的所有买入记录，用于审计核对。

        参数:
        target_date_str: 日期字符串，格式为YYYYMMDD

        返回:
        包含指定日期买入记录的列表，每个记录包含股票代码、时间、数量、价格、金额等信息
        """
        try:
            target_date = datetime.strptime(target_date_str, '%Y%m%d').date()
            records = []

            for stock_code, queue in self.buy_queues.items():
                for record in list(queue):
                    if record['date'] == target_date:
                        record_with_stock = record.copy()
                        record_with_stock['stock_code'] = stock_code
                        records.append(record_with_stock)

            logger.debug(f"获取到{target_date_str}的买入记录共{len(records)}条")
            return records
        except Exception as e:
            logger.error(f"获取{target_date_str}买入记录失败: {e}")
            return []

    def get_sell_records_by_date(self, target_date_str: str) -> List[Dict]:
        """获取指定日期的所有卖出记录，用于审计核对。

        参数:
        target_date_str: 日期字符串，格式为YYYYMMDD

        返回:
        包含指定日期卖出记录的列表，每个记录包含股票代码、时间、数量、价格、金额等信息
        """
        try:
            target_date = datetime.strptime(target_date_str, '%Y%m%d').date()
            records = []

            for stock_code, queue in self.sell_queues.items():
                for record in list(queue):
                    if record['date'] == target_date:
                        record_with_stock = record.copy()
                        record_with_stock['stock_code'] = stock_code
                        records.append(record_with_stock)

            logger.debug(f"获取到{target_date_str}的卖出记录共{len(records)}条")
            return records
        except Exception as e:
            logger.error(f"获取{target_date_str}卖出记录失败: {e}")
            return []

    def can_sell_today(self, stock_code, current_datetime):
        """检查今日是否可以卖出（T+1限制）"""
        return self.get_sellable_quantity(stock_code, current_datetime) > 0

    def get_sellable_quantity(self, stock_code, current_datetime):
        """获取可卖出数量"""
        if stock_code not in self.position_queues:
            return 0
        current_date = to_datetime(current_datetime).date()
        sellable_quantity = 0
        for position in self.position_queues[stock_code]:
            if position['can_sell_date'] <= current_date:
                sellable_quantity += position['quantity']
        return sellable_quantity

    def execute_sell(self, stock_code, sell_quantity, sell_price, executed_time):
        """
        执行卖出操作并记录卖出信息（FIFO顺序）

        参数:
            stock_code: 股票代码
            sell_quantity: 请求卖出的数量
            sell_price: 卖出价格
            executed_time: 执行时间

        返回:
            int: 实际卖出的数量（可能小于请求数量）
        """
        if stock_code not in self.position_queues:
            return 0

        current_date = to_datetime(executed_time).date()
        remaining_sell = sell_quantity
        new_queue = deque()
        total_sold = 0
        actual_sell_price = sell_price  # 记录实际卖出价格

        # FIFO处理逻辑
        for position in list(self.position_queues[stock_code]):
            if remaining_sell <= 0:
                new_queue.append(position)
                continue

            if position['can_sell_date'] <= current_date:
                available_quantity = position['quantity']

                if available_quantity <= remaining_sell:
                    total_sold += available_quantity
                    remaining_sell -= available_quantity
                else:
                    total_sold += remaining_sell
                    new_position = position.copy()
                    new_position['quantity'] = available_quantity - remaining_sell
                    new_queue.append(new_position)
                    remaining_sell = 0
            else:
                new_queue.append(position)

        # 更新持仓队列
        self.position_queues[stock_code] = new_queue

        # 记录卖出信息
        if total_sold > 0:
            # 如果没有提供卖出价格，使用持仓平均成本估算
            if actual_sell_price is None:
                position_info = self.get_position_info(stock_code)
                actual_sell_price = position_info['avg_price'] if position_info['total_quantity'] > 0 else 0

            self.add_sell_record(stock_code, executed_time, total_sold, actual_sell_price, "executed")

        logger.debug(f"T+1卖出: {stock_code}, 请求卖出{sell_quantity}股, 实际卖出{total_sold}股")
        return total_sold

    def force_remove_position(self, stock_code: str, quantity: int, price: float, executed_time) -> bool:
        """
        强制减少持仓（用于T+1队列与broker不同步时的修正）。
        按FIFO顺序移除指定数量的股票，并记录强制卖出。

        参数:
            stock_code: 股票代码
            quantity: 需要强制移除的数量
            price: 实际成交价格
            executed_time: 成交时间

        返回:
            bool: 操作是否成功（持仓存在且移除数量≥0）
        """
        if stock_code not in self.position_queues:
            logger.error(f"强制移除持仓失败：股票 {stock_code} 无持仓记录")
            return False

        if quantity <= 0:
            logger.warning(f"强制移除持仓数量必须为正数，收到 {quantity}")
            return False

        current_date = executed_time.date()
        remaining = quantity
        new_queue = deque()
        total_removed = 0

        for pos in self.position_queues[stock_code]:
            if remaining <= 0:
                new_queue.append(pos)
                continue

            if pos['quantity'] <= remaining:
                total_removed += pos['quantity']
                remaining -= pos['quantity']
                # 该条记录完全移除，不加入新队列
            else:
                total_removed += remaining
                # 部分移除，保留剩余部分
                new_pos = pos.copy()
                new_pos['quantity'] = pos['quantity'] - remaining
                new_queue.append(new_pos)
                remaining = 0

        # 更新持仓队列
        self.position_queues[stock_code] = new_queue

        # 记录强制卖出
        if total_removed > 0:
            self.add_sell_record(stock_code, executed_time, total_removed, price, sell_type="forced")
            logger.debug(f"强制卖出: {stock_code} {total_removed}股 @ {price:.2f}, 剩余持仓 {sum(p['quantity'] for p in new_queue)}")
        else:
            logger.warning(f"强制卖出未移除任何持仓: {stock_code}")

        return True

    def get_position_info(self, stock_code):
        """获取持仓信息"""
        if stock_code not in self.position_queues:
            return {'total_quantity': 0, 'avg_price': 0, 'buy_dates': []}

        total_quantity = 0
        total_value = 0
        buy_dates = []

        for position in self.position_queues[stock_code]:
            total_quantity += position['quantity']
            total_value += position['quantity'] * position['price']
            buy_dates.append(position['buy_date'])

        avg_price = total_value / total_quantity if total_quantity > 0 else 0
        return {
            'total_quantity': total_quantity,
            'avg_price': avg_price,
            'buy_dates': buy_dates
        }

    def get_trading_days_count(self, start_date, end_date):
        """获取两个日期之间的交易日数量"""
        try:
            start_date = to_datetime(start_date).date()
            end_date = to_datetime(end_date).date()
            trading_days = self.market_calendar.valid_days(start_date=start_date, end_date=end_date)
            return len(trading_days)
        except Exception as e:
            logger.warning(f"计算交易日数量失败: {e}")
            return (end_date - start_date).days + 1

    def calculate_cash_by_t1_records(self, initial_capital: float) -> float:
        """基于T+1交易记录计算现金余额（辅助计算功能）

        参数:
        initial_capital (float): 初始资本

        返回:
        float: 基于T+1交易记录计算的现金余额
        """
        try:
            total_buy = sum(record['amount'] for record in self.get_all_buy_records())
            total_sell = sum(record['amount'] for record in self.get_all_sell_records())
            calculated_cash = initial_capital - total_buy + total_sell

            # 添加详细日志便于调试
            logger.debug(
                f"T+1口径现金计算（辅助） | 初始资本: {initial_capital:,.2f} | "
                f"总买入: {total_buy:,.2f} | "
                f"总卖出: {total_sell:,.2f} | "
                f"T+1计算现金: {calculated_cash:,.2f}"
            )

            return calculated_cash
        except Exception as e:
            logger.error(f"T+1口径现金计算（辅助）失败: {e}")
            return initial_capital

    def undo_last_buy(self, stock_code: str, executed_time=None, record_id=None):
        """
        回滚最近一次买入记录。

        参数:
        stock_code (str): 股票代码
        executed_time (datetime, optional): 原买入执行时间（用于时间匹配，当未提供record_id时使用）
        record_id (int, optional): 要撤销的记录ID（若提供则精确删除）
        """
        # 优先使用record_id精确删除
        if record_id is not None:
            # 从买入队列中删除对应记录
            if stock_code in self.buy_queues:
                new_buy_queue = deque()
                removed = False
                for record in self.buy_queues[stock_code]:
                    if record.get('record_id') == record_id:
                        removed = True
                        continue  # 跳过要删除的记录
                    new_buy_queue.append(record)
                if removed:
                    self.buy_queues[stock_code] = new_buy_queue
                else:
                    logger.warning(f"未找到record_id={record_id}的买入记录，股票{stock_code}")

            # 从持仓队列中删除对应记录
            if stock_code in self.position_queues:
                new_pos_queue = deque()
                removed = False
                for pos in self.position_queues[stock_code]:
                    if pos.get('record_id') == record_id:
                        removed = True
                        continue
                    new_pos_queue.append(pos)
                if removed:
                    self.position_queues[stock_code] = new_pos_queue
                else:
                    logger.warning(f"未找到record_id={record_id}的持仓记录，股票{stock_code}")

            if removed:
                logger.debug(f"根据record_id={record_id}回滚买入记录成功: {stock_code}")
            else:
                logger.error(f"根据record_id={record_id}回滚买入记录失败: {stock_code}")
            return

        # 兼容原有逻辑：根据时间匹配（仅当未提供record_id时）
        if executed_time is None:
            logger.error("undo_last_buy需要提供record_id或executed_time")
            return

        logger.warning("使用时间匹配回滚买入记录，可能存在误差，建议传入record_id")
        if stock_code in self.buy_queues:
            buy_queue = self.buy_queues[stock_code]
            for i in range(len(buy_queue)-1, -1, -1):
                record = buy_queue[i]
                if abs((record['datetime'] - executed_time).total_seconds()) < 60:  # 时间容差
                    buy_queue.remove(record)
                    break

        if stock_code in self.position_queues:
            pos_queue = self.position_queues[stock_code]
            for i in range(len(pos_queue)-1, -1, -1):
                pos = pos_queue[i]
                if abs((pos['buy_date'] - executed_time.date()).days) < 1:  # 日期匹配
                    pos_queue.remove(pos)
                    break

        logger.debug(f"回滚买入记录（时间匹配）: {stock_code} at {executed_time}")