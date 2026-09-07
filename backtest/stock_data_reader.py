"""
兼容重导出：新代码请直接从 oskh_data 导入。

.. code-block:: python

    from oskh_data import StockDataReader, DEFAULT_READER_MODE
"""
from __future__ import annotations

from oskh_data.reader import (  # noqa: F401
    DEFAULT_READER_MODE,
    StockDataReader,
)

__all__ = ["StockDataReader", "DEFAULT_READER_MODE"]
