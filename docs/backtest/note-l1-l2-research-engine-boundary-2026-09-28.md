# L1 / L2 研究引擎产品边界（P0）

2026-09-28 · **P0 docs-only** · 基线 `8c4ed6c`（S2-E #242 后）· `production_C=frozen`。

R1：Codex APPROVE / Kimi APPROVE / Cursor COMMENT，三方均同意薄 P0；R2 consensus 后，Human「批薄 P0 docs-only，开干」。授权仅限本说明与最小指针，**不是 L1/L2 代码 implementation GO**；下述两层均为规划，尚未交付能力。

**一句话目标：L1 拟用薄 run 协议包住 native CSV / v7 / JR / grid Mode B 的完整运行；L2 拟在新 Human 冻结合同下提供有独立身份、显式 opt-in 的可选研究后端；二者都不替换共享 CSV，Cerebro 继续禁止复活。**

## 1. 名称与职责（提议）

| 名称 | 拟承担的职责 | 不得扩成 |
|---|---|---|
| L1 run facade | 委托共享分钟 CSV、独立 v7、joint-return（JR）、grid Mode B 各自完整 native run，保留原参数、省略语义、返回值、异常、退出码和 writers | 共享调度 / 定价 / 撮合核；逐 bar 宿主；统一账本或费用重算器 |
| L2 可选研究后端 | 新合同、新身份及独立账本 / 工件；须显式选择，不进 BOOKS 默认 | 替换或融合 CSV / v7 / JR / 网格；Cerebro 类宿主回归；执行验收栈 |
| `l2_analytics/` | 既有 Level-2 行情离线 ETL / 分析，与这里“第二层”无关 | L2 新研究后端的落点；CSV 策略书接入或 live 扩容 |

**这里的 L2 ≠ `l2_analytics/`，≠ LEBS，≠ 1.3 MockQMT 真栈。** 三仓职责及 Cerebro / Rolling 禁令仍以 [引擎定位 SSOT](engine-positioning-ssot.md) 为准；L1 不让旧 CLI 反向依赖 facade，不接管旧后端内部调度。

## 2. 不可抹掉的反例：评审否决题

以下是必须保留的合同差异，**不是待统一修复的 bug**；若设计抹掉任一差异，应否决该设计。

| 反例 | 边界 |
|---|---|
| **Q39≠hl** | Q39 先 open、再 close；hl 同 bar 止损优先。逻辑反例：SL95 / TP105、O106/H107/L94/C100，资格门全过时，Q39 先106止盈，hl 先95止损；这是合同反例，不是本片跑数 |
| **三个不同的 `close`** | `--topk-exec close` 是买侧14:55分钟 close；`--minute-stop-trigger close` 是分钟止损触发域；`--stop-fill close` 是日线 EOD 止损，共享分钟入口拒绝；不能造全局 `close` 别名 |
| **JR≠CSV** | JR 冻结数量、身份及有效期；CSV 按策略书、资金与仓位反馈生成交易。不得从 CSV fills 倒造 JR intents，也不得给 JR 重新 sizing |
| **两个 Mode B 名空间** | `grid`：`unified_exit_modeb` 卖出网格实例实验；`joint_return`：同冻结包 M-REF/M-LAG 对照。输出身份必须带家族，不能只写 Mode B |
| **同费率≠同费用** | CSV lot、v7 聚合、JR 每订单累计补差的扣费粒度不同；L1 不统一收费次数，也不经视图二次扣费 |

成交假设、唯一默认表及混比规则继续见 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md) §4–§6；本说明不另建默认表。v7 gap/timer、价格时点与入账时点等差异也不得借 facade 名称消除。

## 3. 切片门禁：P0 后必须停

**顺序：P0 → stop for Q1（点名 L1 具体消费者）→ only then L1-S0 types。**

2026-09-28 后续 Human 已点名 Q1「joint_return Mode B 入口」并单独批准 [L1-S0 types-only](note-l1-s0-run-protocol-types-2026-09-28.md)，本次仅冻结类型与契约测试，adapter / L2 仍待各自 GO。

- Q1 须点名现有或拟建 notebook / runner，并明确首版认证范围；没有具体消费者就延后 types。Q1 解决后，L1-S0 仍须单独切片 GO。
- 外部 PLAN **§10 的“P0，然后 L1-S0 types”不得读成自动 GO**；须按 R2 共识插入 Q1 停点。P0 不授权 types、DTO、adapter、catalog、helper 抽取或新 CLI。
- 后续每个 PR 只做一个 adapter 家族，逐片明确 GO；签收须钉住具体 pin IDs、输入 hashes、实现 SHA 及环境，不能用 mock-only 通过宣称完整 native parity。
- **2026-09-29 Q2–Q4 已由 Human 冻结**：Q2=A（外部 LIMIT、完成桶 close、partial/expiry），Q3=PLAN §4.2 窄包逐行签认，Q4=机制参考自行实现；Human GO 仅限 L2-S0 docs-only，基线 `7bdc7f7`（#248 后，L1 四个 adapters 已合入）。见[研究合同 v0](note-l2-s0-minute-orders-contract-2026-09-29.md)、[独立手算 oracle 草图](note-l2-s0-handcalc-oracle-sketches-2026-09-29.md)、[来源/LICENSE 决定](note-l2-s0-source-license-decision-2026-09-29.md)。**L2 可执行代码（含 MatchCore）仍未授权，须满足前置门并另获 L2-S1+ 具体切片 GO；L1 views 仍可选、后置，`production_C=frozen`。**
- P0 及后续切片均须 Human「合」才合并；本 PR **勿合 / wait for Human「合」**。

2026-09-29 Human「先做 L1 views」后，[L1-Slast views](note-l1-views-2026-09-29.md) 已实现为点名 joint_return / bt 离线编排消费者的 **opt-in 只读投影**，`run()` 与 native writers 不变、无 sidecar。L2 可执行代码仍受独立 GO 门禁约束。

## 4. 将来的验收用语

| 用语（未来验收，当前未签收） | 只证明什么 |
|---|---|
| **绿P：delegation parity** | 同 native entry、同 SHA / 输入 / 环境下，委托前后的已钉状态、工件与失败行为一致 |
| **绿C：contract conformance** | L2 符合新冻结合同及独立手算 oracle；不证明真湖或可执行收益 |

**绿P / 绿C ≠ SSOT 绿R / 绿S 的 NAV 比较资格。** 绿R / 绿S 仍按分钟 SSOT 的完整身份与实验轴判定；facade、相同返回类型或合成 PASS 都不授予跨后端 NAV 排名资格。L2 与旧后端直接 NAV 混排默认红，本片无新 NAV 数字。

## 5. 来源 / LICENSE 与本片范围外

优先依据新冻结合同自行实现。1.3 的 vendor 源树仅作机制参考，**不 import、不加 `PYTHONPATH`、不安装为运行依赖**；任何源码移植须另获 Human LICENSE pin（来源版本 / 段落及 LICENSE / notice / 分发要求）。本说明不宣称法律许可已获清理或复制已获授权。

本 PR 无 MatchCore / DTO / types / adapters，无 Python、测试、fixture、config、CI、HELP_LOCK、parser、presets 改动；不抽 helper、不建 catalog、不重录 golden，不改 fill / scan / fee / clock 默认或既有 opt-in 语义。不重开 JR clock / G8 / strategy12，不接入或运行 lake，不替换共享 CSV。

工作站 handoff（本机外部文件，**不是仓库文件或可移植 repo 链接**）：`/workspace/handoffs/l1_l2_research_engine_plan_20260928/PLAN_L1_L2_RESEARCH_ENGINE.md`；R2 共识位于其同目录 `multi_review_20260928/R2_CONSENSUS.md`。完整 PLAN 保留在 handoff，本仓只保留薄边界。

## 6. P2-C：L2 `source_loader` ↔ 共享湖读取边界对照（2026-10-02）

Human H4=A：L2 `minute_orders` **永 opt-in** 对照后端。本表保护 MatchCore 研究后端 **不被误读成默认 CSV / 共享湖 loader 替换**。完整刀文见 [P2 adapters note §4](note-minute-engine-p2-adapters-2026-10-02.md)。

| 维度 | 共享 CSV / market export / `ashare_bars` | L2 `source_loader`（`minute_orders_backend`） |
|---|---|---|
| 产品角色 | 主研究路径；Books / TopK / 共享 `--participation-rate` | 可选研究后端；显式 recipe + attestation；不进 BOOKS 默认 |
| 入口 | `csv_minute_backtest` / `run_topk_cap_compare` 等 | `load_minute_orders_source(recipe_path, expected_sha256=…)` → `RunInput` |
| 行情身份 | vendor-bar PIN：`minute_label`×`unit`×…；推荐湖 END+lots→股 export | 独立 recipe：`unit` / window / symbols / transform version / provenance |
| 成交核 | 共享 `simulate`（+ 可选 VolumeCap） | L2 MatchCore / Fees（冻结合同；研究骨架） |
| 完成桶 | `csv_minute_volume.completed_minute_volumes`；邻核冻结 | L2 合同 `completed_bucket_close`；**不得**借本表改共享桶定义 |
| 同 PIN 不同后端 | — | **红混比**：同 PIN / 同 facade 返回类型 **≠** 可绿 R NAV 并排 |
| 默认翻转 | 无（本表不授权） | **禁止**将 L2 接成共享 CSV 默认替换 |

**绿P / 绿C ≠ 绿R / 绿S。** ≠δ5 certified ≠R4。不改 MatchCore / Fees / `simulate` / VolumeCap。P2-A/B/C 已合 #299/#300。

## 7. 统一上限指针（2026-10-02 · U1 docs）

Human 锁定 H-U1=B / H-U2=够 / H-U3=永 opt-in / H-U4=禁碰 simulate / H-U5=暂不真核 / H-U7=仅 U1 docs。统一运行上限 = 现有 L1 Thin adapter；详见 [unify ceiling U1](note-minute-engine-unify-ceiling-u1-2026-10-02.md)。方案 handoff：`/workspace/handoffs/minute_engine_unify_plan_20261002/`。U1 draft **勿合，等待 Human「合」**；本指针不授权码或真核。

