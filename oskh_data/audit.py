"""
回填操作审计追踪。data_audit.db 为独立运维库（非交易持久化），
与 portfolio.db/execution_trade.db 等 oskh_db 五库物理隔离。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from common.infra.quant_logger import get_logger
from common.infra.timekeeping import mono_now

logger = get_logger(__name__)

_DEFAULT_AUDIT_DB = "data_audit.db"


def _resolve_audit_db_path(db_path: Optional[str] = None) -> Path:
    if db_path:
        return Path(db_path)
    return Path(_DEFAULT_AUDIT_DB)


def _ensure_schema(con: sqlite3.Connection) -> None:
    """初始化审计表（幂等）。"""
    con.executescript("""
        CREATE TABLE IF NOT EXISTS backfill_run (
            run_id         TEXT PRIMARY KEY,
            period         TEXT NOT NULL,
            adjust_type    TEXT NOT NULL,
            start_time     TEXT NOT NULL,
            end_time       TEXT NOT NULL,
            total_symbols  INTEGER NOT NULL,
            success_count  INTEGER NOT NULL DEFAULT 0,
            fail_count     INTEGER NOT NULL DEFAULT 0,
            success_rate   REAL NOT NULL DEFAULT 0.0,
            aborted        INTEGER NOT NULL DEFAULT 0,
            created_at     TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS backfill_failure (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id         TEXT NOT NULL REFERENCES backfill_run(run_id),
            symbol         TEXT NOT NULL,
            error_type     TEXT NOT NULL,
            error_message  TEXT,
            retry_count    INTEGER NOT NULL DEFAULT 0,
            created_at     TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_bf_run ON backfill_failure(run_id);
    """)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def generate_run_id() -> str:
    """生成唯一的回填批次标识。"""
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    return f"bf_{ts}_{int(mono_now() * 1000) % 100000:05d}"


def record_run_start(
    run_id: str,
    period: str,
    adjust_type: str,
    start_time: str,
    end_time: str,
    total_symbols: int,
    *,
    db_path: Optional[str] = None,
) -> None:
    """记录回填开始。"""
    path = _resolve_audit_db_path(db_path)
    con = sqlite3.connect(str(path))
    try:
        _ensure_schema(con)
        con.execute(
            "INSERT INTO backfill_run(run_id, period, adjust_type, start_time, end_time, "
            "total_symbols, created_at) VALUES(?,?,?,?,?,?,?)",
            (run_id, period, adjust_type, start_time, end_time, total_symbols,
             datetime.now(timezone.utc).isoformat()),
        )
        con.commit()
        logger.info("Audit run started: %s (%d symbols)", run_id, total_symbols)
    finally:
        con.close()


def record_failure(
    run_id: str,
    symbol: str,
    error_type: str,
    error_message: str = "",
    retry_count: int = 0,
    *,
    db_path: Optional[str] = None,
) -> None:
    """记录单只股票回填失败。"""
    path = _resolve_audit_db_path(db_path)
    con = sqlite3.connect(str(path))
    try:
        _ensure_schema(con)
        con.execute(
            "INSERT INTO backfill_failure(run_id, symbol, error_type, error_message, "
            "retry_count, created_at) VALUES(?,?,?,?,?,?)",
            (run_id, symbol, error_type, error_message, retry_count,
             datetime.now(timezone.utc).isoformat()),
        )
        con.commit()
    finally:
        con.close()


def record_run_end(
    run_id: str,
    success_count: int,
    fail_count: int,
    aborted: bool = False,
    *,
    db_path: Optional[str] = None,
    min_success_rate: float = 0.70,
) -> bool:
    """记录回填结束，返回是否达到成功率阈值。

    Returns:
        True if success_rate >= min_success_rate (batch OK).
        False if below threshold (batch should abort, rollback to previous snapshot).
    """
    path = _resolve_audit_db_path(db_path)
    total = success_count + fail_count
    rate = success_count / total if total > 0 else 0.0
    ok = rate >= min_success_rate

    con = sqlite3.connect(str(path))
    try:
        _ensure_schema(con)
        con.execute(
            "UPDATE backfill_run SET success_count=?, fail_count=?, "
            "success_rate=?, aborted=? WHERE run_id=?",
            (success_count, fail_count, rate, int(not ok or aborted), run_id),
        )
        con.commit()
        logger.info(
            "Audit run ended: %s success=%.1f%% (%d/%d) %s",
            run_id, rate * 100, success_count, total,
            "ABORTED" if not ok else "OK",
            context={"run_id": run_id, "success_rate": rate},
        )
    finally:
        con.close()
    return ok


def get_failed_symbols(
    run_id: str,
    *,
    db_path: Optional[str] = None,
) -> List[str]:
    """获取指定批次失败的股票列表（用于重试）。"""
    path = _resolve_audit_db_path(db_path)
    if not path.exists():
        return []
    con = sqlite3.connect(str(path))
    try:
        rows = con.execute(
            "SELECT symbol FROM backfill_failure WHERE run_id=? AND retry_count < 3",
            (run_id,),
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()
