#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-click retry for float_shares acceptance.

Supports:
- --start-date / --end-date
- --codes
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
DEFAULT_PYTHON = r"D:/anaconda3/envs/vanna311/python.exe"

STOCK_DATA = REPO / "stock_data"
BACKTEST_OUTPUT = REPO / "backtest_output"
ACTIVE_HISTORY = STOCK_DATA / "float_shares_history.parquet"
ACTIVE_SNAPSHOT = STOCK_DATA / "float_shares.parquet"

AK_HIST = STOCK_DATA / "float_shares_history.akretry.parquet"
AK_SNAPSHOT = STOCK_DATA / "float_shares.akretry_snapshot.parquet"
QMT_HIST = STOCK_DATA / "float_shares_history.qmtretry.parquet"
QMT_SNAPSHOT = STOCK_DATA / "float_shares.qmtretry_snapshot.parquet"
BASELINE_JSON = BACKTEST_OUTPUT / "float_shares_time_dimension_baseline.retry.json"
REPORT_JSON = BACKTEST_OUTPUT / "float_shares_retry_report.json"
HISTORY_BACKUP = STOCK_DATA / "float_shares_history.parquet.retry_backup"


def run_cmd(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def recent_10_bdays() -> Tuple[str, str]:
    end_ts = (pd.Timestamp.today().normalize() - pd.offsets.BDay(1)).normalize()
    start_ts = (end_ts - pd.offsets.BDay(9)).normalize()
    return start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d")


def pick_codes(n: int) -> List[str]:
    df = pd.read_parquet(ACTIVE_SNAPSHOT)
    return df["stock_code"].dropna().astype(str).head(n).tolist()


def parse_codes(raw: str | None, n_fallback: int) -> List[str]:
    if raw:
        return [c.strip().upper() for c in raw.split(",") if c.strip()]
    return pick_codes(n_fallback)


def probe_akshare(code: str, start_date: str, end_date: str) -> Tuple[bool, str]:
    try:
        import akshare as ak

        code6 = code[:6]
        df = ak.stock_zh_a_hist(
            symbol=code6,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="",
        )
        if df is None or len(df) == 0:
            return False, "akshare returned empty dataframe"
        return True, f"rows={len(df)}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def probe_qmt(code: str) -> Tuple[bool, str]:
    try:
        from xtquant import xtdata

        detail = xtdata.get_instrument_detail(code)
        if not detail:
            return False, "xtdata returned empty detail"
        fv = detail.get("FloatVolume")
        if fv is None or fv <= 0:
            return False, f"FloatVolume invalid: {fv}"
        return True, f"FloatVolume={fv}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def calc_metrics(history_path: Path, qmt_snapshot_ref: Path) -> Dict[str, float]:
    h = pd.read_parquet(history_path)
    h["date"] = pd.to_datetime(h["date"]).dt.normalize()
    rows = int(len(h))
    codes = int(h["stock_code"].nunique())
    dup = int(h.duplicated(["date", "stock_code"]).sum())
    nonnull = float(h["float_shares"].notna().mean()) if rows else 0.0
    dmin = h["date"].min()
    dmax = h["date"].max()
    exp_dates = len(pd.bdate_range(dmin, dmax))
    coverage = float(rows / (codes * exp_dates)) if codes and exp_dates else 0.0

    s = pd.read_parquet(qmt_snapshot_ref)[["stock_code", "float_shares"]].copy()
    latest = h[h["date"] == dmax][["stock_code", "float_shares"]].copy()
    m = latest.merge(s, on="stock_code", suffixes=("_hist", "_qmt"))
    m = m[(m["float_shares_qmt"] > 0) & (m["float_shares_hist"] > 0)].copy()
    if len(m):
        rel = (m["float_shares_hist"] - m["float_shares_qmt"]).abs() / m["float_shares_qmt"]
        p50 = float(np.quantile(rel, 0.5))
        p95 = float(np.quantile(rel, 0.95))
        pmax = float(rel.max())
    else:
        p50 = p95 = pmax = float("nan")

    return {
        "rows": rows,
        "codes": codes,
        "duplicate_keys": dup,
        "nonnull_ratio": nonnull,
        "coverage": coverage,
        "latest_overlap": int(len(m)),
        "rel_diff_p50": p50,
        "rel_diff_p95": p95,
        "rel_diff_max": pmax,
        "date_min": str(dmin.date()),
        "date_max": str(dmax.date()),
    }


def baseline_with_temp_history(python_bin: str, sample_size: int, bars: int) -> Tuple[subprocess.CompletedProcess, Dict]:
    had_active = ACTIVE_HISTORY.exists()
    if had_active:
        shutil.copy2(ACTIVE_HISTORY, HISTORY_BACKUP)
    elif HISTORY_BACKUP.exists():
        HISTORY_BACKUP.unlink()
    try:
        shutil.copy2(AK_HIST, ACTIVE_HISTORY)
        cmd = [
            python_bin,
            str(REPO / "backtest" / "verify_float_shares_time_dimension_baseline.py"),
            "--sample-size",
            str(sample_size),
            "--bars",
            str(bars),
            "--output-json",
            str(BASELINE_JSON),
        ]
        p = run_cmd(cmd)
        metrics = {}
        if BASELINE_JSON.exists():
            metrics = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
        return p, metrics
    finally:
        if HISTORY_BACKUP.exists():
            shutil.copy2(HISTORY_BACKUP, ACTIVE_HISTORY)
            HISTORY_BACKUP.unlink()
        elif not had_active and ACTIVE_HISTORY.exists():
            ACTIVE_HISTORY.unlink()


def eval_thresholds(akm: Dict, bm: Dict) -> Dict[str, object]:
    hard = {
        "duplicate_keys_zero": akm.get("duplicate_keys") == 0,
        "nonnull_ratio_ge_0_99": akm.get("nonnull_ratio", 0.0) >= 0.99,
        "coverage_ge_0_95": akm.get("coverage", 0.0) >= 0.95,
        "latest_overlap_ge_3": akm.get("latest_overlap", 0) >= 3,
        "baseline_history_exists": bool(bm.get("history_exists", False)),
    }
    soft = {
        "rel_diff_p50_le_0_05": akm.get("rel_diff_p50", 1.0) <= 0.05,
        "rel_diff_p95_le_0_20": akm.get("rel_diff_p95", 1.0) <= 0.20,
        "rel_diff_max_le_0_35": akm.get("rel_diff_max", 1.0) <= 0.35,
    }
    hard_pass = all(hard.values())
    soft_fail = sum(1 for v in soft.values() if not v)
    overall = hard_pass and soft_fail <= 1
    return {
        "hard_checks": hard,
        "soft_checks": soft,
        "hard_pass": hard_pass,
        "soft_fail_count": soft_fail,
        "overall_pass": overall,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="One-click retry for float_shares acceptance")
    parser.add_argument("--python-bin", default=DEFAULT_PYTHON)
    parser.add_argument("--stocks", type=int, default=5, help="fallback stock count if --codes not provided")
    parser.add_argument("--codes", default=None, help="comma-separated stock codes, e.g. 000001.SZ,600000.SH")
    parser.add_argument("--start-date", default=None, help="YYYY-MM-DD; default recent 10 business days")
    parser.add_argument("--end-date", default=None, help="YYYY-MM-DD; default recent 10 business days end")
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--bars", type=int, default=200)
    parser.add_argument("--sleep-s", type=float, default=0.2)
    parser.add_argument("--dry-run", action="store_true", help="parse args and show planned branches only; no network/no external runs")
    args = parser.parse_args()

    BACKTEST_OUTPUT.mkdir(parents=True, exist_ok=True)

    if args.start_date and args.end_date:
        start_date, end_date = args.start_date, args.end_date
    else:
        start_date, end_date = recent_10_bdays()

    codes = parse_codes(args.codes, args.stocks)
    if not codes:
        print("[ERROR] empty codes")
        return 2

    if args.dry_run:
        plan = {
            "window": {"start_date": start_date, "end_date": end_date},
            "codes": codes,
            "dry_run": True,
            "planned_steps": [
                "probe_akshare",
                "probe_qmt",
                "akshare_backfill_5x10",
                "qmt_daily_snapshot",
                "baseline_with_temp_history",
                "threshold_evaluation",
            ],
            "note": "No network probes and no external commands were executed.",
        }
        BACKTEST_OUTPUT.mkdir(parents=True, exist_ok=True)
        REPORT_JSON.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        print("=== float_shares retry acceptance (dry-run) ===")
        print(f"window: {start_date} ~ {end_date}")
        print(f"codes: {','.join(codes)}")
        print("planned_steps: probe_akshare -> probe_qmt -> ak_backfill -> qmt_snapshot -> baseline -> threshold")
        print(f"report_json: {REPORT_JSON}")
        print("OVERALL_PASS: DRY_RUN_ONLY")
        return 0

    ak_ok, ak_msg = probe_akshare(codes[0], start_date, end_date)
    qmt_ok, qmt_msg = probe_qmt(codes[0])

    report: Dict[str, object] = {
        "window": {"start_date": start_date, "end_date": end_date},
        "codes": codes,
        "probes": {"akshare_ok": ak_ok, "akshare_msg": ak_msg, "qmt_ok": qmt_ok, "qmt_msg": qmt_msg},
        "steps": {},
    }

    if ak_ok:
        # Ensure ak backfill input snapshot exists
        if ACTIVE_SNAPSHOT.exists():
            shutil.copy2(ACTIVE_SNAPSHOT, AK_SNAPSHOT)
        p_ak = run_cmd([
            args.python_bin,
            str(REPO / "backtest" / "backfill_float_shares_history.py"),
            "--source", "akshare",
            "--start-date", start_date,
            "--end-date", end_date,
            "--codes", ",".join(codes),
            "--max-stocks", str(len(codes)),
            "--history-output", str(AK_HIST),
            "--snapshot-path", str(AK_SNAPSHOT),
            "--replace",
            "--sleep-s", str(args.sleep_s),
        ])
    else:
        p_ak = subprocess.CompletedProcess([], 998, "", "akshare probe failed")

    ak_metrics = calc_metrics(AK_HIST, ACTIVE_SNAPSHOT) if (p_ak.returncode == 0 and AK_HIST.exists()) else {}
    report["steps"]["akshare_backfill"] = {
        "ok": p_ak.returncode == 0,
        "returncode": p_ak.returncode,
        "stdout_tail": p_ak.stdout[-1000:],
        "stderr_tail": p_ak.stderr[-1000:],
        "metrics": ak_metrics,
    }

    if qmt_ok:
        p_qmt = run_cmd([
            args.python_bin,
            str(REPO / "backtest" / "fetch_float_shares.py"),
            "--mode", "daily-snapshot",
            "--stocks", ",".join(codes),
            "--snapshot-date", end_date,
            "--output", str(QMT_SNAPSHOT),
            "--history-output", str(QMT_HIST),
            "--no-diff",
        ])
    else:
        p_qmt = subprocess.CompletedProcess([], 997, "", "qmt probe failed")

    qmt_rows = len(pd.read_parquet(QMT_HIST)) if (p_qmt.returncode == 0 and QMT_HIST.exists()) else 0
    report["steps"]["qmt_daily_snapshot"] = {
        "ok": p_qmt.returncode == 0,
        "returncode": p_qmt.returncode,
        "rows": qmt_rows,
        "stdout_tail": p_qmt.stdout[-1000:],
        "stderr_tail": p_qmt.stderr[-1000:],
    }

    if p_ak.returncode == 0 and AK_HIST.exists():
        p_base, base_metrics = baseline_with_temp_history(args.python_bin, args.sample_size, args.bars)
    else:
        p_base = subprocess.CompletedProcess([], 996, "", "ak history not available")
        base_metrics = {}

    report["steps"]["baseline_with_temp_history"] = {
        "ok": p_base.returncode == 0,
        "returncode": p_base.returncode,
        "stdout_tail": p_base.stdout[-1000:],
        "stderr_tail": p_base.stderr[-1000:],
        "metrics": base_metrics,
    }

    thresholds = eval_thresholds(ak_metrics, base_metrics) if ak_metrics else {
        "hard_checks": {},
        "soft_checks": {},
        "hard_pass": False,
        "soft_fail_count": 999,
        "overall_pass": False,
    }
    preconditions = {
        "akshare_probe_pass": ak_ok,
        "qmt_probe_pass": qmt_ok,
        "ak_backfill_pass": p_ak.returncode == 0,
        "qmt_daily_snapshot_pass": p_qmt.returncode == 0 and qmt_rows > 0,
        "baseline_pass": p_base.returncode == 0,
    }
    overall = all(preconditions.values()) and bool(thresholds.get("overall_pass"))

    report["threshold_evaluation"] = thresholds
    report["preconditions"] = preconditions
    report["overall_pass"] = overall
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== float_shares retry acceptance ===")
    print(f"window: {start_date} ~ {end_date}")
    print(f"codes: {','.join(codes)}")
    print(f"akshare_probe: {ak_ok} ({ak_msg})")
    print(f"qmt_probe: {qmt_ok} ({qmt_msg})")
    print(f"ak_backfill_ok: {p_ak.returncode == 0}")
    print(f"qmt_daily_snapshot_ok: {p_qmt.returncode == 0} rows={qmt_rows}")
    print(f"baseline_ok: {p_base.returncode == 0}")
    print(f"threshold_overall_pass: {thresholds.get('overall_pass')}")
    print(f"OVERALL_PASS: {overall}")
    print(f"report_json: {REPORT_JSON}")

    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())

