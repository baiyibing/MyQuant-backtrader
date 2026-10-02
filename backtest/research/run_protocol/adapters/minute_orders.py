"""Explicit L2 research delegation; native runner and writer remain owners."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from ..types import OMITTED, ApiResult, CliResult, NativeApiRequest, NativeCliRequest


def _shell_precheck_run_input(run_input) -> None:
    """P2-B adapter shell: rate unit/domain only. ≠δ5≠R4. Not MatchCore."""
    from backtest.research.participation_rate_precheck import (
        precheck_cli_participation_rate,
    )

    rate = getattr(run_input, "participation_rate", None)
    if rate is None:
        return
    precheck_cli_participation_rate(float(rate))


def run_minute_orders_research(request: NativeApiRequest) -> ApiResult:
    from backtest.research.minute_orders_backend import runner as native

    if request.args:
        _shell_precheck_run_input(request.args[0])
    value = native.run_minute_orders_research(*request.args, **request.kwargs)
    return ApiResult(request=request, native_value=value)


def run_minute_orders_research_with_artifacts(request: NativeApiRequest) -> ApiResult:
    from backtest.research.minute_orders_backend import runner as native

    if request.args:
        _shell_precheck_run_input(request.args[0])
    value = native.run_minute_orders_research_with_artifacts(*request.args, **request.kwargs)
    # The native wrapper returns the root for both completed and failed evidence.
    # A returned envelope does not turn its native status into success.
    return ApiResult(request=request, native_value=value, native_artifact_refs=(value.root,))


def run_cli(request: NativeCliRequest) -> CliResult:
    from scripts._script_bootstrap import resolve_oskh_python

    interpreter = resolve_oskh_python().absolute()
    script = Path(__file__).resolve().parents[4] / "scripts/research/run_minute_orders_research.py"
    context = {}
    if request.context.cwd is not OMITTED:
        context["cwd"] = request.context.cwd
    if request.context.env_overlay is not OMITTED:
        context["env"] = dict(os.environ)
        context["env"].update(request.context.env_overlay)
    process = subprocess.run(
        [str(interpreter), str(script), *request.argv],
        capture_output=True, check=False, **context,
    )
    return CliResult(request=request, native_exit_status=process.returncode,
                     stdout_bytes=process.stdout, stderr_bytes=process.stderr)
