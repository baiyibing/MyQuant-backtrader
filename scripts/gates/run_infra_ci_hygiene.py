#!/usr/bin/env python3
"""Optional, additive infra encoding/secret/link checks for a BT checkout.

Use a local git archive of the requirements-infra.txt pin via --infra-root.
No downloads, application imports, hook installation or automatic fixes occur.
live_trading/ and trade_decision/ are excluded; host gates remain authoritative.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA_PIN = "1a497682258503bf748e1e873aea9be9a818e92e"
# scripts/ci is source-only. Verify every script before executing any of them;
# a clone's HEAD alone cannot detect edits to its working-tree source.
SCRIPT_HASHES = {
    "check_repo_hygiene": "3c6a7a26cb3796aabc5707d4d675e40ca8baf6cef5d5014192a8de1446026e2a",
    # File digest of scripts/ci/scan_secrets.py at INFRA_PIN — not a credential.
    "scan_secrets": "6b6d26ccf1a7df589f1f8184e1e16071eab3cb5ae6300fff9420fe99b408515f",  # gitleaks:allow
    "check_md_links": "338980b301231721671921a01a83f9310d150e48b206e7cab96323b6a4e06b1b",
}
EXCLUDED_PARTS = frozenset({"live_trading", "trade_decision"})


def load_scripts(infra_root: Path | None) -> dict[str, ModuleType]:
    hint = (
        f"Use requirements-infra.txt (pin {INFRA_PIN}); "
        "materialize that pin with git archive from a local MyQuant-infra clone, "
        "then pass --infra-root <archive-root>. A wheel alone lacks scripts/ci. "
        "See docs/engineering/b9-ci-hygiene-infra-adopt-20261106.md."
    )
    if infra_root is None:
        raise ValueError(f"Optional infra CI source is missing. {hint}")
    sources: dict[str, tuple[Path, bytes]] = {}
    for name, expected in SCRIPT_HASHES.items():
        path = infra_root.resolve() / "scripts" / "ci" / f"{name}.py"
        try:
            source = path.read_bytes()
        except OSError as exc:
            raise ValueError(f"Optional infra CI scripts are missing. {hint}") from exc
        if hashlib.sha256(source).hexdigest() != expected:
            raise ValueError(f"Infra CI script {name} does not match the pin. {hint}")
        sources[name] = (path, source)
    modules = {}
    for name, (path, source) in sources.items():
        module = ModuleType(f"_b9_infra_{name}")
        module.__file__ = str(path)
        # Load only verified source, without importing myquant_infra or creating
        # bytecode in the archive. Scanned application code is never executed.
        exec(compile(source, str(path), "exec", dont_inherit=True), module.__dict__)
        modules[name] = module
    return modules


def scoped_paths(paths: list[Path], root: Path) -> list[Path]:
    """Exclude trading trees before reading; reject links/escapes before IO."""
    selected = []
    for path in paths:
        rel = path.relative_to(root)
        if EXCLUDED_PARTS.intersection(rel.parts):
            continue
        resolved = path.resolve()
        if resolved != path or not resolved.is_relative_to(root):
            raise ValueError(f"{rel.as_posix()}:0: symlink-or-escape")
        selected.append(path)
    return selected


def check_encoding(checker: ModuleType, root: Path) -> int:
    """Adopt encoding_rule/repo_files only; semantic policy stays with BT."""
    errors = []
    count = 0
    for path in scoped_paths(checker.repo_files(root), root):
        rel = path.relative_to(root).as_posix()
        if not (path.suffix.lower() in checker.TEXT_EXTS
                or path.name in checker.TEXT_NAMES or rel.startswith(".githooks/")):
            continue
        count += 1
        rule = checker.encoding_rule(path.read_bytes())
        if rule:
            errors.append(f"{rel}:0: {rule}")
    for error in errors:
        print(error, file=sys.stderr)
    print(f"Infra encoding: {len(errors)} finding(s) in {count} file(s)", flush=True)
    return int(bool(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT,
                        help="Git checkout to inspect (default: this BT checkout, never cwd)")
    parser.add_argument("--infra-root", type=Path,
                        help=f"local infra source archive at {INFRA_PIN}")
    parser.add_argument("--check", action="append", choices=("encoding", "secrets", "links"),
                        help="repeat to select checks; default: all three")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        modules = load_scripts(args.infra_root)
        # Validate even for link-only runs, supporting worktrees (.git is a file).
        # The infra archive must never become an implicit target checkout.
        modules["check_repo_hygiene"].repo_files(root)
        scanner = modules["scan_secrets"]
        # Actual pinned globals/functions, not invented --root flags. Bind once
        # per invocation so even repeated --check selections remain isolated.
        scanner.REPO = root
        scanner.ALLOWLIST = root / "scripts" / "ci" / "scan_secrets_allow.txt"
        tracked_files = scanner.tracked_files
        scanner.tracked_files = lambda: scoped_paths(tracked_files(), root)
        links = modules["check_md_links"]
        links.ROOT = root
        iter_md = links.iter_md
        links.iter_md = lambda: scoped_paths(iter_md(), root)
        results = []
        print(f"Additive infra CI ({INFRA_PIN}) target: {root}", flush=True)
        for check in args.check or ("encoding", "secrets", "links"):
            if check == "encoding":
                results.append(check_encoding(modules["check_repo_hygiene"], root))
            elif check == "secrets":
                if scanner.ALLOWLIST.exists():
                    scoped_paths([scanner.ALLOWLIST], root)
                results.append(scanner.scan(argparse.Namespace(staged=False, verbose=False)))
            else:
                results.append(links.main())
        return int(any(results))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # Never print scanned source lines, credential values or IO exceptions
        # that might contain them. Configuration errors carry actionable hints.
        message = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print(f"Optional infra CI configuration failed: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
