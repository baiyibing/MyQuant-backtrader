"""CSV 回测策略书注册表。

日线 / 分钟引擎只跑买侧、资金、T+1、涨跌停。卖点与是否加仓由策略书提供。
必须显式指定已注册策略；无缺省。新策略：strategyN_rules.py + register()。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from backtest.research import (
    strategy1_rules,
    strategy2_rules,
    strategy3_rules,
    strategy4_rules,
    strategy5_rules,
    strategy6_rules,
    strategy6_1_rules,
    strategy6_2_rules,
    strategy6_3_rules,
    strategy6_4_rules,
    strategy6_5_rules,
    strategy6_6_rules,
    strategy6_7_rules,
    strategy6_8_rules,
    strategy6_9_rules,
    strategy6_10_rules,
    strategy6_11_rules,
    strategy6_12_rules,
    strategy6_13_rules,
    strategy6_14_rules,
    strategy6_15_rules,
    strategy6_16_rules,
    strategy6_17_rules,
    strategy6_18_rules,
    strategy6_19_rules,
    strategy6_20_rules,
    strategy6_21_rules,
    strategy6_22_rules,
    strategy6_23_rules,
    strategy6_24_rules,
    strategy6_25_rules,
    strategy6_26_rules,
    strategy6_27_rules,
    strategy6_28_rules,
    strategy6_29_rules,
    strategy6_30_rules,
    strategy6_31_rules,
    strategy6_32_rules,
    strategy6_33_rules,
    strategy6_34_rules,
    strategy6_35_rules,
    strategy6_36_rules,
    strategy6_37_rules,
    strategy6_38_rules,
    strategy6_39_rules,
    strategy6_40_rules,
    strategy6_41_rules,
    strategy6_42_rules,
    strategy6_43_rules,
    strategy6_44_rules,
    strategy6_45_rules,
    strategy6_46_rules,
    strategy6_47_rules,
    strategy6_48_rules,
    strategy6_49_rules,
    strategy6_50_rules,
    strategy6_51_rules,
    strategy6_52_rules,
    strategy6_53_rules,
    strategy6_54_rules,
    strategy6_55_rules,
    strategy8_rules,
    strategy8_1_rules,
    strategy8_2_rules,
    strategy8_3_rules,
    strategy8_4_rules,
    strategy8_5_rules,
    strategy8_6_rules,
    strategy9_rules,
    strategy9_1_rules,
    strategy9_2_rules,
    strategy9_3_rules,
    strategy10_rules,
    strategy11_rules,
    strategy12_rules,
    strategy_topk_dropout_rules,
    strategy_topk_score_exit_rules,
)
from backtest.research.csv_pool import is_repo_stock_pool
from backtest.research.csv_strategy_books_v6_family import (
    _apply_version6_1,
    _run_kwargs_version6_1,
    _apply_version6_2,
    _run_kwargs_version6_2,
    _apply_version6_3,
    _run_kwargs_version6_3,
    _apply_version6_4,
    _run_kwargs_version6_4,
    _apply_version6_5,
    _run_kwargs_version6_5,
    _apply_version6_6,
    _run_kwargs_version6_6,
    _apply_version6_7,
    _run_kwargs_version6_7,
    _apply_version6_8,
    _run_kwargs_version6_8,
    _apply_version6_9,
    _run_kwargs_version6_9,
    _apply_version6_10,
    _run_kwargs_version6_10,
    _apply_version6_11,
    _run_kwargs_version6_11,
    _apply_version6_12,
    _run_kwargs_version6_12,
    _apply_version6_13,
    _run_kwargs_version6_13,
    _apply_version6_14,
    _run_kwargs_version6_14,
    _apply_version6_15,
    _run_kwargs_version6_15,
    _apply_version6_16,
    _run_kwargs_version6_16,
    _apply_version6_17,
    _run_kwargs_version6_17,
    _apply_version6_18,
    _run_kwargs_version6_18,
    _apply_version6_19,
    _run_kwargs_version6_19,
    _apply_version6_20,
    _run_kwargs_version6_20,
    _apply_version6_21,
    _run_kwargs_version6_21,
    _apply_version6_22,
    _run_kwargs_version6_22,
    _apply_version6_23,
    _run_kwargs_version6_23,
    _apply_version6_24,
    _run_kwargs_version6_24,
    _apply_version6_25,
    _run_kwargs_version6_25,
    _apply_version6_26,
    _run_kwargs_version6_26,
    _apply_version6_27,
    _run_kwargs_version6_27,
    _apply_version6_28,
    _run_kwargs_version6_28,
    _apply_version6_29,
    _run_kwargs_version6_29,
    _apply_version6_30,
    _run_kwargs_version6_30,
    _apply_version6_31,
    _run_kwargs_version6_31,
    _apply_version6_32,
    _run_kwargs_version6_32,
    _apply_version6_33,
    _run_kwargs_version6_33,
    _apply_version6_34,
    _run_kwargs_version6_34,
    _apply_version6_35,
    _run_kwargs_version6_35,
    _apply_version6_36,
    _run_kwargs_version6_36,
    _apply_version6_37,
    _run_kwargs_version6_37,
    _apply_version6_38,
    _run_kwargs_version6_38,
    _apply_version6_39,
    _run_kwargs_version6_39,
    _apply_version6_40,
    _run_kwargs_version6_40,
    _apply_version6_41,
    _run_kwargs_version6_41,
    _apply_version6_42,
    _run_kwargs_version6_42,
    _apply_version6_43,
    _run_kwargs_version6_43,
    _apply_version6_44,
    _run_kwargs_version6_44,
    _apply_version6_45,
    _run_kwargs_version6_45,
    _apply_version6_46,
    _run_kwargs_version6_46,
    _apply_version6_47,
    _run_kwargs_version6_47,
    _apply_version6_48,
    _run_kwargs_version6_48,
    _apply_version6_49,
    _run_kwargs_version6_49,
    _apply_version6_50,
    _run_kwargs_version6_50,
    _apply_version6_51,
    _run_kwargs_version6_51,
    _apply_version6_52,
    _run_kwargs_version6_52,
    _apply_version6_53,
    _run_kwargs_version6_53,
    _apply_version6_54,
    _run_kwargs_version6_54,
    _apply_version6_55,
    _run_kwargs_version6_55,
)

HELP_LOCK_V1 = strategy1_rules.HELP_LOCK
HELP_LOCK_V2 = strategy2_rules.HELP_LOCK
HELP_LOCK_V3 = strategy3_rules.HELP_LOCK
HELP_LOCK_V4 = strategy4_rules.HELP_LOCK
HELP_LOCK_V5 = strategy5_rules.HELP_LOCK
HELP_LOCK_V6 = strategy6_rules.HELP_LOCK
HELP_LOCK_V6_1 = strategy6_1_rules.HELP_LOCK
HELP_LOCK_V6_2 = strategy6_2_rules.HELP_LOCK
HELP_LOCK_V6_3 = strategy6_3_rules.HELP_LOCK
HELP_LOCK_V6_4 = strategy6_4_rules.HELP_LOCK
HELP_LOCK_V6_5 = strategy6_5_rules.HELP_LOCK
HELP_LOCK_V6_6 = strategy6_6_rules.HELP_LOCK
HELP_LOCK_V6_7 = strategy6_7_rules.HELP_LOCK
HELP_LOCK_V6_8 = strategy6_8_rules.HELP_LOCK
HELP_LOCK_V6_9 = strategy6_9_rules.HELP_LOCK
HELP_LOCK_V6_10 = strategy6_10_rules.HELP_LOCK
HELP_LOCK_V6_11 = strategy6_11_rules.HELP_LOCK
HELP_LOCK_V6_12 = strategy6_12_rules.HELP_LOCK
HELP_LOCK_V6_13 = strategy6_13_rules.HELP_LOCK
HELP_LOCK_V6_14 = strategy6_14_rules.HELP_LOCK
HELP_LOCK_V6_15 = strategy6_15_rules.HELP_LOCK
HELP_LOCK_V6_16 = strategy6_16_rules.HELP_LOCK
HELP_LOCK_V6_17 = strategy6_17_rules.HELP_LOCK
HELP_LOCK_V6_18 = strategy6_18_rules.HELP_LOCK
HELP_LOCK_V6_19 = strategy6_19_rules.HELP_LOCK
HELP_LOCK_V6_20 = strategy6_20_rules.HELP_LOCK
HELP_LOCK_V6_21 = strategy6_21_rules.HELP_LOCK
HELP_LOCK_V6_22 = strategy6_22_rules.HELP_LOCK
HELP_LOCK_V6_23 = strategy6_23_rules.HELP_LOCK
HELP_LOCK_V6_24 = strategy6_24_rules.HELP_LOCK
HELP_LOCK_V6_25 = strategy6_25_rules.HELP_LOCK
HELP_LOCK_V6_26 = strategy6_26_rules.HELP_LOCK
HELP_LOCK_V6_27 = strategy6_27_rules.HELP_LOCK
HELP_LOCK_V6_28 = strategy6_28_rules.HELP_LOCK
HELP_LOCK_V6_29 = strategy6_29_rules.HELP_LOCK
HELP_LOCK_V6_30 = strategy6_30_rules.HELP_LOCK
HELP_LOCK_V6_31 = strategy6_31_rules.HELP_LOCK
HELP_LOCK_V6_32 = strategy6_32_rules.HELP_LOCK
HELP_LOCK_V6_33 = strategy6_33_rules.HELP_LOCK
HELP_LOCK_V6_34 = strategy6_34_rules.HELP_LOCK
HELP_LOCK_V6_35 = strategy6_35_rules.HELP_LOCK
HELP_LOCK_V6_36 = strategy6_36_rules.HELP_LOCK
HELP_LOCK_V6_37 = strategy6_37_rules.HELP_LOCK
HELP_LOCK_V6_38 = strategy6_38_rules.HELP_LOCK
HELP_LOCK_V6_39 = strategy6_39_rules.HELP_LOCK
HELP_LOCK_V6_40 = strategy6_40_rules.HELP_LOCK
HELP_LOCK_V6_41 = strategy6_41_rules.HELP_LOCK
HELP_LOCK_V6_42 = strategy6_42_rules.HELP_LOCK
HELP_LOCK_V6_43 = strategy6_43_rules.HELP_LOCK
HELP_LOCK_V6_44 = strategy6_44_rules.HELP_LOCK
HELP_LOCK_V6_45 = strategy6_45_rules.HELP_LOCK
HELP_LOCK_V6_46 = strategy6_46_rules.HELP_LOCK
HELP_LOCK_V6_47 = strategy6_47_rules.HELP_LOCK
HELP_LOCK_V6_48 = strategy6_48_rules.HELP_LOCK
HELP_LOCK_V6_49 = strategy6_49_rules.HELP_LOCK
HELP_LOCK_V6_50 = strategy6_50_rules.HELP_LOCK
HELP_LOCK_V6_51 = strategy6_51_rules.HELP_LOCK
HELP_LOCK_V6_52 = strategy6_52_rules.HELP_LOCK
HELP_LOCK_V6_53 = strategy6_53_rules.HELP_LOCK
HELP_LOCK_V6_54 = strategy6_54_rules.HELP_LOCK
HELP_LOCK_V6_55 = strategy6_55_rules.HELP_LOCK
HELP_LOCK_V8 = strategy8_rules.HELP_LOCK
HELP_LOCK_V8_1 = strategy8_1_rules.HELP_LOCK
HELP_LOCK_V8_2 = strategy8_2_rules.HELP_LOCK
HELP_LOCK_V8_3 = strategy8_3_rules.HELP_LOCK
HELP_LOCK_V8_4 = strategy8_4_rules.HELP_LOCK
HELP_LOCK_V8_5 = strategy8_5_rules.HELP_LOCK
HELP_LOCK_V8_6 = strategy8_6_rules.HELP_LOCK
HELP_LOCK_V9 = strategy9_rules.HELP_LOCK
HELP_LOCK_V10 = strategy10_rules.HELP_LOCK
HELP_LOCK_TOPK = strategy_topk_dropout_rules.HELP_LOCK
HELP_LOCK_SCORE_EXIT = strategy_topk_score_exit_rules.HELP_LOCK

FORBIDDEN_DEFAULT_STOCK_POOL = frozenset({
    "version9", "version9_1", "version9_2", "version9_3", "version10", "version11",
})
STOP_FILL_TOUCH = "touch"
STOP_FILL_CLOSE = "close"
STOP_FILL_ALLOWED = (STOP_FILL_TOUCH, STOP_FILL_CLOSE)
STOP_FILL_CLOSE_BOOKS = frozenset({"topk_dropout", "topk_score_exit"})


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
    sizing: str = "daily_quota"
    name_budget: float = 1_000_000.0


BOOKS: dict[str, CsvStrategyBook] = {}


def register(book: CsvStrategyBook) -> None:
    shared_tokens = set(BOOKS) | set(_alias_map())
    minute_tokens = set(MINUTE_ONLY_BOOKS)
    for registered in MINUTE_ONLY_BOOKS.values():
        minute_tokens.update(registered.aliases)
    occupied = shared_tokens | minute_tokens
    for token in (book.name, *book.aliases):
        if token in occupied:
            domain = "shared" if token in shared_tokens else "minute-only"
            raise ValueError(
                f"cannot register csv strategy {book.name!r}: token {token!r} "
                f"is already claimed by a {domain} strategy"
            )
    BOOKS[book.name] = book


def csv_strategy_names() -> tuple[str, ...]:
    return tuple(BOOKS)


def _alias_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for book in BOOKS.values():
        for alias in book.aliases:
            if alias in out and out[alias] != book.name:
                raise ValueError(
                    f"csv strategy alias {alias!r} is already claimed by "
                    f"{out[alias]!r}; cannot also map to {book.name!r}"
                )
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


def validate_hold_days(
    strategy: str, hold_days: int, *, cli_option: bool = False
) -> int:
    label = "--hold-days" if cli_option else "hold_days"
    if hold_days not in (20, 30):
        raise ValueError(f"{label} must be 20 or 30, got {hold_days}")
    raw = (strategy or "").strip().lower()
    name = next(
        (
            book.name
            for book in MINUTE_ONLY_BOOKS.values()
            if raw == book.name or raw in book.aliases
        ),
        None,
    )
    if name is None:
        name = normalize_csv_strategy(strategy)
    if hold_days != 20 and name != "version9_3":
        raise ValueError(f"{label} is supported only by version9_3")
    return hold_days


# API-only execution books. Shared/daily CLI names and HELP_LOCK use BOOKS.
# Version7 keeps its native CLI while using the main minute scheduler.
MINUTE_ONLY_BOOKS: dict[str, CsvStrategyBook] = {}


def register_minute_book(book: CsvStrategyBook) -> None:
    occupied = set(_alias_map()) | set(BOOKS) | set(MINUTE_ONLY_BOOKS)
    for registered in MINUTE_ONLY_BOOKS.values():
        occupied.update(registered.aliases)
    if book.name in occupied or any(alias in occupied for alias in book.aliases):
        raise ValueError(f"minute strategy {book.name!r} already registered")
    MINUTE_ONLY_BOOKS[book.name] = book


def normalize_minute_strategy(strategy: str) -> str:
    raw = (strategy or "").strip().lower()
    for book in MINUTE_ONLY_BOOKS.values():
        if raw == book.name or raw in book.aliases:
            return book.name
    return normalize_csv_strategy(strategy)


def get_minute_book(strategy: str) -> CsvStrategyBook:
    name = normalize_minute_strategy(strategy)
    return MINUTE_ONLY_BOOKS[name] if name in MINUTE_ONLY_BOOKS else BOOKS[name]


def apply_csv_strategy(strategy: str, **kwargs) -> dict:
    book = get_book(strategy)
    strategy9_rules.validate_sell_mode(book.name, kwargs.get("version9_sell"), kwargs.get("max_hold", False))
    validate_hold_days(book.name, kwargs.get("hold_days", 20))
    if kwargs.get("fix_s81_band_precision") and book.name != "version8_1":
        raise ValueError("fix_s81_band_precision is supported only by version8_1")
    name_budget = kwargs.pop("name_budget", None)
    ration = kwargs.pop("ration", "file_order")
    ration_seed = int(kwargs.pop("ration_seed", 0))
    min_lot_top_up = kwargs.pop("min_lot_top_up", None)
    hooks = dict(book.apply(**kwargs))
    hooks["sizing"] = book.sizing
    hooks["name_budget"] = (
        float(name_budget)
        if book.sizing == "per_name" and name_budget is not None
        else book.name_budget
    )
    hooks["ration"] = ration
    hooks["ration_seed"] = ration_seed
    hooks["allow_add"] = book.allow_add
    hooks["peak_gap_min"] = book.peak_gap_min
    hooks["book"] = book.tag
    hooks["name"] = book.name
    hooks.setdefault("force_sell_hm", None)
    hooks.setdefault("close_clear", None)
    hooks.setdefault("buy_gate", None)
    hooks.setdefault("add_gate", None)
    hooks.setdefault("allow_new_name", None)
    hooks.setdefault("index_blocks_add", True)
    hooks.setdefault("sell_gate", None)
    hooks.setdefault("reserve_limit_up", False)
    hooks.setdefault("defer_limit_up", False)
    hooks.setdefault("daily_same_bar_prefixes", ("open_board",))
    hooks.setdefault("planned_for_day", None)
    hooks.setdefault("bind_opening_held", None)
    hooks.setdefault("name_lot_budget", None)
    hooks.setdefault("step_add", None)
    hooks.setdefault("add_step", 0.20)  # s8 price-add ladder step (fraction of cost)
    hooks.setdefault("step_frac", 1.0)  # s8 price-add lot size (fraction of name_budget)
    hooks.setdefault("cost_anchor", "weighted")  # group exit-cost basis; 6.x uses first_lot
    hooks.setdefault("step_cap", None)  # per-code step lot cap; None = unlimited
    hooks.setdefault("step_stop_pct", None)  # per-step-lot own stop; None = off
    hooks.setdefault("scale_out_step", None)  # per +rise ladder selling a fraction; None = off
    hooks.setdefault("scale_out_frac", 0.05)
    hooks.setdefault("scale_out_anchor", "first_lot")  # 6.51 = weighted remaining avg
    hooks.setdefault("peak_dd_exit", None)  # peak drawdown clear; None = off
    hooks.setdefault("peak_dd_sessions", 15)
    hooks.setdefault("add_schedule", None)
    hooks.setdefault("add_schedule_trigger", None)  # "peak" = group peak arms a tier; None = px/cost
    hooks.setdefault("cont_stop_rebuy", False)
    hooks.setdefault("cont_from_rise", None)
    hooks.setdefault("cont_stop_rebuy_lift", None)
    hooks.setdefault("cont_stop_rebuy_frac", None)
    hooks.setdefault("cont_stop_rebuy_open_frac", None)
    hooks.setdefault("cont_stop_rebuy_with_schedule", False)
    hooks.setdefault("min_lot_top_up", False)
    if min_lot_top_up is not None:
        hooks["min_lot_top_up"] = bool(min_lot_top_up)
    hooks.setdefault("profit_skim", False)
    hooks.setdefault("profit_skim_step", None)
    hooks.setdefault("profit_skim_frac", None)
    hooks.setdefault("profit_skim_pro_rata", False)
    hooks.setdefault("profit_skim_keep_idle", False)
    hooks.setdefault("profit_skim_to_parking", False)
    hooks.setdefault("profit_skim_base", None)
    hooks.setdefault("index_cut", False)
    hooks.setdefault("index_cut_frac", None)
    hooks.setdefault("index_cut_min_keep", None)
    hooks.setdefault("index_blocks_s8_add", False)
    hooks.setdefault("div_to_parking", False)
    hooks.setdefault("add_step2", None)  # second (base) ladder step; None = single ladder
    hooks.setdefault("step_frac2", None)
    hooks.setdefault("tranche_max", None)
    hooks.setdefault("base_zone_caps", None)
    hooks.setdefault("add_offset", 0)  # ladder thresholds skipped before first add
    hooks.setdefault("breakout_day", None)  # daily pending-breakout step (v6.11)
    hooks.setdefault("exit_plan", None)
    hooks.setdefault("buyback_plan", None)
    hooks.setdefault("on_reclaim", None)
    hooks.setdefault("on_buy", None)
    hooks.setdefault("on_exdiv", None)
    hooks.setdefault("run_daily_day", None)
    hooks.setdefault("cash_deploy_frac", None)
    hooks.setdefault("qlib_limit_pct", None)
    hooks.setdefault("limit_up_chase", True)
    hooks.setdefault("limit_down_pending", True)
    hooks.setdefault("forbid_all_trade_at_limit", False)
    hooks.setdefault("stop_fill", STOP_FILL_TOUCH)
    if hooks.get("take_profit") is None:
        raise RuntimeError(f"{book.name} book missing take_profit")
    if hooks.get("record_params") is None:
        raise RuntimeError(f"{book.name} book missing record_params")
    record = hooks["record_params"]

    def record_money_params(st):
        record(st)
        st.stats["sizing"] = hooks["sizing"]
        st.stats["name_budget"] = hooks["name_budget"]
        st.stats["ration"] = hooks["ration"]
        st.stats["ration_seed"] = hooks["ration_seed"]
        for key in (
            "skip_cash",
            "skip_cash_notional",
            "chase_buy_fail_cash",
            "chase_buy_fail_shares",
        ):
            st.stats.setdefault(key, 0)

    hooks["record_params"] = record_money_params
    return hooks


def add_csv_strategy_arg(ap: argparse.ArgumentParser) -> None:
    names = csv_strategy_names()
    ap.add_argument(
        "--strategy",
        type=normalize_csv_strategy,
        choices=names,
        required=True,
        help="required sell book (" + ", ".join(names) + "); no default",
    )


def engine_book(strategy: str, *, hold_days: int = 20) -> str:
    book = get_book(strategy)
    validate_hold_days(book.name, hold_days)
    if book.name == "version9_3" and hold_days == 30:
        return f"{book.tag}_h30"
    return book.tag


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
        help="stop-loss fraction override (v6 0.06, v8 0.20, v9 trailing range (no override))",
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
    ap.add_argument(
        "--min-lot-top-up",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "top up a short name budget to one board lot from account cash "
            "(6.50+ default on; other books default off). "
            "--no-min-lot-top-up skips the order (industry B8-03)"
        ),
    )


def add_topk_dropout_args(ap: argparse.ArgumentParser) -> None:
    """TopkDropout score inputs + knobs; ignored by other books."""
    ap.add_argument(
        "--pred-csv",
        type=Path,
        default=None,
        help="topk_dropout: multi-day pred CSV; buy day T uses pred[T-1]",
    )
    ap.add_argument(
        "--scores-dir",
        type=Path,
        default=None,
        help="topk_dropout: dir of YYYYMMDD.csv (filename=buy day, code+score)",
    )
    ap.add_argument(
        "--topk",
        type=int,
        default=strategy_topk_dropout_rules.DEFAULT_TOPK,
        help=f"topk_dropout topk (default {strategy_topk_dropout_rules.DEFAULT_TOPK})",
    )
    ap.add_argument(
        "--n-drop",
        type=int,
        default=strategy_topk_dropout_rules.DEFAULT_N_DROP,
        help=f"topk_dropout n_drop (default {strategy_topk_dropout_rules.DEFAULT_N_DROP})",
    )
    ap.add_argument(
        "--st-daily-file",
        type=Path,
        default=None,
        help="topk_dropout: st_daily.parquet PIT (BT-B; missing path fail-closed)",
    )
    ap.add_argument(
        "--age-map-file",
        type=Path,
        default=None,
        help="topk_dropout: code\tYYYYMMDD min-buy or listing start (BT-B)",
    )
    ap.add_argument(
        "--age-days",
        type=int,
        default=60,
        help="topk_dropout: listing age trading days when calendar given (default 60)",
    )
    ap.add_argument(
        "--return-threshold-filter",
        action="store_true",
        help=(
            "topk_dropout: skip new buys whose 5-session close return > 15%% "
            "(T-1 vs T-6, loaded daily close). Independent of ST/age."
        ),
    )
    ap.add_argument(
        "--stop-fill",
        choices=STOP_FILL_ALLOWED,
        default=STOP_FILL_TOUCH,
        help=(
            "topk_dropout daily stop fill: touch=gap_open/low trigger (default); "
            "close=EOD close (minute refuses close)"
        ),
    )
    ap.add_argument(
        "--buy-state-file",
        type=Path,
        default=None,
        help=(
            "topk_dropout: MyQuant sidecar (close/ma20/ma60/winratio=$winratio); "
            "new buys only; score_exit refuses"
        ),
    )
    ap.add_argument(
        "--buy-state-rule",
        choices=("oral", "above-ma20", "above-ma20-week20", "above-ma5-ma20-week20"),
        default="oral",
        help=(
            "topk_dropout buy-state predicate. oral keeps the winratio dip OR "
            "close>MA20. above-ma20 turns the dip off and keeps close>MA20 only. "
            "above-ma20-week20 also requires close > qlib's 20-week mean "
            "(first session of each week). above-ma5-ma20-week20 also requires "
            "close > the stock's own 5-day mean (5 closes ending that day). "
            "Computed from loaded daily closes, so minute fills can use the same gates. "
            "Requires --buy-state-file. Minute still refuses --stop-fill close."
        ),
    )
    ap.add_argument(
        "--index-ma5-gate",
        action="store_true",
        help=(
            "topk_dropout: block every new buy on T when 000001.SH close on "
            "the previous session is below its 5-day mean. One index for all "
            "names. Default off."
        ),
    )
    ap.add_argument(
        "--keep-buy-vacancy",
        action="store_true",
        help=(
            "topk: if a name on the original buy list fails a buy gate, leave "
            "the seat empty. Do not walk down the score list. Size off the "
            "original list so that cash stays unspent. Default off."
        ),
    )


def resolve_daily_quota(
    strategy: str,
    requested: Optional[float],
    *,
    cash_total: float,
    fallback_quota: float = 1_000_000.0,
) -> float:
    """Money-mode pairing (plan-capital-pairing-2026-09-25).

    Explicit ``--daily-quota`` wins. Otherwise the default pairs with the
    strategy family: the qlib topk books deploy available cash qlib-style
    (quota = cash_total, then × risk_degree ÷ day's names); every other
    book keeps the stock-pool heritage quota default.
    """
    if requested is not None:
        return float(requested)
    if normalize_csv_strategy(strategy) in ("topk_dropout", "topk_score_exit"):
        return float(cash_total)
    return float(fallback_quota)


def add_csv_backtest_common_args(
    ap: argparse.ArgumentParser,
    *,
    repo: str | Path,
    end_default: str,
    cash_total_default: float,
    daily_quota_default: float,
    end_help: Optional[str] = None,
    start_default: str = "20251023",
    workers_default: int = 16,
) -> None:
    """Shared daily/minute CSV backtest CLI flags (names + defaults preserved).

    Adds ``--start/--end/--cash-total/--daily-quota/--workers/--pool-dir`` plus
    strategy book args. Callers then add mode-specific flags (daily
    ``--out-dir``; minute ``--no-cache`` / ``--rebuild-cache``).
    """
    ap.add_argument("--version9-sell", choices=strategy9_rules.SELL_MODES, default=None)
    ap.add_argument("--max-hold", action="store_true",
                    help="version9: enable 20-trading-day force-flat (force_sell:max_hold); default off")
    ap.add_argument("--no-range-stop", action="store_true",
                    help="version9: turn off the rolling 20-bar range stop; default on")
    ap.add_argument(
        "--hold-days",
        type=int,
        choices=(20, 30),
        default=20,
        help="version9_3 maximum hold in trading days (default 20)",
    )
    ap.add_argument("--start", default=start_default)
    ap.add_argument(
        "--fix-s81-band-precision", action="store_true",
        help="version8_1 exact decimal-input peak-return bands (default OFF)",
    )
    if end_help is None:
        ap.add_argument("--end", default=end_default)
    else:
        ap.add_argument("--end", default=end_default, help=end_help)
    ap.add_argument("--cash-total", type=float, default=cash_total_default)
    ap.add_argument(
        "--rule-profile",
        choices=("legacy", "industry"),
        default="industry",
    )
    ap.add_argument(
        "--daily-quota",
        type=float,
        default=None,
        help=(
            "explicit per-day buy quota override; when omitted the default "
            "pairs with the strategy family (topk family = cash_total qlib "
            "risk-degree deploy; other books = 1,000,000/day stock-pool quota)"
        ),
    )
    ap.add_argument(
        "--name-budget",
        type=float,
        default=None,
        help="per-name budget override; only for per_name books; default = the book's own name_budget",
    )
    ap.add_argument(
        "--ration",
        choices=("file_order", "seeded_shuffle"),
        default="file_order",
        help="capital-ration order (default: file_order)",
    )
    ap.add_argument(
        "--ration-seed",
        type=int,
        default=0,
        help="base seed for seeded_shuffle; derived independently per date",
    )
    ap.add_argument("--workers", type=int, default=workers_default)
    ap.add_argument("--pool-dir", type=Path, default=Path(repo) / "stock_pool")
    add_csv_strategy_arg(ap)
    add_strategy6_ratio_args(ap)
    add_topk_dropout_args(ap)


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


def resolve_research_pool_dir(
    strategy: str,
    pool_dir: Path | None,
    *,
    repo: str | Path,
) -> Path:
    """1–6/8 default to ``stock_pool/``; version9/10/11 refuse that tree."""
    name = normalize_csv_strategy(strategy)
    default = Path(repo) / "stock_pool"
    chosen = default if pool_dir is None else Path(pool_dir)
    if name in FORBIDDEN_DEFAULT_STOCK_POOL and is_repo_stock_pool(
        chosen, repo=Path(repo)
    ):
        exporter = (
            "export_strategy11_pool.py"
            if name == "version11"
            else "export_strategy9_pool.py"
        )
        raise SystemExit(
            f"{name} requires --pool-dir from {exporter}; "
            f"refusing stock_pool/: {chosen}"
        )
    return chosen


def resolve_stop_fill(raw) -> str:
    if raw is None or str(raw).strip() == "":
        return STOP_FILL_TOUCH
    v = str(raw).strip().lower()
    if v not in STOP_FILL_ALLOWED:
        raise SystemExit(f"--stop-fill must be touch or close, got {raw}")
    return v


def csv_run_kwargs_from_args(args) -> dict:
    name = normalize_csv_strategy(getattr(args, "strategy", "") or "")
    hold_days = getattr(args, "hold_days", 20)
    try:
        validate_hold_days(name, hold_days, cli_option=True)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    try:
        strategy9_rules.validate_sell_mode(name, getattr(args, "version9_sell", None), getattr(args, "max_hold", False))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    budget_override = getattr(args, "name_budget", None)
    if budget_override is not None:
        if not budget_override > 0:
            raise SystemExit(f"--name-budget must be positive, got {budget_override}")
        if BOOKS[name].sizing != "per_name":
            raise SystemExit(f"--name-budget applies only to per_name books; {name} is {BOOKS[name].sizing}")
    if getattr(args, "fix_s81_band_precision", False) and name != "version8_1":
        raise SystemExit("--fix-s81-band-precision is supported only by version8_1")
    if getattr(args, "max_hold", False) and name != "version9":
        raise SystemExit("--max-hold is supported only by version9")
    if getattr(args, "no_range_stop", False) and name != "version9":
        raise SystemExit("--no-range-stop is supported only by version9")
    if getattr(args, "no_range_stop", False) and getattr(args, "version9_sell", None) is not None:
        raise SystemExit("--no-range-stop cannot be combined with --version9-sell")
    fill_s = getattr(args, "stop_fill", None)
    fill_s = None if fill_s is None else str(fill_s).strip().lower()
    if fill_s == "":
        fill_s = None
    if fill_s is not None and fill_s not in STOP_FILL_ALLOWED:
        raise SystemExit(f"--stop-fill must be touch or close, got {fill_s}")
    if fill_s == STOP_FILL_CLOSE and name not in STOP_FILL_CLOSE_BOOKS:
        raise SystemExit("--stop-fill close is only for topk_dropout / topk_score_exit")
    kwargs = get_book(name).run_kwargs(args)
    kwargs["ration"] = getattr(args, "ration", "file_order")
    kwargs["ration_seed"] = int(getattr(args, "ration_seed", 0))
    rule_profile = getattr(args, "rule_profile", "industry")
    if rule_profile != "industry":
        kwargs["rule_profile"] = rule_profile
    if get_book(name).sizing == "per_name":
        kwargs["name_budget"] = (
            float(budget_override)
            if budget_override is not None
            else float(get_book(name).name_budget)
        )
    if getattr(args, "min_lot_top_up", None) is not None:
        kwargs["min_lot_top_up"] = bool(args.min_lot_top_up)
    return kwargs


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


def _apply_version3(
    *, stop_pct: Optional[float] = None, take_profit=None, record_params=None, **_
) -> dict:
    resolved = strategy3_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days):
        return strategy3_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy3_rules.record_strategy3_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": _tp if take_profit is None else take_profit,
        "record_params": _rec if record_params is None else record_params,
        "reserve_limit_up": True,
        "force_sell_hm": None,
        "daily_same_bar_prefixes": ("open_board",),
    }


def _run_kwargs_version3(args) -> dict:
    return {"strategy": "version3", "stop_pct": _stop_override_from_args(args)}


def _apply_version4(
    *, stop_pct: Optional[float] = None, take_profit=None, record_params=None, **_
) -> dict:
    del stop_pct

    def _tp(*args):
        del args
        return None

    def _rec(st):
        strategy4_rules.record_strategy4_params(st, stop_pct=None)

    return {
        "stop_pct": None,
        "take_profit": _tp if take_profit is None else take_profit,
        "record_params": _rec if record_params is None else record_params,
        "buy_gate": strategy4_rules.buy_gate,
        "sell_gate": strategy4_rules.sell_gate,
        "force_sell_hm": None,
        "reserve_limit_up": False,
    }


def _run_kwargs_version4(args) -> dict:
    if getattr(args, "stop_pct", None) is not None:
        raise SystemExit("--stop-pct is not supported for version4 (no stop loss)")
    return {"strategy": "version4"}


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
    del profit_base, tiers, tier_default
    resolved_stop = strategy6_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_rules.record_strategy6_params(st, stop_pct=resolved_stop)

    return {
        "stop_pct": resolved_stop,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
    }


def _run_kwargs_version6(args) -> dict:
    return {"strategy": "version6", **strategy6_kwargs_from_args(args)}


def _apply_version12(*, index_block_new=None, **_) -> dict:
    from backtest.research import strategy12_engine

    return {
        "stop_pct": None,
        "take_profit": strategy12_rules.take_profit_reason,
        "record_params": strategy12_rules.record_strategy12_params,
        "reserve_limit_up": False,
        "defer_limit_up": False,
        "daily_same_bar_prefixes": (),
        "allow_new_name": strategy12_rules.allow_new_name_from_gate(index_block_new),
        "index_blocks_add": strategy12_rules.INDEX_BLOCKS_ADD,
        "exit_plan": strategy12_engine.plan_exit,
        "buyback_plan": strategy12_engine.plan_buybacks,
        "on_reclaim": strategy12_engine.on_reclaim,
        "on_buy": strategy12_engine.on_buy,
        "on_exdiv": strategy12_engine.on_exdiv,
        "run_daily_day": strategy12_engine.run_daily_day,
        "minute_session": strategy12_engine.MinuteSession,
    }


def _run_kwargs_version12(args) -> dict:
    if getattr(args, "stop_pct", None) is not None:
        raise SystemExit("--stop-pct is not supported by version12 (book MA10 stop)")
    return {"strategy": "version12"}


def _apply_version8(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    index_block_new=None,
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
        "add_gate": strategy8_rules.may_add,
        "step_add": (
            strategy8_rules.step_add_due if strategy8_rules.ADD_STEP > 0 else None
        ),
        "name_lot_budget": strategy8_rules.lot_budget,
        "allow_new_name": strategy8_rules.allow_new_name_from_gate(index_block_new),
        "index_blocks_add": strategy8_rules.INDEX_BLOCKS_ADD,
        "reserve_limit_up": strategy8_rules.RESERVE_LIMIT_UP,
        "defer_limit_up": strategy8_rules.DEFER_LIMIT_UP,
        "daily_same_bar_prefixes": ("open_board",),
    }


def _run_kwargs_version8(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version8", "stop_pct": stop}


def _apply_version8_1(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    fix_s81_band_precision: bool = False,
    **_,
) -> dict:
    resolved = strategy8_1_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy8_1_rules.take_profit_reason(
            px, cost, peak, n_days, fix_s81_band_precision=fix_s81_band_precision,
        )

    def _rec(st):
        strategy8_1_rules.record_strategy8_1_params(st, stop_pct=resolved)
        if fix_s81_band_precision:
            st.stats["fix_s81_band_precision"] = True

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
    }


def _run_kwargs_version8_1(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version8_1", "stop_pct": stop,
            **({"fix_s81_band_precision": True}
               if getattr(args, "fix_s81_band_precision", False) else {})}


def _apply_version8_2(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy8_2_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy8_2_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy8_2_rules.record_strategy8_2_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
    }


def _run_kwargs_version8_2(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version8_2", "stop_pct": stop}


def _apply_version8_3(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    index_block_new=None,
    **_,
) -> dict:
    resolved = strategy8_3_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _rec(st):
        strategy8_3_rules.record_strategy8_3_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": (
            strategy8_3_rules.take_profit_reason if take_profit is None else take_profit
        ),
        "record_params": record_params if record_params is not None else _rec,
        "add_gate": strategy8_3_rules.may_add,
        "name_lot_budget": strategy8_3_rules.lot_budget,
        "allow_new_name": strategy8_3_rules.allow_new_name_from_gate(index_block_new),
        "index_blocks_add": strategy8_3_rules.INDEX_BLOCKS_ADD,
    }


def _run_kwargs_version8_3(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version8_3", "stop_pct": stop}


def _apply_version8_4(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    index_block_new=None,
    **_,
) -> dict:
    resolved = strategy8_4_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _rec(st):
        strategy8_4_rules.record_strategy8_4_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": (
            strategy8_4_rules.take_profit_reason if take_profit is None else take_profit
        ),
        "record_params": record_params if record_params is not None else _rec,
        "add_gate": strategy8_4_rules.may_add,
        "step_add": (
            strategy8_4_rules.step_add_due if strategy8_4_rules.ADD_STEP > 0 else None
        ),
        "name_lot_budget": strategy8_4_rules.lot_budget,
        "allow_new_name": strategy8_4_rules.allow_new_name_from_gate(index_block_new),
        "index_blocks_add": strategy8_4_rules.INDEX_BLOCKS_ADD,
        "reserve_limit_up": strategy8_4_rules.RESERVE_LIMIT_UP,
        "defer_limit_up": strategy8_4_rules.DEFER_LIMIT_UP,
        "daily_same_bar_prefixes": ("open_board",),
    }


def _run_kwargs_version8_4(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version8_4", "stop_pct": stop}


def _apply_version8_5(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    index_block_new=None,
    **_,
) -> dict:
    resolved = strategy8_5_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _rec(st):
        strategy8_5_rules.record_strategy8_5_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": (
            strategy8_5_rules.take_profit_reason if take_profit is None else take_profit
        ),
        "record_params": record_params if record_params is not None else _rec,
        "add_gate": strategy8_5_rules.may_add,
        "step_add": (
            strategy8_5_rules.step_add_due if strategy8_5_rules.ADD_STEP > 0 else None
        ),
        "name_lot_budget": strategy8_5_rules.lot_budget,
        "allow_new_name": strategy8_5_rules.allow_new_name_from_gate(index_block_new),
        "index_blocks_add": strategy8_5_rules.INDEX_BLOCKS_ADD,
        "reserve_limit_up": strategy8_5_rules.RESERVE_LIMIT_UP,
        "defer_limit_up": strategy8_5_rules.DEFER_LIMIT_UP,
        "close_clear": strategy8_5_rules.t4_close_reason,
        "daily_same_bar_prefixes": strategy8_5_rules.SAME_BAR_PREFIXES,
    }


def _run_kwargs_version8_5(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version8_5", "stop_pct": stop}


def _apply_version8_6(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    index_block_new=None,
    **_,
) -> dict:
    resolved = strategy8_6_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _rec(st):
        strategy8_6_rules.record_strategy8_6_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": (
            strategy8_6_rules.take_profit_reason if take_profit is None else take_profit
        ),
        "record_params": record_params if record_params is not None else _rec,
        "add_gate": strategy8_6_rules.may_add,
        "step_add": None,
        "name_lot_budget": strategy8_6_rules.lot_budget,
        "allow_new_name": strategy8_6_rules.allow_new_name_from_gate(index_block_new),
        "index_blocks_add": strategy8_6_rules.INDEX_BLOCKS_ADD,
        "reserve_limit_up": strategy8_6_rules.RESERVE_LIMIT_UP,
        "defer_limit_up": strategy8_6_rules.DEFER_LIMIT_UP,
        "close_clear": strategy8_6_rules.t1_close_reason,
        "daily_same_bar_prefixes": strategy8_6_rules.SAME_BAR_PREFIXES,
    }


def _run_kwargs_version8_6(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version8_6", "stop_pct": stop}


def _apply_version9_2(*, stop_pct=None, **_):
    from backtest.research import strategy9_2_rules as rules, strategy9_2_engine as engine
    if stop_pct is not None:
        raise SystemExit("version9_2 does not accept --stop-pct")
    return {"stop_pct": None, "take_profit": rules.take_profit_reason,
            "record_params": rules.record_strategy9_2_params,
            "on_buy": engine.on_buy, "exit_plan": engine.plan_exit,
            "run_daily_day": engine.run_daily_day, "minute_session": engine.MinuteSession}


def _run_kwargs_version9_2(args):
    if getattr(args, "stop_pct", None) is not None:
        raise SystemExit("version9_2 does not accept --stop-pct")
    return {"strategy": "version9_2"}


def _apply_version9_3(*, hold_days=20, stop_pct=None, **_):
    if stop_pct is not None:
        raise SystemExit("version9_3 does not accept --stop-pct")

    def take_profit(px, cost, peak, n_days):
        reason = strategy9_rules.take_profit_reason(
            px, cost, peak, n_days, max_hold=False
        )
        if reason:
            return reason
        return strategy9_3_rules.max_hold_reason(
            px, cost, peak, n_days, hold_days=hold_days
        )

    def minute_take_profit(px, cost, peak, n_days):
        return strategy9_rules.take_profit_reason(
            px, cost, peak, n_days, max_hold=False
        )

    def minute_next_open_exit(px, cost, peak, n_days):
        return strategy9_3_rules.max_hold_reason(
            px, cost, peak, n_days, hold_days=hold_days
        )

    def record_params(st):
        strategy9_3_rules.record_strategy9_3_params(st, hold_days=hold_days)

    return {
        "stop_pct": None,
        "take_profit": take_profit,
        "record_params": record_params,
        "bind_absolute_exit": strategy9_3_rules.bind_absolute_exit,
        "limit_up_chase": False,
        "pool_buy_at_open": True,
        "minute_take_profit": minute_take_profit,
        "minute_next_open_exit": minute_next_open_exit,
    }


def _run_kwargs_version9_3(args):
    if getattr(args, "stop_pct", None) is not None:
        raise SystemExit("version9_3 does not accept --stop-pct")
    return {
        "strategy": "version9_3",
        "hold_days": getattr(args, "hold_days", 20),
    }


def _apply_version9(
    *, version9_sell=None, max_hold: bool = False, range_stop: bool = True, stop_pct: Optional[float] = None, take_profit=None, record_params=None, **_
) -> dict:
    if stop_pct is not None:
        raise SystemExit("version9 does not accept --stop-pct")
    if version9_sell is not None and not range_stop:
        raise SystemExit("--no-range-stop cannot be combined with --version9-sell")

    strategy9_rules.validate_sell_mode("version9", version9_sell, max_hold)
    if version9_sell is not None:
        def record(st):
            strategy9_rules.record_strategy9_params(st, max_hold=max_hold)
            st.stats.update(sell_mode=version9_sell,
                            stop_mode=("range_amp_20_trailing" if version9_sell == "range_amp_tp_amp" else
                                       "mean_tr_20_yuan_" + ("3" if version9_sell == "mean_tr3_tp10" else "2")),
                            profit_target=(0.10 if version9_sell == "mean_tr3_tp10" else
                                           "range_amp_20_trailing" if version9_sell == "range_amp_tp_amp" else None))
        return dict(stop_pct=None, version9_exit=lambda frame, day: strategy9_rules.version9_exit(frame, day, version9_sell),
                    take_profit=lambda *args: None, record_params=record)

    def _tp(px, cost, peak, n_days):
        return strategy9_rules.take_profit_reason(px, cost, peak, n_days, max_hold=max_hold)

    def _rec(st):
        strategy9_rules.record_strategy9_params(st, max_hold=max_hold, range_stop=range_stop)

    hooks = {
        "stop_pct": None,
        "take_profit": _tp if take_profit is None else take_profit,
        "record_params": _rec if record_params is None else record_params,
    }
    if range_stop:
        hooks["stop_range"] = strategy9_rules.stop_range_amplitude
    return hooks


def _run_kwargs_version9(args) -> dict:
    if getattr(args, "stop_pct", None) is not None:
        raise SystemExit("version9 does not accept --stop-pct")
    return {
        "strategy": "version9",
        "max_hold": bool(getattr(args, "max_hold", False)),
        "range_stop": not bool(getattr(args, "no_range_stop", False)),
        "version9_sell": getattr(args, "version9_sell", None),
    }


def _apply_version10(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    profit_base: Optional[float] = None,
    tiers: Optional[dict] = None,
    tier_default: Optional[float] = None,
    **_,
) -> dict:
    resolved_stop = strategy10_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    pb = strategy10_rules.PROFIT_BASE if profit_base is None else float(profit_base)
    tier_map = dict(tiers or strategy10_rules.TIERS)
    td = strategy10_rules.TIER_DEFAULT if tier_default is None else float(tier_default)

    def _tp(px, cost, peak, n_days=1):
        return strategy10_rules.take_profit_reason(
            px, cost, peak, n_days, profit_base=pb, tiers=tier_map, tier_default=td
        )

    def _rec(st):
        strategy10_rules.record_strategy10_params(
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


def _run_kwargs_version10(args) -> dict:
    return {"strategy": "version10", **strategy6_kwargs_from_args(args)}


def _apply_version11(*, take_profit=None, record_params=None, **_) -> dict:
    return {
        "stop_pct": None,
        "take_profit": strategy11_rules.take_profit_reason
        if take_profit is None
        else take_profit,
        "record_params": strategy11_rules.record_strategy11_params
        if record_params is None
        else record_params,
        "limit_up_chase": False,
        "minute_open": True,
        "eod_exit": strategy11_rules.eod_exit,
        "skip_sold_today": True,
    }


def _run_kwargs_version11(args) -> dict:
    if getattr(args, "stop_pct", None) is not None:
        raise SystemExit("--stop-pct is not supported for version11")
    return {"strategy": "version11"}


def _apply_topk_dropout(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    scores_by_day: Optional[dict] = None,
    topk: Optional[int] = None,
    n_drop: Optional[int] = None,
    eligible_buy=None,
    stop_fill=None,
    keep_buy_vacancy: bool = False,
    **_,
) -> dict:
    if not scores_by_day:
        raise SystemExit(
            "topk_dropout fail-closed: scores_by_day required "
            "(pass --pred-csv or --scores-dir)"
        )
    topk_i = strategy_topk_dropout_rules.DEFAULT_TOPK if topk is None else int(topk)
    n_drop_i = (
        strategy_topk_dropout_rules.DEFAULT_N_DROP if n_drop is None else int(n_drop)
    )
    # Omit → book default 0.10. Explicit 0 → no stop (arm 0 / qlib align).
    if stop_pct is None:
        resolved_stop = strategy_topk_dropout_rules.STOP_PCT
    elif float(stop_pct) == 0:
        resolved_stop = None
    else:
        resolved_stop = float(stop_pct)
    resolved_fill = resolve_stop_fill(stop_fill)

    day_state: dict = {"ds": None, "opening_held": ()}

    def _tp(*args):
        del args
        return None

    def _rec(st):
        strategy_topk_dropout_rules.record_topk_dropout_params(
            st,
            stop_pct=resolved_stop,
            topk=topk_i,
            n_drop=n_drop_i,
            stop_fill=resolved_fill,
        )

    return {
        "stop_pct": resolved_stop,
        "stop_fill": resolved_fill,
        "take_profit": _tp if take_profit is None else take_profit,
        "record_params": _rec if record_params is None else record_params,
        "sell_gate": strategy_topk_dropout_rules.make_sell_gate(
            scores_by_day=scores_by_day,
            topk=topk_i,
            n_drop=n_drop_i,
            day_state=day_state,
        ),
        "planned_for_day": strategy_topk_dropout_rules.make_planned_for_day(
            scores_by_day=scores_by_day,
            topk=topk_i,
            n_drop=n_drop_i,
            day_state=day_state,
            eligible_buy=eligible_buy,
            keep_vacancy=keep_buy_vacancy,
        ),
        "bind_opening_held": strategy_topk_dropout_rules.make_bind_opening_held(
            day_state,
            scores_by_day,
            topk_i,
            n_drop_i,
        ),
        "daily_same_bar_prefixes": strategy_topk_dropout_rules.SAME_BAR_PREFIXES,
        "cash_deploy_frac": strategy_topk_dropout_rules.QLIB_CASH_DEPLOY,
        "qlib_limit_pct": strategy_topk_dropout_rules.QLIB_LIMIT_PCT,
        "limit_up_chase": False,
        "limit_down_pending": False,
        "forbid_all_trade_at_limit": True,
        "buy_gate": None,
        "force_sell_hm": None,
        "reserve_limit_up": False,
    }


def _apply_topk_score_exit(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    scores_by_day: Optional[dict] = None,
    topk: Optional[int] = None,
    n_drop: Optional[int] = None,
    eligible_buy=None,
    stop_fill=None,
    keep_buy_vacancy: bool = False,
    **_,
) -> dict:
    if not scores_by_day:
        raise SystemExit(
            "topk_score_exit fail-closed: scores_by_day required "
            "(pass --pred-csv or --scores-dir)"
        )
    topk_i = strategy_topk_score_exit_rules.DEFAULT_TOPK if topk is None else int(topk)
    n_drop_i = (
        strategy_topk_score_exit_rules.DEFAULT_N_DROP if n_drop is None else int(n_drop)
    )
    if stop_pct is None:
        resolved_stop = strategy_topk_score_exit_rules.STOP_PCT
    elif float(stop_pct) == 0:
        resolved_stop = None
    else:
        resolved_stop = float(stop_pct)
    resolved_fill = resolve_stop_fill(stop_fill)

    day_state: dict = {"ds": None, "opening_held": ()}

    def _tp(*args):
        del args
        return None

    def _rec(st):
        strategy_topk_score_exit_rules.record_topk_score_exit_params(
            st,
            stop_pct=resolved_stop,
            topk=topk_i,
            n_drop=n_drop_i,
            stop_fill=resolved_fill,
        )

    return {
        "stop_pct": resolved_stop,
        "stop_fill": resolved_fill,
        "take_profit": _tp if take_profit is None else take_profit,
        "record_params": _rec if record_params is None else record_params,
        "sell_gate": strategy_topk_score_exit_rules.make_sell_gate(
            scores_by_day=scores_by_day,
            topk=topk_i,
            n_drop=n_drop_i,
            day_state=day_state,
        ),
        "planned_for_day": strategy_topk_score_exit_rules.make_planned_for_day(
            scores_by_day=scores_by_day,
            topk=topk_i,
            n_drop=n_drop_i,
            day_state=day_state,
            eligible_buy=eligible_buy,
            keep_vacancy=keep_buy_vacancy,
        ),
        "bind_opening_held": strategy_topk_score_exit_rules.make_bind_opening_held(
            day_state,
            scores_by_day,
            topk_i,
            n_drop_i,
        ),
        "daily_same_bar_prefixes": strategy_topk_score_exit_rules.SAME_BAR_PREFIXES,
        "cash_deploy_frac": strategy_topk_score_exit_rules.QLIB_CASH_DEPLOY,
        "qlib_limit_pct": strategy_topk_score_exit_rules.QLIB_LIMIT_PCT,
        "limit_up_chase": False,
        "limit_down_pending": False,
        "forbid_all_trade_at_limit": True,
        "buy_gate": None,
        "force_sell_hm": None,
        "reserve_limit_up": False,
    }


def _run_kwargs_topk_dropout(args) -> dict:
    from backtest.research.topk_dropout_scores import load_scores_from_args

    buy_rule = str(getattr(args, "buy_state_rule", "oral") or "oral")
    if (
        buy_rule
        in (
            "above-ma20",
            "above-ma20-week20",
            "above-ma5-ma20-week20",
        )
        and getattr(args, "buy_state_file", None) is None
    ):
        raise SystemExit(f"--buy-state-rule {buy_rule} requires --buy-state-file")

    scores_by_day = load_scores_from_args(
        pred_csv=getattr(args, "pred_csv", None),
        scores_dir=getattr(args, "scores_dir", None),
    )
    stop = getattr(args, "stop_pct", None)
    if stop is not None and float(stop) != 0 and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1) or 0 to disable, got {stop}")
    # Omit → book 0.10. --stop-pct 0 stays 0 (apply disables).
    if stop is None:
        resolved_stop = strategy_topk_dropout_rules.STOP_PCT
    elif float(stop) == 0:
        resolved_stop = 0.0
    else:
        resolved_stop = float(stop)
    topk = int(getattr(args, "topk", strategy_topk_dropout_rules.DEFAULT_TOPK))
    n_drop = int(getattr(args, "n_drop", strategy_topk_dropout_rules.DEFAULT_N_DROP))
    if topk < 0 or n_drop < 0:
        raise SystemExit(f"--topk/--n-drop must be >= 0, got {topk}/{n_drop}")
    out = {
        "strategy": "topk_dropout",
        "scores_by_day": scores_by_day,
        "topk": topk,
        "n_drop": n_drop,
        "stop_pct": resolved_stop,
        "stop_fill": resolve_stop_fill(getattr(args, "stop_fill", None)),
    }
    st_daily = getattr(args, "st_daily_file", None)
    age_map = getattr(args, "age_map_file", None)
    age_days = int(getattr(args, "age_days", 60))
    buy_state = getattr(args, "buy_state_file", None)
    buy_state_rule = str(getattr(args, "buy_state_rule", "oral") or "oral")
    index_ma5 = bool(getattr(args, "index_ma5_gate", False))
    if (
        st_daily is not None
        or age_map is not None
        or buy_state is not None
        or index_ma5
    ):
        from backtest.research.topk_dropout_eligibility import make_eligible_buy

        out["eligible_buy"] = make_eligible_buy(
            st_daily_file=st_daily,
            age_map_file=age_map,
            age_days=age_days,
            buy_state_file=buy_state,
            index_ma5_gate=index_ma5,
            buy_state_rule=buy_state_rule,
        )
    if buy_state_rule in ("above-ma20-week20", "above-ma5-ma20-week20"):
        out["week_ma_gate"] = True
    if buy_state_rule == "above-ma5-ma20-week20":
        out["ma5_gate"] = True
    if bool(getattr(args, "keep_buy_vacancy", False)):
        out["keep_buy_vacancy"] = True
    if bool(getattr(args, "return_threshold_filter", False)):
        out["return_threshold_filter"] = True
    return out


def _run_kwargs_topk_score_exit(args) -> dict:
    if getattr(args, "buy_state_file", None) is not None:
        raise SystemExit("topk_score_exit refuses --buy-state-file; use topk_dropout")
    out = _run_kwargs_topk_dropout(args)
    out["strategy"] = "topk_score_exit"
    return out


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
        name="version3",
        tag=strategy3_rules.BOOK_TAG,
        aliases=("3", "v3", "version3"),
        allow_add=strategy3_rules.ALLOW_ADD,
        peak_gap_min=strategy3_rules.PEAK_GAP_MIN,
        help_lock=strategy3_rules.HELP_LOCK,
        apply=_apply_version3,
        run_kwargs=_run_kwargs_version3,
    )
)
register(
    CsvStrategyBook(
        name="version4",
        tag=strategy4_rules.BOOK_TAG,
        aliases=("4", "v4", "version4"),
        allow_add=strategy4_rules.ALLOW_ADD,
        peak_gap_min=strategy4_rules.PEAK_GAP_MIN,
        help_lock=strategy4_rules.HELP_LOCK,
        apply=_apply_version4,
        run_kwargs=_run_kwargs_version4,
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
        name="version6_1",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_1_rules.BOOK_TAG,
        aliases=("6.1", "6_1", "v6.1", "v6_1", "version6_1"),
        allow_add=strategy6_1_rules.ALLOW_ADD,
        peak_gap_min=strategy6_1_rules.PEAK_GAP_MIN,
        help_lock=strategy6_1_rules.HELP_LOCK,
        apply=_apply_version6_1,
        run_kwargs=_run_kwargs_version6_1,
    )
)
register(
    CsvStrategyBook(
        name="version6_2",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_2_rules.BOOK_TAG,
        aliases=("6.2", "6_2", "v6.2", "v6_2", "version6_2"),
        allow_add=strategy6_2_rules.ALLOW_ADD,
        peak_gap_min=strategy6_2_rules.PEAK_GAP_MIN,
        help_lock=strategy6_2_rules.HELP_LOCK,
        apply=_apply_version6_2,
        run_kwargs=_run_kwargs_version6_2,
    )
)
register(
    CsvStrategyBook(
        name="version6_3",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_3_rules.BOOK_TAG,
        aliases=("6.3", "6_3", "v6.3", "v6_3", "version6_3"),
        allow_add=strategy6_3_rules.ALLOW_ADD,
        peak_gap_min=strategy6_3_rules.PEAK_GAP_MIN,
        help_lock=strategy6_3_rules.HELP_LOCK,
        apply=_apply_version6_3,
        run_kwargs=_run_kwargs_version6_3,
    )
)
register(
    CsvStrategyBook(
        name="version6_4",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_4_rules.BOOK_TAG,
        aliases=("6.4", "6_4", "v6.4", "v6_4", "version6_4"),
        allow_add=strategy6_4_rules.ALLOW_ADD,
        peak_gap_min=strategy6_4_rules.PEAK_GAP_MIN,
        help_lock=strategy6_4_rules.HELP_LOCK,
        apply=_apply_version6_4,
        run_kwargs=_run_kwargs_version6_4,
    )
)
register(
    CsvStrategyBook(
        name="version6_5",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_5_rules.BOOK_TAG,
        aliases=("6.5", "6_5", "v6.5", "v6_5", "version6_5"),
        allow_add=strategy6_5_rules.ALLOW_ADD,
        peak_gap_min=strategy6_5_rules.PEAK_GAP_MIN,
        help_lock=strategy6_5_rules.HELP_LOCK,
        apply=_apply_version6_5,
        run_kwargs=_run_kwargs_version6_5,
    )
)
register(
    CsvStrategyBook(
        name="version6_6",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_6_rules.BOOK_TAG,
        aliases=("6.6", "6_6", "v6.6", "v6_6", "version6_6"),
        allow_add=strategy6_6_rules.ALLOW_ADD,
        peak_gap_min=strategy6_6_rules.PEAK_GAP_MIN,
        help_lock=strategy6_6_rules.HELP_LOCK,
        apply=_apply_version6_6,
        run_kwargs=_run_kwargs_version6_6,
    )
)
register(
    CsvStrategyBook(
        name="version6_7",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_7_rules.BOOK_TAG,
        aliases=("6.7", "6_7", "v6.7", "v6_7", "version6_7"),
        allow_add=strategy6_7_rules.ALLOW_ADD,
        peak_gap_min=strategy6_7_rules.PEAK_GAP_MIN,
        help_lock=strategy6_7_rules.HELP_LOCK,
        apply=_apply_version6_7,
        run_kwargs=_run_kwargs_version6_7,
    )
)
register(
    CsvStrategyBook(
        name="version6_8",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_8_rules.BOOK_TAG,
        aliases=("6.8", "6_8", "v6.8", "v6_8", "version6_8"),
        allow_add=strategy6_8_rules.ALLOW_ADD,
        peak_gap_min=strategy6_8_rules.PEAK_GAP_MIN,
        help_lock=strategy6_8_rules.HELP_LOCK,
        apply=_apply_version6_8,
        run_kwargs=_run_kwargs_version6_8,
    )
)
register(
    CsvStrategyBook(
        name="version6_9",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_9_rules.BOOK_TAG,
        aliases=("6.9", "6_9", "v6.9", "v6_9", "version6_9"),
        allow_add=strategy6_9_rules.ALLOW_ADD,
        peak_gap_min=strategy6_9_rules.PEAK_GAP_MIN,
        help_lock=strategy6_9_rules.HELP_LOCK,
        apply=_apply_version6_9,
        run_kwargs=_run_kwargs_version6_9,
    )
)
register(
    CsvStrategyBook(
        name="version6_10",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_10_rules.BOOK_TAG,
        aliases=("6.10", "6_10", "v6.10", "v6_10", "version6_10"),
        allow_add=strategy6_10_rules.ALLOW_ADD,
        peak_gap_min=strategy6_10_rules.PEAK_GAP_MIN,
        help_lock=strategy6_10_rules.HELP_LOCK,
        apply=_apply_version6_10,
        run_kwargs=_run_kwargs_version6_10,
    )
)
register(
    CsvStrategyBook(
        name="version6_11",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_11_rules.BOOK_TAG,
        aliases=("6.11", "6_11", "v6.11", "v6_11", "version6_11"),
        allow_add=strategy6_11_rules.ALLOW_ADD,
        peak_gap_min=strategy6_11_rules.PEAK_GAP_MIN,
        help_lock=strategy6_11_rules.HELP_LOCK,
        apply=_apply_version6_11,
        run_kwargs=_run_kwargs_version6_11,
    )
)
register(
    CsvStrategyBook(
        name="version6_12",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_12_rules.BOOK_TAG,
        aliases=("6.12", "6_12", "v6.12", "v6_12", "version6_12"),
        allow_add=strategy6_12_rules.ALLOW_ADD,
        peak_gap_min=strategy6_12_rules.PEAK_GAP_MIN,
        help_lock=strategy6_12_rules.HELP_LOCK,
        apply=_apply_version6_12,
        run_kwargs=_run_kwargs_version6_12,
    )
)
register(
    CsvStrategyBook(
        name="version6_13",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_13_rules.BOOK_TAG,
        aliases=("6.13", "6_13", "v6.13", "v6_13", "version6_13"),
        allow_add=strategy6_13_rules.ALLOW_ADD,
        peak_gap_min=strategy6_13_rules.PEAK_GAP_MIN,
        help_lock=strategy6_13_rules.HELP_LOCK,
        apply=_apply_version6_13,
        run_kwargs=_run_kwargs_version6_13,
    )
)
register(
    CsvStrategyBook(
        name="version6_14",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_14_rules.BOOK_TAG,
        aliases=("6.14", "6_14", "v6.14", "v6_14", "version6_14"),
        allow_add=strategy6_14_rules.ALLOW_ADD,
        peak_gap_min=strategy6_14_rules.PEAK_GAP_MIN,
        help_lock=strategy6_14_rules.HELP_LOCK,
        apply=_apply_version6_14,
        run_kwargs=_run_kwargs_version6_14,
    )
)
register(
    CsvStrategyBook(
        name="version6_15",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_15_rules.BOOK_TAG,
        aliases=("6.15", "6_15", "v6.15", "v6_15", "version6_15"),
        allow_add=strategy6_15_rules.ALLOW_ADD,
        peak_gap_min=strategy6_15_rules.PEAK_GAP_MIN,
        help_lock=strategy6_15_rules.HELP_LOCK,
        apply=_apply_version6_15,
        run_kwargs=_run_kwargs_version6_15,
    )
)
register(
    CsvStrategyBook(
        name="version6_16",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_16_rules.BOOK_TAG,
        aliases=("6.16", "6_16", "v6.16", "v6_16", "version6_16"),
        allow_add=strategy6_16_rules.ALLOW_ADD,
        peak_gap_min=strategy6_16_rules.PEAK_GAP_MIN,
        help_lock=strategy6_16_rules.HELP_LOCK,
        apply=_apply_version6_16,
        run_kwargs=_run_kwargs_version6_16,
    )
)
register(
    CsvStrategyBook(
        name="version6_17",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_17_rules.BOOK_TAG,
        aliases=("6.17", "6_17", "v6.17", "v6_17", "version6_17"),
        allow_add=strategy6_17_rules.ALLOW_ADD,
        peak_gap_min=strategy6_17_rules.PEAK_GAP_MIN,
        help_lock=strategy6_17_rules.HELP_LOCK,
        apply=_apply_version6_17,
        run_kwargs=_run_kwargs_version6_17,
    )
)
register(
    CsvStrategyBook(
        name="version6_18",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_18_rules.BOOK_TAG,
        aliases=("6.18", "6_18", "v6.18", "v6_18", "version6_18"),
        allow_add=strategy6_18_rules.ALLOW_ADD,
        peak_gap_min=strategy6_18_rules.PEAK_GAP_MIN,
        help_lock=strategy6_18_rules.HELP_LOCK,
        apply=_apply_version6_18,
        run_kwargs=_run_kwargs_version6_18,
    )
)
register(
    CsvStrategyBook(
        name="version6_19",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_19_rules.BOOK_TAG,
        aliases=("6.19", "6_19", "v6.19", "v6_19", "version6_19"),
        allow_add=strategy6_19_rules.ALLOW_ADD,
        peak_gap_min=strategy6_19_rules.PEAK_GAP_MIN,
        help_lock=strategy6_19_rules.HELP_LOCK,
        apply=_apply_version6_19,
        run_kwargs=_run_kwargs_version6_19,
    )
)
register(
    CsvStrategyBook(
        name="version6_20",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_20_rules.BOOK_TAG,
        aliases=("6.20", "6_20", "v6.20", "v6_20", "version6_20"),
        allow_add=strategy6_20_rules.ALLOW_ADD,
        peak_gap_min=strategy6_20_rules.PEAK_GAP_MIN,
        help_lock=strategy6_20_rules.HELP_LOCK,
        apply=_apply_version6_20,
        run_kwargs=_run_kwargs_version6_20,
    )
)
register(
    CsvStrategyBook(
        name="version6_21",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_21_rules.BOOK_TAG,
        aliases=("6.21", "6_21", "v6.21", "v6_21", "version6_21"),
        allow_add=strategy6_21_rules.ALLOW_ADD,
        peak_gap_min=strategy6_21_rules.PEAK_GAP_MIN,
        help_lock=strategy6_21_rules.HELP_LOCK,
        apply=_apply_version6_21,
        run_kwargs=_run_kwargs_version6_21,
    )
)
register(
    CsvStrategyBook(
        name="version6_22",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_22_rules.BOOK_TAG,
        aliases=("6.22", "6_22", "v6.22", "v6_22", "version6_22"),
        allow_add=strategy6_22_rules.ALLOW_ADD,
        peak_gap_min=strategy6_22_rules.PEAK_GAP_MIN,
        help_lock=strategy6_22_rules.HELP_LOCK,
        apply=_apply_version6_22,
        run_kwargs=_run_kwargs_version6_22,
    )
)
register(
    CsvStrategyBook(
        name="version6_23",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_23_rules.BOOK_TAG,
        aliases=("6.23", "6_23", "v6.23", "v6_23", "version6_23"),
        allow_add=strategy6_23_rules.ALLOW_ADD,
        peak_gap_min=strategy6_23_rules.PEAK_GAP_MIN,
        help_lock=strategy6_23_rules.HELP_LOCK,
        apply=_apply_version6_23,
        run_kwargs=_run_kwargs_version6_23,
    )
)
register(
    CsvStrategyBook(
        name="version6_24",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_24_rules.BOOK_TAG,
        aliases=("6.24", "6_24", "v6.24", "v6_24", "version6_24"),
        allow_add=strategy6_24_rules.ALLOW_ADD,
        peak_gap_min=strategy6_24_rules.PEAK_GAP_MIN,
        help_lock=strategy6_24_rules.HELP_LOCK,
        apply=_apply_version6_24,
        run_kwargs=_run_kwargs_version6_24,
    )
)
register(
    CsvStrategyBook(
        name="version6_25",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_25_rules.BOOK_TAG,
        aliases=("6.25", "6_25", "v6.25", "v6_25", "version6_25"),
        allow_add=strategy6_25_rules.ALLOW_ADD,
        peak_gap_min=strategy6_25_rules.PEAK_GAP_MIN,
        help_lock=strategy6_25_rules.HELP_LOCK,
        apply=_apply_version6_25,
        run_kwargs=_run_kwargs_version6_25,
    )
)
register(
    CsvStrategyBook(
        name="version6_26",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_26_rules.BOOK_TAG,
        aliases=("6.26", "6_26", "v6.26", "v6_26", "version6_26"),
        allow_add=strategy6_26_rules.ALLOW_ADD,
        peak_gap_min=strategy6_26_rules.PEAK_GAP_MIN,
        help_lock=strategy6_26_rules.HELP_LOCK,
        apply=_apply_version6_26,
        run_kwargs=_run_kwargs_version6_26,
    )
)
register(
    CsvStrategyBook(
        name="version6_27",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_27_rules.BOOK_TAG,
        aliases=("6.27", "6_27", "v6.27", "v6_27", "version6_27"),
        allow_add=strategy6_27_rules.ALLOW_ADD,
        peak_gap_min=strategy6_27_rules.PEAK_GAP_MIN,
        help_lock=strategy6_27_rules.HELP_LOCK,
        apply=_apply_version6_27,
        run_kwargs=_run_kwargs_version6_27,
    )
)
register(
    CsvStrategyBook(
        name="version6_28",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_28_rules.BOOK_TAG,
        aliases=("6.28", "6_28", "v6.28", "v6_28", "version6_28"),
        allow_add=strategy6_28_rules.ALLOW_ADD,
        peak_gap_min=strategy6_28_rules.PEAK_GAP_MIN,
        help_lock=strategy6_28_rules.HELP_LOCK,
        apply=_apply_version6_28,
        run_kwargs=_run_kwargs_version6_28,
    )
)
register(
    CsvStrategyBook(
        name="version6_29",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_29_rules.BOOK_TAG,
        aliases=("6.29", "6_29", "v6.29", "v6_29", "version6_29"),
        allow_add=strategy6_29_rules.ALLOW_ADD,
        peak_gap_min=strategy6_29_rules.PEAK_GAP_MIN,
        help_lock=strategy6_29_rules.HELP_LOCK,
        apply=_apply_version6_29,
        run_kwargs=_run_kwargs_version6_29,
    )
)
register(
    CsvStrategyBook(
        name="version6_30",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_30_rules.BOOK_TAG,
        aliases=("6.30", "6_30", "v6.30", "v6_30", "version6_30"),
        allow_add=strategy6_30_rules.ALLOW_ADD,
        peak_gap_min=strategy6_30_rules.PEAK_GAP_MIN,
        help_lock=strategy6_30_rules.HELP_LOCK,
        apply=_apply_version6_30,
        run_kwargs=_run_kwargs_version6_30,
    )
)
register(
    CsvStrategyBook(
        name="version6_31",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_31_rules.BOOK_TAG,
        aliases=("6.31", "6_31", "v6.31", "v6_31", "version6_31"),
        allow_add=strategy6_31_rules.ALLOW_ADD,
        peak_gap_min=strategy6_31_rules.PEAK_GAP_MIN,
        help_lock=strategy6_31_rules.HELP_LOCK,
        apply=_apply_version6_31,
        run_kwargs=_run_kwargs_version6_31,
    )
)
register(
    CsvStrategyBook(
        name="version6_32",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_32_rules.BOOK_TAG,
        aliases=("6.32", "6_32", "v6.32", "v6_32", "version6_32"),
        allow_add=strategy6_32_rules.ALLOW_ADD,
        peak_gap_min=strategy6_32_rules.PEAK_GAP_MIN,
        help_lock=strategy6_32_rules.HELP_LOCK,
        apply=_apply_version6_32,
        run_kwargs=_run_kwargs_version6_32,
    )
)

register(
    CsvStrategyBook(
        name="version6_33",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_33_rules.BOOK_TAG,
        aliases=("6.33", "6_33", "v6.33", "v6_33", "version6_33"),
        allow_add=strategy6_33_rules.ALLOW_ADD,
        peak_gap_min=strategy6_33_rules.PEAK_GAP_MIN,
        help_lock=strategy6_33_rules.HELP_LOCK,
        apply=_apply_version6_33,
        run_kwargs=_run_kwargs_version6_33,
    )
)
register(
    CsvStrategyBook(
        name="version6_34",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_34_rules.BOOK_TAG,
        aliases=("6.34", "6_34", "v6.34", "v6_34", "version6_34"),
        allow_add=strategy6_34_rules.ALLOW_ADD,
        peak_gap_min=strategy6_34_rules.PEAK_GAP_MIN,
        help_lock=strategy6_34_rules.HELP_LOCK,
        apply=_apply_version6_34,
        run_kwargs=_run_kwargs_version6_34,
    )
)
register(
    CsvStrategyBook(
        name="version6_35",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_35_rules.BOOK_TAG,
        aliases=("6.35", "6_35", "v6.35", "v6_35", "version6_35"),
        allow_add=strategy6_35_rules.ALLOW_ADD,
        peak_gap_min=strategy6_35_rules.PEAK_GAP_MIN,
        help_lock=strategy6_35_rules.HELP_LOCK,
        apply=_apply_version6_35,
        run_kwargs=_run_kwargs_version6_35,
    )
)

register(
    CsvStrategyBook(
        name="version6_36",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_36_rules.BOOK_TAG,
        aliases=("6.36", "6_36", "v6.36", "v6_36", "version6_36"),
        allow_add=strategy6_36_rules.ALLOW_ADD,
        peak_gap_min=strategy6_36_rules.PEAK_GAP_MIN,
        help_lock=strategy6_36_rules.HELP_LOCK,
        apply=_apply_version6_36,
        run_kwargs=_run_kwargs_version6_36,
    )
)
register(
    CsvStrategyBook(
        name="version6_37",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_37_rules.BOOK_TAG,
        aliases=("6.37", "6_37", "v6.37", "v6_37", "version6_37"),
        allow_add=strategy6_37_rules.ALLOW_ADD,
        peak_gap_min=strategy6_37_rules.PEAK_GAP_MIN,
        help_lock=strategy6_37_rules.HELP_LOCK,
        apply=_apply_version6_37,
        run_kwargs=_run_kwargs_version6_37,
    )
)
register(
    CsvStrategyBook(
        name="version6_38",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_38_rules.BOOK_TAG,
        aliases=("6.38", "6_38", "v6.38", "v6_38", "version6_38"),
        allow_add=strategy6_38_rules.ALLOW_ADD,
        peak_gap_min=strategy6_38_rules.PEAK_GAP_MIN,
        help_lock=strategy6_38_rules.HELP_LOCK,
        apply=_apply_version6_38,
        run_kwargs=_run_kwargs_version6_38,
    )
)

register(
    CsvStrategyBook(
        name="version6_39",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_39_rules.BOOK_TAG,
        aliases=("6.39", "6_39", "v6.39", "v6_39", "version6_39"),
        allow_add=strategy6_39_rules.ALLOW_ADD,
        peak_gap_min=strategy6_39_rules.PEAK_GAP_MIN,
        help_lock=strategy6_39_rules.HELP_LOCK,
        apply=_apply_version6_39,
        run_kwargs=_run_kwargs_version6_39,
    )
)
register(
    CsvStrategyBook(
        name="version6_40",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_40_rules.BOOK_TAG,
        aliases=("6.40", "6_40", "v6.40", "v6_40", "version6_40"),
        allow_add=strategy6_40_rules.ALLOW_ADD,
        peak_gap_min=strategy6_40_rules.PEAK_GAP_MIN,
        help_lock=strategy6_40_rules.HELP_LOCK,
        apply=_apply_version6_40,
        run_kwargs=_run_kwargs_version6_40,
    )
)
register(
    CsvStrategyBook(
        name="version6_41",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_41_rules.BOOK_TAG,
        aliases=("6.41", "6_41", "v6.41", "v6_41", "version6_41"),
        allow_add=strategy6_41_rules.ALLOW_ADD,
        peak_gap_min=strategy6_41_rules.PEAK_GAP_MIN,
        help_lock=strategy6_41_rules.HELP_LOCK,
        apply=_apply_version6_41,
        run_kwargs=_run_kwargs_version6_41,
    )
)

register(
    CsvStrategyBook(
        name="version6_42",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_42_rules.BOOK_TAG,
        aliases=("6.42", "6_42", "v6.42", "v6_42", "version6_42"),
        allow_add=strategy6_42_rules.ALLOW_ADD,
        peak_gap_min=strategy6_42_rules.PEAK_GAP_MIN,
        help_lock=strategy6_42_rules.HELP_LOCK,
        apply=_apply_version6_42,
        run_kwargs=_run_kwargs_version6_42,
    )
)
register(
    CsvStrategyBook(
        name="version6_43",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_43_rules.BOOK_TAG,
        aliases=("6.43", "6_43", "v6.43", "v6_43", "version6_43"),
        allow_add=strategy6_43_rules.ALLOW_ADD,
        peak_gap_min=strategy6_43_rules.PEAK_GAP_MIN,
        help_lock=strategy6_43_rules.HELP_LOCK,
        apply=_apply_version6_43,
        run_kwargs=_run_kwargs_version6_43,
    )
)
register(
    CsvStrategyBook(
        name="version6_44",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_44_rules.BOOK_TAG,
        aliases=("6.44", "6_44", "v6.44", "v6_44", "version6_44"),
        allow_add=strategy6_44_rules.ALLOW_ADD,
        peak_gap_min=strategy6_44_rules.PEAK_GAP_MIN,
        help_lock=strategy6_44_rules.HELP_LOCK,
        apply=_apply_version6_44,
        run_kwargs=_run_kwargs_version6_44,
    )
)


register(
    CsvStrategyBook(
        name="version6_45",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_45_rules.BOOK_TAG,
        aliases=("6.45", "6_45", "v6.45", "v6_45", "version6_45"),
        allow_add=strategy6_45_rules.ALLOW_ADD,
        peak_gap_min=strategy6_45_rules.PEAK_GAP_MIN,
        help_lock=strategy6_45_rules.HELP_LOCK,
        apply=_apply_version6_45,
        run_kwargs=_run_kwargs_version6_45,
    )
)


register(
    CsvStrategyBook(
        name="version6_46",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_46_rules.BOOK_TAG,
        aliases=("6.46", "6_46", "v6.46", "v6_46", "version6_46"),
        allow_add=strategy6_46_rules.ALLOW_ADD,
        peak_gap_min=strategy6_46_rules.PEAK_GAP_MIN,
        help_lock=strategy6_46_rules.HELP_LOCK,
        apply=_apply_version6_46,
        run_kwargs=_run_kwargs_version6_46,
    )
)


register(
    CsvStrategyBook(
        name='version6_47', sizing='per_name', name_budget=1_000_000.0,
        tag=strategy6_47_rules.BOOK_TAG,
        aliases=('6.47', '6_47', 'v6.47', 'v6_47', 'version6_47'),
        allow_add=strategy6_47_rules.ALLOW_ADD,
        peak_gap_min=strategy6_47_rules.PEAK_GAP_MIN,
        help_lock=strategy6_47_rules.HELP_LOCK,
        apply=_apply_version6_47,
        run_kwargs=_run_kwargs_version6_47,
    )
)

register(
    CsvStrategyBook(
        name="version6_48",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_48_rules.BOOK_TAG,
        aliases=("6.48", "6_48", "v6.48", "v6_48", "version6_48"),
        allow_add=strategy6_48_rules.ALLOW_ADD,
        peak_gap_min=strategy6_48_rules.PEAK_GAP_MIN,
        help_lock=strategy6_48_rules.HELP_LOCK,
        apply=_apply_version6_48,
        run_kwargs=_run_kwargs_version6_48,
    )
)

register(
    CsvStrategyBook(
        name="version6_49",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_49_rules.BOOK_TAG,
        aliases=("6.49", "6_49", "v6.49", "v6_49", "version6_49"),
        allow_add=strategy6_49_rules.ALLOW_ADD,
        peak_gap_min=strategy6_49_rules.PEAK_GAP_MIN,
        help_lock=strategy6_49_rules.HELP_LOCK,
        apply=_apply_version6_49,
        run_kwargs=_run_kwargs_version6_49,
    )
)

register(
    CsvStrategyBook(
        name="version6_50",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_50_rules.BOOK_TAG,
        aliases=("6.50", "6_50", "v6.50", "v6_50", "version6_50"),
        allow_add=strategy6_50_rules.ALLOW_ADD,
        peak_gap_min=strategy6_50_rules.PEAK_GAP_MIN,
        help_lock=strategy6_50_rules.HELP_LOCK,
        apply=_apply_version6_50,
        run_kwargs=_run_kwargs_version6_50,
    )
)

register(
    CsvStrategyBook(
        name="version6_51",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_51_rules.BOOK_TAG,
        aliases=("6.51", "6_51", "v6.51", "v6_51", "version6_51"),
        allow_add=strategy6_51_rules.ALLOW_ADD,
        peak_gap_min=strategy6_51_rules.PEAK_GAP_MIN,
        help_lock=strategy6_51_rules.HELP_LOCK,
        apply=_apply_version6_51,
        run_kwargs=_run_kwargs_version6_51,
    )
)

register(
    CsvStrategyBook(
        name="version6_52",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_52_rules.BOOK_TAG,
        aliases=("6.52", "6_52", "v6.52", "v6_52", "version6_52"),
        allow_add=strategy6_52_rules.ALLOW_ADD,
        peak_gap_min=strategy6_52_rules.PEAK_GAP_MIN,
        help_lock=strategy6_52_rules.HELP_LOCK,
        apply=_apply_version6_52,
        run_kwargs=_run_kwargs_version6_52,
    )
)

register(
    CsvStrategyBook(
        name="version6_53",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_53_rules.BOOK_TAG,
        aliases=("6.53", "6_53", "v6.53", "v6_53", "version6_53"),
        allow_add=strategy6_53_rules.ALLOW_ADD,
        peak_gap_min=strategy6_53_rules.PEAK_GAP_MIN,
        help_lock=strategy6_53_rules.HELP_LOCK,
        apply=_apply_version6_53,
        run_kwargs=_run_kwargs_version6_53,
    )
)

register(
    CsvStrategyBook(
        name="version6_54",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_54_rules.BOOK_TAG,
        aliases=("6.54", "6_54", "v6.54", "v6_54", "version6_54"),
        allow_add=strategy6_54_rules.ALLOW_ADD,
        peak_gap_min=strategy6_54_rules.PEAK_GAP_MIN,
        help_lock=strategy6_54_rules.HELP_LOCK,
        apply=_apply_version6_54,
        run_kwargs=_run_kwargs_version6_54,
    )
)

register(
    CsvStrategyBook(
        name="version6_55",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy6_55_rules.BOOK_TAG,
        aliases=("6.55", "6_55", "v6.55", "v6_55", "version6_55"),
        allow_add=strategy6_55_rules.ALLOW_ADD,
        peak_gap_min=strategy6_55_rules.PEAK_GAP_MIN,
        help_lock=strategy6_55_rules.HELP_LOCK,
        apply=_apply_version6_55,
        run_kwargs=_run_kwargs_version6_55,
    )
)

register(
    CsvStrategyBook(
        name="version8",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy8_rules.BOOK_TAG,
        aliases=("8", "v8", "version8"),
        allow_add=strategy8_rules.ALLOW_ADD,
        peak_gap_min=strategy8_rules.PEAK_GAP_MIN,
        help_lock=strategy8_rules.HELP_LOCK,
        apply=_apply_version8,
        run_kwargs=_run_kwargs_version8,
    )
)
register(
    CsvStrategyBook(
        name="version8_1",
        tag=strategy8_1_rules.BOOK_TAG,
        aliases=("8.1", "8_1", "v8.1", "v8_1", "version8_1"),
        allow_add=strategy8_1_rules.ALLOW_ADD,
        peak_gap_min=strategy8_1_rules.PEAK_GAP_MIN,
        help_lock=strategy8_1_rules.HELP_LOCK,
        apply=_apply_version8_1,
        run_kwargs=_run_kwargs_version8_1,
    )
)
register(
    CsvStrategyBook(
        name="version8_2",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy8_2_rules.BOOK_TAG,
        aliases=("8.2", "8_2", "v8.2", "v8_2", "version8_2"),
        allow_add=strategy8_2_rules.ALLOW_ADD,
        peak_gap_min=strategy8_2_rules.PEAK_GAP_MIN,
        help_lock=strategy8_2_rules.HELP_LOCK,
        apply=_apply_version8_2,
        run_kwargs=_run_kwargs_version8_2,
    )
)
register(
    CsvStrategyBook(
        name="version8_3",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy8_3_rules.BOOK_TAG,
        aliases=("8.3", "8_3", "v8.3", "v8_3", "version8_3"),
        allow_add=strategy8_3_rules.ALLOW_ADD,
        peak_gap_min=strategy8_3_rules.PEAK_GAP_MIN,
        help_lock=strategy8_3_rules.HELP_LOCK,
        apply=_apply_version8_3,
        run_kwargs=_run_kwargs_version8_3,
    )
)
register(
    CsvStrategyBook(
        name="version8_4",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy8_4_rules.BOOK_TAG,
        aliases=("8.4", "8_4", "v8.4", "v8_4", "version8_4"),
        allow_add=strategy8_4_rules.ALLOW_ADD,
        peak_gap_min=strategy8_4_rules.PEAK_GAP_MIN,
        help_lock=strategy8_4_rules.HELP_LOCK,
        apply=_apply_version8_4,
        run_kwargs=_run_kwargs_version8_4,
    )
)
register(
    CsvStrategyBook(
        name="version8_5",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy8_5_rules.BOOK_TAG,
        aliases=("8.5", "8_5", "v8.5", "v8_5", "version8_5"),
        allow_add=strategy8_5_rules.ALLOW_ADD,
        peak_gap_min=strategy8_5_rules.PEAK_GAP_MIN,
        help_lock=strategy8_5_rules.HELP_LOCK,
        apply=_apply_version8_5,
        run_kwargs=_run_kwargs_version8_5,
    )
)
register(
    CsvStrategyBook(
        name="version8_6",
        sizing="per_name",
        name_budget=1_000_000.0,
        tag=strategy8_6_rules.BOOK_TAG,
        aliases=("8.6", "8_6", "v8.6", "v8_6", "version8_6"),
        allow_add=strategy8_6_rules.ALLOW_ADD,
        peak_gap_min=strategy8_6_rules.PEAK_GAP_MIN,
        help_lock=strategy8_6_rules.HELP_LOCK,
        apply=_apply_version8_6,
        run_kwargs=_run_kwargs_version8_6,
    )
)
register(
    CsvStrategyBook(
        name="version9",
        tag=strategy9_rules.BOOK_TAG,
        aliases=("9", "v9", "version9"),
        allow_add=strategy9_rules.ALLOW_ADD,
        peak_gap_min=strategy9_rules.PEAK_GAP_MIN,
        help_lock=strategy9_rules.HELP_LOCK,
        apply=_apply_version9,
        run_kwargs=_run_kwargs_version9,
    )
)
register(CsvStrategyBook(
    name="version9_2", tag=strategy9_2_rules.BOOK_TAG,
    aliases=("9.2", "9_2", "v9.2", "v9_2", "version9_2"),
    allow_add=True, peak_gap_min=0, help_lock=strategy9_2_rules.HELP_LOCK,
    apply=_apply_version9_2, run_kwargs=_run_kwargs_version9_2, sizing="per_name",
))
register(CsvStrategyBook(
    name="version9_3", tag=strategy9_3_rules.BOOK_TAG,
    aliases=("9.3", "9_3", "v9.3", "v9_3", "version9_3"),
    allow_add=strategy9_3_rules.ALLOW_ADD,
    peak_gap_min=strategy9_3_rules.PEAK_GAP_MIN,
    help_lock=strategy9_3_rules.HELP_LOCK,
    apply=_apply_version9_3, run_kwargs=_run_kwargs_version9_3,
))
register(
    CsvStrategyBook(
        name="version10",
        tag=strategy10_rules.BOOK_TAG,
        aliases=("10", "v10", "version10"),
        allow_add=strategy10_rules.ALLOW_ADD,
        peak_gap_min=strategy10_rules.PEAK_GAP_MIN,
        help_lock=strategy10_rules.HELP_LOCK,
        apply=_apply_version10,
        run_kwargs=_run_kwargs_version10,
    )
)

register(
    CsvStrategyBook(
        name="version11",
        tag=strategy11_rules.BOOK_TAG,
        aliases=("11", "v11", "version11"),
        allow_add=strategy11_rules.ALLOW_ADD,
        peak_gap_min=strategy11_rules.PEAK_GAP_MIN,
        help_lock=strategy11_rules.HELP_LOCK,
        apply=_apply_version11,
        run_kwargs=_run_kwargs_version11,
    )
)
register(
    CsvStrategyBook(
        name="version12",
        tag=strategy12_rules.BOOK_TAG,
        aliases=("12", "v12", "version12"),
        allow_add=True,
        peak_gap_min=0,
        help_lock=strategy12_rules.HELP_LOCK,
        apply=_apply_version12,
        run_kwargs=_run_kwargs_version12,
        sizing="per_name",
        name_budget=1_000_000.0,
    )
)
register(
    CsvStrategyBook(
        name="topk_dropout",
        tag=strategy_topk_dropout_rules.BOOK_TAG,
        aliases=("topk", "version_topk", "topk_dropout"),
        allow_add=strategy_topk_dropout_rules.ALLOW_ADD,
        peak_gap_min=strategy_topk_dropout_rules.PEAK_GAP_MIN,
        help_lock=strategy_topk_dropout_rules.HELP_LOCK,
        apply=_apply_topk_dropout,
        run_kwargs=_run_kwargs_topk_dropout,
    )
)
register(
    CsvStrategyBook(
        name="topk_score_exit",
        tag=strategy_topk_score_exit_rules.BOOK_TAG,
        aliases=("topk_score_exit",),
        allow_add=strategy_topk_score_exit_rules.ALLOW_ADD,
        peak_gap_min=strategy_topk_score_exit_rules.PEAK_GAP_MIN,
        help_lock=strategy_topk_score_exit_rules.HELP_LOCK,
        apply=_apply_topk_score_exit,
        run_kwargs=_run_kwargs_topk_score_exit,
    )
)


def _apply_version9_1(*, stop_pct=None, **_):
    if stop_pct is not None:
        raise SystemExit("version9_1 does not accept --stop-pct")
    return dict(stop_pct=None, take_profit=lambda *a: None,
                record_params=strategy9_1_rules.record_strategy9_1_params,
                bind_absolute_exit=strategy9_1_rules.bind,
                limit_up_chase=False, step_add=lambda lots, px: True)


def _run_kwargs_version9_1(args):
    if getattr(args, "stop_pct", None) is not None:
        raise SystemExit("version9_1 does not accept --stop-pct")
    return {"strategy": "version9_1"}

register(CsvStrategyBook(
    name="version9_1", tag="v9_1",
    aliases=("9.1", "9_1", "v9.1", "v9_1", "version9_1"),
    allow_add=True, peak_gap_min=0, help_lock=strategy9_1_rules.HELP_LOCK,
    apply=_apply_version9_1, run_kwargs=_run_kwargs_version9_1,
    sizing="per_name", name_budget=strategy9_1_rules.NAME_BUDGET,
))


from backtest.research.strategy7_engine import minute_hooks as _apply_version7

register_minute_book(CsvStrategyBook(
    name="version7", tag="v7", aliases=("7", "v7", "version7"),
    allow_add=True, peak_gap_min=0, help_lock="", apply=_apply_version7,
    run_kwargs=lambda args: {"strategy": "version7"}, sizing="per_name",
))
