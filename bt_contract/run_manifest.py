"""Opt-in run provenance; records fee labels without importing engine code."""

from __future__ import annotations

import hashlib
import math
import re
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .signal_bundle import canonical_json_bytes


def _json_config(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {key: _json_config(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_config(item) for item in value]
    return value


def build_bt_run_manifest(
    *,
    strategy: str,
    dividend_type: str,
    config: Mapping[str, Any],
    artifacts: Iterable[str | Path] = (),
    fee_schedule: str = "BILATERAL_10BP",
    participation_rate: float | None = None,
    signal_bundle_sha256: str | None = None,
    git_commit: str = "UNKNOWN",
) -> dict[str, Any]:
    """Hash resolved flags and caller-supplied artifacts, without changing them.

    Paths in config are serialized as POSIX strings. The config contains flags,
    not this manifest. No pool sidecars or market data are discovered here.
    """
    if not isinstance(strategy, str) or not isinstance(git_commit, str):
        raise TypeError("strategy and git_commit must be strings")
    if dividend_type not in ("none", "front", "back"):
        raise ValueError("invalid dividend_type")
    if fee_schedule not in ("BILATERAL_10BP", "QLIB_PORTANA"):
        raise ValueError("invalid fee_schedule")
    if not isinstance(config, Mapping):
        raise TypeError("config must be a mapping")
    if participation_rate is not None:
        if (
            isinstance(participation_rate, bool)
            or not isinstance(participation_rate, (int, float))
            or not math.isfinite(participation_rate)
            or not 0 <= participation_rate <= 1
        ):
            raise ValueError("participation_rate must be finite and in [0, 1]")
        participation_rate = float(participation_rate)
    if signal_bundle_sha256 is not None and (
        not isinstance(signal_bundle_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", signal_bundle_sha256) is None
    ):
        raise ValueError("invalid signal_bundle_sha256")
    artifact_rows = []
    for artifact in artifacts:
        path = Path(artifact)
        data = path.read_bytes()
        artifact_rows.append({
            "path": path.as_posix(),
            "md5": hashlib.md5(data).hexdigest(),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    return {
        "schema": "myquant.bt-run/1",
        "git_commit": git_commit,
        "strategy": strategy,
        "dividend_type": dividend_type,
        "fee_schedule": fee_schedule,
        "liquidity_cap": "off" if participation_rate is None else "on",
        "participation_rate": participation_rate,
        "signal_bundle_sha256": signal_bundle_sha256,
        "config_sha256": hashlib.sha256(canonical_json_bytes(_json_config(config))).hexdigest(),
        "artifacts": artifact_rows,
    }


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1],
            stderr=subprocess.DEVNULL, text=True, timeout=5,
        ).strip() or "UNKNOWN"
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


def write_bt_run_manifest(path: str | Path, **kwargs: Any) -> dict[str, Any]:
    """Write canonical UTF-8 JSON; capture local git provenance when not supplied."""
    if "git_commit" not in kwargs:
        kwargs["git_commit"] = _git_commit()
    manifest = build_bt_run_manifest(**kwargs)
    Path(path).write_bytes(canonical_json_bytes(manifest))
    return manifest
