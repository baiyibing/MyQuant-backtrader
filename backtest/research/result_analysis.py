"""Post-run account curve and closed-trip payoff. Does not resimulate."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

PERIODS_PER_YEAR = 252


def _unavailable(reason: str) -> dict[str, str]:
    return {"status": "unavailable", "reason": reason}


def _metric(value: float) -> dict[str, Any]:
    value = float(value)
    if not math.isfinite(value):
        return _unavailable("computed metric is nonfinite")
    return {"status": "available", "value": value}


def _dates(frame: pd.DataFrame) -> pd.Series:
    dates = pd.to_datetime(frame["date"].astype(str), errors="raise")
    if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("dates must be unique and increasing")
    return dates


def _levels(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({"date": _dates(frame), "equity": pd.to_numeric(frame["equity"], errors="raise")})
    if not out["equity"].map(math.isfinite).all():
        raise ValueError("equity must be finite")
    return out.reset_index(drop=True)


def _sharpe(returns: pd.Series, risk_free: float, periods: int) -> tuple[dict, dict]:
    """Annualised volatility and Sharpe. Zero volatility keeps volatility at 0."""
    if len(returns) < 2:
        reason = "fewer than two daily returns"
        return _unavailable(reason), _unavailable(reason)
    vol = float(returns.std(ddof=1))
    annual_vol = _metric(vol * math.sqrt(periods))
    if vol == 0.0:
        return _metric(0.0), _unavailable("zero volatility")
    daily_rf = (1.0 + risk_free) ** (1.0 / periods) - 1.0
    sharpe = (float(returns.mean()) - daily_rf) / vol * math.sqrt(periods)
    return annual_vol, _metric(sharpe)


def _drawdown(levels: pd.DataFrame) -> dict[str, Any]:
    levels = levels.reset_index(drop=True)
    equity = levels["equity"]
    if (equity <= 0).any():
        return _unavailable("nonpositive equity")
    peak = equity.cummax()
    dd = equity / peak - 1.0
    trough = int(dd.to_numpy().argmin())
    depth = float(dd.iloc[trough])
    if depth == 0.0:
        day = levels["date"].iloc[0].strftime("%Y-%m-%d")
        return {
            "status": "available",
            "value": 0.0,
            "trough_date": day,
            "peak_date": day,
            "trading_days": 0,
            "calendar_days": 0,
        }
    window = equity.iloc[: trough + 1]
    peak_at = int(window[window == window.max()].index[-1])
    peak_date = levels["date"].iloc[peak_at]
    trough_date = levels["date"].iloc[trough]
    return {
        "status": "available",
        "value": depth,
        "trough_date": trough_date.strftime("%Y-%m-%d"),
        "peak_date": peak_date.strftime("%Y-%m-%d"),
        "trading_days": trough - peak_at,
        "calendar_days": int((trough_date - peak_date).days),
    }


def _month_return(levels: pd.DataFrame) -> list[dict[str, Any]]:
    months: list[dict[str, Any]] = []
    if levels.empty:
        return months
    ym = levels["date"].dt.strftime("%Y-%m")
    first_month = True
    for month, group in levels.groupby(ym, sort=False):
        last_pos = int(group.index[-1])
        if first_month:
            base_pos = int(group.index[0])
            first_month = False
        else:
            base_pos = int(group.index[0]) - 1
        base = float(levels["equity"].iloc[base_pos])
        last = float(levels["equity"].iloc[last_pos])
        node = {
            "month": str(month),
            "start_date": levels["date"].iloc[base_pos].strftime("%Y-%m-%d"),
            "end_date": levels["date"].iloc[last_pos].strftime("%Y-%m-%d"),
        }
        if base <= 0:
            node["return"] = _unavailable("nonpositive equity")
        else:
            node["return"] = _metric(last / base - 1.0)
        months.append(node)
    return months


def _attach_month_excess(months: list[dict[str, Any]], bench: pd.DataFrame) -> None:
    lookup = {day.strftime("%Y-%m-%d"): float(px) for day, px in zip(bench["date"], bench["equity"])}
    for row in months:
        start, end = row["start_date"], row["end_date"]
        if start not in lookup or end not in lookup:
            row["geometric_excess"] = _unavailable("month endpoints are not on both series")
            continue
        base, last = lookup[start], lookup[end]
        account = row["return"]
        if account.get("status") != "available" or base <= 0:
            row["geometric_excess"] = _unavailable("nonpositive equity")
            continue
        bench_return = last / base - 1.0
        if 1.0 + bench_return == 0.0:
            row["geometric_excess"] = _unavailable("benchmark month return is -1")
            continue
        row["geometric_excess"] = _metric((1.0 + account["value"]) / (1.0 + bench_return) - 1.0)


def _aligned_steps(account: pd.DataFrame, bench: pd.DataFrame) -> pd.DataFrame:
    left = pd.DataFrame(
        {
            "date": account["date"],
            "start": account["date"].shift(),
            "equity": account["equity"],
            "r": account["equity"].pct_change(),
        }
    )
    right = pd.DataFrame(
        {
            "date": bench["date"],
            "start": bench["date"].shift(),
            "b": bench["equity"].pct_change(),
        }
    )
    return left.merge(right, on=["date", "start"]).dropna()


def _excess_block(account: pd.DataFrame, bench: pd.DataFrame, n_intervals: int) -> dict[str, Any]:
    overlap = account.merge(bench, on="date", suffixes=("_e", "_b"))
    if overlap.empty or float(overlap["equity_e"].iloc[0]) <= 0 or float(overlap["equity_b"].iloc[0]) <= 0:
        return _unavailable("no positive overlapping equity")
    e0 = float(overlap["equity_e"].iloc[0])
    b0 = float(overlap["equity_b"].iloc[0])
    e_t = float(overlap["equity_e"].iloc[-1])
    b_t = float(overlap["equity_b"].iloc[-1])
    wealth = (overlap["equity_e"] / e0) / (overlap["equity_b"] / b0)
    curve = pd.DataFrame({"date": overlap["date"], "equity": wealth})
    steps = _aligned_steps(account, bench)
    dropped = n_intervals - len(steps)
    block: dict[str, Any] = {
        "status": "available",
        "aligned_intervals": len(steps),
        "dropped_intervals": int(dropped),
        "geometric_excess": _metric((e_t / e0) / (b_t / b0) - 1.0),
        "arithmetic_excess": _metric((e_t / e0 - 1.0) - (b_t / b0 - 1.0)),
        "excess_max_drawdown": _drawdown(curve),
    }
    if len(steps) < 2:
        block["information_ratio"] = _unavailable("fewer than two aligned intervals")
        block["excess_sharpe"] = _unavailable("fewer than two aligned intervals")
        return block
    excess = steps["r"] - steps["b"]
    std = float(excess.std(ddof=1))
    block["information_ratio"] = (
        _metric(float(excess.mean()) / std * math.sqrt(PERIODS_PER_YEAR))
        if std
        else _unavailable("zero excess volatility")
    )
    if (steps["b"] <= -1.0).any():
        block["excess_sharpe"] = _unavailable("benchmark return is at or below -1")
        return block
    geometric = (1.0 + steps["r"]) / (1.0 + steps["b"]) - 1.0
    _, block["excess_sharpe"] = _sharpe(geometric, 0.0, PERIODS_PER_YEAR)
    return block


def _notional(trades: pd.DataFrame) -> pd.Series | None:
    if "side" not in trades.columns:
        return pd.Series(dtype=float)
    fills = trades[trades["side"].astype(str).str.upper().isin(["BUY", "SELL"])]
    if fills.empty:
        return fills["notional"] if "notional" in fills else pd.Series(dtype=float)
    if "notional" in fills and fills["notional"].map(math.isfinite).all():
        return fills["notional"].astype(float)
    if {"price", "shares"} <= set(fills.columns):
        notion = fills["price"].astype(float) * fills["shares"].astype(float)
        if notion.map(math.isfinite).all():
            return notion
    return None


def account_curve(
    nav: pd.DataFrame,
    trades: pd.DataFrame | None = None,
    benchmark: pd.DataFrame | None = None,
    *,
    commission_total: float | None = None,
    risk_free: float = 0.0,
    benchmark_label: str | None = None,
) -> dict[str, Any]:
    """Account metrics from a full equity curve. Benchmark is optional."""
    if not math.isfinite(risk_free) or risk_free <= -1:
        raise ValueError("risk_free must be finite and greater than -1")
    levels = _levels(nav)
    equity = levels["equity"]
    n = len(levels) - 1
    returns = equity.pct_change().iloc[1:]
    e0 = float(equity.iloc[0]) if len(equity) else None
    period = _unavailable("no equity rows")
    annual = _unavailable("no daily return intervals")
    if e0 is not None and e0 <= 0:
        period = _unavailable("nonpositive equity")
        annual = _unavailable("nonpositive equity")
    elif e0 is not None:
        period = _metric(float(equity.iloc[-1]) / e0 - 1.0)
        if n >= 1:
            annual = _metric((float(equity.iloc[-1]) / e0) ** (PERIODS_PER_YEAR / n) - 1.0)
    vol, sharpe = _sharpe(returns, risk_free, PERIODS_PER_YEAR)
    months = _month_return(levels)
    bench_block: dict[str, Any] = _unavailable("benchmark not supplied")
    if benchmark is not None:
        bench = _levels(benchmark)
        bench_block = _excess_block(levels, bench, n)
        if benchmark_label and bench_block.get("status") == "available":
            bench_block["label"] = benchmark_label
        _attach_month_excess(months, bench)
    else:
        for row in months:
            row["geometric_excess"] = _unavailable("benchmark not supplied")
    average = float(equity.mean()) if len(equity) else None
    turnover_period = _unavailable("trades not supplied")
    turnover_annual = _unavailable("trades not supplied")
    if trades is not None:
        notion = _notional(trades)
        if notion is None:
            turnover_period = _unavailable("fill notionals are not finite")
            turnover_annual = _unavailable("fill notionals are not finite")
        elif average is None or average == 0.0:
            turnover_period = _unavailable("average equity is zero")
            turnover_annual = _unavailable("average equity is zero")
        else:
            one_way = float(notion.abs().sum()) / 2.0 / average
            turnover_period = _metric(one_way)
            turnover_annual = (
                _metric(one_way * PERIODS_PER_YEAR / n) if n >= 1 else _unavailable("no daily return intervals")
            )
    if commission_total is None or average is None or average == 0.0:
        fee = _unavailable("commission not supplied" if commission_total is None else "average equity is zero")
        added = _unavailable("commission not supplied" if commission_total is None else "average equity is zero")
    else:
        fee = _metric(float(commission_total) / average)
        added = _metric(float(equity.iloc[-1]) + float(commission_total))
    return {
        "schema": "result-analysis-p1",
        "period_return_basis": "first_equity_row",
        "periods_per_year": PERIODS_PER_YEAR,
        "risk_free_annual": risk_free,
        "n_return_intervals": n,
        "period_return": period,
        "annualised_return": annual,
        "annualised_volatility": vol,
        "sharpe": sharpe,
        "max_drawdown": _drawdown(levels),
        "benchmark": bench_block,
        "months": months,
        "turnover": {"basis": "one_way", "period": turnover_period, "annualised": turnover_annual},
        "fee_drag": fee,
        "equity_commission_added_back": added,
    }


def _payoff_block(closed: pd.DataFrame) -> dict[str, Any]:
    n = len(closed)
    if n == 0:
        empty = _unavailable("no closed trips")
        return {
            "closed_trips": 0,
            "wins": 0,
            "flat": 0,
            "losses": 0,
            "win_rate": empty,
            "avg_win": empty,
            "avg_loss": empty,
            "payoff_ratio": empty,
            "profit_factor": empty,
        }
    pnl = closed["realized_pnl"].astype(float)
    wins = pnl[pnl > 0]
    flats = pnl[pnl == 0]
    losses = pnl[pnl < 0]
    block = {
        "closed_trips": n,
        "wins": len(wins),
        "flat": len(flats),
        "losses": int(len(losses) + len(flats)),
        "win_rate": _metric(len(wins) / n),
        "avg_win": _metric(float(wins.mean())) if len(wins) else _unavailable("no winning closed trips"),
        "avg_loss": _metric(float(losses.mean())) if len(losses) else _unavailable("no losing closed trips"),
    }
    if len(losses) == 0 or len(wins) == 0:
        block["payoff_ratio"] = _unavailable("no losing closed trips" if len(losses) == 0 else "no winning closed trips")
    else:
        block["payoff_ratio"] = _metric(float(wins.mean()) / abs(float(losses.mean())))
    if len(losses) == 0:
        block["profit_factor"] = _unavailable("no losing closed trips")
    else:
        block["profit_factor"] = _metric(float(wins.sum()) / abs(float(losses.sum())))
    return block


def trade_payoff(trips: pd.DataFrame) -> dict[str, Any]:
    """Closed-trip payoff. Flat trips stay in the win-rate denominator."""
    if trips is None or len(trips) == 0 or "status" not in trips.columns:
        closed = pd.DataFrame(columns=["realized_pnl", "sell_reason"])
    else:
        closed = trips[trips["status"] == "closed"].copy()
    if "sell_reason" not in closed.columns:
        closed["sell_reason"] = ""
    overall = _payoff_block(closed)
    rows = []
    if len(closed):
        grouped = closed.fillna({"sell_reason": ""}).groupby("sell_reason", sort=True)
        for reason, group in grouped:
            item = _payoff_block(group)
            item["sell_reason"] = str(reason)
            rows.append(item)
    overall["by_sell_reason"] = rows
    overall["schema"] = "result-analysis-p1"
    return overall


def with_realized_share(frame: pd.DataFrame) -> pd.DataFrame:
    """Add book-level realized-pnl share and the top positive names' share."""
    out = frame.copy()
    if out.empty:
        out["realized_pnl_share"] = pd.Series(dtype=float)
        out["top_profit_count"] = pd.Series(dtype=int)
        out["top_profit_share"] = pd.Series(dtype=float)
        return out
    realized = out["realized_pnl"].astype(float)
    total = float(realized.sum())
    out["realized_pnl_share"] = realized / total if total else float("nan")
    positive = out.loc[realized > 0].sort_values(
        ["realized_pnl", "code"], ascending=[False, True], kind="mergesort"
    )
    count = min(5, len(positive))
    out["top_profit_count"] = count
    if count == 0:
        out["top_profit_share"] = float("nan")
    else:
        top = float(positive["realized_pnl"].iloc[:count].sum())
        out["top_profit_share"] = top / float(positive["realized_pnl"].sum())
    return out


def window_split(nav: pd.DataFrame) -> dict[str, Any]:
    """Score only the later half of an existing equity curve. No parameter search."""
    levels = _levels(nav)
    n = len(levels)
    cut = n // 2
    later = levels.iloc[cut:].reset_index(drop=True)
    earlier = levels.iloc[:cut].reset_index(drop=True)
    scored = account_curve(later) if len(later) >= 2 else None
    reason = "later window has fewer than two equity rows"

    def piece(block: dict | None, key: str) -> dict:
        if block is None:
            return _unavailable(reason)
        return block[key]

    return {
        "schema": "result-analysis-p3",
        "role": "later_window_score",
        "split": "first half of equity rows is not a score",
        "rows": n,
        "selection_rows": len(earlier),
        "score_rows": len(later),
        "score_start": None if later.empty else later["date"].iloc[0].strftime("%Y-%m-%d"),
        "score_end": None if later.empty else later["date"].iloc[-1].strftime("%Y-%m-%d"),
        "period_return": piece(scored, "period_return"),
        "annualised_return": piece(scored, "annualised_return"),
        "max_drawdown": piece(scored, "max_drawdown"),
    }


def walkforward_folds(nav: pd.DataFrame, folds: int = 4) -> dict[str, Any]:
    """Score each later chunk of an existing curve. The first chunk is not a score."""
    if folds < 2:
        raise ValueError("walkforward folds must be at least 2")
    levels = _levels(nav)
    n = len(levels)
    size = n // folds
    if size < 2:
        return {
            "schema": "result-analysis-p3",
            "parameters_reselected": False,
            "folds": folds,
            "oos_period_return": _unavailable("each fold needs at least two equity rows"),
            "segments": [],
        }
    segments = []
    oos_returns: list[float] = []
    for i in range(folds):
        start = i * size
        stop = n if i == folds - 1 else (i + 1) * size
        chunk = levels.iloc[start:stop].reset_index(drop=True)
        role = "selection" if i == 0 else "test"
        scored = account_curve(chunk) if len(chunk) >= 2 else None
        period = scored["period_return"] if scored else _unavailable("fold has fewer than two equity rows")
        if role == "test" and period.get("status") == "available":
            oos_returns.append(float(period["value"]))
        segments.append(
            {
                "fold": i,
                "role": role,
                "start": chunk["date"].iloc[0].strftime("%Y-%m-%d"),
                "end": chunk["date"].iloc[-1].strftime("%Y-%m-%d"),
                "period_return": period,
                "annualised_return": scored["annualised_return"] if scored else _unavailable("fold has fewer than two equity rows"),
                "max_drawdown": scored["max_drawdown"] if scored else _unavailable("fold has fewer than two equity rows"),
            }
        )
    if not oos_returns:
        oos = _unavailable("no scored test fold")
    else:
        compound = 1.0
        for value in oos_returns:
            compound *= 1.0 + value
        oos = _metric(compound - 1.0)
    return {
        "schema": "result-analysis-p3",
        "parameters_reselected": False,
        "folds": folds,
        "oos_period_return": oos,
        "segments": segments,
    }


def citation_lines(account: dict[str, Any], payoff: dict[str, Any]) -> tuple[str, str]:
    """Two readout lines. Numbers come only from the JSON objects."""

    def shown(node: dict | None, *, percent: bool) -> str:
        if not isinstance(node, dict) or node.get("status") != "available":
            return "缺失"
        value = float(node["value"])
        return f"{value:+.2%}" if percent else f"{value:.4f}"

    excess = ""
    benchmark = account.get("benchmark")
    if isinstance(benchmark, dict):
        geometric = benchmark.get("geometric_excess")
        if isinstance(geometric, dict) and geometric.get("status") == "available":
            excess = f"，几何超额 {shown(geometric, percent=True)}"
    account_line = (
        "净值页: 相对净值首行 "
        f"{shown(account.get('period_return'), percent=True)}，复利年化 "
        f"{shown(account.get('annualised_return'), percent=True)}{excess}，见 account_curve.json。"
    )
    trade_line = (
        "交易页: 盈亏比 "
        f"{shown(payoff.get('payoff_ratio'), percent=False)}，获利因子 "
        f"{shown(payoff.get('profit_factor'), percent=False)}，见 trade_payoff.json。"
    )
    return account_line, trade_line
