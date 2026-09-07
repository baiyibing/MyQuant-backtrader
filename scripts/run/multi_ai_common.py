# -*- coding: utf-8 -*-
"""多 agent 评审/核查工具的共享 agent 基础设施（命令构造 + cursor 解析 + PRESETS + run_agent）。

抽取自 run_multi_ai_review.py + run_multi_ai_period_verify.py（此前两处近乎逐字复制）。
**agent 模型配置集中在此**——改一家模型只改本文件一处（历史教训：cursor v2026.07.13
ID 迁移 + kimi K3 + qoder Qwen3.8-Max 曾被迫同步改 2 脚本 + 3 提示词 5 处）。

各编排脚本（review / period_verify）`from multi_ai_common import ...` 后，保留各自的
任务专属部分（FRAMEWORK_PROMPT / role-suffix / main）。doc_verify 经
importlib 复用 period_verify，传递复用本模块（含 run_agent）。

2026-07-18 增补（cursor headless 官方文档对齐，https://cursor.com/docs/cli/headless）：
- cursor 命令加 ``--workspace <repo_root>`` 显式钉仓根；
- ``cursor_list_models`` / ``check_cursor_models`` / ``preflight_cursor_models``：
  mixed 预设 ``cursor:<model>`` 变体在 fan-out 前预检（模型 ID 随 CLI 自更新漂移，
  预检不可用仅告警不阻断）；
- ``run_agent`` 上移本模块（此前 review/period_verify 两处逐字复制），并加
  **空输出 stub 自动重试**（cursor r2/r4 实测 rc=0 但正文为空的事故）。
- 2026-08-07：并行多路 ``cursor:<model>`` 会抢写 ``~/.cursor/cli-config.json``
  （r2 实测 ``EPERM rename ...cli-config.json.*.tmp``）。``run_agent`` 对 cursor*
  自动设独立 ``CURSOR_CONFIG_DIR``（种子复制 cli-config / agent-cli-state；**不**改
  HOME/USERPROFILE，避免鉴权失效）。官方：cursor.com/docs/cli/reference/configuration。

关联：docs/engineering/multi-ai-review-workflow.md（runbook）
"""

from __future__ import annotations

import os
import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _parse_version_stamp(path: Path) -> dict[str, str]:
    """Parse the small ``key=value`` stamp emitted by fan-out orchestrators."""
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            out[key] = value.strip()
    return out or {"raw": path.read_text(encoding="utf-8")}


def _write_version_manifest(
    out_dir: Path,
    *,
    version_kind: str,
    stamps: dict[str, dict[str, str]],
) -> None:
    manifest_path = out_dir / "_version_manifest.json"
    data: dict[str, object] = {"schema_version": 1}
    if manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            data = {"schema_version": 1}
    data["schema_version"] = 1
    versions = data.get(version_kind)
    if not isinstance(versions, dict):
        versions = {}
        data[version_kind] = versions
    versions.update(stamps)
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def merge_parallel_artifacts(
    parallel_root: Path,
    out_dir: Path,
    *,
    version_filename: str,
    version_kind: str,
) -> None:
    """Promote parallel outputs to the review root and remove the scratch tree.

    Agent outputs remain canonical ``out_dir/<agent>.md`` files. Per-agent version
    stamps are compacted into ``out_dir/_version_manifest.json``. The scratch
    directory is removed only after all copies and the manifest write succeed.
    """
    if not parallel_root.is_dir():
        return
    if parallel_root.parent.resolve() != out_dir.resolve():
        raise ValueError(
            f"parallel scratch parent mismatch: {parallel_root} != {out_dir / '_parallel'}"
        )
    stamps: dict[str, dict[str, str]] = {}
    for agent_dir in sorted(parallel_root.iterdir()):
        if not agent_dir.is_dir():
            continue
        agent_name = agent_dir.name
        agent_output = agent_dir / f"{agent_name}.md"
        if agent_output.is_file():
            shutil.copy2(agent_output, out_dir / agent_output.name)
        version_path = agent_dir / version_filename
        if version_path.is_file():
            stamps[agent_name] = _parse_version_stamp(version_path)
    if stamps:
        _write_version_manifest(out_dir, version_kind=version_kind, stamps=stamps)
    shutil.rmtree(parallel_root)


# ── cursor-agent node 自动发现（自更新 CLI，取最新版本目录）──────────────
def _discover_cursor_agent_dir() -> Path:
    """定位 cursor-agent 安装目录（Windows AppData + Linux XDG + SYSTEM fallback）。

    自托管 runner（win11-dev）以 ``NT AUTHORITY\\SYSTEM`` 计划任务运行（2026-08-04 实测），
    SYSTEM 的 ``Path.home()`` = ``C:\\Windows\\System32\\config\\systemprofile``，其下无
    cursor-agent → 回退枚举 ``C:\\Users\\*\\AppData\\Local\\cursor-agent``（排除系统内建目录），
    取任一存在 versions 的用户目录。正常交互会话走 ``Path.home()`` 直连，行为不变。

    Linux（2026-08-16）：官方安装在 ``~/.local/share/cursor-agent``；本机曾用
    ``~/AppData/Local/cursor-agent`` 软链骗 Windows 发现逻辑。现优先 XDG 路径，
    AppData 软链仅作兼容回退。
    """
    candidates = []
    if sys.platform == "win32":
        candidates.append(Path.home() / "AppData/Local/cursor-agent")
    else:
        candidates.append(Path.home() / ".local/share/cursor-agent")
        candidates.append(Path.home() / "AppData/Local/cursor-agent")
    for cand in candidates:
        if (cand / "versions").is_dir():
            return cand
    _users_root = Path("C:/Users")
    if _users_root.is_dir():
        for _u in sorted(_users_root.iterdir()):
            if _u.name.lower() in ("public", "default", "default user", "all users"):
                continue
            _cand = _u / "AppData/Local/cursor-agent"
            if (_cand / "versions").is_dir():
                return _cand
    return candidates[0]



def _ensure_cursor_helpers_executable(ver_dir: Path) -> None:
    """Linux 安装包里 rg/cursorsandbox 常是 644，spawn 报 EACCES，长评审空转。"""
    if sys.platform == "win32":
        return
    for name in ("rg", "cursorsandbox", "crepectl", "cursor-askpass"):
        helper = ver_dir / name
        if helper.is_file():
            try:
                mode = helper.stat().st_mode
                if not mode & stat.S_IXUSR:
                    # The helper is launched by its owning Cursor user. Check
                    # actual mode: ACL/root may make os.access() misleading.
                    # Do not broaden execution permission to group/other.
                    helper.chmod(mode | stat.S_IXUSR)
            except OSError:
                pass


def _resolve_cursor_node() -> tuple[str, str]:
    """Auto-discover latest cursor-agent version → (node_exe, index_js) paths.

    Bypasses cursor-agent.cmd/.ps1 because PowerShell corrupts Chinese UTF-8
    stdin on Windows (verified 2026-07-08: direct Node works; .cmd→.ps1→Node
    causes hanging/empty output with long Chinese prompts piped via stdin).
    """
    _agent_dir = _discover_cursor_agent_dir()
    _versions_dir = _agent_dir / "versions"
    if not _versions_dir.is_dir():
        raise FileNotFoundError(f"cursor-agent versions dir not found: {_versions_dir}")
    _latest = None
    _latest_int = 0
    _pat = re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})(?:-\d{2}-\d{2}-\d{2})?-[a-f0-9]+$")
    for _d in _versions_dir.iterdir():
        if not _d.is_dir():
            continue
        _m = _pat.match(_d.name)
        if not _m:
            continue
        _ver_int = int(_m.group(1)) * 10000 + int(_m.group(2)) * 100 + int(_m.group(3))
        if _ver_int > _latest_int:
            _latest_int = _ver_int
            _latest = _d.name
    if not _latest:
        raise FileNotFoundError(f"No version directories found in {_versions_dir}")
    _ver_dir = _versions_dir / _latest
    _ensure_cursor_helpers_executable(_ver_dir)
    if sys.platform == "win32":
        _node = _ver_dir / "node.exe"
    else:
        _node = _ver_dir / "node"
        if not _node.is_file():
            _node = _ver_dir / "node.exe"
    _index_js = str(_ver_dir / "index.js")
    return str(_node), _index_js


try:
    CURSOR_NODE_EXE, CURSOR_INDEX_JS = _resolve_cursor_node()
except FileNotFoundError:
    # Windows-only install tree. Linux CI / hosts without cursor-agent stay importable.
    CURSOR_NODE_EXE, CURSOR_INDEX_JS = "", ""


# ── 命令构造（模型配置在此！改一家模型只改这里）──────────────────────────
def codex_cmd(prompt: str) -> list[str]:
    """codex CLI headless（``codex exec``，cmd_arg 形态）。

    v0.144.5 实测（2026-07-19，`exec --help` / 三形态实跑；调用细节 SSOT 见
    ``docs/prompts/Codex-CLI-Headless模式完整指南.md`` 附录）；v0.147.0（2026-08-11 核对
    GitHub openai/codex @ rust-v0.147.0 源码 + release notes，无命令形态变化）。
    - 模型/供应商走 ``~/.codex/config.toml``：``model=deepseek-v4-flash`` 经本地 cc-switch 代理（2026-08-17 核：config.toml 现值）
      ``127.0.0.1:15721``（``model_provider="custom"``），无 ``-m``。
    - **审批/沙盒由 config 管**（``--ask-for-approval``/``-a`` 是**交互式** ``codex`` 的 flag，
      ``codex exec`` 从未提供过——早前「已移除」表述不准确）：本仓 full-auto 配置
      ``approval_policy="never"`` + ``sandbox_mode="workspace-write"``
      （幂等脚本 ``scripts/ops/configure_codex_fullauto.py``；升级后会丢键，须重跑——
      2026-07-19 实测漂移过一次）。指南「exec 默认 read-only」对本机 config 不适用。
    - ``--full-auto``：**v0.147.0 已正式移除**（release notes + PR #36054：
      use ``--sandbox workspace-write`` instead；v0.144.5 尚是 hidden+deprecation 警告）。
      本命令从不传它（走 config），无影响。
    - ``--ephemeral``：一次性评审不留 rollout 会话存档（实测 rc=0）。
    - 0.147.0 可选新 flag（本命令未用）：``--sandbox/-s``、``--approve-for-me``、
      ``-o/--output-last-message``、``approval_policy`` 新增合法值 ``granular``。
    - **双二进制陷阱（2026-07-19 实测，与 qoder 同类）**：bash 命中 npm shim（v0.144.5），
      python CreateProcess 命中 WinGet ``codex.exe``（旧 0.142.5）→ 本命令直连
      ``node @openai/codex/bin/codex.js``（``_resolve_codex_node_entry``），
      找不到入口时回退裸 ``codex``。
    - stdin 亦可喂 prompt（无位置参数时读 stdin；有位置参数时管道内容追加为 ``<stdin>`` 块），
      编排器沿用 cmd_arg（2026-07-08 probe：28s cmd_arg 略快于 stdin 37s）。
    - stdout=最终消息、stderr=进度；``--json`` 为 JSONL 事件流（thread.started/item.completed 等）。"""
    if _CODEX_NODE_ENTRY is not None:
        node, entry = _CODEX_NODE_ENTRY
        return [node, entry, "exec", "--ephemeral", prompt]
    return ["codex", "exec", "--ephemeral", prompt]


def cursor_headless_mode() -> str:
    """只读 headless 模式：Windows 用 plan（r1 实测 stdout 有正文）；Linux 用 ask。

    2026-08-16 Linux 实测：``--mode plan`` 短 prompt 能出字，但长评审走 CreatePlan，
    ``-p --output-format text`` 终稿不落 stdout（rc=0 空产）。``--mode ask`` 是只读
    问答，正文进 stdout。Windows 保持 plan，不改已验证路径。

    2026-09-06 Windows 补判：plan 在**跨盘探查/头脑风暴类任务**（读 workspace 外
    F: 盘 + 长产出）同样 rc=0 空 stdout——composer-2.5-fast / auto / kimi-k3-high
    三模型实证，与模型家族无关；直连加 ``--mode ask`` 同任务 11KB 满产。此类任务
    绕编排器直连 ask 根治；文档评审类任务 plan 维持。行为开关改造（env 覆盖/空产
    升档重试）见 ``plan-cursor-headless-ask-fallback-2026-09-06.md``（GO 前禁编码）。

    Slice A（2026-09-06 GO 落地）：env ``OSKH_CURSOR_HEADLESS_MODE``（``plan``|``ask``，
    大小写归一、空白裁剪）覆盖平台默认；非法值 ValueError fail-fast（工具级显式报错
    优于静默回落）。默认不设 = 平台默认不动。
    """
    env = os.environ.get("OSKH_CURSOR_HEADLESS_MODE", "").strip().lower()
    if env:
        if env not in ("plan", "ask"):
            raise ValueError(
                f"OSKH_CURSOR_HEADLESS_MODE 非法值 {env!r}（仅 plan|ask；"
                "不设则用平台默认 win32=plan / 其他=ask）"
            )
        return env
    return "plan" if sys.platform == "win32" else "ask"


def kimi_model_alias() -> str:
    """kimi-code 模型别名：统一 ``kimi-code/k3``（config.toml ``[models."kimi-code/k3"]``）。

    2026-09-05 linux-ci-02：裸 ``k3`` 报 ``Model "k3" is not configured in config.toml``；
    托管键与 Win OAuth 同形。勿再按平台拆裸名。
    """
    return "kimi-code/k3"

def kimi_cmd(prompt: str) -> list[str]:
    """kimi-code headless：``-p`` 非交互 + ``-m kimi-code/k3``（K3 = 当前默认/最新旗舰，= max thinking）。

    v0.27.0 实测（2026-07-18；调用细节 SSOT 见 ``docs/prompts/kimi-code-cli-Headless模式.md``）；
    v0.34.0（2026-08-11 核对官方文档站 ``moonshotai.github.io/kimi-code/`` + 本机实测，无形态变化）。
    - **裸 ``-p`` 即 auto 权限**（含写/shell 自动放行），**不可加** ``--yolo``——实测
      ``error: Cannot combine --prompt with --yolo.``（``--auto``/``--plan`` 同理互斥，见 headless 文档 §3）。
    - ⚠ 模型别名由 OAuth 托管服务下发（managed:kimi-code 现 4 个别名：kimi-for-coding /
      kimi-for-coding-highspeed / k3 / k3-256k；CLI ``-m`` 须用完整键 ``kimi-code/k3``）
      ——若 K3 退役改名，先 ``kimi provider list --json`` 复核。
    - **无** ``--thinking`` / ``--system-prompt`` flag（commander 报 ``unknown option``）。Thinking 由模型
      别名决定：K3 ``default_effort="max"``（``support_efforts=["low","high","max"]`` 三档，默认为 max）
      → 选 K3 即默认 max thinking，无 CLI effort flag。
    - **stdin 不支持**：``-p "<prompt>"`` 不读管道 stdin（模型侧 stdin 立即 EOF），故走 **cmd_arg**
      （prompt 作为 ``-p`` 的值参数）。与 cursor/claude（``-p`` 布尔 print 模式、prompt 走 stdin）语义不同——
      kimi 无法复用 ``STDIN_AGENTS`` 路径。
    - stdout=Assistant 正文；stderr=thinking+进度+``To resume this session: kimi -r <id>``（``-r``=``--resume``）。
    - config 在 ``~/.kimi-code/config.toml``。
    """
    return ["kimi", "-m", kimi_model_alias(), "--output-format", "text", "-p", prompt]


def _npm_global_roots() -> list[Path]:
    """机器级 npm 全局根候选（SYSTEM 账户下 PATH 无 npm/node 时的兜底探测）。

    自托管 runner（win11-dev）以 ``NT AUTHORITY\\SYSTEM`` 计划任务运行，其 PATH/用户环境
    不含交互用户的 npm 全局（2026-08-04 实测）。探测：nvm4w 根（``C:\\nvm4w\\nodejs``）、
    Program Files nodejs、各用户 ``AppData\\Roaming\\npm``。目录级探测无需执行任何命令。
    """
    roots: list[Path] = []
    for _root in (Path("C:/nvm4w/nodejs"), Path("C:/Program Files/nodejs")):
        if (_root / "node.exe").is_file():
            roots.append(_root)
    _users_root = Path("C:/Users")
    if _users_root.is_dir():
        for _u in sorted(_users_root.iterdir()):
            if _u.name.lower() in ("public", "default", "default user", "all users"):
                continue
            _npm_dir = _u / "AppData/Roaming/npm"
            if _npm_dir.is_dir():
                roots.append(_npm_dir)
    return roots


def _find_node_entry(cmd: str, entry_rel: tuple[str, ...]) -> tuple[str, str] | None:
    """通用 npm CLI 直连解析：``shutil.which(cmd)`` 目录推导 + ``npm root -g`` 兜底 → ``(node, entry_js)``。

    背景（2026-07-19 实测）：Windows 上 python ``subprocess``（CreateProcess）只认真 .exe，
    与 bash 的 shim（shell 脚本 / .CMD）解析不一致，易命中**旧版真 exe**（qoder 1.0.10 /
    codex 0.142.5 双坑）——绕开 shim 直连 ``node <entry.js>``，版本锁定 npm 安装。
    找不到返回 None（调用方回退裸命令名）。SYSTEM 账户（runner）下 PATH 无 npm/node 时
    走 ``_npm_global_roots`` 机器级目录探测，与交互会话解析一致。
    """
    import shutil

    candidates: list[Path] = []
    w = shutil.which(cmd)
    if w:
        candidates.append(Path(w).resolve().parent.joinpath(*entry_rel))
    npm = shutil.which("npm")
    if npm:
        try:
            import subprocess as _sp

            r = _sp.run([npm, "root", "-g"], capture_output=True, text=True, timeout=15)
            if r.returncode == 0 and r.stdout.strip():
                candidates.append(Path(r.stdout.strip()).joinpath(*entry_rel))
        except Exception:
            pass
    node = shutil.which("node")
    for b in candidates:
        if b.is_file() and node:
            return node, str(b)
    # SYSTEM 兜底：机器级 npm 全局根（entry 与 node.exe 同根）。
    for _root in _npm_global_roots():
        _entry = _root.joinpath(*entry_rel)
        if _entry.is_file():
            _node = (_root.parent / "node.exe") if _root.name == "npm" else (_root / "node.exe")
            if _node.is_file():
                return str(_node), str(_entry)
    return None


def _resolve_qoder_node_bundle() -> tuple[str, str] | None:
    """直连 node + qodercli bundle（cursor 同款绕 shim 思路；详见 qoder_cmd docstring 双二进制陷阱）。"""
    return _find_node_entry("qodercli", ("node_modules", "@qoder-ai", "qodercli", "bundle", "qodercli.js"))


def _resolve_codex_node_entry() -> tuple[str, str] | None:
    """直连 node + codex 入口 js（同 qoder 双二进制陷阱——WinGet codex.exe 0.142.5 旧版）。"""
    return _find_node_entry("codex", ("node_modules", "@openai", "codex", "bin", "codex.js"))


_QODER_NODE_BUNDLE = _resolve_qoder_node_bundle()
_CODEX_NODE_ENTRY = _resolve_codex_node_entry()


def qoder_cmd(prompt: str) -> list[str]:
    """qodercli headless（-p 非交互）+ -m Qwen3.8-Max（2026-08-07 账户可用模型 pin）。

    v1.0.48 实测（2026-07-18，`--help` / `--list-models` / 实跑 18.9s 出文）：
    - `--list-models` 13 档：Auto/Ultimate/Performance/Efficient/Lite + Qwen3.7-Max/Plus +
      Kimi-K3/K2.7-Code + GLM-5.2 + DeepSeek-V4-Pro/Flash + MiniMax-M3。曾 pin Qwen3.7-Plus
      （避 Auto 504）；2026-08-07 起 pin Qwen3.8-Max（`--list-models` 仅 Lite / Qwen3.8-Max）。
    - `--permission-mode bypass_permissions`：choices = default/accept_edits/bypass_permissions/
      dont_ask/auto（评审需跑 git/读文件，bypass 免确认）。
    - `--no-session-persistence`：一次性评审/核查不留会话存档（仅 -p 模式有效；实测 rc=0 26.9s）。
    - ⚠️ 指南（``Qoder-CLI-Print模式完整指南.md``）过时项：``--yolo``/``-q``/
      ``--max-turns`` 实测不存在——该结论为 v1.0.48（2026-07-18）时代；现行官方文档
      （docs.qoder.com/cli/permissions、/cli/model）已列 ``--yolo``/``--max-turns``，但
      1.1.19 实测 ``--yolo`` 仍报 unknown option（疑 CN/国际版差异）——故本地继续用
      「文档有效 + 实测有效」交集 ``--permission-mode bypass_permissions``，勿换 ``--yolo``；
      免权限跳检实测为 ``--dangerously-skip-permissions``（本命令用 permission-mode 即可）；
      工作区参数为 ``-w, --cwd``（run_agent 已设 cwd，免加）。
    - 官方文档：docs.qoder.com/cli/using-cli（print 模式/Flags）、/cli/permissions、/cli/model。
      1.1.18 起新增启动命令 ``qoder``（国际版）/``qodercn``（CN 版），``qodercli`` 保持兼容——
      非 breaking，本地仍走 ``qodercli``（node 直连 bundle）。
    - **双二进制陷阱（2026-07-19 实测）**：bash 命中 npm shim（v1.0.48），python CreateProcess
      命中 `.qoder/bin/qodercli.exe`（旧 1.0.10，无新 flag）→ 本命令直连
      ``node <bundle>``（``_resolve_qoder_node_bundle``，cursor 同款绕 shim），
      找不到 bundle 时回退裸 ``qodercli``。
    - stdin：长 prompt 超时而 cmd_arg 稳（2026-07-08 probe），故 prompt 走位置参数。"""
    if _QODER_NODE_BUNDLE is not None:
        node, bundle = _QODER_NODE_BUNDLE
        return [node, bundle, "-p", "--no-session-persistence",
                "--permission-mode", "bypass_permissions", "-m", "Qwen3.8-Max", prompt]
    return ["qodercli", "-p", "--no-session-persistence",
            "--permission-mode", "bypass_permissions", "-m", "Qwen3.8-Max", prompt]


def cursor_cmd(prompt: str) -> list[str]:
    """cursor-agent 非交互 headless（默认 auto）。可用模型**完整清单见本文件
    CURSOR_MODEL_CATALOG**（2026-08-14 实测 23 档快照；自更新会漂移，实时以
    cursor_list_models()/--list-models 为准）。auto=Cursor Auto agent router（动态路由非固定）。
    历史：07.08→07.13 grok-4.5-xhigh 等旧 ID 已废（xhigh 档取消）；08.13 4.6 系列恢复 xhigh。
    裸 CLI ``agent --model`` 必须用完整 ID（``cursor-grok-4.6-xhigh-fast``）；短名
    ``grok-4.6-xhigh-fast`` 会被拒。编排器 ``cursor:grok-…`` 由 normalize_cursor_model 补前缀。
    prompt 由 run_agent 走 stdin 管道（避 Windows CLI 长度/编码限制；直连 Node 绕 .ps1）。
    --mode 由 cursor_headless_mode() 选：Windows plan（r1 实测 stdout 有正文；
    但跨盘探查类任务空 stdout，2026-09-06——须直连 ask，见该函数 docstring），
    Linux ask（2026-08-16：长评审 plan 走 CreatePlan，-p text 空 stdout）。
    裸 -p 按官方语义可访问全部工具含写/shell，所以必须钉只读 mode；
    --trust = headless 免工作区信任提示；
    -f/--force = headless 下自动放行工具审批（2026-08-13 实测：无 -f 时 plan 模式读文件/搜索/终端被审批墙拦死，
        评审只能空转「被拦断」；plan 模式本身禁编辑（help 原文 "no edits"），-f 不扩编辑权限，只解除读/终端审批）；
    --workspace = 显式钉仓根（官方 headless 参数，防 cwd 漂移）。"""
    return [CURSOR_NODE_EXE, CURSOR_INDEX_JS, "-p", "--output-format", "text",
            "--trust", "-f", "--mode", cursor_headless_mode(), "--workspace", str(_REPO_ROOT)]


def cursor_model_cmd(variant: str) -> list[str]:
    """cursor:<model> → --model <canonical>（mixed preset 用；短名 grok-* 补 cursor- 前缀）。"""
    return [CURSOR_NODE_EXE, CURSOR_INDEX_JS, "--model", normalize_cursor_model(variant),
            "-p", "--output-format", "text", "--trust", "-f", "--mode", cursor_headless_mode(),
            "--workspace", str(_REPO_ROOT)]


def claude_cmd(prompt: str) -> list[str]:
    """claude CLI headless（Claude Code v2.1.227 实测，2026-08-11；调用细节 SSOT 见
    ``docs/prompts/Claude-CLI-Headless指南.md`` 附录）。

    - 模型经 ``~/.claude/settings.json`` env（``ANTHROPIC_MODEL=glm-5.3[1M]``，bigmodel anthropic 代理——2026-08-17 核，勿加 ``--model`` 旗标重复指定）；``-p`` 非交互；``--permission-mode bypassPermissions``（choices 实测：
      acceptEdits/auto/bypassPermissions/manual/dontAsk/plan）——评审需跑 git/读文件，bypass 免确认。
    - ``--no-session-persistence``：一次性评审不留会话存档（仅 -p 模式有效，实测 rc=0）。
    - **prompt 走位置参数（cmd_arg）**：v2.1.227 双 MARKER 探针实测——positional 存在时
      **stdin 内容会一并喂入**（追加，非「被忽略」；2.1.214 时代是忽略，行为已变）——
      故 claude 必须在 STDIN_AGENTS 之外（否则重复喂入浪费 token）。stdin-only 形态亦可用。
    - **勿加 ``--bare``**：bare 跳过 OAuth/keychain 读取（本机认证走该路径），
      需 ``ANTHROPIC_API_KEY`` 才可用——本机不适用。
    - ``--max-turns`` 隐藏但有效（--help 不显示）；``--tools`` 已转在册；正形
      ``--session-persistence`` 已移除（负形 ``--no-session-persistence`` 即官方唯一形态）。"""
    return ["claude", "-p", "--no-session-persistence", "--output-format", "text",
            "--permission-mode", "bypassPermissions", prompt]


def grok_cmd(prompt: str) -> list[str]:
    """grok CLI headless（Linux VM）。``-p/--single <PROMPT>`` 后紧跟正文；再挂权限 flag。

    2026-09-05：新版 grok 把 ``-p`` 从布尔改为 ``--single <PROMPT>``。旧序
    ``grok -p --permission-mode ... <prompt>`` 会让 ``-p`` 吃掉下一个 flag，
    报 ``a value is required for '--single <PROMPT>'``（走读评审 grok rc=2）。
    正解：``grok -p "<prompt>" --permission-mode bypassPermissions --always-approve``。

    acceptEdits 会取消 ``run_terminal_command``，headless 评审/核查不可用。
    """
    return ["grok", "-p", prompt, "--permission-mode", "bypassPermissions", "--always-approve"]


# 标准 agent（period_verify 本地追加 "claw"）。qoder 保留以便 OSKH_ENABLE_QODER 一键恢复。
BASE_AGENTS: Dict[str, Callable[[str], list[str]]] = {
    "codex": codex_cmd,
    "kimi": kimi_cmd,
    "qoder": qoder_cmd,
    "cursor": cursor_cmd,
    "claude": claude_cmd,
    "grok": grok_cmd,
}


# ── agent 命令解析（cursor:model 语法 + builders）───────────────────────
def resolve_agent_cmd(agent_name: str, prompt: str, agents_map: Dict[str, Callable[[str], list[str]]]) -> Optional[list[str]]:
    """Resolve agent command. ``cursor:<model>`` → cursor_model_cmd；否则 agents_map[name](prompt)。

    Examples:
      cursor                                  → default model (auto)
      cursor:cursor-grok-4.6-xhigh-fast       → --model cursor-grok-4.6-xhigh-fast
      cursor:grok-4.6-xhigh-fast              → 同上（短名补 cursor- 前缀）
      codex                                   → agents_map["codex"](prompt)
    """
    if ":" in agent_name:
        base, variant = agent_name.split(":", 1)
        if base == "cursor":
            return cursor_model_cmd(variant)
    builder = agents_map.get(agent_name)
    if builder:
        return builder(prompt)
    return None


# ── 预设（classic/mixed，review 与 verify 共用）────────────────────────
# ── CURSOR_MODEL_CATALOG（cursor 可用模型唯一手写清单 SSOT；其他位置一律指向此处，原则⑩）──
# 快照：2026-08-14 `agent --list-models` 实测，共 23 档。
# 自更新会漂移——实时以 cursor_list_models() / --list-models 为准（编排器 fan-out 前自动预检）。
# 裸 CLI `agent --model` 必须用完整 ID：`grok-4.6-xhigh-fast` 会被拒，正确为
# `cursor-grok-4.6-xhigh-fast`。编排器 `cursor:grok-…` 短名由 normalize_cursor_model 补前缀。
# classic 的 cursor 席位 2026-08-26 人裁改 **auto**（--model auto；grok-4.6 家族长评审空产三连实证、
# composer-2.5 换家族一次出活佐证问题在家族级。显式换钉用 cursor:<model> 语法；08-13 曾钉 grok-4.6-xhigh-fast）。
CURSOR_MODEL_CATALOG: frozenset[str] = frozenset({
    "auto",
    "cursor-grok-4.6-low",
    "cursor-grok-4.6-low-fast",
    "cursor-grok-4.6-medium",
    "cursor-grok-4.6-medium-fast",
    "cursor-grok-4.6-high",
    "cursor-grok-4.6-high-fast",
    "cursor-grok-4.6-xhigh",
    "cursor-grok-4.6-xhigh-fast",
    "cursor-grok-4.5-low",
    "cursor-grok-4.5-low-fast",
    "cursor-grok-4.5-medium",
    "cursor-grok-4.5-medium-fast",
    "cursor-grok-4.5-high",
    "cursor-grok-4.5-high-fast",
    "composer-2.5",
    "composer-2.5-fast",
    "kimi-k2.7-code",
    "kimi-k3-low",
    "kimi-k3-high",
    "kimi-k3-max",
    "glm-5.2-high",
    "glm-5.2-max",
})


def normalize_cursor_model(variant: str) -> str:
    """把短名补成 CLI 完整 ID。``grok-4.6-xhigh-fast`` → ``cursor-grok-4.6-xhigh-fast``。

    仅当 ``cursor-{variant}`` 在 CURSOR_MODEL_CATALOG 时改写；auto / composer / kimi / glm
    等本就无前缀的 ID 原样返回。未知 ID 不改写（交给 --list-models 预检报缺失）。
    """
    if variant in CURSOR_MODEL_CATALOG:
        return variant
    prefixed = f"cursor-{variant}"
    if prefixed in CURSOR_MODEL_CATALOG:
        return prefixed
    return variant

# host 走空槽（人填），不被 subprocess 拉起。允许独立 CLI / 某个 cursor:<model> / cursor-desktop。
# mixed：host 不预设，谁发起谁综合；脚本省略 --host 仅兜底空槽文件名 claude。
# classic：host 从成员里选一（省略=claude）；--host cursor 对唯一 cursor:<model> 席位。
# host=cursor-desktop → 成员全跑（桌面版只做 host）。
# host=cursor:<model> 且该变体在成员里 → 该路改空槽，其余 cursor 变体照跑。
HOST_CHOICES = ["claude", "cursor", "codex", "kimi", "qoder", "grok", "cursor-desktop"]


def normalize_host(host: str) -> str:
    """``cursor:grok-…`` → ``cursor:cursor-grok-…``；其余原样。"""
    if ":" in host:
        base, variant = host.split(":", 1)
        if base == "cursor" and variant:
            return f"cursor:{normalize_cursor_model(variant)}"
    return host


def is_allowed_host(host: str) -> bool:
    if host in HOST_CHOICES:
        return True
    return bool(host.startswith("cursor:") and host.split(":", 1)[1])


def parse_host_arg(value: str) -> str:
    """argparse type：独立 agent / cursor-desktop / cursor:<model>（短名补前缀）。"""
    host = normalize_host((value or "").strip())
    if not host or not is_allowed_host(host):
        raise ValueError(
            f"invalid host {value!r}；允许 {HOST_CHOICES} 或 cursor:<model>"
        )
    return host


def canonical_host_slot(names: list[str], host: str) -> str:
    """把 ``--host cursor`` 对到阵容里的 host 空槽名。

    - host 已在 names 里 → 原样（精确命中 ``cursor:<model>`` / ``claude`` 等）
    - host=``cursor`` 且 names 里**恰好一个** ``cursor:`` 席位（classic 钉死模型）→ 该席位
    - host=``cursor`` 且多个 ``cursor:``（mixed）→ 仍为 ``cursor``（额外空槽，成员全跑）
    """
    if host in names:
        return host
    if host == "cursor":
        variants = [n for n in names if n.startswith("cursor:")]
        if len(variants) == 1:
            return variants[0]
    return host


def classic_agents_csv() -> str:
    """Platform classic roster (qoder never in default lists).

    Linux: grok CLI + kimi + codex + cursor.
    Windows: claude + kimi + codex + cursor.
    """
    cursor = "cursor:auto"
    if sys.platform == "win32":
        return f"codex,kimi,{cursor},claude"
    return f"codex,kimi,{cursor},grok"


def default_host() -> str:
    """Omit --host: Linux extra slot claude (4 Linux agents fan-out);
    Windows cursor-desktop so claude/kimi/codex/cursor all fan-out.
    """
    return "cursor-desktop" if sys.platform == "win32" else "claude"


def _env_enables_qoder() -> bool:
    return os.environ.get("OSKH_ENABLE_QODER", "").strip().lower() in ("1", "true", "yes")


# Default True unless process env already enables qoder. assert_qoder_allowed re-reads env.
QODER_PAUSED = not _env_enables_qoder()


def assert_qoder_allowed(names: list[str]) -> None:
    """Fail-fast if any agent is qoder while paused (额度暂停).

    Re-enable: explicit notice or ``OSKH_ENABLE_QODER=1`` / true / yes.
    """
    if not any(agent_base(n) == "qoder" for n in names):
        return
    if _env_enables_qoder():
        return
    if QODER_PAUSED:
        raise SystemExit(
            "qoder 额度暂停，等明确启用；临时可 OSKH_ENABLE_QODER=1。"
        )


class _ClassicPreset(dict):
    """PRESETS['classic']['agents'] is computed at access time (platform-dependent)."""

    def __getitem__(self, key):  # type: ignore[override]
        if key == "agents":
            return classic_agents_csv()
        return super().__getitem__(key)

    def get(self, key, default=None):  # type: ignore[override]
        if key == "agents":
            return classic_agents_csv()
        return super().get(key, default)


# 2026-08-24：classic 按平台四家；qoder 默认暂停，不进 classic/mixed。
PRESETS: Dict[str, dict] = {
    "classic": _ClassicPreset({
        "agents": classic_agents_csv,
        "description": (
            "经典组（按平台）：Linux=codex+kimi+cursor+grok；"
            "Windows=codex+kimi+cursor+claude。"
            "默认 host：Linux=claude（空槽，四家全跑）；Windows=cursor-desktop（四家全跑）。"
            "qoder 额度暂停，不进默认阵容；明确启用或 OSKH_ENABLE_QODER=1 才可 --agents qoder。"
            "cursor 显式 --model auto（2026-08-26 人裁；换钉用 cursor:<model> 语法）。"
        ),
    }),
    "mixed": {
        # 成员必须全是 cursor:<model>。host 不预设：谁发起谁综合
        # （独立 CLI / 某个 cursor:<model> / cursor-desktop）。脚本省略 --host 仅兜底空槽名 claude。
        # 人裁 2026-08-14：① Cursor Ultra 额度最多，独立 CLI 常没额度；
        # ② cursor 自带模型多且全（grok / kimi / glm / composer / auto 一族）。
        # 人裁 2026-08-15（节省额度）：成员只保留 **Cursor 自家模型**（Cursor Models：Grok/Composer）+ auto；
        # **不用 Other Models**（kimi-k3-max / glm-5.2-max 从 mixed 预设移除）。
        "agents": "cursor:auto,cursor:cursor-grok-4.6-xhigh-fast,cursor:composer-2.5-fast",
        "host": None,
        "description": (
            "混合组：成员全是 cursor 自带模型（auto / cursor-grok-4.6-xhigh-fast / composer-2.5-fast——"
            "仅 Cursor 自家 Models + auto；2026-08-15 人裁：Other Models（kimi/glm）不再使用，节省额度）。"
            "不拉独立 CLI。host 不预设，谁发起谁综合（独立 agent / 某个 cursor:<model> / cursor-desktop）。"
            "模型 ID 随自更新会变，指定前先 --list-models 核"
        ),
    },
}


# ── 共享常量 / helpers ─────────────────────────────────────────────────
# 经 stdin 管道模式传入 prompt 的 agent（probe 实测；agent 自更新快，以最新实测为准）：
#   cursor: 直连 Node 后两种模式都 OK，stdin 避 Windows CLI 长度限制
#   qoder:  stdin 短 prompt OK，长 prompt 超时 → 退回 cmd_arg（run_agent 内处理）
#   kimi:   cmd_arg（**stdin 不支持**：v0.23.1 报 rc=1；v0.27.0 复核——模型侧 stdin 立即 EOF，
#           `-p "<prompt>"` 不读管道。且 kimi `-p` 取「值参数」语义，非 cursor/claude 的布尔
#           print 模式，无法走 stdin-as-prompt。详见 kimi_cmd docstring）
#   codex:  cmd_arg（略快）
#   claude: **cmd_arg**（2026-08-11 v2.1.227 MARKER 探针实测：positional 存在时 stdin **一并喂入**
#           ——claude 不入本集合是防重复喂入的必要决策，勿加回）
STDIN_AGENTS = {"cursor"}

# 5 标准 agent 超时（秒）；period_verify 本地追加 claw=900
# kimi=1500（2026-08-13 r31 轮 900s 超时 rc=124——思考流完整但死在整理阶段，产出 82KB 未整理；
# 评审发现不亚于其他家，问题纯在预算；调大让其出正式报告）
DEFAULT_TIMEOUTS_BASE: Dict[str, int] = {
    "codex": 900, "kimi": 1500, "qoder": 900, "cursor": 900, "claude": 900, "grok": 900,
}


def agent_base(agent: str) -> str:
    """Return base agent name (strip :model suffix). 'cursor:auto' -> 'cursor'."""
    return agent.split(":", 1)[0]


def fs_safe(name: str) -> str:
    """Sanitize agent name for filesystem paths (replace : with -)."""
    return name.replace(":", "-")


def ensure_run_dir_on_path(file_path: str) -> None:
    """Ensure scripts/run/ (this module's dir) is on sys.path.

    For robustness when a script is loaded via importlib from another dir
    (e.g. doc_verify in scripts/misc/ loads period_verify in scripts/run/),
    so the latter's ``from multi_ai_common import`` resolves. No-op if already present.
    """
    run_dir = str(Path(file_path).resolve().parent)
    if run_dir not in __import__("sys").path:
        __import__("sys").path.insert(0, run_dir)


# ── cursor 模型预检（mixed 预设 cursor:<model> 变体；模型 ID 随 CLI 自更新漂移）──
def cursor_list_models(timeout: int = 30) -> Optional[list[str]]:
    """``cursor-agent --list-models`` → 可用模型 ID 列表；失败（网络/鉴权/超时）返回 ``None``。

    输出形如 ``auto - Auto (default)`` / ``cursor-grok-4.5-high - Cursor Grok 4.5``；
    取 ``" - "`` 前的 ID 段。2026-07-18 v2026.07.16-899851b 实测 12 个模型。
    """
    try:
        p = subprocess.run(
            [CURSOR_NODE_EXE, CURSOR_INDEX_JS, "--list-models"],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
    except Exception:
        return None
    if p.returncode != 0:
        return None
    models: list[str] = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith(("Available", "Tip:")):
            continue
        mid = line.split(" - ", 1)[0].strip()
        if mid:
            models.append(mid)
    return models or None


def check_cursor_models(models: list[str], timeout: int = 30) -> tuple[list[str], Optional[list[str]]]:
    """校验 cursor 模型变体可用性。返回 ``(missing, available)``；``available=None`` 表示
    预检本身不可用（调用方应仅告警、不阻断 fan-out）。"""
    if not models:
        return [], []
    available = cursor_list_models(timeout=timeout)
    if available is None:
        return [], None
    return [m for m in models if m not in available], available


def preflight_cursor_models(names: list[str], timeout: int = 30) -> tuple[list[str], Optional[list[str]]]:
    """从 agent 名单提取 ``cursor:<model>`` 变体并校验可用性（bare ``cursor`` = 默认 auto，免校验）。

    返回 ``(missing, available|None)``；供各编排器 main() 在 fan-out 前调用。
    """
    variants = sorted({
        normalize_cursor_model(n.split(":", 1)[1])
        for n in names if n.startswith("cursor:") and n.split(":", 1)[1]
    })
    return check_cursor_models(variants, timeout=timeout)


# ── cursor 并行配置隔离（防 cli-config.json EPERM）────────────────────
def _prepare_cursor_config_dir(agent_name: str) -> Tuple[Path, Dict[str, str]]:
    """为单次 cursor 调用准备独立 ``CURSOR_CONFIG_DIR``。

    多路并行 cursor-agent 会原子 rename 写 ``~/.cursor/cli-config.json``；Windows 上
    并发 rename 会 ``EPERM``（2026-08-07 r2：cursor-grok-4.5-high-fast rc=1）。
    官方支持 ``CURSOR_CONFIG_DIR`` 覆盖配置目录；每调用一座临时目录并种子复制
    用户 ``cli-config.json`` / ``agent-cli-state.json``。**不**覆盖 HOME/USERPROFILE
    （第三方实测假 HOME 会导致 Authentication required）。
    """
    src = Path.home() / ".cursor"
    td = Path(
        tempfile.mkdtemp(
            prefix=f"oskh_cursor_cfg_{fs_safe(agent_name)}_",
        )
    )
    for name in ("cli-config.json", "agent-cli-state.json"):
        src_f = src / name
        if src_f.is_file():
            shutil.copy2(src_f, td / name)
    return td, {"CURSOR_CONFIG_DIR": str(td)}


# ── run_agent（上移自 review/period_verify 两处逐字复制）+ 空输出 stub 自动重试 ──
def is_stub_output(outpath: Path, min_content_chars: int = 80) -> bool:
    """检测「rc=0 但正文为空」的 stub 输出（cursor r2/r4 实测事故：文件只有 header 行）。

    排除 ``<!-- agent=... -->`` header 行后，剩余非空白字符 < ``min_content_chars`` 即 stub。
    """
    try:
        text = Path(outpath).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return True
    body = "\n".join(line for line in text.splitlines() if not line.startswith("<!-- agent="))
    return len(body.strip()) < min_content_chars


# 拒评签名：agent 因 hook/环境故障主动声明拒评（2026-08-09 G1 cursor 实测：
# hookify preToolUse 被 Cursor 包成 PowerShell 片段进 bash eval → 工具全拦 → 拒评）
_REFUSAL_SIGNATURES = (
    "无法完成评审",
    "修好钩子",
    "Hook blocked",
    "钩子全部拦截",
)


def is_refusal_output(outpath: Path) -> bool:
    """检测「agent 拒评」输出（环境类故障的主动声明）。

    拒评 ≠ stub（正文非空，不会触发 stub 重试）；同环境重跑必复现——
    命中后标记分类、不自动重试，修复环境后需人工重跑。
    """
    try:
        text = Path(outpath).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    return any(sig in text for sig in _REFUSAL_SIGNATURES)


def _run_agent_once(
    name: str, cmd: list[str], timeout: int, outpath: Path,
    cwd: str, env: Dict[str, str], stdin_text: str,
) -> int:
    """单次执行：header 行 + subprocess（stdout 流式写文件，stderr 捕获）。"""
    import tempfile as _tempfile

    # Windows: CreateProcess 不认 .CMD shim 的**裸名**（qodercli/codex/npm 等——PATH 里是
    # .CMD 无 .exe），裸名会 FileNotFoundError→127（2026-07-20 qoder r2 实测 "CLI not found
    # on PATH"；upgrade_agent_cli.py 同坑）。用 shutil.which 解析完整路径（同 _find_node_entry），
    # 真 .exe 裸名（kimi/node）which 返回同路径，无副作用。消除 qoder_cmd/codex_cmd 回退分支的 127。
    import shutil as _shutil
    _resolved = _shutil.which(cmd[0])
    if _resolved:
        cmd = [_resolved, *cmd[1:]]

    with outpath.open("w", encoding="utf-8") as fh:
        fh.write(f"<!-- agent={name} cmd-prefix={' '.join(cmd)} <prompt> -->\n")
        fh.flush()
        try:
            if stdin_text:
                # stdin 文件重定向模式：写入临时文件 → subprocess stdin 从文件读
                # （避 Python communicate() 在 Windows 上长中文 prompt 下 stdout 空输出的间歇性问题）
                _tmp = _tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", encoding="utf-8", delete=False
                )
                try:
                    _tmp.write(stdin_text)
                    _tmp.close()
                    with open(_tmp.name, "r", encoding="utf-8") as _infh:
                        p = subprocess.run(
                            cmd, cwd=cwd,
                            stdin=_infh, stdout=fh, stderr=subprocess.PIPE,
                            text=True, timeout=timeout,
                            encoding="utf-8", errors="replace", env=env,
                        )
                    rc = p.returncode
                    stderr_text = p.stderr
                finally:
                    os.unlink(_tmp.name)
            else:
                p = subprocess.run(
                    cmd, cwd=cwd,
                    stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.PIPE,
                    text=True, timeout=timeout,
                    encoding="utf-8", errors="replace", env=env,
                )
                rc = p.returncode
                stderr_text = p.stderr
            if rc != 0:
                fh.write(f"\n\n[runner] {name} exit={rc}\n[stderr]\n{stderr_text}\n")
            return rc
        except subprocess.TimeoutExpired as e:
            fh.write(f"\n\n[runner] {name} TIMEOUT after {timeout}s (partial output above, if any)\n")
            if e.stderr:
                fh.write(f"[stderr-partial]\n{e.stderr}\n")
            return 124
        except FileNotFoundError:
            fh.write(f"\n[runner] {name} CLI not found on PATH\n")
            return 127
        except Exception as e:
            fh.write(f"\n[runner] {name} error: {e!r}\n")
            return 1


def linux_review_preflight(names: list[str]) -> list[str]:
    """Fan-out 硬门（Linux 查 bwrap/PATH；Win 查四家 CLI 存在性——2026-08-30 F5 残余）。

    返回错误字符串列表（空=通过）。Win 侧此前直接空列表，缺席员只能等空产/127
    才暴露；现与 Linux 同为硬门（grok/qoder 不查：Win=SKIP by design、qoder 暂停）。
    """
    errs: list[str] = []
    bases = {agent_base(n) for n in names}
    if sys.platform == "win32":
        if "kimi" in bases and shutil.which("kimi") is None:
            errs.append("kimi 不在 PATH（~/.kimi-code/bin/kimi.exe）")
        if "codex" in bases:
            # _CODEX_NODE_ENTRY 是 (node, entry) 二元组（见 _resolve_codex_node_entry
            # 与 :244 解包用法）；此前整元组当路径用，Win 预检必 TypeError。
            entry = (globals().get("_CODEX_NODE_ENTRY") or ("", ""))[1]
            if not entry or not Path(entry).exists():
                errs.append("codex node 入口未发现（npm -g @openai/codex）")
        if "cursor" in bases and (not CURSOR_NODE_EXE or not Path(CURSOR_NODE_EXE).exists()):
            errs.append("cursor-agent node 未发现（versions/ 目录）")
        if "claude" in bases and shutil.which("claude") is None:
            errs.append("claude 不在 PATH")
        return errs
    if "codex" in bases and shutil.which("bwrap") is None:
        errs.append("codex 需要 bwrap（apt install bubblewrap）；Linux 无 bundled sandbox")
    if "kimi" in bases and shutil.which("kimi") is None:
        errs.append("kimi 不在 PATH")
    if "cursor" in bases:
        if not CURSOR_NODE_EXE or not Path(CURSOR_NODE_EXE).exists():
            errs.append("cursor-agent node 未发现（~/.local/share/cursor-agent）")
    if "grok" in bases and shutil.which("grok") is None:
        errs.append("grok 不在 PATH")
    return errs


def run_agent(
    name: str, cmd: list[str], timeout: int, outpath: Path, *,
    stdin_text: str = "", env: Optional[Dict[str, str]] = None, retries: int = 1,
) -> tuple[int, float]:
    """运行单个 CLI，stdout 流式写入 outpath（可 ``tail -f``；超时不丢已产出）。

    - ``stdin_text`` 非空 → 临时文件重定向 stdin（cursor/claude 走此路径）。
    - ``env`` → 叠加到 ``os.environ``（claw 等需 token 的 agent；None=继承父进程）。
    - ``retries`` → **rc=0 但输出为 stub（空输出事故，cursor r2/r4 实测）时的自动重跑次数**
      （默认 1，即最多 2 次尝试）；此前只能手动 ``--agents cursor`` 重试。
    """
    _env = os.environ.copy()
    if env:
        _env.update(env)
    cfg_dir: Optional[Path] = None
    # cursor / cursor:<model>：并行时隔离 cli-config，避免抢写 ~/.cursor/cli-config.json
    if agent_base(name) == "cursor" and "CURSOR_CONFIG_DIR" not in _env:
        cfg_dir, cursor_env = _prepare_cursor_config_dir(name)
        _env.update(cursor_env)
        print(f"[cursor-cfg] {name}: CURSOR_CONFIG_DIR={cfg_dir}", flush=True)
    t0 = time.time()
    attempts = 0
    try:
        while True:
            attempts += 1
            rc = _run_agent_once(name, cmd, timeout, Path(outpath), str(_REPO_ROOT), _env, stdin_text)
            if rc == 0 and is_refusal_output(outpath):
                print(f"[refusal] {name}: 输出含拒评签名（hook/环境类故障），不自动重试", flush=True)
                with Path(outpath).open("a", encoding="utf-8") as fh:
                    fh.write(f"\n\n[runner] {name} 拒评签名命中（hook/环境类故障），不自动重试；修复环境后需人工重跑\n")
                return rc, time.time() - t0
            if rc == 0 and attempts <= retries and is_stub_output(outpath):
                print(f"[retry] {name}: rc=0 但输出为空（stub），自动重试 {attempts}/{retries}", flush=True)
                continue
            if attempts > 1:
                with Path(outpath).open("a", encoding="utf-8") as fh:
                    fh.write(f"\n\n[runner] {name} 经 {attempts} 次尝试完成（含 rc=0 空输出自动重试）\n")
            return rc, time.time() - t0
    finally:
        if cfg_dir is not None:
            shutil.rmtree(cfg_dir, ignore_errors=True)
