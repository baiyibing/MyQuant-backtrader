# G5｜joint-return 同分钟语义 tie-break 联合合同提案

日期：2026-09-28。基线：BT `3e7b6d4d600e380126d6bd24d92dbafbb62b8067`。
状态：**Human sequential GO 仅授权 G5 窄合同提案 + 当前规则锁定测试；勿合。候选政策未裁，默认不翻。**

## 1 问题与证据边界

本刀只问：**语义及序列相同的 intents，仅非经济 provenance（hash lineage / intent_id）改变时，研究经济分配是否应保持稳定？**
依据为[基线审计](industry-gaps-bt-2026-09-28.md) **§G5** 及 [D30](handoff-joint-return-clock-regen-2026-09-24.md) **§6b**（旧页首误指 §7，正文实际为 §6b）。
D30 记录跨重生成 3631 vs 4475 fills、net 59.1% vs 59.3%，且旧包 × 新引擎仍为 4475；这是既有同分钟排序下的跨包分配差异，**不是旧 pack 在新 engine 上的回归**。此处仅转述归档，未重跑、未重验宿主产物，不外推所有窗口。

**不存在本提案已证实的“行业强制公平排序”。** 是否要求 provenance 不变性、何种经济优先级算公平，都 needs Human；稳定可复现不等于公平。

## 2 当前规则冻结（本 PR 不改）

[joint_return_replay.py](../../backtest/research/joint_return_replay.py) 中有不同层次：

| 层次 | 现行 key | 含义 |
|---|---|---|
| 输入 `sort_intents`（约 311 行） | `(arm_id, decision_at, side != "SELL", instrument, intent_id)` | 输入规范排序；不能据此推断同分钟资金按 instrument 分配 |
| `_Replay.run` 同时到达的 activation（约 1141 行） | `(intent.side != "SELL", intent.intent_id)` | SELL-first，再按 intent_id 字典序 |
| `_Replay.run` 同分钟 eligible fills（约 1160 行） | 同上 | SELL-first，再按 intent_id 字典序，逐单 attempt 消耗资源 |

现金是组合共享余额；该分钟 capacity 按 instrument 维护，同码订单共享该码容量，不是所有股票共用一个容量池。SELL-first 和后续 BUY 次序可影响资金可用性；input `sort_intents` 不覆盖这两处 key。相同 key 使用 Python 稳定排序；有效 pack 的 intent_id 唯一性另由现有校验负责。

## 3 两个 BUY 的手算反例

同一 arm、同一分钟，两条 BUY 输入序列始终为 A、B，各目标 200 股；价格都为 10，现金 3000，整手 100 股，手续费显式设 0，各码容量充足。时钟、价格、数量、方向与输入序列全部固定。

| 非经济身份示意 | A 的 intent_id | B 的 intent_id | 当前处理顺序 | A / B 成交股数 |
|---|---|---|---|---|
| 原血统 | `1` 重复 64 次 | `e` 重复 64 次 | A → B | 200 / 100 |
| 重生成血统 | `f` 重复 64 次 | `0` 重复 64 次 | B → A | 100 / 200 |

首单用 2000，次单剩 1000，只能买 100 股。总成交数量同为 300，却改变持仓组成；后续价格不同即可传播到收益路径。这里的 ID 是说明字典序翻转的占位值，**不是实际 hash 重生成、合法完整 pack 或 seal 取证**。生产身份必须遵守现有内容 hash 校验，不能手改 ID 绕过。

## 4 候选政策（选项而非默认）

以下均保留外层 SELL-first，讨论同侧同分钟的资源优先级；不改变时钟资格或触发规则。

| 选项 | 候选方式 | 代价 / 未决点（Human） |
|---|---|---|
| 保留现规则 | 同侧 `intent_id` 序 | 保留旧回放合同，接受跨血统分配差异；是否可接受需明确裁决 |
| 稳定语义键 | 同侧 `(instrument, original_target_quantity, side)`，数量按双方约定的数值口径 | 本例两种血统均为 A 200 / B 100；长期偏向代码较前者，数量升序也带偏好，不是公平认证 |
| 确定性轮转 | 在规范语义序列上按约定交易日/分钟锚点轮转 | 起点、周期、状态重置与候选集合变化都需合同化；不得以 provenance hash 作种子；本刀不实现 |

语义键并非完整订单经济身份：同码同量同侧但 lot、instance、有效时钟或约束不同仍可能竞争。MQ/BT 须共同界定经济等价投影及重复语义键处置；不能偷偷回落 intent_id 再宣称血统无关。若保留输入序列作最终次序，还必须证明该序列不由 hash 重排生成。本例只验证两个不同 instrument 的无碰撞场景。

## 5 联合 Human GO 与兼容边界

本 PR 是 **BT-side proposal + tests only**；MQ 可在后续共同裁决时镜像这一小型 fixture，本刀不修改 MQ，也不宣称已获 MQ 同意。任何 replay kernel 改动前必须取得 **MQ/BT 联合 Human GO**，至少明确：

1. 是否要求仅 provenance 改变时经济分配不变；对比以语义订单/持仓映射后的成交数量、现金、费用、持仓与 NAV 为准，不要求 ID 或产物字节相同。
2. 选择何种公平/优先级政策；确定经济字段、重复键处置、数量规范化，以及选择轮转时的锚点规则。
3. 新旧政策的显式识别和兼容办法，另立实施与合成验收范围。旧 pack/seal 合同及校验保留，不能用新政策静默解释旧证据；不得改旧 seal 来伪装回放一致。

**本 PR replay 内核完全不改**：allocation、SELL-first、intent_id sort、输入 sort_intents 都保持；无 helper 抽取、无新生产选项、无 pack 格式或 seal 变更。G6–G8 另刀；不重开 G2–G4、TopK P1–P4、hl/fen、δ*、Cerebro/PortAna；不运行 Mode B、lake 或 4090。

## 6 合成证据与验收范围

[test_joint_return_semantic_tiebreak.py](../../tests/test_joint_return_semantic_tiebreak.py) 用 AST 读取 `_Replay.run` 两处真实 lambda，逐一锁定与现行 key 的结构一致，再只执行该纯 key；不 import 重 replay，也不更改生产代码。覆盖 SELL-first / 同侧字典序、输入排列不影响唯一 ID 排序、instrument 不作为当前同分钟优先级，以及 §3 的两血统现金拆分。候选 key 仅存在于测试，演示本例在血统与输入排列变化下仍为 200 / 100。

运行：`"$OSKH_MERGE_PYTHON" -m pytest -q tests/test_joint_return_semantic_tiebreak.py`（解释器须显式配置）。2026-09-28 在本 worktree 使用显式 `/workspace/vanna312/bin/python`：**7 passed in ~0.2s**。这是当前 key 的源码锁定与简化分配模型证据，不是完整 replay、真实 hash/seal、手续费/容量组合或真湖收益验收；不据此宣布候选政策已投产或经济公平已证。
