"""CSV 回测策略书注册表。

日线 / 分钟引擎只跑买侧、资金、T+1、涨跌停。卖点与是否加仓由策略书提供。
必须显式指定 version6 / version8；无缺省。新策略：strategyN_rules.py + register()。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Callable, Optional

from backtest.research import (
    strategy1_rules,
    strategy2_rules,
    strategy5_rules,
    strategy6_rules,
    strategy8_rules,
)

HELP_LOCK_V1 = strategy1_rules.HELP_LOCK
HELP_LOCK_V2 = strategy2_rules.HELP_LOCK
HELP_LOCK_V5 = strategy5_rules.HELP_LOCK
HELP_LOCK_V6 = strategy6_rules.HELP_LOCK
HELP_LOCK_V8 = strategy8_rules.HELP_LOCK


@dataclass(frozen=True)
class CsvStrategyBook:
    name: str
    tag: str
    aliases: tuple[str, ...]
    allow_add: bool
    peak_gap_min: int
    help_lock: str
    apply: Callable[..., dict]
    run_kwargs: Callable[[Any], dict]


BOOKS: dict[str, CsvStrategyBook] = {}


def register(book: CsvStrategyBook) -> None:
    if book.name in BOOKS:
        raise ValueError(f"csv strategy {book.name!r} already registered")
    BOOKS[book.name] = book


def csv_strategy_names() -> tuple[str, ...]:
    return tuple(BOOKS)


def _alias_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for book in BOOKS.values():
        for alias in book.aliases:
            out[alias] = book.name
    return out


def normalize_csv_strategy(strategy: str) -> str:
    raw = (strategy or "").strip().lower()
    if not raw:
        names = " or ".join(csv_strategy_names())
        raise ValueError(f"csv strategy is required; choose {names}")
    aliases = _alias_map()
    if raw not in aliases:
        names = " or ".join(csv_strategy_names())
        raise ValueError(f"unsupported csv strategy {strategy!r}; use {names}")
    return aliases[raw]


def get_book(strategy: str) -> CsvStrategyBook:
    return BOOKS[normalize_csv_strategy(strategy)]


def apply_csv_strategy(strategy: str, **kwargs) -> dict:
    book = get_book(strategy)
    hooks = dict(book.apply(**kwargs))
    hooks["allow_add"] = book.allow_add
    hooks["peak_gap_min"] = book.peak_gap_min
    hooks["book"] = book.tag
    hooks["name"] = book.name
    hooks.setdefault("force_sell_hm", None)
    hooks.setdefault("buy_gate", None)
    hooks.setdefault("sell_gate", None)
    hooks.setdefault("reserve_limit_up", False)
    hooks.setdefault("daily_same_bar_prefixes", ("open_board",))
    if hooks.get("take_profit") is None:
        raise RuntimeError(f"{book.name} book missing take_profit")
    if hooks.get("record_params") is None:
        raise RuntimeError(f"{book.name} book missing record_params")
    return hooks


def add_csv_strategy_arg(ap: argparse.ArgumentParser) -> None:
    names = csv_strategy_names()
    ap.add_argument(
        "--strategy",
        choices=names,
        required=True,
        help="required sell book (" + ", ".join(names) + "); no default",
    )


def engine_book(strategy: str) -> str:
    return get_book(strategy).tag


def help_lock_for(strategy: str, *, shared: str) -> str:
    return shared + get_book(strategy).help_lock


def help_lock_all(shared: str) -> str:
    return shared + "".join(book.help_lock for book in BOOKS.values())


def add_strategy6_ratio_args(ap: argparse.ArgumentParser) -> None:
    """策略 6 比例覆盖；其它策略书忽略这些开关。"""
    ap.add_argument(
        "--stop-pct",
        type=float,
        default=None,
        help="stop-loss fraction override (version6 default 0.06, version8 default 0.20)",
    )
    ap.add_argument(
        "--profit-base",
        type=float,
        default=strategy6_rules.PROFIT_BASE,
        help=f"version6 take-profit anchor (default {strategy6_rules.PROFIT_BASE:g})",
    )
    ap.add_argument(
        "--trail-t1",
        type=float,
        default=strategy6_rules.TIERS[1],
        help=f"version6 T+1 retain ratio (default {strategy6_rules.TIERS[1]:g})",
    )
    ap.add_argument(
        "--trail-t2",
        type=float,
        default=strategy6_rules.TIERS[2],
        help=f"version6 T+2 retain ratio (default {strategy6_rules.TIERS[2]:g})",
    )
    ap.add_argument(
        "--trail-t3",
        type=float,
        default=strategy6_rules.TIERS[3],
        help=f"version6 T+3 retain ratio (default {strategy6_rules.TIERS[3]:g})",
    )
    ap.add_argument(
        "--trail-t4",
        type=float,
        default=strategy6_rules.TIERS[4],
        help=f"version6 T+4 retain ratio (default {strategy6_rules.TIERS[4]:g})",
    )
    ap.add_argument(
        "--trail-t5",
        type=float,
        default=strategy6_rules.TIER_DEFAULT,
        help=f"version6 T+5+ retain ratio (default {strategy6_rules.TIER_DEFAULT:g})",
    )


def strategy6_kwargs_from_args(args) -> dict:
    stop_pct = (
        strategy6_rules.STOP_PCT if args.stop_pct is None else float(args.stop_pct)
    )
    profit_base = float(args.profit_base)
    t1 = float(args.trail_t1)
    t2 = float(args.trail_t2)
    t3 = float(args.trail_t3)
    t4 = float(args.trail_t4)
    t5 = float(args.trail_t5)
    for name, val in (
        ("--stop-pct", stop_pct),
        ("--profit-base", profit_base),
        ("--trail-t1", t1),
        ("--trail-t2", t2),
        ("--trail-t3", t3),
        ("--trail-t4", t4),
        ("--trail-t5", t5),
    ):
        if not 0 < val < 1:
            raise SystemExit(f"{name} must be in (0, 1), got {val}")
    return {
        "stop_pct": stop_pct,
        "profit_base": profit_base,
        "tiers": {1: t1, 2: t2, 3: t3, 4: t4},
        "tier_default": t5,
    }


def csv_run_kwargs_from_args(args) -> dict:
    name = normalize_csv_strategy(getattr(args, "strategy", "") or "")
    return get_book(name).run_kwargs(args)


def _stop_override_from_args(args) -> Optional[float]:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return None if stop is None else float(stop)


def _apply_version1(
    *, stop_pct: Optional[float] = None, take_profit=None, record_params=None, **_
) -> dict:
    resolved = strategy1_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days):
        return strategy1_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy1_rules.record_strategy1_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": _tp if take_profit is None else take_profit,
        "record_params": _rec if record_params is None else record_params,
    }


def _run_kwargs_version1(args) -> dict:
    return {"strategy": "version1", "stop_pct": _stop_override_from_args(args)}


def _apply_version2(
    *, stop_pct: Optional[float] = None, take_profit=None, record_params=None, **_
) -> dict:
    resolved = strategy2_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days):
        return strategy2_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy2_rules.record_strategy2_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": _tp if take_profit is None else take_profit,
        "record_params": _rec if record_params is None else record_params,
    }


def _run_kwargs_version2(args) -> dict:
    return {"strategy": "version2", "stop_pct": _stop_override_from_args(args)}


def _apply_version5(
    *, stop_pct: Optional[float] = None, take_profit=None, record_params=None, **_
) -> dict:
    del stop_pct

    def _tp(px, cost, peak, n_days):
        return strategy5_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy5_rules.record_strategy5_params(st, stop_pct=None)

    return {
        "stop_pct": None,
        "take_profit": _tp if take_profit is None else take_profit,
        "record_params": _rec if record_params is None else record_params,
        "force_sell_hm": strategy5_rules.FORCE_SELL_HM,
        "sell_gate": None,
        "reserve_limit_up": False,
        "daily_same_bar_prefixes": ("open_board",),
    }


def _run_kwargs_version5(args) -> dict:
    if getattr(args, "stop_pct", None) is not None:
        raise SystemExit("--stop-pct is not supported for version5 (no stop loss)")
    return {"strategy": "version5"}


def _apply_version6(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    profit_base: Optional[float] = None,
    tiers: Optional[dict] = None,
    tier_default: Optional[float] = None,
    **_,
) -> dict:
    resolved_stop = strategy6_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    pb = strategy6_rules.PROFIT_BASE if profit_base is None else float(profit_base)
    tier_map = dict(tiers or strategy6_rules.TIERS)
    td = strategy6_rules.TIER_DEFAULT if tier_default is None else float(tier_default)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_rules.take_profit_reason(
            px, cost, peak, n_days, profit_base=pb, tiers=tier_map, tier_default=td
        )

    def _rec(st):
        strategy6_rules.record_strategy6_params(
            st,
            stop_pct=resolved_stop,
            profit_base=pb,
            tiers=tier_map,
            tier_default=td,
        )

    return {
        "stop_pct": resolved_stop,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
    }


def _run_kwargs_version6(args) -> dict:
    return {"strategy": "version6", **strategy6_kwargs_from_args(args)}


def _apply_version8(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy8_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _rec(st):
        strategy8_rules.record_strategy8_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": (
            strategy8_rules.take_profit_reason if take_profit is None else take_profit
        ),
        "record_params": record_params if record_params is not None else _rec,
    }


def _run_kwargs_version8(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version8", "stop_pct": stop}


register(
    CsvStrategyBook(
        name="version1",
        tag=strategy1_rules.BOOK_TAG,
        aliases=("1", "v1", "version1"),
        allow_add=strategy1_rules.ALLOW_ADD,
        peak_gap_min=strategy1_rules.PEAK_GAP_MIN,
        help_lock=strategy1_rules.HELP_LOCK,
        apply=_apply_version1,
        run_kwargs=_run_kwargs_version1,
    )
)
register(
    CsvStrategyBook(
        name="version2",
        tag=strategy2_rules.BOOK_TAG,
        aliases=("2", "v2", "version2"),
        allow_add=strategy2_rules.ALLOW_ADD,
        peak_gap_min=strategy2_rules.PEAK_GAP_MIN,
        help_lock=strategy2_rules.HELP_LOCK,
        apply=_apply_version2,
        run_kwargs=_run_kwargs_version2,
    )
)
register(
    CsvStrategyBook(
        name="version5",
        tag=strategy5_rules.BOOK_TAG,
        aliases=("5", "v5", "version5"),
        allow_add=strategy5_rules.ALLOW_ADD,
        peak_gap_min=strategy5_rules.PEAK_GAP_MIN,
        help_lock=strategy5_rules.HELP_LOCK,
        apply=_apply_version5,
        run_kwargs=_run_kwargs_version5,
    )
)
register(
    CsvStrategyBook(
        name="version6",
        tag=strategy6_rules.BOOK_TAG,
        aliases=("6", "v6", "version6"),
        allow_add=strategy6_rules.ALLOW_ADD,
        peak_gap_min=strategy6_rules.PEAK_GAP_MIN,
        help_lock=strategy6_rules.HELP_LOCK,
        apply=_apply_version6,
        run_kwargs=_run_kwargs_version6,
    )
)
register(
    CsvStrategyBook(
        name="version8",
        tag=strategy8_rules.BOOK_TAG,
        aliases=("8", "v8", "version8"),
        allow_add=strategy8_rules.ALLOW_ADD,
        peak_gap_min=strategy8_rules.PEAK_GAP_MIN,
        help_lock=strategy8_rules.HELP_LOCK,
        apply=_apply_version8,
        run_kwargs=_run_kwargs_version8,
    )
)
