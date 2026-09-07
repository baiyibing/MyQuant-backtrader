# -*- coding: utf-8 -*-
"""Pytest bootstrap for standalone backtrader + data fork."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Generator

import pytest

from common.infra.security import mask_account


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
def loguru_caplog_mirror() -> Generator[None, None, None]:
    """Forward Loguru to stdlib so ``caplog`` sees ``get_logger`` output."""
    try:
        from loguru import logger as loguru_logger
    except ImportError:  # pragma: no cover
        yield
        return

    _lv = {
        "TRACE": logging.DEBUG,
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "SUCCESS": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    def _sink(message: object) -> None:
        rec = message.record  # type: ignore[union-attr]
        lvl = _lv.get(str(rec["level"].name), logging.INFO)
        logging.getLogger(str(rec["name"])).log(lvl, str(rec["message"]))

    handler_id = loguru_logger.add(_sink, level="DEBUG", enqueue=False)
    yield
    try:
        loguru_logger.remove(handler_id)
    except ValueError:
        pass


TEST_FIXTURE_ACCOUNT_ID = "62205221"
TEST_FIXTURE_ACCOUNT_ID_MASKED = mask_account(TEST_FIXTURE_ACCOUNT_ID)
