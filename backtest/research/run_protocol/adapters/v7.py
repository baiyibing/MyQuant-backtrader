"""v7 delegation only; native stages, validators and CLI writers remain owners."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from ..types import OMITTED, ApiResult, CliResult, NativeApiRequest, NativeCliRequest


def simulate_v7(request: NativeApiRequest) -> ApiResult:
    from backtest.research import csv_minute_backtest_v7 as native

    value = native.simulate_v7(*request.args, **request.kwargs)
    # SimResult has no writer path; the full writer belongs to the native CLI.
    return ApiResult(request=request, native_value=value)


def run_cli(request: NativeCliRequest) -> CliResult:
    from scripts._script_bootstrap import resolve_oskh_python

    # Anchor in the caller's cwd before applying the child's cwd. Preserve
    # virtualenv symlinks with absolute(), as in the JR/CSV adapters.
    interpreter = resolve_oskh_python().absolute()
    script = Path(__file__).resolve().parents[4] / "backtest/research/csv_minute_backtest_v7.py"
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
