# rolling_investment_strategy.py
from typing import Dict, List
import backtrader as bt
from datetime import datetime, time, date, timedelta
import pandas as pd
from portfolio_manager import PortfolioManager
from qmt_utils_adv import read_stock_codes, batch_format_stock_codes, is_trading_day, to_datetime, is_close
import logging
import os
import psutil
import gc
import re
import numpy as np
from collections import deque
import copy
import pandas_market_calendars as mcal
import bisect

logger = logging.getLogger(__name__)


class RollingInvestmentStrategy(bt.Strategy):
    """
    A股交易策略类 - 支持多个买入日期（支持一对多映射）

    该策略实现了基于动态的A股交易策略，包括：
    - 次日开盘买入（9:30-9:45）
    - 正常买入（14:55后）
    - 涨跌停价格控制
    - T+1交易规则管理

    策略版本说明（通过参数 strategy_version 选择）：
    - version1: 止损（亏损2%） + 止盈（个股冲高,在最高点回撤,回撤达到利润的50%卖出）
    - version2: 止损（亏损2%） + 动态止盈（根据持仓天数调整回撤比例）
    - version3: 止损（亏损4%） + 止盈（盈利20%）
    - version4: 十日线上买进 + 五日线下卖出
    - version5: 不设止损（亏损100%,固定时间后强制卖出） + 止盈（盈利2%）

    优化点：
    1. 修复了持仓天数计算问题
    2. 优化了T+1交易规则实现
    3. 增加了时间分析功能
    4. 修复了涨跌停价格计算
    5. 支持多个买入日期（字典格式）
    6. 集成全局资金池管理，实现每日100万限额投资
    7. 支持 {股票代码: [买入日期列表]} 格式的买入日期参数
    8. 新增涨停延期额度和最低购入补充资金功能
    9. 按照方案二优化资金流追踪架构
    10. 方案三适配：补充资金合并到主资金池，仅保留统计标记
    11. 资金分配计算移至 PortfolioManager，策略仅负责调用（混合方案）
    12. 【优化】策略完全通过 PortfolioManager 访问资金池，彻底解除对 GlobalCapitalManager 的直接依赖
    13. 【优化】动态补充资金机制：买入订单改为市价单，补充资金在成交后计算
    14. 【新增】接近涨停阈值控制：在价格接近涨停（未涨停但距离小于阈值）时，可选择延期或跳过，避免在极端价位追涨
    15. 【新增】资金分配模式切换：支持等额分配（equal）、强制一手（force_min）、动态按需分配（dynamic）
    16. 【新增】每日累计统计开关：daily_summary_enabled，控制每日收盘是否输出累计绩效报告
    """

    params = (
        ('start_date', '20200101'),  # 直接定义参数
        ('end_date', '20301231'),
        ('stock_pool', []),                      # 股票池（分钟线数据列表）
        ('init_cash', 1000000),                  # 初始资金（主要用于兼容性，实际资金由全局资金池管理）
        ('stock_buy_dict', {}),                   # 买入日期字典，格式 {买入日期: 股票代码列表}
        ('buy_time', time(14, 55)),               # 正常买入时间（14:55）
        ('max_position_pct', 0.1),                # 最大持仓比例（10%）
        ('skip_limit_up', False),                 # 是否跳过涨停股票（涨停时不买入，也不标记次日买入）
        ('enable_tplus1', True),                   # 是否启用T+1交易规则
        ('enable_limit_control', True),            # 是否启用涨跌停限制
        ('enable_time_analysis', True),            # 是否启用时间分析（记录订单决策、创建、执行延迟）
        ('indicator_config', {'ma5': 5, 'ma10': 10}),
        ('strategy_version', 'version1'),          # 策略版本，影响买卖信号判断
        ('strategy_params', None),                  # 自定义策略参数（传递给 PortfolioManager）
        ('use_preset_sell_adapter', False),         # P0-1: 切 preset adapter（默认关；或 env BACKTEST_USE_PRESET_SELL_ADAPTER）
        ('preset_adapter_price_mode', 'adjusted'),  # P0-1 Phase 1 默认前复权；Phase 2 可切 raw
        ('log_level', 'INFO'),                       # 日志级别
        ('printlog', False),                          # 是否打印日志（兼容旧版）
        ('global_capital_manager', None),             # 全局资金管理器（由外部传入）
        ('deferred_quota_valid_days', 3),              # 涨停延期额度有效期（交易日）
        ('near_limit_up_threshold', 0.01),             # 接近涨停阈值，默认1%
        ('defer_on_near_limit_up', False),             # 接近涨停时是否延期（True: 延期；False: 跳过且不延期）
        # ===== 新增参数：资金分配模式 =====
        ('allocation_mode', 'force_min'),                 # 可选：'equal'（等额分配，不足100股放弃）
                                                        #       'force_min'（等额分配，但强制买入一手，差额由补充资金填补）
                                                        #       'dynamic'（动态按需分配，优先保证每只股票至少一手）
        # ===== 新增参数：每日累计统计开关 =====
        ('daily_summary_enabled', True),                 # 是否在每日收盘时输出累计绩效报告（总交易次数、资金池状态等）
    )

    def __init__(self):
        """初始化策略

        1. 创建投资组合管理器（PortfolioManager）
        2. 初始化股票数据字典
        3. 初始化订单状态
        4. 初始化交易日志
        5. 初始化盈利记录
        6. 初始化时间分析数据结构
        7. 初始化股票买入日期映射（支持一对多格式）
        """
        start_date = self.params.start_date   # 直接使用
        end_date = self.params.end_date

        # 保存资金管理器引用（仅用于初始化 PortfolioManager，后续不再直接使用）
        self.global_capital_manager = self.params.global_capital_manager
        if not self.global_capital_manager:
            logger.error("❌ 策略未收到全局资金管理器，资金管理将失效！")
        else:
            logger.info(f"✅ 策略已注入全局资金管理器")

        # 初始化PortfolioManager（注入策略和资金管理器）
        self.portfolio_manager = PortfolioManager(
            start_date=start_date,
            end_date=end_date,
            strategy_version=self.params.strategy_version,
            strategy_params=self.params.strategy_params,
            global_capital_manager=self.global_capital_manager,
            use_preset_sell_adapter=self.params.use_preset_sell_adapter,
            preset_adapter_price_mode=self.params.preset_adapter_price_mode,
        )

        # 验证资金管理器是否有效注入
        if not self.portfolio_manager.global_capital_manager:
            logger.error("❌ PortfolioManager未正确初始化global_capital_manager")
        else:
            logger.info(f"✅ PortfolioManager已注入全局资金管理器")

        # 策略6买侧契约（2026-09-10）：尾盘涨停直接弃买——不建延期额度、不标记次日买入。
        if self.params.strategy_version == 'version6' and not self.params.skip_limit_up:
            logger.info("✅ 策略6：强制 skip_limit_up=True（尾盘涨停跳过，不延期不次日追）")
            self.params.skip_limit_up = True

        # 存储日线数据（用于计算指标）
        self.stock_daily_data = {}
        self.calc_indicators = {}
        self.indicator_periods = self._resolve_indicator_periods()

        self.stock_data = {}            # 存储分钟线数据
        self.orders = {}                # 记录订单对象
        self.trade_log = []              # 交易日志列表
        self.cancel_log = []              # 新增：记录订单取消事件
        self.deferred_create_log = []      # 新增：记录延期额度创建事件
        self.stock_profits = {}           # 每只股票的盈利记录
        self.memory_usage_log = []        # 内存使用记录
        self._last_memory_log_date = None

        self.time_analysis_log = []       # 时间分析数据结构
        self.order_decision_time = {}     # 记录订单决策时间
        self.order_creation_time = {}      # 记录订单实际创建时间（将在notify_order中更新）

        # 新增：收盘标志，防止收盘后再次创建订单
        self._market_closed = False

        # 存储股票买入日期映射（支持一对多）
        # 格式: {买入日期: [股票代码]}  和  {股票代码: [买入日期列表]}
        stock_buy_dict = self.params.stock_buy_dict
        self.stock_buy_dates = {}          # {股票代码: [买入日期列表]}
        self.date_to_stocks = {}            # {买入日期: [股票代码列表]}

        if not stock_buy_dict:
            logger.warning("买入日期字典为空，策略将不会执行任何买入操作。")
        else:
            # 处理格式1: {买入日期: 股票代码列表}
            for buy_date_key, stock_list in stock_buy_dict.items():
                # 1. 标准化买入日期
                if isinstance(buy_date_key, str):
                    try:
                        buy_date = datetime.strptime(buy_date_key, "%Y%m%d").date()
                    except ValueError:
                        logger.error(f"买入日期格式错误: {buy_date_key}，期望格式YYYYMMDD")
                        continue
                elif isinstance(buy_date_key, date):
                    buy_date = buy_date_key
                else:
                    logger.error(f"买入日期键类型不支持: {type(buy_date_key)}")
                    continue

                # 2. 标准化股票列表（确保是列表）
                if isinstance(stock_list, str):
                    stock_list = [stock_list]
                elif not isinstance(stock_list, list):
                    logger.error(f"股票列表应为list或str类型，但收到: {type(stock_list)}")
                    continue

                # 3. 构建映射 {日期: 股票列表}
                self.date_to_stocks[buy_date] = stock_list

                # 4. 构建映射 {股票: 日期列表}
                for stock in stock_list:
                    if stock not in self.stock_buy_dates:
                        self.stock_buy_dates[stock] = []
                    if buy_date not in self.stock_buy_dates[stock]:
                        self.stock_buy_dates[stock].append(buy_date)

        # 对所有买入日期列表进行排序，便于后续可能的查找
        for stock in self.stock_buy_dates:
            self.stock_buy_dates[stock].sort()

        logger.info(f"买入日期映射初始化完成。")
        logger.info(f"  - 共涉及 {len(self.stock_buy_dates)} 只股票，{len(self.date_to_stocks)} 个不同的买入日。")

        # 可选：打印示例
        if self.stock_buy_dates:
            sample_stock = next(iter(self.stock_buy_dates))
            logger.info(f"  - 示例：股票 '{sample_stock}' 的买入日期列表: {self.stock_buy_dates[sample_stock]}")

        # 实际股票池（分钟线数据，不包含日线数据）
        self.actual_stock_pool = [data._name for data in self.datas if not data._name.endswith('_daily')]
        logger.info(f"实际股票池数量: {len(self.actual_stock_pool)}")

        # 当日已分配资金累计（用于日志和平均分配控制）
        self._daily_allocated_cash = 0.0

        # 初始化状态
        for i, data in enumerate(self.datas):
            stock_name = data._name
            if stock_name.endswith('_daily'):
                # 这是日线数据，提取股票代码
                base_stock_name = stock_name.replace('_daily', '')
                self.stock_daily_data[base_stock_name] = data

                # 为每只股票创建独立的指标（SMA）
                self.calc_indicators[base_stock_name] = {
                    f"ma{period}": bt.indicators.SMA(data.close, period=period)
                    for period in self.indicator_periods
                }
            else:
                # 为分钟线数据初始化日线引用（可能为None）
                if stock_name not in self.stock_daily_data:
                    self.stock_daily_data[stock_name] = None

                # 这是分钟线主数据
                self.stock_data[stock_name] = data
                self.orders[stock_name] = None
                self.stock_profits[stock_name] = self._init_profit_record()

                # 初始化股票买入日期（从我们刚构建的映射中获取，若无则设为空列表）
                self.stock_buy_dates[stock_name] = self.stock_buy_dates.get(stock_name, [])
                if not self.stock_buy_dates[stock_name]:
                    logger.debug(f"股票 {stock_name} 未在buy_dates参数中指定买入日期，买入列表为空。")

                # 初始化时间记录
                self.order_decision_time[stock_name] = None
                self.order_creation_time[stock_name] = None

        # 记录最后交易日期
        self.last_trade_date = None
        # 交易计数
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

        # 添加每日 15:00 触发的定时器
        self.add_timer(
            when=time(15, 0),  # 每天 15:00
            repeat=timedelta(days=1),  # 每天重复
            weekdays=[0, 1, 2, 3, 4],  # 仅周一至周五触发
        )
        # when 是每日触发的时间点，Backtrader 会在每个数据点上检查当前时间是否已达到或超过该时间。
        # repeat 指定触发间隔，timedelta(days=1) 表示每次触发后，下一个触发时间 = 当前触发时间 + 1天。
        # weekdays 限制只在指定的星期几触发（0=周一，4=周五），自动跳过周末。
        # 在 Backtrader 中，定时器的 repeat 参数用于定义每次触发后下一次触发的时间间隔。
        # 当使用 repeat=timedelta(days=1) 时，每次触发后会将“下次触发时间”增加一天。
        # 这种机制在连续的交易日内工作正常，但遇到周末或节假日（数据缺失的日期）时，会导致“跨日重复触发”问题，造成逻辑混乱。

        # 记录已处理收盘的日期，避免重复处理
        self._processed_close_dates = set()

        # 当日已使用的补充资金（用于日志）
        self._supplementary_capital_used_today = 0.0

        self.cash_per_stock = 0.0       # 当日每个股票平均分配的资金（由每日开盘时计算）
        # ===== 新增：动态分配模式下每只股票的分配金额 =====
        self.dynamic_allocations = {}   # {stock: allocated_cash}
        # 记录上次动态计算的日期，避免重复计算
        self._last_dynamic_calc_date = None

        # 累计佣金（用于资金校验）
        self.total_commission = 0.0

        # ========== 新增：计划买入股票数统计 ==========
        self.planned_regular_today = 0   # 当日计划常规买入股票数
        self.planned_deferred_today = 0  # 当日计划延期买入股票数
        # ============================================
        # ===== 新增：当日过期释放的延期额度股票数 =====
        self.expired_released_today = 0
        # ===== 新增：收盘时延期股票数 =====
        self.deferred_at_close_today = 0

        logger.info(f"优化策略初始化完成，共加载 {len(self.actual_stock_pool)} 只股票")

    def _resolve_indicator_periods(self):
        """
        统一解析需要计算的均线周期，确保：
        1) indicator_config 中声明的周期会被计算；
        2) 策略4参数覆盖(ma_buy_period/ma_sell_period)不会因为指标缺失失效。
        """
        periods = set()

        indicator_cfg = self.params.indicator_config
        if isinstance(indicator_cfg, dict):
            for value in indicator_cfg.values():
                try:
                    p = int(value)
                    if p > 0:
                        periods.add(p)
                except (TypeError, ValueError):
                    continue

        strategy_params = self.params.strategy_params
        if isinstance(strategy_params, dict):
            for key in ("ma_buy_period", "ma_sell_period"):
                if key in strategy_params:
                    try:
                        p = int(strategy_params.get(key))
                        if p > 0:
                            periods.add(p)
                    except (TypeError, ValueError):
                        continue

        if not periods:
            periods.update({5, 10})
        return sorted(periods)
        logger.info(f"💡 资金管理：使用全局资金池，每日限额1,000,000元")
        logger.info(f"💡 新增功能：涨停延期额度（有效期{self.params.deferred_quota_valid_days}天）和最低购入补充资金")
        logger.info(f"💡 资金分配计算已移至 PortfolioManager（混合方案）")
        logger.info(f"💡 新增：累计佣金跟踪，用于资金校验")
        logger.info(f"✅ 优化：策略完全通过 PortfolioManager 访问资金池，解除直接依赖")
        logger.info(f"✅ 优化：动态补充资金机制已启用（买入订单使用市价单，补充资金成交后计算）")
        logger.info(f"✅ 新增：接近涨停阈值 {self.params.near_limit_up_threshold*100:.1f}%，"
                    f"延期选项: {self.params.defer_on_near_limit_up}")
        logger.info(f"✅ 新增资金分配模式: {self.params.allocation_mode}")
        logger.info(f"✅ 每日累计统计开关: {self.params.daily_summary_enabled}")

    def notify_timer(self, timer, when, *args, **kwargs):
        """定时器回调函数 - 每天15:00触发，仅记录日志，不执行收盘处理"""
        trigger_date = when.date()
        # 获取当前数据日期（第一个数据源的日期）
        current_data_date = self.data.datetime.date(0)

        # 只处理与当前数据日期相同的触发（即当天的触发）
        if trigger_date != current_data_date:
            logger.debug(f"定时器触发日期 {trigger_date} 与当前数据日期 {current_data_date} 不一致，忽略（补触发）")
            return

        # 避免同一日重复处理（理论上不会，但防御性编程）
        if trigger_date in self._processed_close_dates:
            logger.debug(f"日期 {trigger_date} 的定时器已处理过，跳过")
            return

        logger.info(f"⏰ 定时器正常触发 - 日期: {trigger_date} 时间: {when.time()}")
        # self._processed_close_dates.add(trigger_date)
        # 注意：此处不调用 _on_daily_close，收盘处理仍在 next 中手动执行

    def _get_stocks_for_buy_date(self, target_date):
        """获取指定买入日期对应的股票列表"""
        return self.date_to_stocks.get(target_date, [])

    # ==================== 现金一致性校验 ====================
    def _check_cash_consistency(self, current_datetime, tolerance=10.0):
        """校验 Broker 现金与全局资金池总现金的一致性"""
        # 优化：通过 PortfolioManager 获取预期现金
        broker_cash = self.broker.getcash()

        # 使用 portfolio_manager 的总现金
        expected_cash = self.portfolio_manager.get_total_cash()

        diff = abs(broker_cash - expected_cash)
        if diff > tolerance:
            logger.error(f"❌ 资金不一致！broker现金={broker_cash:.2f}, "
                         f"预期总现金={expected_cash:.2f}, "
                         f"差额={diff:.2f}")
        else:
            logger.info(f"✅ 资金校验通过，broker现金≈预期总现金，差额={diff:.2f}")

    def _on_daily_close(self, when=None):
        """每日收盘处理函数

        参数:
        when: 由定时器传入的准确触发时间（datetime），如果为None则使用当前数据时间
        """
        try:
            # 确定基准时间
            if when is not None:
                current_datetime = when
            else:
                current_datetime = bt.num2date(self.datas[0].datetime[0])

            current_date = current_datetime.date()
            current_time = current_datetime.time()

            logger.info(f"🔔 执行每日收盘处理 - 日期: {current_date}, 时间: {current_time}")

            # 检查是否为交易日
            if not is_trading_day(current_date):
                logger.info(f"跳过非交易日: {current_date}")
                return

            # 避免同一天重复处理（理论上定时器已避免，但加一层保险）
            if current_date in self._processed_close_dates:
                logger.info(f"日期 {current_date} 已处理，跳过")
                return

            logger.info(f"⏰ 开始每日收盘处理，日期: {current_date}")

            # 取消所有未成交订单
            cancelled_count = 0
            for stock, order in list(self.orders.items()):
                if order and order.status not in [bt.Order.Completed, bt.Order.Canceled, bt.Order.Margin,
                                                  bt.Order.Rejected]:
                    # ----- 新增：提取订单详细信息用于日志 -----
                    direction = "买入" if order.isbuy() else "卖出"
                    # 订单类型映射
                    exectype_map = {
                        bt.Order.Market: "市价单",
                        bt.Order.Limit: "限价单",
                        bt.Order.Stop: "止损单",
                        bt.Order.StopLimit: "止损限价单"
                    }
                    exectype_str = exectype_map.get(order.exectype, "未知类型")

                    # 从订单 info 中获取延期标志
                    info_dict = None
                    is_deferred = None
                    if hasattr(order, 'info'):
                        # 兼容可能存在的嵌套
                        info_dict = order.info.get('info', {}) if hasattr(order.info, 'get') else {}
                        if not info_dict and isinstance(order.info, dict):
                            info_dict = order.info
                        is_deferred = info_dict.get('is_deferred', False)
                    else:
                        is_deferred = False

                    deferred_str = "延期" if is_deferred else "常规"
                    # 获取创建时间
                    if hasattr(order, 'created') and hasattr(order.created, 'dt'):
                        creation_time = bt.num2date(order.created.dt).strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        creation_time = "未知"
                    # 未成交数量
                    remaining = order.created.size - abs(order.executed.size)
                    # 价格（优先取订单限价，若无则取创建时的指定价格）
                    price = order.created.price if order.created.price else (order.limit if order.limit else 0)
                    # -----------------------------------------

                    self.cancel(order)
                    logger.info(f"取消未成交订单: {stock} {direction} {deferred_str} {exectype_str}, "
                                f"创建时间: {creation_time}, 未成交数量: {remaining}, 价格: {price:.2f}, "
                                f"状态: {order.getstatusname()}")
                    cancelled_count += 1

            if cancelled_count > 0:
                logger.info(f"收盘共取消 {cancelled_count} 笔未成交订单，释放冻结资金。")

            # 执行收盘处理（更新组合、结算等）
            self.portfolio_manager.end_of_day_processing(current_datetime)

            # 重置当日已分配资金
            self._daily_allocated_cash = 0.0
            # 重置当日补充资金使用
            self._supplementary_capital_used_today = 0.0

            # 标记已处理
            self._processed_close_dates.add(current_date)

            # 设置收盘标志，防止后续创建新订单
            self._market_closed = True

            # 资金一致性验证
            if not self.portfolio_manager.validate_cash_consistency(current_datetime):
                breakdown = self.portfolio_manager.get_cash_flow_breakdown()
                logger.critical(f"回测后资金不一致！明细: {breakdown}")

            # 输出全局资金池状态（通过 PortfolioManager 封装的方法）
            self.portfolio_manager.log_daily_status(current_date, self._supplementary_capital_used_today)

            # 新增：现金一致性校验
            self._check_cash_consistency(current_datetime)

            # ===== 新增：统计收盘时延期股票数 =====
            current_date_str = current_date.strftime('%Y%m%d')
            deferred_at_close = 0
            for stock in self.actual_stock_pool:
                status = self.portfolio_manager.get_stock_status(stock)
                if status.need_buy_next_day:
                    deferred = self.portfolio_manager.get_deferred_for_stock(stock, current_date_str)
                    if deferred > 0:
                        deferred_at_close += 1
            self.deferred_at_close_today = deferred_at_close
            # =====================================

            # ===== 新增：生成每日交易报告 =====
            self._generate_daily_report(current_date, current_datetime)

            # ===== 可选：生成每日累计统计报告 =====
            if self.params.daily_summary_enabled:
                self._generate_performance_summary(is_final=False)
                self._generate_capital_pool_summary(is_final=False)
                self._generate_comparison_report(current_datetime, is_final=False)
                self._generate_return_report(current_datetime, is_final=False)

            # ========== 重置每日统计变量 ==========
            self.planned_regular_today = 0
            self.planned_deferred_today = 0
            self.expired_released_today = 0
            self.deferred_at_close_today = 0  # 重置
            # ====================================

            logger.info(f"✅ {current_date}每日收盘处理完成")

        except Exception as e:
            logger.error(f"❌ 收盘处理失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _generate_daily_report(self, current_date, current_datetime):
        """生成并输出每日交易流水、汇总和持仓报告"""
        # 1. 筛选当天事件
        day_trades = [t for t in self.trade_log if t['date'] == current_date]
        day_cancels = [c for c in self.cancel_log if c['date'] == current_date]
        day_deferred = [d for d in self.deferred_create_log if d['date'] == current_date]

        # 2. 分类统计（金额）
        buy_regular_total = 0.0  # 常规买入金额
        buy_deferred_total = 0.0  # 延期买入金额
        sell_total = 0.0
        cancel_buy_total = 0.0
        cancel_sell_total = 0.0
        deferred_create_total = 0.0

        # 新增：个数统计
        buy_regular_count = 0
        buy_deferred_count = 0
        sell_count = 0
        cancel_buy_count = 0
        cancel_sell_count = 0

        for t in day_trades:
            if t['action'] == 'BUY':
                amount = t['price'] * t['size']
                if t.get('is_deferred', False):
                    buy_deferred_total += amount
                    buy_deferred_count += 1
                else:
                    buy_regular_total += amount
                    buy_regular_count += 1
            elif t['action'] == 'SELL':
                sell_total += t['price'] * t['size']
                sell_count += 1

        for c in day_cancels:
            if c['direction'] == 'BUY':
                cancel_buy_total += c['amount']
                cancel_buy_count += 1
            else:
                cancel_sell_total += c['amount']
                cancel_sell_count += 1

        for d in day_deferred:
            deferred_create_total += d['amount']

        net_cash_flow = sell_total - (buy_regular_total + buy_deferred_total)

        # 3. 输出流水（按时间排序）
        logger.info("=" * 80)
        logger.info(f"📊 每日交易报告 - {current_date}")
        logger.info("=" * 80)

        # 合并所有事件并按时间排序
        all_events = []
        all_events.extend([{**t, 'event_type': 'TRADE'} for t in day_trades])
        all_events.extend([{**c, 'event_type': 'CANCEL'} for c in day_cancels])
        all_events.extend([{**d, 'event_type': 'DEFERRED_CREATE'} for d in day_deferred])
        all_events.sort(key=lambda x: x['datetime'])

        # 表头
        logger.info(f"{'时间':<10} {'类型':<12} {'股票':<8} {'股数':>8} {'价格':>8} {'金额':>12} {'备注'}")
        logger.info("-" * 80)

        for ev in all_events:
            time_str = ev['datetime'].strftime('%H:%M:%S')
            if ev['event_type'] == 'TRADE':
                typ = '延期买入' if ev.get('is_deferred') and ev['action'] == 'BUY' else (
                    '常规买入' if ev['action'] == 'BUY' else '卖出')
                stock = ev['stock']
                size = ev['size']
                price = ev['price']
                amount = price * size
                remark = ev.get('reason', '')
                logger.info(f"{time_str:<10} {typ:<12} {stock:<8} {size:>8} {price:>8.2f} {amount:>12.2f} {remark}")
            elif ev['event_type'] == 'CANCEL':
                typ = '未成交取消' + ('(买)' if ev['direction'] == 'BUY' else '(卖)')
                stock = ev['stock']
                size = ev['remaining_size']
                price = ev['price']
                amount = ev['amount']
                remark = ev.get('reason', '')
                logger.info(f"{time_str:<10} {typ:<12} {stock:<8} {size:>8} {price:>8.2f} {amount:>12.2f} {remark}")
            elif ev['event_type'] == 'DEFERRED_CREATE':
                typ = '延期额度记录'
                stock = ev['stock']
                amount = ev['amount']
                # 如果有到期日则显示，否则显示有效期天数
                remark = f"有效天数:{ev['valid_days']} {ev.get('reason', '')}"
                logger.info(f"{time_str:<10} {typ:<12} {stock:<8} {'-':>8} {'-':>8} {amount:>12.2f} {remark}")

        # 4. 输出金额汇总
        logger.info("-" * 80)
        logger.info(f"📈 今日汇总（金额）:")
        logger.info(f"   常规买入总额: {buy_regular_total:>12.2f}")
        logger.info(f"   延期买入总额: {buy_deferred_total:>12.2f}")
        logger.info(f"   卖出总额    : {sell_total:>12.2f}")
        logger.info(f"   净现金流    : {net_cash_flow:>12.2f}")
        logger.info(f"   延期额度创建: {deferred_create_total:>12.2f}")
        logger.info(f"   取消买入金额: {cancel_buy_total:>12.2f}")
        logger.info(f"   取消卖出金额: {cancel_sell_total:>12.2f}")

        # 5. 新增：输出个数汇总
        logger.info(f"📊 今日汇总（笔数）:")
        logger.info(f"   常规买入笔数: {buy_regular_count:>12}")
        logger.info(f"   延期买入笔数: {buy_deferred_count:>12}")
        logger.info(f"   卖出笔数    : {sell_count:>12}")
        logger.info(f"   取消买入笔数: {cancel_buy_count:>12}")
        logger.info(f"   取消卖出笔数: {cancel_sell_count:>12}")
        # 延期额度相关统计
        deferred_create_count = len(day_deferred)
        logger.info(f"   当日延期额度创建股票数: {deferred_create_count:>12}")
        redeferred_count = sum(1 for d in day_deferred if d.get('is_redeferred', False))
        logger.info(f"   当日再延期股票数: {redeferred_count:>12}")
        # 新增：当日过期自动释放延期额度的股票数
        logger.info(f"   当日过期释放延期股票数: {self.expired_released_today:>12}")
        # 新增：收盘时延期股票数
        logger.info(f"   收盘时延期股票数: {self.deferred_at_close_today:>12}")
        # ========== 新增：计划买入股票数 ==========
        logger.info(f"   计划常规买入股票数: {self.planned_regular_today:>12}")
        logger.info(f"   计划延期买入股票数: {self.planned_deferred_today:>12}")
        # =========================================

        # 6. 输出每日持仓
        logger.info("=" * 80)
        logger.info(f"📈 收盘持仓 - {current_date}")
        portfolio_status = self.portfolio_manager.get_portfolio_status(current_datetime)
        positions = portfolio_status.get('positions', {})
        if positions:
            logger.info(f"{'股票':<8} {'持仓天数':>6} {'数量':>8} {'成本价':>8} {'现价':>8} {'市值':>10} {'盈亏%':>8}")
            logger.info("-" * 80)
            for stock, pos in positions.items():
                logger.info(
                    f"{stock:<8} {pos['hold_days']:>6} {pos['size']:>8} {pos['cost_price']:>8.2f} {pos['current_price']:>8.2f} {pos['current_value']:>10.2f} {pos['profit_pct']:>7.2f}%")
        else:
            logger.info("无持仓")
        logger.info("=" * 80)

    # ==================== 新增统计报告方法 ====================

    def _generate_comparison_report(self, current_datetime, is_final=False):
        """生成并输出 Broker 与 PortfolioManager 的对比报告（现金、持仓、差异）"""
        prefix = "【最终】" if is_final else "【每日】"
        logger.info(f"{prefix} 资金对比报告:")

        # 获取权威数据
        portfolio_status = self.portfolio_manager.get_portfolio_status(current_datetime)
        auth_cash = portfolio_status['cash']
        auth_positions = portfolio_status['positions']
        auth_portfolio_value = portfolio_status['portfolio_value']
        auth_holdings = auth_portfolio_value - auth_cash

        # Broker 数据
        broker_cash = self.broker.getcash()
        broker_value = self.broker.getvalue()
        broker_holdings = broker_value - broker_cash
        cash_diff = broker_cash - auth_cash
        value_diff = broker_value - auth_portfolio_value

        logger.info(f"  【权威】PortfolioManager 统计：")
        logger.info(f"    投资组合总价值: {auth_portfolio_value:,.2f}")
        logger.info(f"    现金余额: {auth_cash:,.2f}")
        logger.info(f"    持仓市值: {auth_holdings:,.2f}")
        logger.info(f"    持仓股票数: {len(auth_positions)}")

        logger.info(f"  【参考】Broker 统计：")
        logger.info(f"    Broker 总资产: {broker_value:,.2f}")
        logger.info(f"    Broker 现金: {broker_cash:,.2f}")
        logger.info(f"    Broker 持仓市值: {broker_holdings:,.2f}")

        logger.info(f"  【对比】差异 (Broker - 权威)：")
        logger.info(f"    现金差异: {cash_diff:+.2f} 元")
        logger.info(f"    总资产差异: {value_diff:+.2f} 元")

        if abs(cash_diff) > 1.0:
            logger.warning(f"  ⚠️ 现金差异超过 1 元，可能存在资金流不一致，请检查延期额度、补充资金或佣金处理。")

        # 如果是最终报告，输出完整资金流水审计（可选）
        if is_final:
            logger.info("🔍 执行最终资金一致性验证...")
            is_consistent = self.portfolio_manager.validate_cash_consistency(current_datetime)
            if is_consistent:
                logger.info("  ✅ 资金一致性验证通过")
            else:
                logger.error("  ❌ 资金一致性验证失败！请检查资金流逻辑")
                cash_breakdown = self.portfolio_manager.get_cash_flow_breakdown()
                logger.error("  资金流明细:")
                for key, value in cash_breakdown.items():
                    logger.error(f"    {key}: {value}")

    def _generate_performance_summary(self, is_final=False):
        """生成并输出累计交易绩效统计"""
        prefix = "【最终】" if is_final else "【每日】"
        logger.info(f"{prefix} 交易绩效统计:")

        if self.total_trades > 0:
            win_rate = (self.winning_trades / self.total_trades) * 100
            logger.info(f"  总交易次数: {self.total_trades}")
            logger.info(f"  盈利交易次数: {self.winning_trades}")
            logger.info(f"  亏损交易次数: {self.losing_trades}")
            logger.info(f"  胜率: {win_rate:.2f}%")
        else:
            logger.info("  无交易记录")

    def _generate_capital_pool_summary(self, is_final=False):
        """生成并输出全局资金池状态（初始/剩余资金、延期额度、补充资金）"""
        prefix = "【最终】" if is_final else "【每日】"
        logger.info(f"{prefix} 全局资金池状态:")

        initial_capital = self.portfolio_manager.get_initial_capital()
        final_capital = self.portfolio_manager.get_total_cash()
        summary = self.portfolio_manager.get_summary()
        total_invested = summary.get('total_invested', 0.0)

        logger.info(f"  初始总资金: {initial_capital:,.2f}")
        logger.info(f"  当前剩余资金: {final_capital:,.2f}")
        logger.info(f"  总投资金额（含所有来源）: {total_invested:,.2f}")

        if is_final:
            logger.info(f"  资金利用率: {total_invested / initial_capital * 100:.2f}%")

        # 延期额度统计
        deferred_status = self.portfolio_manager.get_deferred_quota_status()
        logger.info(f"  可用延期额度总额: {deferred_status.get('total_usable_deferred_quota', 0):,.2f}")
        logger.info(f"  已使用延期额度总额: {deferred_status.get('total_used_deferred_quota', 0):,.2f}")

        # 补充资金统计
        supplementary_status = self.portfolio_manager.get_supplementary_capital_status()
        logger.info(f"  总使用补充资金: {supplementary_status.get('total_supplementary_used', 0):,.2f}")
        if is_final:
            logger.info(f"  补充资金使用明细: {dict(supplementary_status.get('supplementary_used_by_date', {}))}")

    def _generate_return_report(self, current_datetime, is_final=False):
        """生成并输出收益率相关报告（基于权威数据）"""
        logger.info("\n【收益率】基于全局初始资金：")
        initial_capital = self.portfolio_manager.get_initial_capital()
        portfolio_status = self.portfolio_manager.get_portfolio_status(current_datetime)
        auth_portfolio_value = portfolio_status['portfolio_value']

        auth_total_return = (auth_portfolio_value / initial_capital - 1) * 100
        logger.info(f"  权威总收益率: {auth_total_return:.2f}%")

        broker_value = self.broker.getvalue()
        broker_total_return = (broker_value / initial_capital - 1) * 100
        logger.info(f"  Broker 总收益率 (参考): {broker_total_return:.2f}%")
        logger.info(f"  (说明：Broker 收益率未考虑延期预留资金，仅供参考)")

        final_global_cash = self.portfolio_manager.get_total_cash()
        actually_invested_capital = initial_capital - final_global_cash
        if actually_invested_capital > 0:
            return_on_invested = ((auth_portfolio_value - final_global_cash) / actually_invested_capital - 1) * 100
            logger.info(f"  已动用资金收益率: {return_on_invested:.2f}%")
        else:
            logger.info("  无已动用资金（未发生投资）")

    # ==================== 原有方法保持不变 ====================

    def start(self):
        """策略开始运行时检查"""
        logger.info("策略开始运行")

        # 通过 PortfolioManager 获取资金池初始状态
        initial_capital = self.portfolio_manager.get_initial_capital()  # 假设存在
        daily_limit = self.portfolio_manager.get_daily_limit()          # 假设存在

        logger.info(f"💰 全局资金池初始状态:")
        logger.info(f"  - 总资金: {initial_capital:.2f}")
        logger.info(f"  - 每日投资限额: {daily_limit:.2f}")

        # 获取延期额度和补充资金状态
        deferred_status = self.portfolio_manager.get_deferred_quota_status()
        supplementary_status = self.portfolio_manager.get_supplementary_capital_status()

        logger.info(f"  - 初始延期额度可用总额: {deferred_status.get('total_usable_deferred_quota', 0):.2f}")
        logger.info(f"  - 补充资金累计使用（初始为0）: {supplementary_status.get('total_supplementary_used', 0):.2f}")

    def _init_profit_record(self):
        """初始化盈利记录

        返回包含盈利统计信息的字典

        返回:
        dict: 盈利记录
        """
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_profit': 0.0,
            'total_profit_pct': 0.0,
            'avg_profit_pct': 0.0,
            'max_profit_pct': -float('inf'),
            'max_loss_pct': float('inf'),
            'trade_dates': []
        }

    def log_memory_usage(self):
        """记录内存使用情况 - 优化版本

        1. 检查是否已记录当日内存使用
        2. 获取当前进程的内存使用
        3. 记录内存使用情况
        4. 如果内存使用过高，记录警告
        """
        try:
            current_date = self.datas[0].datetime.date(0)
            if hasattr(self, '_last_memory_log_date') and self._last_memory_log_date == current_date:
                return

            self._last_memory_log_date = current_date

            process = psutil.Process(os.getpid())
            mem_usage = process.memory_info().rss / 1024 / 1024
            self.memory_usage_log.append({
                'date': current_date,
                'memory_usage_mb': mem_usage
            })

            # 只在内存使用较高时记录警告
            if mem_usage > 500:
                logger.warning(f"内存使用较高: {mem_usage:.2f} MB")
            else:
                logger.debug(f"内存使用: {mem_usage:.2f} MB")

        except Exception as e:
            logger.warning(f"记录内存使用失败: {e}")

    def log_trade(self, action, stock, price, size, reason="",
                  decision_time=None, creation_time=None, execution_time=None,
                  is_deferred=False, supplementary_amount=0.0):
        """改进的交易日志记录 - 增加时间分析和资金类型

        1. 记录交易详细信息
        2. 计算决策到创建、创建到执行的延迟
        3. 记录时间分析信息
        4. 记录涨跌停信息
        5. 记录资金类型（延期额度、补充资金）

        参数:
        action (str): 交易动作（BUY/SELL）
        stock (str): 股票代码
        price (float): 交易价格
        size (int): 交易数量
        reason (str): 交易原因
        decision_time (datetime): 决策时间
        creation_time (datetime): 创建时间
        execution_time (datetime): 执行时间
        is_deferred (bool): 是否使用延期额度
        supplementary_amount (float): 使用的补充资金金额（动态补充资金机制下，此值在成交后计算）
        """
        # 获取精确的日期时间
        current_datetime = bt.num2date(self.datas[0].datetime[0])

        trade_info = {
            'date': current_datetime.date(),          # 日期
            'time': current_datetime.time(),          # 时间（时:分:秒）
            'datetime': current_datetime,             # 完整时间戳
            'action': action,
            'stock': stock,
            'price': price,
            'size': size,
            'reason': reason,
            'portfolio_value': self.broker.getvalue(),
            # 新增时间分析字段
            'decision_time': decision_time or current_datetime,
            'creation_time': creation_time or current_datetime,
            'execution_time': execution_time,
            'decision_to_creation_delay': None,
            'creation_to_execution_delay': None,
            'total_decision_to_execution_delay': None,
            # 新增：标记时间来源
            'creation_time_source': 'order.created.dt' if creation_time and hasattr(creation_time,
                                                                                    'second') else 'estimated',
            # 新增：资金类型标记
            'is_deferred': is_deferred,
            'supplementary_amount': supplementary_amount
        }

        # 计算时间延迟
        if decision_time and creation_time:
            trade_info['decision_to_creation_delay'] = (creation_time - decision_time).total_seconds()

        if creation_time and execution_time:
            trade_info['creation_to_execution_delay'] = (execution_time - creation_time).total_seconds()

        if decision_time and execution_time:
            trade_info['total_decision_to_execution_delay'] = (decision_time - execution_time).total_seconds()

        # 添加涨跌停信息
        if action in ['BUY', 'SELL']:
            status = self.portfolio_manager.get_stock_status(stock)
            trade_info['limit_up'] = status.limit_up_price
            trade_info['limit_down'] = status.limit_down_price

        self.trade_log.append(trade_info)

        # 记录时间分析日志
        if self.params.enable_time_analysis:
            time_analysis_info = trade_info.copy()
            time_analysis_info['log_type'] = 'time_analysis'
            self.time_analysis_log.append(time_analysis_info)

            # 记录详细的时间分析信息
            if decision_time and creation_time:
                delay = (creation_time - decision_time).total_seconds()
                logger.debug(f"时间分析 - {stock} {action}: 决策{decision_time}到创建{creation_time}延迟 {delay:.3f}秒")

            if creation_time and execution_time:
                delay = (execution_time - creation_time).total_seconds()
                logger.debug(
                    f"时间分析 - {stock} {action}: 创建{creation_time}到执行{execution_time}延迟 {delay:.3f}秒，")

        # 构建资金来源描述
        source_desc = []
        if is_deferred:
            source_desc.append("延期额度")
        if supplementary_amount > 0:
            source_desc.append(f"补充资金({supplementary_amount:.2f})")
        if not is_deferred and supplementary_amount == 0:
            source_desc.append("正常投资")

        source_str = "+".join(source_desc) if source_desc else "正常投资"

        logger.info(f"{action} {stock}: 价格{price:.2f}, 数量{size}, 原因: {reason}, 资金来源: {source_str}")

    def notify_order(self, order):
        """订单状态通知 - 优化版本，增加时间分析和资金回滚

        1. 处理订单完成状态
        2. 处理订单异常状态（取消/拒绝/保证金不足），并回滚已扣除的资金
        3. 记录时间分析信息
        4. 更新投资组合状态
        5. 从订单info中提取资金类型信息
        """
        stock_name = order.data._name
        current_datetime = bt.num2date(self.datas[0].datetime[0])
        current_date = current_datetime.date()

        # 兼容嵌套结构读取订单info
        if hasattr(order, 'info'):
            # 兼容可能存在的嵌套
            info_dict = order.info.get('info', {}) if hasattr(order.info, 'get') else {}
            if not info_dict and isinstance(order.info, dict):
                info_dict = order.info
            is_deferred = info_dict.get('is_deferred', False)
            # 动态补充资金机制：不再从订单info传递 supplementary_amount
            # supplementary_amount = info_dict.get('supplementary_amount', 0.0)
            supplementary_amount = 0.0  # 占位，实际在成交后计算
            date_str = info_dict.get('date_str', '')
        else:
            is_deferred = False
            supplementary_amount = 0.0
            date_str = ''

        logger.debug(f"订单 {stock_name} 状态 {order.getstatusname()}, is_deferred={is_deferred}")

        if order.status in [order.Completed]:
            # 获取订单创建时间（从order.created.dt获取）
            decision_time = self.order_decision_time.get(stock_name)

            # 使用order.created.dt作为精确的创建时间
            if hasattr(order, 'created') and hasattr(order.created, 'dt'):
                creation_time = bt.num2date(order.created.dt)
            else:
                # 备用方案：如果order.created.dt不存在，使用当前时间
                creation_time = current_datetime

            execution_time = current_datetime  # 订单完成时间

            # 获取成交时间（用于佣金记录和后续订单执行）
            order_executed_time = bt.num2date(order.executed.dt) if hasattr(order.executed, 'dt') else current_datetime
            order_executed_date_str = order_executed_time.strftime('%Y%m%d')

            # 累计佣金并通过 PortfolioManager 同步到全局资金管理器
            if hasattr(order, 'executed') and hasattr(order.executed, 'comm'):
                self.total_commission += order.executed.comm
                # 通过 portfolio_manager 记录佣金
                self.portfolio_manager.record_commission(order.executed.comm, order_executed_time, stock_code=stock_name)
                logger.debug(f"累计佣金增加 {order.executed.comm:.2f}, 总佣金 {self.total_commission:.2f}")

            if order.isbuy():
                size = order.executed.size
                price = order.executed.price
                actual_cost = price * size  # 实际成交金额

                # 调用 execute_buy_order，不再传递 supplementary_amount
                # 补充资金将在 PortfolioManager.execute_buy_order 内部动态计算
                success = self.portfolio_manager.execute_buy_order(
                    stock_name, price, size, order_executed_time,
                    is_deferred=is_deferred
                )
                if success:
                    self.log_trade('BUY', stock_name, price, size, "买入完成",
                                   decision_time, creation_time, order_executed_time,
                                   is_deferred=is_deferred, supplementary_amount=0.0)  # 补充金额已在资金池记录，日志中可暂不体现
                    self._update_profit_record(stock_name, 'BUY', current_date, price, size)
                else:
                    # 买入记录失败，execute_buy_order 内部已回滚，但此处仍应终止回测，防止资金不一致
                    logger.critical(f"❌ 严重资金不一致！订单 {stock_name} 已成交但全局资金池未扣款，请检查。")
                    # ==== 增加详细订单信息日志 ====
                    logger.critical(f"订单详情: 方向=BUY, 成交价={price:.2f}, 成交数量={size}, 成交金额={actual_cost:.2f}, 佣金={order.executed.comm:.2f}")
                    logger.critical(f"订单状态: {order.getstatusname()}, 创建时间={bt.num2date(order.created.dt) if hasattr(order.created, 'dt') else 'N/A'}")
                    if hasattr(order, 'info'):
                        logger.critical(f"订单info: {order.info}")
                    # ==============================
                    raise RuntimeError(f"资金不一致，终止回测: {stock_name}")

            elif order.issell():
                size = abs(order.executed.size)  # 实际成交数量
                price = order.executed.price
                # 调用成交后处理方法，不再调用 execute_sell_order
                if self.portfolio_manager.process_sell_order_execution(stock_name, price, size, order_executed_time):
                    self.log_trade('SELL', stock_name, price, size, "卖出完成",
                                   decision_time, creation_time, order_executed_time,
                                   is_deferred=is_deferred, supplementary_amount=0.0)
                    self._update_profit_record(stock_name, 'SELL', current_date, price, size)

            # 清理时间记录
            if stock_name in self.order_decision_time:
                del self.order_decision_time[stock_name]
            if stock_name in self.order_creation_time:
                del self.order_creation_time[stock_name]

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            logger.warning(f"订单异常: {stock_name}, 状态: {order.getstatusname()}")

            # 注意：补充资金和延期额度仅在成交时才从资金池扣除，取消订单时无需回滚
            # 仅移除挂单卖出数量（对于未成交的卖出订单）
            if order.issell():
                # 计算需要移除的挂单数量：原始订单大小 - 已成交部分
                remaining_size = order.created.size - abs(order.executed.size)
                if remaining_size > 0:
                    self.portfolio_manager.remove_pending_sell(stock_name, remaining_size)
                    logger.info(f"移除挂单卖出: {stock_name} 数量 {remaining_size} (订单取消/拒绝)")

            # ===== 新增：记录取消事件 =====
            # 获取订单基本信息
            is_buy = order.isbuy()
            original_size = abs(order.created.size)
            executed_size = abs(order.executed.size) if order.executed.size else 0
            remaining = original_size - executed_size
            price = order.created.price if hasattr(order.created, 'price') else (order.limit if hasattr(order, 'limit') else 0)
            cancel_time = current_datetime  # 使用当前数据时间

            self.cancel_log.append({
                'date': cancel_time.date(),
                'datetime': cancel_time,
                'stock': stock_name,
                'direction': 'BUY' if is_buy else 'SELL',
                'remaining_size': remaining,
                'price': price,
                'amount': remaining * price,
                'reason': order.getstatusname()
            })
            logger.info(f"记录取消订单: {stock_name} {remaining}股 @ {price:.2f}, 原因: {order.getstatusname()}")

            # ===== 新增：处理延期买入订单取消，重新标记 need_buy_next_day =====
            if order.isbuy() and is_deferred:
                status = self.portfolio_manager.get_stock_status(stock_name)
                status.need_buy_next_day = True
                logger.info(f"延期买入订单取消，重新标记 {stock_name} 为需要次日买入")

            # 记录失败订单的时间分析
            decision_time = self.order_decision_time.get(stock_name)

            # 使用order.created.dt作为精确的创建时间
            if hasattr(order, 'created') and hasattr(order.created, 'dt'):
                creation_time = bt.num2date(order.created.dt)
            else:
                creation_time = current_datetime

            if decision_time and creation_time:
                delay = (current_datetime - decision_time).total_seconds()
                logger.warning(f"时间分析 - 失败订单 {stock_name}: 总延迟 {delay:.3f}秒, 状态: {order.getstatusname()}")

            # 清理时间记录
            if stock_name in self.order_decision_time:
                del self.order_decision_time[stock_name]
            if stock_name in self.order_creation_time:
                del self.order_creation_time[stock_name]

        if order.status in [order.Completed, order.Canceled, order.Margin]:
            self.orders[stock_name] = None

    def _update_profit_record(self, stock_name, action, date, price, size):
        """更新盈利记录

        1. 更新总交易次数
        2. 更新盈利/亏损交易次数
        3. 计算盈亏百分比
        4. 记录交易详情

        参数:
        stock_name (str): 股票代码
        action (str): 交易动作（BUY/SELL）
        date (date): 交易日期
        price (float): 交易价格
        size (int): 交易数量
        """
        profit_info = self.stock_profits[stock_name]
        profit_info['total_trades'] += 1
        profit_info['trade_dates'].append({
            'date': date,
            'action': action,
            'price': price,
            'size': size
        })

        if action == 'SELL':
            # 计算盈亏
            status = self.portfolio_manager.get_stock_status(stock_name)
            if status.cost_price > 0:
                pnl_pct = (price - status.cost_price) / status.cost_price * 100
                self.total_trades += 1

                if pnl_pct > 0:
                    self.winning_trades += 1
                    profit_info['winning_trades'] += 1
                else:
                    self.losing_trades += 1
                    profit_info['losing_trades'] += 1

                profit_info['trade_dates'][-1]['profit_pct'] = pnl_pct

    def next(self):
        """策略核心逻辑 - 优化版本，增加时间分析

        1. 更新持仓天数
        2. 更新市场数据
        3. 自动检查止损止盈
        4. 清理已完成的订单
        5. 处理交易逻辑
        """
        current_stock_being_processed = None
        try:
            current_datetime = bt.num2date(self.datas[0].datetime[0])
            current_date = current_datetime.date()
            current_time = current_datetime.time()

            # 更新持仓天数（每日一次）
            if self.last_trade_date != current_date:
                self.log_memory_usage()
                logger.debug(f"{current_date}更新持仓天数前")
                self.portfolio_manager.update_hold_days(current_date)
                logger.debug(f"{current_date}更新持仓天数后")
                self.last_trade_date = current_date

                # ===== 新增：统计过期释放的延期额度股票数 =====
                current_date_str = current_date.strftime('%Y%m%d')
                # 记录释放前每个股票的延期额度
                before_deferred = {}
                for stock in self.actual_stock_pool:
                    deferred = self.portfolio_manager.get_deferred_for_stock(stock, current_date_str)
                    if deferred > 0:
                        before_deferred[stock] = deferred

                # 每日开盘强制释放过期延期额度
                self.portfolio_manager.release_expired_deferred(current_date)
                logger.debug(f"每日开盘强制释放过期延期额度: {current_date}")

                # 统计释放后变为0的股票数量
                released_count = 0
                for stock in before_deferred:
                    deferred_after = self.portfolio_manager.get_deferred_for_stock(stock, current_date_str)
                    if deferred_after <= 0:
                        released_count += 1
                self.expired_released_today = released_count
                if released_count > 0:
                    logger.info(f"今日过期自动释放延期额度的股票数: {released_count}")
                # ============================================

                # ===== 新增：清理过期的 need_buy_next_day 标记 =====
                for stock in self.actual_stock_pool:
                    status = self.portfolio_manager.get_stock_status(stock)
                    if status.need_buy_next_day:
                        deferred = self.portfolio_manager.get_deferred_for_stock(stock, current_date_str)
                        if deferred <= 0:
                            status.need_buy_next_day = False
                            logger.debug(f"清除 {stock} 过期的 need_buy_next_day 标记")

                portfolio_status = self.portfolio_manager.get_portfolio_status(current_datetime)  # 很容易在此卡死
                logger.info(f"组合价值: {portfolio_status['portfolio_value']:.2f}, "
                            f"现金: {portfolio_status['cash']:.2f}")

                # 计算当日可用投资额度（不含延期），用于平均分配
                daily_available_normal = self.portfolio_manager.get_available_normal(current_datetime)

                # 获取当日候选股票列表
                stocks_for_current = self._get_stocks_for_buy_date(current_date)
                if len(stocks_for_current) >= 1:
                    # ===== 根据分配模式计算资金分配 =====
                    if self.params.allocation_mode in ('equal', 'force_min'):
                        # 等额分配（模式一和模式二都使用相同的现金额度）
                        self.cash_per_stock = daily_available_normal / len(stocks_for_current)
                        logger.info(
                            f"[等额分配] {current_date} 共有 {len(stocks_for_current)} 只候选股，平均分配金额: {self.cash_per_stock:.2f} 元 (模式: {self.params.allocation_mode})")
                    elif self.params.allocation_mode == 'dynamic':
                        # 动态分配模式：不在开盘时计算，推迟到买入前重新计算
                        # 这里仅记录候选股票列表，实际分配在 _process_normal_buy_orders 中计算
                        self.dynamic_allocations = {}  # 清空旧数据
                        logger.info(f"[动态分配] {current_date} 共有 {len(stocks_for_current)} 只候选股，将在买入前重新计算分配")
                    else:
                        logger.error(f"未知的资金分配模式: {self.params.allocation_mode}，回退到等额分配")
                        self.cash_per_stock = daily_available_normal / len(stocks_for_current)
                else:
                    self.cash_per_stock = 0.0
                    self.dynamic_allocations = {}
                    logger.debug(f"今日{current_date} 无候选股，重置cash_per_stock和dynamic_allocations")

                # ========== 新增：计算计划买入股票数 ==========
                # 计划常规买入股票数 = 当日候选股数量
                self.planned_regular_today = len(stocks_for_current)

                # 计划延期买入股票数 = 统计 need_buy_next_day 为 True 且有可用延期额度的股票数
                deferred_planned = 0
                for stock in self.actual_stock_pool:
                    status = self.portfolio_manager.get_stock_status(stock)
                    if status.need_buy_next_day:
                        deferred = self.portfolio_manager.get_deferred_for_stock(stock, current_date_str)
                        if deferred > 0:
                            deferred_planned += 1
                self.planned_deferred_today = deferred_planned
                logger.debug(f"今日计划：常规买入 {self.planned_regular_today} 只，延期买入 {self.planned_deferred_today} 只")
                # ============================================

                # 重置收盘标志，新的一天可以重新买入
                self._market_closed = False

            # 更新市场数据
            stock_data_dict = self._prepare_market_data(current_datetime)
            self.portfolio_manager.update_market_data(current_datetime, stock_data_dict)

            # 自动检查止损止盈
            self._process_sell_orders(current_datetime)

            # 清理已完成的订单
            self._cleanup_completed_orders(current_datetime)

            # 处理交易逻辑 - 优化检查顺序
            self._process_buy_orders(current_datetime)

            # 注意：不再在此处手动调用 _on_daily_close，改为依赖定时器
            # 定时器好像漏过了每日交易报告 - 2025-10-24
            if current_time == time(15, 0):
                logger.info("🕒 到达15:00，手动调用一次")
                # 手动调用一次，测试功能
                self._on_daily_close()

        except Exception as e:
            logger.error(f"策略执行错误: {e}")
            logger.error(f"当前日期: {current_date}, 当前时间: {current_time}")
            logger.error(f"当前处理的股票: {current_stock_being_processed or 'unknown'}")
            import traceback
            logger.error(traceback.format_exc())

    def _prepare_market_data(self, current_datetime):
        """准备市场数据

        1. 为每只股票准备市场数据
        2. 包含开盘价、最高价、最低价、收盘价、成交量、前收盘价

        返回:
        dict: 股票市场数据字典
        """
        current_date = current_datetime.date()
        current_time = current_datetime.time()

        stock_data_dict = {}
        for stock in self.actual_stock_pool:
            data = self.stock_data[stock]
            stock_data_dict[stock] = {
                'open': data.open[0],
                'high': data.high[0],
                'low': data.low[0],
                'close': data.close[0],
                'volume': data.volume[0],
                'prev_close': data.prev_close[0] if hasattr(data, 'prev_close') and len(data.prev_close) > 0 else
                data.close[-1],
            }

        return stock_data_dict

    # ==================== 动态分配计算（支持传入价格字典）====================
    def _calculate_dynamic_allocation(self, current_date, stocks, total_available, price_dict=None):
        """
        计算动态分配模式下每只股票的分配金额。
        策略：优先保证每只股票至少买入100股，若资金不足则按比例分配资金，然后计算可买手数（向下取整到100的倍数）。
        若某只股票分配资金不足100股，则放弃该股票，并将剩余资金保留（不再重新分配，简化处理）。

        参数:
            current_date: 当前日期
            stocks: 候选股票列表
            total_available: 当前可用资金总额
            price_dict: 可选，预先获取的价格字典 {stock: price}，若未提供则使用开盘价

        返回:
            dict: {stock: allocated_cash}
        """
        allocations = {}
        prices = {}
        required = {}
        total_required = 0.0

        for stock in stocks:
            data = self.stock_data.get(stock)
            if data is None:
                continue
            if price_dict is not None and stock in price_dict:
                price = price_dict[stock]
            else:
                price = data.open[0]  # 默认使用开盘价
            prices[stock] = price
            req = price * 100
            required[stock] = req
            total_required += req

        if total_required <= total_available:
            # 资金充足，每只股票分配一手所需资金
            for stock in stocks:
                allocations[stock] = required[stock]
        else:
            # 资金不足，按比例分配资金，然后计算可买手数
            ratio = total_available / total_required
            temp_alloc = {}
            for stock in stocks:
                alloc = required[stock] * ratio
                price = prices[stock]
                shares = int(alloc / price / 100) * 100  # 向下取整到100的倍数
                if shares >= 100:
                    alloc = shares * price
                    temp_alloc[stock] = alloc
                else:
                    temp_alloc[stock] = 0  # 无法买入
            # 仅保留能买入的股票
            for stock, alloc in temp_alloc.items():
                if alloc > 0:
                    allocations[stock] = alloc
            # 剩余资金不再分配（简化处理）

        return allocations

    # ==================== 修复点：_process_sell_orders 修改为计算可用数量 ====================
    def _process_sell_orders(self, current_datetime):
        """处理止损止盈订单 - 根据信号类型动态选择订单类型

        1. 获取需要卖出的订单
        2. 为每只股票创建卖出订单
        3. 记录决策时间
        """
        stop_loss_orders = []
        all_stock_status = self.portfolio_manager.get_all_stock_status()
        for stock_code, status in all_stock_status.items():
            # 检查是否已持仓
            data = self.stock_data[stock_code]
            position = self.getposition(data)
            if not position or position.size <= 0:
                continue  # 没有持仓，跳过卖出检查

            current_price = data.close[0]
            # 检查跌停（跌停时不能卖出，但允许涨停卖出）
            if self.portfolio_manager.limit_manager.is_limit_down(stock_code, current_price):
                continue

            # 获取技术指标（策略4必需）
            indicators = self._get_indicators(stock_code)

            should_sell, reason = self.portfolio_manager.should_sell(
                stock_code=stock_code,
                current_datetime=current_datetime,
                current_price=current_price,
                indicators=indicators
            )

            if should_sell:
                # 检查T+1规则
                if not self.portfolio_manager.can_trade_tplus1(stock_code, 'SELL', current_datetime):
                    continue

                # 获取可卖数量和当前挂单数量
                sellable_quantity = self.portfolio_manager.tplus1_manager.get_sellable_quantity(stock_code, current_datetime)
                pending = self.portfolio_manager.pending_sells.get(stock_code, 0)
                available = sellable_quantity - pending

                if available > 0:
                    stop_loss_orders.append({
                        'stock_code': stock_code,
                        'direction': 'SELL',
                        'price': status.current_price,
                        'size': available,
                        'reason': reason
                    })

        for order_info in stop_loss_orders:
            stock_code = order_info['stock_code']
            data = self.stock_data[stock_code]
            position = self.getposition(data)

            if position and position.size > 0:
                # 记录止损决策时间
                decision_time = bt.num2date(self.datas[0].datetime[0])
                self.order_decision_time[stock_code] = decision_time

                # 记录挂单卖出数量
                self.portfolio_manager.add_pending_sell(stock_code, order_info['size'])

                reason = order_info['reason']
                reason_type = None

                # 根据信号类型动态选择订单类型
                order_exectype = bt.Order.Limit  # 默认限价单
                if reason.startswith('profit_take'):
                    reason_type = '止盈'
                    # 动态止盈（version1/version2）与策略6分档回撤止盈需使用市价单确保成交
                    if self.params.strategy_version in ('version1', 'version2', 'version6'):
                        order_exectype = bt.Order.Market
                    # 静态止盈（version3/version5）保持限价单以获取更好价格
                elif reason.startswith('stop_loss'):
                    reason_type = '止损'
                    order_exectype = bt.Order.Market
                elif reason.startswith('force_sell'):  # 新增：强制平仓使用市价单
                    reason_type = '强制平仓'
                    order_exectype = bt.Order.Market
                else:
                    reason_type = '卖出'
                    # 其他卖出信号（如均线卖出）暂保留限价单，可根据需要调整

                # 创建卖出订单
                self.orders[stock_code] = self.sell(
                    data,
                    size=order_info['size'],
                    price=order_info['price'],
                    exectype=order_exectype,
                    valid=bt.Order.DAY,
                    info=order_info
                )

                # 修改这里：不再立即设置creation_time
                self.order_creation_time[stock_code] = None  # 设置为None，等待notify_order更新

                logger.info(
                    f"创建{reason_type}订单，原因{reason}: {stock_code}, 价格{order_info['price']:.2f}, 数量{order_info['size']}, 订单类型: {order_exectype}")

    def _cleanup_completed_orders(self, current_datetime):
        """清理已完成的订单

        1. 检查每只股票的订单状态
        2. 清理已完成的订单
        """
        for stock in self.actual_stock_pool:
            order = self.orders[stock]
            if order and order.status in [bt.Order.Completed, bt.Order.Canceled, bt.Order.Margin]:
                self.orders[stock] = None

    def _get_indicators(self, stock_code: str) -> Dict[str, float]:
        """
        获取当前股票的技术指标值（供策略4使用）
        :return: 指标字典，如 {'ma5': 10.5, 'ma10': 10.2}
        """
        if stock_code not in self.calc_indicators:
            return {}

        indicators = {}
        for name, indicator in self.calc_indicators[stock_code].items():
            # 获取最新有效值（处理NaN）
            val = indicator[0]
            if np.isnan(val) or not np.isfinite(val):
                # 尝试获取历史有效值（最多回溯5根K线）
                for i in range(1, 6):
                    val = indicator[-i]
                    if not (np.isnan(val) or not np.isfinite(val)):
                        break
                else:
                    val = None
            indicators[name] = val if val is not None else None
        return indicators

    def _can_buy(self, stock_code: str) -> bool:
        """检查是否满足买入条件（仓位、资金等）"""
        # 检查是否有相同未完成订单
        order = self.orders[stock_code]
        if order is not None:
            return False

        # 检查单票仓位上限（通过calculate_position_size中的检查实现）
        # 检查可用资金（通过calculate_position_size中的检查实现）

        return True

    def _process_buy_orders(self, current_datetime):
        """处理交易逻辑 - 优化检查顺序，增加时间分析

        1. 次日开盘买入（9:30-9:45）
        2. 正常买入（14:55后） - 根据每个股票的买入日期判断
        """
        # 如果已经收盘，不再创建任何买入订单
        if self._market_closed:
            logger.debug("市场已收盘，跳过买入处理")
            return

        current_time = current_datetime.time()
        current_date = current_datetime.date()

        if self.params.skip_limit_up:
            pass
        else:
            # 1. 处理次日开盘买入逻辑
            if time(9, 30) <= current_time <= time(9, 45):
                self._process_next_day_buy_orders(current_datetime)

        # 2. 处理正常买入逻辑（14:55后）
        if current_time >= self.params.buy_time:
            # 注意：每次触发都会计算平均分配资金，已在每日开始时计算，此处直接使用
            self._process_normal_buy_orders(current_datetime)

    def _process_next_day_buy_orders(self, current_datetime):
        """处理次日开盘买入逻辑，增加时间分析

        新增功能：使用延期额度进行买入（按股票独立使用）

        1. 获取所有股票池中的股票
        2. 对每只股票，检查是否标记为 need_buy_next_day 并且有可用延期额度
        3. 检查股票是否已持有、是否涨停等
        4. 如果满足买入条件，使用其专属延期额度计算买入数量
        5. 创建买入订单，标记为延期额度（限价单）
        6. 买入成功后，扣减该股票的延期额度记录
        """
        # 如果已经收盘，不再创建任何买入订单
        if self._market_closed:
            return

        current_date = current_datetime.date()
        current_date_str = current_date.strftime('%Y%m%d')

        # 获取所有股票池
        all_stocks = self.actual_stock_pool

        # 过滤出需要次日买入且可用延期额度>0的股票
        candidates = []
        for stock in all_stocks:
            # 检查是否标记为需要次日买入
            status = self.portfolio_manager.get_stock_status(stock)
            if not status.need_buy_next_day:
                continue

            # 查询该股票今日可用的延期额度
            deferred = self.portfolio_manager.get_deferred_for_stock(stock, current_date_str)
            if deferred <= 0:
                # 如果没有可用延期额度，清除标记，避免后续无效尝试
                status.need_buy_next_day = False
                logger.debug(f"清除 {stock} 过期的 need_buy_next_day 标记（无可用延期额度）")
                continue

            # ===== 新增：再次确认延期额度足够购买100股 =====
            data = self.stock_data[stock]
            current_price = data.open[0]
            if deferred < 100 * current_price:
                logger.debug(f"股票 {stock} 延期额度 {deferred:.2f} 不足购买100股，清除标记")
                status.need_buy_next_day = False
                continue

            candidates.append((stock, deferred, status))

        if not candidates:
            logger.debug(f"📅 {current_date} 次日开盘买入：无符合条件的股票")
            return

        logger.info(f"📅 处理次日开盘买入，日期: {current_date}，候选股票数: {len(candidates)}")

        for stock, deferred_for_stock, status in candidates:
            # 确保股票在数据中
            if stock not in self.actual_stock_pool:
                continue

            # 检查是否有相同未完成订单
            if not self._can_buy(stock):
                continue

            # 检查当日是否有相同股票的已完成订单
            if not self.portfolio_manager.can_trade_tplus1(stock, 'BUY', current_datetime):
                continue

            # 检查订单状态
            if self.orders[stock] and self.orders[stock].status in [bt.Order.Submitted, bt.Order.Accepted]:
                continue

            data = self.stock_data[stock]
            current_price = data.open[0]

            # ========== 新增：检查开盘价是否接近涨停 ==========
            if self.portfolio_manager.limit_manager.is_near_limit_up(
                    stock, current_price, self.params.near_limit_up_threshold):
                if self.params.defer_on_near_limit_up:
                    # 延期额度继续保留，等待下一个交易日
                    logger.info(f"股票 {stock} 次日开盘价接近涨停，延期额度继续保留")
                else:
                    # 跳过买入，延期额度保留（不清除标记，未来继续尝试）
                    logger.info(f"股票 {stock} 次日开盘价接近涨停，跳过买入，延期额度保留")
                continue
            # ================================================

            # 检查涨停
            if self.portfolio_manager.limit_manager.is_limit_up(stock, current_price):
                if self.params.skip_limit_up:
                    status.need_buy_next_day = False
                    self.log_trade("涨停跳过", stock, data.open[0], 0, "不标记次日买入")
                else:
                    # 继续延期（原延期额度未使用，可保留到下一个交易日）
                    logger.debug(f"股票 {stock} 再次涨停，延期额度 {deferred_for_stock:.2f} 继续保留")
                continue

            # 获取技术指标（策略4必需）
            indicators = self._get_indicators(stock)

            should_buy, reason = self.portfolio_manager.should_buy(
                stock_code=stock,
                current_datetime=current_datetime,
                current_price=current_price,
                indicators=indicators
            )

            if should_buy:
                # 调用 PortfolioManager 的 get_buy_size 计算数量
                # 注意：延期买入时，get_buy_size 应返回基于延期额度的最大可买数量
                size, _ = self.portfolio_manager.get_buy_size(
                    price=current_price,
                    stock_code=stock,
                    allocated_cash=deferred_for_stock,
                    allow_supplementary=False,  # 延期买入不使用补充资金
                    is_deferred=True
                )
                if size < 100:  # 最小交易单位
                    logger.debug(
                        f"不能创建次日开盘买入订单: {stock}, 价格{current_price:.2f}, 延期额度{deferred_for_stock:.2f}不足购买100股")
                    continue

                # 记录决策时间
                decision_time = current_datetime
                self.order_decision_time[stock] = decision_time

                # 创建订单 - 使用限价单，价格为当前价格，确保成本不超过计算值
                order_info = {
                    'is_deferred': True,
                    'stock': stock,
                    'date_str': current_date_str
                }

                # 订单创建前日志
                logger.debug(f"[DEBUG_ORDER_INFO_CREATE] {stock} 创建订单时 order_info: {order_info}")

                # ===== 修改：将市价单改为限价单 =====
                order = self.buy(
                    data,
                    size=size,
                    price=current_price,          # 限价单价格
                    exectype=bt.Order.Limit,      # 改为限价单
                    valid=bt.Order.DAY,
                    info=order_info
                )
                # =================================

                # 订单创建后日志
                logger.debug(f"[DEBUG_ORDER_CREATED] {stock} 订单已创建，order.info 类型: {type(order.info)}，内容: {order.info}")

                self.orders[stock] = order

                # 修改这里：不再立即设置creation_time，等待notify_order中获取
                self.order_creation_time[stock] = None  # 设置为None，等待notify_order更新

                status.need_buy_next_day = False
                # 移除 has_ever_bought 设置

    def _process_normal_buy_orders(self, current_datetime):
        """处理正常买入逻辑，增加时间分析

        新增功能：涨停延期额度和最低购入补充资金

        1. 检查股票是否已买入
        2. 检查股票是否已标记为次日买入
        3. 检查订单状态
        4. 检查是否已持有
        5. 检查涨停（若涨停，按可用额度预留延期）
        6. 检查全局资金池
        7. 创建买入订单（市价单）
        """
        # 如果已经收盘，不再创建任何买入订单
        if self._market_closed:
            return

        current_time = current_datetime.time()
        current_date = current_datetime.date()
        current_date_str = current_date.strftime('%Y%m%d')

        # 遍历_get_stocks_for_buy_date
        stocks_for_current = self._get_stocks_for_buy_date(current_date)
        if len(stocks_for_current) < 1:
            logger.debug(f"今日{current_date}共有 {len(stocks_for_current)} 只候选股")
            return

        # 只在指定时间执行
        if current_time < self.params.buy_time:
            return

        # 1. 检查全局资金池当日是否可投资（通过 PortfolioManager）
        if not self.portfolio_manager.can_invest_today(current_datetime):
            logger.debug(f" 今日{current_date}投资额度已用完。")
            return

        # 2. 获取当日实际可用投资总额（受总池余额和日限额约束）
        daily_available_normal = self.portfolio_manager.get_available_normal(current_datetime)
        if daily_available_normal <= 0:
            logger.debug(f" 今日{current_date}常规可用投资额度为0或不足。")
            return

        # ===== 动态分配模式：在开始遍历前重新计算分配 =====
        if self.params.allocation_mode == 'dynamic':
            # 过滤出当前可买入的股票
            buyable_stocks = []
            for stock in stocks_for_current:
                if stock not in self.stock_data:
                    continue
                # 检查是否有未完成订单
                if not self._can_buy(stock):
                    continue
                # 检查当日是否已买入过（无论延期还是常规）
                if stock in self.portfolio_manager.today_buy_stocks:
                    continue
                # 可选：再次检查T+1规则（实际已由 today_buy_stocks 隐含）
                if not self.portfolio_manager.can_trade_tplus1(stock, 'BUY', current_datetime):
                    continue
                buyable_stocks.append(stock)

            if not buyable_stocks:
                self.dynamic_allocations = {}
                logger.debug(f"[动态分配] {current_date} 无可买入股票，跳过重新计算")
            else:
                # 获取当前价格字典（使用当前 bar 的收盘价）
                price_dict = {stock: self.stock_data[stock].close[0] for stock in buyable_stocks}
                # 获取当前可用额度（可能因之前订单而减少）
                current_available = self.portfolio_manager.get_available_normal(current_datetime)
                # 重新计算动态分配
                self.dynamic_allocations = self._calculate_dynamic_allocation(
                    current_date, buyable_stocks, current_available, price_dict)
                logger.info(
                    f"[动态分配重新计算] {current_date} 可用资金 {current_available:.2f} 元，分配详情: { {k: f'{v:.2f}' for k, v in self.dynamic_allocations.items()} }")

        # 遍历所有股票，判断今天是否是它的买入日
        for stock in stocks_for_current:

            if stock not in self.actual_stock_pool:
                continue

            # 检查是否在数据中
            if stock not in self.stock_data:
                continue

            # 检查是否有相同未完成订单
            if not self._can_buy(stock):
                continue

            # 检查当日是否有相同股票的已完成订单
            if not self.portfolio_manager.can_trade_tplus1(stock, 'BUY', current_datetime):
                continue

            # 判断当前日期是否在股票的买入日期列表中
            if current_date not in self.stock_buy_dates.get(stock, []):
                continue  # 今天不是这只股票的买入日，跳过

            status = self.portfolio_manager.get_stock_status(stock)
            # 检查是否已标记为次日买入
            if status.need_buy_next_day:
                continue

            # 检查订单状态
            if self.orders[stock] and self.orders[stock].status in [bt.Order.Submitted, bt.Order.Accepted]:
                continue

            data = self.stock_data[stock]
            current_price = data.close[0]

            # ========== 新增：检查是否接近涨停 ==========
            if self.portfolio_manager.limit_manager.is_near_limit_up(
                    stock, current_price, self.params.near_limit_up_threshold):
                if self.params.defer_on_near_limit_up:
                    # 类似涨停延期：将今日可用额度转为延期额度
                    available_normal_now = self.portfolio_manager.get_available_normal(current_datetime)
                    if available_normal_now <= 0:
                        logger.info(f"股票 {stock} 接近涨停，但当日无可用常规额度，无法预留延期")
                        continue
                    # 根据分配模式获取计划金额
                    if self.params.allocation_mode in ('equal', 'force_min'):
                        planned_amount = self.cash_per_stock
                    elif self.params.allocation_mode == 'dynamic':
                        planned_amount = self.dynamic_allocations.get(stock, 0.0)
                    else:
                        planned_amount = 0.0
                    amount_to_defer = min(planned_amount, available_normal_now)
                    if amount_to_defer <= 0:
                        continue

                    # 获取延期前的可用额度（用于判断是否再延期）
                    deferred_before = self.portfolio_manager.get_deferred_for_stock(stock, current_date_str)
                    success = self.portfolio_manager.handle_limit_up_deferral(
                        stock_code=stock,
                        defer_from_date=current_date_str,
                        amount=amount_to_defer,
                        valid_days=self.params.deferred_quota_valid_days
                    )
                    if success:
                        is_redeferred = deferred_before > 0  # 之前已有延期额度，则为再延期
                        logger.info(f"✅ 记录接近涨停延期额度: {stock}, 金额{amount_to_defer:.2f} from {current_date_str}")
                        self.deferred_create_log.append({
                            'date': current_date,
                            'datetime': current_datetime,
                            'stock': stock,
                            'amount': amount_to_defer,
                            'valid_days': self.params.deferred_quota_valid_days,
                            'expiry_date': None,
                            'reason': '接近涨停延期',
                            'is_redeferred': is_redeferred
                        })
                    else:
                        logger.warning(f"❌ 记录接近涨停延期额度失败: {stock}")
                else:
                    logger.info(f"股票 {stock} 接近涨停 ({current_price:.2f})，跳过买入")
                continue  # 无论延期与否，都不创建订单
            # ===========================================

            # 检查涨停
            if self.portfolio_manager.limit_manager.is_limit_up(stock, current_price):
                if self.params.skip_limit_up:
                    status.need_buy_next_day = False
                    self.log_trade("涨停跳过", stock, data.close[0], 0, "不标记次日买入")
                else:
                    # 获取当前剩余常规额度
                    available_normal_now = self.portfolio_manager.get_available_normal(current_datetime)
                    if available_normal_now <= 0:
                        logger.info(f"股票 {stock} 涨停，但当日无可用常规额度，无法预留延期")
                        continue
                    # 根据分配模式获取计划金额
                    if self.params.allocation_mode in ('equal', 'force_min'):
                        planned_amount = self.cash_per_stock
                    elif self.params.allocation_mode == 'dynamic':
                        planned_amount = self.dynamic_allocations.get(stock, 0.0)
                    else:
                        planned_amount = 0.0
                    amount_to_defer = min(planned_amount, available_normal_now)
                    if amount_to_defer <= 0:
                        continue

                    # 获取延期前的可用额度（用于判断是否再延期）
                    deferred_before = self.portfolio_manager.get_deferred_for_stock(stock, current_date_str)
                    # 调用 PortfolioManager 的方法处理涨停延期
                    success = self.portfolio_manager.handle_limit_up_deferral(
                        stock_code=stock,
                        defer_from_date=current_date_str,
                        amount=amount_to_defer,
                        valid_days=self.params.deferred_quota_valid_days
                    )
                    if success:
                        is_redeferred = deferred_before > 0  # 之前已有延期额度，则为再延期
                        logger.info(f"✅ 记录涨停延期额度: {stock}, 金额{amount_to_defer:.2f} from {current_date_str}")
                        # ===== 新增：记录延期额度创建事件 =====
                        self.deferred_create_log.append({
                            'date': current_date,
                            'datetime': current_datetime,
                            'stock': stock,
                            'amount': amount_to_defer,
                            'valid_days': self.params.deferred_quota_valid_days,
                            'expiry_date': None,  # 无法获取到期日，留空
                            'reason': '涨停延期',
                            'is_redeferred': is_redeferred
                        })
                        # handle_limit_up_deferral 内部应已设置 need_buy_next_day = True
                    else:
                        logger.warning(f"❌ 记录涨停延期额度失败: {stock}")
                continue

            # 获取技术指标（策略4必需）
            indicators = self._get_indicators(stock)

            should_buy, reason = self.portfolio_manager.should_buy(
                stock_code=stock,
                current_datetime=current_datetime,
                current_price=current_price,
                indicators=indicators
            )

            if should_buy:
                # ===== 根据分配模式获取分配给该股票的资金 =====
                if self.params.allocation_mode == 'equal':
                    allocated_cash = self.cash_per_stock
                    force_min = False
                elif self.params.allocation_mode == 'force_min':
                    allocated_cash = self.cash_per_stock
                    force_min = True
                elif self.params.allocation_mode == 'dynamic':
                    allocated_cash = self.dynamic_allocations.get(stock, 0.0)
                    if allocated_cash <= 0:
                        logger.debug(f"[DYNAMIC_SKIP] {stock} 分配金额为0，跳过买入")
                        continue
                    force_min = False  # 动态分配已考虑资金，无需强制一手
                else:
                    allocated_cash = self.cash_per_stock
                    force_min = False

                # 调用 PortfolioManager 的 get_buy_size 计算数量
                # 注意：需要 portfolio_manager.get_buy_size 支持 force_min 参数
                # 此处假设 portfolio_manager.get_buy_size 已增加 force_min 参数
                size, _ = self.portfolio_manager.get_buy_size(
                    price=current_price,
                    stock_code=stock,
                    allocated_cash=allocated_cash,
                    allow_supplementary=True,
                    is_deferred=False,
                    force_min=force_min  # 新增参数，需要修改 portfolio_manager.py
                )

                # 调用后日志
                logger.debug(f"[BUY_POST] {stock} | 分配资金={allocated_cash:.2f}, 计算得 size={size}")

                if size < 100:  # 最小交易单位
                    logger.debug(f"[BUY_SKIP] {stock} 数量不足100，跳过买入")
                    continue

                # 记录决策时间
                decision_time = current_datetime
                self.order_decision_time[stock] = decision_time

                # 创建订单 - 使用市价单以确保成交，价格设为0（市价单价格被忽略）
                order_info = {
                    'is_deferred': False,
                    'stock': stock,
                    'date_str': current_date_str
                }

                # 订单创建前日志
                logger.debug(f"[DEBUG_ORDER_INFO_CREATE_NORMAL] {stock} 创建订单时 order_info: {order_info}")

                order = self.buy(
                    data,
                    size=size,
                    price=0,  # 市价单价格无效
                    exectype=bt.Order.Market,
                    valid=bt.Order.DAY,
                    info=order_info
                )

                # 订单创建后日志
                logger.debug(f"[DEBUG_ORDER_CREATED_NORMAL] {stock} 订单已创建，order.info 类型: {type(order.info)}，内容: {order.info}")

                self.orders[stock] = order

                # 修改这里：不再立即设置creation_time，等待notify_order中获取
                self.order_creation_time[stock] = None  # 设置为None，等待notify_order更新

                # 记录当日已分配资金（用于日志，实际资金由成交后确定）
                cost = current_price * size  # 预计成本，仅供参考
                self._daily_allocated_cash += cost

                # 移除 has_ever_bought 设置

    def stop(self):
        """策略结束时的统计 - 最终版：先收盘处理，再调用各报告方法"""
        logger.info("=" * 50)
        logger.info("策略回测最终统计报告")
        logger.info("=" * 50)

        final_datetime = datetime.combine(self.last_trade_date, time(15, 0))

        # ----- 1. 执行收盘后处理（若最后一天未处理）-----
        try:
            if self.last_trade_date not in self._processed_close_dates:
                self._on_daily_close(final_datetime)  # 内部已调用 portfolio_manager.end_of_day_processing
                logger.info(f"📊 执行最终收盘处理，日期: {self.last_trade_date}")
        except Exception as e:
            logger.error(f"❌ 最终收盘处理失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

        # ----- 2. 依次输出各类最终报告 -----
        self._generate_comparison_report(final_datetime, is_final=True)
        self._generate_performance_summary(is_final=True)
        self._generate_capital_pool_summary(is_final=True)
        self._generate_return_report(final_datetime, is_final=True)

        if self.params.enable_time_analysis and self.time_analysis_log:
            self._generate_time_analysis_report()

        self._generate_capital_type_report()

        logger.info("=" * 50)

    def _generate_time_analysis_report(self):
        """生成时间分析报告

        1. 计算决策到创建、创建到执行的延迟统计
        2. 输出平均、最大、最小延迟
        """
        logger.info("=" * 50)
        logger.info("时间分析报告")
        logger.info("=" * 50)

        if not self.time_analysis_log:
            logger.info("无时间分析数据")
            return

        df_time_analysis = pd.DataFrame(self.time_analysis_log)

        # 计算平均延迟
        valid_delays = df_time_analysis['decision_to_creation_delay'].dropna()
        if len(valid_delays) > 0:
            avg_decision_creation_delay = valid_delays.mean()
            max_decision_creation_delay = valid_delays.max()
            min_decision_creation_delay = valid_delays.min()

            logger.info(f"决策到创建延迟统计:")
            logger.info(f"  平均: {avg_decision_creation_delay:.3f}秒")
            logger.info(f"  最大: {max_decision_creation_delay:.3f}秒")
            logger.info(f"  最小: {min_decision_creation_delay:.3f}秒")

        valid_execution_delays = df_time_analysis['creation_to_execution_delay'].dropna()
        if len(valid_execution_delays) > 0:
            avg_creation_execution_delay = valid_execution_delays.mean()
            max_creation_execution_delay = valid_execution_delays.max()
            min_creation_execution_delay = valid_execution_delays.min()

            logger.info(f"创建到执行延迟统计:")
            logger.info(f"  平均: {avg_creation_execution_delay:.3f}秒")
            logger.info(f"  最大: {max_creation_execution_delay:.3f}秒")
            logger.info(f"  最小: {min_creation_execution_delay:.3f}秒")

        valid_total_delays = df_time_analysis['total_decision_to_execution_delay'].dropna()
        if len(valid_total_delays) > 0:
            avg_total_delay = valid_total_delays.mean()
            max_total_delay = valid_total_delays.max()
            min_total_delay = valid_total_delays.min()

            logger.info(f"总决策到执行延迟统计:")
            logger.info(f"  平均: {avg_total_delay:.3f}秒")
            logger.info(f"  最大: {max_total_delay:.3f}秒")
            logger.info(f"  最小: {min_total_delay:.3f}秒")

    def _generate_capital_type_report(self):
        """生成资金类型使用报告"""
        logger.info("=" * 50)
        logger.info("资金类型使用报告")
        logger.info("=" * 50)

        if not self.trade_log:
            logger.info("无交易数据")
            return

        # 统计不同资金类型的交易
        deferred_trades = [trade for trade in self.trade_log if trade.get('is_deferred', False)]
        supplementary_trades = [trade for trade in self.trade_log if trade.get('supplementary_amount', 0) > 0]
        normal_trades = [trade for trade in self.trade_log if not trade.get('is_deferred', False)
                         and trade.get('supplementary_amount', 0) == 0]

        logger.info(f"总交易笔数: {len(self.trade_log)}")
        logger.info(f"使用延期额度交易笔数: {len(deferred_trades)}")
        logger.info(f"使用补充资金交易笔数: {len(supplementary_trades)}")
        logger.info(f"正常投资交易笔数: {len(normal_trades)}")

        # 统计不同资金类型的交易金额
        deferred_amount = sum(trade['price'] * trade['size'] for trade in deferred_trades
                              if trade['action'] == 'BUY')
        supplementary_amount = sum(trade['price'] * trade['size'] for trade in supplementary_trades
                                   if trade['action'] == 'BUY')
        normal_amount = sum(trade['price'] * trade['size'] for trade in normal_trades
                            if trade['action'] == 'BUY')

        logger.info(f"使用延期额度投资总额: {deferred_amount:.2f}")
        logger.info(f"使用补充资金投资总额: {supplementary_amount:.2f}")
        logger.info(f"正常投资总额: {normal_amount:.2f}")