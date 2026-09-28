"""Public L1 types and lazy one-shot run entry; importing loads no engines."""

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
]


def __getattr__(name):
    # Keep the S0 types-only import contract; load the facade only on access.
    if name == "run":
        from .facade import run

        return run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
