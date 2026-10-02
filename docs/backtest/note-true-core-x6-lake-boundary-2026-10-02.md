# 真核大票 · C-New · X6 真湖 END / loader 边界差分（2026-10-02）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-02（Asia/Shanghai / CST） |
| tip 基线 | `f0620ace`（master · #307 X6 合成 attestation MERGED） |
| Human GO | **「C GO」** = H-TC5-NEXT **C · X6 真湖**；本刀 = **只读 lake END / loader 边界**（**非**写湖；**非** host PASS；**非**解锁 CLI `--evidence-level=lake`） |
| 方案 | `/workspace/handoffs/minute_engine_true_core_new_20261002/`；合同锚 [TC1](note-true-core-c-new-tc1-contract-2026-10-02.md) §5 X6；前序合成 [X6 synthetic](note-true-core-x6-synthetic-attestation-2026-10-02.md)（#307） |
| 硬约束 | **不** mint 新经济合同 / 新 `backend_id`；`tool_id` ≠ backend_id；独立 tool 根；`differential_status` 恒 `lake_boundary_attested_not_host_pass`；**不**产成功 `summary.json`；**不**写湖；**不**调 `load_minute_orders_source`；拒 synthetic 伪装；≠δ5≠R4；无 4090；永 opt-in |
| PR | **#309 MERGED** `d0804d09` |

> **本 note ≠ 第二套成交默认表，≠ 绿 R，≠ fill-policy，≠ 真湖 PASS / host attestation / item-4 live。**  
> Lake boundary attestation ≠ host PASS。Fixture PASS ≠ lake PASS（#307 仍独立）。工具身份 ≠ 经济合同版本。  
> 入口默认 / 绿 R·S 继续只链 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。

## 1. 目的

落实 TC1 §5 **X6 loader** 的**真湖**刀（与 #307 合成分开）：对照 tip `source_loader` 已接受 `lake|synthetic_fixture` 的双门面，本刀具名加固 **lake-only + Phase5 END 研究路径** 的**只读边界**——拒绝 synthetic_fixture 伪装成湖 PASS、拒绝证据升级、拒绝写湖、拒绝把 boundary attestation 伪装成 host PASS / 绿 R。

| 本刀交付 | 明确不做 |
|---|---|
| lake boundary meta 摄取 + END/`bucket_end` 钉死 | 写湖；4090 live；host attestation PASS |
| tip 缺口对照报告（`tip_gap_checks`） | 新 contract / 新 backend_id / 新经济语义 |
| 独立根 `…/minute_orders_x6_lake/<run_id>/differential_report.json` | 成功 `summary.json`；落 `minute_orders_research_v1` 成功根 |
| `differential_status` 恒 `lake_boundary_attested_not_host_pass` | 进 fill-policy；NAV 榜；绿 R；item-4 live |
| 薄 CLI + HELP + 拒收 synthetic / START / 升级宣称 | 改 MatchCore / Fees / `simulate` / VolumeCap / 旧 L1 `_ENTRIES` / `views._FAMILIES` / backend CLI |
| 本 docs + TC1/industry/X6-synthetic 轻指针 | 解锁 CLI `--evidence-level=lake`；调 `load_minute_orders_source`；完整真湖 recipe e2e |
| 本码已合 #309 | 默改 `simulate`；把 Fixture PASS 升为 lake PASS |

## 2. tip 缺口（相对 TC1 §5 X6 + Phase5）

| tip 已有 | 本刀加固 |
|---|---|
| `source_loader`：`source_kind ∈ {lake, synthetic_fixture}` | X6 真湖工具 **只**收 `lake`；`synthetic_fixture` 拒（对称 #307） |
| CLI `--evidence-level` 仅 `synthetic`（no lake loader） | `evidence_level` 必须 `lake_boundary`；**不**解锁 CLI `lake` |
| bars：`availability=bucket_end`；`time.label ∈ {START, END}` | 本刀研究路径钉 `bar_time_label=END`（Phase5） |
| 账户 origin 仍 `synthetic_account` | meta 钉死该 origin |
| 命令 origin 仍 `designed_limit_batch` | meta 钉死该 origin |
| lake notice：源校验 ≠ host certification | notice 必须含 `lake boundary attestation != host PASS`；禁升级宣称 |

本刀 **不**调用完整 `load_minute_orders_source`（避免把 implementation pin / 真湖 recipe e2e / 写湖拖进本边界刀）；只对照并加固边界不变量。本边界刀仍不调用 `load_minute_orders_source`；recipe e2e 见 [e2e note](note-true-core-x6-lake-recipe-e2e-2026-10-02.md)（**#310 draft · 勿合**，只读）；4090 仍须另 GO。

## 3. 身份澄清

| 层 | 本刀取值 | 说明 |
|---|---|---|
| **经济合同** | 仍 `research contract v0 (L2-S0)` | **不** mint 新 contract 字符串 |
| **backend_id** | 仍 `minute_orders_research_v1`（仅文档标签） | **不**换经济身份；本刀不跑 runner |
| **工具身份** | `tool_id=minute_orders_x6_lake` | **仅**工具/报告身份；**不是** backend_id |
| **报告根** | `minute_orders_x6_lake/<run_id>/` | **独立**于 `minute_orders_research_v1` 与 `minute_orders_x6_synthetic` |
| **差分状态** | 恒 `lake_boundary_attested_not_host_pass` | 红标签；只读边界 / 诊断 only |
| **完成标记** | 仅 `differential_report.json` | **禁止**写成功 `summary.json` |
| **默认化** | 永 opt-in（H-TC9） | 永不 BOOKS 默认 |

## 4. 如何调用

### 4.1 HELP

```bash
python scripts/research/run_x6_lake_differential.py --help
```

### 4.2 内存诊断

```bash
python scripts/research/run_x6_lake_differential.py \
  --meta tests/fixtures/minute_orders_x6_lake/boundary_ok.json \
  --memory-only
```

### 4.3 写独立 tool 根

```bash
python scripts/research/run_x6_lake_differential.py \
  --meta tests/fixtures/minute_orders_x6_lake/boundary_ok.json \
  --parent /tmp/x6-lake-out \
  --run-id unique-run-id
# 产出: /tmp/x6-lake-out/minute_orders_x6_lake/unique-run-id/differential_report.json
# 同 run_id 再写 → FileExistsError；根下无 summary.json；不写湖
```

### 4.4 库 API

```python
from backtest.research.minute_orders_x6_lake import (
    load_lake_boundary_meta, run_x6_lake_differential,
)
meta = load_lake_boundary_meta(".../boundary_ok.json")
outcome = run_x6_lake_differential(meta, parent=parent, run_id=run_id)
# outcome.report["differential_status"] == "lake_boundary_attested_not_host_pass"
```

### 4.5 测试

```bash
pytest tests/test_minute_orders_x6_lake.py -q
```

## 5. 模块地图

```
backtest/research/minute_orders_x6_lake/
  __init__.py
  ingest.py                 # lake boundary meta；拒 synthetic / START / 升级 / 写湖键
  differential.py           # tip_gap_checks + 独立根写盘（仅报告，不写湖）
scripts/research/run_x6_lake_differential.py
tests/fixtures/minute_orders_x6_lake/
  boundary_ok.json
  synthetic_kind_rejected.json
  start_label_rejected.json
tests/test_minute_orders_x6_lake.py
docs/backtest/note-true-core-x6-lake-boundary-2026-10-02.md
```

## 6. 负面清单（diff 须空）

| 面 | 禁止 |
|---|---|
| `match.py` / `fees.py` | 任何改动 |
| `csv_minute_backtest.simulate` / `simulate_v7` | 任何改动 |
| `source_loader.py` / `cli.py` | 本刀不改；不解锁 CLI lake evidence |
| VolumeCap / clamp / 完成桶共享 | 借本刀改共享核 |
| 旧 L1 `_ENTRIES` / `views._FAMILIES` | 改成事件宿主或塞 New |
| 新 contract / 新 backend_id | 本刀不 mint |
| 写湖 / 4090 / host attestation PASS | 另具名 GO |
| 成功 `summary.json` / 绿 R / NAV 混比 | 永不 |
| 把 #307 Fixture PASS 升为 lake PASS | 永不 |

## 7. 仍须 Human 裁的残留（本刀未开）

| 残留 | 说明 |
|---|---|
| 完整 `load_minute_orders_source` lake recipe e2e | 见 [X6 lake recipe e2e](note-true-core-x6-lake-recipe-e2e-2026-10-02.md)（#310 MERGED） |
| 解锁 backend CLI `--evidence-level=lake` | 见 [CLI lake note](note-true-core-cli-lake-2026-10-02.md)（残差 R1） |
| 写湖 / Phase4 写路径 | 须另具名「写湖 GO」 |
| 4090 host attestation / item-4 live | 须另 GO |
| TC5 其它轴（X2/X3/X4/X5/X7） | 见 [TC5 GO/scope](note-true-core-tc5-go-scope-2026-10-02.md)（#308 本刀合入；码轴另 GO） |

## 8. 指针

- TC1 合同：[note-true-core-c-new-tc1-contract-2026-10-02.md](note-true-core-c-new-tc1-contract-2026-10-02.md) §5 X6
- X6 合成（#307 MERGED）：[note-true-core-x6-synthetic-attestation-2026-10-02.md](note-true-core-x6-synthetic-attestation-2026-10-02.md)
- tip loader / notice：`backtest/research/minute_orders_backend/source_loader.py` · `source_provenance.py`
- 湖 ingress 合同：[note-l2-lake-source-ingress-b-l2-01-2026-09-29.md](note-l2-lake-source-ingress-b-l2-01-2026-09-29.md)
- Phase5 END 研究路径：[ssot/vendor-bar-alignment-ssot.md](ssot/vendor-bar-alignment-ssot.md) §10；[vendor-three-symbol-lake-ingest PLAN](vendor-three-symbol-lake-ingest-2026-10-01/PLAN.md)
- 成交假设 SSOT：[minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)
- X6 真湖 recipe e2e（只读 load；残差 GO）：[note-true-core-x6-lake-recipe-e2e-2026-10-02.md](note-true-core-x6-lake-recipe-e2e-2026-10-02.md)

**≠δ5 certified ≠R4；无 MatchCore/Fees/simulate 重写；无写湖；#309/#310 工具自身不解锁 CLI；backend CLI lake 见 [CLI lake note](note-true-core-cli-lake-2026-10-02.md)（draft）；#309 MERGED。**
