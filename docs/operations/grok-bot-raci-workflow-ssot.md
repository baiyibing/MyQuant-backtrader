# Grok Bot RACI/CLI workflow SSOT 指针（MyQuant-backtrader）

本仓**不再维护** RACI / 工作流 / 模型钉 / headless 正文。唯一权威仓库为 `grok-bot-ops` 的 `master`。

<a id="access"></a>
## 访问方式

Human 2026-11-16：ops 只保留在私有 Gitea，GitHub 副本已删除。使用从 Gitea 同步的显式本地 checkout；远端地址保留在宿主 Git 配置中，本公开仓不记录内部 URL。

CLI 通过绝对路径 `MYQUANT_OPS_ROOT` 或 `--ops-root` 消费该 checkout。先确认其版本包含当前 `scripts/runtime-api.json` 所声明的能力；缺失或不兼容时明确失败，不复制运行时或模型目录，也不自动猜测兄弟目录。

以下路径均相对于该 ops checkout；在本地打开或在已登录的 Gitea 仓库中按路径查看。

<a id="raci"></a>
## RACI 与执行通道

- RACI / Owner / 流水线 / 模型钉：`docs/raci/grok-bot-raci-workflow-ssot.md`。
- 4090 通道：`docs/channels/newtest-4090-execution-channels-ssot.md`。
- 沟通与复现词典：`docs/glossary/research-ops-glossary.md`。
- Codex 交接工作流：`docs/handoff/workflow-codex-handoff.md`。

<a id="runtime"></a>
## 共享运行时与提示词

- 运行时合同：`docs/multi-ai/shared-runtime-20261109.md`。
- 设计评审提示词：`docs/multi-ai/prompt-multi-ai-design-review.md`。
- 对抗评审提示词：`docs/multi-ai/prompt-adversarial-subagent-review.md`。
- BT 消费入口与领域配置：[消费工作流](../engineering/multi-ai-review-workflow.md)。

<a id="archive"></a>
## 历史证据

ops 的迁移、源版本和原 GitHub PR 元数据归档见其 `docs/forge/github-retirement-20261116.md` 及迁移 release。历史 GitHub PR 编号仍表示原记录，不映射成同号 Gitea PR。本仓历史证据保留原身份。

**禁止**在本仓镜像 Owners 表、pipeline 步骤或 `-m` pins。历史正文曾合于本路径（PR #163 / #466）；2026-10-12 迁入 ops 后本文件保持薄指针。
