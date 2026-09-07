import os

import pandas as pd
import re

from qmt_utils_adv import detect_encoding, check_bom


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

def compare_stock_files(xls_file, csv_file):
    """
    比较两个文件中的股票代码和名称是否一致
    """
    # 读取Excel文件
    try:
        # 读取xls文件，跳过第一行（列名）
        # df_xls = pd.read_excel(xls_file, sheet_name='Sheet1', skiprows=1, header=None, engine='xlrd')
        df_xls = read_simple_method(xls_file)

        # 提取股票代码和名称（从数据中观察，代码在第0列，名称在第1列）
        stocks_xls = {}
        for index, row in df_xls.iterrows():
            if len(row) >= 2:
                code = str(row[0]).strip()
                name = str(row[1]).strip()

                # 清理代码格式（去除="等符号）
                code = re.sub(r'[="]', '', code)

                if code and len(code) == 6 and code.isdigit():
                    stocks_xls[code] = name

        print(f"XLS文件读取完成，共{len(stocks_xls)}只股票")

    except Exception as e:
        print(f"读取XLS文件出错: {e}")
        return False

    # 读取CSV文件
    try:
        # 方法1: 检查BOM（字节顺序标记）
        encoding = check_bom(csv_file)
        confidence = 1.0
        if encoding != 'unknown':
            pass
        else:
            # 方法2: 检查BOM（字节顺序标记）
            encoding, confidence = detect_encoding(csv_file)

        if encoding in ['GB2312','gb2312']:
            encoding = 'GBK'

        # 尝试读取CSV文件
        df_csv = pd.read_csv(csv_file, header=None, dtype={0: str, 1: str}, encoding=encoding, skip_blank_lines=True)

        stocks_csv = {}
        for index, row in df_csv.iterrows():
            if len(row) >= 2:
                code = str(row[0]).strip()
                name = str(row[1]).strip()

                # 清理代码格式（去除="等符号）
                code = re.sub(r'[="]', '', code)

                if code and len(code) == 6 and code.isdigit():
                    stocks_csv[code] = name

        print(f"CSV文件读取完成，共{len(stocks_csv)}只股票")

    except Exception as e:
        print(f"读取CSV文件出错: {e}")
        return False

    # 比较两个文件
    results = {
        'both_files': {},
        'only_in_xls': {},
        'only_in_csv': {},
        'name_mismatch': {}
    }

    # 查找共同存在的股票
    common_codes = set(stocks_xls.keys()) & set(stocks_csv.keys())

    for code in common_codes:
        if stocks_xls[code] == stocks_csv[code]:
            results['both_files'][code] = stocks_xls[code]
        else:
            results['name_mismatch'][code] = {
                'xls_name': stocks_xls[code],
                'csv_name': stocks_csv[code]
            }

    # 查找只在XLS中存在的股票
    for code in set(stocks_xls.keys()) - set(stocks_csv.keys()):
        results['only_in_xls'][code] = stocks_xls[code]

    # 查找只在CSV中存在的股票
    for code in set(stocks_csv.keys()) - set(stocks_xls.keys()):
        results['only_in_csv'][code] = stocks_csv[code]

    # 输出比较结果
    print("\n" + "=" * 60)
    print("股票代码和名称比较结果")
    print("=" * 60)

    print(f"\n1. 两个文件中都存在的股票（{len(results['both_files'])}只）:")
    if results['both_files']:
        for code, name in results['both_files'].items():
            print(f"   {code} {name}")
    else:
        print("   无")

    print(f"\n2. 名称不一致的股票（{len(results['name_mismatch'])}只）:")
    if results['name_mismatch']:
        for code, names in results['name_mismatch'].items():
            print(f"   {code}: XLS中为'{names['xls_name']}', CSV中为'{names['csv_name']}'")
    else:
        print("   无")

    print(f"\n3. 只在XLS文件中存在的股票（{len(results['only_in_xls'])}只）:")
    if results['only_in_xls']:
        for code, name in results['only_in_xls'].items():
            print(f"   {code} {name}")
    else:
        print("   无")

    print(f"\n4. 只在CSV文件中存在的股票（{len(results['only_in_csv'])}只）:")
    if results['only_in_csv']:
        for code, name in results['only_in_csv'].items():
            print(f"   {code} {name}")
    else:
        print("   无")

    # 返回总体一致性结果
    total_mismatch = len(results['name_mismatch']) + len(results['only_in_xls']) + len(results['only_in_csv'])
    is_consistent = total_mismatch == 0

    print(f"\n总体结果:{'一致' if is_consistent else '不一致'} {xls_file}与{csv_file} ")
    return is_consistent


def modify_file_path_advanced(original_path):
    """
    使用更安全的方法修改文件路径（推荐使用）
    """
    # 创建Path对象[1,4](@ref)
    path_obj = Path(original_path)

    # 获取路径的各个部分[4,5](@ref)
    parts = list(path_obj.parts)

    # 过滤掉APPDATA目录[6,8](@ref)
    filtered_parts = [part for part in parts if part != 'APPDATA']

    # 重新构建路径[2,3](@ref)
    new_path = Path(*filtered_parts)

    # 修改文件扩展名[4](@ref)
    new_path = new_path.with_suffix('.csv')

    return new_path

# 使用示例
if __name__ == "__main__":
    # xls_file = r"E:\PycharmProjects\OSkhQuant1.3\stock_pool\APPDATA\20251023.xls"  # 替换为实际文件路径
    # csv_file = r"E:\PycharmProjects\OSkhQuant1.3\stock_pool\20251023.csv"  # 替换为实际文件路径
    # compare_stock_files(xls_file, csv_file)

    from pathlib import Path

    csv_path = Path('../stock_pool')
    # 递归查找所有 .csv 文件
    csv_files = list(csv_path.rglob('*.csv'))

    xls_path = Path('../stock_pool/APPDATA')
    # 递归查找所有 .csv 文件
    xls_files = list(xls_path.rglob('*.xls'))

    # 找出同名但后缀不同的文件对
    file_pairs = []
    for xls_file in xls_files:
        if xls_file.suffix == '.xls':
            # 获取不带后缀的文件名
            # base_name = xls_file.stem
            # 在第二个目录中查找同名的xls文件
            # csv_file = base_name + '.csv'
            csv_file = modify_file_path_advanced(xls_file)
            if (csv_file.is_file() and xls_file.suffix == '.csv') or csv_file in csv_files:
                file_pairs.append((xls_file, csv_file))

    for xls_file, csv_file in file_pairs:
        compare_stock_files(xls_file, csv_file)