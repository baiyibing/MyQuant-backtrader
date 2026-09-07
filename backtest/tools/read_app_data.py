import pandas as pd
import re
from io import StringIO


def read_special_excel_format(file_path):
    """
    读取特殊格式的表格文件

    Parameters:
    file_path (str): 文件路径

    Returns:
    pd.DataFrame: 读取的数据
    """

    # 读取文件内容
    with open(file_path, 'r', encoding='gbk') as f:  # 尝试gbk编码，中文常见
        content = f.read()

    # 按行分割
    lines = content.split('\n')

    # 找到数据开始的行（跳过文件名和<Sheet1>）
    data_start = 0
    for i, line in enumerate(lines):
        if re.match(r'代码\s+名称', line):  # 找到列名行
            data_start = i
            break

    if data_start == 0:
        # 如果没找到标准的列名行，尝试从第三行开始
        data_start = 2

    # 获取列名行
    header_line = lines[data_start]

    # 清理列名：替换特殊字符，简化列名
    header_line = re.sub(r'\([^)]*\)', '', header_line)  # 移除括号内容
    header_line = re.sub(r'[^\w\s%]', '', header_line)  # 移除非字母数字字符
    header_line = re.sub(r'\s+', ' ', header_line).strip()  # 合并多个空格

    # 手工分割列名（因为列名中有空格，需要特殊处理）
    # 基于观察，前几列是：代码 名称 涨幅 现价 涨跌 买价 卖价 总量 现量 涨速 换手
    headers = []
    current_header = ""
    in_header = False

    for char in header_line:
        if char == ' ':
            if in_header and current_header.strip():
                headers.append(current_header.strip())
                current_header = ""
                in_header = False
        else:
            current_header += char
            in_header = True

    if current_header.strip():
        headers.append(current_header.strip())

    # 数据行处理
    data_lines = []
    for i in range(data_start + 1, len(lines)):
        line = lines[i].strip()
        if not line or line.startswith('#'):  # 跳过空行和数据来源行
            continue

        # 清理数据行：移除开头的 ="
        line = re.sub(r'^=\"', '', line)
        line = re.sub(r'\"$', '', line)

        # 处理数据中的空格，用制表符替换多个空格以便分割
        line = re.sub(r'\s+', '\t', line)
        data_lines.append(line)

    # 创建DataFrame
    if len(headers) > 0 and len(data_lines) > 0:
        # 使用StringIO和read_csv读取处理后的数据
        data_content = '\n'.join(data_lines)

        try:
            # 尝试用制表符分割
            df = pd.read_csv(StringIO(data_content),
                             sep='\t',
                             header=None,
                             na_values=['--', ''],
                             engine='python')

            # 如果列数匹配，设置列名
            if df.shape[1] == len(headers):
                df.columns = headers[:df.shape[1]]
            else:
                print(f"警告: 列数不匹配。数据有{df.shape[1]}列，列名有{len(headers)}个")
                # 创建默认列名
                df.columns = [f'col_{i}' for i in range(df.shape[1])]

            return df

        except Exception as e:
            print(f"读取数据时出错: {e}")
            return None

    return None


# 更简单的方法：如果文件实际上是制表符分隔的
def read_simple_method(file_path):
    """
    简化版本的读取方法
    """
    try:
        # 跳过前两行，从第三行开始读取
        df = pd.read_csv(file_path,
                         sep='\t',  # 尝试制表符分隔
                         skiprows=0,  # 跳过前两行
                         skipfooter=1,
                         header=0,  # 第一行为列名
                         na_values=['--', ''],
                         encoding='gbk',
                         engine='python',
                         quotechar='"')  # 引号字符

        # 清理列名
        df.columns = [re.sub(r'\([^)]*\)', '', col) for col in df.columns]
        df.columns = [re.sub(r'[^\w]', '', col) for col in df.columns]
        df['代码'] = df['代码'].str.replace('=', '').str.replace('"', '')
        # 先确保是字符串类型
        df['代码'] = df['代码'].astype(str)
        # 然后使用 zfill 方法在左侧补零，确保长度为6位
        df['代码'] = df['代码'].str.zfill(6)
        return df

    except Exception as e:
        print(f"简化方法读取失败: {e}")
        return None


# 使用示例
if __name__ == "__main__":
    file_path = r"E:\PycharmProjects\OSkhQuant1.3\stock_pool\APPDATA\20251023.xls"  # 替换为实际文件路径

    # 方法1: 复杂但可能更准确
    df1 = read_special_excel_format(file_path)

    # 方法2: 简单直接
    df2 = read_simple_method(file_path)



    if df2 is not None:
        print("方法2 数据读取成功!")
        print(f"方法2 数据形状: {df2.shape}")
        print("\n方法2 前5行数据:")
        print(df2.head())
        print("\n方法2 后5行数据:")
        print(df2.tail())
        print("\n方法2 列名:")
        print(df2.columns.tolist())
    elif df1 is not None:
        print("方法1 使用复杂方法读取成功!")
        print(f"数据形状: {df1.shape}")
        print("\n前5行数据:")
        print(df1.head())
    else:
        print("两种方法都失败了，请检查文件格式")