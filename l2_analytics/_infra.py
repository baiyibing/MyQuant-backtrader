"""Load the optional, pinned offline L2 implementation only when used."""
from __future__ import annotations

from importlib import import_module


def require_l2(module: str):
    try:
        return import_module(f"myquant_infra.l2.{module}")
    except ModuleNotFoundError as exc:
        if exc.name != "myquant_infra" and not exc.name.startswith("myquant_infra."):
            raise
        raise ImportError(
            "Offline L2 requires the optional pinned myquant-infra package. "
            "Install requirements-infra.txt; see "
            "docs/engineering/b3-l2-ingest-infra-switch-20261105.md "
            f"(requested myquant_infra.l2.{module})."
        ) from exc
