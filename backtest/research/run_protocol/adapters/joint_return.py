"""JR delegation only; native validation, expansion and writers remain owners."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from ..types import OMITTED, ApiResult, CliResult, NativeApiRequest, NativeCliRequest


def replay(request: NativeApiRequest) -> ApiResult:
    from backtest.research import joint_return_replay as native

    value = native.replay(*request.args, **request.kwargs)
    return ApiResult(request=request, native_value=value)


def run_replay(request: NativeApiRequest) -> ApiResult:
    from backtest.research import joint_return_replay as native

    value = native.run_replay(*request.args, **request.kwargs)
    # The native writer returns its completed run directory. Do not discover
    # files or guess optional profiling sidecars from the request.
    return ApiResult(request=request, native_value=value, native_artifact_refs=(value,))


def run_cli(request: NativeCliRequest) -> CliResult:
    from scripts._script_bootstrap import resolve_oskh_python

    # Anchor a relative interpreter in the caller's cwd before applying the
    # child's cwd; absolute() preserves virtualenv symlinks (resolve() does not).
    interpreter = resolve_oskh_python().absolute()
    script = Path(__file__).resolve().parents[4] / "scripts/research/run_joint_return_replay.py"
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
