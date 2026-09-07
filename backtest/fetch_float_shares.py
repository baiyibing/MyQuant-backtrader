"""兼容重导出：新代码请直接从 oskh_data 导入。

.. code-block:: python

    from oskh_data.float_shares import main, collect_from_daily_data
"""
from __future__ import annotations

from oskh_data.float_shares import collect_from_daily_data, main  # noqa: F401

__all__ = ["main", "collect_from_daily_data"]
