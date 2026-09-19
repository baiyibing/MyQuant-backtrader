#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宿主机并行启动 Codex 三路对抗审查（禁止会话内套娃）。

2026-09-19 本机复现：在单个 ``codex exec`` 会话里再 ``codex exec`` / collab spawn
会因外层 bwrap 只读挂载 ``/`` + 常 ``--unshare-net`` 失败
（``Read-only file system (os error 30)`` / 断网挂起）。
正确做法：由**本脚本在宿主机**并行起 3 个独立 ``codex exec`` 进程。

用法::

    python3 scripts/run/run_codex_adversarial_lanes.py \\
      --plan docs/backtest/plan-xxx.md \\
      --out-dir docs/architecture/reviews/2026-09-19/plan-xxx-codex-adv

默认模型：ChatGPT 登录下以本机可用最高编码档为准（可用 ``--model`` 覆盖）。
详见 ``docs/prompts/prompt-adversarial-subagent-review.md``「编排硬规则」。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

LANES: tuple[tuple[str, str, str], ...] = (
    (
        "dissent-steelman",
        "dissent-steelman",
        "强制立场：反对主笔裁决。必查可测性黑洞、不可逆窗口、主笔「已覆盖」反例。",
    ),
    (
        "domain-safety",
        "domain-safety",
        "强制立场：fail-closed。必查 T+1、未来函数、复权混用、盈筹率单位、停牌/涨跌停。",
    ),
    (
        "pattern-evidence",
        "pattern-evidence",
        "强制立场：怀疑过度类比。必查是否该复用 chip_indicator / StockDataReader、包边界、文档漂移。",
    ),
)


def _build_prompt(*, plan_rel: str, lane_id: str, stance: str) -> str:
    return f"""按 docs/prompts/prompt-adversarial-subagent-review.md，你只跑三路中的【{lane_id}】这一路。

{stance}

审查对象：仓库内 `{plan_rel}`（先 Read 全文；行号以你读到的版本为准）。

硬约束：
- Docs-only：只写本路产物；禁止改 production Python；禁止跑回测。
- 证据优先；每条 Finding 必须 file:line。
- 不要再 spawn 子 agent，也不要再套一层 codex exec（宿主机已做进程隔离）。
- 开工时用 git rev-parse HEAD 与 origin/master（或 plan 内 IMPLEMENTATION_BASE）核对基线。

只写入这一个文件（覆盖写）：
docs 相对路径由调用方指定的 out-dir 下的 `{lane_id}.md`

文件结构：
# {lane_id}
## 结论
## Findings（file:line）
## 对 plan §3 / 主船范围的独立裁决
## 未验证
## 模型与 effort（写你实际用到的）
"""


def _codex_cmd(
    *,
    prompt: str,
    model: str | None,
    effort: str | None,
    sandbox: str,
    workdir: Path,
    last_message: Path,
) -> list[str]:
    cmd = [
        "codex",
        "exec",
        "--ephemeral",
        "-s",
        sandbox,
        "-C",
        str(workdir),
        "--output-last-message",
        str(last_message),
    ]
    if model:
        cmd.extend(["-m", model])
    if effort:
        cmd.extend(["-c", f"model_reasoning_effort={effort}"])
    cmd.append(prompt)
    return cmd


def _run_lane(
    *,
    lane_id: str,
    stance: str,
    plan_rel: str,
    out_dir: Path,
    workdir: Path,
    model: str | None,
    effort: str | None,
    sandbox: str,
    timeout_s: int,
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    last_path = out_dir / f"_{lane_id}.last.txt"
    stdout_path = out_dir / f"_{lane_id}.stdout.log"
    stderr_path = out_dir / f"_{lane_id}.stderr.log"
    # Ask codex to write the lane markdown itself under out_dir.
    # Also keep last-message as a fallback artifact.
    prompt = _build_prompt(plan_rel=plan_rel, lane_id=lane_id, stance=stance)
    prompt += (
        f"\n\n请把完整本路报告写入：`{out_dir.relative_to(workdir).as_posix()}/{lane_id}.md`"
        "（相对仓库根）。写完后在 stdout 最后一行打印 LANE_DONE="
        + lane_id
    )
    cmd = _codex_cmd(
        prompt=prompt,
        model=model,
        effort=effort,
        sandbox=sandbox,
        workdir=workdir,
        last_message=last_path,
    )
    t0 = time.time()
    try:
        with stdout_path.open("w", encoding="utf-8") as so, stderr_path.open(
            "w", encoding="utf-8"
        ) as se:
            proc = subprocess.run(
                cmd,
                cwd=str(workdir),
                stdin=subprocess.DEVNULL,
                stdout=so,
                stderr=se,
                timeout=timeout_s,
                env=os.environ.copy(),
                check=False,
            )
        rc = int(proc.returncode)
    except subprocess.TimeoutExpired:
        rc = 124
    except FileNotFoundError as e:
        stderr_path.write_text(f"codex binary missing: {e}\n", encoding="utf-8")
        rc = 127
    elapsed = round(time.time() - t0, 1)
    lane_md = out_dir / f"{lane_id}.md"
    # Fallback: if model forgot to write the md, promote last-message.
    if not lane_md.is_file() and last_path.is_file() and last_path.stat().st_size > 0:
        lane_md.write_text(
            f"# {lane_id}\n\n"
            f"> fallback: promoted from --output-last-message "
            f"(codex did not write {lane_id}.md directly)\n\n"
            + last_path.read_text(encoding="utf-8", errors="replace"),
            encoding="utf-8",
        )
    return {
        "lane": lane_id,
        "rc": rc,
        "elapsed_s": elapsed,
        "lane_md": str(lane_md.relative_to(workdir)) if lane_md.is_file() else None,
        "stderr": str(stderr_path.relative_to(workdir)),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", required=True, help="plan 路径（相对仓库根）")
    ap.add_argument("--out-dir", required=True, help="三路产物目录（相对仓库根）")
    ap.add_argument(
        "--model",
        default=os.environ.get("CODEX_ADV_MODEL") or None,
        help="可选；默认走 ~/.codex 配置 / 账号可用最高档",
    )
    ap.add_argument(
        "--effort",
        default=os.environ.get("CODEX_ADV_EFFORT", "xhigh"),
        help="model_reasoning_effort（默认 xhigh）",
    )
    ap.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="每路独立进程的 sandbox（默认 workspace-write，便于写 out-dir）",
    )
    ap.add_argument("--timeout", type=int, default=1800, help="每路超时秒数")
    ap.add_argument(
        "--serial",
        action="store_true",
        help="串行跑三路（默认并行）",
    )
    args = ap.parse_args(argv)

    workdir = _REPO_ROOT
    plan_path = (workdir / args.plan).resolve()
    if not plan_path.is_file():
        print(f"ERROR: plan not found: {args.plan}", file=sys.stderr)
        return 2
    out_dir = (workdir / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Refuse nested invocation inside an existing Codex sandbox.
    if os.environ.get("CODEX_SANDBOX") or os.environ.get("CODEX_THREAD_ID"):
        print(
            "ERROR: detected CODEX_SANDBOX/CODEX_THREAD_ID — refuse nested launch. "
            "Run this script on the host (outside any codex exec session).",
            file=sys.stderr,
        )
        return 3

    print(
        f"host-parallel codex adversarial: plan={args.plan} out={args.out_dir} "
        f"model={args.model or '(config default)'} effort={args.effort} "
        f"parallel={not args.serial}",
        flush=True,
    )

    results: list[dict[str, object]] = []
    if args.serial:
        for lane_id, _name, stance in LANES:
            results.append(
                _run_lane(
                    lane_id=lane_id,
                    stance=stance,
                    plan_rel=args.plan,
                    out_dir=out_dir,
                    workdir=workdir,
                    model=args.model,
                    effort=args.effort,
                    sandbox=args.sandbox,
                    timeout_s=args.timeout,
                )
            )
    else:
        with ThreadPoolExecutor(max_workers=len(LANES)) as pool:
            futs = {
                pool.submit(
                    _run_lane,
                    lane_id=lane_id,
                    stance=stance,
                    plan_rel=args.plan,
                    out_dir=out_dir,
                    workdir=workdir,
                    model=args.model,
                    effort=args.effort,
                    sandbox=args.sandbox,
                    timeout_s=args.timeout,
                ): lane_id
                for lane_id, _name, stance in LANES
            }
            for fut in as_completed(futs):
                results.append(fut.result())

    results.sort(key=lambda r: str(r["lane"]))
    summary = out_dir / "_host_launch_summary.md"
    lines = [
        "# Codex adversarial host-parallel launch summary",
        "",
        f"- plan: `{args.plan}`",
        f"- model: `{args.model or '(config default)'}`",
        f"- effort: `{args.effort}`",
        f"- sandbox: `{args.sandbox}`",
        f"- parallel: `{not args.serial}`",
        "",
        "| lane | rc | elapsed_s | lane_md |",
        "|---|---:|---:|---|",
    ]
    worst = 0
    for r in results:
        worst = max(worst, int(r["rc"]))
        lines.append(
            f"| `{r['lane']}` | {r['rc']} | {r['elapsed_s']} | `{r['lane_md']}` |"
        )
    lines.extend(
        [
            "",
            "## Reminder",
            "",
            "- 三路文件齐了之后，由 **host**（编排者，非再套一层 Codex 子会话）写",
            "  `adversarial-errata.md` 并回填 plan。",
            "- 任一路 rc≠0 或缺少 md：该路不计独立票，须在勘误里标明。",
            "",
        ]
    )
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for r in results:
        print(
            f"lane={r['lane']} rc={r['rc']} elapsed_s={r['elapsed_s']} md={r['lane_md']}",
            flush=True,
        )
    print(f"summary={summary.relative_to(workdir)}", flush=True)
    return 0 if worst == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
