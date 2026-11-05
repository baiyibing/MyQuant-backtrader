"""BT compatibility exports for infra's offline Hithink artifact consumer.

Artifact IO requires optional requirements-infra.txt. The small validation/JSON
helpers used by BT's economics gate remain usable without that private package.
No artifact parser, probe validator or downloader is implemented in this host.
"""
from __future__ import annotations

try:
    from myquant_infra.hithink.artifacts import (
        ERRORS, FILES, canonical_json, proves_empty, read_artifact, read_json,
        request_identity, validate_probes,
    )
    from myquant_infra.hithink.export import (
        DUMP_ENDPOINT, EVENT_ENDPOINT, IDENTITY_ENDPOINT, NUMBERS,
        QUARANTINE_POLICY, SHANGHAI, SOURCE, FILES as PAYLOAD_FILES,
        code, day, digest, inspect_dump, number, present_codes,
    )
except ModuleNotFoundError as exc:
    # Only an absent optional package permits stubs. An incomplete installed
    # package or a missing public symbol must surface instead of falling back.
    if exc.name != "myquant_infra":
        raise

    from datetime import date
    from decimal import Decimal
    import hashlib
    import json
    from pathlib import Path
    import re
    from zoneinfo import ZoneInfo

    import pyarrow as pa

    SOURCE = "hithink:market-dumps/adjustment-factors"
    DUMP_ENDPOINT = "/api/dump/market-dumps/adjustment-factors/download-url"
    IDENTITY_ENDPOINT = "/api/meta/tickers/search"
    EVENT_ENDPOINT = "/api/a-share/corporate-actions/adjustment-factors"
    PAYLOAD_FILES = ("hithink_dump.parquet", "probes.json")
    FILES = (*PAYLOAD_FILES, "manifest.json", "COMMITTED.json")
    QUARANTINE_POLICY = "negative_amounts_outside_window_v1"
    NUMBERS = ("dividend_per_share", "per_share_bonus", "allotment_ratio", "allotment_price")
    SHANGHAI = ZoneInfo("Asia/Shanghai")
    ERRORS = {"redirect_blocked", "invalid_https_url", "credential_origin_blocked", "http_error",
              "transfer_budget_exceeded", "response_too_large", "transport_error", "invalid_json_envelope",
              "business_error", "invalid_data", "skipped_after_vendor_stop"}

    def digest(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def read_json(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def canonical_json(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def code(value):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{6}\.(SH|SZ|BJ)", value):
            raise ValueError("invalid A-share code")
        return value

    def day(value):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("expected ISO calendar date")
        return date.fromisoformat(value)

    def number(value, *, allow_negative=False):
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError("adjustment amount must be numeric")
        value = Decimal(str(value))
        if not value.is_finite() or (value < 0 and not allow_negative):
            raise ValueError("adjustment amount must be finite and nonnegative")
        pa.scalar(value, type=pa.decimal128(24, 12))
        return value

    def _missing_infra(*args, **kwargs):
        raise ImportError(
            "Offline Hithink artifact import requires optional myquant-infra. "
            "Install requirements-infra.txt; see "
            "docs/engineering/b7-hithink-artifact-infra-switch-20261105.md."
        )

    inspect_dump = present_codes = request_identity = _missing_infra
    validate_probes = proves_empty = read_artifact = _missing_infra

# Historical BT spelling; infra calls the same parser inspect_dump.
parse_dump = inspect_dump

__all__ = [
    "SOURCE", "DUMP_ENDPOINT", "IDENTITY_ENDPOINT", "EVENT_ENDPOINT", "FILES",
    "PAYLOAD_FILES", "QUARANTINE_POLICY", "NUMBERS", "SHANGHAI", "ERRORS",
    "digest", "read_json", "canonical_json", "code", "day", "number",
    "parse_dump", "inspect_dump", "present_codes", "request_identity",
    "validate_probes", "proves_empty", "read_artifact",
]
