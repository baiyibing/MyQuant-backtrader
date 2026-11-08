"""BT pool-date selection only; lake integrity tools live in MyQuant-infra."""
from pathlib import Path

from common.infra.quant_logger import get_logger
from common.infra.qmt_utils_adv import batch_format_stock_codes, read_stock_codes

logger = get_logger(__name__)


def collect_stock_codes(pool_dir: str, start_date: str, end_date: str) -> set:
    """从股票池目录中读取指定日期范围内的所有股票代码，返回格式化后的集合。"""
    path = Path(pool_dir)
    csv_files = list(path.rglob('*.csv'))
    stock_set = set()

    for file_path in csv_files:
        filename = file_path.stem
        if not (start_date <= filename <= end_date):
            continue

        df = read_stock_codes(str(file_path))
        if df is None or df.empty:
            logger.warning(f"无法读取文件或文件为空: {file_path}")
            continue

        raw_list = df['stock_code'].tolist()
        formatted = batch_format_stock_codes(raw_list)
        stock_set.update(formatted)
        logger.debug(f"文件 {filename} 添加 {len(formatted)} 只股票")

    logger.info(f"共收集到 {len(stock_set)} 只股票")
    return stock_set
