#!/usr/bin/env python3
"""Scan 底量超顶量 and write contract day CSVs (strategy 9).

Filename = buy day T. Compute with bars ``date<=T`` only. Never writes
``stock_pool/``. Lake I/O is host-only; CI injects frames via
``scan_ohlcv`` / ``write_strategy9_pool``.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.bottom_vol_over_top import (  # noqa: E402
    FORWARD_HORIZONS,
    MIN_LISTED_BARS,
    evaluate_at,
    forward_close_returns,
    is_main_board_code,
    scan_ohlcv,
)
from backtest.research.csv_pool import (  # noqa: E402
    is_repo_stock_pool,
    validate_pool_dir,
)
from backtest.research.market_layer import utc_ms_range  # noqa: E402
from common.infra.data_root import resolve_period_root  # noqa: E402
from oskh_core.a_share_symbol_normalize import canonical_from_bare_code  # noqa: E402
from oskh_data.symbol_format import to_canonical_symbol, to_partition_key  # noqa: E402

SCAN_CALENDAR_SLACK_DAYS = 400


def default_out_dir(start: str, end: str) -> Path:
    return REPO_ROOT / "exports" / f"s9_bvot_{start}_{end}"


def _bare_code(canonical: str) -> str:
    return str(canonical).split(".", 1)[0]


def write_strategy9_pool(
    days: Mapping[str, Sequence[str]],
    out_dir: Path,
    *,
    repo: Path = REPO_ROOT,
) -> list[Path]:
    """Write non-empty days as headerless LF CSVs of bare six-digit codes."""
    out_root = Path(out_dir)
    if is_repo_stock_pool(out_root, repo=repo):
        raise SystemExit(f"refusing to write into stock_pool/: {out_root}")
    out_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for ymd in sorted(days):
        codes = [_bare_code(code) for code in days[ymd]]
        codes = [c for c in codes if c.isdigit() and len(c) == 6]
        # stable: already sorted canonical in scan_ohlcv; keep that order via bare
        if not codes:
            continue
        dest = out_root / f"{ymd}.csv"
        dest.write_text(
            "".join(f"{code}\n" for code in codes),
            encoding="utf-8",
            newline="\n",
        )
        written.append(dest)
    return written


def list_main_board_from_lake(root: Path) -> list[str]:
    out: list[str] = []
    for part in sorted(Path(root).glob("symbol=*")):
        if not (part / "data.parquet").is_file():
            continue
        code = to_canonical_symbol(part.name[len("symbol=") :])
        if is_main_board_code(code):
            out.append(code)
    return out


def read_one_daily_ohlcv(
    code: str, root: Path, start: str, end: str
) -> Optional[pd.DataFrame]:
    """Unadjusted daily OHLCV; drop ``volume==0``. Keeps volume for the signal."""
    path = Path(root) / f"symbol={to_partition_key(code)}" / "data.parquet"
    if not path.is_file():
        return None
    t0, t1 = utc_ms_range(start, end)
    try:
        names = pq.read_schema(path).names
        if "volume" not in names:
            return None
        table = pq.read_table(
            path, columns=["time", "open", "high", "low", "close", "volume"]
        )
        table = table.filter((pc.field("time") >= t0) & (pc.field("time") <= t1))
    except Exception:
        return None
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
            "volume": table["volume"].to_numpy(),
        },
        index=idx,
    ).astype(np.float64)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out.loc[out["volume"] != 0]
    return out if not out.empty else None


def load_daily_ohlcv(
    codes: Iterable[str],
    start: str,
    end: str,
    *,
    root: Optional[Path] = None,
    workers: int = 16,
) -> dict[str, pd.DataFrame]:
    lake = (
        Path(root)
        if root is not None
        else resolve_period_root("1d") / "dividend_type=none"
    )
    out: dict[str, pd.DataFrame] = {}
    codes_list = sorted(set(codes))
    n = max(1, int(workers))
    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = {
            pool.submit(read_one_daily_ohlcv, code, lake, start, end): code
            for code in codes_list
        }
        done = 0
        total = len(futs)
        for fut in as_completed(futs):
            done += 1
            if done == 1 or done == total or done % 200 == 0:
                print(f"s9 lake {done}/{total}", flush=True)
            code = futs[fut]
            try:
                frame = fut.result()
            except Exception:
                continue
            if frame is not None and not frame.empty:
                out[code] = frame
    return out


def warmup_start(start: str, days: int = SCAN_CALENDAR_SLACK_DAYS) -> str:
    return (pd.Timestamp(start) - pd.Timedelta(days=int(days))).strftime("%Y%m%d")


def event_study_rows(
    frames: Mapping[str, pd.DataFrame],
    start: str,
    end: str,
    *,
    names: Optional[Mapping[str, str]] = None,
) -> list[dict]:
    name_map = dict(names or {})
    rows: list[dict] = []
    for code, frame in frames.items():
        close = np.asarray(frame["close"].to_numpy(), dtype=np.float64)
        t0 = pd.Timestamp(start)
        t1 = pd.Timestamp(end)
        for ts in frame.index[(frame.index >= t0) & (frame.index <= t1)]:
            sig = evaluate_at(frame, ts, code=code, name=name_map.get(code, ""))
            if sig is None:
                continue
            loc = frame.index.get_loc(pd.Timestamp(ts).normalize())
            t = int(loc.stop - 1) if isinstance(loc, slice) else int(loc)
            fwd = forward_close_returns(close, t)
            row = {
                "date": sig.ymd,
                "code": _bare_code(code),
                "top_ago": sig.top_ago,
                "bottom_ago": sig.bottom_ago,
                "ratio": sig.ratio,
            }
            for h in FORWARD_HORIZONS:
                row[f"h{h}"] = fwd.get(h)
            rows.append(row)
    rows.sort(key=lambda item: (item["date"], item["code"]))
    return rows


def write_event_study(rows: Sequence[Mapping], dest: Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "date",
        "code",
        "top_ago",
        "bottom_ago",
        "ratio",
        *[f"h{h}" for h in FORWARD_HORIZONS],
    ]
    if not rows:
        dest.write_text(",".join(cols) + "\n", encoding="utf-8", newline="\n")
        return dest
    frame = pd.DataFrame(list(rows), columns=cols)
    frame.to_csv(dest, index=False, encoding="utf-8", lineterminator="\n")
    return dest


def _parse_codes(raw: Optional[str], path: Optional[Path]) -> Optional[list[str]]:
    codes: list[str] = []
    if raw:
        codes.extend(part.strip() for part in raw.split(",") if part.strip())
    if path is not None:
        text = Path(path).read_text(encoding="utf-8")
        codes.extend(line.strip() for line in text.splitlines() if line.strip())
    if not codes:
        return None
    out: list[str] = []
    seen: set[str] = set()
    for item in codes:
        digits = "".join(ch for ch in item if ch.isdigit())
        if len(digits) < 6:
            continue
        bare = digits[:6]
        canon = canonical_from_bare_code(bare)
        if canon and canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Strategy 9 pool exporter (bottom-vol-over-top); never stock_pool/"
    )
    ap.add_argument("--start", required=True, help="first buy-day filename YYYYMMDD")
    ap.add_argument("--end", required=True, help="last buy-day filename YYYYMMDD")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--codes", default=None, help="optional comma-separated bare codes")
    ap.add_argument("--universe-file", type=Path, default=None)
    ap.add_argument(
        "--event-study",
        action="store_true",
        help="also write event_study.csv (forward returns; not a buy input)",
    )
    args = ap.parse_args(argv if argv is not None else None)

    out_dir = (
        Path(args.out_dir)
        if args.out_dir is not None
        else default_out_dir(args.start, args.end)
    )
    if is_repo_stock_pool(out_dir):
        raise SystemExit(f"refusing to write into stock_pool/: {out_dir}")

    lake = resolve_period_root("1d") / "dividend_type=none"
    injected = _parse_codes(args.codes, args.universe_file)
    if injected is None:
        symbols = list_main_board_from_lake(lake)
    else:
        symbols = [c for c in injected if is_main_board_code(c)]
    if not symbols:
        raise SystemExit("no main-board symbols to scan")

    load_start = warmup_start(args.start)
    print(
        f"s9 scan {len(symbols)} codes {load_start}..{args.end} -> {out_dir}",
        flush=True,
    )
    frames = load_daily_ohlcv(
        symbols, load_start, args.end, root=lake, workers=args.workers
    )
    kept = {
        code: frame for code, frame in frames.items() if len(frame) >= MIN_LISTED_BARS
    }
    days = scan_ohlcv(kept, args.start, args.end)
    written = write_strategy9_pool(days, out_dir)
    failures = validate_pool_dir(out_dir)
    if failures:
        raise SystemExit("validate_pool_dir failed: " + "; ".join(failures[:8]))
    print(
        f"s9 wrote {len(written)} files, {sum(len(v) for v in days.values())} names",
        flush=True,
    )
    if args.event_study:
        rows = event_study_rows(kept, args.start, args.end)
        dest = write_event_study(rows, out_dir / "event_study.csv")
        print(f"s9 event-study {len(rows)} rows -> {dest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
