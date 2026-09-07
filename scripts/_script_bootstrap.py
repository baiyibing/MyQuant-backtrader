#!/usr/bin/env python3
"""Shared bootstrap helpers for operational scripts.

Resolve order matches OSkhQuant1.3 AGENTS.md:
OSKH_MERGE_PYTHON → OSKH_MERGE_ENV_HOME → VANNA312_PYTHON → VANNA312_HOME →
VANNA311_PYTHON → VANNA311_HOME (legacy) → win32 fallback vanna312.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Mapping, Optional

CANONICAL_OSKH_HOME = Path(r"D:\anaconda3\envs\vanna312")
CANONICAL_OSKH_WIN = CANONICAL_OSKH_HOME / "python.exe"
CANONICAL_OSKH_PYTHONW = CANONICAL_OSKH_HOME / "pythonw.exe"
CANONICAL_VANNA312_HOME = CANONICAL_OSKH_HOME
CANONICAL_VANNA312_WIN = CANONICAL_OSKH_WIN
CANONICAL_VANNA312_PYTHONW = CANONICAL_OSKH_PYTHONW
CANONICAL_VANNA311_HOME = CANONICAL_OSKH_HOME
CANONICAL_VANNA311_WIN = CANONICAL_OSKH_WIN
CANONICAL_VANNA311_PYTHONW = CANONICAL_OSKH_PYTHONW

_IS_WIN32 = sys.platform == "win32"


def repo_root_from_script(script_file: str) -> Path:
    """Resolve repository root from a script file path under ``scripts/``."""
    p = Path(script_file).resolve()
    parts = p.parts
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == "scripts":
            return Path(*parts[:i])
    return p.parent.parent


def ensure_repo_on_syspath(script_file: str) -> Path:
    """Ensure repository root is importable and return the root path."""
    root = repo_root_from_script(script_file)
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)
    return root


def set_default_env(defaults: Mapping[str, str]) -> None:
    """Set environment defaults without overriding already-defined values."""
    for key, value in defaults.items():
        os.environ.setdefault(str(key), str(value))


def _env_strip(key: str) -> str:
    return (os.environ.get(key) or "").strip().strip('"')


def _platform_python_exe(env_home: Path) -> Path:
    if _IS_WIN32:
        return env_home / "python.exe"
    return env_home / "bin" / "python"


def _validate_python_version(python_path: Path) -> None:
    requested = _env_strip("OSKH_PYTHON_VERSION")
    if not requested:
        return
    parts = requested.split(".")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        print(
            f"ERROR: OSKH_PYTHON_VERSION={requested!r} must be major.minor (e.g. 3.12).",
            file=sys.stderr,
        )
        raise SystemExit(2)
    try:
        proc = subprocess.run(
            [
                str(python_path),
                "-c",
                "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: Failed to query version from {python_path}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    actual = proc.stdout.strip()
    if actual != requested:
        print(
            f"ERROR: OSKH_PYTHON_VERSION={requested} but {python_path} reports {actual}.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def resolve_oskh_python(*, exit_on_missing: bool = True) -> Path:
    """Resolve the canonical Python interpreter (cross-platform)."""

    def _try_python_var(key: str) -> Path | None:
        raw = _env_strip(key)
        if not raw:
            return None
        p = Path(raw)
        if not p.is_file():
            print(f"ERROR: {key}={raw!r} is not an existing file.", file=sys.stderr)
            raise SystemExit(2)
        _validate_python_version(p)
        return p

    def _try_home_var(key: str) -> Path | None:
        raw = _env_strip(key)
        if not raw:
            return None
        home = Path(raw)
        if not home.is_dir():
            print(f"ERROR: {key}={raw!r} is not an existing directory.", file=sys.stderr)
            raise SystemExit(2)
        p = _platform_python_exe(home)
        if p.is_file():
            _validate_python_version(p)
            return p
        return None

    for key in ("OSKH_MERGE_PYTHON", "VANNA312_PYTHON", "VANNA311_PYTHON"):
        result = _try_python_var(key)
        if result is not None:
            return result
    for key in ("OSKH_MERGE_ENV_HOME", "VANNA312_HOME", "VANNA311_HOME"):
        result = _try_home_var(key)
        if result is not None:
            return result

    if _IS_WIN32 and CANONICAL_OSKH_WIN.is_file():
        _validate_python_version(CANONICAL_OSKH_WIN)
        return CANONICAL_OSKH_WIN

    if exit_on_missing:
        print(
            "ERROR: Canonical interpreter not found.\n"
            f"  Checked: {CANONICAL_OSKH_WIN}\n"
            "Set OSKH_MERGE_PYTHON or VANNA312_PYTHON, then retry.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if _IS_WIN32:
        return CANONICAL_OSKH_WIN
    raise SystemExit(2)


def resolve_oskh_home() -> Path:
    for key in ("OSKH_MERGE_ENV_HOME", "VANNA312_HOME", "VANNA311_HOME"):
        raw = _env_strip(key)
        if not raw:
            continue
        home = Path(raw)
        if home.is_dir():
            return home
        print(f"ERROR: {key}={raw!r} is not an existing directory.", file=sys.stderr)
        raise SystemExit(2)

    py = resolve_oskh_python()
    if _IS_WIN32:
        return py.parent
    return py.parent.parent


def resolve_oskh_pythonw(*, exit_on_missing: bool = True) -> Optional[Path]:
    if not _IS_WIN32:
        if exit_on_missing:
            print("ERROR: pythonw is Windows-only.", file=sys.stderr)
            raise SystemExit(2)
        return None
    home = resolve_oskh_home()
    pyw = home / "pythonw.exe"
    if pyw.is_file() or not exit_on_missing:
        return pyw
    print(f"ERROR: pythonw.exe not found at {pyw}", file=sys.stderr)
    raise SystemExit(2)


def resolve_oskh_site_packages(*, exit_on_missing: bool = True) -> Path:
    py = resolve_oskh_python()
    try:
        proc = subprocess.run(
            [str(py), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if exit_on_missing:
            print(f"ERROR: Failed to query site-packages from {py}: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc
        return resolve_oskh_home() / "Lib" / "site-packages"

    site_str = proc.stdout.strip()
    if proc.returncode != 0 or not site_str:
        if exit_on_missing:
            print(f"ERROR: Could not determine site-packages from {py}.", file=sys.stderr)
            raise SystemExit(2)
        return resolve_oskh_home() / "Lib" / "site-packages"

    site = Path(site_str)
    if site.is_dir() or not exit_on_missing:
        return site
    print(f"ERROR: site-packages not found at {site}", file=sys.stderr)
    raise SystemExit(2)


def guarded_destructive_script(
    *,
    allow_flag_env: str = "OSKH_ALLOW_DESTRUCTIVE_SCRIPT",
    trading_type_env: str = "TRADING_TYPE",
    quant_env_env: str = "QUANT_ENV",
    blocked_trading_types: Optional[Iterable[str]] = None,
    blocked_quant_envs: Optional[Iterable[str]] = None,
) -> int:
    blocked_trading = {x.lower() for x in (blocked_trading_types or ("live",))}
    blocked_envs = {x.lower() for x in (blocked_quant_envs or ("prod", "production"))}
    trading_type = str(os.getenv(trading_type_env, "paper")).strip().lower()
    quant_env = str(os.getenv(quant_env_env, "")).strip().lower()
    allow_flag = str(os.getenv(allow_flag_env, "")).strip().lower()
    if trading_type in blocked_trading or quant_env in blocked_envs:
        return 2
    return 0 if allow_flag in ("1", "true", "yes", "on") else 2
