#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
fetch_float_shares.py — 批量获取 A 股流通股本 (Step 2)

通过 xtdata.get_instrument_detail() 批量获取 FloatVolume/TotalVolume，
输出 Parquet 供 chip_algorithm._adapt_columns() 读取真实流通股本。

用法：
    # 默认：从日线数据目录获取全市场标的，输出到 float_shares.parquet
    python -m oskh_data.float_shares

    # 从 stock_pool 目录收集标的
    python -m oskh_data.float_shares --from-stock-pool

    # 指定标的列表
    python -m oskh_data.float_shares --stocks 000001.SZ,000002.SZ

    # 指定输出路径
    python -m oskh_data.float_shares --output stock_data/float_shares.parquet

定时任务集成（无参数运行，适合 cron/计划任务）：
    python -m oskh_data.float_shares

输出：stock_data/float_shares.parquet
    columns: stock_code, FloatVolume, TotalVolume, name, updated_at

环境依赖：需要 QMT 客户端运行中（xtdata 连接到本地 xtquant 服务）。
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

# xtquant 延迟导入（仅 QMT 环境需要）
_xtdata = None


def _get_xtdata():
    global _xtdata
    if _xtdata is None:
        from xtquant import xtdata as _xt

        _xtdata = _xt
    return _xtdata


DEFAULT_SNAPSHOT_PATH = os.path.join(REPO, "stock_data", "float_shares.parquet")


def collect_from_daily_data(data_dir: str) -> list:
    """从日线 Parquet 目录收集全市场标的代码。"""
    codes = []
    path = Path(data_dir)
    if not path.exists():
        print(f"[WARN] Daily data directory not found: {data_dir}")
        return []

    for d in sorted(path.iterdir()):
        if d.is_dir() and d.name.startswith("symbol="):
            sym = d.name.replace("symbol=", "")
            code = sym.replace("_SZ", ".SZ").replace("_SH", ".SH").replace("_BJ", ".BJ")
            codes.append(code)
    return codes


def collect_stocks_from_pool(pool_dir: str) -> list:
    """从 stock_pool/ 目录收集所有出现过的标的代码。"""
    codes: set = set()
    pool_path = Path(pool_dir)
    if not pool_path.exists():
        print(f"[WARN] stock_pool directory not found: {pool_dir}")
        return []

    for f in sorted(pool_path.glob("*.csv")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    code = line.strip().split(",")[0].strip()
                    if code.isdigit() and len(code) == 6:
                        codes.add(code)
        except Exception as e:
            print(f"[WARN] Failed to read {f.name}: {e}")

    if not codes:
        return []

    result = []
    for code in sorted(codes):
        if code.startswith(("60", "68")):
            result.append(f"{code}.SH")
        elif code.startswith(("00", "30")):
            result.append(f"{code}.SZ")
        elif code.startswith(("8", "4", "9")):
            result.append(f"{code}.BJ")
        else:
            result.append(f"{code}.SZ")
    return result


def fetch(stock_list: list) -> list:
    """批量获取流通股本，返回 dict 列表。"""
    rows = []
    n = len(stock_list)
    for i, code in enumerate(stock_list):
        try:
            detail = _get_xtdata().get_instrument_detail(code)
            if detail:
                rows.append({
                    "stock_code": code,
                    "FloatVolume": detail.get("FloatVolume"),
                    "TotalVolume": detail.get("TotalVolume"),
                    "name": detail.get("InstrumentName", ""),
                })
        except Exception as e:
            print(f"[WARN] {code}: {e}")

        if (i + 1) % 200 == 0:
            print(f"  ... {i + 1}/{n}")

    return rows


def diff_summary(old_df: pd.DataFrame, new_df: pd.DataFrame) -> str:
    """对比新旧股本数据，生成变更摘要。"""
    lines = []
    if old_df.empty:
        lines.append("  (首次生成，无历史对比)")
        return "\n".join(lines)

    old_map = dict(zip(old_df["stock_code"], old_df["FloatVolume"]))
    new_map = dict(zip(new_df["stock_code"], new_df["FloatVolume"]))

    old_set = set(old_map.keys())
    new_set = set(new_map.keys())

    added = new_set - old_set
    removed = old_set - new_set
    if added:
        lines.append(f"  新增标的: {len(added)} ({', '.join(sorted(added)[:10])}{'...' if len(added) > 10 else ''})")
    if removed:
        lines.append(f"  移除标的: {len(removed)} ({', '.join(sorted(removed)[:10])}{'...' if len(removed) > 10 else ''})")

    changed = []
    for code in old_set & new_set:
        ov = old_map.get(code)
        nv = new_map.get(code)
        if ov and nv and ov != nv:
            pct = (nv - ov) / ov * 100
            if abs(pct) > 0.1:  # 只报告 >0.1% 的变化
                changed.append((code, pct))
    if changed:
        changed.sort(key=lambda x: -abs(x[1]))
        detail = ", ".join(f"{c}({p:+.1f}%)" for c, p in changed[:10])
        if len(changed) > 10:
            detail += f" ...共 {len(changed)} 只"
        lines.append(f"  股本变化: {detail}")
    if not added and not removed and not changed:
        lines.append("  无变化")
    return "\n".join(lines)


def build_snapshot_df(rows: list, now_ts: str) -> pd.DataFrame:
    """构建 latest snapshot DataFrame。"""
    new_df = pd.DataFrame(rows)
    if new_df.empty:
        return new_df
    new_df["updated_at"] = now_ts
    return new_df.sort_values("stock_code").reset_index(drop=True)


def normalize_snapshot_date(snapshot_date=None) -> pd.Timestamp:  # type: ignore[reportArgumentType]
    """将快照日期归一化为交易日维度日期。"""
    if snapshot_date:
        return pd.Timestamp(snapshot_date).normalize()
    return pd.Timestamp.today().normalize()


def main():
    parser = argparse.ArgumentParser(description="批量获取 A 股流通股本")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--stocks", default=None,
                     help="逗号分隔的标的列表，如 000001.SZ,000002.SZ")
    src.add_argument("--from-stock-pool", action="store_true",
                     help="从 stock_pool/ 目录自动收集标的")
    src.add_argument("--from-daily-data", action="store_true",
                     help="从 stock_data/period=1d/dividend_type=front/ 收集全市场标的（默认）")
    parser.add_argument("--output", default=DEFAULT_SNAPSHOT_PATH,
                        help="输出 Parquet 路径（默认 stock_data/float_shares.parquet）")
    parser.add_argument("--diff", action="store_true", default=True,
                        help="与已有 parquet 对比变更（默认开启）")
    parser.add_argument("--no-diff", action="store_false", dest="diff",
                        help="跳过变更对比")
    args = parser.parse_args()

    # ── 收集标的列表 ──
    if args.stocks:
        stock_list = [s.strip() for s in args.stocks.split(",") if s.strip()]
        source_label = f"--stocks ({len(stock_list)} codes)"
    elif args.from_stock_pool:
        pool_dir = os.path.join(REPO, "stock_pool")
        stock_list = collect_stocks_from_pool(pool_dir)
        source_label = f"stock_pool ({len(stock_list)} stocks)"
    else:
        # 默认：从日线前复权数据获取全市场标的
        daily_dir = os.path.join(REPO, "stock_data", "period=1d", "dividend_type=front")
        stock_list = collect_from_daily_data(daily_dir)
        source_label = f"daily data ({len(stock_list)} stocks)"

    if not stock_list:
        print("[ERROR] No stocks to fetch")
        sys.exit(1)

    # ── 时间戳 ──
    from common.infra.timekeeping import mono_now

    _t0 = mono_now()
    _now = datetime.now(timezone.utc)
    print(f"[{_now.strftime('%Y-%m-%d %H:%M:%S')} UTC] fetch_float_shares start")
    print(f"  Source: {source_label}")

    # ── 批量获取 ──
    print(f"  Fetching float shares for {len(stock_list)} stocks ...")
    rows = fetch(stock_list)
    ok = sum(1 for r in rows if r.get("FloatVolume"))
    print(f"  Fetched: {ok}/{len(stock_list)} stocks returned FloatVolume")

    # ── 构建 DataFrame ──
    now_ts = datetime.now(timezone.utc).isoformat()
    new_df = build_snapshot_df(rows, now_ts)

    # ── 变更对比 ──
    if args.diff and os.path.exists(args.output):
        old_df = pd.read_parquet(args.output)
        print(f"  Previous: {len(old_df)} stocks")
        print(diff_summary(old_df, new_df))

    # ── 输出（含备份与门禁）──
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    # 备份旧版本
    if output.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = output.with_name(f"{output.stem}.bak.{ts}{output.suffix}")
        output.rename(backup_path)
        print(f"  Backed up: {backup_path.name}")

    new_df.to_parquet(str(output), index=False)

    # 覆盖率门禁：基于有效 float_shares 值（非空且 >0），低于阈值时回滚
    _COVERAGE_THRESHOLD = 0.95
    daily_dir = os.path.join(os.path.dirname(str(output)), "period=1d", "dividend_type=front")
    if os.path.exists(daily_dir):
        total_symbols = sum(
            1 for d in os.listdir(daily_dir)
            if d.startswith("symbol=") and os.path.exists(os.path.join(daily_dir, d, "data.parquet"))
        )
        # P0-1 fix: 计算有效值覆盖率（>0 且非空），而非总行数覆盖率
        valid_count = int((new_df["FloatVolume"] > 0).sum()) if "FloatVolume" in new_df.columns else 0
        coverage = valid_count / total_symbols if total_symbols > 0 else 0
        print(f"  Coverage: {valid_count}/{total_symbols} valid = {coverage:.2%} (total rows: {len(new_df)})")
        if coverage < _COVERAGE_THRESHOLD:
            # 回滚
            output.unlink()
            if output.exists():
                pass  # parquet 已删除
            backup_path.rename(output)
            print(f"  [FAIL] Valid coverage {coverage:.2%} < {_COVERAGE_THRESHOLD:.0%}, rolled back to backup")
            sys.exit(1)

    elapsed = mono_now() - _t0
    _done = datetime.now(timezone.utc)
    print(f"[{_done.strftime('%Y-%m-%d %H:%M:%S')} UTC] fetch_float_shares done "
          f"({elapsed:.1f}s, {len(new_df)} rows → {output})")


if __name__ == "__main__":
    main()
