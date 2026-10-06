"""Pure, opt-in RB-13 side metrics; see the caliber document."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from backtest.research.csv_analysis_export import drawdown_and_win_rates, pair_round_trips

PERIODS_PER_YEAR = 252


def _unavailable(reason):
    return {"status": "unavailable", "reason": reason}


def _metric(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("metric is nonfinite")
    return {"status": "available", "value": value}


def _numbers(values, *, positive=False):
    out = pd.to_numeric(values, errors="raise").astype(float)
    if not out.map(math.isfinite).all() or (positive and (out <= 0).any()):
        raise ValueError("values must be finite" + (" and positive" if positive else ""))
    return out


def _nav(frame):
    nav = frame.copy().reset_index(drop=True)
    dates = pd.to_datetime(nav["date"].astype(str), errors="raise")
    if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("dates must be unique and increasing")
    nav["date"] = dates.dt.strftime("%Y-%m-%d")
    nav["ymd"] = dates.dt.strftime("%Y%m%d")
    nav["equity"] = _numbers(nav["equity"], positive=True)
    return nav


def compute_metrics_pack(
    equity_daily,
    trades=None,
    fees=None,
    benchmark=None,
    *,
    risk_free=0.0,
    periods_per_year=PERIODS_PER_YEAR,
) -> dict:
    """Compute from existing export frames without IO or input mutation."""
    if not math.isfinite(risk_free) or risk_free <= -1:
        raise ValueError("risk_free must be finite and greater than -1")
    if not math.isfinite(periods_per_year) or periods_per_year <= 0:
        raise ValueError("periods_per_year must be finite and positive")
    nav = _nav(equity_daily)
    eq = nav["equity"]
    returns = eq.pct_change(fill_method=None).iloc[1:]
    n = len(returns)
    short = _unavailable("fewer than two daily returns")
    pack = {
        "schema": "rb13-v1",
        "periods_per_year": periods_per_year,
        "risk_free_annual": risk_free,
        "risk_free_label": "annual effective; default 0",
        "daily_returns": [
            {"date": nav.at[i, "date"], "value": float(r)} for i, r in returns.items()
        ],
        "annualised_return": _metric((eq.iloc[-1] / eq.iloc[0]) ** (periods_per_year / n) - 1)
        if n
        else _unavailable("no daily return intervals"),
        "annualised_volatility": short,
        "sharpe": short,
        "benchmark_excess": _unavailable("benchmark not supplied"),
        "beta": _unavailable("benchmark not supplied"),
        "tracking_error": _unavailable("benchmark not supplied"),
        "win_rate_closed": _unavailable("trades not supplied"),
        "turnover": _unavailable("fill notionals not supplied"),
        "fee_drag": _unavailable("fees not supplied"),
        "exposure": _unavailable("gross_invested not supplied"),
        "skip_rate": _unavailable("sim counters and attempt denominator not supplied"),
        "defer_rate": _unavailable("sim counters and attempt denominator not supplied"),
    }
    if n >= 2:
        vol = float(returns.std(ddof=1))
        pack["annualised_volatility"] = _metric(vol * math.sqrt(periods_per_year))
        pack["sharpe"] = (
            _metric(
                (returns.mean() - ((1 + risk_free) ** (1 / periods_per_year) - 1))
                / vol
                * math.sqrt(periods_per_year)
            )
            if vol
            else _unavailable("zero volatility")
        )
    if benchmark is not None:
        bn = _nav(benchmark)
        br = bn["equity"].pct_change(fill_method=None)
        left = pd.DataFrame(
            {
                "date": nav["date"],
                "start": nav["date"].shift(),
                "r": eq.pct_change(fill_method=None),
            }
        )
        right = pd.DataFrame({"date": bn["date"], "start": bn["date"].shift(), "b": br})
        aligned = left.merge(right, on=["date", "start"]).dropna()
        for key in ("benchmark_excess", "beta", "tracking_error"):
            pack[key] = _unavailable("fewer than two matching benchmark intervals")
        if len(aligned) >= 2:
            excess = aligned.r - aligned.b
            pack["benchmark_excess"] = _metric(excess.mean() * periods_per_year)
            pack["tracking_error"] = _metric(excess.std(ddof=1) * math.sqrt(periods_per_year))
            variance = aligned.b.var(ddof=1)
            pack["beta"] = (
                _metric(aligned.r.cov(aligned.b) / variance)
                if variance
                else _unavailable("zero benchmark variance")
            )
    fills = None
    if trades is not None:
        if "status" in trades:
            trips = trades.copy()
        else:
            fills = trades[trades["side"].str.upper().isin(["BUY", "SELL"])].copy()
            _, trips, _ = pair_round_trips(trades.copy(), nav)
        win = drawdown_and_win_rates(nav, trips, None)["win_rate_closed"]
        pack["win_rate_closed"] = (
            _metric(win) if win is not None else _unavailable("no closed lots")
        )
    average = float(eq.mean()) if len(eq) else None
    if average is not None:
        if fills is not None and "notional" in fills:
            pack["turnover"] = _metric(_numbers(fills["notional"]).abs().sum() / average)
        fee_values = fees["commission"] if isinstance(fees, pd.DataFrame) else fees
        if fee_values is None and fills is not None and "commission" in fills:
            fee_values = fills["commission"]
        if fee_values is not None:
            pack["fee_drag"] = _metric(_numbers(pd.Series(fee_values)).sum() / average)
        if "gross_invested" in nav:
            gross = _numbers(nav["gross_invested"])
            if (gross < 0).any():
                raise ValueError("gross_invested must be nonnegative")
            pack["exposure"] = _metric((gross / eq).mean())
    return pack


def write_metrics_pack(path, pack):
    """Write canonical JSON only on this explicit call."""
    body = json.dumps(pack, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    Path(path).write_text(body, encoding="utf-8", newline="\n")
