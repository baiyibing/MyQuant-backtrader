# 真核大票 · C-New · 残差 R1 · CLI `--evidence-level=lake`（2026-10-02）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-02（Asia/Shanghai / CST） |
| tip 基线 | `6c8178ad`（master · #310 真湖 recipe e2e MERGED） |
| Human GO | **「GO CLI Lake」** = Codex R1 · 解锁 backend CLI `--evidence-level=lake` 窄 opt-in 消费接线 |
| 方案 | `/workspace/handoffs/minute_engine_true_core_new_20261002/`；顾问 [CODEX_RESIDUAL_GO](`/workspace/handoffs/minute_engine_true_core_new_20261002/reviews/CODEX_RESIDUAL_GO.md`)（仓外）；合同锚 [TC1](note-true-core-c-new-tc1-contract-2026-10-02.md) |
| 硬约束 | **不** mint 新经济合同 / 新 `backend_id`；复用 v0 (L2-S0) + `minute_orders_research_v1`；CLI `lake` → S4 **`hybrid`**；`tool_id`≠backend_id；**不**写湖；**不** 4090；空 diff MatchCore/Fees/`simulate`/source_loader；≠δ5≠R4；永 opt-in |
| PR | **draft · 勿合**（本刀） |

> **本 note ≠ host PASS，≠ item-4 live，≠ 绿 R，≠ 写湖授权，≠ 新身份 mint。**  
> CLI `--evidence-level=lake` = **来源选择**；落盘证据等级仍是既有 S4 **`hybrid`** + `source_kind=lake`。  
> #310 e2e load ≠ 本刀研究运行；#309 boundary ≠ host PASS；Fixture PASS ≠ lake PASS。  
> 入口默认 / 绿 R·S 继续只链 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。

## 1. 目的

在 #309 边界 + #310 只读 load 之上，补 **backend 研究消费者** 的显式湖输入门：pinned `lake+END` recipe → 现有 `load_minute_orders_source` → 现有 `run_minute_orders_research_with_artifacts(..., evidence_level="hybrid")` → 原生 S4 完成工件。

| 本刀交付 | 明确不做 |
|---|---|
| CLI `--evidence-level=lake` + `--recipe` + `--expected-sha256` | 写湖 / Phase4；4090 / host attestation PASS |
| 预检 lake+END / `bucket_end`；拒 synthetic 伪装 / `--input` / `--code-sha` | 改 MatchCore / Fees / `simulate` / VolumeCap / source_loader |
| CLI `lake` → S4 `hybrid`；保留非认证标记 | mint 新 contract / backend_id；BOOKS 默认 |
| synthetic 旧路径行为不变 | 把 #309/#310 报告补成功 summary 冒充 |
| HELP / docs / 拒收与成功测例 | 绿 R；NAV 榜；第二价格；交易栈 |

## 2. 证据映射

| 层 | 取值 |
|---|---|
| CLI `--evidence-level` | `lake`（来源选择；永 opt-in） |
| S4 `evidence_level` | **`hybrid`**（既有 schema `minute_orders_artifacts_v2`） |
| provenance `source_kind` | `lake` |
| 账户 / 命令 | 仍 `synthetic_account` / `designed_limit_batch` |
| `host_attestation_status` | 恒 `not_certified_by_writer` |
| `live_acceptance_status` | 恒 `not_assessed` |
| `comparison_status` | 恒 `no_ssot_compare_authorization` |

## 3. 如何调用

### 3.1 HELP

```bash
python scripts/research/run_minute_orders_research.py --help
```

### 3.2 synthetic（旧路径，不变）

```bash
python scripts/research/run_minute_orders_research.py \
  --input tests/fixtures/minute_orders/partial_cancel_expiry_v1.json \
  --parent /tmp/minute-orders-example \
  --run-id synthetic-example-01 \
  --evidence-level synthetic
```

### 3.3 lake（本刀；须绝对 recipe 路径；parent/run-id 与 recipe 一致）

```bash
python scripts/research/run_minute_orders_research.py \
  --evidence-level lake \
  --recipe /abs/path/to/lake_end_recipe.json \
  --expected-sha256 <64-hex> \
  --parent /abs/path/matching/recipe.parent \
  --run-id matching-recipe-run-id
# 产出: <parent>/backtest_output/minute_orders_research_v1/<run-id>/
# manifest.evidence_level=hybrid · source_kind=lake · 含 source_provenance.json
# 成功 = 该研究运行完成；≠ host PASS
```

### 3.4 拒收（exit 2 · 不建研究根）

- `--evidence-level=lake` 却带 `--input` / `--code-sha`
- `source_kind≠lake`（含 synthetic_fixture 伪装）
- bar `time.label≠END` 或 `availability≠bucket_end`
- recipe SHA / run-id / parent 与 CLI 不一致
- lake + dirty git（loader 既有门）

### 3.5 测试

```bash
pytest tests/test_minute_orders_cli_lake.py tests/test_minute_orders_cli.py -q
```

测例用 **tmp 伪造 lake+END**（`SyntheticCase`）；**不**读生产湖、**不**写湖。

## 4. 模块地图

| 路径 | 角色 |
|---|---|
| `backtest/research/minute_orders_backend/cli.py` | 本刀：lake 分支 + 完成校验 |
| `scripts/research/run_minute_orders_research.py` | 入口 docstring |
| `source_loader` / `runner` / `artifacts` | **未改**；仅调用 |
| `match.py` / `fees.py` / `simulate*` | **空 diff** |

## 5. 负面清单

| 禁止 | 说明 |
|---|---|
| 裸传 `lake` 给 S4 | CLI 映射为 `hybrid` + provenance |
| 缺数据转 synthetic / 空表 | 失败即停 |
| `--code-sha` 覆盖湖路径 | 拒；hybrid 钉 git HEAD |
| 写湖 / 建缺失分区 | 另「写湖 GO」 |
| 4090 / 填 host PASS | 另 R3 |
| 改 MatchCore / Fees / simulate | H-TC3/4/5 |
| BOOKS 默认 / 绿 R | H-TC9；比较权限不因成功解除 |
| 新 contract / backend_id | 不 mint；`tool_id` 仍独立 |

## 6. 指针

- #310 e2e load：[note-true-core-x6-lake-recipe-e2e-2026-10-02.md](note-true-core-x6-lake-recipe-e2e-2026-10-02.md)
- #309 边界：[note-true-core-x6-lake-boundary-2026-10-02.md](note-true-core-x6-lake-boundary-2026-10-02.md)
- CLI 历史 synthetic note：[note-minute-orders-cli-2026-09-29.md](note-minute-orders-cli-2026-09-29.md)
- TC5 菜单：[note-true-core-tc5-go-scope-2026-10-02.md](note-true-core-tc5-go-scope-2026-10-02.md)

**≠δ5 certified ≠R4；CLI lake ≠ host PASS；无写湖；无 MatchCore/Fees/simulate/loader 重写；永 opt-in；本刀 draft 勿合。**
