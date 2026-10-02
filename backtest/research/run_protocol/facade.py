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


def _csv_simulate(request):
    from .adapters.csv_minute import simulate

    return simulate(request)


def _csv_run(request):
    from .adapters.csv_minute import run

    return run(request)


def _csv_run_cli(request):
    from .adapters.csv_minute import run_cli

    return run_cli(request)


def _v7_simulate(request):
    from .adapters.v7 import simulate_v7

    return simulate_v7(request)


def _v7_run_cli(request):
    from .adapters.v7 import run_cli

    return run_cli(request)


def _grid_modeb_run(request):
    from .adapters.grid_modeb import run_modeb

    return run_modeb(request)


def _grid_modeb_run_cli(request):
    from .adapters.grid_modeb import run_cli

    return run_cli(request)


def _minute_orders_run(request):
    from .adapters.minute_orders import run_minute_orders_research

    return run_minute_orders_research(request)


def _minute_orders_run_with_artifacts(request):
    from .adapters.minute_orders import run_minute_orders_research_with_artifacts

    return run_minute_orders_research_with_artifacts(request)


def _minute_orders_run_cli(request):
    from .adapters.minute_orders import run_cli

    return run_cli(request)


_ENTRIES = MappingProxyType({
    ("joint_return", "native_api", "joint_return_replay.replay"): _replay,
    ("joint_return", "native_api", "joint_return_replay.run_replay"): _run_replay,
    ("joint_return", "native_cli", "scripts/research/run_joint_return_replay.py"): _run_cli,
    ("csv_minute", "native_api", "csv_minute_backtest.simulate"): _csv_simulate,
    ("csv_minute", "native_api", "csv_minute_backtest.run"): _csv_run,
    ("csv_minute", "native_cli", "backtest/research/csv_minute_backtest.py"): _csv_run_cli,
    ("v7", "native_api", "csv_minute_backtest_v7.simulate_v7"): _v7_simulate,
    ("v7", "native_cli", "backtest/research/csv_minute_backtest_v7.py"): _v7_run_cli,
    ("grid_modeb", "native_api", "unified_exit_modeb.run_modeb"): _grid_modeb_run,
    ("grid_modeb", "native_cli", "scripts/research/run_unified_exit_modeb.py"): _grid_modeb_run_cli,
    ("minute_orders_research", "native_api",
     "minute_orders_backend.runner.run_minute_orders_research"): _minute_orders_run,
    ("minute_orders_research", "native_api",
     "minute_orders_backend.runner.run_minute_orders_research_with_artifacts"): _minute_orders_run_with_artifacts,
    ("minute_orders_research", "native_cli",
     "scripts/research/run_minute_orders_research.py"): _minute_orders_run_cli,
})


def run(request: NativeRunRequest) -> NativeRunResult:
    """Delegate once; native API exceptions and launch failures propagate."""
    key = (request.family, request.entry_kind, request.native_entry)
    try:
        handler = _ENTRIES[key]
    except KeyError:
        raise UnregisteredEntryError(f"Unregistered research entry: {key!r}") from None
    return handler(request)
