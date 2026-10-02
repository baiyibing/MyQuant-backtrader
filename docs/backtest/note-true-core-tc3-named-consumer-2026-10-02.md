# 真核大票 · C-New · TC3 首个具名消费者闭环（2026-10-02）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-02（Asia/Shanghai / CST） |
| tip 基线 | `1815bcf5`（master · #304 TC2 X1 MERGED） |
| Human GO | TC3 = notebook/runner/CLI 点名；HELP/preset 若需要；完成研究闭环；永 opt-in；不以 BOOKS 默认为验收 |
| 方案 | `/workspace/handoffs/minute_engine_true_core_new_20261002/`；合同锚 [TC1](note-true-core-c-new-tc1-contract-2026-10-02.md) §5–7；码刀基线 [TC2 X1](note-true-core-tc2-x1-intent-adapter-2026-10-02.md) |
| 硬约束 | **不** mint 新经济合同 / 新 `backend_id`；复用 v0 runner；≠δ5≠R4；无写湖；无 4090；无 Compat；无 X2–X8 / P3 / X6 真湖 |
| PR | draft **勿合** |

> **本 note ≠ 第二套成交默认表，≠ 绿 R 资格认证。** 适配器身份 ≠ 经济合同版本。入口默认 / 绿 R·S 继续只链 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。

## 1. 目的

在 tip 已合的 TC2 窄 X1 适配器之上，补齐 **具名 CLI / HELP 表面**，让 Human 能点名调用冻结 LIMIT 批次消费者，并走通「freeze → `run_x1_frozen_batch` → 手算终态」研究闭环。可选 S4 写仍落既有 `minute_orders_research_v1` 根（已存在根拒绝不变）。

| 本刀交付 | 明确不做 |
|---|---|
| `scripts/research/run_x1_frozen_batch.py` argparse + `--help` | 膨胀 `minute_orders_backend/cli.py`（保持 v0 CLI 身份干净） |
| 合成 fixture meta（attestation 级） | X6 真湖 loader；新 contract / backend_id |
| 合成 closed-loop e2e（内存 + 可选 S4） | X2–X5 / X7 `_FAMILIES` / X8 对照桥 / P3 |
| 本 docs + TC1/TC2/industry 轻指针 | 改 MatchCore / Fees / `simulate` / VolumeCap / 旧 L1 `_ENTRIES` |
| draft **勿合** | 成为 BOOKS 默认；绿 R / NAV 混比 |

## 2. 身份澄清（仍 = TC2）

| 层 | 本刀取值 | 说明 |
|---|---|---|
| **经济合同** | 仍 `research contract v0 (L2-S0)` | **不** mint 新 contract 字符串 |
| **backend_id / 工件根** | 仍 `minute_orders_research_v1` | 可选 S4 写仍落旧根；已存在根拒绝（S4 既有） |
| **适配器身份** | `minute_orders_intent_x1` | **仅**适配层名；观测/日志/HELP 用；不是 backend_id |
| **价格模型** | 仍 `completed_bucket_close`（LIMIT-only） | H-TC3=否；无第二模型 |
| **比较权限** | 恒不授绿 R | `comparison_status` 语义仍由 S4/v0 声明 |
| **默认化** | 永 opt-in（H-TC9） | **不以** BOOKS 默认为验收 |

## 3. 如何调用

### 3.1 HELP

```bash
python scripts/research/run_x1_frozen_batch.py --help
```

HELP 点名：`adapter_id=minute_orders_intent_x1`、合同仍 v0、backend 仍 `minute_orders_research_v1`、以及 bans（无新合同/无第二价格/无 MatchCore·Fees·simulate 改/无写湖/≠δ5≠R4/永 opt-in/非 BOOKS 默认）。

### 3.2 合成闭环（内存）

```bash
python scripts/research/run_x1_frozen_batch.py \
  --preset sketch_a \
  --fixture tests/fixtures/minute_orders_intent_x1/sketch_a_meta.json
# 打印 adapter_id / command_ids / 终态；exit 0 当 sketch A 手算终态匹配
```

fixture 是身份与终态 attestation；桶与价仍在脚本的合成 sketch A 中（meta-only，非湖 loader）。

### 3.3 可选 S4 写（既有根策略）

```bash
python scripts/research/run_x1_frozen_batch.py \
  --preset sketch_a \
  --write-artifacts \
  --parent /tmp/x1-tc3-out \
  --run-id unique-run-id \
  --evidence-level synthetic
# 第二次同 run_id → S4 FileExistsError（覆盖拒绝不变）
```

### 3.4 库 API（与 TC2 相同）

```python
from backtest.research.minute_orders_intent_x1 import (
    LimitIntent, freeze_command_batch, run_x1_frozen_batch,
)
# freeze → assemble → run_minute_orders_research；见 TC2 note / tests
```

### 3.5 测试

```bash
pytest tests/test_minute_orders_intent_x1.py \
       tests/test_minute_orders_intent_x1_named_consumer.py -q
```

验收：HELP 点名身份与 bans；CLI/API 闭环 sketch A 手算终态；可选 S4 唯一 `run_id` 成功且覆盖仍拒；旧 X1 单测非回归。

## 4. 模块地图（相对 TC2 增量）

```
scripts/research/run_x1_frozen_batch.py          # TC3：argparse CLI + HELP + preset/fixture
tests/fixtures/minute_orders_intent_x1/
  sketch_a_meta.json                            # attestation 级合成 meta（非湖）
tests/test_minute_orders_intent_x1_named_consumer.py
docs/backtest/note-true-core-tc3-named-consumer-2026-10-02.md
```

TC2 包 `backtest/research/minute_orders_intent_x1/{builders,consumer}.py` **不改经济语义**；本刀只接线具名调用面。

## 5. 负面清单（diff 须空）

| 面 | 禁止 |
|---|---|
| `csv_minute_backtest.simulate` / `simulate_v7` | 任何改动 |
| MatchCore `match_candidates` / `compute_bucket_capacity` | 改现语义 |
| Fees | 偷接 production；改累计名义→增量费 |
| VolumeCap / 旧 L1 `_ENTRIES` / `views._FAMILIES` | 借本票改 |
| 新 `backend_id` / 新合同字符串 / 新工件根名 | |
| 第二价格模型；stop/market/replace/GTC；真湖 loader | |
| 绿 R / NAV 混比；merge 本 draft；覆盖已存在工件根 | |
| 以 BOOKS 默认为验收；翻转 H-TC9 | |

## 6. ≠δ5≠R4 · 范围外

- **≠δ5 certified ≠R4**；无绿 R / NAV 混比授权。
- Out of scope：X2–X5、X6 真湖 loader、X7 进 `_FAMILIES`、X8 对照桥、P3、4090、湖写入、Compat 主路径、BOOKS 默认。
- 本 draft **勿合**，等 Human「合」。

## 7. 指针

- TC1 合同冻结：[note-true-core-c-new-tc1-contract-2026-10-02.md](note-true-core-c-new-tc1-contract-2026-10-02.md)
- TC2 窄 X1 适配器：[note-true-core-tc2-x1-intent-adapter-2026-10-02.md](note-true-core-tc2-x1-intent-adapter-2026-10-02.md)
- L2-S0 合同 / 手算：[note-l2-s0-minute-orders-contract-2026-09-29.md](note-l2-s0-minute-orders-contract-2026-09-29.md) · [handcalc](note-l2-s0-handcalc-oracle-sketches-2026-09-29.md)
- S4 工件隔离：[note-l2-s4-artifacts-isolation-2026-09-29.md](note-l2-s4-artifacts-isolation-2026-09-29.md)
- 行业索引：[industry-state-acceptance-index-2026-09-28.md](industry-state-acceptance-index-2026-09-28.md) §7
- handoff（仓外）：`/workspace/handoffs/minute_engine_true_core_new_20261002/`

**≠δ5≠R4；具名消费者闭环 on tip X1；无新 contract/backend_id；无 MatchCore/Fees/simulate 重写；draft 勿合。**
