"""BT-B: ST PIT + listing-age gate for new buys only (no forced ST sells)."""

from __future__ import annotations

from bisect import bisect_right
from datetime import date
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

import pandas as pd

from backtest.research.topk_dropout_scores import _bare_or_canon

EligibleBuyFn = Callable[[str, str], bool]


def _as_date(value) -> date:
    return pd.Timestamp(value).date()


def _ymd(value) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y%m%d")
    text = str(value).strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 8:
        return digits[:8]
    raise ValueError(f"cannot parse YYYYMMDD: {value!r}")


def load_st_daily_by_day(path: Path | str) -> dict[date, set[str]]:
    """st_daily.parquet → {date: {canonical code}} for rows with is_st.

    Same contract as MyQuant ``BuyEligibilityFilter`` + ``--st-daily-file``:
    parquet ``is_st`` only; do not read ``st_coverage.json``.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"st-daily-file not found: {p}")
    df = pd.read_parquet(p)
    by_date: dict[date, set[str]] = {}
    if df.empty:
        return by_date
    if "is_st" not in df.columns or "trade_date" not in df.columns or "code" not in df.columns:
        raise ValueError(f"st_daily.parquet needs code/trade_date/is_st: {p}")
    hit = df[df["is_st"] == True].copy()  # noqa: E712
    hit["trade_date"] = pd.to_datetime(hit["trade_date"])
    for d, sub in hit.groupby(hit["trade_date"].dt.date):
        codes = set()
        for raw in sub["code"]:
            c = _bare_or_canon(str(raw))
            if c:
                codes.add(c)
        by_date[d] = codes
    return by_date


def load_age_min_buy_ymd(
    path: Path | str,
    *,
    age_days: int = 60,
    calendar_ymd: Sequence[str] | None = None,
) -> dict[str, str]:
    """Load code → earliest eligible buy YYYYMMDD.

    File lines: ``CODE\\tYYYY-MM-DD`` (or comma). If ``calendar_ymd`` is given,
    values are treated as listing/data start and shifted by ``age_days`` trading
    days. Otherwise values are treated as already-computed min buy dates.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"age-map-file not found: {p}")
    out: dict[str, str] = {}
    cal = [str(x) for x in (calendar_ymd or [])]
    cal_pos = {d: i for i, d in enumerate(cal)} if cal else None
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            left, right = line.split("\t", 1)
        elif "," in line:
            left, right = line.split(",", 1)
        else:
            parts = line.split()
            if len(parts) < 2:
                continue
            left, right = parts[0], parts[1]
        code = _bare_or_canon(left)
        if not code:
            continue
        start_ymd = _ymd(right)
        if cal_pos is None:
            out[code] = start_ymd
            continue
        idx = cal_pos.get(start_ymd)
        if idx is None:
            # 日历之前的老股保持原日期；日历之后或无法对齐 → 窗内不可买
            out[code] = "99991231" if cal and start_ymd > cal[-1] else start_ymd
            continue
        j = idx + int(age_days)
        if j >= len(cal):
            out[code] = "99991231"
        else:
            out[code] = cal[j]
    return out


def st_codes_asof(by_date: Mapping[date, set[str]], buy_date) -> set[str]:
    if not by_date:
        return set()
    dates = sorted(by_date)
    target = _as_date(buy_date)
    idx = bisect_right(dates, target) - 1
    if idx < 0:
        return set()
    return set(by_date[dates[idx]])


def make_eligible_buy(
    *,
    st_daily_file: Path | str | None = None,
    age_map_file: Path | str | None = None,
    age_days: int = 60,
    calendar_ymd: Sequence[str] | None = None,
    st_by_day: Mapping[date, set[str]] | None = None,
    min_buy_ymd: Mapping[str, str] | None = None,
) -> EligibleBuyFn:
    """Return ``eligible_buy(code, buy_date_ymd) -> bool``.

    Missing configured files fail closed. Unconfigured dimensions allow all.
    Never used to force-sell on becoming ST.
    """
    st_map: dict[date, set[str]]
    if st_by_day is not None:
        st_map = {d: set(s) for d, s in st_by_day.items()}
    elif st_daily_file is not None:
        st_map = load_st_daily_by_day(st_daily_file)
    else:
        st_map = {}

    age_map: dict[str, str]
    if min_buy_ymd is not None:
        age_map = {str(k): _ymd(v) for k, v in min_buy_ymd.items()}
    elif age_map_file is not None:
        age_map = load_age_min_buy_ymd(
            age_map_file, age_days=age_days, calendar_ymd=calendar_ymd
        )
    else:
        age_map = {}

    check_st = st_daily_file is not None or st_by_day is not None
    check_age = age_map_file is not None or min_buy_ymd is not None

    def eligible_buy(code: str, buy_date: str) -> bool:
        c = _bare_or_canon(code) or str(code)
        ds = _ymd(buy_date)
        if check_st:
            if c in st_codes_asof(st_map, ds):
                return False
        if check_age:
            min_d = age_map.get(c)
            if min_d is None:
                # unknown age → fail-closed (cannot verify ≥60)
                return False
            if ds < min_d:
                return False
        return True

    return eligible_buy


def with_return_threshold(
    eligible_buy: EligibleBuyFn | None,
    bars: Mapping[str, pd.DataFrame],
    *,
    lookback_days: int = 5,
    max_return_threshold: float = 0.15,
    calendar_ymd: Sequence[str] | None = None,
) -> EligibleBuyFn:
    """Block new buys whose close[T-1]/close[T-(lookback+1)]-1 exceeds threshold.

    Same endpoints as MyQuant ``TopkDropoutStrategyWithFilter`` (T-1 vs T-6
    for lookback=5). Missing closes pass (qlib treats missing as -inf ≤ 15%).
    Does not force-sell names already held.
    """
    if lookback_days <= 0 or max_return_threshold < 0:
        return eligible_buy if eligible_buy is not None else (lambda _c, _d: True)

    if calendar_ymd is not None:
        cal = [str(x) for x in calendar_ymd]
    else:
        dates: set[str] = set()
        for df in bars.values():
            if df is None or df.empty:
                continue
            for ts in df.index:
                dates.add(pd.Timestamp(ts).strftime("%Y%m%d"))
        cal = sorted(dates)
    pos = {d: i for i, d in enumerate(cal)}

    def _close(code: str, ymd: str) -> float | None:
        c = _bare_or_canon(code) or str(code)
        df = bars.get(c)
        if df is None:
            df = bars.get(code)
        if df is None or df.empty:
            return None
        ts = pd.Timestamp(ymd)
        if ts not in df.index:
            return None
        val = df.loc[ts, "close"]
        if hasattr(val, "iloc"):
            val = val.iloc[-1]
        try:
            px = float(val)
        except (TypeError, ValueError):
            return None
        if px != px or px <= 0:  # NaN
            return None
        return px

    def gated(code: str, buy_date: str) -> bool:
        if eligible_buy is not None and not eligible_buy(code, buy_date):
            return False
        ds = _ymd(buy_date)
        i = pos.get(ds)
        if i is None or i < lookback_days + 1:
            return True
        end_d = cal[i - 1]
        start_d = cal[i - (lookback_days + 1)]
        c0 = _close(code, start_d)
        c1 = _close(code, end_d)
        if c0 is None or c1 is None:
            return True
        return (c1 / c0 - 1.0) <= float(max_return_threshold)

    return gated
