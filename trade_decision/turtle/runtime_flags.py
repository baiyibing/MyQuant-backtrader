"""Opt-in turtle risk switches, read at evaluation time and off by default."""

import os


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def is_turtle_risk_enhancements_enabled() -> bool:
    return _enabled("TURTLE_RISK_ENHANCEMENTS_ENABLED")


def is_turtle_risk_ma10_exit_enabled() -> bool:
    return _enabled("TURTLE_RISK_MA10_EXIT_ENABLED")
