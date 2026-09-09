#!/usr/bin/env python3
"""P0b: DuckDB views + templates + A/B/C/D latency baseline (with RSS/temp profile)."""

from __future__ import annotations

import argparse
import importlib.util as _ilu
import json
import sys
import time
from pathlib import Path
from typing import Any

_sb_dir = next(
    (_p for _p in Path(__file__).resolve().parents if _p.name == "scripts"),
    Path(__file__).resolve().parent,
)
_sb_spec = _ilu.spec_from_file_location("_script_bootstrap", _sb_dir / "_script_bootstrap.py")
if _sb_spec is None or _sb_spec.loader is None:
    raise ImportError("_script_bootstrap unavailable")
_bs_mod = _ilu.module_from_spec(_sb_spec)
sys.modules["_script_bootstrap"] = _bs_mod
_sb_spec.loader.exec_module(_bs_mod)
_bs_mod.ensure_repo_on_syspath(__file__)

from l2_analytics.db import connect, default_parquet_root  # noqa: E402
from l2_analytics.perf import (  # noqa: E402
    bytes_to_gb,
    dir_size_bytes,
    note_peak,
    note_temp_peak,
    process_rss_bytes,
)
from l2_analytics.templates import load_template, run_template  # noqa: E402


def _timed_profiled(
    con,
    sql: str,
    *,
    peak_rss: list[int | None],
    peak_temp: list[int | None],
    temp_dir: Path,
) -> tuple[float, list[Any], dict[str, Any]]:
    rss0 = process_rss_bytes()
    t0 = time.perf_counter()
    rows = con.execute(sql).fetchall()
    elapsed = time.perf_counter() - t0
    note_peak(peak_rss)
    note_temp_peak(peak_temp, temp_dir)
    rss1 = process_rss_bytes()
    meta = {
        "elapsed_s": elapsed,
        "rss_before_bytes": rss0,
        "rss_after_bytes": rss1,
        "temp_bytes_after": dir_size_bytes(temp_dir),
    }
    return elapsed, rows, meta


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--parquet-root", default="")
    p.add_argument("--date", default="2026-07-17")
    p.add_argument("--memory-limit", default="18GB")
    p.add_argument("--out-json", default="")
    p.add_argument(
        "--raw-bc",
        action="store_true",
        help="also time B/C against raw l2_main/l2_order (minutes for C; default uses pre-agg)",
    )
    args = p.parse_args(argv)

    root = Path(args.parquet_root) if args.parquet_root else default_parquet_root()
    temp_dir = root / "_duckdb_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    peak_rss: list[int | None] = [None]
    peak_temp: list[int | None] = [None]
    note_peak(peak_rss)
    note_temp_peak(peak_temp, temp_dir)

    t_wall0 = time.perf_counter()
    con = connect(
        parquet_root=root,
        memory_limit=args.memory_limit,
        temp_directory=temp_dir,
    )
    date = args.date
    report: dict[str, Any] = {
        "date": date,
        "parquet_root": str(root),
        "templates": {},
        "access_modes": {},
        "smoke": {},
        "profile": {},
    }

    elapsed, rows, meta = _timed_profiled(
        con,
        f"SELECT count(*), count(DISTINCT stock_code) FROM l2_main WHERE date = DATE '{date}'",
        peak_rss=peak_rss,
        peak_temp=peak_temp,
        temp_dir=temp_dir,
    )
    report["smoke"]["main_rows"] = int(rows[0][0])
    report["smoke"]["main_codes"] = int(rows[0][1])
    report["smoke"]["main_count_s"] = elapsed
    report["smoke"]["main_count_profile"] = meta

    elapsed, rows, meta = _timed_profiled(
        con,
        f"SELECT count(*) FROM l2_main WHERE date = DATE '{date}' AND stock_code = '000001.SZ'",
        peak_rss=peak_rss,
        peak_temp=peak_temp,
        temp_dir=temp_dir,
    )
    report["smoke"]["000001_ticks"] = int(rows[0][0])
    report["smoke"]["000001_filter_s"] = elapsed
    report["smoke"]["000001_filter_profile"] = meta

    size_rows = con.execute(
        f"""
        SELECT stock_code, count(*) AS n FROM l2_main
        WHERE date = DATE '{date}' AND instrument_type = 'stock'
          AND session LIKE 'continuous%'
        GROUP BY stock_code ORDER BY n DESC
        """
    ).fetchall()
    note_peak(peak_rss)
    note_temp_peak(peak_temp, temp_dir)
    mid = {"stock_code": size_rows[len(size_rows) // 2][0], "ticks": int(size_rows[len(size_rows) // 2][1])}
    small = {"stock_code": size_rows[-1][0], "ticks": int(size_rows[-1][1])}
    large = {"stock_code": size_rows[0][0], "ticks": int(size_rows[0][1])}
    for code, n in size_rows:
        if code == "000001.SZ":
            large = {"stock_code": code, "ticks": int(n)}
            break
    buckets = {"large": large, "mid": mid, "small": small}
    report["size_buckets_A"] = buckets

    mode_a: dict[str, Any] = {}
    for label, meta_b in buckets.items():
        code = meta_b["stock_code"]
        sql = f"""
        SELECT stock_code, date,
          SUM(CASE WHEN Type='B' THEN Volume*Price ELSE -Volume*Price END) AS net_inflow
        FROM l2_main
        WHERE instrument_type='stock' AND session LIKE 'continuous%'
          AND date = DATE '{date}' AND stock_code = '{code}'
        GROUP BY stock_code, date
        """
        elapsed, out, qprof = _timed_profiled(
            con, sql, peak_rss=peak_rss, peak_temp=peak_temp, temp_dir=temp_dir
        )
        mode_a[label] = {
            "stock_code": code,
            "ticks": meta_b["ticks"],
            "elapsed_s": elapsed,
            "net_inflow": float(out[0][2]) if out else None,
            "profile": qprof,
        }
    report["access_modes"]["A_single_stock_net_inflow"] = mode_a

    # B/C default to persisted pre-agg (v5.10). Raw join+groupby is optional
    # via --raw-bc (mode C historically ~185–270s/day).
    views = {
        r[0]
        for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_type='VIEW'"
        ).fetchall()
    }
    has_daily = "l2_daily_metrics" in views
    has_cluster = "l2_cluster_agg" in views

    if has_daily:
        sql_b = f"""
        SELECT stock_code, date, net_inflow
        FROM l2_daily_metrics
        WHERE date = DATE '{date}'
        ORDER BY net_inflow DESC LIMIT 50
        """
        b_source = "l2_daily_metrics"
    else:
        sql_b = f"""
        SELECT stock_code, date,
          SUM(CASE WHEN Type='B' THEN Volume*Price ELSE -Volume*Price END) AS net_inflow
        FROM l2_main
        WHERE instrument_type='stock' AND session LIKE 'continuous%'
          AND date = DATE '{date}'
        GROUP BY stock_code, date
        ORDER BY net_inflow DESC LIMIT 50
        """
        b_source = "l2_main_raw"
    elapsed_b, rows_b, prof_b = _timed_profiled(
        con, sql_b, peak_rss=peak_rss, peak_temp=peak_temp, temp_dir=temp_dir
    )
    report["access_modes"]["B_cross_section_top50"] = {
        "elapsed_s": elapsed_b,
        "n_returned": len(rows_b),
        "source": b_source,
        "top5": [
            {
                "stock_code": r[0],
                "net_inflow": float(r[2] if len(r) > 2 else r[1]),
            }
            for r in rows_b[:5]
        ],
        "profile": prof_b,
    }

    if has_cluster:
        sql_c = f"""
        SELECT count(*), coalesce(sum(fill_count),0), coalesce(sum(total_notional),0)
        FROM l2_cluster_agg WHERE date = DATE '{date}'
        """
        c_source = "l2_cluster_agg"
    else:
        sql_c = f"""
        WITH clusters AS (
          SELECT o.stock_code, o.date, o.SaleOrderID,
                 COUNT(*) AS fill_count,
                 SUM(m.Volume * m.Price) AS total_notional
          FROM l2_order o
          INNER JOIN l2_main m
            ON o.stock_code = m.stock_code AND o.date = m.date AND o.TranID = m.TranID
          WHERE m.instrument_type = 'stock' AND m.session LIKE 'continuous%'
            AND m.date = DATE '{date}'
          GROUP BY o.stock_code, o.date, o.SaleOrderID
          HAVING COUNT(*) >= 5 OR SUM(m.Volume * m.Price) >= 1000000
        )
        SELECT count(*), coalesce(sum(fill_count),0), coalesce(sum(total_notional),0) FROM clusters
        """
        c_source = "l2_order_join_l2_main_raw"
    elapsed_c, rows_c, prof_c = _timed_profiled(
        con, sql_c, peak_rss=peak_rss, peak_temp=peak_temp, temp_dir=temp_dir
    )
    report["access_modes"]["C_large_order_clusters"] = {
        "elapsed_s": elapsed_c,
        "cluster_count": int(rows_c[0][0]),
        "total_fills": int(rows_c[0][1]),
        "total_notional": float(rows_c[0][2]),
        "source": c_source,
        "profile": prof_c,
    }

    if args.raw_bc and (has_daily or has_cluster):
        sql_b_raw = f"""
        SELECT stock_code, date,
          SUM(CASE WHEN Type='B' THEN Volume*Price ELSE -Volume*Price END) AS net_inflow
        FROM l2_main
        WHERE instrument_type='stock' AND session LIKE 'continuous%'
          AND date = DATE '{date}'
        GROUP BY stock_code, date
        ORDER BY net_inflow DESC LIMIT 50
        """
        eb, rb, pb = _timed_profiled(
            con, sql_b_raw, peak_rss=peak_rss, peak_temp=peak_temp, temp_dir=temp_dir
        )
        report["access_modes"]["B_cross_section_top50_raw"] = {
            "elapsed_s": eb,
            "n_returned": len(rb),
            "source": "l2_main_raw",
            "profile": pb,
        }
        sql_c_raw = f"""
        WITH clusters AS (
          SELECT o.stock_code, o.date, o.SaleOrderID,
                 COUNT(*) AS fill_count,
                 SUM(m.Volume * m.Price) AS total_notional
          FROM l2_order o
          INNER JOIN l2_main m
            ON o.stock_code = m.stock_code AND o.date = m.date AND o.TranID = m.TranID
          WHERE m.instrument_type = 'stock' AND m.session LIKE 'continuous%'
            AND m.date = DATE '{date}'
          GROUP BY o.stock_code, o.date, o.SaleOrderID
          HAVING COUNT(*) >= 5 OR SUM(m.Volume * m.Price) >= 1000000
        )
        SELECT count(*), coalesce(sum(fill_count),0), coalesce(sum(total_notional),0) FROM clusters
        """
        ec, rc, pc = _timed_profiled(
            con, sql_c_raw, peak_rss=peak_rss, peak_temp=peak_temp, temp_dir=temp_dir
        )
        report["access_modes"]["C_large_order_clusters_raw"] = {
            "elapsed_s": ec,
            "cluster_count": int(rc[0][0]),
            "total_fills": int(rc[0][1]),
            "total_notional": float(rc[0][2]),
            "source": "l2_order_join_l2_main_raw",
            "profile": pc,
        }

    sql_d = f"""
    SELECT stock_code, count(*) AS ticks_30m
    FROM l2_main
    WHERE instrument_type='stock' AND date = DATE '{date}'
      AND session='continuous_am' AND Time >= '09:30:00' AND Time < '10:00:00'
    GROUP BY stock_code ORDER BY ticks_30m DESC LIMIT 20
    """
    elapsed_d, rows_d, prof_d = _timed_profiled(
        con, sql_d, peak_rss=peak_rss, peak_temp=peak_temp, temp_dir=temp_dir
    )
    report["access_modes"]["D_open30m_tick_speed"] = {
        "elapsed_s": elapsed_d,
        "n_returned": len(rows_d),
        "top5": [{"stock_code": r[0], "ticks_30m": int(r[1])} for r in rows_d[:5]],
        "profile": prof_d,
    }

    # Template smoke (+ optional adj / true-limit when ref views exist)
    t0 = time.perf_counter()
    vwap_rows = run_template(
        con, "vwap", extra_where=f"date = DATE '{date}' AND stock_code = '000001.SZ'"
    )
    note_peak(peak_rss)
    note_temp_peak(peak_temp, temp_dir)
    report["templates"]["vwap_000001"] = {
        "elapsed_s": time.perf_counter() - t0,
        "vwap": float(vwap_rows[0][2]) if vwap_rows else None,
        "volume": int(vwap_rows[0][3]) if vwap_rows else None,
        "ticks": int(vwap_rows[0][4]) if vwap_rows else None,
    }

    t0 = time.perf_counter()
    ni_rows = run_template(
        con, "net_inflow", extra_where=f"date = DATE '{date}' AND stock_code = '000001.SZ'"
    )
    note_peak(peak_rss)
    note_temp_peak(peak_temp, temp_dir)
    report["templates"]["net_inflow_000001"] = {
        "elapsed_s": time.perf_counter() - t0,
        "net_inflow": float(ni_rows[0][2]) if ni_rows else None,
        "buy_notional": float(ni_rows[0][3]) if ni_rows else None,
        "sell_notional": float(ni_rows[0][4]) if ni_rows else None,
    }

    t0 = time.perf_counter()
    cluster_sql = load_template("large_order_cluster").rstrip().rstrip(";")
    cluster_sql = cluster_sql.replace(
        "WHERE m.instrument_type = 'stock'",
        f"WHERE m.instrument_type = 'stock'\n  AND m.date = DATE '{date}'\n"
        f"  AND m.stock_code = '{large['stock_code']}'",
    )
    cluster_sql += "\nORDER BY total_notional DESC\nLIMIT 10"
    c_rows = con.execute(cluster_sql).fetchall()
    note_peak(peak_rss)
    note_temp_peak(peak_temp, temp_dir)
    report["templates"]["large_order_cluster_sample"] = {
        "elapsed_s": time.perf_counter() - t0,
        "stock_code": large["stock_code"],
        "top_clusters": len(c_rows),
        "top1_notional": float(c_rows[0][5]) if c_rows else None,
    }

    # Optional adj / true-limit (skip cleanly if ref views missing)
    try:
        t0 = time.perf_counter()
        adj_rows = run_template(
            con, "vwap_adj", extra_where=f"m.date = DATE '{date}'", limit=5
        )
        note_peak(peak_rss)
        report["templates"]["vwap_adj_sample"] = {
            "elapsed_s": time.perf_counter() - t0,
            "n_returned": len(adj_rows),
        }
    except Exception as exc:  # noqa: BLE001 — optional template; log reason
        report["templates"]["vwap_adj_sample"] = {"skipped": True, "reason": str(exc)[:200]}

    try:
        t0 = time.perf_counter()
        lim_rows = run_template(
            con, "limit_up_down_true", extra_where=f"m.date = DATE '{date}'", limit=20
        )
        note_peak(peak_rss)
        report["templates"]["limit_up_down_true_sample"] = {
            "elapsed_s": time.perf_counter() - t0,
            "n_returned": len(lim_rows),
        }
    except Exception as exc:  # noqa: BLE001
        report["templates"]["limit_up_down_true_sample"] = {
            "skipped": True,
            "reason": str(exc)[:200],
        }

    peak_rss_b = peak_rss[0]
    peak_temp_b = peak_temp[0]
    report["profile"] = {
        "wall_s": round(time.perf_counter() - t_wall0, 3),
        "memory_limit": args.memory_limit,
        "temp_directory": temp_dir.as_posix(),
        "peak_rss_bytes": peak_rss_b,
        "peak_rss_gb": bytes_to_gb(peak_rss_b),
        "peak_temp_bytes": peak_temp_b,
        "peak_temp_gb": bytes_to_gb(peak_temp_b),
        "rss_end_bytes": process_rss_bytes(),
        "modes_timed": {
            "A_max_s": max(v["elapsed_s"] for v in mode_a.values()),
            "B_s": elapsed_b,
            "C_s": elapsed_c,
            "D_s": elapsed_d,
        },
    }

    report["verdict"] = {
        "A_max_s": max(v["elapsed_s"] for v in mode_a.values()),
        "B_s": elapsed_b,
        "C_s": elapsed_c,
        "D_s": elapsed_d,
        "peak_rss_gb": bytes_to_gb(peak_rss_b),
        "peak_temp_gb": bytes_to_gb(peak_temp_b),
        "notes": "Single-day only; net inflow is Type=B convention, not Eastmoney-aligned.",
    }

    out_path = Path(args.out_json) if args.out_json else root / f"p0b_baseline_{date}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[wrote] {out_path}", flush=True)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
