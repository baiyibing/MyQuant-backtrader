"""Invoke an explicitly configured ops checkout; no local runtime fallback."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import NoReturn

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRIES = frozenset({
    "scripts/run/run_multi_ai_review.py",
    "scripts/run/run_codex_adversarial_lanes.py",
    "scripts/ops/push_github_pr_via_api.py",
})
REVIEW_ENTRY = "scripts/run/run_multi_ai_review.py"
REVIEW_CAPABILITIES = frozenset({"review-protocol-v2", "domain-profile-v2", "repo-machine-entry-scopes"})


def fail(message: str) -> NoReturn:
    print("[ops-runtime] " + message, file=sys.stderr)
    raise SystemExit(2)


def run_ops(entry: str, argv: list[str] | None = None, *, profile: str | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--ops-root", help="explicit grok-bot-ops checkout")
    config, remaining = parser.parse_known_args(argv)
    for arg in remaining:
        name = arg.split("=", 1)[0]
        if name.startswith("--") and len(name) > 2 and any(option.startswith(name) for option in ("--repo-root", "--profile-file")):
            fail("BT injects --repo-root/--profile-file; call ops directly for another repository")
    configured = config.ops_root or os.environ.get("MYQUANT_OPS_ROOT")
    if not configured:
        fail("required ops runtime missing: set MYQUANT_OPS_ROOT or pass --ops-root")
    root = Path(configured).expanduser()
    if not root.is_absolute():
        fail("MYQUANT_OPS_ROOT / --ops-root must be an absolute checkout path")
    root = root.resolve()
    try:
        api = json.loads((root / "scripts/runtime-api.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail(f"ops runtime API v1 required at {root}; update grok-bot-ops ({type(exc).__name__})")
    source = root / entry
    if (entry not in ENTRIES or not isinstance(api, dict) or type(api.get("schema_version")) is not int or api.get("schema_version") != 1
            or not isinstance(api.get("entries"), list) or not all(isinstance(e, str) for e in api["entries"])
            or entry not in api["entries"] or not source.is_file()
            or not source.resolve().is_relative_to(root)):
        fail(f"incompatible or missing ops runtime entry: {entry}")
    scopes, capabilities = api.get("entry_scopes", {}), api.get("capabilities", [])
    if not isinstance(scopes, dict) or scopes.get(entry, "repo") != "repo":
        fail("BT entries require repo scope")
    if entry == REVIEW_ENTRY and (scopes.get(entry) != "repo" or not isinstance(capabilities, list)
            or not all(isinstance(c, str) for c in capabilities) or not REVIEW_CAPABILITIES.issubset(capabilities)):
        fail("BT domain profile v2 requires updated ops review-protocol-v2/domain-profile-v2")
    command = [sys.executable, str(source), "--repo-root", str(REPO_ROOT)]
    if profile is not None:
        profile_path = (REPO_ROOT / profile).resolve()
        if not profile_path.is_relative_to(REPO_ROOT) or not profile_path.is_file():
            fail("BT profile must be an existing host-owned file")
        command.extend(("--profile-file", str(profile_path)))
    return subprocess.call(command + remaining, cwd=REPO_ROOT)
