# -*- coding: utf-8 -*-
"""CSV daily bar loader + period-env hygiene for both engines.

三职责：日线湖装载（``load_daily_bars`` / ``_read_one_daily``）、warmup 起点、
以及 ``warn_stale_period_env`` 对残留 ``OSKH_PERIOD_*`` 的告警。本模块不 import
任一引擎文件；常量 ``WARMUP_DAYS`` 等来自 ``csv_common``。
"""

from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from backtest.research.bar_store import mem_drop, mem_get, mem_key, mem_put
from backtest.research.csv_common import WARMUP_DAYS, _progress
from backtest.research.market_layer import utc_ms_range
from common.infra.data_root import resolve_period_root
from oskh_data.symbol_format import to_partition_key

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Leftover fine-grained overrides. OSKH_SOURCE_PARQUET_ROOT is the one-key
# product env (lesson 58) and is not stale by itself.
_PERIOD_ENV_KEYS = (
    "OSKH_PERIOD_1D_ROOT",
    "OSKH_PERIOD_1M_ROOT",
    "OSKH_INDEX_DAILY_ROOT",
    "OSKH_ETF_DAILY_ROOT",
)


def warmup_start(start: str, days: int = WARMUP_DAYS) -> str:
    return (pd.Timestamp(start) - pd.Timedelta(days=int(days))).strftime("%Y%m%d")


def warn_stale_period_env() -> None:
    hit = [k for k in _PERIOD_ENV_KEYS if os.environ.get(k)]
    if hit:
        print(
            f"[warn] {', '.join(hit)} is set; leftover PERIOD_* may ignore "
            f".authority and OSKH_SOURCE_PARQUET_ROOT (lesson 58)",
            flush=True,
        )
    source = str(os.environ.get("OSKH_SOURCE_PARQUET_ROOT") or "").strip()
    period = str(os.environ.get("OSKH_PERIOD_1D_ROOT") or "").strip()
    if source and period:
        expected = (Path(source) / "stock" / "period=1d").resolve()
        if Path(period).resolve() != expected:
            print(
                f"[warn] CONFLICT OSKH_PERIOD_1D_ROOT={period} != {expected} "
                f"from SOURCE (lesson 58)",
                flush=True,
            )


class DailyBarReadError(RuntimeError):
    """An existing daily partition could not be read or converted."""

    def __init__(self, code: str, path: Path) -> None:
        self.code = code
        self.path = path
        super().__init__(f"failed to read daily bars for {code}: {path}")


def _read_one_daily(code: str, root: Path, start: str, end: str) -> Optional[pd.DataFrame]:
    path = root / f"symbol={to_partition_key(code)}" / "data.parquet"
    if not path.is_file():
        return None
    t0, t1 = utc_ms_range(start, end)
    try:
        columns = ["time", "open", "high", "low", "close"]
        has_volume = "volume" in pq.read_schema(path).names
        table = pq.read_table(path, columns=columns + (["volume"] if has_volume else []))
        table = table.filter((pc.field("time") >= t0) & (pc.field("time") <= t1))
        if table.num_rows == 0:
            return None
        ms = table["time"].to_numpy()
        idx = pd.to_datetime(ms, unit="ms", utc=True).tz_localize(None).normalize()
        out = pd.DataFrame(
            {
                "open": table["open"].to_numpy(),
                "high": table["high"].to_numpy(),
                "low": table["low"].to_numpy(),
                "close": table["close"].to_numpy(),
                **({"_volume": table["volume"].to_numpy()} if has_volume else {}),
            },
            index=idx,
        ).astype(np.float64)
        out = out[~out.index.duplicated(keep="last")].sort_index()
        if has_volume:
            out = out.loc[out["_volume"] != 0].drop(columns="_volume")
        return out if not out.empty else None
    except Exception as exc:
        raise DailyBarReadError(code, path) from exc


_DIVIDEND_TYPES = ("none", "front", "back")


def _identity_hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _shallow_entry_stamp(path: Path):
    stat = path.stat()
    return [path.name, stat.st_mode, stat.st_size, stat.st_mtime_ns]


def _daily_cache_schema():
    return pa.schema(
        [
            ("symbol", pa.string()),
            ("time", pa.timestamp("ns")),
            ("open", pa.float64()),
            ("high", pa.float64()),
            ("low", pa.float64()),
            ("close", pa.float64()),
        ]
    )


def daily_cache_identity(
    start: str,
    end: str,
    *,
    dividend_type: str = "none",
    daily_root: Path | str | None = None,
) -> dict:
    kind = str(dividend_type or "none").strip().lower()
    base = Path(daily_root) if daily_root is not None else resolve_period_root("1d")
    root = (base / f"dividend_type={kind}").resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)
    source_snapshot = "shallow-v1:" + _identity_hash(
        [
            _shallow_entry_stamp(root),
            [_shallow_entry_stamp(p) for p in sorted(root.iterdir(), key=lambda p: p.name)],
        ]
    )
    schema = [[field.name, str(field.type), field.nullable] for field in _daily_cache_schema()]
    return {
        "identity_version": 1,
        "start": str(start),
        "end": str(end),
        "dividend_type": kind,
        "schema": _identity_hash(schema),
        "resolver_identity": str(root),
        "source_snapshot": source_snapshot,
    }


def daily_cache_path(
    start: str,
    end: str,
    cache_dir: Optional[Path] = None,
    *,
    identity: Optional[dict] = None,
    dividend_type: str = "none",
    daily_root: Path | str | None = None,
) -> Path:
    from backtest.research.ashare_bars import CACHE_ROOT

    root = Path(cache_dir) if cache_dir is not None else CACHE_ROOT
    if identity is None:
        identity = daily_cache_identity(
            start, end, dividend_type=dividend_type, daily_root=daily_root
        )
    digest = _identity_hash(identity)[:12]
    return root / (
        f"daily_{identity['dividend_type']}_{identity['start']}_{identity['end']}_{digest}.parquet"
    )


def _daily_identity_matches(path: Path, identity: dict) -> bool:
    try:
        metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(metadata, dict) and all(
        key in metadata and type(metadata[key]) is type(value) and metadata[key] == value
        for key, value in identity.items()
    )


def write_daily_cache(
    bars: dict,
    start: str,
    end: str,
    cache_dir: Optional[Path] = None,
    *,
    identity: Optional[dict] = None,
    dividend_type: str = "none",
    daily_root: Path | str | None = None,
) -> Path:
    if identity is None:
        identity = daily_cache_identity(
            start, end, dividend_type=dividend_type, daily_root=daily_root
        )
    path = daily_cache_path(start, end, cache_dir, identity=identity)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = _daily_cache_schema()
    tmp = path.with_suffix(".parquet.tmp")
    if tmp.exists():
        tmp.unlink()
    writer = None
    n_rows = 0
    try:
        for code, frame in bars.items():
            if frame is None or getattr(frame, "empty", True):
                continue
            chunk = frame.reset_index()
            time_col = chunk.columns[0]
            chunk = chunk.rename(columns={time_col: "time"})
            chunk.insert(0, "symbol", str(code))
            chunk["time"] = pd.to_datetime(chunk["time"]).astype("datetime64[ns]")
            table = pa.Table.from_pandas(
                chunk[["symbol", "time", "open", "high", "low", "close"]],
                schema=schema,
                preserve_index=False,
            )
            if writer is None:
                writer = pq.ParquetWriter(tmp, schema, compression="zstd")
            writer.write_table(table)
            n_rows += table.num_rows
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
                **identity,
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
    print(f"wrote daily cache {path} symbols={len(bars)} rows={n_rows}", flush=True)
    return path


def _normalize_daily_index(frame: pd.DataFrame) -> pd.DataFrame:
    """Cache frames are tz-naive ns; lake reads may still be ms."""
    out = frame.copy()
    out.index = pd.DatetimeIndex(out.index).as_unit("ns")
    out.index.name = None
    return out.astype(np.float64)


def read_daily_cache(path: Path, codes: Optional[set[str]] = None) -> dict[str, pd.DataFrame]:
    print(f"reading daily cache {path}", flush=True)
    table = pq.read_table(path)
    if codes is not None:
        table = table.filter(pc.field("symbol").isin(sorted(codes)))
    frame = table.to_pandas()
    out: dict[str, pd.DataFrame] = {}
    if frame.empty:
        return out
    for code, group in frame.groupby("symbol", sort=False):
        parsed = group.drop(columns=["symbol"])
        parsed.index = pd.DatetimeIndex(parsed.pop("time"))
        if not parsed.index.is_monotonic_increasing:
            parsed = parsed.sort_index()
        out[str(code)] = _normalize_daily_index(parsed)
    print(f"daily cache symbols={len(out)} rows={len(frame)}", flush=True)
    return out


def _load_daily_from_lake(
    codes: set[str] | list[str],
    root: Path,
    start: str,
    end: str,
    *,
    workers: int = 16,
) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    codes_list = sorted(codes)
    n = max(1, int(workers))
    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = {pool.submit(_read_one_daily, c, root, start, end): c for c in codes_list}
        done = 0
        total = len(futs)
        for fut in as_completed(futs):
            done += 1
            _progress(done, total, "daily lake")
            code = futs[fut]
            df = fut.result()
            if df is not None and not df.empty:
                out[code] = df
    return out


def load_daily_bars(
    codes: set[str],
    start: str,
    end: str,
    *,
    workers: int = 16,
    dividend_type: str = "none",
    daily_root: Path | str | None = None,
    use_cache: bool = False,
    rebuild_cache: bool = False,
    cache_dir: Optional[Path] = None,
    status: Optional[dict] = None,
) -> dict[str, pd.DataFrame]:
    """日线湖装载。默认 ``none``（不复权）；``front`` / ``back`` 读对应分区。

    ``daily_root`` 若给定，则替代 ``resolve_period_root("1d")``（其下仍要
    ``dividend_type=.../symbol=.../data.parquet``）。不写权威湖。
    文件缓存默认关，由 ``load_daily_ohlc`` 打开，避免测试湖写进仓库 cache。
    """
    kind = str(dividend_type or "none").strip().lower()
    if kind not in _DIVIDEND_TYPES:
        raise ValueError(f"dividend_type must be one of {_DIVIDEND_TYPES}, got {dividend_type!r}")
    base = Path(daily_root) if daily_root is not None else resolve_period_root("1d")
    root = base / f"dividend_type={kind}"
    want = {str(code) for code in codes}
    if not use_cache:
        if status is not None:
            status["cache"] = "off"
        return _load_daily_from_lake(want, root, start, end, workers=workers)

    identity = daily_cache_identity(start, end, dividend_type=kind, daily_root=daily_root)
    store_key = mem_key("daily", identity)
    if rebuild_cache:
        mem_drop(store_key)
    else:
        remembered = mem_get(store_key, want)
        if remembered is not None:
            if status is not None:
                status["cache"] = "mem"
            return remembered
    path = daily_cache_path(start, end, cache_dir, identity=identity)
    cached: dict[str, pd.DataFrame] = {}
    had_file = path.is_file()
    reusable = had_file and not rebuild_cache and _daily_identity_matches(path, identity)
    if reusable:
        print(f"daily cache hit {path}", flush=True)
        cached = read_daily_cache(path, want)
    missing = want - set(cached)
    if missing:
        print(f"daily lake load {len(missing)} codes ({len(cached)} cached)", flush=True)
        fresh = _load_daily_from_lake(missing, root, start, end, workers=workers)
        cached.update(fresh)
        if fresh:
            merged = cached
            if reusable:
                old = read_daily_cache(path, None)
                old.update(cached)
                merged = old
            write_daily_cache(merged, start, end, cache_dir, identity=identity)
    got = {code: _normalize_daily_index(cached[code]) for code in want if code in cached}
    mem_put(store_key, got)
    if status is not None:
        if rebuild_cache:
            status["cache"] = "rebuild"
        elif reusable and not missing:
            status["cache"] = "hit"
        elif reusable:
            status["cache"] = "partial"
        elif had_file:
            status["cache"] = "miss:identity"
        else:
            status["cache"] = "miss"
    return got
