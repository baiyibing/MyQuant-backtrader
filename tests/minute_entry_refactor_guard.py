"""Keep the historical minute_orders CLI surface pinned during CSV dedupe."""

import ast
import hashlib
from pathlib import Path

# HELP_LOCK + main() bytes at knife base 501de569; main refreshed for research overlay flags.
# Frozen hashes avoid `git show` so shallow Actions checkouts can still enforce.
_EXPECTED_SHA256 = {
    "HELP_LOCK": "abdc73bf56b1e3318d25191fcc8bee78ab51d1b7877c603e9a0a70b1df305473",
    "main": "dd2a3cc38c651b7c0febb8da80bc46f1aec8c9ef4f464d3e234103084759be93",
}


def _cli_surface(source: str) -> dict[str, str]:
    lines = source.splitlines(keepends=True)
    result = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            result["main"] = "".join(lines[node.lineno - 1:node.end_lineno])
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "HELP_LOCK"
            for target in node.targets
        ):
            result["HELP_LOCK"] = "".join(lines[node.lineno - 1:node.end_lineno])
    assert set(result) == {"main", "HELP_LOCK"}
    return result


def assert_shared_minute_cli_unchanged(root: Path):
    relative = "backtest/research/csv_minute_backtest.py"
    after = (root / relative).read_text(encoding="utf-8")
    surface = _cli_surface(after)
    for name, expected in _EXPECTED_SHA256.items():
        got = hashlib.sha256(surface[name].encode("utf-8")).hexdigest()
        assert got == expected, f"{relative} {name} drifted from knife CLI surface"
