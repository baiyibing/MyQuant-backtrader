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
