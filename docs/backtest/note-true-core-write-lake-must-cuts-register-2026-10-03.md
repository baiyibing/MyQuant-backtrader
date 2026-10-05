# 真核大票 · C-New · 生产写湖 MUST cuts 登记 · Human cut **A**（2026-10-03）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-03（Asia/Shanghai / CST） |
| tip 基线 | `6a4e6d7a`（master · #314 MERGED · Codex residual plan + A·X7 observe） |
| Human 裁断 | **A**：`owner=host/1.3`；本仓只登记 cuts，**不**实现生产写路径；`no_borrow`；`rollback=禁原地覆盖` |
| 顾问 | Kimi 只读排序首推 A（`reviews/KIMI_WRITE_LAKE_MUST_CUTS.md`，仓外 handoff；**建议 ≠ GO**） |
| 前置 | [#312](https://github.com/baiyibing/MyQuant-backtrader/pull/312) MERGED `3f7af6a2`（staging dry-run + MUST cuts **草案**）；[residual note](note-true-core-write-lake-residual-2026-10-02.md) |
| 本刀 | **docs-only 登记**；空 diff MatchCore / Fees / `simulate*` / source_loader / CLI / `views._FAMILIES` / 任何 writer |
| 硬约束 | ≠δ5≠R4；staging ≠ 生产写；本登记 ≠ 生产写授权；无 `--write-lake`；无 4090；永不 BOOKS；永 opt-in |

> **本 note = Human cut A 的仓内登记，≠ 生产写湖授权，≠ host PASS，≠ item-4 live，≠ 绿 R，≠ 借用 vendor Phase4/Phase5 收据，≠ 新身份 mint，≠ 本仓实现写路径。**  
> AGENTS.md：**Consume only**；外部下载与 vendor merge 在 OSkhQuant1.3。本 research fork 默认**不是**写方。  
> #312 staging dry-run 骨架仍是本仓边界；本刀不长生产写码、不改 staging 行为。

## 1. 目的

Human 在 Kimi 首推 A 后点名裁断：生产写湖 MUST cuts 按 **A** 落档。本刀把裁断写入 tip docs，便于后续残差与 host 链对照；**不**在本仓实施任何生产写路径。

| 本刀交付 | 明确不做 |
|---|---|
| 本登记 note（Human cut A 字段表） | 生产湖写入；`--write-lake`；探测盘符 |
| industry-index §7 / residual note 轻指针 | 改 MatchCore / Fees / `simulate` / source_loader / CLI |
| （可选）staging 包机器可读状态 — **本刀跳过**，防 scope creep | 4090；host PASS 填表；绿 R |
| | mint 新 contract / backend_id；改 `views._FAMILIES` |

## 2. Human cut **A** · 字段登记

| ID | 状态 | 登记措辞 |
|---|---|---|
| **owner** | **已裁 · A** | 生产写执行方 = **host agent / OSkhQuant1.3 download transport / vendor merge**（与 vendor 三票 Phase4 同归属）。**本 research fork 不是写方**；本仓仅登记 cuts 与维护 #312 staging dry-run 骨架。任何把写方改回本仓的裁断须具名说明 host/1.3 不能承担的理由，并同步修订 AGENTS.md「Consume only」句。 |
| **no_borrow_receipt** | **已裁 · A** | **不借** vendor 三票 Phase4/Phase5 PASS 收据作为本真核残差链的写权或验收证据；另链收据 ≠ 本链授权。本链若将来另开 host 写，须自有新 run / 新 receipt，结果允许 FAIL/BLOCKED，不得预定 PASS。 |
| **rollback** | **已裁 · A** | **禁原地覆盖**：写入只允许 **append-only** 新分区；任何替换既有分区须 **Human 具名批准 + 先落备份**（备份校验通过后才动目标）；同分区重跑默认拒绝而非覆盖。执行细节在 **host 链**。 |
| **target_pin** | **未裁** | 执行细节（湖根、underscore hive 标的、`{1m,1d}`、`dividend_type`、源 sha256）在 **host 链**裁断与钉死；**本仓不钉生产 pin**。缺 pin 不得在本仓或假借本仓名义写生产湖。 |
| **budget** | **已裁 · A 含义** | A 下 **本仓无新码刀**；H-TC8 **不为写路径重估**。host 侧预算由 host 链自理。「C 已开」不吞进原 1–2 人周。 |
| **no_write_flag_in_tip** | **仍锁（#312）** | tip **不得**长出生产 `--write-lake`；staging dry-run only，直至另具名且与本 A 一致的生产写 GO（预期在 host/1.3，不在本 fork）。 |
| **locks** | **仍锁** | 空 MatchCore / Fees / `simulate` / source_loader；≠δ5≠R4；**永不 BOOKS**；**永 opt-in**；无绿 R；**无 4090**（除非另 GO）。 |

### 显式非宣称

- 本登记 **≠** 生产写授权；未在 host 链完成 target_pin 等执行裁断前，任何生产写仍属越权。
- **#312 staging ≠ 生产写湖 ≠ host PASS**；本刀不升格 staging 报告，不补成功 `summary.json`。
- **不在本仓实现写路径**（adapter / writer / `--write-lake` / 湖 I/O）。

## 3. 与 Kimi / Codex 的关系

| 来源 | 角色 |
|---|---|
| Kimi `KIMI_WRITE_LAKE_MUST_CUTS.md` | 只读顾问；偏序 **A → C → D → B**；首推 A。**建议 ≠ GO**。 |
| Codex `CODEX_RESIDUAL_GO.md` | R2 写湖排最末（污染/覆盖最高）；与 A「本仓不写」一致。 |
| Human | 勾选 A 后本刀才落地；顾问文件不使任何 cut 自动实施。 |

## 4. 模块地图（本刀触及）

| 路径 | 角色 |
|---|---|
| `docs/backtest/note-true-core-write-lake-must-cuts-register-2026-10-03.md` | **本登记** |
| `docs/backtest/note-true-core-write-lake-residual-2026-10-02.md` | 页脚指针 → Human cut A registered |
| `docs/backtest/industry-state-acceptance-index-2026-09-28.md` §7 | 轻指针行 |
| `backtest/research/minute_orders_write_lake_staging/` | **空 diff**（本刀不改机器可读模板，避免码刀 creep） |
| `match.py` / `fees.py` / `simulate*` / `source_loader` / `cli.py` / `views` | **空 diff** |

## 5. 负面清单

| 禁止 | 说明 |
|---|---|
| 本仓生产写湖 | A 已裁 owner 出本仓 |
| `--write-lake` / 湖 I/O | 本 tip 永拒 |
| 借用 Phase4/Phase5 RECEIPT | no_borrow 已裁 |
| 原地覆盖分区 | rollback 已裁 |
| 本仓钉生产 target_pin | 未裁；属 host |
| 改 MatchCore / Fees / simulate / loader / CLI | locks |
| 4090 / host PASS / 绿 R / BOOKS 默认 | 另 GO 或永禁 |
| 新 contract / backend_id | 不 mint |
| 把本登记读成「可写了」 | 登记 ≠ 授权 |

## 6. 指针

- Staging 残差（#312）：[note-true-core-write-lake-residual-2026-10-02.md](note-true-core-write-lake-residual-2026-10-02.md)
- CLI lake（#311）：[note-true-core-cli-lake-2026-10-02.md](note-true-core-cli-lake-2026-10-02.md)
- TC5 菜单：[note-true-core-tc5-go-scope-2026-10-02.md](note-true-core-tc5-go-scope-2026-10-02.md)
- Industry index §7：[industry-state-acceptance-index-2026-09-28.md](industry-state-acceptance-index-2026-09-28.md)
- Kimi 顾问（仓外）：`/workspace/handoffs/minute_engine_true_core_new_20261002/reviews/KIMI_WRITE_LAKE_MUST_CUTS.md`

**≠δ5 certified ≠R4；Human cut A registered ≠ 生产写湖 ≠ host PASS；#312 staging 仍是本仓边界；空 MatchCore/Fees/simulate；永 opt-in；本刀 draft 勿合直至 Human「合」。**
