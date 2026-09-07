# -*- coding: utf-8 -*-
"""
Explicit UTC vs Asia/Shanghai clocks for audit vs A-share market semantics.

- UTC: persisted audit timestamps, trace-id date segment (YYYYMMDD), cross-process logs.
- Asia/Shanghai: trading calendar wall date, session windows, exchange-oriented fields.

Stdlib only at import time; no quant_logger / trace_context / runtime_config
import-time triggers (YAML debug toggle is applied post-bootstrap via
``set_mono_debug_mode`` / main.py).

See docs/architecture/timezone-v2.md (single entry for clocks and QMT wall-time parsing).
"""

from __future__ import annotations

import os
import re
import time as _stdlib_time
import warnings
from datetime import datetime, time, timedelta, timezone, tzinfo
from typing import Literal, NewType, Optional, Tuple
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")


# ---------------------------------------------------------------------------
# Emergency debug toggle: mono_now() -> wall_now_s()
# ---------------------------------------------------------------------------
# Import-time: read OSKH_DEBUG_MONOTONIC_AS_WALLCLOCK from os.environ only
# (once). Do NOT call runtime_config/ensure_* here — that cold-loads config
# before MINIQMT_CONFIG_PATH may be pinned (start-stack landmine).
# YAML key is applied after bootstrap via set_mono_debug_mode (main.py).
# DEBUG-ONLY; never enable in production.
def _mono_debug_flag_from_environ() -> bool:
    """Module-level read of env debug flag (no runtime_config)."""
    return (os.environ.get("OSKH_DEBUG_MONOTONIC_AS_WALLCLOCK") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


_OSKH_DEBUG_MONOTONIC_AS_WALLCLOCK = _mono_debug_flag_from_environ()


def set_mono_debug_mode(enabled: bool) -> None:
    """Runtime override for monotonic debug mode (e.g. from YAML config).

    Call once after config bootstrap and before any hot-path mono_now() usage.
    """
    global _OSKH_DEBUG_MONOTONIC_AS_WALLCLOCK
    _OSKH_DEBUG_MONOTONIC_AS_WALLCLOCK = enabled
    if enabled:
        import sys as _stdlib_sys

        print(
            "[EMERGENCY DEBUG] mono_now() returns wall_now_s(). "
            "Clock-domain guarantees are BROKEN. Do NOT use in production.",
            file=_stdlib_sys.stderr,
            flush=True,
        )


def to_shanghai(dt: datetime) -> datetime:
    """Interpret ``dt`` as an instant in Asia/Shanghai (aware).

    Naive values are treated as Shanghai wall time (same rule as closed-order window helpers).
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=CN_TZ)
    return dt.astimezone(CN_TZ)


def utc_now() -> datetime:
    """Current instant in UTC (timezone-aware).

    Never derived from :func:`set_mock_trading_datetime` (clock-domain iron rule).
    """
    return datetime.now(timezone.utc)


def now_utc() -> datetime:
    """Doc v2.0 name: current instant in UTC (timezone-aware)."""
    return utc_now()


# ---------------------------------------------------------------------------
# Mock trading datetime (MOCK_QMT multi-strategy) — shanghai_now only
# ---------------------------------------------------------------------------
# Full-stack / subprocess injection. Process-local live_trading tests should use
# MockTradingClockPort instead (same process must not use both — dual-source ban).
# Does NOT fake mono_now() / utc_now() / wall_now_s().
_MOCK_SHANGHAI_NOW: Optional[datetime] = None
# 跨进程 mock 时钟文件（2026-08-04）：OSKH_MOCK_CLOCK_FILE 指向一个文本文件
# （内容 ISO-8601 Asia/Shanghai），trading/executor 两进程的 shanghai_now() 都读它 →
# 外部驱动脚本周期性写文件即可**运行时推进 mock 时钟**（价格剧本按时间选档随之
# 变动 → 依赖价格变化的路径——熔断/止损/破位——可在单次栈运行内触发）。
# 文件不存在/未配置 → 回退 _MOCK_SHANGHAI_NOW（进程内静态，原行为）。
# 2026-08-21：未开 MOCK_QMT_ENABLED 时忽略钟文件（纸/实盘残留 env 不得改 shanghai_now）。
_MOCK_CLOCK_FILE: Optional[str] = None
_MOCK_CLOCK_CACHE: Tuple[str, Optional[datetime]] = ("", None)  # (文件签名, 解析值)


def _is_truthy_flag(raw: object) -> bool:
    return str(raw or "").strip().lower() in ("1", "true", "yes", "on")


def _mock_qmt_enabled() -> bool:
    """MOCK_QMT_ENABLED 是否开。env 优先，避免冷加载 YAML。"""
    env = os.environ.get("MOCK_QMT_ENABLED")
    if env is not None and str(env).strip() != "":
        return _is_truthy_flag(env)
    try:
        from common.infra.runtime_config import get_raw as _cfg_raw

        return _is_truthy_flag(_cfg_raw("MOCK_QMT_ENABLED"))
    except Exception:
        return False


def _configure_mock_clock_file() -> None:
    global _MOCK_CLOCK_FILE
    if _MOCK_CLOCK_FILE is not None:
        return
    raw = ""
    try:
        from common.infra.runtime_config import get_raw as _cfg_raw

        raw = str(_cfg_raw("OSKH_MOCK_CLOCK_FILE") or "").strip()
    except Exception:
        raw = ""
    if not raw:
        # get_raw 未注册时回退 env（OSKH_MOCK_CLOCK_FILE 由 mock 栈 launcher 注入）
        raw = str(os.environ.get("OSKH_MOCK_CLOCK_FILE", "") or "").strip()
    if raw and not _mock_qmt_enabled():
        # 残留钟文件不得污染 paper/live 的 AUTO 日 / shanghai_now
        _MOCK_CLOCK_FILE = ""
        return
    _MOCK_CLOCK_FILE = raw or ""


def mock_clock_file_now() -> Optional[datetime]:
    """读跨进程 mock 时钟文件（有变化才重读，防高频 stat）。"""
    global _MOCK_CLOCK_CACHE
    if not _MOCK_CLOCK_FILE:
        return None
    try:
        from pathlib import Path as _P

        p = _P(_MOCK_CLOCK_FILE)
        if not p.is_file():
            return None
        sig = f"{p.stat().st_mtime_ns}:{p.stat().st_size}"
        if sig == _MOCK_CLOCK_CACHE[0]:
            return _MOCK_CLOCK_CACHE[1]
        text = p.read_text(encoding="utf-8").strip()
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        parsed = parsed.astimezone(CN_TZ)
        _MOCK_CLOCK_CACHE = (sig, parsed)
        return parsed
    except Exception:
        return None


def mock_trading_datetime_active() -> bool:
    """True when mock 时钟持有非 None instant（文件或进程内）。"""
    if _MOCK_CLOCK_FILE is not None and mock_clock_file_now() is not None:
        return True
    return _MOCK_SHANGHAI_NOW is not None


def get_mock_trading_datetime() -> Optional[datetime]:
    """Return the active mock Shanghai instant, or None."""
    return mock_clock_file_now() or _MOCK_SHANGHAI_NOW


def clear_mock_trading_datetime() -> None:
    """Clear timekeeping-level mock trading datetime."""
    global _MOCK_SHANGHAI_NOW
    _MOCK_SHANGHAI_NOW = None


def set_mock_trading_datetime(dt: Optional[datetime]) -> None:
    """Set process-wide mock for :func:`shanghai_now` (None clears).

    Dual-source ban vs ``MockTradingClockPort``: probe only if
    ``live_trading.ports.trading_clock`` is **already** in ``sys.modules``.
    Never import ``live_trading`` here — ``strategy_config.bootstrap_time`` may
    call this while ``strategy_config`` is still initializing; importing
    ``live_trading`` → facade assembly → ``TRADING_SESSION_SCHEDULE`` re-enters
    partial ``strategy_config`` and leaves ``sys.modules`` without a loaded
    ``live_trading`` package (submodules remain → later
    ``RuntimeError: live_trading package is not loaded``).
    """
    global _MOCK_SHANGHAI_NOW
    if dt is None:
        _MOCK_SHANGHAI_NOW = None
        return
    aware = to_shanghai(dt)
    import sys

    tc = sys.modules.get("live_trading.ports.trading_clock")
    if tc is not None:
        peek = getattr(tc, "peek_process_trading_clock_port", None)
        port = peek() if callable(peek) else None
        if port is not None and type(port).__name__ == "MockTradingClockPort":
            raise RuntimeError(
                "Dual mock clock sources forbidden: MockTradingClockPort is bound "
                "and set_mock_trading_datetime() was called (use one injection point)"
            )
    _MOCK_SHANGHAI_NOW = aware


def apply_mock_trading_datetime_from_config() -> Optional[datetime]:
    """Apply ``OSKH_MOCK_TRADING_DATETIME`` via runtime_config (lazy import).

    Returns the applied instant, or None when unset. Caller must ensure
    ``MOCK_QMT_ENABLED`` (strategy_config bootstrap enforces).
    """
    try:
        from common.infra.runtime_config import get_raw as _cfg_raw

        raw = _cfg_raw("OSKH_MOCK_TRADING_DATETIME")
    except Exception:
        return None
    text = str(raw or "").strip()
    if not text:
        return None
    # Accept ISO-8601 with offset, or naive Shanghai wall.
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    set_mock_trading_datetime(parsed)
    return _MOCK_SHANGHAI_NOW


def shanghai_now() -> datetime:
    """Current instant in Asia/Shanghai (aware).

    When mock trading datetime is set (MOCK_QMT scenarios), returns that instant.
    优先级：跨进程 mock 时钟文件（OSKH_MOCK_CLOCK_FILE）> 进程内静态 mock。
    """
    if _MOCK_CLOCK_FILE is None:
        _configure_mock_clock_file()
    fnow = mock_clock_file_now() if _MOCK_CLOCK_FILE is not None else None
    if fnow is not None:
        return fnow
    if _MOCK_SHANGHAI_NOW is not None:
        return _MOCK_SHANGHAI_NOW
    return datetime.now(CN_TZ)


def now_shanghai() -> datetime:
    """Doc v2.0 name: current instant in Asia/Shanghai (aware)."""
    return shanghai_now()


def utc_now_iso_z() -> str:
    """UTC ISO8601 with second resolution and Z suffix (no microseconds)."""
    return (
        utc_now()
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def utc_iso_z_from_posix(ts: float) -> str:
    """POSIX seconds (e.g. time.time()) to UTC ISO8601 with Z suffix, second resolution."""
    return (
        datetime.fromtimestamp(float(ts), tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def utc_iso_z_from_aware(dt: datetime) -> str:
    """Convert an instant to UTC ISO8601 with Z suffix, second resolution (no microseconds).

    Aware values are converted to UTC. Naive values are treated as UTC wall time
    (legacy DB / serialized timestamps).
    """
    if dt.tzinfo is None:
        u = dt.replace(tzinfo=timezone.utc)
    else:
        u = dt.astimezone(timezone.utc)
    return (
        u.replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def utc_compact_filename_stamp() -> str:
    """UTC wall time YYYYMMDD_HHMMSS for archive filenames (no microseconds)."""
    return utc_now().replace(microsecond=0).strftime("%Y%m%d_%H%M%S")


def utc_date_yyyymmdd() -> str:
    """UTC calendar date for trace segments and UTC-dated artifacts."""
    return utc_now().strftime("%Y%m%d")


def utc_date_iso() -> str:
    """UTC calendar date YYYY-MM-DD."""
    return utc_now().date().isoformat()


def shanghai_date_yyyymmdd() -> str:
    """Shanghai local calendar date YYYYMMDD."""
    return shanghai_now().strftime("%Y%m%d")


def shanghai_date_iso() -> str:
    """Shanghai local calendar date YYYY-MM-DD."""
    return shanghai_now().date().isoformat()


def parse_hhmm_to_minutes(raw: str, *, default: int | None = None) -> int:
    """Parse ``HH:MM`` or ``HHMM`` string to minutes-from-midnight.

    Args:
        raw: Time string like ``"14:30"`` or ``"1430"``.
             ``"HH:MM:SS"``, ``"H:MM"``, and minutes-as-integer are **rejected**.
        default: If ``None`` (strict mode), raises ``ValueError`` on parse failure.
                 If ``int`` (lenient mode), returns *default* on failure.

    Returns:
        Minutes from midnight, 0–1440.

    Raises:
        ValueError: In strict mode when *raw* cannot be parsed.

    Bootstrap 阶段用 strict 模式（失败即 ConfigurationError），运行时降级路径用
    explicit default。严格模式防止 typo（如 ``"16:5"``）静默回退导致撤单窗口漂移。

    Single entry point for all HH:MM → minutes parsing across:
      - ``strategy_config/_bootstrap.py``
      - ``live_trading/runtime/loop.py``
      - ``common/infra/csv_production_baseline.py``
    """
    s = (raw or "").strip().replace("：", ":")
    if not s:
        if default is not None:
            return default
        raise ValueError(f"empty time string; expected 'HH:MM' or 'HHMM'")

    # Accept HH:MM (exactly 2 parts) or HHMM (4 digits, no colon)
    if ":" in s:
        parts = s.split(":")
        if len(parts) != 2:
            if default is not None:
                return default
            raise ValueError(
                f"invalid time string: {raw!r}. "
                f"Expected 'HH:MM' (e.g. '14:30') with exactly 2 parts, "
                f"got {len(parts)} parts. HH:MM:SS is not accepted."
            ) from None
        try:
            h = int(parts[0], 10)
            m = int(parts[1], 10)
        except (ValueError, IndexError):
            if default is not None:
                return default
            raise ValueError(
                f"invalid HH:MM time string: {raw!r}. "
                f"Expected 'HH:MM' (e.g. '14:30') or 'HHMM' (e.g. '1430')"
            ) from None
    else:
        # Try bare HHMM (exactly 4 digits)
        if len(s) != 4 or not s.isdigit():
            if default is not None:
                return default
            raise ValueError(
                f"invalid time string: {raw!r}. "
                f"Expected 'HH:MM' (e.g. '14:30') or 'HHMM' (e.g. '1430') with exactly 4 digits. "
                f"Hint: minutes-from-midnight format (e.g. 870) is deprecated."
            ) from None
        h = int(s[:2], 10)
        m = int(s[2:], 10)

    if not (0 <= h < 24 and 0 <= m < 60):
        if default is not None:
            return default
        raise ValueError(
            f"time out of range: {raw!r} → {h:02d}:{m:02d}. "
            f"Expected 00:00–23:59."
        ) from None

    return h * 60 + m


def _shanghai_instant(
    dt_utc: Optional[datetime],
    *,
    now_shanghai: Optional[datetime],
) -> datetime:
    if now_shanghai is not None:
        return to_shanghai(now_shanghai)
    if dt_utc is None:
        return utc_now().astimezone(CN_TZ)
    if dt_utc.tzinfo is None:
        return dt_utc.replace(tzinfo=CN_TZ)
    return dt_utc.astimezone(CN_TZ)


def shanghai_segment_inclusive(
    now_sh: datetime,
    start: time,
    end: time,
    *,
    tolerance_seconds: int = 0,
) -> bool:
    """
    True iff ``now_sh`` lies in ``[start, end]`` on the same Shanghai calendar date,
    inclusive on both ends, after applying symmetric tolerance (v2.0).

    ``now_sh`` must be timezone-aware (typically Asia/Shanghai).
    """
    if now_sh.tzinfo is None:
        now_sh = now_sh.replace(tzinfo=CN_TZ)
    else:
        now_sh = now_sh.astimezone(CN_TZ)
    tol = timedelta(seconds=max(0, int(tolerance_seconds)))
    d = now_sh.date()
    tzinfo = now_sh.tzinfo
    start_dt = datetime.combine(d, start, tzinfo=tzinfo) - tol
    end_dt = datetime.combine(d, end, tzinfo=tzinfo) + tol
    return start_dt <= now_sh <= end_dt


def shanghai_segment_half_open_end(
    now_sh: datetime,
    start: time,
    end: time,
    *,
    tolerance_seconds: int = 0,
) -> bool:
    """
    ``[start, end)`` on the Shanghai calendar date: inclusive start, **exclusive** end
    (after tolerance applied to the boundary instants).
    """
    if now_sh.tzinfo is None:
        now_sh = now_sh.replace(tzinfo=CN_TZ)
    else:
        now_sh = now_sh.astimezone(CN_TZ)
    tol = timedelta(seconds=max(0, int(tolerance_seconds)))
    d = now_sh.date()
    tzinfo = now_sh.tzinfo
    start_dt = datetime.combine(d, start, tzinfo=tzinfo) - tol
    end_dt = datetime.combine(d, end, tzinfo=tzinfo) + tol
    return start_dt <= now_sh < end_dt


TradingWindowKind = Literal["continuous", "continuous_plus_preopen"]


def in_trading_window(
    dt_utc: Optional[datetime] = None,
    *,
    kind: TradingWindowKind = "continuous",
    trading_type: str = "live",
    tolerance_seconds: int = 0,
    now_shanghai: Optional[datetime] = None,
    morning_start: time = time(9, 30),
    morning_end: time = time(11, 30),
    afternoon_start: time = time(13, 0),
    afternoon_end: time = time(15, 0),
    pre_open_start: time = time(9, 15),
    pre_open_end: time = time(9, 25),
) -> bool:
    """
    Trading session gate (Shanghai wall clock), v2.0 **inclusive** segment ends for live.

    - ``continuous``: A-share continuous auction (morning + afternoon); **not** call auction.
    - ``continuous_plus_preopen``: above plus ``pre_open`` segment (09:15–09:25).
    - ``paper`` and ``live`` use the same inclusive morning and afternoon
      continuous-auction segments; the lunch break is outside the session.
    """
    now_sh = _shanghai_instant(dt_utc, now_shanghai=now_shanghai)
    tt = str(trading_type or "live").strip().lower()
    tol = int(tolerance_seconds)
    segs: list[Tuple[time, time]] = []
    if kind == "continuous_plus_preopen":
        segs.append((pre_open_start, pre_open_end))
    segs.extend(
        (
            (morning_start, morning_end),
            (afternoon_start, afternoon_end),
        )
    )
    return any(shanghai_segment_inclusive(now_sh, a, b, tolerance_seconds=tol) for a, b in segs)


def shanghai_session_clock_phase(
    now_sh: datetime,
    *,
    morning_start: time = time(9, 30),
    morning_end: time = time(11, 30),
    afternoon_start: time = time(13, 0),
    afternoon_end: time = time(15, 0),
    routine_start: time = time(14, 30),
) -> str:
    """
    Dashboard-style phase label (legacy key names).

    ``pre_open`` here means *before morning open* (wall clock ``< morning_start``), not call auction.
    Morning/afternoon use the same **inclusive** end semantics as :func:`in_trading_window`.
    When the afternoon continuous segment overlaps the routine buy window
    ``[routine_start, afternoon_end)`` (half-open at close, same as :func:`routine_buy_window_active`),
    returns ``routine_buy`` instead of ``afternoon``.
    """
    if now_sh.tzinfo is None:
        now_sh = now_sh.replace(tzinfo=CN_TZ)
    else:
        now_sh = now_sh.astimezone(CN_TZ)
    wall = now_sh.time()
    if wall < morning_start:
        return "pre_open"
    if shanghai_segment_inclusive(now_sh, morning_start, morning_end):
        return "morning"
    if wall < afternoon_start:
        return "lunch"
    if shanghai_segment_inclusive(now_sh, afternoon_start, afternoon_end):
        if routine_buy_window_active(
            now_sh,
            routine_start=routine_start,
            afternoon_end=afternoon_end,
            tolerance_seconds=0,
        ):
            return "routine_buy"
        return "afternoon"
    return "after_close"


def intraday_continuous_scan_typically_active(
    now_sh: datetime,
    *,
    morning_start: time = time(9, 30),
    morning_end: time = time(11, 30),
    afternoon_start: time = time(13, 0),
    afternoon_end: time = time(15, 0),
) -> bool:
    """True during continuous auction segments (inclusive ends), for monitor hints."""
    return in_trading_window(
        now_shanghai=now_sh,
        kind="continuous",
        trading_type="live",
        tolerance_seconds=0,
        morning_start=morning_start,
        morning_end=morning_end,
        afternoon_start=afternoon_start,
        afternoon_end=afternoon_end,
    )


def routine_buy_window_active(
    now_sh: datetime,
    *,
    routine_start: time,
    afternoon_end: time = time(15, 0),
    tolerance_seconds: int = 0,
) -> bool:
    """Routine buy window ``[routine_start, afternoon_end)`` (exclusive at close), live semantics."""
    return shanghai_segment_half_open_end(
        now_sh, routine_start, afternoon_end, tolerance_seconds=tolerance_seconds
    )


def _log_naive_time(func: str, s: str, tz: tzinfo, *, stacklevel: int = 2) -> None:
    warnings.warn(
        f"Naive time {s!r} in {func} interpreted as tz={getattr(tz, 'key', tz)}",
        UserWarning,
        stacklevel=stacklevel,
    )


def parse_qmt_time(
    naive_str: str,
    default_tz: tzinfo = CN_TZ,
    *,
    warn_on_naive: bool = True,
) -> datetime:
    """
    MiniQMT-style wall string → aware :class:`datetime`.

    ``default_tz`` is the zone used for naive calendar/wall fragments (often ``CN_TZ``;
    use ``datetime.timezone.utc`` for persisted SQLite / broker UTC strings).

    Calendar-only ``YYYYMMDD`` or ``YYYY-MM-DD`` (no clock) map to midnight in ``default_tz`` without warning.
    Compact ``YYYYMMDDHHMMSS`` (14 digits, year 1990–2100) is treated as naive exchange wall time in ``default_tz``.
    If the string includes an offset, it is parsed first and then converted to ``default_tz``.
    Otherwise the value is treated as naive **wall time** in ``default_tz``.

    ``warn_on_naive=False`` suppresses :class:`UserWarning` for naive clock strings (typical for UTC DB paths).
    """
    s = (naive_str or "").strip()
    if not s:
        raise ValueError("parse_qmt_time: empty string")
    # Exchange calendar day (no clock) → Shanghai midnight.
    if re.fullmatch(r"\d{8}", s):
        return datetime.strptime(s, "%Y%m%d").replace(tzinfo=default_tz)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=default_tz)
    # QMT compact wall clock (minute bars / range end); guard year to avoid epoch digit collisions.
    if re.fullmatch(r"\d{14}", s) and 1990 <= int(s[:4]) <= 2100:
        dt = datetime.strptime(s, "%Y%m%d%H%M%S")
        if warn_on_naive:
            warnings.warn(
                f"QMT-style naive time {s!r} interpreted as tz={getattr(default_tz, 'key', default_tz)}",
                UserWarning,
                stacklevel=2,
            )
        return dt.replace(tzinfo=default_tz)
    if s.endswith("Z"):
        dt_z = None
        try:
            dt_z = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            dt_z = None
        if dt_z is not None:
            return dt_z.astimezone(default_tz)
    for probe in (s, s.replace(" ", "T", 1)):
        try:
            dt = datetime.fromisoformat(probe)
            if dt.tzinfo is not None:
                return dt.astimezone(default_tz)
            # P1: handle naive ISO-8601 T-separated timestamps.
            # Treat as local wall-time in default_tz.
            if warn_on_naive:
                _log_naive_time("parse_qmt_time", s, default_tz, stacklevel=4)
            return dt.replace(tzinfo=default_tz)
        except ValueError:
            continue
    for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y%m%d %H:%M:%S%z"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.astimezone(default_tz)
        except ValueError:
            continue
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y%m%d %H:%M:%S.%f",
        "%Y%m%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            if warn_on_naive:
                warnings.warn(
                    f"QMT-style naive time {s!r} interpreted as tz={getattr(default_tz, 'key', default_tz)}",
                    UserWarning,
                    stacklevel=2,
                )
            return dt.replace(tzinfo=default_tz)
        except ValueError:
            continue
    raise ValueError(f"parse_qmt_time: unsupported format: {s!r}")


def parse_qmt_timestamp(ts: int | float, unit: str = "ms") -> datetime:
    """Epoch from QMT (seconds, milliseconds, or microseconds) → UTC aware."""
    x = float(ts)
    if unit == "ms":
        x = x / 1000.0
    elif unit == "us":
        x = x / 1_000_000.0
    elif unit != "s":
        raise ValueError("unit must be 's', 'ms', or 'us'")
    return datetime.fromtimestamp(x, tz=timezone.utc)


# --- Process vs wall clock (see AGENTS.md Timekeeping; scripts/gates/verify_clock_domain_policy.py) ---

MonoSeconds = NewType("MonoSeconds", float)
"""Seconds in ``time.monotonic()`` domain; combine only with same-domain timestamps."""

WallSeconds = NewType("WallSeconds", float)
"""Seconds in ``time.time()`` (POSIX) domain; DB, QMT SDK, cross-process ordering."""


def mono_now() -> MonoSeconds:
    """Process-monotonic instant for TTL, heartbeat, in-process cache age (not for SQLite wall columns).

    When ``OSKH_DEBUG_MONOTONIC_AS_WALLCLOCK=1`` is set, returns
    ``wall_now_s()`` instead to provide a uniform baseline for diagnosing
    whether a bug is related to monotonic vs wall-clock choice.
    See ``scripts/misc/toggle_monotonic_debug_mode.py``.
    """
    if _OSKH_DEBUG_MONOTONIC_AS_WALLCLOCK:
        return MonoSeconds(wall_now_s())
    return MonoSeconds(_stdlib_time.monotonic())


def wall_now_s() -> WallSeconds:
    """POSIX wall instant in seconds; prefer for persisted REAL columns and broker protocol windows."""
    return WallSeconds(_stdlib_time.time())

