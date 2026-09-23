# 研究工程沟通与复现词典

> **用途**：本文是人机沟通与研究复现词典，面向 Bai Yibing 与 bt / qlib / qmt / 4090bot，统一术语与复现证据。
> **边界**：本文**不替代** [grok-bot-raci-workflow-ssot.md](grok-bot-raci-workflow-ssot.md)，不复制 RACI 正文；不改 fill / 策略业务口径。
> **来源与日期**：合并 2026-09-23 handoff 的沟通词典与复现草稿；当前主线快照见 §6。

沟通时尽量沿用下表中的词；正式跑数按 §7–§12 留齐复现证据。

## 1. 一张图（业务，不是 bot）

```text
日线分数 / 名单          组合规则                 冻包                成交回放              实盘
(scores / stock_pool) → (TopK·Dropout 意图) → (frozen pack) → (BT joint_return_replay) → (1.3 执行)
     ↑ MyQuant / qlib          ↑ rule_intents         ↑ seal/hash           ↑ M-REF / M-LAG         ↑ 同合同 live 源
```

业内常叫：**Alpha → Portfolio construction → Research artifact → Execution sim → Live OMS**。

---

## 2. 业内名 ↔ 我们叫什么

| 业内常说 | 我们口头 / 文档 | 落在哪 | 一句话 |
|---|---|---|---|
| Alpha / 预测分 | **分数 / scores / control 分** | MyQuant 产出 JSON；可来自 qlib 日线 pred | 每天每只股票一个数，用来排序 |
| Universe / 名单 | **stock_pool / 池 CSV** | BT `stock_pool/` 或 exports | 谁允许买；as-of = 买入日 T |
| Portfolio rule / TopK Dropout | **rule_intents / TopK·Dropout** | `my_scripts/joint_return_rule_intents.py` | 按分决定买谁卖谁；**不是**模型直接吐 sell |
| Order / Intent | **意图 / intent** | 冻包里的 intents | 一笔计划买卖（含时钟、数量、身份 hash） |
| Research freeze / sealed run | **冻包 / frozen pack** | MQ runs + BT `--bars` + intents | 固定输入，可复现；改价不重 seal 会挂 |
| Execution assumption | **成交模式 fill-mode** | `M-REF` / `M-LAG` | 同一意图，两种「怎么成交」的假设 |
| Ideal fill @ ref | **M-REF** | joint_return_replay | 用参考时刻真实 mark；偏纸面 |
| Lagged / next-bar fill | **M-LAG** | joint_return_replay | 用意图生效后的分钟 open；偏可执行 |
| Backtest engine | **BT 回放 / joint_return_replay** | MyQuant-backtrader research | **只回放**冻包，不重新算分 |
| Live OMS | **1.3 / 实盘执行** | OSkhQuant1.3 | 吃同合同意图；不重放历史冻包 |
| Bar data store | **bars**（json / 拟 qlib_bin·Parquet·Arrow） | `--bars` 显式路径 | 只有 I/O；不改谁买谁卖 |
| Contract gate | **合同门**（INPUT_BLOCKED / CONTRACT_MISMATCH） | freeze / replay 校验 | 缺证据或 hash 对不上就停，不瞎补 |

### 两个容易混的「Mode B」

| 名字 | 其实是什么 | 别当成 |
|---|---|---|
| **joint-return Mode B** | 同一冻包上 **M-REF vs M-LAG** 成交对照 | 不是另一套组合臂 |
| **统一卖出 Mode B（分钟网格）** | csv 分钟引擎上的规则触价卖出网格 | 不是 joint-return 信号冻包 |

口头默认：说「Mode B」若在谈 joint-return / 614 / M-REF，指**成交对照**；谈策略书止损网格时再标明「分钟 Mode B」。

---

## 3. 冻包合同：我们交流时会用的词

| 词 | 含义 | 你听到时可以问我 |
|---|---|---|
| **冻包** | 一组密封输入：意图 + metadata + bars（+ marks） | 包路径？哪次 run？ |
| **seal / content_sha256** | 内容指纹；改了必须重算 | 是改业务还是只改 I/O？ |
| **CONTRACT_MISMATCH** | 指纹或字段和合同不一致 | 谁改了未重 seal？ |
| **INPUT_BLOCKED** | 缺必需证据，故意不跑 | 缺的是 marks / bars / 臂？ |
| **reference_marks** | M-REF 用的真实湖价证据（按 intent_id） | 覆盖全了吗？是不是 1.0 占位？ |
| **reference_price** | 意图上的身份/数量锚，**不等于**成交价 | 别把它当市价 |
| **CLOCK_PATCH** | 只改意图时钟的研究补丁包（如 614） | 是全量重导出还是补丁？ |
| **control_only** | 只用 control 分、单臂 P-BASE 的瘦路径 | 是不是还没上 full anti/P-REF？ |
| **P-BASE** | 基准组合臂 | 其它臂（P-CHASE/weak）是否仍挡？ |
| **RECEIPT** | 一次跑数回执（路径、fills、NAV、flags） | 出数目录？是否覆盖旧 out？ |
| **显式 `--bars`** | 回放必须指出价源文件；不偷偷读湖 | bars 路径？格式？ |
| **bit-compare** | 新格式读出与 JSON 逻辑一致才切默认 | 绿了吗？谁裁切默认？ |

### 冻包最小心智模型

```text
意图谁买卖、何时可成交  ← 规则 + 分数（业务）
bars 怎么存怎么读      ← I/O（加速，不改谁买卖）
marks 给 M-REF 什么价  ← 证据（假 1.0 会挡）
hash/seal              ← 防偷改
```

---

## 4. 机器人流程：我们交流时会用的词

权威流程正文见 [Grok Bot RACI 与工作流 SSOT](grok-bot-raci-workflow-ssot.md)（BT 仓）。这里只留**聊天用短词**，适用范围、角色权限与流程细节均以该 SSOT 为准。

| 词 | 谁 | 你听到时表示 |
|---|---|---|
| **Owner** | bt=BT仓，qlib=MyQuant，qmt=1.3 | 这个仓谁拍板、谁派 Codex |
| **Codex** | Bot VM 实现 CLI（默认 gpt-6-astra，headless） | 在写代码 / 开 PR，**不合入** |
| **Grok 核** | Grok CLI 4.7 缺陷优先评审 | 出 GO / NO-GO / nits |
| **人裁合** | 你 | CI 绿 + 核过之后，你说合才合 |
| **handoff 目录** | `/workspace/handoffs/...` 或仓内 docs handoff | **跨仓合同**；路径=约定，不互改对方仓 |
| **4090bot** | 物理机 runner | 在 4090 跑湖/导出/长回放；不当业务 Owner |
| **刀 / knife** | 一次有边界的改动 | 目标、非目标、DoD；禁止平行第二刀 |
| **TRACK** | 并行研究线（如 bars I/O vs Track B 向量化） | 别混进同一 PR |
| **绿了就合** | 你的站令 | CI 绿且核过 → 我合；否则停 |

### 标准一句话进度（我会尽量按这个汇报）

```text
【仓】BT/MQ/1.3  【刀】一句话目标
【状态】起草合同 / Codex 开 PR / CI / Grok 核 / 等人裁 / 4090 跑数 / 出 RECEIPT
【路径】冻包或 PR 链接
【你需要做的】无 / 裁合 / 裁格式 / 裁是否重跑
```

---

## 5. 信号卖 vs 规则卖（再钉一句）

| | 信号卖（joint-return） | 规则卖（策略书 / 分钟触价） |
|---|---|---|
| 谁决定卖 | 分数 + TopK/Dropout **规则意图** | 止损止盈等代码规则 |
| 何时决定 | 偏日终 → 下一交易时段可执行 | 盘中分钟触价 |
| 是否必须 qlib ML | **否**；分数可来自 pred，也可 control | 通常不需要 pred |
| 实盘复用 | 同意图合同 + live 产分/产意图 | 同策略代码 |

---

## 6. 当前主线备注（2026-09-23）

以下为 2026-09-23 权威交接草稿记录的状态快照；后续状态以对应 RECEIPT / PR 为准。

| 线 | 状态 | 人话 |
|---|---|---|
| Mode B 614 M-REF/M-LAG | 已出数；M-REF 稀疏因现金/1.0 数量 | 成交对照有 RECEIPT |
| bars 列式 I/O | 三格式候选；**写+读**对比测进行中 | 加速读盘，不改买卖 |
| #172 阶段计时 | 已合；4090 正式 profile 待跑 | 看时间花在哪 |
| 本词典文档 | 整理入 BT docs，随本次 PR 待人裁合 | 统一沟通与复现用词 |

---

## 7. 一条研究的「最小复现包」

目标：换一天、换一个人，也能从 RECEIPT / handoff 把同一次研究重跑出来（或证明跑不了）。每次正式跑数，至少留齐：

| 件 | 必须有 | 例子 |
|---|---|---|
| **意图冻包路径** | 是 | `.../portfolio/joint-return-control-only-50-5-narrow-clock-patch-614` |
| **bars 路径 + 内容 hash** | 是 | `..._with_marks.json` + `bars_content_sha256` |
| **BT tip / PR** | 是 | commit 或 PR #171 / #172 |
| **命令行 flags** | 是 | `--arm P-BASE --fill-mode all` |
| **out 目录** | 是 | 且写明「勿覆盖」规则 |
| **RECEIPT.md** | 是 | fills / NAV / STATUS / 时钟 |
| **handoff 目录** | 建议 | `/workspace/handoffs/<topic>_YYYYMMDD/` |

缺任一必需项 → 状态写 **不可复现**，先补证据再谈结论。

---

## 8. 标准复现步骤（joint-return Mode B）

1. **读 RECEIPT**，抄齐 pack / bars / tip / flags / out。
2. **核对 tip**：BT 仓 checkout 到 RECEIPT 写的 commit（或含该 PR 的 master）。
3. **核对 bars hash**：`sha256` 与 RECEIPT 一致；含 marks 的包不要拿错无 marks 的 twin。
4. **出目录**：新建目录，**禁止**覆盖历史 modeb out。
5. **重跑同一 flags**（研究加速可先 `--fill-mode M-LAG` 单臂，但正式对照要用 RECEIPT 同款）。
6. **对比**：fills、net_return、turnover；若只改 I/O，还要做 JSON vs 新格式 **bit-compare**。
7. **写新 RECEIPT**：写明「复现自 \<旧 RECEIPT\>」，差一笔也要写原因。

---

## 9. 改代码类研究（刀）怎么复现

1. handoff 里的 **目标 / 非目标 / DoD**。
2. PR + Grok 评语文件。
3. CI 绿记录。
4. 人裁合 commit。
5. 若影响跑数：附「合入后必须重跑」清单（哪条 RECEIPT 作废）。

RACI 细节不重复：见 [Grok Bot RACI 与工作流 SSOT](grok-bot-raci-workflow-ssot.md)。

---

## 10. 跨仓复现（MQ → BT → 1.3）

| 步 | 仓 | Owner | 产物 |
|---|---|---|---|
| 产分 / 规则意图 / 冻包 | MyQuant | qlib | scores, plans, intents, metadata |
| 回放 / 研究工具 | MyQuant-backtrader | bt | RECEIPT, fills, NAV |
| 实盘执行（同合同） | OSkhQuant1.3 | qmt | live 消费意图（不重放历史包） |

**边界：** 上游改合同要在 handoff 写清；下游不得改上游业务仓「顺便修」。

---

## 11. 不可复现时的说法（统一）

- **INPUT_BLOCKED**：缺输入证据（合法停）。
- **CONTRACT_MISMATCH**：输入被改过未重 seal。
- **环境缺口**：4090 离线 / 湖路径丢 / Python 环境丢 → 写清缺什么，不编数。
- **口径漂移**：Mode A/B 混读、M-REF 稀疏当「更优策略」→ 在 RECEIPT 标 **不可比**。

---

## 12. 研究复现检查清单（复制用）

```text
[ ] RECEIPT 路径
[ ] pack / bars / sha256
[ ] BT tip 或 PR
[ ] flags 全文
[ ] out 新目录（未覆盖）
[ ] 关键与基线差（若有）
[ ] 是否改了 fill（默认否）
[ ] 是否需要人裁（合入 / 切默认格式 / 重跑资金）
```
