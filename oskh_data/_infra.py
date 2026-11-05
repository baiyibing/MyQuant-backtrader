"""Lazy optional infra dependency; unrelated host imports need no lake extras."""
from __future__ import annotations

from importlib import import_module
from types import ModuleType


def require_infra(module: str) -> ModuleType:
    try:
        return import_module(f"myquant_infra.{module}")
    except ImportError as exc:
        raise ImportError(
            "This lake/DuckDB path requires the optional myquant-infra package. "
            "Install via requirements-infra.txt / docs/engineering/k18-duckdb-infra-switch-20261105.md "
            f"(requested myquant_infra.{module})."
        ) from exc
