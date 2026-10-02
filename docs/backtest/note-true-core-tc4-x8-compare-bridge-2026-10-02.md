# 真核大票 · C-New · TC4 · X8 对照桥（2026-10-02）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-02（Asia/Shanghai / CST） |
| tip 基线 | `00ab1a24`（master · #305 TC3 MERGED） |
| Human GO | TC4 = 可选对照桥：仅**撮合前**意图快照 ↔ New/X1 冻结批次跑；红标签诊断 |
| 方案 | `/workspace/handoffs/minute_engine_true_core_new_20261002/`；合同锚 [TC1](note-true-core-c-new-tc1-contract-2026-10-02.md) §5 X8 / PLAN TC4；前序 [TC2](note-true-core-tc2-x1-intent-adapter-2026-10-02.md) · [TC3](note-true-core-tc3-named-consumer-2026-10-02.md) |
| 硬约束 | **不** mint 新经济合同 / 新 `backend_id`（runner 复用 v0/X1）；`comparison_id` ≠ backend_id；独立 comparison 根；`comparison_status` 恒 `no_ssot_compare_authorization`；**不**产成功 `summary.json`；禁止 fills→意图倒造；≠δ5≠R4；无写湖；无 4090；无 Compat；无 X2–X5 / X6 真湖 / X7 `_FAMILIES` |
| PR | **#306 MERGED** `79b3995c` |

> **本 note ≠ 第二套成交默认表，≠ 绿 R 资格认证，≠ fill-policy，≠ NAV 排行。** 对照桥身份 ≠ 经济合同版本。入口默认 / 绿 R·S 继续只链 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。

## 1. 目的

落实 TC1 §5 **X8 对照桥**：在存在**撮合前**订单意图快照时，与 tip 已合的 X1 冻结批次跑做红标签差异报告，诊断迁移成本。输出落在**独立 comparison 根**，永不伪装成 L2-S4 研究成功跑。

| 本刀交付 | 明确不做 |
|---|---|
| 摄取 pre-match intent snapshot JSON | fills / trades → 意图倒造 |
| 复用 `run_x1_frozen_batch` + 合成 sketch A 行情 | 新 contract / 新 backend_id / 新经济语义 |
| 独立根 `…/minute_orders_x8_compare/<run_id>/comparison_report.json` | 成功 `summary.json`；落 `minute_orders_research_v1` 成功根 |
| `comparison_status` 恒 `no_ssot_compare_authorization` | 进 fill-policy；NAV 榜；绿 R |
| 薄 CLI + HELP + 合成 e2e（含 fills 拒收） | 改 MatchCore / Fees / `simulate` / VolumeCap / 旧 L1 `_ENTRIES` / `views._FAMILIES` |
| 本 docs + TC1/TC3/industry 轻指针 | X2–X5 / X6 真湖 / X7 `_FAMILIES` / P3 / 4090 / BOOKS 默认 |
| 本码已合 #306 | 默改 `simulate`；byte-compat 门禁 |

## 2. 身份澄清

| 层 | 本刀取值 | 说明 |
|---|---|---|
| **经济合同** | 仍 `research contract v0 (L2-S0)` | **不** mint 新 contract 字符串 |
| **backend_id** | 仍 `minute_orders_research_v1`（runner 复用） | 对照桥**不**换经济身份 |
| **适配器** | 仍 `minute_orders_intent_x1` | 经 X1 freeze→run |
| **对照桥身份** | `comparison_id=minute_orders_x8_compare` | **仅**工具/报告身份；**不是** backend_id |
| **比较根** | `minute_orders_x8_compare/<run_id>/` | **独立**于 `minute_orders_research_v1` |
| **比较权限** | 恒 `no_ssot_compare_authorization` | 红标签；诊断 only |
| **完成标记** | 仅 `comparison_report.json` | **禁止**写成功 `summary.json` |
| **默认化** | 永 opt-in（H-TC9） | 永不 BOOKS 默认 |

## 3. 如何调用

### 3.1 HELP

```bash
python scripts/research/run_x8_compare_bridge.py --help
```

HELP 点名：`comparison_id`、合同/backend 仍 v0、`comparison_status` 恒值、以及 bans（仅撮合前快照 / 禁 fills→意图 / 禁成功 summary.json / 独立根 / 无新合同 / 无 MatchCore·Fees·simulate 改 / ≠δ5≠R4 / 永 opt-in）。

### 3.2 内存诊断

```bash
python scripts/research/run_x8_compare_bridge.py \
  --snapshot tests/fixtures/minute_orders_x8_compare/sketch_a_prematch_snapshot.json \
  --memory-only
```

### 3.3 写独立 comparison 根

```bash
python scripts/research/run_x8_compare_bridge.py \
  --snapshot tests/fixtures/minute_orders_x8_compare/sketch_a_prematch_snapshot.json \
  --preset sketch_a \
  --parent /tmp/x8-tc4-out \
  --run-id unique-run-id
# 产出: /tmp/x8-tc4-out/minute_orders_x8_compare/unique-run-id/comparison_report.json
# 同 run_id 再写 → FileExistsError；根下无 summary.json
```

### 3.4 库 API

```python
from backtest.research.minute_orders_x8_compare import (
    load_prematch_intent_snapshot, run_x8_compare,
)
snap = load_prematch_intent_snapshot(".../sketch_a_prematch_snapshot.json")
outcome = run_x8_compare(snap, facts_preset="sketch_a", parent=parent, run_id=run_id)
# outcome.report["comparison_status"] == "no_ssot_compare_authorization"
```

### 3.5 测试

```bash
pytest tests/test_minute_orders_x8_compare.py \
       tests/test_minute_orders_intent_x1.py \
       tests/test_minute_orders_intent_x1_named_consumer.py -q
```

## 4. 模块地图

```
backtest/research/minute_orders_x8_compare/
  __init__.py
  ingest.py      # pre-match snapshot only；fills/trades → CompareIngestError
  bridge.py      # freeze→X1 run→comparison_report；独立根；禁 summary.json

scripts/research/run_x8_compare_bridge.py
tests/fixtures/minute_orders_x8_compare/
  sketch_a_prematch_snapshot.json
  fills_derived_rejected.json
tests/test_minute_orders_x8_compare.py
docs/backtest/note-true-core-tc4-x8-compare-bridge-2026-10-02.md
```

**允许 import：** `minute_orders_intent_x1`、`minute_orders_backend.types`（及本包）。  
**禁止 import：** `match` / `fees` / `broker` / `ledger` / `clock` / `csv_minute_backtest` / VolumeCap（测试源码扫描护栏）。

## 5. 负面清单（diff 须空）

| 面 | 禁止 |
|---|---|
| `csv_minute_backtest.simulate` / `simulate_v7` | 任何改动 |
| MatchCore `match_candidates` / `compute_bucket_capacity` | 改现语义 |
| Fees | 偷接 production；改累计名义→增量费 |
| VolumeCap / 旧 L1 `_ENTRIES` / `views._FAMILIES` | 借本票改 |
| `minute_orders_backend/cli.py` / intent_x1 经济语义 | 借本票改 |
| 新 `backend_id` / 新合同字符串（runner） | |
| fills→意图；成功 `summary.json`；落 research_v1 成功根 | |
| NAV 榜；fill-policy 行；绿 R | |
| 真湖 loader；X2–X5；X7 `_FAMILIES`；P3；BOOKS 默认 | |

## 6. ≠δ5≠R4 · 范围外

- **≠δ5 certified ≠R4**；无绿 R / NAV 混比授权。
- Out of scope：X2–X5、X6 真湖、X7 进 `_FAMILIES`、P3、4090、湖写入、Compat 主路径、BOOKS 默认、默改 `simulate`。
- 本码已合 #306；后续 X6 合成差分已合 #307：[X6 note](note-true-core-x6-synthetic-attestation-2026-10-02.md)；真湖边界已合 #309：[X6 lake](note-true-core-x6-lake-boundary-2026-10-02.md)；TC5 见 [TC5 note](note-true-core-tc5-go-scope-2026-10-02.md)（本刀合入）。

## 7. 指针

- TC1 合同冻结：[note-true-core-c-new-tc1-contract-2026-10-02.md](note-true-core-c-new-tc1-contract-2026-10-02.md) §5 X8
- TC2 窄 X1：[note-true-core-tc2-x1-intent-adapter-2026-10-02.md](note-true-core-tc2-x1-intent-adapter-2026-10-02.md)（#304 MERGED）
- TC3 具名消费者：[note-true-core-tc3-named-consumer-2026-10-02.md](note-true-core-tc3-named-consumer-2026-10-02.md)（#305 MERGED）
- S4 工件隔离（对照：本刀**不**走 S4 成功 summary）：[note-l2-s4-artifacts-isolation-2026-09-29.md](note-l2-s4-artifacts-isolation-2026-09-29.md)
- 行业索引：[industry-state-acceptance-index-2026-09-28.md](industry-state-acceptance-index-2026-09-28.md) §7
- handoff（仓外）：`/workspace/handoffs/minute_engine_true_core_new_20261002/`
- X6 合成差分（非真湖 · #307 MERGED）：[note-true-core-x6-synthetic-attestation-2026-10-02.md](note-true-core-x6-synthetic-attestation-2026-10-02.md)
- X6 真湖边界（#309 MERGED）：[note-true-core-x6-lake-boundary-2026-10-02.md](note-true-core-x6-lake-boundary-2026-10-02.md)
- TC5 GO/scope（本刀合入）：[note-true-core-tc5-go-scope-2026-10-02.md](note-true-core-tc5-go-scope-2026-10-02.md)

**≠δ5≠R4；X8 红标签对照桥；仅撮合前意图；独立 comparison 根；无成功 summary.json；无新 contract/backend_id；无 MatchCore/Fees/simulate 重写；#306 MERGED。**
