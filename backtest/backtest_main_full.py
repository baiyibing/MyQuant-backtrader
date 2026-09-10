import os
import gc
import pprint
import sys
import timeit
import time
from datetime import datetime, timedelta

# 平铺导入（rolling_investment_strategy 等）要求 repo 根在 sys.path；
# 本机 vanna312 的 oskh_quant editable 已移除，无全局 common 来源。
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import psutil
import backtrader as bt
from backtrader.feeds import PandasData
import logging
import pandas as pd
from rolling_investment_strategy import RollingInvestmentStrategy
from qmt_utils_adv import to_datetime, read_stock_codes, batch_format_stock_codes, load_single_stock_data, \
    get_stock_data_from_cache
from global_capital_manager import GlobalCapitalManager

# 设置日志
import logging
from logging.handlers import RotatingFileHandler
import os

# 配置日志文件路径
LOG_FILE = "backtest.log"
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILEPATH = os.path.join(LOG_DIR, LOG_FILE)

# 配置日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(module)s:%(lineno)d - %(funcName)s] %(message)s"

# 创建日志处理器（文件 + 控制台）
file_handler = RotatingFileHandler(
    LOG_FILEPATH, maxBytes=100 * 1024 * 1024,  # 每个日志文件最大 100MB
    backupCount=5,  # 保留 5 个备份文件
    encoding='utf-8'  # 显式指定 UTF-8 编码
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# 配置根日志记录器（初始级别设为 INFO，稍后可根据命令行参数调整）
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[file_handler, console_handler]
)

logger = logging.getLogger(__name__)


def load_stock_data(cerebro, processed_list, start_date: str, end_date: str, buy_date: str, adjust_type: str = 'none'):
    """统一的数据加载函数 - 优化版本（使用交易日历计算日线起始日期）

    参数:
        cerebro: Backtrader Cerebro 实例
        processed_list: 已格式化的股票代码列表
        start_date: 回测开始日期时间（格式YYYYMMDDHHMMSS）
        end_date: 回测结束日期时间（格式YYYYMMDDHHMMSS）
        buy_date: 买入日期（用于检查数据是否包含该日）
        adjust_type: 复权类型（'none', 'qfq', 'hfq'）

    返回:
        successfully_loaded_stocks: 成功加载的股票代码列表
        missing_buy_date_stocks: 缺少买入日数据的股票代码列表
        data_contains_buy_date: 是否存在至少一只股票包含买入日数据
    """
    successfully_loaded_stocks = []
    missing_buy_date_stocks = []
    data_contains_buy_date = False

    # 使用统一的日期转换
    start_dt = to_datetime(start_date)
    end_dt = to_datetime(end_date)
    buy_date = to_datetime(buy_date).date()

    # 优化：使用交易日历计算前20个交易日作为日线开始日期，确保有足够数据计算均线
    try:
        import pandas_market_calendars as mcal
        cal = mcal.get_calendar('SSE')
        start_search = start_dt - pd.Timedelta(days=60)
        trading_days = cal.valid_days(start_date=start_search.date(), end_date=start_dt.date())

        if len(trading_days) >= 20:
            if start_dt.date() in trading_days:
                target_idx = -21
            else:
                target_idx = -20
            if abs(target_idx) <= len(trading_days):
                daily_start_dt = trading_days[target_idx].date()
            else:
                daily_start_dt = trading_days[0].date()
            logger.debug(f"使用交易日历计算日线开始日期: {daily_start_dt}")
        else:
            daily_start_dt = start_dt - pd.Timedelta(days=30)
            logger.warning(f"交易日不足20个，回退到使用 {daily_start_dt.date()} 作为日线开始日期")
    except ImportError:
        logger.warning("未安装 pandas_market_calendars，使用简单方法计算日线开始日期")
        daily_start_dt = start_dt - pd.Timedelta(days=30)
    except Exception as e:
        logger.warning(f"计算交易日历出错: {e}，回退到简单方法")
        daily_start_dt = start_dt - pd.Timedelta(days=30)

    for i, code in enumerate(processed_list):
        logger.debug(f"加载数据 ({i + 1}/{len(processed_list)}): {code}...")

        # 动态内存管理：每10个股票检查一次内存使用
        if i % 10 == 0:
            mem_usage = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
            if mem_usage > 1000:
                gc.collect()
                logger.debug(f"内存使用超过1GB({mem_usage:.2f}MB)，执行垃圾回收")

        # 加载分钟线数据
        data, has_buy_date = load_single_stock_data(code, start_dt, end_dt, buy_date, adjust_type)

        # 加载日线数据
        daily_data = get_stock_data_from_cache(
            stock_code=code,
            period='1d',
            adjust_type=adjust_type,
            start_time=daily_start_dt,
            end_time=end_dt.date()
        )

        if daily_data is not None and len(daily_data) < 10:
            logger.info(f"日线数据量不足 (需要至少10个点): {code}, 数据长度: {len(daily_data)}")
            missing_buy_date_stocks.append(code)
            continue

        if data is not None:
            cerebro.adddata(data, name=code)

            if daily_data is not None:
                daily_data_bt = PandasData(
                    dataname=daily_data,
                    open='open',
                    high='high',
                    low='low',
                    close='close',
                    volume='volume',
                    timeframe=bt.TimeFrame.Days,
                    compression=1,
                    fromdate=pd.to_datetime(daily_start_dt),
                    todate=pd.to_datetime(end_dt.date())
                )
                cerebro.adddata(daily_data_bt, name=code + '_daily')

            successfully_loaded_stocks.append(code)
            if has_buy_date:
                data_contains_buy_date = True
            logger.debug(f"✅ {code} 数据加载成功")
        else:
            missing_buy_date_stocks.append(code)

    return successfully_loaded_stocks, missing_buy_date_stocks, data_contains_buy_date


# ==================== 主程序 ====================
if __name__ == '__main__':
    import argparse

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Backtest with logging control')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--strategies', default='', help='comma versions to run (e.g. version6); default all')
    args = parser.parse_args()

    # 根据 debug 标志调整根日志级别
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    # 抑制第三方库的 INFO 日志（非调试模式）
    if not args.debug:
        logging.getLogger('pandas_market_calendars').setLevel(logging.WARNING)
        logging.getLogger('backtrader').setLevel(logging.WARNING)
        # 可根据需要添加其他模块

    """批量回测策略（含五个预设 + 两个参数覆盖变体）。"""
    strategies = [
        ('version1', None, "策略1: 2%止损 + 50%回撤止盈"),
        ('version2', None, "策略2: 2%止损 + 动态止盈"),
        ('version3', None, "策略3: 4%止损 + 20%止盈 + 开盘涨停保留"),
        ('version4', None, "策略4: 10日线买/5日线卖"),
        ('version5', None, "策略5: 无止损 + 2%止盈 + 固定时间强制卖出"),
        ('version6', None, "策略6: 4%止损 + 2%锚定分档回撤止盈(T+1=50%/T+2=40%/T+3+=30%) + 尾盘涨停弃买"),
        ('version1', {'profit_drawdown_pct': 0.60}, "策略1变体: 回撤阈值60%"),
        ('version2', {'dynamic_drawdown_rules': {1: 0.55, 2: 0.45, 3: 0.35, 4: 0.25, 5: 0.15}}, "策略2变体: 调整动态规则"),
    ]

    # 默认跑全量策略集合；如需缩小范围用 --strategies version6,version1 过滤。
    select_strategies = strategies
    if args.strategies.strip():
        wanted = {v.strip() for v in args.strategies.split(',') if v.strip()}
        select_strategies = [row for row in strategies if row[0] in wanted]

    for version, params, desc in select_strategies:
        logger.info(f"批量回测五种策略（对比效果）: {desc}")

        from pathlib import Path

        total_start_time = timeit.default_timer()

        path = Path('../stock_pool')
        csv_files = list(path.rglob('*.csv'))

        result_list = []
        stock_buy_set = set()
        stock_buy_dict = {}

        BUY_DATE_STR = '20251023'
        END_DATE_STR = '20251104'

        for file_path in csv_files:
            file_start_time = timeit.default_timer()
            logger.debug(f"\n{'=' * 60}")
            logger.debug(f"处理文件: {file_path}")
            logger.debug(f"{'=' * 60}")

            filename = Path(file_path).stem
            if BUY_DATE_STR <= filename <= END_DATE_STR:
                pass
            else:
                continue

            stock_df = read_stock_codes(file_path)
            stock_list = stock_df['stock_code']
            processed_list = batch_format_stock_codes(stock_list)

            logger.debug("股票代码转换结果:")
            for original, processed in zip(stock_list, processed_list):
                logger.debug(f" {original} -> {processed}")

            stock_buy_dict[filename] = processed_list
            stock_buy_set.update(processed_list)

        if not stock_buy_dict:
            logger.error("没有找到任何有效的买入日期文件，程序退出。")
            exit(1)

        buy_dates = [datetime.strptime(date_str, "%Y%m%d") for date_str in stock_buy_dict.keys()]
        min_buy_date = min(buy_dates)
        max_buy_date = max(buy_dates)
        logger.info(f"回测买入日期范围: {min_buy_date.strftime('%Y%m%d')} - {max_buy_date.strftime('%Y%m%d')}")

        try:
            import pandas_market_calendars as mcal
            cal = mcal.get_calendar('SSE')
            start_search = (min_buy_date - timedelta(days=30)).strftime("%Y%m%d")
            end_search = (max_buy_date + timedelta(days=60)).strftime("%Y%m%d")
            trading_days = cal.valid_days(start_date=start_search, end_date=end_search)
            trading_day_list = [d.strftime("%Y%m%d") for d in trading_days.date]
            logger.info(f"获取交易日列表，共 {len(trading_day_list)} 天，范围 {trading_day_list[0]} 至 {trading_day_list[-1]}")
        except ImportError:
            logger.error("未安装 pandas_market_calendars，无法获取交易日列表，延期额度将无法正确计算。")
            raise
        except Exception as e:
            logger.error(f"获取交易日列表失败: {e}")
            raise

        START_DATETIME_STR = BUY_DATE_STR + "093000"
        END_DATETIME_STR = END_DATE_STR + "150000"

        global_capital_manager = GlobalCapitalManager(
            total_capital=21000000.0,
            daily_investment=1000000.0,
            trading_days=trading_day_list
        )

        global_capital_manager.reset_for_new_sequence('20251023')
        init_cash = 1000000

        cerebro = bt.Cerebro()

        logger.info("股票数据加载开始...")
        data_loading_start = timeit.default_timer()
        successfully_loaded_stocks, missing_buy_date_stocks, data_contains_buy_date = load_stock_data(
            cerebro,
            list(stock_buy_set),
            START_DATETIME_STR,
            END_DATETIME_STR,
            BUY_DATE_STR,
            adjust_type='none'
        )
        data_loading_time = timeit.default_timer() - data_loading_start
        logger.info(f"✅ 股票数据加载完成，耗时: {data_loading_time:.2f} 秒")

        if len(successfully_loaded_stocks) == 0:
            logger.info("没有成功加载任何股票数据，程序退出")
            exit(1)

        # 根据调试模式决定策略日志级别
        strategy_log_level = 'DEBUG' if args.debug else 'WARNING'

        cerebro.addstrategy(
            RollingInvestmentStrategy,
            stock_pool=successfully_loaded_stocks,
            stock_buy_dict=stock_buy_dict,
            init_cash=init_cash,
            max_position_pct=0.1,
            enable_tplus1=True,
            skip_limit_up=False,
            enable_limit_control=True,
            strategy_version=version,
            strategy_params=params,
            log_level=strategy_log_level,  # 动态传入
            indicator_config={
                'ma5': 5,
                'ma10': 10,
            },
            global_capital_manager=global_capital_manager
        )

        cerebro.broker.setcash(global_capital_manager.total_capital)
        cerebro.broker.setcommission(commission=0.001)

        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', timeframe=bt.TimeFrame.Days, riskfreerate=0.0,
                            annualize=True, stddev_sample=True)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

        logger.info(f"\n✅ 成功加载 {len(successfully_loaded_stocks)} 只股票")
        logger.info("开始回测...")
        logger.info(f"💰 期初投资组合价值: {cerebro.broker.getvalue():.2f}")

        try:
            backtest_start = timeit.default_timer()
            results = cerebro.run()
            backtest_time = timeit.default_timer() - backtest_start

            strat = results[0]

            original_final_value = cerebro.broker.getvalue()
            original_total_return = (original_final_value / global_capital_manager.total_capital - 1) * 100

            logger.info(f"✅ 回测完成，耗时: {backtest_time:.2f} 秒")
            logger.info("\n" + "=" * 50)
            logger.info("优化后的策略绩效指标分析")
            logger.info("=" * 50)

            returns_analysis = strat.analyzers.returns.get_analysis()
            sharpe_analysis = strat.analyzers.sharpe.get_analysis()
            drawdown_analysis = strat.analyzers.drawdown.get_analysis()


            def safe_format(value, fmt="{:.2f}"):
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    return "N/A"
                try:
                    return fmt.format(float(value))
                except (TypeError, ValueError, OverflowError):
                    return str(value)


            sharpe_ratio = sharpe_analysis.get('sharperatio')
            max_dd = drawdown_analysis.get('max', {}).get('drawdown')
            total_ret = returns_analysis.get('rtot', 0) * 100

            logger.info(f"夏普比率: {safe_format(sharpe_ratio)}")
            logger.info(f"最大回撤: {safe_format(max_dd, '{:.2f}%')}")
            logger.info(f"总收益率: {safe_format(total_ret, '{:.2f}%')}")
            logger.info(f"original_final_value: {safe_format(original_final_value, '{:.2f}')}")
            logger.info(f"original_total_return: {safe_format(original_total_return, '{:.2f}%')}")
            logger.info(f"数据加载耗时: {data_loading_time}秒")
        except Exception as e:
            logger.info(f"回测执行失败或分析器数据获取失败: {e}")
            import traceback
            logger.info(traceback.format_exc())

        total_end_time = timeit.default_timer()
        total_processing_time = total_end_time - total_start_time

        logger.info(f"\n{'=' * 80}")
        logger.info(f"🎉 所有文件处理完成!")
        logger.info(f"⏱️ 总处理时间: {total_processing_time:.2f} 秒")
        logger.info(f"{'=' * 80}")