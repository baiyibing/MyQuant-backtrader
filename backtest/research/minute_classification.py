"""Data-free minute strategy classification from registered strategy hooks."""

from dataclasses import dataclass
from inspect import signature
from math import isfinite
from numbers import Real
from typing import Literal

from backtest.research.csv_strategy_books import apply_csv_strategy, csv_strategy_names

CLI_MINUTE = "backtest/research/csv_minute_backtest.py"
CLI_V7 = "backtest/research/csv_minute_backtest_v7.py"
CLI_TOPK_APP = "backtest/research/csv_minute_backtest_topk_app_dropout.py"
EXTRA_MINUTE_STRATEGIES = ("version7", "topk_app_dropout")

_SPECIAL_HOOKS = (
    "minute_session", "minute_open", "run_daily_day", "version9_exit",
    "stop_range", "exit_plan", "drawdown_of", "drawdown_take_profit",
)


@dataclass(frozen=True, slots=True)
class MinuteStrategyEntry:
    name: str
    cli: str
    status: Literal["wired"]
    missing_field: str | None


def minute_strategy_names() -> tuple[str, ...]:
    books = csv_strategy_names()
    overlap = [name for name in EXTRA_MINUTE_STRATEGIES if name in books]
    if overlap:
        raise RuntimeError(f"extra minute strategy already registered: {overlap}")
    return books + EXTRA_MINUTE_STRATEGIES


def minute_strategy_entries() -> tuple[MinuteStrategyEntry, ...]:
    entries = []
    errors = []
    for name in minute_strategy_names():
        cli = CLI_MINUTE
        if name in EXTRA_MINUTE_STRATEGIES:
            cli = CLI_V7 if name == "version7" else CLI_TOPK_APP
        else:
            try:
                # TopK registration requires scores; these synthetic inputs never run.
                kwargs = {"scores_by_day": {"20260101": {"000001": 1.0}}} if name.startswith("topk_") else {}
                hooks = apply_csv_strategy(name, **kwargs)
                stop = hooks.get("stop_pct")
                take = hooks.get("take_profit")
                percent = isinstance(stop, Real) and not isinstance(stop, bool) and isfinite(stop) and callable(take)
                if percent:
                    try:
                        signature(take).bind(10.0, 10.0, 10.0, 1)
                    except (TypeError, ValueError):
                        percent = False
                special = any(hooks.get(field) is not None for field in _SPECIAL_HOOKS)
                main_engine = (
                    callable(hooks.get("bind_absolute_exit"))
                    or hooks.get("force_sell_hm") is not None
                    or (callable(hooks.get("buy_gate")) and callable(take))
                )
                if not (percent or special or main_engine):
                    raise ValueError("missing minute exit hooks")
            except (Exception, SystemExit) as exc:
                errors.append(
                    f"minute strategy not classified: {name}: {exc}; "
                    "fix its registration in backtest/research/csv_strategy_books.py"
                )
                continue
        entries.append(MinuteStrategyEntry(name, cli, "wired", None))
    if errors:
        raise RuntimeError("\n".join(errors))
    return tuple(entries)


def wired_names() -> tuple[str, ...]:
    return tuple(entry.name for entry in minute_strategy_entries() if entry.status == "wired")
