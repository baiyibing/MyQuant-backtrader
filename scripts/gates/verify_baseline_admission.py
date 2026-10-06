#!/usr/bin/env python3
"""Data-free, read-only overlay schema and pandas triple-anchor admission."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gates.verify_book_admission import format_coverage_failure
from scripts.research import generate_off_byte_baseline as baseline

AUTHORIZED_PANDAS = "3.0.6"
SCOPED_OVERLAYS = (
    "S8", "V61", "V91", "V92", "V6F", "S12", "S9", "P03", "P04", "P05",
    "P06",
)
REQUIRED_KEYS = (
    "rule_revision", "books", "cases", "captured_environment", "contract",
    "historical_raw_sha256", "historical_canonical_sha256",
)


def manifest_errors(path: Path, manifest: object, *, overlay: bool) -> list[str]:
    """Return schema diagnostics without invoking loaders or simulations."""
    if not isinstance(manifest, dict):
        return [f"{path}: manifest must be a JSON object"]
    errors = [f"{path}: missing required key {key}" for key in REQUIRED_KEYS
              if overlay and key not in manifest]
    environment = manifest.get("captured_environment")
    if not isinstance(environment, dict) or not isinstance(environment.get("pandas"), str):
        errors.append(f"{path}: captured_environment.pandas must be present (string)")
    return errors


def main() -> int:
    try:
        baseline.assert_baseline_coverage()
    except AssertionError as error:
        print(format_coverage_failure(error))
        return 1

    errors = []
    anchors = []
    for name in ("HISTORICAL", *SCOPED_OVERLAYS):
        path = baseline.GOLDEN if name == "HISTORICAL" else getattr(baseline, f"{name}_GOLDEN")
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            errors.append(f"{path}: cannot read manifest: {error}")
            continue
        errors.extend(manifest_errors(path, manifest, overlay=name != "HISTORICAL"))
        if isinstance(manifest, dict) and isinstance(manifest.get("captured_environment"), dict):
            anchors.append((str(path), manifest["captured_environment"].get("pandas")))

    requirements = ROOT / "requirements.txt"
    workflow = ROOT / ".github/workflows/python-tests.yml"
    try:
        pins = re.findall(r"^\s*pandas\s*==\s*([^\s#;]+)\s*(?:#.*)?$",
                          requirements.read_text(encoding="utf-8"), re.MULTILINE)
        if pins != [AUTHORIZED_PANDAS]:
            errors.append(f"{requirements}: expected single pandas=={AUTHORIZED_PANDAS} pin; found {pins}")
        assertion = f"pandas.__version__ == '{AUTHORIZED_PANDAS}'"
        if assertion not in workflow.read_text(encoding="utf-8"):
            errors.append(f"{workflow}: missing workflow assert string {assertion}")
    except OSError as error:
        errors.append(f"pandas triple-anchor: cannot read anchor: {error}")
    for source, version in anchors:
        if version != AUTHORIZED_PANDAS:
            errors.append(f"{source}: captured_environment.pandas={version!r}; expected {AUTHORIZED_PANDAS}")

    print("Record note: generate_off_byte_baseline docstring / --record-* behavior refuses overwrite of existing overlays; new revision uses a new file and revision id.")
    if errors:
        for error in errors:
            print(f"FAIL: baseline admission overlay schema / pandas triple-anchor: {error}")
        print("Changing the pandas pin requires an independent re-anchor ticket; do not auto-fix anchors or goldens.")
        return 1
    print(f"OK: baseline coverage, overlay schema ({len(SCOPED_OVERLAYS)} scoped overlays), pandas triple-anchor == {AUTHORIZED_PANDAS}; no simulations or golden writes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
