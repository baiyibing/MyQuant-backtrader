# 真核大票 · C-New · X6 真湖 recipe e2e（只读 load）（2026-10-02）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-02（Asia/Shanghai / CST） |
| tip 基线 | `5fe84f7`（master · #308 TC5 docs MERGED；前序 #309 真湖边界 `d0804d09`） |
| Human GO | **「GO lake e2e」** = C 残差 · **完整 `load_minute_orders_source` / lake recipe e2e**（**只读**；**非**写湖；**非**解锁 CLI `--evidence-level=lake`；**非** 4090） |
| 方案 | `/workspace/handoffs/minute_engine_true_core_new_20261002/`；合同锚 [TC1](note-true-core-c-new-tc1-contract-2026-10-02.md) §5 X6；前序边界 [X6 lake boundary](note-true-core-x6-lake-boundary-2026-10-02.md)（#309） |
| 硬约束 | **不** mint 新经济合同 / 新 `backend_id`；`tool_id` ≠ backend_id；复用 `tool_id=minute_orders_x6_lake`；`e2e_status` 恒 `lake_recipe_e2e_loaded_not_host_pass`；**不**产成功 `summary.json`；**不**写湖；**不**跑 MatchCore fills；≠δ5≠R4；无 4090；永 opt-in |
| PR | **#310 draft** https://github.com/baiyibing/MyQuant-backtrader/pull/310（勿合） |

> **本 note ≠ 第二套成交默认表，≠ 绿 R，≠ fill-policy，≠ 真湖 PASS / host attestation / item-4 live。**  
> Lake recipe e2e load ≠ host PASS。Fixture PASS ≠ lake PASS（#307 仍独立）。边界 attestation（#309）≠ 本 e2e。工具身份 ≠ 经济合同版本。  
> 入口默认 / 绿 R·S 继续只链 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。

## 1. 目的

落实 #309 残留表中的 **完整 `load_minute_orders_source` lake recipe e2e**：在已合的只读 lake END/loader **边界**之上，接一条**最小忠实**路径——预检 `source_kind=lake` + Phase5 `bar_time_label=END` + `availability=bucket_end` → 调用 tip `load_minute_orders_source` → 写独立 tool 根 `e2e_report.json`（**不**写湖、**不**解锁 backend CLI lake、**不**落 `minute_orders_research_v1` 成功 `summary.json`）。

| 本刀交付 | 明确不做 |
|---|---|
| 预检 lake+END recipe + 调 `load_minute_orders_source` | 写湖；4090 live；host attestation PASS |
| 独立根 `…/minute_orders_x6_lake/<run_id>/e2e_report.json` | 成功 `summary.json`；落 `minute_orders_research_v1` 成功根 |
| `e2e_status` 恒 `lake_recipe_e2e_loaded_not_host_pass` | 进 fill-policy；NAV 榜；绿 R；item-4 live |
| 薄 CLI + HELP；拒 synthetic / START / sha 错 / dirty code | 改 MatchCore / Fees / `simulate` / VolumeCap / 旧 L1 `_ENTRIES` / `views._FAMILIES` / **backend CLI** |
| 本 docs + TC1/industry/TC5/X6-boundary 轻指针 | 解锁 CLI `--evidence-level=lake`（另 opt-in GO）；写湖 Phase4；4090 |

## 2. 相对 #309 的增量

| #309 边界刀 | 本 e2e 刀 |
|---|---|
| **不**调 `load_minute_orders_source` | **调** tip loader（只读） |
| meta schema `…boundary_meta_v0` | 输入 = 既有 `minute_orders_source_recipe_v1`（lake+END） |
| `differential_status=lake_boundary_attested_not_host_pass` | `e2e_status=lake_recipe_e2e_loaded_not_host_pass` |
| `differential_report.json` | `e2e_report.json`（同 tool 根名，不同 run） |
| 拒 synthetic 伪装 / 写湖键 / 升级宣称 | 同上 + sha 钉死 + dirty code 拒（loader 湖门） |

## 3. 身份澄清

| 层 | 本刀取值 | 说明 |
|---|---|---|
| **经济合同** | 仍 `research contract v0 (L2-S0)` | **不** mint 新 contract 字符串 |
| **backend_id** | 仍 `minute_orders_research_v1`（仅文档标签） | **不**换经济身份；本刀不写其成功根 |
| **工具身份** | `tool_id=minute_orders_x6_lake` | **仅**工具/报告身份；**不是** backend_id |
| **报告根** | `minute_orders_x6_lake/<run_id>/` | **独立**于 `minute_orders_research_v1` |
| **e2e 状态** | 恒 `lake_recipe_e2e_loaded_not_host_pass` | 红标签；只读 load 诊断 only |
| **完成标记** | 仅 `e2e_report.json` | **禁止**写成功 `summary.json` |
| **默认化** | 永 opt-in（H-TC9） | 永不 BOOKS 默认 |

## 4. 如何调用

### 4.1 HELP

```bash
python scripts/research/run_x6_lake_recipe_e2e.py --help
```

### 4.2 内存诊断

```bash
python scripts/research/run_x6_lake_recipe_e2e.py \
  --recipe /abs/path/to/recipe.json \
  --expected-sha256 <64-hex> \
  --memory-only
```

### 4.3 写独立 tool 根

```bash
python scripts/research/run_x6_lake_recipe_e2e.py \
  --recipe /abs/path/to/recipe.json \
  --expected-sha256 <64-hex> \
  --parent /tmp/x6-lake-e2e-out \
  --run-id unique-run-id
# 产出: /tmp/x6-lake-e2e-out/minute_orders_x6_lake/unique-run-id/e2e_report.json
# 同 run_id 再写 → FileExistsError；根下无 summary.json；不写湖
```

### 4.4 库 API

```python
from backtest.research.minute_orders_x6_lake import run_x6_lake_recipe_e2e
outcome = run_x6_lake_recipe_e2e(
    "/abs/recipe.json", expected_sha256="...", parent=parent, run_id=run_id,
)
# outcome.report["e2e_status"] == "lake_recipe_e2e_loaded_not_host_pass"
```

### 4.5 测试

```bash
pytest tests/test_minute_orders_x6_lake_e2e.py tests/test_minute_orders_x6_lake.py -q
```

测例用 **tmp 伪造 lake 文件**（`SyntheticCase` + `source_kind=lake` + END 标签）；**不**读生产湖、**不**写湖。

## 5. 模块地图

```
backtest/research/minute_orders_x6_lake/
  __init__.py
  ingest.py                 # #309 boundary meta（本刀不改语义）
  differential.py           # #309 boundary report（本刀不改语义）
  e2e.py                    # NEW · preflight + load_minute_orders_source + e2e_report
scripts/research/run_x6_lake_recipe_e2e.py
tests/test_minute_orders_x6_lake_e2e.py
docs/backtest/note-true-core-x6-lake-recipe-e2e-2026-10-02.md
```

## 6. 负面清单（diff 须空）

| 面 | 禁止 |
|---|---|
| `match.py` / `fees.py` | 任何改动 |
| `csv_minute_backtest.simulate` / `simulate_v7` | 任何改动 |
| `source_loader.py` / backend `cli.py` | 本刀不改；**不**解锁 CLI lake evidence |
| VolumeCap / clamp / 完成桶共享 | 借本刀改共享核 |
| 旧 L1 `_ENTRIES` / `views._FAMILIES` | 改成事件宿主或塞 New |
| 新 contract / 新 backend_id | 本刀不 mint |
| 写湖 / 4090 / host attestation PASS | 另具名 GO |
| 成功 `summary.json` / 绿 R / NAV 混比 | 永不 |
| 把 Fixture PASS / boundary attestation 升为 lake PASS | 永不 |

## 7. 仍须 Human 裁的残留（本刀未开）

| 残留 | 说明 |
|---|---|
| 解锁 backend CLI `--evidence-level=lake` | 须另 opt-in GO；本刀明确不解锁 |
| 写湖 / Phase4 写路径 | 须另具名「写湖 GO」 |
| 4090 host attestation / item-4 live | 须另 GO |
| TC5 其它轴（X2/X3/X4/X5/X7） | 见 [TC5 GO/scope](note-true-core-tc5-go-scope-2026-10-02.md) |

## 8. 指针

- TC1 合同：[note-true-core-c-new-tc1-contract-2026-10-02.md](note-true-core-c-new-tc1-contract-2026-10-02.md) §5 X6
- X6 合成（#307 MERGED）：[note-true-core-x6-synthetic-attestation-2026-10-02.md](note-true-core-x6-synthetic-attestation-2026-10-02.md)
- X6 真湖只读边界（#309 MERGED）：[note-true-core-x6-lake-boundary-2026-10-02.md](note-true-core-x6-lake-boundary-2026-10-02.md)
- tip loader：`backtest/research/minute_orders_backend/source_loader.py`
- 湖 ingress 合同：[note-l2-lake-source-ingress-b-l2-01-2026-09-29.md](note-l2-lake-source-ingress-b-l2-01-2026-09-29.md)
- 成交假设 SSOT：[minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)

**≠δ5 certified ≠R4；无 MatchCore/Fees/simulate/backend-cli 重写；无写湖；无 CLI lake unlock；本刀 draft 勿合。**
