from pprint import pprint

import akshare as ak
import pandas as pd

# 显示所有行
pd.set_option('display.max_rows', None)
# 显示所有列
pd.set_option('display.max_columns', None)
# 设置列宽，确保长文本完整显示
pd.set_option('display.max_colwidth', None)
# 设置显示宽度，防止自动换行
pd.set_option('display.width', None)

# 获取前复权日线数据（推荐用于回测）
df = ak.stock_zh_a_hist(
    symbol="600519",        # 股票代码（不带 SH/SZ 前缀）
    period="daily",
    start_date="20200101",
    end_date="20251203",
    adjust="qfq"            # qfq=前复权, hfq=后复权, None=不复权
)
# 重要提示：A股回测必须使用复权价格（推荐前复权 qfq），否则分红送股会导致策略信号失真！
# 重命名列以匹配 Backtrader 的 GenericCSVData 要求
df.rename(columns={
    '日期': 'date',
    '开盘': 'open',
    '收盘': 'close',
    '最高': 'high',
    '最低': 'low',
    '成交量': 'volume'
}, inplace=True)

df['date'] = pd.to_datetime(df['date'])
df.set_index('date', inplace=True)

pprint(df)

import backtrader as bt

# 假设 df 是上面任一方式获取的 DataFrame，索引为 datetime
data = bt.feeds.PandasData(
    dataname=df,
    datetime=None,        # 因为 index 已是 datetime
    open=1,               # 列位置：'open' 是第1列（从0开始）
    close=2,
    high=3,
    low=4,
    volume=5,
    openinterest=-1       # A股无 openinterest，设为 -1
)

cerebro = bt.Cerebro()
cerebro.adddata(data)

# 最佳实践：用 AKShare 获取前复权日线数据 → 转为 Pandas DataFrame → 用 bt.feeds.PandasData 加载到 Backtrader。