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
    strategy10_rules,
    strategy11_rules,
    strategy12_rules,
    strategy_topk_dropout_rules,
    strategy_topk_score_exit_rules,
)
from backtest.research.csv_pool import is_repo_stock_pool

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

FORBIDDEN_DEFAULT_STOCK_POOL = frozenset({"version9", "version9_1", "version9_2", "version10", "version11"})
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
    strategy9_rules.validate_sell_mode(book.name, kwargs.get("version9_sell"), kwargs.get("max_hold", False))
    if kwargs.get("fix_s81_band_precision") and book.name != "version8_1":
        raise ValueError("fix_s81_band_precision is supported only by version8_1")
    name_budget = kwargs.pop("name_budget", None)
    ration = kwargs.pop("ration", "file_order")
    ration_seed = int(kwargs.pop("ration_seed", 0))
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
    hooks.setdefault("peak_dd_exit", None)  # peak drawdown clear; None = off
    hooks.setdefault("peak_dd_sessions", 15)
    hooks.setdefault("add_schedule", None)
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
    if get_book(name).sizing == "per_name":
        kwargs["name_budget"] = (
            float(budget_override)
            if budget_override is not None
            else float(get_book(name).name_budget)
        )
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


def _apply_version6_1(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_1_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_1_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_1_rules.record_strategy6_1_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_1_rules.lot_budget,
        "cost_anchor": "first_lot",
    }


def _run_kwargs_version6_1(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_1", "stop_pct": stop}


def _apply_version6_2(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_2_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_2_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_2_rules.record_strategy6_2_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_2_rules.lot_budget,
        "cost_anchor": "first_lot",
        "add_step": strategy6_2_rules.ADD_STEP,
        "step_frac": strategy6_2_rules.STEP_FRAC,
    }


def _run_kwargs_version6_2(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_2", "stop_pct": stop}


def _apply_version6_3(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_3_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_3_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_3_rules.record_strategy6_3_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_3_rules.lot_budget,
        "cost_anchor": "first_lot",
        "add_step": strategy6_3_rules.ADD_STEP,
        "step_frac": strategy6_3_rules.STEP_FRAC,
    }


def _run_kwargs_version6_3(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_3", "stop_pct": stop}


def _apply_version6_4(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_4_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_4_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_4_rules.record_strategy6_4_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_4_rules.lot_budget,
        "add_step": strategy6_4_rules.ADD_STEP,
        "step_frac": strategy6_4_rules.STEP_FRAC,
        "step_cap": strategy6_4_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
    }


def _run_kwargs_version6_4(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_4", "stop_pct": stop}


def _apply_version6_5(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_5_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_5_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_5_rules.record_strategy6_5_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_5_rules.lot_budget,
        "add_step": strategy6_5_rules.ADD_STEP,
        "step_frac": strategy6_5_rules.STEP_FRAC,
        "step_cap": strategy6_5_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
    }


def _run_kwargs_version6_5(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_5", "stop_pct": stop}


def _apply_version6_6(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_6_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_6_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_6_rules.record_strategy6_6_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_6_rules.lot_budget,
        "add_step": strategy6_6_rules.ADD_STEP,
        "step_frac": strategy6_6_rules.STEP_FRAC,
        "step_cap": strategy6_6_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
    }


def _run_kwargs_version6_6(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_6", "stop_pct": stop}


def _apply_version6_7(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_7_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_7_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_7_rules.record_strategy6_7_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_7_rules.lot_budget,
        "add_step": strategy6_7_rules.ADD_STEP,
        "step_frac": strategy6_7_rules.STEP_FRAC,
        "step_cap": strategy6_7_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
    }


def _run_kwargs_version6_7(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_7", "stop_pct": stop}


def _apply_version6_8(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_8_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_8_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_8_rules.record_strategy6_8_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_8_rules.lot_budget,
        "add_step": strategy6_8_rules.ADD_STEP,
        "step_frac": strategy6_8_rules.STEP_FRAC,
        "step_cap": strategy6_8_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_8_rules.STEP_STOP_PCT,
    }


def _run_kwargs_version6_8(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_8", "stop_pct": stop}


def _apply_version6_9(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_9_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_9_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_9_rules.record_strategy6_9_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_9_rules.lot_budget,
        "add_step": strategy6_9_rules.ADD_STEP,
        "step_frac": strategy6_9_rules.STEP_FRAC,
        "add_step2": strategy6_9_rules.ADD_STEP2,
        "step_frac2": strategy6_9_rules.STEP_FRAC2,
        "tranche_max": strategy6_9_rules.TRANCHE_MAX,
        "base_zone_caps": strategy6_9_rules.BASE_ZONE_CAPS,
        "step_cap": strategy6_9_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
    }


def _run_kwargs_version6_9(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_9", "stop_pct": stop}


def _apply_version6_10(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_10_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_10_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_10_rules.record_strategy6_10_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_10_rules.lot_budget,
        "add_step": strategy6_10_rules.ADD_STEP,
        "step_frac": strategy6_10_rules.STEP_FRAC,
        "add_step2": strategy6_10_rules.ADD_STEP2,
        "step_frac2": strategy6_10_rules.STEP_FRAC2,
        "tranche_max": strategy6_10_rules.TRANCHE_MAX,
        "base_zone_caps": strategy6_10_rules.BASE_ZONE_CAPS,
        "step_cap": strategy6_10_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_10_rules.STEP_STOP_PCT,
    }


def _run_kwargs_version6_10(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_10", "stop_pct": stop}


def _apply_version6_11(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    from backtest.research.csv_simulate_loop import run_breakout_day

    resolved = strategy6_11_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_11_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_11_rules.record_strategy6_11_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_11_rules.lot_budget,
        "add_step": strategy6_11_rules.ADD_STEP,
        "step_frac": strategy6_11_rules.STEP_FRAC,
        "add_offset": strategy6_11_rules.ADD_OFFSET,
        "tranche_max": strategy6_11_rules.TRANCHE_MAX,
        "step_cap": strategy6_11_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "breakout_day": run_breakout_day,
        # 突破书不在名单日成交：标准池买整日置空（买由 breakout_day 驱动）。
        "planned_for_day": lambda ds, held_codes: [],
    }


def _run_kwargs_version6_11(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_11", "stop_pct": stop}


def _apply_version6_12(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    from backtest.research.csv_simulate_loop import run_breakout_day

    resolved = strategy6_12_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_12_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_12_rules.record_strategy6_12_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_12_rules.lot_budget,
        "add_step": strategy6_12_rules.ADD_STEP,
        "step_frac": strategy6_12_rules.STEP_FRAC,
        "add_offset": strategy6_12_rules.ADD_OFFSET,
        "tranche_max": strategy6_12_rules.TRANCHE_MAX,
        "step_cap": strategy6_12_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "breakout_day": run_breakout_day,
        "planned_for_day": lambda ds, held_codes: [],
    }


def _run_kwargs_version6_12(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_12", "stop_pct": stop}


def _apply_version6_13(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_13_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_13_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_13_rules.record_strategy6_13_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_13_rules.lot_budget,
        "add_step": strategy6_13_rules.ADD_STEP,
        "step_frac": strategy6_13_rules.STEP_FRAC,
        "step_cap": strategy6_13_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_13_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_13_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_13_rules.SCALE_OUT_FRAC,
    }


def _run_kwargs_version6_13(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_13", "stop_pct": stop}


def _apply_version6_14(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_14_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_14_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_14_rules.record_strategy6_14_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_14_rules.lot_budget,
        "add_step": strategy6_14_rules.ADD_STEP,
        "step_frac": strategy6_14_rules.STEP_FRAC,
        "step_cap": strategy6_14_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_14_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_14_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_14_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_14_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_14_rules.PEAK_DD_SESSIONS,
    }


def _run_kwargs_version6_14(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_14", "stop_pct": stop}


def _apply_version6_15(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_15_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_15_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_15_rules.record_strategy6_15_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_15_rules.lot_budget,
        "add_step": strategy6_15_rules.ADD_STEP,
        "step_frac": strategy6_15_rules.STEP_FRAC,
        "step_cap": strategy6_15_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_15_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_15_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_15_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_15_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_15_rules.PEAK_DD_SESSIONS,
    }


def _run_kwargs_version6_15(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_15", "stop_pct": stop}


def _apply_version6_16(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_16_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_16_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_16_rules.record_strategy6_16_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_16_rules.lot_budget,
        "add_step": strategy6_16_rules.ADD_STEP,
        "step_frac": strategy6_16_rules.STEP_FRAC,
        "step_cap": strategy6_16_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_16_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_16_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_16_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_16_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_16_rules.PEAK_DD_SESSIONS,
    }


def _run_kwargs_version6_16(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_16", "stop_pct": stop}


def _apply_version6_17(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_17_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_17_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_17_rules.record_strategy6_17_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_17_rules.lot_budget,
        "add_step": strategy6_17_rules.ADD_STEP,
        "step_frac": strategy6_17_rules.STEP_FRAC,
        "step_cap": strategy6_17_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_17_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_17_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_17_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_17_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_17_rules.PEAK_DD_SESSIONS,
    }


def _run_kwargs_version6_17(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_17", "stop_pct": stop}


def _apply_version6_18(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_18_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_18_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_18_rules.record_strategy6_18_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_18_rules.lot_budget,
        "add_step": strategy6_18_rules.ADD_STEP,
        "step_frac": strategy6_18_rules.STEP_FRAC,
        "step_cap": strategy6_18_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_18_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_18_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_18_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_18_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_18_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_18_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_18(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_18", "stop_pct": stop}


def _apply_version6_19(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_19_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_19_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_19_rules.record_strategy6_19_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_19_rules.lot_budget,
        "add_step": strategy6_19_rules.ADD_STEP,
        "step_frac": strategy6_19_rules.STEP_FRAC,
        "step_cap": strategy6_19_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_19_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_19_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_19_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_19_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_19_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_19_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_19(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_19", "stop_pct": stop}


def _apply_version6_20(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_20_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_20_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_20_rules.record_strategy6_20_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_20_rules.lot_budget,
        "add_step": strategy6_20_rules.ADD_STEP,
        "step_frac": strategy6_20_rules.STEP_FRAC,
        "step_cap": strategy6_20_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_20_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_20_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_20_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_20_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_20_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_20_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_20(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_20", "stop_pct": stop}


def _apply_version6_21(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_21_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_21_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_21_rules.record_strategy6_21_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_21_rules.lot_budget,
        "add_step": strategy6_21_rules.ADD_STEP,
        "step_frac": strategy6_21_rules.STEP_FRAC,
        "step_cap": strategy6_21_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_21_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_21_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_21_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_21_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_21_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_21_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_21(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_21", "stop_pct": stop}


def _apply_version6_22(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_22_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_22_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_22_rules.record_strategy6_22_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_22_rules.lot_budget,
        "add_step": strategy6_22_rules.ADD_STEP,
        "step_frac": strategy6_22_rules.STEP_FRAC,
        "step_cap": strategy6_22_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_22_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_22_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_22_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_22_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_22_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_22_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_22(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_22", "stop_pct": stop}


def _apply_version6_23(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_23_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_23_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_23_rules.record_strategy6_23_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_23_rules.lot_budget,
        "add_step": strategy6_23_rules.ADD_STEP,
        "step_frac": strategy6_23_rules.STEP_FRAC,
        "step_cap": strategy6_23_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_23_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_23_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_23_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_23_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_23_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_23_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_23(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_23", "stop_pct": stop}


def _apply_version6_24(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_24_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_24_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_24_rules.record_strategy6_24_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_24_rules.lot_budget,
        "add_step": strategy6_24_rules.ADD_STEP,
        "step_frac": strategy6_24_rules.STEP_FRAC,
        "step_cap": strategy6_24_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_24_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_24_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_24_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_24_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_24_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_24_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_24(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_24", "stop_pct": stop}


def _apply_version6_25(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_25_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_25_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_25_rules.record_strategy6_25_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_25_rules.lot_budget,
        "add_step": strategy6_25_rules.ADD_STEP,
        "step_frac": strategy6_25_rules.STEP_FRAC,
        "step_cap": strategy6_25_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_25_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_25_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_25_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_25_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_25_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_25_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_25(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_25", "stop_pct": stop}


def _apply_version6_26(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_26_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_26_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_26_rules.record_strategy6_26_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_26_rules.lot_budget,
        "add_step": strategy6_26_rules.ADD_STEP,
        "step_frac": strategy6_26_rules.STEP_FRAC,
        "step_cap": strategy6_26_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_26_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_26_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_26_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_26_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_26_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_26_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_26(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_26", "stop_pct": stop}


def _apply_version6_27(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_27_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_27_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_27_rules.record_strategy6_27_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_27_rules.lot_budget,
        "add_step": strategy6_27_rules.ADD_STEP,
        "step_frac": strategy6_27_rules.STEP_FRAC,
        "step_cap": strategy6_27_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_27_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_27_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_27_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_27_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_27_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_27_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_27(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_27", "stop_pct": stop}


def _apply_version6_28(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_28_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_28_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_28_rules.record_strategy6_28_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_28_rules.lot_budget,
        "add_step": strategy6_28_rules.ADD_STEP,
        "step_frac": strategy6_28_rules.STEP_FRAC,
        "step_cap": strategy6_28_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_28_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_28_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_28_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_28_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_28_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_28_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_28(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_28", "stop_pct": stop}


def _apply_version6_29(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_29_rules.STOP_PCT if stop_pct is None else float(stop_pct)

    def _tp(px, cost, peak, n_days=1):
        return strategy6_29_rules.take_profit_reason(px, cost, peak, n_days)

    def _rec(st):
        strategy6_29_rules.record_strategy6_29_params(st, stop_pct=resolved)

    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_29_rules.lot_budget,
        "add_step": strategy6_29_rules.ADD_STEP,
        "step_frac": strategy6_29_rules.STEP_FRAC,
        "step_cap": strategy6_29_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_29_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_29_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_29_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_29_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_29_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_29_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_29(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_29", "stop_pct": stop}


def _apply_version6_30(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_30_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_30_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_30_rules.record_strategy6_30_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_30_rules.lot_budget,
        "add_step": strategy6_30_rules.ADD_STEP,
        "step_frac": strategy6_30_rules.STEP_FRAC,
        "step_cap": strategy6_30_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_30_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_30_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_30_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_30_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_30_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_30_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_30(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_30", "stop_pct": stop}


def _apply_version6_31(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_31_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_31_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_31_rules.record_strategy6_31_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_31_rules.lot_budget,
        "add_step": strategy6_31_rules.ADD_STEP,
        "step_frac": strategy6_31_rules.STEP_FRAC,
        "step_cap": strategy6_31_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_31_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_31_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_31_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_31_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_31_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_31_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_31(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_31", "stop_pct": stop}


def _apply_version6_32(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_32_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_32_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_32_rules.record_strategy6_32_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_32_rules.lot_budget,
        "add_step": strategy6_32_rules.ADD_STEP,
        "step_frac": strategy6_32_rules.STEP_FRAC,
        "step_cap": strategy6_32_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_32_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_32_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_32_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_32_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_32_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_32_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_32(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_32", "stop_pct": stop}


def _apply_version6_33(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_33_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_33_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_33_rules.record_strategy6_33_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_33_rules.lot_budget,
        "add_step": strategy6_33_rules.ADD_STEP,
        "step_frac": strategy6_33_rules.STEP_FRAC,
        "step_cap": strategy6_33_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_33_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_33_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_33_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_33_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_33_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_33_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_33(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_33", "stop_pct": stop}


def _apply_version6_34(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_34_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_34_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_34_rules.record_strategy6_34_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_34_rules.lot_budget,
        "add_step": strategy6_34_rules.ADD_STEP,
        "step_frac": strategy6_34_rules.STEP_FRAC,
        "step_cap": strategy6_34_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_34_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_34_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_34_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_34_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_34_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_34_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_34(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_34", "stop_pct": stop}


def _apply_version6_35(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_35_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_35_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_35_rules.record_strategy6_35_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_35_rules.lot_budget,
        "add_step": strategy6_35_rules.ADD_STEP,
        "step_frac": strategy6_35_rules.STEP_FRAC,
        "step_cap": strategy6_35_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_35_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_35_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_35_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_35_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_35_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_35_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_35(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_35", "stop_pct": stop}


def _apply_version6_36(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_36_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_36_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_36_rules.record_strategy6_36_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_36_rules.lot_budget,
        "add_step": strategy6_36_rules.ADD_STEP,
        "step_frac": strategy6_36_rules.STEP_FRAC,
        "step_cap": strategy6_36_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_36_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_36_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_36_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_36_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_36_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_36_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_36(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_36", "stop_pct": stop}


def _apply_version6_37(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_37_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_37_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_37_rules.record_strategy6_37_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_37_rules.lot_budget,
        "add_step": strategy6_37_rules.ADD_STEP,
        "step_frac": strategy6_37_rules.STEP_FRAC,
        "step_cap": strategy6_37_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_37_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_37_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_37_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_37_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_37_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_37_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_37(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_37", "stop_pct": stop}


def _apply_version6_38(
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
    **_,
) -> dict:
    resolved = strategy6_38_rules.STOP_PCT if stop_pct is None else float(stop_pct)
    def _tp(px, cost, peak, n_days=1):
        return strategy6_38_rules.take_profit_reason(px, cost, peak, n_days)
    def _rec(st):
        strategy6_38_rules.record_strategy6_38_params(st, stop_pct=resolved)
    return {
        "stop_pct": resolved,
        "take_profit": take_profit if take_profit is not None else _tp,
        "record_params": record_params if record_params is not None else _rec,
        "name_lot_budget": strategy6_38_rules.lot_budget,
        "add_step": strategy6_38_rules.ADD_STEP,
        "step_frac": strategy6_38_rules.STEP_FRAC,
        "step_cap": strategy6_38_rules.STEP_CAP_PER_CODE,
        "cost_anchor": "first_lot",
        "step_stop_pct": strategy6_38_rules.STEP_STOP_PCT,
        "scale_out_step": strategy6_38_rules.SCALE_OUT_STEP,
        "scale_out_frac": strategy6_38_rules.SCALE_OUT_FRAC,
        "peak_dd_exit": strategy6_38_rules.PEAK_DD_EXIT,
        "peak_dd_sessions": strategy6_38_rules.PEAK_DD_SESSIONS,
        "add_schedule": strategy6_38_rules.ADD_SCHEDULE,
    }


def _run_kwargs_version6_38(args) -> dict:
    stop = getattr(args, "stop_pct", None)
    if stop is not None and not 0 < float(stop) < 1:
        raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
    return {"strategy": "version6_38", "stop_pct": stop}


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


def _apply_version9(
    *, version9_sell=None, max_hold: bool = False, stop_pct: Optional[float] = None, take_profit=None, record_params=None, **_
) -> dict:
    if stop_pct is not None:
        raise SystemExit("version9 does not accept --stop-pct")

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
        strategy9_rules.record_strategy9_params(st, max_hold=max_hold)

    return {
        "stop_pct": None,
        "stop_range": strategy9_rules.stop_range_amplitude,
        "take_profit": _tp if take_profit is None else take_profit,
        "record_params": _rec if record_params is None else record_params,
    }


def _run_kwargs_version9(args) -> dict:
    if getattr(args, "stop_pct", None) is not None:
        raise SystemExit("version9 does not accept --stop-pct")
    return {"strategy": "version9", "max_hold": bool(getattr(args, "max_hold", False)), "version9_sell": getattr(args, "version9_sell", None)}


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
