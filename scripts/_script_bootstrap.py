#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared bootstrap helpers for operational scripts.

Goal:
- Avoid repeating ad-hoc ``sys.path.insert(0, ...)`` snippets in every script.
- Keep runtime defaults and destructive-script guard conventions consistent.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, Mapping, Optional


def repo_root_from_script(script_file: str) -> Path:
    """Resolve repository root from a script file path under ``scripts/``."""
    return Path(script_file).resolve().parent.parent


def ensure_repo_on_syspath(script_file: str) -> Path:
    """
    Ensure repository root is importable and return the root path.

    This replaces repeated ``sys.path.insert(0, REPO)`` snippets.
    """
    root = repo_root_from_script(script_file)
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)
    return root


def set_default_env(defaults: Mapping[str, str]) -> None:
    """Set environment defaults without overriding already-defined values."""
    for key, value in defaults.items():
        os.environ.setdefault(str(key), str(value))


def guarded_destructive_script(
    *,
    allow_flag_env: str = "OSKH_ALLOW_DESTRUCTIVE_SCRIPT",
    trading_type_env: str = "TRADING_TYPE",
    quant_env_env: str = "QUANT_ENV",
    blocked_trading_types: Optional[Iterable[str]] = None,
    blocked_quant_envs: Optional[Iterable[str]] = None,
) -> int:
    """
    Return 0 when execution is allowed, else return a non-zero code.

    Policy:
    - Block in live-like trading types or production-like quant envs.
    - Require explicit opt-in via ``allow_flag_env``.
    """
    blocked_trading = {x.lower() for x in (blocked_trading_types or ("live",))}
    blocked_envs = {x.lower() for x in (blocked_quant_envs or ("prod", "production"))}
    trading_type = str(os.getenv(trading_type_env, "paper")).strip().lower()
    quant_env = str(os.getenv(quant_env_env, "")).strip().lower()
    allow_flag = str(os.getenv(allow_flag_env, "")).strip().lower()
    if trading_type in blocked_trading or quant_env in blocked_envs:
        return 2
    return 0 if allow_flag in ("1", "true", "yes", "on") else 2
