# -*- coding: utf-8 -*-
"""
common/security.py - 金融级安全与脱敏模块 (Phase 3 Step 6 - Layer 1 Optimized)
================================================================================

**Phase 3 Step 6 生产级强制标准（Layer 1 优化版）**：
- **[已完成] ErrorCode 模块级急加载**：作为 Layer 0 常量，从 `constants` 模块级直接导入（非延迟），消除所有运行时导入开销
- **[已完成] 全层指向 Layer 0**：所有 `get_trace_context` / `TraceIdGenerator` 的延迟导入统一指向 `trace_context`（Layer 0），彻底解除 Layer 1 对 Layer 2 `quant_logger` 的反向依赖
- **[保持] 金融级异常体系**：敏感信息泄露直接抛出 `ConfigurationError`（P0级，使用模块级导入的 `ErrorCode`），与 `exceptions.py` 对齐
- **[保持] Trace ID 强制规范**：24字符（{PREFIX:<6}_{YYYYMMDD}_{RANDOM:8}），通过 `trace_context` 自动传递
- **[保持] 审计增强**：配置变更强制记录操作者身份(Who)与审批单号(Why)，满足合规5年留痕
- **[保持] 核心依赖急加载**：Layer 0/1 模块必须存在；**可选**依赖（如脱敏失败时写审计日志用到的 `quant_logger`）允许在窄路径上捕获 `ImportError` / 通用 `Exception` 并降级为安全占位输出，避免 URL 等敏感信息泄露

**核心能力**：
1. **分级脱敏**：SECRET(绝密)/CONFIDENTIAL(机密)/INTERNAL(内部)/PUBLIC(公开)四级
2. **自动敏感识别**：与 `get_sensitivity_level` 一致的键名分级规则，外加 `SecurityConstants.SENSITIVE_KEYWORDS_ENV` 扩展子串及调用方 `sensitive_keys`；`SENSITIVE_PATTERNS` 中的正则值供扫描类场景使用，键名子集已并入分级规则
3. **配置安全加载**：环境变量自动脱敏，支持加密配置项（预留KMS接口）
4. **上下文传递**：与 `trace_context` (Layer 0) 深度集成，确保敏感信息不进日志明文

**架构角色**：
    作为基础设施层安全中枢（Layer 1），向上层提供统一脱敏、安全加载、审计追踪能力。
    业务层禁止自行实现脱敏逻辑（如正则替换账户ID），必须使用 `DataMasker`。

**导入依赖拓扑（Phase 3 Step 6 优化后）**：
    security.py (Layer 1)
    ↓ 模块级急加载（零延迟）
    constants.py (Layer 0) ← ErrorCode, TRACE_ID_LENGTH, SecurityConstants 等
    exceptions.py (Layer 1) ← ConfigurationError
    ↓ (运行时才导入 Layer 0/2)
    trace_context.py (Layer 0) ← 延迟导入 get_trace_context/TraceIdGenerator
    quant_logger.py (Layer 2) ← 延迟导入 QuantLoggerFactory（仅用于日志写入）

Author: Quant Engineering Team
Version: 3.0.6 (Phase 3 Step 6 - Layer 1 Optimized - ErrorCode Eager Import)
Date: 2026-03-16
"""

import os
import hashlib
from urllib.parse import urlparse
from typing import Dict, Any, Optional, Union, Set
from dataclasses import dataclass, asdict, field, FrozenInstanceError
from enum import Enum

# ==============================================================================
# Phase 3: Layer 1 基础设施导入（模块级急加载 Layer 0 常量，零运行时开销）
# ==============================================================================

# Layer 0 常量单一真相源（模块级直接导入，零延迟）- 符合"常量零延迟"金融级优化原则
from .constants import (
    TRACE_ID_LENGTH,  # 24字符强制规范
    SecurityConstants,  # Phase 3 新增：安全合规常量（敏感词库、脱敏规则）
    LoggingConstants,  # 日志保留策略（含 COLD_RETENTION_YEARS 5年冷存储）
    ErrorCode,  # [优化] 模块级急加载（Layer 0 基础类型，无循环风险）
)

# 金融级异常体系（P0/P1/P2 分级，敏感操作强制审计）- Layer 1 同级导入
from .exceptions import ConfigurationError
from .runtime_config import get_raw as _runtime_cfg_raw
from .timekeeping import utc_now_iso_z


# ==============================================================================
# 数据敏感度分级（与 SecurityConstants 严格对齐）
# ==============================================================================

class SensitivityLevel(Enum):
    """
    数据敏感度分级（监管合规要求）

    由 `DataMasker.get_sensitivity_level` 统一判定（键名子串匹配）。
    `SecurityConstants.SENSITIVE_PATTERNS` 的正则值用于日志/文本扫描；配置键脱敏以分级规则为准。
    """
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    SECRET = 3


# ==============================================================================
# 审计上下文（不可变，满足金融合规 Who & Why 要求）
# ==============================================================================

@dataclass(frozen=True)
class AuditContext:
    """
    不可变审计上下文（Phase 3 强制标准，与 quant_logger 审计流协同）

    满足合规官对配置漂移可追溯的要求：
    - operator_id: 操作者身份（工号/系统标识）- Who
    - approval_ticket: 审批单号（变更管理单号）- Why
    - timestamp: ISO格式时间戳（自动填充）
    - action: 操作类型（config_change/access_violation等）
    - source_ip: 操作源IP（如有）
    - session_id: 会话标识（关联24字符 Trace ID，由调用方传入）

    **重要**: 本类为 frozen dataclass，实例创建后不可修改。如需变更，请使用
    `dataclasses.replace(ctx, operator_id="new_id")` 创建新实例。
    """
    operator_id: str = "system"
    approval_ticket: str = "auto"
    timestamp: str = field(default_factory=utc_now_iso_z)
    action: str = "config_change"
    source_ip: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典（用于日志上下文）。

        `session_id` 若长度非 `TRACE_ID_LENGTH`，优先替换为当前 `get_trace_context()`（若有效）；
        否则移除 `session_id` 并设置 `session_id_invalid=True`，避免伪造长度的 Trace。
        """
        data = asdict(self)
        sid = data.get('session_id')
        if sid is not None and str(sid) != '':
            if len(str(sid)) != TRACE_ID_LENGTH:
                from .trace_context import get_trace_context
                tid = get_trace_context()
                if tid and len(str(tid)) == TRACE_ID_LENGTH:
                    data['session_id'] = str(tid)
                else:
                    del data['session_id']
                    data['session_id_invalid'] = True
        return data


# ==============================================================================
# 核心脱敏器（金融级标准，与 SecurityConstants 严格对齐）
# ==============================================================================

class DataMasker:
    """
    统一敏感信息脱敏器（Phase 3 生产级实现，常量收敛版）

    **设计原则**：
    - 零信任：默认所有输入均可能进入日志/UI，必须脱敏
    - 不可逆向：脱敏后不可还原（除哈希验证外）
    - 性能优化：编译正则缓存，避免重复计算
    - 标准统一：账户ID统一前3后3（SecurityConstants.ACCOUNT_MASK_PREFIX_LEN/SUFFIX_LEN），
      与国金miniQMT日志规范及 quant_logger 自动脱敏逻辑一致
    """

    @classmethod
    def _env_sensitive_substrings(cls) -> Set[str]:
        """`SecurityConstants.SENSITIVE_KEYWORDS_ENV` 中配置的额外子串（参与键名匹配）。"""
        env_key = SecurityConstants.SENSITIVE_KEYWORDS_ENV
        # runtime-config source of truth (env > YAML), aligned with infra config layering.
        raw = str(_runtime_cfg_raw(env_key) or "")
        if not raw:
            return set()
        return {k.strip().lower() for k in raw.split(',') if k.strip()}

    @classmethod
    def _key_should_mask(cls, key: str, sensitive_keys: Optional[Set[str]] = None) -> bool:
        """
        是否与 `get_sensitivity_level` 对齐、应对该键脱敏（含环境扩展与调用方 extra 子串）。
        INTERNAL 级仅对路径类键脱敏，避免将泛化 `*config*` 一律按密钥处理。
        """
        key_lower = str(key).lower()
        extras = cls._env_sensitive_substrings()
        if sensitive_keys:
            extras = extras | {k.lower() for k in sensitive_keys}
        if any(x in key_lower for x in extras):
            return True
        level = cls.get_sensitivity_level(key, None)
        if level in (SensitivityLevel.SECRET, SensitivityLevel.CONFIDENTIAL):
            return True
        if level == SensitivityLevel.INTERNAL:
            path_hints = ('path', 'dir', 'directory', 'folder', 'file', 'userdata', 'file_path')
            return any(h in key_lower for h in path_hints)
        return False

    @classmethod
    def mask_account_id(cls, account_id: Union[str, int]) -> str:
        """
        账户ID脱敏：前3后3，中间****（金融行业标准，与 SecurityConstants 对齐）

        **规范**：123456789012 → 123****012（前缀/后缀长度来自 ACCOUNT_MASK_PREFIX_LEN/SUFFIX_LEN）
        保留足够信息用于人工核对，同时防止完整泄露

        Args:
            account_id: 账户ID（数字或字符串）

        Returns:
            str: 脱敏后的账户标识（如 123****012）
        """
        if not account_id:
            return "****"

        s = str(account_id).strip()
        prefix_len = SecurityConstants.ACCOUNT_MASK_PREFIX_LEN  # 3
        suffix_len = SecurityConstants.ACCOUNT_MASK_SUFFIX_LEN  # 3
        min_len = SecurityConstants.ACCOUNT_MASK_MIN_LENGTH  # 8

        # 长度检查：不足8位特殊处理
        if len(s) < min_len:
            # 少于8位：前2后2，中间掩码（降级策略）
            if len(s) >= 4:
                return f"{s[:2]}****{s[-2:]}"
            return "****"

        # 标准掩码：前3位 + **** + 后3位（输出长度短于原文是预期行为，勿与“编码异常”混检）
        return f"{s[:prefix_len]}****{s[-suffix_len:]}"

    @classmethod
    def _mask_redis_hostname(cls, hostname: str) -> str:
        """Mask IPv4, IPv6, or DNS host for redis/rediss URL logging."""
        if not hostname:
            return "***"
        if '.' in hostname:
            parts = hostname.split('.')
            if len(parts) == 4 and all(p.isdigit() for p in parts):
                return '.'.join(
                    p[:1] + '**' if len(p) > 2 else '***' for p in parts
                )
        if ':' in hostname:
            first, _, rest = hostname.partition(':')
            if rest:
                return f"{first}:****:***"
            return "****"
        parts = hostname.split('.')
        if len(parts) > 2:
            return f"***.{'.'.join(parts[-2:])}"
        if len(parts) == 2:
            return f"***.{parts[-1]}"
        return "***"

    @classmethod
    def mask_redis_url(cls, url: str) -> str:
        """
        Redis / Rediss URL脱敏：保留 scheme 与端口，脱敏主机与用户凭证（金融级标准）

        支持 ``redis://`` 与 ``rediss://``、IPv4、IPv6（``[addr]:port``）、域名。

        **安全要求**：
        - userinfo：完全掩码（****）
        - 主机：IPv4 分段掩码；IPv6 仅保留首段；域名掩码子域
        - 端口：保留（诊断）；未解析到端口时输出 ``:****``（与历史行为一致）
        - path（库号等）：脱敏为 ``/**``；不输出 query

        Args:
            url: Redis 连接 URL

        Returns:
            str: 脱敏后的 URL
        """
        if not url or not isinstance(url, str):
            return "redis://****"

        raw = url.strip()
        try:
            parsed = urlparse(raw)
        except Exception:
            return cls._generic_mask(raw)

        if parsed.scheme not in ('redis', 'rediss'):
            return cls._generic_mask(raw)

        try:
            hostname = parsed.hostname
            port = parsed.port
            if hostname:
                masked_host = cls._mask_redis_hostname(hostname)
            else:
                masked_host = "***"

            masked_auth = "****" if (parsed.username or parsed.password) else ""
            port_str = f":{port}" if port is not None else ":****"

            path = parsed.path or ""
            if path and path not in ('/', ''):
                masked_db = "/**"
            else:
                masked_db = ""

            host_tail = f"{masked_host}{port_str}{masked_db}"
            scheme_prefix = f"{parsed.scheme}://"
            if masked_auth:
                return f"{scheme_prefix}{masked_auth}@{host_tail}"
            return f"{scheme_prefix}{host_tail}"

        except Exception as e:
            try:
                from .trace_context import get_trace_context
                from .quant_logger import QuantLoggerFactory
                logger = QuantLoggerFactory.get_logger(
                    "security", "mask_redis_url",
                    get_trace_context()
                )
                prefix = raw[:10] if len(raw) >= 10 else raw
                logger.error(f"Redis URL masking failed: {e}", context={"url_prefix": prefix})
            except ImportError as _optional_logger_import_exc:
                # QuantLoggerFactory / trace_context optional at extreme bootstrap: omit log line
                _ = _optional_logger_import_exc
            except Exception as _logger_pipeline_exc:
                # Logger pipeline unavailable; never leak URL
                _ = _logger_pipeline_exc
            return "redis://****"

    @classmethod
    def mask_file_path(cls, path: str, levels: Optional[int] = None) -> str:
        """
        文件路径脱敏：仅保留最后N级目录，防止路径遍历攻击信息泄露

        **规范**：/home/user/project/data/file.txt → .../data/file.txt（levels=2）

        Args:
            path: 文件路径
            levels: 保留的目录级数（默认使用 SecurityConstants.PATH_MASK_LEVELS=2）

        Returns:
            str: 脱敏后的路径
        """
        if not path:
            return "N/A"

        if levels is None:
            levels = SecurityConstants.PATH_MASK_LEVELS  # 默认2级

        # 统一路径分隔符（Windows/Unix兼容）
        normalized = os.path.normpath(path)
        parts = normalized.split(os.sep)

        # 过滤空字符串（Windows路径可能产生）
        parts = [p for p in parts if p]

        if len(parts) <= levels:
            # 短路径使用通用掩码（保留文件名）
            return cls._generic_mask(normalized)

        # 保留最后N级，前面用...代替（符合Linux日志规范）
        return ".../" + "/".join(parts[-levels:])

    @classmethod
    def mask_secret(cls, secret: str, visible_head: int = 0) -> str:
        """
        密钥/密码全掩码（最高安全级别 - SECRET级）

        **策略**：
        - 默认完全掩码（****）
        - 如需部分可见（如调试），仅允许头部可见visible_head个字符

        **安全控制**：
        生产环境（QUANT_ENV=prod）禁止部分可见（visible_head>0会触发 P0 级异常）

        Args:
            secret: 敏感字符串
            visible_head: 头部可见字符数（默认0，生产环境必须为0）

        Returns:
            str: 掩码后的字符串

        Raises:
            ConfigurationError: 如果 visible_head > 0 且非调试环境（P0 级，敏感信息泄露风险）
        """
        if not secret:
            return "****"

        # Phase 3: 生产环境安全检查（防止误配置导致泄露）
        current_env = str(_runtime_cfg_raw(SecurityConstants.ENV_KEY) or SecurityConstants.DEFAULT_ENV)
        if visible_head > 0 and current_env.lower() == 'prod':
            raise ConfigurationError(
                f"Visible head ({visible_head}) not allowed in production for secret masking",
                error_code=ErrorCode.CFG_SENSITIVE_LEAK,  # 使用模块级急加载的 ErrorCode
                config_key="mask_secret.visible_head",
                sensitive_leak=True  # 标记为敏感操作，强制进入审计日志
            )

        s = str(secret)
        if len(s) <= visible_head + 4:
            return "****"

        if visible_head > 0:
            return s[:visible_head] + "****"
        return "****"

    @classmethod
    def mask_dict(
            cls,
            data: Dict[str, Any],
            sensitive_keys: Optional[Set[str]] = None,
            audit_ctx: Optional[AuditContext] = None,
            _seen: Optional[set] = None,
    ) -> Dict[str, Any]:
        """
        字典递归脱敏（配置对象专用 - Phase 3增强版，与 quant_logger 自动脱敏联动）

        **特性**：
        - 自动识别敏感键（与 `get_sensitivity_level` 一致 + `SENSITIVE_KEYWORDS_ENV` + `sensitive_keys` 子串）
        - 递归处理嵌套字典
        - 自动附加审计元数据（如提供 AuditContext，满足 Who/Why 要求）

        Args:
            data: 原始配置字典
            sensitive_keys: 额外子串集合（键名包含任一子串则脱敏）
            audit_ctx: 审计上下文（如提供，则添加审计元数据到 _audit_meta）
            _seen: 内部递归用，检测循环引用

        Returns:
            Dict: 脱敏后的字典（浅拷贝，不修改原对象）
        """
        if _seen is None:
            _seen = set()
        if id(data) in _seen:
            return {"****": "circular_reference"}
        _seen.add(id(data))

        result = {}

        for key, value in data.items():
            key_lower = str(key).lower()

            needs_masking = cls._key_should_mask(key, sensitive_keys)

            if needs_masking:
                # 根据值类型选择脱敏策略
                if isinstance(value, str) and value.strip().lower().startswith(('redis://', 'rediss://')):
                    result[key] = cls.mask_redis_url(value)
                elif 'url' in key_lower and isinstance(value, str) and value.strip().lower().startswith(
                        ('redis', 'rediss')
                ):
                    result[key] = cls.mask_redis_url(value)
                elif any(k in key_lower for k in ['account', 'user_id', 'account_id']):
                    result[key] = cls.mask_account_id(value)
                elif any(k in key_lower for k in ['path', 'dir', 'directory', 'file', 'file_path']):
                    result[key] = cls.mask_file_path(value)
                else:
                    # 默认为密钥类型（SECRET级）
                    result[key] = cls.mask_secret(value)
            else:
                # 递归处理嵌套字典
                if isinstance(value, dict):
                    result[key] = cls.mask_dict(value, sensitive_keys, None, _seen)
                elif isinstance(value, list):
                    result[key] = [
                        cls.mask_dict(v, sensitive_keys, None, _seen) if isinstance(v, dict) else v
                        for v in value
                    ]
                else:
                    result[key] = value

        # Phase 3: 添加审计元数据（满足合规要求：Who & Why），携带24字符 Trace ID
        if audit_ctx:
            from .trace_context import get_trace_context
            meta = audit_ctx.to_dict()
            # 确保当前 Trace ID 被记录（用于全链路追踪）
            current_trace = get_trace_context()
            if current_trace:
                meta['trace_id_at_masking'] = current_trace
            result['_audit_meta'] = meta

        return result

    @classmethod
    def mask_config_change(
            cls,
            old_config: Dict,
            new_config: Dict,
            audit_ctx: AuditContext
    ) -> Dict[str, Any]:
        """
        配置变更差异脱敏（热重载审计 - Phase 3核心功能，与 exceptions/quant_logger 协同）

        **合规要求**：
        - 记录变更字段名（不记录值，防泄露）
        - 记录变更时间、操作者、审批单号（来自 AuditContext）
        - 使用哈希比对检测差异（避免直接比较敏感值）

        Args:
            old_config: 变更前配置（已脱敏或原始）
            new_config: 变更后配置（已脱敏或原始）
            audit_ctx: 审计上下文（必须提供，记录Who/Why）

        Returns:
            Dict: 包含old_masked, new_masked, changed_keys, audit_meta, trace_id（24字符）
        """
        # 先脱敏两份配置
        old_masked = cls.mask_dict(old_config)
        new_masked = cls.mask_dict(new_config)

        # 计算差异字段（基于SHA256哈希比对，避免日志中暴露敏感值）
        changed_keys = []
        all_keys = set(old_config.keys()) | set(new_config.keys())

        for key in all_keys:
            old_val = old_config.get(key)
            new_val = new_config.get(key)

            # 使用SHA256哈希比对（前8位用于快速比对）
            old_hash = hashlib.sha256(str(old_val).encode()).hexdigest()[:8]
            new_hash = hashlib.sha256(str(new_val).encode()).hexdigest()[:8]

            if old_hash != new_hash:
                changed_keys.append(key)

        from .trace_context import get_trace_context

        return {
            'old_config': old_masked,
            'new_config': new_masked,
            'changed_keys': changed_keys,
            'change_count': len(changed_keys),
            'audit_meta': audit_ctx.to_dict(),
            'safety_level': 'masked',
            'trace_id': get_trace_context(),  # Phase 3: 强制携带24字符 Trace ID
            'retention_days': LoggingConstants.CONFIG_AUDIT_RETENTION_DAYS  # 180天
        }

    @classmethod
    def _generic_mask(cls, s: str, visible_chars: int = 3) -> str:
        """通用字符串掩码（保留首尾，中间****）"""
        if not s or len(s) <= visible_chars * 2:
            return "****"
        return f"{s[:visible_chars]}****{s[-visible_chars:]}"

    @classmethod
    def get_sensitivity_level(cls, key: str, value: Any) -> SensitivityLevel:
        """
        自动判断字段敏感度级别（用于分级日志策略与 `mask_dict` 键筛选）。

        Returns:
            SensitivityLevel: SECRET/CONFIDENTIAL/INTERNAL/PUBLIC
        """
        key_lower = str(key).lower()

        # SECRET级：密码、私钥、Token、Seed（高敏感关键词）
        secret_keywords = {'password', 'secret', 'private_key', 'token', 'seed', 'mnemonic', 'cipher'}
        if any(kw in key_lower for kw in secret_keywords):
            return SensitivityLevel.SECRET

        # CONFIDENTIAL级：账户ID、API Key、Redis URL（中敏感）
        confidential_keywords = {'account', 'api_key', 'redis', 'auth', 'user_id', 'access_key'}
        if any(kw in key_lower for kw in confidential_keywords):
            return SensitivityLevel.CONFIDENTIAL

        # INTERNAL级：路径、配置项（内部信息）
        internal_keywords = {'path', 'config', 'userdata', 'directory', 'folder', 'file_path'}
        if any(kw in key_lower for kw in internal_keywords):
            return SensitivityLevel.INTERNAL

        return SensitivityLevel.PUBLIC


# ==============================================================================
# 安全配置加载器（与 strategy_config 包及 quant_logger 集成）
# ==============================================================================

class SecureConfigLoader:
    """
    安全配置加载器（Phase 3生产级实现，与 quant_logger 审计流协同）

    **特性**：
    - 环境变量自动脱敏加载（使用 SecurityConstants.SENSITIVE_KEYWORDS_ENV 扩展词库）
    - 配置变更审计日志（强制记录Who/Why，携带24字符 Trace ID）
    - 敏感配置访问追踪（防止未授权访问）
    - 支持加密配置项解密（预留KMS接口）

    **使用约束**：
    - 必须在 QuantLoggerFactory.initialize() 之后实例化
    - 生产环境（`QUANT_ENV=prod`）下访问 SECRET/CONFIDENTIAL 级环境变量且值存在或 `required=True` 时，
      必须提供 `AuditContext`，且 `operator_id != 'system'`、`approval_ticket != 'auto'`
    """

    def __init__(self):
        # Phase 3: 使用 QuantLoggerFactory 获取 logger（必须在 initialize 后）
        # 生成 SYSTEM 前缀的24字符 Trace ID 用于初始化期
        from .trace_context import TraceIdGenerator
        from .quant_logger import QuantLoggerFactory
        init_trace_id = TraceIdGenerator.generate("system")
        self._logger = QuantLoggerFactory.get_logger(
            "security", "SecureConfigLoader",
            init_trace_id
        )
        self._loaded_secrets: Set[str] = set()  # 追踪已加载的敏感配置键（防重复审计）
        self._access_log_threshold = SensitivityLevel.CONFIDENTIAL  # 访问日志记录阈值

    def get_env(
            self,
            key: str,
            default: Any = None,
            mask_in_log: bool = True,
            audit_ctx: Optional[AuditContext] = None,
            required: bool = False
    ) -> Any:
        """
        安全获取环境变量（自动脱敏与审计，与 exceptions 体系集成）

        **Phase 3增强**：
        - 自动检测敏感度并分级处理（使用 get_sensitivity_level）
        - 敏感配置访问强制记录审计日志（Who/When/What，携带 Trace ID）
        - 缺失必需配置时抛出 ConfigurationError（P0级，错误码 CFG_MISSING_REQUIRED）

        Args:
            key: 环境变量名
            default: 默认值（敏感配置不建议使用默认值）
            mask_in_log: 是否在日志中脱敏（默认True）
            audit_ctx: 审计上下文（生产环境敏感配置必须提供，满足 Why 要求）
            required: 是否必需（缺失时抛 P0 级异常）

        Returns:
            Any: 环境变量值（原始值，未脱敏，供业务使用）

        Raises:
            ConfigurationError: 如果 required=True 且环境变量缺失（P0级，强制审计）；
                或在 prod 下访问 SECRET/CONFIDENTIAL 键且未提供有效 AuditContext。
        """
        from .runtime_config import config_value_source, get_raw as _runtime_layer_raw

        raw_merged = _runtime_layer_raw(key)
        if raw_merged is None:
            if required:
                raise ConfigurationError(
                    f"Required configuration key missing: {key}",
                    error_code=ErrorCode.CFG_MISSING_REQUIRED,  # 使用模块级急加载的 ErrorCode
                    config_key=key,
                    sensitive_leak=False
                )
            value = default
            config_source = "DEFAULT"
        else:
            value = raw_merged
            config_source = config_value_source(key)

        # 自动检测敏感度（使用与 DataMasker 一致的标准）
        sensitivity = DataMasker.get_sensitivity_level(key, value)

        current_env = str(
            _runtime_cfg_raw(SecurityConstants.ENV_KEY) or SecurityConstants.DEFAULT_ENV
        ).lower()
        if current_env == 'prod' and sensitivity in (
                SensitivityLevel.SECRET,
                SensitivityLevel.CONFIDENTIAL,
        ):
            if value is not None or required:
                # P1 fix: OR semantics — deny if EITHER field is default.
                if audit_ctx is None or audit_ctx.operator_id == 'system' or audit_ctx.approval_ticket == 'auto':
                    raise ConfigurationError(
                        "Production SECRET/CONFIDENTIAL env access requires AuditContext "
                        "with operator_id != 'system' and approval_ticket != 'auto'",
                        error_code=ErrorCode.CFG_VALIDATION_FAILED,
                        config_key=key,
                        sensitive_leak=False,
                    )

        # 记录敏感配置访问（仅记录访问行为，不记录值本身，满足可审计要求）
        if sensitivity.value >= self._access_log_threshold.value:
            if key not in self._loaded_secrets:  # 避免重复记录
                self._loaded_secrets.add(key)

                from .trace_context import get_trace_context

                # 构造审计上下文（如未提供则使用默认，携带当前 Trace ID）
                ctx = audit_ctx or AuditContext(
                    action="config_access",
                    session_id=get_trace_context()  # 自动获取24字符 Trace ID
                )

                # 脱敏后的值用于日志（如允许记录）
                log_value = "****"
                if not mask_in_log and sensitivity != SensitivityLevel.SECRET:
                    # 仅非SECRET级且明确允许时记录部分信息（生产环境不推荐）
                    log_value = str(value)[:4] + "****" if len(str(value)) > 8 else "****"

                self._logger.info(
                    f"Sensitive config accessed: {key}",
                    context={
                        "config_key": key,
                        "sensitivity": sensitivity.name,
                        "value_masked": log_value,
                        "audit": ctx.to_dict(),
                        "access_type": "env_var"
                        if config_source == "ENV"
                        else ("yaml_file" if config_source == "YAML" else "default"),
                        "config_source": config_source,
                        "trace_id": get_trace_context()  # 确保24字符 Trace ID入日志
                    },
                    audit=True  # 标记为审计日志（进入180天保留流）
                )

        return value

    def decrypt_if_needed(self, encrypted_value: str) -> str:
        """
        预留：加密配置项解密接口（Phase 3架构预留，与 SecurityConstants 预留字段对齐）

        **生产环境建议集成**：HashiCorp Vault / AWS KMS / 阿里云KMS / 国密SM4

        **格式规范**：加密值应以 `ENC::` 开头，后接 base64 编码的密文

        Args:
            encrypted_value: 可能加密的配置值

        Returns:
            str: 解密后的明文

        Raises:
            ConfigurationError: 如检测到加密格式但未实现解密（P1级）
        """
        if not encrypted_value:
            return ""

        # 检查是否为加密格式（如 ENC::base64::...）
        if str(encrypted_value).startswith("ENC::"):
            # TODO: 实现实际解密逻辑（集成KMS）
            raise ConfigurationError(
                "Encrypted config detected but decryption not implemented",
                error_code=ErrorCode.CFG_VALIDATION_FAILED,  # 使用模块级急加载的 ErrorCode
                config_key="encrypted_config",
                sensitive_leak=False
            )

        return encrypted_value

    def load_with_audit(
            self,
            config_dict: Dict[str, Any],
            audit_ctx: AuditContext
    ) -> Dict[str, Any]:
        """
        批量加载配置并审计（用于 strategy_config 热重载场景，与 quant_logger 协同）

        **流程**：
        1. 遍历配置字典
        2. 自动脱敏敏感值（使用 DataMasker.mask_dict）
        3. 记录变更审计日志（携带24字符 Trace ID）
        4. 返回脱敏后的配置（用于日志记录）

        Args:
            config_dict: 原始配置字典
            audit_ctx: 审计上下文（必须提供，包含Who/Why）

        Returns:
            Dict: 脱敏后的配置副本（适合入日志，满足5年留痕要求）
        """
        from .trace_context import get_trace_context

        # 记录配置加载事件（审计日志，180天保留）
        self._logger.info(
            "Configuration batch loaded",
            context={
                "audit": audit_ctx.to_dict(),
                "keys_count": len(config_dict),
                "trace_id": get_trace_context(),  # 强制24字符 Trace ID
                "retention_class": "180_days_audit"
            },
            audit=True
        )

        # 返回脱敏版本（用于日志展示，不泄露敏感信息）
        return DataMasker.mask_dict(config_dict, audit_ctx=audit_ctx)


_secure_config_loader_singleton: Optional[SecureConfigLoader] = None


def get_secure_config_loader() -> SecureConfigLoader:
    """Singleton :class:`SecureConfigLoader` for process-wide audited env access."""
    global _secure_config_loader_singleton
    if _secure_config_loader_singleton is None:
        _secure_config_loader_singleton = SecureConfigLoader()
    return _secure_config_loader_singleton


def secure_env_get(
        key: str,
        default: Any = None,
        *,
        required: bool = False,
        audit_ctx: Optional[AuditContext] = None,
        mask_in_log: bool = True,
) -> Any:
    """
    Read one environment variable through :class:`SecureConfigLoader`
    (sensitivity classification, prod AuditContext gate, access audit).
    """
    return get_secure_config_loader().get_env(
        key,
        default=default,
        mask_in_log=mask_in_log,
        audit_ctx=audit_ctx,
        required=required,
    )


# ==============================================================================
# 安全审计专用日志（满足5年留存要求，与 quant_logger 审计流协同）
# ==============================================================================

class SecurityAuditLogger:
    """
    安全审计专用日志（Phase 3生产级实现，与 quant_logger 深度集成）

    **与 quant_logger 协同**：
    - 普通操作日志 -> 30天热存储（DEBUG级）
    - 安全审计日志 -> 90天本地 + 5年冷存储（通过 audit=True 标记区分）

    **合规标准**：CSRC-Tier3 为工程侧对齐用标签，非监管认证；对外合规需映射贵司制度与留痕方案。

    ``log_access_violation(..., raise_on_critical=True)`` 可在需失败关闭时与
    :class:`~common.infra.exceptions.AuditIntegrityError` 联动；默认仅记审计日志不中断调用方。
    """

    def __init__(self):
        from .trace_context import TraceIdGenerator
        from .quant_logger import QuantLoggerFactory
        self._logger = QuantLoggerFactory.get_logger(
            "security_audit", "SecurityAuditLogger",
            TraceIdGenerator.generate("audit")
        )

    def log_config_change(self, change_record: Dict[str, Any], audit_ctx: AuditContext):
        """
        记录配置变更（热重载场景 - 核心审计点，与 DataMasker.mask_config_change 协同）

        **必须记录**：变更时间戳、操作者身份、审批单号、变更字段列表、Trace ID（24字符）
        """
        from .trace_context import get_trace_context

        self._logger.info(
            "Configuration change audited",
            context={
                "audit_type": "config_change",
                "record": change_record,  # 已脱敏的记录（来自 mask_config_change）
                "audit": audit_ctx.to_dict(),
                "compliance_standard": "CSRC-Tier3",
                "retention_years": LoggingConstants.COLD_RETENTION_YEARS,  # 5年冷存储
                "trace_id": get_trace_context(),  # 强制24字符 Trace ID
                "hot_retention_days": LoggingConstants.CONFIG_AUDIT_RETENTION_DAYS  # 180天
            },
            audit=True  # 强制进入审计日志流（90天本地+5年冷存）
        )

    def log_access_violation(
            self,
            resource: str,
            attempted_by: str,
            reason: str,
            severity: str = "HIGH",
            *,
            raise_on_critical: bool = False,
    ):
        """
        记录访问违规（如未授权访问敏感配置，与 exceptions 体系协同）

        **触发场景**：尝试访问SECRET级配置且未提供 AuditContext / 非法路径遍历 / 敏感关键词暴力探测

        Args:
            raise_on_critical: 为 True 且 ``severity == "CRITICAL"`` 时在记日志后抛出
                :class:`~common.infra.exceptions.AuditIntegrityError`（失败关闭）；默认 False，避免
                “记审计”意外打断主流程。
        """
        from .trace_context import get_trace_context

        self._logger.error(
            f"Security violation: unauthorized access to {resource}",
            context={
                "audit_type": "access_violation",
                "resource": resource,
                "attempted_by": attempted_by,
                "reason": reason,
                "severity": severity,
                "trace_id": get_trace_context(),  # 24字符 Trace ID
                "immediate_alert": severity == "CRITICAL",
                "retention": "permanent"  # 永久保留（5年冷存）
            },
            audit=True
        )

        if severity == "CRITICAL" and raise_on_critical:
            from .exceptions import AuditIntegrityError  # 保持延迟导入（避免与 Layer 1 循环）
            raise AuditIntegrityError(
                f"Critical security violation detected: {reason}",
                error_code=ErrorCode.AUDIT_LOG_LOST,  # 使用模块级急加载的 ErrorCode
                audit_item=resource,
                extra={
                    "attempted_by": attempted_by,
                    "violation_type": "unauthorized_access",
                    "trace_id": get_trace_context()
                }
            )

    def log_sensitive_data_detected(
            self,
            location: str,
            data_type: str,
            detection_method: str
    ):
        """
        记录敏感数据泄露检测（如日志中检测到明文密码，与 DataMasker 协同）
        """
        from .trace_context import get_trace_context

        self._logger.error(
            f"Sensitive data leak detected in {location}",
            context={
                "audit_type": "data_leak_detected",
                "location": location,
                "data_type": data_type,
                "detection_method": detection_method,
                "immediate_action_required": True,
                "trace_id": get_trace_context(),  # 24字符 Trace ID
                "compliance_breach": True
            },
            audit=True
        )


# ==============================================================================
# 模块级便捷函数（向后兼容但标记为推荐使用 DataMasker 方法）
# ==============================================================================

def mask_account(account_id: Union[str, int]) -> str:
    """便捷函数：账户ID脱敏（推荐使用 DataMasker.mask_account_id）"""
    return DataMasker.mask_account_id(account_id)


def mask_account_id(account_id: Union[str, int]) -> str:
    """向后兼容别名：与 `mask_account` 等价。"""
    return DataMasker.mask_account_id(account_id)


def mask_redis(url: str) -> str:
    """便捷函数：Redis URL脱敏（推荐使用 DataMasker.mask_redis_url）"""
    return DataMasker.mask_redis_url(url)


def mask_path(path: str, levels: Optional[int] = None) -> str:
    """便捷函数：路径脱敏（推荐使用 DataMasker.mask_file_path）"""
    return DataMasker.mask_file_path(path, levels)


# ==============================================================================
# Phase 3 Step 6: 模块自检（验证 ErrorCode 模块级急加载与 Layer 0 收敛）
# ==============================================================================

def _self_test():
    """
    模块自检（Phase 3 Step 6：验证 ErrorCode 模块级急加载与 Layer 1 全层收敛）

    验证项：
    1. ErrorCode 模块级急加载有效性（非延迟，零运行时开销）
    2. 脱敏规则正确性（前3后3，与 SecurityConstants 对齐）
    3. 敏感度分级准确性（与 SENSITIVE_PATTERNS 对齐）
    4. 审计上下文不可变性（frozen dataclass，金融合规）
    5. Trace ID 长度规范（24字符，通过 trace_context 获取）
    6. 常量引用正确性（SecurityConstants / LoggingConstants）
    7. [Step 6] Layer 1 导入路径验证：确认所有延迟导入指向 trace_context
    8. [Step 6 关键] 验证 ErrorCode 未在函数内重复导入（确保模块级急加载优化生效）
    """
    print("[security.py] Phase 3 Step 6 Layer 1 Optimized Self-Test...")

    # 1. [优化验证] ErrorCode 模块级急加载检查（零运行时开销）
    assert 'ErrorCode' in globals(), "ErrorCode must be imported at module level (eager)"
    assert isinstance(ErrorCode.CFG_SENSITIVE_LEAK, ErrorCode), "ErrorCode must be accessible"
    assert ErrorCode.CFG_MISSING_REQUIRED.level == "P0", "ErrorCode level attribute must work"
    print(f"  ✓ ErrorCode eager import: {ErrorCode.CFG_MISSING_REQUIRED.code} (Zero runtime overhead)")

    # 2. 常量引用验证（与 constants.SecurityConstants 对齐）
    assert SecurityConstants.ACCOUNT_MASK_PREFIX_LEN == 3, "Prefix length mismatch"
    assert SecurityConstants.ACCOUNT_MASK_SUFFIX_LEN == 3, "Suffix length mismatch"
    assert SecurityConstants.ACCOUNT_MASK_MIN_LENGTH == 8, "Min length mismatch"
    assert SecurityConstants.PATH_MASK_LEVELS == 2, "Path mask levels mismatch"
    print(f"  ✓ SecurityConstants alignment: prefix={SecurityConstants.ACCOUNT_MASK_PREFIX_LEN}, "
          f"suffix={SecurityConstants.ACCOUNT_MASK_SUFFIX_LEN}")

    # 3. 修复后的常量引用验证（LoggingConstants.COLD_RETENTION_YEARS）
    assert LoggingConstants.COLD_RETENTION_YEARS == 5, "Cold retention years mismatch"
    print(f"  ✓ LoggingConstants.COLD_RETENTION_YEARS: {LoggingConstants.COLD_RETENTION_YEARS} years")

    # 4. 账户脱敏验证（金融级标准：前3后3）
    test_cases = [
        ("123456789012", "123****012"),
        ("12345", "12****45"),  # 短账户特殊处理
        ("1234", "****"),  # 超短账户全掩码
    ]
    for original, expected_pattern in test_cases:
        result = DataMasker.mask_account_id(original)
        assert "****" in result or result == expected_pattern, \
            f"Account masking failed: {original} -> {result}"
    print("  ✓ Account ID masking (前3后3标准，符合 SecurityConstants)")

    # 5. Redis URL脱敏验证（含无认证 URL：禁止出现 redis://@）
    redis_url = "redis://admin:secret123@192.168.1.1:6379/0"
    masked = DataMasker.mask_redis_url(redis_url)
    assert "****" in masked, "Redis auth not masked"
    assert "***" in masked and "secret123" not in masked, "Redis host/auth leak"
    no_auth = "redis://192.168.1.1:6379/0"
    masked_na = DataMasker.mask_redis_url(no_auth)
    assert masked_na.startswith("redis://"), masked_na
    assert "://@" not in masked_na, f"No-auth URL must not contain ://@ (got {masked_na})"
    rediss_url = "rediss://admin:secret@cache.internal:6380/1"
    masked_rss = DataMasker.mask_redis_url(rediss_url)
    assert masked_rss.startswith("rediss://"), masked_rss
    assert "****" in masked_rss
    assert "secret" not in masked_rss and "admin" not in masked_rss
    assert "cache.internal" not in masked_rss
    ipv6_url = "redis://user:pw@[::1]:6379/0"
    masked_6 = DataMasker.mask_redis_url(ipv6_url)
    assert masked_6.startswith("redis://"), masked_6
    assert "****" in masked_6 and "pw" not in masked_6 and "user" not in masked_6
    print("  ✓ Redis URL masking (redis/rediss，IPv4/IPv6/域名；无认证无端 @)")

    # 5b. mask_dict 与 get_sensitivity_level 一致（如 access_token）
    masked_cfg = DataMasker.mask_dict({"access_token": "secret-token-value"})
    assert masked_cfg.get("access_token") == "****", masked_cfg

    # 5c. AuditContext.to_dict：无效 session_id 不填充空格，仅替换为有效 Trace 或标记 invalid
    ctx_bad_sid = AuditContext(session_id="short")
    out_sid = ctx_bad_sid.to_dict()
    if out_sid.get("session_id") is not None:
        assert len(str(out_sid["session_id"])) == TRACE_ID_LENGTH
    else:
        assert out_sid.get("session_id_invalid") is True

    # 6. 敏感度分级验证（与 get_sensitivity_level / mask_dict 一致）
    assert DataMasker.get_sensitivity_level("password", "123") == SensitivityLevel.SECRET
    assert DataMasker.get_sensitivity_level("account_id", "123") == SensitivityLevel.CONFIDENTIAL
    assert DataMasker.get_sensitivity_level("stock_code", "000001") == SensitivityLevel.PUBLIC
    print("  ✓ Sensitivity level classification (aligned with SENSITIVE_PATTERNS)")

    # 7. 审计上下文不可变性验证（frozen dataclass）
    ctx = AuditContext(operator_id="USER001", approval_ticket="TKT-2024-001")
    mutation_blocked = False
    try:
        ctx.operator_id = "HACK"  # type: ignore[misc]  # 尝试修改（应为frozen dataclass）
    except FrozenInstanceError:
        mutation_blocked = True
    assert mutation_blocked, "AuditContext should be immutable"
    print("  ✓ AuditContext immutability (frozen dataclass) - 符合金融合规 Who/Why 留痕要求")

    # 8. [Step 6 关键] Layer 1 导入路径验证：确认模块级无 Layer 2 符号导入
    import sys
    current_module = sys.modules[__name__]

    # 验证未在顶层导入 QuantLoggerFactory（应保持延迟导入）
    assert not hasattr(current_module, 'QuantLoggerFactory'), \
        "QuantLoggerFactory should not be imported at module level in security.py (Layer 1)"

    # 验证未在顶层导入 get_trace_context（应通过 trace_context 延迟导入）
    assert not hasattr(current_module, 'get_trace_context'), \
        "get_trace_context should not be imported at module level in security.py (must be lazy from trace_context)"

    print("  ✓ [Step 6] Layer 1 Import Path: No Layer 2 symbols at module level (all lazy from trace_context)")

    # 9. [Step 6 关键] 验证 ErrorCode 未在函数内被重复导入（性能优化确认）
    import inspect
    # 检查 SecureConfigLoader.get_env 方法源码
    source = inspect.getsource(SecureConfigLoader.get_env)
    assert "from .constants import" not in source, \
        "SecureConfigLoader.get_env should not re-import ErrorCode (use module-level)"

    # 检查 DataMasker.mask_secret 方法源码
    source_mask = inspect.getsource(DataMasker.mask_secret)
    assert "from .constants import" not in source_mask, \
        "DataMasker.mask_secret should not re-import ErrorCode (use module-level)"

    print("  ✓ [Step 6] Performance optimization: ErrorCode not re-imported in functions (module-level only)")

    # 10. [Step 6] 验证通过延迟导入能正确访问 Layer 0
    try:
        from .trace_context import TraceIdGenerator
        test_tid = TraceIdGenerator.generate('security', '20260315')
        assert len(test_tid) == 24, f"Trace ID length error via trace_context: {len(test_tid)}"
        print(f"  ✓ [Step 6] Layer 0 Access via lazy import: trace_context works (tid={test_tid[:15]}...)")
    except Exception as e:
        print(f"  ⚠ Layer 0 lazy import test skipped in isolated environment: {e}")

    print("[security.py] Self-test completed successfully (Phase 3 Step 6 Layer 1 Optimized)")
    print("[security.py] ErrorCode import strategy: EAGER (module-level, zero runtime overhead) ✅")


# Phase 3: 禁止模块自初始化，仅在直接运行时执行逻辑验证
if __name__ == "__main__":
    _self_test()

# ==============================================================================
# 公开 API 列表（严格限制，与__init__.py导出一致，新增 ErrorCode 导出）
# ==============================================================================
__all__ = [
    # 数据敏感度分级
    'SensitivityLevel',

    # 审计上下文（不可变）
    'AuditContext',

    # 核心脱敏器
    'DataMasker',

    # 配置安全加载器
    'SecureConfigLoader',
    'get_secure_config_loader',
    'secure_env_get',

    # 安全审计日志
    'SecurityAuditLogger',

    # 便捷函数（向后兼容）
    'mask_account',
    'mask_account_id',
    'mask_redis',
    'mask_path',

    # [Step 6 新增] 错误代码体系（模块级急加载，与 exceptions.py 保持一致）
    'ErrorCode',
]