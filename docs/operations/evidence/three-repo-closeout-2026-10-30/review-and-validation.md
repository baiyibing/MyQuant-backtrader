# 统一收尾计划复核与验证

本次为仓库审计和规划文档，不是生产运行签收。主计划在独立审查后按下列证据修订；#1258 的合入是作者在盘点期间完成的另一个 PR，不计作本计划执行成果。

## 独立审查

审查初稿内容 SHA-256：`b1b5eb64d3ca17b8d225b2a2f7eee67dce6d6c65614f8913d879dca3a5de9e41`。三仓专项审查覆盖 1.3 核心 8 项、MyQuant 17 项、BT 18 项；主审另核 1.3 数据/运维 21 项。外部 CLI 使用仓内 `run_multi_ai_review.py`、自定义只读提示词、host 综合空槽；两次调用退出码均为 0。

| 审查视角 | 结果与处置 |
|---|---|
| 1.3 SHM/SDD/6.53 独立审查 | 无阻塞。采纳：P03→P04 只取该部署/消费者的字段；无首笔订单时保留订单链未签 |
| MyQuant 独立审查 | 17/17 条和 10 组完成/替代记录覆盖完整。采纳：R4/R5 最小路径不等待 R2/R3，PIT/证券转换不做研究总闸；修正首次空 bundle 措辞 |
| BT 独立审查 | 18/18 条覆盖完整。采纳：0C 同修旧费用身份并记录实际 profile/revision/费用合同；低现金必须有直接触发证据，未触发仍 NOT_COVERED |
| [Kimi CLI](kimi-review.md) | 无阻塞。采纳：#1258 计数保留为回执而非永久门槛；通知按 alert_domain 验收。volume 建议限定为具体消费者，不代签其他策略数据质量 |
| [Claude CLI](claude-review.md) | 可合入、两处轻微项。采纳：明确未合后续计划/草稿的补充 SHA 来源；清理列表拼接标点。其「大概率后续已合」推测不采纳，gh 核实的是未合分支文件存在 |

模型/调用元数据及专项审查摘要见 [review-manifest.json](review-manifest.json)。Claude CLI 使用本机已有路由，本轮没有另行证明后端模型身份；不把 CLI 品牌当作模型身份。原始 stdout 含本机路径/提示词的头部保留于本地审计目录，入仓正文去除该头部，原始与正文 hash 均留在 manifest。

## 事实增量与校验

- `gh` 在 2026-10-30 09:54 UTC 刷新五个原开放 PR 和三仓 head。#1258 已合，18 SUCCESS/1 SKIPPED；其余四个仍开放。1.3 compare 仅新增该 PR 的七个文件，MyQuant/BT head 未变。见 [github-refresh.json](github-refresh.json)。
- 两份主分支之外的补充来源已通过 `gh api .../contents?...ref=` 核文件存在：BT `42662418231ea87af4c72e83f8ee69d6396db715` 的 `hithink-coverage-followup-2026-10-30.md`，blob `8e1958dbe6c87a6a13d3ee172b6a02f0c67d57ed`；1.3 `6825f22169` 的 `plan-cninfo-economic-date-evidence-2026-10-30.md`，blob `a4547f6008767cc92326b5915f7f05b5ce2c87be`。它们证明后续计划/草稿，不证明已实现或已合入。
- 机器映射校验要求：64 条记录恰好归入 21 个主包，无漏项、无重复归包；正文与附录使用相同 ID。
- 对冻结主分支的 GitHub blob 链接，按本地 `tracked-files` 与对应提交内容核路径存在、行号不越界；额外分支来源按前项单独核验。PR/issue/运行链接取自 `gh` 返回和对应源记录，不声称匿名网页可访问私有仓库。
- 对本次新增文件检查 UTF-8 无 BOM、NUL=0、相对链接、显式锚点及 `git diff --check`。最终结果见 [validation.json](validation.json)。仅文档/JSON 变更，无需重跑交易测试或真实数据任务。

审查指出的非阻塞问题已经逐项回填。签收边界维持主计划定义：本机/4090/75 的新运行回执、实际通知、训练、paper 与行情湖变更均未在此次规划中执行。
