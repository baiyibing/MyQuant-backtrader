#!/usr/bin/env python3
"""分钟线增量回填（可断点续传）。用法: python -m oskh_data.minute_backfill

断点续传机制：
    中断后重新运行会自动从上次位置继续。
    进度保存在 stock_data/.backfill_1m_progress.json（已完成股票代码列表）。

实际执行委托给 oskh_data.backfill --period 1m，本模块仅为 CLI 提供便捷的入口名。
"""
from __future__ import annotations

import sys

from oskh_data.backfill import main

if __name__ == "__main__":
    main(argv=["--period", "1m"] + sys.argv[1:])
