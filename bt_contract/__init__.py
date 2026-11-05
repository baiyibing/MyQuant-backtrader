"""Import-safe research contract facades; feature calls require optional infra."""

from .signal_bundle import canonical_json_bytes, validate_signal_bundle

__all__ = ["canonical_json_bytes", "validate_signal_bundle"]
