"""One-shot dispatch to explicitly registered native research entries."""

from __future__ import annotations

from types import MappingProxyType

from .types import NativeRunRequest, NativeRunResult


class UnregisteredEntryError(LookupError):
    """The requested family/transport/entry has no approved adapter."""


def _replay(request):
    from .adapters.joint_return import replay

    return replay(request)


def _run_replay(request):
    from .adapters.joint_return import run_replay

    return run_replay(request)


def _run_cli(request):
    from .adapters.joint_return import run_cli

    return run_cli(request)


_ENTRIES = MappingProxyType({
    ("joint_return", "native_api", "joint_return_replay.replay"): _replay,
    ("joint_return", "native_api", "joint_return_replay.run_replay"): _run_replay,
    ("joint_return", "native_cli", "scripts/research/run_joint_return_replay.py"): _run_cli,
})


def run(request: NativeRunRequest) -> NativeRunResult:
    """Delegate once; native API exceptions and launch failures propagate."""
    key = (request.family, request.entry_kind, request.native_entry)
    try:
        handler = _ENTRIES[key]
    except KeyError:
        raise UnregisteredEntryError(f"Unregistered research entry: {key!r}") from None
    return handler(request)
