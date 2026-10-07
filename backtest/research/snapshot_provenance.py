"""Opt-in extraction of recorded G2 provenance; never constructs an identity."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from bt_contract.run_manifest import _identity_mapping


def snapshot_provenance_tokens(sidecar_or_identity) -> dict[str, str]:
    """Read only the supplied JSON sidecar or mapping; absent tokens return {}.

    A str argument is treated as a filesystem path, not inline JSON.
    Invalid JSON/path errors propagate. Invalid token types and absolute host
    paths use RB-09's existing validation. No authenticity or PIT certification.
    """
    identity = sidecar_or_identity
    if isinstance(identity, (str, Path)):
        identity = json.loads(Path(identity).read_text(encoding="utf-8"))
    if not isinstance(identity, Mapping):
        raise TypeError("sidecar_or_identity must be a JSON object or mapping")
    token = identity.get("source_snapshot")
    if token is None or (isinstance(token, str) and not token.strip()):
        return {}
    return _identity_mapping({"source_snapshot": token}, "input_tokens")
