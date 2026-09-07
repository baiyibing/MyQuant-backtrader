# -*- coding: utf-8 -*-
"""
common/infra/exceptions.py - 金融级异常体系 (Financial-Grade Exception Hierarchy - Phase 3 Layer 1 Converged + P0 Emergency Fix + Week 4 Layer 2.5 Enhancement)
================================================================================

**Phase 3 P0级热修复（紧急止血）**：
- **[新增] 递归防护机制**：线程级 `_thread_local.writing_audit_log` 标志，防止审计日志写入引发的死循环
- **[新增] 启动期降级策略**：当 `QuantLoggerFactory` 未初始化时，直接输出至 `stderr` 而非抛出新的 `ConfigurationError`，避免递归崩溃
- **[保持] 金融级合规**：即使降级到 `stderr`，仍强制记录错误代码、严重级别与Trace ID，满足可追溯黄金准则

**Phase 3 异常分层增强（本次修改）**：
- **[新增] TradingExecutionError**：交易执行层异常（订单委托、成交回报、交易确认失败）
- **[新增] StrategyExecutionError**：策略执行层异常（选股、仓位计算、组合记录、日终对账失败）

**Week 4 修复（本次提交）**：
- **[P1 Fixed] 错误码命名对齐**：`ORDER_CALLBACK_FAILED` → `TRADE_ORDER_CALLBACK_FAILED` (TRADE_009)
- **[P1 Fixed] 错误码命名对齐**：`TRADE_CALLBACK_FAILED` → `TRADE_TRADE_CALLBACK_FAILED` (TRADE_010)
- **[新增] ExecutionRecorderError**：Layer 2.5 执行记录器专用异常（miniQMT C++回调缓冲层）

**Week 4 Layer 2.5 增强说明**：
- ExecutionRecorderError 专门处理 C++ 回调线程的异常，确保：
  1. 队列溢出时自动降级至同步写入（数据不丢失）
  2. 初始化失败时触发 P0 级审计（内存分配或线程创建失败）
  3. 与 DatabaseError 区分（Layer 2.5 独立不经过 Gateway）

**修复背景**：
原 `QuantException._write_audit_log()` 在 Logger 未初始化时会抛出 `ConfigurationError`（继承自 `QuantException`），
导致 `__init__` → `_write_audit_log` → 抛出 `ConfigurationError` → `__init__` 的无限递归，直至 C 栈溢出。
本修复确保任何情况下（包括系统启动期）异常审计绝不丢失、绝不阻塞、绝不递归。

**架构层级**：保持不变（Layer 1，依赖 Layer 0 常量与延迟导入 Layer 2）
"""

import sys
import os
import traceback
import hashlib
import json
import threading  # P0 Fix: 导入线程局部存储用于递归防护
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict

# P0 Fix: 线程级递归防护锁（防止 _write_audit_log 同线程重入导致的死循环）
_thread_local = threading.local()

# ==============================================================================
# Phase 3: Layer 1 基础设施导入（模块级直接导入 Layer 0 常量，无延迟）
# ==============================================================================

# Layer 0 常量单一真相源（零依赖层）- 模块级直接导入，符合"常量零延迟"原则
from .constants import (
    ErrorCode,  # [优化] 模块级直接导入（Layer 0 常量，无循环风险，减少运行时开销）
    MAX_RECONNECT_24H,  # 24小时重连限制（国金内存泄漏防护）
    MAX_CONN_PER_ACCOUNT,  # 单账户连接上限
    CONNECTION_SLOT_TIMEOUT_SEC,  # 槽位等待超时
    EnvVarKeys,  # 环境变量键名（含QMT_EMERGENCY_MODE）
)
from .timekeeping import utc_now_iso_z


# ==============================================================================
# 延迟导入辅助函数（避免循环依赖 - 指向 Layer 0 trace_context）
# ==============================================================================

def _get_trace_context() -> str:
    """
    延迟获取 Trace ID（从 trace_context Layer 0 直接获取，避免 Layer 1->Layer 2 反向依赖）

    符合中国A股量化交易系统黄金准则：Trace ID 基础设施位于 Layer 0（零依赖层），
    确保在 quant_logger（Layer 2）初始化前即可安全获取上下文。

    Returns:
        str: 当前协程上下文的 Trace ID（24字符规范），若不可用则返回临时降级 ID
    """
    try:
        # [Phase 3] 从 Layer 0 trace_context 导入，而非 Layer 2 quant_logger
        from .trace_context import get_trace_context as _ctx_getter
        return _ctx_getter()
    except (ImportError, LookupError):
        # 降级：生成带时间戳+随机数的临时 24 字符 ID，避免所有降级异常共享同一 ID
        import time, random
        ts = time.strftime("%Y%m%d")
        rand = f"{random.randint(0, 99999999):08X}"
        return f"DEGRAD_{ts}_{rand}"


def _get_data_masker():
    """延迟获取 DataMasker 类（避免循环导入 security）"""
    from .security import DataMasker
    return DataMasker


def _get_logger_factory():
    """延迟获取 QuantLoggerFactory（避免循环导入 quant_logger）"""
    from .quant_logger import QuantLoggerFactory
    return QuantLoggerFactory


def _in_loguru_queue_writer() -> bool:
    """
    Detect loguru queue-consumer context.

    Logging again from loguru's own queued writer thread can deadlock because
    emit() re-enters handler locks. In that context we must degrade to stderr.
    """
    try:
        cur = threading.current_thread()
        name = (cur.name or "").lower()
        if "loguru" in name and "writer" in name:
            return True
        for frame in traceback.extract_stack(limit=20):
            fn = (frame.filename or "").replace("/", "\\").lower()
            if fn.endswith("loguru\\_handler.py") and frame.name == "_queued_writer":
                return True
    except Exception:
        return False
    return False


# ==============================================================================
# 异常上下文数据类（支持序列化与审计）
# ==============================================================================

@dataclass
class ExceptionContext:
    """
    异常上下文数据类（Phase 3 强化版 - 延迟导入兼容）

    支持审计日志自动挂载，包含国金miniQMT特定的上下文（如槽位信息、重连计数）
    """
    # 使用延迟导入辅助函数作为默认工厂（Layer 0 收敛后仍保持延迟获取）
    trace_id: str = field(default_factory=lambda: str(_get_trace_context()))
    timestamp: str = field(default_factory=utc_now_iso_z)
    module: Optional[str] = None
    func: Optional[str] = None
    account_id: Optional[str] = None  # 存储原始值，脱敏在序列化时处理
    extra: Dict[str, Any] = field(default_factory=dict)
    error_chain: List[str] = field(default_factory=list)

    # Phase 3 新增：审计增强字段（合规要求：Who & Why）
    operator_id: str = "system"  # 操作者身份（合规要求：Who）
    approval_ticket: str = "auto"  # 审批单号（合规要求：Why）
    session_id: Optional[str] = None  # 会话标识

    # 国金miniQMT特定上下文
    reconnect_count_24h: Optional[int] = None  # 24小时重连计数
    connection_slot_info: Optional[Dict] = None  # 槽位使用情况
    emergency_mode: bool = False  # 是否处于紧急模式

    def to_dict(self, mask_sensitive: bool = True) -> Dict[str, Any]:
        """转换为字典（支持脱敏与ELK索引）"""
        data = asdict(self)

        # 账户ID脱敏（金融级标准：前3后3）- 延迟导入 DataMasker
        if mask_sensitive and self.account_id:
            try:
                DataMasker = _get_data_masker()
                data['account_id'] = DataMasker.mask_account_id(self.account_id)
            except Exception:
                data['account_id'] = "****MASK_FAIL****"

        # 清理None值（节省存储）
        data = {k: v for k, v in data.items() if v is not None}

        return data

    def to_json(self, mask_sensitive: bool = True) -> str:
        """JSON序列化（供ELK索引）"""
        return json.dumps(self.to_dict(mask_sensitive), ensure_ascii=False, default=str)


# ==============================================================================
# 基类：QuantException（所有金融异常基类 - P0修复版）
# ==============================================================================

class QuantException(Exception):
    """
    全系统异常基类（金融级 - Phase 3 强制标准 + P0递归防护）

    **核心特性**：
    1. **Trace ID强制规范**：24字符，自动从contextvars获取（协程安全，现通过 Layer 0 trace_context）
    2. **自动脱敏**：异常消息中的账户ID、密码等自动脱敏
    3. **结构化输出**：支持to_dict()直接入ELK，无需额外处理
    4. **国金适配**：支持标记 `fail_open`（紧急模式绕过）与 `reconnect_count`
    5. **零开销审计**：可选自动审计日志（audit_immediate=True）
    6. **P0级递归防护**：通过 `_thread_local.writing_audit_log` 确保审计失败绝不引发递归崩溃

    **使用约束**：
    - 禁止手动传入trace_id（必须从contextvars自动获取，现统一由 Layer 0 提供）
    - 所有敏感字段必须通过extra字典传递（自动脱敏）
    - 异常消息禁止包含原始账户ID（使用脱敏后的）
    """

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.SYS_UNKNOWN,  # [优化] 直接使用模块级导入的 ErrorCode
            *,
            # Phase 3：禁止手动传入trace_id，强制从contextvars获取（现由 Layer 0 trace_context 提供）
            account_id: Optional[str] = None,
            module: Optional[str] = None,
            func: Optional[str] = None,
            extra: Optional[Dict[str, Any]] = None,
            # hkcodex / convert_exception：_build_exception_context 返回的 dict 历史参数名
            context: Optional[Dict[str, Any]] = None,
            cause: Optional[Exception] = None,
            retryable: bool = False,
            audit_immediate: bool = False,
            suppress_audit: bool = False,
            # Phase 3 新增：合规审计字段
            operator_id: str = "system",
            approval_ticket: str = "auto",
            fail_open: bool = False,  # 是否为国金紧急模式异常
    ):
        # 处理敏感信息脱敏（消息中的账户ID等）- 延迟导入 DataMasker
        self._raw_message = message
        self._masked_message = self._mask_sensitive_in_msg(message)

        super().__init__(self._masked_message)

        # 错误代码与分级（使用模块级导入的 ErrorCode）
        self.error_code = error_code
        self.severity = error_code.level  # P0/P1/P2

        # Phase 3：强制通过延迟导入辅助函数获取Trace ID（现指向 Layer 0 trace_context）
        self.trace_id = self._get_current_trace_id()

        merged_extra: Dict[str, Any] = {}
        if context:
            merged_extra.update(context)
        if extra:
            merged_extra.update(extra)

        # 上下文构建（包含国金特定字段）
        self.context = ExceptionContext(
            trace_id=self.trace_id,
            module=module or self._get_calling_module(),
            func=func or self._get_calling_function(),
            account_id=account_id,
            extra=merged_extra,
            operator_id=operator_id,
            approval_ticket=approval_ticket,
            reconnect_count_24h=merged_extra.get('reconnect_count_24h'),
            emergency_mode=fail_open
        )

        # 原始异常链
        self.__cause__ = cause
        if cause:
            self.context.error_chain = self._extract_error_chain(cause)

        # 重试与模式标记
        self.retryable = retryable
        self.fail_open = fail_open  # 标记是否可进入紧急模式

        # 立即审计（P0级默认开启）- P0 Fix: 现在通过防护机制确保绝不递归
        # suppress_audit=True：CONN_003 等重复风暴时由调用方节流，避免 stderr/ELK 刷屏
        if not suppress_audit and (audit_immediate or error_code.level == "P0"):
            self._write_audit_log()

    def _get_current_trace_id(self) -> str:
        """
        获取当前Trace ID（Phase 3标准 - 使用收敛后的 Layer 0 延迟导入）
        替代旧版TLS方案，确保asyncio/gevent协程安全
        """
        try:
            tid = _get_trace_context()
            return str(tid)
        except Exception:
            return "SYSTEM_20260315_00000000"

    def _get_calling_module(self) -> Optional[str]:
        """获取调用者模块名（堆栈回溯）"""
        try:
            # 调用栈末尾通常为: _get_calling_module -> __init__ -> 业务调用点
            stack = traceback.extract_stack(limit=8)
            caller = stack[-3] if len(stack) >= 3 else stack[0]
            module_name = os.path.splitext(os.path.basename(caller.filename))[0]
            return module_name or None
        except IndexError:
            return None

    def _get_calling_function(self) -> Optional[str]:
        """获取调用者函数名"""
        try:
            stack = traceback.extract_stack(limit=8)
            caller = stack[-3] if len(stack) >= 3 else stack[0]
            return caller.name
        except IndexError:
            return None

    def _mask_sensitive_in_msg(self, msg: str) -> str:
        """
        对异常消息中的敏感信息进行脱敏（启发式规则）- 延迟导入 DataMasker
        Phase 3：增加对国金miniQMT路径的脱敏
        """
        try:
            DataMasker = _get_data_masker()
            masked_dict = DataMasker.mask_dict({"msg": msg})
            return masked_dict.get("msg", msg)
        except Exception:
            # 防御性编程：脱敏失败时返回最小可诊断摘要（不回显原始消息，避免泄露）
            safe_msg = str(msg)
            msg_hash = hashlib.sha256(safe_msg.encode("utf-8", errors="replace")).hexdigest()[:16]
            return f"[MASK_FAILED][msg_hash={msg_hash}][msg_len={len(safe_msg)}]"

    def _extract_error_chain(self, cause: Exception) -> List[str]:
        """提取原始异常链（限制长度防内存泄漏）"""
        chain = []
        current: Optional[BaseException] = cause
        depth = 0
        while current and depth < 5:  # 限制5层防止过长
            chain.append(f"{type(current).__name__}: {str(current)[:100]}")
            current = getattr(current, '__cause__', None) or getattr(current, '__context__', None)
            depth += 1
        if depth >= 5:
            chain.append("... (truncated)")
        return chain

    def _write_audit_log(self) -> None:
        """
        写入异常审计日志（结构化JSON格式，直入ELK）- 延迟导入 QuantLoggerFactory
        Phase 3 P0级热修复：添加递归防护与启动期降级，确保系统启动期异常绝不触发死循环

        **金融级合规保证**：
        - 启动期（Logger未初始化）：降级至stderr，确保P0异常可见（满足可追溯）
        - 递归防护：同线程重入检测，防止审计故障引发级联崩溃（满足分级管理）
        - 生产期：正常进入ELK结构化审计流（满足可审计）
        """
        # ==================== P0 Fix: 递归防护层 ====================
        # 防护1：线程级递归锁（防止同线程重入导致的无限递归）
        if getattr(_thread_local, 'writing_audit_log', False):
            # 已处于审计写入状态，说明发生了递归调用（如Logger未初始化又抛异常）
            # 降级到标准错误输出，确保P0级异常信息绝不丢失
            print(
                f"[AUDIT-RECURSION-BLOCKED][{self.error_code.code}][{self.severity}] "
                f"{str(self)[:200]}",
                file=sys.stderr
            )
            return

        _thread_local.writing_audit_log = True
        try:
            # 防护3：loguru 队列线程中禁止再次走 logger，避免 re-entrant deadlock
            if _in_loguru_queue_writer():
                print(
                    f"[AUDIT-LOGURU-DEGRADED][{self.error_code.code}][{self.severity}][{self.trace_id}] "
                    f"{str(self)[:200]}",
                    file=sys.stderr,
                )
                return

            # ==================== P0 Fix: 启动期降级层 ====================
            # 防护2：启动期降级（Logger未初始化时直接输出，不构造新异常）
            try:
                from .quant_logger import QuantLoggerFactory
                if not QuantLoggerFactory.is_ready():
                    # 启动期：直接输出至stderr，满足可追溯黄金准则（记录不丢失）
                    # 绝不尝试创建新logger或抛出ConfigurationError（防止递归）
                    print(
                        f"[BOOTSTRAP-P0][{self.error_code.code}][{self.severity}][{self.trace_id}] "
                        f"{str(self)[:200]}",
                        file=sys.stderr
                    )
                    return
            except Exception as e:
                # 极端情况：QuantLoggerFactory导入失败（循环依赖或模块损坏）
                # 同样降级到stderr，确保异常可见
                print(
                    f"[BOOTSTRAP-CRITICAL][{getattr(self, 'error_code', ErrorCode.SYS_UNKNOWN).code}] "
                    f"{str(self)[:200]} | LoggerImportError: {e}",
                    file=sys.stderr
                )
                return

            # ==================== 生产级审计逻辑（保持原有） ====================
            try:
                # 获取logger（携带当前trace_id）
                logger_factory = _get_logger_factory()
                logger = logger_factory.get_logger(
                    module=self.context.module or "exception",
                    func=self.context.func or "raise",
                    trace_id=self.trace_id,
                    error_code=self.error_code.code,
                    severity=self.severity,
                    audit=True  # 标记为审计日志
                )

                # 构建结构化上下文
                log_context = {
                    "exception_type": type(self).__name__,
                    "error_code": self.error_code.code,
                    "severity": self.severity,
                    "message_masked": str(self),
                    "message_raw_hash": hashlib.sha256(
                        self._raw_message.encode("utf-8", errors="replace")
                    ).hexdigest()[:16],
                    "retryable": self.retryable,
                    "fail_open": self.fail_open,
                    "context": self.context.to_dict(mask_sensitive=True),
                    "audit": True,
                    "sensitive": False,
                    "compliance_standard": "CSRC-Tier3"
                }

                # 根据级别选择日志方法
                if self.severity == "P0":
                    logger.error(f"[P0] {self.error_code.description}", context=log_context)
                elif self.severity == "P1":
                    logger.warning(f"[P1] {self.error_code.description}", context=log_context)
                else:
                    logger.info(f"[P2] {self.error_code.description}", context=log_context)

            except Exception as e:
                # 审计日志失败不应阻断主异常，但需打印到stderr（双重保险）
                print(f"[CRITICAL] Failed to write exception audit log: {e}", file=sys.stderr)

        finally:
            # 确保递归锁释放，防止线程长期占用标志
            _thread_local.writing_audit_log = False

    def to_dict(self, include_traceback: bool = False, mask_sensitive: bool = True) -> Dict[str, Any]:
        """
        序列化为字典（供API返回、监控上报、ELK索引）

        Args:
            include_traceback: 是否包含堆栈（生产环境谨慎开启）
            mask_sensitive: 是否脱敏敏感字段
        """
        data = {
            "error_code": self.error_code.code,
            "severity": self.severity,
            "message": str(self),
            "message_hash": hashlib.sha256(
                self._raw_message.encode("utf-8", errors="replace")
            ).hexdigest()[:16],
            "type": type(self).__name__,
            "trace_id": self.trace_id,
            "timestamp": self.context.timestamp,
            "context": self.context.to_dict(mask_sensitive=mask_sensitive),
            "retryable": self.retryable,
            "fail_open_available": self.fail_open,
        }

        if include_traceback:
            # traceback.format_exception返回List[str]，需join为str以保持类型一致性
            tb_list = traceback.format_exception(type(self), self, self.__traceback__)
            data["traceback"] = "".join(tb_list)

        return data

    def to_json(self, **kwargs) -> str:
        """JSON字符串表示（便于Redis/日志传输）"""
        return json.dumps(self.to_dict(**kwargs), ensure_ascii=False, default=str)

    def __str__(self) -> str:
        """格式化输出（含错误代码与Trace ID）"""
        base_msg = self._masked_message
        return f"[{self.error_code.code}][{self.severity}][{self.trace_id}] {base_msg}"

    def __repr__(self) -> str:
        return (f"{type(self).__name__}(code={self.error_code.code}, "
                f"trace_id={self.trace_id}, "
                f"severity={self.severity}, "
                f"retryable={self.retryable})")


# ==============================================================================
# 分层异常类（按业务域划分，Phase 3 国金miniQMT增强版）
# ==============================================================================

class QMTConnectionError(QuantException):
    """
    miniQMT连接层异常（国金适配专用 - Phase 2/3 增强）

    **国金特异性处理**：
    - 自动识别重连限制错误（引用模块级导入的 MAX_RECONNECT_24H）
    - 自动识别连接槽位耗尽（引用模块级导入的 MAX_CONN_PER_ACCOUNT）
    - 支持紧急模式（fail_open）标记
    """

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.CONN_FAILED,  # [优化] 直接使用模块级 ErrorCode
            reconnect_count: Optional[int] = None,
            max_reconnect: Optional[int] = None,  # 默认使用模块级导入的常量值
            slot_info: Optional[Dict] = None,  # 连接槽位信息
            **kwargs
    ):
        # 使用模块级导入的默认值（如果未提供）
        max_reconn = max_reconnect or MAX_RECONNECT_24H

        # 自动判断是否因重连限制触发（国金内存泄漏防护）
        if reconnect_count is not None and reconnect_count >= max_reconn:
            error_code = ErrorCode.CONN_RECONNECT_LIMIT  # [优化] 直接使用模块级 ErrorCode
            message = (f"国金QMT内存泄漏防护触发：24小时重连{reconnect_count}次已达上限"
                       f"（≤{max_reconn}），建议进程重启")
            kwargs["retryable"] = False  # 强制不可重试，需人工介入
            kwargs["audit_immediate"] = True  # P0级强制审计
        else:
            kwargs.setdefault("retryable", True)

        # 国金特定上下文
        extra = kwargs.get('extra', {})
        extra['reconnect_count_24h'] = reconnect_count
        extra['max_reconnect_limit'] = max_reconn
        extra['connection_slot_info'] = slot_info
        kwargs['extra'] = extra

        super().__init__(message, error_code, **kwargs)
        self.reconnect_count = reconnect_count
        self.max_reconnect_limit = max_reconn


class QMTSlotExhaustedError(QMTConnectionError):
    """
    国金miniQMT连接槽位耗尽异常（Phase 2/3 新增）

    触发场景：单账户并发连接数 > MAX_CONN_PER_ACCOUNT（默认2），且等待超时
    """

    def __init__(
            self,
            account_id: str,
            requested_slots: int = 1,
            available_slots: int = 0,
            wait_timeout: Optional[float] = None,
            **kwargs
    ):
        # 使用模块级导入的 CONNECTION_SLOT_TIMEOUT_SEC（Layer 0 常量）
        timeout = wait_timeout or CONNECTION_SLOT_TIMEOUT_SEC

        # 延迟导入 DataMasker 用于脱敏 account_id
        try:
            DataMasker = _get_data_masker()
            masked_account = DataMasker.mask_account_id(account_id)
        except Exception:
            masked_account = "****MASK_FAIL****"

        message = (f"账户 {masked_account} "
                   f"连接槽位耗尽：请求{requested_slots}个，可用{available_slots}个"
                   f"（国金限制≤{MAX_CONN_PER_ACCOUNT}），等待超时{timeout}s")

        super().__init__(
            message,
            error_code=ErrorCode.CONN_SLOT_TIMEOUT,  # [优化] 直接使用模块级 ErrorCode
            retryable=True,  # 可重试（等待后重试）
            account_id=account_id,
            extra={
                "requested_slots": requested_slots,
                "available_slots": available_slots,
                "wait_timeout": timeout,
                "max_slots": MAX_CONN_PER_ACCOUNT  # 使用模块级导入常量
            },
            **kwargs
        )


class QMTEmergencyModeError(QuantException):
    """
    紧急模式异常（国金miniQMT fail-open 场景）

    触发场景：
    - 尝试进入紧急直连但环境变量 QMT_EMERGENCY_MODE 未设置
    - 紧急模式下操作失败
    """

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.EMERG_MODE_FORBIDDEN,  # [优化] 直接使用模块级 ErrorCode
            emergency_env_set: bool = False,
            **kwargs
    ):
        if not emergency_env_set:
            message = f"紧急直连模式未启用（{EnvVarKeys.QMT_EMERGENCY_MODE} != 1）：{message}"
            kwargs["retryable"] = False

        kwargs["fail_open"] = True  # 标记为紧急模式相关

        super().__init__(
            message,
            error_code=error_code,
            audit_immediate=True,  # 强制审计（涉及绕过安全控制）
            **kwargs
        )


class TradingRiskError(QuantException):
    """
    交易风控层异常（含资金熔断、持仓限制）

    Phase 3：增加对 constants.CASH_FUSE_THRESHOLD 的引用能力（通过 extra 传递）
    """

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.TRADE_CASH_FUSE,  # [优化] 直接使用模块级 ErrorCode
            stock_code: Optional[str] = None,
            risk_amount: Optional[float] = None,
            limit_value: Optional[float] = None,
            **kwargs
    ):
        super().__init__(message, error_code, **kwargs)
        self.stock_code = stock_code
        self.risk_amount = risk_amount
        self.limit_value = limit_value

        # 自动补全上下文
        if stock_code:
            self.context.extra['stock_code'] = stock_code
        if risk_amount is not None:
            self.context.extra['risk_amount'] = risk_amount
        if limit_value is not None:
            self.context.extra['limit_value'] = limit_value


# ==============================================================================
# Phase 3 新增：交易执行层与策略执行层异常（解决 live_trading.py 导入缺失）
# ==============================================================================

class TradingExecutionError(QuantException):
    """
    交易执行层异常（订单委托、成交回报、交易确认等执行阶段失败）

    **业务定位**：
    覆盖实际交易执行阶段，区别于 TradingRiskError（事前风控）和 StrategyExecutionError（策略逻辑）。
    用于处理订单已经过风控检查，但在委托、成交、确认环节失败的场景。

    **触发场景（国金miniQMT特定）**：
    - 订单委托失败（order_stock 返回 None 或抛出异常）
    - 订单等待完成超时（wait_for_orders_completion 中断）
    - 成交回报处理异常（on_trade/on_order 回调失败）
    - 买卖执行最终失败（超过 TradingConstants.SELL/BUY_MAX_RETRIES 重试次数）
    - 交易记录持久化失败（CSV文件锁定、IO错误、权限拒绝）
    - 资金熔断触发（CASH_CIRCUIT_BREAKER_TRIGGERED）后的执行中断

    **可重试性**：
    - 网络瞬断、槽位暂时占用：默认可重试（retryable=True）
    - 账户资金不足、股票停牌：默认不可重试
    """

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.TRADE_EXECUTION_FAILED,  # 需确保 ErrorCode 中存在此枚举
            stock_code: Optional[str] = None,
            order_id: Optional[str] = None,
            account_id: Optional[str] = None,
            filled_volume: Optional[int] = None,  # 已成交数量（部分成交场景）
            target_volume: Optional[int] = None,  # 目标数量
            **kwargs
    ):
        # 默认交易执行异常默认可重试（区别于风控异常）
        kwargs.setdefault("retryable", True)

        super().__init__(message, error_code, account_id=account_id, **kwargs)
        self.stock_code = stock_code
        self.order_id = order_id
        self.filled_volume = filled_volume
        self.target_volume = target_volume

        # 自动补全审计上下文（满足可追溯黄金准则）
        if stock_code:
            self.context.extra['stock_code'] = stock_code
        if order_id:
            self.context.extra['order_id'] = order_id
        if filled_volume is not None:
            self.context.extra['filled_volume'] = filled_volume
        if target_volume is not None:
            self.context.extra['target_volume'] = target_volume
            # 计算并记录成交率
            if target_volume > 0:
                self.context.extra['fill_ratio'] = round(filled_volume / target_volume, 4) if filled_volume else 0.0


class DataIntegrityError(TradingExecutionError):
    """
    跨域数据完整性异常（M.1-M.5 静默数据腐败治理基础设施）

    **业务定位**：
    标记数据在跨层/跨进程传递中发生的结构性损坏，不是瞬时网络错误或业务逻辑错误。
    默认不可重试——数据腐败重试无意义。

    **触发场景**：
    - 必填字段为 None（静默丢失）
    - 数值字段收到 bool 类型（Python bool 是 int 的子类，float(True) == 1.0）
    - 字符串无法解析为期望的数值类型
    - 跨层序列化/反序列化中数值精度丢失
    - Broker 返回数据中关键字段异常
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.DATA_INTEGRITY_INVALID_VALUE,
        *,
        field_name: Optional[str] = None,
        expected_type: Optional[str] = None,
        raw_value_repr: Optional[str] = None,
        stock_code: Optional[str] = None,
        **kwargs,
    ):
        kwargs.setdefault("retryable", False)
        super().__init__(message, error_code, stock_code=stock_code, **kwargs)
        self.field_name = field_name
        self.expected_type = expected_type
        self.raw_value_repr = raw_value_repr

        if field_name:
            self.context.extra["field_name"] = field_name
        if expected_type:
            self.context.extra["expected_type"] = expected_type
        if raw_value_repr is not None:
            self.context.extra["raw_value_preview"] = raw_value_repr[:200]

    @classmethod
    def null_field(
        cls, field_name: str, data_source: str = "", *, trace_id: str = "", **kwargs
    ) -> "DataIntegrityError":
        """Factory: required field is None or empty."""
        msg = f"Required field '{field_name}' is None/empty"
        if data_source:
            msg += f" in {data_source}"
        return cls(
            msg,
            error_code=ErrorCode.DATA_INTEGRITY_NULL_FIELD,
            field_name=field_name,
            expected_type="non-None, non-empty",
            **kwargs,
        )

    @classmethod
    def invalid_value(
        cls, field_name: str, raw_value_repr: Optional[str] = None, *, trace_id: str = "", **kwargs
    ) -> "DataIntegrityError":
        """Factory: field value is invalid (wrong type/format)."""
        return cls(
            f"Invalid value for field '{field_name}'",
            error_code=ErrorCode.DATA_INTEGRITY_INVALID_VALUE,
            field_name=field_name,
            raw_value_repr=raw_value_repr,
            **kwargs,
        )

    @classmethod
    def type_coercion_trap(
        cls,
        field_name: str,
        raw_type: str,
        *,
        trace_id: str = "",
        raw_value_repr: Optional[str] = None,
        **kwargs,
    ) -> "DataIntegrityError":
        """Factory: bool-in-int/float trap (Python isinstance(True, int) == True)."""
        return cls(
            f"Type coercion trap: '{field_name}' has type {raw_type} "
            f"(likely bool disguised as numeric -- Python bool is subclass of int)",
            error_code=ErrorCode.DATA_INTEGRITY_TYPE_COERCION,
            field_name=field_name,
            expected_type="float or int (not bool)",
            raw_value_repr=raw_value_repr,
            **kwargs,
        )

    @classmethod
    def broker_payload(
        cls, field_name: str, detail: str = "", *, trace_id: str = "", **kwargs
    ) -> "DataIntegrityError":
        """Factory: broker/QMT returned data fails validation."""
        msg = f"Broker data validation failed for field '{field_name}'"
        if detail:
            msg += f": {detail}"
        return cls(
            msg,
            error_code=ErrorCode.DATA_INTEGRITY_BROKER,
            field_name=field_name,
            **kwargs,
        )


class StrategyExecutionError(QuantException):
    """
    策略执行层异常（选股、仓位计算、组合记录、日终对账等策略逻辑失败）

    **业务定位**：
    覆盖交易决策与准备阶段，区别于 TradingExecutionError（交易执行）。
    用于处理策略初始化、数据准备、信号生成等环节的失败。

    **触发场景（量化策略特定）**：
    - 策略数据加载失败（CSV/Portfolio记录损坏、格式不兼容）
    - 选股文件读写失败（权限错误、磁盘满、编码错误）
    - 选股生成失败（generate_stock_selection 算法异常）
    - 交易日历查询失败（依赖服务不可用，is_trade_day/is_rebalance_day）
    - 投资组合记录更新失败（SQLite WAL冲突、并发写入、Schema不匹配）
    - 日终对账（EOD Reconcile）执行失败（资金偏差超限）
    - 日终刷新失败（EOD Refresh，价格获取失败）
    - Redis流桥接安装失败（信号分发基础设施异常）
    - 配置验证失败（CONFIG_VALIDATION_FAILED）

    **可重试性**：
    - 数据加载、文件IO：默认可重试（可能为临时锁定）
    - 算法错误、配置错误：默认不可重试（需人工修正）
    """

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.STRATEGY_EXECUTION_FAILED,  # 需确保 ErrorCode 中存在此枚举
            strategy_name: Optional[str] = None,
            trading_date: Optional[str] = None,
            data_file: Optional[str] = None,  # 相关数据文件路径（自动脱敏）
            **kwargs
    ):
        # 策略执行异常默认可重试（数据类问题可能是临时的）
        kwargs.setdefault("retryable", True)

        super().__init__(message, error_code, **kwargs)
        self.strategy_name = strategy_name or "unknown"
        self.trading_date = trading_date
        self.data_file = data_file

        # 自动补全审计上下文（满足可追溯黄金准则）
        if strategy_name:
            self.context.extra['strategy_name'] = strategy_name
        if trading_date:
            self.context.extra['trading_date'] = trading_date
        if data_file:
            # 延迟导入 DataMasker 进行路径脱敏（防敏感路径泄露）
            try:
                DataMasker = _get_data_masker()
                self.context.extra['data_file_masked'] = DataMasker.mask_file_path(data_file)
            except Exception:
                self.context.extra['data_file_masked'] = "****MASK_FAIL****"


class AuditIntegrityError(QuantException):
    """
    审计一致性异常（最高优先级 P0）

    触发场景：
    - SQLite WAL损坏导致审计日志丢失
    - Trace ID链路断裂（无法全链路追踪）
    - 冷存储归档失败（不满足5年留痕要求）
    - Phase 3：性能监控数据异常（PERF_VIOLATION）
    """

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.AUDIT_LOG_LOST,  # [优化] 直接使用模块级 ErrorCode
            audit_item: Optional[str] = None,
            expected_hash: Optional[str] = None,
            actual_hash: Optional[str] = None,
            **kwargs
    ):
        kwargs.setdefault("audit_immediate", True)  # 审计异常必须立即记录
        kwargs.setdefault("retryable", False)  # 审计错误通常不可重试

        super().__init__(message, error_code, **kwargs)
        self.audit_item = audit_item
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash

        # 补全审计上下文
        if audit_item:
            self.context.extra['audit_item'] = audit_item
        if expected_hash:
            self.context.extra['expected_hash'] = expected_hash


class MarketDataError(QuantException):
    """
    行情数据异常（xtdata特定）

    触发场景：
    - xtdata.subscribe失败
    - 价格数据异常（负价格、零成交量）
    - 涨跌停数据缺失
    """

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.SYS_UNKNOWN,  # [优化] 直接使用模块级 ErrorCode
            stock_code: Optional[str] = None,
            data_source: str = "xtdata",
            **kwargs
    ):
        super().__init__(message, error_code, **kwargs)
        self.data_source = data_source
        if stock_code:
            self.context.extra['stock_code'] = stock_code


class ConfigurationError(QuantException):
    """
    配置层异常（Phase 3：敏感信息泄露防护增强）

    触发场景：
    - 缺少必要环境变量
    - 配置校验失败
    - 敏感配置脱敏失败（信息泄露风险）
    """

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.CFG_MISSING_REQUIRED,  # [优化] 直接使用模块级 ErrorCode
            config_key: Optional[str] = None,
            config_file: Optional[str] = None,
            sensitive_leak: bool = False,  # 标记是否为敏感信息泄露
            **kwargs
    ):
        if sensitive_leak:
            error_code = ErrorCode.CFG_SENSITIVE_LEAK  # [优化] 直接使用模块级 ErrorCode
            kwargs["audit_immediate"] = True

        super().__init__(message, error_code, **kwargs)
        self.config_key = config_key
        self.config_file = config_file
        self.sensitive_leak = sensitive_leak

        if config_key:
            self.context.extra['config_key'] = config_key
        if config_file:
            # 延迟导入 DataMasker 进行路径脱敏
            try:
                DataMasker = _get_data_masker()
                self.context.extra['config_file_masked'] = DataMasker.mask_file_path(config_file)
            except Exception:
                self.context.extra['config_file_masked'] = "****MASK_FAIL****"


class PersistenceTransparentError(Exception):
    """
    Marker for domain business exceptions that must pass through
    persistence-layer transactions **unwrapped**.

    ``oskh_db.persistence.SQLiteManager.transaction()`` catches ``Exception``:
    instances of this marker are re-raised directly; everything else is
    wrapped in :class:`DatabaseError`.

    ``oskh_core`` domain exceptions (``CashManagerError``,
    ``PositionManagerError``, etc.) inherit from this marker so the
    persistence layer can recognise them without importing ``oskh_core``
    at compile time — eliminating the hidden reverse dependency and the
    fragile ``type(e).__name__`` string-matching fallback.

    .. seealso:: :class:`DatabaseError`
    """


class DatabaseError(QuantException):
    """
    持久化层异常（SQLite/WAL特定）

    涵盖：WAL损坏、批量写入失败、连接超时等
    """

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.DB_CONNECTION_FAILED,  # [优化] 直接使用模块级 ErrorCode
            db_path: Optional[str] = None,
            operation: Optional[str] = None,  # INSERT/UPDATE/CHECKPOINT等
            **kwargs
    ):
        super().__init__(message, error_code, **kwargs)
        self.db_path = db_path
        self.operation = operation

        if db_path:
            # 延迟导入 DataMasker 进行路径脱敏
            try:
                DataMasker = _get_data_masker()
                self.context.extra['db_path_masked'] = DataMasker.mask_file_path(db_path)
            except Exception:
                self.context.extra['db_path_masked'] = "****MASK_FAIL****"
        if operation:
            self.context.extra['db_operation'] = operation


# ==============================================================================
# Week 4 新增：Layer 2.5 ExecutionRecorder 专用异常类
# ==============================================================================

class ExecutionRecorderError(QuantException):
    """
    Layer 2.5 ExecutionRecorder 异常（miniQMT C++回调专用）

    负责处理交易执行记录缓冲层的故障，确保 C++ 回调不阻塞主线程。

    **架构定位**：
    - Layer 2.5 线程边界解耦层（独立于 Layer 3 Gateway）
    - 处理 miniQMT C++ 回调的异步写入异常
    - 与 DatabaseError 区分（不经过 DatabaseGateway 路由）

    **触发场景**：
    - 初始化失败（内存分配或线程创建失败，P0级）
    - 队列溢出（>80%阈值或满队列写入失败，P1级）
    - 紧急降级至同步写入（性能降级但数据安全，P1级）

    **设计原则**：
    1. **不阻塞回调线程**：异常处理必须非阻塞，防止影响 C++ 层
    2. **数据零丢失**：队列溢出时自动触发降级至同步写入
    3. **独立审计通道**：不依赖 Gateway，直接写入 Layer 2 日志
    4. **队列状态透明**：自动记录队列利用率（queue_utilization_pct）

    **错误码映射**：
    - LAYER25_INIT_FAILED (LAYER25_001): 初始化失败，P0级
    - LAYER25_QUEUE_OVERFLOW (LAYER25_002): 队列溢出，P1级
    - LAYER25_EMERGENCY_FALLBACK (LAYER25_003): 紧急降级，P1级

    **使用示例**：
        try:
            recorder.put(order_data)
        except ExecutionRecorderError as e:
            if e.error_code == ErrorCode.LAYER25_QUEUE_OVERFLOW:
                # 触发降级至同步写入
                sync_write_fallback(order_data)
    """

    def __init__(
            self,
            message: str,
            error_code: ErrorCode = ErrorCode.LAYER25_INIT_FAILED,
            *,
            queue_utilization: Optional[float] = None,
            dropped_records: Optional[int] = None,
            **kwargs
    ):
        # 初始化失败（LAYER25_001）为 P0 级，默认不可重试
        # 队列溢出（LAYER25_002）和降级（LAYER25_003）为 P1 级，默认可重试（降级后恢复）
        kwargs.setdefault("retryable", error_code != ErrorCode.LAYER25_INIT_FAILED)

        super().__init__(message, error_code, **kwargs)

        self.queue_utilization = queue_utilization
        self.dropped_records = dropped_records

        # 自动补全审计上下文（满足可追溯黄金准则）
        if queue_utilization is not None:
            self.context.extra['queue_utilization_pct'] = round(queue_utilization * 100, 2)
        if dropped_records:
            self.context.extra['dropped_records'] = dropped_records

    @classmethod
    def queue_overflow(cls, utilization: float, dropped: int) -> "ExecutionRecorderError":
        """
        工厂方法：队列溢出场景

        当 ExecutionRecorder 内部队列超过 80% 阈值或满队列无法写入时触发。
        自动标记为 P1 级（非致命）并强制审计（确保运维可见）。

        Args:
            utilization: 队列利用率（0.0-1.0）
            dropped: 本次溢出丢弃的记录数

        Returns:
            ExecutionRecorderError: 配置完成的异常实例

        Example:
            if queue.qsize() > maxsize * 0.8:
                raise ExecutionRecorderError.queue_overflow(0.85, 10)
        """
        return cls(
            message=f"ExecutionRecorder queue overflow: {utilization:.1%} utilization, {dropped} records dropped",
            error_code=ErrorCode.LAYER25_QUEUE_OVERFLOW,
            queue_utilization=utilization,
            dropped_records=dropped,
            audit_immediate=True  # 强制审计，确保运维及时感知
        )

    @classmethod
    def emergency_fallback(cls, reason: str, records_pending: int) -> "ExecutionRecorderError":
        """
        工厂方法：紧急降级场景

        当队列溢出或异步写入失败时，降级至同步写入模式触发。
        标记为 P1 级，确保审计记录降级事件（满足可审计黄金准则）。

        Args:
            reason: 降级原因（如 "queue_full", "async_timeout"）
            records_pending: 待刷盘的记录数

        Returns:
            ExecutionRecorderError: 配置完成的异常实例
        """
        return cls(
            message=f"ExecutionRecorder emergency fallback triggered: {reason}, {records_pending} records pending sync write",
            error_code=ErrorCode.LAYER25_EMERGENCY_FALLBACK,
            audit_immediate=True,
            extra={"fallback_reason": reason, "records_pending": records_pending}
        )


# ==============================================================================
# 便捷函数（供业务层与基础设施层使用）
# ==============================================================================

def raise_with_audit(
        exception: Exception,
        logger: Optional[Any] = None
) -> None:
    """
    抛出异常并强制立即审计（供关键路径使用）

    Args:
        exception: 异常实例（QuantException 或任意 Exception，后者将被自动包装）
        logger: 可选的外部logger（默认使用 QuantLoggerFactory，预留扩展）
    """
    # 类型守卫：若非系统异常则自动包装（防御性编程）
    if not isinstance(exception, QuantException):
        # 包装非系统异常
        exception = convert_exception(
            exception,
            QuantException,
            ErrorCode.SYS_UNKNOWN,  # [优化] 直接使用模块级导入的 ErrorCode
            "Wrapped non-quant exception"
        )

    # 强制立即审计（双重保险）
    exception._write_audit_log()

    # 抛出
    raise exception


def convert_exception(
        original: Exception,
        target_class: type,
        error_code: ErrorCode,  # [优化] 直接使用模块级导入的 ErrorCode 类型注解
        message: Optional[str] = None,
        **kwargs
) -> QuantException:
    """
    将原生异常转换为金融级异常（保留原始异常链）

    使用场景：捕获第三方库（如 xtquant, sqlite3）异常后转为系统异常

    Args:
        original: 原始异常（将被设置为 __cause__）
        target_class: 目标异常类（必须继承 QuantException）
        error_code: 错误代码（直接使用模块级导入的 ErrorCode）
        message: 新消息（默认使用原始消息）
        **kwargs: 传递给目标异常的额外参数；``context`` 为 dict 时与 ``extra`` 合并后传入 QuantException

    Returns:
        QuantException: 包装后的新异常（未抛出）

    Example:
        try:
            fn = getattr(xtdata, "reconnect", None) or getattr(xtdata, "init", None)
            if callable(fn):
                fn()
        except Exception as e:
            raise convert_exception(e, QMTConnectionError, ErrorCode.CONN_FAILED)
    """
    if not issubclass(target_class, QuantException):
        raise TypeError("target_class 必须继承自 QuantException")

    msg = message or str(original)

    # 自动判断是否为sqlite3或xtquant特定错误
    error_type = type(original).__name__
    if 'sqlite' in error_type.lower():
        kwargs.setdefault("db_path", getattr(original, 'filename', None))
    elif 'xt' in error_type.lower():
        kwargs.setdefault("retryable", True)

    new_exc = target_class(
        message=msg,
        error_code=error_code,
        cause=original,
        **kwargs
    )
    return new_exc


def is_retryable_error(exc: Exception) -> bool:
    """
    判断异常是否可重试（供连接管理器重试策略使用）

    规则：
    - QuantException 且 retryable=True: 可重试
    - 连接类错误（CONN_xxx）：默认可重试（除非是重连限制CONN_003）
    - 风控类（RISK_xxx）、审计类（AUDIT_xxx）：不可重试
    - 国金特定：槽位超时（CONN_007）可重试，重连限制（CONN_003）不可重试
    - 交易执行类（TRADE_xxx）：根据具体错误码判断（如 ORDER_PLACEMENT_FAILED 可重试，SELL_EXECUTION_FAILED 需人工介入）
    - 策略执行类（STRAT_xxx）：默认可重试（数据类问题可能是临时的）
    - Layer 2.5（LAYER25_xxx）：初始化失败（LAYER25_001）不可重试，其余默认可重试
    """
    if isinstance(exc, QuantException):
        if hasattr(exc, 'retryable'):
            return exc.retryable

        # 根据错误代码推断（直接使用模块级导入的 ErrorCode 属性）
        code = exc.error_code.code
        if code.startswith("CONN_"):
            return code not in ("CONN_003", "CONN_005", "CONN_008")  # 重连限制、紧急模式拒绝、xtdata初始化失败不可重试
        elif code.startswith(("RISK_", "AUDIT_", "EMERG_", "CFG_")):
            return False
        elif code.startswith("TRADE_"):
            # 交易执行错误：最终失败类不可重试，过程类可重试
            return code not in ("TRADE_004", "TRADE_005", "TRADE_015", "TRADE_016")  # 持仓不足、超时、买卖最终失败不可重试
        elif code.startswith("STRAT_"):
            # 策略执行错误：默认可重试（数据类可能是临时的）
            return True
        elif code.startswith("LAYER25_"):
            # Layer 2.5 错误：初始化失败（LAYER25_001）不可重试，队列溢出（LAYER25_002）和降级（LAYER25_003）可重试
            return code != "LAYER25_001"
        elif code.startswith("DATA_"):
            return False  # 数据完整性错误不可重试（数据腐败重试无意义）

        return exc.severity != "P0"  # P0错误默认不可重试（除明确标记外）

    # 对非系统异常，保守策略：不可重试
    return False


def get_error_alert_level(exc: Exception) -> str:
    """
    获取异常报警级别（供监控面板使用）

    与 :class:`ErrorCode` 的 ``level``（P0/P1/P2）对齐，避免枚举名与 ``.code`` 字符串混用导致误判。

    Returns:
        str: "CRITICAL", "HIGH", "MEDIUM", "LOW"
    """
    if isinstance(exc, AuditIntegrityError):
        return "CRITICAL"
    if isinstance(exc, QMTEmergencyModeError):
        return "HIGH"
    if isinstance(exc, ExecutionRecorderError):
        return "CRITICAL" if exc.error_code.code == "LAYER25_001" else "HIGH"
    if isinstance(exc, DataIntegrityError):
        level = getattr(getattr(exc, "error_code", None), "level", None)
        if level == "P0":
            return "CRITICAL"  # 预留：当前 DATA_* 均为 P1，暂不触发
        return "HIGH"  # P1/P2 默认
    if isinstance(exc, StrategyExecutionError):
        if exc.severity == "P0":
            return "CRITICAL"
        if exc.severity == "P1":
            return "HIGH"
        return "MEDIUM"
    if isinstance(exc, (TradingRiskError, TradingExecutionError)):
        if exc.severity == "P0":
            return "CRITICAL"
        if exc.severity == "P1":
            return "HIGH"
        return "MEDIUM"
    if isinstance(exc, QMTConnectionError):
        if exc.severity == "P0":
            return "CRITICAL"
        if exc.severity == "P1":
            return "HIGH"
        return "MEDIUM"
    if isinstance(exc, QuantException):
        if exc.severity == "P0":
            return "CRITICAL"
        if exc.severity == "P1":
            return "HIGH"
        return "MEDIUM"
    return "MEDIUM"


def is_emergency_mode_applicable(exc: Exception) -> Tuple[bool, str]:
    """
    判断是否可进入国金紧急模式（fail-open）

    Returns:
        (bool, str): (是否适用, 原因)
    """
    if isinstance(exc, QMTConnectionError):
        if exc.error_code.code == "CONN_003":  # 重连限制，可尝试紧急模式
            return (True, "24h reconnect limit reached, emergency mode applicable")
        elif exc.error_code.code == "CONN_006":  # 多账户限制
            return (True, "Connection limit reached, emergency mode applicable")

    if isinstance(exc, QuantException) and hasattr(exc, 'fail_open'):
        return (exc.fail_open, "Marked as fail_open capable")

    return (False, "Not applicable for emergency mode")


# ==============================================================================
# 模块自检（与constants.py兼容性验证，含ErrorCode模块级导入验证）
# ==============================================================================

def _self_test():
    """
    模块自检（Phase 3 Layer 1 优化版 + Week 4 Layer 2.5 增强验证）

    **验证项**：
    1. ErrorCode 模块级导入有效性（非延迟，零运行时开销）
    2. 基础异常测试（24字符Trace ID）
    3. 国金miniQMT重连限制测试（引用模块级常量）
    4. 连接槽位耗尽测试（含延迟导入 DataMasker 验证）
    5. 序列化测试（ELK兼容性）
    6. 重试策略测试（基于 ErrorCode 模块级引用）
    7. 紧急模式适用性测试
    8. raise_with_audit 类型兼容性测试
    9. [关键] 验证 ErrorCode 未在函数内重复导入（确保模块级导入优化生效）
    10. [P0 Fix] 递归防护机制有效性（模拟Logger未初始化场景）
    11. TradingExecutionError 与 StrategyExecutionError 基础功能测试
    12. [Week 4 新增] ExecutionRecorderError Layer 2.5 专用验证
    """
    print("[exceptions.py] Phase 3 Layer 1 Optimized + P0 Recursion Guard + Week 4 Layer 2.5 Self-Test Starting...")

    # 1. [优化验证] ErrorCode 模块级导入检查
    assert 'ErrorCode' in globals(), "ErrorCode must be imported at module level"
    assert isinstance(ErrorCode.SYS_UNKNOWN, ErrorCode), "ErrorCode.SYS_UNKNOWN must be accessible"
    assert ErrorCode.CONN_FAILED.level == "P0", "ErrorCode level attribute must be accessible"
    print(f"  ✓ ErrorCode module-level import: {ErrorCode.SYS_UNKNOWN.code} (Zero runtime overhead)")

    # 2. 基础异常测试（24字符Trace ID）
    try:
        raise QuantException(
            "Test exception",
            ErrorCode.SYS_UNKNOWN,  # 使用模块级导入的 ErrorCode
            extra={"test": True}
        )
    except QuantException as e:
        assert e.error_code == ErrorCode.SYS_UNKNOWN
        assert e.severity == "P0"
        assert len(e.trace_id) == 24, f"Trace ID长度违规: {len(e.trace_id)}"
        print(f"  ✓ QuantException: Trace ID={e.trace_id}, Len={len(e.trace_id)}")

    # 3. 国金miniQMT重连限制测试（引用模块级导入的 MAX_RECONNECT_24H）
    try:
        raise QMTConnectionError(
            "Connection lost",
            reconnect_count=MAX_RECONNECT_24H,  # 使用模块级导入的常量
            max_reconnect=MAX_RECONNECT_24H
        )
    except QMTConnectionError as e:
        assert e.error_code == ErrorCode.CONN_RECONNECT_LIMIT  # 使用模块级导入的 ErrorCode 比较
        assert not e.retryable  # 强制不可重试
        assert e.max_reconnect_limit == MAX_RECONNECT_24H
        print(f"  ✓ QMTConnectionError (reconnect limit): {e.error_code.code}")
        print(f"    Max reconnect limit: {MAX_RECONNECT_24H} (from constants, module-level)")

    # 4. 连接槽位耗尽测试（含延迟导入 DataMasker 验证）
    try:
        raise QMTSlotExhaustedError(
            account_id="123456789012",
            requested_slots=1,
            available_slots=0
        )
    except QMTSlotExhaustedError as e:
        assert e.error_code == ErrorCode.CONN_SLOT_TIMEOUT  # 使用模块级导入的 ErrorCode
        assert e.retryable  # 槽位超时默认可重试
        assert "123****012" in str(e)  # 验证脱敏生效
        print(f"  ✓ QMTSlotExhaustedError: {e.error_code.code} (masking verified)")

    # 5. 序列化测试（ELK兼容性）
    exc = TradingRiskError(
        "资金不足",
        ErrorCode.TRADE_CASH_FUSE,  # 使用模块级导入的 ErrorCode
        stock_code="000001.SZ",
        risk_amount=1000000.0,
        account_id="123456789012"
    )
    data = exc.to_dict(mask_sensitive=True)
    assert len(data['trace_id']) == 24
    assert data['context']['account_id'] == "123****012"  # 脱敏验证
    json_str = exc.to_json()
    assert isinstance(json_str, str)
    print(f"  ✓ Serialization & Masking: {data['context']['account_id']}")

    # 6. 重试策略测试（基于 ErrorCode 模块级引用）
    retry_exc = QMTConnectionError("Timeout", error_code=ErrorCode.CONN_LOST)  # 模块级 ErrorCode
    no_retry_exc = QMTConnectionError("Limit reached", error_code=ErrorCode.CONN_RECONNECT_LIMIT)
    assert is_retryable_error(retry_exc) == True
    assert is_retryable_error(no_retry_exc) == False
    print(
        f"  ✓ Retry logic: retryable={is_retryable_error(retry_exc)}, non-retryable={is_retryable_error(no_retry_exc)}")

    # 7. 紧急模式适用性测试
    emg_check = is_emergency_mode_applicable(no_retry_exc)
    assert emg_check[0] == True  # 重连限制可进入紧急模式
    print(f"  ✓ Emergency mode check: {emg_check}")

    # 8. raise_with_audit 类型兼容性测试（含延迟导入 logger 验证）
    try:
        # 测试接受原生异常并包装
        raise_with_audit(ValueError("原生异常测试"))
    except QuantException as e:
        assert e.error_code == ErrorCode.SYS_UNKNOWN  # 使用模块级导入的 ErrorCode
        assert "Wrapped non-quant exception" in str(e)
        print(f"  ✓ raise_with_audit 类型兼容性: 已正确包装 ValueError -> QuantException")

    # 9. [关键验证] 确认 ErrorCode 未在函数内被重复导入（性能优化确认）
    import inspect
    source = inspect.getsource(convert_exception)
    assert "from .constants import" not in source, "convert_exception should not re-import ErrorCode (use module-level)"
    print("  ✓ Performance optimization: ErrorCode not re-imported in functions (module-level only)")

    # 10. [P0 Fix] 递归防护机制验证（模拟Logger未初始化场景）
    print("  ⚙ Testing P0 recursion guard (simulating uninitialized logger)...")
    # 保存原始状态
    original_initialized = None
    try:
        from .quant_logger import QuantLoggerFactory
        original_initialized = QuantLoggerFactory._initialized
        # 强制设置为未初始化状态（模拟启动期）
        QuantLoggerFactory._initialized = False

        # 尝试创建P0异常并触发审计（此操作在修复前会导致递归崩溃）
        test_exc = QuantException(
            "Bootstrap test exception",
            ErrorCode.SYS_INITIALIZATION_FAILED,
            audit_immediate=True
        )
        # 如果执行到这里没有发生RecursionError，说明防护有效
        print("  ✓ P0 Recursion Guard: BOOTSTRAP-P0 message printed to stderr without recursion")

        # 验证递归锁机制
        assert hasattr(_thread_local, 'writing_audit_log') == False or _thread_local.writing_audit_log == False, \
            "Recursion lock should be released after _write_audit_log"
        print("  ✓ P0 Recursion Guard: Thread-local lock properly released")

    except RecursionError:
        raise AssertionError("P0 Fix failed: Recursion still occurs when logger uninitialized")
    finally:
        # 恢复原始状态
        if original_initialized is not None:
            from .quant_logger import QuantLoggerFactory
            QuantLoggerFactory._initialized = original_initialized

    # 11. TradingExecutionError 与 StrategyExecutionError 基础测试
    print("  ⚙ Testing TradingExecutionError & StrategyExecutionError...")

    # 测试 TradingExecutionError
    try:
        raise TradingExecutionError(
            "Order placement failed",
            error_code=ErrorCode.TRADE_ORDER_CALLBACK_FAILED,  # [P1 Fixed] 使用正确命名
            stock_code="000001.SZ",
            order_id="ORDER_12345",
            filled_volume=100,
            target_volume=1000,
            account_id="123456789012"
        )
    except TradingExecutionError as e:
        assert e.stock_code == "000001.SZ"
        assert e.order_id == "ORDER_12345"
        assert e.context.extra.get('fill_ratio') == 0.1  # 100/1000
        assert len(e.trace_id) == 24
        print(f"  ✓ TradingExecutionError: stock={e.stock_code}, fill_ratio={e.context.extra.get('fill_ratio')}")

    # 测试 StrategyExecutionError
    try:
        raise StrategyExecutionError(
            "Portfolio update failed",
            error_code=ErrorCode.STRATEGY_EXECUTION_FAILED,  # 确保使用正确命名
            strategy_name="MultiFactorV6",
            trading_date="20260315",
            data_file="/敏感路径/portfolio.csv"
        )
    except StrategyExecutionError as e:
        assert e.strategy_name == "MultiFactorV6"
        assert e.trading_date == "20260315"
        assert "data_file_masked" in e.context.extra
        assert len(e.trace_id) == 24
        print(f"  ✓ StrategyExecutionError: strategy={e.strategy_name}, date={e.trading_date}")

    # 12. [Week 4 新增] ExecutionRecorderError Layer 2.5 专用验证
    print("  ⚙ Testing ExecutionRecorderError (Layer 2.5 miniQMT callback buffer)...")

    # 测试初始化失败（P0级）
    try:
        raise ExecutionRecorderError(
            "Memory allocation failed for callback buffer",
            error_code=ErrorCode.LAYER25_INIT_FAILED,
            queue_utilization=0.0,
            dropped_records=0
        )
    except ExecutionRecorderError as e:
        assert e.error_code == ErrorCode.LAYER25_INIT_FAILED
        assert not e.retryable  # LAYER25_001 默认可重试=False
        assert e.queue_utilization == 0.0
        assert len(e.trace_id) == 24
        print(f"  ✓ ExecutionRecorderError (init failed): code={e.error_code.code}, retryable={e.retryable}")

    # 测试队列溢出（工厂方法）
    try:
        raise ExecutionRecorderError.queue_overflow(utilization=0.85, dropped=150)
    except ExecutionRecorderError as e:
        assert e.error_code == ErrorCode.LAYER25_QUEUE_OVERFLOW
        assert e.queue_utilization == 0.85
        assert e.dropped_records == 150
        assert e.context.extra.get('queue_utilization_pct') == 85.0
        assert e.retryable  # LAYER25_002 默认可重试=True
        print(
            f"  ✓ ExecutionRecorderError.queue_overflow: utilization={e.queue_utilization}, dropped={e.dropped_records}")

    # 测试紧急降级（工厂方法）
    try:
        raise ExecutionRecorderError.emergency_fallback(reason="queue_full", records_pending=42)
    except ExecutionRecorderError as e:
        assert e.error_code == ErrorCode.LAYER25_EMERGENCY_FALLBACK
        assert e.context.extra.get('fallback_reason') == "queue_full"
        assert e.context.extra.get('records_pending') == 42
        assert e.retryable  # LAYER25_003 默认可重试=True
        print(f"  ✓ ExecutionRecorderError.emergency_fallback: reason={e.context.extra.get('fallback_reason')}")

    # 13. [Week 4 Fixed] 错误码命名漂移回归测试
    print("  ⚙ Week 4 ErrorCode naming alignment validation...")
    assert hasattr(ErrorCode, 'TRADE_ORDER_CALLBACK_FAILED'), "TRADE_ORDER_CALLBACK_FAILED (TRADE_009) must exist"
    assert hasattr(ErrorCode, 'TRADE_TRADE_CALLBACK_FAILED'), "TRADE_TRADE_CALLBACK_FAILED (TRADE_010) must exist"
    assert hasattr(ErrorCode, 'LAYER25_INIT_FAILED'), "LAYER25_INIT_FAILED (LAYER25_001) must exist"
    assert hasattr(ErrorCode, 'LAYER25_QUEUE_OVERFLOW'), "LAYER25_QUEUE_OVERFLOW (LAYER25_002) must exist"
    assert hasattr(ErrorCode, 'LAYER25_EMERGENCY_FALLBACK'), "LAYER25_EMERGENCY_FALLBACK (LAYER25_003) must exist"
    # 验证旧命名已不存在（防止回退）
    assert not hasattr(ErrorCode, 'ORDER_CALLBACK_FAILED'), "Old name ORDER_CALLBACK_FAILED should be removed"
    assert not hasattr(ErrorCode, 'TRADE_CALLBACK_FAILED'), "Old name TRADE_CALLBACK_FAILED should be removed"
    print("  ✓ Week 4 ErrorCode naming: All drift issues fixed (TRADE_009/TRADE_010/LAYER25_xxx aligned)")

    print("[exceptions.py] Self-test completed successfully")
    print("[exceptions.py] Phase 3 Layer 1 Optimized + P0 Recursion Guard + Week 4 Layer 2.5 ✅")
    print("[exceptions.py] ErrorCode import strategy: EAGER (module-level, zero runtime overhead) ✅")
    print("[exceptions.py] P0 Fix: Recursion Guard ACTIVE (thread-local + bootstrap degradation) 🛡️")
    print("[exceptions.py] Week 4 Fix: ErrorCode naming drift RESOLVED (TRADE_009/TRADE_010) ✅")
    print("[exceptions.py] Week 4 Enhancement: ExecutionRecorderError for Layer 2.5 miniQMT callback buffer 🚀")


# 执行自检（仅在直接运行时）
if __name__ == "__main__":
    _self_test()

# ==============================================================================
# 公开 API 列表（严格限制，与__init__.py导出一致，新增线程局部变量不导出）
# ==============================================================================
__all__ = [
    # 错误代码体系（从 constants 模块级导入后导出，零延迟）
    'ErrorCode',

    # 异常上下文
    'ExceptionContext',

    # 基础异常
    'QuantException',

    # 分层异常类（国金miniQMT增强）
    'QMTConnectionError',  # 连接层（含重连限制）
    'QMTSlotExhaustedError',  # 槽位耗尽（Phase 2/3新增）
    'QMTEmergencyModeError',  # 紧急模式（Phase 2/3新增）
    'TradingRiskError',  # 交易风控层（资金熔断、持仓限制）
    'TradingExecutionError',  # [新增] 交易执行层（下单、成交、记录）
    'DataIntegrityError',  # 跨域数据完整性（M.1-M.5 静默腐败治理）
    'StrategyExecutionError',  # [新增] 策略执行层（选股、仓位、日终）
    'AuditIntegrityError',  # 审计一致性层（P0）
    'MarketDataError',  # 行情数据层
    'ConfigurationError',  # 配置层（含泄露防护）
    'DatabaseError',  # 持久化层

    # Week 4 新增：Layer 2.5 执行记录器专用异常
    'ExecutionRecorderError',  # Layer 2.5 miniQMT C++回调缓冲层

    # 便捷函数
    'raise_with_audit',  # 强制审计抛出
    'convert_exception',  # 原生异常转换
    'is_retryable_error',  # 重试策略判断
    'get_error_alert_level',  # 报警级别获取
    'is_emergency_mode_applicable',  # 紧急模式适用性检查（国金特定）

    # 国金miniQMT关键配置常量导出（供外部模块引用，模块级导入零延迟）
    'CONNECTION_SLOT_TIMEOUT_SEC',  # 槽位等待超时（国金限制）
]