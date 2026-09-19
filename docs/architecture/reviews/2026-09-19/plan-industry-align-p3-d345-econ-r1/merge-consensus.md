# merge-consensus — plan-industry-align-p3-d345-econ r1

> 日期：2026-09-19（Asia/Shanghai）  
> 对象：PR [#124](https://github.com/baiyibing/MyQuant-backtrader/pull/124) 五份 docs @ HEAD `1e9994e`（勘误后见本轮 errata commit）  
> `IMPLEMENTATION_BASE=1049b904bdd818dbb79f51f1830a008c8f83b141`（short `1049b90`）  
> 工作假设（**pending human GO**，非已录入人裁）：δ3=A，δ4=A，δ5=B(design)，δ6=A（ledger 可选 B；生产 shares/cash/NAV 须显式 C）  
> 对抗前置：[adv-r1-summary.md](./adv-r1-summary.md)（三路 host-parallel `codex exec` · `gpt-6-astra` · `xhigh`；rc=0）  
> Classic fan-out：codex / cursor-kimi-k3-high / cursor-auto / grok（claude=host 空槽）  
> 计票：**证据裁决，不投票**。host 对全部 🔴 亲验。

---

## 席位总览

| 席位 | 裁决 | 要点 |
|---|---|---|
| dissent-steelman（adv） | REQUEST CHANGES（验收充分性） | DS-1..6：partial 扫描、无 bar NAV、held-None 可达性、qlib band、接线 pin、期初权利 |
| domain-safety（adv） | GO-WITH-NITS | raw close 域；qlib band；D6 loader 前缀 |
| pattern-evidence（adv） | GO-WITH-NITS | PE-01/PE-02；不复用 chip/StockDataReader |
| codex | **GO-WITH-NITS** | 无 🔴；δ5 现金门/预算顺序/API 契约黄项 |
| cursor-kimi-k3-high | **GO-WITH-NITS** | 🔴 R1 qlib band；动态证实 held-None 自然不可达 |
| cursor-auto | **GO-WITH-NITS** | 🔴 R1+R2；黄项含接线 pin / D6 / partial |
| grok | **GO-WITH-NITS** | 🔴 R1+R2；Y1–Y7 Linux/CLI/可达性等 |
| claude | host 空槽 | 见 `claude.md`；不计独立票 |

**主持综合**：主船（docs-only、默认 A/A/B/A、冻结、δ6 C 闸门、P1/P2/P4 deferred）事实成立；**无生产冻结泄漏、无 Mode B 经济已关误报、无 P1–P4 重开**。唯一须在人裁引用前落地的 as-built 勘误为 **MC-1 / MC-2**（多席共指且 host 亲验）。对抗 DS-1..6 与 fan-out 黄项记入 Slice B / § notes，**不挡** docs 人裁入口，也**不授权**编码。

**共识标签：GO-WITH-NITS**

---

## host 抽验记录（🔴 亲验）

- **MC-1 / δ4 named-band（adv PE-01·DS-02·DS-4；kimi R1；auto R1；grok R1）✅**  
  `csv_common.py:80-82`：`qlib_limit_pct is not None` → 固定 band，绕过 named/板块。`csv_strategy_books.py:713`、`:788` 实接。δ3 `:32` 已钉例外；δ4 `:38` 原表无前提 → 独立审阅会误导 pins。  
  **处置：ACCEPT → 已回填 δ4 v0.1.1**（表收窄 + 固定 band 对照行）。

- **MC-2 / δ6 raw close（adv PE-02·DS-01；auto R2；grok R2；kimi 🟡-1）✅**  
  `csv_ledger.py:173-178` 只取传入 `close`；raw 是 none 路径夹具前提，非 helper 保证。  
  **处置：ACCEPT → 已回填 δ6 v0.1.1**。

- **MC-3 / 生产冻结 / C creep / P1–P4** ✅  
  base→HEAD（勘误前）仅五 Markdown；22 文件冻结四份同序且文件均存在；Mode B `shares/=k` + `no cash dividend` 与 δ6 F-R2/3、index `:16` 隔离成立。

- **MC-4 / held-None 自然不可达（kimi 实验 5；dissent DS-3；auto/grok Y）✅ 作黄项**  
  当前 flat names 合同下 held-None 依赖 seed；δ3 未来 `.1=C` 须强制重做 δ4 可达性矩阵。不挡本轮 docs 人裁。

- **MC-5 / δ5 partial 扫描 / δ6 无 bar·期初权利 / δ3 接线 pin** ✅ 作黄项  
  属未来 Slice B 合同完整度，非本 PR 假断言或 freeze 泄漏。

---

## 勘误表

| # | 严重度 | 来源 | 裁决 | 勘误 | 落点 |
|---|---|---|---|---|---|
| **MC-1** | 🔴 | 多席共指 | **ACCEPT·已回填** | δ4 书侧未知板块早拒限定默认 named-band；增固定 band 行 | δ4 §2 v0.1.1 |
| **MC-2** | 🔴 | 多席共指 | **ACCEPT·已回填** | δ6 书 NAV：传入 close；none/raw 才是 raw mark | δ6 §2 v0.1.1 |
| **MC-3** | 🟡 | dissent/kimi/auto/grok | **ACCEPT→Slice B** | δ5：首次触发×零/部分成交后扫描游标/rider/peak；现金门按请求量 vs cap 后量；共享预算跨 lot 顺序 | δ5 §5/§7 |
| **MC-4** | 🟡 | dissent/kimi/auto/grok | **ACCEPT→Slice B** | δ4 held-None 三态表 + δ3.C→δ4 可达性交接 | δ4/δ3/index |
| **MC-5** | 🟡 | dissent/kimi/auto | **ACCEPT→Slice B** | δ3：`load_pool_names_by_day→context→names=` 接线 pin 升必需 | δ3 Slice B |
| **MC-6** | 🟡 | dissent/kimi/grok | **ACCEPT→Slice B** | δ6 B：无 bar 估值轨迹；登记→清仓→到账期初权利 | δ6 §7 B |
| **MC-7** | 🟡 | domain/auto/kimi | **ACCEPT→Slice B** | δ5 D6：loader 整日零量过滤 ≠ 桶级前缀因果 | δ5 D6/B1 |
| **MC-8** | 🟡 | grok/codex/auto | **ACCEPT→§ notes** | §8.2：CLI 禁令收窄；解释器链 vs 3.12 assert；chase pending 已消耗 | 各 plan §8 |
| **MC-9** | ⚪ | kimi/grok | **DEFER** | δ6 `exdiv_map` 锚点行略宽；index 历史统计口径 | 可选 |

---

## 推荐人裁表（工作假设；**pending human GO**）

| ID | 建议 | 边界 |
|----|------|------|
| **δ3** | **A** | 契约+未来 pins；不修 v7 PIT；接线 pin 进 Slice B DoD |
| **δ4** | **A** | 已收窄 named-band；fail-closed/policy 须另案 `.1=C` |
| **δ5** | **B（仅设计）** | 不接生产 cap；`.3` 部分成交待状态表后再裁；P1 继续挂起 |
| **δ6** | **A**；账本清晰可选 **B** | 生产增股/入账/NAV **必须显式 `.1=C` + 独立实施 PR** |
| **P1 / P2 / P4** | **继续 deferred** | 不重开 14:57 / trades 列 / touch↔mark |

头部回写「已人裁 GO（commit hash）」之前，仍视为未裁。**未裁不得开 feat、不得写生产 Python。**

---

## 是否可进人裁

**可以（GO-WITH-NITS）**，条件：

1. 本轮 review 产物 + MC-1/MC-2 勘误已在分支上（见 errata commit）。  
2. **人裁正式录入** δ3/δ4/δ5/δ6（或明示改口）后，再考虑未来 Slice A→B（仍 docs/tests-only，除非显式 C）。  
3. 合 docs PR ≠ 授权生产；§9 22 文件在默认 A/B 下保持零行为变更。  
4. **不合并 #124 于本任务**；不开 feat/impl PR。

---

## 下一动作

1. **等人裁** cut widget / 正式 GO。  
2. 人裁 GO 前：**禁止编码**；黄项写入各刀 Slice B / § notes 即可，不必再开 r2 fan-out（🔴 已回填可验证）。  
3. 不回复 BT；不嵌套 codex-in-codex；无 cloud 实施。
