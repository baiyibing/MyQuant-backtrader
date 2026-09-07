# 提示词：对某方案做多 agent 多轮评审

对任意 agent 说：

**按 `docs/prompts/prompt-multi-ai-design-review.md`，对 `<方案>` 做多 agent 多轮评审**

`<方案>` = `docs/` 里已落盘的 plan 路径。

编排器：`scripts/run/run_multi_ai_review.py`  
Runbook：`docs/engineering/multi-ai-review-workflow.md`

## 步骤

1. 若只有口头方案，先起草 `docs/backtest/plan-<topic>-<date>.md`。
2. 复杂取舍先跑 `docs/prompts/prompt-adversarial-subagent-review.md` 三路对抗，回填 plan。
3. fan-out：

```powershell
D:\anaconda3\envs\vanna312\python.exe scripts/run/run_multi_ai_review.py `
    --plan <plan路径> --host cursor-desktop
```

4. host 综合为 `merge-consensus.md`。有 🔴 则修订 plan 再跑。
5. 收敛后说「按 plan 实施」。

## 本仓约束

- 只评 Cerebro / path-SSOT / 筹码包装，不把实盘栈当前提。
- 评审员禁改文件。
- 输出：🔴 / 🟡 / 🟢 / ✅，每条带 `file:line`。
