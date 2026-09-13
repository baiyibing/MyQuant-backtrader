"""底量超顶量（策略 9）买点：只看 ``date<=T`` 的 OHLCV，禁止未来函数。

通达信式 ``SUM(VOL, 底距今-3, 底距今+3)`` 在底靠近 T 时会读到 T+1..T+3。
本模块把量能窗裁到 ``[0, T]``。顶/底取最近 N 根（含 T）的 HHV(H)/LLV(L)，
并列取最近一根（BARSLAST）。不写 ``stock_pool/``，不 import qlib。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Optional

import numpy as np
import pandas as pd

from backtest.research.market_layer import board_limit_pct, is_st_name

LOOKBACK = 120
VOL_HALF = 3
MIN_TOP_LEAD = 10
MIN_BOTTOM_AGE = 1
MAX_BOTTOM_AGE = 15
R_MIN = 1.2
CLOSE_CAP = 1.10
MIN_LISTED_BARS = 250
TURNOVER_MIN = 0.10
TINY_TOP_TURNOVER = 0.02
FORWARD_HORIZONS = (1, 5, 10, 20, 30)
REQUIRED_OHLCV = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class BottomVolSignal:
    ymd: str
    top_ago: int
    bottom_ago: int
    top_vol: float
    bottom_vol: float
    ratio: float


def is_main_board_code(code: str) -> bool:
    """主板 + 中小板（10% 档）。创科 / 北交 / 未知前缀一律 False。"""
    return board_limit_pct(code) == 0.10


def last_extreme_ago(
    values: np.ndarray, t: int, lookback: int = LOOKBACK, *, which: str
) -> Optional[int]:
    """Bars since the most recent HHV/LLV in ``[t-lookback+1, t]``."""
    start = int(t) - int(lookback) + 1
    if start < 0 or t >= len(values):
        return None
    window = np.asarray(values[start : t + 1], dtype=np.float64)
    if window.size == 0 or not np.isfinite(window).all():
        return None
    if which == "high":
        target = float(np.max(window))
    elif which == "low":
        target = float(np.min(window))
    else:
        raise ValueError(f"which must be 'high' or 'low', got {which!r}")
    rel = int(np.flatnonzero(window == target)[-1])
    return int(t - (start + rel))


def clipped_volume_sum(
    volume: np.ndarray,
    center: int,
    t: int,
    half: int = VOL_HALF,
) -> float:
    """Sum volume on ``[center-half, center+half]`` clipped to ``[0, t]``."""
    lo = max(0, int(center) - int(half))
    hi = min(int(t), int(center) + int(half))
    if hi < lo:
        return 0.0
    return float(np.sum(np.asarray(volume[lo : hi + 1], dtype=np.float64)))


def forward_close_returns(
    close: np.ndarray,
    t: int,
    horizons: Iterable[int] = FORWARD_HORIZONS,
) -> dict[int, Optional[float]]:
    """Event-study close-to-close returns. Uses bars after T; not a buy input."""
    px = float(close[t]) if 0 <= t < len(close) else 0.0
    out: dict[int, Optional[float]] = {}
    for raw in horizons:
        h = int(raw)
        j = int(t) + h
        if px <= 0 or j >= len(close) or j < 0:
            out[h] = None
        else:
            out[h] = float(close[j]) / px - 1.0
    return out


def _as_ymd(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y%m%d")


def _window_max_turnover(
    volume: np.ndarray,
    shares: Optional[np.ndarray],
    lo: int,
    hi: int,
) -> Optional[float]:
    if shares is None or hi < lo:
        return None
    vol = np.asarray(volume[lo : hi + 1], dtype=np.float64)
    sh = np.asarray(shares[lo : hi + 1], dtype=np.float64)
    if vol.size == 0 or sh.size != vol.size:
        return None
    if not np.isfinite(sh).all() or np.any(sh <= 0):
        return None
    return float(np.max(vol / sh))


def _optional_float_shares(
    df: pd.DataFrame, aligned: Optional[pd.Series]
) -> Optional[np.ndarray]:
    if aligned is not None:
        return np.asarray(aligned.reindex(df.index).to_numpy(), dtype=np.float64)
    if "float_shares" in df.columns:
        return np.asarray(df["float_shares"].to_numpy(), dtype=np.float64)
    return None


def evaluate_at(
    df: pd.DataFrame,
    ts,
    *,
    code: str,
    name: str = "",
    float_shares: Optional[pd.Series] = None,
    lookback: int = LOOKBACK,
    r_min: float = R_MIN,
) -> Optional[BottomVolSignal]:
    """Return a signal when T is a valid 底量超顶量 bar; else None."""
    if not is_main_board_code(code) or is_st_name(name):
        return None
    if any(col not in df.columns for col in REQUIRED_OHLCV):
        return None
    day = pd.Timestamp(ts).normalize()
    if day not in df.index:
        return None
    loc = df.index.get_loc(day)
    t = int(loc.stop - 1) if isinstance(loc, slice) else int(loc)
    if t + 1 < MIN_LISTED_BARS or t + 1 < int(lookback):
        return None

    high = np.asarray(df["high"].to_numpy(), dtype=np.float64)
    low = np.asarray(df["low"].to_numpy(), dtype=np.float64)
    close = np.asarray(df["close"].to_numpy(), dtype=np.float64)
    volume = np.asarray(df["volume"].to_numpy(), dtype=np.float64)
    top_ago = last_extreme_ago(high, t, lookback, which="high")
    bottom_ago = last_extreme_ago(low, t, lookback, which="low")
    if top_ago is None or bottom_ago is None:
        return None
    if not (MIN_BOTTOM_AGE <= bottom_ago <= MAX_BOTTOM_AGE):
        return None
    if top_ago <= bottom_ago + MIN_TOP_LEAD:
        return None

    bottom_i = t - bottom_ago
    top_i = t - top_ago
    after = low[bottom_i + 1 : t + 1]
    if after.size == 0 or float(np.min(after)) <= float(low[bottom_i]):
        return None
    if float(close[t]) > float(low[bottom_i]) * float(CLOSE_CAP):
        return None

    top_vol = clipped_volume_sum(volume, top_i, t)
    bottom_vol = clipped_volume_sum(volume, bottom_i, t)
    if top_vol <= 0 or bottom_vol <= top_vol * float(r_min):
        return None

    shares = _optional_float_shares(df, float_shares)
    if shares is not None:
        b_lo, b_hi = max(0, bottom_i - VOL_HALF), min(t, bottom_i + VOL_HALF)
        t_lo, t_hi = max(0, top_i - VOL_HALF), min(t, top_i + VOL_HALF)
        bottom_to = _window_max_turnover(volume, shares, b_lo, b_hi)
        top_to = _window_max_turnover(volume, shares, t_lo, t_hi)
        if bottom_to is not None and top_to is not None:
            if bottom_to < TURNOVER_MIN or top_to < TINY_TOP_TURNOVER:
                return None

    return BottomVolSignal(
        ymd=_as_ymd(day),
        top_ago=int(top_ago),
        bottom_ago=int(bottom_ago),
        top_vol=float(top_vol),
        bottom_vol=float(bottom_vol),
        ratio=float(bottom_vol / top_vol),
    )


def scan_symbol(
    df: pd.DataFrame,
    start: str,
    end: str,
    *,
    code: str,
    name: str = "",
    float_shares: Optional[pd.Series] = None,
) -> list[BottomVolSignal]:
    """Evaluate every bar in ``[start, end]`` that exists on ``df``."""
    t0 = pd.Timestamp(start)
    t1 = pd.Timestamp(end)
    hits: list[BottomVolSignal] = []
    for ts in df.index[(df.index >= t0) & (df.index <= t1)]:
        sig = evaluate_at(df, ts, code=code, name=name, float_shares=float_shares)
        if sig is not None:
            hits.append(sig)
    return hits


def scan_ohlcv(
    frames: Mapping[str, pd.DataFrame],
    start: str,
    end: str,
    *,
    names: Optional[Mapping[str, str]] = None,
) -> dict[str, list[str]]:
    """``{YYYYMMDD: [canonical codes]}`` for days that have at least one hit."""
    name_map = dict(names or {})
    days: dict[str, list[str]] = {}
    for code, frame in frames.items():
        for sig in scan_symbol(
            frame, start, end, code=code, name=name_map.get(code, "")
        ):
            days.setdefault(sig.ymd, []).append(code)
    return {ymd: sorted(set(codes)) for ymd, codes in days.items() if codes}
