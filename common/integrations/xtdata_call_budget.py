# -*- coding: utf-8 -*-
"""P2-4 option-X: xtdata RLock budget safety valve (paper/audit only, default off).

SSOT: docs/knowledge/performance/solutions/solution-P2-4-option-x-budget.md
"""
from __future__ import annotations

import os
import threading
from typing import Any, Callable, Optional, TypeVar

from common.infra.constants import EnvVarKeys
from common.infra.exceptions import ErrorCode, MarketDataError

_T = TypeVar("_T")

BUDGET_SECONDS_CAP = 10.0
_MIN_SAMPLES_FOR_BUDGET = 100


def compute_budget_seconds_from_p99_ms(p99_ms: float) -> float:
    """``max(P99×2, P99+3s)`` capped at 10s (solution SSOT)."""
    if p99_ms <= 0:
        raise ValueError("p99_ms must be positive")
    p99_s = p99_ms / 1000.0
    return min(max(p99_s * 2.0, p99_s + 3.0), BUDGET_SECONDS_CAP)


def _truthy(raw: Any) -> bool:
    return str(raw or "").strip().lower() in ("1", "true", "yes", "on")


def _executor_account_count() -> int:
    raw = os.environ.get(EnvVarKeys.EXECUTOR_ACCOUNTS, "")
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    if parts:
        return len(parts)
    try:
        import strategy_config as config

        aid = str(getattr(config, "ACCOUNT_ID", "") or "").strip()
        return 1 if aid else 0
    except Exception:
        return 1


def _trading_type_is_live() -> bool:
    """Live hard-ban: env/YAML via get_raw first (config priority), then import-time snapshot.

    Preferring ``strategy_config.TRADING_TYPE`` alone breaks tests that monkeypatch
    ``TRADING_TYPE`` after the config module was already imported as paper.
    """
    raw = _cfg_raw(EnvVarKeys.TRADING_TYPE)
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip().lower() == "live"
    try:
        import strategy_config as config

        tt = str(getattr(config, "TRADING_TYPE", "") or "").strip().lower()
    except Exception:
        tt = "paper"
    return tt == "live"


def _cfg_raw(key: str) -> Any:
    try:
        from common.infra.runtime_config import get_raw

        return get_raw(key)
    except Exception:
        return os.environ.get(key)


def is_xtdata_budget_enabled() -> bool:
    """True only when flag on, non-live, and multi-account (N>1)."""
    if _trading_type_is_live():
        return False
    if not _truthy(_cfg_raw(EnvVarKeys.OSKH_XTDATA_BUDGET_ENABLED)):
        return False
    if _executor_account_count() <= 1:
        return False
    return True


def resolve_xtdata_budget_seconds() -> Optional[float]:
    """Configured budget seconds; None when disabled or unset."""
    if not is_xtdata_budget_enabled():
        return None
    raw = _cfg_raw(EnvVarKeys.OSKH_XTDATA_BUDGET_SEC)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        val = float(str(raw).strip())
    except ValueError:
        return None
    if val <= 0 or val > BUDGET_SECONDS_CAP:
        return None
    return val


def xtdata_call_with_budget_sync(
    fn: Callable[[], _T],
    *,
    budget_s: float,
    retries: int = 0,
) -> _T:
    """Run ``fn`` in a daemon worker thread with wall-clock budget (sync callers).

    On timeout the *caller* is released immediately (does NOT join the orphan);
    the C++ xtdata call continues in the daemon orphan thread until it returns
    (zombie risk by design — see SSOT). Daemon so a truly-hung C++ call does not
    block process exit.

    Note: ``ThreadPoolExecutor`` as a context manager is intentionally avoided —
    its ``__exit__`` calls ``shutdown(wait=True)`` which blocks until the orphan
    finishes, defeating the budget (regression-pinned 2026-07-04, r1 review).
    """
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        result_box: dict[str, Any] = {}

        def _runner() -> None:
            try:
                result_box["value"] = fn()
            except BaseException as exc:  # noqa: BLE001 — propagate fn's error to caller
                result_box["error"] = exc

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join(timeout=budget_s)
        if t.is_alive():
            # Budget exceeded — release caller now; daemon orphan keeps running (C++ zombie).
            last_exc = TimeoutError(f"budget {budget_s}s exceeded")
            if attempt >= retries:
                raise MarketDataError(
                    "xtdata_budget_exceeded",
                    error_code=ErrorCode.SYS_UNKNOWN,
                    extra={
                        "reason_code": "xtdata_budget_zombie_risk",
                        "budget_s": budget_s,
                    },
                ) from last_exc
            continue
        if "error" in result_box:
            err = result_box["error"]
            if isinstance(err, BaseException):
                raise err
            raise RuntimeError(repr(err))
        return result_box["value"]  # type: ignore[return-value]
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("xtdata_call_with_budget_sync failed without exception")  # pragma: no cover


def run_xtdata_rlock_path(
    fn: Callable[[], _T],
    *,
    lock: threading.RLock,
    lock_ctx_factory: Callable[[], Any],
) -> _T:
    """Execute ``fn`` under optional budget; ``lock_ctx_factory`` yields metrics context."""
    budget_s = resolve_xtdata_budget_seconds()
    if budget_s is not None:

        def _locked() -> _T:
            with lock_ctx_factory():
                return fn()

        return xtdata_call_with_budget_sync(_locked, budget_s=budget_s, retries=0)
    with lock_ctx_factory():
        return fn()
