import pandas as pd
from qmt_utils import get_stock_data_from_cache

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.max_colwidth", None)
pd.set_option("display.width", None)

if __name__ == "__main__":
    print("\n=== 从本地 SSOT 缓存读取单个股票 ===")
    single_stock_data = get_stock_data_from_cache(
        stock_code="002540.SZ",
        adjust_type="front",
        period="1d",
        start_time="20250101",
        end_time="20251208",
    )

    if single_stock_data is not None:
        print("单个股票数据示例:")
        print(single_stock_data)
        print(f"数据形状: {single_stock_data.shape}")
