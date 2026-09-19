# merge-consensus — plan-industry-align-p3-fees-2026-09-19 r1

> 日期：2026-09-19（Asia/Shanghai）  
> 对象：[plan v0.3.1→v0.3.2](../../../backtest/plan-industry-align-p3-fees-2026-09-19.md) @ human GO P3.1/P3.2/P3.3=A/A/A；`IMPLEMENTATION_BASE=f548cc2ff808e7ecd5357e4d3786a62c76d8f8c5`  
> 对抗前置：[codex-adv-r2](../plan-industry-align-p3-fees-codex-adv-r2/)（E-r2-01..06 已回填 v0.3）  
> 本轮席位：codex / cursor-kimi-k3-high / cursor-auto / grok（claude=host 空槽）  
> Fan-out：`run_multi_ai_review.py --preset classic --host claude --parallel`；四路 rc=0（codex 125s / kimi 152s / auto 145s / grok 511s）  
> 计票：**证据裁决，不投票**。host 对全部 🔴 亲验。

---

## 四路总裁决

| 席位 | 裁决 | 要点 |
|---|---|---|
| codex | **修后可进** | 🔴 R1 §8 漏跑接线测；🟡 floor 数值/入口约定/解释器前提 |
| cursor-kimi-k3-high | **修 🟡 后可进** | 无 🔴；印花口径注解、解释器前提、分钟 CLI 负向 pin |
| cursor-auto | **R1/R2 修前不宜进 Slice B** | 🔴 缺两 lot 数值 oracle；🔴 `DEFAULT_SCHEDULE is` 钉不住书引擎默认 |
| grok | **有条件可以** | 🔴 §8 验收缺口（同 codex）；🔴 §2.4 totals 未写（升 cursor-auto）；交叉验证三路 |

**主持综合**：方向正确、人裁 A/A/A 不翻、生产冻结成立。两处 **契约可执行性洞** 为真 🔴（验收命令盖不住 Slice B；floor oracle 无 totals）。已回填 **v0.3.2**（MC-1/MC-2）。其余 🟡 进 Slice A 文档整理，**不挡**本轮 docs/tests 实施开船。

**共识标签：GO-WITH-NITS**（v0.3.2 已合本 PR；可开 Slice A→B→C docs/tests；生产零行为变更；不重开 P3.\* / P1/P2/P4）。

---

## host 抽验记录（🔴 亲验）

- **MC-1 / codex R1 / grok R1 ✅**  
  §7 要求 Extend/add wiring；§8 仅跑 `test_ashare_fees`（公式/重导出）+ fence + predicates。  
  `tests/test_ashare_fees.py` 现仅 3 个公式测，不经 `execute_buy` / `_sell` / `simulate`。  
  实现者若把接线测放进 `test_csv_*` 或新文件，§8 仍可全绿 → **E-r2-01 在验收层复活**。kimi「零 🔴」漏了这条协议缺口（锚点对 ≠ 验收覆盖交付物）。

- **MC-2 / cursor-auto R1 / grok R2 ✅**  
  §2.4 原只有定性句；Slice B 写 *locks documented as-built totals* 但文档无 totals。  
  亲算（`QLIB_PORTANA` 卖侧 15bp+min5；2×100@10）：书 `_sell`×2 → 佣金 10 / 现金 +1990；v7 一次 `_sell_lots` → 5 / +1995。与三路数字一致。默认 `BILATERAL_10BP`（min=0）测不出 floor 分叉。

- **cursor-auto R2（DEFAULT_SCHEDULE vs SimState）→ 并入 MC-1/Slice B，严重度 🟡→契约钉法**  
  `SimState` 三 float 默认绑 `COMMISSION`，书/分钟不经 `FeeSchedule` 对象。事实成立；§7 已点到 SimState，缺双指针写法 → 写进 v0.3.2 Slice B，不单列第二 🔴。

- **人裁 P3.1/2/3=A**：四路均未要求重开；印花 booking / 默认改 PortAna 均维持 A。

---

## 勘误表（已回填 v0.3.2）

| # | 严重度 | 来源 | 裁决 | 勘误 | 回填落点 |
|---|---|---|---|---|---|
| **MC-1** | 🔴 | codex R1 / grok R1 | **ACCEPT** | §8 必须列入 Slice B 接线落点（扩 `test_ashare_fees.py` 或新建 `test_ashare_fee_wiring.py`）；predicates+fence 标为旁证非 contract surface；F-R7 允许纯内存合成 `simulate` | §7 Slice B、§8、Pass criteria |
| **MC-2** | 🔴 | auto R1 / grok R2 / codex R2 | **ACCEPT** | §2.4 锁定两 lot 数值 oracle（书 10/1990 vs v7-one-call 5/1995；须 `QLIB_PORTANA`）；粒度=每次函数调用 | §2.4 |
| **MC-3** | 🟡 | auto R2 / grok Y1 / codex R3 | **ACCEPT→Slice B 文本** | 双默认指针：`DEFAULT_SCHEDULE is BILATERAL_10BP` + `SimState()` 三字段；禁止 monkeypatch 冒充 v7 透传 | §7 Slice B |
| **MC-4** | 🟡 | auto Y3/Y4 / grok Y2 | **ACCEPT→§2.5** | 书 `trades` 已有 `commission`；δ1 不改 schema、不给 v7 补列；EOD_MARK `commission:0` 非卖出扣费 | §2.5 |
| **MC-5** | 🟡 | kimi 🟡-2 / codex R4 / grok Y3 | **DEFER→Slice A/C** | §8 解释器前提（项目 venv / CI setup-python）；本 PR 已加一行注释 | §8 注释；实施 handoff 再钉绝对路径 |
| **MC-6** | 🟡 | kimi 🟡-1 / grok Y4 | **DEFER→Slice A** | 研究费率=代理口径，≠ 现行印花账单；禁止未来双重计入。不把「15bp=5+10」写成仓内已证分解 | Slice A 契约表一行 |
| **MC-7** | 🟡 | auto Y5 / grok Y5 | **DEFER→Slice A** | 显式 park `unified_exit_modea` 线性近似与 `research/engine.py` 占位，非 CSV 书/v7 接线证据 | Slice A non-goals |
| **MC-8** | ⚪ | kimi 🟡-3 / 锚点 off-by-one / path-allowlist | **DEFER** | 分钟 CLI 负向 pin（freeze 已挡加旗）；行号顺手校正；path-allowlist 升硬门可选 | Slice A/C |

---

## 对 P* 的立场

| 点 | 四路 | host |
|---|---|---|
| P3.1/P3.2/P3.3 = A | 一致维持 | **维持 A**；不重开默认改 PortAna / 印花 booking / 放宽 fence |
| P1 / P2 / P4 | 一致停放 | **维持停放**；书已有 commission 列 ≠ 重开 P2 |

---

## 是否可进 Slice A 实现

**可以（GO-WITH-NITS）**，条件：

1. 本 docs PR 合入 v0.3.2 + 本 merge-consensus + 四路评审 md。  
2. 实施仅 docs + data-free tests；十文件生产 freeze 零 diff。  
3. Slice B 必须把接线测编进 §8 命令；floor oracle 用 §2.4 锁定数字。  
4. 合 docs PR ≠ 自动改生产；任何行为变更必须停船重开 P3.\*。

---

## 下一步

1. 推本分支 docs PR（v0.3.1 human GO + r1 consensus + v0.3.2 errata）。  
2. 人/编排者合 PR 后开 feat 实施 Slice A→B→C（仍 docs/tests）。  
3. **不必再开 r2 fan-out**（本轮 🔴 均为文档可执行性，已回填可验证）。  
4. 不回复 BT；不嵌套 codex-in-codex。
