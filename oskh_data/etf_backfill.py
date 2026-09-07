#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 日线数据回填脚本。

标的识别：交易所产品类型字段优先 + 本地白名单兜底 + 每日快照 + diff。
数据隔离：stock_data/etf/ 独立目录 + stock_data_etf_none.duckdb 独立文件。
仅 none 复权（ETF 无复权需求）。

用法：
    D:/anaconda3/envs/vanna311/python.exe -m oskh_data.etf_backfill --start 20200101
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Set, Tuple

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

from common.infra.quant_logger import get_logger

logger = get_logger(__name__)

# ETF 数据隔离目录
ETF_DATA_DIR = "stock_data/etf"
ETF_DUCKDB = "stock_data/stock_data_etf_none.duckdb"
ETF_SYMBOLS_SNAPSHOT = "stock_data/etf/.symbols_snapshot.json"
ETF_SYMBOLS_DIFF = "stock_data/etf/.symbols_diff.log"

# 本地白名单（核心 ETF，兜底用）
_CORE_ETF_WHITELIST = [
    # 宽基
    "510050.SH", "510300.SH", "510500.SH", "510880.SH",  # 上证50/沪深300/中证500/红利
    "159915.SZ", "159919.SZ", "159922.SZ", "159949.SZ",  # 创业板/沪深300/中证500/创业板50
    # 行业
    "512880.SH", "512100.SH", "512010.SH", "512690.SH",  # 证券/中证1000/医药/酒
    # 科创板
    "588000.SH", "588080.SH",  # 科创50/科创50ETF
    # 商品
    "518880.SH",  # 黄金
    # 债券
    "511010.SH", "511260.SH",  # 国债/10年国债
    # 跨境
    "513100.SH", "513050.SH", "159941.SZ",  # 纳指100/中概互联/纳指
]


def _get_xtdata():
    try:
        from xtquant import xtdata as _xt  # type: ignore[reportUnusedImport]
        return _xt
    except ImportError:
        return None


def _identify_etf_codes() -> Tuple[List[str], str]:
    """识别 ETF 标的：QMT 产品类型优先 + 本地白名单兜底。

    Returns (codes, source) where source is one of:
      - "qmt_sector" — QMT 行业列表（最完整）
      - "qmt_instrument_detail" — get_instrument_detail 扫描（采样）
      - "local_whitelist" — 本地白名单兜底（仅 20 只核心 ETF）
    """
    codes: Set[str] = set()
    source = "local_whitelist"
    xtdata = _get_xtdata()

    if xtdata is not None:
        # 优先：QMT 行业列表
        sector_hits = 0
        for sector in ("沪深ETF", "深市ETF", "上海ETF", "深圳ETF"):
            try:
                sector_codes = xtdata.get_stock_list_in_sector(sector)
                if sector_codes:
                    valid = [c for c in sector_codes if c.endswith((".SH", ".SZ"))]
                    codes.update(valid)
                    sector_hits += len(valid)
                    logger.info("QMT sector %s: %d ETFs", sector, len(valid))
            except Exception:
                pass
        if sector_hits > 0:
            source = "qmt_sector"

        # 备选：get_instrument_detail 识别 ETF 产品类型
        if not codes:
            logger.warning("QMT sector list empty, falling back to instrument detail...")
            try:
                all_stocks = xtdata.get_stock_list_in_sector("沪深A股")
                inst_hits = 0
                for code in all_stocks[:1000]:  # 采样前1000只
                    try:
                        detail = xtdata.get_instrument_detail(code)
                        if detail and "ETF" in str(detail.get("ProductType", "")):
                            codes.add(code)
                            inst_hits += 1
                    except Exception:
                        pass
                if inst_hits > 0:
                    source = "qmt_instrument_detail"
                    logger.info("Instrument detail scan found %d ETFs", inst_hits)
            except Exception:
                pass

    # 兜底：本地白名单
    if not codes:
        logger.warning(
            "QMT ETF identification failed, using local whitelist (%d ETFs). "
            "ETF coverage will be incomplete — run during trading hours for full sector list.",
            len(_CORE_ETF_WHITELIST),
        )
        codes.update(_CORE_ETF_WHITELIST)

    logger.info("ETF identification complete: %d codes, source=%s", len(codes), source)
    return sorted(codes), source


def _save_snapshot(codes: List[str]) -> None:
    """保存 ETF 标的快照 + 与前一日 diff。"""
    snapshot_path = Path(REPO) / ETF_SYMBOLS_SNAPSHOT
    diff_path = Path(REPO) / ETF_SYMBOLS_DIFF
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    # 读取旧快照
    old_codes: Set[str] = set()
    if snapshot_path.exists():
        old = json.loads(snapshot_path.read_text(encoding="utf-8"))
        old_codes = set(old.get("codes", []))

    # 写入新快照
    snapshot = {
        "date": datetime.now(timezone.utc).strftime("%Y%m%d"),
        "count": len(codes),
        "codes": codes,
    }
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    # Diff
    added = sorted(set(codes) - old_codes)
    removed = sorted(old_codes - set(codes))
    diff_lines = [
        f"# ETF symbols diff {snapshot['date']}",
        f"# Total: {len(codes)} (was {len(old_codes)})",
    ]
    for a in added:
        diff_lines.append(f"+ {a}")
    for r in removed:
        diff_lines.append(f"- {r}")
    diff_path.write_text("\n".join(diff_lines) + "\n", encoding="utf-8")

    if added or removed:
        logger.warning("ETF symbols changed: +%d / -%d (manual review recommended)",
                       len(added), len(removed),
                       context={"added": added, "removed": removed})


def main() -> int:
    parser = argparse.ArgumentParser(description="ETF 日线数据回填")
    parser.add_argument("--start", default="20200101", help="开始日期 YYYYMMDD")
    parser.add_argument("--end", default=None, help="结束日期（默认今天）")
    parser.add_argument("--identify-only", action="store_true",
                        help="仅识别 ETF 标的并保存快照，不下载数据")
    parser.add_argument("--rebuild-duckdb", action="store_true",
                        help="下载完成后重建 stock_data_etf_none.duckdb")
    args = parser.parse_args()

    end_date = args.end or datetime.now(timezone.utc).strftime("%Y%m%d")

    # ── 标的识别 + 快照 ──
    logger.info("Identifying ETF codes...")
    codes, etf_source = _identify_etf_codes()
    _save_snapshot(codes)
    print(f"ETF codes identified: {len(codes)} (source: {etf_source})")
    for c in codes[:10]:
        print(f"  {c}")
    if len(codes) > 10:
        print(f"  ... and {len(codes) - 10} more")

    if args.identify_only:
        return 0

    # ── 下载日线数据（仅 none 复权） ──
    xtdata = _get_xtdata()
    if xtdata is None:
        logger.error("QMT not available, cannot download ETF data")
        return 1

    from oskh_data.downloader import DataDownloader

    etf_dir = os.path.join(REPO, ETF_DATA_DIR)
    downloader = DataDownloader(base_dir=etf_dir)
    logger.info("Downloading ETF daily data: %d codes, %s → %s",
                len(codes), args.start, end_date)
    result = downloader.download_data(
        codes, args.start, end_date, period="1d", adjust_type="none",
    )
    print(f"Downloaded: {len(result)}/{len(codes)} ETFs")

    # ── 重建 DuckDB ──
    if args.rebuild_duckdb:
        from oskh_data.reader import StockDataReader

        db_path = os.path.join(REPO, ETF_DUCKDB)
        logger.info("Rebuilding %s ...", ETF_DUCKDB)
        db_file, elapsed = StockDataReader.build_persistent_db(
            base_dir=etf_dir, db_path=db_path,
            period="1d", adjust_type="none",
        )
        size_mb = os.path.getsize(db_file) / (1024 * 1024)
        print(f"ETF DuckDB built: {db_file} ({size_mb:.0f} MB) in {elapsed:.0f}s")

    return 0


if __name__ == "__main__":
    sys.exit(main())
