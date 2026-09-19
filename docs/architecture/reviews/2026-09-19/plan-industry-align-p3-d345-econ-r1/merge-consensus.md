# merge-consensus — plan-industry-align-p3-d345-econ r1

> 日期：2026-09-19（Asia/Shanghai）  
> 对象：PR [#124](https://github.com/baiyibing/MyQuant-backtrader/pull/124) 五份 docs；原评审 HEAD `1e9994e`，本次 Human GO 对应勘误后 tip `7eeb475`（`7eeb47588c3f3ec37e4e15dd7703c89ff84bd23a`）
> `IMPLEMENTATION_BASE=1049b904bdd818dbb79f51f1830a008c8f83b141`（short `1049b90`）  
> **Status：已人裁 GO / Human GO recorded 2026-09-19（Asia/Shanghai）**：δ3=A，δ4=A，δ5=B(design)，δ6=A（ledger 可选 B，仅 docs；生产 shares/cash/NAV 须另裁显式 C，**本轮不授权**）；P1/P2/P4 继续挂起。完整权威 cut 表见下文。
> 对抗前置：[adv-r1-summary.md](./adv-r1-summary.md)（三路 host-parallel `codex exec` · `gpt-6-astra` · `xhigh`；rc=0）  
> 人裁短笺：[human-go-2026-09-19.md](./human-go-2026-09-19.md)
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

**主持综合（评审时历史结论）**：主船（docs-only、默认 A/A/B/A、冻结、δ6 C 闸门、P1/P2/P4 deferred）事实成立；**无生产冻结泄漏、无 Mode B 经济已关误报、无 P1–P4 重开**。唯一须在人裁引用前落地的 as-built 勘误为 **MC-1 / MC-2**（多席共指且 host 亲验）。对抗 DS-1..6 与 fan-out 黄项记入 Slice B / § notes，**不挡** docs 人裁入口，也**不授权**编码。

**共识标签：GO-WITH-NITS**

本次 Human GO 在该评审历史之上正式记录；后续授权以本文已录入 cut 表为准，GO-WITH-NITS 及 MC-1/MC-2 勘误记录保留。下文历史「ACCEPT→Slice B」仅记录评审交接，不把 δ5 设计 B 或 δ6 可选账本 B 扩成测试/生产接线授权。

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

## 已录入人裁 GO 表（权威裁决；2026-09-19，Asia/Shanghai）

| ID | 权威 Human GO（原文） |
|---|---|
| **δ3** | δ3=A：契约 + data-free pins，不改生产 |
| **δ4** | δ4=A：先契约化；fail-closed 另裁 |
| **δ5** | δ5=B：只设计，不接生产 cap |
| **δ6** | δ6=A：残留+oracle；账本可选 B；**生产增股/入账/NAV 须另裁 C，本轮不授权** |
| **P1 / P2 / P4** | P1/P2/P4 继续挂起 |

局部编号落点：P3δ3.1/3.2/3.3=A/A/A，P3δ4.1/4.2/4.3=A/A/A，P3δ5.1=B，P3δ6.1=A。δ5 其它 §5 推荐仍是 B 下设计候选；δ6 账本可选 B **仅 docs**。δ3 接线 pin 仍进未来 Slice B DoD；δ4 named-band 勘误保留，fail-closed/policy 须另裁 `.1=C`。**所有生产选项 C 均未授权，禁止生产 Python 修改。**

---

## 是否可进人裁 / 当前合并与实施资格

**已人裁 GO，docs PR #124 可合并；评审历史共识仍为 GO-WITH-NITS。**

1. MC-1/MC-2 勘误已在本次 GO 对应 tip `7eeb475`；历史 review 与勘误表保留。
2. 合并 #124 后，δ3/δ4 的未来 feat **Slice A→B（并至验收 Slice C）已获 docs + data-free pins 授权**，仅契约化、生产冻结，尚未实施。
3. δ5 仅设计文档落地；δ6 A 残留+oracle，账本可选 B 仅 docs。**生产 cap、增股/入账/NAV 及其它生产选项 C 均未授权**；P1/P2/P4 继续挂起，§9 22 文件冻结不变，禁止生产 Python 修改。
4. 本任务仅记录 GO：不执行 #124 合并、不开 feat/impl 分支或 PR，不修改/运行测试。`IMPLEMENTATION_BASE` 仍为 `1049b904bdd818dbb79f51f1830a008c8f83b141`，待 #124 合并、后续 feat 分支刷新时再记录新基线；不扩白名单、冻结表或 §8 命令。

---

## 下一动作

1. **先合并 #124，再推进 feat δ3 契约+data-free pins**；后续 feat 分支刷新基线时记录完整 SHA，本次不改 `IMPLEMENTATION_BASE`。
2. δ3/δ4 按已授权 Slice A→B→C 完成契约/pins/验收，生产冻结；δ5 只设计，δ6 A 残留+oracle（账本可选 B，仅 docs）。**不实施任何生产 C，不写生产 Python。** 黄项按此授权边界承接，不必再开 r2 fan-out。
3. 本次只录入人裁，不执行上述后续动作、不运行 pytest/回测/湖；不回复 BT，不嵌套 codex-in-codex，无 cloud 实施。
