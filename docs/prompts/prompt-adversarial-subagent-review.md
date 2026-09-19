# 提示词：主笔侧对抗性子代理评审

对任意 agent 说：

**按 `docs/prompts/prompt-adversarial-subagent-review.md`，对 `<plan>` vN 的 §3 启动 3 路对抗性子代理审查，综合为 host 评审草案并列出须回填 plan 的勘误表**

## 原则

1. 证据优先于票数。
2. 主笔让步必须写进勘误表，禁止 silently 改口。
3. 对抗草案不计独立票。
4. 本阶段不改业务代码。
5. 不只信 docstring。

## 编排硬规则（2026-09-19 实测）

**三路必须由宿主机（或编排脚本）各自起独立进程；禁止在一个 Codex/agent 会话内部再套一层子 Codex。**

| 做法 | 结果 |
|------|------|
| 宿主机并行 3× `codex exec`（推荐：`scripts/run/run_codex_adversarial_lanes.py`） | ✅ 可用 |
| `run_multi_ai_review.py` fan-out（各 CLI 独立子进程） | ✅ 可用 |
| 会话内 `collaboration.spawn_agent` / 同类 collab spawn | ❌ headless 无 thread → `no thread with id` |
| 会话内再跑 `codex exec`（含 `-s read-only` / `workspace-write` / `danger-full-access`） | ❌ 外层 bwrap 只读挂载 `/` + 常 `--unshare-net` → 内层写 `~/.codex` 报 `Read-only file system (os error 30)`；即便 `CODEX_HOME=/tmp` 仍可能因断网挂起 |

若某路未能以**独立进程**跑完：该路文件必须标注「host 代拟 / 不计独立票」，**不得**伪装成三路独立审查已完成。

ChatGPT 登录（非 API key）本机当前可用最高编码档以 `codex` 默认/`models_cache` 为准（2026-09-19：`gpt-6-astra` + `model_reasoning_effort=xhigh`）；`gpt-5.1-codex-max` / `gpt-5.3-codex` 在该登录方式下不可用。

## 三路

| 角色 | 强制立场 | 必查 |
|------|----------|------|
| dissent-steelman | 反对主笔裁决 | 可测性黑洞、不可逆窗口、主笔「已覆盖」反例 |
| domain-safety | fail-closed | T+1、未来函数、复权混用、盈筹率单位、停牌/涨跌停 |
| pattern-evidence | 怀疑过度类比 | 是否该复用 `chip_indicator` / `StockDataReader`、包边界、文档漂移 |

每路输出：结论 / Findings（`file:line`）/ 对 §3 的独立裁决 / 未验证。
