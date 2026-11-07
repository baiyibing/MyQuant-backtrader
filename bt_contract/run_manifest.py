"""Lazy BT provenance facade; fee labels remain labels, with no engine import."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ._infra import require_infra
from .signal_bundle import canonical_json_bytes

__all__ = [
    "build_bt_run_manifest", "canonical_json_bytes", "validate_bt_run_manifest",
    "write_bt_run_manifest", "write_run_identity_sidecar",
]


def _identity_mapping(value: Any, field: str) -> dict[str, str]:
    """Keep the existing snapshot-provenance caller on the shared validator."""
    return require_infra("myquant_infra.artifacts.provenance")._identity_mapping(value, field)


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
    book_rule_revision: str | None = None,
    pool_identity: str | None = None,
    price_domain: str | None = None,
    input_tokens: Mapping[str, str] | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Delegate explicit flags and artifacts without discovering inputs."""
    return require_infra("myquant_infra.artifacts.provenance").build_bt_run_manifest(
        strategy=strategy, dividend_type=dividend_type, config=config, artifacts=artifacts,
        fee_schedule=fee_schedule, participation_rate=participation_rate,
        signal_bundle_sha256=signal_bundle_sha256, git_commit=git_commit,
        book_rule_revision=book_rule_revision, pool_identity=pool_identity,
        price_domain=price_domain, input_tokens=input_tokens, environment=environment,
    )


def validate_bt_run_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate the existing BT dialect through infra, without reading inputs."""
    return require_infra("myquant_infra.artifacts.provenance").validate_bt_run_manifest(manifest)


def write_bt_run_manifest(path: str | Path, **kwargs: Any) -> dict[str, Any]:
    """Write canonical JSON; omitted git_commit still refers to this BT repo."""
    return require_infra("myquant_infra.artifacts.provenance").write_bt_run_manifest(
        path, repo_root=Path(__file__).resolve().parents[1], **kwargs,
    )


def write_run_identity_sidecar(path: str | Path, manifest: Mapping[str, Any]) -> None:
    """Write only the supplied sidecar, with no git or input discovery."""
    return require_infra("myquant_infra.artifacts.provenance").write_run_identity_sidecar(
        path, manifest,
    )
