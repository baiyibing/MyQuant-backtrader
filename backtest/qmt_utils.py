import re
import pandas as pd
import time
import os
from datetime import datetime, timedelta
import shutil
from pathlib import Path
from xtquant import xtdata

def read_stock_codes(file_path):
    """ 读取股票代码文件并转换为pandas DataFrame 参数: file_path: 文件路径 返回: pandas DataFrame，包含序号和股票代码两列 """
    try:
        # 读取文件，使用空格作为分隔符，跳过空行
        df = pd.read_csv(file_path, sep='\s+', # 使用空格作为分隔符
                         header=None, # 没有表头
                         names=['序号', '股票代码'], # 设置列名
                         dtype={'序号': int, '股票代码': str}, # 指定数据类型
                         skip_blank_lines=True) # 跳过空行
        # 确保股票代码是6位字符串，不足6位前面补0
        df['股票代码'] = df['股票代码'].astype(str).str.zfill(6)
        print(f"成功读取文件，共{len(df)}条记录")
        return df
    except FileNotFoundError:
        print(f"错误：文件 '{file_path}' 未找到")
        return None
    except Exception as e:
        print(f"读取文件时出错: {e}")
        return None

def format_stock_code(input_str):
    """格式化A股股票代码，添加正确的交易所后缀。 支持处理带前缀的输入（如ST、*ST、N、XD等），但只提取数字代码部分添加后缀。 参数: input_str: 字符串，可能包含前缀的股票标识，如'000001', 'ST000001', '600000' 返回: 带交易所后缀的股票代码字符串，如'000001.SZ' 异常: ValueError: 如果输入中找不到6位数字代码或代码无法识别交易所 """
    # 正则表达式提取所有数字
    digits = re.findall(r'\d+', input_str)
    if not digits:
        raise ValueError(f"输入 '{input_str}' 中未找到数字部分")
    code_str = ''.join(digits)
    if len(code_str) != 6:
        raise ValueError(f"提取的数字代码 '{code_str}' 不是6位数字")
    # 修复关键点：深交所判断条件扩展为包含300和301开头（创业板新代码）
    # 上交所: 600,601,603,605,688开头
    if code_str.startswith(('600', '601', '603', '605', '688')):
        suffix = '.SH'
    # 深交所: 000,001,002,003,300,301开头（包含创业板新代码301xxx）
    elif code_str.startswith(('000', '001', '002', '003', '300', '301')):
        suffix = '.SZ'
    # 北交所: 43,83,87,88开头或920开头
    elif code_str.startswith(('43', '83', '87', '88')) or code_str.startswith('920'):
        suffix = '.BJ'
    else:
        raise ValueError(f"无法识别股票代码 {code_str} 的交易所")
    return code_str + suffix

def batch_format_stock_codes(stock_list):
    """批量处理股票代码列表，添加交易所后缀。 参数: stock_list: 字符串列表，股票代码或标识列表 返回: 处理后的股票代码列表，无法处理的代码保留原样 """
    result = []
    for code in stock_list:
        try:
            formatted_code = format_stock_code(code)
            result.append(formatted_code)
        except ValueError as e:
            print(f"处理失败: {code} -> 错误: {e}")
            result.append(code)
    return result

def get_miniqmt_data(stock_list, start_time, end_time, period='1d', incrementally=True, base_dir="../stock_data", adjust_type='front'):
    """ 使用MiniQMT的xtdata接口批量获取多只股票历史数据，支持增量下载模式 参数: stock_list: 股票代码列表，如 ['000001.SZ', '600000.SH'] start_time: 开始时间，如 '20240101' end_time: 结束时间，如 '20240930' period: K线周期，默认为日线 '1d' incrementally: 是否启用增量下载模式，默认为True base_dir: 数据存储基础目录，默认为 "../stock_data" adjust_type: 复权类型，可选值: 'none' - 不复权(原始数据) 'front' - 前复权(默认) 'back' - 后复权 返回: data_dict: 字典，键为股票代码，值为格式化后的DataFrame """
    # 复权类型映射
    adjust_mapping = {
        'none': 'none',  # 不复权
        'front': 'front',  # 前复权
        'back': 'back'  # 后复权
    }
    if adjust_type not in adjust_mapping:
        print(f"⚠️ 不支持的复权类型: {adjust_type}，使用默认前复权")
        adjust_type = 'front'
    adjust_value = adjust_mapping[adjust_type]
    adjust_name = {'none': '不复权', 'front': '前复权', 'back': '后复权'}[adjust_type]
    print(f"正在批量获取 {len(stock_list)} 只股票从 {start_time} 到 {end_time} 的{period}数据...")
    print(f"复权类型: {adjust_name}")
    print(f"下载模式: {'增量下载' if incrementally else '全量下载'}")
    print(f"数据存储目录: {base_dir}/period={period}/dividend_type={adjust_type}")
    data_dict = {}  # 用于存储所有股票的数据

    # 定义下载进度回调函数
    def on_progress(data):
        """下载进度回调函数，实时显示下载进度"""
        if 'finished' in data and 'total' in data:
            finished = data['finished']
            total = data['total']
            stockcode = data.get('stockcode', '未知代码')
            progress = (finished / total) * 100 if total > 0 else 0
            print(f"下载进度: {finished}/{total} ({progress:.1f}%) - 当前股票: {stockcode}")
        else:
            print(f"进度信息: {data}")

    try:
        # 增量下载逻辑：检查本地数据状态
        if incrementally:
            print("检查本地数据状态，筛选需要更新的股票...")
            need_update_stocks = []
            for stock_code in stock_list:
                # 构建Hive格式的目录路径
                file_path = _get_hive_path(base_dir, period, adjust_type, stock_code)
                if os.path.exists(file_path):
                    try:
                        # 读取本地数据的最新日期
                        existing_data = pd.read_parquet(file_path)
                        if not existing_data.empty and isinstance(existing_data.index, pd.DatetimeIndex):
                            latest_date = existing_data.index.max()
                            # 如果本地最新日期早于请求的结束日期，则需更新
                            if latest_date < pd.to_datetime(end_time):
                                need_update_stocks.append(stock_code)
                                print(f"🔁🔁🔁🔁 {stock_code} 需要更新，本地最新日期: {latest_date.strftime('%Y-%m-%d')}")
                            else:
                                print(f"✅ {stock_code} 数据已是最新，跳过下载")
                        else:
                            need_update_stocks.append(stock_code)
                    except Exception as e:
                        print(f"⚠️ 检查 {stock_code} 本地数据时出错: {e}，将重新下载")
                        need_update_stocks.append(stock_code)
                else:
                    print(f"📥📥📥📥 {stock_code} 本地无数据，需要下载")
                    need_update_stocks.append(stock_code)
            print(f"实际需要下载的股票数量: {len(need_update_stocks)}/{len(stock_list)}")
            actual_download_list = need_update_stocks if need_update_stocks else stock_list
        else:
            actual_download_list = stock_list

        if not actual_download_list:
            print("所有股票数据均已是最新，无需下载")
            return _load_hive_data(stock_list, base_dir, period, adjust_type, start_time, end_time)

        # 1. 批量下载历史数据到本地缓存
        print("步骤1: 批量下载历史数据...")
        if incrementally:
            # 增量下载模式
            print("使用增量下载模式，只下载缺失或更新的数据...")
            xtdata.download_history_data2(
                stock_list=actual_download_list,
                period=period,
                start_time=start_time,
                end_time=end_time,
                incrementally=True,
                callback=on_progress
            )
        else:
            # 全量下载模式
            print("使用全量下载模式，下载所有请求时间范围内的数据...")
            xtdata.download_history_data2(
                stock_list=actual_download_list,
                period=period,
                start_time=start_time,
                end_time=end_time,
                incrementally=False,
                callback=on_progress
            )

        # 等待下载完成
        min_wait_time = max(2, len(actual_download_list) * 0.1)
        print(f"等待数据最终处理完成，预计{min_wait_time}秒...")
        time.sleep(min_wait_time)

        # 2. 批量获取数据（添加复权参数）
        print("步骤2: 从本地缓存批量读取数据...")
        raw_data = xtdata.get_market_data_ex(
            field_list=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'],
            stock_list=stock_list,
            period=period,
            start_time=start_time,
            end_time=end_time,
            count=-1,
            dividend_type=adjust_value,  # 使用 dividend_type 而不是 adjust
            fill_data=True  # 添加填充选项
        )
        if not raw_data:
            print("获取数据失败，返回数据为空")
            return None

        # 3. 保存数据到本地（按照Hive分区结构）
        print("步骤3: 保存数据到本地(Hive分区结构)...")
        success_count = _save_hive_data(raw_data, base_dir, period, adjust_type, start_time, end_time)
        print(f"✅ 成功保存 {success_count} 只股票数据到本地")

        # 4. 处理数据格式
        print("步骤4: 处理数据格式...")
        processed_data, success_count = _process_stock_data(raw_data, stock_list)
        print(f"\n📊📊📊📊 批量数据获取完成！成功: {success_count}/{len(stock_list)}")
        return processed_data if success_count > 0 else None
    except Exception as e:
        print(f"❌❌❌❌ 批量获取数据过程中发生错误: {e}")
        return None

def _get_hive_path(base_dir, period, adjust_type, stock_code):
    """ 构建Hive分区格式的文件路径 格式: {base_dir}/period={period}/dividend_type={adjust_type}/symbol={stock_code}/data.parquet """
    # 修复：将股票代码中的点号替换为下划线
    safe_stock_code = stock_code.replace('.', '_')
    # 构建路径：将周期作为第一级分区
    path = Path(base_dir) / f"period={period}" / f"dividend_type={adjust_type}" / f"symbol={safe_stock_code}"
    # 确保目录存在
    path.mkdir(parents=True, exist_ok=True)
    return path / "data.parquet"

def _save_hive_data(raw_data, base_dir, period, adjust_type, start_time, end_time):
    """ 按照Hive分区结构保存数据到本地 """
    success_count = 0
    for stock_code, stock_df in raw_data.items():
        if not isinstance(stock_df, pd.DataFrame) or stock_df.empty:
            continue
        try:
            # 构建Hive格式的文件路径
            file_path = _get_hive_path(base_dir, period, adjust_type, stock_code)
            # 处理数据格式
            processed_df = _format_dataframe(stock_df)
            if processed_df is None or processed_df.empty:
                continue
            # 按时间范围过滤
            start_dt = pd.to_datetime(start_time)
            end_dt = pd.to_datetime(end_time)
            mask = (processed_df.index >= start_dt) & (processed_df.index <= end_dt)
            df_filtered = processed_df.loc[mask]
            if df_filtered.empty:
                print(f"⚠️ {stock_code} 在时间范围内无数据，跳过保存")
                continue
            # 保存到Parquet文件
            df_filtered.to_parquet(file_path, engine='pyarrow', compression='snappy')
            # 验证保存的数据
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path) / 1024  # KB
                print(f"✅ 保存 {stock_code} 成功！路径: {file_path}，数据量: {len(df_filtered)} 条，文件大小: {file_size:.2f} KB")
                success_count += 1
            else:
                print(f"❌❌ 保存 {stock_code} 失败！文件未创建")
        except Exception as e:
            print(f"❌❌ 保存 {stock_code} 数据失败: {e}")
            continue
    return success_count

def _load_hive_data(stock_list, base_dir, period, adjust_type, start_time, end_time):
    """ 从Hive分区结构加载已有数据 """
    data_dict = {}
    success_count = 0
    for stock_code in stock_list:
        try:
            # 构建Hive格式的文件路径
            file_path = _get_hive_path(base_dir, period, adjust_type, stock_code)
            if not os.path.exists(file_path):
                print(f"⚠️ {stock_code} 本地无数据文件: {file_path}")
                continue
            # 读取Parquet文件
            df = pd.read_parquet(file_path)
            if df.empty:
                print(f"⚠️ {stock_code} 本地数据文件为空")
                continue
            # 按时间范围过滤
            start_dt = pd.to_datetime(start_time)
            end_dt = pd.to_datetime(end_time)
            mask = (df.index >= start_dt) & (df.index <= end_dt)
            df_filtered = df.loc[mask]
            if df_filtered.empty:
                print(f"⚠️ {stock_code} 在时间范围内无数据")
                continue
            data_dict[stock_code] = df_filtered
            success_count += 1
            print(f"✅ 从本地加载 {stock_code} 数据成功！共 {len(df_filtered)} 条记录，路径: {file_path}")
        except Exception as e:
            print(f"⚠️ 从本地加载 {stock_code} 数据失败: {e}")
            continue
    print(f"从本地加载完成！成功: {success_count}/{len(stock_list)}")
    return data_dict if success_count > 0 else None

def _format_dataframe(stock_df):
    """处理数据格式"""
    try:
        # 列名重映射
        column_mapping = {
            'time': 'Time',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume',
            'amount': 'Amount',
        }
        # 重命名列
        stock_df = stock_df.rename(columns=column_mapping)
        # 确保包含必需的列
        required_columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Amount']
        missing_columns = [col for col in required_columns if col not in stock_df.columns]
        if missing_columns:
            print(f"⚠️ 数据缺少必要的列: {missing_columns}")
            return None
        # 选择所需的列
        data_df = stock_df[required_columns].copy()
        # 确保数据类型正确
        data_df = data_df.apply(pd.to_numeric, errors='coerce')
        # 删除空值
        data_df = data_df.dropna()
        if data_df.empty:
            print("⚠️ 数据清洗后为空")
            return None
        # 确保索引是日期时间类型
        if not isinstance(data_df.index, pd.DatetimeIndex):
            try:
                data_df.index = pd.to_datetime(data_df.index)
            except Exception as e:
                print(f"⚠️ 无法将索引转换为日期时间格式: {e}")
                return None
        return data_df
    except Exception as e:
        print(f"❌❌ 处理数据框时发生错误: {e}")
        return None

def _process_stock_data(raw_data, stock_list):
    """处理股票数据格式"""
    data_dict = {}
    success_count = 0
    for stock_code in stock_list:
        if stock_code not in raw_data:
            print(f"⚠️ {stock_code} 数据不存在，跳过处理")
            continue
        try:
            stock_data = raw_data[stock_code]
            formatted_df = _format_dataframe(stock_data)
            if formatted_df is None or formatted_df.empty:
                print(f"⚠️ {stock_code} 数据格式不符合预期或为空")
                continue
            data_dict[stock_code] = formatted_df
            success_count += 1
            print(f"✅ {stock_code} 数据处理成功！共 {len(formatted_df)} 条记录")
        except Exception as e:
            print(f"❌❌❌❌ 处理 {stock_code} 数据时发生错误: {e}")
            continue
    return data_dict, success_count

def get_hive_directory_structure(base_dir="../stock_data"):
    """获取Hive目录结构"""
    try:
        base_path = Path(base_dir)
        if not base_path.exists():
            print("基础目录不存在")
            return
        print(f"Hive目录结构: {base_path}")
        for period_dir in base_path.iterdir():
            if period_dir.is_dir() and period_dir.name.startswith("period="):
                print(f" ├── {period_dir.name}")
                for adjust_dir in period_dir.iterdir():
                    if adjust_dir.is_dir() and adjust_dir.name.startswith("dividend_type="):
                        print(f" │ ├── {adjust_dir.name}")
                        symbol_count = 0
                        for symbol_dir in adjust_dir.iterdir():
                            if symbol_dir.is_dir() and symbol_dir.name.startswith("symbol="):
                                symbol_count += 1
                        print(f" │ │ └── 共 {symbol_count} 个股票文件夹")
                        # 显示前几个股票文件夹
                        for i, symbol_dir in enumerate(adjust_dir.iterdir()):
                            if i >= 3:  # 只显示前3个
                                print(f" │ │ ... 还有 {symbol_count - 3} 个文件夹")
                                break
                            if symbol_dir.is_dir() and symbol_dir.name.startswith("symbol="):
                                # 修复：在打印时，将下划线替换回点号，以便于人类阅读
                                raw_stock_code = symbol_dir.name.replace('symbol=', '').replace('_', '.')
                                data_file = symbol_dir / "data.parquet"
                                if data_file.exists():
                                    file_size = data_file.stat().st_size / 1024
                                    print(f" │ │ ├── {raw_stock_code} (文件大小: {file_size:.1f} KB)")
                                else:
                                    print(f" │ │ ├── {raw_stock_code} (无数据文件)")
    except Exception as e:
        print(f"获取目录结构时出错: {e}")

def clear_hive_data(base_dir="../stock_data", period=None, adjust_type=None, stock_code=None):
    """ 清理Hive格式的股票数据 参数: base_dir: 基础目录 period: 周期，如'1d'，为None时清理所有周期 adjust_type: 复权类型，如'front'，为None时清理所有复权类型 stock_code: 股票代码，如'000001.SZ'，为None时清理所有股票 """
    try:
        base_path = Path(base_dir)
        if not base_path.exists():
            print("目录不存在，无需清理")
            return
        if period is None:
            # 清理所有周期
            for period_dir in base_path.iterdir():
                if period_dir.is_dir() and period_dir.name.startswith("period="):
                    _clear_specific_hive_data(period_dir, adjust_type, stock_code)
        else:
            # 清理特定周期
            period_path = base_path / f"period={period}"
            if period_path.exists():
                _clear_specific_hive_data(period_path, adjust_type, stock_code)
            else:
                print(f"周期目录不存在: {period_path}")
    except Exception as e:
        print(f"清理数据时出错: {e}")

def _clear_specific_hive_data(period_path, adjust_type, stock_code):
    """清理特定周期下的数据"""
    if adjust_type is None:
        # 清理特定周期的所有复权类型
        for adjust_dir in period_path.iterdir():
            if adjust_dir.is_dir() and adjust_dir.name.startswith("dividend_type="):
                _clear_adjust_type_data(adjust_dir, stock_code)
    else:
        # 清理特定复权类型
        adjust_path = period_path / f"dividend_type={adjust_type}"
        if adjust_path.exists():
            _clear_adjust_type_data(adjust_path, stock_code)
        else:
            print(f"复权类型目录不存在: {adjust_path}")

def _clear_adjust_type_data(adjust_path, stock_code):
    """清理特定复权类型下的数据"""
    if stock_code is None:
        # 清理特定复权类型的所有股票
        if adjust_path.exists():
            shutil.rmtree(adjust_path)
            print(f"已删除目录: {adjust_path}")
        else:
            print(f"目录不存在: {adjust_path}")
    else:
        # 修复：将股票代码中的点号替换为下划线
        safe_stock_code = stock_code.replace('.', '_')
        target_path = adjust_path / f"symbol={safe_stock_code}"
        if target_path.exists():
            shutil.rmtree(target_path)
            print(f"已删除目录: {target_path}")
        else:
            print(f"目录不存在: {target_path}")

def get_stock_data_from_cache(base_dir="../stock_data", stock_code=None, period='1d', adjust_type='front', start_time=None, end_time=None):
    """Load OHLCV via path-SSOT. Legacy ``../stock_data`` is ignored."""
    if stock_code is None:
        print("请指定股票代码")
        return None
    from common.infra.qmt_utils_adv import get_stock_data_from_cache as _ssot_get

    kwargs = {}
    if base_dir not in (None, "", "../stock_data"):
        kwargs["base_dir"] = base_dir
    start = start_time if start_time is not None else "19900101"
    end = end_time if end_time is not None else "20991231"
    try:
        df = _ssot_get(
            stock_code=stock_code,
            start_time=start,
            end_time=end,
            period=period,
            adjust_type=adjust_type,
            **kwargs,
        )
        if df is not None:
            print(f"✅ 成功加载 {stock_code} 数据，共 {len(df)} 条记录")
        return df
    except Exception as e:
        print(f"加载股票数据时出错: {e}")
        return None

def getdata4bt(stock_code, start_time, end_time, period='1d'):
    """ 使用MiniQMT的xtdata接口获取股票历史数据[1,4](@ref) 参数: stock_code: 股票代码，如 '000001.SZ' start_time: 开始时间，如 '20240101' end_time: 结束时间，如 '20240930' period: K线周期，默认为日线 '1d' 返回: data_df: 格式化后的DataFrame """
    print(f"正在获取 {stock_code} 从 {start_time} 到 {end_time} 的{period}数据...")
    try:
        single_stock_data = get_stock_data_from_cache(
            base_dir="../stock_data",
            stock_code=stock_code,
            period=period,
            adjust_type='front',
            start_time=start_time,
            end_time=end_time
        )
        if single_stock_data is not None:
            print(f"数据形状: {single_stock_data.shape}")
            if not isinstance(single_stock_data, pd.DataFrame):
                print("获取的数据格式不符合预期")
                return None
            # 重命名列以符合Backtrader要求
            column_mapping = {
                'time': 'Time',
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume',
                'amount': 'Amount',
            }
            single_stock_data = single_stock_data.rename(columns=column_mapping)
            # 确保包含所有必需的列
            required_columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Amount']
            missing_columns = [col for col in required_columns if col not in single_stock_data.columns]
            if missing_columns:
                print(f"数据缺少必要的列: {missing_columns}")
                return None
            # 选择所需的列并确保数据类型正确
            data_df = single_stock_data[required_columns].copy()
            data_df = data_df.apply(pd.to_numeric, errors='coerce')
            data_df = data_df.dropna()
            # 确保索引是日期时间类型
            if not isinstance(data_df.index, pd.DatetimeIndex):
                try:
                    data_df.index = pd.to_datetime(data_df.index)
                except:
                    print("无法将索引转换为日期时间格式")
                    return None
            print(f"{stock_code} 数据获取成功！共获取 {len(data_df)} 条记录")
            return data_df
        else:
            print(f"未获取到 {stock_code} 的数据")
            return None
    except Exception as e:
        print(f"获取 {stock_code} 数据过程中发生错误: {e}")
        return None

# 使用示例
if __name__ == "__main__":
    test_cases = [
        '000001',  # 深市主板
        '000858',  # 深市主板
        '002304',  # 深市主板
        '300750',  # 创业板（老）
        '600000',  # 沪市主板
        '601318',  # 沪市主板
        '603259',  # 沪市主板
        '605499',  # 沪市主板
        '688981',  # 科创板
        '430090',  # 北交所
        '831010',  # 北交所
        '920000',  # 北交所新代码
        'ST000001',  # 带ST前缀
        '*ST600000',  # 带*ST前缀
        'N300750',  # 带N前缀(新股)
        'XD601318',  # 带XD前缀(除息)
        '301567',  # 修复点：创业板新代码（301开头）
        '123',  # 无效代码(数字位数不足)
        'abcdef',  # 无效代码(无数字)
    ]

    print("A股股票代码后缀处理测试:")
    print("=" * 50)
    for test in test_cases:
        try:
            result = format_stock_code(test)
            print(f"输入: {test:>12} -> 输出: {result}")
        except ValueError as e:
            print(f"输入: {test:>12} -> 错误: {e}")

    # 假设文件名为 stock_codes.txt
    file_path = r"./20251201.txt"  # 请替换为实际文件路径
    # 读取文件
    stock_df = read_stock_codes(file_path)
    if stock_df is not None:
        # 显示前几行数据
        print("\n数据预览:")
        print(stock_df.head())
        # 显示数据基本信息
        print("\n数据基本信息:")
        print(stock_df.info())
        # 显示数据统计信息
        print("\n数据统计信息:")
        print(stock_df.describe())
        # 保存为CSV文件（可选）
        stock_df.to_csv('20251201.csv', index=False, encoding='utf-8-sig')
        print("\n数据已保存为 stock_codes.csv")

    # 示例股票列表
    file_path = r"./20251201.txt"  # 请替换为实际文件路径
    # 读取文件
    stock_df = read_stock_codes(file_path)
    stock_list = stock_df['股票代码']
    processed_list = batch_format_stock_codes(stock_list)
    for original, processed in zip(stock_list, processed_list):
        print(f"{original} -> {processed}")
    processed_list.append('000001.SZ')

    # 1. 首次全量下载前复权数据
    print("=== 首次全量下载(前复权) ===")
    data_front = get_miniqmt_data(
        stock_list=processed_list,
        start_time='20250101',
        end_time='20251201',
        period='1d',
        incrementally=False,  # 全量下载
        base_dir="../stock_data",  # 基础目录
        adjust_type='front'  # 前复权
    )

    # 查看目录结构
    print("\n=== 目录结构 ===")
    get_hive_directory_structure("../stock_data")

    # 2. 下载不复权数据
    print("\n=== 下载不复权数据 ===")
    data_none = get_miniqmt_data(
        stock_list=processed_list,
        start_time='20251201',
        end_time='20251211',
        period='1d',
        incrementally=False,  # 全量下载
        base_dir="../stock_data",
        adjust_type='none'  # 不复权
    )

    # 查看目录结构
    print("\n=== 目录结构(新增不复权数据后) ===")
    get_hive_directory_structure("../stock_data")

    # 3. 增量更新
    print("\n=== 增量更新(前复权) ===")
    data_incremental = get_miniqmt_data(
        stock_list=processed_list,
        start_time='20250101',
        end_time='20251211',  # 延长结束日期以获取新数据
        period='1d',
        incrementally=True,  # 增量下载
        base_dir="../stock_data",
        adjust_type='front'  # 前复权
    )

    # 4. 从缓存中获取单个股票数据
    print("\n=== 从缓存获取单个股票数据 ===")
    single_stock_data = get_stock_data_from_cache(
        base_dir="../stock_data",
        stock_code='000001.SZ',
        period='1d',
        adjust_type='front',
        start_time='20250101',
        end_time='20251211'
    )
    if single_stock_data is not None:
        print(f"单个股票数据示例(前5行):")
        print(single_stock_data.head())
        print(f"数据形状: {single_stock_data.shape}")