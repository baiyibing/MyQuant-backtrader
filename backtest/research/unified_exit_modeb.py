# -*- coding: utf-8 -*-
"""Unified-exit Mode B: none daily entries, session-minute exits (Q36/Q37).

Research only. Mode A and the shared trading ledger remain unchanged.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from backtest.research import unified_exit_modea as modea
from backtest.research.csv_daily_loader import warmup_start
from backtest.research.exdiv_map import load_exdiv_ratios
from backtest.research.ashare_bars import (
    AM_CLOSE,
    AM_OPEN,
    CACHE_ROOT,
    MINUTE_LAKE_END,
    PM_CLOSE,
    PM_OPEN,
    load_minute_bars,
)
from backtest.research.market_layer import as_date, limit_pct
from backtest.research import strategy8_rules as s8
from common.infra.data_root import resolve_period_root


def load_none_bars(codes, start, end, *, none_root=None, workers=8, bars=None):
    """Reuse daily I/O only, explicitly selecting the unadjusted price domain."""
    root = Path(none_root) if none_root is not None else resolve_period_root("1d") / "dividend_type=none"
    return modea.load_front_bars(codes, start, end, front_root=root, workers=workers, bars=bars)


def load_monitor_bars(codes, start=modea.DEFAULT_START, end=modea.DEFAULT_END,
                      *, workers=16, cache_dir=None, status=None):
    """Use the existing ten-calendar-day warmup cache (20251013 by default)."""
    return load_minute_bars(set(codes), warmup_start(start, days=10), end,
                            workers=workers, use_cache=True,
                            cache_dir=cache_dir, status=status)


def load_prepared_minutes(codes, start=modea.DEFAULT_START, end=modea.DEFAULT_END,
                          *, workers=16, cache_dir=None, status=None):
    """Prefer the Mode B mmap pack; otherwise parquet/lake then write the pack."""
    warm = warmup_start(start, days=10)
    wanted = set(codes)
    pack = modeb_pack_dir(warm, end, cache_dir)
    if _pack_covers(pack, wanted):
        if status is not None:
            status["cache"] = "pack"
            status["pack"] = "hit"
        return PreparedMinutes.from_mmap(pack, wanted)
    frames = load_monitor_bars(
        wanted, start, end, workers=workers, cache_dir=cache_dir, status=status
    )
    prepared = PreparedMinutes(frames)
    write_modeb_pack(prepared, pack, start=warm, end=end)
    if status is not None:
        status["pack"] = "write"
    return prepared


def minute_coverage(codes, bars, *, start=modea.DEFAULT_START, end=modea.DEFAULT_END):
    """Count unique requested codes with session minutes inside the run window."""
    wanted = set(codes)
    found = set()
    if isinstance(bars, PreparedMinutes):
        for code in wanted:
            pk = bars.packed.get(code)
            if pk is not None and any(start <= ymd <= end for ymd in pk.slices):
                found.add(code)
    else:
        for code in wanted & bars.keys():
            df = session_minutes(bars[code])
            if not df.empty and df["ymd"].between(start, end).any():
                found.add(code)
    return {"requested_codes": len(wanted), "covered_codes": len(found),
            "missing_codes": sorted(wanted - found), "minute_lake_end": MINUTE_LAKE_END}


def session_minutes(df):
    """Return session rows with lake/cache hm in minutes since midnight, not HHMM."""
    if df.empty:
        return df
    hm = df["hm"]
    mask = hm.between(AM_OPEN, AM_CLOSE) | hm.between(PM_OPEN, PM_CLOSE)
    out = df.loc[mask].copy()
    out["ymd"] = out["ymd"].astype(str)
    return out.sort_values(["ymd", "hm"], kind="stable")


def assemble_instances(pool_dir, sessions, bars, *, tol=modea.DEFAULT_TOL, exdiv=None):
    """Mode A identity/filter contract with explicitly supplied none daily bars."""
    prepared = modea._PreparedBars(bars)
    for symbol in prepared:
        prepared.prev_maps[symbol] = _previous_refs(prepared, symbol, exdiv)
    return modea.assemble_instances(pool_dir, sessions, prepared, tol=tol)


def _previous_refs(daily, symbol, exdiv):
    """Map the prior raw daily close across intervening ex dates (including halts)."""
    closes = daily.closes(symbol)
    ordered = sorted(closes)
    events = (exdiv or {}).get(symbol, {})
    refs = {}
    for previous, current in zip(ordered, ordered[1:]):
        ref = closes[previous]
        for day, k in events.items():
            if previous < day <= current:
                ref *= k
        refs[current] = ref
    return refs


PACK_VERSION = 1


def modeb_pack_dir(start, end, cache_dir=None) -> Path:
    root = Path(cache_dir) if cache_dir is not None else CACHE_ROOT
    return root / f"modeb_pack_{start}_{end}"


def _slices_from_ymd(ymd):
    n = len(ymd)
    if n == 0:
        return {}
    change = np.empty(n, dtype=bool)
    change[0] = True
    change[1:] = ymd[1:] != ymd[:-1]
    starts = np.flatnonzero(change)
    stops = np.append(starts[1:], n)
    return {f"{int(ymd[i]):08d}": (int(i), int(j)) for i, j in zip(starts, stops)}


def _pack_covers(pack_dir: Path, codes) -> bool:
    meta_path = Path(pack_dir) / "meta.json"
    if not meta_path.is_file():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if meta.get("version") != PACK_VERSION:
        return False
    have = meta.get("symbols") or {}
    return all(code in have for code in codes)


class _Packed:
    """Per-symbol session arrays. ``slices[ymd] = (start, end)`` into the arrays."""

    __slots__ = ("hm", "open", "close", "ymd", "slices")

    def __init__(self, hm, open_, close, ymd, slices):
        self.hm = hm
        self.open = open_
        self.close = close
        self.ymd = ymd
        self.slices = slices


class PreparedMinutes:
    """Run-local numpy minutes. Tuple ``days`` stays lazy for the ref scanner."""

    def __init__(self, bars):
        self.packed = {}
        self._days = None
        self._mmkeep = ()
        for symbol, frame in bars.items():
            frame = session_minutes(frame)
            if frame.empty:
                self.packed[symbol] = None
                continue
            if "open" not in frame.columns:
                frame = frame.copy()
                frame["open"] = frame["close"]
            ymd = frame["ymd"].to_numpy().astype("U8").astype(np.int32)
            self.packed[symbol] = _Packed(
                frame["hm"].to_numpy(dtype=np.int32, copy=False),
                frame["open"].to_numpy(dtype=np.float64, copy=False),
                frame["close"].to_numpy(dtype=np.float64, copy=False),
                ymd,
                _slices_from_ymd(ymd),
            )

    @classmethod
    def from_mmap(cls, pack_dir, codes=None):
        root = Path(pack_dir)
        meta = json.loads((root / "meta.json").read_text(encoding="utf-8"))
        n = int(meta["n_rows"])
        keep = (
            np.memmap(root / "hm.i32", dtype=np.int32, mode="r", shape=(n,)),
            np.memmap(root / "open.f64", dtype=np.float64, mode="r", shape=(n,)),
            np.memmap(root / "close.f64", dtype=np.float64, mode="r", shape=(n,)),
            np.memmap(root / "ymd.i32", dtype=np.int32, mode="r", shape=(n,)),
        )
        hm, opn, close, ymd = keep
        obj = cls.__new__(cls)
        obj.packed = {}
        obj._days = None
        obj._mmkeep = keep
        want = meta["symbols"] if codes is None else {c: meta["symbols"][c] for c in codes}
        for symbol, (s, e) in want.items():
            if s == e:
                obj.packed[symbol] = None
                continue
            y = ymd[s:e]
            obj.packed[symbol] = _Packed(hm[s:e], opn[s:e], close[s:e], y, _slices_from_ymd(y))
        return obj

    @property
    def days(self):
        if self._days is None:
            self._days = {}
            for symbol, pk in self.packed.items():
                if pk is None:
                    self._days[symbol] = {}
                    continue
                self._days[symbol] = {
                    ymd: list(
                        zip(
                            pk.hm[s:e].tolist(),
                            pk.open[s:e].tolist(),
                            pk.open[s:e].tolist(),
                            pk.close[s:e].tolist(),
                            pk.close[s:e].tolist(),
                        )
                    )
                    for ymd, (s, e) in pk.slices.items()
                }
        return self._days

    def last_close(self, symbol, ymd):
        pk = self.packed.get(symbol)
        if pk is None:
            return None
        sl = pk.slices.get(ymd)
        if sl is None:
            return None
        return float(pk.close[sl[1] - 1])


def write_modeb_pack(minutes: PreparedMinutes, pack_dir, *, start, end):
    """Sidecar mmap pack: session-filtered hm/open/close/ymd. Not the parquet cache."""
    root = Path(pack_dir)
    tmp = root.with_name(root.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    symbols = sorted(minutes.packed)
    offsets = {}
    chunks = []
    cursor = 0
    for symbol in symbols:
        pk = minutes.packed[symbol]
        if pk is None:
            offsets[symbol] = [cursor, cursor]
            continue
        n = int(pk.hm.size)
        offsets[symbol] = [cursor, cursor + n]
        chunks.append(pk)
        cursor += n
    n_rows = cursor
    files = (
        ("hm.i32", np.int32, "hm"),
        ("open.f64", np.float64, "open"),
        ("close.f64", np.float64, "close"),
        ("ymd.i32", np.int32, "ymd"),
    )
    for name, dtype, attr in files:
        mm = np.memmap(tmp / name, dtype=dtype, mode="w+", shape=(n_rows,))
        pos = 0
        for pk in chunks:
            arr = np.asarray(getattr(pk, attr), dtype=dtype)
            mm[pos:pos + arr.size] = arr
            pos += arr.size
        mm.flush()
        del mm
    meta = {
        "version": PACK_VERSION,
        "start": start,
        "end": end,
        "n_rows": n_rows,
        "symbols": offsets,
        "session_filtered": True,
        "columns": ["hm", "open", "close", "ymd"],
    }
    (tmp / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    if root.exists():
        shutil.rmtree(root)
    tmp.rename(root)
    return root

    @property
    def days(self):
        if self._days is None:
            self._days = {}
            for symbol, pk in self.packed.items():
                if pk is None:
                    self._days[symbol] = {}
                    continue
                self._days[symbol] = {
                    ymd: list(
                        zip(
                            pk.hm[s:e].tolist(),
                            pk.open[s:e].tolist(),
                            pk.open[s:e].tolist(),
                            pk.close[s:e].tolist(),
                            pk.close[s:e].tolist(),
                        )
                    )
                    for ymd, (s, e) in pk.slices.items()
                }
        return self._days

    def last_close(self, symbol, ymd):
        pk = self.packed.get(symbol)
        if pk is None:
            return None
        sl = pk.slices.get(ymd)
        if sl is None:
            return None
        return float(pk.close[sl[1] - 1])


def _prepare_minutes(bars):
    return bars if isinstance(bars, PreparedMinutes) else PreparedMinutes(bars)


@dataclass(frozen=True)
class ExitResult(modea.ExitResult):
    shares: float
    sell_hm: int | None = None


def _result(inst, ymd, hm, price, shares, held, reason, *, trade):
    buy_cost = modea._lot_shares(inst.buy_price) * inst.buy_price * (1 + modea.COMMISSION)
    proceeds = shares * price * (1 - modea.COMMISSION if trade else 1)
    pnl = proceeds - buy_cost
    return ExitResult(ymd, price, reason, pnl / buy_cost, pnl, shares, held, trade, hm)


def _validate_spec(spec):
    if spec.rule not in (0, 1, 2, 3, 4, 5, 6):
        raise ValueError(f"unknown rule {spec.rule}")
    if spec.rule and (spec.n is None or spec.n < 1):
        raise ValueError("N must be positive")
    if spec.rule == 3 and spec.y is None:
        raise ValueError("trailing requires Y")
    if spec.rule in (4, 5) and spec.y is None:
        raise ValueError("livermore requires stop Y")
    if spec.rule == 6 and spec.x is None:
        raise ValueError("sse overlay requires take-profit X")


def _block_ymd(index_block):
    """Map a v8 ``block_new`` table to YYYYMMDD; missing sessions do not block."""
    if not index_block:
        return {}
    return {modea.date_to_ymd(as_date(key)): bool(flag) for key, flag in index_block.items()}


def load_sse_ma10_block_ymd(start, end, *, root=None):
    """Load the locked SSE gate. Prior closes only; same table for every name."""
    from backtest.research.csv_minute_backtest_v7 import load_index_daily

    closes = load_index_daily(modea.ymd_to_date(start), modea.ymd_to_date(end), root=root)
    return _block_ymd(s8.build_sse_ma10_block_new(closes))


@dataclass
class _Path:
    ymd: np.ndarray
    hm: np.ndarray
    open: np.ndarray
    close: np.ndarray
    cost: np.ndarray
    shares: np.ndarray
    held: np.ndarray
    prev: np.ndarray
    is_last: np.ndarray
    day_id: np.ndarray
    mark_day: str
    mark_hm: int | None
    mark_price: float
    mark_held: int
    mark_shares: float


_EMPTY = np.array((), dtype=np.float64)


def _instance_path(inst, minutes, sessions, prev_by, *, end, exdiv):
    """One T+1..end path: shared by every spec on this instance."""
    buy_i = modea._session_index(sessions, inst.list_date)
    cost = mark_price = float(inst.buy_price)
    shares = float(modea._lot_shares(cost))
    mark_day, mark_hm, mark_held = inst.list_date, None, 0
    pk = minutes.packed.get(inst.symbol)
    events = (exdiv or {}).get(inst.symbol, {})
    chunks = []
    day_no = 0
    for i in range(buy_i + 1, len(sessions)):
        ymd = sessions[i]
        if ymd > end:
            break
        k = events.get(ymd, 1.0)
        cost *= k
        shares /= k
        mark_price *= k
        sl = None if pk is None else pk.slices.get(ymd)
        if sl is None:
            continue
        s, e = sl
        n = e - s
        last = np.zeros(n, dtype=bool)
        last[-1] = True
        prev = float(prev_by[ymd]) if prev_by.get(ymd) is not None else 0.0
        chunks.append((
            np.full(n, ymd, dtype=object),
            pk.hm[s:e],
            pk.open[s:e],
            pk.close[s:e],
            np.full(n, cost, dtype=np.float64),
            np.full(n, shares, dtype=np.float64),
            np.full(n, i - buy_i, dtype=np.int32),
            np.full(n, prev, dtype=np.float64),
            last,
            np.full(n, day_no, dtype=np.int32),
        ))
        mark_day, mark_hm, mark_price, mark_held = ymd, int(pk.hm[e - 1]), float(pk.close[e - 1]), i - buy_i
        day_no += 1
    if not chunks:
        return _Path(
            np.array((), dtype=object), np.array((), dtype=np.int32),
            _EMPTY, _EMPTY, _EMPTY, _EMPTY,
            np.array((), dtype=np.int32), _EMPTY,
            np.array((), dtype=bool), np.array((), dtype=np.int32),
            mark_day, mark_hm, mark_price, mark_held, shares,
        )
    cols = [np.concatenate([c[j] for c in chunks]) for j in range(10)]
    return _Path(*cols, mark_day, mark_hm, mark_price, mark_held, shares)


def _ld_mask(price, prev, lp, tol):
    if lp is None:
        return np.zeros(price.shape, dtype=bool)
    safe = np.where(prev > 0, prev, 1.0)
    return (prev > 0) & ((price / safe - 1.0) <= -(lp - tol))


def _close_peak(path):
    """Running peak from minute close after the same daily k as cost (Q39)."""
    scale_rel = path.cost / path.cost[0]
    acc = np.maximum.accumulate(path.close / scale_rel)
    return scale_rel * np.maximum(path.cost[0], acc)


def _v8_band_line(cost, peak):
    line = np.full(cost.shape, np.inf)
    m2 = (peak >= cost * (1.0 + s8.BAND_ARMS[0])) & (peak < cost * (1.0 + s8.BAND_ARMS[1]))
    m3 = (peak >= cost * (1.0 + s8.BAND_ARMS[1])) & (peak < cost * (1.0 + s8.BAND_ARMS[2]))
    m4 = (peak >= cost * (1.0 + s8.BAND_ARMS[2])) & (peak < cost * (1.0 + s8.BAND_ARMS[3]))
    m5 = peak >= cost * (1.0 + s8.BAND_ARMS[3])
    line[m2] = cost[m2] * s8.BAND2_ABS_MULT
    line[m3] = np.maximum(
        cost[m3] * s8.BAND3_GLOBAL_MULT,
        cost[m3] + s8.BAND3_KEEP * (peak[m3] - cost[m3]),
    )
    line[m4] = cost[m4] + s8.BAND4_KEEP * (peak[m4] - cost[m4])
    line[m5] = cost[m5] + s8.BAND5_KEEP * (peak[m5] - cost[m5])
    return line


_REASON = (
    "", "stop_loss", "take_profit", "trailing", "n_expire",
    "force_sell:stale", "trail:band", "force_sell:sse_ma10",
)


def _first_hit(path, spec, *, lp, tol, index_block=None):
    n = path.close.size
    if n == 0:
        return None
    sl_on = spec.rule in (2, 4, 5, 6) and spec.y is not None
    tp_on = spec.rule in (2, 4, 6) and spec.x is not None
    trail_on = spec.rule == 3
    live_on = spec.rule in (4, 5)
    bands_on = spec.rule == 4 and spec.x is None
    expire_on = spec.rule in (1, 2, 3, 6)
    index_on = spec.rule == 6
    ev = np.zeros(n, dtype=np.int8)
    fill = path.close.copy()
    peak = None
    if trail_on or live_on:
        peak = _close_peak(path)
    if expire_on:
        ev[(path.held >= spec.n) & path.is_last] = 4
    if trail_on:
        ev[path.close < peak * (1.0 - spec.y / 100.0)] = 3
        fill[ev == 3] = path.close[ev == 3]
    if live_on:
        stale = (path.held >= spec.n) & (peak < path.cost * (1.0 + s8.BAND_ARMS[0]))
        ev[stale] = 5
        fill[stale] = path.close[stale]
        if bands_on:
            line = _v8_band_line(path.cost, peak)
            band = (
                (path.close >= path.cost)
                & (peak > path.cost * s8.BAND_TRAIL_MIN_MULT)
                & (path.close <= line)
            )
            ev[band] = 6
            fill[band] = path.close[band]
    if tp_on:
        hit = path.close >= path.cost * (1.0 + spec.x / 100.0)
        ev[hit] = 2
        fill[hit] = path.close[hit]
    if sl_on:
        hit = path.close <= path.cost * (1.0 - spec.y / 100.0)
        ev[hit] = 1
        fill[hit] = path.close[hit]
    if index_on and index_block:
        blocked = np.fromiter(
            (bool(index_block.get(str(ymd), False)) for ymd in path.ymd),
            dtype=bool, count=n,
        )
        ev[blocked] = 7
        fill[blocked] = path.open[blocked]
    if tp_on:
        hit = path.open >= path.cost * (1.0 + spec.x / 100.0)
        ev[hit] = 2
        fill[hit] = path.open[hit]
    if sl_on:
        hit = path.open <= path.cost * (1.0 - spec.y / 100.0)
        ev[hit] = 1
        fill[hit] = path.open[hit]
    open_ld = _ld_mask(path.open, path.prev, lp, tol)
    fill_ld = _ld_mask(fill, path.prev, lp, tol)
    blocker = open_ld | ((ev > 0) & fill_ld)
    prev_cum = np.empty(n, dtype=np.int32)
    prev_cum[0] = 0
    if n > 1:
        prev_cum[1:] = np.cumsum(blocker.astype(np.int32))[:-1]
    starts = np.flatnonzero(np.concatenate(([True], path.day_id[1:] != path.day_id[:-1])))
    already = prev_cum > prev_cum[starts[path.day_id]]
    sell = (ev > 0) & ~open_ld & ~fill_ld & ~already
    if not sell.any():
        return None
    i = int(np.flatnonzero(sell)[0])
    code = int(ev[i])
    if code == 6:
        reason = s8.take_profit_reason(
            float(path.close[i]), float(path.cost[i]), float(peak[i]), int(path.held[i])
        ) or "trail:band"
    else:
        reason = _REASON[code]
    return i, reason, float(fill[i])


def _exit_from_path(inst, spec, path, *, tol, lp=None, index_block=None):
    if lp is None:
        lp = limit_pct(inst.symbol, inst.name)
    hit = _first_hit(path, spec, lp=lp, tol=tol, index_block=index_block)
    if hit is None:
        return _result(
            inst, path.mark_day, path.mark_hm, path.mark_price, path.mark_shares,
            path.mark_held, "mark_end", trade=False,
        )
    i, reason, fill = hit
    return _result(
        inst, str(path.ymd[i]), int(path.hm[i]), fill, float(path.shares[i]),
        int(path.held[i]), reason, trade=True,
    )


def _oracle_from_path(inst, path, *, tol, lp=None):
    n = path.close.size
    if n == 0:
        return None
    if lp is None:
        lp = limit_pct(inst.symbol, inst.name)
    buy_cost = modea._lot_shares(inst.buy_price) * inst.buy_price * (1 + modea.COMMISSION)
    pnl = path.shares * path.close * (1 - modea.COMMISSION) - buy_cost
    pnl = np.where(_ld_mask(path.close, path.prev, lp, tol), -np.inf, pnl)
    i = int(np.argmax(pnl))
    if not np.isfinite(pnl[i]):
        return None
    return _result(
        inst, str(path.ymd[i]), int(path.hm[i]), float(path.close[i]),
        float(path.shares[i]), int(path.held[i]), "oracle", trade=True,
    )


def evaluate_exit_modeb(inst, spec, daily_bars, minute_bars, sessions, *,
                        end=modea.DEFAULT_END, tol=modea.DEFAULT_TOL, exdiv=None,
                        impl="fast", index_block=None):
    """Open-gap then close triggers and fills; high/low never fire.

    Aligns with the minute strategy-8 book: gap-through at open, otherwise the
    minute close. N counts market sessions. A blocked fill prevents all further
    sells that day (Q7). Buy-day minutes never affect triggers or the peak.
    ``impl="ref"`` keeps the original day/minute Python loop for parity tests.
    """
    if not inst.opened:
        raise ValueError("evaluate_exit_modeb requires an opened instance")
    _validate_spec(spec)
    daily = modea._prepare_bars(daily_bars)
    minutes = _prepare_minutes(minute_bars)
    prev_by = _previous_refs(daily, inst.symbol, exdiv) if inst.symbol in daily else {}
    block = _block_ymd(index_block)
    if impl == "ref":
        return _evaluate_exit_modeb_ref(
            inst, spec, minutes, sessions, prev_by, end=end, tol=tol, exdiv=exdiv,
            index_block=block,
        )
    path = _instance_path(inst, minutes, sessions, prev_by, end=end, exdiv=exdiv)
    return _exit_from_path(inst, spec, path, tol=tol, index_block=block)


def _evaluate_exit_modeb_ref(inst, spec, minutes, sessions, prev_by, *, end, tol, exdiv,
                             index_block=None):
    """Scalar reference: same book as the numpy first-hit scanner."""
    days = minutes.days.get(inst.symbol, {})
    buy_i = modea._session_index(sessions, inst.list_date)
    cost = peak = mark_price = float(inst.buy_price)
    shares = float(modea._lot_shares(cost))
    mark_day, mark_hm, mark_held = inst.list_date, None, 0
    sl_on = spec.rule in (2, 4, 5, 6) and spec.y is not None
    tp_on = spec.rule in (2, 4, 6) and spec.x is not None
    block = index_block or {}
    for i in range(buy_i + 1, len(sessions)):
        ymd = sessions[i]
        if ymd > end:
            break
        k = (exdiv or {}).get(inst.symbol, {}).get(ymd, 1.0)
        cost *= k
        peak *= k
        shares /= k
        mark_price *= k
        sl_line = cost * (1 - spec.y / 100) if sl_on else None
        tp_line = cost * (1 + spec.x / 100) if tp_on else None
        rows = days.get(ymd, [])
        blocked = False
        prev = prev_by.get(ymd)
        for j, (hm, opn, _high, _low, close) in enumerate(rows):
            mark_day, mark_hm, mark_price, mark_held = ymd, int(hm), close, i - buy_i
            peak = max(peak, close)
            if blocked:
                continue
            if (
                prev is not None
                and prev > 0
                and modea._is_limit_down(opn, prev, inst.symbol, inst.name, tol=tol)
            ):
                blocked = True
                continue
            reason = None
            fill = close
            if sl_on and opn <= sl_line:
                reason, fill = "stop_loss", opn
            elif tp_on and opn >= tp_line:
                reason, fill = "take_profit", opn
            elif spec.rule == 6 and block.get(ymd):
                reason, fill = "force_sell:sse_ma10", opn
            elif sl_on and close <= sl_line:
                reason, fill = "stop_loss", close
            elif tp_on and close >= tp_line:
                reason, fill = "take_profit", close
            elif spec.rule == 3 and close < peak * (1 - spec.y / 100):
                reason = "trailing"
            elif spec.rule == 4 and spec.x is None:
                reason = s8.take_profit_reason(close, cost, peak, i - buy_i)
            elif spec.rule in (4, 5) and i - buy_i >= spec.n and s8.never_armed(cost, peak):
                reason = "force_sell:stale"
            if reason is None and spec.rule in (1, 2, 3, 6) and i - buy_i >= spec.n and j == len(rows) - 1:
                reason, fill = "n_expire", close
            if reason is None:
                continue
            if (
                prev is not None
                and prev > 0
                and modea._is_limit_down(fill, prev, inst.symbol, inst.name, tol=tol)
            ):
                blocked = True
                continue
            return _result(inst, ymd, int(hm), fill, shares, i - buy_i, reason, trade=True)
    return _result(inst, mark_day, mark_hm, mark_price, shares, mark_held, "mark_end", trade=False)


def evaluate_matrix(instances, specs, daily_bars, minute_bars, sessions, **kwargs):
    end = kwargs.get("end", modea.DEFAULT_END)
    tol = kwargs.get("tol", modea.DEFAULT_TOL)
    exdiv = kwargs.get("exdiv")
    block = _block_ymd(kwargs.get("index_block"))
    daily = modea._prepare_bars(daily_bars)
    minutes = _prepare_minutes(minute_bars)
    for spec in specs:
        _validate_spec(spec)
    prev_cache = {}
    out = {spec.label(): {} for spec in specs}
    for inst in modea.opened_instances(instances):
        if inst.symbol not in prev_cache:
            prev_cache[inst.symbol] = (
                _previous_refs(daily, inst.symbol, exdiv) if inst.symbol in daily else {}
            )
        path = _instance_path(
            inst, minutes, sessions, prev_cache[inst.symbol], end=end, exdiv=exdiv
        )
        key = modea.instance_key(inst)
        lp = limit_pct(inst.symbol, inst.name)
        for spec in specs:
            out[spec.label()][key] = _exit_from_path(
                inst, spec, path, tol=tol, lp=lp, index_block=block,
            )
    return out


# Slice D: all accounting stays local; only price-independent Mode A helpers reuse.
DEFAULT_OUT_DIR = Path("backtest_output/unified_exit_modeb")


def iter_grid():
    """P1=A narrow cells plus Livermore path arms and the SSE MA10 overlay."""
    cells = [s for s in modea.iter_grid(include_anchor_hold_end=True)
             if s.rule == 0 or (s.rule == 1 and s.n == 1)
             or (s.rule == 2 and s.x in (5, 7, 10)
                 and s.y in (5, 10, None) and s.n in (8, 10))]
    cells.extend((
        modea.StrategySpec(4, s8.STALE_DAYS, 10, 10),
        modea.StrategySpec(4, s8.STALE_DAYS, None, 10),
        modea.StrategySpec(5, s8.STALE_DAYS, None, 10),
        modea.StrategySpec(6, 10, 10, None),
    ))
    return cells


def oracle_exits(instances, daily_bars, minute_bars, sessions, *,
                 end=modea.DEFAULT_END, tol=modea.DEFAULT_TOL, exdiv=None):
    """Q38=A hindsight upper bound: exclude only each limit-down minute close.

    No earlier attempted/failed sale is simulated. Compare net proceeds across
    ex dates using the then-current shares, not unadjusted nominal prices.
    """
    daily = modea._prepare_bars(daily_bars)
    minutes = _prepare_minutes(minute_bars)
    out = {}
    for inst in modea.opened_instances(instances):
        prev_by = _previous_refs(daily, inst.symbol, exdiv) if inst.symbol in daily else {}
        path = _instance_path(inst, minutes, sessions, prev_by, end=end, exdiv=exdiv)
        lp = limit_pct(inst.symbol, inst.name)
        best = _oracle_from_path(inst, path, tol=tol, lp=lp)
        if best is None:
            best = _exit_from_path(inst, modea.StrategySpec(0, None), path, tol=tol, lp=lp)
        out[modea.instance_key(inst)] = best
    return out


def delisting_zero_exits(instances, exits, sessions, *, end=modea.DEFAULT_END):
    """Q33: preserve frozen positions; loss uses original, pre-exdiv buy cost."""
    from dataclasses import replace

    out = dict(exits)
    for inst in modea.opened_instances(instances):
        key = modea.instance_key(inst)
        er = exits[key]
        if er.reason == "mark_end" and er.sell_date < end:
            cost = modea._lot_shares(inst.buy_price) * inst.buy_price * (1 + modea.COMMISSION)
            out[key] = replace(er, sell_price=0., reason="mark_end_zero",
                               return_pct=-1., pnl=-cost)
    return out


def build_daily_equity(instances, exits, minute_bars, sessions, *,
                       cash_pool=modea.CASH_POOL, exdiv=None):
    """Sells before daily-close buys; local E-R6 shares and last minute marks.

    Missing minutes freeze the mark; ex events rescale both shares and that mark.
    Q33 changes only the final valuation, never historical equity or cash flows.
    """
    minutes = _prepare_minutes(minute_bars)
    buys = {}
    for inst in modea.opened_instances(instances):
        buys.setdefault(inst.list_date, []).append(inst)
    cash = float(cash_pool)
    held = {}
    rows = []
    peak_lots = 0
    for day in sessions:
        for key, (inst, shares, price) in list(held.items()):
            k = (exdiv or {}).get(inst.symbol, {}).get(day, 1.)
            shares /= k
            price *= k
            er = exits[key]
            if er.is_trade and er.sell_date == day:
                cash += er.shares * er.sell_price * (1 - modea.COMMISSION)
                del held[key]
                continue
            last = minutes.last_close(inst.symbol, day)
            if last is not None:
                price = last
            held[key] = (inst, shares, price)
        for inst in buys.get(day, []):
            shares = float(modea._lot_shares(inst.buy_price))
            cash -= shares * inst.buy_price * (1 + modea.COMMISSION)
            held[modea.instance_key(inst)] = (inst, shares, inst.buy_price)
        mtm = sum(shares * price for key, (_, shares, price) in held.items()
                  if not (day == sessions[-1] and exits[key].reason == "mark_end_zero"))
        peak_lots = max(peak_lots, len(held))
        rows.append(dict(date=day, equity=cash+mtm, cash=cash, lots=len(held), mtm=mtm))
    return rows, peak_lots, peak_lots * modea.LOT_NOTIONAL


def aggregate_strategy(label, instances, exits, minute_bars, sessions, *,
                       cash_pool=modea.CASH_POOL, exdiv=None):
    opened = modea.opened_instances(instances)
    results = [exits[modea.instance_key(i)] for i in opened]
    rets = [r.return_pct for r in results]
    pnls = [r.pnl for r in results]
    rows, lots, capital = build_daily_equity(opened, exits, minute_bars, sessions,
                                            cash_pool=cash_pool, exdiv=exdiv)
    total = ((rows[-1]["equity"] if rows else cash_pool) - cash_pool) / cash_pool
    n = len(results)
    return modea.StrategyMetrics(
        label, n, total, modea._annualize(total), modea._max_drawdown(rows),
        sum(r > 0 for r in rets)/n if n else 0., modea._profit_factor(pnls),
        sum(r.hold_sessions for r in results)/n if n else 0.,
        sum(rets)/n if n else 0., sorted(rets)[n//2] if n else 0.,
        sum(pnls), capital, lots)


def _validate_out_dir(out_dir):
    path = Path(out_dir).resolve()
    if any(part.lower() == "unified_exit_modea" for part in path.parts):
        raise ValueError("Mode B 输出不得写入 unified_exit_modea 目录")
    return path


def write_reports(out_dir, ranked, matrix, instances, anchors, robustness, *, meta=None):
    """Reuse Mode A report shape, adding the minute timestamp for fill auditing."""
    import csv

    out_dir = _validate_out_dir(out_dir)
    modea.write_reports(out_dir, ranked, matrix, instances, anchors, robustness, meta=meta)
    detail = out_dir / "instance_detail_top.csv"
    with detail.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = list(reader.fieldnames) + ["sell_hm"]
        rows = list(reader)
    for row in rows:
        row["sell_hm"] = matrix[row["strategy"]][row["instance_key"]].sell_hm
    with detail.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_modeb(
    pool_dir: Path,
    *,
    start: str = modea.DEFAULT_START,
    end: str = modea.DEFAULT_END,
    none_root=None,
    minute_bars=None,
    exdiv=None,
    cache_dir=None,
    sessions: Optional[Sequence[str]] = None,
    bars: Optional[Mapping[str, pd.DataFrame]] = None,
    tol: float = modea.DEFAULT_TOL,
    workers: int = 8,
    out_dir: Path = DEFAULT_OUT_DIR,
    cash_pool: float = modea.CASH_POOL,
    index_block=None,
    industry_map=None,
) -> dict:
    """Mode B narrow-grid pipeline: assemble → matrix → aggregate → reports."""
    out_dir = _validate_out_dir(out_dir)
    sess = modea.load_session_calendar(start, end, sessions=sessions)
    pool_rows = modea.iterate_pool_entries(Path(pool_dir), sess)
    codes = sorted({c for c, _n, _y in pool_rows})
    bar_map = load_none_bars(
        codes, start, end, none_root=none_root, workers=workers, bars=bars
    )
    bar_map = modea._prepare_bars(bar_map)
    if exdiv is None:
        exdiv = load_exdiv_ratios(codes, warmup_start(start, days=20), end)
    instances = assemble_instances(Path(pool_dir), sess, bar_map, tol=tol, exdiv=exdiv)
    load_status = {}
    if minute_bars is None:
        minute_bars = load_prepared_minutes(
            {i.symbol for i in modea.opened_instances(instances)}, start, end,
            workers=workers, cache_dir=cache_dir, status=load_status)
    coverage = minute_coverage({i.symbol for i in modea.opened_instances(instances)},
                               minute_bars, start=start, end=end)
    minutes = _prepare_minutes(minute_bars)
    specs = iter_grid()
    if index_block is None:
        index_block = load_sse_ma10_block_ymd(start, end)
    else:
        index_block = _block_ymd(index_block)
    matrix = evaluate_matrix(
        instances, specs, bar_map, minutes, sess,
        end=end, tol=tol, exdiv=exdiv, index_block=index_block,
    )

    # Oracle + delist sensitivity overlays
    matrix["oracle"] = oracle_exits(instances, bar_map, minutes, sess, end=end, tol=tol, exdiv=exdiv)
    hold_label = "anchor_hold_end"
    matrix["delist_zero"] = delisting_zero_exits(
        instances, matrix[hold_label], sess, end=end
    )

    metrics = [
        aggregate_strategy(lab, instances, exits, minutes, sess, cash_pool=cash_pool, exdiv=exdiv)
        for lab, exits in matrix.items()
        if lab not in ("oracle", "delist_zero", "anchor_hold_end")
    ]
    ranked = modea.rank_strategies(metrics)
    anchors = {
        "anchor_hold_end": aggregate_strategy(
            hold_label, instances, matrix[hold_label], minutes, sess, cash_pool=cash_pool, exdiv=exdiv
        ),
        "r1_n1": next(m for m in ranked if m.label == "r1_n1"),
        "oracle": aggregate_strategy(
            "oracle", instances, matrix["oracle"], minutes, sess, cash_pool=cash_pool, exdiv=exdiv
        ),
        "delist_zero": aggregate_strategy(
            "delist_zero",
            instances,
            matrix["delist_zero"],
            minutes,
            sess,
            cash_pool=cash_pool, exdiv=exdiv,
        ),
    }

    # Robustness ① half windows
    h1s, h1e, h2s, h2e = modea.half_window_split(start, end)
    robustness: dict = {"half_windows": {}, "board": {}, "month": {}, "plateau": []}
    for tag, s0, s1 in (("h1", h1s, h1e), ("h2", h2s, h2e)):
        sub = modea.filter_instances_by_list_date(instances, s0, s1)
        # Re-aggregate existing exits on the subset (same sell paths)
        sub_metrics = []
        # All narrow-grid labels (excl. anchors) so half-window top20 is not truncated
        # by full-window top subset (Q34①).
        half_labs = [
            lab
            for lab in matrix
            if lab not in ("oracle", "delist_zero", "anchor_hold_end")
        ]
        for lab in half_labs:
            sub_exits = {
                modea.instance_key(i): matrix[lab][modea.instance_key(i)]
                for i in modea.opened_instances(sub)
                if modea.instance_key(i) in matrix[lab]
            }
            if not sub_exits:
                continue
            # Equity curve on full sessions but only subset instances
            sub_metrics.append(
                aggregate_strategy(lab, sub, sub_exits, minutes, sess, cash_pool=cash_pool, exdiv=exdiv)
            )
        robustness["half_windows"][tag] = [
            modea.metrics_to_row(x) for x in modea.rank_strategies(sub_metrics)[:20]
        ]

    # top20 name consistency
    h1_labs = [r["label"] for r in robustness["half_windows"].get("h1", [])]
    h2_labs = [r["label"] for r in robustness["half_windows"].get("h2", [])]
    robustness["half_windows"]["top20_overlap"] = len(set(h1_labs) & set(h2_labs))

    # ② plateau
    robustness["plateau"] = modea.neighborhood_plateau_flags(ranked, top_n=20)

    # ③ board / month on best label
    if ranked:
        best = ranked[0].label
        robustness["board"] = modea.stratify_mean_returns(instances, matrix[best], by="board")
        robustness["month"] = modea.stratify_mean_returns(instances, matrix[best], by="month")
        if industry_map is not None:
            robustness["industry"] = modea.stratify_mean_returns(
                instances, matrix[best], by="industry", industry_map=industry_map
            )

    # ④ next-open buy sensitivity (rebuild matrix for top specs + r1_n1 only — cost control)
    sens_inst = modea.next_open_buy_instances(instances, bar_map, sess)
    sens_specs = [s for s in specs if s.label() in {m.label for m in ranked[:5]} or s.label() == "r1_n1"]
    if not sens_specs:
        sens_specs = [modea.StrategySpec(1, 1)]
    sens_matrix = evaluate_matrix(
        sens_inst, sens_specs, bar_map, minutes, sess,
        end=end, tol=tol, exdiv=exdiv, index_block=index_block,
    )
    robustness["next_open_buy"] = [
        modea.metrics_to_row(
            aggregate_strategy(lab, sens_inst, ex, minutes, sess, cash_pool=cash_pool, exdiv=exdiv)
        )
        for lab, ex in sens_matrix.items()
    ]

    write_reports(
        out_dir,
        ranked,
        matrix,
        instances,
        anchors,
        robustness,
        meta={"mode": "B", "price_domain": "none daily entry / minute open-gap then close trigger and fill",
              "scan": "numpy first-hit; path shared across specs",
              "pack": load_status.get("pack"), "minute_cache": load_status.get("cache"),
              "grid": "P1=A narrow (18 r2 + N=1) + livermore L1/L2/L3 + sse_ma10 overlay",
              "index_gate": "v8 SSE 000001.SH MA10 two-below, next session, all names",
              "oracle": "Q38=A 分钟可成交 close 事后上界；仅排除跌停分钟；不模拟更早失败卖出",
              "start": start, "end": end, "cash_pool": cash_pool, "tol": tol,
              "minute_coverage": coverage, "exdiv": "cost/peak *= k; shares /= k; no cash dividend"},
    )
    return {
        "ranked": ranked,
        "anchors": anchors,
        "robustness": robustness,
        "instances": instances,
        "matrix": matrix,
        "sessions": sess,
    }



def main(argv=None):
    import argparse
    import json

    ap = argparse.ArgumentParser(description="统一卖出规则网格 · 模式 B（不复权分钟；默认 P1=A 窄网格；11 亿现金池）")
    ap.add_argument("--start", default=modea.DEFAULT_START, help="起始日期 YYYYMMDD")
    ap.add_argument("--end", default=modea.DEFAULT_END, help="结束日期 YYYYMMDD")
    ap.add_argument("--pool-dir", type=Path, default=Path("stock_pool"), help="名单目录")
    ap.add_argument("--none-root", type=Path, help="不复权日线目录；默认使用湖路径解析器")
    ap.add_argument("--cache-dir", type=Path, help="分钟缓存目录；沿用 warmup 超集缓存")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Mode B 独立报告目录")
    ap.add_argument("--tol", type=float, default=modea.DEFAULT_TOL, help="涨跌停容差")
    ap.add_argument("--workers", type=int, default=8, help="读取线程数")
    ap.add_argument(
        "--industry",
        action="store_true",
        help="按申万一级分层稳健性；湖表缺失则报错",
    )
    args = ap.parse_args(argv)
    try:
        _validate_out_dir(args.out_dir)
    except ValueError as exc:
        ap.error(str(exc))
    kwargs = vars(args)
    if kwargs.pop("industry"):
        from oskh_data.industry_sw_l1 import load_industry_map

        kwargs["industry_map"] = load_industry_map()
    result = run_modeb(**kwargs)
    print(json.dumps({"mode": "B", "n_opened": len(modea.opened_instances(result["instances"])),
                      "n_strategies": len(result["ranked"]), "out_dir": str(args.out_dir)},
                     ensure_ascii=False))
    return 0
