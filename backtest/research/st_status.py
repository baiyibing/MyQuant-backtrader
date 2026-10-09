"""Wind ``st_daily`` membership for research backtests.

Reads ``vendor_wind_st_status/st_daily.parquet`` under the parquet container.
A code is ST on a session only when that file has ``is_st`` true for the date.
A missing file or a missing row is a waiver: the name is not treated as ST.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from oskh_core.a_share_symbol_normalize import canonical_from_bare_code

_ST_RELATIVE = Path("vendor_wind_st_status") / "st_daily.parquet"


def st_daily_path() -> Path | None:
    """Lake path of the Wind daily ST table, or None when the container is unset."""
    try:
        from common.infra.data_root import resolve_parquet_container
    except Exception:
        return None
    try:
        return resolve_parquet_container() / _ST_RELATIVE
    except Exception:
        return None


def _ymd(value) -> str:
    text = str(value).strip().replace("-", "")
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[:8]


def membership_from_frame(frame: pd.DataFrame) -> dict[str, set[str]]:
    """``{YYYYMMDD: {canonical code}}`` for rows with ``is_st`` true."""
    if frame is None or frame.empty:
        return {}
    if not {"trade_date", "code", "is_st"}.issubset(frame.columns):
        raise ValueError("st_daily.parquet needs code/trade_date/is_st")
    hit = frame[frame["is_st"] == True]  # noqa: E712
    out: dict[str, set[str]] = {}
    for raw_day, raw_code in zip(hit["trade_date"], hit["code"], strict=False):
        day = _ymd(pd.Timestamp(raw_day))
        code = canonical_from_bare_code(str(raw_code))
        if day and code:
            out.setdefault(day, set()).add(code)
    return out


@lru_cache(maxsize=4)
def _load_cached(path_text: str) -> dict[str, frozenset[str]]:
    frame = pd.read_parquet(path_text, columns=["trade_date", "code", "is_st"])
    return {day: frozenset(codes) for day, codes in membership_from_frame(frame).items()}


def load_st_membership(path: Path | str | None = None) -> dict[str, frozenset[str]]:
    """Load the lake table. Missing path or file returns an empty map (waiver)."""
    chosen = Path(path) if path is not None else st_daily_path()
    if chosen is None or not chosen.is_file():
        return {}
    return _load_cached(str(chosen.resolve()))


def is_st_on(code: str, ymd: str, membership: dict | None = None) -> bool:
    """True only when the loaded table marks this code ST on this session."""
    table = load_st_membership() if membership is None else membership
    canon = canonical_from_bare_code(str(code))
    return canon in table.get(_ymd(ymd), ())


def drop_st_names(days: dict, membership: dict | None = None) -> tuple[dict, int]:
    """Drop signal-day names that the table marks ST. Missing rows stay."""
    table = load_st_membership() if membership is None else membership
    kept: dict = {}
    dropped = 0
    for raw_day, codes in days.items():
        day = _ymd(raw_day)
        accepted = []
        for code in codes:
            if is_st_on(code, day, table):
                dropped += 1
                continue
            accepted.append(code)
        if accepted:
            kept[raw_day] = accepted
    return kept, dropped
