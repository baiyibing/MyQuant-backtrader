# global_capital_manager.py
import logging
from datetime import datetime, date, timedelta

from common.infra.timekeeping import shanghai_date_yyyymmdd
from typing import Dict, Optional, List, Tuple, Any
import threading
import pandas as pd
from collections import defaultdict

logger = logging.getLogger(__name__)


class GlobalCapitalManager:
    """全局资金池管理器 - 支持跨交易日、跨回测周期的即时资金再投资

    实现跨交易日且跨回测周期的资金再投资。这意味着当日卖出的回流资金不仅要在同一回测周期（同一买入日期文件）的后续交易日中可用，还要能在后续其他回测周期（不同买入日期文件）中立即使用。

    核心特性：
    1. 涨停延期额度管理：支持因涨停未买入的资金延期使用，有有效期限制，按股票独立记录
    2. 最低购入补充资金：支持当平均分配金额不足100股时申请补充资金，资金从主资金池划拨，仅保留统计标记，补充资金不包含再每日常规限额内
    3. 订单失败回滚：提供 undo_deferred_quota 方法用于撤销已扣除的延期额度，补充资金回滚通过 undo_investment 统一处理
    4. 佣金记录：跟踪交易佣金，使资金池与 broker 现金保持一致
    5. 原子化投资记录：支持按来源拆分记录，并提供撤销方法
    """

    _instance = None
    _lock = threading.Lock()  # 类级别的锁，用于保护实例化过程

    def __new__(cls, total_capital: float = 21000000.0, daily_investment: float = 1000000.0, trading_days: List[str] = None):
        """单例模式实现"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GlobalCapitalManager, cls).__new__(cls)
                # 标记实例已创建，但__init__可能被多次调用
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, total_capital: float = 21000000.0, daily_investment: float = 1000000.0, trading_days: List[str] = None):
        """初始化（单例模式下只执行一次）

        参数:
            total_capital: 总资金
            daily_investment: 每日投资限额
            trading_days: 交易日列表（必须提供），格式如 ['20251023', '20251024', ...]
        """
        # 防止单例被重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return

        # 强制要求交易日列表（延期额度必须按交易日计算）
        if trading_days is None:
            raise ValueError("❌ GlobalCapitalManager 必须提供交易日列表 trading_days，延期额度无法使用自然日计算。")

        self._instance_lock = threading.RLock()  # 实例级别的锁，用于保护状态修改
        self.total_capital = total_capital
        self.daily_investment = daily_investment
        self.trading_days = trading_days          # 交易日列表，用于计算有效期
        self._audit_mode = 'light'                 # 审计模式：light（快速汇总）/strict（逐笔）
        self._reset_state()
        self._initialized = True
        logger.info(f"✅ 全局资金池初始化（单例）| 总资金: {total_capital:,.0f} | 日投额度: {daily_investment:,.0f} | 交易日历: {trading_days[0]} 至 {trading_days[-1]} (共{len(trading_days)}天) | 审计模式: {self._audit_mode}")

    def _reset_state(self):
        """重置内部状态"""
        with self._instance_lock:
            # 主资金池：常规可用现金（总资金 - 延期预留资金）
            self.available_regular_capital = self.total_capital

            self.investment_records: Dict[str, float] = {}  # 日期 -> 投资额（仅常规投资）
            self.max_investment_records: Dict[str, float] = {}  # 每日可最大投资额 日期 -> 投资额
            self.reflow_records: Dict[str, float] = {}  # 日期 -> 回流额
            self.last_operation_date: Optional[str] = None

            # 即时再投资资金跟踪：存储每个交易日通过卖出回流的资金总额（用于统计和优化）
            self._daily_reinvestment_inflow: Dict[str, float] = defaultdict(float)
            # 存储每个交易日已使用的再投资额度（从当日回流资金中使用的部分）
            self._daily_reinvestment_used: Dict[str, float] = defaultdict(float)
            # 注意：回流资金立即加入 available_regular_capital，此处仅作跟踪

            # 涨停延期额度管理（按股票独立记录 + 资金预留）
            # 延期额度记录结构：{股票代码: {到期日: 金额}}
            self._deferred_quota_records: Dict[str, Dict[str, float]] = defaultdict(dict)
            # 已使用的延期额度记录（按日期汇总）
            self._deferred_quota_used: Dict[str, float] = defaultdict(float)
            # 按到期日汇总的预留资金（用于快速计算可用延期总额和释放过期）
            self._deferred_reserved_by_date: Dict[str, float] = defaultdict(float)
            # 延期额度的默认有效期（交易日/自然日）
            self._deferred_quota_valid_days = 3

            # 补充资金使用记录（仅用于统计）
            self._supplementary_capital_used: Dict[str, float] = defaultdict(float)

            # 权威交易流水（用于审计），每条记录包含：日期、金额、类型、来源、股票代码（可选）、参考信息
            self._transaction_ledger: Dict[str, Dict] = {}
            self._next_transaction_id = 1

            # 累计佣金总额
            self.total_commission = 0.0

    def reset_for_new_sequence(self, reference_date: str = None):
        """外部显式重置（仅在全新回测序列开始时调用）"""
        self._reset_state()
        logger.info(f"🔄 资金池重置 | 参考日期: {reference_date or 'N/A'}")

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
            except Exception:
                logger.warning(f"无法解析日期: {dt}, 使用当前日期")
                return shanghai_date_yyyymmdd()

    def _calculate_expiry_date(self, from_date: str, valid_days: int) -> str:
        """计算到期日期（按交易日计算）

        参数:
            from_date: 起始日期（格式YYYYMMDD）
            valid_days: 有效期（交易日个数）

        返回:
            到期日（格式YYYYMMDD）
        """
        from_dt = datetime.strptime(from_date, '%Y%m%d')
        # 将交易日字符串转为date对象（假设trading_days已排序）
        trading_dates = [datetime.strptime(d, '%Y%m%d').date() for d in self.trading_days]
        from_date_obj = from_dt.date()
        # 找到from_date在交易日列表中的位置（第一个大于from_date的交易日）
        import bisect
        idx = bisect.bisect_right(trading_dates, from_date_obj)
        target_idx = idx + valid_days - 1  # 第valid_days个交易日
        if target_idx < len(trading_dates):
            expiry_date_obj = trading_dates[target_idx]
        else:
            # 超出列表范围，使用最后一个交易日作为到期日（避免回退自然日）
            expiry_date_obj = trading_dates[-1]
            logger.warning(f"交易日列表不足以计算{valid_days}天后的日期，使用最后一个交易日 {expiry_date_obj} 作为到期日")
        return expiry_date_obj.strftime('%Y%m%d')

    def _release_expired_deferred(self, reference_date: str) -> float:
        """释放所有已过期的延期预留资金回主资金池，并返回释放总额"""
        with self._instance_lock:
            ref_date_str = self._normalize_date(reference_date)
            release_total = 0.0
            # 找出所有过期的到期日
            expired_dates = [exp for exp in list(self._deferred_reserved_by_date.keys()) if exp < ref_date_str]
            for exp in expired_dates:
                amount = self._deferred_reserved_by_date.pop(exp, 0.0)
                if amount > 0:
                    self.available_regular_capital += amount
                    release_total += amount
                    logger.debug(f"释放过期延期额度: 到期日{exp}, 金额{amount:,.2f}")

            # 清理股票明细中过期的记录
            for stock_code in list(self._deferred_quota_records.keys()):
                expired = [exp for exp in list(self._deferred_quota_records[stock_code].keys()) if exp < ref_date_str]
                for exp in expired:
                    amount = self._deferred_quota_records[stock_code].pop(exp, 0.0)
                    if amount > 0:
                        logger.debug(f"清理股票 {stock_code} 过期延期额度: {exp} {amount:,.2f}")
                if not self._deferred_quota_records[stock_code]:
                    del self._deferred_quota_records[stock_code]

            if release_total > 0:
                # 将释放总额日志降为 DEBUG，减少常规运行输出
                logger.debug(f"💰 释放过期延期额度总计: {release_total:,.2f} 元，剩余常规可用现金: {self.available_regular_capital:,.2f}")
            return release_total

    def release_expired_deferred(self, reference_date) -> float:
        """公共方法：释放所有已过期的延期额度，返回释放总额"""
        date_str = self._normalize_date(reference_date)
        return self._release_expired_deferred(date_str)

    def validate_with_authoritative_cash(self, tplus1_manager, current_datetime,
                                         tolerance: float = 1.0) -> Tuple[bool, str]:
        """
        基于权威流水与T+1记录的审计验证。
        核对T+1管理器的每笔交易记录是否都在全局资金池中有对应且一致的资金操作。

        参数:
            tplus1_manager: TPlus1QueueManager实例，提供交易记录作为审计依据。
            current_datetime: 当前日期时间，用于日志。
            tolerance: 金额容差（元），默认为1.0。

        返回:
            (是否一致, 详细报告)
        """
        with self._instance_lock:
            # 先释放过期，确保状态最新
            self._release_expired_deferred(current_datetime)

            report_lines = []
            date_str = self._normalize_date(current_datetime)

            # 1. 获取T+1管理器的所有交易记录
            try:
                all_buy_records = tplus1_manager.get_all_buy_records()
                all_sell_records = tplus1_manager.get_all_sell_records()
            except AttributeError as e:
                error_msg = f"❌ 无法从tplus1_manager获取交易记录，请检查其接口。错误: {e}"
                logger.error(error_msg)
                return False, error_msg

            report_lines.append(f"🔍 【资金一致性审计报告】日期: {date_str}")
            report_lines.append(f"    T+1买入记录笔数: {len(all_buy_records)}")
            report_lines.append(f"    T+1卖出记录笔数: {len(all_sell_records)}")
            report_lines.append(f"    全局资金流水笔数: {len(self._transaction_ledger)}")

            # ===== 快速汇总核对（light模式） =====
            if self._audit_mode == 'light':
                # 按日期汇总T+1交易
                tplus1_by_date = defaultdict(lambda: {'invest': 0.0, 'reflow': 0.0, 'invest_count': 0, 'reflow_count': 0})
                for rec in all_buy_records:
                    d = self._normalize_date(rec['date'])
                    tplus1_by_date[d]['invest'] += rec['amount']
                    tplus1_by_date[d]['invest_count'] += 1
                for rec in all_sell_records:
                    d = self._normalize_date(rec['date'])
                    tplus1_by_date[d]['reflow'] += rec['amount']
                    tplus1_by_date[d]['reflow_count'] += 1

                # 按日期汇总全局流水（只考虑INVEST和REFLOW）
                ledger_by_date = defaultdict(lambda: {'invest': 0.0, 'reflow': 0.0, 'invest_count': 0, 'reflow_count': 0})
                for lid, entry in self._transaction_ledger.items():
                    if entry['type'] == 'INVEST':
                        d = entry['date']
                        ledger_by_date[d]['invest'] += abs(entry['amount'])
                        ledger_by_date[d]['invest_count'] += 1
                    elif entry['type'] == 'REFLOW':
                        d = entry['date']
                        ledger_by_date[d]['reflow'] += entry['amount']
                        ledger_by_date[d]['reflow_count'] += 1

                # 比较每个日期的净投资额（投资 - 回流）
                all_dates = set(tplus1_by_date.keys()) | set(ledger_by_date.keys())
                consistent = True
                for d in sorted(all_dates):
                    t_invest = tplus1_by_date[d]['invest']
                    t_reflow = tplus1_by_date[d]['reflow']
                    t_net = t_invest - t_reflow
                    l_invest = ledger_by_date[d]['invest']
                    l_reflow = ledger_by_date[d]['reflow']
                    l_net = l_invest - l_reflow
                    diff = abs(t_net - l_net)
                    if diff > tolerance:
                        consistent = False
                        report_lines.append(f"    ⚠️ 日期 {d} 净投资额不一致: T+1净={t_net:,.2f}, 流水净={l_net:,.2f}, 差额={diff:,.2f}")
                    # 可选检查记录数是否匹配
                    if tplus1_by_date[d]['invest_count'] != ledger_by_date[d]['invest_count']:
                        consistent = False
                        report_lines.append(f"    ⚠️ 日期 {d} 买入记录数不一致: T+1={tplus1_by_date[d]['invest_count']}, 流水={ledger_by_date[d]['invest_count']}")
                    if tplus1_by_date[d]['reflow_count'] != ledger_by_date[d]['reflow_count']:
                        consistent = False
                        report_lines.append(f"    ⚠️ 日期 {d} 卖出记录数不一致: T+1={tplus1_by_date[d]['reflow_count']}, 流水={ledger_by_date[d]['reflow_count']}")

                if consistent:
                    report_lines.append(f"\n✅ 快速汇总核对通过，所有日期净投资额一致，记录数匹配。")
                    # 仍需总资金平衡校验
                    total_invest_from_ledger = sum(ledger_by_date[d]['invest'] for d in ledger_by_date)
                    total_reflow_from_ledger = sum(ledger_by_date[d]['reflow'] for d in ledger_by_date)
                    net_invest_from_ledger = total_invest_from_ledger - total_reflow_from_ledger
                    total_reserved = sum(self._deferred_reserved_by_date.values())
                    capital_sum = self.available_regular_capital + net_invest_from_ledger + total_reserved + self.total_commission
                    capital_diff = abs(capital_sum - self.total_capital)
                    if capital_diff > tolerance:
                        report_lines.append(f"\n❌ 总资金不平衡：常规可用{self.available_regular_capital:,.2f} + 净投资{net_invest_from_ledger:,.2f} + 预留{total_reserved:,.2f} + 佣金{self.total_commission:,.2f} = {capital_sum:,.2f} ≠ 总资金{self.total_capital:,.2f}，差额{capital_diff:,.2f}")
                        return False, "\n".join(report_lines)
                    else:
                        report_lines.append(f"\n✅ 总资金平衡：常规可用{self.available_regular_capital:,.2f} + 净投资{net_invest_from_ledger:,.2f} + 预留{total_reserved:,.2f} + 佣金{self.total_commission:,.2f} = {capital_sum:,.2f} = 总资金{self.total_capital:,.2f}")
                        report_lines.append(f"\n✅ 资金一致性审计通过！")
                        logger.info(f"✅ 资金一致性审计通过（快速汇总） | 日期: {date_str}")
                        return True, "\n".join(report_lines)
                else:
                    report_lines.append(f"\n⚠️ 快速汇总核对发现不一致，降级为逐笔核对...")

            # ===== 原有逐笔核对逻辑（作为回退或 strict 模式） =====
            # 2. 准备待核对的交易列表 (格式: (日期, 金额, 类型, 股票代码, 原始记录))
            tplus1_entries_to_match = []
            for record in all_buy_records:
                tplus1_entries_to_match.append((
                    self._normalize_date(record['date']),
                    abs(record['amount']),  # 买入为资金流出，取正
                    'INVEST',
                    record.get('stock_code', 'N/A'),
                    record
                ))
            for record in all_sell_records:
                tplus1_entries_to_match.append((
                    self._normalize_date(record['date']),
                    abs(record['amount']),  # 卖出为资金流入，取正
                    'REFLOW',
                    record.get('stock_code', 'N/A'),
                    record
                ))

            # 3. 与全局资金流水进行逐笔核对（只匹配INVEST和REFLOW类型）
            matched_ledger_ids = set()
            unmatched_tplus1 = []

            for t_date, t_amount, t_type, t_stock, t_record in tplus1_entries_to_match:
                matched = False
                for ledger_id, ledger_entry in self._transaction_ledger.items():
                    if ledger_id in matched_ledger_ids:
                        continue
                    # 只考虑与T+1类型匹配的流水
                    if ledger_entry['type'] not in ['INVEST', 'REFLOW']:
                        continue
                    if ledger_entry['date'] == t_date and ledger_entry['type'] == t_type:
                        # 符号修正
                        ledger_amount = ledger_entry['amount']
                        if t_type == 'INVEST':
                            ledger_amount = -ledger_amount
                        if abs(ledger_amount - t_amount) <= tolerance:
                            # 如果流水中有股票代码，也进行匹配
                            ledger_stock = ledger_entry.get('stock_code', None)
                            if ledger_stock is not None and ledger_stock != t_stock:
                                continue  # 股票代码不匹配，跳过
                            # 找到匹配项
                            matched_ledger_ids.add(ledger_id)
                            matched = True
                            ref_info = f"(参考: {t_record.get('stock_code', 'N/A')})"
                            report_lines.append(
                                f"       ✅ 匹配: T+1 {t_type} {t_amount:,.2f} {ref_info} <-> 流水ID {ledger_id}")
                            break

                if not matched:
                    stock_info = f"股票 {t_record.get('stock_code', 'N/A')}"
                    unmatched_tplus1.append((t_date, t_type, t_amount, stock_info))
                    report_lines.append(f"       ❌ 未匹配: T+1 {t_date} {t_type} {t_amount:,.2f} {stock_info}")

            # 4. 检查全局流水中是否有未匹配的条目（跳过佣金等非核心流水）
            unmatched_ledger = []
            for ledger_id, ledger_entry in self._transaction_ledger.items():
                if ledger_id not in matched_ledger_ids:
                    # 跳过佣金记录，它们不与T+1交易直接匹配
                    if ledger_entry['type'] == 'COMMISSION':
                        continue
                    source_info = f"[来源: {ledger_entry.get('source', 'NORMAL')}]"
                    unmatched_ledger.append(
                        (ledger_entry['date'], ledger_entry['type'], ledger_entry['amount'], source_info))
                    report_lines.append(
                        f"       ⚠️  多余流水: {ledger_entry['date']} {ledger_entry['type']} {ledger_entry['amount']:,.2f} {source_info}")

            # 5. 计算并比对净投资额
            total_invest_from_ledger = sum(
                abs(e['amount']) for e in self._transaction_ledger.values() if e['type'] == 'INVEST')
            total_reflow_from_ledger = sum(
                e['amount'] for e in self._transaction_ledger.values() if e['type'] == 'REFLOW')
            net_invest_from_ledger = total_invest_from_ledger - total_reflow_from_ledger

            total_invest_from_tplus1 = sum(r['amount'] for r in all_buy_records)
            total_reflow_from_tplus1 = sum(r['amount'] for r in all_sell_records)
            net_invest_from_tplus1 = total_invest_from_tplus1 - total_reflow_from_tplus1

            report_lines.append("")
            report_lines.append("【金额汇总比对】")
            report_lines.append(
                f"    全局流水 - 总投资: {total_invest_from_ledger:,.2f}, 总回流: {total_reflow_from_ledger:,.2f}, 净投资: {net_invest_from_ledger:,.2f}")
            report_lines.append(
                f"    T+1记录 - 总投资: {total_invest_from_tplus1:,.2f}, 总回流: {total_reflow_from_tplus1:,.2f}, 净投资: {net_invest_from_tplus1:,.2f}")
            report_lines.append(f"    净投资差额: {abs(net_invest_from_ledger - net_invest_from_tplus1):,.2f}")

            # 6. 核心判断：所有T+1记录是否都匹配成功，且净投资额一致
            net_invest_diff = abs(net_invest_from_ledger - net_invest_from_tplus1)
            is_consistent = (len(unmatched_tplus1) == 0) and (net_invest_diff <= tolerance)

            # 7. 总资金平衡校验（常规可用现金 + 净投资 + 预留资金 + 累计佣金 = 总资金）
            total_reserved = sum(self._deferred_reserved_by_date.values())
            net_invest = net_invest_from_ledger
            capital_sum = self.available_regular_capital + net_invest + total_reserved + self.total_commission
            capital_diff = abs(capital_sum - self.total_capital)
            if capital_diff > tolerance:
                is_consistent = False
                report_lines.append(f"\n❌ 总资金不平衡：常规可用{self.available_regular_capital:,.2f} + 净投资{net_invest:,.2f} + 预留{total_reserved:,.2f} + 佣金{self.total_commission:,.2f} = {capital_sum:,.2f} ≠ 总资金{self.total_capital:,.2f}，差额{capital_diff:,.2f}")
            else:
                report_lines.append(f"\n✅ 总资金平衡：常规可用{self.available_regular_capital:,.2f} + 净投资{net_invest:,.2f} + 预留{total_reserved:,.2f} + 佣金{self.total_commission:,.2f} = {capital_sum:,.2f} = 总资金{self.total_capital:,.2f}")

            if not is_consistent:
                report_lines.append(f"\n❌ 资金一致性审计失败！")
                if len(unmatched_tplus1) > 0:
                    report_lines.append(f"    原因: 有 {len(unmatched_tplus1)} 笔T+1交易未在全局资金流水中找到匹配项。")
                if net_invest_diff > tolerance:
                    report_lines.append(f"    原因: 净投资额不一致，差额 {net_invest_diff:,.2f} 超过容差 {tolerance}。")
                logger.warning("\n".join(report_lines[-5:]))
                return False, "\n".join(report_lines)
            else:
                report_lines.append(f"\n✅ 资金一致性审计通过！")
                logger.info(f"✅ 资金一致性审计通过（逐笔） | 日期: {date_str} | T+1记录与全局流水完全匹配，总资金平衡。")
                return True, "\n".join(report_lines)

    def can_invest_today(self, current_date) -> bool:
        """检查今日是否可投资（改进版：基于实际可用额度判断）"""
        # 直接调用 get_available_investment 判断可用资金是否大于0
        # include_deferred=False 表示不考虑延期额度，因为那是未来的资金
        return self.get_available_investment(current_date, include_deferred=False) > 0

    def get_available_investment(self, current_date, include_deferred=False) -> float:
        """
        获取今日实际可投资金额（补充资金已合并到主资金池）
        """

        date_str = self._normalize_date(current_date)

        with self._instance_lock:
            # 先释放过期资金
            self._release_expired_deferred(date_str)

            # 计算当日已投资金额（仅常规投资）
            invested_today = self.investment_records.get(date_str, 0)

            # 基础可用资金 = 每日固定额度 与 常规可用现金 的较小值
            base_available = min(self.daily_investment - invested_today, self.available_regular_capital)

            total_available = base_available
            if include_deferred:
                # 获取当日可用的延期额度（从预留汇总中计算）
                deferred_available = sum(amt for exp, amt in self._deferred_reserved_by_date.items() if exp >= date_str)
                total_available += deferred_available

            # 可选优化：如果希望优先使用当日回流资金，可以在此处计算
            daily_reflow_available = self._daily_reinvestment_inflow.get(date_str,
                                                                         0) - self._daily_reinvestment_used.get(
                date_str, 0)
            if daily_reflow_available > 0:
                logger.debug(f"📈 日期 {date_str} 有当日回流资金可用: {daily_reflow_available:,.2f}")

            log_parts = [f"基础{base_available:,.2f}"]
            if include_deferred:
                log_parts.append(f"延期{deferred_available:,.2f}")

            log_str = f"📊 日期 {date_str} 可用资金: " + " + ".join(log_parts) + f" = {total_available:,.2f}"
            logger.info(log_str)

            return total_available

    def defer_quota(self, stock_code: str, defer_from_date: str, amount: float, valid_days: int = 3) -> Tuple[bool, Optional[str]]:
        """
        将指定股票的额度延期，立即从主资金池预留资金，指定有效期。

        参数:
            stock_code: 股票代码
            defer_from_date: 原定投资日期
            amount: 延期金额
            valid_days: 延期有效期（交易日个数）

        返回:
            (bool, expiry_date) 是否成功预留，以及到期日（成功时返回，失败返回 None）
        """
        if amount <= 0:
            return False, None

        defer_from_date_str = self._normalize_date(defer_from_date)

        with self._instance_lock:
            # 1. 检查常规可用现金是否足够
            if amount > self.available_regular_capital + 0.01:
                logger.warning(f"❌ 延期额度预留失败: 股票 {stock_code} 需 {amount:,.2f}，但常规可用现金仅剩 {self.available_regular_capital:,.2f}")
                return False, None

            # 2. 计算到期日期（按交易日）
            expiry_date = self._calculate_expiry_date(defer_from_date_str, valid_days)

            # 3. 从常规可用现金扣除
            self.available_regular_capital -= amount

            # 4. 记录到预留汇总
            self._deferred_reserved_by_date[expiry_date] += amount

            # 5. 记录到股票明细
            self._deferred_quota_records[stock_code][expiry_date] = \
                self._deferred_quota_records[stock_code].get(expiry_date, 0) + amount

            logger.info(
                f"✅ 延期额度预留: 股票 {stock_code} 金额 {amount:,.2f} from {defer_from_date_str} to {expiry_date} (有效期{valid_days}个交易日) | 剩余常规可用现金: {self.available_regular_capital:,.2f}")
            return True, expiry_date

    def _get_usable_deferred_quota(self, use_date: str) -> float:
        """
        获取指定日期可用的延期额度总额（所有股票汇总，考虑有效期）
        用于全局可用额度计算。
        """
        use_date_str = self._normalize_date(use_date)
        # 直接从预留汇总中计算，因为预留汇总已按到期日分类，且已使用部分会在 use_deferred_quota 中扣除
        total_usable = sum(amt for exp, amt in self._deferred_reserved_by_date.items() if exp >= use_date_str)
        return total_usable

    def get_deferred_quota_for_stock(self, stock_code: str, use_date: str) -> float:
        """
        获取指定股票在指定日期的可用延期额度（考虑有效期）
        """
        use_date_str = self._normalize_date(use_date)
        with self._instance_lock:
            # 先释放过期
            self._release_expired_deferred(use_date_str)

            expiry_records = self._deferred_quota_records.get(stock_code, {})
            total = 0.0
            for expiry_date, amount in expiry_records.items():
                if expiry_date >= use_date_str:
                    total += amount
            return total

    def use_deferred_quota(self, stock_code: str, use_date: str, amount: float) -> Tuple[bool, float, Optional[Dict]]:
        """
        使用指定股票的延期额度

        按到期日顺序（FIFO）扣减，并更新预留汇总。

        参数:
            stock_code: 股票代码
            use_date: 使用日期
            amount: 请求使用的金额

        返回:
            (是否成功, 实际使用金额, 使用明细字典)
            使用明细字典结构：{expiry_date: used_amount}，可用于撤销时恢复原到期日
        """
        use_date_str = self._normalize_date(use_date)

        with self._instance_lock:
            # 释放过期，确保可用额度准确
            self._release_expired_deferred(use_date_str)

            # 获取该股票的可用延期额度
            available = self.get_deferred_quota_for_stock(stock_code, use_date_str)

            if amount <= 0:
                return True, 0.0, {}

            if available <= 0:
                logger.warning(f"⚠️ 股票 {stock_code} 无可用延期额度: {use_date_str}")
                return False, 0.0, {}

            # 实际使用金额不能超过请求金额和可用额度
            actual_used = min(amount, available)

            # 按到期日顺序使用额度（FIFO）
            remaining_to_use = actual_used
            used_details = {}  # 记录每个到期日使用的金额
            used_details_list = []

            expiry_records = self._deferred_quota_records.get(stock_code, {})
            # 按到期日排序
            sorted_expiries = sorted(expiry_records.items())  # [(expiry, amount), ...]

            for expiry_date, record_amount in sorted_expiries:
                if remaining_to_use <= 0:
                    break

                if record_amount >= remaining_to_use:
                    # 当前记录足够
                    self._deferred_quota_records[stock_code][expiry_date] -= remaining_to_use
                    # 同时从预留汇总中扣减
                    self._deferred_reserved_by_date[expiry_date] -= remaining_to_use
                    used_details[expiry_date] = used_details.get(expiry_date, 0) + remaining_to_use
                    used_details_list.append(f"{expiry_date}:{remaining_to_use:,.2f}")
                    remaining_to_use = 0
                else:
                    # 当前记录不足
                    used_details[expiry_date] = used_details.get(expiry_date, 0) + record_amount
                    used_details_list.append(f"{expiry_date}:{record_amount:,.2f}")
                    remaining_to_use -= record_amount
                    # 从股票记录和预留汇总中移除该记录
                    self._deferred_reserved_by_date[expiry_date] -= record_amount
                    del self._deferred_quota_records[stock_code][expiry_date]

            # 清理空记录
            if not self._deferred_quota_records.get(stock_code):
                del self._deferred_quota_records[stock_code]

            # 记录全局已使用的延期额度（按日期）
            self._deferred_quota_used[use_date_str] += actual_used

            logger.info(f"✅ 使用延期额度: 股票 {stock_code} {actual_used:,.2f} at {use_date_str} | 详情: {'; '.join(used_details_list)}")
            return True, actual_used, used_details

    # ==================== 重构后的 record_investment（统一补充资金入口） ====================

    def record_investment(self, amount: float, operation_date,
                          use_reinvestment_pool: bool = True,
                          is_deferred: bool = False,
                          supplementary_amount: float = 0.0,
                          stock_code: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        记录投资操作，根据资金来源更新相应统计和资金池。

        参数:
            amount: 投资总金额
            operation_date: 操作日期
            use_reinvestment_pool: 是否优先使用当日回流资金（仅统计优化，不影响实际扣款）
            is_deferred: 是否使用延期额度（若为True，则假设额度已通过 use_deferred_quota 扣减，此处仅记录）
            supplementary_amount: 本次投资需要使用的补充资金金额（0表示无补充）
            stock_code: 关联的股票代码（用于审计匹配）

        返回:
            (bool, transaction_id) 是否成功记录，以及交易流水ID
        """
        date_str = self._normalize_date(operation_date)

        with self._instance_lock:
            # 参数有效性检查
            if amount <= 0:
                logger.error(f"❌ 投资失败: 金额必须大于0")
                return False, None

            if supplementary_amount < 0:
                logger.error(f"❌ 投资失败: supplementary_amount 不能为负数")
                return False, None

            if supplementary_amount > amount + 0.01:  # 允许微小浮点误差
                logger.error(f"❌ 投资失败: 补充金额 {supplementary_amount:,.2f} 超过总金额 {amount:,.2f}")
                return False, None

            regular_part = amount - supplementary_amount

            # ===== 延期投资处理 =====
            if is_deferred:
                # 延期投资：资金已在 use_deferred_quota 中从预留扣除，此处仅记录流水
                # 不检查常规额度，也不更新 investment_records
                pass

            else:
                # ===== 非延期投资（常规+补充） =====
                # 检查常规部分是否足够
                if regular_part > self.available_regular_capital + 0.01:
                    logger.error(f"❌ 投资失败: 常规部分 {regular_part:,.2f} > 常规可用现金 {self.available_regular_capital:,.2f}")
                    return False, None

                # 检查每日常规投资上限
                invested_today = self.investment_records.get(date_str, 0)
                if invested_today + regular_part > self.daily_investment + 0.01:
                    logger.warning(
                        f"⚠️ 投资失败: 日期 {date_str} 常规投资额 {invested_today + regular_part:,.2f} 将超过日限额 {self.daily_investment:,.2f}"
                    )
                    return False, None

                # 检查总金额是否超过可用现金（为安全）
                if amount > self.available_regular_capital + 0.01:
                    logger.error(f"❌ 投资失败: 总金额 {amount:,.2f} > 常规可用现金 {self.available_regular_capital:,.2f}")
                    return False, None

                # 扣除常规部分
                if regular_part > 0:
                    self.available_regular_capital -= regular_part
                    # 更新常规投资记录
                    self.investment_records[date_str] = self.investment_records.get(date_str, 0) + regular_part

                # 扣除补充部分（修正：补充资金也必须从主资金池扣除）
                if supplementary_amount > 0:
                    self.available_regular_capital -= supplementary_amount
                    # 更新补充资金统计
                    self._supplementary_capital_used[date_str] += supplementary_amount

            # ===== 资金分配策略（统计优化，不影响实际扣款） =====
            allocation = self._allocate_investment_funds(date_str, amount, use_reinvestment_pool)

            # ===== 记录权威交易流水 =====
            if is_deferred:
                source_type = 'DEFERRED'
            else:
                source_type = 'SUPPLEMENTARY' if supplementary_amount > 0 else 'NORMAL'

            transaction_id = f"INV_{self._next_transaction_id}"
            self._next_transaction_id += 1
            self._transaction_ledger[transaction_id] = {
                'date': date_str,
                'amount': -amount,
                'type': 'INVEST',
                'source': source_type,
                'stock_code': stock_code,
                'ref_info': f"记录于 record_investment (supplementary={supplementary_amount:.2f})"
            }

            self.last_operation_date = date_str

            # 构建资金来源描述
            source_desc = []
            if is_deferred:
                source_desc.append("延期额度")
            else:
                if supplementary_amount > 0:
                    source_desc.append(f"补充资金({supplementary_amount:.2f})")
                if regular_part > 0:
                    source_desc.append(f"常规投资({regular_part:.2f})")
                if not source_desc:  # 理论上不会发生
                    source_desc.append("正常投资")

            source_str = "+".join(source_desc)

            logger.info(
                f"🟢 投资记录 | 日期: {date_str} | "
                f"总金额: {amount:,.2f} | "
                f"来源: {source_str} | "
                f"股票: {stock_code or 'N/A'} | "
                f"本日累计常规投资: {self.investment_records.get(date_str, 0):,.2f} | "
                f"优化来源: 当日回流{allocation['from_daily_reflow']:,.2f}, "
                f"常规可用现金{allocation['from_main_pool']:,.2f} | "
                f"剩余常规可用现金: {self.available_regular_capital:,.2f}"
            )

            return True, transaction_id

    def undo_investment(self, transaction_id: str) -> bool:
        """
        撤销一笔投资记录（通过添加反向流水并恢复资金）
        参数:
            transaction_id: 要撤销的交易流水ID
        返回:
            bool: 是否成功撤销
        """
        with self._instance_lock:
            if transaction_id not in self._transaction_ledger:
                logger.error(f"撤销投资失败：未找到交易流水 {transaction_id}")
                return False

            entry = self._transaction_ledger[transaction_id]
            if entry['type'] != 'INVEST':
                logger.error(f"撤销投资失败：流水 {transaction_id} 不是投资记录")
                return False

            date_str = entry['date']
            amount = -entry['amount']  # 原支出为负，转为正数表示返还金额
            source = entry.get('source', 'NORMAL')
            stock_code = entry.get('stock_code')

            # 恢复资金
            if source == 'NORMAL':
                # 常规投资：返还常规可用现金，并冲销投资记录
                self.available_regular_capital += amount
                # 从 investment_records 中扣除
                if date_str in self.investment_records:
                    self.investment_records[date_str] -= amount
                    if self.investment_records[date_str] <= 0:
                        del self.investment_records[date_str]
            elif source == 'SUPPLEMENTARY':
                # 补充资金：返还常规可用现金，并冲销补充使用记录
                self.available_regular_capital += amount
                if date_str in self._supplementary_capital_used:
                    self._supplementary_capital_used[date_str] -= amount
                    if self._supplementary_capital_used[date_str] <= 0:
                        del self._supplementary_capital_used[date_str]
            elif source == 'DEFERRED':
                # 延期额度：这里不操作 available_regular_capital，而是恢复延期预留
                # 由于延期额度的扣减在 use_deferred_quota 中完成，撤销时需恢复预留
                # 但 undo_investment 仅用于撤销 record_investment 本身，不涉及延期额度的恢复
                # 延期额度的恢复应由专门的 undo_deferred_quota 处理
                logger.warning(f"撤销延期投资 {transaction_id}，但延期额度恢复需单独调用 undo_deferred_quota")
                # 我们仍然添加反向流水，但不调整资金池
                pass
            else:
                logger.error(f"未知资金来源 {source}，无法撤销")
                return False

            # 标记原流水为已撤销（通过添加反向流水）
            undo_id = f"UNDO_{transaction_id}"
            self._transaction_ledger[undo_id] = {
                'date': date_str,
                'amount': amount,  # 正数表示返还
                'type': 'INVEST_CANCEL',
                'source': source,
                'stock_code': stock_code,
                'ref_info': f"撤销投资 {transaction_id}"
            }
            logger.info(f"🔄 撤销投资成功: {transaction_id}, 返还金额 {amount:,.2f}")
            return True

    def _allocate_investment_funds(self, date_str: str, amount: float, use_reinvestment_pool: bool) -> Dict[str, float]:
        """智能分配投资资金来源（仅作统计和优化，不影响实际资金流）

        返回: {'from_daily_reflow': X, 'from_main_pool': Y}
        """
        allocation = {'from_daily_reflow': 0.0, 'from_main_pool': amount}

        if use_reinvestment_pool:
            # 计算当日回流资金的可用余额
            daily_inflow = self._daily_reinvestment_inflow.get(date_str, 0)
            daily_used = self._daily_reinvestment_used.get(date_str, 0)
            daily_available = max(0, daily_inflow - daily_used)

            # 优先使用当日回流资金（统计意义上）
            from_daily_reflow = min(amount, daily_available)
            allocation['from_daily_reflow'] = from_daily_reflow
            allocation['from_main_pool'] = amount - from_daily_reflow

            # 更新当日已使用回流资金统计
            if from_daily_reflow > 0:
                self._daily_reinvestment_used[date_str] += from_daily_reflow
                logger.debug(f"💰 优化使用当日回流资金: {from_daily_reflow:,.2f}")

        return allocation

    def record_reflow(self, amount: float, operation_date, stock_code: Optional[str] = None) -> bool:
        """记录资金回流（线程安全）

        回流资金立即加入 available_regular_capital，实现跨周期即时可用
        同时记录到当日回流统计，用于优化当日资金周转

        参数:
            amount: 回流金额
            operation_date: 操作日期
            stock_code: 关联的股票代码（用于审计匹配）
        """
        date_str = self._normalize_date(operation_date)

        with self._instance_lock:
            # 1. 记录回流总额（历史统计）
            self.reflow_records[date_str] = self.reflow_records.get(date_str, 0) + amount

            # 2. 立即将回流资金加入常规可用现金（实现跨周期可用）
            self.available_regular_capital += amount

            # 3. 记录到当日回流统计（用于优化当日资金周转）
            self._daily_reinvestment_inflow[date_str] += amount

            # 记录权威交易流水
            transaction_id = f"REF_{self._next_transaction_id}"
            self._next_transaction_id += 1
            self._transaction_ledger[transaction_id] = {
                'date': date_str,
                'amount': amount,
                'type': 'REFLOW',
                'source': 'NORMAL',
                'stock_code': stock_code,
                'ref_info': f"记录于 record_reflow"
            }

            self.last_operation_date = date_str

            # 增强日志：包含更多上下文信息
            available = self.get_available_investment(date_str)
            logger.info(
                f"🟠 资金回流 | 日期: {date_str} | "
                f"金额: {amount:,.2f} | "
                f"常规可用现金: {self.available_regular_capital:,.2f} | "
                f"当日可用: {available:,.2f} | "
                f"当日累计回流: {self._daily_reinvestment_inflow[date_str]:,.2f} | "
                f"股票: {stock_code or 'N/A'}"
            )

            return True

    def record_commission(self, amount: float, operation_date, stock_code: Optional[str] = None) -> bool:
        """记录交易佣金（从主资金池扣除）

        参数:
            amount: 佣金金额（正数）
            operation_date: 交易日期
            stock_code: 关联的股票代码（用于审计）
        返回:
            bool: 是否成功扣除
        """
        if amount <= 0:
            return False

        date_str = self._normalize_date(operation_date)

        with self._instance_lock:
            # 检查常规可用现金是否足够
            if amount > self.available_regular_capital + 0.01:
                logger.error(f"❌ 佣金扣除失败: 金额 {amount:,.2f} > 常规可用现金 {self.available_regular_capital:,.2f}")
                return False

            # 从常规可用现金扣除
            self.available_regular_capital -= amount
            self.total_commission += amount

            # 记录权威交易流水
            transaction_id = f"COM_{self._next_transaction_id}"
            self._next_transaction_id += 1
            self._transaction_ledger[transaction_id] = {
                'date': date_str,
                'amount': -amount,  # 负值表示支出
                'type': 'COMMISSION',
                'source': 'NORMAL',
                'stock_code': stock_code,
                'ref_info': f"记录于 record_commission"
            }

            self.last_operation_date = date_str

            logger.info(
                f"💸 佣金记录 | 日期: {date_str} | 金额: {amount:,.2f} | 累计佣金: {self.total_commission:,.2f} | 剩余常规可用现金: {self.available_regular_capital:,.2f} | 股票: {stock_code or 'N/A'}"
            )

            return True

    def get_daily_reinvestment_status(self, date_str: str) -> Dict[str, float]:
        """获取指定日期的再投资资金状态（统计信息）"""
        date_str = self._normalize_date(date_str)

        with self._instance_lock:
            daily_inflow = self._daily_reinvestment_inflow.get(date_str, 0)
            daily_used = self._daily_reinvestment_used.get(date_str, 0)

            return {
                'date': date_str,
                'daily_reflow_inflow': daily_inflow,
                'daily_reflow_used': daily_used,
                'daily_reflow_available': max(0, daily_inflow - daily_used),
                'utilization_rate': (daily_used / daily_inflow * 100) if daily_inflow > 0 else 0
            }

    def get_deferred_quota_status(self, date_str: str = None) -> Dict[str, any]:
        """获取延期额度状态"""
        date_str_normalized = self._normalize_date(date_str) if date_str else None

        with self._instance_lock:
            if date_str_normalized:
                # 获取指定日期的延期额度（全局汇总）
                usable_quota = self._get_usable_deferred_quota(date_str_normalized)
                used_quota = self._deferred_quota_used.get(date_str_normalized, 0)

                return {
                    'date': date_str_normalized,
                    'usable_deferred_quota': usable_quota,
                    'used_deferred_quota': used_quota,
                    'total_available': usable_quota + used_quota
                }
            else:
                # 获取所有延期额度（按股票汇总）
                total_usable = 0
                quota_details = []

                for stock_code, expiry_records in self._deferred_quota_records.items():
                    for expiry_date, amount in expiry_records.items():
                        total_usable += amount
                        quota_details.append({
                            'stock': stock_code,
                            'expiry_date': expiry_date,
                            'amount': amount
                        })

                total_used = sum(self._deferred_quota_used.values())

                return {
                    'total_usable_deferred_quota': total_usable,
                    'total_used_deferred_quota': total_used,
                    'quota_details': quota_details
                }

    def get_supplementary_capital_status(self) -> Dict[str, any]:
        """获取补充资金状态（仅统计已使用金额）"""
        with self._instance_lock:
            total_used = sum(self._supplementary_capital_used.values())
            return {
                'total_supplementary_used': total_used,
                'supplementary_used_by_date': dict(self._supplementary_capital_used)
            }

    # ========== 回滚方法（用于订单失败时撤销已扣除的资金） ==========

    def undo_deferred_quota(self, stock_code: str, date_str: str, amount: float, used_details: Optional[Dict] = None) -> bool:
        """
        撤销一笔延期额度投资（订单失败时调用）

        恢复预留额度，添加反向流水。如果提供了 used_details，则按原到期日恢复；否则按默认有效期重新计算。

        参数:
            stock_code: 股票代码
            date_str: 原使用日期
            amount: 撤销金额
            used_details: 使用明细字典，格式 {expiry_date: amount}，由 use_deferred_quota 返回

        返回:
            bool: 是否成功
        """
        date_str = self._normalize_date(date_str)
        with self._instance_lock:
            # 从已使用延期额度统计中减去
            if date_str in self._deferred_quota_used:
                self._deferred_quota_used[date_str] -= amount
                if self._deferred_quota_used[date_str] <= 0:
                    del self._deferred_quota_used[date_str]

            if used_details:
                # 按原到期日恢复
                for expiry_date, amt in used_details.items():
                    # 添加到股票记录
                    stock_records = self._deferred_quota_records.setdefault(stock_code, {})
                    stock_records[expiry_date] = stock_records.get(expiry_date, 0) + amt
                    # 添加到预留汇总
                    self._deferred_reserved_by_date[expiry_date] += amt
                logger.info(f"🔄 撤销延期额度投资: 股票{stock_code} 日期{date_str} 金额{amount:,.2f}，按原到期日恢复")
            else:
                # 未提供明细，按默认有效期重新计算（按交易日）
                new_expiry = self._calculate_expiry_date(date_str, self._deferred_quota_valid_days)
                # 添加到股票记录
                stock_records = self._deferred_quota_records.setdefault(stock_code, {})
                stock_records[new_expiry] = stock_records.get(new_expiry, 0) + amount
                # 添加到预留汇总
                self._deferred_reserved_by_date[new_expiry] += amount
                logger.info(f"🔄 撤销延期额度投资: 股票{stock_code} 日期{date_str} 金额{amount:,.2f}，重新计算到期日 {new_expiry}")

            # 添加反向流水
            transaction_id = f"UNDO_DEF_{self._next_transaction_id}"
            self._next_transaction_id += 1
            self._transaction_ledger[transaction_id] = {
                'date': date_str,
                'amount': amount,  # 正数，抵消原投资负额
                'type': 'INVEST_CANCEL',
                'source': 'DEFERRED',
                'stock_code': stock_code,
                'ref_info': f"撤销延期额度投资"
            }

            return True

    # ========== 新增方法：获取总现金 ==========
    def get_total_cash(self) -> float:
        """返回总现金 = 常规可用现金 + 所有延期预留资金"""
        with self._instance_lock:
            total_reserved = sum(self._deferred_reserved_by_date.values())
            return self.available_regular_capital + total_reserved

    def get_summary(self) -> dict:
        """获取资金池摘要"""
        with self._instance_lock:
            # 从流水中统计总投资（所有 INVEST 类型，取绝对值）
            total_invest_from_ledger = sum(
                abs(e['amount']) for e in self._transaction_ledger.values() if e['type'] == 'INVEST')
            total_reflow = sum(self.reflow_records.values())
            total_reserved = sum(self._deferred_reserved_by_date.values())

            # 计算当日回流资金使用效率
            total_daily_inflow = sum(self._daily_reinvestment_inflow.values())
            total_daily_used = sum(self._daily_reinvestment_used.values())

            # 计算有回流资金的交易日中，再投资利用率
            days_with_reflow = [date for date, inflow in self._daily_reinvestment_inflow.items() if inflow > 0]
            utilized_days = 0
            for date in days_with_reflow:
                used = self._daily_reinvestment_used.get(date, 0)
                if used > 0:
                    utilized_days += 1

            # 获取延期额度状态
            deferred_status = self.get_deferred_quota_status()
            # 获取补充资金状态
            supplementary_status = self.get_supplementary_capital_status()

            return {
                "total_capital": self.total_capital,
                "available_regular_capital": self.available_regular_capital,
                "total_invested": total_invest_from_ledger,  # 使用流水统计，包含所有来源
                "total_reflow": total_reflow,
                "net_invested": total_invest_from_ledger - total_reflow,
                "investment_days": len(self.investment_records),
                "last_operation_date": self.last_operation_date,
                "utilization_ratio": (total_invest_from_ledger / self.total_capital * 100) if self.total_capital > 0 else 0,
                "total_daily_reflow": total_daily_inflow,
                "total_daily_reflow_used": total_daily_used,
                "daily_reflow_utilization": (
                        total_daily_used / total_daily_inflow * 100) if total_daily_inflow > 0 else 0,
                "cross_cycle_available": self.available_regular_capital,
                "days_with_reflow": len(days_with_reflow),
                "days_reflow_utilized": utilized_days,
                "reflow_utilization_rate": (utilized_days / len(days_with_reflow) * 100) if days_with_reflow else 0,
                "total_usable_deferred_quota": deferred_status.get('total_usable_deferred_quota', 0),
                "total_used_deferred_quota": deferred_status.get('total_used_deferred_quota', 0),
                "total_reserved_deferred": total_reserved,
                "total_supplementary_used": supplementary_status['total_supplementary_used'],
                "supplementary_used_by_date": supplementary_status['supplementary_used_by_date'],
                "transaction_ledger_count": len(self._transaction_ledger),
                "is_singleton": True,
                "instance_id": id(self),
                "total_commission": self.total_commission,
            }

    def __repr__(self):
        summary = self.get_summary()
        return (f"GlobalCapitalManager(总资金: {summary['total_capital']:,.0f} | "
                f"常规可用: {summary['available_regular_capital']:,.0f} | "
                f"已投: {summary['total_invested']:,.0f} | "
                f"回流: {summary['total_reflow']:,.0f} | "
                f"延期额度可用: {summary['total_usable_deferred_quota']:,.0f} | "
                f"延期预留: {summary.get('total_reserved_deferred', 0):,.0f} | "
                f"补充资金已用: {summary['total_supplementary_used']:,.0f} | "
                f"累计佣金: {summary['total_commission']:,.2f} | "
                f"流水记录数: {summary['transaction_ledger_count']} | "
                f"利用率: {summary['utilization_ratio']:.1f}%)")