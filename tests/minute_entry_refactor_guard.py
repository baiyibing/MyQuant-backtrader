"""Keep the historical minute_orders CLI surface pinned during CSV dedupe."""

import ast
import subprocess
from pathlib import Path


BASE = "501de569d5d46eca2c1766988231a2dbaac3849d"


def assert_shared_minute_cli_unchanged(root: Path):
    relative = "backtest/research/csv_minute_backtest.py"
    before = subprocess.check_output(
        ["git", "show", f"{BASE}:{relative}"], cwd=root, text=True,
    )
    after = (root / relative).read_text(encoding="utf-8")

    def surface(source):
        lines = source.splitlines(keepends=True)
        result = {}
        for node in ast.parse(source).body:
            if (isinstance(node, ast.FunctionDef) and node.name == "main"
                or isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "HELP_LOCK"
                    for target in node.targets
                )):
                result["main" if isinstance(node, ast.FunctionDef) else "HELP_LOCK"] = (
                    "".join(lines[node.lineno - 1:node.end_lineno])
                )
        assert set(result) == {"main", "HELP_LOCK"}
        return result

    assert surface(after) == surface(before)
