#!/usr/bin/env python3
"""Strategy 9: 10-trading-day force-close PnL with peak capital occupancy.

Previous ``s9_s10_signal_10d_range`` ``gain_pct`` was **peak high / signal close**
inside the window (unrealized max excursion), not realized exit PnL.

This script:

- each pool signal (date, code) = one lot of ``--notional`` (default 1_000_000)
- entry = signal-day close (front adj)
- exit = close of the ``--horizon``-th trading day **after** signal day
  (signal day excluded; same window as the 10d range script)
- capital occupied = notional from entry day through exit day (inclusive)
- peak capital = max daily sum of open notionals
- strategy return = total PnL / peak capital

Never writes ``stock_pool/``.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.source_b_tr_pool import normalize_stock_code  # noqa: E402
from common.infra.data_root import resolve_period_root  # noqa: E402
from scripts.data.export_strategy9_pool import load_daily_ohlcv  # noqa: E402
from scripts.research.s10_signal_peak_gains import load_pool_days  # noqa: E402
from scripts.research.s9_s10_signal_10d_range import _ohlcv_end  # noqa: E402
from scripts.research.s9_signal_peak_gains import _bare, _ymd  # noqa: E402


def build_lots(
    days: dict[str, list[str]],
    frames: dict[str, pd.DataFrame],
    *,
    horizon: int,
    notional: float,
    no_add: bool = True,
) -> tuple[list[dict[str, Any]], int]:
    """Build force-close lots.

    ``no_add=True`` (原书): skip a signal while the same code still has an open
    lot (entry through exit date inclusive). Returns (lots, n_skipped_no_add).
    """
    lots: list[dict[str, Any]] = []
    held_until: dict[str, str] = {}
    n_skipped_no_add = 0
    for ymd in sorted(days):
        day = pd.Timestamp(ymd)
        # stable order within a day
        for code in sorted(days[ymd], key=lambda c: normalize_stock_code(c) or c):
            canon = normalize_stock_code(code)
            if not canon:
                continue
            bare = _bare(canon)
            if no_add and bare in held_until and ymd <= held_until[bare]:
                n_skipped_no_add += 1
                continue
            frame = frames.get(canon)
            if frame is None or frame.empty or day not in frame.index:
                continue
            loc = frame.index.get_loc(day)
            i = int(loc.stop - 1) if isinstance(loc, slice) else int(loc)
            entry = float(frame["close"].iloc[i])
            if not np.isfinite(entry) or entry <= 0:
                continue
            exit_i = i + int(horizon)
            if exit_i >= len(frame):
                # incomplete horizon: skip (fail-closed for force-close study)
                continue
            exit_px = float(frame["close"].iloc[exit_i])
            if not np.isfinite(exit_px) or exit_px <= 0:
                continue
            exit_ymd = _ymd(frame.index[exit_i])
            ret = exit_px / entry - 1.0
            pnl = float(notional) * ret
            lots.append(
                {
                    "code": bare,
                    "canonical": canon,
                    "signal_date": ymd,
                    "exit_date": exit_ymd,
                    "entry_close": round(entry, 4),
                    "exit_close": round(exit_px, 4),
                    "ret_pct": round(ret * 100.0, 2),
                    "notional": float(notional),
                    "pnl": round(pnl, 2),
                    "horizon": int(horizon),
                }
            )
            if no_add:
                held_until[bare] = exit_ymd
    return lots, n_skipped_no_add


def peak_capital_and_curve(
    lots: list[dict[str, Any]],
    frames: dict[str, pd.DataFrame],
) -> tuple[float, str, pd.DataFrame]:
    """Return (peak_capital, peak_ymd, daily occupancy frame).

    Occupancy counts each lot's notional on actual trading days in that
    name's frame from entry through exit (inclusive).
    """
    occ: dict[str, float] = defaultdict(float)
    for lot in lots:
        n = float(lot["notional"])
        frame = frames.get(str(lot["canonical"]))
        if frame is None or frame.empty:
            continue
        t0 = pd.Timestamp(lot["signal_date"])
        t1 = pd.Timestamp(lot["exit_date"])
        for ts in frame.index[(frame.index >= t0) & (frame.index <= t1)]:
            occ[_ymd(ts)] += n
    if not occ:
        return 0.0, "", pd.DataFrame(columns=["date", "capital"])
    peak_ymd = max(occ.items(), key=lambda kv: (kv[1], kv[0]))[0]
    peak = float(occ[peak_ymd])
    curve = pd.DataFrame(
        [{"date": d, "capital": round(c, 2)} for d, c in sorted(occ.items())]
    )
    return peak, peak_ymd, curve


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "s9 10-day force-close PnL: per-signal notional, "
            "return = total_pnl / peak_capital"
        )
    )
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--pool-dir", type=Path, required=True)
    ap.add_argument("--horizon", type=int, default=10)
    ap.add_argument(
        "--notional",
        type=float,
        default=1_000_000.0,
        help="CNY per signal lot (default 1e6)",
    )
    ap.add_argument(
        "--allow-add",
        action="store_true",
        default=False,
        help="允许同码叠仓（默认关=原书已持同码不加仓）",
    )
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args(argv if argv is not None else None)

    if int(args.horizon) <= 0:
        raise SystemExit("--horizon must be > 0")
    out_dir = Path(args.out_dir) if args.out_dir is not None else REPO_ROOT / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    days = load_pool_days(Path(args.pool_dir), args.start, args.end)
    print(
        f"pool days={len(days)} name-days={sum(len(v) for v in days.values())}",
        flush=True,
    )
    codes = sorted(
        {
            normalize_stock_code(c)
            for cs in days.values()
            for c in cs
            if normalize_stock_code(c)
        }
    )
    ohlcv_end = _ohlcv_end(args.end, args.horizon)
    lake = resolve_period_root("1d") / "dividend_type=front"
    print(f"load {len(codes)} codes {args.start}..{ohlcv_end}", flush=True)
    frames = load_daily_ohlcv(
        codes, args.start, ohlcv_end, root=lake, workers=args.workers
    )

    no_add = not bool(args.allow_add)
    lots, n_skipped_no_add = build_lots(
        days,
        frames,
        horizon=args.horizon,
        notional=float(args.notional),
        no_add=no_add,
    )
    n_pool = int(sum(len(v) for v in days.values()))
    incomplete = n_pool - len(lots) - int(n_skipped_no_add)
    peak, peak_ymd, curve = peak_capital_and_curve(lots, frames)
    total_pnl = float(sum(float(x["pnl"]) for x in lots))
    wins = sum(1 for x in lots if float(x["pnl"]) > 0)
    losses = sum(1 for x in lots if float(x["pnl"]) < 0)
    flats = len(lots) - wins - losses
    ret_on_peak = (total_pnl / peak) if peak > 0 else float("nan")
    n_names_peak = 0
    if peak_ymd and lots:
        n_names_peak = len(
            {
                x["code"]
                for x in lots
                if str(x["signal_date"]) <= peak_ymd <= str(x["exit_date"])
            }
        )

    mode = "noadd" if no_add else "stack"
    tag = f"{args.start}_{args.end}_h{args.horizon}_{mode}"
    lots_sorted = sorted(
        lots, key=lambda x: (-float(x["ret_pct"]), x["code"], x["signal_date"])
    )
    lots_path = out_dir / f"s9_force10d_lots_{tag}.csv"
    summary_path = out_dir / f"s9_force10d_summary_{tag}.csv"
    curve_path = out_dir / f"s9_force10d_capital_{tag}.csv"
    pd.DataFrame(lots_sorted).to_csv(
        lots_path, index=False, encoding="utf-8", lineterminator="\n"
    )
    curve.to_csv(curve_path, index=False, encoding="utf-8", lineterminator="\n")
    summary = {
        "start": args.start,
        "end": args.end,
        "horizon": int(args.horizon),
        "notional_per_lot": float(args.notional),
        "no_add": bool(no_add),
        "n_signals_pool": n_pool,
        "n_lots": len(lots),
        "n_skipped_no_add": int(n_skipped_no_add),
        "n_incomplete_skipped": int(incomplete),
        "n_win": wins,
        "n_loss": losses,
        "n_flat": flats,
        "win_rate_pct": round(100.0 * wins / len(lots), 2) if lots else float("nan"),
        "total_pnl": round(total_pnl, 2),
        "peak_capital": round(peak, 2),
        "peak_capital_date": peak_ymd,
        "peak_open_names": int(n_names_peak),
        "return_on_peak_pct": round(ret_on_peak * 100.0, 2) if peak > 0 else float("nan"),
        "avg_ret_pct": round(
            float(np.mean([float(x["ret_pct"]) for x in lots])), 2
        )
        if lots
        else float("nan"),
    }
    pd.DataFrame([summary]).to_csv(
        summary_path, index=False, encoding="utf-8", lineterminator="\n"
    )

    print("=== 口径说明 ===", flush=True)
    print(
        "此前 range 表「涨幅%」= 信号后N日内最高价/信号收盘-1（浮动峰值，非卖出价）。",
        flush=True,
    )
    add_txt = (
        "已持同码不加仓（持仓期含强平日）"
        if no_add
        else "允许同码信号叠仓"
    )
    print(
        f"本脚本：信号收盘买入，第{args.horizon}个交易日收盘强平；"
        f"每笔名义 {args.notional:,.0f}；{add_txt}；"
        "峰值资金=任一交易日未平仓笔数×名义金额之和。",
        flush=True,
    )
    print("=== 汇总 ===", flush=True)
    for k, v in summary.items():
        print(f"  {k}: {v}", flush=True)
    print(f"lots -> {lots_path}", flush=True)
    print(f"summary -> {summary_path}", flush=True)
    print(f"capital curve -> {curve_path}", flush=True)

    print("=== 单笔收益前若干（按强平收益率） ===", flush=True)
    show = pd.DataFrame(lots_sorted[: int(args.top)])
    if not show.empty:
        show.insert(0, "排名", range(1, len(show) + 1))
        show = show.rename(
            columns={
                "code": "代码",
                "signal_date": "信号日",
                "exit_date": "强平日",
                "entry_close": "买入收盘",
                "exit_close": "卖出收盘",
                "ret_pct": "收益率%",
                "pnl": "盈亏(元)",
            }
        )
        cols = [
            "排名",
            "代码",
            "信号日",
            "强平日",
            "买入收盘",
            "卖出收盘",
            "收益率%",
            "盈亏(元)",
        ]
        print(show[cols].to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
