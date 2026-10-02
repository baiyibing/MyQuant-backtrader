# 真核大票 · C-New · TC5 · 扩展包 GO / 范围说明（2026-10-02）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-02（Asia/Shanghai / CST） |
| tip 基线 | `d0804d09`（master · #309 X6 真湖边界 MERGED；前序 #307 合成） |
| Human GO 本刀 | 「开下一刀」→ **TC5 docs-only 范围/裁断单**；**不** mint 新 contract/backend_id；**不**开工码轴；等 Human **点名下一轴** 后才有实施 GO |
| 方案 | `/workspace/handoffs/minute_engine_true_core_new_20261002/`；合同锚 [TC1](note-true-core-c-new-tc1-contract-2026-10-02.md) §4–§5 / PLAN §4 TC5 |
| 硬约束 | **本 PR 只 docs**；复用研究合同 v0 (L2-S0) + `minute_orders_research_v1` **标签**；≠δ5≠R4；无写湖；无 4090；无 Compat；H-TC3/4/5/9 仍锁；空 diff MatchCore/Fees/`simulate` |
| PR | **#308** 本刀合入（docs-only；码轴仍须独立实施 GO） |

> **本 note ≠ 实施 GO，≠ 新经济合同，≠ 绿 R，≠ 真湖 PASS，≠ fill-policy。**  
> TC5 任一码轴须 **独立 GO +（触及 S0 排除时）新 contract 字符串 + 新 backend_id + 增量 oracle**。本刀只列菜单、回填滞后指针。

## 1. 已合进度（至 tip `d0804d09`）

| 阶段 | PR | tip / 备注 |
|---|---|---|
| TC1 合同冻结 docs | [#303](https://github.com/baiyibing/MyQuant-backtrader/pull/303) MERGED | docs-only；H-TC* 落仓 |
| TC2 窄 X1 | [#304](https://github.com/baiyibing/MyQuant-backtrader/pull/304) MERGED | 核外冻结 LIMIT；同 v0 backend |
| TC3 具名消费者 | [#305](https://github.com/baiyibing/MyQuant-backtrader/pull/305) MERGED | CLI/HELP 闭环；永 opt-in |
| TC4 X8 对照桥 | [#306](https://github.com/baiyibing/MyQuant-backtrader/pull/306) MERGED | 撮合前意图↔X1；红标签 |
| X6 合成夹具/attestation | [#307](https://github.com/baiyibing/MyQuant-backtrader/pull/307) MERGED `f0620ace` | **非**真湖；`tool_id` only |
| X6 真湖 END/loader 边界 | [#309](https://github.com/baiyibing/MyQuant-backtrader/pull/309) MERGED `d0804d09` | 只读；`tool_id=minute_orders_x6_lake`；不写湖；不解锁 CLI lake |

PLAN 编号下一阶段 = **TC5 · 扩展包**。旁路轴 X6 **合成**已合；**真湖只读边界**已合 #309（H-TC5-NEXT=**C**）。其它码轴仍须独立实施 GO。

## 2. TC5 候选轴（请 Human 点名其一）

| 轴 | 要什么 | 是否自动带新身份 | 本刀态度 |
|---|---|---|---|
| **X2 · 更富订单**（stop / market-on-bucket / 日内模板） | 触及 S0 Lifecycle LIMIT-only | **必须**新 contract + 新 backend_id + oracle | 候选；**未点名 = 不开码** |
| **X3 · 第二价格**（OHLC 路径 / next-open） | 触及 S0 排除 B；H-TC3=**首包否** | **必须**新身份；对照另包 | **默认不推荐为首刀**（H-TC3） |
| **X4 · 多账户 / 组合层** | 触及 S0 单账户 | **必须**新身份 | 候选；未点名不开 |
| **X5 · 向量/批实例** | 同合同多 symbol 批跑 | 同合同+oracle 时可讨论；经济语义变仍须新身份 | 候选；吞吐须另证 |
| **X6 · 真湖 loader** | 相对 tip `source_loader` 湖路径交付 | **不**用合成刀冒充；须 **具名 GO**；与 #307 合成差分分开 | **已点 C** → 只读边界已合 #309；**recipe e2e** 见 [e2e note](note-true-core-x6-lake-recipe-e2e-2026-10-02.md)（draft）；CLI lake / 写湖仍另 GO |
| **X7 · 观察面** | **新**投影入口；不塞 `views._FAMILIES`；观察 ≠ 绿 R | 加法型观察片可讨论同 backend 升 artifact；**禁止**伪装绿 R | 候选；H-TC6=可设计；实施仍须点名 |
| **其它** | — | — | 须新裁；勿塞进本表默许 |

### 2.1 仍锁定的横切约束（不因点轴而松）

| 锁 | 含义 |
|---|---|
| H-TC3 | 首包（及未另裁前）**不允许**第二种价格模型当默认下一刀 |
| H-TC4 | **默认不改** `simulate`；函数级 allowlist 是最后手段 |
| H-TC5 | MatchCore/Fees **旁路复用**；破坏现语义 → **新模块名** |
| H-TC9 | L2 / New **永 opt-in**；不以 BOOKS 默认为验收 |
| 命名 | adapter/`tool_id`/`comparison_id` ≠ 经济 `backend_id` |
| 产品 | 回测研究系统 ≠ 交易系统；≠δ5 certified ≠R4；绿 R 仍禁 |

## 3. 本 PR 交付 / 明确不做

| 本 PR（TC5 GO/scope docs） | 明确不做 |
|---|---|
| 进度表：TC1–TC4 + X6 合成已合 | 任何业务 Python / 测试 / CI / HELP_LOCK |
| TC5 轴菜单 + 点名裁断题 | mint 新 contract / 新 backend_id |
| industry §7 / TC1 / X6 note：**#307 MERGED** 指针回填 | 开工 X2/X3/X4/X5/真湖/X7 码 |
| 重申 H-TC3/4/5/9 与空核 diff 纪律 | 改 MatchCore / Fees / `simulate` / VolumeCap |
| 本 docs 合入；H-TC5-NEXT=C 已点（#309）；**其它**轴仍须独立实施 GO | 写湖、4090、Compat、BOOKS 默认、绿 R |

**TC5 docs 退出标准 = Human 能勾选下一轴。** 勾选 ≠ 本 PR 自动授权写码；码刀须 **本 docs 已合 + 点名轴的独立实施 GO**（触及 S0 排除时另带新身份草稿）。

## 4. 请 Human 裁断（本刀开放题）

| ID | 问题 | 选项（草案仅供参考） |
|---|---|---|
| **H-TC5-NEXT** | TC5 **下一码刀**选哪一轴？ | **A** X7 观察面（新投影；无新经济语义优先） / **B** X2 富订单（须新身份草稿） / **C** X6 真湖（须具名湖 GO） / **D** X5 批跑 / **E** X4 多账户 / **F** 暂停扩展，只维护旁路 / **G** 其它（须写清） |
| **H-TC5-ID** | 若选触及 S0 排除的轴，新 `contract_version` / `backend_id` 命名草稿？ | 未裁前 **禁止**仓库内预占字符串当已批准身份 |
| **H-TC5-SIM** | 该轴是否需要改 `simulate`？ | 默认 **否**（H-TC4）；要改须函数级 allowlist 另票 |

**H-TC5-NEXT=C** 已裁（真湖只读边界 → #309 MERGED）。**≠** 批 X2–X5/X7 写仓，**≠** 批新合同 mint，**≠** 批写湖 / CLI lake unlock（均须另 GO）。recipe e2e 见 [e2e note](note-true-core-x6-lake-recipe-e2e-2026-10-02.md)。

## 5. 负面清单（本 PR diff 须空）

| 面 | 禁止 |
|---|---|
| `match.py` / `fees.py` | 任何改动 |
| `csv_minute_backtest.simulate` / `simulate_v7` | 任何改动 |
| VolumeCap / clamp / 完成桶共享 | 借本刀改共享核 |
| 旧 L1 `_ENTRIES` / `views._FAMILIES` | 改成事件宿主或塞 New |
| 新 contract / 新 backend_id 落码 | 本刀不 mint |
| 真湖 / 4090 / host attestation PASS | 须另具名 GO |
| 成功 `summary.json` / 绿 R / NAV 混比 | 永不因本 docs |

## 6. 指针

- TC1 合同：[note-true-core-c-new-tc1-contract-2026-10-02.md](note-true-core-c-new-tc1-contract-2026-10-02.md)
- TC2 X1：[note-true-core-tc2-x1-intent-adapter-2026-10-02.md](note-true-core-tc2-x1-intent-adapter-2026-10-02.md)（#304）
- TC3 消费者：[note-true-core-tc3-named-consumer-2026-10-02.md](note-true-core-tc3-named-consumer-2026-10-02.md)（#305）
- TC4 X8：[note-true-core-tc4-x8-compare-bridge-2026-10-02.md](note-true-core-tc4-x8-compare-bridge-2026-10-02.md)（#306）
- X6 合成 attestation：[note-true-core-x6-synthetic-attestation-2026-10-02.md](note-true-core-x6-synthetic-attestation-2026-10-02.md)（#307 MERGED）
- X6 真湖只读边界：[note-true-core-x6-lake-boundary-2026-10-02.md](note-true-core-x6-lake-boundary-2026-10-02.md)（#309 MERGED）
- industry 索引 §7：[industry-state-acceptance-index-2026-09-28.md](industry-state-acceptance-index-2026-09-28.md)
- 方案 handoff（本机外部）：`/workspace/handoffs/minute_engine_true_core_new_20261002/`

**≠δ5 certified ≠R4；无 MatchCore/Fees/simulate 重写；无写湖；无新合同 mint；本 docs 合入。H-TC5-NEXT=C 已点（#309）；其它码轴仍须独立实施 GO。**
