#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
backfill_daily_data.py — 日线/分钟线历史数据向前补录

用法：
    python -m oskh_data.backfill --period 1d --start 20200101 --end 20250101 --batch 100
    python -m oskh_data.backfill --period 1m --start 20250101 --batch 50

说明：
    - 从 QMT 获取全市场 A 股列表（或从本地 float_shares.parquet 备选）。
    - 对每只股票，下载 [start, end] 区间的数据。
    - 日线：三种复权类型（front / back / none）依次执行。
    - 分钟线：仅 none 复权，支持断点续传（进度保存在
      stock_data/.backfill_1m_progress.json）。
    - 新数据与本地已有数据自动合并（去重+排序）。
    - 失败的股票记录到日志，供后续重试。

前置条件：
    - miniQMT 客户端已启动（xtdata 可连接）。
"""

import argparse
from .symbol_format import to_partition_key, to_canonical_symbol
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Set

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

import pandas as pd

from oskh_data.pandas_typing import as_series  # noqa: F401

from common.infra.quant_logger import get_logger
from common.infra.data_root import (
    resolve_e_stock_data_container,
    resolve_period_root,
    resolve_source_parquet,
)
from oskh_data.downloader import DataDownloader
from oskh_data.reader import StockDataReader

logger = get_logger(__name__)


# xtquant 延迟导入（仅 QMT 环境需要）
_xtdata = None
_QMT_AVAILABLE = None


def _get_xtdata():
    global _xtdata, _QMT_AVAILABLE
    if _xtdata is None and _QMT_AVAILABLE is None:
        try:
            from oskh_data.qmt_xtdata import get_xtdata

            _xtdata = get_xtdata()
            _QMT_AVAILABLE = True
        except Exception:
            _QMT_AVAILABLE = False
            logger.warning(
                "xtquant 未导入，无法从 QMT 获取股票列表，将 fallback 到本地 float_shares.parquet"
            )
    return _xtdata


def _qmt_available() -> bool:
    _get_xtdata()
    return bool(_QMT_AVAILABLE)


DEFAULT_START = "20200101"
DEFAULT_END = "20250101"
DEFAULT_BATCH = 100
BASE_DIR = str(resolve_e_stock_data_container())
FLOAT_SHARES_PATH = str(resolve_source_parquet("float_shares.parquet"))
FAILED_LOG_PATH = os.path.join(REPO, "backtest_output", "backfill_failed.json")


# P1-4: 全市场股票数量的保守下限。fallback 结果低于此值时拒绝执行，
# 防止新上市股票因 QMT 不可达而被永久排除在回补之外。
_MIN_EXPECTED_MARKET_SIZE = 4500


def _get_all_a_stock_codes() -> List[str]:
    """获取全市场 A 股代码列表（含主板、科创板、创业板、北交所）。优先 QMT，备选本地。"""
    if _qmt_available():
        xtdata = _get_xtdata()
        assert xtdata is not None, "QMT available but xtdata module is None"
        try:
            all_codes: set = set()
            sector_candidates = [
                '沪深A股', '上海A股', '深圳A股', '北京A股',
                '科创板', '创业板', '北交所', '京市A股',
            ]
            for sector in sector_candidates:
                try:
                    codes = xtdata.get_stock_list_in_sector(sector)
                    if codes:
                        valid = [c for c in codes if c.endswith(('.SH', '.SZ', '.BJ'))]
                        all_codes.update(valid)
                        logger.info("QMT 板块 '%s': %d 只", sector, len(valid))
                except Exception:
                    pass  # 该板块名称不存在，继续尝试下一个

            if len(all_codes) > 1000:
                logger.info("QMT 全市场合并去重后: %d 只", len(all_codes))
                return sorted(all_codes)
        except Exception as e:
            logger.warning("QMT 获取股票列表失败: %s", e)

    # P1-4 fix: fallback 链路增加覆盖度校验。
    # fallback 源（float_shares / front 目录）都是"已有数据"的闭集——
    # 新上市股票不在其中。覆盖度过低时拒绝执行，防止静默漏掉新标的。
    fallback_source = ""
    codes: List[str] = []

    if os.path.exists(FLOAT_SHARES_PATH):
        df = pd.read_parquet(FLOAT_SHARES_PATH)
        codes = df["stock_code"].dropna().unique().tolist()
        fallback_source = os.path.basename(FLOAT_SHARES_PATH)
    else:
        front_dir = str(resolve_period_root("1d") / "dividend_type=front")
        if os.path.exists(front_dir):
            codes = [
                to_canonical_symbol(d)
                for d in os.listdir(front_dir)
                if d.startswith("symbol=")
            ]
            fallback_source = "本地 front 目录"

    if not codes:
        raise RuntimeError(
            "无法获取股票列表：QMT 不可用、float_shares.parquet 不存在、本地 front 目录为空"
        )

    logger.warning(
        "QMT 不可用，从 %s fallback 获取: %d 只（QMT 在线时列表可能更全）",
        fallback_source, len(codes),
    )

    if len(codes) < _MIN_EXPECTED_MARKET_SIZE:
        raise RuntimeError(
            f"Fallback 股票列表覆盖度过低: {len(codes)} 只 < {_MIN_EXPECTED_MARKET_SIZE} 只。"
            f"QMT 不可用且 {fallback_source} 中标的数远低于全市场预期，"
            f"继续执行会导致新上市股票永久不被回补。请先恢复 QMT 连接。"
        )

    return sorted(codes)


def _get_codes_for_minute_backfill() -> List[str]:
    """获取需要补录分钟线的股票：有日线但无分钟线。"""
    daily_dir = str(resolve_period_root("1d") / "dividend_type=none")
    minute_dir = str(resolve_period_root("1m") / "dividend_type=none")

    if not os.path.exists(daily_dir):
        raise RuntimeError(f"日线目录不存在: {daily_dir}")

    all_codes = {
        to_canonical_symbol(d)
        for d in os.listdir(daily_dir)
        if d.startswith("symbol=")
    }

    has_minute = set()
    if os.path.exists(minute_dir):
        has_minute = {
            to_canonical_symbol(d)
            for d in os.listdir(minute_dir)
            if d.startswith("symbol=")
        }

    remaining = sorted(all_codes - has_minute)
    logger.info("分钟线待补录: %d 只 (已有 %d 只)", len(remaining), len(has_minute))
    return remaining


def _progress_path(period: str) -> str:
    return os.path.join(BASE_DIR, f".backfill_{period}_progress.json")


def _load_progress(period: str) -> Set[str]:
    path = _progress_path(period)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f).get("done", []))
    return set()


def _save_progress(period: str, done: Set[str]) -> None:
    path = _progress_path(period)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"done": sorted(list(done))}, f, ensure_ascii=False, indent=2)


def _verify_minute_bar_integrity(done: Set[str], end_date: str) -> Set[str]:
    """Spot-check: verify stocks in progress have 15:00 bars for last 5 trading days.

    Returns set of stocks that FAIL the check (should be removed from progress).
    Sample-based: checks at most 50 random stocks to keep runtime bounded.
    """
    import random

    if not done:
        return set()
    # Sample up to 50 stocks from progress
    sample = random.sample(sorted(done), min(50, len(done)))
    # Determine last 5 trading days from the data files themselves
    minute_dir = str(resolve_period_root("1m") / "dividend_type=none")
    trading_days: Set[str] = set()
    for code in sample[:5]:  # use first 5 stocks to discover recent trading days
        sym_dir = to_partition_key(code)
        data_path = os.path.join(minute_dir, f"symbol={sym_dir}", "data.parquet")
        if not os.path.exists(data_path):
            continue
        try:
            df = pd.read_parquet(data_path, columns=["time"])
            df["date"] = pd.to_datetime(df["time"], unit="ms").dt.strftime("%Y%m%d")
            trading_days.update(df["date"].unique()[-10:])
        except Exception:
            continue
    if not trading_days:
        return set()
    recent_days = sorted(trading_days)[-5:]

    stale: Set[str] = set()
    for code in sample:
        sym_dir = to_partition_key(code)
        data_path = os.path.join(minute_dir, f"symbol={sym_dir}", "data.parquet")
        if not os.path.exists(data_path):
            stale.add(code)
            continue
        try:
            df = pd.read_parquet(data_path, columns=["time"])
            df["date"] = pd.to_datetime(df["time"], unit="ms").dt.strftime("%Y%m%d")
            df["minute"] = pd.to_datetime(df["time"], unit="ms").dt.strftime("%H%M")
            for day in recent_days:
                day_bars = df[df["date"] == day]
                if day_bars.empty:
                    continue  # no data for this day (may be weekend/holiday)
                has_close = "1500" in as_series(day_bars["minute"]).values
                if not has_close:
                    stale.add(code)
                    break
        except Exception:
            stale.add(code)
    return stale


def _clear_progress(period: str) -> None:
    path = _progress_path(period)
    if os.path.exists(path):
        os.remove(path)


def _chunked(lst: List, n: int):
    """将列表分批。"""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _load_failed_set() -> Set[str]:
    """加载之前记录的失败股票。"""
    if os.path.exists(FAILED_LOG_PATH):
        with open(FAILED_LOG_PATH, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def _save_failed_set(failed: Set[str]) -> None:
    """保存失败股票到日志。"""
    os.makedirs(os.path.dirname(FAILED_LOG_PATH), exist_ok=True)
    with open(FAILED_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(list(failed)), f, ensure_ascii=False, indent=2)


def _rebuild_duckdb(rebuild_period: str) -> None:
    """重建指定周期的 .duckdb 持久化文件（仅日线；分钟线已切 :memory: 无需 rebuild）。

    ``none`` / ``front`` 失败会 raise（编排器须感知 exit≠0）。
    ``back``：分区不存在则跳过；存在但失败仅 WARNING（日常默认不下 back）。
    """
    logger.info("=== 重建 .duckdb 持久化文件 ===")
    periods_to_build = []
    if rebuild_period == 'all':
        periods_to_build = [
            ('1d', 'front'), ('1d', 'none'), ('1d', 'back'),
        ]
    elif rebuild_period == '1d':
        periods_to_build = [('1d', 'front'), ('1d', 'none'), ('1d', 'back')]
    elif rebuild_period == '1m':
        logger.info("分钟线已切 :memory: + read_parquet(glob)，无需 rebuild，跳过")
        return

    required_failed: list[str] = []
    for period, adjust in periods_to_build:
        period_dir = resolve_period_root(period) / f"dividend_type={adjust}"
        if adjust == "back" and not period_dir.is_dir():
            logger.info(
                f"{period}/{adjust}: 分区不存在，跳过 rebuild（日常默认不下 back）"
            )
            continue
        try:
            db_path, elapsed = StockDataReader.build_persistent_db(
                base_dir=BASE_DIR, period=period, adjust_type=adjust
            )
            size_mb = db_path.stat().st_size / (1024 * 1024)
            logger.info(
                f"{db_path.name} rebuilt: {size_mb:.0f} MB in {elapsed:.0f}s"
            )
        except Exception as e:
            # quant_logger: use f-string; %-style args are NOT expanded
            msg = f"{period}/{adjust} .duckdb rebuild failed: {e}"
            if adjust in ("none", "front"):
                logger.error(msg)
                required_failed.append(msg)
            else:
                logger.warning(f"{msg} (non-fatal for back)")
    if required_failed:
        raise RuntimeError("; ".join(required_failed))


# ═══════════════════════════════════════════════════════════════════════════
# 安全门禁（会亏大钱 / 不可逆出错）
# ═══════════════════════════════════════════════════════════════════════════

# 接近开盘时 graceful exit 的提前量（分钟）
_GRACEFUL_EXIT_THRESHOLD_MIN = 30


def _gate_time_window(period: str) -> None:
    """门禁 1：交易日盘中禁止 backfill（启动期检查）。

    使用 common SSE cache（``get_trade_days_sse``）判断交易日，
    使用 ``shanghai_now()`` 获取北京时间。

    允许时间窗：
    - 非交易日任意时间
    - 交易日 15:30 之后 / 9:00 之前
    - 分钟线（period='1m'）强制执行；日线警告但不阻断
    """
    from common.infra.timekeeping import shanghai_now

    now = shanghai_now()
    today_str = now.strftime("%Y%m%d")
    hm = now.hour * 60 + now.minute

    # 从 common SSE cache 判断今天是否为交易日
    try:
        from common.infra.trading_calendar_pmc import get_trade_days_sse

        cal = get_trade_days_sse(since=today_str, until=today_str)
        is_trading_day = cal is not None and not cal.empty and str(cal.iloc[0]["cal_date"]) == today_str
    except Exception as _cal_exc:
        # 日历不可用时保守处理：周一至周五视为交易日。
        logger.warning(
            "交易日历不可用，fallback 到周一至周五判断。"
            "非交易日的 weekday 会被误判为交易日，导致 backfill 被错误阻断（fail-safe）。"
            "请检查 common.infra.trading_calendar_pmc / pandas_market_calendars。",
            context={"error_type": type(_cal_exc).__name__, "error": str(_cal_exc)[:200]},
        )
        is_trading_day = now.weekday() < 5

    # 交易时段 9:15–15:15
    in_market_hours = is_trading_day and (9 * 60 + 15) <= hm <= (15 * 60 + 15)
    # 安全窗口：非交易日 或 9:00 之前 或 15:30 之后
    in_safe_window = (not is_trading_day) or hm <= (9 * 60) or hm >= (15 * 60 + 30)

    if in_market_hours and period == '1m':
        logger.error(
            f"门禁 1 阻断：当前处于 A 股交易时段（{now.strftime('%H:%M')}），"
            "分钟线 backfill 禁止运行。请在 15:30 之后或非交易日执行。"
        )
        raise SystemExit(1)

    if in_market_hours:
        logger.warning(
            f"当前处于交易时段但 period='{period}'（非分钟线），继续执行但请注意 QMT 资源竞争"
        )

    if not in_safe_window and not in_market_hours:
        logger.warning(
            f"当前处于交易日非交易时段（{now.strftime('%H:%M')}），"
            "但不在安全窗口内（9:00-9:15 或 15:15-15:30），继续执行"
        )


def _gate_check_approaching_market_open() -> bool:
    """门禁 1b：运行期检查——是否接近下一个交易日的开盘时间。

    用于批次循环内的 graceful exit：若接近开盘（< 30 min），
    保存进度后退出，避免跨夜 backfill 撞上第二天开盘。

    Returns:
        True 如果需要 graceful exit。
    """
    from common.infra.timekeeping import shanghai_now

    now = shanghai_now()
    today_str = now.strftime("%Y%m%d")

    # 从 common SSE cache 判断今天是否为交易日
    try:
        from common.infra.trading_calendar_pmc import get_trade_days_sse

        cal = get_trade_days_sse(since=today_str, until=today_str)
        is_trading_day = cal is not None and not cal.empty and str(cal.iloc[0]["cal_date"]) == today_str
    except Exception as _cal_exc:
        logger.warning(
            "交易日历不可用（门禁1b），fallback 到周一至周五判断",
            context={"error_type": type(_cal_exc).__name__, "error": str(_cal_exc)[:200]},
        )
        is_trading_day = now.weekday() < 5

    # 非交易日不触发
    if not is_trading_day:
        return False

    hm = now.hour * 60 + now.minute
    market_start_min = 9 * 60 + 15
    minutes_to_open = market_start_min - hm
    return 0 < minutes_to_open <= _GRACEFUL_EXIT_THRESHOLD_MIN


def _gate_check_parquet_health(period: str = '1m') -> int:
    """门禁 2：扫描 parquet 文件完整性（损坏文件会导致 :memory: 视图创建失败）。

    使用 DuckDB 快速扫描所有 parquet footer，检测损坏/截断文件。

    Returns:
        损坏文件数量。0 = 全部健康。
    """
    import duckdb as _duckdb

    parquet_glob = os.path.join(
        str(resolve_period_root(period) / 'dividend_type=none' / 'symbol=*' / 'data.parquet')
    ).replace('\\', '/')

    con = _duckdb.connect(':memory:')
    try:
        result = con.execute(f"""
            SELECT COUNT(*) FROM read_parquet('{parquet_glob}',
                                               hive_partitioning=1, union_by_name=True)
        """).fetchone()
        total = result[0] if result else 0
        logger.info(f"门禁 2 通过：parquet 扫描正常，{total:,} 行")
        return 0
    except Exception as e:
        err_msg = str(e)
        # 尝试提取损坏文件名
        logger.error(f"门禁 2 失败：parquet 扫描异常 — {err_msg[:300]}")
        return 1
    finally:
        con.close()


def _gate_verify_freshness(period: str, done_count: int) -> None:
    """门禁 3：下载完成后验证 parquet 数量和日期新鲜度。

    检查项：
    1. parquet 目录数 >= 预期下限（5500 只）
    2. 抽查 000001.SZ 的最新日期不超过 3 个交易日之前
    """
    import pandas as _pd
    from pathlib import Path as _Path

    parquet_dir = resolve_period_root(period) / 'dividend_type=none'
    if not parquet_dir.is_dir():
        logger.warning("门禁 3 跳过：parquet 目录不存在")
        return

    dirs = [d for d in parquet_dir.iterdir()
            if d.is_dir() and d.name.startswith('symbol=') and (d / 'data.parquet').exists()]
    actual = len(dirs)

    if actual < 5500:
        logger.warning(f"门禁 3 警告：parquet 目录数 {actual} < 5500（可能下载未完成或部分股票缺失）")
    else:
        logger.info(f"门禁 3 通过：parquet 目录数 {actual} >= 5500 ✅")

    # 抽查 000001.SZ 的新鲜度
    from common.infra.timekeeping import shanghai_now
    benchmark = parquet_dir / 'symbol=000001_SZ' / 'data.parquet'
    if benchmark.exists():
        try:
            df = _pd.read_parquet(benchmark, engine='pyarrow')
            if not df.empty and hasattr(df.index, 'max'):
                latest = df.index.max()
                if latest is not None and not bool(pd.isna(latest)):
                    ts = pd.Timestamp(str(latest))
                    if not bool(pd.isna(ts)):
                        days_behind = (shanghai_now().replace(tzinfo=None) - ts).days
                        if days_behind > 3:
                            logger.warning(
                                f"门禁 3 警告：000001.SZ 最新日期 {str(latest)[:10]}（{days_behind} 天前），可能 QMT 数据延迟"
                            )
                        else:
                            logger.info(
                                f"门禁 3 通过：000001.SZ 最新日期 {str(latest)[:10]}（{days_behind} 天前）✅"
                            )
        except Exception as e:
            logger.warning(f"门禁 3：000001.SZ 抽查失败 — {e}")


def _gate_inventory_snapshot(period: str = '1m', adjust_type: str = 'none') -> None:
    """门禁 4（可选）：下载前全量盘点——每只股票最新日期分布。

    用途：下载前了解数据参差不齐程度，判断是否需要全量回补。
    使用 DuckDB 扫描所有 parquet 的 max(time) 按 symbol 聚合，输出日期直方图。
    纯只读、不阻断，仅打印报告。

    Args:
        period: '1m' 或 '1d'
        adjust_type: 复权类型（日线默认 'front'，分钟线固定 'none'）
    """
    import duckdb as _duckdb

    adj = 'none' if period == '1m' else adjust_type
    parquet_glob = str(
        resolve_period_root(period)
        / f'dividend_type={adj}' / 'symbol=*' / 'data.parquet'
    ).replace('\\', '/')

    label = '分钟线' if period == '1m' else f'日线({adj})'

    logger.info(f"门禁 4（可选）：全量盘点 {label} 数据日期分布...")
    con = _duckdb.connect(':memory:')
    try:
        rows = con.execute(f"""
            SELECT symbol, MAX(time) as latest_time
            FROM read_parquet('{parquet_glob}', hive_partitioning=1, union_by_name=True)
            GROUP BY symbol
            ORDER BY latest_time DESC
        """).fetchall()

        if not rows:
            logger.warning(f"门禁 4：未找到任何 {label} parquet 数据")
            return

        from collections import Counter as _Counter
        from datetime import datetime as _dt

        date_counter: _Counter = _Counter()
        for sym, ts in rows:
            if ts is None:
                date_counter['(无数据)'] += 1
                continue
            try:
                # 分钟线和日线 parquet 的 time 列统一为 UTC 午夜毫秒 int64
                d = _dt.utcfromtimestamp(int(ts) / 1000).strftime('%Y-%m-%d')
            except (ValueError, OSError, TypeError):
                d = str(ts)[:10]
            date_counter[d] += 1

        total = len(rows)
        logger.info(f"门禁 4 盘点完成：{total} 只 {label}，{len(date_counter)} 个不同日期")

        max_count = max(date_counter.values()) if date_counter else 1
        bar_width = 40
        print(f"\n{'='*60}")
        print(f"  {label} 数据日期分布（{total} 只）")
        print(f"{'='*60}")
        for date_str in sorted(date_counter.keys(), reverse=True):
            count = date_counter[date_str]
            pct = count / total * 100
            bar_len = int(count / max_count * bar_width)
            bar = '█' * bar_len
            if pct < 1.0:
                flag = ' ⚠️ 严重落后'
            elif pct < 80.0:
                flag = ' 📍'
            else:
                flag = ' ← 主流'
            print(f"  {date_str}: {bar} {count:>5} 只 ({pct:5.1f}%){flag}")
        print(f"{'='*60}\n")

        if len(date_counter) > 3:
            top_date, top_count = date_counter.most_common(1)[0]
            if top_count / total < 0.90:
                logger.warning(
                    f"门禁 4：{label} 数据日期分散（主流 {top_date} 仅 {top_count/total*100:.0f}%），"
                    "建议执行全量 backfill 后再使用"
                )
    except Exception as e:
        logger.error(f"门禁 4 失败：{e}")
    finally:
        con.close()


def _download_impl(args):
    """download / all 子命令的共享下载逻辑。返回 failed_codes 集合。"""
    if args.end is None:
        if args.period == "1m":
            args.end = datetime.now(timezone.utc).strftime("%Y%m%d")
        else:
            args.end = DEFAULT_END

    if args.period == "1m":
        adjust_types = ["none"]
        logger.info("分钟线强制使用 none 复权")
        # 门禁 1：时间窗检查（交易日盘中禁止分钟线 backfill）
        _gate_time_window(args.period)
        # 门禁 2：parquet 健康扫描（损坏文件会导致 :memory: 视图创建失败）
        if not args.retry_failed:
            _gate_check_parquet_health(args.period)
    else:
        adjust_types = [a.strip() for a in args.adjust_types.split(",")]

    if args.codes:
        with open(args.codes, "r", encoding="utf-8") as f:
            all_codes = [line.strip() for line in f if line.strip()]
        logger.info("从文件加载股票列表: %d 只", len(all_codes))
    elif args.period == "1m":
        all_codes = _get_codes_for_minute_backfill()
    else:
        all_codes = _get_all_a_stock_codes()

    if args.retry_failed:
        failed_codes_list = _load_failed_set()
        all_codes = [c for c in all_codes if c in failed_codes_list]
        logger.info("重试模式: %d 只上次失败的股票", len(all_codes))

    def _is_valid_code(c: str) -> bool:
        if not (c.endswith(('.SH', '.SZ', '.BJ')) and len(c.split('.')[0]) == 6):
            return False
        prefix = c.split('.')[0]
        # 北交所/新三板有效前缀：43/83/87/82/92（920新代码），排除821等无效号段
        if c.endswith('.BJ'):
            return prefix.startswith(('4', '8', '9')) and not prefix.startswith('821')
        return True

    formatted_codes = [c for c in all_codes if _is_valid_code(c)]
    invalid_count = len(all_codes) - len(formatted_codes)
    if invalid_count:
        logger.warning("过滤掉 %d 只无效代码（如821xxx等）", invalid_count)
    if not formatted_codes:
        logger.error("无有效股票代码，退出")
        sys.exit(1)
    logger.info("有效股票代码: %d 只", len(formatted_codes))

    done: Set[str] = set()
    if args.period == "1m":
        done = _load_progress("1m")
        before = len(formatted_codes)
        formatted_codes = [c for c in formatted_codes if c not in done]
        skipped = before - len(formatted_codes)
        if skipped:
            logger.info("断点续传: 已跳过 %d 只，剩余 %d 只", skipped, len(formatted_codes))
        if not formatted_codes:
            logger.info("所有股票的分钟线数据已补录完成")
            _clear_progress("1m")
            return set()

    logger.info("复权类型: %s", adjust_types)
    logger.info("时间范围: %s ~ %s", args.start, args.end)
    logger.info("每批数量: %d", args.batch)

    downloader = DataDownloader(base_dir=BASE_DIR)
    failed_codes: Set[str] = set()

    for adjust in adjust_types:
        logger.info("=== 开始补录: dividend_type=%s ===", adjust)
        batches = list(_chunked(formatted_codes, args.batch))
        for idx, batch in enumerate(batches, start=1):
            logger.info("[Batch %d/%d] %s | 本批 %d 只", idx, len(batches), adjust, len(batch))
            try:
                result = downloader.download_data(
                    stock_list=batch,
                    start_time=args.start,
                    end_time=args.end,
                    period=args.period,
                    adjust_type=adjust,
                    incrementally=not getattr(args, "no_incremental", False),
                )
                success_count = len(result) if result is not None else 0
                fail_count = len(batch) - success_count
                if fail_count > 0:
                    logger.warning("成功: %d, 失败/空数据: %d", success_count, fail_count)
                else:
                    logger.info("成功: %d/%d", success_count, len(batch))

                if args.period == "1m" and result is not None:
                    done.update(result.keys())
                    _save_progress("1m", done)

            except Exception as e:
                # Phase 2 P1 fix: don't mark ALL batch stocks as failed when
                # a post-download exception occurs.  If download_data() already
                # succeeded for some stocks (in `result`), only the missing ones
                # should be retried.
                logger.error("批次异常: %s", e)
                if isinstance(result, dict) and "_download_error" not in result:
                    # result has real stock data — only missing stocks failed
                    succeeded = set(result.keys())
                    batch_failed = [c for c in batch if c not in succeeded]
                    failed_codes.update(batch_failed)
                    logger.warning(
                        "批次 %d 异常但 %d 只已下载成功，仅标记 %d 只失败",
                        idx, len(succeeded), len(batch_failed),
                    )
                else:
                    failed_codes.update(batch)

            if idx < len(batches):
                time.sleep(0.5)

            # 门禁 1b：运行期 graceful exit（接近开盘自动退出，防止跨夜撞开盘）
            if args.period == "1m" and _gate_check_approaching_market_open():
                logger.warning(
                    "门禁 1b 触发：接近开盘时间，graceful exit。已完成 %d/%d 批，进度已保存",
                    idx, len(batches),
                )
                return failed_codes

        logger.info("=== %s 补录完成 ===", adjust)

    # 门禁 3：分钟线下载完成后验证新鲜度
    if args.period == "1m" and not failed_codes:
        _gate_verify_freshness(args.period, len(done))
        # Phase 2 P2 fix: spot-check progress entries for missing 15:00 bars.
        # Partially-downloaded stocks (network cut mid-batch) would have been
        # marked "done" but lack complete minute data for the last trading day.
        # Remove any stock that fails this check so it gets re-downloaded.
        stale_progress = _verify_minute_bar_integrity(done, args.end)
        if stale_progress:
            logger.warning(
                "完整性校验: %d 只股票最后交易日缺 15:00 bar，移除进度重新下载",
                len(stale_progress),
            )
            for code in stale_progress:
                done.discard(code)
            _save_progress("1m", done)

    if failed_codes:
        _save_failed_set(failed_codes)
        logger.warning("共 %d 只股票失败，已记录到 %s", len(failed_codes), FAILED_LOG_PATH)
        logger.warning("下次可用 --retry-failed 重试")
    else:
        logger.info("全部股票补录成功，无失败记录")
        if os.path.exists(FAILED_LOG_PATH):
            os.remove(FAILED_LOG_PATH)
        if args.period == "1m":
            _clear_progress("1m")

    return failed_codes


def _add_download_args(subparser):
    """为 download / all 子命令添加下载相关参数。"""
    subparser.add_argument("--period", default="1d", choices=["1d", "1m"])
    subparser.add_argument("--start", default=DEFAULT_START, help="起始日期 YYYYMMDD")
    subparser.add_argument("--end", default=None, help="结束日期 YYYYMMDD")
    subparser.add_argument("--batch", type=int, default=DEFAULT_BATCH, help="每批股票数量")
    subparser.add_argument("--adjust-types", default="front,back,none", help="复权类型")
    subparser.add_argument("--retry-failed", action="store_true", help="仅重试上次失败")
    subparser.add_argument("--codes", default=None, help="指定股票代码文件路径")
    subparser.add_argument("--inventory", action="store_true", help="下载前全量盘点数据日期分布（只读，不下载）")
    subparser.add_argument(
        "--no-incremental",
        action="store_true",
        help="P2-4: 强制下载区间内全部股票（不跳过 latest>=end 的标的；用于 pre-2020 xtquant 重拉）",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="日线/分钟线历史数据补录 & DuckDB 重建")
    sub = parser.add_subparsers(dest="command", help="子命令")

    # ---- download ----
    p_dl = sub.add_parser("download", help="仅下载数据，不重建 DuckDB")
    _add_download_args(p_dl)

    # ---- rebuild ----
    p_rb = sub.add_parser("rebuild", help="仅重建 DuckDB 持久化文件")
    p_rb.add_argument("--period", default="1d", choices=["1d", "1m", "all"],
                      help="重建周期: 1d | 1m | all")

    # ---- update (download + rebuild) ----
    p_up = sub.add_parser("update", help="下载数据 + 重建 DuckDB（一步完成）")
    _add_download_args(p_up)

    args = parser.parse_args(argv)

    if args.command in ("download", "update"):
        from oskh_data.qmt_xtdata import skip_if_forbids_xtdata_init
        if skip_if_forbids_xtdata_init():
            return 0

    if args.command == "rebuild":
        _rebuild_duckdb(args.period)
        logger.info("Rebuild 全部完成")
        return

    if args.command in ("download", "update"):
        # --inventory：全量盘点日期分布（下载前可选，独立于门禁）
        if getattr(args, 'inventory', False):
            adj = 'none' if args.period == '1m' else getattr(args, 'adjust_types', 'front').split(',')[0]
            _gate_inventory_snapshot(args.period, adj)
        _download_impl(args)

    if args.command == "update":
        _rebuild_duckdb(args.period)

    if args.command is None:
        parser.print_help()
    else:
        logger.info("Backfill 全部完成")


if __name__ == "__main__":
    main()
