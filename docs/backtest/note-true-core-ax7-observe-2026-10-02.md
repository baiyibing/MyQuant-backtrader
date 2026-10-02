# 真核大票 · C-New · A·X7 观察面（2026-10-02）

| 字段 | 值 |
|---|---|
| 日期 | **2026-10-02 21:53 CST（Asia/Shanghai）** |
| tip 基线 | **`fcf3f6f3`**（master · #313 MERGED） |
| Human GO | 「Codex 计划+A GO」→ **A · X7 观察面**（新投影；无新经济语义；零湖零 4090） |
| 方案 | TC1 §5 X7 / TC5 轴表 / PLAN X7；计划见 [Codex residual plan](note-true-core-codex-residual-plan-2026-10-02.md) |
| 硬约束 | **不** mint 新经济合同 / 新 `backend_id`；`observation_id` ≠ backend_id；**新**投影入口；**不**塞 `views._FAMILIES`；观察 ≠ 绿 R；**不**重算 NAV；不产成功 `summary.json`；≠δ5≠R4；无生产写湖；无 4090；永 opt-in |
| PR | **#314 MERGED** |

> **本 note ≠ 绿 R，≠ fill-policy，≠ NAV 排行，≠ host PASS，≠ 生产写湖。**  
> 观察面身份 ≠ 经济合同版本。入口默认 / 绿 R·S 继续只链 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。

## 1. 目的

落实 TC1 / TC5 **X7 · 观察面**：对**已经获得**的 New 核工具报告做红标签投影切片，提高可解释性。使用**新**投影入口 `projection_family=minute_orders_x7_observe`，**禁止**把 L2/New 塞进既有 L1 `views._FAMILIES` 四元组充数。

| 本刀交付 | 明确不做 |
|---|---|
| `observation_id=minute_orders_x7_observe` | 新 contract / 新 backend_id |
| 摄取已获 source_kind 请求 JSON | fills/trades 倒造；NAV/equity 重算 |
| 独立根 `…/minute_orders_x7_observe/<run_id>/observation_report.json` | 成功 `summary.json`；落 research_v1 成功根 |
| 恒 `observation_status=observation_only_not_green_r` | 进 fill-policy；绿 R；BOOKS 默认 |
| 拒 `views_family` / `_FAMILIES` 注册 | 改 `run_protocol/views.py` |
| 薄 CLI + 合成测例 | 改 MatchCore / Fees / `simulate` / source_loader / backend CLI |
| 本 docs + residual plan + industry 轻指针 | 生产写湖；4090；X2–X5 码 |

## 2. 身份澄清

| 层 | 本刀取值 | 说明 |
|---|---|---|
| **经济合同** | 仍 `research contract v0 (L2-S0)` | **不** mint |
| **backend_id** | 仍 `minute_orders_research_v1`（标签 only） | 观察面**不**换经济身份 |
| **观察身份** | `observation_id=minute_orders_x7_observe` | **仅**工具/投影身份；**不是** backend_id |
| **投影族** | `minute_orders_x7_observe` | **新**入口；**不**在 `views._FAMILIES` |
| **观察根** | `minute_orders_x7_observe/<run_id>/` | **独立**于 `minute_orders_research_v1` |
| **状态** | 恒 `observation_only_not_green_r` | 红标签；观察 only |
| **完成标记** | 仅 `observation_report.json` | **禁止**写成功 `summary.json` |
| **默认化** | 永 opt-in（H-TC9） | 永不 BOOKS 默认 |

## 3. 如何调用

### 3.1 HELP

```bash
python scripts/research/run_x7_observe.py --help
```

HELP 点名：`observation_id`、新 `projection_family`、永不 `views._FAMILIES`、合同/backend 仍 v0、`observation_status` 恒值、以及 bans（无 NAV 重写 / 无绿 R / 无成功 summary.json / 独立根 / 无新合同 / 无 MatchCore·Fees·simulate 改 / ≠δ5≠R4 / 永 opt-in）。

### 3.2 内存投影

```bash
python scripts/research/run_x7_observe.py \
  --request /abs/path/to/request_ok.json \
  --memory-only
```

### 3.3 写独立观察根

```bash
python scripts/research/run_x7_observe.py \
  --request /abs/path/to/request_ok.json \
  --parent /tmp/x7-out \
  --run-id unique-run-id
# 产出: /tmp/x7-out/backtest_output/minute_orders_x7_observe/unique-run-id/observation_report.json
# 同 run_id 再写 → ObserveError（wrapping FileExistsError）；根下无 summary.json；CLI exit 2
```

### 3.4 库 API

```python
from backtest.research.minute_orders_x7_observe import (
    load_observe_request, run_x7_observe,
)
req = load_observe_request(".../request_ok.json")
outcome = run_x7_observe(request=req, parent=parent, run_id=run_id)
# outcome.report["observation_status"] == "observation_only_not_green_r"
```

### 3.5 测试

```bash
pytest tests/test_minute_orders_x7_observe.py -q
```

## 4. 模块地图

```
backtest/research/minute_orders_x7_observe/
  __init__.py
  policy.py      # observation_id / status / bans；禁 _FAMILIES
  project.py     # 请求摄取 + 投影切片 + 独立根写入

scripts/research/run_x7_observe.py
tests/fixtures/minute_orders_x7_observe/
  request_ok.json
  request_nav_rejected.json
  request_families_rejected.json
  request_fills_rejected.json
tests/test_minute_orders_x7_observe.py
```

`match.py` / `fees.py` / `simulate*` / `source_loader` / `cli.py` / `run_protocol/views.py` → **空 diff**。

## 5. 允许的 source_kind（已获工件）

| source_kind | 含义 |
|---|---|
| `x1_named_consumer_report` | TC3 具名消费者报告 |
| `x6_synthetic_differential_report` | #307 合成差分 |
| `x6_lake_boundary_report` | #309 边界 |
| `x6_lake_e2e_report` | #310 e2e load |
| `x8_comparison_report` | #306 对照桥 |
| `write_lake_staging_dry_run_report` | #312 staging（仍 ≠ 生产写） |
| `synthetic_observation_sketch` | 本刀合成夹具 |

禁止顶层 / evidence 内：`fills` / `trades` / `nav` / `equity_curve` / `summary` / `green_r` / `host_pass` / 写湖键；禁止 `views_family` 字段。

## 6. 负面清单

| 禁止 | 说明 |
|---|---|
| 改 `views._FAMILIES` | H-TC6 / TC5 硬锁 |
| NAV / 绿 R | 观察 ≠ 验收升级 |
| 成功 `summary.json` | 独立观察根 only |
| 生产写湖 / 4090 | 另 GO |
| mint 新 contract/backend_id | 加法型观察片复用 v0 标签 |
| 改 MatchCore / Fees / `simulate` | H-TC4/5 |
| BOOKS 默认 | H-TC9 永 opt-in |

## 7. 指针

- Codex 残差计划：[note-true-core-codex-residual-plan-2026-10-02.md](note-true-core-codex-residual-plan-2026-10-02.md)
- TC1：[note-true-core-c-new-tc1-contract-2026-10-02.md](note-true-core-c-new-tc1-contract-2026-10-02.md)
- TC5：[note-true-core-tc5-go-scope-2026-10-02.md](note-true-core-tc5-go-scope-2026-10-02.md)
- 写湖 staging：[note-true-core-write-lake-residual-2026-10-02.md](note-true-core-write-lake-residual-2026-10-02.md)（#312 MERGED；≠ 生产写）
- industry §7：[industry-state-acceptance-index-2026-09-28.md](industry-state-acceptance-index-2026-09-28.md)

**≠δ5 certified ≠R4；观察 ≠ 绿 R；无 MatchCore/Fees/simulate 重写；无生产写湖；无 4090；#314 MERGED。**
