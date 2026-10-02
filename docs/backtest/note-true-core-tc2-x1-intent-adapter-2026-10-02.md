# 真核大票 · C-New · TC2 窄 X1 意图适配器（2026-10-02）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-02（Asia/Shanghai / CST） |
| tip 基线 | `fee8f88d`（master · #303 TC1 MERGED） |
| Human GO | 前 H-TC1 选项 **A**：核外、事前、冻结 LIMIT 批次 + 具名消费者调用**现有** `run_minute_orders_research` |
| 方案 | `/workspace/handoffs/minute_engine_true_core_new_20261002/`；合同锚 [TC1](note-true-core-c-new-tc1-contract-2026-10-02.md) §5 X1 / §6 / §7 |
| 硬约束 | 研究回测 lean；**不** mint 新经济合同 / 新 `backend_id`；复用 v0 runner 不变；≠δ5≠R4；无写湖；无 4090；无 Compat；无 X2–X8 实装 |
| PR | draft **勿合** |

> **本 note ≠ 第二套成交默认表，≠ 绿 R 资格认证。** 适配器身份 ≠ 经济合同版本。入口默认 / 绿 R·S 继续只链 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。

## 1. 目的

把 TC1 §5 **X1 核外意图** 落到可调用码：调用方给出**显式、事前**的 LIMIT 意图规格，适配器在 Broker / MatchCore / Ledger **之外**冻结为现有 `SubmitOrder` / `CancelOrder` 批次，再经具名消费者组装 `RunInput` 并调用 tip 已有三 entry 之一（默认内存 `run_minute_orders_research`）。

| 本刀交付 | 明确不做 |
|---|---|
| 核外纯 builder → 冻结 LIMIT 命令批次 | 核内名单扫描 / 现金反馈缩量 / StrategyPort |
| 具名消费者 `run_x1_frozen_batch` | fills→意图倒造（X8）；反馈式意图流（新 contract） |
| 可选工件写仍走现有 S4 wrapper | 新 `backend_id` / 新合同字符串 / 新工件根名 |
| 合成夹具脚本 + 手算风格 e2e | stop / market / replace / GTC；第二价格模型；真湖 loader |
| 本 docs | 改 MatchCore / Fees / `simulate` / VolumeCap / 旧 L1 `_ENTRIES` / `views._FAMILIES` |

## 2. 身份澄清（适配器 ≠ 新经济合同）

| 层 | 本刀取值 | 说明 |
|---|---|---|
| **经济合同** | 仍 `research contract v0 (L2-S0)` | **不** mint 新 contract 字符串 |
| **backend_id / 工件根** | 仍 `minute_orders_research_v1` | 可选 S4 写仍落旧根策略；已存在根拒绝（S4 既有） |
| **适配器身份** | `minute_orders_intent_x1` | **仅**适配层名；观测/日志用；不是 backend_id |
| **价格模型** | 仍 `completed_bucket_close`（LIMIT-only） | H-TC3=否；无第二模型 |
| **比较权限** | 恒不授绿 R | `comparison_status` 语义仍由 S4/v0 声明 |

Additive X1（命令来源在核外）**不**改变撮合/账本语义，故按 TC1 H-TC2 / Claude N5 判据：**同 backend 旁路复用**，不换经济身份。若将来做反馈意图流 / 富订单 / 第二价格，必须新 contract + 新 backend_id（TC1 §4.1）。

## 3. 模块地图

```
backtest/research/minute_orders_intent_x1/
  __init__.py     # 公开导出
  builders.py     # LimitIntent / CancelIntent → SubmitOrder / CancelOrder；freeze_command_batch
  consumer.py     # assemble_run_input；run_x1_frozen_batch[|_with_artifacts]

scripts/research/run_x1_frozen_batch.py   # 合成 sketch A 薄脚本
tests/test_minute_orders_intent_x1.py     # unit + handcalc e2e + import 负面扫描
```

| 符号 | 职责 |
|---|---|
| `LimitIntent` / `CancelIntent` | 显式意图规格（timezone-aware、Decimal、LIMIT-only） |
| `freeze_command_batch` | **事前**冻结为 `tuple[SubmitOrder \| CancelOrder, ...]`；重复 `command_id` 失败 |
| `assemble_run_input` | 冻结批次 + 调用方显式行情/账户/费率 → `RunInput`（无经济默认） |
| `run_x1_frozen_batch` | freeze → assemble → `run_minute_orders_research`；返回 `FrozenBatchRun`（含 commands 身份） |
| `run_x1_frozen_batch_with_artifacts` | 同上，再调现有 `run_minute_orders_research_with_artifacts` |

**允许 import：** `minute_orders_backend.types`、`minute_orders_backend.runner`（及本包）。  
**禁止 import：** `broker` / `match` / `ledger` / `fees` / `clock` 及旧 CSV/`simulate` 路径（测试源码扫描护栏）。

## 4. 负面清单（diff 须空）

| 面 | 禁止 |
|---|---|
| `csv_minute_backtest.simulate` / `simulate_v7` | 任何改动 |
| MatchCore `match_candidates` / `compute_bucket_capacity` | 改现语义 |
| Fees | 偷接 production；改累计名义→增量费 |
| VolumeCap / 旧 L1 `_ENTRIES` / `views._FAMILIES` | 借本票改 |
| 核内 universe scan / 现金反馈 resize / StrategyPort / fills→intent | |
| 第二价格模型；stop/market/replace/GTC；真湖 loader | |
| 绿 R / NAV 混比；merge 本 draft | |
| 覆盖已存在工件根 | S4 已拒绝；本刀不绕过 |

## 5. 调用方法

### 5.1 库 API（内存）

```python
from decimal import Decimal, ROUND_HALF_UP
from backtest.research.minute_orders_intent_x1 import LimitIntent, run_x1_frozen_batch
from backtest.research.minute_orders_backend.types import Side, FeeModelParams
# ... 显式构造 buckets / calendar / instruments / marks（见 tests/test_minute_orders_intent_x1.py）

intents = (
    LimitIntent("O1", "X", Side.BUY, 300, Decimal("10.00"),
                available_at, submitted_at, effective_at, expires_at, sequence=1),
)
outcome = run_x1_frozen_batch(
    intents,
    start_at=..., end_at=..., buckets=..., calendar=..., instruments=...,
    initial_cash=Decimal("10000.00"),
    buy_fees=FeeModelParams(Decimal("0"), Decimal("0.00"), ROUND_HALF_UP),
    sell_fees=FeeModelParams(Decimal("0"), Decimal("0.00"), ROUND_HALF_UP),
    participation_rate=Decimal("0.20"),
)
# outcome.commands 在 run 前已冻结；outcome.result 为既有 RunResult
```

### 5.2 薄脚本

```bash
python scripts/research/run_x1_frozen_batch.py
# 打印 adapter_id / command_ids / 终态；exit 0 当 sketch A 手算终态匹配
```

### 5.3 测试

```bash
pytest tests/test_minute_orders_intent_x1.py tests/test_minute_orders_runner.py -q
```

验收要点：批次在 `run_minute_orders_research` 之前固定；sketch A 终态与 [S0 handcalc](note-l2-s0-handcalc-oracle-sketches-2026-09-29.md) / `test_minute_orders_runner.test_sketch_a_*` 一致；旧 runner 测试非回归。

## 6. ≠δ5≠R4 · 范围外

- **≠δ5 certified ≠R4**；无绿 R / NAV 混比授权。
- Out of scope：X2–X8 实装、P3、4090、湖写入、Compat 主路径、L1 `_ENTRIES` 注册。
- 具名 CLI/HELP 闭环见 [TC3](note-true-core-tc3-named-consumer-2026-10-02.md)（本 tip 后刀；draft 勿合）。
- 本 note 对应码已合 #304；后续消费者接线见 TC3。

## 7. 指针

- TC1 合同冻结：[note-true-core-c-new-tc1-contract-2026-10-02.md](note-true-core-c-new-tc1-contract-2026-10-02.md)
- L2-S0 合同 / 手算：[note-l2-s0-minute-orders-contract-2026-09-29.md](note-l2-s0-minute-orders-contract-2026-09-29.md) · [handcalc](note-l2-s0-handcalc-oracle-sketches-2026-09-29.md)
- S3 runner：[note-l2-s3-clock-broker-runner-2026-09-29.md](note-l2-s3-clock-broker-runner-2026-09-29.md)
- 统一上限 U1：[note-minute-engine-unify-ceiling-u1-2026-10-02.md](note-minute-engine-unify-ceiling-u1-2026-10-02.md)
- handoff（仓外）：`/workspace/handoffs/minute_engine_true_core_new_20261002/`
- TC3 具名消费者闭环：[note-true-core-tc3-named-consumer-2026-10-02.md](note-true-core-tc3-named-consumer-2026-10-02.md)

**≠δ5≠R4；适配器身份 only；复用 v0 runner；无 MatchCore/Fees/simulate 重写；#304 MERGED；消费者 CLI 见 TC3。**
