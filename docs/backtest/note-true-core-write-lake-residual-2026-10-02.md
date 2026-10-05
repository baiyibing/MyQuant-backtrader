# 真核大票 · C-New · 残差 R2 · 写湖 staging dry-run（2026-10-02）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-02（Asia/Shanghai / CST） |
| tip 基线 | `706a3487`（master · #311 CLI lake MERGED） |
| Human GO | **「GO 写湖」** = Codex R2 · 写湖 / Phase4 残差；本刀因 **本仓 consume-only** 与污染风险，落地为 **docs + staging dry-run 骨架 + MUST Human cuts**（**非**生产写湖） |
| 方案 | `/workspace/handoffs/minute_engine_true_core_new_20261002/`；顾问 [CODEX_RESIDUAL_GO](`/workspace/handoffs/minute_engine_true_core_new_20261002/reviews/CODEX_RESIDUAL_GO.md`)（仓外；R2 排最末） |
| 硬约束 | **不** mint 新经济合同 / 新 `backend_id`；`tool_id`≠backend_id；**无** `--write-lake` 生产旗；**不**写 `stock_data` / 配置湖根；空 diff MatchCore/Fees/`simulate`/source_loader/CLI；≠δ5≠R4；无 4090；永 opt-in；永不 BOOKS |
| PR | **#312 MERGED** `3f7af6a2` |

> **本 note ≠ 生产写湖授权，≠ host PASS，≠ item-4 live，≠ 绿 R，≠ 借用 vendor Phase4/Phase5 收据作本链写权，≠ 新身份 mint。**  
> 本仓 [AGENTS.md](../../AGENTS.md)：**Consume only**；外部下载与 vendor merge 在 OSkhQuant1.3。  
> 既有三票 Phase4 写湖 PASS 属 **vendor/host** 链（见 [vendor ingest PLAN](vendor-three-symbol-lake-ingest-2026-10-01/PLAN.md)）；**不得**借其 RECEIPT 宣称本真核残差已获生产写权。  
> 入口默认 / 绿 R·S 继续只链 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。

## 1. 目的

Human 点了「GO 写湖」。Codex 将该轴排在残差最末：物理污染/覆盖风险最高，且材料未证明「为消费已 pin 的湖数据」必须在本链再写一次。父任务也要求：**若范围过险且缺 Human 裁断，则开 docs+骨架并列出 MUST cuts**；并优先 staging/dry-run 或既有 Phase4 模式，而非盲写。

| 本刀交付 | 明确不做 |
|---|---|
| docs 残差说明 + MUST Human cuts 清单 | 生产湖写入；探测盘符；vendor merge |
| `tool_id=minute_orders_write_lake_staging` 骨架 | `--write-lake` 旗；覆盖已有分区 |
| 拒 `stock_data` / 配置湖根 / 写湖键 / production mode | 改 MatchCore / Fees / `simulate` / source_loader / CLI |
| 独立 tool 根 `staging_dry_run_report.json` + `MUST_HUMAN_CUTS.json` | 产成功 `summary.json`；host PASS；绿 R |
| 合成测例（无湖 I/O） | 4090；借用 Phase4 RECEIPT 升格本链 |

## 2. MUST Human cuts（生产写前必裁 · #312 当时清单）

| ID | 裁断（#312 草案措辞；当前状态见页脚 Human cut A） |
|---|---|
| **owner** | 点名生产写执行方：host agent / 1.3 download transport / vendor merge — **默认不是**本 research fork |
| **target_pin** | 钉死湖根、underscore hive 标的、`{1m,1d}`、`dividend_type`、源 sha256；禁通配 |
| **no_borrow_receipt** | 不得借用三票 vendor Phase4/Phase5 PASS 收据作为本真核残差写权 |
| **rollback** | 点名回滚：禁止原地覆盖；新增或 Human 明示替换+备份 |
| **no_write_flag_in_tip** | 本 tip 刀不得长出生产 `--write-lake`；仅 staging dry-run，直至另具名生产写 GO |
| **locks** | 空 MatchCore/Fees/simulate/loader；≠δ5≠R4；永不 BOOKS；永 opt-in；无绿 R；无 4090（除非另 GO） |
| **budget** | 按 H-TC8 **单独重估**；「C 已开」不吞进原 1–2 人周 |

#312 机器清单仍是当时草案（`MUST_HUMAN_CUTS.json` 本刀不改）。Human cut A 已登记于 [note-true-core-write-lake-must-cuts-register-2026-10-03.md](note-true-core-write-lake-must-cuts-register-2026-10-03.md)：owner=host/1.3（本仓不是写方）、no_borrow_receipt、rollback=禁原地覆盖、budget=本仓无新码刀已登记；target_pin **未裁**（host 链）；no_write_flag / locks 仍锁。登记 ≠ 生产写授权。target_pin 未裁且无另具名生产写 GO 前，任何生产写仍越权。

## 3. 如何调用（staging dry-run）

```bash
python scripts/research/run_write_lake_staging_dry_run.py --help

python scripts/research/run_write_lake_staging_dry_run.py \
  --request /abs/path/to/request_ok.json \
  --parent /abs/path/to/parent \
  --run-id staging-example-01 \
  --print-must-cuts
# 产出: <parent>/backtest_output/minute_orders_write_lake_staging/<run-id>/
#   staging_dry_run_report.json
#   MUST_HUMAN_CUTS.json
# 根下无 summary.json；不写湖
```

### 拒收（exit 2）

- 请求含 `write_lake` / `lake_write` / `production_write` 等禁键
- `mode≠staging_dry_run`
- `--parent` / `--request` 非绝对路径
- out-dir 含 `stock_data` 路径组件，或落在配置湖根（`OSKH_SOURCE_PARQUET_ROOT` 等）之下
- 同 `run_id` 重复写入（目录已存在）

### 测试

```bash
pytest tests/test_minute_orders_write_lake_staging.py -q
```

测例 **不**读生产湖、**不**写湖。

## 4. 模块地图

| 路径 | 角色 |
|---|---|
| `backtest/research/minute_orders_write_lake_staging/` | 本刀：policy + staging dry-run |
| `scripts/research/run_write_lake_staging_dry_run.py` | CLI |
| `scripts/research/vendor_to_lake_adapter.py` | **既有** Phase2 staging（优先复用模式；本刀不改） |
| `match.py` / `fees.py` / `simulate*` / `source_loader` / `cli.py` | **空 diff** |

## 5. 与既有 Phase4 的关系

| 链 | 状态 | 与本刀 |
|---|---|---|
| Vendor 三票 Phase2 staging | tip 已有 adapter；dry-run 恒 true | **模式参考**（路径防护 / 独立 staging） |
| Vendor 三票 Phase4 写湖 | host PASS（另链 RECEIPT） | **不得**借为真核 R2 写权 |
| Vendor Phase5 研究读湖 END | 已交付（研究消费） | 只读消费；无回写 |
| 真核 #309/#310/#311 | 只读边界 / e2e / CLI lake | **不**写湖；本刀仍不解锁生产写 |

若 Human 最终裁「生产写由 host + vendor adapter 执行」，本真核残差可在 cuts 登记后 **停在 staging 骨架**，不必在本仓实现写路径。

## 6. 负面清单

| 禁止 | 说明 |
|---|---|
| 本刀写生产湖 | AGENTS consume-only；须另具名生产写 GO + owner |
| `--write-lake` 旗 | 本 tip 永拒 |
| 借用 Phase4 RECEIPT | 另链证据 ≠ 本链授权 |
| 改 MatchCore / Fees / simulate / loader / CLI | H-TC3/4/5 |
| 4090 / host PASS 填表 | 另 R3 |
| BOOKS 默认 / 绿 R | H-TC9 |
| 新 contract / backend_id | 不 mint；`tool_id` 独立 |
| 成功 `summary.json` | 研究成交冒充禁 |

## 7. 指针

- Codex 残差排序（R2 最末）：handoff `reviews/CODEX_RESIDUAL_GO.md`
- CLI lake（#311）：[note-true-core-cli-lake-2026-10-02.md](note-true-core-cli-lake-2026-10-02.md)
- X6 e2e（#310）：[note-true-core-x6-lake-recipe-e2e-2026-10-02.md](note-true-core-x6-lake-recipe-e2e-2026-10-02.md)
- Vendor staging：[vendor-three-symbol-lake-ingest-2026-10-01/PLAN.md](vendor-three-symbol-lake-ingest-2026-10-01/PLAN.md)
- TC5 菜单：[note-true-core-tc5-go-scope-2026-10-02.md](note-true-core-tc5-go-scope-2026-10-02.md)
- **Human cut A registered（2026-10-03）**：[note-true-core-write-lake-must-cuts-register-2026-10-03.md](note-true-core-write-lake-must-cuts-register-2026-10-03.md) — owner=host/1.3；本仓只登记 cuts、不实现生产写路径；no_borrow；rollback=禁原地覆盖；target_pin **未裁**（host 链）；本登记 ≠ 生产写授权

**≠δ5 certified ≠R4；#312 已合；staging dry-run ≠ 生产写湖 ≠ host PASS；无 MatchCore/Fees/simulate 重写；永 opt-in；Human cut A 已登记 ≠ 本仓写权。**
