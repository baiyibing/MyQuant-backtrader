# -*- coding: utf-8 -*-
"""
common/infra/trace_context.py - 全链路追踪上下文管理（Layer 0 基础设施 - Phase 3 Big Bang）
================================================================================

**架构定位**：
    Layer 0 零依赖层，仅依赖 `constants.TraceConstants`。
    作为全系统最基础的追踪基础设施，向上层提供协程安全的 Trace ID 生成与上下文传递。

**核心职责**：
    1. Trace ID 生成与验证（24字符黄金准则：{PREFIX:<6}_{YYYYMMDD}_{RANDOM:8}）
    2. contextvars 协程安全上下文管理（替代 TLS，支持 asyncio/gevent）
    3. 国金 miniQMT 多账户上下文隔离支持

**设计约束**：
    - 零业务逻辑；依赖标准库 + `constants` + `timekeeping`（同为时钟工具层，无业务依赖）
    - **禁止**导入 exceptions/quant_logger/perf_monitor 等上层模块（防循环依赖）
    - 所有常量引用 `TraceConstants`（单一真相源）
    - Trace ID 中段 ``YYYYMMDD`` 为 **UTC** 日历日（与 execution_recorder / risk_runtime 一致）

**合规标准**：
    - 中国A股量化交易系统黄金准则：可追溯（24字符全链路ID）
    - Trace ID 格式强制规范：前缀(6) + 日期(8) + 随机(8) = 24字符
    - **规范 ID 为 24 个字符、无尾部空白**；`validate` 拒绝 trailing whitespace。
    - **miniQMT 回调线程**：`ContextVar` 不会从新线程继承，请在 XtQuant 回调入口调用
      `apply_trace_for_miniqmt_callback`（见下文），再写日志或访问 SQLite 审计字段。

Author: Quant Engineering Team
Version: 3.0.0 (Phase 3 Layer 0 - Zero Dependency)
Date: 2026-03-16
"""

import uuid
from typing import Optional, Dict
from contextvars import ContextVar

# ==============================================================================
# Layer 0: 仅依赖 constants（零业务模块依赖）
# ==============================================================================
from .constants import (
    TRACE_ID_LENGTH,  # 24字符强制
    TraceConstants,  # 前缀映射单一真相源
)
from .timekeeping import parse_qmt_time, utc_date_yyyymmdd

# ==============================================================================
# 工厂默认占位 Trace ID（单一真相源，与 qmt_client 等模块对齐）
# ==============================================================================

# 显式 24 字符：{PREFIX6}_{YYYYMMDD}_{RANDOM8}，禁止双下划线等导致的长度漂移
DEFAULT_TRACE_CONTEXT_ID: str = "SYSTEM_20260315_00000000"

if len(DEFAULT_TRACE_CONTEXT_ID) != TRACE_ID_LENGTH:
    raise RuntimeError(
        "DEFAULT_TRACE_CONTEXT_ID must be exactly TRACE_ID_LENGTH characters"
    )

# ==============================================================================
# 协程安全上下文变量（替代 TLS，支持 miniQMT 多账户并发）
# ==============================================================================

_current_trace_ctx: ContextVar[str] = ContextVar(
    "trace_id",
    default=DEFAULT_TRACE_CONTEXT_ID,
)


# ==============================================================================
# Trace ID 生成器（金融级标准实现）
# ==============================================================================

class TraceIdGenerator:
    """
    全系统统一 Trace ID 生成器（Layer 0 实现）

    **格式规范**: {PREFIX:<6}_{YYYYMMDD}_{RANDOM:8}
    总长度: 6 + 1 + 8 + 1 + 8 = 24（与 ``TRACE_ID_LENGTH`` 一致；**规范串无尾部空白**）。
    前缀槽位不足 6 位时，右补 ``0``（而非空格）。
    ``generate`` 末尾的 ``ljust`` 仅在异常截断路径下作为防御性填充；正常路径下自然为 24 字符且可通过 ``validate``。

    **前缀映射**（来自 TraceConstants.TRACE_PREFIXES 单一真相源）:
        - SEL:     选股模块
        - REBAL:   调仓模块
        - BRIDGE:  Redis桥接
        - EXEC:    执行器
        - RECON:   日终对账
        - HKQ:     miniQMT适配（国金特定）
        - CFG:     配置管理
        - MON:     监控面板
        - LOAD:    策略加载
        - STRAT:   策略基类
        - QUERY:   查询操作
        - LMTUP:   涨停检查
        - TRADE:   交易执行
        - AUDIT:   审计操作
        - RISK:    风控检查
        - SYSTEM:  系统级

    **国金miniQMT特定**:
        使用 HKQ 前缀确保 miniQMT 相关操作（xtdata初始化、连接管理）可快速检索
    """

    @classmethod
    def _resolve_module_key(cls, module: str) -> str:
        """解析模块键：直连 > 小写 > 别名（大小写兼容）> 原值。"""
        key = str(module or "")
        key_lower = key.lower()
        prefix_map: Dict[str, str] = TraceConstants.TRACE_PREFIXES
        if key in prefix_map:
            return key
        if key_lower in prefix_map:
            return key_lower
        aliases: Dict[str, str] = getattr(TraceConstants, "TRACE_MODULE_ALIASES", {})
        alias_target = aliases.get(key) or aliases.get(key_lower)
        if alias_target:
            return alias_target
        return key

    @classmethod
    def generate(cls, module: str, date: Optional[str] = None) -> str:
        """
        生成严格 24 字符 Trace ID（与 ``validate`` 一致、无尾部空白）。

        Args:
            module: 模块标识符（如 'selector', 'executor', 'hkcodex'）
            date: 日期字符串 YYYYMMDD，默认 **UTC** 当前日历日

        Returns:
            str: 24 字符 Trace ID

        Raises:
            RuntimeError: 如果生成的 Trace ID 长度不为24（基础设施层使用 RuntimeError
                         而非 ConfigurationError，避免依赖上层异常体系）
        """
        # 从单一真相源获取 6 字符前缀（不足右补 "0"，超长截断）
        prefix_map: Dict[str, str] = TraceConstants.TRACE_PREFIXES
        module_key = cls._resolve_module_key(module)
        prefix = prefix_map.get(module_key, 'TRACE')[:6].ljust(TraceConstants.TRACE_PREFIX_LENGTH, "0")

        # 日期部分（8字符 YYYYMMDD，UTC 日历日）
        date_part = date or utc_date_yyyymmdd()

        # 随机部分（8字符十六进制，UUID前8位确保唯一性）
        rand_part = uuid.uuid4().hex[:8].upper()

        # 组装并截断至 TRACE_ID_LENGTH；ljust 仅防御性（正常路径长度已为 24）
        trace_id = f"{prefix}_{date_part}_{rand_part}"
        trace_id = trace_id[:TRACE_ID_LENGTH].ljust(TRACE_ID_LENGTH)

        # 防御性编程：长度违规视为基础设施崩溃级错误（Layer 0 使用 RuntimeError）
        if len(trace_id) != TRACE_ID_LENGTH:
            raise RuntimeError(
                f"CRITICAL: Trace ID length violation in Layer 0 infrastructure: "
                f"got {len(trace_id)} chars, expected {TRACE_ID_LENGTH}. "
                f"This indicates constants.TRACE_ID_LENGTH mismatch or generation logic error."
            )

        return trace_id

    @classmethod
    def validate(cls, trace_id: str) -> bool:
        """验证 Trace ID 是否符合24字符规范（用于入口校验）"""
        if not trace_id or len(trace_id) != TRACE_ID_LENGTH:
            return False
        if trace_id != trace_id.rstrip():
            return False
        # 检查格式：前缀(6)_日期(8)_随机(8)
        parts = trace_id.split("_")
        if not (
            len(parts) == 3
            and len(parts[0]) == 6
            and len(parts[1]) == 8
            and len(parts[2]) == 8
        ):
            return False
        date_part, rand_part = parts[1], parts[2]
        if not date_part.isdigit():
            return False
        try:
            parse_qmt_time(date_part)
        except ValueError:
            return False
        if len(rand_part) != TraceConstants.TRACE_RANDOM_LENGTH:
            return False
        if not all(c in "0123456789ABCDEFabcdef" for c in rand_part):
            return False
        return True

    @classmethod
    def extract_components(cls, trace_id: str) -> Optional[Dict[str, str]]:
        """
        解析 Trace ID 组件（用于审计分析）

        Returns:
            Dict: {'prefix': str, 'date': str, 'random': str, 'module_hint': str}
                  或 None（格式无效时）
        """
        if not cls.validate(trace_id):
            return None

        parts = trace_id.split("_")
        _hint = cls._reverse_prefix_lookup(parts[0])
        return {
            "prefix": parts[0],
            "date": parts[1],
            "random": parts[2],
            "module_hint": _hint or "",
        }

    @classmethod
    def _reverse_prefix_lookup(cls, prefix: str) -> Optional[str]:
        """反向查找模块名（用于调试；前缀在 ID 中为 6 字符宽度，与 generate 一致）"""
        prefix_map: Dict[str, str] = TraceConstants.TRACE_PREFIXES
        for module, pref in prefix_map.items():
            if pref[:6].ljust(TraceConstants.TRACE_PREFIX_LENGTH, "0") == prefix:
                return module
        return None


# ==============================================================================
# 上下文管理便捷函数（协程安全 API）
# ==============================================================================

def set_trace_context(trace_id: str) -> str:
    """
    设置当前协程/线程的 Trace ID 上下文（contextvars实现，协程安全）

    **国金miniQMT多账户适配**:
    支持在多账户并发场景下，为每个账户独立设置 Trace ID，避免 TLS 的线程串扰问题

    Args:
        trace_id: 严格 24 字符规范 ID（见 TraceIdGenerator.generate / validate）

    Returns:
        str: 与入参等价的 24 字符 Trace ID

    Raises:
        ValueError: 长度或格式不符合 TraceIdGenerator.validate
    """
    raw = str(trace_id)
    if len(raw) != TRACE_ID_LENGTH:
        raise ValueError(
            f"trace_id must be exactly {TRACE_ID_LENGTH} chars, got {len(raw)}"
        )
    if not TraceIdGenerator.validate(raw):
        raise ValueError(
            f"trace_id failed validation (expected PREFIX6_YYYYMMDD_RANDOM8HEX): {raw!r}"
        )
    _current_trace_ctx.set(raw)
    return raw


def get_trace_context() -> str:
    """
    获取当前上下文 Trace ID（24字符，协程安全）

    适用于：
    - 日志记录（自动携带到 ELK）
    - 异常上下文（Error Code 关联）
    - 性能监控（PerfTimer 自动携带）
    - miniQMT 多账户操作追踪
    """
    return _current_trace_ctx.get()


def apply_trace_for_miniqmt_callback(
    stored_trace_id: Optional[str],
    module: str = "executor",
) -> str:
    """
    在当前线程建立可用的 24 字符 Trace（XtQuant / miniQMT 原生回调线程专用）。

    Python ``ContextVar`` 不会随 miniQMT 派生的回调线程继承；若在回调内直接
    ``get_trace_context()``，往往长期停留在 ``DEFAULT_TRACE_CONTEXT_ID``。
    在 ``on_order`` / ``on_trade`` / ``on_connected`` 等入口首行调用本函数：

    - 若 ``stored_trace_id`` 已通过 ``TraceIdGenerator.validate``（例如执行器镜像的
      ``ExecutorCallback._current_trace_id``），则 ``set_trace_context`` 恢复该 ID；
    - 否则为 ``module`` 生成新 ID（如 ``hkcodex``、``executor``、``trade``）。

    Returns:
        已写入上下文的 24 字符 Trace ID（与 ``get_trace_context()`` 一致）。
    """
    if stored_trace_id:
        cand = str(stored_trace_id)
        if TraceIdGenerator.validate(cand):
            return set_trace_context(cand)
    return set_trace_context(TraceIdGenerator.generate(module))


def get_trace_context_safe(default: Optional[str] = None) -> str:
    """
    获取当前上下文 Trace ID；在仍为工厂占位符且调用方提供 ``default`` 时，用规范 ID 覆盖上下文。

    ``ContextVar`` 已配置 default，因此 ``get()`` 不会抛出 `LookupError`。当 ``default`` 非空且当前值等于
    `DEFAULT_TRACE_CONTEXT_ID` 时，视为尚未建立业务 trace，会调用 `set_trace_context(default)` 并返回之。

    Args:
        default: 可选；若提供且当前仍为占位符，须为可通过 `TraceIdGenerator.validate` 的 24 字符 ID

    Returns:
        str: 24 字符 Trace ID
    """
    current = _current_trace_ctx.get()
    if default is not None and current == DEFAULT_TRACE_CONTEXT_ID:
        return set_trace_context(default)
    return current


# ==============================================================================
# 向后兼容 API（测试/旧调用方适配层）
# ==============================================================================
def generate_trace_id(module: str, date: Optional[str] = None) -> str:
    """
    向后兼容的 Trace ID 生成函数名。

    历史代码/测试约定函数为 `generate_trace_id(module, date)`，
    当前实现使用 `TraceIdGenerator.generate()`，本函数仅做包装。
    """
    return TraceIdGenerator.generate(module=module, date=date)


# ==============================================================================
# 公开 API 列表（严格限制）
# ==============================================================================

__all__ = [
    "DEFAULT_TRACE_CONTEXT_ID",
    # Trace ID 生成与验证
    "TraceIdGenerator",
    "generate_trace_id",
    # 上下文变量（供高级用户直接操作，如多账户场景）
    "_current_trace_ctx",  # 命名保持与 quant_logger 兼容，但现位于 Layer 0
    # 便捷函数（业务层推荐入口）
    "get_trace_context",
    "set_trace_context",
    "get_trace_context_safe",
    "apply_trace_for_miniqmt_callback",
]


# ==============================================================================
# 模块自检（Layer 0 纯逻辑验证，零外部依赖）
# ==============================================================================

def _self_test():
    """
    模块自检（Phase 3 Layer 0 合规验证）

    **验证项**：
    1. Trace ID 生成与长度验证（24字符严格对齐）
    2. 前缀映射与 TraceConstants 一致性检查
    3. 上下文传递协程安全性（contextvars 基础功能）
    4. 国金 miniQMT 特定前缀（HKQ）验证
    5. 日期格式标准化（YYYYMMDD）
    6. 防御性编程（截断/填充逻辑）
    """
    print("[trace_context.py] Layer 0 Infrastructure Self-Test...")

    # 1. 基础生成测试（覆盖所有关键模块）
    test_modules = ['selector', 'executor', 'hkcodex', 'system', 'trade', 'audit', 'risk']
    for mod in test_modules:
        tid = TraceIdGenerator.generate(mod)
        assert len(tid) == TRACE_ID_LENGTH, \
            f"Length violation for {mod}: {len(tid)} != {TRACE_ID_LENGTH}"
        assert TraceIdGenerator.validate(tid), f"Validation failed for {mod}: {tid}"
        print(f"  [ok] {mod:15} -> {tid} (Len: {TRACE_ID_LENGTH})")

    # 2. 特定日期生成测试（确保格式固定）
    fixed_date = '20260315'
    tid_fixed = TraceIdGenerator.generate('reconcile', fixed_date)
    assert fixed_date in tid_fixed, "Date part missing in fixed date generation"
    print(f"  [ok] Fixed date generation: {tid_fixed}")

    # 3. 国金 miniQMT 前缀验证（关键业务适配；前缀 6 字符左对齐，含空格）
    hkq_tid = TraceIdGenerator.generate('hkcodex')
    assert hkq_tid[:6].strip() == 'HKQ', f"HKQ prefix error: {hkq_tid!r}"
    assert len(hkq_tid) == 24
    print(f"  [ok] Guojin miniQMT prefix (HKQ): {hkq_tid[:10]}...")

    # 4. 上下文传递验证（协程安全基础）
    test_tid = TraceIdGenerator.generate('system')
    set_trace_context(test_tid)
    retrieved = get_trace_context()
    assert retrieved == test_tid, f"ContextVars mismatch: {retrieved} != {test_tid}"
    print(f"  [ok] ContextVars (asyncio-safe): {retrieved[:20]}...")

    # 5. 组件解析测试（审计友好）
    components = TraceIdGenerator.extract_components(test_tid)
    assert components is not None, "Component extraction failed"
    assert 'prefix' in components and 'date' in components and 'random' in components
    assert components['module_hint'] == 'system'  # 反向查找验证
    print(f"  [ok] Component extraction: {components}")

    # 6. 占位符 + get_trace_context_safe：应用调用方 default 并写入上下文
    _current_trace_ctx.set(DEFAULT_TRACE_CONTEXT_ID)
    fallback = TraceIdGenerator.generate("audit")
    safe_tid = get_trace_context_safe(fallback)
    assert safe_tid == fallback
    assert get_trace_context() == fallback
    assert len(safe_tid) == TRACE_ID_LENGTH
    print(f"  [ok] Safe retrieval with default: {safe_tid[:20]}...")

    # 7. set_trace_context 拒绝非规范 ID
    try:
        set_trace_context("THIS_IS_A_VERY_LONG_TRACE_ID_THAT_EXCEEDS_24_CHARS")
        raise AssertionError("expected ValueError for overlong trace_id")
    except ValueError:
        print("  [ok] Overlong trace_id rejected (ValueError)")
    try:
        set_trace_context("SHORT")
        raise AssertionError("expected ValueError for short trace_id")
    except ValueError:
        print("  [ok] Short trace_id rejected (ValueError)")

    valid_tid = "SYSTEM_20260315_DEADBEEF"
    assert TraceIdGenerator.validate(valid_tid)
    result = set_trace_context(valid_tid)
    assert result == valid_tid
    print(f"  [ok] set_trace_context accepts canonical 24-char ID: {result}")

    print("[trace_context.py] Layer 0 Self-test completed successfully")
    print(f"[trace_context.py] Ready for Phase 2: Layer 2 decoupling (quant_logger/perf_monitor)")


# Phase 3: Layer 0 模块独立自检（执行：python -m common.infra.trace_context）
if __name__ == "__main__":
    _self_test()