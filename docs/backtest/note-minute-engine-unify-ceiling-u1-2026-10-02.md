# 分钟引擎统一 · 上限锁 + U1 覆盖对账（2026-10-02）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-02（Asia/Shanghai / CST） |
| tip | `8c7ddc9ec6f05c5fda4602bcce98c9a3441b80c5`（master · laptop merge after #300） |
| Human GO | 锁定全部 H-U* 为方案推荐；开 **U1 docs draft**；**勿合**，等「合」 |
| 方案 | `/workspace/handoffs/minute_engine_unify_plan_20261002/`（`PLAN.md` / `COMPARISON.md` / `EXEC_ZH.md` / `reviews/R1_SYNTHESIS.md`） |
| 仓内落点 | 本 note；轻指针见 [engine-positioning §3.4](engine-positioning-ssot.md) / [industry-state §7](industry-state-acceptance-index-2026-09-28.md) |
| 硬约束 | **docs-only**；不改 MatchCore / Fees / `simulate` / VolumeCap·clamp·完成桶；≠δ5 certified ≠R4；无写湖；无 4090；无真核码 |

> **本 note ≠ 第二套成交默认表，≠ 绿 R 资格认证。** 入口默认 / 绿 R·S / 红混比继续只链 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。**同 facade 返回类型 ≠ 绿 R。**

## 1. 锁定裁断（H-U1…H-U7）

| ID | 锁定 | 含义（执行口径） |
|---|---|---|
| **H-U1=B** | 统一运行**上限** = 现有 Thin adapter（档 B） | 完整 run 委托原生；可含已批外壳预检；**不**接管下一事件 / 选价 / 账户 |
| **H-U2=够** | 现有 L1 facade / views **已够**；至多本 U1 说明 | 不造第二 catalog；不补齐所有未注册入口当作目标；views 仍排除 L2（见 §3） |
| **H-U3=永 opt-in** | L2 `minute_orders` **永远 opt-in** | 延续 P1 H4=A / P2-C；不得随「统一」默许替换共享 CSV |
| **H-U4=不允许** | **禁止**为统一触及 `simulate` | MatchCore / Fees / VolumeCap·clamp·完成桶同禁；升格须独立点名票 |
| **H-U5=暂不** | **不开**真核大票（C-S / C-M） | 缺共同目标合同与足以覆盖迁移成本的需求证据；重开条件见方案 §3.3 |
| **H-U6** | *不适用* | H-U5=暂不 → 不裁 C-Compat / C-New |
| **H-U7=仅 U1** | 下一刀封口 = **本 docs 页** | 不打包码、真核、跑数、发布、U2 adapter/helper |

R1 四席（Kimi / Codex / Grok / Claude）均为 **APPROVE_WITH_NITS**（0 MUST-FIX）；清晰 nits 已回填 handoff。**评审 APPROVE ≠ 实施 GO**；本 PR 仅落仓 Human 已锁上限。

### 1.1 后续覆盖（2026-10-02 · 真核 TC1 · 非本 U1 正文改写）

Human 另开真核大票：**H-U5 开票门被覆盖** → **H-U6=New**（C-New）；**H-TC1=C** 仅 docs。详见 [真核 C-New TC1 合同冻结](note-true-core-c-new-tc1-contract-2026-10-02.md)。**本表 H-U1=B / H-U2 / H-U3 / H-U4 对旧入口仍有效**；L2 三 entry 的 v0 语义旁路冻结，不在覆盖范围。覆盖的是「暂不」开票门，**不**宣称 unify 方案证据条件已齐。

## 2. 统一上限一句话

**统一运行停在 tip 已有 L1 Thin adapter（五家族 · 13 精确 entry）；不重造 facade；不默认加第六家；不进真核；不碰 MatchCore / Fees / `simulate`。**

三档对照（定义详见 handoff `PLAN.md` §2）：

| 档 | tip 现状 | 本锁 |
|---|---|---|
| A Facade-only | SSOT + 部分 views；非完整机器 catalog | 不另开；本 U1 仅文档对账 |
| **B Thin adapter** | **已有** L1 + #298/#299/#300 | **推荐上限 · 锁定** |
| C True unified match core | L2 是窄先例，非跨家族共同合同 | **不开票**（H-U5） |

## 3. U1 覆盖差分（现有 L1 够不够）

下表是 ownership / 接入范围索引，**不是第二份默认表**。源码锚：`backtest/research/run_protocol/facade.py` `_ENTRIES`；views：`views.py` `_FAMILIES`。

### 3.1 已注册（五家族 · 13 entry）

| family | entry_kind | native_entry | 状态 |
|---|---|---|---|
| `joint_return` | native_api | `joint_return_replay.replay` | 已有 |
| `joint_return` | native_api | `joint_return_replay.run_replay` | 已有 |
| `joint_return` | native_cli | `scripts/research/run_joint_return_replay.py` | 已有 |
| `csv_minute` | native_api | `csv_minute_backtest.simulate` | 已有 |
| `csv_minute` | native_api | `csv_minute_backtest.run` | 已有 |
| `csv_minute` | native_cli | `backtest/research/csv_minute_backtest.py` | 已有 |
| `v7` | native_api | `csv_minute_backtest_v7.simulate_v7` | 已有 |
| `v7` | native_cli | `backtest/research/csv_minute_backtest_v7.py` | 已有 |
| `grid_modeb` | native_api | `unified_exit_modeb.run_modeb` | 已有 |
| `grid_modeb` | native_cli | `scripts/research/run_unified_exit_modeb.py` | 已有 |
| `minute_orders_research` | native_api | `minute_orders_backend.runner.run_minute_orders_research` | 已有 · 永 opt-in |
| `minute_orders_research` | native_api | `…run_minute_orders_research_with_artifacts` | 已有 · 永 opt-in |
| `minute_orders_research` | native_cli | `scripts/research/run_minute_orders_research.py` | 已有 · 永 opt-in |

> **五家族** = `_ENTRIES` family 键去重：**CSV / v7 / 网格 B / JR / L2**。TopK / X-02 / H/L / X-04 为 CSV/v7 内组件，不是新 L1 家族。

### 3.2 Views（四家族 · 不含 L2）

`views._FAMILIES = (csv_minute, v7, joint_return, grid_modeb)`。**明确排除** `minute_orders_research`。若将来需要 L2 run 后只读投影，须具名消费者 + 独立 GO；本 U1 **不**补。

Views 只投影已取得的内存证据：不读文件、不跑引擎、不生成订单、不补 missing 为 0、不重算 NAV；网格无 incremental fills。

### 3.3 未注册 / 明确拒绝 / 允许但未证

| 类别 | 项 | 口径 |
|---|---|---|
| **未单独注册** | APP dropout；敏感格 R1/R2 fullstrat | #300 预检接线 ≠ 统一研究臂；缺具名消费者前不造第六家 |
| **不在本 L1 白名单** | 日线策略；网格 Mode A | 本统一方案不扩日线范围 |
| **明确拒绝当目标** | 跨家族绿 R；同返回类型混 NAV；默认替换 L2→共享 CSV | fill-policy SSOT + P2-C |
| **允许但联合效果未证** | CSV `run` 真 loader 成功；完整 CLI writer；全开关组合绿 P | 见既有 [CSV adapter note](note-l1-csv-minute-adapter-2026-09-28.md)；注册存在 ≠ 全组合 parity |

### 3.4 Writer / 预检 ownership（不改核）

| 面 | tip 事实 | 本锁 |
|---|---|---|
| Native writers | 成功/失败证据仍由各家族原 CLI / wrapper 拥有 | L1 不 mkdir、不清空、不改名；artifact refs 保持原语义 |
| P2 外壳预检 | #299/#300：CLI/adapter/loader 出口；`participation_rate=None` = 旧臂 no-op | **保留**；不为「更薄」撤销；不塞进 `simulate` / MatchCore |
| 绿 P 参照 | tip **原生入口自身**可观察行为（含其原生出口预检） | adapter 壳预检与原生出口预检先后重复 ≠ 须修差异 |

## 4. 本刀交付 / 明确不做

| 本 PR（U1 docs） | 明确不做 |
|---|---|
| 锁定 H-U* 上限落仓 | 任何业务 Python / 测试 / CI / HELP_LOCK |
| §3 覆盖差分一页 | 新 adapter、机器 catalog、O1 投影码 |
| 轻指针校准历史「规划中」措辞 | 改 MatchCore / Fees / `simulate` / VolumeCap |
| 引用 handoff 方案与 R1 | 开真核票、P3、δ5 certified、R4、#135、G3 码 |
| draft **勿合**，等 Human「合」 | 写湖、4090、默认翻转、NAV 混比 |

**U1 退出标准不是「必须发现缺口」。** Human 已裁：现有 L1 够用；本页即封口。若日后出现具名缺口，另批 U2-A/B/H 窄片；真核需求走独立 U3 合同票，**不得**藏进 adapter。

## 5. 指针

- L1/L2 产品边界：[note-l1-l2-research-engine-boundary-2026-09-28.md](note-l1-l2-research-engine-boundary-2026-09-28.md)
- P1 Human defaults：[note-minute-engine-p1-human-defaults-2026-10-02.md](note-minute-engine-p1-human-defaults-2026-10-02.md)（#298）
- P2 adapters / 预检 / P2-C：[note-minute-engine-p2-adapters-2026-10-02.md](note-minute-engine-p2-adapters-2026-10-02.md)（#299/#300）
- L1 views：[note-l1-views-2026-09-29.md](note-l1-views-2026-09-29.md)
- 成交假设 SSOT：[minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)
- 引擎定位：[engine-positioning-ssot.md](engine-positioning-ssot.md)
- 统一方案 handoff（本机外部，**不是仓库文件**）：`/workspace/handoffs/minute_engine_unify_plan_20261002/`
- 真核 C-New TC1（覆盖 H-U5 开票门 / H-U6=New）：[note-true-core-c-new-tc1-contract-2026-10-02.md](note-true-core-c-new-tc1-contract-2026-10-02.md)；handoff `/workspace/handoffs/minute_engine_true_core_new_20261002/`

**≠δ5 certified ≠R4；docs-only；无 MatchCore/Fees/simulate；勿合，等待 Human「合」。**
