#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate: block machine-local path hardcodes outside the allowlisted fallback.

Data-free / repo-only — safe for CI without ``F:\\stock_data``.

Scans production packages, ``scripts/**/*.py``, and ``tests/**/*.py`` for:

- ``E:\\PycharmProjects`` / ``E:/PycharmProjects``
- ``C:\\Users\\Thinkpad`` / ``C:/Users/Thinkpad``
- ``D:\\anaconda3`` / ``D:/anaconda3`` (except allowlisted files)

Docstrings and ``#`` comments are ignored. Production packages must stay at 0 hits.

Allowlist (sole machine fallback for win11-dev):

- ``scripts/_script_bootstrap.py`` (``CANONICAL_*`` / resolve helpers)

Usage::

  python scripts/gates/verify_no_hardcoded_machine_paths.py
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

_PATTERNS = (
    re.compile(r"E:[/\\]+PycharmProjects", re.I),
    re.compile(r"C:[/\\]+Users[/\\]+Thinkpad", re.I),
    re.compile(r"D:[/\\]+anaconda3", re.I),
)

# Slim research-face packages (no live_trading / oskh_db / executor_stream).
_PROD_PACKAGES = (
    "common",
    "oskh_core",
    "oskh_data",
    "oskh_factors",
    "backtest",
    "trade_decision",
    "qlib_cost",
    "l2_analytics",
    "strategies",
)

_ALLOWLIST_FILES = frozenset(
    {
        "scripts/_script_bootstrap.py",
    }
)

_ALLOWLIST_LINES: frozenset[str] = frozenset()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _doc_comment_lines(src: str) -> set[int]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    docs: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(
            getattr(first, "value", None), ast.Constant
        ):
            if isinstance(first.value.value, str):
                end = getattr(first, "end_lineno", first.lineno) or first.lineno
                docs.update(range(first.lineno, end + 1))
    return docs


def _iter_py_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for name in _PROD_PACKAGES:
        base = root / name
        if base.is_dir():
            out.extend(base.rglob("*.py"))
    for base_name in ("scripts", "tests"):
        base = root / base_name
        if base.is_dir():
            out.extend(base.rglob("*.py"))
    return out


def scan(root: Path) -> list[str]:
    hits: list[str] = []
    for path in sorted(_iter_py_files(root)):
        rel = path.relative_to(root).as_posix()
        if rel in _ALLOWLIST_FILES:
            continue
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not any(p.search(src) for p in _PATTERNS):
            continue
        ignore = _doc_comment_lines(src)
        for i, line in enumerate(src.splitlines(), 1):
            if not any(p.search(line) for p in _PATTERNS):
                continue
            stripped = line.strip()
            if stripped.startswith("#") or i in ignore:
                continue
            key = f"{rel}:{i}"
            if key in _ALLOWLIST_LINES:
                continue
            hits.append(f"{key}: {stripped[:160]}")
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--all",
        action="store_true",
        help="Accepted for symmetry with other gates; always full-scans.",
    )
    ap.parse_args(argv)
    root = _repo_root()
    hits = scan(root)
    if hits:
        print("ERROR: hardcoded machine paths in executable code:", file=sys.stderr)
        for h in hits:
            print(f"  {h}", file=sys.stderr)
        print(
            "Use scripts/_script_bootstrap.resolve_oskh_python() / "
            "ensure_repo_on_syspath(); or set OSKH_MERGE_PYTHON / VANNA312_PYTHON.",
            file=sys.stderr,
        )
        return 1
    print("OK: no executable machine-path hardcodes outside allowlist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
