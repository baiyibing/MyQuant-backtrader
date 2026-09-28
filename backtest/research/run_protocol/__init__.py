"""Public L1 types with lazy run/views access; importing loads no engines."""

from .types import (
    OMITTED,
    ApiExceptionResult,
    ApiResult,
    CallerContext,
    CliContext,
    CliResult,
    EntryKind,
    Family,
    NativeApiRequest,
    NativeCliRequest,
    NativeRunRequest,
    NativeRunResult,
    NotRunResult,
    Omitted,
)

_VIEW_EXPORTS = (
    "Provenance", "Evidence", "Projection", "OrderView", "FillView",
    "PortfolioView", "AccountPortfolioView", "GridInstancePortfolioView",
    "GridSpecPortfolioView", "TimeEvidence", "project_orders", "project_fills",
    "project_portfolio", "project_time_evidence",
)

__all__ = [
    "OMITTED",
    "ApiExceptionResult",
    "ApiResult",
    "CallerContext",
    "CliContext",
    "CliResult",
    "EntryKind",
    "Family",
    "NativeApiRequest",
    "NativeCliRequest",
    "NativeRunRequest",
    "NativeRunResult",
    "NotRunResult",
    "Omitted",
    "run",
    *_VIEW_EXPORTS,
]


def __getattr__(name):
    # Keep the S0 types-only import contract; load the facade only on access.
    if name == "run":
        from .facade import run

        return run
    if name in _VIEW_EXPORTS:
        from . import views

        return getattr(views, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
