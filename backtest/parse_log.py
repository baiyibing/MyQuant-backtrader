import re
from collections import defaultdict
from typing import List, Dict, Any, Optional

def parse_backtest_log_advanced(log_file_path: str) -> Dict[str, Dict[str, Any]]:
    """
    增强版日志解析器，提取每日交易记录并按类型分类。

    返回格式:
    {
        '2025-10-23': {
            'regular_buys': [{'stock':..., 'price':..., 'shares':..., 'amount':..., 'time':...}],
            'deferred_buys': [...],
            'sells': [{'stock':..., 'price':..., 'shares':..., 'amount':..., 'time':...}],
            'canceled_orders': [{'stock':..., 'shares':..., 'reason': 'Canceled'}],
            'deferred_reservations': [{'stock':..., 'amount':..., 'expiry_date':...}],
            'summary': {...}  # 包含各类汇总
        }
    }
    """
    # 正则表达式
    pattern_date_update = re.compile(
        r'\[INFO\]\s+\[rolling_investment_strategy:826\]\s+(\d{4}-\d{2}-\d{2})更新持仓天数前'
    )
    # 买入执行日志
    pattern_buy_exec = re.compile(
        r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+执行买入\s+(\S+)\s+(\d+)股\s+@\s+([\d.]+)'
    )
    # 卖出成交日志 (rolling_investment_strategy:641)
    pattern_sell_exec = re.compile(
        r'\[INFO\]\s+\[rolling_investment_strategy:641\]\s+SELL\s+(\S+):\s+价格([\d.]+),\s+数量(\d+),'
    )
    # 订单创建日志（常规买入）
    pattern_order_create_normal = re.compile(
        r'\[DEBUG_ORDER_INFO_CREATE_NORMAL\]\s+(\S+)\s+创建订单时 order_info:\s*\{.*\'is_deferred\': False,.*\'stock\': \'\1\', \'date_str\': \'(\d+)\'.*\}'
    )
    # 订单创建日志（延期买入）
    pattern_order_create_deferred = re.compile(
        r'\[DEBUG_ORDER_INFO_CREATE\]\s+(\S+)\s+创建订单时 order_info:\s*\{.*\'is_deferred\': True,.*\'stock\': \'\1\', \'date_str\': \'(\d+)\'.*\}'
    )
    # 订单状态取消日志
    pattern_order_canceled = re.compile(
        r'\[INFO\]\s+\[rolling_investment_strategy:670\]\s+订单\s+(\S+)\s+状态 Canceled'
    )
    # 延期额度预留日志
    pattern_deferred_reserve = re.compile(
        r'\[INFO\]\s+\[global_capital_manager:463\]\s+✅\s+延期额度预留:\s+股票\s+(\S+)\s+金额\s+([\d,]+\.?\d*)\s+from\s+(\d+)\s+to\s+(\d+)'
    )
    # 可选：用于捕获资金回流（卖出）的辅助信息，但已用pattern_sell_exec

    # 数据结构
    orders_info = {}  # key: (stock, date_str) -> {'is_deferred': bool, 'supplementary': float}
    transactions_by_date = defaultdict(lambda: {
        'regular_buys': [],
        'deferred_buys': [],
        'sells': [],
        'canceled_orders': [],
        'deferred_reservations': []
    })
    current_date = None

    with open(log_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            # 1. 更新当前模拟日期
            m_date = pattern_date_update.search(line)
            if m_date:
                current_date = m_date.group(1)
                continue

            # 2. 捕获订单创建信息（常规买入）
            m_create_normal = pattern_order_create_normal.search(line)
            if m_create_normal:
                stock = m_create_normal.group(1)
                date_str = m_create_normal.group(2)
                orders_info[(stock, date_str)] = {'is_deferred': False, 'supplementary': 0.0}
                continue

            # 3. 捕获订单创建信息（延期买入）
            m_create_deferred = pattern_order_create_deferred.search(line)
            if m_create_deferred:
                stock = m_create_deferred.group(1)
                date_str = m_create_deferred.group(2)
                orders_info[(stock, date_str)] = {'is_deferred': True, 'supplementary': 0.0}
                continue

            # 4. 捕获取消订单
            m_canceled = pattern_order_canceled.search(line)
            if m_canceled and current_date:
                stock = m_canceled.group(1)
                # 尝试获取订单的股数（从之前的信息？无法直接获取，只记录股票和日期）
                transactions_by_date[current_date]['canceled_orders'].append({
                    'stock': stock,
                    'shares': None,  # 无法从日志中获取数量，可留空或从其他行尝试
                    'reason': 'Canceled'
                })
                continue

            # 5. 捕获延期额度预留
            m_reserve = pattern_deferred_reserve.search(line)
            if m_reserve:
                stock = m_reserve.group(1)
                amount = float(m_reserve.group(2).replace(',', ''))
                from_date = m_reserve.group(3)
                to_date = m_reserve.group(4)
                # 存入 from_date 对应的日期（预留发生的日期）
                transactions_by_date[from_date]['deferred_reservations'].append({
                    'stock': stock,
                    'amount': amount,
                    'expiry_date': to_date
                })
                continue

            # 6. 捕获买入执行
            m_buy = pattern_buy_exec.search(line)
            if m_buy:
                trade_date = m_buy.group(1)
                trade_time = m_buy.group(2)
                stock = m_buy.group(3)
                shares = int(m_buy.group(4))
                price = float(m_buy.group(5))
                amount = shares * price
                # 查找订单信息，判断是常规还是延期
                order_key = (stock, trade_date)
                is_deferred = orders_info.get(order_key, {}).get('is_deferred', False)
                transaction = {
                    'stock': stock,
                    'price': price,
                    'shares': shares,
                    'amount': amount,
                    'time': trade_time
                }
                if is_deferred:
                    transactions_by_date[trade_date]['deferred_buys'].append(transaction)
                else:
                    transactions_by_date[trade_date]['regular_buys'].append(transaction)
                continue

            # 7. 捕获卖出成交
            m_sell = pattern_sell_exec.search(line)
            if m_sell and current_date:
                stock = m_sell.group(1)
                price = float(m_sell.group(2))
                shares = int(m_sell.group(3))
                amount = shares * price
                transaction = {
                    'stock': stock,
                    'price': price,
                    'shares': shares,
                    'amount': amount,
                    'time': None  # 卖出具体时间未知
                }
                transactions_by_date[current_date]['sells'].append(transaction)
                continue

    # 按日期排序，并计算每日汇总
    result = {}
    for date in sorted(transactions_by_date.keys()):
        day_data = transactions_by_date[date]
        # 对每个列表按时间排序（如果有时间）
        day_data['regular_buys'].sort(key=lambda x: x['time'] or '00:00:00')
        day_data['deferred_buys'].sort(key=lambda x: x['time'] or '00:00:00')
        day_data['sells'].sort(key=lambda x: x['time'] or '00:00:00')
        # 计算汇总
        regular_buy_count = len(day_data['regular_buys'])
        regular_buy_shares = sum(t['shares'] for t in day_data['regular_buys'])
        regular_buy_amount = sum(t['amount'] for t in day_data['regular_buys'])
        deferred_buy_count = len(day_data['deferred_buys'])
        deferred_buy_shares = sum(t['shares'] for t in day_data['deferred_buys'])
        deferred_buy_amount = sum(t['amount'] for t in day_data['deferred_buys'])
        sell_count = len(day_data['sells'])
        sell_shares = sum(t['shares'] for t in day_data['sells'])
        sell_amount = sum(t['amount'] for t in day_data['sells'])
        canceled_count = len(day_data['canceled_orders'])
        reservation_count = len(day_data['deferred_reservations'])
        reservation_amount = sum(r['amount'] for r in day_data['deferred_reservations'])

        result[date] = {
            'regular_buys': day_data['regular_buys'],
            'deferred_buys': day_data['deferred_buys'],
            'sells': day_data['sells'],
            'canceled_orders': day_data['canceled_orders'],
            'deferred_reservations': day_data['deferred_reservations'],
            'summary': {
                'regular_buy_count': regular_buy_count,
                'regular_buy_shares': regular_buy_shares,
                'regular_buy_amount': round(regular_buy_amount, 2),
                'deferred_buy_count': deferred_buy_count,
                'deferred_buy_shares': deferred_buy_shares,
                'deferred_buy_amount': round(deferred_buy_amount, 2),
                'sell_count': sell_count,
                'sell_shares': sell_shares,
                'sell_amount': round(sell_amount, 2),
                'canceled_count': canceled_count,
                'reservation_count': reservation_count,
                'reservation_amount': round(reservation_amount, 2),
                'total_buy_count': regular_buy_count + deferred_buy_count,
                'total_buy_shares': regular_buy_shares + deferred_buy_shares,
                'total_buy_amount': round(regular_buy_amount + deferred_buy_amount, 2),
            }
        }
    return result

def print_daily_summary_advanced(data: Dict[str, Dict[str, Any]]):
    """打印每日交易清单，按类型分类"""
    for date, info in data.items():
        print(f"\n{'='*60}")
        print(f"日期: {date}")
        print(f"{'='*60}")

        # 常规买入
        if info['regular_buys']:
            print("\n【常规买入】")
            for t in info['regular_buys']:
                print(f"  {t['stock']:12} {t['shares']:>6}股 @ {t['price']:8.2f} 金额:{t['amount']:10.2f} at {t['time']}")
        else:
            print("\n【常规买入】无")

        # 延期买入
        if info['deferred_buys']:
            print("\n【延期买入】")
            for t in info['deferred_buys']:
                print(f"  {t['stock']:12} {t['shares']:>6}股 @ {t['price']:8.2f} 金额:{t['amount']:10.2f} at {t['time']}")
        else:
            print("\n【延期买入】无")

        # 卖出成交
        if info['sells']:
            print("\n【卖出成交】")
            for t in info['sells']:
                tm = f" at {t['time']}" if t['time'] else ""
                print(f"  {t['stock']:12} {t['shares']:>6}股 @ {t['price']:8.2f} 金额:{t['amount']:10.2f}{tm}")
        else:
            print("\n【卖出成交】无")

        # 未成交（取消）
        if info['canceled_orders']:
            print("\n【未成交（取消）】")
            for c in info['canceled_orders']:
                shares_info = f"{c['shares']}股" if c['shares'] else "数量未知"
                print(f"  {c['stock']:12} {shares_info} - {c['reason']}")
        else:
            print("\n【未成交（取消）】无")

        # 延期额度记录
        if info['deferred_reservations']:
            print("\n【延期额度记录（涨停未买成）】")
            for r in info['deferred_reservations']:
                print(f"  {r['stock']:12} 金额:{r['amount']:10.2f} 有效期至 {r['expiry_date']}")
        else:
            print("\n【延期额度记录】无")

        summary = info['summary']
        print("\n汇总:")
        print(f"  常规买入笔数: {summary['regular_buy_count']:3}  股数: {summary['regular_buy_shares']:6}  金额: {summary['regular_buy_amount']:12.2f}")
        print(f"  延期买入笔数: {summary['deferred_buy_count']:3}  股数: {summary['deferred_buy_shares']:6}  金额: {summary['deferred_buy_amount']:12.2f}")
        print(f"  卖出笔数: {summary['sell_count']:3}  股数: {summary['sell_shares']:6}  金额: {summary['sell_amount']:12.2f}")
        print(f"  未成交取消笔数: {summary['canceled_count']:3}")
        print(f"  延期额度记录笔数: {summary['reservation_count']:3}  总金额: {summary['reservation_amount']:12.2f}")
        print(f"  合计买入笔数: {summary['total_buy_count']:3}  股数: {summary['total_buy_shares']:6}  金额: {summary['total_buy_amount']:12.2f}")

if __name__ == "__main__":
    log_file = "./logs/backtest.log"  # 请根据实际路径修改
    result = parse_backtest_log_advanced(log_file)
    print_daily_summary_advanced(result)

    # 整体统计
    total_regular_buy = sum(v['summary']['regular_buy_amount'] for v in result.values())
    total_deferred_buy = sum(v['summary']['deferred_buy_amount'] for v in result.values())
    total_sell = sum(v['summary']['sell_amount'] for v in result.values())
    total_reservation = sum(v['summary']['reservation_amount'] for v in result.values())

    print(f"\n{'#'*60}")
    print(f"整体统计 (所有交易日)")
    print(f"  总常规买入金额: {total_regular_buy:.2f}")
    print(f"  总延期买入金额: {total_deferred_buy:.2f}")
    print(f"  总卖出金额: {total_sell:.2f}")
    print(f"  总延期额度预留金额: {total_reservation:.2f}")
    print(f"  净收益 (卖出-买入): {total_sell - (total_regular_buy + total_deferred_buy):.2f}")