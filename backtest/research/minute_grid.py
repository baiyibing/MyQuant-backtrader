"""Minute layout switches. The lake cache stays variable-length frames.

``OSKH_MINUTE_LENGTH`` is ``variable`` (default) or ``fixed``.
``OSKH_MINUTE_STORE`` is ``frame`` (default) or ``array``.
The two switches are independent. ``fixed`` is one row per in-session minute,
242 slots, and a missing minute stays an empty slot: NaN prices, clock still
in ``hm``. An empty slot is not a bar and must not trade. Days with no
in-session minute stay absent. A later duplicate ``hm`` overwrites the slot.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

from backtest.research.ashare_bars import AM_CLOSE, AM_OPEN, PM_CLOSE, PM_OPEN
from backtest.research.bar_store import build_day_spans

SESSION_HM = np.concatenate(
    [
        np.arange(AM_OPEN, AM_CLOSE + 1, dtype=np.int64),
        np.arange(PM_OPEN, PM_CLOSE + 1, dtype=np.int64),
    ]
)
SESSION_BARS = int(SESSION_HM.shape[0])
if SESSION_BARS != 242:
    raise RuntimeError(f"A-share minute session is 242 slots, got {SESSION_BARS}")

_SLOT = np.full(PM_CLOSE + 1, -1, dtype=np.int16)
_SLOT[SESSION_HM] = np.arange(SESSION_BARS, dtype=np.int16)


def resolve_minute_layout(length=None, store=None) -> tuple[str, str]:
    """``None`` reads ``OSKH_MINUTE_LENGTH`` / ``OSKH_MINUTE_STORE``."""
    if length is None or str(length).strip() == "":
        length = os.environ.get("OSKH_MINUTE_LENGTH") or "variable"
    if store is None or str(store).strip() == "":
        store = os.environ.get("OSKH_MINUTE_STORE") or "frame"
    length = str(length).strip().lower()
    store = str(store).strip().lower()
    if length not in {"variable", "fixed"}:
        raise ValueError(f"minute length must be variable or fixed, got {length}")
    if store not in {"frame", "array"}:
        raise ValueError(f"minute store must be frame or array, got {store}")
    return length, store


class _Col:
    def __init__(self, values: np.ndarray):
        self._values = values

    def to_numpy(self, dtype=None, copy=False):
        arr = self._values
        if dtype is None:
            return arr.copy() if copy else arr
        dtype = np.dtype(dtype)
        if arr.dtype == dtype and not copy:
            return arr
        return np.array(arr, dtype=dtype, copy=True)

    def min(self):
        arr = self._values
        if arr.size == 0 or not np.isfinite(arr).any():
            return float("nan")
        return float(np.nanmin(arr))

    def __eq__(self, other):
        return self._values == other

    def between(self, left, right, inclusive="both"):
        if inclusive != "both":
            raise ValueError(inclusive)
        return (self._values >= left) & (self._values <= right)

    @property
    def iloc(self):
        return self._values


class _Loc:
    def __init__(self, owner: MinuteBars):
        self.owner = owner

    def __getitem__(self, key):
        mask = np.asarray(key, dtype=bool)
        return self.owner.take(np.flatnonzero(mask))


class _ILoc:
    def __init__(self, owner: MinuteBars):
        self.owner = owner

    def __getitem__(self, key):
        n = len(self.owner)
        if isinstance(key, slice):
            start, stop, step = key.indices(n)
            if step == 1:
                return self.owner.view(start, stop)
            return self.owner.take(np.arange(start, stop, step, dtype=np.int64))
        if isinstance(key, (int, np.integer)):
            idx = int(key)
            if idx < 0:
                idx += n
            return self.owner.take(np.asarray([idx], dtype=np.int64))
        raise TypeError(f"unsupported iloc key: {type(key)!r}")


class MinuteBars:
    """Column arrays in the same row order as the frame they were built from."""

    def __init__(
        self,
        *,
        open,
        high,
        low,
        close,
        hm,
        ymd,
        volume,
        amount,
        spans: dict,
    ):
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.hm = hm
        self.ymd = ymd
        self.volume = volume
        self.amount = amount
        self.spans = spans

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> MinuteBars:
        if df is None or df.empty:
            empty_px = np.zeros(0, np.float64)
            return cls(
                open=empty_px,
                high=empty_px,
                low=empty_px,
                close=empty_px,
                hm=np.zeros(0, np.int64),
                ymd=np.zeros(0, dtype="U8"),
                volume=None,
                amount=None,
                spans={},
            )
        spans = build_day_spans(df)
        if not spans:
            df = df.sort_values(["ymd", "hm"], kind="mergesort")
            spans = build_day_spans(df)

        def col(name, dtype):
            return np.asarray(df[name].to_numpy(dtype, copy=False))

        return cls(
            open=col("open", np.float64),
            high=col("high", np.float64),
            low=col("low", np.float64),
            close=col("close", np.float64),
            hm=col("hm", np.int64),
            ymd=np.asarray(df["ymd"].to_numpy()),
            volume=col("volume", np.float64) if "volume" in df.columns else None,
            amount=col("amount", np.float64) if "amount" in df.columns else None,
            spans=spans,
        )

    def __len__(self) -> int:
        return int(self.close.shape[0])

    @property
    def empty(self) -> bool:
        return len(self) == 0

    @property
    def columns(self) -> tuple[str, ...]:
        names = ["open", "high", "low", "close", "ymd", "hm"]
        if self.volume is not None:
            names.append("volume")
        if self.amount is not None:
            names.append("amount")
        return tuple(names)

    def __getitem__(self, key: str) -> _Col:
        if key == "ymd":
            return _Col(self.ymd)
        if key == "hm":
            return _Col(self.hm)
        arr = getattr(self, key, None)
        if arr is None or key not in {"open", "high", "low", "close", "volume", "amount"}:
            raise KeyError(key)
        return _Col(arr)

    @property
    def loc(self) -> _Loc:
        return _Loc(self)

    @property
    def iloc(self) -> _ILoc:
        return _ILoc(self)

    def view(self, start: int, stop: int) -> MinuteBars:
        return MinuteBars(
            open=self.open[start:stop],
            high=self.high[start:stop],
            low=self.low[start:stop],
            close=self.close[start:stop],
            hm=self.hm[start:stop],
            ymd=self.ymd[start:stop],
            volume=None if self.volume is None else self.volume[start:stop],
            amount=None if self.amount is None else self.amount[start:stop],
            spans={},
        )

    def take(self, idx) -> MinuteBars:
        idx = np.asarray(idx, dtype=np.int64)
        return MinuteBars(
            open=self.open[idx],
            high=self.high[idx],
            low=self.low[idx],
            close=self.close[idx],
            hm=self.hm[idx],
            ymd=self.ymd[idx],
            volume=None if self.volume is None else self.volume[idx],
            amount=None if self.amount is None else self.amount[idx],
            spans={},
        )

    def to_frame(self) -> pd.DataFrame:
        data = {
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "ymd": self.ymd,
            "hm": self.hm,
        }
        if self.volume is not None:
            data["volume"] = self.volume
        if self.amount is not None:
            data["amount"] = self.amount
        return pd.DataFrame(data)


def _day_bounds(ymd: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if len(ymd) <= 1:
        change = np.zeros(0, dtype=np.int64)
    else:
        change = np.flatnonzero(ymd[1:] != ymd[:-1]) + 1
    starts = np.concatenate((np.asarray([0], dtype=np.int64), change))
    ends = np.concatenate((change, np.asarray([len(ymd)], dtype=np.int64)))
    return starts, ends


def densify_frame(df: pd.DataFrame) -> pd.DataFrame:
    """One 242-slot block per day that has an in-session minute."""
    if df is None or len(df) == 0:
        return df
    ymd = df["ymd"].to_numpy()
    try:
        unsorted = len(ymd) >= 2 and bool(np.any(ymd[1:] < ymd[:-1]))
    except TypeError:
        unsorted = True
    if unsorted:
        df = df.sort_values(["ymd", "hm"], kind="mergesort")
        ymd = df["ymd"].to_numpy()
    hm = df["hm"].to_numpy(np.int64, copy=False)
    starts, ends = _day_bounds(ymd)
    bounds: list[tuple[int, int]] = []
    for s, e in zip(starts.tolist(), ends.tolist()):
        raw = hm[s:e]
        in_session = ((raw >= AM_OPEN) & (raw <= AM_CLOSE)) | ((raw >= PM_OPEN) & (raw <= PM_CLOSE))
        if np.any(in_session):
            bounds.append((s, e))
    if not bounds:
        return df.iloc[0:0]
    n = len(bounds) * SESSION_BARS
    src = {
        name: df[name].to_numpy(np.float64, copy=False)
        for name in ("open", "high", "low", "close")
    }
    for name in ("volume", "amount"):
        if name in df.columns:
            src[name] = df[name].to_numpy(np.float64, copy=False)
    cols = {name: np.full(n, np.nan, dtype=np.float64) for name in src}
    ymd_out = np.empty(n, dtype=object)
    hm_out = np.tile(SESSION_HM, len(bounds))
    for day_i, (s, e) in enumerate(bounds):
        base = day_i * SESSION_BARS
        ymd_out[base : base + SESSION_BARS] = ymd[s]
        raw = hm[s:e]
        slots = np.full(e - s, -1, dtype=np.int32)
        ok = (raw >= 0) & (raw <= PM_CLOSE)
        if np.any(ok):
            slots[ok] = _SLOT[raw[ok]]
        keep = np.flatnonzero(slots >= 0)
        if keep.size == 0:
            continue
        slot_k = slots[keep]
        src_k = keep + s
        rev_slots = slot_k[::-1]
        rev_src = src_k[::-1]
        uniq, first = np.unique(rev_slots, return_index=True)
        dest = base + uniq.astype(np.int64)
        chosen = rev_src[first]
        for name, arr in src.items():
            cols[name][dest] = arr[chosen]
    out = pd.DataFrame(cols)
    out["ymd"] = ymd_out
    out["hm"] = hm_out
    return out


def apply_minute_layout(bars: dict, length: str, store: str) -> dict:
    """Return ``bars`` unchanged for the default variable DataFrame layout."""
    length, store = resolve_minute_layout(length, store)
    if length == "variable" and store == "frame":
        return bars
    out = {}
    for code, frame in bars.items():
        if frame is None or getattr(frame, "empty", True):
            out[code] = frame
            continue
        laid = densify_frame(frame) if length == "fixed" else frame
        out[code] = MinuteBars.from_frame(laid) if store == "array" else laid
    return out
