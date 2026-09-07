from pprint import pprint

import akshare as ak
import pandas as pd
from xtquant import xtdata
import pandas as pd
from qmt_utils import get_stock_data_from_cache

# 显示所有行
pd.set_option('display.max_rows', None)
# 显示所有列
pd.set_option('display.max_columns', None)
# 设置列宽，确保长文本完整显示
pd.set_option('display.max_colwidth', None)
# 设置显示宽度，防止自动换行
pd.set_option('display.width', None)

# 使用示例
if __name__ == "__main__":
    # 4. 从缓存中获取单个股票数据
    # print("\n=== 从缓存获取单个股票数据 ===")
    # single_stock_data = get_stock_data_from_cache(
    #     base_dir="../stock_data",
    #     stock_code='002540.SZ',
    #     adjust_type='front',
    #     period='1d',
    #     start_time='20250101',
    #     end_time='20251208'
    # )
    #
    # if single_stock_data is not None:
    #     print(f"单个股票数据示例(前5行):")
    #     print(single_stock_data)
    #     print(f"数据形状: {single_stock_data.shape}")



    # 1. 设置基本参数
    stock_codes = ['000036.SZ','000863.SZ','000049.SZ','002160.SZ','002540.SZ']  # 股票代码，格式：代码.市场
    period_type = '1h'
    # KH常用数据周期：'tick'(分笔)/'1m'(1分钟)/'5m'(5分钟)/'1d'(1天)
    # 数据周期：'tick'(分笔)/'1m'(1分钟)/'5m'(5分钟)/'10m'(10分钟)/'15m'(15分钟)/'30m'(30分钟)/'1h'(60分钟)/'1d'(1天)/'1w'(1周)/'1M'(1月)
    start_date = '20251001'  # 开始日期
    end_date = '20251210'  # 结束日期

    # '1M' 无效
    # '60m'	⚠️ 可能无效	虽逻辑等价于 '1h'，但国金环境建议统一用 '1h'，避免兼容问题
    # 'tick' 虽然列在部分文档中，但实际应使用 xtdata.get_full_tick() 获取，get_market_data 的 period='tick' 可能无效或返回空。
    # tick
    # 股票 000036.SZ 的数据形状： (0, 20)
    # Empty DataFrame
    # Columns: [time, lastPrice, open, high, low, lastClose, amount, volume, pvolume, tickvol, stockStatus, openInt, lastSettlementPrice, askPrice, bidPrice, askVol, bidVol, settlementPrice, transactionNum, pe]
    # Index: []

    # 2. 下载历史数据到本地缓存
    # 使用download_history_data2可支持批量股票列表下载，效率更高
    print("开始下载数据...")
    result = xtdata.download_history_data2(
        stock_list=stock_codes,
        period=period_type,
        start_time=start_date,
        end_time=end_date
    )
    print("下载完成。")

    # 检查返回值
    print(f"下载结果: {result}")

    # 如果返回的是字典，可以查看详情
    if isinstance(result, dict):
        for stock, status in result.items():
            print(f"股票 {stock}: 下载状态 {status}")

    # 在 XTQuant 中，从 xtdata.download_history_data2下载成功到 xtdata.get_market_data_ex能够获取到数据，通常需要一定的处理时间。

    # 3. 从本地缓存读取数据
    # field_list为空列表表示获取该周期下所有默认字段
    local_data = xtdata.get_market_data_ex(
        field_list=[],  # 如需指定字段，可填入如['time','open','high','low','close','volume']
        stock_list=stock_codes,
        period=period_type,
        start_time=start_date,
        end_time=end_date,
        count=-1,  # -1表示取指定时间区间内的所有数据
        dividend_type='none',  # 复权类型：'none'(不复权)/'front'(前复权)/'back'(后复权)
        fill_data=True  # 是否自动填充缺失数据（如停牌期间），确保时间序列连续性
    )

    # 4. 处理数据
    # get_market_data_ex返回的是字典，key为股票代码，value为DataFrame
    for stock_code in stock_codes:
        if stock_code in local_data:
            df = local_data[stock_code]
            # 确保索引是时间格式（如果索引是时间戳）
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index.astype(str), format='%Y%m%d%H%M%S', errors='coerce')
            print(f"股票 {stock_code} 的数据形状：", df.shape)
            # print(df)  # 查看前几行数据
            print(df.head())  # 查看前几行数据
            print(df.tail())  # 查看前几行数据
            print(f"  {stock_code}: {len(df)} 条记录, 时间范围: {df.index.min()} ~ {df.index.max()}")
        else:
            print(f"未找到股票 {stock_code} 的数据。")

    # 可以将DataFrame保存到CSV文件
    # df.to_csv(f'{stock_code}_{period_type}_{start_date}_{end_date}.csv')

"""
000036.SZ---触发止盈 000036.SZ: 最高5.05 现价4.78 回撤87.10%
2025-11-28  4.20  4.31  4.18   4.31   287292
2025-12-01  4.32  4.74  4.30   4.74   594519
2025-12-02  4.90  5.05  4.72   4.78  1406231
2025-12-03  4.82  4.82  4.65   4.67   542013
2025-12-04  4.65  4.72  4.52   4.68   481376
2025-12-05  4.68  4.68  4.55   4.63   348099
2025-12-08  4.69  4.79  4.61   4.72   516986

000863.SZ---触发止损 000863.SZ: 成本5.28 现价5.17 亏损-2.08%
2025-11-28  5.00  5.05  4.91   5.03   246919
2025-12-01  5.01  5.45  5.00   5.28   520248
2025-12-02  5.28  5.35  5.08   5.17   290547
2025-12-03  5.19  5.19  5.00   5.03   320407
2025-12-04  5.00  5.05  4.63   4.70   611728
2025-12-05  4.65  4.66  4.24   4.38   955143
2025-12-08  4.34  4.59  4.30   4.57   608590

000049.SZ
2025-11-28  26.50  27.19  26.29  26.89   70721
2025-12-01  27.11  29.58  27.01  29.58  418366
2025-12-02  30.10  30.62  28.83  29.60  462180
2025-12-03  29.74  29.74  28.34  28.46  211884
2025-12-04  28.50  28.84  28.30  28.37  125900
2025-12-05  28.22  29.09  27.91  28.82  132457
2025-12-08  28.83  29.66  28.20  29.35  218634

002160.SZ---触发止损 : 成本5.41 现价5.24 亏损-3.14%
2025-11-28  5.12  5.30  5.07   5.19   618267
2025-12-01  5.28  5.65  5.28   5.41  1173662
2025-12-02  5.31  5.38  5.17   5.24   663049
2025-12-03  5.23  5.48  5.19   5.39  1018273
2025-12-04  5.47  5.48  5.23   5.25   698914
2025-12-05  5.21  5.55  5.18   5.52  1045009
2025-12-08  5.62  5.63  5.37   5.48  1042566

002540.SZ
2025-11-28  6.51  6.58  6.44   6.56   80296
2025-12-01  6.61  7.22  6.60   7.22  287777
2025-12-02  7.33  7.33  7.07   7.18  495773
2025-12-03  7.19  7.62  7.12   7.41  586819
2025-12-04  7.30  7.37  7.21   7.32  312601
2025-12-05  7.32  7.51  7.28   7.43  350207
2025-12-08  7.44  7.47  7.28   7.42  296899
"""