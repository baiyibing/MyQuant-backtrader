"""兼容重导出：新代码请直接从 oskh_data 导入。

.. code-block:: python

    from oskh_data.backfill import main, rebuild_duckdb
"""
from __future__ import annotations

from oskh_data.backfill import main  # noqa: F401

__all__ = ["main"]
