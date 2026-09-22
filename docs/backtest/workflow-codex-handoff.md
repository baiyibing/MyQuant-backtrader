# Codex 交接工作流（codex-impl-handoff）

> **用途**：本仓把一份已人裁 GO 的 plan 交给 Codex 无头实施的标准化流程。本文是**薄指针**，权威细则住 MyQuant（1.3）；本仓只锁命名约定与七步顺序。
> **命名**：中文「Codex 交接工作流」／slug `codex-impl-handoff`。plan 里写「走 [Codex 交接工作流](workflow-codex-handoff.md)」即指本文。

> **角色落点**：物理机 agent 发起 → 仓主管 bot 接手 → Codex → Grok 核，见 [`../operations/grok-bot-raci-workflow-ssot.md`](../operations/grok-bot-raci-workflow-ssot.md)。

## 七步

1. **Plan 起草**：dated plan 文档 `docs/backtest/plan-<slug>-<YYYY-MM-DD>.md`。必含：状态/风险档头、业务源、现状锚点（禁止重做已落地项）、现锁 `R*` 规则、人裁点 `P*`、非目标、切片（分 commit、带完成定义）、验证命令、代码落点、修订程序。
2. **评审**：多路独立评审，产物落 `docs/architecture/reviews/<YYYY-MM-DD>/plan-<slug>/<host>.md` + `merge-consensus.md`（证据裁决，不投票）。MyQuant 侧可跑 `scripts/run/run_multi_ai_review.py`（runbook 见 [multi-ai-review-workflow.md](../../../../OSkhQuant1.3/docs/engineering/multi-ai-review-workflow.md)）。
3. **人裁 GO**：`P*` 问题逐条裁决；plan 修订到 vN 并把状态改为「✅ 已人裁 GO（commit hash）」。**GO 前禁编码**（分级见 MyQuant [ai-code-review-governance.md](../../../../OSkhQuant1.3/docs/engineering/ai-code-review-governance.md)）。
4. **交接文档**：`docs/backtest/handoff-<slug>-codex-impl-<YYYY-MM-DD>.md`，结构照范例 [handoff-closeout-followups-codex-impl-2026-08-14.md](../../../../OSkhQuant1.3/docs/engineering/handoff-closeout-followups-codex-impl-2026-08-14.md)：
   - 头部：日期 / plan vX 已 GO（hash）/ 评审链 / 权威 plan 链接；
   - **§0 硬边界**（人裁已定，勿越，编号列表）；
   - 每切片：**代码事实锚点（HEAD hash + file:line）**→ 实施步骤（精确到签名/调用点）→ 语义要点（评审实证，勿推翻）→ 测试（新增/更新清单）；
   - 末尾门禁清单 + 回写要求。
5. **Codex 无头实施**：从当时 master 开 `feat/<slug>` 分支；`codex exec --dangerously-bypass-approvals-and-sandbox`（full-auto 配置：`approval_policy=never` + `sandbox_mode=workspace-write`，见 [prompt-codex-config-fullauto.md](../../../../OSkhQuant1.3/docs/prompts/prompt-codex-config-fullauto.md)）。切片 A/B 分 commit；遇 plan 未覆盖的语义分叉**停下来问人**，不自裁。
6. **缺陷优先复核**：实施完成后对 diff 做缺陷优先（defect-first）复核，证据回写 reviews 目录或 run-record。
7. **回写 plan 状态**：plan 头部改「✅ 已实施（PR #N）」；交接文档标完成；数字类产物不入库（exports/ 除外约定照各 plan）。

## 门禁（本仓）

- `D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/`（受影响域全文件）
- 行为变更类断言**更新断言不放宽 gate**（契约涟漪原则）
- 文本文件 UTF-8 无 BOM、NUL 计数为 0

## 坑位（累积）

- **对抗/多路评审不要 Codex 套娃**（2026-09-19）：三路对抗与多 agent fan-out 必须由**宿主机**起独立 `codex exec` / CLI 子进程（`scripts/run/run_codex_adversarial_lanes.py`、`scripts/run/run_multi_ai_review.py`）。在单个 Codex 会话内 `spawn_agent` 或再套 `codex exec` 会因外层 bwrap 只读 `/` + `--unshare-net` 失败（`os error 30` / 断网挂起）。细则见 `docs/prompts/prompt-adversarial-subagent-review.md`「编排硬规则」。
- **堆叠 PR 的 base 分支被删会连带关闭上层 PR**（实例：#59 base=`feat/cerebro-retire`，#58 合并删分支后 GitHub 自动关闭 #59，内容 rebase 后重开为 #61）。规则：前置 PR 合并后**立即确认上层 PR 存活**；重开时 rebase、并在 plan/交接文档回填新 PR 号。

## 历史用例

- [plan-pool-pipeline-r2r5-2026-09-12.md](_archive/plans/plan-pool-pipeline-r2r5-2026-09-12.md)（"lock plan for Codex"，PR #24）
- [plan-cerebro-retire-2026-09-16.md](_archive/plans/plan-cerebro-retire-2026-09-16.md)（前置退场，PR #58 / merge `e89d1b8`）
- [plan-money-modes-v8-pername-2026-09-16.md](_archive/plans/plan-money-modes-v8-pername-2026-09-16.md)（首个显式引用本工作流的 plan，含两路评审记录与 [handoff 交接文档](handoff-money-modes-v8-pername-codex-impl-2026-09-16.md)；PR #61 / merge `a606070`，#59 因 base 删除重开）
