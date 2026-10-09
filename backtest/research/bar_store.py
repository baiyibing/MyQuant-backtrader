"""Process-local bar reuse and minute day-span sidecars.

Frames checked out of the store are read-only. File caches remain the
cross-process source of truth; this module only skips a second decode.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_MEM: dict[tuple, dict] = {}


def mem_enabled() -> bool:
    flag = (os.environ.get("OSKH_BAR_MEM") or "1").strip().lower()
    return flag not in {"0", "false", "off", "no"}


def mem_clear() -> None:
    _MEM.clear()


def mem_key(kind: str, identity: dict, extra: tuple = ()) -> tuple:
    items = tuple(
        sorted((str(k), json.dumps(v, sort_keys=True, default=str)) for k, v in identity.items())
    )
    return (kind, items, extra)


def mem_get(key: tuple, want: set[str]) -> Optional[dict]:
    if not mem_enabled():
        return None
    entry = _MEM.get(key)
    if entry is None or not want <= entry["codes"]:
        return None
    return {code: entry["bars"][code] for code in want if code in entry["bars"]}


def mem_put(key: tuple, bars: dict) -> None:
    if not mem_enabled() or not bars:
        return
    entry = _MEM.setdefault(key, {"codes": set(), "bars": {}, "spans": None})
    entry["bars"].update(bars)
    entry["codes"].update(bars.keys())


def mem_drop(key: tuple) -> None:
    _MEM.pop(key, None)


def mem_get_spans(key: tuple, want: set[str]) -> Optional[dict]:
    if not mem_enabled():
        return None
    entry = _MEM.get(key)
    spans = None if entry is None else entry.get("spans")
    if not spans or not want <= set(spans):
        return None
    return {code: spans[code] for code in want if code in spans}


def mem_put_spans(key: tuple, spans: dict) -> None:
    if not mem_enabled() or not spans:
        return
    entry = _MEM.setdefault(key, {"codes": set(), "bars": {}, "spans": None})
    if entry["spans"] is None:
        entry["spans"] = {}
    entry["spans"].update(spans)


def build_day_spans(df: pd.DataFrame) -> dict[str, tuple[int, int]]:
    """Split a time-sorted minute frame into ``ymd -> (iloc_lo, iloc_hi)``."""
    if df is None or df.empty or "ymd" not in df.columns:
        return {}
    ymd = df["ymd"].to_numpy()
    if len(ymd) >= 2 and np.any(ymd[1:] < ymd[:-1]):
        return {}
    change = np.flatnonzero(ymd[1:] != ymd[:-1]) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [len(ymd)]))
    return {str(ymd[s]): (int(s), int(e)) for s, e in zip(starts, ends)}


def build_day_spans_map(bars: dict) -> dict[str, dict[str, tuple[int, int]]]:
    return {
        code: build_day_spans(frame)
        for code, frame in bars.items()
        if frame is not None and not getattr(frame, "empty", True)
    }


def span_sidecar_path(cache_path: Path) -> Path:
    return cache_path.with_name(cache_path.stem + ".spans.json")


def _fingerprints(bars: dict) -> dict[str, list]:
    out: dict[str, list] = {}
    for code, frame in bars.items():
        if frame is None or getattr(frame, "empty", True) or "ymd" not in frame.columns:
            continue
        ymd = frame["ymd"].to_numpy()
        out[str(code)] = [int(len(frame)), str(ymd[0]), str(ymd[-1])]
    return out


def write_span_sidecar(cache_path: Path, identity: dict, bars: dict) -> Path:
    spans = build_day_spans_map(bars)
    path = span_sidecar_path(cache_path)
    path.write_text(
        json.dumps(
            {
                "start": identity.get("start"),
                "end": identity.get("end"),
                "resolver_identity": identity.get("resolver_identity"),
                "source_snapshot": identity.get("source_snapshot"),
                "fingerprints": _fingerprints(bars),
                "spans": {
                    code: {ymd: [int(lo), int(hi)] for ymd, (lo, hi) in rows.items()}
                    for code, rows in spans.items()
                },
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def read_span_sidecar(
    cache_path: Path, identity: dict, bars: dict
) -> Optional[dict[str, dict[str, tuple[int, int]]]]:
    path = span_sidecar_path(cache_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    for field in ("start", "end", "resolver_identity", "source_snapshot"):
        if payload.get(field) != identity.get(field):
            return None
    marks = payload.get("fingerprints") or {}
    raw_spans = payload.get("spans") or {}
    expect = _fingerprints(bars)
    if any(marks.get(code) != finger for code, finger in expect.items()):
        return None
    out: dict[str, dict[str, tuple[int, int]]] = {}
    for code in expect:
        rows = raw_spans.get(code) or {}
        out[code] = {str(ymd): (int(pair[0]), int(pair[1])) for ymd, pair in rows.items()}
    return out


def resolve_day_spans(
    bars: dict,
    *,
    identity: Optional[dict] = None,
    cache_path: Optional[Path] = None,
    mem_id: Optional[tuple] = None,
) -> dict[str, dict[str, tuple[int, int]]]:
    """Return per-code day spans; persist a sidecar when the cache path is known."""
    want = set(bars)
    if mem_id is not None:
        hit = mem_get_spans(mem_id, want)
        if hit is not None:
            return hit
    spans = None
    if identity is not None and cache_path is not None:
        spans = read_span_sidecar(cache_path, identity, bars)
    if spans is None:
        spans = build_day_spans_map(bars)
        if identity is not None and cache_path is not None:
            write_span_sidecar(cache_path, identity, bars)
    if mem_id is not None:
        mem_put_spans(mem_id, spans)
    return spans
