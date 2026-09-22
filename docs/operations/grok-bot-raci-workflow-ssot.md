# Grok Bot 多 Bot RACI 与工作流 SSOT（本仓视角）

> **适用范围：仅 Grok Bot 协作链路**（bt / qlib / qmt / 4090bot 等）。  
> 人类本地 IDE、未经过 Grok Bot 调度的流程 **不适用**。  
> 生效：2026-09-22（用户当面逐条裁定）  
>
> **分工**：本文锁 **角色 / 仓 Owner / 跨仓边界 / handoff 工作流 / 4090 派活**。  
> CLI 默认流水线与模型钉见 OSkhQuant1.3  
> [`OSkhQuant1.3/docs/operations/agent-cli-workflow-ssot.md`](https://github.com/baiyibing/OSkhQuant1.3/blob/master/docs/operations/agent-cli-workflow-ssot.md)  
> （Codex `gpt-6-astra` → Grok CLI `grok-4.7` → CI 绿 → 合）。  
> 物理机发起 → 主管接手的七步手续见本仓  
> [`docs/backtest/workflow-codex-handoff.md`](../backtest/workflow-codex-handoff.md)。

## 1. 仓 Owner（主管 bot）

| 仓 | Owner bot |
|---|---|
| `baiyibing/OSkhQuant1.3` | **qmt** |
| `baiyibing/MyQuant` | **qlib** |
| `baiyibing/MyQuant-backtrader` | **bt**（本文所在仓） |

- **没有**独立 Doer bot。实现由该仓 Owner **亲自**在 Bot VM 上调度 Codex。
- Owner 职责：拆任务、写/收 handoff、调度 Codex 开 PR、调度 Grok 核、回写 plan、**人裁后合入**（Codex 只开 PR，不合）。
- 禁止对同一把刀平行开第二把实现刀；跟刀在原 PR 上改。

## 2. 执行面（谁干活）

| 角色 | 做 | 别做 |
|---|---|---|
| **仓 Owner bot**（bt / qlib / qmt） | 协调、调度、host；安排 Codex / Grok；合入决策侧执行 | 用 Bot 对话额度硬干大段实现；默认上 Cursor 云端 agent |
| **Bot VM agent CLI** | Codex 实现开 PR；Grok CLI 缺陷优先核 | 绕过模型钉；平行第二刀 |
| **4090bot** | 唯一「bot 当 runner」：4090 湖 / Windows / headless Cursor（Grok 4.7） | 冒充仓业务 Owner；在对话里假装已读 4090 盘却不调度 |
| **物理机发起 agent** | 见 §4（任意注册物理机 + 任意 agent） | 越过 Owner 直接改对方仓业务 |

Grok Bot 站规优先级：**Bot VM CLI > 云端 agent**；重活不烧 Bot 对话配额。细节与检查清单以 1.3 `agent-cli-workflow-ssot.md` 为准。

## 3. 三仓配合顺序（上下游）

```
MyQuant  →  MyQuant-backtrader  →  OSkhQuant1.3
 (qlib)           (bt)                  (qmt)
```

- **现阶段**跨仓任务多半发生在 **MyQuant ↔ MyQuant-backtrader**（Owner：qlib / bt）。
- **handoff 目录是合同边界**：上游交付 pack / 说明；下游消费、在本仓实现、回执。
- 跨仓互不越界：
  - 上游 Owner **不**直接派下游仓的实现刀（不替下游调度 Codex 改对方仓）。
  - 下游 Owner **不**直接改上游业务仓代码（例如 bt 不直接改 MyQuant 业务）。

## 4. Grok Bot handoff 工作流（`codex-impl-handoff`）

权威手续薄指针：[`workflow-codex-handoff.md`](../backtest/workflow-codex-handoff.md)（七步：plan → 多路评 → 人裁 GO → 交接文档 → Codex 无头实施 → 缺陷优先核 → 回写 plan）。

**角色落点（2026-09-22 锁定）**：

1. **物理机上的 agent 发起**：起草 plan、多路评、人裁 GO，并开到 PR。  
   - **物理机不限定 4090**：含 `newtest_4090`、笔记本 `LAPTOP-75JKCBED` 等已注册机器。  
   - **agent 不限定 Cursor**：任意 agent（含 zcode 等）均可发起。
2. **该仓主管 bot 接手**（本仓即 **bt**）。
3. **主管安排 Codex**（Bot VM，`gpt-6-astra`）按交接文档无头实现 / 推 PR。
4. **Grok 核**（`grok-4.7`，缺陷优先）。
5. **主管侧回写 plan**；**人裁合入**。

这是 Grok Bot 的一种 **handoff 工作流**，不是旁路。

## 5. 4090 派活

谁 **当前正在干的活** 需要 4090 物理机，谁就派 **4090bot**——**跨仓刀、本仓刀都一样**。

- 不绑「只有当前仓 Owner 才能派」。
- 仍只有 **4090bot** 作为物理机 runner；发起方是 §4 的物理机 agent 时，与「跑湖的 4090bot」角色分开。

## 6. 待定（尚未当面锁死）

| 项 | 状态 |
|---|---|
| 两 bot 同时需要 4090 时的排队 / 互斥 | **待定** |
| handoff 回执固定字段（STATUS / INPUT_BLOCKED / 数字栏等） | **待定** |
| 本文是否在 MyQuant / OSkhQuant1.3 各放一份镜像或仅指针 | **待定**（本仓已落；跨仓同步另裁） |

## 7. 检查清单（开跨仓或本仓刀前）

- [ ] 当前是否确属 Grok Bot 协作？
- [ ] 本刀 Owner 是否正确（本仓 → bt）？
- [ ] 跨仓是否只经 handoff 目录，未直接改对方业务仓？
- [ ] 若走 `codex-impl-handoff`：发起方是否为物理机 agent，接手是否为仓主管？
- [ ] 实现是否 Codex `gpt-6-astra`、核是否 Grok `grok-4.7`？
- [ ] 需要 4090 时，是否由 **正在干这活的 bot** 派 4090bot？
- [ ] Codex 是否只开 PR；合入是否等人裁？

## 8. 修订

| 日期 | 变更 |
|---|---|
| 2026-09-22 | 初版：仓 Owner、无 Doer、三仓链、handoff 角色落点、物理机/agent 不限定、4090 派活「谁干谁派」、待定项 |
