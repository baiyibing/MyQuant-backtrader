import sys
import time
from pathlib import Path

import pandas as pd
from pytdx.hq import TdxHq_API

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from common.infra.timekeeping import shanghai_now
from pytdx.config.hosts import hq_hosts

def download_daily_k_data(stock_code, exchange=0, days=1):
    """
    下载指定股票的最近N天日K线数据（兼容 pytdx 1.72）

    参数:
    stock_code: 股票代码（如'601318'）
    exchange: 交易所（0=上海，1=深圳）
    days: 需要下载的天数（默认1天）

    返回:
    pandas DataFrame，包含K线数据
    """
    api = TdxHq_API()

    # 连接行情服务器（尝试多个服务器）
    servers = hq_hosts

    connected = False
    for name,ip, port in servers:
        try:
            print(f"尝试连接服务器: {ip}:{port}")
            api.connect(ip, port, time_out=5)

            # 使用简单的API调用来验证连接
            # test_data = api.get_security_quotes([(exchange, stock_code)])
            print("获取股票行情")
            test_data = api.get_security_quotes([(0, "000001"), (1, "600300")])
            if test_data:
                print(f"✅ 已连接到服务器: {ip}:{port}")
                connected = True
                break
            else:
                print(f"⚠️ 连接成功但未获取到测试数据: {ip}:{port}")
                api.disconnect()
        except Exception as e:
            print(f"⚠️ 连接失败 {ip}:{port} - {str(e)}")
            continue

    if not connected:
        print("❌ 所有服务器连接失败")
        return None

    try:
        # pytdx 1.72 中 get_k_data 的正确用法
        # 参数: (market, code, start, count)
        kline_data = api.get_k_data('000001', '2026-01-01', '2026-01-20')

        if kline_data is None or len(kline_data) == 0:
            print("⚠️ 未获取到K线数据，请检查股票代码和交易所设置")
            return None

        # 转换为DataFrame（pytdx 1.72返回的字段顺序）
        df = pd.DataFrame(kline_data, columns=[
            'datetime', 'open', 'high', 'low', 'close',
            'volume', 'amount'
        ])

        # 分离日期和时间
        df['date'] = pd.to_datetime(df['datetime'].astype(str).str[:8], format='%Y%m%d')
        df['time'] = df['datetime'].astype(str).str[8:]

        # 添加股票代码
        df['code'] = stock_code

        # 重新排列列顺序
        df = df[['date', 'time', 'open', 'high', 'low', 'close', 'volume', 'amount', 'code']]

        return df

    except Exception as e:
        print(f"❌ 数据获取过程中出现错误: {str(e)}")
        return None
    finally:
        try:
            api.disconnect()
        except:
            pass


# 测试函数
def run_download():
    """测试下载功能"""
    test_cases = [
        ('601318', 0),  # 上海交易所
        ('000001', 1),  # 深圳交易所
    ]

    for stock_code, exchange in test_cases:
        print(f"\n{'=' * 50}")
        print(f"测试股票: {stock_code}, 交易所: {exchange}")
        print(f"当前系统时间: {shanghai_now().strftime('%Y-%m-%d %H:%M:%S')}")

        df = download_daily_k_data(stock_code, exchange, 10)  # 下载10天数据测试

        if df is not None:
            print(f"\n✅ 成功获取数据，共{len(df)}条记录")
            print("前5条数据:")
            print(df.head())

            # 保存到CSV
            output_file = f"{stock_code}_{shanghai_now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(output_file, index=False)
            print(f"数据已保存至: {output_file}")
        else:
            print("\n❌ 数据获取失败")


if __name__ == "__main__":
    from pytdx.util.best_ip import select_best_ip

    best_ip = select_best_ip()
    print(f"最优服务器：IP={best_ip['ip']}, 端口={best_ip['port']}")
    run_download()