"""Load infra implementations without vendored fallbacks."""
from __future__ import annotations

from importlib import import_module
from types import ModuleType


def require_infra(module: str) -> ModuleType:
    try:
        return import_module(f"myquant_infra.{module}")
    except ImportError as exc:
        raise ImportError(
            "This path requires the myquant-infra package. "
            "Install requirements.txt (including requirements-infra.txt); see README.md "
            f"(requested myquant_infra.{module})."
        ) from exc
