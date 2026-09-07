# 多 agent 设计稿评审（本仓精简版）

从 OSkhQuant1.3 复制编排器，按本仓范围裁剪。本仓是 Cerebro + path-SSOT 只读回测，不评实盘 / QMT / Redis。

## 一条命令

```powershell
D:\anaconda3\envs\vanna312\python.exe scripts/run/run_multi_ai_review.py `
    --plan docs/backtest/plan-xxx.md --host cursor-desktop
```

常用 flag：

- `--preset classic`（默认；Windows = codex + **Cursor Kimi** + cursor:auto + claude；host 默认 `cursor-desktop`）
- kimi 席位默认 `cursor:kimi-k3-high`（独立 kimi-code 周额度用尽）。`OSKH_KIMI_VIA_CURSOR=0` 才回独立 CLI
- `--preset mixed`（只拉 Cursor 自家模型：auto / grok-4.6-xhigh-fast / composer-2.5-fast）
- `--dry-run` 只打印命令
- Cursor headless 默认 ``--mode ask``（``plan`` 会长评审 rc=0 空壳）。空产会再以 ask 重试。``OSKH_CURSOR_HEADLESS_MODE=plan`` 可强制 plan

产物：`docs/architecture/reviews/<YYYY-MM-DD>/<plan-stem>/`

## 主笔侧对抗层（fan-out 前）

按 `docs/prompts/prompt-adversarial-subagent-review.md` 开 3 路 Task：

- `dissent-steelman`
- `domain-safety`
- `pattern-evidence`

对抗草案不计独立票。回填 plan 后再 fan-out。

## 综合

主持裁写 `merge-consensus.md`：事实看代码/实验，取舍看 A 股回测惯例。有 🔴 则改 plan 再开一轮；无新 🔴 或用户叫停则进实现。

## 源文件

- `scripts/run/run_multi_ai_review.py`
- `scripts/run/multi_ai_common.py`
- `docs/prompts/prompt-multi-ai-design-review.md`
