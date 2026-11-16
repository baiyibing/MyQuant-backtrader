# 多agent评审消费入口（BT）

共享运行时、模型与全局core/任务模板唯一归
[Gitea-only ops](../operations/grok-bot-raci-workflow-ssot.md#runtime)，权威正文路径为该 checkout 的 `docs/multi-ai/shared-runtime-20261109.md`。
本仓只保留[领域profile](../../config/ops/bt-review.json)与薄入口，不复制通用框架；adversarial v1 lanes合同不变。

设置绝对 `MYQUANT_OPS_ROOT` 或传 `--ops-root`，指向从 Gitea 同步的当前 checkout；GitHub ops 副本已删除。新review需要API-v1的v2能力标记；缺依赖/旧能力明确失败，不回退本地源码。

```text
<configured-python> scripts/run/run_multi_ai_review.py --ops-root <absolute-ops-checkout> --plan docs/<plan>.md --author codex --host codex --round-number 1
<configured-python> scripts/run/run_multi_ai_review.py --ops-root <absolute-ops-checkout> --plan docs/<plan>.md --author codex --host codex --round-number 2 --task-type implementation
```

本仓注入root/profile，完整参数及缩写均不能覆盖。正式review显式声明作者；host只综合。奇classic偶mixed，当前模型只读ops PRESETS。
`--prompt-file`仅换task正文，core始终保留；同轮独立封稿，host回源裁决，不靠多数票。
状态0/2/3/4/130分别表示有效完整/配置错/有效需修/未完整或漂移/中断；dry-run离线且received=0，不算签收。
原生失败、报告和decision分列。模型家族未知不凭CLI品牌猜；quota/timeout缺席不自动换模型。

BT评审核向量化CSV、T+1、分钟成交、费用、资金/持仓与本仓策略书；数据/因子已迁边界仍按AGENTS及领域SSOT。
历史 GitHub ops #240 记录方案、人GO及原票，#244 记录实现；原编号和材料从 [ops 迁移归档](../operations/grok-bot-raci-workflow-ssot.md#archive) 查阅，不作为当前 Gitea PR 编号。
