"""Lazy facade for the shared ``myquant.signal-bundle/1`` contract.

Infra owns validation and canonical UTF-8 JSON, including the trailing LF used
in v1 hashes. Importing this module does not require the private dependency.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ._infra import require_infra

SCHEMA = "myquant.signal-bundle/1"
__all__ = ["SCHEMA", "build_signal_bundle", "canonical_json_bytes", "validate_signal_bundle"]


def canonical_json_bytes(value: Any) -> bytes:
    """Use infra's v1 canonical bytes; no host hashing fallback exists."""
    return require_infra("myquant_infra.contracts.signal_bundle").canonical_json_bytes(value)


def validate_signal_bundle(
    bundle: Mapping[str, Any], *, files_root: str | Path | None = None,
) -> None:
    """Validate metadata and, when requested, explicit pool-file digests."""
    return require_infra("myquant_infra.contracts.signal_bundle").validate_signal_bundle(
        bundle, files_root=files_root,
    )


def build_signal_bundle(
    rows: Sequence[Mapping[str, Any]],
    *,
    signal_asof_policy: str = "pred_minus_one",
    availability: str = "unproven",
    available_at: str | None = None,
    price_domain: str = "unspecified",
) -> dict[str, Any]:
    """Build from caller-selected rows using the existing shared v1 API."""
    return require_infra("myquant_infra.contracts.signal_bundle").build_signal_bundle(
        rows, signal_asof_policy=signal_asof_policy, availability=availability,
        available_at=available_at, price_domain=price_domain,
    )
