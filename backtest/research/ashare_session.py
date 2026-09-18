# -*- coding: utf-8 -*-
"""A-share microstructure SSOT for daily and minute CSV engines.

Owns the facts every book must share and must not reimplement:

- ST / board limit band (Decimal fen, fail-closed unknown prefix)
- official none 昨收 + E-R6 ex-div map
- limit-up skip / limit-down defer
- T+1 lot eligibility (``buy_date < session``)

Strategy stops, ladders, and sizing stay in the book. This module must not
import a simulate loop or ``csv_ledger``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable, Mapping

from backtest.research.csv_pool import load_pool_names_by_day
from backtest.research.exdiv_map import k_for, load_exdiv_ratios, mapped_prev_close
from backtest.research.market_layer import is_st_name, limit_pct, limit_prices
from oskh_data.symbol_format import to_canonical_symbol

LIMIT_EPS = 0.001


def hit_limit_up(price: float, limit_up: float) -> bool:
    """买价达到或超过涨停价则不可买（含舍入导致买价高于算出的涨停价）。"""
    return float(price) + LIMIT_EPS >= float(limit_up)


def hit_limit_down(price: float, limit_down: float) -> bool:
    """卖价达到或低于跌停价则不可卖。"""
    return float(price) - LIMIT_EPS <= float(limit_down)


def t1_sellable(buy_date: date, session: date) -> bool:
    """A-share T+1: a lot is sellable only on a later session than ``buy_date``."""
    return buy_date < session


def raw_prev_close(closes: Mapping[date, float], today: date) -> float | None:
    prior = [day for day in closes if day < today]
    return float(closes[max(prior)]) if prior else None


def session_prev_close(
    closes: Mapping[date, float],
    today: date,
    symbol: str,
    exdiv: Mapping[str, Mapping[str, float]] | None,
) -> float | None:
    """None 昨收：上一交易日收盘，除权日乘 E-R6 ``k``。"""
    raw = raw_prev_close(closes, today)
    if raw is None:
        return None
    previous, _did_map = mapped_prev_close(exdiv, symbol, today.strftime("%Y%m%d"), raw)
    return previous


def session_limit_prices(
    code: str,
    previous: float | None,
    name: str = "",
) -> tuple[float, float] | None:
    if previous is None:
        return None
    return limit_prices(code, previous, name)


def skip_buy_at_limit(price: float, limits: tuple[float, float] | None) -> bool:
    return limits is not None and hit_limit_up(price, limits[0])


def defer_sell_at_limit(price: float, limits: tuple[float, float] | None) -> bool:
    return limits is not None and hit_limit_down(price, limits[1])


def flatten_pool_names(names_by_day: Mapping[str, Mapping[str, str]]) -> dict[str, str]:
    names: dict[str, str] = {}
    for ymd in sorted(names_by_day):
        names.update(names_by_day[ymd])
    return names


def load_limit_context(
    pool_dir: Path | None,
    symbols: Iterable[str],
    start: date,
    end: date,
) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    """E-R6 exdiv map + last-seen pool names (ST column)."""
    names: dict[str, str] = {}
    if pool_dir is not None:
        names = flatten_pool_names(load_pool_names_by_day(pool_dir, start, end))
    codes = [to_canonical_symbol(str(symbol)) for symbol in symbols]
    exdiv = load_exdiv_ratios(codes, start.strftime("%Y%m%d"), end.strftime("%Y%m%d")) if codes else {}
    return exdiv, names


__all__ = [
    "LIMIT_EPS",
    "defer_sell_at_limit",
    "flatten_pool_names",
    "hit_limit_down",
    "hit_limit_up",
    "is_st_name",
    "k_for",
    "limit_pct",
    "limit_prices",
    "load_limit_context",
    "raw_prev_close",
    "session_limit_prices",
    "session_prev_close",
    "skip_buy_at_limit",
    "t1_sellable",
]
