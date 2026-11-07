"""Load the optional shared contracts only when a feature is called."""

from importlib import import_module
from types import ModuleType


def require_infra(module: str) -> ModuleType:
    try:
        return import_module(module)
    except ModuleNotFoundError as exc:
        if exc.name != "myquant_infra":
            raise
        raise ImportError(
            "BT signal/provenance features require myquant-infra; install the pinned "
            "optional dependency with your project Python: "
            "python -m pip install -r requirements-infra.txt"
        ) from exc
