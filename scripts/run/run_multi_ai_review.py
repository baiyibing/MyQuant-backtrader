"""run_multi_ai_review.py — 多 agent 设计稿评审 fan-out 编排器。

把一份 plan/design 文档发给外部 CLI 做独立评审，各自原始 stdout **流式**落到
docs/architecture/reviews/<date>/<slug>/<agent>.md（可 `tail -f` 实时看；超时也不丢已产出内容）。
host（综合者空槽，谁发起谁综合，不被子进程拉起）。省略 --host：
Linux=claude（空槽，classic 四家全跑）；Windows=cursor-desktop（classic 四家全跑）。

两种预设模式（--preset）：
  classic      按平台四家（默认；Linux=codex+kimi+cursor+grok；Win=codex+kimi+cursor+claude；
               kimi 席位默认 Cursor Kimi）。qoder 额度暂停，不进默认阵容。
               host 从成员选一 / cursor-desktop→全员跑
  mixed        混合组：成员全是 cursor 自带模型（不拉独立 CLI）。host 不预设，
               谁发起谁综合（独立 agent / 某个 cursor:<model> / cursor-desktop）。
               省略 --host 仅兜底空槽名 claude。2026-08-15 人裁：只用 Cursor 自家
               Models（Grok/Composer）+ auto；Other Models（kimi/glm）不再使用（节省额度）。

host 指定约定（与提示词一致）：指令里 host=cursor桌面版 → --host cursor-desktop。
起草者即 host 时**无需** `--exclude <起草者>`：host 是综合空槽（不被子进程拉起为评审员），
exclude 里出现 host 会被 fail-fast 拦下；要换综合者直接 `--host <name>`。
agent 命令构造/模型配置在 multi_ai_common.py（改一处全局生效）。

用法:
  # 经典模式 + claude host（默认，不指定 --host 即 claude）
  python scripts/run/run_multi_ai_review.py \\
      --plan docs/engineering/plan-xxx.md

  # 经典模式 + cursor 桌面版 host
  python scripts/run/run_multi_ai_review.py \\
      --plan <plan> --host cursor-desktop

  # 混合模式
  python scripts/run/run_multi_ai_review.py \\
      --plan <plan> --preset mixed

  # qoder 默认暂停；要临时启用：OSKH_ENABLE_QODER=1 --agents ...,qoder

注意:
  - 各 CLI 各自走自己的 login（不依赖 env API key），互不依赖 → 可安全并行。
  - stdout 流式写入 per-agent 文件（subprocess stdout=fh），stderr 捕获；超时仅追加
    footer、不丢已产出内容（修早期 capture_output + 丢弃 TimeoutExpired.stdout 的 bug）。
  - 单 agent 默认 900s；--timeout N 覆盖全部。
  - cursor-agent 只读 headless：Windows --mode plan，Linux --mode ask（长评审 plan 在 Linux 空 stdout）；claude 用 --permission-mode bypassPermissions。
  - --exclude 排除 agent（如起草者避利益冲突）。
  - --parallel 时各 agent 先写入 <out-dir>/_parallel/<agent>/；全部完成后合并回
    <out-dir>/，per-agent 版本戳进 _version_manifest.json，并自动删除 _parallel/。
    host 空槽（<host>.md）仍在主目录。
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as _dt
import subprocess
import sys
from pathlib import Path

def _repo_root() -> Path:
    scripts_dir = next((p for p in Path(__file__).resolve().parents if p.name == "scripts"), None)
    if scripts_dir is None:
        raise RuntimeError(f"script not under scripts/: {__file__}")
    return scripts_dir.parent

REPO_ROOT = _repo_root()


def _rel_display(p: Path) -> str:
    """repo 内路径显示为相对路径；repo 外（如 tmp 目录的 --out-dir）回退绝对路径。

    防 ``relative_to(REPO_ROOT)`` 在 --out-dir 指向仓外时抛 ValueError。
    """
    try:
        return str(Path(p).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(p)

# ── agent 基础设施（共享，from multi_ai_common；模型配置改一处即可全局生效）──
# 桥接 common 的公开名为本脚本 body 既用的私有名（_STDIN_AGENTS/_agent_base 等），
# 避免 diff 全 body。命令构造/cursor 解析/PRESETS 单一来源在 multi_ai_common.py。
sys.path.insert(0, str(Path(__file__).resolve().parent))  # ensure scripts/run/ on sys.path
from multi_ai_common import (  # noqa: E402
    BASE_AGENTS,
    PRESETS,
    preflight_cursor_models,
    linux_review_preflight,
    resolve_agent_cmd,
    run_agent,
    STDIN_AGENTS,
    DEFAULT_TIMEOUTS_BASE,
    agent_base,
    agent_timeout_key,
    review_seat,
    fs_safe,
    HOST_CHOICES,
    parse_host_arg,
    canonical_host_slot,
    merge_parallel_artifacts,
    default_host,
    assert_qoder_allowed,
)
AGENTS = BASE_AGENTS  # review 无 claw；period_verify 本地追加 claw
_HOST_CHOICES = HOST_CHOICES  # 全 6 agent 可当 host
_STDIN_AGENTS = STDIN_AGENTS
DEFAULT_AGENT_TIMEOUTS = DEFAULT_TIMEOUTS_BASE
_agent_base = agent_base
_fs_safe = fs_safe


def _resolve_agent_cmd(agent_name: str, prompt: str) -> list[str] | None:
    """cursor:<model> → cursor_model_cmd; else AGENTS[name]。桥接 common.resolve_agent_cmd。"""
    return resolve_agent_cmd(agent_name, prompt, AGENTS)


# 评审框架（用户 6 点 + 裁决原则 + 输出契约）。改这里即可全局调整 prompt。
FRAMEWORK_PROMPT = """你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】{plan_relpath}
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `{out_dir_rel}/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本仓是 **Cerebro / path-SSOT 只读回测叉**：无实盘、无 QMT 下载、无 Redis 流。把握不准可读代码或做实验，以事实为准。

【本仓必查盲区（评审必须逐条核对）】
- **T+1 / 隔日成交**：买入信号能否在当日卖出？卖出是收盘价还是次日开盘？有无用到未来 bar？
- **复权口径**：均线与盈筹率是否同一套 `adjust_type`（本仓筹码默认 front）？
- **盈筹率尺度**：`cyqk_c` 是 0–1 还是 0–100？70% 阈值有无单位错误？
- **周均线定义**：20 周均线是周线 resample 后 SMA(20)，还是 100 日近似？
- **包边界**：算法走 `oskh_factors` / `qlib_cost`，Cerebro 包装走 `backtest/`，研究 CLI 走 `backtest/research/`。

【裁决原则（重要）】
- 视自己与其他评审者为同行专家，**参考学习、互相验证、取长补短**：结论交叉核对、补彼此盲区，而非单纯挑错。
- **事实类断言**（函数位置 / 行为 / 数值等可验证项）→ **以代码与实验为准**：读代码取证，把握不准时跑最小实验，不靠票数下结论。
- **经验/取舍类断言**（该不该这样做、风险量级、更稳的写法）→ **以业内 A 股量化惯例与成熟开源实践为准**（backtrader / 本仓 Cerebro）。
- **SSOT 一致性检查**：对照 `README.md` 布局、`common/infra/data_root.py` path-SSOT、`backtest/chip_indicator.py` 筹码包装。勿引用本仓不存在的实盘/LEBS 文档当硬 SSOT。
- **★ 安全阀/超时/并发类设计，必须跑最小实验验证行为**（不只读代码！）：timeout / budget / safety-valve / circuit-breaker / 并发锁 / 异步 / fallback / 重试——这些 bug 藏在 stdlib/框架行为里（如 `ThreadPoolExecutor.__exit__`→`shutdown(wait=True)` 让超时从不生效），**读代码看不出来**。实验格式：构造 slow fn + tight budget → 测调用方**何时返回**（`time.monotonic` 对比 budget_s vs 实际）。2026-07-04 实测：option-X budget docstring 宣称 "releases caller" 但实际 8s 才返（非 1s budget）——**docstring 不可信，实验为准**。**实验结论须附可复现脚本 + 完整原始输出**（含进程 pid/存活检查等），与官方文档/CPython 源码矛盾的结论标注「建议主持裁/下游复核」。2026-07-16 教训：r3 kimi 实验「subprocess.run(timeout) 不杀子进程」结论错，r4 qoder 引源码 + 主持裁亲自实验（child TERMINATED）才纠正——下游 incorporate 实验断言须亲自复现。

【输出格式】
按严重度分级，每条尽量带 file:line 证据：
- 🔴 必须修（事实错误 / 会误导实现 / 逻辑矛盾）
- 🟡 应修（设计缺口 / 风险）
- 🟢 可选（nice-to-have）
- ✅ 做对的地方（保留）
末尾给一句总评 + 是否可进实现。"""


# --host 省略时走 default_host()（Linux=claude 空槽；Win=cursor-desktop）。


def _host_type(value: str) -> str:
    try:
        return parse_host_arg(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from e

# Per-agent role suffix（固定角色，不交换）：给每家不同侧重，减 groupthink。
# mixed 预设下所有 cursor:model 走 base "cursor" 角色。
AGENT_ROLE_SUFFIX: dict[str, str] = {
    "codex": "\n\n【你的评审侧重】优先审**实现可操作性**：函数名/文件位置/调用链/API 契约——程序员能否照此编码？哪里会卡住？哪些 import 是私有的需 wrapper？",
    "kimi": "\n\n【你的评审侧重】优先**跑实验验证关键行为**：对 timeout/budget/safety-valve/并发锁/异步/fallback/重试类设计，构造最小实验（slow fn + tight budget → 测调用方何时返回）。读码不够时动手测——**docstring 不可信**（docstring 宣称的行为可能被 stdlib/框架吞掉，如 `ThreadPoolExecutor.__exit__`→`shutdown(wait=True)` 让超时从不生效）。保持这个习惯。",
    "qoder": "\n\n【你的评审侧重】优先**量化风险**：给数值场景/边界 case/capital-risk 评估——用数字，不给定性。例：阈值不一致→数值表展示哪些 case 触发/不触发；silent drop→量化受影响行数/股票数。",
    "cursor": "\n\n【你的评审侧重】优先核 **SSOT 一致性 + 行级精确性**：逐条 file:line 读代码取证（不只信 docstring/注释/历史文档——文档与代码漂移是常见事实反转源）；对照 SSOT 文档查 config 键/格式/命名冲突；gate/exit code/触发条件须核代码实际逻辑。",
    "grok": "\n\n【你的评审侧重】优先**实现 / 协议 / Linux-VM CLI**：核对实现是否可落地、协议/契约用词是否越界、Linux 侧 CLI 与编排是否可 headless 跑通。",
    # claude 仅在作为评审员（非 host）时使用
    "claude": "\n\n【你的评审侧重】优先**综合裁决 + 跨文档交叉验证**：检查方案内部自洽（不自相矛盾）、跨节引用一致、与关联 plan/SSOT 的衔接；对抗性复核其他评审员的断言（凭代码/实验驳回误判）。",
}


def _resolve_role_suffix(agent: str, host: str) -> str:
    """Resolve fixed role suffix for agent.

    - ``agent == host`` → 空串（host 做综合裁决，不追加评审侧重）
    - ``cursor:kimi-*`` → **kimi** 席位（实验验证），不走 cursor SSOT 角色
    - 其余 ``cursor:<model>`` → base ``cursor`` 角色
    - 其余 → agent 自己的侧重
    """
    if agent == host:
        return ""
    return AGENT_ROLE_SUFFIX.get(review_seat(agent), "")


def _fs_safe(name: str) -> str:
    """Sanitize agent name for filesystem paths (replace : with -)."""
    return name.replace(":", "-")


def _is_host_slot(name: str, host: str) -> bool:
    """host 走空槽分支，不被子进程拉起。"""
    return name == host


def _host_slot_text(host: str, plan_relpath: str) -> str:
    return (
        f"# {host} 评审（由编排者填写）\n\n"
        f"> 待评审：{plan_relpath}\n\n"
        f"> 状态：⏳ 待编排者填写——填好后并入 merge-consensus 综合步骤。\n\n"
        "<!-- 按 🔴 必须修 / 🟡 应修 / 🟢 可选 / ✅ 做对 分级，每条带 file:line 证据 -->\n"
    )


def _run_single_agent(
    agent_name: str, cmd: list[str], timeout: int, outpath: Path, stdin_text: str = ""
) -> tuple[str, str, float, Path]:
    """Thin wrapper for parallel executor map."""
    rc, elapsed = run_agent(agent_name, cmd, timeout, outpath, stdin_text=stdin_text)
    return agent_name, str(rc), elapsed, outpath


def _out_dir_rel(out_dir: Path) -> str:
    """Repo-relative posix path for prompt embedding (fallback: absolute)."""
    try:
        return out_dir.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(out_dir)


def _build_prompt(plan_relpath: str, out_dir: Path) -> str:
    return FRAMEWORK_PROMPT.format(
        plan_relpath=plan_relpath, out_dir_rel=_out_dir_rel(out_dir)
    )


def _write_plan_meta(
    args: argparse.Namespace, plan_abs: Path, out_dir: Path, prompt: str | None = None
) -> None:
    """Write _prompt.md + _plan_version.txt into *out_dir* (shared metadata)."""
    if prompt is None:
        prompt = _build_prompt(args.plan, out_dir)
    (out_dir / "_prompt.md").write_text(prompt, encoding="utf-8")

    import hashlib as _hl

    try:
        _sha = (
            subprocess.run(
                ["git", "rev-parse", "--short", f"HEAD:{args.plan}"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            or "<untracked>"
        )
    except Exception:
        _sha = "<git-unavailable>"
    _chash = _hl.sha256(plan_abs.read_bytes()).hexdigest()[:16]
    today = _dt.date.today().isoformat()
    (out_dir / "_plan_version.txt").write_text(
        f"path={args.plan}\ngit_sha={_sha}\ncontent_sha256_16={_chash}\nreviewed_at={today}\n",
        encoding="utf-8",
    )


def _run_serial(
    args: argparse.Namespace,
    plan_abs: Path,
    out_dir: Path,
    names: list[str],
    prompt: str,
    host: str,
) -> list[tuple[str, str, float, Path]]:
    """串行模式（依次执行，可逐个 tail -f 实时看）。"""
    results: list[tuple[str, str, float, Path]] = []
    for n in names:
        if _is_host_slot(n, host):
            slot = out_dir / f"{_fs_safe(n)}.md"
            if args.dry_run:
                print(f"[dry] {n}: (host 空槽，编排者另填)")
            elif slot.exists():
                print(f"[slot] {n}: {_rel_display(slot)}  (已存在，保留)")
            else:
                slot.write_text(_host_slot_text(host, args.plan), encoding="utf-8")
                print(f"[slot] {n}: {_rel_display(slot)}  (空槽已建)")
            results.append((n, "slot", 0.0, slot))
            continue
        agent_prompt = prompt + _resolve_role_suffix(n, host)
        cmd = _resolve_agent_cmd(n, agent_prompt)
        if not cmd:
            print(f"[skip] unknown agent: {n}")
            continue
        base_name = n.split(":", 1)[0]
        timeout = (
            args.timeout if args.timeout > 0 else DEFAULT_AGENT_TIMEOUTS.get(agent_timeout_key(n), 600)
        )
        if args.dry_run:
            shown = (
                " ".join(cmd + ["<prompt via stdin>"])
                if base_name in _STDIN_AGENTS
                else " ".join(cmd[:-1] + ["<prompt...>"])
            )
            print(f"[dry] {n} (timeout {timeout}s): {shown}")
            results.append((n, "dry", 0.0, out_dir / f"{_fs_safe(n)}.md"))
            continue
        outpath = out_dir / f"{_fs_safe(n)}.md"
        print(f"[..] {n} running (timeout {timeout}s)...")
        stdin_text = agent_prompt if base_name in _STDIN_AGENTS else ""
        rc, elapsed = run_agent(n, cmd, timeout, outpath, stdin_text=stdin_text)
        results.append((n, str(rc), elapsed, outpath))
        flag = "OK  " if rc == 0 else f"FAIL(rc={rc})"
        print(f"[{flag}] {n}: {_rel_display(outpath)}  ({elapsed:.0f}s)")
    return results


def _run_parallel(
    args: argparse.Namespace,
    plan_abs: Path,
    out_dir: Path,
    names: list[str],
    prompt: str,
    host: str,
) -> list[tuple[str, str, float, Path]]:
    """并行 fan-out：各 agent 写入独立子目录，完成后合并回主目录。
    host 空槽在主目录，不参与并行。"""
    parallel_root = out_dir / "_parallel"
    parallel_root.mkdir(parents=True, exist_ok=True)

    # Collect external agents to run in parallel
    futures: dict[str, concurrent.futures.Future] = {}
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max(1, len(AGENTS))
    ) as executor:
        for n in names:
            if _is_host_slot(n, host):
                continue  # handled after parallel block
            agent_prompt = prompt + _resolve_role_suffix(n, host)
            cmd = _resolve_agent_cmd(n, agent_prompt)
            if not cmd:
                print(f"[skip] unknown agent: {n}")
                continue
            base_name = n.split(":", 1)[0]
            timeout = (
                args.timeout if args.timeout > 0 else DEFAULT_AGENT_TIMEOUTS.get(agent_timeout_key(n), 600)
            )
            agent_dir = parallel_root / _fs_safe(n)
            agent_dir.mkdir(parents=True, exist_ok=True)
            _write_plan_meta(args, plan_abs, agent_dir, prompt)
            outpath = agent_dir / f"{_fs_safe(n)}.md"
            if args.dry_run:
                shown = (
                    " ".join(cmd + ["<prompt via stdin>"])
                    if base_name in _STDIN_AGENTS
                    else " ".join(cmd[:-1] + ["<prompt...>"])
                )
                print(f"[dry] {n} (timeout {timeout}s): {shown}")
                continue
            print(f"[..] {n} running (parallel, timeout {timeout}s)...")
            stdin_text = agent_prompt if base_name in _STDIN_AGENTS else ""
            futures[n] = executor.submit(
                _run_single_agent, n, cmd, timeout, outpath, stdin_text
            )

    # Collect results live: as_completed → 完成即打印（原实现按提交顺序 f.result()
    # 阻塞，先完成的后报）。结果行仍按 preset 顺序组装，executor 级异常按排除法归属。
    by_name: dict[str, tuple[str, str, float, Path]] = {}
    for f in concurrent.futures.as_completed(futures.values()):
        try:
            agent_name, rc_raw, elapsed, outpath = f.result()
        except Exception as e:
            print(f"[FAIL] parallel executor error: {e!r}")
            continue
        rc = (
            int(rc_raw)
            if isinstance(rc_raw, str) and str(rc_raw).isdigit()
            else rc_raw
        )
        flag = "OK  " if rc == 0 else f"FAIL(rc={rc})"
        print(f"[{flag}] {agent_name}: {_rel_display(outpath)}  ({elapsed:.0f}s)")
        by_name[agent_name] = (agent_name, str(rc), elapsed, outpath)

    results: list[tuple[str, str, float, Path]] = []
    for n in names:
        if _is_host_slot(n, host):
            slot = out_dir / f"{_fs_safe(n)}.md"
            if args.dry_run:
                print(f"[dry] {n}: (host 空槽)")
            elif slot.exists():
                print(f"[slot] {n}: {_rel_display(slot)}  (已存在，保留)")
            else:
                slot.write_text(_host_slot_text(host, args.plan), encoding="utf-8")
                print(f"[slot] {n}: {_rel_display(slot)}  (空槽已建)")
            results.append((n, "slot", 0.0, slot))
            continue
        r = by_name.get(n)
        if r is not None:
            results.append(r)
            continue
        if n in futures:
            # future 抛异常未产出结果行（上方已打印 FAIL）→ 按排除法补 rc=1 行
            results.append(
                (n, "1", 0.0, parallel_root / _fs_safe(n) / f"{_fs_safe(n)}.md")
            )

    # Merge parallel outputs back to main out_dir
    _merge_parallel_outputs(parallel_root, out_dir)
    return results


def _merge_parallel_outputs(parallel_root: Path, out_dir: Path) -> None:
    """Promote scratch outputs; version stamps enter _version_manifest.json."""
    merge_parallel_artifacts(
        parallel_root,
        out_dir,
        version_filename="_plan_version.txt",
        version_kind="plan",
    )


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(line_buffered=True)
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="多 agent 设计稿评审 fan-out 编排器")
    ap.add_argument("--plan", required=True, help="待评审文档，相对仓库根")
    ap.add_argument(
        "--out-dir", help="输出目录（默认 docs/architecture/reviews/<today>/<slug>）"
    )
    ap.add_argument(
        "--preset",
        default="classic",
        choices=["classic", "mixed"],
        help="预设模式（默认 classic=按平台四家；mixed=host + cursor 自带多模型，不拉独立 CLI）",
    )
    ap.add_argument(
        "--host",
        default=None,
        type=_host_type,
        help="主持人（综合者空槽，谁发起谁综合）：独立 agent / cursor-desktop / cursor:<model>。"
        f"省略 = preset.host 或 default_host()（Linux=claude 空槽，Win=cursor-desktop；mixed 不预设 host）",
    )
    ap.add_argument(
        "--agents",
        default="",
        help="手动指定 agent 列表（逗号分隔）；为空则用 --preset 默认。支持 cursor:<model> 语法",
    )
    ap.add_argument(
        "--exclude",
        default="",
        help="逗号分隔，排除的 agent（如起草者避利益冲突）",
    )
    ap.add_argument(
        "--parallel",
        action="store_true",
        default=True,
        help="并行运行外部 agent（默认开启；写入独立子目录后合并）",
    )
    ap.add_argument(
        "--serial",
        action="store_false",
        dest="parallel",
        help="串行运行（依次执行，可逐个 tail -f 实时看）",
    )
    ap.add_argument(
        "--timeout", type=int, default=0, help="每个 agent 超时秒；0=按 agent 默认"
    )
    ap.add_argument(
        "--ignore-cursor-preflight",
        action="store_true",
        help="cursor 模型预检不可用（--list-models 网络/鉴权失败）时仍继续 fan-out（默认阻断——"
        "2026-08-14 教训：预检不可用拦不住 5 路全挂，烧一轮无效评审）",
    )
    ap.add_argument(
        "--prompt-file",
        default="",
        help="自定义评审 prompt 文件（替代内置 FRAMEWORK_PROMPT；聚焦单章节等场景用）",
    )
    ap.add_argument("--dry-run", action="store_true", help="只打印命令不执行")
    args = ap.parse_args(argv)

    plan_abs = (REPO_ROOT / args.plan).resolve()
    if not plan_abs.is_file():
        print(f"[err] plan not found: {plan_abs}", file=sys.stderr)
        return 2

    host = args.host or PRESETS[args.preset].get("host") or default_host()

    # 解析 preset → agents 列表
    if args.agents:
        agents_str = args.agents
        preset_desc = "手动"
    else:
        preset = PRESETS[args.preset]
        agents_str = preset["agents"]
        preset_desc = preset["description"]

    names = [a.strip() for a in agents_str.split(",") if a.strip()]
    excluded = {a.strip() for a in args.exclude.split(",") if a.strip()}
    host = canonical_host_slot(names, host)

    # host 在 exclude 里 = 矛盾配置，fail-fast（此前静默保留 host 并继续 fan-out，
    # tests/test_run_multi_ai_review_host.py 记录的期望行为）
    if host in excluded or review_seat(host) in excluded or _agent_base(host) in excluded:
        print(
            f"[err] host={host} 在 --exclude 列表中（矛盾配置）。\n"
            f"      host 是综合空槽（不被子进程拉起为评审员）：起草者=host 时无需 exclude，\n"
            f"      它本来就不会作为评审员被拉起；要换综合者用 --host <name>；\n"
            f"      要去掉某评审员，只把它（非 host）加进 --exclude。",
            file=sys.stderr,
        )
        return 2

    # host 必须在列表里
    if host not in names:
        names.append(host)

    # 排除非 host agent（--exclude cursor 也去掉 cursor:<model> 变体）
    names = [
        n for n in names
        if n == host or (
            n not in excluded
            and _agent_base(n) not in excluded
            and review_seat(n) not in excluded
        )
    ]

    assert_qoder_allowed(names)

    # cursor:<model> 变体可用性预检（mixed 预设；模型 ID 随 CLI 自更新漂移）。
    # fail-closed：--list-models 不可用（网络/鉴权）时默认阻断 fan-out（2026-08-14 教训：
    # 预检不可用但 5 路照跑全 rc=1，烧一轮无效评审）；--ignore-cursor-preflight 显式旁路。
    _variants_cm = sorted({n.split(":", 1)[1] for n in names if n.startswith("cursor:")})
    if _variants_cm:
        _missing_cm, _avail_cm = preflight_cursor_models(names)
        if _avail_cm is None:
            if not args.ignore_cursor_preflight:
                print(
                    "[err] cursor --list-models 预检不可用（网络/鉴权）——"
                    "默认阻断 fan-out；确认环境后重跑，或显式 --ignore-cursor-preflight 旁路",
                    file=sys.stderr,
                )
                return 2
            print("[warn] cursor --list-models 预检不可用（--ignore-cursor-preflight 旁路），跳过 cursor 模型校验")
        elif _missing_cm:
            print(
                f"[err] cursor 模型不存在: {_missing_cm}；当前 --list-models 可用: {_avail_cm}",
                file=sys.stderr,
            )
            return 2
        else:
            print(f"[ok] cursor 模型预检通过: {_variants_cm}")

    linux_errs = linux_review_preflight(names)
    if linux_errs:
        for e in linux_errs:
            print(f"[err] Linux 评审预检: {e}", file=sys.stderr)
        return 2

    # 校验至少 1 个外部评审员
    non_host = [n for n in names if not _is_host_slot(n, host)]
    if not non_host:
        print(
            f"[warn] 仅 host={host} 在列表（无外部评审员）；将只建空槽，无子进程评审",
            file=sys.stderr,
        )

    today = _dt.date.today().isoformat()
    slug = plan_abs.stem
    out_dir = (
        Path(args.out_dir).resolve()
        if args.out_dir
        else REPO_ROOT / "docs" / "architecture" / "reviews" / today / slug
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    else:
        prompt = _build_prompt(args.plan, out_dir)
    _write_plan_meta(args, plan_abs, out_dir, prompt)

    names_msg = (
        f"host={host}  preset={args.preset} ({preset_desc})  "
        f"agents={names}  "
        f"excluded={sorted(excluded) if excluded else 'none'}  "
        f"mode={'parallel' if args.parallel else 'serial'}  "
        f"timeout={'per-agent' if args.timeout <= 0 else args.timeout}s"
    )
    print(f"[run] plan={args.plan}  out={_rel_display(out_dir)}  {names_msg}")

    if args.parallel and not args.dry_run:
        results = _run_parallel(args, plan_abs, out_dir, names, prompt, host)
    else:
        results = _run_serial(args, plan_abs, out_dir, names, prompt, host)

    print("\n=== summary ===")
    for n, rc, elapsed, outpath in results:
        print(
            f"  {n:8s} rc={str(rc):10s} {elapsed:6.1f}s  {_rel_display(outpath)}"
        )
    print(
        f"\n下一步：{host} 评审由编排者另出；之后做综合 / 证据裁决（merge-consensus）。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
