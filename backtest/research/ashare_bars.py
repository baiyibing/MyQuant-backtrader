# -*- coding: utf-8 -*-
"""Market-bar loaders shared by daily and minute CSV engines.

Sources (do not import qlib):

- ``lake`` / ``lake_1m`` / ``lake_1d``: hive parquet under the path SSOT
- ``qlib_1min``: ``features/*.1min.bin`` + ``calendars/1min.txt``
- ``qlib_day``: ``features/*.day.bin`` + ``calendars/day.txt``

Fills and 昨收 are separate knobs. Official A-share limits keep ``daily_source=lake``
(none close). This module must not import a simulate loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional

from oskh_data.symbol_format import to_canonical_symbol, to_partition_key

MINUTE_SOURCES = ("lake", "qlib_1min")
DAILY_SOURCES = ("lake", "qlib_day")
DAILY_PRELOAD_DAYS = 40
MINUTE_LAKE_END = "20260909"
AM_OPEN, AM_CLOSE = 9 * 60 + 30, 11 * 60 + 30
PM_OPEN, PM_CLOSE = 13 * 60, 15 * 60
CACHE_ROOT = Path(__file__).resolve().parents[2] / "backtest_output" / "bar_cache"


@dataclass(frozen=True)
class SessionBars:
    minute: dict[str, object]
    daily_close: dict[str, dict[date, float]]
    minute_source: str
    daily_source: str


def _canonical_symbols(symbols: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(to_canonical_symbol(str(symbol)) for symbol in symbols))


def _as_ymd(value: date | str) -> str:
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) < 8:
        raise ValueError(f"cannot parse YYYYMMDD: {value!r}")
    return digits[:8]


def _as_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    ymd = _as_ymd(value)
    return date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]))


def _check_source(source: str, allowed: tuple[str, ...], kind: str) -> str:
    name = str(source or "").strip().lower()
    if name not in allowed:
        raise ValueError(f"{kind} source must be one of {allowed}, got {source!r}")
    return name


def _closes_from_ohlc(frames: Mapping[str, object]) -> dict[str, dict[date, float]]:
    out: dict[str, dict[date, float]] = {}
    for code, frame in frames.items():
        if frame is None or getattr(frame, "empty", True):
            continue
        closes: dict[date, float] = {}
        if hasattr(frame, "index") and "close" in getattr(frame, "columns", []):
            for stamp, close in zip(frame.index, frame["close"]):
                day = stamp.date() if hasattr(stamp, "date") else _as_date(stamp)
                closes[day] = float(close)
        out[to_canonical_symbol(str(code))] = closes
    return out


def load_daily_ohlc(
    symbols: Iterable[str],
    start: date | str,
    end: date | str,
    *,
    source: str = "lake",
    qlib_root: Path | str | None = None,
    dividend_type: str = "none",
    daily_root: Path | str | None = None,
    workers: int = 16,
) -> dict[str, object]:
    """Daily OHLC frames for the book engines (DatetimeIndex)."""
    kind = _check_source(source, DAILY_SOURCES, "daily")
    codes = set(_canonical_symbols(symbols))
    if not codes:
        return {}
    start_ymd, end_ymd = _as_ymd(start), _as_ymd(end)
    if kind == "qlib_day":
        if qlib_root is None:
            raise ValueError("qlib_day source requires qlib_root")
        from backtest.research.qlib_bin_daily import load_qlib_bin_daily_bars

        return load_qlib_bin_daily_bars(codes, start_ymd, end_ymd, qlib_root=qlib_root, workers=workers)
    from backtest.research.csv_daily_loader import load_daily_bars

    return load_daily_bars(
        codes,
        start_ymd,
        end_ymd,
        workers=workers,
        dividend_type=dividend_type,
        daily_root=daily_root,
    )


def load_daily_closes(
    symbols: Iterable[str],
    start: date | str,
    end: date | str,
    *,
    source: str = "lake",
    qlib_root: Path | str | None = None,
    dividend_type: str = "none",
    daily_root: Path | str | None = None,
    workers: int = 16,
    preload_days: int = DAILY_PRELOAD_DAYS,
) -> dict[str, dict[date, float]]:
    """Session 昨收 map. Lake none is the official-limit default."""
    load_start = _as_date(start) - timedelta(days=max(0, int(preload_days)))
    frames = load_daily_ohlc(
        symbols,
        load_start,
        end,
        source=source,
        qlib_root=qlib_root,
        dividend_type=dividend_type,
        daily_root=daily_root,
        workers=workers,
    )
    return _closes_from_ohlc(frames)


def _stamp_column(frame) -> str:
    for key in ("datetime", "timestamp", "date", "time"):
        if key in frame.columns:
            return key
    raise ValueError("parquet requires datetime/timestamp/date/time")


def _compact_minute_frame(frame, start: date, end: date):
    import pandas as pd

    stamp = frame[_stamp_column(frame)]
    if pd.api.types.is_numeric_dtype(stamp):
        ts = pd.to_datetime(stamp, unit="ms", utc=True)
    else:
        ts = pd.to_datetime(stamp, utc=True)
    close = frame["close"].to_numpy()
    out = pd.DataFrame(
        {
            "date": pd.Series(ts.dt.date, dtype="object"),
            "hm": (ts.dt.hour * 60 + ts.dt.minute).astype("int32"),
            "open": frame["open"].to_numpy() if "open" in frame.columns else close,
            "high": frame["high"].to_numpy() if "high" in frame.columns else close,
            "close": close,
        }
    )
    return out.loc[(out["date"] >= start) & (out["date"] <= end)].reset_index(drop=True)


def _read_lake_minute(symbol: str, start: date, end: date):
    import pandas as pd

    from backtest.research.market_layer import utc_ms_range
    from common.infra.data_root import resolve_period_root

    directory = resolve_period_root("1m") / "dividend_type=none" / f"symbol={to_partition_key(symbol)}"
    files = sorted(directory.glob("*.parquet"))
    if not files:
        return None
    try:
        import pyarrow.compute as pc
        import pyarrow.parquet as pq

        t0, t1 = utc_ms_range(start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        tables = []
        for path in files:
            table = pq.read_table(path, columns=["time", "open", "high", "close"])
            if "time" in table.column_names:
                table = table.filter((pc.field("time") >= t0) & (pc.field("time") <= t1))
            if table.num_rows:
                tables.append(table)
        if not tables:
            return None
        frame = pd.concat((t.to_pandas() for t in tables), ignore_index=True)
    except Exception:
        frame = pd.concat((pd.read_parquet(path) for path in files), ignore_index=True)
    compacted = _compact_minute_frame(frame, start, end)
    return None if compacted.empty else compacted


def _load_minute_compact(
    symbols: Iterable[str],
    start: date | str,
    end: date | str,
    *,
    source: str = "lake",
    qlib_root: Path | str | None = None,
    workers: int = 16,
) -> dict[str, object]:
    """Private compact source for qlib_1min and frozen lake comparisons."""
    kind = _check_source(source, MINUTE_SOURCES, "minute")
    codes = _canonical_symbols(symbols)
    if not codes:
        return {}
    first, last = _as_date(start), _as_date(end)
    if kind == "qlib_1min":
        if qlib_root is None:
            raise ValueError("qlib_1min source requires qlib_root")
        from backtest.research.qlib_bin_1min import load_qlib_bin_1min_bars

        return load_qlib_bin_1min_bars(codes, first, last, qlib_root=qlib_root, workers=workers, preload_days=0)

    from concurrent.futures import ThreadPoolExecutor, as_completed

    from backtest.research.csv_common import _progress

    out: dict[str, object] = {}
    n = max(1, int(workers))
    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = {pool.submit(_read_lake_minute, code, first, last): code for code in codes}
        done = 0
        total = len(futs)
        for fut in as_completed(futs):
            done += 1
            _progress(done, total, "lake 1m")
            code = futs[fut]
            try:
                frame = fut.result()
            except Exception:
                continue
            if frame is not None and not getattr(frame, "empty", True):
                out[code] = frame
    return out


def load_session_bars(
    symbols: Iterable[str],
    start: date | str,
    end: date | str,
    *,
    minute_source: str = "lake",
    daily_source: str = "lake",
    qlib_1min_root: Path | str | None = None,
    qlib_day_root: Path | str | None = None,
    dividend_type: str = "none",
    daily_root: Path | str | None = None,
    workers: int = 16,
) -> SessionBars:
    """Minute fills + daily 昨收; lake uses book frames, bin stays compact."""
    minute_kind = _check_source(minute_source, MINUTE_SOURCES, "minute")
    daily_kind = _check_source(daily_source, DAILY_SOURCES, "daily")
    codes = _canonical_symbols(symbols)
    if not codes:
        return SessionBars({}, {}, minute_kind, daily_kind)
    if minute_kind == "lake":
        # Pool windows must not read/overwrite the shared, window-only cache.
        minute = load_minute_ohlc(
            codes, _as_ymd(start), _as_ymd(end), workers=workers, use_cache=False
        )
    else:
        minute = _load_minute_compact(
            codes, start, end, source=minute_kind, qlib_root=qlib_1min_root, workers=workers
        )
    daily_close = load_daily_closes(
        codes,
        start,
        end,
        source=daily_kind,
        qlib_root=qlib_day_root,
        dividend_type=dividend_type,
        daily_root=daily_root,
        workers=workers,
    )
    return SessionBars(minute, daily_close, minute_kind, daily_kind)


def bars_from_pool(
    pool_days: Mapping[date, Iterable[str]],
    start: date | str,
    end: date | str,
    **kwargs,
) -> SessionBars:
    symbols = [symbol for values in pool_days.values() for symbol in values]
    if not symbols:
        minute_source = str(kwargs.get("minute_source") or "lake")
        daily_source = str(kwargs.get("daily_source") or "lake")
        return SessionBars({}, {}, minute_source, daily_source)
    return load_session_bars(symbols, start, end, **kwargs)


def _in_session(hm) -> object:
    import numpy as np

    arr = np.asarray(hm)
    return ((arr >= AM_OPEN) & (arr <= AM_CLOSE)) | ((arr >= PM_OPEN) & (arr <= PM_CLOSE))


def _session_index(idx):
    import pandas as pd

    stamps = pd.DatetimeIndex(idx)
    if stamps.tz is not None:
        stamps = stamps.tz_convert("UTC").tz_localize(None)
    return stamps


def annotate_session(frame):
    """Keep only A-share session minutes; add ``ymd`` / ``hm``."""
    out = frame.copy()
    idx = _session_index(out.index)
    out.index = idx
    out["ymd"] = idx.strftime("%Y%m%d")
    out["hm"] = idx.hour * 60 + idx.minute
    return out.loc[_in_session(out["hm"].to_numpy())]


def read_lake_minute_ohlc(code: str, root: Path, start: str, end: str):
    """Book-engine lake frame: DatetimeIndex + open/high/low/close/ymd/hm."""
    import numpy as np
    import pandas as pd
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    from backtest.research.market_layer import utc_ms_range

    path = Path(root) / f"symbol={to_partition_key(code)}" / "data.parquet"
    if not path.is_file():
        return None
    t0, t1 = utc_ms_range(start, end)
    try:
        columns = ["time", "open", "high", "low", "close"]
        has_volume = "volume" in pq.read_schema(path).names
        table = pq.read_table(path, columns=columns + (["volume"] if has_volume else []))
        table = table.filter((pc.field("time") >= t0) & (pc.field("time") <= t1))
    except Exception:
        return None
    if table.num_rows == 0:
        return None
    utc = pd.to_datetime(table["time"].to_numpy(), unit="ms", utc=True)
    hm = utc.hour * 60 + utc.minute
    keep = _in_session(hm.to_numpy())
    if not bool(keep.any()):
        return None
    utc = utc[keep]
    out = pd.DataFrame(
        {
            "open": table["open"].to_numpy()[keep],
            "high": table["high"].to_numpy()[keep],
            "low": table["low"].to_numpy()[keep],
            "close": table["close"].to_numpy()[keep],
            "ymd": utc.strftime("%Y%m%d"),
            "hm": hm.to_numpy()[keep],
            **({"_volume": table["volume"].to_numpy()[keep]} if has_volume else {}),
        },
        index=utc.tz_localize(None),
    ).astype({"open": np.float64, "high": np.float64, "low": np.float64, "close": np.float64, "hm": np.int64})
    out = out[~out.index.duplicated(keep="last")].sort_index()
    if has_volume:
        day_volume = out.groupby("ymd")["_volume"].transform("sum")
        out = out.loc[day_volume != 0].drop(columns="_volume")
    return out if not out.empty else None


def load_minute_from_lake(codes: set[str] | list[str], start: str, end: str, *, workers: int = 16, lake_root=None):
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from backtest.research.csv_common import _progress
    from common.infra.data_root import resolve_period_root

    root = Path(lake_root) if lake_root is not None else resolve_period_root("1m") / "dividend_type=none"
    out = {}
    wanted = sorted({to_canonical_symbol(str(code)) for code in codes})
    if not wanted:
        return out
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futs = {pool.submit(read_lake_minute_ohlc, code, root, start, end): code for code in wanted}
        done = 0
        total = len(futs)
        for fut in as_completed(futs):
            done += 1
            _progress(done, total, "minute lake")
            code = futs[fut]
            try:
                frame = fut.result()
            except Exception:
                continue
            if frame is not None and not frame.empty:
                out[code] = frame
    return out


def minute_cache_path(start: str, end: str, cache_dir: Optional[Path] = None) -> Path:
    root = Path(cache_dir) if cache_dir is not None else CACHE_ROOT
    return root / f"minute_none_{start}_{end}.parquet"


def _cache_schema():
    import pyarrow as pa

    return pa.schema(
        [
            ("symbol", pa.string()),
            ("time", pa.timestamp("ns")),
            ("open", pa.float64()),
            ("high", pa.float64()),
            ("low", pa.float64()),
            ("close", pa.float64()),
            ("ymd", pa.string()),
            ("hm", pa.int64()),
        ]
    )


def write_minute_cache(bars: dict, start: str, end: str, cache_dir: Optional[Path] = None) -> Path:
    import json

    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    from backtest.research.csv_common import _progress

    schema = _cache_schema()
    path = minute_cache_path(start, end, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    if tmp.exists():
        tmp.unlink()
    writer = None
    n_rows = 0
    n_sym = 0
    total_sym = sum(1 for df in bars.values() if df is not None and not getattr(df, "empty", True))
    try:
        for code, frame in bars.items():
            if frame is None or getattr(frame, "empty", True):
                continue
            chunk = frame.reset_index()
            time_col = chunk.columns[0]
            chunk = chunk.rename(columns={time_col: "time"})
            chunk.insert(0, "symbol", code)
            chunk["time"] = pd.to_datetime(chunk["time"])
            chunk["ymd"] = chunk["ymd"].astype(str)
            chunk["hm"] = chunk["hm"].astype(np.int64)
            table = pa.Table.from_pandas(
                chunk[["symbol", "time", "open", "high", "low", "close", "ymd", "hm"]],
                schema=schema,
                preserve_index=False,
            )
            if writer is None:
                writer = pq.ParquetWriter(tmp, schema, compression="zstd")
            writer.write_table(table)
            n_rows += table.num_rows
            n_sym += 1
            _progress(n_sym, total_sym, "minute cache write", every=400)
        if writer is not None:
            writer.close()
            writer = None
            tmp.replace(path)
        elif tmp.exists():
            tmp.unlink()
    finally:
        if writer is not None:
            writer.close()
            if tmp.exists():
                tmp.unlink()
    path.with_suffix(".json").write_text(
        json.dumps(
            {
                "start": start,
                "end": end,
                "n_symbols": len(bars),
                "n_rows": n_rows,
                "created_utc": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote minute cache {path} symbols={len(bars)} rows={n_rows}", flush=True)
    return path


def _frame_from_cache_group(group):
    import pandas as pd

    frame = group.drop(columns=["symbol"])
    frame.index = pd.DatetimeIndex(frame.pop("time"))
    frame["hm"] = frame["hm"].astype("int64", copy=False)
    if not frame.index.is_monotonic_increasing:
        frame = frame.sort_index()
    return frame


def read_minute_cache(path: Path, codes: Optional[set[str]] = None) -> dict:
    import pandas as pd
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    print(f"reading minute cache {path}", flush=True)
    parquet = pq.ParquetFile(path)
    want = set(codes) if codes else None
    out: dict = {}
    n_rows = 0
    n_rg = parquet.num_row_groups
    for i in range(n_rg):
        table = parquet.read_row_group(i)
        if table.num_rows == 0:
            continue
        uniq = pc.unique(table.column("symbol"))
        if len(uniq) == 1:
            code = uniq[0].as_py()
            if want is not None and code not in want:
                continue
            key = str(code)
            frame = table.to_pandas()
            n_rows += len(frame)
            parsed = _frame_from_cache_group(frame)
            out[key] = pd.concat([out[key], parsed]).sort_index() if key in out else parsed
        else:
            if want is not None:
                table = table.filter(pc.field("symbol").isin(sorted(want)))
                if table.num_rows == 0:
                    continue
            frame = table.to_pandas()
            n_rows += len(frame)
            for code, group in frame.groupby("symbol", sort=False):
                parsed = _frame_from_cache_group(group)
                key = str(code)
                out[key] = pd.concat([out[key], parsed]).sort_index() if key in out else parsed
        if (i + 1) == n_rg or (i + 1) % 400 == 0:
            print(f"minute cache rg {i + 1}/{n_rg} symbols={len(out)}", flush=True)
    print(f"minute cache rows={n_rows}", flush=True)
    return out


def load_minute_ohlc(
    codes: set[str] | list[str],
    start: str,
    end: str,
    *,
    workers: int = 16,
    use_cache: bool = True,
    rebuild_cache: bool = False,
    cache_dir: Optional[Path] = None,
    status: Optional[dict] = None,
    lake_root=None,
) -> dict:
    """Book 1–10 / Mode B frames. Cache lives here, not in the engine."""
    want = {to_canonical_symbol(str(code)) for code in codes}
    path = minute_cache_path(start, end, cache_dir)
    cached: dict = {}
    had_file = path.is_file()
    if use_cache and had_file and not rebuild_cache:
        print(f"minute cache hit {path}", flush=True)
        cached = read_minute_cache(path, want)
    missing = want - set(cached)
    if missing:
        print(f"minute lake load {len(missing)} codes ({len(cached)} cached)", flush=True)
        fresh = load_minute_from_lake(missing, start, end, workers=workers, lake_root=lake_root)
        cached.update(fresh)
        if use_cache and fresh:
            merged = cached
            if path.is_file() and not rebuild_cache:
                old = read_minute_cache(path, None)
                old.update(cached)
                merged = old
            write_minute_cache(merged, start, end, cache_dir)
    if status is not None:
        if not use_cache:
            status["cache"] = "off"
        elif rebuild_cache:
            status["cache"] = "rebuild"
        elif had_file and not missing:
            status["cache"] = "hit"
        elif had_file:
            status["cache"] = "partial"
        else:
            status["cache"] = "miss"
    return {code: cached[code] for code in want if code in cached}


def book_frames_from_compact(minute: Mapping[str, object]) -> dict:
    """Compact qlib_1min frames → book engine frames (DatetimeIndex + ymd/hm)."""
    import numpy as np
    import pandas as pd

    out: dict = {}
    for code, frame in minute.items():
        if frame is None or getattr(frame, "empty", True):
            continue
        dates = pd.to_datetime(frame["date"])
        hm = np.asarray(frame["hm"], dtype=np.int64)
        idx = dates + pd.to_timedelta(hm // 60, unit="h") + pd.to_timedelta(hm % 60, unit="m")
        close = np.asarray(frame["close"], dtype=np.float64)
        high = np.asarray(frame["high"], dtype=np.float64) if "high" in frame.columns else close
        open_ = np.asarray(frame["open"], dtype=np.float64) if "open" in frame.columns else close
        low = np.asarray(frame["low"], dtype=np.float64) if "low" in frame.columns else high
        out[str(code)] = pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "ymd": pd.DatetimeIndex(dates).strftime("%Y%m%d").to_numpy(),
                "hm": hm,
            },
            index=pd.DatetimeIndex(idx),
        )
    return out


load_minute_bars = load_minute_ohlc
_annotate = annotate_session
_read_one_minute = read_lake_minute_ohlc
_load_minute_from_lake = load_minute_from_lake
