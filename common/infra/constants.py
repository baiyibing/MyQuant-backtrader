# -*- coding: utf-8 -*-
"""
common/infra/constants.py - 全系统常量收敛管理（金融级配置中心 - Phase 3 P0 + Week 4 P1 修复版）
==========================================================

职责：
    集中管理所有技术基础设施常量，消除硬编码，支持环境变量注入，符合中国A股
    量化交易系统黄金准则（可追溯、可审计、分级管理、异步非阻塞）。

Phase 3 P0 热修复（前序变更）：
    1. [P0] ErrorCode 补全：新增 DB_SCHEMA_VIOLATION 等 4 个持久化层错误码
    2. [P0] ErrorCode 补全：新增 CFG_CONFIG_MISSING（Gateway初始化等场景）
    3. [P0] ErrorCode 补全：新增 TRADE_RECORD_FAILED（交易记录前置校验失败）
    4. [P0] ErrorCode 体系扩展：新增 Layer 2.5 专用域（LAYER25_001-003）
    5. [P1] 常量导出补全：新增 CONFIG_AUDIT_RETENTION_DAYS 至 __all__（合规审计要求）

Week 4 P1 修复（本次变更 - 审查报告 2.1 节）：
    - [P1] 调度常量导出补全：新增 MAIN_LOOP_INTERVAL_SEC 等 9 个高频调度常量便捷别名
    - [P1] __all__ 对齐：确保与 common/__init__.py 中 _LAYER2_SCHEDULING 严格一致
    - [合规] 支持 live_trading.py 等业务模块通过 `from common import MAIN_LOOP_INTERVAL_SEC` 直接访问

版本：3.0.7 (Phase 3 P0 Fix + Week 4 P1 Scheduling Constants Export)
作者：Quant Architect
日期：2026-03-18
"""

import json
import warnings
from typing import Final, List, Dict, Any, Tuple, FrozenSet, cast
from enum import Enum

from .runtime_config import ensure_runtime_config_loaded, get_raw as _config_get_raw


# ==================== 环境变量 / YAML 分层读取（带类型转换与审计日志） ====================

_ENV_BOOL_TRUE = frozenset(("true", "1", "yes", "on"))
_ENV_BOOL_FALSE = frozenset(("false", "0", "no", "off"))


def _warn_invalid_env_value(key: str, raw_value: Any, fallback: Any) -> None:
    """环境变量非法值告警（仅使用标准库，避免依赖上层日志模块）。"""
    warnings.warn(
        f"[constants] invalid env {key}={raw_value!r}, fallback to {fallback!r}",
        RuntimeWarning,
        stacklevel=3,
    )


def _get_env_int(key: str, default: int) -> int:
    """安全读取整型配置（环境变量优先，其次 YAML）；已设置但不可解析时告警并回退默认值。"""
    ensure_runtime_config_loaded()
    raw = _config_get_raw(key)
    if raw is None:
        return default
    s = str(raw).strip()
    if s == "":
        return default
    try:
        return int(s)
    except (ValueError, TypeError):
        _warn_invalid_env_value(key, raw, default)
        return default


def _get_env_float(key: str, default: float) -> float:
    """安全读取浮点型配置（环境变量优先，其次 YAML）；已设置但不可解析时告警并回退默认值。"""
    ensure_runtime_config_loaded()
    raw = _config_get_raw(key)
    if raw is None:
        return default
    s = str(raw).strip()
    if s == "":
        return default
    try:
        return float(s)
    except (ValueError, TypeError):
        _warn_invalid_env_value(key, raw, default)
        return default


def _get_env_bool(key: str, default: bool) -> bool:
    """安全读取布尔型配置（环境变量优先，其次 YAML）；无法识别的非空值告警并回退默认值。"""
    ensure_runtime_config_loaded()
    raw = _config_get_raw(key)
    if raw is None:
        return default
    val = str(raw).strip().lower()
    if val == "":
        return default
    if val in _ENV_BOOL_TRUE:
        return True
    if val in _ENV_BOOL_FALSE:
        return False
    _warn_invalid_env_value(key, raw, default)
    return default


def _get_env_str(key: str, default: str) -> str:
    """安全读取字符串配置（环境变量优先，其次 YAML）。"""
    ensure_runtime_config_loaded()
    raw = _config_get_raw(key)
    if raw is None:
        return default
    return raw


def _get_env_int_in_range(key: str, default: int, *, min_value: int, max_value: int) -> int:
    """读取整型配置并校验区间，越界/解析失败均回退默认值。"""
    ensure_runtime_config_loaded()
    raw = _config_get_raw(key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = int(raw)
    except (ValueError, TypeError):
        _warn_invalid_env_value(key, raw, default)
        return default
    if value < min_value or value > max_value:
        _warn_invalid_env_value(key, raw, default)
        return default
    return value


def _get_env_float_in_range(
    key: str, default: float, *, min_value: float, max_value: float
) -> float:
    """读取浮点配置并校验区间，越界/解析失败均回退默认值。"""
    ensure_runtime_config_loaded()
    raw = _config_get_raw(key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = float(raw)
    except (ValueError, TypeError):
        _warn_invalid_env_value(key, raw, default)
        return default
    if value < min_value or value > max_value:
        _warn_invalid_env_value(key, raw, default)
        return default
    return value


def _get_env_list(key: str, default: List[str], separator: str = ",") -> List[str]:
    """安全读取列表型配置（逗号分隔）。"""
    ensure_runtime_config_loaded()
    val = _config_get_raw(key)
    if val is None or val == "":
        return default
    return [item.strip() for item in val.split(separator) if item.strip()]


def _get_env_json(key: str, default: Dict[str, Any]) -> Dict[str, Any]:
    """安全读取 JSON 型配置（支持字典配置）；非对象 JSON 或解析失败时告警并回退默认值。"""
    ensure_runtime_config_loaded()
    val = _config_get_raw(key)
    if val is None:
        return default
    s = str(val).strip()
    if s == "":
        return default
    try:
        loaded = json.loads(s)
    except (json.JSONDecodeError, TypeError):
        _warn_invalid_env_value(key, val, default)
        return default
    if isinstance(loaded, dict):
        return cast(Dict[str, Any], loaded)
    _warn_invalid_env_value(key, val, default)
    return default


# ==================== Redis Stream 默认（env/YAML 均未设时；monitor ImportError 兜底同源） ====================
DEFAULT_REDIS_STREAM_NAME: Final[str] = "miniqmt:trade:stream"
DEFAULT_REDIS_CONSUMER_GROUP: Final[str] = "miniqmt_executors"


# ==================== 环境变量键名集中管理（Phase 3 新增 - 消除硬编码） ====================

class EnvVarKeys:
    """
    全系统环境变量键名集中管理（单一真相源）

    消除各模块硬编码字符串（如"os.environ.get('QMT_MAX_CONN')"），
    统一在此定义，防止拼写错误和配置漂移。
    """
    # YAML 引导（值可为 os.pathsep 分隔的多文件路径；后者覆盖前者）
    MINIQMT_CONFIG_PATH: Final[str] = "MINIQMT_CONFIG_PATH"
    # main.py bootstrap：为 true 时，工作日上海时间 09:25–15:00 禁止启动 trading-* / executor（粗粒度，不含节假日历）
    BOOTSTRAP_ENFORCE_PRE_OPEN_WINDOW: Final[str] = "BOOTSTRAP_ENFORCE_PRE_OPEN_WINDOW"

    # QMT连接层
    QMT_BATCH_SIZE: Final[str] = "QMT_BATCH_SIZE"
    QMT_PRICE_TOLERANCE: Final[str] = "QMT_PRICE_TOLERANCE"
    QMT_PRICE_CACHE_TIMEOUT_SEC: Final[str] = "QMT_PRICE_CACHE_TIMEOUT_SEC"
    QMT_RECONNECT_DELAY: Final[str] = "QMT_RECONNECT_DELAY"
    QMT_MAX_RECONNECT_24H: Final[str] = "QMT_MAX_RECONNECT_24H"
    # Paper/ops: archive reconnect JSON when a new OS process starts (INSTANCE_ID shard unchanged).
    QMT_RESET_RECONNECT_COUNTER_ON_PROCESS_START: Final[str] = (
        "QMT_RESET_RECONNECT_COUNTER_ON_PROCESS_START"
    )
    QMT_MAX_CONN_PER_ACCOUNT: Final[str] = "QMT_MAX_CONN_PER_ACCOUNT"
    QMT_SLOT_TIMEOUT_SEC: Final[str] = "QMT_SLOT_TIMEOUT_SEC"
    QMT_MAX_RETRY: Final[str] = "QMT_MAX_RETRY"
    QMT_PING_INTERVAL_SEC: Final[str] = "QMT_PING_INTERVAL_SEC"
    # is_healthy：last_heartbeat 超过该秒数视为陈旧（可与 Runner 周期 perform_heartbeat 配合）
    QMT_SESSION_STALE_SEC: Final[str] = "QMT_SESSION_STALE_SEC"
    # TRADING_TYPE=paper 时仍为 true：Runner 直连 miniQMT（含模拟柜）并启用 init/probe/keepalive 与再平衡等 QMT 路径
    QMT_XDATA_TIMEOUT_SEC: Final[str] = "QMT_XDATA_TIMEOUT_SEC"
    QMT_XDATA_READ_TIMEOUT_SEC: Final[str] = "QMT_XDATA_READ_TIMEOUT_SEC"
    QMT_MARKET_BATCH: Final[str] = "QMT_MARKET_BATCH"
    # Live 默认要求见 qmt_client：自动 session_id 时需显式 INSTANCE_ID，降低多进程 session 碰撞
    QMT_AUTO_SESSION_REQUIRES_INSTANCE_ID: Final[str] = "QMT_AUTO_SESSION_REQUIRES_INSTANCE_ID"
    QMT_EMERGENCY_MODE: Final[str] = "QMT_EMERGENCY_MODE"  # 紧急模式开关
    # 紧急直连审批/收口审计字段（机审用）
    QMT_EMERGENCY_APPROVAL_ID: Final[str] = "QMT_EMERGENCY_APPROVAL_ID"
    QMT_EMERGENCY_APPROVED_BY: Final[str] = "QMT_EMERGENCY_APPROVED_BY"
    QMT_EMERGENCY_REASON: Final[str] = "QMT_EMERGENCY_REASON"
    QMT_EMERGENCY_SCOPE: Final[str] = "QMT_EMERGENCY_SCOPE"
    QMT_EMERGENCY_EXPIRES_AT: Final[str] = "QMT_EMERGENCY_EXPIRES_AT"
    QMT_EMERGENCY_CLOSURE_ID: Final[str] = "QMT_EMERGENCY_CLOSURE_ID"
    QMT_EMERGENCY_CLOSED_BY: Final[str] = "QMT_EMERGENCY_CLOSED_BY"
    QMT_EMERGENCY_CLOSE_REASON: Final[str] = "QMT_EMERGENCY_CLOSE_REASON"
    # 为 true 时：全市场行情订阅失败则禁止调仓信号检查 / 执行器下单（见 qmt_client.subscribe_whole_quote 容错路径）
    REQUIRE_QMT_MARKET_SUBSCRIPTION: Final[str] = "REQUIRE_QMT_MARKET_SUBSCRIPTION"
    # 为 true 时：账户状态不健康则阻断交易路径（见 validate_config / go-live gates）
    REQUIRE_QMT_ACCOUNT_STATUS_HEALTH: Final[str] = "REQUIRE_QMT_ACCOUNT_STATUS_HEALTH"
    # 逗号分隔的“健康”账户状态取值（与券商返回对齐）
    QMT_ACCOUNT_STATUS_HEALTHY_VALUES: Final[str] = "QMT_ACCOUNT_STATUS_HEALTHY_VALUES"
    # 进程内仅首次会话创建时调用 xtdata.init（国金/xtquant 常见最佳实践）；设 0/false 则每次建连都 init（便于单测）
    QMT_XTDATA_INIT_ONCE: Final[str] = "QMT_XTDATA_INIT_ONCE"
    # subscribe_whole_quote 在单次建连阶段的最大尝试次数与间隔
    QMT_MARKET_SUBSCRIBE_MAX_RETRY: Final[str] = "QMT_MARKET_SUBSCRIBE_MAX_RETRY"
    QMT_MARKET_SUBSCRIBE_RETRY_DELAY_SEC: Final[str] = "QMT_MARKET_SUBSCRIBE_RETRY_DELAY_SEC"
    # main.py drill-reconnect：release 后等待；建连后对 get_health_status 的短轮询（executor_qmt_reconnect_drill）
    QMT_RECONNECT_DRILL_RELEASE_DELAY_SEC: Final[str] = "QMT_RECONNECT_DRILL_RELEASE_DELAY_SEC"
    QMT_RECONNECT_DRILL_HEALTH_POLL_TIMEOUT_SEC: Final[str] = "QMT_RECONNECT_DRILL_HEALTH_POLL_TIMEOUT_SEC"
    QMT_RECONNECT_DRILL_HEALTH_POLL_INTERVAL_SEC: Final[str] = "QMT_RECONNECT_DRILL_HEALTH_POLL_INTERVAL_SEC"
    # query_closed_orders 查询起点：在「本机当日 00:00」基础上再向前扩展（降低 broker_order_not_found）
    QMT_CLOSED_ORDERS_EXTRA_CALENDAR_DAYS: Final[str] = "QMT_CLOSED_ORDERS_EXTRA_CALENDAR_DAYS"
    QMT_CLOSED_ORDERS_LOOKBACK_SEC: Final[str] = "QMT_CLOSED_ORDERS_LOOKBACK_SEC"
    # query_closed_orders 时间窗口运行时探针（off|debug|evidence；默认 off）
    QMT_CLOSED_ORDERS_WINDOW_PROBE_MODE: Final[str] = "QMT_CLOSED_ORDERS_WINDOW_PROBE_MODE"
    # XtTrader vendor capability marker (see common.integrations.vendor_capabilities)
    QMT_BROKER_VENDOR: Final[str] = "QMT_BROKER_VENDOR"
    # Phase-1 execution_log duplicate block when closed-orders API missing (guojin paper)
    QMT_DEDUP_FALLBACK_LOCAL_DB: Final[str] = "QMT_DEDUP_FALLBACK_LOCAL_DB"
    # 心跳路径上对已失败订阅的 Whole Quote 重试最小间隔（秒）；0 允许每轮心跳尝试（单测可用）
    QMT_MARKET_RESUB_INTERVAL_SEC: Final[str] = "QMT_MARKET_RESUB_INTERVAL_SEC"
    # P0-10：行情数据静默超时阈值（秒）。subscribe_whole_quote 成功但超过该时间未收到有效 tick，视为行情冻结。
    # 0 表示禁用该检查（回退到仅检查 _market_subscribed 布尔标志）。
    QMT_MARKET_DATA_FROZEN_THRESHOLD_SEC: Final[str] = "QMT_MARKET_DATA_FROZEN_THRESHOLD_SEC"
    # Connection budget auto-fuse (CONN_003 death-spiral prevention)
    QMT_CONNECTION_BUDGET_RECONNECT_WARN_REMAINING: Final[str] = (
        "QMT_CONNECTION_BUDGET_RECONNECT_WARN_REMAINING"
    )
    QMT_CONNECTION_BUDGET_BROKER_SYNC_STORM_TRIP: Final[str] = (
        "QMT_CONNECTION_BUDGET_BROKER_SYNC_STORM_TRIP"
    )
    QMT_CONNECTION_BUDGET_BROKER_SYNC_STORM_WINDOW_SEC: Final[str] = (
        "QMT_CONNECTION_BUDGET_BROKER_SYNC_STORM_WINDOW_SEC"
    )
    QMT_CONNECTION_BUDGET_FUSE_COOLDOWN_SEC: Final[str] = "QMT_CONNECTION_BUDGET_FUSE_COOLDOWN_SEC"
    QMT_CONNECTION_BUDGET_ALERT_DEDUPE_SEC: Final[str] = "QMT_CONNECTION_BUDGET_ALERT_DEDUPE_SEC"
    # P0-13：资产连续相同快照阈值（交易时段内连续 N 次心跳 cash 不变 → 标记 stale）
    QMT_ASSET_STALE_CONSECUTIVE_THRESHOLD: Final[str] = "QMT_ASSET_STALE_CONSECUTIVE_THRESHOLD"
    # P1-25：资产载荷异常（cash=None/NaN/负值）连续阈值；达到后标记 payload invalid。
    QMT_ASSET_INVALID_CONSECUTIVE_THRESHOLD: Final[str] = "QMT_ASSET_INVALID_CONSECUTIVE_THRESHOLD"
    # P1-25：live 下资产载荷 invalid 是否强制 fail-close（默认开启）。
    QMT_ASSET_INVALID_FAIL_CLOSE_LIVE: Final[str] = "QMT_ASSET_INVALID_FAIL_CLOSE_LIVE"
    # XtTrader 回调线程策略：开启后调用 set_relaxed_response_order_enabled(True)。
    # 默认关闭（异步查询优先，避免回调线程阻塞）。
    QMT_RELAXED_RESPONSE_ORDER_ENABLED: Final[str] = "QMT_RELAXED_RESPONSE_ORDER_ENABLED"
    # hkcodex_miniqmt：为 true 时才允许 stock_list=None 的全市场重查询（get_limit_info / daily_basic；stk_limit 同源）
    HKCODEX_ALLOW_FULL_MARKET_QUERIES: Final[str] = "HKCODEX_ALLOW_FULL_MARKET_QUERIES"

    # 交易执行层
    TRADE_MIN_COMMISSION: Final[str] = "TRADE_MIN_COMMISSION"
    TRADE_LOT_SIZE: Final[str] = "TRADE_LOT_SIZE"
    TRADE_SELL_MAX_RETRY: Final[str] = "TRADE_SELL_MAX_RETRY"
    TRADE_BUY_MAX_RETRY: Final[str] = "TRADE_BUY_MAX_RETRY"
    TRADE_ORDER_INTERVAL_SEC: Final[str] = "TRADE_ORDER_INTERVAL_SEC"
    TRADE_FAST_POLL_SEC: Final[str] = "TRADE_FAST_POLL_SEC"
    TRADE_EVENT_WAIT_SEC: Final[str] = "TRADE_EVENT_WAIT_SEC"
    TRADE_COMPLETION_TIMEOUT_SEC: Final[str] = "TRADE_COMPLETION_TIMEOUT_SEC"
    TRADE_OPEN_BOARD_THRESHOLD: Final[str] = "TRADE_OPEN_BOARD_THRESHOLD"
    TRADE_CASH_FUSE_THRESHOLD: Final[str] = "TRADE_CASH_FUSE_THRESHOLD"
    # 再平衡意图发送失败策略：auto/fail_open/fail_closed（见 live_trading.rebalance_portfolio_async）
    ORDER_INTENT_FAIL_POLICY: Final[str] = "ORDER_INTENT_FAIL_POLICY"
    # 行情适配失败策略：fail_open | fail_closed（见 live_trading_broker）
    BROKER_ADAPTER_QUOTE_FAIL_POLICY: Final[str] = "BROKER_ADAPTER_QUOTE_FAIL_POLICY"
    # 连续 T+1 缺失与可卖量为零的告警阈值（见 broker 健康观测）
    BROKER_T1_MISSING_ALERT_THRESHOLD: Final[str] = "BROKER_T1_MISSING_ALERT_THRESHOLD"
    BROKER_SELLABLE_ZERO_ALERT_THRESHOLD: Final[str] = "BROKER_SELLABLE_ZERO_ALERT_THRESHOLD"
    # 为 true 时：证券状态不确定则禁止下单（见 go-live YAML 模板）
    ORDER_BLOCK_UNCERTAIN_STOCK_STATUS: Final[str] = "ORDER_BLOCK_UNCERTAIN_STOCK_STATUS"
    # 为 true 时：缺少估算涨跌停信息则禁止下单（见 go-live YAML 模板）
    ORDER_BLOCK_ESTIMATED_LIMIT_INFO: Final[str] = "ORDER_BLOCK_ESTIMATED_LIMIT_INFO"
    # 逗号分隔的可交易证券状态取值
    TRADEABLE_STOCK_STATUS_VALUES: Final[str] = "TRADEABLE_STOCK_STATUS_VALUES"
    CASH_LEDGER_WRITE_MODE: Final[str] = "CASH_LEDGER_WRITE_MODE"
    # 下单执行线程超时秒数：<=0 或未设置表示不启用超时（见 oskh_core.execution_ports）
    EXECUTION_THREAD_TIMEOUT_SEC: Final[str] = "EXECUTION_THREAD_TIMEOUT_SEC"
    EXECUTION_RETRY_ALLOW_SLEEP_ON_LOOP_THREAD: Final[str] = "EXECUTION_RETRY_ALLOW_SLEEP_ON_LOOP_THREAD"
    # 执行器关键 schema 初始化失败策略：hard_fail | warn
    EXECUTOR_SCHEMA_INIT_FAILURE_POLICY: Final[str] = "EXECUTOR_SCHEMA_INIT_FAILURE_POLICY"

    # Redis层
    REDIS_AUDIT_FLUSH_SEC: Final[str] = "REDIS_AUDIT_FLUSH_SEC"
    REDIS_AUDIT_BATCH_SIZE: Final[str] = "REDIS_AUDIT_BATCH_SIZE"
    REDIS_BRIDGE_WORKERS: Final[str] = "REDIS_BRIDGE_WORKERS"
    REDIS_MONITOR_WORKERS: Final[str] = "REDIS_MONITOR_WORKERS"
    REDIS_BLOCK_MS: Final[str] = "REDIS_BLOCK_MS"

    # SQLite/持久化层
    # 决策路由审计写库采样（见 gateway / sqlite 路由）
    DB_ROUTE_DECISION_AUDIT_DB_ENABLED: Final[str] = "DB_ROUTE_DECISION_AUDIT_DB_ENABLED"
    DB_ROUTE_DECISION_AUDIT_DB_MIN_PRIORITY: Final[str] = "DB_ROUTE_DECISION_AUDIT_DB_MIN_PRIORITY"
    DB_ROUTE_DECISION_AUDIT_DB_SAMPLE_RATE: Final[str] = "DB_ROUTE_DECISION_AUDIT_DB_SAMPLE_RATE"
    SQLITE_TIMEOUT_SEC: Final[str] = "SQLITE_TIMEOUT_SEC"
    GATEWAY_SCHEMA_ENSURE_OP_TIMEOUT_SEC: Final[str] = "GATEWAY_SCHEMA_ENSURE_OP_TIMEOUT_SEC"
    SQLITE_WAL_CHECKPOINT: Final[str] = "SQLITE_WAL_CHECKPOINT"
    WAL_SIZE_CHECKPOINT_THRESHOLD_KB: Final[str] = "WAL_SIZE_CHECKPOINT_THRESHOLD_KB"
    WAL_CHECKPOINT_MODE: Final[str] = "WAL_CHECKPOINT_MODE"
    WAL_PERIODIC_CHECKPOINT_INTERVAL_S: Final[str] = "WAL_PERIODIC_CHECKPOINT_INTERVAL_S"
    COLD_STORAGE_ENABLED: Final[str] = "COLD_STORAGE_ENABLED"
    COLD_STORAGE_PATH: Final[str] = "COLD_STORAGE_PATH"
    COLD_STORAGE_URI: Final[str] = "QUANT_COLD_STORAGE_URI"  # S3/OSS URI
    MONEY_SQLITE_ROUNDING: Final[str] = "MONEY_SQLITE_ROUNDING"
    # strategy_cash_book FEN migration:
    # - 0/false: read REAL columns (legacy/default)
    # - 1/true: prefer *_fen columns for read path (fallback to REAL when schema not ready)
    # P1-14: 已删除 schema 兼容层，统一用 fen 查询；保留常量定义避免引用报错
    CASH_BOOK_READ_FROM_FEN: Final[str] = "CASH_BOOK_READ_FROM_FEN"

    # 日志层
    QUANT_LOG_DIR: Final[str] = "QUANT_LOG_DIR"
    QUANT_LOG_CONSOLE: Final[str] = "QUANT_LOG_CONSOLE"
    # 热日志最低级别（DEBUG/INFO/WARNING/ERROR）；未设时热日志默认为 DEBUG
    QUANT_LOG_HOT_LEVEL: Final[str] = "QUANT_LOG_HOT_LEVEL"
    # 为 true 时额外写入 quant_json_*.log（JSON Lines，便于 Loki/ELK）
    QUANT_LOG_JSON: Final[str] = "QUANT_LOG_JSON"
    # scoped（默认）：日志写在 QUANT_LOG_DIR/<INSTANCE_ID|pid_xxx>/ 下，避免多进程轮转竞态；flat 则直接写根目录
    QUANT_LOG_ROOT_LAYOUT: Final[str] = "QUANT_LOG_ROOT_LAYOUT"
    # quant_logger 诊断与 backtrace 开关（见 QuantLoggerFactory.initialize）
    QUANT_LOG_DIAGNOSE: Final[str] = "QUANT_LOG_DIAGNOSE"
    QUANT_LOG_BACKTRACE_DEBUG: Final[str] = "QUANT_LOG_BACKTRACE_DEBUG"
    QUANT_LOG_BACKTRACE_ERROR: Final[str] = "QUANT_LOG_BACKTRACE_ERROR"
    # 为 false 时不在初始化时 logger.remove(0)，便于同进程内保留先于 initialize 注册的第三方 sink
    QUANT_LOGURU_REMOVE_DEFAULT: Final[str] = "QUANT_LOGURU_REMOVE_DEFAULT"
    LOG_RETENTION_DAYS: Final[str] = "LOG_RETENTION_DAYS"
    ERROR_RETENTION: Final[str] = "ERROR_RETENTION"

    # 性能监控层
    PERF_MONITOR_ENABLED: Final[str] = "PERF_MONITOR_ENABLED"
    PERF_CRITICAL_MS: Final[str] = "PERF_CRITICAL_MS"
    # true 时 PERF_CRITICAL / PERF_CRITICAL_SLOW_STAGE 走 warning，降低与真实 ERROR 混淆（默认 false）
    PERF_CRITICAL_LOG_AS_WARNING: Final[str] = "PERF_CRITICAL_LOG_AS_WARNING"
    PERF_STRATEGY_MS: Final[str] = "PERF_STRATEGY_MS"

    # 基础设施生命周期（common.lifecycle）：Layer 2.5 预加载失败时是否阻断启动
    QUANT_LAYER25_FAIL_FAST: Final[str] = "QUANT_LAYER25_FAIL_FAST"
    # 基础设施生命周期（common.lifecycle）：true 时非致命合规项失败也阻断启动
    QUANT_INFRA_COMPLIANCE_FAIL_FAST: Final[str] = "QUANT_INFRA_COMPLIANCE_FAIL_FAST"

    # 安全层（Phase 3新增）
    SENSITIVE_KEYWORDS_ENV: Final[str] = "SENSITIVE_KEYWORDS_ENV"  # 敏感词扩展
    QUANT_ENV: Final[str] = "QUANT_ENV"  # 运行环境（prod/dev/test）

    # 多账户配置（Phase 3新增）
    ACCOUNT_ID_LIST: Final[str] = "ACCOUNT_ID_LIST"  # 逗号分隔的多账户列表
    DEFAULT_ACCOUNT_ID: Final[str] = "DEFAULT_ACCOUNT_ID"

    # miniQMT  userdata / 连接管理（业务与 hkcodex）
    QMT_USERDATA_PATH: Final[str] = "QMT_USERDATA_PATH"
    QMT_PATH_PROP: Final[str] = "QMT_PATH_PROP"
    QMT_PATH_AM: Final[str] = "QMT_PATH_AM"
    USE_NEW_CONNECTION_MANAGER: Final[str] = "USE_NEW_CONNECTION_MANAGER"
    ACCOUNT_ID: Final[str] = "ACCOUNT_ID"

    # 策略与展示 / 选股元数据（CLI 可能写入 os.environ 供子进程读取）
    STRATEGY_NAME: Final[str] = "STRATEGY_NAME"
    # 为 true 时：桥接 send_signal 在尚无 strategy_cash_book 行时用账户级 portfolio_snapshots 种子（旧语义；默认 false 与 strategy_key 严格对齐）
    SEED_STRATEGY_BOOK_FROM_ACCOUNT_SNAPSHOT: Final[str] = "SEED_STRATEGY_BOOK_FROM_ACCOUNT_SNAPSHOT"
    # stock_selections.selection_logic / EOD 末级回退（统一 SELECTION_LOGIC）
    SELECTION_LOGIC: Final[str] = "SELECTION_LOGIC"
    # Deprecated. Kept only for fail-fast error reporting in strategy_config.
    SELECTION_LOGIC_FALLBACK: Final[str] = "SELECTION_LOGIC_FALLBACK"
    SELECTION_INTRADAY_OVERWRITE_GUARD: Final[str] = "SELECTION_INTRADAY_OVERWRITE_GUARD"
    SELECTOR_ALLOW_INTRADAY_OVERWRITE: Final[str] = "SELECTOR_ALLOW_INTRADAY_OVERWRITE"
    SELECTOR_FAIL_CLOSED: Final[str] = "SELECTOR_FAIL_CLOSED"
    STRATEGY_CLASS: Final[str] = "STRATEGY_CLASS"
    STRATEGY_CLASS_ALLOWLIST: Final[str] = "STRATEGY_CLASS_ALLOWLIST"
    # Primary strategy import failure only: optional substitute class (discouraged for live; see startup_precheck).
    DEFAULT_FALLBACK_STRATEGY_CLASS: Final[str] = "DEFAULT_FALLBACK_STRATEGY_CLASS"
    STRATEGY_CONFIG: Final[str] = "STRATEGY_CONFIG"
    # Runner profile isolation: pool_sqlite | etf | grid
    TRADING_RUNNER_PROFILE: Final[str] = "TRADING_RUNNER_PROFILE"
    # 模式语义契约：buy_sell_decoupled | rebalance_coupled（见 oskh_core.trading_mode_contract）
    TRADING_MODE_CONTRACT: Final[str] = "TRADING_MODE_CONTRACT"
    # pool_sqlite 上允许 TRADING_MODE_CONTRACT=rebalance_coupled 的实验开关（默认关闭；非 CSV 生产基线）
    TRADING_POOL_SQLITE_ALLOW_REBALANCE_COUPLED_EXPERIMENTAL: Final[str] = (
        "TRADING_POOL_SQLITE_ALLOW_REBALANCE_COUPLED_EXPERIMENTAL"
    )
    TRADING_ENABLE_ROUTINE_WINDOW_GUARD: Final[str] = "TRADING_ENABLE_ROUTINE_WINDOW_GUARD"
    # 可选：从午夜算起的分钟数，覆盖常规买入窗口左端点（默认 14:30）；仅用于本地/测试，生产勿设
    ROUTINE_BUY_WINDOW_START: Final[str] = "ROUTINE_BUY_WINDOW_START"
    # 可选：从午夜算起的分钟数，覆盖常规买入窗口右端点（默认 live 15:00 / paper 17:00）；仅用于本地/测试，生产勿设
    ROUTINE_BUY_WINDOW_END: Final[str] = "ROUTINE_BUY_WINDOW_END"
    TRADING_ENABLE_DEFERRED_CYCLE: Final[str] = "TRADING_ENABLE_DEFERRED_CYCLE"
    # 延期买入时间策略：
    # - trading_session: 交易时段内均可执行（默认）
    # - outside_routine_window: 仅在常规买入窗口[14:30,15:00)之外执行
    # - after_routine_window: outside_routine_window 的历史别名
    TRADING_DEFERRED_BUY_SCHEDULE_MODE: Final[str] = "TRADING_DEFERRED_BUY_SCHEDULE_MODE"
    # pool_sqlite 默认可 true：允许延期买入分钟任务与常规买入窗口并发（各资金池独立）
    TRADING_DEFERRED_BUY_ALLOW_ROUTINE_WINDOW_OVERLAP: Final[str] = (
        "TRADING_DEFERRED_BUY_ALLOW_ROUTINE_WINDOW_OVERLAP"
    )
    # 为 true 时：即使 CAPITAL_ROUTINE_DAILY_CAP_YUAN<=0 仍执行延期到期释放任务
    TRADING_ENABLE_DEFERRED_RELEASE_WHEN_ROUTINE_CAP_OFF: Final[str] = (
        "TRADING_ENABLE_DEFERRED_RELEASE_WHEN_ROUTINE_CAP_OFF"
    )
    TRADING_ENABLE_ROUTINE_CLOSE_CANCEL: Final[str] = "TRADING_ENABLE_ROUTINE_CLOSE_CANCEL"
    TRADING_ENABLE_ROUTINE_CLOSE_CANCEL_SELL: Final[str] = (
        "TRADING_ENABLE_ROUTINE_CLOSE_CANCEL_SELL"
    )
    TRADING_ENABLE_INTRADAY_SELL_SCAN: Final[str] = "TRADING_ENABLE_INTRADAY_SELL_SCAN"
    # 可卖量查询失败策略：
    # - fail_closed: 默认；卖出巡检不降级
    # - fallback_with_approval: 需人工审批码 + 连续失败阈值后允许回退到持仓量（break-glass）
    SELLABLE_QUERY_FAILURE_POLICY: Final[str] = "SELLABLE_QUERY_FAILURE_POLICY"
    SELLABLE_QUERY_FALLBACK_APPROVAL_CODE: Final[str] = "SELLABLE_QUERY_FALLBACK_APPROVAL_CODE"
    SELLABLE_QUERY_FALLBACK_FAILURE_THRESHOLD: Final[str] = "SELLABLE_QUERY_FALLBACK_FAILURE_THRESHOLD"
    # 为 true 时：卖出决策内核在需 lot 指标但加载失败时不再评估卖出（本周期无卖单）；默认 false=降级为空指标继续
    SELL_METRICS_LOAD_FAIL_CLOSED: Final[str] = "SELL_METRICS_LOAD_FAIL_CLOSED"
    # 为 true 时：再平衡买计划若两次读 strategy_cash_book 均不可用则本周期不买；默认 false=沿用内存 STRATEGY_CASH
    STRATEGY_CASH_BOOK_READ_FAIL_CLOSED: Final[str] = "STRATEGY_CASH_BOOK_READ_FAIL_CLOSED"
    # P0-3：再平衡 buy-submit 预标记失败是否阻断下单（默认 true=fail-closed）
    REBALANCE_PRECOMMIT_FAIL_CLOSED: Final[str] = "REBALANCE_PRECOMMIT_FAIL_CLOSED"
    # P0-3：再平衡同股 SUBMITTED BUY 去重总开关（默认 true）
    REBALANCE_DEDUP_SUBMITTED_BUYS: Final[str] = "REBALANCE_DEDUP_SUBMITTED_BUYS"
    # P0-3：去重查询异常时是否 fail-closed（默认 true=宁可少买不可多买）
    REBALANCE_DEDUP_FAIL_CLOSED: Final[str] = "REBALANCE_DEDUP_FAIL_CLOSED"
    DEFERRED_CAPITAL_AUDIT_TOLERANCE_YUAN: Final[str] = "DEFERRED_CAPITAL_AUDIT_TOLERANCE_YUAN"
    # 延迟资金一致性审计容忍度百分比（0.001 = 0.1%）；与固定金额 max() 取大
    DEFERRED_CAPITAL_AUDIT_TOLERANCE_PCT: Final[str] = "DEFERRED_CAPITAL_AUDIT_TOLERANCE_PCT"
    INTRADAY_SELL_SCAN_INTERVAL_MINUTES: Final[str] = "INTRADAY_SELL_SCAN_INTERVAL_MINUTES"
    # CSV 解耦基线：ignore=卖出巡检不参与当日选股名单语义；use_if_ready=名单就绪时可参与 in_selection
    INTRADAY_SELL_SCAN_SELECTION_MODE: Final[str] = "INTRADAY_SELL_SCAN_SELECTION_MODE"
    # true 时允许选股未就绪仍走再平衡买入（削弱 CSV 流程；生产基线应为 false）
    CSV_REBALANCE_ALLOW_BUY_WITHOUT_SELECTION_READY: Final[str] = (
        "CSV_REBALANCE_ALLOW_BUY_WITHOUT_SELECTION_READY"
    )
    ROUTINE_CLOSE_CANCEL_MODE: Final[str] = "ROUTINE_CLOSE_CANCEL_MODE"
    # 收盘撤单窗口 [start, end)，HHMM 格式。默认 live 14:57-15:00 / paper 16:57-17:00
    ROUTINE_CLOSE_CANCEL_WINDOW_START: Final[str] = "ROUTINE_CLOSE_CANCEL_WINDOW_START"
    ROUTINE_CLOSE_CANCEL_WINDOW_END: Final[str] = "ROUTINE_CLOSE_CANCEL_WINDOW_END"
    # CSV close governance（§3.4）参数化：常规买收盘治理轮询/预算/重试上限
    ROUTINE_CLOSE_GOVERNANCE_INTERVAL_SEC: Final[str] = "ROUTINE_CLOSE_GOVERNANCE_INTERVAL_SEC"
    ROUTINE_CLOSE_GOVERNANCE_TIMEOUT_SEC: Final[str] = "ROUTINE_CLOSE_GOVERNANCE_TIMEOUT_SEC"
    ROUTINE_CLOSE_GOVERNANCE_MAX_RETRIES: Final[str] = "ROUTINE_CLOSE_GOVERNANCE_MAX_RETRIES"
    # 卖侧 stop_loss / take_profit 口径参数（用于策略与监控统一默认值）
    SELL_STOP_LOSS_GOVERNANCE_CHECK_INTERVAL_SEC: Final[str] = (
        "SELL_STOP_LOSS_GOVERNANCE_CHECK_INTERVAL_SEC"
    )
    SELL_STOP_LOSS_GOVERNANCE_TIMEOUT_SEC: Final[str] = "SELL_STOP_LOSS_GOVERNANCE_TIMEOUT_SEC"
    SELL_STOP_LOSS_GOVERNANCE_MAX_RETRIES: Final[str] = "SELL_STOP_LOSS_GOVERNANCE_MAX_RETRIES"
    SELL_TAKE_PROFIT_GOVERNANCE_CHECK_INTERVAL_SEC: Final[str] = (
        "SELL_TAKE_PROFIT_GOVERNANCE_CHECK_INTERVAL_SEC"
    )
    SELL_TAKE_PROFIT_GOVERNANCE_TIMEOUT_SEC: Final[str] = "SELL_TAKE_PROFIT_GOVERNANCE_TIMEOUT_SEC"
    SELL_TAKE_PROFIT_GOVERNANCE_MAX_RETRIES: Final[str] = "SELL_TAKE_PROFIT_GOVERNANCE_MAX_RETRIES"
    # 延期买入治理轮询口径（交易时段内）
    DEFERRED_BUY_GOVERNANCE_CHECK_INTERVAL_SEC: Final[str] = "DEFERRED_BUY_GOVERNANCE_CHECK_INTERVAL_SEC"
    TRADING_ENABLE_CAPITAL_POOL: Final[str] = "TRADING_ENABLE_CAPITAL_POOL"
    # CSV 模式全量买入候选：true 时不按仓位上限截断当次买入候选集（仅影响 CSV runner）
    CSV_BUY_ALL_SELECTION_ENABLED: Final[str] = "CSV_BUY_ALL_SELECTION_ENABLED"
    # CSV 选股就绪门禁：当前墙钟 >= UNIVERSE_READY_TIME 时买入流水线才消费导入数据（设 "00:00" 即全天可用）
    UNIVERSE_READY_TIME: Final[str] = "UNIVERSE_READY_TIME"
    CSV_SELECTION_NOT_READY_ALERT_THROTTLE_SEC: Final[str] = "CSV_SELECTION_NOT_READY_ALERT_THROTTLE_SEC"
    # CSV 选股就绪栅栏宽限期（分钟）：REBALANCE_TIME 后多久未就绪则升级 P0
    SELECTION_BARRIER_GRACE_MIN: Final[str] = "SELECTION_BARRIER_GRACE_MIN"
    CSV_STRATEGY_PLACEHOLDER_POLICY: Final[str] = "CSV_STRATEGY_PLACEHOLDER_POLICY"
    CSV_LIVE_GUARD_MODE: Final[str] = "CSV_LIVE_GUARD_MODE"
    # CSV 基线指纹/严格校验（见 main.py / CSV gates）
    TRADING_CSV_BASELINE_STRICT: Final[str] = "TRADING_CSV_BASELINE_STRICT"
    # CSV-only：拒绝 trading-etf / trading-grid；与 runtime YAML 合并（env > YAML > 默认 true）
    TRADING_CSV_ONLY_MODE: Final[str] = "TRADING_CSV_ONLY_MODE"
    # 分钟任务失败升级阈值（Monitor / 交易路径）
    TRADING_MINUTE_TASK_FAILURE_ESCALATION_THRESHOLD: Final[str] = (
        "TRADING_MINUTE_TASK_FAILURE_ESCALATION_THRESHOLD"
    )
    TRADING_MINUTE_TASK_FAILURE_ESCALATION_THRESHOLD_CRITICAL: Final[str] = (
        "TRADING_MINUTE_TASK_FAILURE_ESCALATION_THRESHOLD_CRITICAL"
    )
    STRICT_STRATEGY_ENTER: Final[str] = "STRICT_STRATEGY_ENTER"
    # 策略键切换时从 execution_log 重放持仓批次（见 live_trading + position_manager）
    REPLAY_POSITION_LOTS_ON_STRATEGY_SWITCH: Final[str] = "REPLAY_POSITION_LOTS_ON_STRATEGY_SWITCH"
    REPLAY_FAIL_BLOCKS_STARTUP: Final[str] = "REPLAY_FAIL_BLOCKS_STARTUP"
    STRATEGY_SWITCH_AUDIT_FAILS_STARTUP: Final[str] = "STRATEGY_SWITCH_AUDIT_FAILS_STARTUP"
    STRATEGY_SWITCH_OPERATOR_NOTE: Final[str] = "STRATEGY_SWITCH_OPERATOR_NOTE"
    STRATEGY_RUNTIME_STATE_PATH: Final[str] = "STRATEGY_RUNTIME_STATE_PATH"
    # 为 true 时：持久化 strategy_runtime_state（portfolio.db 单例行）失败则阻断启动（默认 false，仅打 warning）
    STRATEGY_RUNTIME_STATE_SAVE_REQUIRED: Final[str] = (
        "STRATEGY_RUNTIME_STATE_SAVE_REQUIRED"
    )

    # 费用与资金
    COMMISSION_RATE: Final[str] = "COMMISSION_RATE"
    TAX_RATE: Final[str] = "TAX_RATE"
    STAMP_TAX_RATE_STOCK: Final[str] = "STAMP_TAX_RATE_STOCK"
    STAMP_TAX_EXEMPT_PREFIXES: Final[str] = "STAMP_TAX_EXEMPT_PREFIXES"
    STAMP_TAX_EXEMPT_SYMBOLS: Final[str] = "STAMP_TAX_EXEMPT_SYMBOLS"
    STAMP_TAX_UNKNOWN_AS_STOCK: Final[str] = "STAMP_TAX_UNKNOWN_AS_STOCK"
    # Optional Shanghai A-share transfer fee estimate (see trade_fee_policy); default 0 = unchanged legacy behavior.
    TRANSFER_FEE_RATE_SH: Final[str] = "TRANSFER_FEE_RATE_SH"
    MIN_COMMISSION: Final[str] = "MIN_COMMISSION"
    INITIAL_STRATEGY_CASH: Final[str] = "INITIAL_STRATEGY_CASH"
    INITIAL_STRATEGY_POSITIONS: Final[str] = "INITIAL_STRATEGY_POSITIONS"
    TRADING_TYPE: Final[str] = "TRADING_TYPE"
    # 覆盖 Stream 载荷 `source`（审计）；非空时优先于 TRADING_TYPE 推导的 live_bridge/sim_bridge
    STREAM_ORDER_SIGNAL_SOURCE: Final[str] = "STREAM_ORDER_SIGNAL_SOURCE"

    # 交易时段与再平衡（与 strategy_config 一致；SchedulingConstants 另有 SCHED_* 别名）
    EOD_UPDATE_TIME: Final[str] = "EOD_UPDATE_TIME"
    REBALANCE_FREQUENCY: Final[str] = "REBALANCE_FREQUENCY"
    REBALANCE_TIME: Final[str] = "REBALANCE_TIME"
    REBALANCE_WEEKLY_DAY: Final[str] = "REBALANCE_WEEKLY_DAY"
    REBALANCE_MONTHLY_DAY: Final[str] = "REBALANCE_MONTHLY_DAY"
    CHECK_TIME: Final[str] = "CHECK_TIME"
    # 为 true 时：主循环在 HH:MM 交易时段内再校验 is_trade_day（防本机时钟/日历与交易所不一致；不替代临时休市公告）
    TRADING_SESSION_CROSSCHECK_TRADE_DAY: Final[str] = "TRADING_SESSION_CROSSCHECK_TRADE_DAY"
    # 为 1/true 时：主循环在加载策略/校验 QMT 前若 wall 历日非交易所交易日则早退（仅审计；默认关闭以免改变生产行为）
    TRADING_ENABLE_MAIN_LOOP_EXCHANGE_TRADING_DAY_GATE: Final[str] = (
        "TRADING_ENABLE_MAIN_LOOP_EXCHANGE_TRADING_DAY_GATE"
    )
    # docs/architecture/timezone-v2.md：业务语义默认时区（IANA）；当前实现固定 Asia/Shanghai，键供配置显式与审计
    TRADING_GLOBAL_TZ: Final[str] = "TRADING_GLOBAL_TZ"
    # 连续竞价窗口边界容差（秒），默认 0；上限见 strategy_config 钳制
    TRADING_SESSION_TOLERANCE_SEC: Final[str] = "TRADING_SESSION_TOLERANCE_SEC"
    TRADING_LIVE_SESSION_MORNING_START: Final[str] = "TRADING_LIVE_SESSION_MORNING_START"
    TRADING_LIVE_SESSION_MORNING_END: Final[str] = "TRADING_LIVE_SESSION_MORNING_END"
    TRADING_LIVE_SESSION_AFTERNOON_START: Final[str] = "TRADING_LIVE_SESSION_AFTERNOON_START"
    TRADING_LIVE_SESSION_AFTERNOON_END: Final[str] = "TRADING_LIVE_SESSION_AFTERNOON_END"
    TRADING_PAPER_SESSION_START: Final[str] = "TRADING_PAPER_SESSION_START"
    TRADING_PAPER_SESSION_END: Final[str] = "TRADING_PAPER_SESSION_END"

    # 业务侧价格容差（live_trading / 策略）；QMT 行情层见 QMT_PRICE_TOLERANCE
    PRICE_TOLERANCE: Final[str] = "PRICE_TOLERANCE"

    TARGET_POSITION_RATIO: Final[str] = "TARGET_POSITION_RATIO"
    MIN_CASH_LEFT: Final[str] = "MIN_CASH_LEFT"
    # Deprecated for non-ETF modes; kept only for hard-cut validation and migration diagnostics.
    STOCK_NUM: Final[str] = "STOCK_NUM"
    # ETF-only capacity control.
    ETF_MAX_POSITIONS: Final[str] = "ETF_MAX_POSITIONS"
    # 当日选股名单（selection universe）最大行数；0=不截断（仅防 OOM 时设正数上限）
    MAX_SELECTION_ROWS: Final[str] = "MAX_SELECTION_ROWS"
    # 每次再平衡最多新开仓只数；0=不额外限制（仅用 max_positions 空槽）
    MAX_NEW_BUYS_PER_REBALANCE: Final[str] = "MAX_NEW_BUYS_PER_REBALANCE"
    POSITION_COST_METHOD: Final[str] = "POSITION_COST_METHOD"
    POSITION_MANAGER_REQUIRE_TRACE_ID_24: Final[str] = "POSITION_MANAGER_REQUIRE_TRACE_ID_24"

    # 再平衡卖出增强（0/默认=关闭；见 live_trading determine_sells）
    SELL_RULE_STOP_LOSS_PCT: Final[str] = "SELL_RULE_STOP_LOSS_PCT"
    SELL_RULE_TAKE_PROFIT_PCT: Final[str] = "SELL_RULE_TAKE_PROFIT_PCT"
    SELL_RULE_MAX_HOLD_DAYS: Final[str] = "SELL_RULE_MAX_HOLD_DAYS"
    SELL_RULE_MIN_HOLD_DAYS: Final[str] = "SELL_RULE_MIN_HOLD_DAYS"
    SELL_RULE_PRECEDENCE: Final[str] = "SELL_RULE_PRECEDENCE"
    # 方案3（按分桶）配置：stock->bucket, bucket->preset, bucket规则覆盖与默认项
    SELL_BUCKET_STOCK_MAP_JSON: Final[str] = "SELL_BUCKET_STOCK_MAP_JSON"
    SELL_BUCKET_PRESET_MAP_JSON: Final[str] = "SELL_BUCKET_PRESET_MAP_JSON"
    SELL_BUCKET_RULE_OVERRIDES_JSON: Final[str] = "SELL_BUCKET_RULE_OVERRIDES_JSON"
    SELL_BUCKET_ACCOUNT_BINDINGS_JSON: Final[str] = "SELL_BUCKET_ACCOUNT_BINDINGS_JSON"
    SELL_BUCKET_STRATEGY_BINDINGS_JSON: Final[str] = "SELL_BUCKET_STRATEGY_BINDINGS_JSON"
    SELL_BUCKET_PRESET_PARAMS_JSON: Final[str] = "SELL_BUCKET_PRESET_PARAMS_JSON"
    SELL_BUCKET_DEFAULT_ID: Final[str] = "SELL_BUCKET_DEFAULT_ID"
    SELL_BUCKET_DEFAULT_PRESET: Final[str] = "SELL_BUCKET_DEFAULT_PRESET"
    # 持仓批次 entry 归因 与 account/strategy 治理约束冲突时的优先级：entry_preferred | governance_override
    SELL_BUCKET_ENTRY_BINDING_PRECEDENCE: Final[str] = "SELL_BUCKET_ENTRY_BINDING_PRECEDENCE"
    # 非 live 时默认仅 warning 后仍建 router；置 true 则与 live 一致对无效 SELL_BUCKET_* fail-closed（联调/CI）
    SELL_BUCKET_STRICT_OUTSIDE_LIVE: Final[str] = "SELL_BUCKET_STRICT_OUTSIDE_LIVE"
    # MA 快照口径：prior_completed_session | intraday
    MA_INDICATOR_BAR_POLICY: Final[str] = "MA_INDICATOR_BAR_POLICY"

    # 日度常规额度资金池（0=关闭，再平衡仍用 TARGET_POSITION_RATIO）
    CAPITAL_ROUTINE_DAILY_CAP_YUAN: Final[str] = "CAPITAL_ROUTINE_DAILY_CAP_YUAN"
    # BASE_PLUS_SUPPLEMENT（默认，补充资金不计入日度cap）| HARD_TOTAL（补充资金也计入日度cap）
    ROUTINE_CAP_POLICY: Final[str] = "ROUTINE_CAP_POLICY"
    DEFERRED_BUY_MAX_TRADING_DAYS: Final[str] = "DEFERRED_BUY_MAX_TRADING_DAYS"
    # 延期买入保护性限价：默认 current_price_100pct；可切换为 slippage_cap 并支持按预设/标的覆盖
    DEFERRED_BUY_LIMIT_PRICE_MODE: Final[str] = "DEFERRED_BUY_LIMIT_PRICE_MODE"
    DEFERRED_BUY_SLIPPAGE_CAP_DEFAULT_PCT: Final[str] = "DEFERRED_BUY_SLIPPAGE_CAP_DEFAULT_PCT"
    DEFERRED_BUY_SLIPPAGE_CAP_BY_PRESET_JSON: Final[str] = "DEFERRED_BUY_SLIPPAGE_CAP_BY_PRESET_JSON"
    DEFERRED_BUY_SLIPPAGE_CAP_BY_STOCK_JSON: Final[str] = "DEFERRED_BUY_SLIPPAGE_CAP_BY_STOCK_JSON"
    CAPITAL_POOL_INITIAL_YUAN: Final[str] = "CAPITAL_POOL_INITIAL_YUAN"
    # 策略逻辑封顶（元）；0=关闭。与 strategy_cash_book 组合见 strategy_config
    CAPITAL_STRATEGY_CEILING_YUAN: Final[str] = "CAPITAL_STRATEGY_CEILING_YUAN"
    # CSV 口径自检声明总资金（元）；0=关闭自检
    CAPITAL_EXPECTED_TOTAL_YUAN: Final[str] = "CAPITAL_EXPECTED_TOTAL_YUAN"
    # 封顶口径：CASH_ONLY（仅可用现金）或 CASH_PLUS_POSITION_MV（现金+持仓市值，策略内视图）
    CAPITAL_STRATEGY_CEILING_MODE: Final[str] = "CAPITAL_STRATEGY_CEILING_MODE"
    # EOD 对账：现金/权益偏差超过该比例（如 0.01=1%）触发软告警（0=关闭软告警阈值）
    EOD_RECONCILE_SOFT_ALERT_PCT: Final[str] = "EOD_RECONCILE_SOFT_ALERT_PCT"
    # 再平衡卖出规则：风险类 reason 组合 any|all（见 sell_rules）
    SELL_RULE_RISK_COMBINE: Final[str] = "SELL_RULE_RISK_COMBINE"
    # 技术面分轨：入场/出场是否启用（false 则跳过该轨求值）
    INDICATOR_RULES_ENTRY_ENABLED: Final[str] = "INDICATOR_RULES_ENTRY_ENABLED"
    INDICATOR_RULES_EXIT_ENABLED: Final[str] = "INDICATOR_RULES_EXIT_ENABLED"
    # K 线截止策略：prior_completed_session | intraday（默认 prior_completed_session）
    INDICATOR_BAR_POLICY: Final[str] = "INDICATOR_BAR_POLICY"
    # RSRS 技术轨：0 表示沿用 STRATEGY_CONFIG_JSON.reg_num；否则覆盖窗口长度
    INDICATOR_RSRS_REG_NUM: Final[str] = "INDICATOR_RSRS_REG_NUM"
    # signal_date | prior_completed_session；空表示尽量沿用 STRATEGY_CONFIG_JSON.rsrs_data_end_mode，否则 prior_completed_session
    INDICATOR_RSRS_DATA_END_MODE: Final[str] = "INDICATOR_RSRS_DATA_END_MODE"
    # 入场：features.rsrs_score 须 >= 该值（未设置等价 -inf，不挡）
    INDICATOR_ENTRY_RSRS_MIN_SCORE: Final[str] = "INDICATOR_ENTRY_RSRS_MIN_SCORE"
    # 出场：data_ok 且 score < 该值则追加 rsrs_below_threshold（未设置等价 -inf，不触发）
    INDICATOR_EXIT_RSRS_BELOW_SCORE: Final[str] = "INDICATOR_EXIT_RSRS_BELOW_SCORE"
    # M.1-3: RSRS 退出阈值解析失败策略（block / conservative_exit）
    RSRS_EXIT_ON_FAILURE: Final[str] = "RSRS_EXIT_ON_FAILURE"

    # P1-5 风控
    RISK_HARD_GATES_ENABLED: Final[str] = "RISK_HARD_GATES_ENABLED"
    # 缺快照/历史 NAV/波动估计时默认 fail-open；true 时对已启用的对应规则改 fail-closed（见 risk_engine.evaluate_*）
    RISK_GATES_STRICT_MODE: Final[str] = "RISK_GATES_STRICT_MODE"
    RISK_STOCK_STATUS_FAIL_CLOSE: Final[str] = "RISK_STOCK_STATUS_FAIL_CLOSE"
    RISK_STOCK_STATUS_UNCERTAIN_CODES: Final[str] = "RISK_STOCK_STATUS_UNCERTAIN_CODES"
    RISK_MAX_SINGLE_NAME_WEIGHT: Final[str] = "RISK_MAX_SINGLE_NAME_WEIGHT"
    RISK_MIN_CASH_BUFFER: Final[str] = "RISK_MIN_CASH_BUFFER"
    RISK_STOCK_BLACKLIST: Final[str] = "RISK_STOCK_BLACKLIST"
    RISK_STOP_LOSS_PCT: Final[str] = "RISK_STOP_LOSS_PCT"
    RISK_FREEZE_TTL_SEC: Final[str] = "RISK_FREEZE_TTL_SEC"
    RISK_MAX_GROSS_POSITION_PCT: Final[str] = "RISK_MAX_GROSS_POSITION_PCT"
    RISK_MIN_CASH_RATIO: Final[str] = "RISK_MIN_CASH_RATIO"
    RISK_INDUSTRY_MAP_PATH: Final[str] = "RISK_INDUSTRY_MAP_PATH"
    RISK_MAX_INDUSTRY_WEIGHT: Final[str] = "RISK_MAX_INDUSTRY_WEIGHT"
    RISK_MAX_DAILY_LOSS_PCT: Final[str] = "RISK_MAX_DAILY_LOSS_PCT"
    # 相对历史峰值权益的最大回撤比例阈值（0 关闭）；供组合级闸扩展，纯函数见 risk_engine.max_drawdown_vs_peak_check
    RISK_MAX_DRAWDOWN_PCT: Final[str] = "RISK_MAX_DRAWDOWN_PCT"
    # 回撤峰值窗口（自然日，0=全历史 MAX）；与 portfolio_snapshots 的 trading_date 比较
    RISK_ROLLING_DRAWDOWN_DAYS: Final[str] = "RISK_ROLLING_DRAWDOWN_DAYS"
    # 名单文件：与 RISK_STOCK_BLACKLIST env 合并；mtime 或轮询刷新
    RISK_STOCK_BLACKLIST_PATH: Final[str] = "RISK_STOCK_BLACKLIST_PATH"
    RISK_STOCK_WHITELIST_PATH: Final[str] = "RISK_STOCK_WHITELIST_PATH"
    RISK_DYNAMIC_LIST_POLL_SEC: Final[str] = "RISK_DYNAMIC_LIST_POLL_SEC"
    # P2 pretrade guard switches
    RISK_PRETRADE_GUARD_ENABLED: Final[str] = "RISK_PRETRADE_GUARD_ENABLED"
    RISK_PRETRADE_GUARD_STRICT_MODE: Final[str] = "RISK_PRETRADE_GUARD_STRICT_MODE"
    RISK_PRETRADE_GUARD_ENABLE_SUSPEND_BLOCK: Final[str] = "RISK_PRETRADE_GUARD_ENABLE_SUSPEND_BLOCK"
    RISK_PRETRADE_GUARD_ENABLE_ST_BUY_BLOCK: Final[str] = "RISK_PRETRADE_GUARD_ENABLE_ST_BUY_BLOCK"
    RISK_PRETRADE_GUARD_ST_FAIL_CLOSED: Final[str] = "RISK_PRETRADE_GUARD_ST_FAIL_CLOSED"
    RISK_PRETRADE_GUARD_ENABLE_BLACKLIST_BLOCK: Final[str] = "RISK_PRETRADE_GUARD_ENABLE_BLACKLIST_BLOCK"
    RISK_PRETRADE_GUARD_ENABLE_WHITELIST_BUY_ONLY: Final[str] = "RISK_PRETRADE_GUARD_ENABLE_WHITELIST_BUY_ONLY"
    RISK_PRETRADE_GUARD_AUDIT_ENABLED: Final[str] = "RISK_PRETRADE_GUARD_AUDIT_ENABLED"
    RISK_PRETRADE_GUARD_METRICS_ENABLED: Final[str] = "RISK_PRETRADE_GUARD_METRICS_ENABLED"
    # True：从 portfolio 加载 risk_config 快照的传输层失败（超时/异常）时 pretrade 一律拒单；默认 false（与无活动版本时回退 env 并存）
    RISK_PRETRADE_DB_SNAPSHOT_STRICT: Final[str] = "RISK_PRETRADE_DB_SNAPSHOT_STRICT"
    PRETRADE_MARKET_DATA_CACHE_TTL_SEC: Final[str] = "PRETRADE_MARKET_DATA_CACHE_TTL_SEC"
    PRETRADE_COLD_START_BATCH_WARMUP_ENABLED: Final[str] = "PRETRADE_COLD_START_BATCH_WARMUP_ENABLED"
    PRETRADE_BUILD_DAILY_ST_SET: Final[str] = "PRETRADE_BUILD_DAILY_ST_SET"
    # 组合级动态指标（portfolio_snapshots 序列）
    RISK_ROLLING_LOSS_TRADING_DAYS: Final[str] = "RISK_ROLLING_LOSS_TRADING_DAYS"
    RISK_MAX_ROLLING_LOSS_PCT: Final[str] = "RISK_MAX_ROLLING_LOSS_PCT"
    RISK_INTRAWINDOW_MDD_TRADING_DAYS: Final[str] = "RISK_INTRAWINDOW_MDD_TRADING_DAYS"
    RISK_MAX_INTRAWINDOW_MDD_PCT: Final[str] = "RISK_MAX_INTRAWINDOW_MDD_PCT"
    RISK_NAV_VOL_LOOKBACK_TRADING_DAYS: Final[str] = "RISK_NAV_VOL_LOOKBACK_TRADING_DAYS"
    RISK_MAX_PORTFOLIO_VOL_ANNUAL: Final[str] = "RISK_MAX_PORTFOLIO_VOL_ANNUAL"
    RISK_VAR_Z: Final[str] = "RISK_VAR_Z"
    RISK_MAX_VAR_PCT_OF_NAV: Final[str] = "RISK_MAX_VAR_PCT_OF_NAV"
    # 组合杠杆率（NAV/下单后可用现金）上界，>=1 生效；0=关闭；见 risk_engine.nav_to_available_cash_leverage_buy_check
    RISK_MAX_LEVERAGE_RATIO: Final[str] = "RISK_MAX_LEVERAGE_RATIO"
    RISK_DEBUG_CASH_BOOK_EPSILON: Final[str] = "RISK_DEBUG_CASH_BOOK_EPSILON"
    # P2 runtime fuse (Redis + order_ops)
    RISK_RUNTIME_FUSE_ENABLED: Final[str] = "RISK_RUNTIME_FUSE_ENABLED"
    RISK_FUSE_ON_BROKER_TRIP_ENABLED: Final[str] = "RISK_FUSE_ON_BROKER_TRIP_ENABLED"
    RISK_FUSE_ON_BROKER_TRIP_CODES: Final[str] = "RISK_FUSE_ON_BROKER_TRIP_CODES"
    RISK_FUSE_ON_BROKER_TRIP_TARGET_MODE: Final[str] = "RISK_FUSE_ON_BROKER_TRIP_TARGET_MODE"
    RISK_FUSE_AUTO_CANCEL_OPEN_ON_TRIP: Final[str] = "RISK_FUSE_AUTO_CANCEL_OPEN_ON_TRIP"
    RISK_RUNTIME_FUSE_REDIS_TTL_SEC: Final[str] = "RISK_RUNTIME_FUSE_REDIS_TTL_SEC"
    RISK_RUNTIME_BRIDGE_PAUSE_ENABLED: Final[str] = "RISK_RUNTIME_BRIDGE_PAUSE_ENABLED"
    # open（默认，读失败视为 normal）| halt（读失败视为 halt）| last_known（读失败沿用进程内最近一次成功快照）
    RISK_RUNTIME_FUSE_READ_FAILURE_MODE: Final[str] = "RISK_RUNTIME_FUSE_READ_FAILURE_MODE"
    # 当 RISK_RUNTIME_FUSE_READ_FAILURE_MODE=last_known 时，本地快照允许的最大年龄（秒）；超时后按 fail-closed 处理。
    RISK_RUNTIME_LAST_KNOWN_MAX_AGE_SEC: Final[str] = "RISK_RUNTIME_LAST_KNOWN_MAX_AGE_SEC"
    # Redis 不可用时 Bridge 熔断策略：fail_closed（默认）| last_known（本地缓存）| open（仅调试）
    RISK_RUNTIME_BRIDGE_REDIS_DOWN_POLICY: Final[str] = "RISK_RUNTIME_BRIDGE_REDIS_DOWN_POLICY"
    # CSV(pool_sqlite) 生产契约：仅在演练白名单时允许 redis down -> open
    RISK_RUNTIME_BRIDGE_ALLOW_FAIL_OPEN_FOR_DRILL: Final[str] = "RISK_RUNTIME_BRIDGE_ALLOW_FAIL_OPEN_FOR_DRILL"
    # bulk cancel 分页（每页最大 2000，与 OrderManager.list_orders 上限一致）
    RISK_RUNTIME_BULK_CANCEL_PAGE_SIZE: Final[str] = "RISK_RUNTIME_BULK_CANCEL_PAGE_SIZE"

    # Redis Stream（strategy_config）
    ENABLE_REDIS_STREAM: Final[str] = "ENABLE_REDIS_STREAM"
    REDIS_URL: Final[str] = "REDIS_URL"
    REDIS_STREAM_NAME: Final[str] = "REDIS_STREAM_NAME"
    REDIS_CONSUMER_GROUP: Final[str] = "REDIS_CONSUMER_GROUP"
    REDIS_CONSUMER_NAME: Final[str] = "REDIS_CONSUMER_NAME"
    REDIS_STREAM_MAXLEN: Final[str] = "REDIS_STREAM_MAXLEN"
    ACK_TIMEOUT_SEC: Final[str] = "ACK_TIMEOUT_SEC"
    REDIS_ACK_TIMEOUT_SEC: Final[str] = "REDIS_ACK_TIMEOUT_SEC"
    # 阻塞读毫秒：canonical BLOCK_TIME_MS；REDIS_BLOCK_MS 为历史别名（与 RedisConstants 对齐）
    BLOCK_TIME_MS: Final[str] = "BLOCK_TIME_MS"
    REDIS_FALLBACK_ENABLED: Final[str] = "REDIS_FALLBACK_ENABLED"
    MAX_REDELIVERY_COUNT: Final[str] = "MAX_REDELIVERY_COUNT"
    # execution_log 处于 in-progress 且无 broker order_id 时，超过该秒数进入 DLQ 隔离并 ACK（避免PEL长期卡死）
    EXECUTOR_DIRTY_INPROGRESS_GRACE_SEC: Final[str] = "EXECUTOR_DIRTY_INPROGRESS_GRACE_SEC"
    # FIX_PRICE（默认）| MARKET_SEMANTICS（仅BUY，按 BUY_ROUTINE 语义解析）
    EXECUTOR_BUY_PRICE_MODE: Final[str] = "EXECUTOR_BUY_PRICE_MODE"
    FALLBACK_RETRY_BACKOFF_BASE_SEC: Final[str] = "FALLBACK_RETRY_BACKOFF_BASE_SEC"
    FALLBACK_RETRY_BACKOFF_MAX_SEC: Final[str] = "FALLBACK_RETRY_BACKOFF_MAX_SEC"
    FALLBACK_RETRY_BACKOFF_JITTER_PCT: Final[str] = "FALLBACK_RETRY_BACKOFF_JITTER_PCT"
    FALLBACK_REPLAY_INTERVAL_DEFAULT_SEC: Final[str] = "FALLBACK_REPLAY_INTERVAL_DEFAULT_SEC"
    FALLBACK_REPLAY_INTERVAL_SEC: Final[str] = "FALLBACK_REPLAY_INTERVAL_SEC"
    # wait->reconcile delayed review windows (by retry_count) before marking non-retryable
    QMT_RECONCILE_NOT_FOUND_NON_RETRY_MIN_RETRY: Final[str] = "QMT_RECONCILE_NOT_FOUND_NON_RETRY_MIN_RETRY"
    QMT_RECONCILE_CANCEL_FAILED_NON_RETRY_MIN_RETRY: Final[str] = "QMT_RECONCILE_CANCEL_FAILED_NON_RETRY_MIN_RETRY"
    # broker snapshot query连续失败多少次后标记为non_retryable（防止snapshot持续失败导致重复下单）
    QMT_RECONCILE_SNAPSHOT_FAIL_MAX_RETRY: Final[str] = "QMT_RECONCILE_SNAPSHOT_FAIL_MAX_RETRY"
    # R2 fix: 当为true时，broker snapshot查询失败直接标记为non_retryable，不检查retry_count
    QMT_RECONCILE_SNAPSHOT_FAIL_ANY_BLOCKS_RETRY: Final[str] = "QMT_RECONCILE_SNAPSHOT_FAIL_ANY_BLOCKS_RETRY"
    # CSV模式下ROUTINE_DAILY_CAP的默认值（元），可覆盖硬编码的100万
    CSV_ROUTINE_CAP_DEFAULT_YUAN: Final[str] = "CSV_ROUTINE_CAP_DEFAULT_YUAN"
    REDIS_XREADGROUP_BLOCK_MS: Final[str] = "REDIS_XREADGROUP_BLOCK_MS"
    REDIS_CONNECT_TIMEOUT_SEC: Final[str] = "REDIS_CONNECT_TIMEOUT_SEC"
    REDIS_SOCKET_TIMEOUT_SEC: Final[str] = "REDIS_SOCKET_TIMEOUT_SEC"
    REDIS_HEALTH_CHECK_INTERVAL_SEC: Final[str] = "REDIS_HEALTH_CHECK_INTERVAL_SEC"
    REDIS_MAX_CONNECTIONS: Final[str] = "REDIS_MAX_CONNECTIONS"
    REDIS_RETRY_ON_TIMEOUT: Final[str] = "REDIS_RETRY_ON_TIMEOUT"
    REDIS_LIVE_SECURITY_STRICT: Final[str] = "REDIS_LIVE_SECURITY_STRICT"
    REDIS_INFO_SAMPLE_INTERVAL_SEC: Final[str] = "REDIS_INFO_SAMPLE_INTERVAL_SEC"
    FALLBACK_REPLAY_BATCH_SIZE: Final[str] = "FALLBACK_REPLAY_BATCH_SIZE"
    FALLBACK_REPLAY_MAX_BATCHES_PER_RUN: Final[str] = "FALLBACK_REPLAY_MAX_BATCHES_PER_RUN"
    BRIDGE_DEDUP_WINDOW_SEC: Final[str] = "BRIDGE_DEDUP_WINDOW_SEC"
    BRIDGE_DEDUP_PERSIST_FAILED_1H_P1: Final[str] = "BRIDGE_DEDUP_PERSIST_FAILED_1H_P1"
    BRIDGE_ORPHAN_RECONCILE_ON_STARTUP: Final[str] = "BRIDGE_ORPHAN_RECONCILE_ON_STARTUP"
    BRIDGE_ORPHAN_RECONCILE_INTERVAL_SEC: Final[str] = "BRIDGE_ORPHAN_RECONCILE_INTERVAL_SEC"
    BRIDGE_ORPHAN_PENDING_DISPATCH_MIN_AGE_SEC: Final[str] = "BRIDGE_ORPHAN_PENDING_DISPATCH_MIN_AGE_SEC"
    DISPATCH_OUTBOX_PRIMARY: Final[str] = "DISPATCH_OUTBOX_PRIMARY"
    DISPATCH_OUTBOX_PRIMARY_LEGACY_FALLBACK: Final[str] = "DISPATCH_OUTBOX_PRIMARY_LEGACY_FALLBACK"
    QMT_DEDICATED_THREAD_ENABLED: Final[str] = "QMT_DEDICATED_THREAD_ENABLED"

    # Mock QMT（common/integrations/qmt_client_mock.py）
    MOCK_QMT_ENABLED: Final[str] = "MOCK_QMT_ENABLED"
    MOCK_QMT_BROKER_SYNC_COUNT: Final[str] = "MOCK_QMT_BROKER_SYNC_COUNT"
    MOCK_QMT_FILL_DELAY_QUERIES: Final[str] = "MOCK_QMT_FILL_DELAY_QUERIES"
    MOCK_QMT_PARTIAL_FILL_RATIO: Final[str] = "MOCK_QMT_PARTIAL_FILL_RATIO"
    MOCK_QMT_CALLBACK_BEFORE_POLL: Final[str] = "MOCK_QMT_CALLBACK_BEFORE_POLL"
    MOCK_QMT_CALLBACK_DELAY_MS: Final[str] = "MOCK_QMT_CALLBACK_DELAY_MS"
    MOCK_QMT_CALLBACK_DROP_RATE: Final[str] = "MOCK_QMT_CALLBACK_DROP_RATE"
    MOCK_QMT_CALLBACK_DROP_MODE: Final[str] = "MOCK_QMT_CALLBACK_DROP_MODE"
    MOCK_QMT_CALLBACK_DROP_BURST_LEN: Final[str] = "MOCK_QMT_CALLBACK_DROP_BURST_LEN"
    MOCK_QMT_CALLBACK_LOSS_MODEL_DB: Final[str] = "MOCK_QMT_CALLBACK_LOSS_MODEL_DB"  # DuckDB load-aware model
    MOCK_QMT_BROKER_REJECT_FIXTURE: Final[str] = "MOCK_QMT_BROKER_REJECT_FIXTURE"
    MOCK_QMT_REJECT_BUY_INSUFFICIENT_CASH: Final[str] = "MOCK_QMT_REJECT_BUY_INSUFFICIENT_CASH"
    MOCK_QMT_REJECT_SELL_NO_POSITION: Final[str] = "MOCK_QMT_REJECT_SELL_NO_POSITION"
    MOCK_QMT_REJECT_DUPLICATE_ORDER: Final[str] = "MOCK_QMT_REJECT_DUPLICATE_ORDER"
    MOCK_QMT_REJECT_LIMIT_PRICE: Final[str] = "MOCK_QMT_REJECT_LIMIT_PRICE"
    MOCK_QMT_LIMIT_UP: Final[str] = "MOCK_QMT_LIMIT_UP"
    MOCK_QMT_LIMIT_DOWN: Final[str] = "MOCK_QMT_LIMIT_DOWN"
    MOCK_QMT_T_PLUS_1: Final[str] = "MOCK_QMT_T_PLUS_1"
    MOCK_QMT_INITIAL_CASH: Final[str] = "MOCK_QMT_INITIAL_CASH"
    MOCK_QMT_HISTORY_CSV_PATH: Final[str] = "MOCK_QMT_HISTORY_CSV_PATH"
    MOCK_QMT_HISTORY_RELOAD_EVERY_CALL: Final[str] = "MOCK_QMT_HISTORY_RELOAD_EVERY_CALL"
    MOCK_QMT_HISTORY_SYMBOLS: Final[str] = "MOCK_QMT_HISTORY_SYMBOLS"
    MOCK_QMT_HISTORY_PERIOD: Final[str] = "MOCK_QMT_HISTORY_PERIOD"
    MOCK_QMT_HISTORY_START: Final[str] = "MOCK_QMT_HISTORY_START"
    MOCK_QMT_HISTORY_END: Final[str] = "MOCK_QMT_HISTORY_END"
    MOCK_QMT_HISTORY_MODE: Final[str] = "MOCK_QMT_HISTORY_MODE"
    MOCK_QMT_INJECT_TIMEOUT_ENABLED: Final[str] = "MOCK_QMT_INJECT_TIMEOUT_ENABLED"
    MOCK_QMT_INJECT_DISCONNECT: Final[str] = "MOCK_QMT_INJECT_DISCONNECT"
    MOCK_QMT_ENFORCE_CONNECTION_BUDGET: Final[str] = "MOCK_QMT_ENFORCE_CONNECTION_BUDGET"  # default true: semaphore(2) per account
    MOCK_XTDATA_LATENCY_MS: Final[str] = "MOCK_XTDATA_LATENCY_MS"
    # Matching engine + fees (Phase A)
    MOCK_QMT_MATCHING_ENABLED: Final[str] = "MOCK_QMT_MATCHING_ENABLED"
    MOCK_QMT_MATCHING_SLIPPAGE_PCT: Final[str] = "MOCK_QMT_MATCHING_SLIPPAGE_PCT"
    MOCK_QMT_MATCHING_PARTICIPATION_RATE: Final[str] = "MOCK_QMT_MATCHING_PARTICIPATION_RATE"
    MOCK_QMT_MATCHING_PRICE_CAGE_ENABLED: Final[str] = "MOCK_QMT_MATCHING_PRICE_CAGE_ENABLED"
    MOCK_QMT_MATCHING_MIN_FILL_VOLUME: Final[str] = "MOCK_QMT_MATCHING_MIN_FILL_VOLUME"
    MOCK_QMT_PRICE_CAGE_STRICT: Final[str] = "MOCK_QMT_PRICE_CAGE_STRICT"
    MOCK_QMT_MARKET_AS_COUNTERPARTY: Final[str] = "MOCK_QMT_MARKET_AS_COUNTERPARTY"
    MOCK_QMT_FEES_ENABLED: Final[str] = "MOCK_QMT_FEES_ENABLED"
    MOCK_QMT_COMMISSION_RATE: Final[str] = "MOCK_QMT_COMMISSION_RATE"
    MOCK_QMT_STAMP_TAX_RATE: Final[str] = "MOCK_QMT_STAMP_TAX_RATE"
    MOCK_QMT_TRANSFER_FEE_RATE: Final[str] = "MOCK_QMT_TRANSFER_FEE_RATE"

    # QMT 健康（strategy_config 与 HealthScoringConstants 共用键名）
    QMT_HEALTH_THRESHOLD: Final[str] = "QMT_HEALTH_THRESHOLD"
    QMT_HEALTH_CHECK_INTERVAL_SEC: Final[str] = "QMT_HEALTH_CHECK_INTERVAL_SEC"
    QMT_LATENCY_P99_THRESHOLD: Final[str] = "QMT_LATENCY_P99_THRESHOLD"
    QMT_PROACTIVE_RECONNECT: Final[str] = "QMT_PROACTIVE_RECONNECT"

    # SQLite 路径与模式
    AUDIT_DB_PATH: Final[str] = "AUDIT_DB_PATH"
    EXEC_DB_PATH: Final[str] = "EXEC_DB_PATH"
    FALLBACK_QUEUE_PATH: Final[str] = "FALLBACK_QUEUE_PATH"
    PORTFOLIO_DB_PATH: Final[str] = "PORTFOLIO_DB_PATH"
    PORTFOLIO_BYPASS_EVIDENCE_FAILURE_POLICY: Final[str] = "PORTFOLIO_BYPASS_EVIDENCE_FAILURE_POLICY"
    PORTFOLIO_SQLITE_TX_WARN_MS: Final[str] = "PORTFOLIO_SQLITE_TX_WARN_MS"
    OSKH_SQL_TX_PROFILE: Final[str] = "OSKH_SQL_TX_PROFILE"
    OSKH_SELL_METRICS_PRECOMPUTE_CALENDAR: Final[str] = "OSKH_SELL_METRICS_PRECOMPUTE_CALENDAR"
    OSKH_TRADE_CALENDAR_XSHG_CACHE: Final[str] = "OSKH_TRADE_CALENDAR_XSHG_CACHE"
    OSKH_QUOTE_SNAPSHOT_ENABLED: Final[str] = "OSKH_QUOTE_SNAPSHOT_ENABLED"
    STRATEGY_DB: Final[str] = "STRATEGY_DB"
    STRATEGY_DB_PATH: Final[str] = "STRATEGY_DB_PATH"
    SQLITE_WAL_MODE: Final[str] = "SQLITE_WAL_MODE"

    # 交易日历：异常时 fail_close=保守视为非交易日；fail_open=与旧行为一致视为交易日
    TRADE_DAY_ON_CALENDAR_ERROR: Final[str] = "TRADE_DAY_ON_CALENDAR_ERROR"
    # 月度再平衡日用 hx.get_trade_days 失败时：fail_close=不触发再平衡日；fail_open=视为再平衡日（与 TRADE_DAY 键语义对齐）
    REBALANCE_DAY_ON_CALENDAR_ERROR: Final[str] = "REBALANCE_DAY_ON_CALENDAR_ERROR"
    # CI/import-smoke：跳过 live_trading 对 xtquant / hkcodex 的启动强校验
    SKIP_TRADING_RUNTIME_DEPS_CHECK: Final[str] = "SKIP_TRADING_RUNTIME_DEPS_CHECK"
    SKIP_EXECUTION_TOPOLOGY_CHECK: Final[str] = "SKIP_EXECUTION_TOPOLOGY_CHECK"
    # break-glass：仅在紧急情况下允许 live 环境启用 SKIP_*（默认关闭，生产建议固定为 0/未设置）
    ALLOW_SKIP_CHECKS_IN_LIVE: Final[str] = "ALLOW_SKIP_CHECKS_IN_LIVE"
    TRADING_EXECUTION_MODE: Final[str] = "TRADING_EXECUTION_MODE"
    # trading live 固定 executor-only（语义等价 historical ``none``）。遗留 ``full`` 在 strategy_config 加载时归一为 none。
    TRADING_QMT_ATTACHMENT: Final[str] = "TRADING_QMT_ATTACHMENT"
    # 逗号分隔 YYYY-MM-DD，与纯决策本地交易日历对齐（上交所风格：周末休 + 列表节假日）
    TRADING_DECISION_CALENDAR_HOLIDAYS: Final[str] = "TRADING_DECISION_CALENDAR_HOLIDAYS"
    # ``local`` (default): weekend + TRADING_DECISION_CALENDAR_HOLIDAYS.
    # ``executor_xtdata``: TRADE_CALENDAR_RANGE qmt_op + Redis cache (official exchange calendar via executor).
    TRADING_DECISION_CALENDAR_SOURCE: Final[str] = "TRADING_DECISION_CALENDAR_SOURCE"
    TRADING_DECISION_CALENDAR_CACHE_TTL_SEC: Final[str] = "TRADING_DECISION_CALENDAR_CACHE_TTL_SEC"
    # 纯决策下 REQUIRE_QMT_MARKET_SUBSCRIPTION 探活用的单标的（FULL_TICK）
    TRADING_DECISION_MD_PROBE_SYMBOL: Final[str] = "TRADING_DECISION_MD_PROBE_SYMBOL"
    # 决策侧行情/日历经 Redis qmt_ops 的数据平面：auto（默认）| redis_qmt_ops | disabled
    TRADING_MARKET_DATA_PLANE: Final[str] = "TRADING_MARKET_DATA_PLANE"
    # Trading 进程：禁止构造真实 ``xtquant.xttrader.XtQuantTrader``（应急设 0/false/off）
    TRADING_FORBID_XTQUANT_TRADER_CONSTRUCT: Final[str] = "TRADING_FORBID_XTQUANT_TRADER_CONSTRUCT"
    # Live：为 true 时，若 ``peek_decision_market_intent_snapshot`` 为 L3_no_decision_plane 则桥接拒发 Stream 意图
    TRADING_FAIL_CLOSE_INTENT_ON_DECISION_MD_L3: Final[str] = "TRADING_FAIL_CLOSE_INTENT_ON_DECISION_MD_L3"
    # Live：连续 ``qmt_ops`` Redis TIMEOUT 达到该次数（>=2 有意义）则拒发意图；0 或未设关闭（见 ``qmt_market_ops_client_sync`` streak）
    TRADING_FAIL_CLOSE_QMT_OPS_TIMEOUT_STREAK: Final[str] = "TRADING_FAIL_CLOSE_QMT_OPS_TIMEOUT_STREAK"
    # Live：L1 tick 缓存命中且 ``decision_md_staleness_ms`` >= 该阈值时拒发意图（0=关闭）；与 ``TRADING_ALLOW_INTENT_ON_STALE_L1_WITH_AUDIT`` 并存时 fail-close 优先
    TRADING_FAIL_CLOSE_INTENT_ON_STALE_L1: Final[str] = "TRADING_FAIL_CLOSE_INTENT_ON_STALE_L1"
    # Live：与上项同阈语义；为 true 时允许在 stale L1 下仍发单并带 ``decision_md_degraded`` / ``decision_md_fail_open_reason``（fail-close 未触发时）
    TRADING_ALLOW_INTENT_ON_STALE_L1_WITH_AUDIT: Final[str] = "TRADING_ALLOW_INTENT_ON_STALE_L1_WITH_AUDIT"
    # 决策进程 ``qmt_ops`` 等待秒数；0 或未设则回退 ``MONITOR_QMT_OPS_TIMEOUT_SEC``
    TRADING_DECISION_QMT_OPS_TIMEOUT_SEC: Final[str] = "TRADING_DECISION_QMT_OPS_TIMEOUT_SEC"
    # L1：Redis 只读 tick 缓存（executor 写、trading 读）；0/false/off=关闭
    TRADING_DECISION_TICK_CACHE_ENABLED: Final[str] = "TRADING_DECISION_TICK_CACHE_ENABLED"
    TRADING_DECISION_TICK_CACHE_TTL_SEC: Final[str] = "TRADING_DECISION_TICK_CACHE_TTL_SEC"
    TRADING_DECISION_TICK_CACHE_KEY_PREFIX: Final[str] = "TRADING_DECISION_TICK_CACHE_KEY_PREFIX"
    TRADING_DECISION_TICK_CACHE_MAX_JSON_BYTES: Final[str] = "TRADING_DECISION_TICK_CACHE_MAX_JSON_BYTES"
    # stale 判定毫秒（用于 fail-close / fail-open 与 ``decision_md_staleness_ms`` 对照）；0=不标 stale（仅记录 age）
    TRADING_DECISION_TICK_CACHE_STALE_GATE_MS: Final[str] = "TRADING_DECISION_TICK_CACHE_STALE_GATE_MS"
    TRADING_DECISION_LIMIT_INFO_CACHE_ENABLED: Final[str] = "TRADING_DECISION_LIMIT_INFO_CACHE_ENABLED"
    TRADING_DECISION_LIMIT_INFO_CACHE_TTL_SEC: Final[str] = "TRADING_DECISION_LIMIT_INFO_CACHE_TTL_SEC"
    LIMIT_INFO_PREV_CLOSE_SOURCE: Final[str] = "LIMIT_INFO_PREV_CLOSE_SOURCE"

    # 对账与输出路径
    RECONCILE_TIME: Final[str] = "RECONCILE_TIME"
    MAX_PENDING_HOURS: Final[str] = "MAX_PENDING_HOURS"
    RECONCILE_CASH_THRESHOLD: Final[str] = "RECONCILE_CASH_THRESHOLD"
    RECONCILE_AUTO_FIX: Final[str] = "RECONCILE_AUTO_FIX"
    EOD_RECONCILE_PERSIST_ENABLED: Final[str] = "EOD_RECONCILE_PERSIST_ENABLED"
    EOD_RECONCILE_RETURN_FALSE_ON_ANOMALIES: Final[str] = "EOD_RECONCILE_RETURN_FALSE_ON_ANOMALIES"
    EOD_RECONCILE_ALERT_ENABLED: Final[str] = "EOD_RECONCILE_ALERT_ENABLED"
    EOD_RECONCILE_ALERT_P2_ON_SUCCESS: Final[str] = "EOD_RECONCILE_ALERT_P2_ON_SUCCESS"
    EOD_RECONCILE_ANOMALY_P0_THRESHOLD: Final[str] = "EOD_RECONCILE_ANOMALY_P0_THRESHOLD"
    SELECTION_DIR: Final[str] = "SELECTION_DIR"
    PORTFOLIO_RECORD_FILE: Final[str] = "PORTFOLIO_RECORD_FILE"
    TRADE_RECORD_FILE: Final[str] = "TRADE_RECORD_FILE"
    RECONCILE_OUTPUT_DIR: Final[str] = "RECONCILE_OUTPUT_DIR"
    EOD_RECONCILE_FETCH_BROKER_POSITIONS: Final[str] = "EOD_RECONCILE_FETCH_BROKER_POSITIONS"
    EOD_RECONCILE_ENABLE_BROKER_CASHFLOW_RECONCILE: Final[str] = "EOD_RECONCILE_ENABLE_BROKER_CASHFLOW_RECONCILE"
    EOD_RECONCILE_BROKER_STATEMENT_CSV_PATH: Final[str] = "EOD_RECONCILE_BROKER_STATEMENT_CSV_PATH"
    EOD_RECONCILE_BROKER_STATEMENT_TEMPLATE: Final[str] = "EOD_RECONCILE_BROKER_STATEMENT_TEMPLATE"
    EOD_RECONCILE_BROKER_STATEMENT_MAPPING_PATH: Final[str] = "EOD_RECONCILE_BROKER_STATEMENT_MAPPING_PATH"
    EOD_RECONCILE_BROKER_AMOUNT_PARSE_POLICY: Final[str] = "EOD_RECONCILE_BROKER_AMOUNT_PARSE_POLICY"
    EOD_RECONCILE_EXTERNAL_CASHFLOW_THRESHOLD: Final[str] = "EOD_RECONCILE_EXTERNAL_CASHFLOW_THRESHOLD"
    EOD_RECONCILE_CLI_EXIT_ON_LAYER25_CRITICAL: Final[str] = "EOD_RECONCILE_CLI_EXIT_ON_LAYER25_CRITICAL"
    EOD_RECONCILE_CLI_EXIT_ON_ANY_ANOMALY: Final[str] = "EOD_RECONCILE_CLI_EXIT_ON_ANY_ANOMALY"
    EOD_RECONCILE_CLI_EXIT_STATUSES: Final[str] = "EOD_RECONCILE_CLI_EXIT_STATUSES"
    EOD_RECONCILE_RUN_FILLS_SYNC: Final[str] = "EOD_RECONCILE_RUN_FILLS_SYNC"
    EOD_RECONCILE_RUN_ORPHAN_CALLBACK_SYNC: Final[str] = "EOD_RECONCILE_RUN_ORPHAN_CALLBACK_SYNC"
    # EOD snapshot fallback job master switch
    EOD_SNAPSHOT_FALLBACK_ENABLED: Final[str] = "EOD_SNAPSHOT_FALLBACK_ENABLED"
    # Market price source for fallback snapshot valuation:
    #   "auto"     = historical snapshot price first, avg_cost fallback (default)
    #   "avg_cost" = always use avg_cost (forces quality=cost_fallback; for debug/benchmark)
    EOD_SNAPSHOT_FALLBACK_MARKET_PRICE_SOURCE: Final[str] = "EOD_SNAPSHOT_FALLBACK_MARKET_PRICE_SOURCE"

    CASH_CHECK_INTERVAL_SEC: Final[str] = "CASH_CHECK_INTERVAL_SEC"
    PENDING_ALERT_THRESHOLD: Final[str] = "PENDING_ALERT_THRESHOLD"
    DLQ_ALERT_THRESHOLD: Final[str] = "DLQ_ALERT_THRESHOLD"
    LATENCY_ALERT_THRESHOLD: Final[str] = "LATENCY_ALERT_THRESHOLD"
    BROKER_EXEC_LATENCY_P99_WARN_MS: Final[str] = "BROKER_EXEC_LATENCY_P99_WARN_MS"
    BROKER_EXEC_LATENCY_P99_P1_MS: Final[str] = "BROKER_EXEC_LATENCY_P99_P1_MS"
    FALLBACK_QUEUE_DEPTH_WARN: Final[str] = "FALLBACK_QUEUE_DEPTH_WARN"
    FALLBACK_QUEUE_DEPTH_P1: Final[str] = "FALLBACK_QUEUE_DEPTH_P1"
    FALLBACK_DUE_LAG_SEC_WARN: Final[str] = "FALLBACK_DUE_LAG_SEC_WARN"
    FALLBACK_SENT_NOT_DELETED_WARN: Final[str] = "FALLBACK_SENT_NOT_DELETED_WARN"
    FALLBACK_SENT_NOT_DELETED_OVERDUE_P1: Final[str] = "FALLBACK_SENT_NOT_DELETED_OVERDUE_P1"
    DLQ_NEW_1H_P1_THRESHOLD: Final[str] = "DLQ_NEW_1H_P1_THRESHOLD"
    PENDING_ALERT_P0_MULTIPLIER: Final[str] = "PENDING_ALERT_P0_MULTIPLIER"
    REDIS_GROUP_LAG_WARN: Final[str] = "REDIS_GROUP_LAG_WARN"
    REDIS_GROUP_LAG_P1: Final[str] = "REDIS_GROUP_LAG_P1"
    RISK_RUNTIME_FUSE_EVENTS_1H_WARN: Final[str] = "RISK_RUNTIME_FUSE_EVENTS_1H_WARN"
    RISK_RUNTIME_FUSE_EVENTS_1H_P1: Final[str] = "RISK_RUNTIME_FUSE_EVENTS_1H_P1"
    ORDER_OPS_FAIL_REJECT_WARN: Final[str] = "ORDER_OPS_FAIL_REJECT_WARN"
    ORDER_OPS_FAIL_REJECT_P1: Final[str] = "ORDER_OPS_FAIL_REJECT_P1"
    ORDER_OPS_FAIL_REJECT_RATIO_WARN: Final[str] = "ORDER_OPS_FAIL_REJECT_RATIO_WARN"
    ORDER_OPS_FAIL_REJECT_RATIO_MIN_SAMPLES: Final[str] = "ORDER_OPS_FAIL_REJECT_RATIO_MIN_SAMPLES"
    ORDER_OPS_CANCEL_FAILED_1H_WARN: Final[str] = "ORDER_OPS_CANCEL_FAILED_1H_WARN"
    ORDER_OPS_CANCEL_FAILED_1H_P1: Final[str] = "ORDER_OPS_CANCEL_FAILED_1H_P1"
    DIRTY_INPROGRESS_DLQ_1H_WARN: Final[str] = "DIRTY_INPROGRESS_DLQ_1H_WARN"
    DIRTY_INPROGRESS_DLQ_1H_P1: Final[str] = "DIRTY_INPROGRESS_DLQ_1H_P1"
    CSV_SELECTION_NOT_READY_1H_WARN: Final[str] = "CSV_SELECTION_NOT_READY_1H_WARN"
    CSV_SELECTION_NOT_READY_1H_P1: Final[str] = "CSV_SELECTION_NOT_READY_1H_P1"
    ROUTINE_CAP_HARD_TOTAL_UNFILLED_1H_WARN: Final[str] = "ROUTINE_CAP_HARD_TOTAL_UNFILLED_1H_WARN"
    ROUTINE_CAP_HARD_TOTAL_UNFILLED_1H_P1: Final[str] = "ROUTINE_CAP_HARD_TOTAL_UNFILLED_1H_P1"
    ROUTINE_CLOSE_TIMEOUT_GOVERNANCE_1H_WARN: Final[str] = "ROUTINE_CLOSE_TIMEOUT_GOVERNANCE_1H_WARN"
    ROUTINE_CLOSE_TIMEOUT_GOVERNANCE_1H_P1: Final[str] = "ROUTINE_CLOSE_TIMEOUT_GOVERNANCE_1H_P1"
    SELL_STOP_LOSS_TIMEOUT_ESCALATION_1H_WARN: Final[str] = "SELL_STOP_LOSS_TIMEOUT_ESCALATION_1H_WARN"
    SELL_STOP_LOSS_TIMEOUT_ESCALATION_1H_P1: Final[str] = "SELL_STOP_LOSS_TIMEOUT_ESCALATION_1H_P1"
    SELL_TAKE_PROFIT_TIMEOUT_RELAXED_1H_WARN: Final[str] = "SELL_TAKE_PROFIT_TIMEOUT_RELAXED_1H_WARN"
    SELL_TAKE_PROFIT_TIMEOUT_RELAXED_1H_P1: Final[str] = "SELL_TAKE_PROFIT_TIMEOUT_RELAXED_1H_P1"
    ORDER_UNKNOWN_STATUS_1H_WARN: Final[str] = "ORDER_UNKNOWN_STATUS_1H_WARN"
    ORDER_UNKNOWN_STATUS_1H_P1: Final[str] = "ORDER_UNKNOWN_STATUS_1H_P1"
    EXECUTION_SUBMITTED_STALE_WARN_SEC: Final[str] = "EXECUTION_SUBMITTED_STALE_WARN_SEC"
    EXECUTION_SUBMITTED_STALE_P1_SEC: Final[str] = "EXECUTION_SUBMITTED_STALE_P1_SEC"
    RECORDER_QUEUE_DEPTH_WARN: Final[str] = "RECORDER_QUEUE_DEPTH_WARN"
    RECORDER_QUEUE_DEPTH_P1: Final[str] = "RECORDER_QUEUE_DEPTH_P1"
    RECORDER_FLUSH_LAG_WARN_RECORDS: Final[str] = "RECORDER_FLUSH_LAG_WARN_RECORDS"
    RECORDER_FLUSH_LAG_P1_RECORDS: Final[str] = "RECORDER_FLUSH_LAG_P1_RECORDS"
    READONLY_SHARED_DB_ACTIVE_WARN: Final[str] = "READONLY_SHARED_DB_ACTIVE_WARN"
    READONLY_SHARED_DB_BUSY_EVENTS_P1: Final[str] = "READONLY_SHARED_DB_BUSY_EVENTS_P1"
    READONLY_SHARED_DB_DEGRADED_DWELL_P1_SEC: Final[str] = "READONLY_SHARED_DB_DEGRADED_DWELL_P1_SEC"
    STRATEGY_SWITCH_AUDIT_DEGRADED_1H_WARN: Final[str] = "STRATEGY_SWITCH_AUDIT_DEGRADED_1H_WARN"
    STRATEGY_SWITCH_AUDIT_DEGRADED_1H_P1: Final[str] = "STRATEGY_SWITCH_AUDIT_DEGRADED_1H_P1"
    MONITOR_GOVERNANCE_INTERVAL_SEC: Final[str] = "MONITOR_GOVERNANCE_INTERVAL_SEC"
    ORDER_OPS_MAX_PER_SEC: Final[str] = "ORDER_OPS_MAX_PER_SEC"
    ORDER_OPS_XAUTOCLAIM_MIN_IDLE_MS: Final[str] = "ORDER_OPS_XAUTOCLAIM_MIN_IDLE_MS"
    CALLBACK_FILL_XAUTOCLAIM_MIN_IDLE_MS: Final[str] = "CALLBACK_FILL_XAUTOCLAIM_MIN_IDLE_MS"
    EXECUTOR_FILL_CHECK_INTERVAL_SEC: Final[str] = "EXECUTOR_FILL_CHECK_INTERVAL_SEC"
    CRITICAL_EXECUTOR_MAX_WORKERS: Final[str] = "CRITICAL_EXECUTOR_MAX_WORKERS"
    READONLY_POOL_MAX_CONN: Final[str] = "READONLY_POOL_MAX_CONN"
    EXECUTOR_QMT_TIMEOUT_SEC: Final[str] = "EXECUTOR_QMT_TIMEOUT_SEC"
    EXECUTOR_ENABLE_BROKER_POLL_SYNC: Final[str] = "EXECUTOR_ENABLE_BROKER_POLL_SYNC"
    EXECUTOR_STARTUP_BROKER_POLL_ROUNDS: Final[str] = "EXECUTOR_STARTUP_BROKER_POLL_ROUNDS"
    BATCH_SETTLEMENT_PHASE1_ONLY: Final[str] = "BATCH_SETTLEMENT_PHASE1_ONLY"
    BATCH_SETTLEMENT_PHASE1_MAX_IN_FLIGHT: Final[str] = "BATCH_SETTLEMENT_PHASE1_MAX_IN_FLIGHT"
    BATCH_SETTLEMENT_PHASE1_MIN_ROWS: Final[str] = "BATCH_SETTLEMENT_PHASE1_MIN_ROWS"
    BATCH_SETTLEMENT_ENABLED: Final[str] = "BATCH_SETTLEMENT_ENABLED"
    BATCH_SETTLEMENT_SIZE_THRESHOLD: Final[str] = "BATCH_SETTLEMENT_SIZE_THRESHOLD"
    BATCH_SETTLEMENT_STOCK_THRESHOLD: Final[str] = "BATCH_SETTLEMENT_STOCK_THRESHOLD"
    CHECK_FILLS_DEFER_SNAPSHOT_REFRESH: Final[str] = "CHECK_FILLS_DEFER_SNAPSHOT_REFRESH"
    ENABLE_HOT_RELOAD: Final[str] = "ENABLE_HOT_RELOAD"
    RELOAD_CHECK_INTERVAL_SEC: Final[str] = "RELOAD_CHECK_INTERVAL_SEC"

    # 告警 Webhook（alerter.py）
    ALERT_SILENT_SEC: Final[str] = "ALERT_SILENT_SEC"
    ALERT_WEBHOOK_URL: Final[str] = "ALERT_WEBHOOK_URL"
    DINGTALK_WEBHOOK_URL: Final[str] = "DINGTALK_WEBHOOK_URL"
    WECOM_WEBHOOK_URL: Final[str] = "WECOM_WEBHOOK_URL"
    ALERT_WEBHOOK_URL_P0: Final[str] = "ALERT_WEBHOOK_URL_P0"
    ALERT_WEBHOOK_URL_P1: Final[str] = "ALERT_WEBHOOK_URL_P1"
    ALERT_WEBHOOK_URL_P2: Final[str] = "ALERT_WEBHOOK_URL_P2"
    DINGTALK_WEBHOOK_URL_P0: Final[str] = "DINGTALK_WEBHOOK_URL_P0"
    DINGTALK_WEBHOOK_URL_P1: Final[str] = "DINGTALK_WEBHOOK_URL_P1"
    DINGTALK_WEBHOOK_URL_P2: Final[str] = "DINGTALK_WEBHOOK_URL_P2"
    WECOM_WEBHOOK_URL_P0: Final[str] = "WECOM_WEBHOOK_URL_P0"
    WECOM_WEBHOOK_URL_P1: Final[str] = "WECOM_WEBHOOK_URL_P1"
    WECOM_WEBHOOK_URL_P2: Final[str] = "WECOM_WEBHOOK_URL_P2"
    WECOM_BOT_ENABLED: Final[str] = "WECOM_BOT_ENABLED"
    WECOM_MENTION_ALL_FOR_TIERS: Final[str] = "WECOM_MENTION_ALL_FOR_TIERS"
    # 企业微信应用消息（非群机器人）
    WECOM_APP_ENABLED: Final[str] = "WECOM_APP_ENABLED"
    WECOM_APP_CORP_ID: Final[str] = "WECOM_APP_CORP_ID"
    WECOM_APP_AGENT_ID: Final[str] = "WECOM_APP_AGENT_ID"
    WECOM_APP_SECRET: Final[str] = "WECOM_APP_SECRET"
    WECOM_APP_TOUSER: Final[str] = "WECOM_APP_TOUSER"
    WECOM_APP_TOPARTY: Final[str] = "WECOM_APP_TOPARTY"
    WECOM_APP_TOTAG: Final[str] = "WECOM_APP_TOTAG"
    WECOM_APP_TOUSER_P0: Final[str] = "WECOM_APP_TOUSER_P0"
    WECOM_APP_TOUSER_P1: Final[str] = "WECOM_APP_TOUSER_P1"
    WECOM_APP_TOUSER_P2: Final[str] = "WECOM_APP_TOUSER_P2"
    WECOM_APP_TOPARTY_P0: Final[str] = "WECOM_APP_TOPARTY_P0"
    WECOM_APP_TOPARTY_P1: Final[str] = "WECOM_APP_TOPARTY_P1"
    WECOM_APP_TOPARTY_P2: Final[str] = "WECOM_APP_TOPARTY_P2"
    WECOM_APP_TOTAG_P0: Final[str] = "WECOM_APP_TOTAG_P0"
    WECOM_APP_TOTAG_P1: Final[str] = "WECOM_APP_TOTAG_P1"
    WECOM_APP_TOTAG_P2: Final[str] = "WECOM_APP_TOTAG_P2"
    WECOM_APP_TOKEN_TTL_SEC: Final[str] = "WECOM_APP_TOKEN_TTL_SEC"
    WECOM_APP_TIMEOUT_SEC: Final[str] = "WECOM_APP_TIMEOUT_SEC"

    # 可选 SMTP（分级告警旁路；未配置 host 则不发送）
    ALERT_SMTP_HOST: Final[str] = "ALERT_SMTP_HOST"
    ALERT_SMTP_PORT: Final[str] = "ALERT_SMTP_PORT"
    ALERT_SMTP_USER: Final[str] = "ALERT_SMTP_USER"
    ALERT_SMTP_PASSWORD: Final[str] = "ALERT_SMTP_PASSWORD"
    ALERT_EMAIL_FROM: Final[str] = "ALERT_EMAIL_FROM"
    ALERT_EMAIL_TO: Final[str] = "ALERT_EMAIL_TO"
    ALERT_EMAIL_FOR_TIERS: Final[str] = "ALERT_EMAIL_FOR_TIERS"  # 如 P0,P1；空=全部 tier
    WECOM_P0_USE_TEXT_AT_ALL: Final[str] = "WECOM_P0_USE_TEXT_AT_ALL"
    ALERT_CACHE_MAX_KEYS: Final[str] = "ALERT_CACHE_MAX_KEYS"
    ALERT_CACHE_TTL_SEC: Final[str] = "ALERT_CACHE_TTL_SEC"
    ALERT_REDACT_ENABLED: Final[str] = "ALERT_REDACT_ENABLED"
    ALERT_REDACT_KEYWORDS: Final[str] = "ALERT_REDACT_KEYWORDS"
    # 告警外发：默认异步队列（1/true）；0/false 则同步调用 urllib，便于测试与调试
    ALERT_ASYNC_QUEUE: Final[str] = "ALERT_ASYNC_QUEUE"
    ALERT_QUEUE_MAX: Final[str] = "ALERT_QUEUE_MAX"

    # 调试 / 导入诊断
    QUANT_VERBOSE_IMPORT: Final[str] = "QUANT_VERBOSE_IMPORT"
    QUANT_DEBUG_LAZY_LOAD: Final[str] = "QUANT_DEBUG_LAZY_LOAD"

    # 编排实例标识（qmt_client session_id 等）
    INSTANCE_ID: Final[str] = "INSTANCE_ID"
    # Backward-compat alias used by legacy test/runtime checks (prefer INSTANCE_ID).
    QUANT_INSTANCE_ID: Final[str] = "QUANT_INSTANCE_ID"
    HOSTNAME: Final[str] = "HOSTNAME"
    DOCKER_CONTAINER_ID: Final[str] = "DOCKER_CONTAINER_ID"

    # TradingConstants 补充（原字面量键）
    TRADE_POLL_INTERVAL_SEC: Final[str] = "TRADE_POLL_INTERVAL_SEC"
    TRADE_POLL_INTERVAL_FAST_SEC: Final[str] = "TRADE_POLL_INTERVAL_FAST_SEC"
    TRADE_CASH_CHECK_INTERVAL_SEC: Final[str] = "TRADE_CASH_CHECK_INTERVAL_SEC"

    # RedisConstants 补充
    REDIS_AUDIT_BUFFER_MAX: Final[str] = "REDIS_AUDIT_BUFFER_MAX"
    REDIS_REPLAY_DELAY: Final[str] = "REDIS_REPLAY_DELAY"
    REDIS_PENDING_BATCH: Final[str] = "REDIS_PENDING_BATCH"
    REDIS_HEALTH_INTERVAL_SEC: Final[str] = "REDIS_HEALTH_INTERVAL_SEC"
    REDIS_MAX_REDELIVERY: Final[str] = "REDIS_MAX_REDELIVERY"
    REDIS_POOL_MAX: Final[str] = "REDIS_POOL_MAX"

    # PersistenceConstants 补充
    SQLITE_SYNC_MODE: Final[str] = "SQLITE_SYNC_MODE"
    DB_MAX_RETRIES: Final[str] = "DB_MAX_RETRIES"
    DB_RETRY_DELAY: Final[str] = "DB_RETRY_DELAY"
    PORTFOLIO_WRITE_RETRY: Final[str] = "PORTFOLIO_WRITE_RETRY"
    PORTFOLIO_RETRY_DELAY: Final[str] = "PORTFOLIO_RETRY_DELAY"
    HOT_DATA_RETENTION_DAYS: Final[str] = "HOT_DATA_RETENTION_DAYS"
    COLD_ARCHIVE_CHUNK_SIZE: Final[str] = "COLD_ARCHIVE_CHUNK_SIZE"

    # LoggingConstants 补充
    CONFIG_AUDIT_RETENTION: Final[str] = "CONFIG_AUDIT_RETENTION"
    COLD_RETENTION_YEARS: Final[str] = "COLD_RETENTION_YEARS"
    LOG_ROTATION_SIZE: Final[str] = "LOG_ROTATION_SIZE"
    RECONCILE_RETENTION: Final[str] = "RECONCILE_RETENTION"
    LOG_COMPRESSION: Final[str] = "LOG_COMPRESSION"
    MON_PENDING_THRESHOLD: Final[str] = "MON_PENDING_THRESHOLD"
    MON_DLQ_THRESHOLD: Final[str] = "MON_DLQ_THRESHOLD"
    MON_LATENCY_THRESHOLD: Final[str] = "MON_LATENCY_THRESHOLD"
    MON_HEALTH_HISTORY: Final[str] = "MON_HEALTH_HISTORY"
    MON_CASH_DRIFT_THRESHOLD: Final[str] = "MON_CASH_DRIFT_THRESHOLD"
    RECON_MAX_PENDING_HOURS: Final[str] = "RECON_MAX_PENDING_HOURS"

    # PerformanceConstants 补充
    PERF_SLOW_THRESHOLD: Final[str] = "PERF_SLOW_THRESHOLD"
    PERF_SLOW_API_THRESHOLD: Final[str] = "PERF_SLOW_API_THRESHOLD"
    PERF_LOAD_SAMPLE_SIZE: Final[str] = "PERF_LOAD_SAMPLE_SIZE"
    PERF_PRICE_SLOW_MS: Final[str] = "PERF_PRICE_SLOW_MS"
    PERF_HIGH_MS: Final[str] = "PERF_HIGH_MS"
    PERF_NORMAL_MS: Final[str] = "PERF_NORMAL_MS"
    PERF_LOW_MS: Final[str] = "PERF_LOW_MS"

    # StrategyConstants 补充
    STRATEGY_LOAD_RETRY: Final[str] = "STRATEGY_LOAD_RETRY"
    SELECTION_SAVE_RETRY: Final[str] = "SELECTION_SAVE_RETRY"
    STRATEGY_CACHE_TTL: Final[str] = "STRATEGY_CACHE_TTL"
    ETF_ROTATION_REG_NUM: Final[str] = "ETF_ROTATION_REG_NUM"
    ETF_MIN_REQUIRED: Final[str] = "ETF_MIN_REQUIRED"
    STRATEGY_HEALTH_MAX_AGE: Final[str] = "STRATEGY_HEALTH_MAX_AGE"
    STRATEGY_HEALTH_ERROR_WINDOW: Final[str] = "STRATEGY_HEALTH_ERROR_WINDOW"
    ETF_RISK_OFF_THRESHOLD: Final[str] = "ETF_RISK_OFF_THRESHOLD"
    ETF_DEFAULT_UNIVERSE: Final[str] = "ETF_DEFAULT_UNIVERSE"
    ETF_DEFAULT_NAMES: Final[str] = "ETF_DEFAULT_NAMES"

    # SchedulingConstants: SCHED_* time-point keys removed (2026-06-03 refactor).
    # REBALANCE/EOD/LIMITUP now read from unified REBALANCE_TIME/EOD_UPDATE_TIME keys.
    SCHED_MAIN_LOOP_INTERVAL_SEC: Final[str] = "SCHED_MAIN_LOOP_INTERVAL_SEC"
    SCHED_MONITOR_STATUS: Final[str] = "SCHED_MONITOR_STATUS"
    SCHED_MONITOR_PERF: Final[str] = "SCHED_MONITOR_PERF"
    # SCHED_RECONCILE_TIME removed (unified under RECONCILE_TIME)
    SCHED_RELOAD_INTERVAL_SEC: Final[str] = "SCHED_RELOAD_INTERVAL_SEC"
    SCHED_LIMIT_UP_POST_CLOSE_TIMEOUT_SEC: Final[str] = "SCHED_LIMIT_UP_POST_CLOSE_TIMEOUT_SEC"
    SCHED_SHUTDOWN_CLOSE_CANCEL_TIMEOUT_SEC: Final[str] = "SCHED_SHUTDOWN_CLOSE_CANCEL_TIMEOUT_SEC"

    # StreamMonitorConstants 补充
    MONITOR_PORT: Final[str] = "MONITOR_PORT"
    MONITOR_HOST: Final[str] = "MONITOR_HOST"
    MONITOR_REDIS_INIT_TIMEOUT_SEC: Final[str] = "MONITOR_REDIS_INIT_TIMEOUT_SEC"
    MONITOR_GATEWAY_INIT_TIMEOUT_SEC: Final[str] = "MONITOR_GATEWAY_INIT_TIMEOUT_SEC"
    MONITOR_XPENDING_SCAN_LIMIT: Final[str] = "MONITOR_XPENDING_SCAN_LIMIT"
    MONITOR_XPENDING_SCAN_TIMEOUT_SEC: Final[str] = "MONITOR_XPENDING_SCAN_TIMEOUT_SEC"
    MON_LIVENESS_TIMEOUT_MS: Final[str] = "MON_LIVENESS_TIMEOUT_MS"
    MON_READINESS_TIMEOUT_MS: Final[str] = "MON_READINESS_TIMEOUT_MS"
    MON_POSITION_TIMEOUT_SEC: Final[str] = "MON_POSITION_TIMEOUT_SEC"
    MONITOR_INCLUDE_ORDER_OPS_STREAMS: Final[str] = "MONITOR_INCLUDE_ORDER_OPS_STREAMS"
    MONITOR_WORKERS: Final[str] = "MONITOR_WORKERS"
    MONITOR_ENABLE_DOCS: Final[str] = "MONITOR_ENABLE_DOCS"
    MONITOR_CORS_ORIGINS: Final[str] = "MONITOR_CORS_ORIGINS"
    # 逗号分隔受信代理 CIDR（安全中间件 X-Forwarded-For 校验）
    MONITOR_TRUSTED_PROXY_CIDRS: Final[str] = "MONITOR_TRUSTED_PROXY_CIDRS"
    # 逗号分隔 HTTP 方法；省略时使用 GET,POST,PUT,PATCH,DELETE,OPTIONS,HEAD；设为 * 则 allow_methods=["*"]
    MONITOR_CORS_ALLOW_METHODS: Final[str] = "MONITOR_CORS_ALLOW_METHODS"
    # 逗号分隔请求头名；省略时使用显式白名单；设为 * 则 allow_headers=["*"]（不推荐生产）
    MONITOR_CORS_ALLOW_HEADERS: Final[str] = "MONITOR_CORS_ALLOW_HEADERS"
    # 非空时敏感 REST 路由须 Header X-Monitor-Token（与 stream_monitor 鉴权一致）
    MONITOR_API_TOKEN: Final[str] = "MONITOR_API_TOKEN"
    # true 时 Monitor 路由强制要求 MONITOR_API_TOKEN 已配置（默认 true）。
    MONITOR_API_TOKEN_STRICT: Final[str] = "MONITOR_API_TOKEN_STRICT"
    # 轮换窗口内仍接受的旧令牌（与对应 scope 主令牌二选一即可）
    MONITOR_API_TOKEN_READ_PREVIOUS: Final[str] = "MONITOR_API_TOKEN_READ_PREVIOUS"
    MONITOR_API_TOKEN_OPS_PREVIOUS: Final[str] = "MONITOR_API_TOKEN_OPS_PREVIOUS"
    MONITOR_API_TOKEN_RISK_PREVIOUS: Final[str] = "MONITOR_API_TOKEN_RISK_PREVIOUS"
    # 逗号分隔 CIDR 或单 IP；非空时仅允许这些来源访问 Monitor API（不含 / /healthz /ready）
    MONITOR_ALLOWED_IP_CIDRS: Final[str] = "MONITOR_ALLOWED_IP_CIDRS"
    # 是否信任 X-Forwarded-For 链中第一个 hop 作为客户端 IP（仅置于可信反向代理后开启，否则 IP 允许列表可被伪造）
    MONITOR_TRUST_X_FORWARDED_FOR: Final[str] = "MONITOR_TRUST_X_FORWARDED_FOR"
    # 对破坏性 POST 路径的每 IP 每分钟上限；0 或空表示不限制
    MONITOR_DESTRUCTIVE_RATE_LIMIT_PER_MINUTE: Final[str] = "MONITOR_DESTRUCTIVE_RATE_LIMIT_PER_MINUTE"
    # 为 true 时优先用 Redis 固定窗口计数（多 uvicorn worker 共享）；失败则回退进程内 deque
    MONITOR_DESTRUCTIVE_RATE_LIMIT_USE_REDIS: Final[str] = "MONITOR_DESTRUCTIVE_RATE_LIMIT_USE_REDIS"
    # 实盘手工下单总闸（Monitor manual_submit）；paper 不校验此项
    MONITOR_MANUAL_ORDER_LIVE_ENABLED: Final[str] = "MONITOR_MANUAL_ORDER_LIVE_ENABLED"
    # Executor 侧可选护栏：intent_provenance=monitor_manual_order 时生效（0/空=不限制）
    MONITOR_MANUAL_ORDER_MAX_NOTIONAL_YUAN: Final[str] = "MONITOR_MANUAL_ORDER_MAX_NOTIONAL_YUAN"
    # 逗号分隔 BUY,SELL；空=双向允许
    MONITOR_MANUAL_ORDER_ALLOWED_ACTIONS: Final[str] = "MONITOR_MANUAL_ORDER_ALLOWED_ACTIONS"
    # 逗号分隔证券代码前缀（点分前段）；空=不限制
    MONITOR_MANUAL_ORDER_STOCK_PREFIX_ALLOWLIST: Final[str] = "MONITOR_MANUAL_ORDER_STOCK_PREFIX_ALLOWLIST"
    # Monitor 经 Redis 转 executor 的行情查询（full_tick / limit_info）等待与轮询
    MONITOR_QMT_OPS_TIMEOUT_SEC: Final[str] = "MONITOR_QMT_OPS_TIMEOUT_SEC"
    MONITOR_QMT_OPS_POLL_MS: Final[str] = "MONITOR_QMT_OPS_POLL_MS"
    # TRADING_TYPE=live 时禁止 api_market 走单测用进程内 hkcodex 直连桥；仅当本键为 true/on 时允许（应急/少数单测）
    MONITOR_MARKET_ALLOW_LEGACY_DIRECT: Final[str] = "MONITOR_MARKET_ALLOW_LEGACY_DIRECT"
    # 为 true/on 时不在 lifespan 预热 QMTConnectionManager；周期健康与 get_qmt_health 跳过本机会话探测（无 XtQuant 的辅助机或降低同机争用）
    MONITOR_SKIP_QMT_WARMUP: Final[str] = "MONITOR_SKIP_QMT_WARMUP"
    # Executor 侧 qmt 行情运维响应 TTL 与限流
    QMT_OPS_RESPONSE_TTL_SEC: Final[str] = "QMT_OPS_RESPONSE_TTL_SEC"
    QMT_OPS_MAX_PER_SEC: Final[str] = "QMT_OPS_MAX_PER_SEC"
    QMT_OPS_XAUTOCLAIM_MIN_IDLE_MS: Final[str] = "QMT_OPS_XAUTOCLAIM_MIN_IDLE_MS"
    ENABLE_TCP_KEEPALIVE: Final[str] = "ENABLE_TCP_KEEPALIVE"

    # 执行器 CLI
    EXECUTOR_ACCOUNTS: Final[str] = "EXECUTOR_ACCOUNTS"

    # live_trading 退避
    BACKOFF_MAX_DELAY_SEC: Final[str] = "BACKOFF_MAX_DELAY_SEC"
    BACKOFF_JITTER_RATIO: Final[str] = "BACKOFF_JITTER_RATIO"

    # 测试与工具（供校验脚本 allowlist 引用，亦为合法键）
    RUN_STREAM_BRIDGE_E2E: Final[str] = "RUN_STREAM_BRIDGE_E2E"
    PYTHONIOENCODING: Final[str] = "PYTHONIOENCODING"

    # A2 方案：资本变更路由到 DatabaseGateway 治理层（默认 false，灰度启用）
    CAPITAL_MUTATION_VIA_GATEWAY: Final[str] = "CAPITAL_MUTATION_VIA_GATEWAY"
    CAPITAL_MUTATION_GATEWAY_FAIL_OPEN: Final[str] = "CAPITAL_MUTATION_GATEWAY_FAIL_OPEN"
    # A2 方案：executor 成交结算走单事务原子路径（默认 false，灰度启用）
    ATOMIC_FILL_SETTLEMENT: Final[str] = "ATOMIC_FILL_SETTLEMENT"

    # oskh_data 本地历史数据基础设施
    OSKH_DATA_ROOT: Final[str] = "OSKH_DATA_ROOT"
    OSKH_DATA_READER_MODE: Final[str] = "OSKH_DATA_READER_MODE"
    OSKH_DATA_MIN_COVERAGE_RATIO: Final[str] = "OSKH_DATA_MIN_COVERAGE_RATIO"
    OSKH_DATA_MAX_STALENESS_DAYS: Final[str] = "OSKH_DATA_MAX_STALENESS_DAYS"
    DAILY_BARS_SOURCE: Final[str] = "DAILY_BARS_SOURCE"  # qmt(default) | duckdb
    OSKH_DATA_DUCKDB_PATH: Final[str] = "OSKH_DATA_DUCKDB_PATH"  # P1-10: explicit DuckDB file path override


def resolve_env_int_first(keys: Tuple[str, ...], default: int) -> int:
    """按顺序读取多个配置键（环境变量优先，其次 YAML），返回首个可解析为 int 的值。"""
    ensure_runtime_config_loaded()
    for key in keys:
        raw = _config_get_raw(key)
        if raw is None or str(raw).strip() == "":
            continue
        try:
            return int(str(raw).strip())
        except (ValueError, TypeError):
            warnings.warn(
                f"[constants] invalid env {key}={raw!r} for resolve_env_int_first, skipped",
                RuntimeWarning,
                stacklevel=3,
            )
            continue
    return default


def iter_registered_env_var_keys() -> FrozenSet[str]:
    """EnvVarKeys 中登记的全部环境变量名字符串（供门禁脚本比对）。"""
    found: set[str] = set()
    for name, val in vars(EnvVarKeys).items():
        if name.startswith("_"):
            continue
        if isinstance(val, str) and val:
            found.add(val)
    return frozenset(found)


# ==================== 第一类：miniQMT 连接与数据获取常量（Phase 3 国金适配增强） ====================

class QMTConstants:
    """
    miniQMT/XtQuant 接口层技术常量（国金证券适配最终版）
    来源文件：qmt_client.py, hkcodex_miniqmt.py, executor_stream/, live_trading.py

    Phase 3 关键限制（国金miniQMT硬性约束）：
    - 单账户≤2连接（突破将触发券商端拒绝）
    - 24小时内重连≤10次（内存泄漏防护）
    - xtdata.init() 必须在 XtQuantTrader 实例化之前调用
    - session_id 范围限制 1-999999（兼容 XtTrader 文档示例与券商运行时）
    """

    # 批量查询限制（国金miniQMT建议单批次不超过50，防止内存溢出）
    BATCH_SIZE: Final[int] = _get_env_int_in_range(
        EnvVarKeys.QMT_BATCH_SIZE, 50, min_value=1, max_value=500
    )

    # 价格比较容差（1分钱，避免浮点精度导致的涨跌停误判）
    PRICE_TOLERANCE: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_PRICE_TOLERANCE, 0.01, min_value=0.0, max_value=1.0
    )

    # 实时价格缓存有效期（秒），降低xtdata API调用频率
    PRICE_CACHE_TIMEOUT_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_PRICE_CACHE_TIMEOUT_SEC, 5.0, min_value=0.1, max_value=300.0
    )

    # 重连策略（指数退避基数，单位秒）
    RECONNECT_DELAY_BASE: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_RECONNECT_DELAY, 1.0, min_value=0.1, max_value=120.0
    )

    # 24小时内最大重连次数（国金miniQMT内存泄漏防护硬性限制）
    MAX_RECONNECT_24H: Final[int] = _get_env_int_in_range(
        EnvVarKeys.QMT_MAX_RECONNECT_24H, 10, min_value=1, max_value=100
    )

    # 距 24h 重连上限还剩 N 次时开启 broker_sync 预防熔断（默认 2 → 8/10 触发）
    CONNECTION_BUDGET_RECONNECT_WARN_REMAINING: Final[int] = _get_env_int_in_range(
        EnvVarKeys.QMT_CONNECTION_BUDGET_RECONNECT_WARN_REMAINING,
        2,
        min_value=0,
        max_value=20,
    )
    # broker_sync 连续 skip 次数达到阈值时打开熔断（默认 5min 内 6 次）
    CONNECTION_BUDGET_BROKER_SYNC_STORM_TRIP: Final[int] = _get_env_int_in_range(
        EnvVarKeys.QMT_CONNECTION_BUDGET_BROKER_SYNC_STORM_TRIP,
        6,
        min_value=2,
        max_value=50,
    )
    CONNECTION_BUDGET_BROKER_SYNC_STORM_WINDOW_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_CONNECTION_BUDGET_BROKER_SYNC_STORM_WINDOW_SEC,
        300.0,
        min_value=30.0,
        max_value=3600.0,
    )
    CONNECTION_BUDGET_FUSE_COOLDOWN_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_CONNECTION_BUDGET_FUSE_COOLDOWN_SEC,
        600.0,
        min_value=60.0,
        max_value=7200.0,
    )
    CONNECTION_BUDGET_ALERT_DEDUPE_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_CONNECTION_BUDGET_ALERT_DEDUPE_SEC,
        600.0,
        min_value=60.0,
        max_value=3600.0,
    )

    # 单账户最大并发连接数（国金miniQMT硬性限制≤2，含等待队列管理）
    MAX_CONCURRENT_CONNECTIONS_PER_ACCOUNT: Final[int] = _get_env_int_in_range(
        EnvVarKeys.QMT_MAX_CONN_PER_ACCOUNT, 2, min_value=1, max_value=2
    )

    # 连接槽位等待超时（秒，超过此时间视为获取槽位失败）
    CONNECTION_SLOT_TIMEOUT_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_SLOT_TIMEOUT_SEC, 30.0, min_value=1.0, max_value=600.0
    )

    # 单次操作最大重试次数
    MAX_OPERATION_RETRY: Final[int] = _get_env_int_in_range(
        EnvVarKeys.QMT_MAX_RETRY, 3, min_value=0, max_value=20
    )

    # 心跳/连接检查间隔（秒）
    PING_INTERVAL_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_PING_INTERVAL_SEC, 30.0, min_value=1.0, max_value=600.0
    )

    # 会话 last_heartbeat 陈旧阈值（秒）；默认 60 与历史 is_healthy 行为一致
    SESSION_STALE_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_SESSION_STALE_SEC, 60.0, min_value=10.0, max_value=3600.0
    )

    # xtdata连接超时（秒）
    XDATA_CONNECT_TIMEOUT_SEC: Final[int] = _get_env_int_in_range(
        EnvVarKeys.QMT_XDATA_TIMEOUT_SEC, 3, min_value=1, max_value=60
    )

    # xtdata读取超时（秒）
    XDATA_READ_TIMEOUT_SEC: Final[int] = _get_env_int_in_range(
        EnvVarKeys.QMT_XDATA_READ_TIMEOUT_SEC, 5, min_value=1, max_value=120
    )

    # 市场数据批次处理大小（与BATCH_SIZE区分，用于不同场景）
    MARKET_DATA_BATCH: Final[int] = _get_env_int_in_range(
        EnvVarKeys.QMT_MARKET_BATCH, 50, min_value=1, max_value=1000
    )

    # Phase 3：session_id 范围（兼容 XtTrader 文档示例 123456）
    SESSION_ID_MIN: Final[int] = 1
    SESSION_ID_MAX: Final[int] = 999999

    # Phase 3 新增：xtdata初始化重试策略（因网络抖动导致init失败）
    XTDATA_INIT_MAX_RETRY: Final[int] = 3
    XTDATA_INIT_RETRY_DELAY: Final[float] = 0.5  # 秒

    # 单次建连阶段 subscribe_whole_quote 重试（与心跳路径互补）
    MARKET_SUBSCRIBE_SESSION_MAX_RETRY: Final[int] = _get_env_int_in_range(
        EnvVarKeys.QMT_MARKET_SUBSCRIBE_MAX_RETRY, 3, min_value=1, max_value=10
    )
    MARKET_SUBSCRIBE_RETRY_DELAY_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_MARKET_SUBSCRIBE_RETRY_DELAY_SEC, 0.5, min_value=0.1, max_value=10.0
    )
    MARKET_RESUB_INTERVAL_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_MARKET_RESUB_INTERVAL_SEC, 60.0, min_value=0.0, max_value=3600.0
    )

    # P0-10：行情数据静默超时阈值（秒）。默认 120 秒，允许 0（禁用）到 3600。
    MARKET_DATA_FROZEN_THRESHOLD_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_MARKET_DATA_FROZEN_THRESHOLD_SEC, 120.0, min_value=0.0, max_value=3600.0
    )

    # P0-13：资产连续相同快照阈值（交易时段内连续 N 次心跳 cash 不变 → 标记 stale）
    ASSET_STALE_CONSECUTIVE_THRESHOLD: Final[int] = _get_env_int_in_range(
        EnvVarKeys.QMT_ASSET_STALE_CONSECUTIVE_THRESHOLD, 3, min_value=2, max_value=10
    )
    # P1-25：资产载荷异常（cash=None/NaN/负值）连续阈值；默认 1（首个异常即生效）。
    ASSET_INVALID_CONSECUTIVE_THRESHOLD: Final[int] = _get_env_int_in_range(
        EnvVarKeys.QMT_ASSET_INVALID_CONSECUTIVE_THRESHOLD, 1, min_value=1, max_value=10
    )
    # P1-25：live 下资产载荷 invalid 强制 fail-close，paper 允许仅观测。
    ASSET_INVALID_FAIL_CLOSE_LIVE: Final[bool] = _get_env_bool(
        EnvVarKeys.QMT_ASSET_INVALID_FAIL_CLOSE_LIVE, True
    )

    # 紧急直连模式开关（环境变量 QMT_EMERGENCY_MODE=1 时启用 fail-open 模式）
    EMERGENCY_MODE_ENV: Final[str] = EnvVarKeys.QMT_EMERGENCY_MODE

    # Phase 3 新增：重连日志持久化默认路径（相对于qmt_client.py）
    RECONNECT_LOG_DEFAULT_PATH: Final[str] = ".qmt_reconnect_log.json"


# ==================== 金融级错误代码体系（Phase 3 P0级重构 + P0热修复完整版） ====================

class ErrorCode(Enum):
    """
    金融级错误代码体系（P0/P1/P2 分级）

    符合《证券期货业信息系统故障分类规范》，支持全链路追踪与ELK索引。
    格式：DOMAIN_xxx（如 CONN_001, TRADE_001）

    Phase 3 P0 热修复变更：
    - [新增] 持久化层扩展：DB_005-008（Schema违规、数据完整性、查询失败、持久化失败）
    - [新增] 配置层扩展：CFG_006（CONFIG_MISSING，用于Gateway初始化等特定缺失场景）
    - [新增] 交易执行层：TRADE_020（RECORD_FAILED，前置校验失败场景）
    - [新增] Layer 2.5 专用域：LAYER25_001-003（初始化失败、队列溢出、紧急降级）

    级别定义：
    - P0（严重）：系统崩溃级，立即熔断，人工介入
    - P1（重要）：业务中断级，自动重试/降级，通知运维
    - P2（一般）：功能降级级，记录日志，监控观察
    """

    # 系统级 (SYS)
    SYS_UNKNOWN = ("SYS_001", "P0", "未知系统错误")
    SYS_INITIALIZATION_FAILED = ("SYS_002", "P0", "基础设施初始化失败")
    SYS_SHUTDOWN_ERROR = ("SYS_003", "P1", "系统关闭异常")
    SYS_CONTEXT_LOST = ("SYS_004", "P1", "Trace ID上下文丢失（协程切换异常）")

    # QMT连接层 (CONN) - 国金miniQMT Phase 2/3 增强
    CONN_FAILED = ("CONN_001", "P0", "miniQMT连接建立失败")
    CONN_LOST = ("CONN_002", "P0", "连接中断")
    CONN_RECONNECT_LIMIT = ("CONN_003", "P0", f"24小时重连次数超限（国金限制≤{QMTConstants.MAX_RECONNECT_24H}）")
    CONN_HEALTH_DEGRADED = ("CONN_004", "P1", "连接健康度低于阈值")
    CONN_EMERGENCY_MODE_DENIED = ("CONN_005", "P0", "紧急直连模式未授权")
    CONN_MULTI_ACCOUNT_LIMIT = ("CONN_006", "P1",
                                f"单账户连接数超限（国金限制≤{QMTConstants.MAX_CONCURRENT_CONNECTIONS_PER_ACCOUNT}）")
    CONN_SLOT_TIMEOUT = ("CONN_007", "P0", f"连接槽位等待超时（>{QMTConstants.CONNECTION_SLOT_TIMEOUT_SEC}s）")
    CONN_XTDATA_INIT_FAILED = ("CONN_008", "P0", "xtdata.init() 初始化失败（国金要求前置）")
    CONN_TRADER_LOCK_ACQUIRE_FAILED = ("CONN_009", "P1", "交易员锁获取失败（并发冲突）")
    CONN_QMT_CONNECTION_FAILED = ("CONN_010", "P0", "QMT连接建立失败（通用）")
    CONN_QMT_MANAGER_INIT_FAILED = ("CONN_011", "P0", "QMT连接管理器初始化失败")

    # 紧急模式 (EMERG)
    EMERG_MODE_TRIGGERED = ("EMERG_001", "P1", "紧急模式已激活（fail-open）")
    EMERG_MODE_FORBIDDEN = ("EMERG_002", "P0", "紧急模式未启用但尝试调用")

    # 交易执行层 (TRADE) - Phase 3 补全（支持 TradingExecutionError）
    TRADE_ORDER_REJECTED = ("TRADE_001", "P0", "订单被券商拒绝")
    TRADE_PRICE_LIMIT = ("TRADE_002", "P1", "价格超出涨跌停限制")
    TRADE_INSUFFICIENT_CASH = ("TRADE_003", "P0", "资金不足")
    TRADE_INSUFFICIENT_POSITION = ("TRADE_004", "P0", "持仓不足")
    TRADE_TIMEOUT = ("TRADE_005", "P1", "订单超时未确认")
    TRADE_PARTIAL_FILL = ("TRADE_006", "P2", "订单部分成交")
    TRADE_CASH_FUSE = ("TRADE_007", "P0", "资金熔断触发（偏差>5%）")
    TRADE_EXECUTION_FAILED = ("TRADE_008", "P1", "交易执行失败（通用）")
    TRADE_ORDER_CALLBACK_FAILED = ("TRADE_009", "P1", "订单回调处理失败（on_order）")
    TRADE_TRADE_CALLBACK_FAILED = ("TRADE_010", "P1", "成交回调处理失败（on_trade）")
    TRADE_DATA_PREPARE_FAILED = ("TRADE_011", "P1", "交易数据准备失败（名称解析等）")
    TRADE_RECORD_PERSIST_FAILED = ("TRADE_012", "P1", "交易记录持久化失败（CSV写入等）")
    TRADE_ORDER_PLACEMENT_FAILED = ("TRADE_013", "P1", "订单委托失败（order_stock返回None）")
    TRADE_ORDER_WAIT_COMPLETION_FAILED = ("TRADE_014", "P1", "订单等待完成失败（超时或中断）")
    TRADE_SELL_EXECUTION_FAILED = ("TRADE_015", "P0", "卖出执行最终失败（超过最大重试次数）")
    TRADE_BUY_EXECUTION_FAILED = ("TRADE_016", "P0", "买入执行最终失败（超过最大重试次数）")
    TRADE_LIMITUP_SELL_FAILED = ("TRADE_017", "P1", "涨停开板卖出失败")
    TRADE_CASH_QUERY_FAILED = ("TRADE_018", "P1", "资金查询失败（连接中断）")
    TRADE_CASH_CIRCUIT_BREAKER_TRIGGERED = ("TRADE_019", "P0", "资金熔断检查触发（策略与真实资金偏差超限）")
    # P0 热修复新增：交易记录前置校验失败（与 PERSIST 区分，RECORD 侧重业务校验，PERSIST 侧重IO）
    TRADE_RECORD_FAILED = ("TRADE_020", "P1", "交易记录生成失败（前置校验未通过）")
    # Week 4 新增：交易数量计算失败（buy_stocks中calculate_quantities阶段）
    TRADE_QUANTITY_CALC_FAILED = ("TRADE_021", "P1", "交易数量计算失败（买入股数计算异常或零股结果）")

    # 策略执行层 (STRAT) - Phase 3 新增（支持 StrategyExecutionError）
    STRATEGY_EXECUTION_FAILED = ("STRAT_001", "P1", "策略执行失败（通用）")
    STRATEGY_DATA_LOAD_FAILED = ("STRAT_002", "P1", "策略数据加载失败（CSV/Portfolio记录损坏）")
    STRATEGY_SELECTION_GENERATION_FAILED = ("STRAT_003", "P1", "选股生成失败（算法异常）")
    STRATEGY_SELECTION_FILE_READ_FAILED = ("STRAT_004", "P1", "选股文件读取失败（权限、不存在）")
    STRATEGY_SELECTION_FILE_WRITE_FAILED = ("STRAT_005", "P1", "选股文件写入失败（磁盘满、权限）")
    STRATEGY_PORTFOLIO_UPDATE_FAILED = ("STRAT_006", "P1", "投资组合记录更新失败")
    STRATEGY_PORTFOLIO_PERSIST_FAILED = ("STRAT_007", "P1", "投资组合持久化失败（文件锁定等）")
    STRATEGY_PORTFOLIO_HISTORY_READ_FAILED = ("STRAT_008", "P2", "投资组合历史读取失败（非关键）")
    STRATEGY_REBALANCE_FAILED = ("STRAT_009", "P0", "调仓执行最终失败")
    STRATEGY_EOD_RECONCILE_FAILED = ("STRAT_010", "P1", "日终对账失败")
    STRATEGY_EOD_REFRESH_FAILED = ("STRAT_011", "P1", "日终刷新失败")
    STRATEGY_SIGNAL_SELECTION_FAILED = ("STRAT_012", "P1", "调仓信号选股失败")
    STRATEGY_CONFIG_VALIDATION_FAILED = ("STRAT_013", "P0", "策略配置验证失败")
    STRATEGY_INIT_DATA_LOAD_FAILED = ("STRAT_014", "P0", "初始化数据加载失败（阻断启动）")
    STRATEGY_MAIN_LOOP_FATAL_ERROR = ("STRAT_015", "P0", "主循环致命错误（需重启）")
    STRATEGY_REBALANCE_DAY_CHECK_FAILED = ("STRAT_016", "P1", "再平衡日期检查失败")

    # 市场数据层 (MARKET) - Phase 3 新增（支持 MarketDataError 细分）
    MARKET_PRICE_FETCH_FAILED = ("MARKET_001", "P1", "实时价格获取失败")
    MARKET_LIMIT_INFO_FETCH_FAILED = ("MARKET_002", "P1", "涨跌停信息获取失败")
    MARKET_NAME_RESOLUTION_FAILED = ("MARKET_003", "P2", "股票名称解析失败（非关键）")
    MARKET_CALENDAR_QUERY_FAILED = ("MARKET_004", "P1", "交易日历查询失败")
    MARKET_HISTORICAL_DATA_FETCH_FAILED = ("MARKET_005", "P1", "历史数据获取失败")
    MARKET_DATA_FETCH_FAILED = ("MARKET_006", "P1", "市场数据获取失败（通用）")
    MARKET_PRICE_CHECK_FAILED = ("MARKET_007", "P1", "价格检查失败（卖出条件判断）")
    MARKET_WHOLE_QUOTE_NOT_READY = ("MARKET_008", "P0", "全市场行情未就绪（subscribe_whole_quote 未成功且 REQUIRE_QMT_MARKET_SUBSCRIPTION）")

    # 风控层 (RISK)
    RISK_POSITION_LIMIT = ("RISK_002", "P0", "持仓集中度超限")
    RISK_VOLATILITY_LIMIT = ("RISK_003", "P1", "波动率异常")
    RISK_BLACKLIST = ("RISK_004", "P0", "交易标的在黑名单中")
    RISK_WHITELIST = ("RISK_011", "P0", "交易标的不在白名单内（BUY）")
    RISK_RUNTIME_FUSE = ("RISK_012", "P1", "运维熔断态拦截（halt / sell_only）")
    RISK_CASH_INSUFFICIENT = ("RISK_005", "P1", "可用资金不足（含冻结与缓冲）")
    RISK_STOP_LOSS_ADDON = ("RISK_006", "P1", "止损触发后禁止加仓")
    RISK_DAILY_LOSS_LIMIT = ("RISK_007", "P1", "日亏损超限（相对前一交易日收盘权益）")
    RISK_INDUSTRY_LIMIT = ("RISK_008", "P1", "行业集中度超限")
    RISK_GROSS_EXPOSURE = ("RISK_009", "P1", "组合总仓位/敞口超限")
    RISK_DRAWDOWN_LIMIT = ("RISK_010", "P1", "最大回撤相对峰值权益超限")
    RISK_LEVERAGE_LIMIT = ("RISK_013", "P1", "组合杠杆率超限（NAV/可用现金）")
    RISK_RUNTIME_BRIDGE_PAUSE = ("RISK_014", "P1", "Bridge 发单暂停标记拦截（暂停新单入队）")
    RISK_DATA_INSUFFICIENT = ("RISK_015", "P1", "风控输入数据不足（strict 模式拒单）")

    # 数据/审计层 (AUDIT)
    AUDIT_LOG_LOST = ("AUDIT_001", "P0", "审计日志丢失或损坏")
    AUDIT_TRACE_ID_MISMATCH = ("AUDIT_002", "P1", "Trace ID 链路断裂")
    AUDIT_DATA_INTEGRITY = ("AUDIT_003", "P0", "数据一致性校验失败")
    AUDIT_COLD_STORAGE_FAILED = ("AUDIT_004", "P1", "冷存储归档失败")
    AUDIT_PERF_VIOLATION = ("AUDIT_005", "P1", "性能监控数据异常")
    AUDIT_ANOMALY_RATE_HIGH = ("AUDIT_006", "P0", "日终对账异常率超阈值")

    # 持久化层 (DB) — 成员按 DB_001…DB_010 编号顺序排列（便于运维对照日志码表）
    DB_CONNECTION_FAILED = ("DB_001", "P0", "数据库连接失败")
    DB_WAL_CORRUPTION = ("DB_002", "P0", "WAL文件损坏（容器重启风险）")
    DB_BATCH_WRITE_FAILED = ("DB_003", "P1", "批量写入失败")
    DB_TIMEOUT = ("DB_004", "P1", "数据库操作超时")
    DB_SCHEMA_VIOLATION = ("DB_005", "P0", "数据库Schema违规（trace_id字段缺失或表结构不兼容）")
    DB_DATA_INTEGRITY_VIOLATION = ("DB_006", "P1", "数据完整性违规（NULL值、长度不符或外键失败）")
    DB_QUERY_FAILED = ("DB_007", "P1", "数据库查询执行失败（SQL语法或运行时错误）")
    DB_PERSISTENCE_FAILED = ("DB_008", "P1", "数据持久化失败（磁盘IO、权限或文件锁定）")
    DB_POOL_EXHAUSTED = ("DB_009", "P1", "数据库连接池耗尽（并发过载或连接泄漏）")
    DB_READONLY_VIOLATION = ("DB_010", "P0", "只读连接写操作违规（安全策略拦截）")

    # 配置层 (CFG) - P0热修复：新增 CFG_006
    CFG_MISSING_REQUIRED = ("CFG_001", "P0", "缺少必要配置项")
    CFG_VALIDATION_FAILED = ("CFG_002", "P1", "配置校验失败")
    CFG_MASKING_ERROR = ("CFG_003", "P2", "配置脱敏处理异常")
    CFG_SENSITIVE_LEAK = ("CFG_004", "P0", "敏感配置泄露风险")
    CFG_VALIDATION_ERROR = ("CFG_005", "P1", "配置验证过程异常（非格式错误）")
    # P0 热修复新增：特定配置缺失（如 Gateway 初始化失败、数据库未注册等场景）
    CFG_CONFIG_MISSING = ("CFG_006", "P0", "特定配置缺失（Gateway初始化或关键依赖未配置）")

    # Redis/消息队列层 (REDIS)
    REDIS_BRIDGE_INSTALL_FAILED = ("REDIS_001", "P1", "Redis流桥接安装失败")
    REDIS_CONNECTION_FAILED = ("REDIS_002", "P0", "Redis连接失败")
    REDIS_STREAM_READ_FAILED = ("REDIS_003", "P1", "Redis流读取失败")

    # Layer 2.5 执行记录器专用 (LAYER25) - P0热修复：新增独立错误域
    # 设计原则：与 DB 层错误区分，专门标识 ExecutionRecorder（C++回调缓冲层）故障
    LAYER25_INIT_FAILED = ("LAYER25_001", "P0", "Layer 2.5 ExecutionRecorder初始化失败（内存分配或线程创建失败）")
    LAYER25_QUEUE_OVERFLOW = ("LAYER25_002", "P1", "Layer 2.5执行记录队列溢出（>80%阈值或满队列写入失败）")
    LAYER25_EMERGENCY_FALLBACK = ("LAYER25_003", "P1", "Layer 2.5紧急降级至同步写入（性能降级但数据安全）")

    # 跨域数据完整性 (DATA) — M.1-M.5 静默数据腐败治理基础设施
    DATA_INTEGRITY_NULL_FIELD = ("DATA_001", "P1", "数据完整性：必填字段为None（跨层传递断裂）")
    DATA_INTEGRITY_INVALID_VALUE = ("DATA_002", "P1", "数据完整性：字段值类型/格式非法")
    DATA_INTEGRITY_TYPE_COERCION = ("DATA_003", "P1", "数据完整性：类型强制陷阱（bool伪装为int/float）")
    DATA_INTEGRITY_BROKER = ("DATA_004", "P1", "数据完整性：券商返回数据校验失败")

    def __init__(self, code: str, level: str, description: str):
        self.code = code
        self.level = level  # P0/P1/P2
        self.description = description

    def to_dict(self) -> Dict[str, str]:
        """序列化为字典（供ELK索引与API响应）"""
        return {
            "code": self.code,
            "level": self.level,
            "description": self.description
        }


# ==================== 第二类：交易执行与订单管理常量 ====================

class TradingConstants:
    """
    交易执行层技术常量（买卖操作、订单等待、风控检查）
    来源文件：live_trading.py, hkcodex_miniqmt.py, executor_stream/
    """

    # 最低佣金（元，不足按此收取）
    MIN_COMMISSION: Final[float] = _get_env_float(EnvVarKeys.TRADE_MIN_COMMISSION, 5.0)

    # 交易股数基数（A股100股=1手）
    LOT_SIZE: Final[int] = _get_env_int(EnvVarKeys.TRADE_LOT_SIZE, 100)

    # 卖单重试最大次数
    SELL_MAX_RETRIES: Final[int] = _get_env_int_in_range(
        EnvVarKeys.TRADE_SELL_MAX_RETRY, 5, min_value=0, max_value=50
    )

    # 买单重试最大次数
    BUY_MAX_RETRIES: Final[int] = _get_env_int_in_range(
        EnvVarKeys.TRADE_BUY_MAX_RETRY, 5, min_value=0, max_value=50
    )

    # 订单提交间隔（秒，防止触发券商流控）
    ORDER_SUBMIT_INTERVAL_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.TRADE_ORDER_INTERVAL_SEC, 0.5, min_value=0.0, max_value=300.0
    )

    # 事件驱动订单等待：高频轮询窗口（秒）
    EVENT_FAST_POLL_DURATION: Final[float] = _get_env_float_in_range(
        EnvVarKeys.TRADE_FAST_POLL_SEC, 5.0, min_value=0.0, max_value=600.0
    )

    # 事件驱动订单等待：单次事件等待超时（秒，10ms级精度）
    EVENT_WAIT_TIMEOUT_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.TRADE_EVENT_WAIT_SEC, 0.01, min_value=0.0, max_value=60.0
    )

    # 订单完成等待总超时（秒）
    ORDER_COMPLETION_TIMEOUT_SEC: Final[int] = _get_env_int_in_range(
        EnvVarKeys.TRADE_COMPLETION_TIMEOUT_SEC, 120, min_value=1, max_value=3600
    )

    # 普通轮询间隔（秒，非事件驱动模式）
    POLL_INTERVAL_STANDARD: Final[float] = _get_env_float_in_range(
        EnvVarKeys.TRADE_POLL_INTERVAL_SEC, 0.5, min_value=0.0, max_value=60.0
    )

    # 高频轮询间隔（秒，用于前N秒兜底）
    POLL_INTERVAL_FAST: Final[float] = _get_env_float_in_range(
        EnvVarKeys.TRADE_POLL_INTERVAL_FAST_SEC, 0.1, min_value=0.0, max_value=60.0
    )

    # 涨停开板卖出阈值（从涨停价回撤比例，如0.02=2%）
    LIMIT_UP_OPEN_THRESHOLD: Final[float] = _get_env_float_in_range(
        EnvVarKeys.TRADE_OPEN_BOARD_THRESHOLD, 0.02, min_value=0.0, max_value=1.0
    )

    # 资金熔断检查偏差阈值（默认5%）
    CASH_FUSE_THRESHOLD: Final[float] = _get_env_float_in_range(
        EnvVarKeys.TRADE_CASH_FUSE_THRESHOLD, 0.05, min_value=0.0, max_value=1.0
    )

    # 资金检查间隔（秒）
    CASH_CHECK_INTERVAL_SEC: Final[int] = _get_env_int_in_range(
        EnvVarKeys.TRADE_CASH_CHECK_INTERVAL_SEC, 300, min_value=1, max_value=86400
    )


# ==================== 第三类：Redis Stream 与消息队列常量 ====================

class RedisConstants:
    """
    Redis Stream 消息队列技术常量（桥接器与执行器）
    来源文件：redis_stream_bridge/, executor_stream/
    """

    # 审计缓冲区：自动刷盘间隔（秒）
    AUDIT_FLUSH_INTERVAL_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.REDIS_AUDIT_FLUSH_SEC, 0.1, min_value=0.0, max_value=60.0
    )

    # 审计缓冲区：批量提交阈值（条）
    AUDIT_BATCH_SIZE: Final[int] = _get_env_int_in_range(
        EnvVarKeys.REDIS_AUDIT_BATCH_SIZE, 50, min_value=1, max_value=10000
    )

    # 审计缓冲区：内存上限（条，防OOM）
    AUDIT_BUFFER_MAX_SIZE: Final[int] = _get_env_int_in_range(
        EnvVarKeys.REDIS_AUDIT_BUFFER_MAX, 1000, min_value=1, max_value=1000000
    )

    # 线程池：桥接器降级重传工作线程数
    BRIDGE_WORKER_THREADS: Final[int] = _get_env_int_in_range(
        EnvVarKeys.REDIS_BRIDGE_WORKERS, 2, min_value=1, max_value=128
    )

    # 线程池：监控器异步查询工作线程数
    MONITOR_WORKER_THREADS: Final[int] = _get_env_int_in_range(
        EnvVarKeys.REDIS_MONITOR_WORKERS, 4, min_value=1, max_value=128
    )

    # 降级重传间隔（秒，Redis恢复后批量重传间隔）
    FALLBACK_REPLAY_DELAY: Final[float] = _get_env_float_in_range(
        EnvVarKeys.REDIS_REPLAY_DELAY, 0.01, min_value=0.0, max_value=300.0
    )

    # Stream消息确认超时（秒，超过此时间未ACK视为Pending）
    ACK_TIMEOUT_SEC: Final[int] = resolve_env_int_first(
        (EnvVarKeys.ACK_TIMEOUT_SEC, EnvVarKeys.REDIS_ACK_TIMEOUT_SEC), 30
    )

    # 阻塞读取超时（毫秒）；BLOCK_TIME_MS 优先，REDIS_BLOCK_MS 为历史别名
    BLOCK_TIME_MS: Final[int] = resolve_env_int_first(
        (EnvVarKeys.BLOCK_TIME_MS, EnvVarKeys.REDIS_BLOCK_MS), 5000
    )

    # executor xreadgroup block（毫秒），与 strategy 侧 BLOCK_TIME_MS 解耦时可单独调优
    XREADGROUP_BLOCK_MS: Final[int] = _get_env_int_in_range(
        EnvVarKeys.REDIS_XREADGROUP_BLOCK_MS, 10000, min_value=1, max_value=600000
    )

    # Pending List检查批大小（单次检查Pending消息数）
    PENDING_CHECK_BATCH: Final[int] = _get_env_int_in_range(
        EnvVarKeys.REDIS_PENDING_BATCH, 10, min_value=1, max_value=2000
    )

    # 消费者组健康检查间隔（秒）
    CONSUMER_HEALTH_INTERVAL_SEC: Final[int] = _get_env_int_in_range(
        EnvVarKeys.REDIS_HEALTH_INTERVAL_SEC, 30, min_value=1, max_value=3600
    )

    # 最大重投递次数（进入死信队列前重试次数）
    MAX_REDELIVERY_COUNT: Final[int] = _get_env_int_in_range(
        EnvVarKeys.REDIS_MAX_REDELIVERY, 3, min_value=0, max_value=100
    )

    # Redis连接池最大连接数
    REDIS_POOL_MAX_CONN: Final[int] = _get_env_int_in_range(
        EnvVarKeys.REDIS_POOL_MAX, 10, min_value=1, max_value=10000
    )


# ==================== 第四类：SQLite 审计与持久化常量 ====================

class PersistenceConstants:
    """
    SQLite 审计数据库与文件操作常量
    来源文件：persistence.py, eod_reconcile/reconciler.py, redis_stream_bridge/, executor_stream/
    """

    # SQLite连接超时（秒）
    SQLITE_TIMEOUT_SEC: Final[int] = _get_env_int_in_range(
        EnvVarKeys.SQLITE_TIMEOUT_SEC, 5, min_value=1, max_value=120
    )

    # WAL模式自动检查点页数（每N页触发一次检查点）
    SQLITE_WAL_AUTOCHECKPOINT: Final[int] = _get_env_int_in_range(
        EnvVarKeys.SQLITE_WAL_CHECKPOINT, 100, min_value=1, max_value=1000000
    )

    # WAL-size-based checkpoint threshold (bytes). Triggers PASSIVE checkpoint when
    # the WAL file exceeds this size. 100 KB ≈ 25 pages at 4096-byte pages.
    # Env var: WAL_SIZE_CHECKPOINT_THRESHOLD_KB (in KB, default 50, range 10-10240).
    WAL_SIZE_CHECKPOINT_THRESHOLD_BYTES: Final[int] = _get_env_int_in_range(
        EnvVarKeys.WAL_SIZE_CHECKPOINT_THRESHOLD_KB, 50,
        min_value=10, max_value=10240,
    ) * 1024

    # P0-8: WAL checkpoint mode. PASSIVE (default before P0-8) does not reclaim
    # WAL frames when readers hold locks, causing the WAL file to grow unbounded.
    # TRUNCATE busy-waits for readers to finish, checkpoints all frames, then
    # truncates the WAL to zero bytes. If readers never release, TRUNCATE
    # degrades gracefully (checkpoints what it can, returns busy, WAL unchanged).
    # Allowed: PASSIVE, FULL, TRUNCATE. Default: TRUNCATE.
    # Env var: WAL_CHECKPOINT_MODE.
    _WAL_CKPT_MODE_RAW: Final[str] = _get_env_str(
        EnvVarKeys.WAL_CHECKPOINT_MODE, "TRUNCATE"
    ).strip().upper()
    WAL_CHECKPOINT_MODE: Final[str] = (
        _WAL_CKPT_MODE_RAW if _WAL_CKPT_MODE_RAW in {"PASSIVE", "FULL", "TRUNCATE"} else "TRUNCATE"
    )

    # P0-8: Periodic WAL checkpoint interval (seconds). The async writer loop
    # runs a checkpoint at this interval independent of batch commits, so the
    # WAL is reclaimed even under sparse write traffic (P0-7 coupling).
    # 0 disables the periodic checkpoint. Default: 30s.
    # Env var: WAL_PERIODIC_CHECKPOINT_INTERVAL_S.
    WAL_PERIODIC_CHECKPOINT_INTERVAL_S: Final[int] = _get_env_int_in_range(
        EnvVarKeys.WAL_PERIODIC_CHECKPOINT_INTERVAL_S, 30,
        min_value=0, max_value=3600,
    )

    # 并发模式（NORMAL确保数据安全且性能平衡）
    SQLITE_SYNCHRONOUS: Final[str] = _get_env_str(EnvVarKeys.SQLITE_SYNC_MODE, "NORMAL")

    # 数据库操作重试次数（文件锁定场景）
    DB_MAX_RETRIES: Final[int] = _get_env_int_in_range(
        EnvVarKeys.DB_MAX_RETRIES, 3, min_value=0, max_value=50
    )

    # 文件锁定重试等待（秒）
    DB_RETRY_DELAY: Final[int] = _get_env_int_in_range(
        EnvVarKeys.DB_RETRY_DELAY, 1, min_value=0, max_value=300
    )

    # 投资组合记录文件写入重试次数
    PORTFOLIO_WRITE_RETRIES: Final[int] = _get_env_int_in_range(
        EnvVarKeys.PORTFOLIO_WRITE_RETRY, 3, min_value=0, max_value=50
    )

    # 投资组合记录文件写入重试等待（秒）
    PORTFOLIO_RETRY_DELAY: Final[int] = _get_env_int_in_range(
        EnvVarKeys.PORTFOLIO_RETRY_DELAY, 10, min_value=0, max_value=600
    )

    # 热数据保留天数（本地WAL模式数据库）
    HOT_DATA_RETENTION_DAYS: Final[int] = _get_env_int_in_range(
        EnvVarKeys.HOT_DATA_RETENTION_DAYS, 90, min_value=1, max_value=3650
    )

    # 冷存储启用开关（S3/OSS归档，满足监管5年要求）
    COLD_STORAGE_ENABLED: Final[bool] = _get_env_bool(EnvVarKeys.COLD_STORAGE_ENABLED, False)

    # 冷存储路径（本地挂载点或S3 URI前缀）
    COLD_STORAGE_PATH: Final[str] = _get_env_str(EnvVarKeys.COLD_STORAGE_PATH, "/data/cold_storage")

    # 冷归档流式导出每批行数（防大表 OOM）
    COLD_ARCHIVE_CHUNK_SIZE: Final[int] = _get_env_int_in_range(
        EnvVarKeys.COLD_ARCHIVE_CHUNK_SIZE, 5000, min_value=100, max_value=100000
    )

    # Phase 3 新增：冷存储URI环境变量键（供quant_logger使用）
    COLD_STORAGE_URI_ENV: Final[str] = EnvVarKeys.COLD_STORAGE_URI


# ==================== 第五类：日志与监控常量 ====================

class LoggingConstants:
    """
    日志管理与监控报警阈值常量
    来源文件：strategy_config/_bootstrap.py, stream_monitor.py, base_strategy.py, eod_reconcile/reconciler.py
    """

    # 日志保留策略（热存储，本地磁盘）- 30天热日志高频交易调试
    LOG_RETENTION_DAYS: Final[int] = _get_env_int(EnvVarKeys.LOG_RETENTION_DAYS, 30)

    # 错误日志保留（天，需满足审计要求）- 90天错误保留故障排查
    ERROR_LOG_RETENTION_DAYS: Final[int] = _get_env_int(EnvVarKeys.ERROR_RETENTION, 90)

    # 配置变更审计日志保留（天，长期审计）
    CONFIG_AUDIT_RETENTION_DAYS: Final[int] = _get_env_int_in_range(
        EnvVarKeys.CONFIG_AUDIT_RETENTION, 180, min_value=1, max_value=3650
    )

    # 冷存储归档保留年数（监管合规5年留痕）
    COLD_RETENTION_YEARS: Final[int] = _get_env_int_in_range(
        EnvVarKeys.COLD_RETENTION_YEARS, 5, min_value=1, max_value=20
    )

    # 日志轮转大小（MB）
    LOG_ROTATION_SIZE: Final[str] = _get_env_str(EnvVarKeys.LOG_ROTATION_SIZE, "10 MB")

    # 对账日志保留（天，合规要求更长）
    RECONCILE_LOG_RETENTION: Final[str] = _get_env_str(EnvVarKeys.RECONCILE_RETENTION, "90 days")

    # 日志压缩格式
    LOG_COMPRESSION: Final[str] = _get_env_str(EnvVarKeys.LOG_COMPRESSION, "zip")

    # Pending消息报警阈值（积压超过此值触发报警）
    PENDING_ALERT_THRESHOLD: Final[int] = _get_env_int_in_range(
        EnvVarKeys.MON_PENDING_THRESHOLD, 100, min_value=1, max_value=1000000
    )

    # 死信队列报警阈值（DLQ堆积超过此值触发报警）
    DLQ_ALERT_THRESHOLD: Final[int] = _get_env_int_in_range(
        EnvVarKeys.MON_DLQ_THRESHOLD, 10, min_value=1, max_value=1000000
    )

    # 延迟报警阈值（秒，Pending消息最大空闲时间）
    LATENCY_ALERT_THRESHOLD: Final[int] = _get_env_int_in_range(
        EnvVarKeys.MON_LATENCY_THRESHOLD, 60, min_value=1, max_value=36000
    )

    # 健康度历史样本数（滑动窗口大小）
    HEALTH_HISTORY_SIZE: Final[int] = _get_env_int_in_range(
        EnvVarKeys.MON_HEALTH_HISTORY, 100, min_value=1, max_value=100000
    )

    # 资金偏差报警阈值（元）
    CASH_DRIFT_ALERT_THRESHOLD: Final[float] = _get_env_float_in_range(
        EnvVarKeys.MON_CASH_DRIFT_THRESHOLD, 1000.0, min_value=0.0, max_value=1e9
    )

    # 日终对账最大Pending小时数（超过视为异常）
    MAX_PENDING_HOURS: Final[int] = _get_env_int_in_range(
        EnvVarKeys.RECON_MAX_PENDING_HOURS, 24, min_value=1, max_value=168
    )


class StreamObservabilityEvent:
    """
    结构化日志 context[\"event\"] 稳定取值（P2 观测面统一）。

    用于 Loki/ELK 等按 event 精确检索；勿随意改名。

    与其它观测出口分工：
    - **本类**：日志 `context[\"event\"]`（配合 `get_logger`）。
    - **探针**：`stream_monitor` HTTP（`/healthz`、`/ready` 等）。
    - **外呼告警**：`common.infra.alerter.dispatch_tiered_alert`。
    """

    # redis_stream_bridge
    FALLBACK_QUEUED: Final[str] = "FALLBACK_QUEUED"
    FALLBACK_QUEUE_READ: Final[str] = "FALLBACK_QUEUE_READ"
    FALLBACK_REPLAY_START: Final[str] = "FALLBACK_REPLAY_START"
    FALLBACK_REPLAY_BATCH: Final[str] = "FALLBACK_REPLAY_BATCH"
    FALLBACK_REPLAY_COMPLETE: Final[str] = "FALLBACK_REPLAY_COMPLETE"
    FALLBACK_RECORD_REMOVED: Final[str] = "FALLBACK_RECORD_REMOVED"
    FALLBACK_DELETE_FAILED: Final[str] = "FALLBACK_DELETE_FAILED"
    BRIDGE_DLQ_WRITTEN: Final[str] = "BRIDGE_DLQ_WRITTEN"
    REDIS_DEGRADED: Final[str] = "REDIS_DEGRADED"
    REDIS_RECOVERED: Final[str] = "REDIS_RECOVERED"
    REDIS_STREAM_SENT: Final[str] = "REDIS_STREAM_SENT"
    SIGNAL_SEND_FAILED: Final[str] = "SIGNAL_SEND_FAILED"
    BRIDGE_SEND_COMPLETED: Final[str] = "BRIDGE_SEND_COMPLETED"

    # executor_stream
    PEL_CLAIM_BATCH: Final[str] = "PEL_CLAIM_BATCH"
    EXEC_DLQ_MOVED: Final[str] = "EXEC_DLQ_MOVED"
    IDEMPOTENCY_TERMINAL_SKIP: Final[str] = "IDEMPOTENCY_TERMINAL_SKIP"
    IDEMPOTENCY_INPROGRESS_SKIP: Final[str] = "IDEMPOTENCY_INPROGRESS_SKIP"
    IDEMPOTENCY_ERROR_TERMINAL_SKIP: Final[str] = "IDEMPOTENCY_ERROR_TERMINAL_SKIP"
    IDEMPOTENCY_DIRTY_INPROGRESS: Final[str] = "IDEMPOTENCY_DIRTY_INPROGRESS"
    EXEC_MAX_RETRIES_DLQ: Final[str] = "EXEC_MAX_RETRIES_DLQ"
    EXEC_SUCCESS: Final[str] = "EXEC_SUCCESS"
    EXEC_FAILED: Final[str] = "EXEC_FAILED"
    EXEC_RETRY_BUMP: Final[str] = "EXEC_RETRY_BUMP"
    EXEC_LOG_MISSING: Final[str] = "EXEC_LOG_MISSING"
    EXEC_INIT_CONFIG_FAILED: Final[str] = "EXEC_INIT_CONFIG_FAILED"

    # qmt_client (pre-init buffer)
    QMT_PREINIT_BUFFER_FLUSH_FAILED: Final[str] = "QMT_PREINIT_BUFFER_FLUSH_FAILED"
    QMT_EMERGENCY_APPROVAL_MISSING: Final[str] = "QMT_EMERGENCY_APPROVAL_MISSING"
    QMT_EMERGENCY_MODE_ACTIVATED: Final[str] = "QMT_EMERGENCY_MODE_ACTIVATED"
    QMT_EMERGENCY_MODE_CLOSED: Final[str] = "QMT_EMERGENCY_MODE_CLOSED"

    # eod_reconcile CLI summary (optional)
    EOD_SUMMARY: Final[str] = "EOD_SUMMARY"

    # cross-domain data integrity governance (M.1-M.5) — Phase 0: register only
    DATA_INTEGRITY_NULL_FIELD: Final[str] = "DATA_INTEGRITY_NULL_FIELD"
    DATA_INTEGRITY_INVALID_VALUE: Final[str] = "DATA_INTEGRITY_INVALID_VALUE"
    DATA_INTEGRITY_TYPE_COERCION: Final[str] = "DATA_INTEGRITY_TYPE_COERCION"
    DATA_INTEGRITY_DECISION_BLOCKED: Final[str] = "DATA_INTEGRITY_DECISION_BLOCKED"


# Executor CSV SOP snapshot: callback-fill consumer counters (Monitor reads without grep).
CALLBACK_FILL_SOP_STAT_KEYS: Final[tuple[str, ...]] = (
    "callback_fill_processed_total",
    "callback_fill_persist_committed_total",
    "callback_fill_stale_partial_discarded_total",
    "callback_fill_persist_rejected_total",
    "callback_fill_validation_rejected_total",
    "callback_fill_db_verify_mismatch_total",
)


# ==================== 第六类：miniQMT 健康度评分常量 ====================

class HealthScoringConstants:
    """
    miniQMT连接健康度评分算法常量（P2级监控）
    来源文件：executor_stream/, stream_monitor.py, qmt_client.py

    注：确保 executor 与 monitor 统计口径完全一致，消除±20分差异
    """

    # 健康度评分阈值（0-100，低于此值视为亚健康）
    HEALTH_THRESHOLD: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_HEALTH_THRESHOLD, 70.0, min_value=0.0, max_value=100.0
    )

    # 健康度检查间隔（秒）
    HEALTH_CHECK_INTERVAL_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_HEALTH_CHECK_INTERVAL_SEC, 30.0, min_value=1.0, max_value=3600.0
    )

    # P99延迟告警阈值（毫秒）
    LATENCY_P99_THRESHOLD: Final[float] = _get_env_float_in_range(
        EnvVarKeys.QMT_LATENCY_P99_THRESHOLD, 500.0, min_value=1.0, max_value=60000.0
    )

    # 是否启用预防性重连
    PROACTIVE_RECONNECT: Final[bool] = _get_env_bool(EnvVarKeys.QMT_PROACTIVE_RECONNECT, True)

    # 成功率权重（40%）
    SUCCESS_RATE_WEIGHT: Final[float] = 0.4

    # 延迟权重（30%）
    LATENCY_WEIGHT: Final[float] = 0.3

    # 连续失败权重（30%）
    CONSECUTIVE_FAILURE_WEIGHT: Final[float] = 0.3

    # 延迟基准（ms，超过此值开始扣分）
    LATENCY_BASELINE_MS: Final[float] = 50.0

    # 延迟上限（ms，达到此值扣完延迟分数）
    LATENCY_MAX_MS: Final[float] = 100.0

    # 连续失败快速熔断阈值（次）
    CONSECUTIVE_FAIL_FAST: Final[int] = 3


# ==================== 第七类：性能监控与埋点常量（Phase 3 强制标准） ====================

class PerformanceConstants:
    """
    性能监控与指标收集常量（Phase 3 大爆炸重构版）
    来源文件：perf_monitor.py, generate_stock_selection.py, strategy_loader.py

    Phase 3 原则：强制启用（默认True），生产环境高频策略如需关闭通过编译时或配置中心控制，
    不支持运行时频繁开关（避免性能抖动）。
    """

    # 性能监控总开关（Phase 3默认强制启用，符合大爆炸重构原则）
    PERF_MONITOR_ENABLED: Final[bool] = _get_env_bool(EnvVarKeys.PERF_MONITOR_ENABLED, True)
    PERF_CRITICAL_LOG_AS_WARNING: Final[bool] = _get_env_bool(
        EnvVarKeys.PERF_CRITICAL_LOG_AS_WARNING, False
    )

    # 慢查询阈值（毫秒，超过此值记录警告）
    SLOW_QUERY_THRESHOLD_MS: Final[float] = _get_env_float_in_range(
        EnvVarKeys.PERF_SLOW_THRESHOLD, 500.0, min_value=1.0, max_value=600000.0
    )

    # API调用慢查询阈值（毫秒）
    SLOW_API_THRESHOLD_MS: Final[float] = _get_env_float_in_range(
        EnvVarKeys.PERF_SLOW_API_THRESHOLD, 100.0, min_value=1.0, max_value=600000.0
    )

    # 策略加载性能统计样本数（用于计算平均加载时间）
    LOAD_METRICS_SAMPLE_SIZE: Final[int] = _get_env_int_in_range(
        EnvVarKeys.PERF_LOAD_SAMPLE_SIZE, 100, min_value=1, max_value=100000
    )

    # 实时价格获取慢查询阈值（毫秒）
    PRICE_FETCH_SLOW_MS: Final[float] = _get_env_float_in_range(
        EnvVarKeys.PERF_PRICE_SLOW_MS, 200.0, min_value=1.0, max_value=600000.0
    )

    # 性能分级阈值（毫秒，与 PerfLevel 枚举对应）
    PERF_CRITICAL_MS: Final[int] = _get_env_int(EnvVarKeys.PERF_CRITICAL_MS, 50)  # P0 关键路径
    PERF_STRATEGY_MS: Final[int] = _get_env_int(EnvVarKeys.PERF_STRATEGY_MS, 100)  # P1 策略计算
    PERF_HIGH_MS: Final[int] = _get_env_int_in_range(EnvVarKeys.PERF_HIGH_MS, 200, min_value=1, max_value=600000)  # P2 高频操作
    PERF_NORMAL_MS: Final[int] = _get_env_int_in_range(EnvVarKeys.PERF_NORMAL_MS, 500, min_value=1, max_value=600000)  # P3 普通操作
    # P4：默认 1200ms 使 2×阈值=2400ms，覆盖 Runner 冷启动（Redis 首连 + ExecutionRecorder）常见墙钟
    PERF_LOW_MS: Final[int] = _get_env_int_in_range(EnvVarKeys.PERF_LOW_MS, 1200, min_value=1, max_value=600000)  # P4 后台 / 启动重路径


# ==================== 第八类：策略加载与管理常量 ====================

class StrategyConstants:
    """
    策略加载器、选股模块及策略基类技术常量
    来源文件：strategy_loader.py, generate_stock_selection.py, base_strategy.py, etf_rotation.py
    """

    # 策略文件扫描排除前缀（以下划线开头的文件）- 源自 strategy_loader.py
    STRATEGY_FILE_EXCLUDE_PREFIX: Final[str] = "_"

    # 策略类名后缀（用于自动模块映射）
    STRATEGY_CLASS_SUFFIX: Final[str] = "Strategy"

    # 策略加载重试次数
    STRATEGY_LOAD_RETRY: Final[int] = _get_env_int_in_range(
        EnvVarKeys.STRATEGY_LOAD_RETRY, 3, min_value=0, max_value=20
    )

    # 选股结果保存重试次数
    SELECTION_SAVE_RETRY: Final[int] = _get_env_int_in_range(
        EnvVarKeys.SELECTION_SAVE_RETRY, 3, min_value=0, max_value=20
    )

    # 策略缓存默认TTL（秒，None表示永不过期）
    STRATEGY_CACHE_TTL: Final[int | None] = _get_env_int_in_range(
        EnvVarKeys.STRATEGY_CACHE_TTL, 0, min_value=0, max_value=86400
    ) or None

    # ETF轮动策略默认回归周期 - 源自 etf_rotation.py: reg_num = 25
    ETF_ROTATION_REG_NUM: Final[int] = _get_env_int_in_range(
        EnvVarKeys.ETF_ROTATION_REG_NUM, 25, min_value=1, max_value=1000
    )

    # ETF轮动策略最少ETF数量（低于此数量触发风控）- 源自 etf_rotation.py: min_etf_required = 2
    MIN_ETF_REQUIRED: Final[int] = _get_env_int_in_range(
        EnvVarKeys.ETF_MIN_REQUIRED, 2, min_value=1, max_value=100
    )

    # 策略实例健康检查：实例最大年龄（小时）- 源自 base_strategy.py: age_hours > 24
    # 超过此值视为潜在内存泄漏风险，建议重启实例
    STRATEGY_HEALTH_MAX_AGE_HOURS: Final[int] = _get_env_int_in_range(
        EnvVarKeys.STRATEGY_HEALTH_MAX_AGE, 24, min_value=1, max_value=8760
    )

    # 策略实例健康检查：近期错误窗口（秒）- 源自 base_strategy.py: time.time() - last_error_time < 300
    # 5分钟内有错误视为亚健康状态
    STRATEGY_HEALTH_ERROR_WINDOW_SEC: Final[int] = _get_env_int_in_range(
        EnvVarKeys.STRATEGY_HEALTH_ERROR_WINDOW, 300, min_value=1, max_value=86400
    )

    # ETF轮动策略：RSRS得分风控阈值 - 源自 etf_rotation.py: risk_off_threshold = 0.0
    # 当最高得分ETF的RSRS得分低于此值时，触发风控返回空仓（['flat']）
    ETF_RISK_OFF_THRESHOLD: Final[float] = _get_env_float_in_range(
        EnvVarKeys.ETF_RISK_OFF_THRESHOLD, 0.0, min_value=-10.0, max_value=10.0
    )

    # ETF轮动策略：默认ETF标的池 - 源自 etf_rotation.py: etf_libs 默认值
    # 支持通过环境变量 ETF_DEFAULT_UNIVERSE 以逗号分隔格式覆盖，如 "510180.SH,510050.SH"
    ETF_DEFAULT_UNIVERSE: Final[List[str]] = _get_env_list(
        EnvVarKeys.ETF_DEFAULT_UNIVERSE,
        ['510180.SH', '159915.SZ', '513100.SH', '518880.SH']
    )

    # ETF轮动策略：默认ETF名称映射表 - 源自 etf_rotation.py: DEFAULT_ETF_NAMES
    # 支持通过环境变量 ETF_DEFAULT_NAMES 以JSON格式覆盖
    ETF_DEFAULT_NAMES: Final[Dict[str, str]] = _get_env_json(
        EnvVarKeys.ETF_DEFAULT_NAMES,
        {
            '510180.SH': '上证180ETF',
            '159915.SZ': '创业板ETF',
            '513100.SH': '纳指ETF',
            '518880.SH': '黄金ETF'
        }
    )


# ==================== 第九类：主循环与调度常量 ====================

class SchedulingConstants:
    """
    主循环调度与定时任务常量（非交易时间窗配置）。

    交易时间窗（SESSION / ROUTINE_BUY_WINDOW / CLOSE_CANCEL / REBALANCE / EOD）
    的权威来源为 ``strategy_config.TRADING_SESSION_SCHEDULE``。

    来源文件：live_trading.py, stream_monitor.py, eod_reconcile/reconciler.py
    """

    # 主循环默认休眠间隔（秒）
    MAIN_LOOP_INTERVAL_SEC: Final[int] = _get_env_int_in_range(
        EnvVarKeys.SCHED_MAIN_LOOP_INTERVAL_SEC, 60, min_value=1, max_value=3600
    )

    # EOD / REBALANCE wall times: use strategy_config.TRADING_SESSION_SCHEDULE at runtime.
    # (Removed EOD_UPDATE_HOUR/MINUTE and REBALANCE_HOUR/MINUTE — 2026-06-03 refactor.)

    # 监控状态报告间隔（秒）
    MONITOR_STATUS_INTERVAL_SEC: Final[int] = _get_env_int_in_range(
        EnvVarKeys.SCHED_MONITOR_STATUS, 300, min_value=1, max_value=86400
    )

    # 监控性能报告间隔（秒）
    MONITOR_PERF_INTERVAL_SEC: Final[int] = _get_env_int_in_range(
        EnvVarKeys.SCHED_MONITOR_PERF, 600, min_value=1, max_value=86400
    )

    # 对账执行时间（HH:MM格式，走统一 RECONCILE_TIME 键）
    RECONCILE_TIME: Final[str] = _get_env_str(EnvVarKeys.RECONCILE_TIME, "15:35")

    # 热重载检查间隔（秒）
    HOT_RELOAD_INTERVAL_SEC: Final[int] = _get_env_int_in_range(
        EnvVarKeys.SCHED_RELOAD_INTERVAL_SEC, 60, min_value=1, max_value=86400
    )

    # 涨停检查收盘后超时（秒）：check_time 落在 session 之外时，asyncio.wait_for 超时。
    # 防止 event loop 被 asyncio.to_thread block 住（pythonw monitor daemon CPU 满载时
    # QMT xtdata 响应变慢，导致 Redis qmt_ops block-poll 超长）。
    # ref: 2026-06-11 incident — monitor daemon CPU 99.4% + get_limit_info block.
    LIMIT_UP_CHECK_POST_CLOSE_TIMEOUT_SEC: Final[int] = _get_env_int_in_range(
        EnvVarKeys.SCHED_LIMIT_UP_POST_CLOSE_TIMEOUT_SEC, 30, min_value=5, max_value=300
    )

    # 关闭时 routine_close_cancel 超时（秒）：shutdown 路径的兜底撤单超时。
    # 防止 event-loop 阻塞错过 close-cancel 窗口后，遗留 SUBMITTED 单至次日。
    # ref: 2026-06-11 incident — routine_close_cancel missed due to event-loop blocking.
    SHUTDOWN_CLOSE_CANCEL_TIMEOUT_SEC: Final[int] = _get_env_int_in_range(
        EnvVarKeys.SCHED_SHUTDOWN_CLOSE_CANCEL_TIMEOUT_SEC, 15, min_value=5, max_value=120
    )


# ==================== 第十类：StreamMonitor FastAPI 服务常量（Phase 3 增强） ====================

class StreamMonitorConstants:
    """
    StreamMonitor FastAPI 异步监控服务常量（Phase 3 生产级增强）
    来源文件：stream_monitor.py

    设计目标：确保健康检查接口 SLA < 50ms，不阻塞交易线程
    """

    # 服务监听端口
    PORT: Final[int] = _get_env_int_in_range(
        EnvVarKeys.MONITOR_PORT, 8080, min_value=1, max_value=65535
    )

    # 服务监听主机（0.0.0.0允许容器外部访问）
    HOST: Final[str] = _get_env_str(EnvVarKeys.MONITOR_HOST, "0.0.0.0")

    # K8s Liveness探针超时（毫秒，严格<50ms）
    LIVENESS_TIMEOUT_MS: Final[float] = _get_env_float_in_range(
        EnvVarKeys.MON_LIVENESS_TIMEOUT_MS, 50.0, min_value=1.0, max_value=5000.0
    )

    # K8s Readiness探针超时（毫秒，允许稍长但<100ms）
    READINESS_TIMEOUT_MS: Final[float] = _get_env_float_in_range(
        EnvVarKeys.MON_READINESS_TIMEOUT_MS, 100.0, min_value=1.0, max_value=10000.0
    )

    # 持仓查询接口超时（秒，较重操作）
    POSITION_QUERY_TIMEOUT_SEC: Final[float] = _get_env_float_in_range(
        EnvVarKeys.MON_POSITION_TIMEOUT_SEC, 5.0, min_value=0.1, max_value=60.0
    )

    # 线程池工作线程数（用于执行同步QMT查询，隔离事件循环）
    WORKER_THREADS: Final[int] = _get_env_int_in_range(
        EnvVarKeys.MONITOR_WORKERS, 2, min_value=1, max_value=128
    )

    # 是否启用Swagger文档（生产环境建议关闭）
    ENABLE_DOCS: Final[bool] = _get_env_bool(EnvVarKeys.MONITOR_ENABLE_DOCS, False)

    # Phase 3 新增：K8s探针端点路径（标准化）
    LIVENESS_PATH: Final[str] = "/healthz"
    READINESS_PATH: Final[str] = "/ready"
    METRICS_PATH: Final[str] = "/metrics"

    # Phase 3 新增：CORS白名单（逗号分隔，空字符串表示禁用CORS）
    CORS_ORIGINS: Final[str] = _get_env_str(EnvVarKeys.MONITOR_CORS_ORIGINS, "")

    # Phase 3 新增：API安全（简单Token认证，空字符串表示禁用）
    API_AUTH_TOKEN_ENV: Final[str] = EnvVarKeys.MONITOR_API_TOKEN


# ==================== 第十一类：Trace ID 与全链路追踪常量（与 trace_context 严格对齐） ====================

class TraceConstants:
    """
    全链路追踪与审计ID生成常量
    来源文件：common/infra/trace_context.py（TraceIdGenerator）、全系统各模块

    Phase 3 强制规范：
    - 严格24字符：{PREFIX:<6}_{YYYYMMDD}_{RANDOM:8}
    - 前缀映射单一真相源为本类 ``TRACE_PREFIXES``；TraceIdGenerator 运行时从此处读取
    - 禁止手动传入Trace ID，必须从 contextvars 获取
    """

    # Trace ID标准长度（字符）
    TRACE_ID_LENGTH: Final[int] = 24

    # 前缀长度（6字符，左对齐）
    TRACE_PREFIX_LENGTH: Final[int] = 6

    # 日期部分格式（8字符）
    TRACE_DATE_FORMAT: Final[str] = "%Y%m%d"

    # 随机码长度（8字符十六进制）
    TRACE_RANDOM_LENGTH: Final[int] = 8

    # 各模块前缀映射（必须严格6字符以内；生成时截断后右补 "0" 到 6 字符）
    TRACE_PREFIXES: Final[Dict[str, str]] = {
        'selector': 'SEL',  # 选股模块 (generate_stock_selection)
        'rebalance': 'REBAL',  # 调仓模块 (live_trading)
        'bridge': 'BRIDGE',  # Redis桥接 (redis_stream_bridge)
        'executor': 'EXEC',  # 执行器 (executor_stream)
        'reconcile': 'RECON',  # 日终对账 (eod_reconcile)
        'hkcodex': 'HKQ',  # miniQMT适配 (hkcodex_miniqmt, qmt_client)
        'config': 'CFG',  # 配置管理 (strategy_config)
        'monitor': 'MON',  # 监控面板 (stream_monitor)
        'loader': 'LOAD',  # 策略加载 (strategy_loader)
        'strategy': 'STRAT',  # 策略基类 (base_strategy)
        'query': 'QUERY',  # 查询操作 (generic query)
        'limitup': 'LMTUP',  # 涨停检查 (limit_up check)
        'trade': 'TRADE',  # 交易执行 (trade execution)
        'audit': 'AUDIT',  # 审计操作 (audit operations)
        'risk': 'RISK',  # 风控检查 (risk control)
        'system': 'SYSTEM',  # 系统级 (system level)
        'init_schema': 'INIT',  # Gateway DDL / 启动幂等建表（RouteDecision 专用，非业务信号）
        'check_fills': 'FILL',  # 执行器周期成交核对批量任务（独立 trace，避免误挂 Stream 消息）
        'pytest': 'TEST',  # 集成/压力测试专用前缀（如 test_production_readiness）
    }
    # 模块名别名（兼容历史/简写调用；值必须指向 TRACE_PREFIXES 的 canonical key）
    TRACE_MODULE_ALIASES: Final[Dict[str, str]] = {
        "mon": "monitor",
        "exec": "executor",
        "sig": "system",
        "ops": "executor",
        "riskrt": "risk",
        "eod": "reconcile",
    }

    # 环境变量名（用于强制设置Trace ID上下文）
    TRACE_ID_ENV_VAR: Final[str] = "QUANT_TRACE_ID"


# ==================== 第十二类：安全与合规常量（Phase 3 新增） ====================

class SecurityConstants:
    """
    金融级安全与合规常量（满足《证券期货业数据安全标准》Tier-3）
    来源文件：security.py, quant_logger.py, exceptions.py

    Phase 3 新增：集中管理安全策略参数，确保全系统脱敏与审计一致性
    """

    # 敏感词库扩展环境变量名（供DataMasker使用）
    SENSITIVE_KEYWORDS_ENV: Final[str] = EnvVarKeys.SENSITIVE_KEYWORDS_ENV

    # 运行环境标识（prod/dev/test），影响安全策略严格程度
    ENV_KEY: Final[str] = EnvVarKeys.QUANT_ENV
    DEFAULT_ENV: Final[str] = "prod"

    # 账户ID脱敏规则：前3后3，中间掩码长度
    ACCOUNT_MASK_PREFIX_LEN: Final[int] = 3
    ACCOUNT_MASK_SUFFIX_LEN: Final[int] = 3
    ACCOUNT_MASK_MIN_LENGTH: Final[int] = 8  # 小于此长度使用特殊处理

    # 路径脱敏保留层级（默认保留最后2级目录）
    PATH_MASK_LEVELS: Final[int] = 2

    # 配置变更审计保留天数（与LoggingConstants对齐）
    CONFIG_AUDIT_RETENTION_DAYS: Final[int] = LoggingConstants.CONFIG_AUDIT_RETENTION_DAYS

    # 敏感数据检测正则（用于自动化审计扫描）
    SENSITIVE_PATTERNS: Final[Dict[str, str]] = {
        'password': r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\']+',
        'secret_key': r'(?i)(secret|private_key)\s*[=:]\s*["\']?[^\s"\']{16,}',
        'api_key': r'(?i)(api_key|access_key)\s*[=:]\s*["\']?[A-Za-z0-9]{16,}',
        'account_id': r'\b\d{12,}\b',  # 12位以上数字序列（疑似账户ID）
    }


# ==================== 第十三类：多账户管理常量（Phase 3 新增） ====================

class MultiAccountConstants:
    """
    多账户管理常量（支持自营+资管并行）
    来源文件：qmt_client.py（QMTConnectionManager多账户字典模式）

    Phase 3 新增：支持多账户隔离与资源配额管理
    """

    # 多账户列表环境变量（逗号分隔，如"account1,account2,account3"）
    ACCOUNT_LIST_ENV: Final[str] = EnvVarKeys.ACCOUNT_ID_LIST

    # 默认账户ID（单账户模式下的fallback）
    DEFAULT_ACCOUNT_ENV: Final[str] = EnvVarKeys.DEFAULT_ACCOUNT_ID

    # 账户ID分隔符（用于解析ACCOUNT_LIST_ENV）
    ACCOUNT_ID_SEPARATOR: Final[str] = ","

    # 最大支持账户数（防止配置错误导致资源耗尽）
    MAX_ACCOUNTS_TOTAL: Final[int] = 10

    # 账户级资源隔离：每个账户独立的健康度检查间隔（秒）
    PER_ACCOUNT_HEALTH_INTERVAL_SEC: Final[float] = 30.0

    # 跨账户操作超时（如批量查询所有账户持仓）
    CROSS_ACCOUNT_TIMEOUT_SEC: Final[int] = 30


# ==================== 便捷导入别名（简化业务代码引用） ====================

# QMT与交易高频常量
BATCH_SIZE = QMTConstants.BATCH_SIZE
PRICE_TOLERANCE = QMTConstants.PRICE_TOLERANCE
CACHE_TIMEOUT_SEC = QMTConstants.PRICE_CACHE_TIMEOUT_SEC
MIN_COMMISSION = TradingConstants.MIN_COMMISSION
LOT_SIZE = TradingConstants.LOT_SIZE
LIMIT_UP_OPEN_THRESHOLD = TradingConstants.LIMIT_UP_OPEN_THRESHOLD
CASH_FUSE_THRESHOLD = TradingConstants.CASH_FUSE_THRESHOLD
MAX_RECONNECT_RETRY = QMTConstants.MAX_OPERATION_RETRY
MAX_RECONNECT_24H = QMTConstants.MAX_RECONNECT_24H
MAX_CONN_PER_ACCOUNT = QMTConstants.MAX_CONCURRENT_CONNECTIONS_PER_ACCOUNT
CONNECTION_SLOT_TIMEOUT_SEC = QMTConstants.CONNECTION_SLOT_TIMEOUT_SEC
PING_INTERVAL_SEC = QMTConstants.PING_INTERVAL_SEC
SESSION_STALE_SEC = QMTConstants.SESSION_STALE_SEC
SQLITE_TIMEOUT_SEC = PersistenceConstants.SQLITE_TIMEOUT_SEC
SQLITE_WAL_MODE = _get_env_bool(EnvVarKeys.SQLITE_WAL_MODE, True)
SQLITE_WAL_AUTOCHECKPOINT = PersistenceConstants.SQLITE_WAL_AUTOCHECKPOINT
COLD_STORAGE_ENABLED = PersistenceConstants.COLD_STORAGE_ENABLED
HOT_DATA_RETENTION_DAYS = PersistenceConstants.HOT_DATA_RETENTION_DAYS
DB_MAX_RETRIES = PersistenceConstants.DB_MAX_RETRIES

# 日志与监控高频常量
LOG_RETENTION_DAYS = LoggingConstants.LOG_RETENTION_DAYS
ERROR_LOG_RETENTION_DAYS = LoggingConstants.ERROR_LOG_RETENTION_DAYS
COLD_RETENTION_YEARS = LoggingConstants.COLD_RETENTION_YEARS
CONFIG_AUDIT_RETENTION_DAYS = LoggingConstants.CONFIG_AUDIT_RETENTION_DAYS  # [P1补全] 金融合规：配置变更审计180天留痕
HEALTH_THRESHOLD = HealthScoringConstants.HEALTH_THRESHOLD

# 追踪与性能高频常量
TRACE_ID_LENGTH = TraceConstants.TRACE_ID_LENGTH
PERF_MONITOR_ENABLED = PerformanceConstants.PERF_MONITOR_ENABLED
PERF_CRITICAL_LOG_AS_WARNING = PerformanceConstants.PERF_CRITICAL_LOG_AS_WARNING

# 性能分级阈值（Phase 3 新增导出，供 perf_monitor.py 使用）
PERF_CRITICAL_MS = PerformanceConstants.PERF_CRITICAL_MS
PERF_STRATEGY_MS = PerformanceConstants.PERF_STRATEGY_MS
PERF_HIGH_MS = PerformanceConstants.PERF_HIGH_MS
PERF_NORMAL_MS = PerformanceConstants.PERF_NORMAL_MS
PERF_LOW_MS = PerformanceConstants.PERF_LOW_MS

# 策略层高频常量（ETF轮动）
ETF_ROTATION_REG_NUM = StrategyConstants.ETF_ROTATION_REG_NUM
MIN_ETF_REQUIRED = StrategyConstants.MIN_ETF_REQUIRED
ETF_RISK_OFF_THRESHOLD = StrategyConstants.ETF_RISK_OFF_THRESHOLD
ETF_DEFAULT_UNIVERSE = StrategyConstants.ETF_DEFAULT_UNIVERSE
ETF_DEFAULT_NAMES = StrategyConstants.ETF_DEFAULT_NAMES
STRATEGY_HEALTH_MAX_AGE_HOURS = StrategyConstants.STRATEGY_HEALTH_MAX_AGE_HOURS
STRATEGY_HEALTH_ERROR_WINDOW_SEC = StrategyConstants.STRATEGY_HEALTH_ERROR_WINDOW_SEC

# Phase 3 新增：国金miniQMT高频常量（供qmt_client直接使用）
SESSION_ID_MIN = QMTConstants.SESSION_ID_MIN
SESSION_ID_MAX = QMTConstants.SESSION_ID_MAX
XTDATA_INIT_MAX_RETRY = QMTConstants.XTDATA_INIT_MAX_RETRY
RECONNECT_LOG_PATH = QMTConstants.RECONNECT_LOG_DEFAULT_PATH

# Phase 3 新增：安全与多账户高频常量
SENSITIVE_KEYWORDS_ENV = SecurityConstants.SENSITIVE_KEYWORDS_ENV
MAX_ACCOUNTS_TOTAL = MultiAccountConstants.MAX_ACCOUNTS_TOTAL

# [审查报告2.1节补全 - Week 4 P1修复] 调度高频常量（供 live_trading.py 等业务层直接导入）
# 确保与 common/__init__.py 中 _LAYER2_SCHEDULING 严格对齐
MAIN_LOOP_INTERVAL_SEC = SchedulingConstants.MAIN_LOOP_INTERVAL_SEC
# EOD_UPDATE: now parsed from EOD_UPDATE_TIME (HH:MM format)
# REBALANCE: now parsed from REBALANCE_TIME (HH:MM format)
# LIMIT_UP_CHECK_HOUR/MINUTE removed (dead code)
MONITOR_STATUS_INTERVAL_SEC = SchedulingConstants.MONITOR_STATUS_INTERVAL_SEC
RECONCILE_TIME = SchedulingConstants.RECONCILE_TIME
# NOTE: wall-clock timeout constants below are intentionally kept as
# SchedulingConstants class attributes only. They are not re-exported as
# module-level aliases or via common/_pep562_package_exports.py because their
# semantics are timeout durations, not wall-clock schedule times.
# See scripts/verify_constants_export_sync.py _SCHEDULING_ALLOWED.


# 导出类供精细引用（如 constants.QMTConstants.BATCH_SIZE）
__all__ = [
    # 环境工具（公开 API：多键解析与键名枚举；具体 _get_env_* 为模块内部实现）
    'resolve_env_int_first',
    'iter_registered_env_var_keys',

    # 常量类（精细引用）
    'EnvVarKeys',
    'ErrorCode',
    'QMTConstants',
    'TradingConstants',
    'RedisConstants',
    'PersistenceConstants',
    'LoggingConstants',
    'StreamObservabilityEvent',
    'CALLBACK_FILL_SOP_STAT_KEYS',
    'HealthScoringConstants',
    'PerformanceConstants',
    'StrategyConstants',
    'SchedulingConstants',
    'StreamMonitorConstants',
    'TraceConstants',
    'SecurityConstants',
    'MultiAccountConstants',

    # 便捷别名（高频使用）
    'BATCH_SIZE',
    'PRICE_TOLERANCE',
    'CACHE_TIMEOUT_SEC',
    'MIN_COMMISSION',
    'LOT_SIZE',
    'LIMIT_UP_OPEN_THRESHOLD',
    'CASH_FUSE_THRESHOLD',
    'MAX_RECONNECT_RETRY',
    'MAX_RECONNECT_24H',
    'MAX_CONN_PER_ACCOUNT',
    'CONNECTION_SLOT_TIMEOUT_SEC',
    'PING_INTERVAL_SEC',
    'SESSION_STALE_SEC',
    'SQLITE_TIMEOUT_SEC',
    'SQLITE_WAL_MODE',
    'SQLITE_WAL_AUTOCHECKPOINT',
    'COLD_STORAGE_ENABLED',
    'HOT_DATA_RETENTION_DAYS',
    'DB_MAX_RETRIES',
    'LOG_RETENTION_DAYS',
    'ERROR_LOG_RETENTION_DAYS',
    'COLD_RETENTION_YEARS',
    'CONFIG_AUDIT_RETENTION_DAYS',  # [P1补全] 金融合规：配置变更审计180天留痕
    'HEALTH_THRESHOLD',
    'TRACE_ID_LENGTH',
    'PERF_MONITOR_ENABLED',
    'PERF_CRITICAL_LOG_AS_WARNING',

    # 性能分级阈值（perf_monitor.py 依赖）
    'PERF_CRITICAL_MS',
    'PERF_STRATEGY_MS',
    'PERF_HIGH_MS',
    'PERF_NORMAL_MS',
    'PERF_LOW_MS',

    # Phase 3 新增：国金miniQMT特定导出
    'SESSION_ID_MIN',
    'SESSION_ID_MAX',
    'XTDATA_INIT_MAX_RETRY',
    'RECONNECT_LOG_PATH',

    # Phase 3 新增：安全与多账户导出
    'SENSITIVE_KEYWORDS_ENV',
    'MAX_ACCOUNTS_TOTAL',

    # 策略层别名
    'ETF_ROTATION_REG_NUM',
    'MIN_ETF_REQUIRED',
    'ETF_RISK_OFF_THRESHOLD',
    'ETF_DEFAULT_UNIVERSE',
    'ETF_DEFAULT_NAMES',
    'STRATEGY_HEALTH_MAX_AGE_HOURS',
    'STRATEGY_HEALTH_ERROR_WINDOW_SEC',

    # [审查报告2.1节补全 - Week 4 P1修复] 调度层高频别名（与_LAYER2_SCHEDULING严格对齐）
    # 支持 live_trading.py 等业务模块通过 `from common import MAIN_LOOP_INTERVAL_SEC` 直接访问
    'MAIN_LOOP_INTERVAL_SEC',           # live_trading.py 主循环间隔（秒）
    # EOD_UPDATE_TIME / REBALANCE_TIME: strategy_config (TRADING_SESSION_SCHEDULE)
    'MONITOR_STATUS_INTERVAL_SEC',      # 监控状态报告间隔（秒）
    'RECONCILE_TIME',               # 对账执行时间（HH:MM格式）
    # NOTE: timeout constants such as LIMIT_UP_CHECK_POST_CLOSE_TIMEOUT_SEC and
    # SHUTDOWN_CLOSE_CANCEL_TIMEOUT_SEC are SchedulingConstants class attributes
    # only; they are not top-level re-exports.
]

# 在 constants.py 文件末尾添加自检，确保 TRACE_PREFIXES 包含国金特定键
assert 'hkcodex' in TraceConstants.TRACE_PREFIXES, "国金miniQMT前缀缺失"
assert TraceConstants.TRACE_PREFIXES['hkcodex'] == 'HKQ'
