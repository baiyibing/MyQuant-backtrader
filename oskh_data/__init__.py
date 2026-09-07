# -*- coding: utf-8 -*-
"""Local market-data *read* infrastructure.

This fork does not download from QMT. Bars, adj factors, and float-share
sidecars are produced by the original repo and consumed via path-SSOT.
"""
from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from oskh_data.period_schema import PeriodDataManager, StockDataManager
    from oskh_data.reader import DEFAULT_READER_MODE, StockDataReader

__all__ = [
    "StockDataReader",
    "DEFAULT_READER_MODE",
    "PeriodDataManager",
    "StockDataManager",
]

_LAZY_EXPORTS = {
    "StockDataReader": ("oskh_data.reader", "StockDataReader"),
    "DEFAULT_READER_MODE": ("oskh_data.reader", "DEFAULT_READER_MODE"),
    "PeriodDataManager": ("oskh_data.period_schema", "PeriodDataManager"),
    "StockDataManager": ("oskh_data.period_schema", "StockDataManager"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
