"""Data-free fence: ops orchestration/publishing must not return to BT."""
from __future__ import annotations

import ast
import json
from pathlib import Path

RETIRED = "scripts/run/multi_ai_common.py"
ENTRIES = (
    "scripts/run/run_multi_ai_review.py",
    "scripts/run/run_codex_adversarial_lanes.py",
    "scripts/ops/push_github_pr_via_api.py",
)


def _thin_shape(entry: str) -> str:
    profiles = {ENTRIES[0]: "config/ops/bt-review.json", ENTRIES[1]: "config/ops/bt-adversarial.json"}
    profile = f", profile={profiles[entry]!r}" if entry in profiles else ""
    return ast.dump(ast.parse(f'''
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _ops_bootstrap import run_ops
def main(argv=None):
    return run_ops({entry!r}, argv{profile})
if __name__ == "__main__":
    raise SystemExit(main())
'''), include_attributes=False)


def violations(root: Path) -> list[str]:
    errors = [f"retired ops implementation restored: {RETIRED}"] if (root / RETIRED).exists() else []
    for name in ENTRIES:
        path = root / name
        if not path.is_file():
            errors.append(f"missing ops consumer entry: {name}")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
            tree.body = tree.body[1:]
        if ast.dump(tree, include_attributes=False) != _thin_shape(name):
            errors.append(f"local ops implementation/configuration: {name}")
    profile = root / "config/ops/bt-review.json"
    try:
        data = json.loads(profile.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict) or data.get("schema_version") != 2 or set(data) - {"schema_version", "domain_context", "ssot_paths", "role_suffix"}:
        errors.append("missing v2 domain profile or duplicated shared prompt/runtime policy")
    return errors


def main() -> int:
    errors = violations(Path(__file__).resolve().parents[2])
    for error in errors:
        print(error)
    print(f"[ops-consumer-boundary] {'FAIL' if errors else 'PASS'}")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
