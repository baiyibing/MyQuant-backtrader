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
    print("\n=== 从缓存获取单个股票数据 ===")
    single_stock_data = get_stock_data_from_cache(
        base_dir="../stock_data",
        stock_code='002540.SZ',
        adjust_type='front',
        period='1d',
        start_time='20250101',
        end_time='20251208'
    )

    if single_stock_data is not None:
        print(f"单个股票数据示例(前5行):")
        print(single_stock_data)
        print(f"数据形状: {single_stock_data.shape}")
