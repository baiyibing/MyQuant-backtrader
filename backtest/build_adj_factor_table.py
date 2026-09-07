"""兼容重导出：新代码请直接从 oskh_data 导入。

.. code-block:: python

    from oskh_data.adj_factor import build_for_symbol, main
"""
from __future__ import annotations

from oskh_data.adj_factor import build_for_symbol, main  # noqa: F401

__all__ = ["build_for_symbol", "main"]
