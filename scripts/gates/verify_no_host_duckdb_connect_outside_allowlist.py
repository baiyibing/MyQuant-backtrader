#!/usr/bin/env python3
"""Keep lake DuckDB connections in MyQuant-infra (Knife R2-18).

Exact-file exceptions below cover only offline L2, TR/Store analytics and test
fixtures. No exception permits front/minute artifact management. See
``docs/engineering/k18-duckdb-infra-switch-20261105.md`` for the inventory.
Runs without third-party packages or lake configuration.
"""
from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]

# (number of connection call sites, permitted purpose). Changes require review;
# counts also reject stale entries and additional connections in an allowed file.
ALLOWLIST: dict[str, tuple[int, str]] = {
    "scripts/gates/verify_l2_manifest.py": (1, "Offline L2 manifest validation"),
    "scripts/tr/backfill_turnover_resistance_bands.py": (1, "TR/Store research date enumeration; no lake artifact management"),
    "scripts/data/full_market_canonical_resist.py": (1, "TR research capital-map query"),
    "scripts/research/full_market_canonical_resist.py": (1, "TR research capital-map query"),
    "scripts/gates/verify_single_stock_turnover_resist.py": (1, "TR audit capital-map query"),
    "scripts/research/verify_single_stock_turnover_resist.py": (1, "TR audit capital-map query"),
    "tests/test_l2_templates.py": (2, "Synthetic L2 query fixtures"),
    "tests/test_l2_etl.py": (3, "Synthetic L2 ETL fixtures"),
    "tests/test_oskh_data_integration.py": (1, "Synthetic legacy daily DB fixture"),
}


def connection_lines(source: str, filename: str = "<source>") -> list[int]:
    """Find calls through module aliases, imported connect and simple aliases.

    AST scanning ignores comments/strings (including mocks' patch targets).
    """
    tree = ast.parse(source, filename=filename)
    modules = {"duckdb"}
    connectors: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "duckdb":
                    modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "duckdb":
            for alias in node.names:
                if alias.name == "connect":
                    connectors.add(alias.asname or alias.name)
                if alias.name == "*":
                    connectors.add("connect")

    def is_connector(expr: ast.expr) -> bool:
        return (
            isinstance(expr, ast.Name) and expr.id in connectors
        ) or (
            isinstance(expr, ast.Attribute) and expr.attr == "connect"
            and isinstance(expr.value, ast.Name) and expr.value.id in modules
        )

    # Follow simple assignments such as connect_db = db.connect or db2 = db.
    changed = True
    while changed:
        before = (len(modules), len(connectors))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            else:
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    if is_connector(value):
                        connectors.add(target.id)
                    if isinstance(value, ast.Name) and value.id in modules:
                        modules.add(target.id)
        changed = before != (len(modules), len(connectors))
    return sorted(node.lineno for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and is_connector(node.func))


def scan(root: Path = REPO_ROOT) -> tuple[list[str], dict[str, list[int]]]:
    paths = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "*.py"],
        cwd=root, check=True, capture_output=True,
    ).stdout.decode("utf-8").split("\0")
    errors: list[str] = []
    hits: dict[str, list[int]] = {}
    for rel in sorted(set(paths) - {""}):
        path = root / rel
        if not path.is_file():
            continue
        try:
            lines = connection_lines(path.read_text(encoding="utf-8-sig"), rel)
        except (SyntaxError, UnicodeError) as exc:
            errors.append(f"{rel}: cannot scan: {exc}")
            continue
        if lines:
            hits[rel] = lines
            if rel not in ALLOWLIST:
                errors.append(f"{rel}:{','.join(map(str, lines))}: host DuckDB connection outside allowlist")
    for rel, (expected, reason) in sorted(ALLOWLIST.items()):
        actual = len(hits.get(rel, []))
        if actual != expected:
            errors.append(f"{rel}: allowlist drift {actual} != {expected} ({reason})")
    return errors, hits


def main() -> int:
    errors, hits = scan()
    if errors:
        print("Host DuckDB connection gate: FAIL")
        print("\n".join(errors))
        return 1
    print(f"Host DuckDB connection gate: OK ({sum(map(len, hits.values()))} allowed calls in {len(hits)} files)")
    for rel in sorted(hits):
        print(f"  {rel}: {len(hits[rel])} — {ALLOWLIST[rel][1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
