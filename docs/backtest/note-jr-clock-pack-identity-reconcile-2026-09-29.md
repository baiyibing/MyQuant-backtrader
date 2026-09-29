# JR-clock pack 身份对账与下一交接门（2026-09-29）

基线：BT `b726e0480b2f4b6a068a7d11975dac91372d6f57`。授权：[Human E GO][go]（2026-09-29，docs/evidence-only）；任务依据：[ORDER_EVAL §8][order]。本轮只读核对仓内文档、提交记录及本地交接材料；没有连接 4090、运行 B/C/D/E/F、重生成 pack 或读取/导出湖数据。`production_C=frozen`。

## 1. 判定及证据层级

本次对账唯一可识别的合同级全量重生成包是 **`narrow_clock_full_20260924`**。归档判定：**已完成、无需恢复**；本轮证据限定：**文档完成；宿主证据本轮未复核**。依据是 [JR 交接终版页首及 §6b][handoff]，以及本地已核的收官提交 [`46ee416`（#201）][close]：B–G 收官，`NOT_READY_FOR_MODE_B` 已解除。既有 [研究入口 §5.1/§5.6][entry]、[AGENTS 的 JR 指针][agents] 与此一致。

这份判定保留归档完成态，不把文档转述升级为本轮完整 pack 验真。**本轮未识别出新的 stalled pack**；没有可派发的恢复任务。成本笔记的早期进度、历史失败和 G5 分配政策问题均不能将该包重新降为 `NOT_READY_FOR_MODE_B`（见 §4）。

## 2. 唯一归档包的身份账

下表中的宿主路径均为来源文档所记定位，不是本轮已访问的文件系统，也不是可直接执行的命令。

| 字段 | 当前可识别值 | 来源 / 本轮核验范围 |
|---|---|---|
| pack 名称 | `narrow_clock_full_20260924` | [交接页首、§2][handoff]；[成本笔记 §6][cost] |
| MQ 运行根 | `D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95` | [交接 §3][handoff] |
| pack 生成根 | 上述运行根下 `handoff_bt_20260922\narrow_clock_full_20260924\` | [成本笔记 §6][cost]；这里只定位生成根，不猜收窄后 portfolio 的完整目录名 |
| C 阶段 run_id | `joint-return-control-only-50-5-narrow-clock` | [交接 §2 C][handoff] 所登记；收窄产物及 E/F 的完整 run_id / out 路径未在已取得材料中确认 |
| 合同前缀 | `c6b85b9b…` | [交接终版][handoff]、[收官提交][close]；本包原 manifest 未取得，完整合同值未核验 |
| pack 登记的 code_shas | MQ `b072cc3` / BT `2f79375` | 同上；不以本轮 BT tip 替换历史登记，不推断 MQ 完整 SHA |
| scores 权威输入 | 运行根下 `inputs\scores_carryforward.json`；`content_sha256` 前缀 `11903c5b…` | [交接 §3、§6][handoff]：成功线的 `rules\rule-manifest.json` 与最终 `snapshot.json` 的 `inputs.scores.uri` 均自登记 carryforward。原件本轮未取得 |
| initial_state / metadata | `inputs\initial_state.json`（cash `1e8`）；metadata 模板 `inputs\metadata.json`，freeze 使用富字段 `inputs\freeze_metadata.json` 叠加本包注册 | [交接 §3、§6b][handoff]；[成本笔记 §7][cost]。具体新文件内容及 hashes 未复核 |
| 执行日历来源 | 运行根下 `handoff_bt_20260922\narrow_clock_20260922\execution-calendar.json`；文档窗口 `2025-01-02` → `2026-01-05`，含末日下一 session | [交接 §3][handoff]。日历来源目录名不等于本次 pack 身份；具体 execution/valuation windows 仍须在 D 逐项验收 |
| B 时钟记录 | 243 × 09:30/15:00，0 × 同日 15:03，尾 session `2026-01-05` | [成本笔记 §2][cost]；没有本轮重新计算的日期集合 |
| C 约束 / 收窄 | 全量 2470 intents；剔除 9 no_file + 150 over_window 后 614 证券 / 1891 intents；constraints 10810 对账 | [交接 §2 C、§3][handoff]；`NARROW.md`、剔除名单及产物未在本轮取得 |
| 原始回执 / 日志定位 | 生成根下 `RECEIPT_CLOCK_REGEN_FULL.md`、`CLOCK_PREP.md`、`_clock_full_pipeline_20260924_cf.log` | [交接页首][handoff]、[成本笔记 §6][cost]；本地指定交接目录中未找到这些原件 |

`merged\scores.json`（历史前缀 `37e87390…`）是 scores-merge 步产物，不能替代成功线的 carryforward。旧模板对 merged 的引用以及旧 freeze metadata 用法已被 [交接 §6][handoff] / [成本笔记 §7][cost] 勘误。未来验收需核原件的 URI 与 content/raw-byte hashes，不能凭模板、前缀或目录名补齐。

完整合同、sessions/calendar、scores、initial_state、plans、snapshot、intents、各 manifest、bars/marks/seal 的 hashes，以及 MQ/BT 完整 `code_shas` 的 pack 内登记，本轮均 **未取得原件并复核**。本地 [9/23 CLOCK_PATCH 交接 §5][old-local] 虽载有完整合同值 `c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7`，该记录属于旧研究包；相同合同前缀不足以替新包签认完整输入/manifest 链。不得将旧 hashes、intent_id 或 marks 移填到本表。

## 3. 阶段与本地回执核查

| 阶段 | 归档所记结果 | 本轮可签认范围 |
|---|---|---|
| B | 时钟准备完成，约 3 min | [交接 §6b][handoff]、[成本笔记 §2][cost] 的完成记录；未验 `CLOCK_PREP.md` 原件 |
| C | rule 6h21m；freeze 完成；portfolio 5h58m；全量及收窄链完成 | [交接 §6b][handoff]、[成本笔记页首勘误][cost]。freeze 耗时两处写作快照约 4 / 2 min，不据此制造第二次停点 |
| D | 终版统一记 B–G 收官；原门槛为覆盖 `missing=0` | 本轮没有取得独立覆盖明细，不声称已重新证明 bars/marks `missing=0` |
| E | P-BASE M-LAG **3631 fills / net +59.1%** | [交接终版][handoff] / [收官提交][close] 转述，未重跑 |
| F | Mode B 真湖 **M-REF 21 / M-LAG 3631**，全 `BT_RESEARCH_REPLAY_PASS` | 同上；未重验真实行情来源、marks 或输出 |
| G | `NOT_READY_FOR_MODE_B` 解除，研究入口与 AGENTS 已同步 | 本轮只读核对终版和提交，保持完成态 |

本地检索范围为 `/workspace/handoffs/joint_return_*`：**23 个目录、568 个普通文件**（本轮盘点；包括隐藏/忽略文件），查文件名及 pack 名称/回执名称/权威 scores 等内容定位。未找到本包完整回执、`CLOCK_PREP.md`、原 manifest 或冻结输入。本次实际读到的相关证据分列如下：

| 本地材料 | 它支持的身份 | 不能替代什么 |
|---|---|---|
| [joint_return_20260922/HANDOFF_TO_BT_MODE_B.md][old-local] | `narrow_clock_20260922` 下 CLOCK_PATCH-614；P-BASE 4475，Mode B 34 / 4475；另有 cash=1e9 研究 fork | 不是 `narrow_clock_full_20260924` 的 B–G 宿主回执 |
| [joint_return_replay_panel_phase_20260924/RECEIPT_REPLAY_PANEL_PHASE.md][panel-local] | tip `dbd6c22` 的 panel 性能验证，63903 fills，cash=1e9 对照 | 不是合同级时钟全量重生成验收 |
| 其余 `joint_return_*` 检索命中 | 旧 clock/hash 讨论、性能任务及代码验收材料 | 未定位到另一份具名新 pack 的最后成功阶段或失败回执 |

“本地未找到”只限定本轮可用材料，不声称 4090 上文件不存在。没有以旧性能回执或归档 PASS 充作本轮宿主验真。

## 4. stalled 主张单独立账

| 容易误读的材料 | 对账解释 |
|---|---|
| [成本笔记 §6][cost] 的“C3 运行中”、PID 36144 | 明示写作时点为 **2026-09-25 07:29**；页首晚间勘误及交接终版已记录完成。历史 PID 不是当前进程证据 |
| B/C 双执行器撞车、freeze 两次失败、磁盘空间失败 | [交接 §6、§6b][handoff] 已记纠正/重跑并收官，是同一归档包的过程史；不是本轮恢复理由 |
| CLOCK_PATCH 4475 与 full-regen 3631 不一致 | [交接 §6b][handoff]、[G5 §1–§5][g5] 记为跨 hash 血统的同分钟 `intent_id` 分配差异；原页首“见 §7”实际应定位 §6b。该问题不证明 clock pack 未完成 |
| 未点名的“新 stalled pack” | **本轮未识别**。其 pack/run_id、最后成功阶段、失败原因、唯一执行者和新输出根均未确认，不能代填或发车 |

若后续确有新包，交接须先给出与归档包不同的 pack/run_id/路径及完整 hashes、最后一份成功回执和失败证据，点名唯一执行者与不会覆盖历史的新输出目录，并核输入、磁盘空间、现存进程与目录时间戳。只从第一个未验收步骤申请单独 GO；不得为“保险”全量重生成。归档包不因新包失败而回退状态。

## 5. 冻结后续交接门：仅列门槛，不派工

顺序固定为 **`4090 B → 4090 C → bt D coverage → 4090 E P-BASE → 4090 F`**。以下字母是 JR 工序，与 ORDER_EVAL 的 tracks B/C/D/E 无关。**每一步均需另行、具名 Human GO；本表及本次 E GO 不授权任何宿主任务。**

| 门 | 责任方 / 动作 | 进入条件与验收停点 | 本轮授权 |
|---|---|---|---|
| B | 4090：时钟准备 | 仅在具名新包确需 B 且获得 B GO 时；新目录存在即停；唯一执行器；核输入/磁盘/进程；无同日 15:03→16:00 空窗、每个尾日信号有下一 session、日期集合可对账 | 未授权；归档包已完成，不重做 |
| C | 4090：rule → freeze → portfolio | B 回执及独立 C GO；成功线 carryforward、完整 SHA/hash/URI 登记相容；`PORTFOLIO_CONSTRAINTS_PASS`、收窄依据与 counts 对账；B/C 不开第二执行器 | 未授权；归档包已完成，不重做 |
| D | bt：新 execution/valuation window 与 bars/marks 覆盖验收 | 独立 D GO；已验 B/C 身份；核证券集合、日历、尾部下一 session、全部执行/估值时点、bar/mark 身份与 seals；**bars missing=0 且 marks missing=0** 才接收 | 未授权；本轮未检查覆盖 |
| E | 4090：P-BASE M-LAG | D 接收回执及独立 E GO；使用另行登记的新 out；非零 `orders_with_fills`，并按本包身份对账。**若仍 0 fills，停回 qlib 查时钟，不交 F** | 未授权 |
| F | 4090：Mode B M-REF / M-LAG | E 通过及独立 F GO；真实 marks 证据链齐全；模式、现金与新输出根在 GO 中明确，不能自动继承旧 cash=1e9 fork | 未授权 |

2026-09-29 后续独立 Human D GO：[本次覆盖核验记录](note-jr-clock-d-coverage-reject-2026-09-29.md)为 **未完成 / REJECT pending host**（宿主已测 bars/marks missing 均为 0；完整执行窗相容性与 seal 复核证明待补）。该记录不改变历史 B–G 完成态，不授权 E/F。

**归档包 B/C 已完成，当前没有待恢复的操作。** 若后来另获具名 GO，要复用该包开展一次新的研究接收，下一 *operational* gate 是 **bt D**：在该 GO 下核对身份、window、bars、marks，只有 `missing=0` 才准接收并申请 E；不能回到 B/C 重跑。未来新包若已有完整 B/C 回执，同样直接申请 D，无需再造一轮时钟。

D 只能在窗口与身份相容时复用旧 bars；`reference_marks` 按 intent_id 挂证，相同证券数或 marks 数并不证明可复用。需改变身份/映射时另定合法新工件和校验范围，遵守现有 seal 合同，不修改旧工件。[交接 §2 D、§6b][handoff] 的真实源定位仅作来源线索：缺口只能在后续明确授权下从已指定真实源合法导出；缺配置/文件/证明即停，不探盘、不补造 bars/marks。**本轮不导出、不重映射、不重算 seal。**

E/F 通过后才可回填 G；G 的文档回写范围仍须在后续 GO 中明确。历史 G 已完成，本文不重复解除状态，也不把归档值当成下一次运行的 PASS。

## 6. 范围锁与交付

- 不覆盖旧 pack、outs、回执或 seal；不原地编辑 clock；不运行 B/C/E/F，也不借 D 进行湖导出。
- 不修改 `joint_return_replay.py`、fill/fee/clock/tie-break 或其他生产 `.py`。G5 候选政策仍需 **MQ/BT 联合 Human GO**，本轮不改政策、不以跨包成交差异调参。
- 不写 MQ 代码、不做性能优化/训练/新 arm；不改 L1/L2，不将 JR 归档结果转成 L2 NAV 比较授权。
- 仅新增本 note；既有 JR 交接、研究入口和 AGENTS 状态未变，故不追加状态指针。提交/推送/开 PR 属本次交付；**未经 Human「合」不合并**。

本轮验证仅为来源定位与文档对账、diff allowlist、Markdown 链接、UTF-8 无 BOM / NUL=0 及 `git diff --check`；不以代码测试或宿主运行补造证据。最终提交、PR 与检查结果写入 [E_RECEIPT.md][receipt]。

[go]: /workspace/handoffs/e_jr_clock_reconcile_20260929/HUMAN_GO.md
[order]: /workspace/handoffs/next_tracks_abcde_order_20260929/ORDER_EVAL.md
[receipt]: /workspace/handoffs/e_jr_clock_reconcile_20260929/E_RECEIPT.md
[handoff]: handoff-joint-return-clock-regen-2026-09-24.md
[cost]: note-joint-return-pack-regen-cost-2026-09-25.md
[entry]: research-backtest-entry.md
[agents]: ../../AGENTS.md
[g5]: g5-jr-semantic-tiebreak-2026-09-28.md
[close]: https://github.com/baiyibing/MyQuant-backtrader/commit/46ee4163a5b833df1f2b8193ae384852b69682e8
[old-local]: /workspace/handoffs/joint_return_20260922/HANDOFF_TO_BT_MODE_B.md
[panel-local]: /workspace/handoffs/joint_return_replay_panel_phase_20260924/RECEIPT_REPLAY_PANEL_PHASE.md
