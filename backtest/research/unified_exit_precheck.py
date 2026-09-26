# -*- coding: utf-8 -*-
"""Read-only precheck reporter for the unified-exit grid proposal (PR #88).

七项只读检查（docs/backtest/stock-backtest-unified-exit-proposal-2026-09-17.md §9.7）：

1. 名单文件 / 实例数（同日重复码立即报错，停止预检）
2. 交易日历覆盖（名单文件 vs 指数交易日：缺文件 / 多余文件）
3. front 湖覆盖：缺失码、日线早断（退市 / 长停候选）、长无 K 间隙、受冻实例
4. 买入日涨停边界统计（front 收盘 vs 板块幅度，±容差口径）
5. 除权事件分布（k 跳变分层）+ A/B 对账标本候选
6. 各持有期 N 的峰值并发上界（无早退出假设 = 「不设止盈+不设止损」组占用）
7. front 分区指纹（文件数 / 字节 / mtime 跨度 / meta+body sha256）

无任何写路径（湖、名单、引擎全不碰）。分支兼容：优先
``csv_daily_loader.load_index_daily_closes``，未抽取该函数的分支回落
``csv_minute_backtest_v7.load_index_daily``。

CLI: ``scripts/research/report_unified_exit_precheck.py``。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Optional

from backtest.research.csv_pool import PoolDuplicateCodeError, parse_pool_csv_entries
from backtest.research.csv_daily_loader import _read_one_daily, warmup_start
from backtest.research.exdiv_map import load_exdiv_ratios
from backtest.research.market_layer import limit_pct
from common.infra.data_root import resolve_period_root

try:  # loader extraction lands later on some branches
    from backtest.research.csv_daily_loader import load_index_daily_closes
except ImportError:  # pragma: no cover - branch-dependent
    from backtest.research.csv_minute_backtest_v7 import load_index_daily

    def load_index_daily_closes(start: str, end: str, **_kw) -> dict[date, float]:
        return load_index_daily(
            date(int(start[:4]), int(start[4:6]), int(start[6:])),
            date(int(end[:4]), int(end[4:6]), int(end[6:])),
        )


HORIZONS = (1, 2, 3, 5, 8, 10, 15, 20)
DEFAULT_TOL = 0.002  # +/-0.2% band around the board limit ratio (fen rounding)


def _pool_and_calendar(pool_dir: Path, start: str, end: str) -> dict:
    """Count pool instances and calendar coverage; duplicate codes raise."""
    files = sorted(Path(pool_dir).glob("*.csv"))
    per_day: dict[str, list[tuple[str, str]]] = {}
    total_rows = 0
    for f in files:
        entries = parse_pool_csv_entries(f)
        per_day[f.stem] = entries
        total_rows += len(entries)
    closes = load_index_daily_closes(start, end)
    d0, d1 = _ymd_to_date(start), _ymd_to_date(end)
    sess_ymd = [d.strftime("%Y%m%d") for d in sorted(closes) if d0 <= d <= d1]
    return {
        "pool": {
            "files": len(files),
            "raw_rows": total_rows,
            "instances": sum(len(v) for v in per_day.values()),
            "union_codes": len({c for v in per_day.values() for c, _ in v}),
            "per_day_min": min((len(v) for v in per_day.values()), default=0),
            "per_day_max": max((len(v) for v in per_day.values()), default=0),
        },
        "calendar": {
            "sessions": len(sess_ymd),
            "missing_pool_files": [y for y in sess_ymd if y not in per_day],
            "extra_pool_files": sorted(set(per_day) - set(sess_ymd)),
        },
        "_per_day": per_day,
        "_sess_ymd": sess_ymd,
    }


def _ymd_to_date(ymd: str) -> date:
    return date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))


def _front_code_stats(codes, root: Path, start: str, end: str, sess_ymd, workers: int) -> dict:
    warm = warmup_start(start, days=20)

    def one(canon: str):
        df = _read_one_daily(canon, root, warm, end)
        if df is None:
            return None
        win = [d.strftime("%Y%m%d") for d in df.index if d.strftime("%Y%m%d") >= start]
        if not win:
            return {"bars_in_window": 0, "last": None, "max_gap": 0}
        present = set(win)
        gaps, run = [], 0
        for y in sess_ymd:
            if y in present:
                if run:
                    gaps.append(run)
                run = 0
            else:
                run += 1
        if run:
            gaps.append(run)
        return {"bars_in_window": len(win), "last": win[-1], "max_gap": max(gaps) if gaps else 0}

    stats: dict[str, Optional[dict]] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for canon, s in ex.map(lambda c: (c, one(c)), codes):
            stats[canon] = s
    return stats


def _front_coverage(per_day, stats, end: str) -> dict:
    early_stop = sorted(
        ((c, s["last"], s["bars_in_window"]) for c, s in stats.items()
         if s and s.get("last") and s["last"] < end),
        key=lambda x: x[1],
    )
    return {
        "missing_codes": [c for c, s in stats.items() if s is None],
        "early_stop_codes": early_stop,
        "gap_ge10_count": sum(1 for s in stats.values() if s and s.get("max_gap", 0) >= 10),
        "gap_ge10_top": sorted(((c, s["max_gap"]) for c, s in stats.items()
                                if s and s.get("max_gap", 0) >= 10), key=lambda x: -x[1])[:20],
        "frozen_instances": sum(1 for y, v in per_day.items() for c, _ in v
                                if stats.get(c) and stats[c].get("last") and stats[c]["last"] < end
                                and y <= stats[c]["last"]),
        "no_bar_buyday_instances": sum(1 for y, v in per_day.items() for c, _ in v
                                       if stats.get(c) is None
                                       or stats[c]["bars_in_window"] == 0
                                       or (stats[c].get("last") and y > stats[c]["last"])),
    }


def _limit_boundary(per_day, stats_codes, root: Path, start: str, end: str, tol: float,
                    workers: int) -> dict:
    warm = warmup_start(start, days=20)

    def one(canon: str):
        df = _read_one_daily(canon, root, warm, end)
        if df is None or len(df) < 2:
            return canon, {}
        pct = (df["close"] / df["close"].shift(1) - 1.0).dropna()
        return canon, {d.strftime("%Y%m%d"): p for d, p in pct.items()}

    lim: dict[str, dict[str, float]] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for canon, m in ex.map(one, stats_codes):
            if m:
                lim[canon] = m
    cnt: Counter = Counter()
    for y, v in per_day.items():
        for c, n in v:
            p = lim.get(c, {}).get(y)
            if p is None:
                continue
            lp = limit_pct(c, n)
            if lp is None:
                cnt["unknown_board"] += 1
            elif p >= lp + tol:
                cnt["way_above_limit"] += 1  # new-listing style / data anomaly
            elif p >= lp - tol:
                cnt["limit_up_close_skip_buy"] += 1
            elif p >= lp - 3 * tol:
                cnt["boundary_band"] += 1
            if lp is not None and p <= -(lp - tol):
                cnt["limit_down_close"] += 1
    return dict(cnt)


def _exdiv_and_specimens(per_day, union, start: str, end: str) -> dict:
    ratios = load_exdiv_ratios(set(union), start, end)
    events = [(c, ymd, k) for c, m in ratios.items() for ymd, k in m.items()]
    jumps_desc = sorted(events, key=lambda x: -abs(1 - x[2]))
    inst_by_code = Counter(c for v in per_day.values() for c, _ in v)
    name_of: dict[str, str] = {}
    for v in per_day.values():
        for c, n in v:
            name_of.setdefault(c, n)
    plain = sorted((c for c in union if not ratios.get(c)), key=lambda c: -inst_by_code[c])[:12]
    return {
        "events": len(events),
        "codes_with_events": len({e[0] for e in events}),
        "gt5pct": sum(1 for e in events if abs(1 - e[2]) > 0.05),
        "mid_0p5_5pct": sum(1 for e in events if 0.005 < abs(1 - e[2]) <= 0.05),
        "le0p5pct_noise": sum(1 for e in events if abs(1 - e[2]) <= 0.005),
        "specimen_big": [(c, y, round(k, 4)) for c, y, k in jumps_desc[:12]],
        "specimen_mid": [(c, y, round(k, 4)) for c, y, k in jumps_desc
                         if 0.005 < abs(1 - k) <= 0.05][:12],
        "specimen_plain": [(c, name_of.get(c, ""), inst_by_code[c]) for c in plain],
    }


def _concurrency(per_day, sess_ymd, horizons) -> list[dict]:
    per_day_n = [len(per_day.get(y, [])) for y in sess_ymd]
    rows = []
    for n in horizons:
        peak = max(sum(per_day_n[i - n + 1: i + 1]) for i in range(len(per_day_n)))
        rows.append({"N": n, "peak_lots": peak, "peak_capital_yi": round(peak / 100.0, 2)})
    return rows


def _fingerprint(root: Path) -> dict:
    h_meta = hashlib.sha256()
    h_body = hashlib.sha256()
    n_files = total_b = 0
    mt_min = mt_max = None
    for p in sorted(root.rglob("*.parquet")):
        st = p.stat()
        n_files += 1
        total_b += st.st_size
        mt = int(st.st_mtime)
        mt_min = mt if mt_min is None else min(mt_min, mt)
        mt_max = mt if mt_max is None else max(mt_max, mt)
        h_meta.update(f"{p.relative_to(root).as_posix()}|{st.st_size}|{mt}\n".encode())
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h_body.update(chunk)
    return {
        "files": n_files,
        "bytes": total_b,
        "mtime_min": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mt_min)) if mt_min else None,
        "mtime_max": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mt_max)) if mt_max else None,
        "meta_sha256": h_meta.hexdigest(),
        "body_sha256": h_body.hexdigest(),
    }


def run_precheck(
    start: str,
    end: str,
    *,
    pool_dir: Path,
    front_root: Optional[Path] = None,
    tol: float = DEFAULT_TOL,
    horizons=HORIZONS,
    workers: int = 12,
) -> dict:
    """Run all checks, raising on duplicate pool codes before lake access."""
    out: dict = {}
    base = _pool_and_calendar(Path(pool_dir), start, end)
    per_day, sess_ymd = base.pop("_per_day"), base.pop("_sess_ymd")
    out.update(base)

    root = front_root or (resolve_period_root("1d") / "dividend_type=front")
    union = sorted({c for v in per_day.values() for c, _ in v})

    t0 = time.time()
    stats = _front_code_stats(union, root, start, end, sess_ymd, workers)
    out["front"] = _front_coverage(per_day, stats, end)
    out["front"]["elapsed_s"] = round(time.time() - t0, 1)

    t0 = time.time()
    out["limit"] = _limit_boundary(per_day, union, root, start, end, tol, workers)
    out["limit"]["tol"] = tol

    t0 = time.time()
    out["exdiv"] = _exdiv_and_specimens(per_day, union, start, end)
    out["exdiv"]["elapsed_s"] = round(time.time() - t0, 1)

    out["concurrency"] = _concurrency(per_day, sess_ymd, horizons)

    t0 = time.time()
    out["fingerprint"] = _fingerprint(root)
    out["fingerprint"]["elapsed_s"] = round(time.time() - t0, 1)
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="read-only unified-exit precheck reporter")
    ap.add_argument("--start", default="20251023")
    ap.add_argument("--end", default="20260909")
    ap.add_argument("--pool-dir", type=Path, default=Path("stock_pool"))
    ap.add_argument("--tol", type=float, default=DEFAULT_TOL)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out-json", type=Path, default=Path("backtest_output/unified_exit_precheck.json"))
    args = ap.parse_args(argv)

    try:
        report = run_precheck(args.start, args.end, pool_dir=args.pool_dir, tol=args.tol, workers=args.workers)
    except PoolDuplicateCodeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, ensure_ascii=True, indent=1, default=str), encoding="utf-8")

    p, cal, fr = report["pool"], report["calendar"], report["front"]
    print(f"[pool] files={p['files']} rows={p['raw_rows']} instances={p['instances']} "
          f"union={p['union_codes']}")
    print(f"[cal] sessions={cal['sessions']} missing_pool_files={cal['missing_pool_files']} "
          f"extra={cal['extra_pool_files']}")
    print(f"[front] missing={len(fr['missing_codes'])} early_stop={len(fr['early_stop_codes'])} "
          f"gap>=10:{fr['gap_ge10_count']} frozen_inst={fr['frozen_instances']} "
          f"no_bar_buy={fr['no_bar_buyday_instances']}")
    print(f"[limit] {report['limit']}")
    ex = report["exdiv"]
    print(f"[exdiv] events={ex['events']} codes={ex['codes_with_events']} "
          f">5%:{ex['gt5pct']} 0.5-5%:{ex['mid_0p5_5pct']} <=0.5%:{ex['le0p5pct_noise']}")
    print("[conc] " + "; ".join(f"N={r['N']}:{r['peak_lots']}({r['peak_capital_yi']}yi)"
                                for r in report["concurrency"]))
    fp = report["fingerprint"]
    print(f"[fp] files={fp['files']} bytes={fp['bytes']/1e6:.0f}MB mtime[{fp['mtime_min']} .. {fp['mtime_max']}]")
    print(f"[fp] meta_sha256={fp['meta_sha256']}")
    print(f"[fp] body_sha256={fp['body_sha256']}")
    print(f"[done] json -> {args.out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
