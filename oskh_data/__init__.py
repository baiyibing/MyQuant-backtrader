# -*- coding: utf-8 -*-
"""
本地历史行情数据基础设施（Local Market Data Infrastructure）—— MVP 阶段。

与同级包的区别：
- oskh_db: 交易持久化（portfolio.db、execution_log、资金账本）
- oskh_data: 历史行情存储（stock_data_none.duckdb / stock_data_front.duckdb、
  Parquet、日线/分钟线回填）
  交易侧默认使用 ``none``（不复权）—— T-1 不可变，涨停检查/收盘价查询的数据源
  回测侧可使用 ``front``（前复权）—— 需盘后批次重建，用于连续价格指标计算

⚠️ 当前为 MVP 阶段。上线前必须完成 4 项保命红线：
A'. 原子发布+盘中禁写、B'. Redis key 防跨日脏读、
C'. 开盘前覆盖率 fail-close、E'. UPSERT 回填+审计追踪
（小团队精简版，砍掉 ACL 双角色/多层校验/缓存预热/自动降级等过度工程）

后续阶段补全：
- as-of 复权查询、ETL 分层（L0/L1/L2）、配置收敛到 strategy_config、时钟域规范落地
（审计追踪已纳入上线前 E，非后续阶段）

生产环境使用前需评估上述 gap 对交易安全的影响。
"""
from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from oskh_data.downloader import DataDownloader, PeriodDataManager, StockDataManager
    from oskh_data.reader import DEFAULT_READER_MODE, StockDataReader

# 子模块按需导入，避免包初始化时触发不必要的依赖：
#   from oskh_data.cache_port import get_daily_bars_cached, ...
#   from oskh_data.freshness import check_data_freshness
#   from oskh_data.audit import record_run_start, record_run_end, ...
#   from oskh_data.etf_limits import get_etf_limit_pct
#   from oskh_data.etf_backfill import main  # ETF 回填 CLI
#   from oskh_data.download_ops import download_market_data  # QMT → parquet
# CLI: scripts/data/backfill_daily_data.py, scripts/data/update_adjusted_daily.py, ...

__all__ = [
    "StockDataReader",
    "DEFAULT_READER_MODE",
    "DataDownloader",
    "PeriodDataManager",
    "StockDataManager",
]

_LAZY_EXPORTS = {
    "StockDataReader": ("oskh_data.reader", "StockDataReader"),
    "DEFAULT_READER_MODE": ("oskh_data.reader", "DEFAULT_READER_MODE"),
    "DataDownloader": ("oskh_data.downloader", "DataDownloader"),
    "PeriodDataManager": ("oskh_data.downloader", "PeriodDataManager"),
    "StockDataManager": ("oskh_data.downloader", "StockDataManager"),
}


def __getattr__(name: str) -> Any:
    """Preserve root exports without loading DuckDB for lightweight submodules."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
