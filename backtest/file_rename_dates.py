import os
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from common.infra.timekeeping import shanghai_now


def rename_files(directory):
    """
    遍历目录中的文件，将文件名中的日期格式从"月.日"转换为"YYYYMMDD"格式。
    例如："12.3" -> "20261203"（假设当前年份为2026），"12.12" -> "20261212"。
    """
    current_year = shanghai_now().year
    # 正则表达式匹配"月.日"模式，如12.3或3.5 [3](@ref)
    date_pattern = r'(\d{1,2})\.(\d{1,2})'  # 匹配1-2位数字、点、1-2位数字

    for filename in os.listdir(directory):  # 遍历目录下的所有项 [1,5](@ref)
        old_path = os.path.join(directory, filename)
        if not os.path.isfile(old_path):  # 跳过目录，只处理文件 [1](@ref)
            continue

        def replace_date(match):
            """内部函数：将匹配的日期部分转换为YYYYMMDD格式"""
            month_str, day_str = match.groups()
            try:
                month = int(month_str)
                day = int(day_str)
            except ValueError:
                return match.group(0)  # 转换失败则返回原字符串

            # 基本验证：月份1-12，日期1-31
            if 1 <= month <= 12 and 1 <= day <= 31:
                # 将月份和日期补零为两位数字 [6](@ref)
                month_fmt = str(month).zfill(2)  # 例如 3 -> "03"
                day_fmt = str(day).zfill(2)  # 例如 3 -> "03", 12 -> "12"
                return f"{current_year}{month_fmt}{day_fmt}"  # 组合为YYYYMMDD
            else:
                return match.group(0)  # 日期无效则返回原字符串

        # 使用正则替换日期部分 [3,10](@ref)
        new_filename = re.sub(date_pattern, replace_date, filename)

        if new_filename != filename:  # 仅当文件名变化时重命名
            new_path = os.path.join(directory, new_filename)
            try:
                os.rename(old_path, new_path)  # 重命名文件 [1,7,9](@ref)
                print(f"成功: '{filename}' -> '{new_filename}'")
            except FileExistsError:
                print(f"错误: 文件已存在，跳过 '{new_filename}'")
            except PermissionError:
                print(f"错误: 无权限修改 '{filename}'")
            except OSError as e:
                print(f"错误: 重命名失败 '{filename}': {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("用法: python rename_dates.py <目录路径>")
        sys.exit(1)
    dir_path = sys.argv[1]
    if not os.path.isdir(dir_path):
        print(f"错误: 目录 '{dir_path}' 不存在")
        sys.exit(1)
    rename_files(dir_path)