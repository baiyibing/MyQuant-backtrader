#!/usr/bin/env python3
"""CSV 模式分钟向量化回测（共用买侧/资金引擎，卖点由策略书提供）。

与日线近似版同一套 CSV 额度 / T+1 / 涨停跳过 / force_min / 0.1% 双边佣金。
卖点按分钟路径扫描：峰值用 bar high，现价用 close；开盘已跌破止损则按开盘价
成交。必须从已注册策略中显式指定 `--strategy`，无缺省。买入用 14:55 分钟收盘
（湖内时间为「中国交易时钟标成 UTC」——09:30 UTC = 09:30 CST）。

用法：
    python backtest/research/csv_minute_backtest.py --strategy version6 --start 20251023 --end 20251104
    python backtest/research/csv_minute_backtest.py --strategy version8 --start 20251023 --end 20260909
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

from backtest.research.csv_ledger import (  # noqa: E402
    CHASE_HM,
    DEFAULT_TOTAL_CASH,
    PEAK_GAP_MIN,
    SimState,
    chase_decision,
    execute_buy,
    finish_pending_chase,
    queue_limit_up_chase,
    hit_limit_down,
    hit_limit_up,
    last_close_mark,
    peak_gap_blocks,
    _sell,
    _ymd,
    rescale_position,
)

from backtest.research.exdiv_map import k_for, load_exdiv_ratios, mapped_prev_close  # noqa: E402
from backtest.research.csv_common import (  # noqa: E402
    DEFAULT_DAILY_QUOTA,
    STRATEGY4_CALENDAR_SLACK_DAYS,
    WARMUP_DAYS,
    build_calendar,
    _named_limits,
    _pool_names_asof,
    _progress,
)
from backtest.research.market_layer import utc_ms_range  # noqa: E402
from backtest.research.csv_pool import (  # noqa: E402
    load_pool_day_map,
    load_pool_names_by_day,
)
from backtest.research.csv_strategy_books import (  # noqa: E402
    add_csv_backtest_common_args,
    apply_csv_strategy,
    csv_run_kwargs_from_args,
    engine_book,
    resolve_research_pool_dir,
    help_lock_all,
    help_lock_for,
    normalize_csv_strategy,
)
from backtest.research.strategy6_rules import (  # noqa: E402
    POS_TRAIL,
    trail_hits,
)
from backtest.research.csv_artifacts import (  # noqa: E402
    maybe_compare_daily,
    summarize,
    write_run_artifacts,
)
from backtest.research.csv_daily_loader import (  # noqa: E402
    load_daily_bars,
    warn_stale_period_env,
    warmup_start,
)

# 2026-09-11 实测：F 盘 period=1m 最后一根交易日（抽样 50 只含 000001，无 20260910）。
MINUTE_LAKE_END = "20260909"
import pyarrow.compute as pc  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from common.infra.data_root import resolve_period_root  # noqa: E402
from oskh_data.symbol_format import to_partition_key  # noqa: E402
from backtest.research.strategy3_rules import reserve_step_minute  # noqa: E402
from backtest.research.csv_simulate_loop import (  # noqa: E402
    append_equity_and_eod_marks,
    init_sim_state,
    prepare_strategy_hooks,
    run_chase_due_day,
    run_pool_buys_day,
)

BUY_HM = 14 * 60 + 55
AM_OPEN, AM_CLOSE = 9 * 60 + 30, 11 * 60 + 30
PM_OPEN, PM_CLOSE = 13 * 60, 15 * 60

HELP_LOCK = """
分钟向量化口径（相对 Cerebro 保真版：无事件总线，同公式逐分钟扫描）：
  时钟：分钟湖 time 把 A 股会话钟点标成 UTC（09:30 UTC=开盘）。交易日=该 UTC 日期。
  买入：池 CSV 当日候选、14:55 收盘价；买价达到或超过涨停价 → 当日不买，
        记下额度。T+1 09:45 市价>当日开盘 → 09:45 收盘追买；否则弃买。
        追买日无 K 保留 pending 到下一有 K 日（仍只评一次）。
        per_name 已持跳过、不加仓；daily_quota 沿用策略书历史加仓路径。
        未知板块且无 ST 名 → skip_unknown_board，不交易。
  止损：D+1 起，开盘 ≤ 买入价×(1-stop) → 开盘成交；否则该分钟 close 触价 → close 成交。
  跌停禁卖：任何卖因成交前若开盘或成交价跌停 → 不成交、当日跳过、次日再评
        （含 trail / profit_take / force / ma_signal / open_board，不只 stop_loss）。
  停牌：冻仓；净值用最近有 K 的 close。
  止盈 / 峰值：见下方对应策略书。峰值用 bar high，现价用 close。
        策略 6 触价 bar 与创新高 bar 间隔不能 < 15 分钟（=15 允许；隔夜/午休 gap<0 视为满足）。
        盘中触线按该分钟 close 走。
  T+0：不可卖；峰值固定为买入价，14:55 之后的 high 不计入。峰值从 T+1 起算。
  资金 / T+1 / force_min / 佣金：与 csv_daily_backtest 相同。
        资金模式见策略书（v8=每股预算）；per_name 现金不足（含佣金）整笔 skip_cash。
  配给：--ration file_order 保持 CSV 行序；seeded_shuffle 用 --ration-seed 与日期
        经 SHA-256 派生逐日稳定乱序；追买沿该次名单遍历产生的排队顺序。
  复权：E-R6 除权日参考价修正 — 持仓期除权日一次性缩放 open lot 的 cost/peak，
        并将当日 prev_close→档位换算点映射到 D 域；成交价/净值/股数仍 none。
        非除权日与 ≤0.5% 噪声带见 E-R5 收窄声明（engine-ashare-correctness.md）。
  窗口：分钟湖目前到 2026-05-25；要「→今天」用日线版。
  加载：time 毫秒先切片再转 datetime（避免对整段 8 万行 strftime）；文件仍是单
        row group，磁盘还是整文件读，但 CPU 从「全历史转换」降到「窗口转换」。
  缓存：窗口分钟条写入 backtest_output/bar_cache/（E 盘，已 annotated）。默认
        命中直接读缓存；缺码再补湖并回写。--no-cache 跳过；--rebuild-cache 重做。
  落盘：与日线同三件套；若已有同策略 csv_daily_{book}_{start}_* 净值，summary 末尾附对照。
  策略：必须显式指定已注册 --strategy（无缺省）。共用引擎，策略书换卖点与加仓。
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
        columns = ["time", "open", "high", "low", "close"]
        has_volume = "volume" in pq.read_schema(path).names
        table = pq.read_table(
            path, columns=columns + (["volume"] if has_volume else [])
        )
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
            **(
                {"_volume": table["volume"].to_numpy()[keep]}
                if has_volume
                else {}
            ),
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
    if has_volume:
        day_volume = out.groupby("ymd")["_volume"].transform("sum")
        out = out.loc[day_volume != 0].drop(columns="_volume")
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


_LIMIT_EPS = 0.001  # mirror csv_ledger.LIMIT_EPS for numba core

try:
    from numba import njit as _njit  # type: ignore

    @_njit(cache=True)
    def _scan_held_day_numba_trail(
        o,
        h,
        c,
        hm,
        cost,
        peak,
        n_days,
        can_sell,
        stop_pct,
        stop_enabled,
        profit_base,
        trail_ratio,
        limit_down,
        peak_hm,
        peak_gap_min,
        force_sell_hm,
        has_force,
    ):
        """Pure trail path (no sell_gate / take_profit / reserve). Reasons as int codes."""
        trigger = cost * (1.0 - stop_pct) if stop_enabled else 0.0
        new_peak = peak
        new_peak_hm = peak_hm
        n = len(c)
        for i in range(n):
            if (not can_sell) or n_days < 1:
                continue
            hi = h[i]
            cur_hm = hm[i]
            if hi > new_peak:
                new_peak = hi
                new_peak_hm = cur_hm
            px_open = o[i]
            px_close = c[i]
            if limit_down > 0.0 and (px_open - _LIMIT_EPS) <= limit_down:
                continue
            if stop_enabled and px_open <= trigger:
                return i, px_open, 1, new_peak, new_peak_hm
            ret = px_close / cost - 1.0
            if stop_enabled and ret <= -stop_pct:
                return i, px_close, 2, new_peak, new_peak_hm
            gap = cur_hm - new_peak_hm
            peak_blocked = new_peak_hm >= 0 and (0 <= gap < peak_gap_min)
            if not peak_blocked:
                # inline trail_hits
                if px_close >= cost:
                    peak_excess = new_peak / cost - 1.0 - profit_base
                    if peak_excess > 0.0:
                        if (
                            px_close / cost - 1.0 - profit_base
                            <= trail_ratio * peak_excess
                        ):
                            return i, px_close, 3, new_peak, new_peak_hm
            if has_force and cur_hm >= force_sell_hm:
                if limit_down > 0.0 and (px_close - _LIMIT_EPS) <= limit_down:
                    continue
                return i, px_close, 4, new_peak, new_peak_hm
        return -1, np.nan, 0, new_peak, new_peak_hm

    _NUMBA_SCAN_AVAILABLE = True
except Exception:  # pragma: no cover - optional dep
    _NUMBA_SCAN_AVAILABLE = False
    _scan_held_day_numba_trail = None  # type: ignore


_NUMBA_REASON = {
    1: "stop_loss:gap_open",
    2: "stop_loss:touch",
    3: None,  # filled with trail:T+N
    4: "force_sell:time",
}


def _want_numba_scan(use_numba: Optional[bool]) -> bool:
    if use_numba is True:
        return True
    if use_numba is False:
        return False
    backend = (os.environ.get("CSV_SCAN_HELD_DAY_BACKEND") or "python").strip().lower()
    return backend in {"numba", "jit"}


def scan_held_day_python(
    o: np.ndarray,
    h: np.ndarray,
    c: np.ndarray,
    *,
    cost: float,
    peak: float,
    n_days: int,
    can_sell: bool,
    stop_pct: Optional[float],
    profit_base: float,
    trail_ratio: float,
    pos_trail: float = 0.0,
    limit_down: float = 0.0,
    hm: Optional[np.ndarray] = None,
    peak_hm: int = -1,
    peak_gap_min: int = PEAK_GAP_MIN,
    take_profit=None,
    sell_gate=None,
    gate_code=None,
    gate_day=None,
    daily_closes_ending_yesterday=None,
    force_sell_hm: Optional[int] = None,
    reserve_limit_up: bool = False,
    limit_up: float = 0.0,
    reserved: bool = False,
    reserve_state: Optional[dict] = None,
) -> tuple[int, float, str, float, int]:
    """Python reference implementation of the minute sell scan."""
    del pos_trail  # reserved for future; kept for API parity with callers
    stop_enabled = isinstance(stop_pct, float) and 0 < stop_pct < 1
    trigger = cost * (1.0 - stop_pct) if stop_enabled else None
    new_peak = float(peak)
    new_peak_hm = int(peak_hm)
    current_reserved = bool(reserved)
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
        if stop_enabled and trigger is not None and px_open <= trigger:
            return i, px_open, "stop_loss:gap_open", new_peak, new_peak_hm
        ret = px_close / cost - 1.0
        if stop_enabled and ret <= -stop_pct:
            return i, px_close, "stop_loss:touch", new_peak, new_peak_hm
        if reserve_limit_up:
            is_limit_up = limit_up > 0 and hit_limit_up(px_close, limit_up)
            current_reserved, reserve_reason = reserve_step_minute(
                reserved=current_reserved, hm=cur_hm, is_limit_up=is_limit_up
            )
            if reserve_state is not None:
                reserve_state["reserved"] = current_reserved
            if reserve_reason:
                return i, px_close, reserve_reason, new_peak, new_peak_hm
            if current_reserved and is_limit_up:
                continue
        peak_blocked = new_peak_hm >= 0 and peak_gap_blocks(
            cur_hm - new_peak_hm, peak_gap_min
        )
        if not peak_blocked:
            if callable(sell_gate):
                reason = sell_gate(
                    gate_code,
                    px_close,
                    gate_day,
                    daily_closes_ending_yesterday or [],
                )
                if reason:
                    return i, px_close, reason, new_peak, new_peak_hm
            elif take_profit is not None:
                reason = take_profit(px_close, cost, new_peak, n_days)
                if reason:
                    return i, px_close, reason, new_peak, new_peak_hm
            elif trail_hits(px_close, cost, new_peak, profit_base, trail_ratio):
                return i, px_close, f"trail:T+{max(1, n_days)}", new_peak, new_peak_hm
        if force_sell_hm is not None and cur_hm >= int(force_sell_hm):
            if limit_down > 0 and hit_limit_down(px_close, limit_down):
                continue
            return i, px_close, "force_sell:time", new_peak, new_peak_hm
    return -1, float("nan"), "", new_peak, new_peak_hm


def scan_held_day(
    o: np.ndarray,
    h: np.ndarray,
    c: np.ndarray,
    *,
    cost: float,
    peak: float,
    n_days: int,
    can_sell: bool,
    stop_pct: Optional[float],
    profit_base: float,
    trail_ratio: float,
    pos_trail: float = 0.0,
    limit_down: float = 0.0,
    hm: Optional[np.ndarray] = None,
    peak_hm: int = -1,
    peak_gap_min: int = PEAK_GAP_MIN,
    take_profit=None,
    sell_gate=None,
    gate_code=None,
    gate_day=None,
    daily_closes_ending_yesterday=None,
    force_sell_hm: Optional[int] = None,
    reserve_limit_up: bool = False,
    limit_up: float = 0.0,
    reserved: bool = False,
    reserve_state: Optional[dict] = None,
    use_numba: Optional[bool] = None,
) -> tuple[int, float, str, float, int]:
    """逐分钟扫描。返回 (idx, px, reason, new_peak, new_peak_hm)。

    Default backend is the Python reference. Optional numba trail-only path
    is gated by ``use_numba=True`` or env ``CSV_SCAN_HELD_DAY_BACKEND=numba``.
    Callables (sell_gate / take_profit) and reserve_limit_up always use Python.
    """
    can_offload = (
        _want_numba_scan(use_numba)
        and _NUMBA_SCAN_AVAILABLE
        and sell_gate is None
        and take_profit is None
        and not reserve_limit_up
        and reserve_state is None
    )
    if can_offload:
        o64 = np.asarray(o, dtype=np.float64)
        h64 = np.asarray(h, dtype=np.float64)
        c64 = np.asarray(c, dtype=np.float64)
        if hm is None:
            hm64 = np.arange(len(c64), dtype=np.int64)
        else:
            hm64 = np.asarray(hm, dtype=np.int64)
        stop_enabled = isinstance(stop_pct, float) and 0 < float(stop_pct) < 1
        stop_v = float(stop_pct) if stop_enabled else 0.0
        has_force = force_sell_hm is not None
        force_v = int(force_sell_hm) if has_force else 0
        idx, px, code, new_peak, new_peak_hm = _scan_held_day_numba_trail(
            o64,
            h64,
            c64,
            hm64,
            float(cost),
            float(peak),
            int(n_days),
            bool(can_sell),
            stop_v,
            bool(stop_enabled),
            float(profit_base),
            float(trail_ratio),
            float(limit_down),
            int(peak_hm),
            int(peak_gap_min),
            force_v,
            bool(has_force),
        )
        if code == 0:
            return -1, float("nan"), "", float(new_peak), int(new_peak_hm)
        if code == 3:
            reason = f"trail:T+{max(1, int(n_days))}"
        else:
            reason = _NUMBA_REASON[int(code)]
        return int(idx), float(px), reason, float(new_peak), int(new_peak_hm)

    return scan_held_day_python(
        o,
        h,
        c,
        cost=cost,
        peak=peak,
        n_days=n_days,
        can_sell=can_sell,
        stop_pct=stop_pct,
        profit_base=profit_base,
        trail_ratio=trail_ratio,
        pos_trail=pos_trail,
        limit_down=limit_down,
        hm=hm,
        peak_hm=peak_hm,
        peak_gap_min=peak_gap_min,
        take_profit=take_profit,
        sell_gate=sell_gate,
        gate_code=gate_code,
        gate_day=gate_day,
        daily_closes_ending_yesterday=daily_closes_ending_yesterday,
        force_sell_hm=force_sell_hm,
        reserve_limit_up=reserve_limit_up,
        limit_up=limit_up,
        reserved=reserved,
        reserve_state=reserve_state,
    )


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


def _previous_rows(df: pd.DataFrame, day) -> pd.DataFrame:
    """Rows strictly before ``day``; kept named so orchestration can be profiled."""
    return df.loc[df.index < day]


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
    name_budget: Optional[float] = None,
    ration: str = "file_order",
    ration_seed: int = 0,
    stop_pct: Optional[float] = None,
    profit_base: Optional[float] = None,
    tiers: Optional[dict] = None,
    tier_default: Optional[float] = None,
    pos_trail: float = POS_TRAIL,
    strategy: str,
    take_profit=None,
    record_params=None,
    pool_names: Optional[dict[str, str]] = None,
    pool_names_by_day: Optional[dict[str, dict[str, str]]] = None,
    exdiv: Optional[dict] = None,
    scores_by_day=None,
    topk=None,
    n_drop=None,
    eligible_buy=None,
) -> SimState:
    hooks = prepare_strategy_hooks(
        strategy,
        stop_pct=stop_pct,
        take_profit=take_profit,
        record_params=record_params,
        name_budget=name_budget,
        ration=ration,
        ration_seed=ration_seed,
        profit_base=profit_base,
        tiers=tiers,
        tier_default=tier_default,
        apply_fn=apply_csv_strategy,
        scores_by_day=scores_by_day,
        topk=topk,
        n_drop=n_drop,
        eligible_buy=eligible_buy,
    )
    stop_pct = hooks["stop_pct"]
    take_profit = hooks["take_profit"]
    buy_gate = hooks.get("buy_gate")
    sell_gate = hooks.get("sell_gate")
    peak_gap_min = int(hooks["peak_gap_min"])
    force_sell_hm = hooks.get("force_sell_hm")
    reserve_limit_up = bool(hooks.get("reserve_limit_up"))
    calendar = build_calendar(daily_bars, start, end)

    st, pending_chase, names_asof = init_sim_state(
        hooks,
        total_cash=total_cash,
        bars_loaded=len(minute_bars),
        pool_days=pool_days,
        pool_names=pool_names,
        pool_names_by_day=pool_names_by_day,
    )
    allow_add = bool(hooks["allow_add"])
    day_spans = {code: build_day_spans(df) for code, df in minute_bars.items()}

    for i, day in enumerate(calendar):
        ds = _ymd(day)
        names = names_asof(ds)
        st.daily_quota_used = 0.0

        bind_opening = hooks.get("bind_opening_held")
        if callable(bind_opening):
            bind_opening(ds, list(st.positions.keys()))

        for code in list(st.positions):
            mdf = minute_bars.get(code)
            ddf = daily_bars.get(code)
            if mdf is None or ddf is None or day not in ddf.index:
                continue
            day_m = _slice_day(mdf, day_spans.get(code, {}), ds)
            if day_m is None:
                continue
            prev_rows = _previous_rows(ddf, day)
            if prev_rows.empty:
                continue
            # E-R6: rescale before scan_held_day; never between scan and peak writeback.
            kk = k_for(exdiv, code, ds)
            if kk is not None:
                for pos in list(st.positions.get(code, [])):
                    rescale_position(pos, kk)
                    st.stats["exdiv_adjusted_lots"] = (
                        int(st.stats.get("exdiv_adjusted_lots", 0)) + 1
                    )
            prev_close, did_map = mapped_prev_close(
                exdiv, code, ds, float(prev_rows.iloc[-1]["close"])
            )
            if did_map:
                st.stats["exdiv_prev_close_mapped"] = (
                    int(st.stats.get("exdiv_prev_close_mapped", 0)) + 1
                )
            limits = _named_limits(code, prev_close, names)
            if limits is None:
                st.stats["skip_unknown_board"] += 1
                continue
            limit_up, limit_down = limits
            o = day_m["open"].to_numpy(np.float64)
            h = day_m["high"].to_numpy(np.float64)
            c = day_m["close"].to_numpy(np.float64)
            hm = day_m["hm"].to_numpy(np.int64)
            for pos in list(st.positions.get(code, [])):
                n_days = i - pos.entry_idx
                reserve_state = {"reserved": bool(pos.reserved)}
                idx, px, reason, new_peak, new_peak_hm = scan_held_day(
                    o,
                    h,
                    c,
                    cost=pos.cost,
                    peak=pos.peak,
                    n_days=n_days,
                    can_sell=(n_days >= 1),
                    stop_pct=stop_pct,
                    profit_base=profit_base if profit_base is not None else 0.0,
                    trail_ratio=0.0,
                    pos_trail=pos_trail,
                    limit_down=limit_down,
                    hm=hm,
                    peak_hm=int(pos.peak_hm),
                    peak_gap_min=peak_gap_min,
                    take_profit=take_profit,
                    sell_gate=sell_gate,
                    gate_code=code,
                    gate_day=day,
                    daily_closes_ending_yesterday=prev_rows["close"].astype(float).tolist(),
                    force_sell_hm=force_sell_hm,
                    reserve_limit_up=reserve_limit_up,
                    limit_up=limit_up,
                    reserved=bool(pos.reserved),
                    reserve_state=reserve_state,
                )
                pos.peak = new_peak
                pos.peak_hm = new_peak_hm
                pos.reserved = bool(reserve_state["reserved"])
                if idx >= 0:
                    fill_open = float(o[idx])
                    if limit_down > 0 and (
                        hit_limit_down(fill_open, limit_down)
                        or hit_limit_down(float(px), limit_down)
                    ):
                        st.stats["defer_sell_limit_down"] += 1
                        continue
                    _sell(st, code, pos, px, day, reason)

        def _chase_quotes_for(code: str):
            mdf = minute_bars.get(code)
            ddf = daily_bars.get(code)
            if mdf is None or ddf is None or day not in ddf.index:
                return None
            day_m = _slice_day(mdf, day_spans.get(code, {}), ds)
            quotes = _chase_quotes(day_m) if day_m is not None else None
            if quotes is None:
                return None
            open_px, px = quotes
            prev_rows = _previous_rows(ddf, day)
            if prev_rows.empty:
                return None
            closes = prev_rows["close"].astype(float).tolist()
            return open_px, px, closes

        run_chase_due_day(
            st,
            pending_chase,
            day_i=i,
            day=day,
            names=names,
            allow_add=allow_add,
            buy_gate=buy_gate,
            quotes_for=_chase_quotes_for,
            exdiv=exdiv,
            ds=ds,
        )

        def _pool_quote_for(code: str):
            mdf = minute_bars.get(code)
            ddf = daily_bars.get(code)
            if mdf is None or ddf is None or day not in ddf.index:
                return None
            day_m = _slice_day(mdf, day_spans.get(code, {}), ds)
            if day_m is None:
                return None
            prev_rows = _previous_rows(ddf, day)
            if prev_rows.empty:
                return None
            px = _buy_px(day_m)
            if px is None or px <= 0:
                return None
            closes = prev_rows["close"].astype(float).tolist()
            return px, closes

        run_pool_buys_day(
            st,
            pending_chase,
            day_i=i,
            day=day,
            ds=ds,
            pool_days=pool_days,
            daily_quota=daily_quota,
            names=names,
            allow_add=allow_add,
            buy_gate=buy_gate,
            buy_quote_for=_pool_quote_for,
            sizing=hooks.get("sizing", "daily_quota"),
            name_budget=hooks.get("name_budget", 1_000_000.0),
            ration=hooks.get("ration", "file_order"),
            ration_seed=hooks.get("ration_seed", 0),
            exdiv=exdiv,
            planned_for_day=hooks.get("planned_for_day"),
        )

        append_equity_and_eod_marks(
            st,
            ds=ds,
            day=day,
            calendar_last=calendar[-1],
            mark_bars=daily_bars,
        )

    finish_pending_chase(st, pending_chase)
    return st


def run(
    start: str,
    end: str,
    *,
    total_cash: float = DEFAULT_TOTAL_CASH,
    daily_quota: float = DEFAULT_DAILY_QUOTA,
    name_budget: Optional[float] = None,
    ration: str = "file_order",
    ration_seed: int = 0,
    stop_pct: Optional[float] = None,
    profit_base: Optional[float] = None,
    tiers: Optional[dict] = None,
    tier_default: Optional[float] = None,
    pos_trail: float = POS_TRAIL,
    workers: int = 16,
    use_cache: bool = True,
    rebuild_cache: bool = False,
    pool_dir: Optional[Path] = None,
    strategy: str,
    take_profit=None,
    record_params=None,
    scores_by_day=None,
    topk=None,
    n_drop=None,
    eligible_buy=None,
) -> SimState:
    warn_stale_period_env()
    if end > MINUTE_LAKE_END:
        print(
            f"[warn] --end {end} past minute lake {MINUTE_LAKE_END}; "
            "bars after that date are missing, use daily engine to reach today",
            flush=True,
        )
    t_pool = time.perf_counter()
    actual_pool_dir = resolve_research_pool_dir(strategy, pool_dir, repo=REPO)
    pool_days = load_pool_day_map(actual_pool_dir, start, end, key="ymd", empty_in_map=False)
    pool_names_by_day = load_pool_names_by_day(actual_pool_dir, start, end)
    t_pool = time.perf_counter() - t_pool
    if not pool_days:
        raise SystemExit(f"no pool CSVs in [{start}, {end}] under {actual_pool_dir}")
    all_codes = {c for codes in pool_days.values() for c in codes}
    load_start = warmup_start(
        start,
        STRATEGY4_CALENDAR_SLACK_DAYS
        if normalize_csv_strategy(strategy) == "version4"
        else WARMUP_DAYS,
    )
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
    skipped: dict[str, int] = {}
    exdiv = load_exdiv_ratios(all_codes, start, end, skipped_out=skipped)
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
        strategy=strategy,
        take_profit=take_profit,
        record_params=record_params,
        name_budget=name_budget,
        ration=ration,
        ration_seed=ration_seed,
        pool_names_by_day=pool_names_by_day,
        exdiv=exdiv,
        scores_by_day=scores_by_day,
        topk=topk,
        n_drop=n_drop,
        eligible_buy=eligible_buy,
    )
    if skipped.get("exdiv_skipped_no_factor"):
        st.stats["exdiv_skipped_no_factor"] = int(skipped["exdiv_skipped_no_factor"])
    st.stats["t_pool_s"] = t_pool
    st.stats["t_daily_s"] = t_daily
    st.stats["t_minute_s"] = t_minute
    st.stats["t_sim_s"] = time.perf_counter() - t_sim
    st.stats["cache"] = cache_status.get("cache", "")
    st.stats["codes_missing"] = max(0, len(all_codes) - min(len(daily), len(minute)))
    return st


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(
        description="CSV-mode vectorized minute backtest (required --strategy)",
        epilog=help_lock_all(HELP_LOCK),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_csv_backtest_common_args(
        ap,
        repo=REPO,
        end_default=MINUTE_LAKE_END,
        end_help=(
            f"minute lake last day is {MINUTE_LAKE_END}; short parity window: 20251104"
        ),
        cash_total_default=DEFAULT_TOTAL_CASH,
        daily_quota_default=DEFAULT_DAILY_QUOTA,
    )
    ap.add_argument("--no-cache", action="store_true", help="skip minute window cache")
    ap.add_argument(
        "--rebuild-cache", action="store_true", help="reload lake and rewrite cache"
    )
    args = ap.parse_args(argv if argv is not None else None)
    pool_dir = resolve_research_pool_dir(args.strategy, args.pool_dir, repo=REPO)

    st = run(
        args.start,
        args.end,
        total_cash=args.cash_total,
        daily_quota=args.daily_quota,
        workers=args.workers,
        pool_dir=pool_dir,
        use_cache=not args.no_cache,
        rebuild_cache=args.rebuild_cache,
        **csv_run_kwargs_from_args(args),
    )
    book = engine_book(args.strategy)
    engine = f"csv_minute_{book}"
    text = summarize(st, args.cash_total, args.start, args.end, engine=engine)
    cmp = maybe_compare_daily(
        st.equity_curve, args.start, args.end, this_label=engine, book=book
    )
    if cmp:
        text = text + "\n" + cmp
    print(text)
    tag = f"{engine}_{args.start}_{args.end}"
    write_run_artifacts(
        Path(REPO) / "backtest_output" / tag,
        st,
        text,
        help_lock_for(args.strategy, shared=HELP_LOCK),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
