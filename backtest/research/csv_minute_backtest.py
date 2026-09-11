#!/usr/bin/env python3
"""CSV 模式分钟向量化回测（策略 6，绕开 Cerebro）。

与日线近似版同一套 CSV 额度 / T+1 / 涨停跳过 / force_min / 0.1% 双边佣金。
卖点按分钟路径扫描：峰值用 bar high，止损/止盈用 Strategy6 公式（close 作现价；
开盘已跌破止损则按开盘价成交）。买入用 14:55 分钟收盘（湖内时间为
「中国交易时钟标成 UTC」——09:30 UTC = 09:30 CST）。

用法：
    python backtest/research/csv_minute_backtest.py --start 20251023 --end 20251104
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import pyarrow as pa

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)

from backtest.research.csv_daily_backtest import (  # noqa: E402
    CHASE_HM,
    DEFAULT_DAILY_QUOTA,
    DEFAULT_TOTAL_CASH,
    MINUTE_LAKE_END,
    PEAK_GAP_MIN,
    POS_TRAIL,
    PROFIT_BASE,
    STOP_PCT,
    TIER_DEFAULT,
    TIERS,
    SimState,
    add_strategy6_ratio_args,
    chase_decision,
    execute_buy,
    record_strategy6_params,
    strategy6_kwargs_from_args,
    _limit_prices,
    hit_limit_down,
    peak_gap_blocks,
    trail_hits,
    hit_limit_up,
    _progress,
    _sell,
    _ymd,
    build_calendar,
    load_daily_bars,
    load_pool_days,
    maybe_compare_daily,
    summarize,
    utc_ms_range,
    warn_stale_period_env,
    warmup_start,
    write_run_artifacts,
)
import pyarrow.compute as pc  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from common.infra.data_root import resolve_period_root  # noqa: E402
from oskh_data.symbol_format import to_partition_key  # noqa: E402

BUY_HM = 14 * 60 + 55
AM_OPEN, AM_CLOSE = 9 * 60 + 30, 11 * 60 + 30
PM_OPEN, PM_CLOSE = 13 * 60, 15 * 60

HELP_LOCK = """
分钟向量化口径（相对 Cerebro 保真版：无事件总线，同公式逐分钟扫描）：
  时钟：分钟湖 time 把 A 股会话钟点标成 UTC（09:30 UTC=开盘）。交易日=该 UTC 日期。
  买入：池 CSV 当日候选、14:55 收盘价；买价达到或超过涨停价 → 当日不买，
        记下额度。T+1 09:45 市价>当日开盘 → 09:45 收盘追买；否则弃买。一次机会。
  止损：D+1 起，开盘 ≤ 买入价×(1-stop) → 开盘成交；否则该分钟 close 触价 → close 成交。
  止盈：基础锚 +1%。峰值用 bar high，现价用 close；仅峰值超过 +1% 后按
        T+1=0.3 / T+2=0.4 / T+3=0.5 / T+4=0.6 / T+5+=0.7 回撤。开盘 < 锚先观察。
        触价 bar 与创新高 bar 间隔不能 < 15 分钟（=15 允许；隔夜/午休 gap<0 视为满足）。
        触发价 < 买入价不止盈。未过锚不止盈。盘中触线按该分钟 close 走。
  比例：--stop-pct / --profit-base / --trail-t1..t5 可改。
  T+0：不可卖；峰值固定为买入价，14:55 之后的 high 不计入。峰值从 T+1 起算。
  资金 / T+1 / force_min / 佣金：与 csv_daily_backtest 相同。
  复权：买卖价、涨跌停、净值全程 dividend_type=none（与日线/Cerebro 对齐，
        不用 front 对照）。
  窗口：分钟湖目前到 2026-05-25；要「→今天」用日线版。
  加载：time 毫秒先切片再转 datetime（避免对整段 8 万行 strftime）；文件仍是单
        row group，磁盘还是整文件读，但 CPU 从「全历史转换」降到「窗口转换」。
  缓存：窗口分钟条写入 backtest_output/bar_cache/（E 盘，已 annotated）。默认
        命中直接读缓存；缺码再补湖并回写。--no-cache 跳过；--rebuild-cache 重做。
  落盘：与日线同三件套；若已有 csv_daily_v6_{start}_* 净值，summary 末尾附对照。
"""

CACHE_ROOT = Path(REPO) / "backtest_output" / "bar_cache"
_CACHE_SCHEMA = pa.schema(
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


def _session_index(idx) -> pd.DatetimeIndex:
    t = pd.DatetimeIndex(idx)
    if t.tz is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    return t


def _in_session(hm: np.ndarray) -> np.ndarray:
    return ((hm >= AM_OPEN) & (hm <= AM_CLOSE)) | ((hm >= PM_OPEN) & (hm <= PM_CLOSE))


def _annotate(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    idx = _session_index(out.index)
    out.index = idx
    out["ymd"] = idx.strftime("%Y%m%d")
    out["hm"] = idx.hour * 60 + idx.minute
    return out.loc[_in_session(out["hm"].to_numpy())]


def _read_one_minute(
    code: str, root: Path, start: str, end: str
) -> Optional[pd.DataFrame]:
    path = root / f"symbol={to_partition_key(code)}" / "data.parquet"
    if not path.is_file():
        return None
    t0, t1 = utc_ms_range(start, end)
    try:
        table = pq.read_table(path, columns=["time", "open", "high", "low", "close"])
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
        },
        index=utc.tz_localize(None),
    ).astype(
        {
            "open": np.float64,
            "high": np.float64,
            "low": np.float64,
            "close": np.float64,
            "hm": np.int64,
        }
    )
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out if not out.empty else None


def minute_cache_path(start: str, end: str, cache_dir: Optional[Path] = None) -> Path:
    root = Path(cache_dir) if cache_dir is not None else CACHE_ROOT
    return root / f"minute_none_{start}_{end}.parquet"


def write_minute_cache(
    bars: dict[str, pd.DataFrame],
    start: str,
    end: str,
    cache_dir: Optional[Path] = None,
) -> Path:
    path = minute_cache_path(start, end, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    if tmp.exists():
        tmp.unlink()
    writer = None
    n_rows = 0
    n_sym = 0
    total_sym = sum(1 for df in bars.values() if df is not None and not df.empty)
    try:
        for code, df in bars.items():
            if df is None or df.empty:
                continue
            chunk = df.reset_index()
            time_col = chunk.columns[0]
            chunk = chunk.rename(columns={time_col: "time"})
            chunk.insert(0, "symbol", code)
            chunk["time"] = pd.to_datetime(chunk["time"])
            chunk["ymd"] = chunk["ymd"].astype(str)
            chunk["hm"] = chunk["hm"].astype(np.int64)
            table = pa.Table.from_pandas(
                chunk[["symbol", "time", "open", "high", "low", "close", "ymd", "hm"]],
                schema=_CACHE_SCHEMA,
                preserve_index=False,
            )
            if writer is None:
                writer = pq.ParquetWriter(tmp, _CACHE_SCHEMA, compression="zstd")
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
    meta = path.with_suffix(".json")
    meta.write_text(
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


def _frame_from_cache_group(g: pd.DataFrame) -> pd.DataFrame:
    frame = g.drop(columns=["symbol"])
    frame.index = pd.DatetimeIndex(frame.pop("time"))
    frame["hm"] = frame["hm"].astype(np.int64, copy=False)
    if not frame.index.is_monotonic_increasing:
        frame = frame.sort_index()
    return frame


def read_minute_cache(
    path: Path, codes: Optional[set[str]] = None
) -> dict[str, pd.DataFrame]:
    """按 row group 读（写入时一码一组），避免整表 to_pandas 顶满内存。"""
    print(f"reading minute cache {path}", flush=True)
    pf = pq.ParquetFile(path)
    want = set(codes) if codes else None
    out: dict[str, pd.DataFrame] = {}
    n_rows = 0
    n_rg = pf.num_row_groups
    for i in range(n_rg):
        table = pf.read_row_group(i)
        if table.num_rows == 0:
            continue
        uniq = pc.unique(table.column("symbol"))
        if len(uniq) == 1:
            code = uniq[0].as_py()
            if want is not None and code not in want:
                continue
            key = str(code)
            df = table.to_pandas()
            n_rows += len(df)
            frame = _frame_from_cache_group(df)
            if key in out:
                merged = pd.concat([out[key], frame])
                out[key] = (
                    merged
                    if merged.index.is_monotonic_increasing
                    else merged.sort_index()
                )
            else:
                out[key] = frame
        else:
            if want is not None:
                table = table.filter(pc.field("symbol").isin(sorted(want)))
                if table.num_rows == 0:
                    continue
            df = table.to_pandas()
            n_rows += len(df)
            for code, g in df.groupby("symbol", sort=False):
                frame = _frame_from_cache_group(g)
                key = str(code)
                if key in out:
                    merged = pd.concat([out[key], frame])
                    out[key] = (
                        merged
                        if merged.index.is_monotonic_increasing
                        else merged.sort_index()
                    )
                else:
                    out[key] = frame
        if (i + 1) == n_rg or (i + 1) % 400 == 0:
            print(f"minute cache rg {i + 1}/{n_rg} symbols={len(out)}", flush=True)
    print(f"minute cache rows={n_rows}", flush=True)
    return out


def _load_minute_from_lake(
    codes: set[str], start: str, end: str, *, workers: int = 16
) -> dict[str, pd.DataFrame]:
    root = resolve_period_root("1m") / "dividend_type=none"
    out: dict[str, pd.DataFrame] = {}
    if not codes:
        return out
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futs = {
            pool.submit(_read_one_minute, c, root, start, end): c for c in sorted(codes)
        }
        done = 0
        total = len(futs)
        for fut in as_completed(futs):
            done += 1
            _progress(done, total, "minute lake")
            code = futs[fut]
            try:
                df = fut.result()
            except Exception:
                continue
            if df is not None and not df.empty:
                out[code] = df
    return out


def load_minute_bars(
    codes: set[str],
    start: str,
    end: str,
    *,
    workers: int = 16,
    use_cache: bool = True,
    rebuild_cache: bool = False,
    cache_dir: Optional[Path] = None,
    status: Optional[dict] = None,
) -> dict[str, pd.DataFrame]:
    want = set(codes)
    path = minute_cache_path(start, end, cache_dir)
    cached: dict[str, pd.DataFrame] = {}
    had_file = path.is_file()
    if use_cache and had_file and not rebuild_cache:
        print(f"minute cache hit {path}", flush=True)
        cached = read_minute_cache(path, want)
    missing = want - set(cached)
    if missing:
        print(
            f"minute lake load {len(missing)} codes ({len(cached)} cached)", flush=True
        )
        fresh = _load_minute_from_lake(missing, start, end, workers=workers)
        cached.update(fresh)
        if use_cache and fresh:
            merged = cached
            if path.is_file() and not rebuild_cache:
                # 保留缓存里本次未请求的旧码，避免子集请求冲掉全量
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
    return {c: cached[c] for c in want if c in cached}


def scan_held_day(
    o: np.ndarray,
    h: np.ndarray,
    c: np.ndarray,
    *,
    cost: float,
    peak: float,
    n_days: int,
    can_sell: bool,
    stop_pct: float,
    profit_base: float,
    trail_ratio: float,
    pos_trail: float = 0.0,
    limit_down: float = 0.0,
    hm: Optional[np.ndarray] = None,
    peak_hm: int = -1,
    peak_gap_min: int = PEAK_GAP_MIN,
) -> tuple[int, float, str, float, int]:
    """逐分钟扫描。返回 (idx, px, reason, new_peak, new_peak_hm)。"""
    trigger = cost * (1.0 - stop_pct)
    new_peak = float(peak)
    new_peak_hm = int(peak_hm)
    n = int(len(c))
    for i in range(n):
        # T+0 不卖、不更新峰值（历史最高价从 T+1 起算）
        if (not can_sell) or n_days < 1:
            continue
        hi = float(h[i])
        cur_hm = int(hm[i]) if hm is not None else i
        if hi > new_peak:
            new_peak = hi
            new_peak_hm = cur_hm
        px_open = float(o[i])
        px_close = float(c[i])
        if limit_down > 0 and hit_limit_down(px_open, limit_down):
            continue
        if px_open <= trigger:
            return i, px_open, "stop_loss:gap_open", new_peak, new_peak_hm
        ret = px_close / cost - 1.0
        if ret <= -stop_pct:
            return i, px_close, "stop_loss:touch", new_peak, new_peak_hm
        if new_peak_hm >= 0 and peak_gap_blocks(cur_hm - new_peak_hm, peak_gap_min):
            continue
        if trail_hits(px_close, cost, new_peak, profit_base, trail_ratio):
            return i, px_close, f"trail:T+{max(1, n_days)}", new_peak, new_peak_hm
    return -1, float("nan"), "", new_peak, new_peak_hm


def _day_arrays(df: pd.DataFrame, ymd: str) -> Optional[pd.DataFrame]:
    sl = df.loc[df["ymd"] == ymd]
    return sl if not sl.empty else None


def build_day_spans(df: pd.DataFrame) -> dict[str, tuple[int, int]]:
    """按 ymd 切 iloc 区间。要求时间升序；乱序则返回空，调用方回退 _day_arrays。"""
    if df is None or df.empty or "ymd" not in df.columns:
        return {}
    ymd = df["ymd"].to_numpy()
    if len(ymd) >= 2 and np.any(ymd[1:] < ymd[:-1]):
        return {}
    change = np.flatnonzero(ymd[1:] != ymd[:-1]) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [len(ymd)]))
    return {str(ymd[s]): (int(s), int(e)) for s, e in zip(starts, ends)}


def _slice_day(
    df: pd.DataFrame, spans: dict[str, tuple[int, int]], ymd: str
) -> Optional[pd.DataFrame]:
    span = spans.get(ymd)
    if span is not None:
        sl = df.iloc[span[0] : span[1]]
        return sl if not sl.empty else None
    if spans:
        return None
    return _day_arrays(df, ymd)


def _buy_px(day_df: pd.DataFrame) -> Optional[float]:
    hit = day_df.loc[day_df["hm"] == BUY_HM]
    if not hit.empty:
        return float(hit["close"].iloc[0])
    late = day_df.loc[(day_df["hm"] >= 14 * 60 + 30) & (day_df["hm"] <= BUY_HM)]
    if late.empty:
        return None
    return float(late["close"].iloc[-1])


def _chase_quotes(day_df: pd.DataFrame) -> Optional[tuple[float, float]]:
    """(当日开盘, 09:45 市价)。缺 09:45 则用 ≤09:45 最后一根 close。"""
    if day_df is None or day_df.empty:
        return None
    open_px = float(day_df.iloc[0]["open"])
    hit = day_df.loc[day_df["hm"] == CHASE_HM]
    if not hit.empty:
        return open_px, float(hit["close"].iloc[0])
    early = day_df.loc[(day_df["hm"] >= AM_OPEN) & (day_df["hm"] <= CHASE_HM)]
    if early.empty:
        return None
    return open_px, float(early["close"].iloc[-1])


def simulate(
    minute_bars: dict[str, pd.DataFrame],
    daily_bars: dict[str, pd.DataFrame],
    pool_days: dict[str, list[str]],
    start: str,
    end: str,
    *,
    total_cash: float = DEFAULT_TOTAL_CASH,
    daily_quota: float = DEFAULT_DAILY_QUOTA,
    stop_pct: float = STOP_PCT,
    profit_base: float = PROFIT_BASE,
    tiers: Optional[dict] = None,
    tier_default: float = TIER_DEFAULT,
    pos_trail: float = POS_TRAIL,
) -> SimState:
    tier_map = dict(tiers or TIERS)
    calendar = build_calendar(daily_bars, start, end)

    st = SimState(cash=float(total_cash))
    record_strategy6_params(
        st,
        stop_pct=stop_pct,
        profit_base=profit_base,
        tiers=tier_map,
        tier_default=tier_default,
    )
    st.stats["bars_loaded"] = len(minute_bars)
    st.stats["pool_days"] = len(pool_days)
    day_spans = {code: build_day_spans(df) for code, df in minute_bars.items()}
    pending_chase: dict[str, tuple[float, int]] = {}

    for i, day in enumerate(calendar):
        ds = _ymd(day)
        st.daily_quota_used = 0.0

        for code in list(st.positions):
            pos = st.positions[code]
            mdf = minute_bars.get(code)
            ddf = daily_bars.get(code)
            if mdf is None or ddf is None or day not in ddf.index:
                continue
            day_m = _slice_day(mdf, day_spans.get(code, {}), ds)
            if day_m is None:
                continue
            prev_rows = ddf.loc[ddf.index < day]
            if prev_rows.empty:
                continue
            prev_close = float(prev_rows.iloc[-1]["close"])
            _, limit_down = _limit_prices(code, prev_close)
            n_days = i - pos.entry_idx
            o = day_m["open"].to_numpy(np.float64)
            h = day_m["high"].to_numpy(np.float64)
            c = day_m["close"].to_numpy(np.float64)
            hm = day_m["hm"].to_numpy(np.int64)
            idx, px, reason, new_peak, new_peak_hm = scan_held_day(
                o,
                h,
                c,
                cost=pos.cost,
                peak=pos.peak,
                n_days=n_days,
                can_sell=(n_days >= 1),
                stop_pct=stop_pct,
                profit_base=profit_base,
                trail_ratio=float(tier_map.get(n_days, tier_default)),
                pos_trail=pos_trail,
                limit_down=limit_down,
                hm=hm,
                peak_hm=int(pos.peak_hm),
            )
            pos.peak = new_peak
            pos.peak_hm = new_peak_hm
            if idx >= 0:
                if hit_limit_down(float(o[idx]), limit_down) and reason.startswith(
                    "stop_loss"
                ):
                    st.stats["defer_sell_limit_down"] += 1
                    continue
                _sell(st, code, pos, px, day, reason)

        due = [c for c, (_per, sig) in pending_chase.items() if i == sig + 1]
        for code in due:
            per_ch, _sig = pending_chase.pop(code)
            if code in st.positions:
                st.stats["skip_held"] += 1
                continue
            mdf = minute_bars.get(code)
            ddf = daily_bars.get(code)
            if mdf is None or ddf is None or day not in ddf.index:
                st.stats["chase_no_bar"] += 1
                continue
            day_m = _slice_day(mdf, day_spans.get(code, {}), ds)
            quotes = _chase_quotes(day_m) if day_m is not None else None
            if quotes is None:
                st.stats["chase_no_bar"] += 1
                continue
            open_px, px = quotes
            prev_rows = ddf.loc[ddf.index < day]
            if prev_rows.empty:
                st.stats["chase_no_bar"] += 1
                continue
            prev_close = float(prev_rows.iloc[-1]["close"])
            limit_up, _ = _limit_prices(code, prev_close)
            decision = chase_decision(open_px, px, limit_up)
            if decision == "limit":
                st.stats["chase_skip_limit"] += 1
                continue
            if decision != "buy":
                st.stats["chase_abandon"] += 1
                continue
            execute_buy(st, code, px, per_ch, i, day, reason="chase:T+1")

        planned = list(pool_days.get(ds, []))
        if planned:
            per = min(daily_quota, st.cash) / len(planned)
            for code in planned:
                if code in st.positions:
                    st.stats["skip_held"] += 1
                    continue
                mdf = minute_bars.get(code)
                ddf = daily_bars.get(code)
                if mdf is None or ddf is None or day not in ddf.index:
                    st.stats["skip_no_bar"] += 1
                    continue
                day_m = _slice_day(mdf, day_spans.get(code, {}), ds)
                if day_m is None:
                    st.stats["skip_no_bar"] += 1
                    continue
                prev_rows = ddf.loc[ddf.index < day]
                if prev_rows.empty:
                    st.stats["skip_no_bar"] += 1
                    continue
                px = _buy_px(day_m)
                if px is None or px <= 0:
                    st.stats["skip_no_bar"] += 1
                    continue
                prev_close = float(prev_rows.iloc[-1]["close"])
                limit_up, _ = _limit_prices(code, prev_close)
                if hit_limit_up(px, limit_up):
                    st.stats["skip_limit_up"] += 1
                    pending_chase[code] = (per, i)
                    continue
                execute_buy(st, code, px, per, i, day, reason="pool")

        eq = st.cash
        for code, pos in st.positions.items():
            ddf = daily_bars.get(code)
            if ddf is not None and day in ddf.index:
                eq += pos.shares * float(ddf.loc[day]["close"])
            else:
                eq += pos.shares * pos.cost
        st.equity_curve.append((ds, eq))

        if day == calendar[-1] and st.positions:
            for code, pos in st.positions.items():
                ddf = daily_bars.get(code)
                last = (
                    float(ddf.loc[day]["close"])
                    if ddf is not None and day in ddf.index
                    else pos.cost
                )
                st.trades.append(
                    {
                        "date": ds,
                        "code": code,
                        "side": "EOD_MARK",
                        "price": last,
                        "shares": pos.shares,
                        "notional": pos.shares * last,
                        "commission": 0.0,
                    }
                )

    return st


def run(
    start: str,
    end: str,
    *,
    total_cash: float = DEFAULT_TOTAL_CASH,
    daily_quota: float = DEFAULT_DAILY_QUOTA,
    stop_pct: float = STOP_PCT,
    profit_base: float = PROFIT_BASE,
    tiers: Optional[dict] = None,
    tier_default: float = TIER_DEFAULT,
    pos_trail: float = POS_TRAIL,
    workers: int = 16,
    use_cache: bool = True,
    rebuild_cache: bool = False,
) -> SimState:
    warn_stale_period_env()
    if end > MINUTE_LAKE_END:
        print(
            f"[warn] --end {end} past minute lake {MINUTE_LAKE_END}; "
            "bars after that date are missing, use daily engine to reach today",
            flush=True,
        )
    t_pool = time.perf_counter()
    pool_days = load_pool_days(start, end)
    t_pool = time.perf_counter() - t_pool
    if not pool_days:
        raise SystemExit(f"no pool CSVs in [{start}, {end}] under stock_pool/")
    all_codes = {c for codes in pool_days.values() for c in codes}
    load_start = warmup_start(start)
    print(
        f"loading daily+minute: {len(all_codes)} codes, {load_start}..{end}; "
        f"pool {min(pool_days)}..{max(pool_days)} ({len(pool_days)} days)",
        flush=True,
    )
    t_daily = time.perf_counter()
    daily = load_daily_bars(all_codes, load_start, end, workers=workers)
    t_daily = time.perf_counter() - t_daily
    cache_status: dict = {}
    t_minute = time.perf_counter()
    minute = load_minute_bars(
        all_codes,
        load_start,
        end,
        workers=workers,
        use_cache=use_cache,
        rebuild_cache=rebuild_cache,
        status=cache_status,
    )
    t_minute = time.perf_counter() - t_minute
    print(
        f"loaded daily {len(daily)} / minute {len(minute)} / pool days {len(pool_days)}",
        flush=True,
    )
    t_sim = time.perf_counter()
    st = simulate(
        minute,
        daily,
        pool_days,
        start,
        end,
        total_cash=total_cash,
        daily_quota=daily_quota,
        stop_pct=stop_pct,
        profit_base=profit_base,
        tiers=tiers,
        tier_default=tier_default,
        pos_trail=pos_trail,
    )
    st.stats["t_pool_s"] = t_pool
    st.stats["t_daily_s"] = t_daily
    st.stats["t_minute_s"] = t_minute
    st.stats["t_sim_s"] = time.perf_counter() - t_sim
    st.stats["cache"] = cache_status.get("cache", "")
    st.stats["codes_missing"] = max(0, len(all_codes) - min(len(daily), len(minute)))
    return st


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(
        description="CSV-mode vectorized minute strategy6 backtest",
        epilog=HELP_LOCK,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--start", default="20251023")
    ap.add_argument(
        "--end",
        default=MINUTE_LAKE_END,
        help=f"minute lake last day is {MINUTE_LAKE_END}; short parity window: 20251104",
    )
    ap.add_argument("--cash-total", type=float, default=DEFAULT_TOTAL_CASH)
    ap.add_argument("--daily-quota", type=float, default=DEFAULT_DAILY_QUOTA)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--no-cache", action="store_true", help="skip minute window cache")
    ap.add_argument(
        "--rebuild-cache", action="store_true", help="reload lake and rewrite cache"
    )
    add_strategy6_ratio_args(ap)
    args = ap.parse_args(argv if argv is not None else None)

    st = run(
        args.start,
        args.end,
        total_cash=args.cash_total,
        daily_quota=args.daily_quota,
        workers=args.workers,
        use_cache=not args.no_cache,
        rebuild_cache=args.rebuild_cache,
        **strategy6_kwargs_from_args(args),
    )
    text = summarize(st, args.cash_total, args.start, args.end, engine="csv_minute_v6")
    cmp = maybe_compare_daily(
        st.equity_curve, args.start, args.end, this_label="csv_minute_v6"
    )
    if cmp:
        text = text + "\n" + cmp
    print(text)
    tag = f"csv_minute_v6_{args.start}_{args.end}"
    write_run_artifacts(Path(REPO) / "backtest_output" / tag, st, text, HELP_LOCK)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
