"""BT-B: ST PIT + listing-age gate for new buys only (no forced ST sells)."""

from __future__ import annotations

from bisect import bisect_right
from datetime import date
from pathlib import Path
from typing import Callable, Mapping, Sequence

import pandas as pd

from backtest.research.topk_dropout_scores import _bare_or_canon

EligibleBuyFn = Callable[[str, str], bool]
BuyStateRow = tuple[float, float, float, float]  # close, ma20, ma60, winratio
WINRATIO_LT = 0.10


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
    if (
        "is_st" not in df.columns
        or "trade_date" not in df.columns
        or "code" not in df.columns
    ):
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


def buy_state_oral_ok(
    close: float,
    ma20: float,
    ma60: float,
    winratio: float,
    *,
    wr_lt: float = WINRATIO_LT,
) -> bool:
    """Joint recipe (Q2/Q4): no MA5 slope; 盈筹 = broker $winratio.

    1) close < MA20 and close < MA60 and winratio < wr_lt
    2) close > MA20
    Any non-finite input → not buy.
    """
    vals = (close, ma20, ma60, winratio)
    if any(v is None for v in vals):
        return False
    try:
        c, m20, m60, wr = (float(v) for v in vals)
    except (TypeError, ValueError):
        return False
    if any(x != x or x in (float("inf"), float("-inf")) for x in (c, m20, m60, wr)):
        return False
    cond1 = c < m20 and c < m60 and wr < float(wr_lt)
    cond2 = c > m20
    return bool(cond1 or cond2)


def buy_state_above_ma20_ok(
    close: float, ma20: float, ma60: float = 0.0, winratio: float = 0.0
) -> bool:
    """Only close > MA20. MA60 and winratio are ignored. Non-finite close or MA20 → not buy."""
    del ma60, winratio
    if close is None or ma20 is None:
        return False
    try:
        c, m20 = float(close), float(ma20)
    except (TypeError, ValueError):
        return False
    if (
        c != c
        or m20 != m20
        or c in (float("inf"), float("-inf"))
        or m20 in (float("inf"), float("-inf"))
    ):
        return False
    return c > m20


WEEK_MA_WEEKS = 20
# 20 qlib week-labels plus a holiday buffer, so the first buy day is not fail-closed.
WEEK_MA_WARMUP_DAYS = 180
MA5_DAYS = 5
BUY_STATE_RULES = ("oral", "above-ma20", "above-ma20-week20", "above-ma5-ma20-week20")


def _qlib_week_labels(days: Sequence[date]) -> list[date]:
    """Same week calendar as qlib ``resam_calendar(..., freq_sam='week')``.

    A day is a week label when it is the first sample, or its weekday is
    lower than the previous sample (the first session of a new week).
    """
    labels: list[date] = []
    prev: int | None = None
    for day in days:
        wd = day.weekday()
        if prev is None or wd < prev:
            labels.append(day)
        prev = wd
    return labels


def weekly_ma_asof(
    closes: Mapping,
    *,
    weeks: int = WEEK_MA_WEEKS,
) -> dict[str, tuple[float, float]]:
    """Qlib week-frequency ``Mean($close, 20)``, carried onto each daily close.

    Week label = first session of the week. That label's close is that day's
    close (qlib reads the day bin at the week-calendar timestamp). Later days
    in the week reuse the latest label on or before them. Fewer than `weeks`
    labels → omitted (fail-closed). Value is (that day's close, week MA).
    close == ma is not above.
    """
    if weeks <= 1:
        raise ValueError("week MA window must be at least 2")
    by_day: dict[date, float] = {}
    for raw_day, raw_px in closes.items():
        try:
            px = float(raw_px)
        except (TypeError, ValueError):
            continue
        if px != px or px <= 0 or px in (float("inf"), float("-inf")):
            continue
        day = raw_day if isinstance(raw_day, date) else pd.Timestamp(raw_day).date()
        by_day[day] = px
    ordered = sorted(by_day)
    labels = _qlib_week_labels(ordered)
    label_ma: dict[date, float] = {}
    for i, day in enumerate(labels):
        if i + 1 < weeks:
            continue
        window = labels[i + 1 - weeks : i + 1]
        label_ma[day] = sum(by_day[item] for item in window) / weeks
    out: dict[str, tuple[float, float]] = {}
    ready = [day for day in labels if day in label_ma]
    if not ready:
        return out
    cursor = 0
    current: float | None = None
    for day in ordered:
        while cursor < len(ready) and ready[cursor] <= day:
            current = label_ma[ready[cursor]]
            cursor += 1
        if current is None:
            continue
        out[day.strftime("%Y%m%d")] = (by_day[day], current)
    return out


def _frame_closes(frame: pd.DataFrame) -> dict[date, float]:
    if frame is None or frame.empty or "close" not in frame.columns:
        return {}
    out: dict[date, float] = {}
    for raw_day, raw_px in zip(frame.index, frame["close"]):
        try:
            px = float(raw_px)
        except (TypeError, ValueError):
            continue
        if px != px or px <= 0:
            continue
        day = raw_day if isinstance(raw_day, date) else pd.Timestamp(raw_day).date()
        out[day] = px
    return out


def with_week_ma_gate(
    eligible_buy: EligibleBuyFn | None,
    bars: Mapping[str, pd.DataFrame],
    *,
    weeks: int = WEEK_MA_WEEKS,
) -> EligibleBuyFn:
    """Require that day's close > qlib 20-week MA. Missing history fails closed.

    Runs after the other buy gates. Does not force-sell.
    """
    tables: dict[str, dict[str, tuple[float, float]]] = {}
    for code, frame in bars.items():
        canon = _bare_or_canon(code) or str(code)
        tables[canon] = weekly_ma_asof(_frame_closes(frame), weeks=weeks)

    def list_ok(code: str, buy_date: str) -> bool:
        return _part(eligible_buy, "list_ok", code, buy_date, missing=True)

    def seat_ok(code: str, buy_date: str) -> bool:
        if not _part(eligible_buy, "seat_ok", code, buy_date, missing=False):
            return False
        canon = _bare_or_canon(code) or str(code)
        point = tables.get(canon, {}).get(_ymd(buy_date))
        if point is None:
            return False
        close, ma = point
        return close > ma

    def gated(code: str, buy_date: str) -> bool:
        return list_ok(code, buy_date) and seat_ok(code, buy_date)

    gated.list_ok = list_ok  # type: ignore[attr-defined]
    gated.seat_ok = seat_ok  # type: ignore[attr-defined]
    return gated


def ma5_asof(
    closes: Mapping,
    *,
    window: int = MA5_DAYS,
) -> dict[str, tuple[float, float]]:
    """That day's close and the mean of `window` closes ending that day.

    Fewer than `window` positive closes → omitted (fail-closed).
    close == ma is not above.
    """
    if window <= 1:
        raise ValueError("MA5 window must be at least 2")
    by_day: dict[date, float] = {}
    for raw_day, raw_px in closes.items():
        try:
            px = float(raw_px)
        except (TypeError, ValueError):
            continue
        if px != px or px <= 0 or px in (float("inf"), float("-inf")):
            continue
        day = raw_day if isinstance(raw_day, date) else pd.Timestamp(raw_day).date()
        by_day[day] = px
    ordered = sorted(by_day)
    out: dict[str, tuple[float, float]] = {}
    for i, day in enumerate(ordered):
        if i + 1 < window:
            continue
        sample = ordered[i + 1 - window : i + 1]
        out[day.strftime("%Y%m%d")] = (
            by_day[day],
            sum(by_day[item] for item in sample) / window,
        )
    return out


def with_ma5_gate(
    eligible_buy: EligibleBuyFn | None,
    bars: Mapping[str, pd.DataFrame],
    *,
    window: int = MA5_DAYS,
) -> EligibleBuyFn:
    """Require that day's close > its own 5-day mean. Missing history fails closed.

    Seat gate: a miss leaves the buy seat empty. Does not force-sell.
    """
    tables: dict[str, dict[str, tuple[float, float]]] = {}
    for code, frame in bars.items():
        canon = _bare_or_canon(code) or str(code)
        tables[canon] = ma5_asof(_frame_closes(frame), window=window)

    def list_ok(code: str, buy_date: str) -> bool:
        return _part(eligible_buy, "list_ok", code, buy_date, missing=True)

    def seat_ok(code: str, buy_date: str) -> bool:
        if not _part(eligible_buy, "seat_ok", code, buy_date, missing=False):
            return False
        canon = _bare_or_canon(code) or str(code)
        point = tables.get(canon, {}).get(_ymd(buy_date))
        if point is None:
            return False
        close, ma = point
        return close > ma

    def gated(code: str, buy_date: str) -> bool:
        return list_ok(code, buy_date) and seat_ok(code, buy_date)

    gated.list_ok = list_ok  # type: ignore[attr-defined]
    gated.seat_ok = seat_ok  # type: ignore[attr-defined]
    return gated


def load_buy_state_sidecar(path: Path | str) -> dict[tuple[str, str], BuyStateRow]:
    """MyQuant export: trade_date, code, close, ma20, ma60, winratio.

    Missing file fail-closed. Unknown code rows skipped. Incomplete rows skipped
    (eligible_buy then fail-closed for that name-day).
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"buy-state-file not found: {p}")
    if p.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(p)
    else:
        df = pd.read_csv(p, dtype=str, encoding="utf-8")
    if df is None or df.empty:
        return {}
    cols = {str(c).strip().lower(): c for c in df.columns}

    def _col(*names: str):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    date_c = _col("trade_date", "date", "datetime", "dt")
    code_c = _col("code", "instrument", "stock_code", "symbol")
    close_c = _col("close", "$close")
    ma20_c = _col(
        "ma20", "ma_20", "mean_close_20", "mean($close, 20)", "mean($close,20)"
    )
    ma60_c = _col(
        "ma60", "ma_60", "mean_close_60", "mean($close, 60)", "mean($close,60)"
    )
    wr_c = _col("winratio", "$winratio", "win_ratio")
    if not all((date_c, code_c, close_c, ma20_c, ma60_c, wr_c)):
        raise ValueError(
            "buy-state-file needs trade_date, code, close, ma20, ma60, winratio"
        )
    date_s = pd.to_datetime(df[date_c], errors="coerce")
    close = pd.to_numeric(df[close_c], errors="coerce")
    ma20 = pd.to_numeric(df[ma20_c], errors="coerce")
    ma60 = pd.to_numeric(df[ma60_c], errors="coerce")
    wr = pd.to_numeric(df[wr_c], errors="coerce")
    ok = date_s.notna() & close.notna() & ma20.notna() & ma60.notna() & wr.notna()
    out: dict[tuple[str, str], BuyStateRow] = {}
    for code_raw, ts, c, m20, m60, w in zip(
        df.loc[ok, code_c],
        date_s.loc[ok],
        close.loc[ok],
        ma20.loc[ok],
        ma60.loc[ok],
        wr.loc[ok],
    ):
        code = _bare_or_canon(code_raw)
        if not code:
            continue
        out[(code, ts.strftime("%Y%m%d"))] = (
            float(c),
            float(m20),
            float(m60),
            float(w),
        )
    return out


# One tape for every name: 上证指数. Lake path index/period=1d, dividend_type=none.
SSE_INDEX_SYMBOL = "000001.SH"
INDEX_MA_WINDOW = 5


def index_ma5_buy_days(
    closes: Mapping,
    *,
    window: int = INDEX_MA_WINDOW,
) -> tuple[set[str], set[str]]:
    """Split later sessions into blocked vs allowed buy days.

    Signal day S is the previous positive-close session. Buy day is the next
    session. Block when close[S] < mean of `window` closes ending at S.
    close == MA does not block. Fewer than `window` closes before the buy
    day is blocked (fail-closed). Non-positive closes are dropped first.
    """
    if window <= 0:
        raise ValueError("index MA window must be positive")
    points: list[tuple[date, float]] = []
    for raw_day, raw_px in closes.items():
        try:
            px = float(raw_px)
        except (TypeError, ValueError):
            continue
        if px != px or px <= 0 or px in (float("inf"), float("-inf")):
            continue
        day = raw_day if isinstance(raw_day, date) else pd.Timestamp(raw_day).date()
        points.append((day, px))
    points.sort(key=lambda item: item[0])
    blocked: set[str] = set()
    allowed: set[str] = set()
    for i in range(1, len(points)):
        sig = i - 1
        ymd = points[i][0].strftime("%Y%m%d")
        if sig + 1 < window:
            blocked.add(ymd)
            continue
        ma = sum(px for _, px in points[sig - window + 1 : sig + 1]) / window
        if points[sig][1] < ma:
            blocked.add(ymd)
        else:
            allowed.add(ymd)
    return blocked, allowed


def load_board_index_closes(
    *,
    root: Path | str | None = None,
) -> dict[str, dict[date, float]]:
    """Read 上证指数 daily closes. Missing partition fails closed."""
    from common.infra.data_root import resolve_index_daily_root
    from oskh_data.symbol_format import to_partition_key

    from backtest.research.market_layer import as_date

    base = Path(root) if root is not None else resolve_index_daily_root()
    out: dict[str, dict[date, float]] = {}
    for symbol in (SSE_INDEX_SYMBOL,):
        directory = base / "dividend_type=none" / f"symbol={to_partition_key(symbol)}"
        files = sorted(directory.glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"index daily partition missing: {directory}")
        frame = pd.concat((pd.read_parquet(path) for path in files), ignore_index=True)
        day_col = next(
            (
                name
                for name in ("date", "datetime", "timestamp", "time")
                if name in frame
            ),
            None,
        )
        if day_col is None or "close" not in frame.columns:
            raise ValueError(
                f"index parquet needs a date column and close: {directory}"
            )
        closes: dict[date, float] = {}
        for raw_day, raw_close in zip(frame[day_col], frame["close"]):
            try:
                px = float(raw_close)
            except (TypeError, ValueError):
                continue
            if px != px or px <= 0:
                continue
            closes[as_date(raw_day)] = px
        if not closes:
            raise FileNotFoundError(f"index daily has no positive close: {directory}")
        out[symbol] = closes
    return out


def make_eligible_buy(
    *,
    st_daily_file: Path | str | None = None,
    age_map_file: Path | str | None = None,
    age_days: int = 60,
    calendar_ymd: Sequence[str] | None = None,
    st_by_day: Mapping[date, set[str]] | None = None,
    min_buy_ymd: Mapping[str, str] | None = None,
    buy_state_file: Path | str | None = None,
    buy_state_by_key: Mapping[tuple[str, str], BuyStateRow] | None = None,
    index_ma5_gate: bool = False,
    index_closes_by_symbol: Mapping[str, Mapping] | None = None,
    buy_state_rule: str = "oral",
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

    state_map: dict[tuple[str, str], BuyStateRow]
    if buy_state_by_key is not None:
        state_map = dict(buy_state_by_key)
    elif buy_state_file is not None:
        state_map = load_buy_state_sidecar(buy_state_file)
    else:
        state_map = {}

    sse_allowed: set[str] = set()
    if index_ma5_gate:
        series = (
            dict(index_closes_by_symbol)
            if index_closes_by_symbol is not None
            else load_board_index_closes()
        )
        closes = series.get(SSE_INDEX_SYMBOL)
        if not closes:
            raise FileNotFoundError(
                f"index MA5 gate missing closes: {SSE_INDEX_SYMBOL}"
            )
        sse_allowed = index_ma5_buy_days(closes)[1]

    check_st = st_daily_file is not None or st_by_day is not None
    check_age = age_map_file is not None or min_buy_ymd is not None
    check_state = buy_state_file is not None or buy_state_by_key is not None
    check_index = bool(index_ma5_gate)
    rule = str(buy_state_rule or "oral")
    if rule not in BUY_STATE_RULES:
        raise ValueError(
            f"buy_state_rule must be one of {BUY_STATE_RULES}, got {buy_state_rule!r}"
        )
    above_only = rule in ("above-ma20", "above-ma20-week20", "above-ma5-ma20-week20")
    if above_only and not check_state:
        raise ValueError(f"buy_state_rule {rule} requires buy-state rows")
    state_ok = buy_state_above_ma20_ok if above_only else buy_state_oral_ok

    def list_ok(code: str, buy_date: str) -> bool:
        c = _bare_or_canon(code) or str(code)
        ds = _ymd(buy_date)
        if check_st and c in st_codes_asof(st_map, ds):
            return False
        if check_age:
            min_d = age_map.get(c)
            if min_d is None or ds < min_d:
                return False
        return True

    def seat_ok(code: str, buy_date: str) -> bool:
        c = _bare_or_canon(code) or str(code)
        ds = _ymd(buy_date)
        if check_state:
            row = state_map.get((c, ds))
            if row is None or not state_ok(*row):
                return False
        if check_index and ds not in sse_allowed:
            return False
        return True

    def eligible_buy(code: str, buy_date: str) -> bool:
        return list_ok(code, buy_date) and seat_ok(code, buy_date)

    eligible_buy.list_ok = list_ok  # type: ignore[attr-defined]
    eligible_buy.seat_ok = seat_ok  # type: ignore[attr-defined]
    return eligible_buy


def _part(fn, name: str, code: str, buy_date: str, *, missing: bool) -> bool:
    if fn is None:
        return True
    piece = getattr(fn, name, None)
    if piece is None:
        return True if missing else bool(fn(code, buy_date))
    return bool(piece(code, buy_date))


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

    def return_ok(code: str, buy_date: str) -> bool:
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

    def list_ok(code: str, buy_date: str) -> bool:
        return _part(
            eligible_buy, "list_ok", code, buy_date, missing=False
        ) and return_ok(code, buy_date)

    def seat_ok(code: str, buy_date: str) -> bool:
        return _part(eligible_buy, "seat_ok", code, buy_date, missing=True)

    def gated(code: str, buy_date: str) -> bool:
        return list_ok(code, buy_date) and seat_ok(code, buy_date)

    gated.list_ok = list_ok  # type: ignore[attr-defined]
    gated.seat_ok = seat_ok  # type: ignore[attr-defined]
    return gated
