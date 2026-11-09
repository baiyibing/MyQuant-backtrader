"""Invoke an explicitly configured ops checkout; no local runtime fallback."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRIES = frozenset({
    "scripts/run/run_multi_ai_review.py",
    "scripts/run/run_codex_adversarial_lanes.py",
    "scripts/ops/push_github_pr_via_api.py",
})


def run_ops(entry: str, argv: list[str] | None = None, *, profile: str | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--ops-root", help="explicit grok-bot-ops checkout")
    config, remaining = parser.parse_known_args(argv)
    if any(arg.split("=", 1)[0] in {"--repo-root", "--profile-file"} for arg in remaining):
        raise SystemExit("BT injects --repo-root/--profile-file; call ops directly for another repository")
    configured = config.ops_root or os.environ.get("MYQUANT_OPS_ROOT")
    if not configured:
        raise SystemExit("required ops runtime missing: set MYQUANT_OPS_ROOT or pass --ops-root")
    root = Path(configured).expanduser()
    if not root.is_absolute():
        raise SystemExit("MYQUANT_OPS_ROOT / --ops-root must be an absolute checkout path")
    root = root.resolve()
    try:
        api = json.loads((root / "scripts/runtime-api.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"ops runtime API v1 required at {root}; update grok-bot-ops") from exc
    source = root / entry
    if (entry not in ENTRIES or not isinstance(api, dict) or api.get("schema_version") != 1
            or entry not in api.get("entries", []) or not source.is_file()
            or not source.resolve().is_relative_to(root)):
        raise SystemExit(f"incompatible or missing ops runtime entry: {entry}")
    command = [sys.executable, str(source), "--repo-root", str(REPO_ROOT)]
    if profile is not None:
        command.extend(("--profile-file", str(REPO_ROOT / profile)))
    return subprocess.call(command + remaining, cwd=REPO_ROOT)
