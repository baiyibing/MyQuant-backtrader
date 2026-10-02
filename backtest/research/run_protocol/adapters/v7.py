"""v7 delegation only; native stages, validators and CLI writers remain owners."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from ..types import OMITTED, ApiResult, CliResult, NativeApiRequest, NativeCliRequest


def simulate_v7(request: NativeApiRequest) -> ApiResult:
    from backtest.research import csv_minute_backtest_v7 as native
    from backtest.research.ashare_volume_cap import BucketVolume
    from backtest.research.participation_rate_precheck import (
        precheck_cli_participation_rate,
        precheck_completed_bucket_samples,
    )

    # P2-B adapter shell only (not simulate / VolumeCap). None → no-op. ≠δ5≠R4.
    rate = request.kwargs.get("participation_rate")
    precheck_cli_participation_rate(rate)
    samples = request.kwargs.get("volume_for_bucket")
    if rate is not None and isinstance(samples, dict):
        clean = {k: v for k, v in samples.items() if isinstance(v, BucketVolume)}
        if clean:
            precheck_completed_bucket_samples(clean)
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
