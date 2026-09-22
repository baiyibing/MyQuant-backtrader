# Grok Bot 专用：多 Bot RACI 与工作流 SSOT

> **适用范围：仅 Grok Bot 协作链路**（bt / qlib / qmt / 4090bot 等）。  
> 人类本地 IDE、纯 Cursor 桌面会话、非 Grok Bot 调度的 Cloud Agent / 其他助手默认流程、仓库 CI runner 与普通运维 runbook **不适用本文**，不要拿本文去约束那些场景。  
> 生效：2026-09-22（用户当面逐条裁定）  
>
> **本文是唯一权威正文**：RACI、跨仓边界、handoff 角色落点、4090 派活、**以及** Bot VM CLI 流水线 / 模型钉，全部写在这一份里。  
> **OSkhQuant1.3 / MyQuant 只放指针到本文，不镜像、不另写第二份 SSOT。**  
> 物理机发起 → 主管接手的七步手续薄指针：[`docs/backtest/workflow-codex-handoff.md`](../backtest/workflow-codex-handoff.md)。  
> 1.3 安装细节仍看该仓 `linux-vm-grokbot-ci.md` / `linux-ci-02-agent-cli-setup.md`（步骤）；**Grok Bot 场景下的角色 / 模型 / 流水线以本文为准**。

## 0. 非适用声明（先读）

| 场景 | 是否适用本文 |
|---|---|
| 用户与 **Grok Bot**（含 bt / qlib / qmt / 4090bot）协作改仓、盯 PR、合入 | **适用** |
| 用户自己在 Cursor / VS Code / 终端里手写、手推 | **不适用** |
| 未经过 Grok Bot 调度的 Cloud Agent / 其他助手默认流程 | **不适用** |
| 仓库 CI runner、生产运维 runbook 本身 | **不适用**（仍看各运维文档） |

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
| **仓 Owner bot**（bt / qlib / qmt） | 协调、调度、host：拆任务、盯 PR/CI、合入、把活派给 VM CLI / 4090 | 用 Bot **自身额度**硬干大段实现；默认上 Cursor **云端 agent** |
| **Bot VM agent CLI** | 写代码、改文档、核验、开 PR | 绕过显式模型钉；平行开第二把同一刀 |
| **4090bot** | 唯一「bot 当 runner」：4090 湖 / Windows / headless Cursor（Grok 4.7） | 冒充仓业务 Owner；在对话里假装已读 4090 盘却不调度 |
| **物理机发起 agent** | 见 §5（任意注册物理机 + 任意 agent） | 越过 Owner 直接改对方仓业务 |

## 3. 优先执行面与默认流水线（Bot VM CLI）

**优先**：Grok Bot 虚拟机上的 agent CLI：

- Codex CLI（`codex`）
- Grok CLI（`grok`）
- Cursor CLI / `cursor-agent`
- Kimi CLI
- Claude CLI

**一般不用**：Cursor Cloud Agents（云端 agent）。已误开则取消，改道 VM CLI。

**额度**：重活烧 CLI / 物理机账户额度；不要把实现塞进 Grok Bot 对话模型的配额里。

```
Codex 做  →  Grok CLI 核  →  CI 绿  →  （再核，若需要）  →  合
```

| 步骤 | 谁 | 模型钉（调用时显式带上） |
|---|---|---|
| 实现 / 开 PR | Codex CLI | **`gpt-6-astra`**（`-m gpt-6-astra`） |
| 对抗核 / 发布核 | Grok CLI | **`grok-4.7`**（`-m grok-4.7`） |
| 合入 | 仓 Owner bot（或用户点名的合入方） | CI 全绿 + 核结论 GO / GO-WITH-NITS 后再合；**人裁** |

说明：

- 「绿了再核、再合」：CI 变绿后若首轮核早于绿点，或有实质 push，再跑一轮 Grok 核再合。
- 用户明确说「绿了就合」且核已过关时，协调 Bot 可直接合，不必再问一次。
- 禁止对同一把刀平行开第二个 Codex/Grok 实现 PR；跟刀在原 PR 上改。

## 4. 三仓配合顺序（上下游）

```
MyQuant  →  MyQuant-backtrader  →  OSkhQuant1.3
 (qlib)           (bt)                  (qmt)
```

- **现阶段**跨仓任务多半发生在 **MyQuant ↔ MyQuant-backtrader**（Owner：qlib / bt）。
- **handoff 目录是合同边界**：上游交付 pack / 说明；下游消费、在本仓实现、回执。
- 跨仓互不越界：
  - 上游 Owner **不**直接派下游仓的实现刀（不替下游调度 Codex 改对方仓）。
  - 下游 Owner **不**直接改上游业务仓代码（例如 bt 不直接改 MyQuant 业务）。

## 5. Grok Bot handoff 工作流（`codex-impl-handoff`）

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

## 6. 4090 派活

谁 **当前正在干的活** 需要 4090 物理机，谁就派 **4090bot**——**跨仓刀、本仓刀都一样**。

- 不绑「只有当前仓 Owner 才能派」。
- 仍只有 **4090bot** 作为物理机 runner；发起方是 §5 的物理机 agent 时，与「跑湖的 4090bot」角色分开。
- **并发**：多个 bot 同时需要 4090 时，按**任务接收顺序**排队（先接到的先跑）。
- 交给 4090bot 的活，一般：headless 调用 4090 上的 Cursor → 用 **Grok 4.7** 完成（湖路径 / Windows / 本机导出）→ 产物与回执回协调 Bot / 对口仓。
- 4090 上通常**没有**与 Bot VM 同款的 Codex CLI 作为默认实现面；不要假设「4090 也能 codex exec」除非现场已装并经用户确认。

## 7. 跨仓文档关系（一份正文 + 指针）

| 仓 | 做法 |
|---|---|
| **MyQuant-backtrader** | 保留本文为 **唯一权威正文** |
| **OSkhQuant1.3** | **只指针**到本文（原 `docs/operations/agent-cli-workflow-ssot.md` / PR #1078 应收成薄指针，不再维护第二份正文） |
| **MyQuant** | **只指针**到本文，不复制全文 |

指针目标（合入 master 后）：

`https://github.com/baiyibing/MyQuant-backtrader/blob/master/docs/operations/grok-bot-raci-workflow-ssot.md`

（PR 合入前可用分支：`docs/grok-bot-raci-workflow` / [#163](https://github.com/baiyibing/MyQuant-backtrader/pull/163)。）

## 8. 跨仓 handoff 回执（薄约定）

下游吃完上游 **handoff 目录**之后，必须回写一份固定样子的结果说明（可落在 handoff 内的 `RESULT.md` 或等价文件），让上游不用猜。先锁薄版，够对齐即可；真跑两三次后再加列。

必含五条：

1. **STATUS**：`OK` / `INPUT_BLOCKED` / `FAILED` / `NOT_RUN` 四选一  
2. **一句话摘要**  
3. **blocker**（非 `OK` 时必填：缺什么、在哪条路径）  
4. **关键数字**（有则写：覆盖率、turnover、净超额等；没有则写 `N/A`）  
5. **落盘路径**（RESULT / 日志相对 handoff 目录的路径）

（4090 排队、跨仓只指针且单正文：已锁，见上文。）

## 9. 检查清单（Grok Bot 派活 / 开刀前）

- [ ] 当前是否确属 Grok Bot 协作（否则不要套用本文）？
- [ ] 是否误开了 Cloud Agent？有则取消。
- [ ] 本刀 Owner 是否正确？
- [ ] 跨仓是否只经 handoff 目录，未直接改对方业务仓？
- [ ] 若走 `codex-impl-handoff`：发起方是否为物理机 agent，接手是否为仓主管？
- [ ] 实现是否走 `codex … -m gpt-6-astra`？核是否走 `grok … -m grok-4.7`？
- [ ] 是否只有一把 PR / 一个分支在干活？
- [ ] 需要 4090 时，是否由 **正在干这活的 bot** 派 4090bot，且按接收顺序排队？
- [ ] Codex 是否只开 PR；CI 绿 + 核过关后，才人裁合？
- [ ] 跨仓下游是否已按 §8 写回执（STATUS / 摘要 / blocker / 数字 / 路径）？

## 10. 修订

| 日期 | 变更 |
|---|---|
| 2026-09-22 | 初版：仓 Owner、无 Doer、三仓链、handoff 角色落点、物理机/agent 不限定、4090 派活「谁干谁派」、待定项 |
| 2026-09-22 | 4090 并发：按任务接收顺序排队 |
| 2026-09-22 | 跨仓只指针；并入 1.3 CLI SSOT 指针说明 |
| 2026-09-22 | **合并为唯一正文**：CLI 流水线/模型钉并入本文；1.3 / MQ 只指针、不另写 SSOT |
| 2026-09-22 | 跨仓 handoff 回执薄约定（STATUS / 摘要 / blocker / 数字 / 路径） |
