# -*- coding: utf-8 -*-
"""Pytest bootstrap for standalone vectorized research + data fork."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001
    """Ensure repo-local pytest basetemp exists."""
    root = Path(str(config.rootpath))
    session_basetemp = root / "artifacts" / "pytest_tmp" / f"run_{os.getpid()}"
    session_basetemp.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = str(session_basetemp)

    try:
        from loguru import logger as _loguru_logger

        _loguru_logger.remove()
        _loguru_logger.add(sys.__stderr__, level="WARNING", colorize=False)  # type: ignore[reportCallIssue]
    except Exception:
        pass


@pytest.fixture
def cheap_bar_tip_modules(monkeypatch):
    """Hash-pinned 0df7697 handoff modules; portable checked-path tests also run."""
    import hashlib
    import importlib.util

    root = Path("/workspace/handoffs/joint_return_cheap_bar_decimal_20260924")
    hashes = {
        "replay": "d50256770cd485571c785db5f8d817fbcf124b6da3a5bdd1c48cce2ff92b88e5",
        "validate_v2": "3e917dc8c388d89c95a0fa38c1af7bd1f1f538d4a8c5440db2b10f6cf259b3dd",
    }
    modules = {}
    for suffix, digest in hashes.items():
        path = root / f"baseline_joint_return_{suffix}.py"
        if not path.exists():
            pytest.skip("exact 0df7697 handoff modules are not installed on this host")
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        name = f"cheap_bar_tip_{suffix}"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)  # dataclass module lookup
        spec.loader.exec_module(module)
        modules[suffix] = module
    return modules["replay"], modules["validate_v2"]
