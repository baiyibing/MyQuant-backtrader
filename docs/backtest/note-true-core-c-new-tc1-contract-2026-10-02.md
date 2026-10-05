# 真核大票 · C-New · TC1 合同冻结（2026-10-02）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-02（Asia/Shanghai / CST） |
| tip | `e64802bb7df070fcf44de3c52d854bdeddaac373`（master · #302 U1 MERGED） |
| Human GO | 锁定全部 **H-TC*** + **H-U6=New** 为方案推荐；**H-TC1=C**（仅 TC1 docs 先）；开本 docs draft；**勿合**，等「合」 |
| 方案 | `/workspace/handoffs/minute_engine_true_core_new_20261002/`（`PLAN.md` / `COMPARISON.md` / `EXEC_ZH.md` / `reviews/R1_SYNTHESIS.md`） |
| 仓内落点 | 本 note；轻指针见 [U1 note](note-minute-engine-unify-ceiling-u1-2026-10-02.md) / [engine-positioning §3.4](engine-positioning-ssot.md) / [industry-state §7](industry-state-acceptance-index-2026-09-28.md) / [L1/L2 边界 §7](note-l1-l2-research-engine-boundary-2026-09-28.md) |
| 硬约束 | **docs-only**；**不**改 MatchCore / Fees / `simulate` / VolumeCap·clamp·完成桶；≠δ5 certified ≠R4；无写湖；无 4090；无业务码；本 PR **无** simulate/MatchCore 重写 |

> **本 note ≠ 第二套成交默认表，≠ 绿 R 资格认证。** 入口默认 / 绿 R·S / 红混比继续只链 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。**同 facade 返回类型 / 同 PIN ≠ 绿 R。**

## 1. 锁定裁断（H-U6 + H-TC1…H-TC9）

| ID | 锁定 | 含义（执行口径） |
|---|---|---|
| **H-U6=New** | 主路径 = **C-New**（非 Compat） | 干净可用 New 研究核；**不要求**旧入口 byte-compat；绿 R 混比仍禁 |
| **H-TC1=C** | 首包增量 = **仅 TC1 docs** | 本 PR 只落合同冻结 + 权威交接；**零核改**；接线/码刀另 GO |
| **H-TC2** | 冻 v0 + 现 backend；增量 = **新 contract + 新 backend_id** | 经济语义变必须新身份；禁止未限定「v1/v2」混指 |
| **H-TC3=否** | 首包**不允许**第二种价格模型（X3） | 对照需求另包 + 新 backend |
| **H-TC4=默认否** | **禁止**默改 `simulate` | 本 PR 只写负面清单；函数级 allowlist 须另票 |
| **H-TC5=复用** | MatchCore / Fees **旁路复用** | 不改写 `match_candidates` / `compute_bucket_capacity` 现语义；破坏性 → 新模块名 |
| **H-TC6** | X7 观察面可进 TC1 **设计** | 实施用**新**投影入口；不塞进现有 `views._FAMILIES`；非本 PR 阻塞 |
| **H-TC7** | **不设**旧书迁移 KPI / 关停日程 | 自愿红标签对照；旧结果不是 New 正确性唯一标尺 |
| **H-TC8** | 不改 v0 时粗估 **1–2 人周** | 仅覆盖合成 oracle + 消费者接线；不含真湖/4090；改核或真湖则重估 |
| **H-TC9=否** | **不**重裁 H-U3 | L2 / New 核 **永 opt-in**；改默认须另裁覆盖 H4=A |

R1 四席（Kimi / Codex / Grok / Claude）：Codex+Grok 首轮 REQUEST_CHANGES → MUST-FIX 已回填 handoff；Kimi/Claude APPROVE_WITH_NITS。**评审 APPROVE ≠ 实施 GO**；本 PR 仅落仓 Human 已锁合同边界。Astra ≠ 独立席。

### 1.1 与 U1 的覆盖关系（权威交接）

| 先前（U1 #302） | 本票（TC1） |
|---|---|
| **H-U5=暂不**真核 | → **开**真核合同设计阶段（本 docs）；**覆盖**开票门，**不**宣称 unify 方案 §3.3 证据条件已齐 |
| **H-U6=N/A** | → **H-U6=New** |
| **H-U1=B** 对旧入口 | → **保留**：CSV/v7/JR/grid 仍 Thin-adapter 上限 |
| **H-U4** 禁默改 `simulate`（为统一旧入口） | → 旧路径仍禁默改；本 New 票默认亦不改（H-TC4） |
| L2 三 entry v0 行为 | → **旁路冻结**（不在覆盖范围） |

> Human GO 覆盖的是「暂不」的*开票门*，不是宣称那些证据条件已经齐备。H-U1=B 对旧四家族 **不在**覆盖范围。

## 2. 冻结身份（L2 v0 · 旁路）

**冻结对象（不得原地改语义）：**

| 身份项 | 冻结值 |
|---|---|
| 经济合同 | `research contract v0 (L2-S0)` |
| backend_id / 工件根名 | `minute_orders_research_v1` |
| L1 family | `minute_orders_research`（永 opt-in） |
| 三 entry | `minute_orders_backend.runner.run_minute_orders_research`；`…run_minute_orders_research_with_artifacts`；`scripts/research/run_minute_orders_research.py` |
| 价格模型 | `completed_bucket_close`（LIMIT-only） |
| 比较权限 | 恒 `no_ssot_compare_authorization`（成功工件亦不授绿 R） |

### 2.1 命名纪律（四套版本号不得混指）

| 层 | tip 现名 | 说明 |
|---|---|---|
| **经济合同** | `research contract v0 (L2-S0)` | 撮合/账本语义；**勿叫「v1」** |
| **backend / 工件根** | `minute_orders_research_v1` | 目录与 `BACKEND_ID`；≠ 经济合同版本 |
| **artifact schema** | `minute_orders_artifacts_v1` / hybrid `v2` | 落盘 schema |
| **source recipe** | `minute_orders_source_recipe_v1` | 输入配方 |

加法型观察/来源片可讨论同 backend 升 artifact/recipe 版本；**经济语义变必须新 contract 字符串 + 新 backend_id**（及独立工件根 / oracle）。

### 2.2 tip 包内 13 个 `.py`（差分范围点名）

`backtest/research/minute_orders_backend/`（tip；旁路复用，本 PR 零改）：

| # | 文件 | TC1 态度 |
|---|---|---|
| 1 | `match.py` | 复用；禁改现语义 |
| 2 | `fees.py` | 复用；禁偷接 production 费率 |
| 3 | `clock.py` | 复用；相位增量须新 contract |
| 4 | `broker.py` | 复用 |
| 5 | `ledger.py` | 复用；账本权威不变 |
| 6 | `runner.py` | 复用；新版本换根/换 backend |
| 7 | `artifacts.py` | 复用；不覆盖旧根 |
| 8 | `source_loader.py` | 复用；X6 差分另刀 |
| 9 | `types.py` | 复用 |
| 10 | `input_codec.py` | 复用 |
| 11 | `source_provenance.py` | 复用 |
| 12 | `cli.py` | 复用；CLI `--evidence-level`=`synthetic`\|`lake`（lake→hybrid；见 [CLI lake](note-true-core-cli-lake-2026-10-02.md)） |
| 13 | `__init__.py` | 复用；保持现有公开导出，不在本模块上新开入口 |

合同文档锚：[L2-S0](note-l2-s0-minute-orders-contract-2026-09-29.md) · [S1 MatchCore](note-l2-s1-matchcore-2026-09-29.md) · [S2](note-l2-s2-ledger-fee-2026-09-29.md) · [S3](note-l2-s3-clock-broker-runner-2026-09-29.md) · [S4](note-l2-s4-artifacts-isolation-2026-09-29.md) · [S5](note-l2-s5-l1-register-2026-09-29.md)。

## 3. C-New 一句话合同（冻结草案）

**New 研究核 = 旁路冻结 tip 已交付的 L2 v0 身份（上表），另起新 `contract_version` 字符串与新 `backend_id`（及独立工件根 / oracle）的「外部冻结意图 → 完成桶成交 → 账本」研究后端；意图生成在核外适配层；核内不做名单扫描 / 现金反馈缩量 / StrategyPort；不承诺复现任何旧 CSV/v7/JR/Mode B NAV 或 writer 字节。**

仍只 `facade.run` 整次委托原生 = **仍是 B**（旧入口）。New 核内部 Clock→Broker→MatchCore→Ledger = tip 已有窄 C-M；本票「扩展」= 获批新能力面，不是再包一层空 facade。

## 4. 新 contract + 新 backend_id 政策

| 规则 | 口径 |
|---|---|
| **冻 v0** | 不原地改 `research contract v0 (L2-S0)` 语义；不复用 v0 golden 改名充数 |
| **语义增量** | 必须：**新** contract 字符串 + **新** backend_id + 独立工件根 + 增量 oracle（绿 C 对新合同） |
| **旧三 entry** | 保留；新能力用新 entry 或新版本字段；**不**改写旧委托语义伪装绿 P |
| **回滚** | 关 New entry / 停用新根；旧 `_ENTRIES` 与旧产物永可复现；禁止覆盖历史 NAV |
| **默认化** | 永 opt-in（H-TC9）；不进 BOOKS 默认 |

### 4.1 触及 S0 v0 排除项 → 必新身份（非首包）

stop / market / replace / GTC · next-open / OHLC 路径（X3）· 多账户（X4）· 反馈式意图流 · StrategyPort · 静默补根 —— 每条都是**新 contract + 新 backend_id**，不得写回 v0 oracle。

## 5. X 轴边界（TC1 设计口径 · 本 PR 无码）

| 轴 | TC1 锁定边界 | 本 PR |
|---|---|---|
| **X1 核外意图** | **核外**、**事前**、**冻结** LIMIT 批次（现有 command schema）；禁止核内名单扫描 / 现金反馈缩量 / 在线 StrategyPort；反馈流 = 新 contract | 只文档；接线另 GO |
| **X2 富订单** | 触及 Lifecycle LIMIT-only → 新身份；后置 | 不做 |
| **X3 第二价格** | **首包否**（H-TC3） | 不做 |
| **X4 多账户** | 触及单账户 → 新身份；后置 | 不做 |
| **X5 批跑** | 同合同+oracle；后置 | 不做 |
| **X6 loader** | tip：行情 `source_kind` 为 pinned `lake` 或 `synthetic_fixture`；账户 origin 仍 `synthetic_account`；命令 origin 仍 `designed_limit_batch`；CLI `--evidence-level` 支持 `synthetic` 与 opt-in `lake`（→ S4 hybrid；≠ host PASS）；首包 X6 合成已合；真湖边界/e2e/CLI 分刀 | 合成差分见 [X6 synthetic](note-true-core-x6-synthetic-attestation-2026-10-02.md)（#307）；真湖边界 [X6 lake](note-true-core-x6-lake-boundary-2026-10-02.md)（#309）；recipe e2e [X6 lake e2e](note-true-core-x6-lake-recipe-e2e-2026-10-02.md)（#310）；CLI lake [CLI lake](note-true-core-cli-lake-2026-10-02.md)（#311 MERGED） |
| **X7 观察面** | 可设计；**新**投影入口；不塞 `_FAMILIES`；观察 ≠ 绿 R | 实装见 [A·X7 observe](note-true-core-ax7-observe-2026-10-02.md)（draft 勿合） |
| **X8 对照桥** | 仅**撮合前**意图快照；**禁止** fills→意图倒造；独立 comparison 根；`comparison_status` 恒 `no_ssot_compare_authorization`；不产成功 `summary.json`；不进 fill-policy；不排 NAV；默认不改 `simulate` | 实装见 [TC4](note-true-core-tc4-x8-compare-bridge-2026-10-02.md)（#306 MERGED） |

## 6. 负面清单（本 PR / 默认后续 · 无补丁草稿）

本 PR **明确不改**（亦不为「下一步方便」预留半改）：

| 面 | 禁止 |
|---|---|
| `csv_minute_backtest.simulate` / `simulate_v7` | 任何函数体 / 签名 / 默认语义 |
| MatchCore | `match_candidates` / `compute_bucket_capacity` 现语义 |
| Fees | 偷接 production 费率；改写 tip 累计名义→增量费语义 |
| VolumeCap / clamp / 完成桶共享定义 | 借 New 票改共享 CSV 邻核 |
| 旧 L1 `_ENTRIES` 四家族委托 | 改成逐步事件宿主 |
| `views._FAMILIES` | 把 L2/New 塞进四元组充数 |
| 绿 R / NAV 混比 | 同 facade / 同 PIN / 同费率数字均不授权 |
| 覆盖旧工件根 | 已存在根拒绝；无清空复用 |

若将来某刀必须改 `simulate`：函数级 allowlist + 点名票 + 声明 ≠δ5≠R4（H-TC4 最后手段）。破坏 MatchCore/Fees 现语义 → **新模块名**（H-TC5），不原地打补丁。

## 7. 工件根 / oracle / 验收语言（草图）

| 项 | 口径 |
|---|---|
| 旧根 | `backtest_output/minute_orders_research_v1/<run_id>/` — 旁路冻结 |
| 新根 | 新 backend_id 下独立目录；已存在即拒绝 |
| 绿 C | 仅对新合同 + 其增量 oracle；**不**继承「v0 已全绿」印象 |
| 失败证据 | 沿用 S0：保留失败证据；不返回成功 NAV；不写 success marker |
| 旧入口非回归 | TC2+ 护栏 = 旧 L1/旧 L2-v0 三 entry **行为不变**；**≠** New≡旧 byte-compat |
| 手算 | 增量草图另刀引用 [S0 handcalc](note-l2-s0-handcalc-oracle-sketches-2026-09-29.md)；样例数字不是默认参数 |

## 8. 本刀交付 / 明确不做

| 本 PR（TC1 docs） | 明确不做 |
|---|---|
| 锁定 H-U6=New + H-TC* 落仓 | 任何业务 Python / 测试 / CI / HELP_LOCK |
| L2 v0 冻结身份 + 新 contract/backend 政策 | 改 MatchCore / Fees / `simulate` / VolumeCap |
| X 轴边界 + simulate/MatchCore 负面清单 | X1 接线码、X6 真湖、X8 对照桥实装 |
| 权威交接：覆盖仓内「H-U5=暂不」指针 | 开 TC2 码刀、P3、δ5 certified、R4、#135、G3 码 |
| 引用 handoff 方案与 R1 | 默认翻转、NAV 混比、关停旧入口 |
| draft **勿合**，等 Human「合」 | 写湖、4090、Compat 主路径 |

**TC1 退出标准 = 合同边界落仓，不是「必须立刻写码」。** 码刀（TC2）须 TC1 已合 + 独立实施 GO。

## 9. 指针

- 统一上限 U1（旧入口仍有效）：[note-minute-engine-unify-ceiling-u1-2026-10-02.md](note-minute-engine-unify-ceiling-u1-2026-10-02.md)
- L1/L2 产品边界：[note-l1-l2-research-engine-boundary-2026-09-28.md](note-l1-l2-research-engine-boundary-2026-09-28.md)
- L2-S0 合同：[note-l2-s0-minute-orders-contract-2026-09-29.md](note-l2-s0-minute-orders-contract-2026-09-29.md)
- 成交假设 SSOT：[minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)
- 引擎定位：[engine-positioning-ssot.md](engine-positioning-ssot.md)
- 真核方案 handoff（本机外部，**不是仓库文件**）：`/workspace/handoffs/minute_engine_true_core_new_20261002/`
- TC2 窄 X1 适配器（码刀；复用 v0 runner；**不** mint 新 contract/backend_id）：[note-true-core-tc2-x1-intent-adapter-2026-10-02.md](note-true-core-tc2-x1-intent-adapter-2026-10-02.md)（#304 MERGED）
- TC3 具名消费者闭环（CLI/HELP；仍无新 contract/backend_id）：[note-true-core-tc3-named-consumer-2026-10-02.md](note-true-core-tc3-named-consumer-2026-10-02.md)（#305 MERGED）
- TC4 X8 对照桥（红标签；独立 comparison 根）：[note-true-core-tc4-x8-compare-bridge-2026-10-02.md](note-true-core-tc4-x8-compare-bridge-2026-10-02.md)（#306 MERGED）
- X6 合成夹具/attestation 差分（非真湖；tool_id only）：[note-true-core-x6-synthetic-attestation-2026-10-02.md](note-true-core-x6-synthetic-attestation-2026-10-02.md)（#307 MERGED）
- X6 真湖只读 END/loader 边界（tool_id only；不写湖）：[note-true-core-x6-lake-boundary-2026-10-02.md](note-true-core-x6-lake-boundary-2026-10-02.md)（#309 MERGED）
- TC5 扩展包 GO/范围（docs-only；H-TC5-NEXT=C 已点 → #309）：[note-true-core-tc5-go-scope-2026-10-02.md](note-true-core-tc5-go-scope-2026-10-02.md)（本刀合入）

**≠δ5 certified ≠R4；TC1 docs 已合 #303；无 MatchCore/Fees/simulate 重写。TC2 X1 已合 #304；TC3 已合 #305；TC4 X8 已合 #306；X6 合成差分已合 #307；X6 真湖只读边界已合 #309；TC5 GO/scope 见 [TC5 note](note-true-core-tc5-go-scope-2026-10-02.md)（本刀合入；其它码轴仍须独立 GO）。**
