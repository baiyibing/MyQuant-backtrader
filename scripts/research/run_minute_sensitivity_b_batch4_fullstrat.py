#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch4 full-strategy NAV/DD/rank harness (research-only, read-only).

Fills (where honest) Book / v7 / Mode B portfolio NAV, return, max drawdown and
within-engine rank that batch1–3 left as DATA_GAP. Does **not** change production
fill/scan/fee/default clock.

VM-safe defaults: ``--dry-run`` / ``--emit-stubs`` / ``--help`` need no lake.
``--execute`` is for 4090 (qlib_1min + pool). One axis at a time: clock XOR slip;
explicit research hooks implement H2 + Q2; numerical cells await 4090.

See:
  docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DEFAULT_QLIB_1MIN_ROOT = Path(r"C:\Users\wangc\.qlib\qlib_data\my_data_1min")
DEFAULT_START = "20260825"
DEFAULT_END = "20260909"
DEFAULT_OUT = (
    REPO
    / "backtest"
    / "research"
    / "exports"
    / "minute_sensitivity_b_20260920"
    / "batch4_fullstrat"
)
FEE_SCHEDULE = "DEFAULT_SCHEDULE=BILATERAL_10BP"
CLOCK_DEFAULT = "production_default"
BAR_LABEL = "lake_index_is_bar_start_wallclock"
BOOK_STRATEGIES = (
    "version1",
    "version2",
    "version3",
    "version4",
    "version5",
    "version6",
    "version8",
    "version9",
    "version10",
)

MATRIX_CELLS = (
    {
        "cell_id": "baseline_default_clock_fee",
        "clock": CLOCK_DEFAULT,
        "slip_bp_per_side": 0,
        "book": "FILLABLE",
        "v7": "FILLABLE",
        "modeb": "FILLABLE",
        "note": "default clock + DEFAULT_SCHEDULE; honest fullstrat NAV",
    },
    {
        "cell_id": "clock_next_open_fullstrat",
        "clock": "next_tradable_open_research",
        "slip_bp_per_side": 0,
        "book": "FILLABLE",
        "v7": "FILLABLE",
        "modeb": "FILLABLE",
        "note": "H2 all fills; same-day expiry; Q2 fill-price sizing; await post-merge 4090",
    },
    {
        "cell_id": "slip_5bp_fullstrat",
        "clock": CLOCK_DEFAULT,
        "slip_bp_per_side": 5,
        "book": "FILLABLE",
        "v7": "FILLABLE",
        "modeb": "FILLABLE",
        "note": "Q2 fill-price sizing; post-impact fees; await post-merge 4090",
    },
    {
        "cell_id": "slip_10bp_fullstrat",
        "clock": CLOCK_DEFAULT,
        "slip_bp_per_side": 10,
        "book": "FILLABLE",
        "v7": "FILLABLE",
        "modeb": "FILLABLE",
        "note": "Q2 fill-price sizing; post-impact fees; await post-merge 4090",
    },
    {
        "cell_id": "slip_20bp_fullstrat",
        "clock": CLOCK_DEFAULT,
        "slip_bp_per_side": 20,
        "book": "FILLABLE",
        "v7": "FILLABLE",
        "modeb": "FILLABLE",
        "note": "Q2 fill-price sizing; post-impact fees; await post-merge 4090",
    },
)

GAP = ""


def _py() -> str:
    return sys.executable


def _ensure_new_or_empty(out_dir: Path, *, allow_existing: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if allow_existing:
        return
    occupied = [p for p in out_dir.iterdir() if p.name != "README.md"]
    # stubs from emit are ok to refresh only when --force
    if occupied:
        raise SystemExit(
            f"refuse overwrite existing {out_dir}; pass --force or pick a new stamp directory"
        )


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, GAP) for k in fieldnames})


def blank_nav_row(**kwargs: Any) -> dict[str, Any]:
    base = {
        "engine": GAP,
        "strategy": GAP,
        "cell_id": "baseline_default_clock_fee",
        "clock": CLOCK_DEFAULT,
        "slip_bp_per_side": 0,
        "fee_schedule": FEE_SCHEDULE,
        "start": DEFAULT_START,
        "end": DEFAULT_END,
        "access": "qlib_bin_1min",
        "bar_label_semantics": BAR_LABEL,
        "daily_entry_source": GAP,
        "final_equity": GAP,
        "total_return": GAP,
        "max_drawdown": GAP,
        "within_engine_rank": GAP,
        "status": "DATA_GAP",
        "artifact_dir": GAP,
        "note": GAP,
    }
    base.update(kwargs)
    return base


def matrix_rows() -> list[dict[str, Any]]:
    rows = []
    for cell in MATRIX_CELLS:
        for engine, key in (("Book", "book"), ("v7", "v7"), ("ModeB", "modeb")):
            rows.append(
                {
                    "cell_id": cell["cell_id"],
                    "engine": engine,
                    "clock": cell["clock"],
                    "slip_bp_per_side": cell["slip_bp_per_side"],
                    "fee_schedule": FEE_SCHEDULE,
                    "fill_status": cell[key],
                    "nav": GAP,
                    "total_return": GAP,
                    "max_drawdown": GAP,
                    "within_engine_rank": GAP,
                    "note": cell["note"],
                }
            )
    return rows


def data_gap_rows(start: str, end: str) -> list[dict[str, Any]]:
    return [
        {
            "item": "fullstrat_clock_swap",
            "status": "DATA_GAP",
            "evidence": "H2 + Q2 hook FILLABLE; numerical results await post-merge 4090",
        },
        {
            "item": "fullstrat_slip_axis",
            "status": "DATA_GAP",
            "evidence": "Q2 slip hook FILLABLE; numerical results await post-merge 4090",
        },
        {
            "item": "cross_engine_nav_superiority",
            "status": "FORBIDDEN",
            "evidence": "Book/v7/ModeB reported in separate columns only",
        },
        {
            "item": "batch2_local_event_bp_as_portfolio_nav",
            "status": "FORBIDDEN",
            "evidence": "local-only deltas remain local-only",
        },
        {
            "item": "qlib_my_data_day_bin_modeb_entry",
            "status": "DATA_GAP",
            "evidence": "Mode B entry must be aggregated_from_1min_none_lineage",
        },
        {
            "item": "stock_pool_publish_time",
            "status": "DATA_GAP",
            "evidence": "pool CSV has code/name only; filename date not availability proof",
        },
        {
            "item": "window_vs_batch2",
            "status": "PROPOSED",
            "evidence": f"expanded {start}..{end} (pool∩MINUTE_LAKE_END); batch2 was 20260916..18×5 symbols",
        },
    ]


def emit_stubs(out_dir: Path, *, start: str, end: str, force: bool) -> dict[str, Any]:
    if out_dir.exists() and any(out_dir.iterdir()) and not force:
        # allow writing alongside README only
        others = [p for p in out_dir.iterdir() if p.name != "README.md"]
        if others:
            raise SystemExit(
                f"refuse overwrite existing {out_dir}; pass --force or new --output-dir"
            )
    out_dir.mkdir(parents=True, exist_ok=True)

    book_rows = [
        blank_nav_row(
            engine="Book",
            strategy=s,
            start=start,
            end=end,
            daily_entry_source="n/a_book_pool_day_close_chase",
            note="await_4090_default_clock_run",
        )
        for s in BOOK_STRATEGIES
    ]
    v7_rows = [
        blank_nav_row(
            engine="v7",
            strategy="strategy7",
            start=start,
            end=end,
            within_engine_rank=GAP,
            daily_entry_source="n/a_v7_turtle",
            note="await_4090_default_clock_run",
        )
    ]
    modeb_rows = [
        blank_nav_row(
            engine="ModeB",
            strategy="grid_top_or_r2_x5_y5_n10",
            start=start,
            end=end,
            daily_entry_source="aggregated_from_1min_none_lineage",
            note="await_4090_library_path_1min_aggregate_entry",
        )
    ]

    nav_fields = list(blank_nav_row().keys())
    write_csv(out_dir / "book_nav.csv", book_rows, nav_fields)
    write_csv(out_dir / "v7_nav.csv", v7_rows, nav_fields)
    write_csv(out_dir / "modeb_nav.csv", modeb_rows, nav_fields)
    write_csv(
        out_dir / "matrix.csv",
        matrix_rows(),
        [
            "cell_id",
            "engine",
            "clock",
            "slip_bp_per_side",
            "fee_schedule",
            "fill_status",
            "nav",
            "total_return",
            "max_drawdown",
            "within_engine_rank",
            "note",
        ],
    )
    write_csv(
        out_dir / "data_gaps.csv",
        data_gap_rows(start, end),
        ["item", "status", "evidence"],
    )

    recipes = {
        "qlib_1min_root": str(DEFAULT_QLIB_1MIN_ROOT),
        "lake_parquet": os.environ.get(
            "OSKH_SOURCE_PARQUET_ROOT", "<OSKH_SOURCE_PARQUET_ROOT>"
        ),
        "book_example": [
            "python backtest/research/csv_minute_backtest.py",
            "--strategy version1",
            f"--start {start}",
            f"--end {end}",
            "--minute-source qlib_1min",
            "--qlib-1min-root <QLIB_1MIN_ROOT>",
            "--pool-dir stock_pool",
            "--out-dir backtest_output/batch4_book_v1_<stamp>",
        ],
        "v7_example": [
            "python backtest/research/csv_minute_backtest_v7.py",
            f"--start {start}",
            f"--end {end}",
            "--pool-dir stock_pool",
            "--minute-source qlib_1min",
            "--qlib-1min-root <QLIB_1MIN_ROOT>",
            "--output-dir backtest_output/batch4_v7_<stamp>",
        ],
        "modeb_note": (
            "Prefer harness --execute --engines modeb (library inject aggregated "
            "1min none entry). Raw run_unified_exit_modeb.py --none-root may use "
            "lake none daily; do not use qlib day.bin 后复权 for entry."
        ),
        "harness_execute": [
            "python scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py",
            "--execute",
            f"--start {start}",
            f"--end {end}",
            "--qlib-1min-root <QLIB_1MIN_ROOT>",
            "--pool-dir stock_pool",
            "--output-dir backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat",
            "--force",
        ],
    }
    (out_dir / "recipes.json").write_text(
        json.dumps(recipes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    manifest = {
        "batch": 4,
        "mode": "fullstrat",
        "status": "STUB_AWAITING_4090",
        "base_tip": "32b78b1",
        "research_contract": {
            "sizing": "Q2",
            "clock_coverage": "H2_all_fills",
            "expiry": "same_day",
            "sell_expiry": "next_session_reevaluate",
        },
        "production_C": "frozen",
        "fee_schedule": FEE_SCHEDULE,
        "bar_label_semantics": BAR_LABEL,
        "access_preference": "qlib_bin_1min_then_oskh_parquet_1m",
        "date_window": {"start": start, "end": end, "format": "YYYYMMDD"},
        "vs_batch2": "expanded days+pool_union vs 3d×5 symbols; batch2 window lacked pool CSVs",
        "matrix": MATRIX_CELLS,
        "separate_engines": True,
        "forbid_cross_engine_nav_rank": True,
        "local_event_bp_into_nav": "FORBIDDEN",
        "book_strategies": list(BOOK_STRATEGIES),
        "modeb_daily_entry_source": "aggregated_from_1min_none_lineage",
        "emitted_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_head": _git_head(),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_readme(out_dir)
    return manifest


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "UNKNOWN"


def _write_readme(out_dir: Path) -> None:
    text = """# batch4_fullstrat · 全策略 NAV / DD / 引擎内排名

只读研究导出。数值由 4090 在 `--execute` 后填入；VM 仅 stubs / DATA_GAP。

- 设计：`docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md`
- 结果桩：`docs/backtest/reviews/results-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md`
- Book / v7 / Mode B **分列**；禁止跨引擎优劣表
- clock 交换与 slip 全策略轴：**FILLABLE**（H2 + Q2；新增数值待合并后 4090）
- 费用：`DEFAULT_SCHEDULE` / Mode B 双边 10bp；单轴矩阵见 `matrix.csv`
"""
    (out_dir / "README.md").write_text(text, encoding="utf-8")


def parse_book_summary(text: str) -> dict[str, Any]:
    """Parse csv_artifacts.summarize Chinese lines."""
    out: dict[str, Any] = {}
    m = re.search(r"期末净值:\s*([0-9,]+\.?[0-9]*)\s*/", text)
    if m:
        out["final_equity"] = float(m.group(1).replace(",", ""))
    m = re.search(r"总收益率\(全资金\):\s*([+-]?[0-9.]+)%", text)
    if m:
        out["total_return"] = float(m.group(1)) / 100.0
    m = re.search(r"最大回撤:\s*([+-]?[0-9.]+)%", text)
    if m:
        out["max_drawdown"] = float(m.group(1)) / 100.0
    return out


def parse_v7_summary(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    m = re.search(r"final_equity=([0-9.]+)", text)
    if m:
        out["final_equity"] = float(m.group(1))
    m = re.search(r"return=([+-]?[0-9.]+)%", text)
    if m:
        out["total_return"] = float(m.group(1)) / 100.0
    m = re.search(r"max_dd=([+-]?[0-9.]+)%", text)
    if m:
        out["max_drawdown"] = float(m.group(1)) / 100.0
    return out


def metrics_from_daily_equity(
    path: Path, *, initial_cash: Optional[float] = None
) -> dict[str, Any]:
    if not path.is_file():
        return {}
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if not rows:
        return {}
    equities = [float(r["equity"]) for r in rows if r.get("equity") not in (None, "")]
    if not equities:
        return {}
    start_eq = float(initial_cash) if initial_cash is not None else equities[0]
    final = equities[-1]
    peak = start_eq
    max_dd = 0.0
    for value in equities:
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, value / peak - 1.0)
    return {
        "final_equity": final,
        "total_return": (final / start_eq - 1.0) if start_eq else None,
        "max_drawdown": max_dd,
    }


def rank_within(rows: list[dict[str, Any]], *, key: str = "total_return") -> None:
    scored = []
    for i, row in enumerate(rows):
        val = row.get(key)
        if val in (None, GAP, "") or row.get("status") != "OK":
            row["within_engine_rank"] = GAP
            continue
        scored.append((i, float(val)))
    scored.sort(key=lambda t: t[1], reverse=True)
    for rank, (i, _) in enumerate(scored, start=1):
        rows[i]["within_engine_rank"] = rank


def _run_research_portfolio(
    engine, strategy, *, start, end, pool_dir, qlib_root, work_root, config
):
    """Fresh experimental artifacts with full-precision cash/equity metrics."""
    out_dir = work_root / f"{engine.lower()}_{strategy}_{start}_{end}"
    row = blank_nav_row(
        engine=engine,
        strategy=strategy,
        start=start,
        end=end,
        clock=config.clock_mode,
        slip_bp_per_side=config.slip_bp_per_side,
        artifact_dir=str(out_dir),
        daily_entry_source="n/a_book_pool_day_close_chase"
        if engine == "Book"
        else "n/a_v7_turtle",
    )
    try:
        from backtest.research.fullstrat_research_runners import (
            run_book_data,
            run_v7_data,
        )

        if out_dir.exists() and any(out_dir.iterdir()):
            raise ValueError(f"refuse reusing experimental artifacts: {out_dir}")
        common = dict(
            start=start,
            end=end,
            pool_dir=pool_dir,
            clock_mode=config.clock_mode,
            slip_bp_per_side=config.slip_bp_per_side,
        )
        if engine == "Book":
            state = run_book_data(
                strategy=strategy,
                minute_source="qlib_1min",
                qlib_1min_root=qlib_root,
                **common,
            )
            equity = [dict(date=d, equity=value) for d, value in state.equity_curve]
        else:
            state = run_v7_data(qlib_root=qlib_root, **common)
            equity = state.equity_curve
        if not equity:
            raise ValueError("empty session calendar; cannot infer NAV")
        out_dir.mkdir(parents=True, exist_ok=True)
        write_csv(out_dir / "daily_equity.csv", equity, list(equity[0]))
        fields = list(dict.fromkeys(k for t in state.trades for k in t)) or [
            "date",
            "side",
            "price",
            "shares",
        ]
        write_csv(out_dir / "trades.csv", state.trades, fields)
        (out_dir / "research_orders.json").write_text(
            json.dumps(state.research_orders, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        row.update(
            metrics_from_daily_equity(
                out_dir / "daily_equity.csv", initial_cash=state.research_initial_cash
            )
        )
        row.update(
            status="OK",
            note="H2_Q2_research_replay; UNFILLED and all-cash NAV valid",
            within_engine_rank=1 if engine == "v7" else GAP,
        )
    except Exception as exc:
        row.update(status="DATA_GAP", note=f"research_run_failed:{exc}")
    return row


def run_book(
    strategy: str,
    *,
    start: str,
    end: str,
    pool_dir: Path,
    qlib_root: Path,
    work_root: Path,
    clock_mode: str = CLOCK_DEFAULT,
    slip_bp_per_side: int = 0,
) -> dict[str, Any]:
    from backtest.research.fullstrat_research_hooks import ResearchFillConfig

    config = ResearchFillConfig(clock_mode, slip_bp_per_side)
    if not config.baseline:
        return _run_research_portfolio(
            "Book",
            strategy,
            start=start,
            end=end,
            pool_dir=pool_dir,
            qlib_root=qlib_root,
            work_root=work_root,
            config=config,
        )

    out_dir = work_root / f"book_{strategy}_{start}_{end}"
    if out_dir.exists() and any(out_dir.iterdir()):
        # reuse parsed artifacts if present
        summary = out_dir / "summary.txt"
        equity = out_dir / "daily_equity.csv"
        parsed = (
            parse_book_summary(summary.read_text(encoding="utf-8"))
            if summary.is_file()
            else {}
        )
        if not parsed:
            parsed = metrics_from_daily_equity(equity)
        row = blank_nav_row(
            engine="Book",
            strategy=strategy,
            start=start,
            end=end,
            artifact_dir=str(out_dir),
            status="OK" if parsed else "DATA_GAP",
            note="reused_existing_artifact" if parsed else "empty_artifact",
            daily_entry_source="n/a_book_pool_day_close_chase",
        )
        row.update(
            {
                k: parsed[k]
                for k in ("final_equity", "total_return", "max_drawdown")
                if k in parsed
            }
        )
        return row

    cmd = [
        _py(),
        str(REPO / "backtest/research/csv_minute_backtest.py"),
        "--strategy",
        strategy,
        "--start",
        start,
        "--end",
        end,
        "--minute-source",
        "qlib_1min",
        "--qlib-1min-root",
        str(qlib_root),
        "--pool-dir",
        str(pool_dir),
        "--out-dir",
        str(out_dir),
    ]
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    summary_path = out_dir / "summary.txt"
    parsed: dict[str, Any] = {}
    if summary_path.is_file():
        parsed = parse_book_summary(summary_path.read_text(encoding="utf-8"))
    if not parsed:
        parsed = metrics_from_daily_equity(out_dir / "daily_equity.csv")
    ok = proc.returncode == 0 and bool(parsed)
    row = blank_nav_row(
        engine="Book",
        strategy=strategy,
        start=start,
        end=end,
        artifact_dir=str(out_dir),
        status="OK" if ok else "DATA_GAP",
        note=(
            "ok"
            if ok
            else f"rc={proc.returncode}; stderr_tail={(proc.stderr or '')[-400:]}"
        ),
        daily_entry_source="n/a_book_pool_day_close_chase",
    )
    row.update(
        {
            k: parsed[k]
            for k in ("final_equity", "total_return", "max_drawdown")
            if k in parsed
        }
    )
    return row


def run_v7(
    *,
    start: str,
    end: str,
    pool_dir: Path,
    qlib_root: Path,
    work_root: Path,
    clock_mode: str = CLOCK_DEFAULT,
    slip_bp_per_side: int = 0,
) -> dict[str, Any]:
    from backtest.research.fullstrat_research_hooks import ResearchFillConfig

    config = ResearchFillConfig(clock_mode, slip_bp_per_side)
    if not config.baseline:
        return _run_research_portfolio(
            "v7",
            "strategy7",
            start=start,
            end=end,
            pool_dir=pool_dir,
            qlib_root=qlib_root,
            work_root=work_root,
            config=config,
        )

    out_dir = work_root / f"v7_{start}_{end}"
    if out_dir.exists() and any(out_dir.iterdir()):
        summary = out_dir / "summary.txt"
        parsed = (
            parse_v7_summary(summary.read_text(encoding="utf-8"))
            if summary.is_file()
            else {}
        )
        if not parsed:
            parsed = metrics_from_daily_equity(out_dir / "daily_equity.csv")
        row = blank_nav_row(
            engine="v7",
            strategy="strategy7",
            start=start,
            end=end,
            within_engine_rank=1 if parsed else GAP,
            artifact_dir=str(out_dir),
            status="OK" if parsed else "DATA_GAP",
            note="reused_existing_artifact" if parsed else "empty_artifact",
            daily_entry_source="n/a_v7_turtle",
        )
        row.update(
            {
                k: parsed[k]
                for k in ("final_equity", "total_return", "max_drawdown")
                if k in parsed
            }
        )
        return row

    cmd = [
        _py(),
        str(REPO / "backtest/research/csv_minute_backtest_v7.py"),
        "--start",
        start,
        "--end",
        end,
        "--pool-dir",
        str(pool_dir),
        "--minute-source",
        "qlib_1min",
        "--qlib-1min-root",
        str(qlib_root),
        "--output-dir",
        str(out_dir),
    ]
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    summary_path = out_dir / "summary.txt"
    parsed = (
        parse_v7_summary(summary_path.read_text(encoding="utf-8"))
        if summary_path.is_file()
        else {}
    )
    if not parsed:
        parsed = metrics_from_daily_equity(out_dir / "daily_equity.csv")
    ok = proc.returncode == 0 and bool(parsed)
    row = blank_nav_row(
        engine="v7",
        strategy="strategy7",
        start=start,
        end=end,
        within_engine_rank=1 if ok else GAP,
        artifact_dir=str(out_dir),
        status="OK" if ok else "DATA_GAP",
        note=(
            "ok"
            if ok
            else f"rc={proc.returncode}; stderr_tail={(proc.stderr or '')[-400:]}"
        ),
        daily_entry_source="n/a_v7_turtle",
    )
    row.update(
        {
            k: parsed[k]
            for k in ("final_equity", "total_return", "max_drawdown")
            if k in parsed
        }
    )
    return row


def _qlib_frames_to_modeb_minutes(compact: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for symbol, frame in compact.items():
        if frame is None or getattr(frame, "empty", True):
            continue
        df = frame.copy()
        if "ymd" not in df.columns:
            if "date" in df.columns:
                df["ymd"] = df["date"].map(
                    lambda d: d.strftime("%Y%m%d")
                    if hasattr(d, "strftime")
                    else str(d).replace("-", "")[:8]
                )
            else:
                continue
        keep = [
            c for c in ("hm", "open", "high", "low", "close", "ymd") if c in df.columns
        ]
        out[symbol] = df[keep]
    return out


def _daily_bars_from_minutes(minute: dict[str, Any]) -> dict[str, Any]:
    """Build Mode A/B front daily OHLC frames from 1min none lineage (last close)."""
    import pandas as pd

    daily: dict[str, Any] = {}
    for symbol, frame in minute.items():
        if frame is None or frame.empty:
            continue
        rows = []
        for ymd, group in frame.groupby("ymd", sort=True):
            group = group.sort_values("hm")
            opn = float(group.iloc[0]["open"])
            close = float(group.iloc[-1]["close"])
            high = (
                float(group["high"].max())
                if "high" in group.columns
                else max(opn, close)
            )
            low = (
                float(group["low"].min()) if "low" in group.columns else min(opn, close)
            )
            idx = pd.Timestamp(datetime.strptime(str(ymd), "%Y%m%d"))
            rows.append(
                {
                    "open": opn,
                    "high": high,
                    "low": low,
                    "close": close,
                    "index": idx,
                }
            )
        if not rows:
            continue
        out = pd.DataFrame(rows).set_index("index").sort_index()
        out.index.name = None
        daily[symbol] = out[["open", "high", "low", "close"]]
    return daily


def run_modeb_library(
    *,
    start: str,
    end: str,
    pool_dir: Path,
    qlib_root: Path,
    work_root: Path,
    clock_mode: str = CLOCK_DEFAULT,
    slip_bp_per_side: int = 0,
) -> dict[str, Any]:
    from backtest.research.fullstrat_research_hooks import ResearchFillConfig

    ResearchFillConfig(clock_mode, slip_bp_per_side)

    """Mode B via library API with entry aggregated from same 1min none lineage."""
    out_dir = work_root / f"modeb_{start}_{end}"
    row = blank_nav_row(
        engine="ModeB",
        strategy="grid",
        start=start,
        end=end,
        daily_entry_source="aggregated_from_1min_none_lineage",
        artifact_dir=str(out_dir),
        status="DATA_GAP",
    )
    if not qlib_root.is_dir():
        row["note"] = f"qlib_1min_root missing: {qlib_root}"
        return row
    try:
        from backtest.research.qlib_bin_1min import load_qlib_bin_1min_bars
        from backtest.research.fullstrat_research_hooks import run_modeb
        from backtest.research.csv_pool import load_pool_day_map
    except Exception as exc:  # pragma: no cover - import env
        row["note"] = f"import_failed:{exc}"
        return row

    start_d = date(int(start[:4]), int(start[4:6]), int(start[6:8]))
    end_d = date(int(end[:4]), int(end[4:6]), int(end[6:8]))
    try:
        pools = load_pool_day_map(pool_dir, start, end, key="ymd", empty_in_map=False)
    except Exception as exc:
        row["note"] = f"pool_load_failed:{exc}"
        return row
    codes = sorted({c for vals in pools.values() for c in vals})
    if not codes:
        row["note"] = "empty_pool_window"
        return row
    try:
        compact = load_qlib_bin_1min_bars(
            set(codes), start_d, end_d, qlib_root=qlib_root, workers=8
        )
    except Exception as exc:
        row["note"] = f"qlib_load_failed:{exc}"
        return row
    minutes = _qlib_frames_to_modeb_minutes(compact)
    daily = _daily_bars_from_minutes(minutes)
    if not daily or not minutes:
        row["note"] = "aggregation_empty_no_invented_prices"
        return row
    try:
        result = run_modeb(
            start=start,
            end=end,
            pool_dir=pool_dir,
            bars=daily,
            minute_bars=minutes,
            out_dir=out_dir,
            workers=8,
            clock_mode=clock_mode,
            slip_bp_per_side=slip_bp_per_side,
        )
    except Exception as exc:
        row["note"] = f"run_modeb_failed:{exc}"
        return row

    ranked = result.get("ranked") or []
    if not ranked:
        row["note"] = "no_ranked_strategies"
        return row
    top = ranked[0]
    total_return = getattr(top, "total_return", None)
    max_dd = getattr(top, "max_drawdown", None)
    try:
        from backtest.research import unified_exit_modea as modea

        cash_pool = float(modea.CASH_POOL)
    except Exception:
        cash_pool = None
    final_equity = (
        cash_pool * (1.0 + float(total_return))
        if cash_pool is not None and total_return is not None
        else GAP
    )
    row.update(
        {
            "strategy": getattr(top, "label", None) or str(top),
            "final_equity": final_equity,
            "total_return": total_return if total_return is not None else GAP,
            "max_drawdown": max_dd if max_dd is not None else GAP,
            "within_engine_rank": 1,
            "status": "OK",
            "note": "top_by_total_return_within_modeb_grid; oracle excluded from this row",
        }
    )
    ranking_path = out_dir / "ranking.csv"
    if ranking_path.is_file():
        rank_rows = list(csv.DictReader(ranking_path.open(encoding="utf-8")))
        if rank_rows:
            top_r = rank_rows[0]
            row["strategy"] = top_r.get("label", row["strategy"])
            if top_r.get("total_return") not in (None, ""):
                row["total_return"] = float(top_r["total_return"])
                if cash_pool is not None:
                    row["final_equity"] = cash_pool * (
                        1.0 + float(top_r["total_return"])
                    )
            if top_r.get("max_drawdown") not in (None, ""):
                row["max_drawdown"] = float(top_r["max_drawdown"])
    # Copy ranking into export root for separate Mode B rank table
    if ranking_path.is_file():
        dest = work_root / "modeb_rank_full.csv"
        dest.write_text(ranking_path.read_text(encoding="utf-8"), encoding="utf-8")
    return row


def selected_cells(value):
    from backtest.research.fullstrat_research_hooks import ResearchFillConfig

    for cell in MATRIX_CELLS:
        ResearchFillConfig(cell["clock"], cell["slip_bp_per_side"])
    names = set(value.split(","))
    known = {c["cell_id"] for c in MATRIX_CELLS}
    if not names or not names <= known:
        raise ValueError(f"unknown cells: {sorted(names - known)}")
    return [c for c in MATRIX_CELLS if c["cell_id"] in names]


def execute(
    *, start, end, pool_dir, qlib_root, out_dir, engines, strategies, force, cells=None
):
    cells = cells or selected_cells("baseline_default_clock_fee")
    _ensure_new_or_empty(out_dir, allow_existing=force)
    rows = {"Book": [], "v7": [], "ModeB": []}
    for cell in cells:
        work_root = out_dir / "runner_artifacts" / cell["cell_id"]
        work_root.mkdir(parents=True, exist_ok=True)
        provenance = dict(
            cell_id=cell["cell_id"],
            clock_mode=cell["clock"],
            slip_bp_per_side=cell["slip_bp_per_side"],
            sizing="Q2",
            coverage="H2_all_fills",
            expiry="same_day",
            sell_expiry="next_session_reevaluate",
            production_C="frozen",
            git_head=_git_head(),
            start=start,
            end=end,
            pool_dir=str(pool_dir),
            qlib_root=str(qlib_root),
        )
        # Experimental artifacts must never be silently reused, even with --force.
        if cell["cell_id"] != "baseline_default_clock_fee" and any(work_root.iterdir()):
            raise ValueError(f"choose a fresh research output directory: {work_root}")
        (work_root / "research_config.json").write_text(
            json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        common = dict(
            start=start,
            end=end,
            pool_dir=pool_dir,
            qlib_root=qlib_root,
            work_root=work_root,
            clock_mode=cell["clock"],
            slip_bp_per_side=cell["slip_bp_per_side"],
        )
        by_cell = {"Book": [], "v7": [], "ModeB": []}
        if "book" in engines:
            by_cell["Book"] = [run_book(strategy, **common) for strategy in strategies]
            rank_within(by_cell["Book"])
        if "v7" in engines:
            by_cell["v7"] = [run_v7(**common)]
        if "modeb" in engines:
            by_cell["ModeB"] = [run_modeb_library(**common)]
        for engine, result in by_cell.items():
            for row in result:
                row.update(
                    cell_id=cell["cell_id"],
                    clock=cell["clock"],
                    slip_bp_per_side=cell["slip_bp_per_side"],
                )
            rows[engine].extend(result)
    emit_stubs(out_dir, start=start, end=end, force=True)
    for engine, filename in (
        ("Book", "book_nav.csv"),
        ("v7", "v7_nav.csv"),
        ("ModeB", "modeb_nav.csv"),
    ):
        write_csv(out_dir / filename, rows[engine], list(blank_nav_row()))
    matrix = matrix_rows()
    for cell in matrix:
        matches = [r for r in rows[cell["engine"]] if r["cell_id"] == cell["cell_id"]]
        ok = [r for r in matches if r["status"] == "OK"]
        if ok:
            top = max(ok, key=lambda r: float(r["total_return"]))
            cell.update(
                nav=top["final_equity"],
                total_return=top["total_return"],
                max_drawdown=top["max_drawdown"],
                within_engine_rank=top["within_engine_rank"],
                fill_status="FILLED",
            )
        elif matches:
            cell.update(
                fill_status="DATA_GAP", note="; ".join(r["note"] for r in matches)
            )
    write_csv(out_dir / "matrix.csv", matrix, list(matrix[0]))
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(
        status="EXECUTED_PARTIAL_OR_FULL",
        cells=[c["cell_id"] for c in cells],
        pool_dir=str(pool_dir),
        qlib_1min_root=str(qlib_root),
        engines=sorted(engines),
        sizing="Q2",
        coverage="H2_all_fills",
        sell_expiry="next_session_reevaluate",
    )
    for engine, name in (("Book", "book_ok"), ("v7", "v7_ok"), ("ModeB", "modeb_ok")):
        manifest[name] = sum(r["status"] == "OK" for r in rows[engine])
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "Batch4 fullstrat NAV/DD/rank research harness "
            "(H2 + Q2 research hooks; clock XOR slip; production_C frozen)"
        )
    )
    ap.add_argument(
        "--cells",
        default="baseline_default_clock_fee",
        help="comma subset of fixed matrix cell_id values; one axis per cell",
    )
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--pool-dir", type=Path, default=REPO / "stock_pool")
    ap.add_argument(
        "--qlib-1min-root",
        type=Path,
        default=Path(os.environ.get("QLIB_1MIN_ROOT", str(DEFAULT_QLIB_1MIN_ROOT))),
    )
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--engines",
        default="book,v7,modeb",
        help="comma subset of book,v7,modeb",
    )
    ap.add_argument(
        "--strategies",
        default=",".join(BOOK_STRATEGIES),
        help="Book strategies for within-engine rank",
    )
    ap.add_argument("--dry-run", action="store_true", help="print matrix plan only")
    ap.add_argument(
        "--emit-stubs",
        action="store_true",
        help="write DATA_GAP CSV/JSON stubs (VM-safe)",
    )
    ap.add_argument(
        "--execute",
        action="store_true",
        help="run existing runners / Mode B library path (4090)",
    )
    ap.add_argument(
        "--force", action="store_true", help="allow rewriting output-dir stubs"
    )
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    cells = selected_cells(args.cells)
    engines = {e.strip().lower() for e in args.engines.split(",") if e.strip()}
    strategies = tuple(s.strip() for s in args.strategies.split(",") if s.strip())
    if not engines or not engines <= {"book", "v7", "modeb"}:
        raise ValueError("engines must be a nonempty subset of book,v7,modeb")
    if not strategies or not set(strategies) <= set(BOOK_STRATEGIES):
        raise ValueError("strategies must belong to the batch4 Book matrix")

    if args.dry_run and not args.emit_stubs and not args.execute:
        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "window": {"start": args.start, "end": args.end},
                    "fee_schedule": FEE_SCHEDULE,
                    "matrix": cells,
                    "book_strategies": list(strategies),
                    "production_C": "frozen",
                    "note": "H2 + Q2 hooks FILLABLE; numbers await post-merge 4090",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.emit_stubs or (not args.execute):
        # default VM path: emit stubs
        if not args.execute:
            manifest = emit_stubs(
                args.output_dir,
                start=args.start,
                end=args.end,
                force=args.force or args.emit_stubs,
            )
            print(
                json.dumps(
                    {
                        "mode": "emit-stubs",
                        "manifest_status": manifest["status"],
                        "output_dir": str(args.output_dir),
                    },
                    ensure_ascii=False,
                )
            )
            if not args.execute:
                return 0

    if args.execute:
        if not args.qlib_1min_root.is_dir():
            # still emit stubs + record gap
            emit_stubs(args.output_dir, start=args.start, end=args.end, force=True)
            gaps = data_gap_rows(args.start, args.end)
            gaps.append(
                {
                    "item": "qlib_1min_root",
                    "status": "DATA_GAP",
                    "evidence": f"missing path {args.qlib_1min_root}",
                }
            )
            write_csv(
                args.output_dir / "data_gaps.csv", gaps, ["item", "status", "evidence"]
            )
            print(
                json.dumps(
                    {
                        "mode": "execute",
                        "status": "DATA_GAP",
                        "reason": "qlib_1min_root_missing",
                        "output_dir": str(args.output_dir),
                    },
                    ensure_ascii=False,
                )
            )
            return 2
        manifest = execute(
            start=args.start,
            end=args.end,
            pool_dir=args.pool_dir,
            qlib_root=args.qlib_1min_root,
            out_dir=args.output_dir,
            engines=engines,
            strategies=strategies,
            force=args.force,
            cells=cells,
        )
        print(
            json.dumps(
                {"mode": "execute", "manifest": manifest}, ensure_ascii=False, indent=2
            )
        )
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
