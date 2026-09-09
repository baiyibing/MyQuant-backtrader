# -*- coding: utf-8 -*-
"""G.6 offline counterfactual harness — EOD dual-side v4 MA-cross parity (Block 2).

Reads ``v4_parity_atoms`` (``source='live'``) for a paper day, recomputes both sides
with post-close QMT front close (live) vs oskh_data front close (backtest), compares
``eval_v4_ma_cross_raw`` booleans, and writes ``parity_report_<date>.jsonl`` + ``.md``.

Coverage denominator (r3 consensus): deduped live decision keys
``(stock, trading_date, side, sell_scan_trigger)`` — "sampled decision EOD verifiability",
not full-universe sampling rate.

Usage (vanna311, repo root)::

  python scripts/backtest/diff_v4_trigger_parity.py --date 20260703
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, cast

import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _P

_sb_dir = next((_p for _p in _P(__file__).resolve().parents if _p.name == "scripts"), _P(__file__).resolve().parent.parent)
_sb_spec = _ilu.spec_from_file_location("_script_bootstrap", _sb_dir / "_script_bootstrap.py")
if _sb_spec is None or _sb_spec.loader is None:
    raise ImportError("_script_bootstrap unavailable")
_bs_mod = _ilu.module_from_spec(_sb_spec)
_sys.modules["_script_bootstrap"] = _bs_mod
_sb_spec.loader.exec_module(_bs_mod)
_bs_mod.ensure_repo_on_syspath(__file__)

from _script_bootstrap import ensure_repo_on_syspath

_REPO_ROOT = ensure_repo_on_syspath(__file__)

import numpy as np
import pandas as pd

from common.infra.trace_context import TraceIdGenerator
from oskh_data import StockDataReader
from oskh_factors.chip.adj_factor import get_adj_factor
from trade_decision.presets import eval_v4_ma_cross_raw

V4_PARITY_L2_REL = 1e-3
V4_PARITY_L2_ABS = 0.02
L1_FACTOR_TOL = 1e-9
DEFAULT_V4_PARAMS = {"ma_sell_period": 5, "ma_buy_period": 10}


@dataclass
class AtomRow:
    stock: str
    trading_date: str
    side: str
    sell_scan_trigger: Optional[str]
    bar_policy: Optional[str]
    cmp_price_mode: str
    data_ok: int


@dataclass
class ParityRow:
    stock: str
    trading_date: str
    side: str
    sell_scan_trigger: Optional[str]
    live_decision: Optional[bool]
    bt_decision: Optional[bool]
    flip: Optional[bool]
    data_ok: bool
    cmp_price_mode_live: str
    cmp_price_mode_eod: str
    factor_live: Optional[float]
    factor_bt: Optional[float]
    factor_rel_err: Optional[float]
    ma5_live: Optional[float]
    ma5_bt: Optional[float]
    ma5_rel_err: Optional[float]
    ma5_abs_err: Optional[float]
    notes: List[str] = field(default_factory=list)


@dataclass
class DaySummary:
    trading_date: str
    denominator: int
    coverage_numerator: int
    coverage_rate: float
    flip_count: int
    flip_rate: float
    l1_fail: int
    l2_spike: int
    eod_unavailable: int
    rows: List[ParityRow] = field(default_factory=list)


def _dedup_key(row: AtomRow) -> Tuple[str, str, str, str]:
    trigger = str(row.sell_scan_trigger or "")
    return (row.stock, row.trading_date, row.side, trigger)


def load_live_atoms(conn: sqlite3.Connection, trading_date: str) -> List[AtomRow]:
    cur = conn.execute(
        """
        SELECT stock, trading_date, side, sell_scan_trigger, bar_policy, cmp_price_mode, data_ok
        FROM v4_parity_atoms
        WHERE source = 'live' AND trading_date = ?
        ORDER BY id ASC
        """,
        (trading_date,),
    )
    out: List[AtomRow] = []
    for r in cur.fetchall():
        out.append(
            AtomRow(
                stock=str(r[0]),
                trading_date=str(r[1]),
                side=str(r[2]),
                sell_scan_trigger=str(r[3]) if r[3] is not None else None,
                bar_policy=str(r[4]) if r[4] is not None else None,
                cmp_price_mode=str(r[5] or "missing"),
                data_ok=int(r[6] or 0),
            )
        )
    seen: Dict[Tuple[str, str, str, str], AtomRow] = {}
    for row in out:
        seen[_dedup_key(row)] = row
    return list(seen.values())


def _ma_period(side: str, params: Mapping[str, Any]) -> int:
    if str(side).upper() == "SELL":
        return int(params.get("ma_sell_period", 5))
    return int(params.get("ma_buy_period", 10))


def _bt_eod_snapshot(
    stock: str,
    trading_date: str,
    side: str,
    *,
    params: Mapping[str, Any],
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], str]:
    period = _ma_period(side, params)
    need = max(period + 2, 12)
    start = (pd.Timestamp(trading_date) - pd.Timedelta(days=need * 3)).strftime("%Y%m%d")
    reader = StockDataReader()
    df = reader.read_stock(stock, start, trading_date, adjust_type="front")
    if df is None or df.empty:
        return None, None, None, None, "eod_unavailable"
    if "close" not in df.columns:
        return None, None, None, None, "eod_unavailable"
    df = df.copy()
    df["ymd"] = pd.to_datetime(df.index).strftime("%Y%m%d")
    sub = df[df["ymd"] <= trading_date].tail(need)
    if sub.empty or trading_date not in set(sub["ymd"]):
        return None, None, None, None, "eod_unavailable"
    raw_close = float(sub.loc[sub["ymd"] == trading_date, "close"].iloc[-1])
    try:
        factor = float(get_adj_factor(stock, trading_date))
    except Exception:
        return raw_close, None, None, None, "eod_unavailable"
    closes = sub["close"].astype(float).values
    if len(closes) < period:
        return raw_close, factor, None, None, "eod_unavailable"
    ma_val = float(np.mean(cast(Any, closes[-period:])))
    # raw_close from adjust_type="front" is already close_none * cumulative_adj_factor.
    ma_cmp = raw_close
    return raw_close, factor, ma_val, ma_cmp, "eod_recomputed"


def _live_eod_snapshot(
    stock: str,
    trading_date: str,
    side: str,
    *,
    params: Mapping[str, Any],
    bar_policy: str,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], str]:
    from live_trading.indicators.ma_provider import (
        _aligned_close_series,
        _expected_trade_dates,
        _ma_fund_daily_adjust,
        _qmt_daily_bars_df,
        _qmt_trade_days_df,
    )

    period = _ma_period(side, params)
    max_p = max(5, 10, period)
    bp = bar_policy if bar_policy in ("prior_completed_session", "intraday") else "prior_completed_session"
    need_n = max_p + (1 if bp == "intraday" else 2)
    trace_id = TraceIdGenerator.generate("v4df", trading_date)
    td_df = _qmt_trade_days_df(until=trading_date, count=need_n, trace_id=trace_id)
    if td_df is None or td_df.empty or len(td_df) < need_n:
        return None, None, None, None, "eod_unavailable"
    if bp == "prior_completed_session":
        expected = _expected_trade_dates(td_df.iloc[:-1], max_p)
    else:
        expected = _expected_trade_dates(td_df, max_p)
    if len(expected) < max_p or trading_date not in expected and trading_date not in set(expected):
        # EOD close for trading_date must be in window end
        pass
    start_d = expected[0] if expected else trading_date
    end_d = trading_date
    df_bar = _qmt_daily_bars_df(
        symbol=stock,
        start_d=start_d,
        end_d=end_d,
        adjust=_ma_fund_daily_adjust(),
        trace_id=trace_id,
    )
    arr = _aligned_close_series(cast(Any, df_bar), expected) if expected and df_bar is not None else None
    if arr is None or len(arr) < max_p:
        return None, None, None, None, "eod_unavailable"
    raw_close = float(arr[-1]) if trading_date == expected[-1] else None
    if raw_close is None and df_bar is not None and not df_bar.empty:
        try:
            raw_close = float(df_bar.iloc[-1]["close"])
        except Exception:
            raw_close = None
    if raw_close is None or raw_close <= 0:
        return None, None, None, None, "eod_unavailable"
    try:
        factor = float(get_adj_factor(stock, trading_date))
    except Exception:
        return raw_close, None, None, None, "eod_unavailable"
    ma_val = float(np.mean(cast(Any, arr[-period:])))
    # QMT front-adjusted daily close is already v4 ma_comparison_price.
    ma_cmp = raw_close
    return raw_close, factor, ma_val, ma_cmp, "eod_recomputed"


def evaluate_day(
    atoms: Sequence[AtomRow],
    *,
    params: Mapping[str, Any],
) -> DaySummary:
    if not atoms:
        td = ""
        return DaySummary(
            trading_date=td,
            denominator=0,
            coverage_numerator=0,
            coverage_rate=0.0,
            flip_count=0,
            flip_rate=0.0,
            l1_fail=0,
            l2_spike=0,
            eod_unavailable=0,
        )
    td = atoms[0].trading_date
    rows: List[ParityRow] = []
    flip_count = 0
    coverage_num = 0
    l1_fail = 0
    l2_spike = 0
    eod_unavailable = 0

    for atom in atoms:
        bp = atom.bar_policy or "prior_completed_session"
        live_raw, live_factor, live_ma, live_ma_cmp, live_mode = _live_eod_snapshot(
            atom.stock, td, atom.side, params=params, bar_policy=bp
        )
        bt_raw, bt_factor, bt_ma, bt_ma_cmp, bt_mode = _bt_eod_snapshot(
            atom.stock, td, atom.side, params=params
        )
        notes: List[str] = []
        if live_mode == "eod_unavailable" or bt_mode == "eod_unavailable":
            eod_unavailable += 1
            rows.append(
                ParityRow(
                    stock=atom.stock,
                    trading_date=td,
                    side=atom.side,
                    sell_scan_trigger=atom.sell_scan_trigger,
                    live_decision=None,
                    bt_decision=None,
                    flip=None,
                    data_ok=False,
                    cmp_price_mode_live=atom.cmp_price_mode,
                    cmp_price_mode_eod="eod_unavailable",
                    factor_live=live_factor,
                    factor_bt=bt_factor,
                    factor_rel_err=None,
                    ma5_live=live_ma,
                    ma5_bt=bt_ma,
                    ma5_rel_err=None,
                    ma5_abs_err=None,
                    notes=["eod_unavailable"],
                )
            )
            continue

        live_ind = {"data_ok": True, f"ma{_ma_period(atom.side, params)}": live_ma}
        bt_ind = {"data_ok": True, f"ma{_ma_period(atom.side, params)}": bt_ma}
        live_dec = eval_v4_ma_cross_raw(
            side=atom.side,
            ma_comparison_price=float(cast(Any, live_ma_cmp)),
            indicators=live_ind,
            params=params,
        )
        bt_dec = eval_v4_ma_cross_raw(
            side=atom.side,
            ma_comparison_price=float(cast(Any, bt_ma_cmp)),
            indicators=bt_ind,
            params=params,
        )
        data_ok = live_ma_cmp is not None and live_factor is not None and bt_ma_cmp is not None and bt_factor is not None
        if data_ok:
            coverage_num += 1
        flipped = bool(live_dec != bt_dec)
        if flipped:
            flip_count += 1

        factor_rel = None
        if live_factor is not None and bt_factor is not None and bt_factor != 0:
            factor_rel = abs(live_factor - bt_factor) / abs(bt_factor)
            if factor_rel > L1_FACTOR_TOL:
                l1_fail += 1
                notes.append("L1_factor_drift")

        ma_rel = ma_abs = None
        if live_ma is not None and bt_ma is not None and bt_ma != 0:
            ma_rel = abs(live_ma - bt_ma) / abs(bt_ma)
            ma_abs = abs(live_ma - bt_ma)
            if ma_rel > V4_PARITY_L2_REL and ma_abs > V4_PARITY_L2_ABS:
                l2_spike += 1
                notes.append("L2_ma_spike")

        rows.append(
            ParityRow(
                stock=atom.stock,
                trading_date=td,
                side=atom.side,
                sell_scan_trigger=atom.sell_scan_trigger,
                live_decision=live_dec,
                bt_decision=bt_dec,
                flip=flipped,
                data_ok=data_ok,
                cmp_price_mode_live=atom.cmp_price_mode,
                cmp_price_mode_eod=live_mode,
                factor_live=live_factor,
                factor_bt=bt_factor,
                factor_rel_err=factor_rel,
                ma5_live=live_ma,
                ma5_bt=bt_ma,
                ma5_rel_err=ma_rel,
                ma5_abs_err=ma_abs,
                notes=notes,
            )
        )

    denom = len(atoms)
    cov_rate = (coverage_num / denom) if denom else 0.0
    flip_rate = (flip_count / coverage_num) if coverage_num else 0.0
    return DaySummary(
        trading_date=td,
        denominator=denom,
        coverage_numerator=coverage_num,
        coverage_rate=cov_rate,
        flip_count=flip_count,
        flip_rate=flip_rate,
        l1_fail=l1_fail,
        l2_spike=l2_spike,
        eod_unavailable=eod_unavailable,
        rows=rows,
    )


def write_reports(summary: DaySummary, out_dir: Path) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / f"parity_report_{summary.trading_date}.jsonl"
    md_path = out_dir / f"parity_report_{summary.trading_date}.md"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in summary.rows:
            fh.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
        fh.write(
            json.dumps(
                {
                    "summary": {
                        "trading_date": summary.trading_date,
                        "denominator": summary.denominator,
                        "coverage_numerator": summary.coverage_numerator,
                        "coverage_rate": summary.coverage_rate,
                        "flip_count": summary.flip_count,
                        "flip_rate": summary.flip_rate,
                        "l1_fail": summary.l1_fail,
                        "l2_spike": summary.l2_spike,
                        "eod_unavailable": summary.eod_unavailable,
                        "coverage_definition": (
                            "coverage = EOD-verifiable rate among sampled live v4 decision keys "
                            "(stock,trading_date,side,sell_scan_trigger), not full-universe sampling"
                        ),
                    }
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    flip_lines = [
        f"- {r.stock} {r.side} trigger={r.sell_scan_trigger!r} live={r.live_decision} bt={r.bt_decision}"
        for r in summary.rows
        if r.flip
    ]
    md_path.write_text(
        "\n".join(
            [
                f"# v4 parity report {summary.trading_date}",
                "",
                f"- denominator (sampled live keys): {summary.denominator}",
                f"- coverage: {summary.coverage_numerator}/{summary.denominator} = {summary.coverage_rate:.4f}",
                f"- flip_rate (over covered): {summary.flip_count}/{summary.coverage_numerator} = {summary.flip_rate:.4f}",
                f"- L1 factor fails: {summary.l1_fail}",
                f"- L2 MA spikes: {summary.l2_spike}",
                f"- eod_unavailable rows: {summary.eod_unavailable}",
                "",
                "## Flips",
                *(flip_lines or ["- (none)"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return jsonl_path, md_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="G.6 v4 trigger parity offline harness")
    parser.add_argument("--date", required=True, help="Trading date YYYYMMDD")
    parser.add_argument("--audit-db", default="", help="Override AUDIT_DB_PATH")
    parser.add_argument(
        "--out-dir",
        default=str(_REPO_ROOT / "reports" / "v4_parity"),
        help="Output directory for parity_report_* files",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    import strategy_config as cfg

    audit_path = str(args.audit_db or getattr(cfg, "AUDIT_DB_PATH", "") or "")
    if not audit_path:
        print("AUDIT_DB_PATH missing", file=sys.stderr)
        return 2

    conn = sqlite3.connect(audit_path)
    try:
        atoms = load_live_atoms(conn, str(args.date).strip())
    finally:
        conn.close()

    summary = evaluate_day(atoms, params=DEFAULT_V4_PARAMS)
    jsonl_path, md_path = write_reports(summary, Path(args.out_dir))
    print(f"wrote {jsonl_path}")
    print(f"wrote {md_path}")
    print(
        f"coverage={summary.coverage_rate:.4f} flip_rate={summary.flip_rate:.4f} "
        f"eod_unavailable={summary.eod_unavailable}"
    )

    if summary.eod_unavailable > 0 and summary.coverage_numerator == 0:
        print("EOD coverage insufficient — G.6 auto-close blocked (exit 2 WARNING)", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
