"""Offline board approximations from infra; no trading-rule registration."""
from __future__ import annotations

from l2_analytics._infra import require_l2


def board_limit_pct(stock_code: str) -> float:
    return require_l2("research.queries.board_limit").board_limit_pct(stock_code)


def __getattr__(name: str):
    if name == "BOARD_LIMIT_PCT_SQL":
        return require_l2("research.queries.board_limit").BOARD_LIMIT_PCT_SQL
    raise AttributeError(name)
