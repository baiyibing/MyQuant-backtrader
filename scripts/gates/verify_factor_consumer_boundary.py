"""Data-free fence: relocated factor sources belong to MyQuant."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def violations(root: Path) -> list[str]:
    exports = json.loads((root / "docs/engineering/factor-consumer-exports-20261109.json").read_text(encoding="utf-8"))
    errors = []
    for relative, shared in exports.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"missing consumer: {relative}")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for n in ast.walk(tree)):
            errors.append(f"factor implementation restored: {relative}")
        module, _, member = shared.rpartition(".")
        forwarded = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name) and n.func.value.id == "importlib"
            and n.func.attr == "import_module" and n.args
            and isinstance(n.args[0], ast.Constant) and n.args[0].value == shared
            or isinstance(n, ast.ImportFrom) and n.module == module
            and any(a.name == member for a in n.names)
            for n in ast.walk(tree)
        )
        if not forwarded:
            errors.append(f"consumer must import {shared}: {relative}")
    for name in ("factor_expr.py", "qlib_workflow.py", "筹码分布因子.ipynb"):
        if (root / "qlib_cost" / name).exists():
            errors.append(f"training source restored: qlib_cost/{name}")
    rust = root / "turnover-resist"
    errors.extend(f"Rust source restored: {p.relative_to(root)}" for p in rust.rglob("*")
                  if p.is_file() and (p.suffix == ".rs" or p.name in {"Cargo.toml", "Cargo.lock", "pyproject.toml"}))
    return errors


def main() -> int:
    errors = violations(ROOT)
    print("verify_factor_consumer_boundary: " + ("FAIL\n" + "\n".join(errors) if errors else "OK"))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
