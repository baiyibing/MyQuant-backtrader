import pandas as pd
import io

import pandas as pd
from io import StringIO

# 显示所有行
pd.set_option('display.max_rows', None)
# 显示所有列
pd.set_option('display.max_columns', None)
# 设置列宽，确保长文本完整显示
pd.set_option('display.max_colwidth', None)
# 设置显示宽度，防止自动换行
pd.set_option('display.width', None)

    # 您提供的示例数据
example_data_20260105 = """
          date      cash  cumulative_buy  cumulative_sell
0   2026-01-05  273064.0        726936.0              0.0
1   2026-01-06  699851.0        928710.0         628561.0
2   2026-01-07  998331.0        928710.0         927041.0
3   2026-01-08  998331.0        928710.0         927041.0
4   2026-01-09  998331.0        928710.0         927041.0
5   2026-01-12  998331.0        928710.0         927041.0
6   2026-01-13  998331.0        928710.0         927041.0
7   2026-01-14  998331.0        928710.0         927041.0
8   2026-01-15  998331.0        928710.0         927041.0
9   2026-01-16  998331.0        928710.0         927041.0
10  2026-01-19  998331.0        928710.0         927041.0
11  2026-01-20  998331.0        928710.0         927041.0
12  2026-01-21  998331.0        928710.0         927041.0
13  2026-01-22  998331.0        928710.0         927041.0
14  2026-01-23  998331.0        928710.0         927041.0
15  2026-01-26  998331.0        928710.0         927041.0
"""

example_data_20260106 = """
              date      cash  cumulative_buy  cumulative_sell
    0   2026-01-05  273064.0        726936.0              0.0
    1   2026-01-06  699851.0        928710.0         628561.0
    2   2026-01-07  998331.0        928710.0         927041.0
    3   2026-01-08  998331.0        928710.0         927041.0
    4   2026-01-09  998331.0        928710.0         927041.0
    5   2026-01-12  998331.0        928710.0         927041.0
    6   2026-01-13  998331.0        928710.0         927041.0
    7   2026-01-14  998331.0        928710.0         927041.0
    8   2026-01-15  998331.0        928710.0         927041.0
    9   2026-01-16  998331.0        928710.0         927041.0
    10  2026-01-19  998331.0        928710.0         927041.0
    11  2026-01-20  998331.0        928710.0         927041.0
    12  2026-01-21  998331.0        928710.0         927041.0
    13  2026-01-22  998331.0        928710.0         927041.0
    14  2026-01-23  998331.0        928710.0         927041.0
    15  2026-01-26  998331.0        928710.0         927041.0
    """

def process_and_merge_data(data1, data2, date1, date2):
    """
    处理并合并两个数据集

    参数:
    data1: 第一个数据字符串
    data2: 第二个数据字符串
    date1: 第一个数据来源日期标识
    date2: 第二个数据来源日期标识

    返回:
    合并后的DataFrame
    """
    # 读取数据
    df1 = pd.read_csv(io.StringIO(data1), delim_whitespace=True)
    df2 = pd.read_csv(io.StringIO(data2), delim_whitespace=True)

    # 选择并重命名列
    df1_clean = df1[['date', 'cumulative_sell']].rename(
        columns={'cumulative_sell': f'cumulative_sell_{date1}'}
    )

    df2_clean = df2[['date', 'cumulative_sell']].rename(
        columns={'cumulative_sell': f'cumulative_sell_{date2}'}
    )

    # 合并数据
    merged_df = pd.merge(df1_clean, df2_clean, on='date', how='outer')

    return merged_df




def process_example_data():
    """
    直接处理您提供的示例数据格式
    """
    # 您提供的示例数据
    example_data = """
              date      cash  cumulative_buy  cumulative_sell
    0   2026-01-05  273064.0        726936.0              0.0
    1   2026-01-06  699851.0        928710.0         628561.0
    2   2026-01-07  998331.0        928710.0         927041.0
    3   2026-01-08  998331.0        928710.0         927041.0
    4   2026-01-09  998331.0        928710.0         927041.0
    5   2026-01-12  998331.0        928710.0         927041.0
    6   2026-01-13  998331.0        928710.0         927041.0
    7   2026-01-14  998331.0        928710.0         927041.0
    8   2026-01-15  998331.0        928710.0         927041.0
    9   2026-01-16  998331.0        928710.0         927041.0
    10  2026-01-19  998331.0        928710.0         927041.0
    11  2026-01-20  998331.0        928710.0         927041.0
    12  2026-01-21  998331.0        928710.0         927041.0
    13  2026-01-22  998331.0        928710.0         927041.0
    14  2026-01-23  998331.0        928710.0         927041.0
    15  2026-01-26  998331.0        928710.0         927041.0
    """

    # 读取数据
    df = pd.read_csv(io.StringIO(example_data), delim_whitespace=True)

    # 只保留date和cumulative_sell列
    result_df = df[['date', 'cumulative_sell']].copy()

    # 添加文件标识
    result_df['source_file'] = '20260105'

    print("处理后的数据:")
    print(result_df)

    return result_df


# 运行示例处理
if __name__ == "__main__":
    # # 执行处理
    # result = process_and_merge_data(
    #     example_data_20260105,
    #     example_data_20260106,
    #     '20260105',
    #     '20260106'
    # )
    #
    # print("最终合并结果:")
    # print(result)

    merged_df = pd.DataFrame(columns=['date', 'cumulative_sell'])

    from pathlib import Path

    path = Path('./optimized_results')
    # 递归查找所有 .csv 文件
    csv_files = list(path.rglob('*.csv'))

    for file_path in csv_files:
        # 示例股票列表
        # file_path = r"../stock_pool/20251219.csv"
        print(file_path)
        filename = Path(file_path).stem
        df = pd.read_csv(file_path, dtype={0: str, 1: float}, skip_blank_lines=True)
        print(df)
        df_rename = df[['date', 'cumulative_sell']].rename(
            columns={'cumulative_sell': filename}
        )
        print(df_rename)
        merged_df = pd.merge(merged_df, df_rename, on='date', how='outer')
        print(merged_df)

    if not merged_df.empty:
        merged_df.to_csv(r'cumulative_sell.csv')