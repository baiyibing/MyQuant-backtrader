# portfolio_manager.py
import pprint
import backtrader as bt
from datetime import datetime, date, timedelta, timezone
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from ProfitStrategy import StrategyFactory, ProfitStrategy
from StockStatus import StockStatus
from LimitUpDownManager import LimitUpDownManager
from TPlus1QueueManager import TPlus1QueueManager
from qmt_utils_adv import read_stock_codes, batch_format_stock_codes, get_stock_data_from_cache, to_datetime, is_close
import logging
import os
import psutil
import gc
import re
import numpy as np
from collections import deque
import copy
import pandas_market_calendars as mcal
import bisect  # 用于二分查找

from common.infra.timekeeping import shanghai_date_yyyymmdd

# 设置日志
logger = logging.getLogger(__name__)


# ==================== 优化后的投资组合管理器 ====================
class PortfolioManager:
    """
    投资组合管理器 - 统一资金流版本

    所有资金操作统一通过 GlobalCapitalManager 进行管理，不再维护独立的现金账户。
    资金验证采用基于权威流水的审计跟踪，确保资金流一致性。

    新增方法：
    - get_buy_size: 计算可买入数量和所需补充资金（混合方案）
    - handle_limit_up_deferral: 处理涨停延期，预留额度并设置 need_buy_next_day
    - 【优化】新增一系列资金操作封装方法，使策略完全通过本类访问资金池，解除直接依赖。
    - log_daily_status: 封装每日收盘资金日志，减少策略对资金池内部细节的了解。
    """

    def __init__(self,
                 start_date=None,
                 end_date=None,
                 strategy_version: str = 'version1',
                 strategy_params: Optional[Dict] = None,
                 # 新增参数
                 global_capital_manager=None,
                 use_preset_sell_adapter: Optional[bool] = None,
                 preset_adapter_price_mode: str = 'adjusted',
                 ):
        """
        初始化投资组合管理器

        参数:
        start_date (str, optional): 开始日期（格式YYYY-MM-DD）
        end_date (str, optional): 结束日期（格式YYYY-MM-DD）
        global_capital_manager (GlobalCapitalManager): 全局资金管理器实例（必须提供）
        """

        # ===== 严格检查全局资金管理器 =====
        if global_capital_manager is None:
            raise ValueError("❌ PortfolioManager初始化失败: global_capital_manager 必须提供")

        self.global_capital_manager = global_capital_manager

        # 资金回流回调函数列表
        self.reflow_callbacks = []
        self.portfolio_value = None
        # 初始化投资组合价值为全局资金管理器的每日可用资金
        try:
            # 从全局资金管理器获取初始可用资金（通常为每日限额）
            self.portfolio_value = self.global_capital_manager.daily_investment
            logger.info(f"✅ 从全局资金管理器获取初始可用资金: {self.portfolio_value:,.2f}")
        except AttributeError:
            # 如果全局资金管理器没有daily_investment属性，使用初始资本作为备选
            logger.warning(f"⚠️ 全局资金管理器无daily_investment，使用初始资本")

        # 集成优化后的管理器
        self.limit_manager = LimitUpDownManager()  # 涨跌停价格管理
        self.tplus1_manager = TPlus1QueueManager(start_date, end_date)  # T+1交易规则管理

        # 股票状态字典，key为股票代码，value为StockStatus实例
        self.stock_status = {}
        # 当前交易日期和时间
        self.current_date = None
        self.current_time = None
        # 今日买入和卖出的股票集合
        self.today_buy_stocks = set()
        self.today_sell_stocks = set()
        # 用于快速检查持仓状态的字典
        self.position_size = {}  # key: stock_code, value: 持仓数量

        # 记录未成交的卖出订单数量，用于T+1规则加强
        self.pending_sells = {}  # key: stock_code, value: 当前挂单卖出数量

        # 用于去重已处理的卖出订单
        self._processed_sell_ids = set()

        # ===== 核心重构：策略实例注入 =====
        from backtest.preset_strategy_adapter import (
            create_preset_strategy_adapter,
            resolve_use_preset_sell_adapter,
        )

        self.strategy_version = strategy_version
        self.use_preset_sell_adapter = resolve_use_preset_sell_adapter(use_preset_sell_adapter)
        try:
            if self.use_preset_sell_adapter:
                self.strategy: ProfitStrategy = create_preset_strategy_adapter(
                    strategy_version,
                    strategy_params,
                    price_mode=preset_adapter_price_mode,  # type: ignore[arg-type]
                )
                logger.info(
                    f"PortfolioManager加载 preset adapter: {strategy_version} | "
                    f"price_mode={preset_adapter_price_mode} | 参数: {strategy_params}"
                )
            else:
                self.strategy = StrategyFactory.create(
                    strategy_version,
                    custom_params=strategy_params,
                )
                logger.info(f"PortfolioManager加载策略: {strategy_version} | 参数: {strategy_params}")
        except Exception as e:
            logger.error(f"策略初始化失败: {e}，回退到version1")
            self.use_preset_sell_adapter = False
            self.strategy = StrategyFactory.create('version1')

        logger.info(
            f"✅ PortfolioManager初始化完成 | 初始资本(兼容性) | "
            f"实际可用资金: {self.portfolio_value:,.2f} | "
            f"全局资金管理器: {'已注入' if self.global_capital_manager else '未注入'}")

    # ===== 挂单卖出数量管理 =====
    def add_pending_sell(self, stock_code: str, size: int):
        """增加挂单卖出数量（应在创建卖出订单前调用）"""
        self.pending_sells[stock_code] = self.pending_sells.get(stock_code, 0) + size
        logger.debug(f"📌 增加挂单卖出: {stock_code} {size}股，当前挂单总数: {self.pending_sells[stock_code]}")

    def remove_pending_sell(self, stock_code: str, size: int):
        """
        减少挂单卖出数量（订单成交或取消时调用）
        增加防御性检查：若待移除数量大于当前记录，则按当前记录全量移除并记录警告
        """
        current = self.pending_sells.get(stock_code, 0)
        if current < size:
            logger.warning(f"⚠️ 挂单计数异常：{stock_code} 当前挂单 {current} 小于要移除的 {size}，将强制移除全部")
            size = current  # 只移除实际存在的数量

        new = current - size
        if new <= 0:
            if stock_code in self.pending_sells:
                del self.pending_sells[stock_code]
            logger.debug(f"📌 移除挂单卖出: {stock_code} {size}股，当前挂单总数: 0")
        else:
            self.pending_sells[stock_code] = new
            logger.debug(f"📌 移除挂单卖出: {stock_code} {size}股，当前挂单总数: {new}")

    def validate_cash_consistency(self, current_datetime, tolerance: float = 1.0) -> bool:
        """资金一致性审计验证。
        核心：核对全局资金流水与T+1交易记录是否完全匹配，不再进行简单的金额比较。

        参数:
            current_datetime: 当前日期时间，用于上下文。
            tolerance: 金额容差（元），默认为1.0（与全局资金管理器默认一致）。
        返回:
            bool: 审计是否通过。
        """
        if not hasattr(self, 'tplus1_manager') or not hasattr(self, 'global_capital_manager'):
            logger.warning("无法进行资金审计：缺少必要组件 (tplus1_manager 或 global_capital_manager)")
            return False  # 无法审计时返回False，由调用方决定是否中断

        try:
            # 调用全局资金管理器的权威审计方法
            is_consistent, audit_report = self.global_capital_manager.validate_with_authoritative_cash(
                tplus1_manager=self.tplus1_manager,
                current_datetime=current_datetime,
                tolerance=tolerance
            )

            if is_consistent:
                logger.debug(f"✅ 资金审计通过 | 日期: {self._normalize_date(current_datetime)}")
            else:
                # 审计失败，打印详细报告
                logger.error(f"❌ 资金审计失败！详情如下：\n{audit_report}")

            return is_consistent

        except Exception as e:
            logger.error(f"资金审计过程发生异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _normalize_date(self, dt) -> str:
        """统一日期格式：支持str/datetime/date -> 'YYYYMMDD'"""
        if isinstance(dt, str):
            # 优先处理YYYYMMDD格式
            if len(dt) == 8 and dt.isdigit():
                return dt
            # 处理YYYY-MM-DD
            elif '-' in dt:
                return dt.replace('-', '')
            # 其他格式，取前8位
            else:
                return dt[:8]
        elif isinstance(dt, (datetime, date)):
            return dt.strftime('%Y%m%d')
        else:
            # 尝试转换
            try:
                return pd.to_datetime(dt).strftime('%Y%m%d')
            except:
                logger.warning(f"无法解析日期: {dt}, 使用当前日期")
                return shanghai_date_yyyymmdd()

    def get_cash_flow_breakdown(self) -> Dict:
        """获取资金流明细与审计状态，用于调试和监控。"""
        try:
            # 获取T+1记录
            buy_records = self.tplus1_manager.get_all_buy_records()
            sell_records = self.tplus1_manager.get_all_sell_records()
            total_buy = sum(record['amount'] for record in buy_records)
            total_sell = sum(record['amount'] for record in sell_records)

            # 获取全局资金池状态
            if self.global_capital_manager:
                global_status = self.global_capital_manager.get_summary()
                global_remaining = self.global_capital_manager.get_total_cash()
                global_allocated = global_status['total_invested']
                # 获取权威流水统计
                ledger_count = global_status.get('transaction_ledger_count', 0)
            else:
                global_remaining = 0
                global_allocated = total_buy - total_sell
                ledger_count = 0

            # 尝试执行一次即时审计（仅用于本报告）
            audit_passed = False
            audit_detail = "未执行"
            if self.global_capital_manager and hasattr(self.global_capital_manager, 'validate_with_authoritative_cash'):
                try:
                    dummy_time = datetime.now(timezone.utc)
                    audit_passed, audit_detail = self.global_capital_manager.validate_with_authoritative_cash(
                        self.tplus1_manager, dummy_time, tolerance=1.0  # 统一容差为1.0
                    )
                    # 简化审计详情，只取第一行
                    audit_detail = audit_detail.split('\n')[0] if audit_detail else "N/A"
                except Exception as e:
                    audit_detail = f"审计异常: {e}"

            return {
                'total_buy_amount': total_buy,
                'total_sell_amount': total_sell,
                'net_cash_flow': total_sell - total_buy,
                'global_capital_remaining': global_remaining,
                'global_allocated_investment': global_allocated,
                'authoritative_ledger_count': ledger_count,  # 权威流水记录数
                'audit_status': audit_passed,  # 审计是否通过
                'audit_summary': audit_detail,  # 审计摘要
                'buy_count': len(buy_records),
                'sell_count': len(sell_records)
            }
        except Exception as e:
            logger.error(f"获取资金流明细失败: {e}")
            return {}

    def add_reflow_callback(self, callback_func):
        """添加资金回流回调函数"""
        self.reflow_callbacks.append(callback_func)
        logger.debug(f"添加资金回流回调函数，当前共有 {len(self.reflow_callbacks)} 个回调")

    # ========== 新增方法：获取常规可用现金 ==========
    def get_regular_cash(self) -> float:
        """
        获取常规可用现金（即主资金池中未被延期预留的部分）。
        该金额应与 broker 的现金余额一致。
        """
        if self.global_capital_manager is None:
            raise RuntimeError("❌ 无法获取常规现金：global_capital_manager 未设置")
        return self.global_capital_manager.available_regular_capital

    # ========== 修改 get_total_cash：直接调用全局资金管理器 ==========
    def get_total_cash(self) -> float:
        """
        获取总现金（常规可用现金 + 所有延期预留资金）。
        用于整体资产概览，如投资组合总价值计算。
        """
        if self.global_capital_manager is None:
            raise RuntimeError("❌ 无法获取总现金：global_capital_manager 未设置")
        return self.global_capital_manager.get_total_cash()

    # ========== 资金操作封装（委托给全局资金管理器）==========
    def record_commission(self, amount, operation_date, stock_code=None):
        """记录佣金"""
        return self.global_capital_manager.record_commission(amount, operation_date, stock_code)

    def release_expired_deferred(self, reference_date):
        """释放过期延期额度"""
        return self.global_capital_manager.release_expired_deferred(reference_date)

    def can_invest_today(self, current_date) -> bool:
        """今日是否可投资（常规额度）"""
        return self.global_capital_manager.can_invest_today(current_date)

    def get_available_normal(self, current_date) -> float:
        """获取今日常规可用投资额度（不含延期）"""
        return self.global_capital_manager.get_available_investment(current_date, include_deferred=False)

    def get_available_with_deferred(self, current_date) -> float:
        """获取今日总可用投资额度（含延期）"""
        return self.global_capital_manager.get_available_investment(current_date, include_deferred=True)

    def get_deferred_for_stock(self, stock_code, use_date) -> float:
        """获取指定股票今日可用延期额度"""
        return self.global_capital_manager.get_deferred_quota_for_stock(stock_code, use_date)

    def get_daily_investment(self, date_str) -> float:
        """获取指定日期已投资的常规金额"""
        # 注意：investment_records 是全局资金管理器的一个属性，需确保存在
        return self.global_capital_manager.investment_records.get(self._normalize_date(date_str), 0.0)

    def get_daily_reinvestment_status(self, date_str) -> dict:
        """获取指定日期的回流资金状态"""
        return self.global_capital_manager.get_daily_reinvestment_status(date_str)

    def get_deferred_quota_status(self, date_str=None) -> dict:
        """获取延期额度状态"""
        return self.global_capital_manager.get_deferred_quota_status(date_str)

    def get_supplementary_capital_status(self) -> dict:
        """获取补充资金状态"""
        return self.global_capital_manager.get_supplementary_capital_status()

    def get_summary(self) -> dict:
        """获取资金池摘要"""
        return self.global_capital_manager.get_summary()

    def get_initial_capital(self) -> float:
        """获取初始总资金"""
        return self.global_capital_manager.total_capital

    def get_daily_limit(self) -> float:
        """获取每日投资限额"""
        return self.global_capital_manager.daily_investment

    def get_stock_status(self, stock_code) -> StockStatus:
        """
        获取或创建股票状态对象

        参数:
        stock_code (str): 股票代码

        返回:
        StockStatus: 股票状态对象
        """
        if stock_code not in self.stock_status:
            self.stock_status[stock_code] = StockStatus(stock_code)
        return self.stock_status[stock_code]

    def get_all_stock_status(self) -> Dict[str, StockStatus]:
        return self.stock_status

    def update_market_data(self, current_datetime, stock_data_dict):
        """
        更新市场数据，包括涨跌停价格和股票状态

        参数:
        current_datetime (datetime): 当前时间
        stock_data_dict (dict): 股票市场数据字典，key为股票代码，value为包含股票数据的字典
        """
        current_date = current_datetime.date()
        current_time = current_datetime.time()
        # 如果日期发生变化，清空当日的买入和卖出集合
        if current_date != self.current_date:
            self.today_buy_stocks.clear()
            self.today_sell_stocks.clear()
            self.current_date = current_date

        self.current_time = current_time  # 保存当前时间
        # 遍历所有股票数据，更新状态
        for stock_code, data in stock_data_dict.items():
            status = self.get_stock_status(stock_code)
            # 更新当前价格和最高价
            status.current_price = data['close']
            status.current_high = data['high']

            # 更新计算指标
            # status.update_indicators(data['indicators'])

            # 更新涨跌停价格 - 使用安全的NaN检查
            if ('prev_close' in data and not pd.isna(data['prev_close'])
                    and data['prev_close'] > 0):
                limit_up, limit_down = self.limit_manager.update_limit_prices(
                    stock_code, data['prev_close']
                )
                status.limit_up_price = limit_up
                status.limit_down_price = limit_down

            # 只有在持有股票时才更新最高价。策略6：峰值从 T+1 起算，T+0 固定买入价。
            if status.cost_price > 0:
                if self.strategy_version == "version6" and int(status.hold_days or 0) < 1:
                    if status.holding_high <= 0:
                        status.holding_high = status.cost_price
                else:
                    status.update_high_price(current_date, current_time, data["high"])

    def can_trade_tplus1(self, stock_code, direction, current_datetime):
        """
        检查T+1交易规则下的交易能力

        参数:
        stock_code (str): 股票代码
        direction (str): 交易方向（'BUY'或'SELL'）
        current_datetime (str or datetime.date): 买入时间

        返回:
        bool: 是否可以交易
        """
        status = self.get_stock_status(stock_code)

        if direction == 'BUY':
            # 买入时检查是否已标记为今日买入或有买入订单
            return stock_code not in self.today_buy_stocks and not status.has_buy_order
        elif direction == 'SELL':
            # 增强检查：T+1规则 + 无卖出订单 + 实际可卖数量 > 挂单数量
            if not self.tplus1_manager.can_sell_today(stock_code, current_datetime):
                return False
            if status.has_sell_order:
                return False
            # 计算当前实际可卖数量
            sellable = self.tplus1_manager.get_sellable_quantity(stock_code, current_datetime)
            # 减去已挂单但未成交的卖出数量
            pending = self.pending_sells.get(stock_code, 0)
            return (sellable - pending) > 0

        return False

    # ==================== 资金分配计算方法（已增加 force_min 参数）====================
    def get_buy_size(self, price, stock_code=None, allocated_cash=None,
                     allow_supplementary=True, is_deferred=False, force_min=False):
        """
        基于分配的固定金额计算持仓数量（混合方案）

        参数:
            price: 当前价格
            stock_code: 股票代码（用于检查已有持仓，当前未使用，可留作扩展）
            allocated_cash: 分配给该股票的固定金额（元）
            allow_supplementary: 是否允许申请补充资金
            is_deferred: 是否为延期买入（True时直接使用 allocated_cash，不检查常规额度，也不允许补充资金）
            force_min: 当 allocated_cash 不足购买100股时，是否强制买入100股（仅在 is_deferred=False 时有效）

        返回:
            tuple: (可买入数量, 本次需要的补充资金金额)
        """
        logger.debug(f"[PortfolioManager.get_buy_size] {stock_code} | price={price:.2f} | allocated_cash={allocated_cash} | allow_supplementary={allow_supplementary} | is_deferred={is_deferred} | force_min={force_min}")

        if price <= 0:
            logger.debug(f"[PortfolioManager.get_buy_size] {stock_code} price<=0, return (0,0)")
            return 0, 0.0

        # 使用当前日期进行基本检查（如果当前日期未更新，则返回0）
        if self.current_date is None:
            logger.warning(f"[PortfolioManager.get_buy_size] current_date 未设置，无法计算")
            return 0, 0.0

        if allocated_cash is not None:
            if is_deferred:
                # 延期买入：不检查常规额度，直接使用 allocated_cash 计算
                price_cents = int(round(price * 100))
                allocated_cents = int(round(allocated_cash * 100))
                if price_cents <= 0:
                    logger.debug(f"[PortfolioManager.get_buy_size] {stock_code} 价格无效")
                    return 0, 0.0

                max_shares = allocated_cents // price_cents
                if max_shares < 100:
                    logger.debug(f"[PortfolioManager.get_buy_size] {stock_code} 延期买入，分配金额{allocated_cash:.2f}不足购买100股")
                    return 0, 0.0

                shares = (max_shares // 100) * 100
                cost = shares * price
                if cost > allocated_cash + 1e-6:
                    while shares >= 100 and shares * price > allocated_cash + 1e-6:
                        shares -= 100
                if shares < 100:
                    shares = 0
                logger.debug(f"[PortfolioManager.get_buy_size] {stock_code} 延期买入，可买{shares}股，成本{cost:.2f} ≤ 额度{allocated_cash:.2f}")
                return shares, 0.0

            # 正常买入或补充资金逻辑（非延期）
            # 检查今日是否可投资（仅常规买入需要检查）
            if not self.global_capital_manager.can_invest_today(self.current_date):
                logger.debug(f"[PortfolioManager.get_buy_size] {stock_code} 今日无常规投资额度")
                return 0, 0.0

            available_normal = self.global_capital_manager.get_available_investment(
                self.current_date, include_deferred=False
            )
            logger.debug(f"[PortfolioManager.get_buy_size] {stock_code} | available_normal={available_normal:.2f}")

            max_shares = int(allocated_cash / price)

            # ===== 处理 force_min 逻辑 =====
            if max_shares < 100:
                if force_min:
                    # 强制买入100股
                    shares = 100
                    cost = shares * price
                    if cost <= available_normal:
                        supplementary_needed = 0.0
                    else:
                        if not allow_supplementary:
                            logger.debug(f"[PortfolioManager.get_buy_size] {stock_code} 强制买入但补充资金不允许，放弃")
                            return 0, 0.0
                        supplementary_needed = cost - available_normal
                    logger.debug(f"[PortfolioManager.get_buy_size] {stock_code} 强制买入一手，成本{cost:.2f}，需要补充{supplementary_needed:.2f}")
                    return shares, supplementary_needed
                else:
                    logger.debug(f"[PortfolioManager.get_buy_size] {stock_code} 分配金额{allocated_cash:.2f}不足购买100股，放弃")
                    return 0, 0.0

            # 正常计算（max_shares >= 100）
            shares = (max_shares // 100) * 100
            cost = shares * price

            if cost <= available_normal:
                supplementary_needed = 0.0
                logger.debug(f"[PortfolioManager.get_buy_size] {stock_code} 常规可用足够，可买{shares}股，成本{cost:.2f}")
                return shares, supplementary_needed
            else:
                if not allow_supplementary:
                    logger.debug(f"[PortfolioManager.get_buy_size] {stock_code} 常规不足且不允许补充，放弃买入")
                    return 0, 0.0
                supplementary_needed = cost - available_normal
                logger.debug(f"[PortfolioManager.get_buy_size] {stock_code} 需要补充{supplementary_needed:.2f}，可买{shares}股")
                return shares, supplementary_needed
        else:
            # 原动态逻辑（allocated_cash为None时的回退，当前策略调用均传入 allocated_cash，此分支极少使用）
            logger.warning(f"[PortfolioManager.get_buy_size] {stock_code} allocated_cash 为 None，使用回退逻辑")
            available_cash = self.global_capital_manager.get_available_investment(self.current_date)
            if available_cash <= 100 * price:
                return 0, 0.0
            max_shares = int(available_cash / price)
            if max_shares < 100:
                return 0, 0.0
            shares = (max_shares // 100) * 100
            return shares, 0.0

    def handle_limit_up_deferral(self, stock_code, defer_from_date, amount, valid_days):
        """
        处理涨停延期额度预留，并设置 need_buy_next_day 标记

        参数:
            stock_code: 股票代码
            defer_from_date: 原定投资日期（字符串 YYYYMMDD）
            amount: 预留金额
            valid_days: 延期有效期（交易日）

        返回:
            bool: 是否成功预留
        """
        success, expiry_date = self.global_capital_manager.defer_quota(
            stock_code, defer_from_date, amount, valid_days
        )
        if success:
            status = self.get_stock_status(stock_code)
            status.need_buy_next_day = True
            logger.info(f"✅ 涨停延期额度预留成功: {stock_code} 金额{amount:.2f}，到期日 {expiry_date}")
        else:
            logger.warning(f"❌ 涨停延期额度预留失败: {stock_code}")
        return success

    # ==================== 新增：封装每日收盘资金日志 ====================
    def log_daily_status(self, current_date, supplementary_used_today):
        """
        输出每日收盘资金状态日志，封装对 GlobalCapitalManager 的调用细节。

        参数:
            current_date: 当前日期 (date 对象或字符串)
            supplementary_used_today: 当日使用的补充资金金额
        """
        date_str = self._normalize_date(current_date)
        daily_investment = self.get_daily_investment(date_str)
        available_capital = self.get_total_cash()

        logger.info(f"💰 {current_date}当日收盘统计:")
        logger.info(f"  - 全局资金池当日投资: {daily_investment:.2f}")
        logger.info(f"  - 全局资金池剩余总资金: {available_capital:.2f}")

        # 获取延期额度状态
        deferred_status = self.get_deferred_quota_status(date_str)
        logger.info(f"  - 当日可用延期额度: {deferred_status.get('usable_deferred_quota', 0):.2f}")
        logger.info(f"  - 当日已用延期额度: {deferred_status.get('used_deferred_quota', 0):.2f}")

        # 获取补充资金状态
        supplementary_status = self.get_supplementary_capital_status()
        logger.info(f"  - 补充资金累计使用: {supplementary_status.get('total_supplementary_used', 0):.2f}")
        logger.info(f"  - 当日使用补充资金: {supplementary_used_today:.2f}")

        reflow_status = self.get_daily_reinvestment_status(date_str)
        daily_inflow = reflow_status.get('daily_reflow_inflow', 0)
        daily_used = reflow_status.get('daily_reflow_used', 0)
        daily_available = reflow_status.get('daily_reflow_available', 0)
        utilization_rate = reflow_status.get('utilization_rate', 0)

        logger.info(f"💧 当日资金回流统计:")
        logger.info(f"    - 总回流金额: {daily_inflow:.2f}")
        logger.info(f"    - 已使用回流金额: {daily_used:.2f}")
        logger.info(f"    - 可用回流余额: {daily_available:.2f}")
        logger.info(f"    - 回流资金利用率: {utilization_rate:.1f}%")

    # ==================== 重构后的 execute_buy_order（动态补充资金版本）====================
    def execute_buy_order(self, stock_code, price, size, executed_time, is_deferred=False):
        """
        执行买入订单 - 动态补充资金版本

        根据实际成交价计算所需资金，动态划拨补充资金（若需要）。

        参数:
            stock_code: 股票代码
            price: 成交价格
            size: 成交数量
            executed_time: 成交时间
            is_deferred: 是否为延期买入

        返回:
            bool: 是否成功
        """
        cost = price * size

        logger.debug(f"[DEBUG_EXECUTE_BUY] {stock_code} 执行买入，is_deferred={is_deferred}, cost={cost:.2f}")

        # ===== 1. 资金检查 =====
        if is_deferred:
            # 延期买入：检查可用延期额度是否足够
            date_str = self._normalize_date(executed_time)
            deferred_available = self.global_capital_manager.get_deferred_quota_for_stock(stock_code, date_str)
            if deferred_available < cost - 0.01:
                logger.warning(f"{executed_time} {stock_code} 延期额度不足，需要{cost:.2f}，可用{deferred_available:.2f}")
                return False
            logger.debug(f"延期买入 {stock_code}，可用延期额度充足")
        else:
            # 非延期买入（常规或补充）：获取当前可用常规额度
            date_str = self._normalize_date(executed_time)
            available_normal = self.global_capital_manager.get_available_investment(date_str, include_deferred=False)

            # 计算所需补充资金
            if cost <= available_normal:
                supplementary_needed = 0.0
            else:
                supplementary_needed = cost - available_normal
                # 检查主资金池余额是否足够（常规可用 + 补充后不应超过总现金）
                total_cash = self.global_capital_manager.get_total_cash()
                if cost > total_cash:
                    logger.warning(f"[EXEC_FAIL] {stock_code} 总资金不足，需要{cost:.2f}，总现金{total_cash:.2f}")
                    return False

            logger.debug(f"常规可用={available_normal:.2f}, 需要补充={supplementary_needed:.2f}")

        # ===== 2. 检查涨跌停限制 =====
        if not self.limit_manager.can_trade_at_limit(stock_code, 'BUY', price):
            logger.warning(f"{executed_time} {stock_code} 涨停限制，无法买入")
            return False

        # ===== 3. 检查T+1限制 =====
        if not self.can_trade_tplus1(stock_code, 'BUY', executed_time):
            logger.warning(f"{executed_time} {stock_code} 违反T+1买入规则")
            return False

        # ===== 4. 先添加T+1记录，并保存record_id =====
        record_id = self.tplus1_manager.add_buy_record(stock_code, executed_time, size, price)

        # ===== 5. 记录到全局资金池（原子化处理）=====
        try:
            # 存储已成功记录的流水ID，用于可能的回滚
            success_ledger_ids = []

            if is_deferred:
                # 延期买入：先扣减延期额度，再记录投资
                success_use, used, used_details = self.global_capital_manager.use_deferred_quota(
                    stock_code, executed_time, cost
                )
                if not success_use or used < cost - 0.01:
                    if used > 0:
                        self.global_capital_manager.undo_deferred_quota(
                            stock_code, executed_time, used, used_details
                        )
                    raise Exception(f"扣减延期额度失败，请求{cost:.2f}，实际{used:.2f}")

                # 扣减成功，记录投资（延期投资）
                success_record, txn_id = self.global_capital_manager.record_investment(
                    amount=cost,
                    operation_date=executed_time,
                    use_reinvestment_pool=False,
                    is_deferred=True,
                    supplementary_amount=0.0,
                    stock_code=stock_code
                )
                if not success_record:
                    # 记录投资失败，回滚已扣减的延期额度
                    self.global_capital_manager.undo_deferred_quota(
                        stock_code, executed_time, cost, used_details
                    )
                    raise Exception("延期买入记录投资失败")
                success_ledger_ids.append(txn_id)
                logger.info(f"✅ 延期买入资金处理成功: {stock_code} 支出 {cost:.2f}，记录ID: {record_id}")

            else:
                # 常规买入或补充资金买入：传入动态计算的 supplementary_needed
                success_record, txn_id = self.global_capital_manager.record_investment(
                    amount=cost,
                    operation_date=executed_time,
                    use_reinvestment_pool=True,
                    is_deferred=False,
                    supplementary_amount=supplementary_needed,
                    stock_code=stock_code
                )
                if not success_record:
                    raise Exception("投资记录失败")
                success_ledger_ids.append(txn_id)
                logger.info(f"📝 买入资金记录成功: {stock_code} 支出 {cost:.2f} (补充 {supplementary_needed:.2f})，记录ID: {record_id}")

        except Exception as e:
            # 发生错误，回滚 T+1 记录
            self.tplus1_manager.undo_last_buy(stock_code, record_id=record_id)

            # 回滚已记录的投资流水（如果有）
            for txn_id in success_ledger_ids:
                self.global_capital_manager.undo_investment(txn_id)

            logger.error(f"❌ 买入失败，已回滚: {stock_code}，错误: {e}")
            return False

        # ===== 6. 更新股票状态（从T+1管理器获取最新持仓信息）=====
        status = self.get_stock_status(stock_code)
        new_position_info = self.tplus1_manager.get_position_info(stock_code)

        # 更新成本价（使用T+1管理器计算的平均成本）
        status.cost_price = new_position_info['avg_price']

        # 初始化最高价相关字段
        if price > status.holding_high:
            status.holding_high = price
            status.last_high_update_date = executed_time.date()
            status.last_high_update_time = executed_time

        status.hold_days = 0
        status.first_buy_date = executed_time.date()
        status.last_buy_date = executed_time.date()
        self.today_buy_stocks.add(stock_code)

        # 更新快速持仓字典
        self.position_size[stock_code] = new_position_info['total_quantity']

        logger.debug(
            f"{executed_time} 执行买入 {stock_code} {size}股 @ {price:.2f}, "
            f"总持仓: {self.position_size[stock_code]}股， 成本: {cost:.2f}"
        )

        # ===== 7. 买入后验证资金一致性 =====
        if not self.validate_cash_consistency(executed_time):
            logger.warning(f"⚠️ 买入操作后资金审计验证警告！股票: {stock_code}")
            cash_breakdown = self.get_cash_flow_breakdown()
            logger.debug(f"资金流明细: {cash_breakdown}")

        # 更新投资组合价值
        self.update_portfolio_value(executed_time)
        return True

    def process_sell_order_execution(self, stock_code, price, size, executed_time):
        """
        专用于卖出订单成交后的处理（不进行任何前置检查）

        参数:
            stock_code: 股票代码
            price: 成交价格
            size: 成交数量（实际成交的总股数）
            executed_time: 成交时间

        返回:
            bool: 总是返回 True（异常时内部处理）
        """
        # 1. 移除挂单数量（实际成交数量）
        self.remove_pending_sell(stock_code, size)

        # 2. 执行 T+1 卖出，获取实际从队列中卖出的数量
        actual_sold = self.tplus1_manager.execute_sell(stock_code, size, price, executed_time)

        # 3. 若实际卖出小于请求，进行强制修正
        if actual_sold < size:
            remaining = size - actual_sold
            logger.warning(f"T+1队列部分卖出: 请求{size}股，实际卖出{actual_sold}股，剩余{remaining}股强制修正")
            force_success = self.tplus1_manager.force_remove_position(stock_code, remaining, price, executed_time)
            if force_success:
                actual_sold += remaining  # 总卖出数量增加
                # 注意：强制修正内部已调用 add_sell_record，但资金回流统一由外部记录
            else:
                logger.error(f"强制修正持仓失败: {stock_code} {remaining}股")

        # 4. 获取卖出后的最新持仓信息
        new_position_info = self.tplus1_manager.get_position_info(stock_code)
        remaining_quantity = new_position_info['total_quantity']

        # 5. 更新持仓状态
        status = self.get_stock_status(stock_code)
        if remaining_quantity > 0:
            self.position_size[stock_code] = remaining_quantity
            status.cost_price = new_position_info['avg_price']
        else:
            status.reset_after_sell()
            self.position_size.pop(stock_code, None)

        # 6. 记录今日卖出（用于 T+1 买入检查）
        self.today_sell_stocks.add(stock_code)

        # 7. **统一记录资金回流（仅一次）**
        proceeds = actual_sold * price
        if self.global_capital_manager and actual_sold > 0:
            self.global_capital_manager.record_reflow(proceeds, executed_time, stock_code=stock_code)
            logger.info(f"💰 资金回流: {stock_code} 回流 {proceeds:.2f}")
        else:
            logger.warning(f"未设置 global_capital_manager 或卖出数量为0，无法记录资金回流")

        # 8. 更新投资组合价值
        self.update_portfolio_value(executed_time)

        return True

    def update_portfolio_value(self, executed_time):
        """
        优化投资组合价值计算：使用统一资金源

        关键：现金部分统一调用 get_total_cash() 获取总现金
        """
        # 计算股票价值
        stock_value = 0
        for stock_code in self.position_size:
            position_info = self.tplus1_manager.get_position_info(stock_code)
            status = self.stock_status[stock_code]
            if status.current_price > 0:  # 确保有有效价格
                stock_value += position_info['total_quantity'] * status.current_price

        # 使用 get_total_cash() 获取总现金（含预留）
        cash = self.get_total_cash()

        # 资金一致性检查已在 validate_cash_consistency 中处理，这里只记录状态
        self.portfolio_value = cash + stock_value

        logger.debug(
            f"更新投资组合价值: {executed_time} | "
            f"现金: {cash:.2f} | "
            f"股票价值: {stock_value:.2f} | "
            f"总价值: {self.portfolio_value:.2f}"
        )

        # 智能刷新：根据交易频率调整刷新策略
        self._should_force_refresh_stats(executed_time)

    def _should_force_refresh_stats(self, current_time):
        """判断是否需要强制刷新统计"""
        # 每日开盘后第一次刷新
        if not hasattr(self, '_last_stats_refresh_date'):
            self._last_stats_refresh_date = current_time.date()
            return True

        if current_time.date() != self._last_stats_refresh_date:
            self._last_stats_refresh_date = current_time.date()
            return True

        # 每30分钟强制刷新一次（数据一致性）
        if hasattr(self, '_last_force_refresh'):
            time_diff = current_time - self._last_force_refresh
            if time_diff.total_seconds() >= 1800:  # 30分钟
                self._last_force_refresh = current_time
                return True
        else:
            self._last_force_refresh = current_time

        return False

    def get_portfolio_status(self, current_datetime):
        """
        获取投资组合状态报告，包括现金、持仓股票信息等

        返回:
        dict: 投资组合状态报告
        """
        # 获取当前现金（总现金）
        current_cash = self.get_total_cash()
        logger.debug(f"投资组合状态报告{current_cash}")
        report = {
            'date': self.current_date,
            'cash': current_cash,  # 使用总现金
            'portfolio_value': self.portfolio_value,
            'positions': {},
            'today_buy_stocks': list(self.today_buy_stocks),
            'today_sell_stocks': list(self.today_sell_stocks),
            'limit_manager_status': {
                'tracked_stocks': list(self.limit_manager.limit_up_prices.keys())
            },
            'tplus1_manager_status': {
                'tracked_stocks': list(self.tplus1_manager.position_queues.keys())
            },
            # 资金一致性审计状态
            'cash_audit_status': {
                'audit_passed': self.validate_cash_consistency(current_datetime),
                'global_capital': self.global_capital_manager.get_total_cash() if self.global_capital_manager else 0,
                'transaction_ledger_count': self.global_capital_manager.get_summary().get('transaction_ledger_count',
                                                                                          0) if self.global_capital_manager else 0,
                'authoritative_cash': current_cash  # 现在两者应该相同
            } if hasattr(self, 'global_capital_manager') else {}
        }
        logger.debug(f"投资组合状态报告")
        # 修复：只遍历有持仓的股票
        for stock_code in self.position_size:
            status = self.stock_status[stock_code]
            position_info = self.tplus1_manager.get_position_info(stock_code)

            if position_info['total_quantity'] > 0:  # 双重检查
                current_value = position_info['total_quantity'] * status.current_price
                profit_pct = (status.current_price - position_info['avg_price']) / position_info['avg_price'] * 100

                report['positions'][stock_code] = {
                    'size': position_info['total_quantity'],
                    'cost_price': position_info['avg_price'],
                    'current_price': status.current_price,
                    'current_value': current_value,
                    'profit_pct': profit_pct,
                    'hold_days': status.hold_days,
                    'holding_high': status.holding_high,
                    'limit_up_price': status.limit_up_price,
                    'limit_down_price': status.limit_down_price,
                    'buy_dates': position_info['buy_dates'],
                    'last_high_update_date': status.last_high_update_date,
                    'last_high_update_time': status.last_high_update_time
                }

        return report

    def update_hold_days(self, current_date):
        """
        修正：基于交易日精确计算持仓天数 - 修复版本

        参数:
        current_date (str or datetime.date): 当前日期
        """
        # 修复：只遍历有持仓的股票
        for stock_code in list(self.position_size.keys()):
            if self.position_size[stock_code] > 0:
                status = self.stock_status[stock_code]
                try:
                    if status.first_buy_date is None:
                        logger.warning(f"{stock_code} first_buy_date 为 None，无法计算持仓天数")
                        status.hold_days = 0
                        continue

                    buy_date = to_datetime(status.first_buy_date).date()
                    current_date_dt = to_datetime(current_date).date()

                    if buy_date is not None and current_date_dt is not None:
                        # 使用交易日历精确计算
                        trading_days = self.tplus1_manager.market_calendar.valid_days(
                            start_date=buy_date,
                            end_date=current_date_dt
                        )

                        # 持仓天数 = 交易日数 - 1（买入当天不算持仓）
                        if len(trading_days) > 0:
                            if buy_date == current_date_dt:
                                status.hold_days = 0
                            else:
                                status.hold_days = max(0, len(trading_days) - 1)
                        else:
                            status.hold_days = 0

                except Exception as e:
                    logger.warning(f"计算{stock_code}持仓天数失败: {e}")
                    # 备选方案：使用自然日差
                    try:
                        natural_days = (current_date_dt - buy_date).days
                        status.hold_days = max(0, natural_days - 1)
                    except:
                        status.hold_days = 0
            else:
                # 如果没有持仓，确保持仓天数为0
                status = self.stock_status.get(stock_code)
                if status is not None and status.hold_days != 0:
                    status.hold_days = 0
            logger.debug(f"{stock_code}：持仓天数{status.hold_days}，持仓数量{self.position_size[stock_code]}")

    def validate_portfolio_consistency(self):
        """
        验证投资组合状态一致性 - 修复版本

        返回:
        bool: 是否一致
        """
        inconsistencies = []

        # 修复：同时检查position_size和T+1队列
        all_stocks = set(list(self.stock_status.keys()) + list(self.position_size.keys()))

        for stock_code in all_stocks:
            status = self.stock_status.get(stock_code)
            if status is None:
                continue

            position_info = self.tplus1_manager.get_position_info(stock_code)
            position_size_quantity = self.position_size.get(stock_code, 0)

            # 检查持仓数量一致性
            tplus1_quantity = position_info['total_quantity']

            if tplus1_quantity != position_size_quantity:
                inconsistencies.append(
                    f"{stock_code}: T+1数量={tplus1_quantity}, position_size={position_size_quantity}")

            # 检查成本价一致性
            if tplus1_quantity == 0 and status.cost_price > 0:
                inconsistencies.append(f"{stock_code}: 持仓为0但cost_price={status.cost_price}")

            # 检查持仓天数一致性
            if tplus1_quantity == 0 and status.hold_days > 0:
                inconsistencies.append(f"{stock_code}: 持仓为0但hold_days={status.hold_days}")

        if inconsistencies:
            logger.warning("投资组合状态不一致:")
            for issue in inconsistencies:
                logger.warning(f"  - {issue}")
        else:
            logger.debug("投资组合状态一致性检查通过")

        return len(inconsistencies) == 0

    def end_of_day_processing(self, current_datetime):
        """每日收盘处理"""
        # 刷新资金统计
        # 执行最终资金流逻辑验证（使用新的审计方法）
        is_consistent = self.validate_cash_consistency(current_datetime)
        if not is_consistent:
            logger.warning("⚠️ 每日处理：资金审计验证警告！")

        # 额外保险：清空挂单计数（所有未成交订单应在收盘前已被取消）
        self.pending_sells.clear()
        logger.debug(f"收盘后清空挂单计数 pending_sells")

        logger.info(
            f"每日处理完成: {current_datetime.date()}, 资金审计验证: {'通过' if is_consistent else '警告'}")

    def should_sell(
            self,
            stock_code: str,
            current_datetime: datetime,
            current_price: float,
            indicators: Optional[Dict] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        委托策略实例判断是否卖出

        :param stock_code: 股票代码
        :param current_datetime: 当前时间
        :param current_price: 当前价格
        :param indicators: 技术指标字典（策略4必需，格式: {'ma5': value, 'ma10': value}）
        :return: (是否卖出, 原因描述)
        """
        status = self.get_stock_status(stock_code)
        try:
            is_limit_up = self.limit_manager.is_limit_up(stock_code, current_price)
            is_limit_down = self.limit_manager.is_limit_down(stock_code, current_price)
            should_sell, reason = self.strategy.should_sell(
                status=status,
                current_datetime=current_datetime,
                current_price=current_price,
                is_limit_up=is_limit_up,
                is_limit_down=is_limit_down,
                indicators=indicators
            )

            if should_sell and reason:
                logger.debug(
                    f"[{stock_code}] 触发卖出 | 价格:{current_price:.2f} | "
                    f"成本:{status.cost_price:.2f} | 高点:{status.holding_high:.2f} | "
                    f"持仓:{status.hold_days}天 | 原因:{reason}"
                )
            return should_sell, reason

        except Exception as e:
            logger.error(f"[{stock_code}] 策略卖出判断异常: {e}", exc_info=True)
            return False, f"策略异常: {str(e)}"

    def should_buy(
            self,
            stock_code: str,
            current_datetime: datetime,
            current_price: float,
            indicators: Optional[Dict] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        委托策略实例判断是否买入（策略4等需技术指标的策略使用）

        :param stock_code: 股票代码
        :param current_datetime: 当前时间
        :param current_price: 当前价格
        :param indicators: 技术指标字典
        :return: (是否买入, 原因描述)
        """
        status = self.get_stock_status(stock_code)

        try:
            is_limit_up = self.limit_manager.is_limit_up(stock_code, current_price)
            is_limit_down = self.limit_manager.is_limit_down(stock_code, current_price)
            should_buy, reason = self.strategy.should_buy(
                status=status,
                current_datetime=current_datetime,
                current_price=current_price,
                is_limit_up=is_limit_up,
                is_limit_down=is_limit_down,
                indicators=indicators
            )

            if should_buy and reason:
                logger.debug(f"[{stock_code}] 触发买入 | 价格:{current_price:.2f} | 原因:{reason}")
            return should_buy, reason

        except Exception as e:
            logger.error(f"[{stock_code}] 策略买入判断异常: {e}", exc_info=True)
            return False, f"策略异常: {str(e)}"