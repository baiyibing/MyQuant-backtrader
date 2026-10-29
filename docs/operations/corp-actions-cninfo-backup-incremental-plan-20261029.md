# C0 — CNINFO backup incremental plan while Wind 401（2026-10-29）

Human t205u 要求在 Wind/Kimi 401 期间规划 CNINFO 备份路径；本次授权仅为 **C0 docs-only**。本文冻结后续讨论的默认提案，不授权编码、拉数、调度、消费方切源或写湖。C1+ 均须另取 Human GO；本 PR 开出后停下，不合并。

## 1. Trigger / status

- [#523](https://github.com/baiyibing/MyQuant-backtrader/pull/523) 已 squash 至 `20b4768cb21462fc03b2663779a4fdedfcbab540`；[2026-10-28 增量状态](corp-actions-incremental-20261028-status.md) 记录 `kimi-datasource` → `wind_get_stock_events` 间歇性 401，同一会话正常响应与 401 混杂，4090 / Thinkpad 均复现。当前按上游 Wind 通道不可用处置，不能靠本机换凭证、换模型或换机解决。
- 该状态记录的增量窗 **2026-10-07 → 2026-10-28 仍为 0 accepted codes**；本文没有重跑或新增 accepted 证据。
- [#501](https://github.com/baiyibing/MyQuant-backtrader/pull/501) 基础快照 `bt_corp_actions_20261006` **仍有效**：2014-01-01 → 2026-10-06，2774 码 lineage，21779 events；Wind 基础湖为 `E:\stock_data\corp_actions`。这些是既有交接证据，不是本次对 4090 磁盘的重新验收。

## 2. Policy

- **Wind/Kimi incremental 在可用时仍是 primary；CNINFO 仅为独立 backup candidate。** 401 不构成换主源授权；禁止自动晋升 CNINFO 为 primary，禁止声称 Wind 已被替代。
- **禁止覆盖、写入或合并至 Wind 湖 `E:\stock_data\corp_actions`、Wind 全量导出或任何 Wind incremental outdir。** CNINFO sandbox CSV 不得当作现有 Wind `assemble` / `prepare-merge` 的输入。
- **gmail / M5 不写湖**；本次不授予这些执行面生产路径访问或湖发布能力。禁用 Cursor Cloud Agents，不做任何 lake writes。
- 1.3 旧可行性文档中的“CNINFO 主 / Wind 辅”仅为历史讨论目标，不是本刀授权；本计划遵守以上 Wind primary / CNINFO backup 边界。

## 3. Independent outdir contract（提案，未创建目录）

| 执行端 | CNINFO 独立输出根提案 |
| --- | --- |
| 4090 | `D:\exports\bt_corp_actions_cninfo_backup_YYYYMMDD` |
| Thinkpad（确有需要才另确认） | `E:\exports\bt_corp_actions_cninfo_backup_YYYYMMDD` |

这些是未来显式选择的 sandbox 路径示例，不是探盘规则或当前运行命令。新 run 使用独立目录；不得与下列目录相同、重叠或位于其内部，也不得向其覆盖或合并：

- `E:\stock_data\corp_actions`（Wind full lake）。
- `D:\exports\bt_corp_actions_20261006`（Wind full-pull）。
- `D:\exports\bt_corp_actions_incr_20261028`、`D:\exports\bt_corp_actions_incr_20261024` 及其他 `D:\exports\bt_corp_actions_incr_*`。
- Thinkpad 的 Wind run `E:\exports\bt_corp_actions_incr_20261028` 与重建湖 `E:\exports\corp_actions_lake`。

未来 C1 sandbox manifest 至少记录以下信息；这是待实现的证据合同，不能宣称现有 MVP 已全部满足：

| 项 | 规划要求 |
| --- | --- |
| 来源 | `source=cninfo:…`，例如 `cninfo:pdf:regex:<extract-version>`；不冒充 Wind |
| 窗口 | base `ask_end`、start/end、Asia/Shanghai 冻结日期；分别标明公告查询窗与事件 ex_date 接纳窗 |
| 宇宙 lineage | 原 full-pull / prior-run 的 `universe.txt` 路径、SHA256、2774 码计数；引用基线快照与哈希 |
| 溯源 | 公告 ID / URL、PDF / 文本哈希、known_at / fetch_at、extract / export 版本、拒绝与覆盖缺口证据 |
| 写湖权限 | **`lake_write_authorized=false`**；独立 outdir 与 sandbox 文件名；无生产发布含义 |

## 4. Frozen planning defaults（proposal only，不是 GO）

**Universe：** 沿用 Wind incr 的 **2774-code strategy-pool lineage**，从 full-pull / prior-run 的冻结 `universe.txt` 取值并校验哈希，保留 Wind 后缀。不得替换为当前策略池、全 A 宇宙或只有 2762 码的湖 listing fallback。3 码 MVP fixture 只作样本，不能充当该分母。

**Window：** 默认讨论口径对齐 Wind incremental：基础 manifest 的 **ask_end + 1 自然日 → today（Asia/Shanghai）**，在 run 建立时冻结。以本次规划日期 2026-10-29 和有效基线 `ask_end=2026-10-06` 为例，提案窗为 **2026-10-07 → 2026-10-29**；历史 Wind run 的 **10-07 → 10-28** 窗保持原样。C1+ 启动前须 Human 确认实际 end、universe 与独立 outdir，不能以本文自动延展或改写既有 run。

CNINFO 公告查询日期与 ex_date 接纳日期不能混用；现 MVP 是按 `known_at` 筛选本地语料的回放，不证明新增量窗的抓取覆盖。公告查询回溯、分页分母与 PIT 规则仍待 Owner 确认，不能因某窗无返回就宣称无事件或推进湖水位。

**Field / diff contract：** 后续逐字段与 Wind 基线比对，至少保留下列语义，不在 C0 修改 schema 或 adapter：

| 字段 | 对齐 / diff 要求 |
| --- | --- |
| `code` | 规范 Wind 后缀；核对发行人 / 代码身份 |
| `ex_date` | 除权除息执行日，精确日期对照；不能用公告日替代 |
| `cash_div_per_share` | 税前 CNY / 原持有股；公告“每10股派 X 元”归一为 `X / 10` |
| `bonus_ratio` | 每原持有股新增送股数；“每10股送 Y 股”归一为 `Y / 10` |
| `transfer_ratio` | 每原持有股新增转增数；“每10股转 Z 股”归一为 `Z / 10`；与送股分列 |
| `record_date` / `pay_date` | 有则保留并比对；缺失保持 NULL，不能静默用 ex_date 补齐 |
| `bonus_list_date` / `list_date` | 保留原公告上市日期及送 / 转不同上市日信息；缺失与合并政策待 Owner，不能推造可售日 |

Wind 已是每股单位，`0.3` 保持 `0.3`，不可再除以 10；NULL 与 0 不同。自然键按 Wind 存储约定记录为 **`(code, ex_date, cash, bonus, transfer)`**，后三项对应上述三个经济字段。同码同日但经济值不同须保留差异供审阅；该键不代替待签的事件身份、修订 / 取消链或 PIT 合同。现 MVP BT sandbox 列未完整保留 Wind 的独立 `transfer_ratio` / `source` 等列，不能据文件存在就认定 schema parity 或直接接入 BT `ExDivEvent`。

## 5. Existing MVP / sandbox map（OSkhQuant1.3，仅指针）

以下资产在 1.3 checkout `a389df96c895560a26b90aa0f5f27707af0fd948` 只读盘点；本仓不复制大树，不运行其 CLI，不据此扩大生产权限。

| 资产 | 1.3 路径 / 状态 |
| --- | --- |
| 可行性讨论 | [`OSkhQuant1.3/docs/operations/corp-actions-cninfo-feasibility-20261015.md`](https://github.com/baiyibing/OSkhQuant1.3/blob/master/docs/operations/corp-actions-cninfo-feasibility-20261015.md)；**不构成 encode GO**，旧主源设想不得覆盖 §2 |
| MVP CLI / extractor | [`oskh_disclosure.cli.corp_actions_mvp`](https://github.com/baiyibing/OSkhQuant1.3/blob/master/oskh_disclosure/cli/corp_actions_mvp.py)、[`oskh_disclosure/extractor_corp_actions.py`](https://github.com/baiyibing/OSkhQuant1.3/blob/master/oskh_disclosure/extractor_corp_actions.py)；本地冻结语料 replay，不是生产增量抓取器 |
| Fixtures | [`oskh_disclosure/tests/fixtures/corp_actions_mvp/`](https://github.com/baiyibing/OSkhQuant1.3/tree/master/oskh_disclosure/tests/fixtures/corp_actions_mvp)：**3 codes / 5 PDFs**（4 实施 + 1 预案）；便利样本不证明 2774 码覆盖 |
| 2026-10-15 reviews | `docs/architecture/reviews/2026-10-15/` 下的 [`corp-actions-mvp/`](https://github.com/baiyibing/OSkhQuant1.3/tree/master/docs/architecture/reviews/2026-10-15/corp-actions-mvp)、[`corp-actions-parity-audit/`](https://github.com/baiyibing/OSkhQuant1.3/tree/master/docs/architecture/reviews/2026-10-15/corp-actions-parity-audit)、[`corp-actions-spike/`](https://github.com/baiyibing/OSkhQuant1.3/tree/master/docs/architecture/reviews/2026-10-15/corp-actions-spike) |
| 2026-10-16 review | [`docs/architecture/reviews/2026-10-16/corp-actions-signoff-expand-prod/`](https://github.com/baiyibing/OSkhQuant1.3/tree/master/docs/architecture/reviews/2026-10-16/corp-actions-signoff-expand-prod)；目录名与历史产物不构成生产 GO |
| 生产域缺口 | [`oskh_disclosure/ingest_multi.py`](https://github.com/baiyibing/OSkhQuant1.3/blob/master/oskh_disclosure/ingest_multi.py) 的 `_DOMAINS_WITH_EXTRACTORS = {"hedge", "periodic_report", "earnings_express"}`；生产 `dividend` 域仍无已接线的公司行为结构化抽取，不能把 sandbox extractor 的存在视为生产完成 |

本计划的 **BT sandbox 导出文件名仅 `cninfo_bt_sandbox.csv`，绝不导出为生产 `corp_actions.csv`**；其他候选 / diff / manifest 证据留在独立 sandbox 内。旧 review 内同名历史文件不是本次接湖输入，也不授予重新导出生产文件名的权限。通用 paper-ingest fixture / 现有 disclosure jobs 不等于 corp-actions 湖增量或并行备份调度授权。

三份 OWNER_SIGNOFF 全部 **UNSIGNED / SIGNED_PENDING，`owner_signature=null`**：

| Pack | OWNER_SIGNOFF 指针 | 状态 |
| --- | --- | --- |
| mvp | [`docs/architecture/reviews/2026-10-15/corp-actions-mvp/OWNER_SIGNOFF.md`](https://github.com/baiyibing/OSkhQuant1.3/blob/master/docs/architecture/reviews/2026-10-15/corp-actions-mvp/OWNER_SIGNOFF.md) | UNSIGNED / SIGNED_PENDING；`owner_signature=null` |
| parity-audit | [`docs/architecture/reviews/2026-10-15/corp-actions-parity-audit/OWNER_SIGNOFF.md`](https://github.com/baiyibing/OSkhQuant1.3/blob/master/docs/architecture/reviews/2026-10-15/corp-actions-parity-audit/OWNER_SIGNOFF.md) | UNSIGNED / SIGNED_PENDING；`owner_signature=null` |
| signoff-expand-prod | [`docs/architecture/reviews/2026-10-16/corp-actions-signoff-expand-prod/OWNER_SIGNOFF.md`](https://github.com/baiyibing/OSkhQuant1.3/blob/master/docs/architecture/reviews/2026-10-16/corp-actions-signoff-expand-prod/OWNER_SIGNOFF.md) | UNSIGNED / SIGNED_PENDING；`owner_signature=null` |

Git author、AI 角色、测试通过或回归匹配均不是 Owner 手签；本次不填写身份、时间戳或签收结论。

## 6. Knife ladder（docs freeze，本刀不实现）

| 刀 | 范围 / 进入条件 |
| --- | --- |
| **C0 ✅** | 本 PR：计划 + 两处文档指针，docs-only；不启动后续刀 |
| **C1 ✅** | Human **t212u** GO → OSkh [#1238](https://github.com/baiyibing/OSkhQuant1.3/pull/1238) squash → `0b2268706`（path guard + `run_manifest.json` `lake_write_authorized=false` / `crawl_complete=false` + `cninfo_bt_sandbox.csv`；fixture CI；OWNER 仍 UNSIGNED）。C2/C3/合湖仍须另 GO |
| **C2 — Owner hand-sign / parity**（部分：工具 ✅；Wind 小样本 diff ✅ UNSIGNED；手签 ⏳） | Human **t215u** GO → OSkh [#1239](https://github.com/baiyibing/OSkhQuant1.3/pull/1239) squash → `2925a307f`：离线 parity diff CLI `oskh_disclosure.cli.corp_actions_parity_diff` + [C2 交接页](https://github.com/baiyibing/OSkhQuant1.3/blob/main/docs/operations/corp-actions-cninfo-parity-c2-20261029.md)。**更正（Human t217u）**：先前“600519.SH / 603888.SH pending、NO_OVERLAP”系读了本机过期 checkout（#451 部分快照 9096 行）；本仓 master 的 #501 完整快照（21779 行，sha `6afe807a…`）即 Wind 样本。证据包 OSkh [#1240](https://github.com/baiyibing/OSkhQuant1.3/pull/1240)：官方 adapter 导出仅 000001.SZ（不在 Wind 2774 宇宙）→ NO_OVERLAP；pre-adapter 复核 4 事件 → MATCH 2（603888 2025-07-25 / 2026-07-23）、FIELD_DIFF 1（600519 2025-06-26 现金/日期一致，仅送/转 NULL_VS_ZERO）、WIND_ONLY 5 为 fixture 语料缺口，非召回结论。仍 UNSIGNED。**C2-wide（Human t221u）**：从本仓 #501 Wind CSV 选 38 码（SH/SZ 主板、创业板、科创板；147 Wind 事件），polite 抓取 152 份 CNINFO 实施公告至 guarded `bt_corp_actions_cninfo_backup_20261029`（不写湖，Wind hash 前后不变），证据包 OSkh [#1241](https://github.com/baiyibing/OSkhQuant1.3/pull/1241)：pre-adapter MATCH 49 / FIELD_DIFF 78（仅 NULL_VS_ZERO 56、NULL_VS_VALUE 20、AMOUNT_DIFF 2）/ CNINFO_ONLY 0 / WIND_ONLY 20（均为 extractor 缺 ex_date，含全部科创板）；adapter 仅接受 24 行（均仅 NULL_VS_ZERO），拒绝 128（needs_review 76、未写不送不转 51、merge 1）——接受策略未改，交 Owner。**v7 复跑（Human 15:07 / 16:30 GO）**：OSkh #1242 → `2eb1e86bb`（parity v2：MATCH_NULL_AS_ZERO t222u / MATCH_WIND_ROUND4 t224u）、#1243 → `5d2d1737e`（extractor mvp-v7 + needs_review 策略 + `review_list.csv`）、#1244 → `50d5ba1d9`（adapter：仅当现金与除权/登记/派息日齐全一致时，空送/转按 0 接受，Human 决定）后，离线复用 152 份 PDF 复跑，Wind hash 前后不变；证据包 OSkh [#1245](https://github.com/baiyibing/OSkhQuant1.3/pull/1245)：adapter 接受 79 / 拒绝 73（needs_review 72、merge 1，`review_list.csv` 73 行）；Run A MATCH 77 / FIELD_DIFF 0 / WIND_ONLY 70（为 adapter 拒绝，非召回缺失）；pre-adapter Run B MATCH 128 / FIELD_DIFF 19（CNINFO 现金空 10、送股上市日空 10、转增 1；AMOUNT_DIFF 0）/ WIND_ONLY 0。**v8 复跑（Human t230u / #1246 → `7cab5af1a`）**：mvp-v8 PDF 核验完整差异化分红 + 现金股息；离线复跑证据 OSkh [#1247](https://github.com/baiyibing/OSkhQuant1.3/pull/1247)：adapter 110 接受 / 42 拒绝；Run A MATCH 107 / FD 0 / WIND_ONLY 40；Run B MATCH 133 / FD 14 / WIND_ONLY 0；v7 空 missing_fields 35 条中 22 条出 review_list、13 条仍阻断（rights/revision/merge/300171 日期核验失败）；剩余 FD 为现金 ambiguous 5 + Wind 惯用上市日=除权日 10 + transfer 1，未发明上市日。仍 UNSIGNED。**v9（Human 02:26 GO / #1248 → `b8708a3bc`）**：PDF 无红股/转增上市日时填 ex_date（Wind 惯例；有明示日不覆盖）；证据 [#1249](https://github.com/baiyibing/OSkhQuant1.3/pull/1249)：adapter 114/38；Run A MATCH 111 / FD 0 / WO 36；Run B MATCH 142 / FD 5 / WO 0；v8 的 10 条 bonus_list_date NVV 中 9 条清除、1 条（301266 歧义）保留。仍 UNSIGNED。三份 OWNER_SIGNOFF 仍 UNSIGNED，手签仅 Human。原定义：Owner 独立手签 mvp / parity，固定哈希与逐事件处置；在 **#501 基线窗内**做小样本 Wind diff，形成日期 / 金额 / 单位 / 拒绝证据与 BT 消费者验收。expand-prod 签收与代表性分母仍须按其 checklist 补齐，不能由小样本自动关闭 |
| **C3 — parallel backup schedule** | 仅 Human 明确 **“backup may run in parallel / backup 可并行” GO** 后，才可另案开独立备份调度；仍无主源切换或湖发布权限。任何 primary swap 须更晚的 **“main-source switch / 主源切换” GO** 及适用签收，不能由 C3 推定 |

## 7. Blockers

| 阻塞 | 证据 / 解锁条件 |
| --- | --- |
| Wind 401 upstream | #523 / 10-28 状态已跨机复现；不是本机 credential fix 可解，联系 Kimi 支持并取得恢复证据 |
| OWNER_SIGNOFF UNSIGNED | mvp / parity / expand-prod 均 `owner_signature=null`；须真实 Owner 手签、哈希绑定及未决政策处置 |
| gmail / M5 无生产湖访问 / 写入能力 | 不能到达或写 `E:\stock_data\corp_actions`；本次无写湖授权，不以本执行面代做 4090 发布 |
| CNINFO → BT `ExDivEvent` 未验收 | 无已签 consumer acceptance / schema parity；送转合并、缺 pay/list 日期等仍未定，sandbox 不可直接充当 Wind 增量 |
| Coverage denominator / PIT / identity 待 Owner | 可行性 **§4.1 / §7** 的分母哈希、事件身份 / 修订、可知时间、日期与单位容差仍待签；3 码 / 5 PDF 不构成市场覆盖，局部 diff 不证明全宇宙召回 |

## 8. Wind resume conditions

1. 继续建议 **联系 Kimi 支持**，确认 Wind 上游鉴权 / 账号绑定要求；取得真实恢复证据后，优先走既有 Wind incremental 路径。
2. 在**包含 #523 的 tip** 上续跑：优先 `D:\exports\bt_corp_actions_incr_20261028`（冻结 k3），或干净的 `D:\exports\bt_corp_actions_incr_20261024`（原 highspeed 窗）。#523 已包含 k3 白名单与 `skipped:` / 空 error 不烧 vendor attempt、全 skipped 会话 exit 2 的记账修正；不要用更旧 tip 的“No K3”说明否定该已授权 run。
3. 按[驱动文档](corp-actions-incremental-driver.md)检查 pending、冻结窗口 / base / universe 哈希；先确认无活跃进程，再处置该 run 的 stale lock。换机必须满足原路径 / 字节哈希合同，不能把 Thinkpad 重建湖与 4090 湖视为相同快照。
4. Wind 增量完成后 **assemble → prepare-merge → 单独 Human GO 才能谈湖发布（条目2）**。现驱动没有 apply / merge / publish 命令；prepare-merge 产物不等于已合湖，不推进现湖水位。
5. Wind 恢复后，CNINFO **C0 / 另获 GO 的 C1** 仍是并行备份工作，除非 Human 明确要求停止；Wind 恢复不自动取消它，也不自动授权 C1、C3 或换主源。

## 9. Explicit non-goals of C0

- 不修改 `scripts/data/pull_corp_actions_incremental.py`，不重写 driver、不切 vendor；无 Python / schema / test 代码变更。
- 不合并、不修改、不依赖 **PR #526**（L2 unrelated）；本 PR 也不合并。
- 不拉数、不写湖、不发布，不覆盖或合并 Wind full lake / full-pull / incremental outdirs；gmail / M5 无写湖授权。
- 不伪签 OWNER_SIGNOFF，不将 UNSIGNED 改为已签，不宣称消费者已接受或 Wind 已被替代。
- 不建立 scheduler job，不启用现有 job，不启动 Cursor Cloud Agents；C1+ 另取 Human GO。
