# -*- coding: utf-8 -*-
"""
common/quant_logger.py - 统一量化日志基础设施（Phase 3 - Zero Dependency on PerfMonitor）
=================================================================================

**Phase 3 关键变更（彻底解耦）**：
- **移除所有 perf_monitor 依赖**：`initialize()` 和 `shutdown()` 不再延迟导入 `perf_monitor`
- **自监控降级**：初始化阶段性能监控改用标准库 `time.perf_counter_ns()` 直接计时
- **分层依赖**：`quant_logger` (Layer 2) 依赖 `trace_context` + `constants` (Layer 0)、
  `exceptions` + `security` (Layer 1)；**不**依赖 `perf_monitor` (同层)。
- **业务 API**：`get_logger`, `TraceIdGenerator`, `set_trace_context`；初始化统一 `QuantLoggerFactory.initialize(...)`（可选 `hot_log_level` / `json_lines` / `trace_id_generator` / `suppress_init_failure`）

**架构角色**：
    Layer 2 基础设施组件，向上层提供结构化日志与审计能力。
    依赖拓扑：quant_logger (L2) -> trace_context (L0) + constants (L0) + exceptions (L1) + security (L1)。

**合规与留存（本进程内）**：
    - 热日志：30天本地（默认最低 DEBUG；``QUANT_LOG_HOT_LEVEL`` 或 ``initialize(hot_log_level=...)`` 可调高）
    - 可选 JSON Lines：``QUANT_LOG_JSON=true`` 或 ``initialize(json_lines=True)`` 时并行写入 ``quant_json_*.log``
    - 日志根布局：默认 ``QUANT_LOG_ROOT_LAYOUT=scoped``（``QUANT_LOG_DIR`` 下按 ``INSTANCE_ID`` 或 ``pid_*`` 分子目录）；``flat`` 则与旧行为一致
    - 错误日志：90天本地（ERROR级）
    - 审计日志：180天本地（`quant_audit_*.log`，由顶层 `audit=True` 或单条 `context["audit"]` 路由）
    - 冷存储 / 监管长期归档：**不在此模块内执行上传**；`COLD_STORAGE_URI` 仅作运维侧提示；
      长期留痕依赖外部备份/对象存储任务消费本地日志目录（留存年限见 `COLD_RETENTION_YEARS` 约定）。

**与标准库 ``logging``（约定入口）**：业务与集成层应通过本模块 ``get_logger`` 写日志；勿在生产路径使用 ``getLogger`` / ``basicConfig`` 作为主通道。若仅需要与 stdlib **级别整型**对齐（如 ``ERROR == 40``），仓库约定与窄例外见仓库根 ``AGENTS.md`` 中 **Logging：`quant_logger` 与标准库 `logging`** 小节。

**观测出口（P2 统一约定，避免用裸 print 充当正式遥测）**：
    - **结构化日志**：`get_logger(...)`，业务/链路事件在 `context` 中携带 `event`（取值见 `common.infra.constants.StreamObservabilityEvent`）。
    - **HTTP 探针**：监控进程 `stream_monitor`（如 `/healthz`、`/ready`；运维摘要见仓库 `docs/p2-2-monitoring.md`）。
    - **外呼分级告警**：`common.infra.alerter.dispatch_tiered_alert`（P0/P1/P2 与 Webhook 路由）。

Author: Quant Engineering Team
Version: 3.1.0 (Scoped log root, tracked loguru handlers, no configure_logging)
Date: 2026-03-16
"""

import json
import logging
import os

from common.infra.timekeeping import mono_now
import sys
import time  # Phase 3: 直接使用标准库time，替代perf_monitor
import collections
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Callable

from loguru import logger
from common.infra.runtime_config import get_raw as _runtime_cfg_raw

# ==============================================================================
# Phase 3: Layer 2 基础设施导入（零同级依赖）
# ==============================================================================

# Layer 0 常量单一真相源（零依赖层）
from .constants import (
    LoggingConstants,
    EnvVarKeys,
    LOG_RETENTION_DAYS,
    ERROR_LOG_RETENTION_DAYS,
    COLD_RETENTION_YEARS,
    TRACE_ID_LENGTH,
    ErrorCode,
)

# 从 Layer 0 计算派生常量
LOG_ROTATION_SIZE = LoggingConstants.LOG_ROTATION_SIZE
LOG_COMPRESSION = LoggingConstants.LOG_COMPRESSION

# Layer 1 金融级异常体系（依赖 constants，无 quant_logger 依赖）
from .exceptions import ConfigurationError

# Layer 1 安全脱敏（依赖 constants；与 quant_logger 无循环依赖）
from .security import DataMasker

# ==============================================================================
# Phase 3: 从 Layer 0 trace_context 导入 Trace ID 基础设施
# ==============================================================================

from .trace_context import (
    TraceIdGenerator,
    get_trace_context,
    set_trace_context,
)
from . import timekeeping as _timekeeping


class ShanghaiLoggingFormatter(logging.Formatter):
    """Stdlib logging: human wall Asia/Shanghai + UTC posix (docs/architecture/timezone-v2.md §4.3)."""

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:  # noqa: N802
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc).astimezone(_timekeeping.CN_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.replace(microsecond=0).isoformat(timespec="seconds")

    def format(self, record: logging.LogRecord) -> str:
        record.utc_timestamp = f"{record.created:.3f}"  # type: ignore[attr-defined]
        return super().format(record)


def _format_hot_sink_record(record: Dict[str, Any]) -> str:
    """Loguru hot/error/audit sinks: Shanghai wall + UTC posix (no strftime %z; see docs/architecture/timezone-v2.md)."""
    t = record["time"]
    utc_ts = ""
    wall = ""
    try:
        if isinstance(t, datetime):
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            utc_ts = f"{t.timestamp():.3f}"
            sh = t.astimezone(_timekeeping.CN_TZ)
            wall = sh.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        else:
            wall = str(t)
    except Exception:
        wall = str(record.get("time", ""))
    level = record["level"]
    level_name = level.name if hasattr(level, "name") else str(level)
    extra = record.get("extra")
    if not isinstance(extra, dict):
        extra = {}
    ctx = extra.get("context", {})
    ctx_str = json.dumps(ctx, ensure_ascii=False, default=str) if ctx else "{}"
    line = (
        f"{wall}+08:00 [UTC:{utc_ts}] | {level_name:<8} | "
        f"{str(extra.get('module', '')).strip():<10} | "
        f"{str(extra.get('trace_id', '')).strip():<24} | "
        f"{str(extra.get('func', '')).strip():<20} | "
        f"{record['message']} | {ctx_str}"
    )
    # Loguru callable format receives a template, not a finalized line;
    # escape any braces that remain after f-string interpolation so they
    # are not interpreted as format placeholders in the second pass.
    # Explicit newline ensures log entries render line-by-line in all editors.
    return line.replace("{", "{{").replace("}", "}}") + "\n"


def _record_targets_audit_sink(record: Any) -> bool:
    """True if this record should go to quant_audit_*.log (bind-level or per-message context)."""
    try:
        extra = record["extra"]
    except (KeyError, TypeError):
        return False
    if not isinstance(extra, dict):
        return False
    if extra.get("audit") is True:
        return True
    ctx = extra.get("context")
    if isinstance(ctx, dict) and ctx.get("audit") is True:
        return True
    return False


def _truthy_env(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.lower() in ("1", "true", "yes", "on")


def _resolve_hot_min_level_no(level_name: str) -> int:
    """Map level name to loguru numeric threshold for the hot + JSON sinks."""
    name = (level_name or "DEBUG").strip().upper()
    try:
        return logger.level(name).no
    except ValueError:
        return logger.level("DEBUG").no


def _json_payload_for_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Structured fields for JSON Lines (Loki/ELK)."""
    t = record["time"]
    ts = ""
    time_shanghai = ""
    utc_posix = ""
    try:
        if isinstance(t, datetime):
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            utc_posix = f"{t.timestamp():.3f}"
            ts = t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            time_shanghai = t.astimezone(_timekeeping.CN_TZ).isoformat(timespec="milliseconds")
        else:
            ts = str(t)
            time_shanghai = str(t)
    except Exception:
        ts = str(t)
        time_shanghai = str(t)
    extra = record.get("extra")
    if not isinstance(extra, dict):
        extra = {}
    ctx = extra.get("context")
    if not isinstance(ctx, dict):
        ctx = {}
    level = record["level"]
    level_name = level.name if hasattr(level, "name") else str(level)
    return {
        "time": ts,
        "time_shanghai": time_shanghai,
        "utc_posix": utc_posix,
        "level": level_name,
        "module": str(extra.get("module", "")).strip(),
        "func": str(extra.get("func", "")).strip(),
        "trace_id": str(extra.get("trace_id", "")).strip(),
        "message": record["message"],
        "context": ctx,
    }


def _json_line_format(record: Dict[str, Any]) -> str:
    """Parseable JSON line (tests, external tools calling the helper with a record dict)."""
    return json.dumps(_json_payload_for_record(record), ensure_ascii=False, default=str) + "\n"


def _json_line_format_loguru(record: Dict[str, Any]) -> str:
    """
    Loguru treats the format return value as a str.format template; escape JSON braces so
    the line is emitted literally after format_map.
    """
    raw = _json_line_format(record)
    return raw.replace("{", "{{").replace("}", "}}")


def _normalize_trace_id_or_system(candidate: Optional[str]) -> str:
    """
    Return a canonical 24-char trace_id or synthesize a system trace.

    This keeps all log records aligned with trace_context validation rules.
    """
    if candidate is not None:
        raw = str(candidate).strip()
        if TraceIdGenerator.validate(raw):
            return raw
    return TraceIdGenerator.generate("system")


def _key_suggests_redis_credential(key_lower: str) -> bool:
    """True when key names a Redis connection string (not e.g. redis_latency_ms)."""
    if key_lower in ("redis_url", "rediss_url", "redis_dsn", "broker_redis_url"):
        return True
    if key_lower.endswith("_redis_url") or key_lower.endswith("_rediss_url"):
        return True
    if "redis" in key_lower and any(s in key_lower for s in ("_url", "_uri", "_dsn")):
        return True
    if key_lower in ("redis_password", "rediss_password"):
        return True
    return False


def _str_looks_like_redis_url(value: str) -> bool:
    s = value.strip()
    return s.startswith("redis://") or s.startswith("rediss://")


def _sanitize_log_scope_segment(segment: str) -> str:
    # Windows 非法文件名字符: \ / : * ? " < > |
    s = segment.strip().replace("..", "_").replace("\\", "_").replace("/", "_").replace(":", "_")
    if not s:
        s = f"pid_{os.getpid()}"
    return s[:200]


def _resolve_scoped_effective_log_dir(base_dir: str) -> str:
    raw = (_runtime_cfg_raw(EnvVarKeys.QUANT_LOG_ROOT_LAYOUT) or "scoped").strip().lower()
    if raw in ("flat", "legacy", "0", "off", "none"):
        return base_dir
    seg = _runtime_cfg_raw(EnvVarKeys.INSTANCE_ID) or f"pid_{os.getpid()}"
    return os.path.join(base_dir, _sanitize_log_scope_segment(seg))


def _strip_loguru_builtin_stderr_enabled() -> bool:
    v = _runtime_cfg_raw(EnvVarKeys.QUANT_LOGURU_REMOVE_DEFAULT) or "true"
    return v.strip().lower() not in ("0", "false", "no", "off")


# ==============================================================================
# 日志工厂（Phase 3：零 perf_monitor 依赖，自监控降级实现）
# ==============================================================================

class QuantLoggerFactory:
    """
    单例日志工厂（Phase 3：零 perf_monitor 依赖，基于 trace_context Layer 0 实现）

    **变更说明**：
    - 移除 `initialize()` 和 `shutdown()` 中对 `perf_monitor` 的延迟导入
    - 初始化阶段性能监控改用 `time.perf_counter_ns()` 直接计时（极简方案）
    - 性能数据格式简化（仅记录总耗时），不进入统一 PerfTimer 分级体系
    """

    _instance = None
    _initialized: bool = False
    _lock = __import__('threading').Lock()
    _init_lock = __import__('threading').Lock()
    _active_log_dir: Optional[str] = None
    log_dir: str = "logs"
    try:
        _pre_init_buffer_maxlen_val = int(
            str(_runtime_cfg_raw("QUANT_LOG_PREINIT_BUFFER_MAX") or "5000")
        )
    except (ValueError, TypeError):
        _pre_init_buffer_maxlen_val = 5000
    _pre_init_buffer_maxlen: int = max(2000, _pre_init_buffer_maxlen_val)
    _pre_init_buffer = collections.deque(maxlen=_pre_init_buffer_maxlen)
    _pre_init_lock = threading.RLock()
    _last_uninit_warn_ts: float = 0.0
    _uninit_warn_interval_sec: float = 60.0
    _quant_handler_ids: list = []  # loguru handler ids registered by this factory only

    @classmethod
    def _refresh_pre_init_buffer_capacity_from_runtime(cls) -> None:
        """Refresh pre-init buffer maxlen from runtime config before first init."""
        try:
            configured_maxlen = int(str(_runtime_cfg_raw("QUANT_LOG_PREINIT_BUFFER_MAX") or "5000"))
        except (ValueError, TypeError):
            configured_maxlen = 5000
        target_maxlen = max(2000, configured_maxlen)
        if target_maxlen == cls._pre_init_buffer_maxlen:
            return
        with cls._pre_init_lock:
            if target_maxlen == cls._pre_init_buffer_maxlen:
                return
            cls._pre_init_buffer_maxlen = target_maxlen
            cls._pre_init_buffer = collections.deque(cls._pre_init_buffer, maxlen=target_maxlen)

    def __new__(cls):
        """线程安全单例（双检锁模式）"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def is_initialized(cls) -> bool:
        """True after a successful ``initialize()`` (health probes / lifecycle)."""
        return cls._initialized

    @classmethod
    def is_ready(cls) -> bool:
        """Same as :meth:`is_initialized`; preferred by bootstrap-sensitive callers (e.g. exception audit)."""
        return cls._initialized

    @classmethod
    def _detach_quant_handlers(cls) -> None:
        for hid in reversed(cls._quant_handler_ids):
            removed = False
            try:
                logger.remove(hid)
                removed = True
            except ValueError:
                removed = False
            if not removed:
                continue
        cls._quant_handler_ids.clear()

    @classmethod
    def _register_sink(cls, *args: Any, **kwargs: Any) -> int:
        hid = logger.add(*args, **kwargs)
        cls._quant_handler_ids.append(hid)
        return hid

    @classmethod
    def _maybe_strip_loguru_builtin_stderr(cls) -> None:
        if not _strip_loguru_builtin_stderr_enabled():
            return
        removed_builtin = False
        try:
            logger.remove(0)
            removed_builtin = True
        except ValueError:
            removed_builtin = False
        if not removed_builtin:
            return

    @classmethod
    def initialize(
        cls,
        log_dir: Optional[str] = None,
        *,
        hot_log_level: Optional[str] = None,
        json_lines: Optional[bool] = None,
        trace_id_generator: Optional[Callable[[], str]] = None,
        suppress_init_failure: bool = False,
    ) -> None:
        """
        全系统日志基础设施初始化（Phase 3：零 perf_monitor 依赖，自监控降级）

        Args:
            log_dir: 日志根目录（覆盖环境变量 QUANT_LOG_DIR，默认 logs/）
            hot_log_level: 热日志与 JSON sink 最低级别（单次调用优先于环境变量）
            json_lines: 是否启用 ``quant_json_*.log``（单次调用优先于 ``QUANT_LOG_JSON``）
            trace_id_generator: 初始化成功后写入 trace 上下文（可选）
            suppress_init_failure: 为 True 时目录不可写等失败不抛出（仅测试/沙箱）

        Raises:
            ConfigurationError: 如果配置参数无效（P0/P1级，强制审计）
        """
        try:
            cls._initialize_locked(
                log_dir,
                hot_log_level=hot_log_level,
                json_lines=json_lines,
            )
        except ConfigurationError:
            if suppress_init_failure:
                return
            raise

        if trace_id_generator is not None and cls._initialized:
            try:
                set_trace_context(trace_id_generator())
            except Exception:
                if not suppress_init_failure:
                    raise

    @classmethod
    def _initialize_locked(
        cls,
        log_dir: Optional[str],
        *,
        hot_log_level: Optional[str],
        json_lines: Optional[bool],
    ) -> None:
        # 初始化必须串行化，避免并发竞争导致重复配置/竞态
        with cls._init_lock:
            cls._refresh_pre_init_buffer_capacity_from_runtime()
            base_dir = log_dir or _runtime_cfg_raw(EnvVarKeys.QUANT_LOG_DIR) or "logs"
            effective_log_dir = _resolve_scoped_effective_log_dir(base_dir)

            # 幂等要求：已初始化则直接返回（不同 log_dir 只告警，不变更既有配置）
            if cls._initialized:
                if cls._active_log_dir and effective_log_dir != cls._active_log_dir:
                    try:
                        # 仅告警保留已有配置，避免测试/审计因参数漂移造成不可验证差异
                        warn_logger = cls.get_logger(
                            module="QuantLoggerFactory",
                            func="initialize",
                            trace_id=TraceIdGenerator.generate("system"),
                            log_dir_path_requested=effective_log_dir,
                            log_dir_path_existing=cls._active_log_dir,
                        )
                        warn_logger.warning(
                            "Logger infrastructure already initialized; ignoring new log_dir",
                        )
                    except Exception:
                        # 兜底：永不阻断业务启动链路
                        try:
                            print(
                                f"[WARN] QuantLoggerFactory already initialized; ignoring new log_dir={effective_log_dir!r}, "
                                f"existing_log_dir={cls._active_log_dir!r}",
                                file=sys.stderr,
                            )
                        except Exception:
                            return
                return

            factory = cls()
            factory.log_dir = effective_log_dir
            cls._active_log_dir = effective_log_dir

            # Phase 3: 自监控降级 - 直接使用标准库time，零perf_monitor依赖
            init_start_ns = time.perf_counter_ns()
            stage_timings = {}  # 简化的阶段计时存储

            try:
                # Stage 1: 目录创建（直接计时，无PerfTimer嵌套）
                stage_start = time.perf_counter_ns()
                try:
                    os.makedirs(factory.log_dir, exist_ok=True)
                    stage_timings['mkdir'] = (time.perf_counter_ns() - stage_start) / 1_000_000  # 转换为ms
                except Exception as e:
                    raise ConfigurationError(
                        f"Failed to create log directory: {factory.log_dir}",
                        error_code=ErrorCode.CFG_VALIDATION_FAILED,
                        config_key="log_dir",
                        cause=e,
                        audit_immediate=True
                    )

                cls._detach_quant_handlers()
                cls._maybe_strip_loguru_builtin_stderr()

                # Phase 3 + v2.0 时钟：上海墙钟人读 + UTC posix（见 docs/architecture/timezone-v2.md）
                fmt = _format_hot_sink_record
                diagnose_enabled = (
                    (_runtime_cfg_raw(EnvVarKeys.QUANT_LOG_DIAGNOSE) or "false").lower() == "true"
                )
                backtrace_debug = (
                    (_runtime_cfg_raw(EnvVarKeys.QUANT_LOG_BACKTRACE_DEBUG) or "false").lower() == "true"
                )
                backtrace_error = (
                    (_runtime_cfg_raw(EnvVarKeys.QUANT_LOG_BACKTRACE_ERROR) or "true").lower() == "true"
                )

                hot_level_name = (
                    hot_log_level
                    if hot_log_level is not None
                    else (_runtime_cfg_raw(EnvVarKeys.QUANT_LOG_HOT_LEVEL) or "DEBUG")
                )
                hot_min_no = _resolve_hot_min_level_no(hot_level_name)
                if json_lines is not None:
                    json_sink_enabled = json_lines
                else:
                    json_sink_enabled = _truthy_env(_runtime_cfg_raw(EnvVarKeys.QUANT_LOG_JSON))

                # Stage 2: 配置日志处理器（直接计时）
                stage_start = time.perf_counter_ns()

                # 1. 热日志：按 QUANT_LOG_HOT_LEVEL / initialize(hot_log_level=...) 过滤（默认 DEBUG，30天按天轮转）
                cls._register_sink(
                    os.path.join(factory.log_dir, "quant_{time:YYYY-MM-DD}.log"),
                    rotation="00:00",
                    retention=f"{LOG_RETENTION_DAYS} days",
                    compression=LOG_COMPRESSION,
                    encoding="utf-8",
                    level="DEBUG",
                    enqueue=True,  # 异步非阻塞
                    format=fmt,
                    backtrace=backtrace_debug,
                    diagnose=diagnose_enabled,
                    filter=lambda record, m=hot_min_no: record["level"].no >= m
                )

                # 1b. JSON Lines（与热日志同级过滤；``QUANT_LOG_JSON`` 或 initialize(json_lines=True)）
                if json_sink_enabled:
                    cls._register_sink(
                        os.path.join(factory.log_dir, "quant_json_{time:YYYY-MM-DD}.log"),
                        rotation="00:00",
                        retention=f"{LOG_RETENTION_DAYS} days",
                        compression=LOG_COMPRESSION,
                        encoding="utf-8",
                        level="DEBUG",
                        enqueue=True,
                        format=_json_line_format_loguru,
                        backtrace=False,
                        diagnose=False,
                        filter=lambda record, m=hot_min_no: record["level"].no >= m
                    )

                # 2. 错误日志：审计与故障排查（90天，按大小轮转）
                cls._register_sink(
                    os.path.join(factory.log_dir, "quant_errors_{time:YYYY-MM-DD}.log"),
                    rotation=LOG_ROTATION_SIZE,
                    retention=f"{ERROR_LOG_RETENTION_DAYS} days",
                    compression=LOG_COMPRESSION,
                    encoding="utf-8",
                    level="ERROR",
                    enqueue=True,
                    format=fmt,
                    backtrace=backtrace_error,
                    diagnose=diagnose_enabled
                )

                # 3. 审计专用日志：配置变更/敏感操作（180天）
                cls._register_sink(
                    # Loguru {time:...} uses Pendulum-style tokens (MM month), not strftime %m.
                    os.path.join(factory.log_dir, "quant_audit_{time:YYYY-MM}.log"),
                    rotation="100 MB",
                    retention=f"{LoggingConstants.CONFIG_AUDIT_RETENTION_DAYS} days",
                    encoding="utf-8",
                    level="INFO",
                    enqueue=True,
                    format=fmt,
                    filter=_record_targets_audit_sink
                )

                # 4. 控制台输出（开发调试）：不低于 INFO，且不低于热日志阈值
                if (_runtime_cfg_raw(EnvVarKeys.QUANT_LOG_CONSOLE) or "false").lower() == "true":
                    console_min_no = max(logger.level("INFO").no, hot_min_no)
                    cls._register_sink(
                        sys.stdout,
                        level="DEBUG",
                        format=_format_hot_sink_record,
                        colorize=False,
                        filter=lambda record, m=console_min_no: record["level"].no >= m
                    )

                stage_timings['log_config'] = (time.perf_counter_ns() - stage_start) / 1_000_000

                # 配置冷存储归档钩子
                cls._setup_cold_storage_hook(factory.log_dir)

                cls._initialized = True
                cls._flush_pre_init_buffer()
                total_init_ms = (time.perf_counter_ns() - init_start_ns) / 1_000_000

                # 记录初始化审计日志（使用从 trace_context 导入的 TraceIdGenerator）
                init_logger = factory.get_logger(
                    "QuantLoggerFactory",
                    "initialize",
                    TraceIdGenerator.generate("system")
                )
                init_logger.info(
                    "Logger infrastructure initialized | "
                    f"Hot:{LOG_RETENTION_DAYS}d | "
                    f"Error:{ERROR_LOG_RETENTION_DAYS}d | "
                    f"Audit:{LoggingConstants.CONFIG_AUDIT_RETENTION_DAYS}d | "
                    f"Cold:{COLD_RETENTION_YEARS}y | "
                    f"Async:True | "
                    f"TraceFormat:{TRACE_ID_LENGTH}char_strict | "
                    f"Phase:3_ZeroDependency | "  # 标记 Phase 3 完成
                    f"GuojinAdapted:True | "
                    f"InitTime:{total_init_ms:.2f}ms",  # Phase 3: 简化性能记录
                    context={
                        "init_stages_ms": stage_timings,  # 简化的阶段耗时（非PerfSnapshot格式）
                        "total_ms": round(total_init_ms, 2),
                        "monitoring_mode": "self_degradation",  # 标记降级模式
                        "hot_log_min_level": hot_level_name.strip().upper(),
                        "json_lines_sink": json_sink_enabled,
                        "log_root_layout": (
                            _runtime_cfg_raw(EnvVarKeys.QUANT_LOG_ROOT_LAYOUT) or "scoped"
                        ).strip().lower(),
                    }
                )

            except Exception as e:
                cls._detach_quant_handlers()
                # 初始化失败：清理状态，允许下一次重试
                cls._initialized = False
                cls._active_log_dir = None

                # Phase 3: 计算失败前的耗时
                failed_ms = (time.perf_counter_ns() - init_start_ns) / 1_000_000 if 'init_start_ns' in locals() else 0
                raise ConfigurationError(
                    f"Logger initialization failed: {str(e)}",
                    error_code=ErrorCode.SYS_INITIALIZATION_FAILED,
                    config_key="quant_logger",
                    cause=e,
                    audit_immediate=True,
                    extra={"failed_after_ms": round(failed_ms, 2)}
                ) from e

    @classmethod
    def _append_pre_init_record(cls, level: str, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """记录初始化前日志请求（轻量环形缓冲，避免关键信息丢失）"""
        try:
            with cls._pre_init_lock:
                cls._pre_init_buffer.append({
                    "ts": mono_now(),
                    "level": str(level).upper(),
                    "message": str(message)[:1000],
                    "context": cls._mask_context(context or {}),
                })
        except Exception as _append_exc:
            try:
                sys.stderr.write(
                    f"[WARN] Pre-init log record append failed: "
                    f"{type(_append_exc).__name__}: {_append_exc}\n"
                )
            except Exception:
                pass
            return

    @classmethod
    def _warn_uninitialized_rate_limited(cls) -> None:
        """未初始化告警限频，防止高频stderr输出放大回调链路I/O压力"""
        now = mono_now()
        if now - cls._last_uninit_warn_ts >= cls._uninit_warn_interval_sec:
            cls._last_uninit_warn_ts = now
            try:
                print("[WARN] QuantLoggerFactory not initialized, fallback mode active", file=sys.stderr)
            except Exception:
                return

    @classmethod
    def _flush_pre_init_buffer(cls) -> None:
        """初始化完成后刷出预初始化缓冲记录（不阻断主流程）"""
        if not cls._initialized:
            return
        try:
            with cls._pre_init_lock:
                records = list(cls._pre_init_buffer)
                cls._pre_init_buffer.clear()
            if not records:
                return
            flush_logger = cls.get_logger("QuantLoggerFactory", "flush_pre_init", TraceIdGenerator.generate("system"))
            for record in records:
                context = {
                    **(record.get("context") or {}),
                    "pre_init": True,
                    "pre_init_ts": record.get("ts"),
                }
                level = record.get("level", "INFO")
                message = record.get("message", "pre-init log")
                if level in ("ERROR", "CRITICAL"):
                    flush_logger.error(message, context=context)
                elif level == "WARNING":
                    flush_logger.warning(message, context=context)
                else:
                    flush_logger.info(message, context=context)
        except Exception as _flush_exc:
            try:
                sys.stderr.write(
                    f"[WARN] Pre-init log buffer flush failed: "
                    f"{type(_flush_exc).__name__}: {_flush_exc}\n"
                )
            except Exception:
                pass
            return

    @classmethod
    def _setup_cold_storage_hook(cls, log_dir: str) -> None:
        """
        冷归档提示（本进程不执行上传/同步）。

        `COLD_STORAGE_URI` 供运维在部署侧配置外部备份/对象存储目标；长期留存需由
        独立作业（rsync、磁带、S3 等）消费 ``log_dir`` 下文件，而非在此模块内实现。
        """
        cold_storage_uri = _runtime_cfg_raw(EnvVarKeys.COLD_STORAGE_URI)
        if cold_storage_uri:
            masked_uri = DataMasker.mask_file_path(cold_storage_uri) if '://' in cold_storage_uri else "configured"
            print(
                f"[QuantLoggerFactory] COLD_STORAGE_URI set for ops ({masked_uri}); "
                f"archival is external to this process (see module doc).",
                file=sys.stderr,
            )

    @classmethod
    def get_logger(cls,
                   module: str,
                   func: str,
                   trace_id: Optional[str] = None,
                   audit: bool = False,
                   **context) -> Any:
        """
        获取带全链路上下文的结构化logger（Phase 3：使用从 trace_context 导入的上下文）

        Args:
            module: 模块名
            func: 函数/操作名
            trace_id: 追踪ID，如未提供则从 trace_context 获取（协程安全）
            audit: 是否标记为审计日志
            **context: 附加上下文键值对（自动脱敏）

        Returns:
            logger: 绑定了trace_id和脱敏context的loguru实例
        """
        if not cls._initialized:
            # Fail-operational: allow import-time callers (e.g. constant export validation / smoke tests)
            # to proceed even if the full logger infrastructure is not initialized yet.
            # Trading runtime should still call QuantLoggerFactory.initialize() in `main.py`.
            cls._warn_uninitialized_rate_limited()
            cls._append_pre_init_record(
                "WARNING",
                "logger_requested_before_initialize",
                {"module": module, "func": func, "audit": audit}
            )

        # 优先使用传入 trace_id，否则继承当前上下文；无效输入统一降级为合法 system trace。
        if trace_id:
            tid = _normalize_trace_id_or_system(trace_id)
        else:
            tid = _normalize_trace_id_or_system(get_trace_context())

        # 自动脱敏上下文中的敏感字段
        masked_context = cls._mask_context(context) if context else {}

        if audit:
            masked_context['audit'] = True
            masked_context['retention_class'] = '180_days_audit'

        bind_kwargs: Dict[str, Any] = {
            "module": module[:10].ljust(10),
            "func": func[:20].ljust(20),
            "trace_id": tid,
            "context": masked_context if masked_context else {},
        }
        if audit:
            bind_kwargs["audit"] = True

        return logger.bind(**bind_kwargs)

    @staticmethod
    def _mask_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """
        自动脱敏上下文中的敏感字段（金融级标准：前3后3）

        **国金miniQMT特定**:
        - 自动检测并脱敏xtquant路径（含QMT_USERDATA_PATH）
        - 自动脱敏session_id（视为敏感连接标识）
        """
        if not context:
            return {}

        masked: Dict[str, Any] = {}
        generic_secret_markers = (
            'password', 'secret', 'token', 'api_key', 'private_key', 'session_id', 'passphrase',
            'authorization', 'auth_token', 'bearer',
        )

        for key, value in context.items():
            key_lower = str(key).lower()
            if 'path' in key_lower and isinstance(value, str):
                masked[key] = DataMasker.mask_file_path(value, levels=2)
                continue
            redis_cred = _key_suggests_redis_credential(key_lower)
            account_like = any(
                acc in key_lower for acc in ('account_id', 'user_id', 'account')
            )
            generic_secret = any(m in key_lower for m in generic_secret_markers)
            is_sensitive = generic_secret or account_like or redis_cred

            if is_sensitive:
                if any(acc in key_lower for acc in ['account', 'account_id', 'user_id']):
                    masked[key] = DataMasker.mask_account_id(value)
                elif redis_cred and isinstance(value, str):
                    masked[key] = DataMasker.mask_redis_url(value)
                elif isinstance(value, (str, bytes, int)):
                    masked[key] = DataMasker.mask_secret(str(value))
                else:
                    masked[key] = "****"
            else:
                if isinstance(value, dict):
                    masked[key] = QuantLoggerFactory._mask_context(value)
                elif isinstance(value, list):
                    masked[key] = [
                        QuantLoggerFactory._mask_context(v) if isinstance(v, dict) else v
                        for v in value
                    ]
                elif isinstance(value, str) and _str_looks_like_redis_url(value):
                    masked[key] = DataMasker.mask_redis_url(value)
                else:
                    masked[key] = value

        return masked

    @classmethod
    def set_thread_trace_id(cls, trace_id: str) -> str:
        """
        设置当前协程/线程的Trace ID上下文（Phase 3：委托给 trace_context）

        **国金miniQMT多账户适配**:
        支持在多账户并发场景下，为每个账户独立设置Trace ID，避免TLS的线程串扰问题

        Args:
            trace_id: Trace ID（将标准化为24字符）

        Returns:
            str: 标准化后的24字符Trace ID
        """
        raw = str(trace_id).strip()
        if not TraceIdGenerator.validate(raw):
            raw = TraceIdGenerator.generate("system")
        set_trace_context(raw)
        return raw

    @classmethod
    def get_current_trace_id(cls) -> str:
        """获取当前上下文的Trace ID（24字符，协程安全）"""
        # Phase 3: 委托给从 trace_context 导入的 get_trace_context()
        return get_trace_context()

    @classmethod
    def shutdown(cls) -> None:
        """
        优雅关闭，确保所有日志落盘（Phase 3：零 perf_monitor 依赖，自监控降级）

        Phase 3: 使用标准库 time 直接计时，移除所有 perf_monitor 依赖
        """
        try:
            # Phase 3: 自监控降级 - 直接使用标准库time
            shutdown_start_ns = time.perf_counter_ns()

            # 执行关闭操作
            logger.complete()
            cls._detach_quant_handlers()
            cls._initialized = False
            cls._active_log_dir = None

            # 计算耗时（简化记录）
            elapsed_ms = (time.perf_counter_ns() - shutdown_start_ns) / 1_000_000

            # 使用stderr输出（因此时logger可能已关闭）
            print(f"[QuantLoggerFactory] Shutdown completed in {elapsed_ms:.2f}ms", file=sys.stderr)

        except Exception as e:
            print(f"[CRITICAL] Logger shutdown failed: {e}", file=sys.stderr)

    @classmethod
    def _get_internal_logger(cls):
        """内部使用：在initialize之前获取临时logger用于诊断（降级防护）"""
        return logger


# ==============================================================================
# 便捷函数（供业务层直接调用，但必须在initialize之后）
# ==============================================================================

def get_logger(module: str,
               func: str = "default",
               trace_id: Optional[str] = None,
               audit: bool = False,
               **context) -> Any:
    """
    便捷函数：获取业务logger（Phase 3：基于 trace_context 的 Trace ID 基础设施）

    **推荐 context 键（P2-1 观测统一）**：在 ``log.info(..., context={...})`` 中优先使用
    ``event``（见 ``StreamObservabilityEvent``）、``signal_id``、``account_id``（脱敏）、
    ``retry_count``、``redis_msg_id``、``stream``、``consumer_group``、``reason``、
    可选 ``component``。列字段 ``trace_id``/``module``/``func`` 已由 bind 提供。

    **使用示例**:
        from common.infra.quant_logger import get_logger, TraceIdGenerator, set_trace_context

        # 生成Trace ID（24字符）
        trace_id = TraceIdGenerator.generate('executor')

        # 设置上下文（协程安全）
        set_trace_context(trace_id)

        # 获取logger（自动脱敏敏感字段）
        log = get_logger(
            'executor_stream',
            'execute_signal',
            trace_id,
            stock='000001.SZ',
            account_id='1234567890',  # 自动脱敏为 123****890
            action='BUY'
        )
        log.info("Order submitted", context={"order_id": "123456"})
    """
    return QuantLoggerFactory.get_logger(module, func, trace_id, audit, **context)


# ==============================================================================
# 模块级便捷函数（向后兼容：可直接从 trace_context 导入，也可从此处导入）
# ==============================================================================

# 注意：以下函数现已直接从 trace_context 导入，保持向后兼容
# 业务层可以继续使用 from common.infra.quant_logger import set_trace_context, get_trace_context
# 也可以改为从 common.infra.trace_context 直接导入

# 无需重新定义，直接使用从 trace_context 导入的函数


# ==============================================================================
# Phase 3: 模块自检（验证零 perf_monitor 依赖与 trace_context 集成）
# ==============================================================================

def _self_test():
    """
    模块自检（Phase 3：验证零 perf_monitor 依赖与 Layer 0 集成）

    **验证项**：
    1. Trace ID生成通过 trace_context 完成（24字符严格对齐）
    2. 上下文传递通过 trace_context 的 ContextVar（协程安全）
    3. 自动脱敏逻辑保持（金融级前3后3标准）
    4. 常量引用正确性
    5. **关键**：验证未导入 perf_monitor（零依赖确认）
    6. 初始化阶段自监控可用（time.perf_counter_ns）
    """
    print("[quant_logger.py] Phase 3 Zero Dependency Self-Test...")

    # 1. Trace ID生成验证（通过 trace_context 导入）
    test_modules = ['selector', 'executor', 'reconcile', 'hkcodex']
    for mod in test_modules:
        tid = TraceIdGenerator.generate(mod)
        assert len(tid) == TRACE_ID_LENGTH, f"Length violation: {len(tid)} != {TRACE_ID_LENGTH}"
        print(f"  ✓ {mod:15} -> {tid} (via trace_context)")

    # 2. 上下文传递验证（通过 trace_context 导入的函数）
    test_tid = TraceIdGenerator.generate('system')
    set_trace_context(test_tid)
    retrieved = get_trace_context()
    assert retrieved == test_tid, f"Context mismatch via trace_context"
    print(f"  ✓ ContextVars via trace_context: {retrieved[:20]}...")

    # 3. 自动脱敏验证
    test_context = {
        "account_id": "123456789012",
        "redis_url": "redis://user:pass@host:6379/0",
        "normal_field": "keep_this"
    }
    masked = QuantLoggerFactory._mask_context(test_context)
    assert masked["account_id"] == "123****012"
    assert "****" in masked["redis_url"]
    assert masked["normal_field"] == "keep_this"
    print(f"  ✓ Auto-masking: account={masked['account_id']}")

    latency_ctx = {"redis_latency_ms": 12.5}
    assert QuantLoggerFactory._mask_context(latency_ctx)["redis_latency_ms"] == 12.5
    print("  ✓ Redis metric keys (e.g. redis_latency_ms) are not over-masked")

    neutral_key_url = {"endpoint": "redis://user:pass@h:6379/0"}
    assert "****" in QuantLoggerFactory._mask_context(neutral_key_url)["endpoint"]
    print("  ✓ Redis URL values masked even on neutral keys")

    # 4. 国金miniQMT前缀验证（通过 trace_context 的 TraceIdGenerator）
    hkq_tid = TraceIdGenerator.generate('hkcodex')
    assert hkq_tid[:6].strip() == 'HKQ'
    print(f"  ✓ Guojin miniQMT prefix (via trace_context): {hkq_tid}")

    # 5. **关键检查**：验证零 perf_monitor 依赖
    import sys
    current_module = sys.modules[__name__]

    # 验证模块命名空间中无 perf_monitor 相关符号
    forbidden_symbols = ['get_timer', 'PerfTimer', 'PerfLevel', 'PerfMonitor', 'perf_monitor']
    for symbol in forbidden_symbols:
        if hasattr(current_module, symbol):
            raise AssertionError(f"Zero dependency violation: {symbol} found in module namespace")

    # 验证源码中无 perf_monitor 导入语句（通过检查源码字符串）
    import inspect
    source = inspect.getsource(current_module)
    if "from .perf_monitor import" in source or "import perf_monitor" in source:
        raise AssertionError("Zero dependency violation: perf_monitor import found in source")

    print("  ✓ Zero dependency check: No perf_monitor symbols or imports (Phase 3 compliant)")

    # 6. 自监控功能验证（标准库time可用）
    test_start = time.perf_counter_ns()
    time.sleep(0.001)  # 1ms sleep for testing
    test_elapsed_ms = (time.perf_counter_ns() - test_start) / 1_000_000
    assert test_elapsed_ms >= 1.0, "time.perf_counter_ns() not working correctly"
    print(f"  ✓ Self-monitoring (time.perf_counter_ns): {test_elapsed_ms:.2f}ms elapsed")

    print("[quant_logger.py] Phase 3 Self-test completed successfully ✅")
    print("[quant_logger.py] Dependency status: ZERO (no perf_monitor imports)")
    print("[quant_logger.py] Architecture: L2 -> L0 trace_context/constants + L1 exceptions/security")


# Phase 3: 禁止模块自初始化，仅在直接运行时执行逻辑验证
if __name__ == "__main__":
    _self_test()