# 提示词：主笔侧对抗性子代理评审

对任意 agent 说：

**按 `docs/prompts/prompt-adversarial-subagent-review.md`，对 `<plan>` vN 的 §3 启动 3 路对抗性子代理审查，综合为 host 评审草案并列出须回填 plan 的勘误表**

## 原则

1. 证据优先于票数。
2. 主笔让步必须写进勘误表，禁止 silently 改口。
3. 对抗草案不计独立票。
4. 本阶段不改业务代码。
5. 不只信 docstring。

## 三路

| 角色 | 强制立场 | 必查 |
|------|----------|------|
| dissent-steelman | 反对主笔裁决 | 可测性黑洞、不可逆窗口、主笔「已覆盖」反例 |
| domain-safety | fail-closed | T+1、未来函数、复权混用、盈筹率单位、停牌/涨跌停 |
| pattern-evidence | 怀疑过度类比 | 是否该复用 `chip_indicator` / `StockDataReader`、包边界、文档漂移 |

每路输出：结论 / Findings（`file:line`）/ 对 §3 的独立裁决 / 未验证。
