# Codex 交接工作流（codex-impl-handoff）

> **用途**：本仓把一份已人裁 GO 的 plan 交给 Codex 无头实施的标准化流程。本文是**薄指针**，权威细则住 MyQuant（1.3）；本仓只锁命名约定与七步顺序。
> **命名**：中文「Codex 交接工作流」／slug `codex-impl-handoff`。plan 里写「走 [Codex 交接工作流](workflow-codex-handoff.md)」即指本文。

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

## 历史用例

- [plan-pool-pipeline-r2r5-2026-09-12.md](_archive/plans/plan-pool-pipeline-r2r5-2026-09-12.md)（"lock plan for Codex"，PR #24）
- [plan-money-modes-v8-pername-2026-09-16.md](plan-money-modes-v8-pername-2026-09-16.md)（首个显式引用本工作流的 plan，含两路评审记录与 [handoff 交接文档](handoff-money-modes-v8-pername-codex-impl-2026-09-16.md)）
- [plan-cerebro-retire-2026-09-16.md](plan-cerebro-retire-2026-09-16.md)（前置退场 plan）
