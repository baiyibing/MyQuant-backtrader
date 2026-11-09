#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Data-free compatibility check; the numerical bridge is owned by MyQuant.

H11 Theme D soft — no lake, no compute. Fails if:
  1. oskh_core.turnover_resist_bridge stops re-exporting from oskh_factors.bridge.turnover_resist
  2. known scripts/tr consumers import compute_turnover_resist from somewhere else
     (e.g. a lake path or a deleted shim)

Usage (repo root)::

  python scripts/gates/verify_tr_bridge_import_ssot.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List, Set, Tuple

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2] if _HERE.parent.name == "gates" else _HERE.parents[1]

_SSOT_MODULE = "oskh_factors.bridge.turnover_resist"
_SHIM = _REPO / "oskh_core" / "turnover_resist_bridge.py"

# Host scripts that must call the bridge (shim or SSOT), never a third path.
_KNOWN_CONSUMERS: Tuple[Path, ...] = (
    _REPO / "scripts" / "tr" / "compute_turnover_resistance_bands.py",
    _REPO / "scripts" / "tr" / "backfill_turnover_resistance_bands.py",
)

_ALLOWED_BRIDGE_MODULES: Set[str] = {
    _SSOT_MODULE,
    "oskh_core.turnover_resist_bridge",
}


def _module_from_import(node: ast.AST) -> List[str]:
    """Return fully-qualified module roots referenced by Import / ImportFrom."""
    out: List[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            out.append(alias.name)
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            out.append(node.module)
    return out


def _imports_compute_turnover_resist(path: Path) -> List[str]:
    """Modules from which ``compute_turnover_resist`` is imported in *path*."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == "compute_turnover_resist":
                    found.append(node.module)
        elif isinstance(node, ast.Import):
            # ``import oskh_factors.bridge.turnover_resist as tr`` then tr.compute_...
            # Not required for known consumers today; skip.
            pass
    return found


def check_shim() -> List[str]:
    errors: List[str] = []
    if not _SHIM.is_file():
        return [f"missing shim: {_SHIM.relative_to(_REPO)}"]
    tree = ast.parse(_SHIM.read_text(encoding="utf-8"), filename=str(_SHIM))
    from_ssot = False
    for node in tree.body:
        for mod in _module_from_import(node):
            if mod == _SSOT_MODULE or mod.startswith(_SSOT_MODULE + "."):
                from_ssot = True
    if not from_ssot:
        errors.append(
            f"{_SHIM.relative_to(_REPO)} must ImportFrom {_SSOT_MODULE} "
            "(compat re-export SSOT)"
        )
    return errors


def check_known_consumers() -> List[str]:
    errors = []
    for path in _KNOWN_CONSUMERS:
        expected = "myquant_factors.research.entries.tr." + path.stem
        if not path.is_file():
            errors.append(f"missing known consumer: {path.relative_to(_REPO)}")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        forwards = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "importlib" and node.func.attr == "import_module"
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == expected]
        if not forwards or any(isinstance(n, (ast.FunctionDef, ast.ClassDef)) for n in ast.walk(tree)):
            errors.append(f"{path.relative_to(_REPO)} must forward to {expected}")
    return errors


def main() -> int:
    errors = check_shim() + check_known_consumers()
    if errors:
        print("verify_tr_bridge_import_ssot: FAIL", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(
        "verify_tr_bridge_import_ssot: OK "
        f"(shim→{_SSOT_MODULE}; {len(_KNOWN_CONSUMERS)} consumers)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
