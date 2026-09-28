"""CSV delegation only; native loaders, validators and CLI writers remain owners."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from ..types import OMITTED, ApiResult, CliResult, NativeApiRequest, NativeCliRequest


def simulate(request: NativeApiRequest) -> ApiResult:
    from backtest.research import csv_minute_backtest as native

    value = native.simulate(*request.args, **request.kwargs)
    return ApiResult(request=request, native_value=value)


def run(request: NativeApiRequest) -> ApiResult:
    from backtest.research import csv_minute_backtest as native

    value = native.run(*request.args, **request.kwargs)
    # Both APIs return SimState; the full writer belongs to the native CLI.
    return ApiResult(request=request, native_value=value)


def run_cli(request: NativeCliRequest) -> CliResult:
    from scripts._script_bootstrap import resolve_oskh_python

    # Anchor in the caller's cwd before applying the child's cwd. Preserve
    # virtualenv symlinks with absolute(), as in the JR adapter.
    interpreter = resolve_oskh_python().absolute()
    script = Path(__file__).resolve().parents[4] / "backtest/research/csv_minute_backtest.py"
    context = {}
    if request.context.cwd is not OMITTED:
        context["cwd"] = request.context.cwd
    if request.context.env_overlay is not OMITTED:
        context["env"] = dict(os.environ)
        context["env"].update(request.context.env_overlay)
    process = subprocess.run(
        [str(interpreter), str(script), *request.argv],
        capture_output=True,
        check=False,
        **context,
    )
    return CliResult(
        request=request,
        native_exit_status=process.returncode,
        stdout_bytes=process.stdout,
        stderr_bytes=process.stderr,
    )
