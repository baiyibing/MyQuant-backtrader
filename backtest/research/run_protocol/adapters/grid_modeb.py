"""grid_modeb delegation only; the native exit grid and reports remain owners."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from ..types import OMITTED, ApiResult, CliResult, NativeApiRequest, NativeCliRequest


def run_modeb(request: NativeApiRequest) -> ApiResult:
    # CLI dispatch leaves engine dependencies to the configured child interpreter.
    from backtest.research.unified_exit_modeb import run_modeb as _native_run_modeb

    value = _native_run_modeb(*request.args, **request.kwargs)
    # Native returns a dict, not writer paths; reports are its own side effect.
    return ApiResult(request=request, native_value=value)


def run_cli(request: NativeCliRequest) -> CliResult:
    from scripts._script_bootstrap import resolve_oskh_python

    # Anchor in the caller's cwd before applying the child's cwd, preserving
    # virtualenv symlinks with absolute(), as in the JR/CSV/v7 adapters.
    interpreter = resolve_oskh_python().absolute()
    script = Path(__file__).resolve().parents[4] / "scripts/research/run_unified_exit_modeb.py"
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
