# 真核大票 · C-New · X6 合成夹具 / attestation 差分（2026-10-02）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-02（Asia/Shanghai / CST） |
| tip 基线 | `79b3995c`（master · #306 TC4 X8 MERGED） |
| Human GO | 「合，继续」后下一刀：优先 **X6 合成夹具/attestation 差分**（**非**真湖）；合成-only；无写湖；复用 v0；≠δ5≠R4；永 opt-in |
| 方案 | `/workspace/handoffs/minute_engine_true_core_new_20261002/`；合同锚 [TC1](note-true-core-c-new-tc1-contract-2026-10-02.md) §5 X6；前序 [TC2](note-true-core-tc2-x1-intent-adapter-2026-10-02.md) · [TC3](note-true-core-tc3-named-consumer-2026-10-02.md) · [TC4](note-true-core-tc4-x8-compare-bridge-2026-10-02.md) |
| 硬约束 | **不** mint 新经济合同 / 新 `backend_id`；`tool_id` ≠ backend_id；独立 tool 根；`differential_status` 恒 `fixture_pass_not_lake_pass`；**不**产成功 `summary.json`；禁 `source_kind=lake` / `evidence_level=lake`；≠δ5≠R4；无写湖；无 4090；无 Compat；无 X2–X5 / X6 **真湖** / X7 `_FAMILIES` |
| PR | **#307 MERGED** `f0620ace`；真湖另见 [lake note](note-true-core-x6-lake-boundary-2026-10-02.md)（#309 MERGED） |

> **本 note ≠ 第二套成交默认表，≠ 绿 R 资格认证，≠ fill-policy，≠ 真湖 PASS。** Fixture PASS ≠ lake PASS / host attestation。工具身份 ≠ 经济合同版本。入口默认 / 绿 R·S 继续只链 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。

## 1. 目的

落实 TC1 §5 **X6 loader** 的**合成夹具 / attestation 级**差分：对照 tip `source_loader` 已接受 `lake|synthetic_fixture` 的双门面，本刀具名加固 **synthetic-only** 表面——拒绝 lake 包、拒绝证据升级、拒绝把 Fixture PASS 伪装成湖 PASS / host attestation / 绿 R。真湖接入仍 **另刀**。

| 本刀交付 | 明确不做 |
|---|---|
| 合成 boundary meta 摄取 + 拒绝 lake / 升级宣称 | 真湖 loader；读湖；写湖；4090 |
| tip 缺口对照报告（`tip_gap_checks`） | 新 contract / 新 backend_id / 新经济语义 |
| 独立根 `…/minute_orders_x6_synthetic/<run_id>/differential_report.json` | 成功 `summary.json`；落 `minute_orders_research_v1` 成功根 |
| `differential_status` 恒 `fixture_pass_not_lake_pass` | 进 fill-policy；NAV 榜；绿 R；host attestation |
| 薄 CLI + HELP + 合成 e2e（含 lake 拒收） | 改 MatchCore / Fees / `simulate` / VolumeCap / 旧 L1 `_ENTRIES` / `views._FAMILIES` |
| 本 docs + TC1/TC4/industry 轻指针 | X2–X5 / X6 真湖 / X7 `_FAMILIES` / P3 / BOOKS 默认 |
| 本码已合 #307 | 默改 `simulate`；把 Fixture PASS 升为 lake PASS |

## 2. tip 缺口（相对 TC1 §5 X6）

| tip 已有 | 本刀加固 |
|---|---|
| `source_loader`：`source_kind ∈ {lake, synthetic_fixture}` | X6 合成工具 **只**收 `synthetic_fixture`；`lake` 拒 |
| CLI `--evidence-level` 仅 `synthetic`（no lake loader） | boundary meta `evidence_level` 必须 `synthetic` |
| 账户 origin 仍 `synthetic_account` | meta 钉死该 origin |
| 命令 origin 仍 `designed_limit_batch` | meta 钉死该 origin |
| `FIXTURE_NOTICE`：Fixture PASS ≠ lake PASS… | notice 必须含该 token；禁 `claims.lake_pass=true` 等升级 |

本刀 **不**调用完整 `load_minute_orders_source`（避免把 implementation pin / 真湖路径拖进合成刀）；只对照并加固边界不变量。

## 3. 身份澄清

| 层 | 本刀取值 | 说明 |
|---|---|---|
| **经济合同** | 仍 `research contract v0 (L2-S0)` | **不** mint 新 contract 字符串 |
| **backend_id** | 仍 `minute_orders_research_v1`（仅文档标签） | **不**换经济身份；本刀不跑 runner |
| **工具身份** | `tool_id=minute_orders_x6_synthetic` | **仅**工具/报告身份；**不是** backend_id |
| **报告根** | `minute_orders_x6_synthetic/<run_id>/` | **独立**于 `minute_orders_research_v1` |
| **差分状态** | 恒 `fixture_pass_not_lake_pass` | 红标签；诊断 / 边界加固 only |
| **完成标记** | 仅 `differential_report.json` | **禁止**写成功 `summary.json` |
| **默认化** | 永 opt-in（H-TC9） | 永不 BOOKS 默认 |

## 4. 如何调用

### 4.1 HELP

```bash
python scripts/research/run_x6_synthetic_differential.py --help
```

### 4.2 内存诊断

```bash
python scripts/research/run_x6_synthetic_differential.py \
  --meta tests/fixtures/minute_orders_x6_synthetic/boundary_ok.json \
  --memory-only
```

### 4.3 写独立 tool 根

```bash
python scripts/research/run_x6_synthetic_differential.py \
  --meta tests/fixtures/minute_orders_x6_synthetic/boundary_ok.json \
  --parent /tmp/x6-out \
  --run-id unique-run-id
# 产出: /tmp/x6-out/minute_orders_x6_synthetic/unique-run-id/differential_report.json
# 同 run_id 再写 → FileExistsError；根下无 summary.json
```

### 4.4 库 API

```python
from backtest.research.minute_orders_x6_synthetic import (
    load_synthetic_boundary_meta, run_x6_synthetic_differential,
)
meta = load_synthetic_boundary_meta(".../boundary_ok.json")
outcome = run_x6_synthetic_differential(meta, parent=parent, run_id=run_id)
# outcome.report["differential_status"] == "fixture_pass_not_lake_pass"
```

### 4.5 测试

```bash
pytest tests/test_minute_orders_x6_synthetic.py -q
```

## 5. 模块地图

```
backtest/research/minute_orders_x6_synthetic/
  __init__.py
  ingest.py                 # boundary meta；拒 lake / 升级宣称
  differential.py           # tip_gap_checks + 独立根写盘
scripts/research/run_x6_synthetic_differential.py
tests/fixtures/minute_orders_x6_synthetic/
  boundary_ok.json
  lake_kind_rejected.json
tests/test_minute_orders_x6_synthetic.py
docs/backtest/note-true-core-x6-synthetic-attestation-2026-10-02.md
```

## 6. 负面清单（diff 须空）

| 面 | 禁止 |
|---|---|
| `match.py` / `fees.py` | 任何改动 |
| `csv_minute_backtest.simulate` / `simulate_v7` | 任何改动 |
| VolumeCap / clamp / 完成桶共享 | 借本刀改共享核 |
| 旧 L1 `_ENTRIES` / `views._FAMILIES` | 改成事件宿主或塞 New |
| 新 contract / 新 backend_id | 本刀不 mint |
| 真湖 / 4090 / host attestation PASS | 另刀 |
| 成功 `summary.json` / 绿 R / NAV 混比 | 永不 |

## 7. 指针

- TC1 合同：[note-true-core-c-new-tc1-contract-2026-10-02.md](note-true-core-c-new-tc1-contract-2026-10-02.md) §5 X6
- tip loader / notice：`backtest/research/minute_orders_backend/source_loader.py` · `source_provenance.FIXTURE_NOTICE`
- 湖 ingress 合同：[note-l2-lake-source-ingress-b-l2-01-2026-09-29.md](note-l2-lake-source-ingress-b-l2-01-2026-09-29.md)
- X6 真湖只读 END/loader 边界：[note-true-core-x6-lake-boundary-2026-10-02.md](note-true-core-x6-lake-boundary-2026-10-02.md)（draft 勿合；Human「C GO」）
- TC4 X8（已合 #306）：[note-true-core-tc4-x8-compare-bridge-2026-10-02.md](note-true-core-tc4-x8-compare-bridge-2026-10-02.md)
- TC5 GO/scope（draft 勿合）：[note-true-core-tc5-go-scope-2026-10-02.md](note-true-core-tc5-go-scope-2026-10-02.md)
- 成交假设 SSOT：[minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)

**≠δ5 certified ≠R4；无 MatchCore/Fees/simulate 重写；无写湖；本码已合 #307。**
