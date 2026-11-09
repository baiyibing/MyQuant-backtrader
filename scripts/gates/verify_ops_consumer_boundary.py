"""Data-free fence: ops orchestration/publishing must not return to BT."""
from __future__ import annotations

import ast
from pathlib import Path

RETIRED = "scripts/run/multi_ai_common.py"
ENTRIES = (
    "scripts/run/run_multi_ai_review.py",
    "scripts/run/run_codex_adversarial_lanes.py",
    "scripts/ops/push_github_pr_via_api.py",
)


def violations(root: Path) -> list[str]:
    errors = [f"retired ops implementation restored: {RETIRED}"] if (root / RETIRED).exists() else []
    for name in ENTRIES:
        path = root / name
        if not path.is_file():
            errors.append(f"missing ops consumer entry: {name}")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if not any(isinstance(n, ast.ImportFrom) and n.module == "_ops_bootstrap"
                   and any(a.name == "run_ops" for a in n.names) for n in tree.body):
            errors.append(f"missing shared ops invocation: {name}")
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                errors.append(f"local ops configuration/implementation: {name}:{node.lineno}")
            if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef, ast.Lambda)):
                errors.append(f"local ops implementation: {name}:{node.lineno}")
            if isinstance(node, ast.FunctionDef):
                body = node.body
                if (node.name != "main" or len(body) != 1 or not isinstance(body[0], ast.Return)
                        or not isinstance(body[0].value, ast.Call)
                        or not isinstance(body[0].value.func, ast.Name) or body[0].value.func.id != "run_ops"):
                    errors.append(f"local ops implementation: {name}:{node.lineno}")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = [node.module] if isinstance(node, ast.ImportFrom) else [n.name for n in node.names]
                if any(module not in {"sys", "pathlib", "_ops_bootstrap"} for module in modules):
                    errors.append(f"local ops dependency: {name}:{node.lineno}")
    return errors


def main() -> int:
    errors = violations(Path(__file__).resolve().parents[2])
    for error in errors:
        print(error)
    print(f"[ops-consumer-boundary] {'FAIL' if errors else 'PASS'}")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
