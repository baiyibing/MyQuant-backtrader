"""QMT *download* channel health vs xtdata sector probe (lesson 44).

``get_stock_list_in_sector('沪深京A股')`` can stay green after
``Connection reset`` / ``download_history_data2`` start-timeout. That probe
must not authorize ``--resume``. After a channel failure the orchestrator
requires an explicit ``--ack-qmt-restart`` (or env) *after* a full miniQMT
restart (XtMiniQmt + leftover miniquote).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ACK_FLAG = "--ack-qmt-restart"
ACK_ENV = "OSKH_ACK_QMT_DOWNLOAD_RESTART"  # keep literal = EnvVarKeys.OSKH_ACK_QMT_DOWNLOAD_RESTART
STALE_MARKER_PREFIX = ".qmt_download_channel_stale_"
ORCH_LOCK_NAME = ".run_daily_adjusted_fast.lock"

_CHANNEL_FAILURE_NEEDLES = (
    "connection reset",
    "connectionreset",
    "未在",
    "内启动",
    "数据下载停滞",
    "数据下载总超时",
    "download_history_data2 线程退出但未完成",
    "重启国金",
)


def normalize_target_yyyymmdd(end_time: str) -> str:
    digits = "".join(ch for ch in str(end_time) if ch.isdigit())
    if len(digits) < 8:
        raise ValueError(f"cannot parse YYYYMMDD from end_time={end_time!r}")
    return digits[:8]


def is_qmt_channel_failure(text: str) -> bool:
    blob = str(text or "").casefold()
    if not blob:
        return False
    return any(needle in blob for needle in _CHANNEL_FAILURE_NEEDLES)


def stale_marker_path(base_dir: str | Path, target_yyyymmdd: str) -> Path:
    ymd = normalize_target_yyyymmdd(target_yyyymmdd)
    return Path(base_dir) / f"{STALE_MARKER_PREFIX}{ymd}"


def read_stale_marker(base_dir: str | Path, target_yyyymmdd: str) -> dict[str, Any] | None:
    path = stale_marker_path(base_dir, target_yyyymmdd)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"path": str(path), "reason": "unreadable"}
    if isinstance(raw, dict):
        return raw
    return {"reason": str(raw)}


def _log_marker_lifecycle(action: str, path: Path, detail: Mapping[str, Any] | None = None) -> None:
    """A3（09-04/05 marker 残挂诊断）：marker 生命周期结构化留痕。

    created/cleared 两条事件让「成功编排该删没删」从猜测变记录：
    `grep "download_channel_marker"` 即得全生命周期。best-effort 永不抛。"""
    try:
        from common.infra.quant_logger import get_logger

        get_logger("QmtDownloadChannel", "marker_lifecycle").info(
            "download_channel_marker",
            context={
                "action": action,
                "path": str(path),
                **(dict(detail or {})),
            },
        )
    except Exception:  # noqa: BLE001 — 观测绝不影响下载链
        pass


def write_stale_marker(
    base_dir: str | Path,
    target_yyyymmdd: str,
    reason: str,
    *,
    extra: Mapping[str, Any] | None = None,
) -> Path:
    path = stale_marker_path(base_dir, target_yyyymmdd)
    payload: dict[str, Any] = {
        "target": normalize_target_yyyymmdd(target_yyyymmdd),
        "reason": str(reason)[:800],
        "written_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lesson": 44,
    }
    if extra:
        payload.update(dict(extra))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _log_marker_lifecycle("created", path, {"target": payload.get("target"), "reason": str(payload.get("reason"))[:160]})
    return path


def maybe_write_stale_marker(
    base_dir: str | Path,
    end_time: str,
    reason: str,
) -> Path | None:
    if not is_qmt_channel_failure(reason):
        return None
    return write_stale_marker(base_dir, end_time, reason)


def clear_stale_marker(base_dir: str | Path, target_yyyymmdd: str) -> None:
    path = stale_marker_path(base_dir, target_yyyymmdd)
    existed_before = path.exists()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return
    if existed_before:
        _log_marker_lifecycle("cleared", path, {"target": normalize_target_yyyymmdd(target_yyyymmdd)})
    # 不存在则静默（幂等清除是常态，不产生噪声）


def ack_requested(ack_flag: bool = False) -> bool:
    if ack_flag:
        return True
    raw = str(os.environ.get(ACK_ENV, "") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def require_ack_if_stale(
    base_dir: str | Path,
    target_yyyymmdd: str,
    *,
    ack_flag: bool = False,
) -> None:
    marker = read_stale_marker(base_dir, target_yyyymmdd)
    if marker is None:
        return
    if ack_requested(ack_flag):
        return
    reason = str(marker.get("reason") or "unknown")
    ymd = normalize_target_yyyymmdd(target_yyyymmdd)

    def _remedy_text() -> str:
        try:
            from oskh_data.download_transport import resolve_download_backend

            if resolve_download_backend() == "daqmt":
                return (
                    " 完整退出大QMT客户端（含内置 Redis shim）并重开，登录就绪、"
                    "确认沪深京A股行情，并用 probe_qmt_simulation_terminal 确认资金/持仓可读。"
                )
        except Exception:  # noqa: BLE001 — 文案降级不影响守卫语义
            pass
        return (
            " 先杀 Python 下载进程，完整退出 XtMiniQmt 并杀掉残留 miniquote，"
            " 再启动 D:\\国金证券QMT交易端\\bin.x64\\XtMiniQmt.exe，"
            " 确认沪深京A股。"
        )

    raise RuntimeError(
        "QMT 下载通道已标记腐坏，禁止在未重启国金客户端的情况下 --resume。"
        f" target={ymd} reason={reason[:240]}。"
        " xtdata 板块列表绿 ≠ 下载通道活。"
        + _remedy_text()
        + f" 重启确认后执行: python scripts/data/run_daily_adjusted_fast.py"
        f" --end {ymd} --resume {ACK_FLAG}"
        f" （或设 {ACK_ENV}=1）。详见教训 44。"
    )


def persist_log_download_status(log_text: str) -> str:
    """Last persist-log download STEP: ok | failed | timeout | interrupted | unknown."""
    last = ""
    for line in str(log_text or "").splitlines():
        if "下载 none" not in line:
            continue
        last = line
    if not last:
        return "unknown"
    if "完成 rc=0" in last:
        return "ok"
    if "完成 rc=124" in last:
        # 编排器 subprocess.TimeoutExpired（教训 49）≠ QMT 通道腐坏
        return "timeout"
    if "完成 rc=" in last:
        return "failed"
    if "开始" in last:
        return "interrupted"
    return "unknown"


def sync_stale_marker_from_persist(
    base_dir: str | Path,
    target_yyyymmdd: str,
    persist_text: str,
) -> str:
    """Update marker from persist log. Returns status."""
    status = persist_log_download_status(persist_text)
    if status == "ok":
        clear_stale_marker(base_dir, target_yyyymmdd)
        return status
    if status in {"failed", "interrupted"}:
        write_stale_marker(
            base_dir,
            target_yyyymmdd,
            reason=f"persist:{status}",
            extra={"source": "persist_log"},
        )
    # timeout：编排器外层 3600s/14400s 护栏截断，勿写 stale（否则 --resume 误要 ack-qmt-restart）
    return status


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        process_query_limited = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited, False, int(pid))
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def orchestrator_lock_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / ORCH_LOCK_NAME


def acquire_orchestrator_lock(base_dir: str | Path, *, target_yyyymmdd: str) -> Path:
    path = orchestrator_lock_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            old = {}
        old_pid = int(old.get("pid") or 0)
        if old_pid and _pid_is_running(old_pid) and old_pid != os.getpid():
            raise RuntimeError(
                f"已有日线编排在跑 pid={old_pid} target={old.get('target')}"
                f" lock={path}。不要叠第二条 --resume（教训 44）。"
            )
        try:
            path.unlink()
        except OSError:
            pass
    payload = {
        "pid": os.getpid(),
        "target": normalize_target_yyyymmdd(target_yyyymmdd),
        "written_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def release_orchestrator_lock(lock_path: str | Path | None) -> None:
    if lock_path is None:
        return
    path = Path(lock_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if int(raw.get("pid") or 0) != os.getpid():
            return
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
