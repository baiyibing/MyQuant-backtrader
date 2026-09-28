"""L1-S0: inert, shallow envelopes for one whole native research run.

Human Q1: first consumer / first certification scope = joint_return Mode B 入口.
The first adapter slice targets the joint_return family; exact Mode B native
symbols (and any adjacent grid_modeb scope) await that slice's Human GO.
Family tags describe identity, not registration or certified availability.

API and CLI are separate transports, never converted. A future adapter must
delegate once, preserve native mutations, and re-raise the original API exception
(including SystemExit). Exception envelopes are observations, not substitutes for
raising. S0 implements no delegation, entry lookup, validation of native arguments,
context switching, output discovery, or success inference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from os import PathLike
from typing import Literal, Mapping, TypeAlias


Family: TypeAlias = Literal["csv_minute", "v7", "joint_return", "grid_modeb"]
EntryKind: TypeAlias = Literal["native_api", "native_cli"]


class Omitted(Enum):
    """Protocol metadata was not supplied; never a native argument default."""

    VALUE = "omitted"


OMITTED = Omitted.VALUE


@dataclass(frozen=True, kw_only=True)
class CallerContext:
    """API always uses the caller's cwd/env; no snapshot or overrides."""

    kind: Literal["caller"] = field(default="caller", init=False)


@dataclass(frozen=True, kw_only=True)
class CliContext:
    """Future child-only overrides; omitted fields inherit the caller's context.

    Supplied cwd is kept literally, with no path resolution. env_overlay only
    carries explicit string overrides (including empty strings), not deletions
    or a snapshot of the parent's environment. No context is applied here.
    """

    cwd: str | PathLike[str] | Omitted = OMITTED
    env_overlay: Mapping[str, str] | Omitted = field(default=OMITTED, repr=False)


@dataclass(frozen=True, kw_only=True)
class NativeApiRequest:
    """Original call payload, retained by reference without default filling.

    A missing kwargs key means omitted; a present key keeps None, False or an
    empty value unchanged. args/kwargs and their contents are not copied/frozen.
    native_entry is an opaque identifier, to be checked against a future static
    adapter whitelist; this type neither resolves nor registers it.
    """

    family: Family
    native_entry: str
    args: tuple[object, ...] = ()
    kwargs: Mapping[str, object] = field(default_factory=dict)
    context: CallerContext = field(default_factory=CallerContext, init=False)
    entry_kind: Literal["native_api"] = field(default="native_api", init=False)


@dataclass(frozen=True, kw_only=True)
class NativeCliRequest:
    """Native argument tokens, excluding the interpreter and entry launcher.

    The future whitelist identifies the script/module via native_entry; argv is
    its untouched argument tail. Order, duplicates and path literals are kept
    by reference. No shell parsing, API conversion or interpreter selection here.
    """

    family: Family
    native_entry: str
    argv: list[str] | tuple[str, ...]
    context: CliContext = field(default_factory=CliContext)
    entry_kind: Literal["native_cli"] = field(default="native_cli", init=False)


NativeRunRequest: TypeAlias = NativeApiRequest | NativeCliRequest


@dataclass(frozen=True, kw_only=True)
class NotRunResult:
    """Explicit absence of execution; contains no fabricated native outcome."""

    request: NativeRunRequest
    status: Literal["not_run"] = field(default="not_run", init=False)


@dataclass(frozen=True, kw_only=True)
class ApiResult:
    """Observation of a native return, including an explicitly returned None.

    native_value is required and retained by reference. Artifact references may
    only come from the real writer or an explicit output request: OMITTED means
    unknown/unreported; () explicitly reports no artifacts. No directory scan.
    """

    request: NativeApiRequest
    native_value: object
    native_artifact_refs: tuple[str | PathLike[str], ...] | Omitted = OMITTED
    status: Literal["returned"] = field(default="returned", init=False)


@dataclass(frozen=True, kw_only=True)
class ApiExceptionResult:
    """Observation retaining exception identity; a future API must still raise.

    This is never an empty successful return or a wrapped replacement exception.
    Construction does not catch, raise, retry, or alter cause/context/traceback.
    """

    request: NativeApiRequest
    native_exception: BaseException
    status: Literal["raised"] = field(default="raised", init=False)


@dataclass(frozen=True, kw_only=True)
class CliResult:
    """Observation of an exited child, with required native status and streams.

    Nonzero/negative statuses and raw bytes remain native; no success boolean.
    A process-launch failure is not a native exit and must not use this shape.
    Artifact-reference omission has the same meaning as in ApiResult.
    """

    request: NativeCliRequest
    native_exit_status: int
    stdout_bytes: bytes
    stderr_bytes: bytes
    native_artifact_refs: tuple[str | PathLike[str], ...] | Omitted = OMITTED
    status: Literal["exited"] = field(default="exited", init=False)


NativeRunResult: TypeAlias = NotRunResult | ApiResult | ApiExceptionResult | CliResult
