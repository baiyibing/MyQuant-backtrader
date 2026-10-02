# 真核大票 · C-New · R3 · 4090 / host attestation 边界（2026-10-03）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-03（Asia/Shanghai / CST） |
| tip 基线 | `c7226a00`（master · #315 MERGED · Human cut A 写湖登记） |
| Human GO | 残差点名 **4090**（R3 / item-4）。本刀 = **attestation 边界登记**，**不是** live 跑，**不是** host PASS |
| 顾问 | Codex `CODEX_RESIDUAL_GO.md` R3：取证须独立范围/材料/验收；结果允许 FAIL/BLOCKED；**不得预订 PASS**；不宣称宿主已就绪 |
| 合同锚 | [ingress §6](note-l2-lake-source-ingress-b-l2-01-2026-09-29.md)（item-4 live 草图）；[residual plan](note-true-core-codex-residual-plan-2026-10-02.md) R3 行 |
| 本刀 | **docs-only**；空 diff MatchCore / Fees / `simulate*` / source_loader / CLI / `views._FAMILIES` |
| 硬约束 | ≠δ5 certified ≠R4；**不**翻 `r4_authorized`；**不**调度 B-L2 R4；无生产写湖（Human cut A：owner=host/1.3）；无绿 R；永 opt-in；永不 BOOKS；数量单位仍是 **股** |

> **本 note = R3 边界登记，≠ item-4 live，≠ host PASS，≠ L2 lake PASS，≠ 绿 R，≠ 借用任何既有宿主收据，≠ 本 PR 已派 4090bot。**  
> 物理跑机只属于 **4090bot**（宿主），且须在下表「未裁」项具名之后另说「开 4090」。本 Bot VM **不**发明跑数、**不**探盘、**不**填 PASS。  
> #307 Fixture PASS ≠ lake PASS；#309 `lake_boundary_attested_not_host_pass` ≠ host PASS；#310 `lake_recipe_e2e_loaded_not_host_pass` ≠ host PASS；#311 CLI `--evidence-level=lake` 成功 ≠ host PASS / item-4 live。

## 1. 目的

Human 把残差下一刀点名为 4090 / host attestation。Codex 把该轴定义为「该宿主、该数据是否验收通过」。验收对象是**新的宿主收据**，不是仓内文档或已合 PR。窗口、标的、recipe pin、跑机 tip 均未裁，现在派 4090 等于替 Human 发明一次 live。因此本刀只把边界写入 tip：**什么算收据、什么绝不升格、live 发车前还缺哪些具名 cut**。

| 本刀交付 | 明确不做 |
|---|---|
| 本边界 note（已钉 / 未裁表） | 4090bot 实跑；任何宿主命令；探盘符 |
| industry-index §7 + residual plan 轻指针 | 填 host PASS / item-4 PASS / 绿 R |
| | 借 B-L2 R3（tip `a268e11`，verdict 仍非本链 PASS）、R4 packs、分钟灵敏度 batch 收据、vendor Phase4/Phase5 |
| | 生产写湖；改 MatchCore / Fees / `simulate` / source_loader / CLI |
| | mint 新 contract / backend_id；开 X2–X5；TopK/byte 盘点 |
| | 把 ingress §6 的验收草图在本刀执行 |

## 2. 已钉（本边界 · 不待再裁才成立）

| ID | 登记 |
|---|---|
| **knife_kind** | docs 边界。本 PR 的完成条件 = 登记打开。**不是** live 验收完成。 |
| **verdict_vocab** | 将来收据的终态只允许 **PASS / FAIL / BLOCKED / NOT_RUN**（及逐格未覆盖）。`returned`、exit 0、非零 fills、`summary.json` **任一单项都不足以总 PASS**。本登记**预填零个 PASS**。 |
| **no_borrow** | 既有收据（B-L2-01 R3/R4、分钟灵敏度 4090 batch、vendor Phase4/Phase5、#307/#309/#310/#311 工件）**不得**抄成真核 R3 PASS。新 run 须自有 GO、run id、code sha、源/输入/工件 hash。 |
| **not_delta5_not_r4** | 本轴 ≠δ5 certified ≠R4。**不**翻 `r4_authorized`；**不**把本 GO 读成「开 R4」或 B-L2 重冻结。 |
| **no_write** | Human cut A 仍在：生产写 owner=host/1.3；本 fork 不写湖。R3 **不**附带写湖。缺分区就 BLOCKED，不补行情。 |
| **identity** | 不 mint 新经济合同 / `backend_id`。`tool_id` ≠ `backend_id`。复用标签仍是研究合同 v0 (L2-S0) + `minute_orders_research_v1`，除非另刀另 mint。 |
| **locks** | 空 MatchCore / Fees / `simulate` / source_loader；比较状态保持 `no_ssot_compare_authorization`；**永不 BOOKS**；**永 opt-in**；绿 R 仍禁。数量口径是 **股**，不在本刀改单位。 |
| **runner** | 物理执行者只能是 **4090bot**（宿主机）。本 Bot VM 与本 PR **不派车**。 |
| **budget** | H-TC8 的 1–2 人周**不含** 4090。本刀是 docs，**不**把 live 成本记进该预算，也**不**替 Human 估宿主工时。 |

## 3. 未裁（未齐之前禁止派 4090bot）

| ID | 状态 | 停点 |
|---|---|---|
| **window** | **未裁** | ingress 默认提案 `20251023`–`20251104` 状态是 **proposed，待 host attestation**，不是已验真窗口。本仓不把它升成 R3 pin。 |
| **symbols** | **未裁** | 未点名代码与板块过滤前，不得开跑。 |
| **recipe_pin** | **未裁** | 须先封存 recipe、源清单与 `expected_sha256`。缺 pin、dirty pin、非 lake+END/`bucket_end` → **BLOCKED/NOT_RUN**，不改输入补洞。 |
| **code_tip** | **未裁** | 宿主跑机 tip 须 Human 点名且 `dirty=false`。本 PR 基线 `c7226a00` 只是登记基线，**不是**已认证跑机 tip。 |
| **evidence_path** | **未裁** | #311 CLI lake 是来源选择，成功落盘仍是 S4 `hybrid` + `host_attestation_status=not_certified_by_writer`。是否用 CLI、loader-only，还是 ingress §6 的 native↔L1 对照，须另点名。未点名不得默认开 CLI 当验收。 |
| **output_root** | **未裁** | 宿主新目录由 4090bot 在发车 GO 里写明。本仓不探盘、不写 `E:\` / `D:\` 默认。 |
| **spot_oracle** | **未裁** | ingress §6 的容量/expiry/T+1/fee/mark 手算是 **live 验收草图**，不是本刀交付。未裁范围前不做，也不用被测核或旧引擎生成 expected。 |

缺上表任一项而发车 = 越权。允许的下一句是 Human「开 4090」并逐项点名；在那之前 4090bot **不应**被派。

## 4. 与已合刀的证据等级（升格禁止）

| 已合 | 原状态常量 / 含义 | 对本 R3 |
|---|---|---|
| #307 | `fixture_pass_not_lake_pass` | 仍 ≠ lake PASS ≠ host PASS |
| #309 | `lake_boundary_attested_not_host_pass` | 边界 ≠ host PASS |
| #310 | `lake_recipe_e2e_loaded_not_host_pass` | load ≠ host PASS；不得补成功 `summary.json` 冒充 |
| #311 | CLI `lake` → S4 `hybrid`；`not_certified_by_writer` / `not_assessed` | 研究运行完成 ≠ item-4 live |
| #312 | `write_lake_staging_dry_run_not_production_write` | staging ≠ 生产写 ≠ host PASS |
| #315 | Human cut A 登记 | 登记 ≠ 写授权 ≠ 本 R3 |

## 5. 模块地图（本刀触及）

| 路径 | 角色 |
|---|---|
| `docs/backtest/note-true-core-r3-host-attestation-boundary-2026-10-03.md` | **本边界** |
| `docs/backtest/note-true-core-codex-residual-plan-2026-10-02.md` | R3 行：边界登记 ≠ live |
| `docs/backtest/industry-state-acceptance-index-2026-09-28.md` §7 | 轻指针 |
| `match.py` / `fees.py` / `simulate*` / `source_loader` / `cli.py` / `views` | **空 diff** |

## 6. 负面清单

| 禁止 | 说明 |
|---|---|
| 本 PR 或本 Bot VM 跑 4090 | 未裁项未齐；且执行者不是本 VM |
| 填写 host PASS / item-4 live PASS | 结果不得预订 |
| 借用别票宿主收据 | no_borrow |
| 翻 `r4_authorized` / 调度 R4 | ≠δ5≠R4 |
| 生产写湖 / `--write-lake` | Human cut A |
| 改 MatchCore / Fees / simulate / loader / CLI | locks |
| 绿 R / BOOKS 默认 / 第二价格 | 永禁或 H-TC3 |
| 新 contract / backend_id；X2–X5 | 另刀 |
| 把本登记读成「宿主已通过」 | 登记 ≠ 收据 |

## 7. 指针

- Ingress item-4 草图：[note-l2-lake-source-ingress-b-l2-01-2026-09-29.md](note-l2-lake-source-ingress-b-l2-01-2026-09-29.md) §6
- Residual plan：[note-true-core-codex-residual-plan-2026-10-02.md](note-true-core-codex-residual-plan-2026-10-02.md)
- CLI lake（#311）：[note-true-core-cli-lake-2026-10-02.md](note-true-core-cli-lake-2026-10-02.md)
- 写湖 cut A（#315）：[note-true-core-write-lake-must-cuts-register-2026-10-03.md](note-true-core-write-lake-must-cuts-register-2026-10-03.md)
- Industry index §7：[industry-state-acceptance-index-2026-09-28.md](industry-state-acceptance-index-2026-09-28.md)

**≠δ5 certified ≠R4；本边界 ≠ item-4 live ≠ host PASS；未派 4090bot；无写湖；空 MatchCore/Fees/simulate；永 opt-in；数量为股；本刀 draft 勿合直至 Human「合」。**
