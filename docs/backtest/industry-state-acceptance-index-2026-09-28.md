---
date: 2026-09-28
timezone: Asia/Shanghai
audit_base_sha: 8a6d6c3cf29006621093561df6bad4a8246b1fd7
audit_base_sha_short: 8a6d6c3
pr_base_sha: 21adb693656cf81e6cb1a80d5c5641fab6415615
pr_base_sha_short: 21adb69
sources:
  - industry-gaps-bt-2026-09-28.md
  - kimi-review-industry-gaps-bt-2026-09-28.md
  - kimi-review-pr231-g9-g1-index-2026-09-28.md
status: "docs-only index; no implementation; no default flip; no new lake GO"
---

# 行业状态与正确性开关验收索引（G9 + G1）

Human 于 2026-09-28 批准 [INDUSTRY_GAPS 基线审计](industry-gaps-bt-2026-09-28.md)：**「批准此稿为基线；先做 G9+G1 合并只读索引（顺带修 B1），其余逐项单独 GO。」** [Kimi 核稿](kimi-review-industry-gaps-bt-2026-09-28.md) 为 **APPROVE_WITH_NITS**，建议 G1 第一、G9 从第八提至第二，合并为同一只读产物。

基线审计与 Kimi 核稿现已落仓（见 frontmatter `sources`）；原稿亦曾存放于 Bot VM `/workspace/`。本文仍是仓内入口与证据边界索引：不把未重审的宿主回执视为已复核。审计基线 tip 为 `8a6d6c3`（#229）；本 PR 已 rebase 到 master tip `21adb69`（#230 squash-merge：docs stop/exdiv P3 `20260927e` archive）。本页“当前默认/opt-in”仍以审计基线为准；#230 **已合入**且 **defaults not flipped**。旧 plan 的历史状态以随后专项冻结记录为准。

## 1 当前默认 vs opt-in（状态面 · G9）

表中“已实现默认 OFF”“docs-only 决策关闭”“API 存在但 CLI 未接”是不同状态；PASS 不等于翻默认 GO。D 编号沿用[基线审计](industry-gaps-bt-2026-09-28.md)，链接落到仓内材料。

| 项目 | 当前默认 | opt-in / flag | 最新验收或状态指针 | 明确未证实 / 延期边界 |
|---|---|---|---|---|
| #214 P1 / #228 分钟止损 | `close` | `--minute-stop-trigger hl` | [P1 冻结 D3](minute-stop-trigger-hl-p1-2026-09-27.md)；P3 stamp `20260927e`（下行） | 非 tick；v7、s12、X-03 不接 hl，不补实现 |
| #214 P2 / #229 参考价到分 | OFF | `--exdiv-ref-fen` | [P2 冻结 D4](exdiv-ref-fen-p2-2026-09-27.md)，R1/R2；P3 stamp `20260927e` | 不改持仓 k 精度；R3/R4 延期，非完整权益账 |
| #214 P3 研究归档 | **defaults not flipped** | 既有 Human GO / re-GO 配方，无新开关 | [仓内 D5](stop-exdiv-p3-ab-2026-09-27.md) §1–6；[#230](https://github.com/baiyibing/MyQuant-backtrader/pull/230) **已 squash-merge** 入 master tip `21adb69`（docs archive only；本任务未合并；非本索引前置依赖） | `20260927e`：s8 四格、s12 两格 PASS；s12 hl 两格 SKIP。固定 `5e8`、`20251023–20260909`、研究 tip `8a6d6c3`；不能回写成首次 `21e6` 配方 PASS；完整宿主回执未重审 |
| TopK P1–P4 | `--topk-exec close` / walkdown OFF / `--topk-limit-rule qlib` | `open` / `intraday` / `vwap`；`--limit-walkdown`；`real` | [P1](topk-exec-p1-2026-09-27.md)、[P2](topk-exec-p2-2026-09-27.md)、[P3](topk-exec-p3-2026-09-27.md)、[P4](topk-exec-p4-2026-09-27.md)；[a/b](topk-exec-3cell-2026-09-27.md)、[c](topk-exec-6cell-2026-09-27.md)、[d real](topk-exec-6cell-real-2026-09-27.md) | vwap 是固定时钟等金额 TWAP-style，非按量 VWAP；vwap×walkdown 拒绝。归档为 2026 minute-none / nostop；不外推 2025 锚、完整 hash 或 hl 交互 |
| X-01 s12 分钟价格域 | OFF | `--fix-s12-price-domain`；必要时 `--s12-price-transform-file` | [D25](x01-s12-price-domain.md)；后续 [D32 附表](note-lessons-2026-09-25-26-experiment-chain.md#附本次实验链的最终状态) 真湖 PASS 摘要、P3 fix-on | 不认证 s12 日线、完整 PIT 或止损后台阶锚；原回执细节未复核 |
| X-02 分钟现金时序 | OFF（TopK 自动路径见 §2） | `--fix-minute-cash-order` | [D26 合成验证 / M 清单](x02-minute-cash-order-2026-09-25.md)；§2 | s12 明确拒绝；共享书/v7 的完整真湖验收未证实，不从 TopK 归档推导全书 PASS |
| X-03 s11 退出信号域 | OFF | `--fix-s11-exit-domain` | [D27](x03-s11-exit-domain.md)；后续 [D32 附表](note-lessons-2026-09-25-26-experiment-chain.md#附本次实验链的最终状态) 真湖 PASS 摘要 | X-02×X-03、exporter/CYQK PIT、Slice D 不因此通过 |
| X-07 named-limit 与 TopK 接线 | 原本的真实 named-limit 路径已按板块/日期修正；TopK 仍 qlib | TopK 显式 `--topk-limit-rule real` | [D14 P4 档位表、接线与后续](topk-exec-p4-2026-09-27.md)；[D17](topk-exec-6cell-real-2026-09-27.md) | **不能把 X-07 整体写为默认 OFF**；real 不证明名称 PIT 或特殊无限制 regime |
| δ3 名称 as-of | v7 flat；开关 OFF | `--asof-pool-names` | [D20](plan-industry-align-p3-d3-st-pit-2026-09-19.md)；[D23 crosscheck §4 D07](../reviews/2026-09-25-minute-engine-review/raw/crosscheck-grok.md)；[审计 §1.1](industry-gaps-bt-2026-09-28.md#11-核心三线与其他已实现能力) | by-day 能力存在；源在决策时刻可得仍需证明，默认不翻 |
| δ5 容量 | API `participation_rate=None`（OFF） | API rate / 量桶参数；共享 CLI `--participation-rate`（#291，opt-in）；P2-B 外壳预检 | [D22 v0.4 / §5–6](plan-industry-align-p3-d5-volume-cap-2026-09-19.md)；[D7 §2.4](engine-ashare-correctness.md)；#291；[P2 adapters](note-minute-engine-p2-adapters-2026-10-02.md) | **VolumeCap API 先于 #291 CLI**；#291=共享入口 opt-in 接线 + 对照脚手架，省略=旧臂；P2-B=CLI/loader 单位+完成桶预检（不改核）；**≠δ5 certified ≠R4**；≠ capacity certified；真实量认证、日线 cap、排队/冲击延期 |
| δ6 权益 | API `exdiv_economics=None`（OFF） | 显式 economics 事件 API | [D24 §5 / §8.4](plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md)；[D7 §2.5](engine-ashare-correctness.md) | API 已实现；无通用 CLI/湖事件 loader；补发、恢复等生命周期延期，不从 k 猜派息 |
| #135 classic P1/P4 与 P2 | P1/P4 A/A，as-built；P2 B 标签已交付 | P1/P4 为 docs-only decision closed，无新行为开关 | [D8 §4](plan-industry-align-next-2026-09-19.md)、[D9 §5](plan-industry-align-refactor-2026-09-18.md) | 不重开集合竞价或 touch/mark；`session_phase` / `price_rule` 可空，v7 schema 不自动扩展；标签不等于真实竞价模型 |

## 2 正确性开关验收覆盖（G1）

这是**既有研究配方/组合的证据索引，不是发车命令或正式配方采纳**。`Y` 仅指所引文档已记录的合成合同/拒绝或接线路径，非本次重跑；`摘要-only` 指后续真湖摘要/归档存在但本次未重审完整宿主回执；`未证实` 不等于从未运行。每行分开写明证据级别。

表内 X-01/02/03 对应 §1 的完整 flag；“旧退出”指未由本行修复改造的退出信号合同。“真实档位”与行情价源分开：TopK 的 qlib 是限价规则，不是 qlib 价源。缓存姿态与输入身份栏区分文档合同和已核回执，未提供实际 hash 就不补造。

| 策略 / 组合 | price-domain flag | cash-order flag / 实际路径 | exit-domain | economics | real-limit | cache posture | input identity | evidence（doc / PR / stamp） | verified? |
|---|---|---|---|---|---|---|---|---|---|
| s12 分钟：X-01 alone | X-01 ON；lake/none，front 经显式上下文转换至 D 日 raw 单位 | X-02 OFF；s12 自有路径 | 既有 MA 规则，使用转换后的历史；raw mark/成交 | 默认 OFF；显式权益独立，`exdiv=None` 防双调 | 独立参考价，非 TopK hook | ON 绕过旧分钟缓存 | 三域源字节 hash + transform/provenance 合同；实际宿主完整 hash 未重审 | [D25 开关/证据](x01-s12-price-domain.md) 合成；[D32 附表](note-lessons-2026-09-25-26-experiment-chain.md#附本次实验链的最终状态) R39/R40、HEAD `343e658` | Y（合成）；摘要-only（真湖）；完整细节未证实 |
| s11 日线/分钟：X-03 alone | X-01 OFF；raw lake 执行 + 独立 1d/front | X-02 OFF；日线不适用 X-02 | X-03 ON；INITIAL/HOLD front；raw mark | 默认 OFF；旧参考映射不派权益 | 保留原参考映射/档位 | 真湖配方分钟显式 `--no-cache`；v11 volume 路径绕过旧无量缓存 | raw/front 源 hash、外层 metadata；池来源须另证，未重审真实池/hash | [D27 合成/真湖配方](x03-s11-exit-domain.md)；[D32 附表](note-lessons-2026-09-25-26-experiment-chain.md#附本次实验链的最终状态) | Y（合成）；摘要-only（真湖）；完整细节未证实 |
| 共享受影响书 / 独立 v7：X-02 alone（合成） | X-01 OFF；原价格域 | X-02 ON；按 hm 与 open/close 推进 | X-03 OFF；旧退出 | 合成 M11–12 含 OFF/ON，不推广到真湖 | 保留既有档位；非切 TopK real 的实验 | 冻结合成输入，不消费旧湖缓存 | D26 记录输入/参数/源码/golden hash 报告合同 | [D26 合成验证与 M 清单](x02-minute-cash-order-2026-09-25.md) | Y（仅合成及 OFF 基线） |
| 共享受影响书 / 独立 v7：X-02 alone（真湖） | X-01 OFF；原域须逐书冻结 | X-02 OFF/ON 独立 A/B | X-03 OFF | 需固定；实际配置未证实 | 需固定；实际配置未证实 | 实际缓存使用未证实 | 原窗/池/seed/费率/快照等冻结要求已写；完整回执未找到 | [D26 真实数据未验证](x02-minute-cash-order-2026-09-25.md)；[基线审计 G1](industry-gaps-bt-2026-09-28.md) | 未证实 / needs Human；紧现金与默认资金两组不能用合成替代 |
| s11 分钟：X-02×X-03 | raw lake + 1d/front；X-01 OFF | X-02 ON | X-03 ON | 默认 OFF；组合实测配置未证实 | 原档位；不得叠 hl | v11 volume 绕过旧无量缓存；组合实测姿态未证实 | 原池/两源/配置 hash 与逐事件回执待核 | [D27 交互边界](x03-s11-exit-domain.md)；[基线审计 G1](industry-gaps-bt-2026-09-28.md) | 未证实；文本合并/单开 PASS 不等于 ON 交互 PASS |
| topk_dropout：非 close 或 walkdown | X-01/X-03 不适用；归档 minute-none | 即使 X-02 flag OFF，`topk_exec != close` **或** walkdown ON 自动入时序路径 | 归档 nostop，不能当 hl 验收 | 默认 OFF；原始配置未重审 | c 为 qlib；d 为 real | 归档实际缓存姿态未重审 | recorder `8a061ea4`；c tip `9e58bde`、d tip `5a3e6e2`；完整 hash 未复核 | [P1](topk-exec-p1-2026-09-27.md)、[P3](topk-exec-p3-2026-09-27.md)、[c](topk-exec-6cell-2026-09-27.md)、[d](topk-exec-6cell-real-2026-09-27.md) | Y（自动接线）；摘要-only（open/intraday 与 walkdown 归档），非全书 X-02 验收 |
| topk_dropout：vwap / walkdown OFF | 同上；X-01/X-03 不适用 | 非 close 自动入时序路径 | 未改卖出合同 | 默认 OFF | qlib 默认；real 可选 | 合成记录；真湖姿态未证实 | P2 固定时钟/预算合同，真湖快照未证实 | [P2 冻结](topk-exec-p2-2026-09-27.md)；[P4](topk-exec-p4-2026-09-27.md) | Y（合成）；真湖未证实；a–d 不含 vwap，vwap×walkdown 拒绝 |
| topk_dropout：real + close / walkdown OFF | minute-none（d 归档） | X-02 OFF：**real 单开不自动切时序**，保留旧 close 调度 | nostop（d） | 默认 OFF；完整回执未重审 | `--topk-limit-rule real` | 实际缓存姿态未重审 | d 同 recorder / tip；完整 hash 未复核 | [P4 close/off 边界](topk-exec-p4-2026-09-27.md)；[d close_plain](topk-exec-6cell-real-2026-09-27.md) | Y（接线）；摘要-only（归档），不是现金时序修复验收 |
| s12 + X-02（含试图叠 X-01） | X-01 任意 | X-02 ON **拒绝** | 不进入模拟 | 不适用 | 不适用 | 不适用 | 拒绝合同，不生成实验身份 | [D26 M05–10](x02-minute-cash-order-2026-09-25.md)；基线 `csv_minute_backtest.py::simulate` 入口守卫 | Y（拒绝），不是待补 PASS 格 |

**后续摘要优先于旧文档的历史“未验证”标题**：D32 已记录 X-01、X-03 真湖 PASS，不能再说“没跑过真湖”；但 **full host receipts not re-audited in this index**。X-01 的摘要指向 `RECEIPT_X01_S12_196f7c6_20260927.md`，本页未定位并核验其宿主完整路径/内容；X-03 的 D32 行也不足以恢复全部配置。若要引用为完整验收，**未证实细节 / needs Human**：须提供实际命令、池与源身份/hash、缓存姿态、开关/economics/限价配置及逐事件归因；本文不把配方要求冒充执行回显。

P3 外置 D5 使用 s12 fix-on + 既有 transform，仅支持该冻结上下文；不替代 X-02 真湖或 X-02×X-03 交互证据。**不得重跑已归档 P3 来填本表**。TopK a–d 的湖末警告、缺行情与不同结束日边界仍以原归档为准；不把 nostop、局部产物相同或 NAV 摘要外推成完整合同等价。

## 3 B1 修正说明（G3 引用精度 · 索引内勘误）

按 Kimi **B1** 记录：[上交所链接 `c_20260424_10816482.shtml`](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml) 是**发布通知页**，Kimi 抓取到的通知正文不含“§6.7 科创板 200 股起申报”条文。本文转录该核稿结论，不声称本次重新核验附件条文号。

未来文档推荐措辞：**「上交所 2026 修订规则（链接为发布通知页；科创板 200 股起申报的条文号未在本次抓取中直接核验，仓内 D23 X-10 独立记录同一规则）」**。

[D23 X-10 与 §4 跟进计划](../reviews/2026-09-25-minute-engine-review/README.md) 独立记录科创板 200 股起、1 股递增；事实有仓内落盘支持。本项是引用精度修正，不是新增 gap，也不认证全板块/订单类型/历史生效日规则表。未来引用[基线审计](industry-gaps-bt-2026-09-28.md) G3 时一并引用本节。

## 4 已裁延期 / 禁止重开（防倒退）

以下承接**[基线审计 §3](industry-gaps-bt-2026-09-28.md#3-明确不做--范围外)、Kimi“不应开工”**；决策关闭不等于真实交易所模型全部完备：

- **#135 classic P1/P4**：A/A docs-only 关闭，14:57–15:00 成交资格与日线 close/NAV mark 分离；不复活集合竞价模型，不因标签空值重开已交付 P2。见 [D8 §4](plan-industry-align-next-2026-09-19.md)。
- **默认翻转**：hl/fen、TopK exec/walkdown/real、X-*、δ3 保持基线；P3/TopK PASS 均不是默认 GO。见 §1 归档。
- **#214 R3/R4**：配股公式、`exdiv=None` / version12-front 语义不借 fen 重写；不静默双调。v4 SMA/raw、无 ex-date 微额兜底与特殊无涨跌幅 regime 不顺带扩围。见 [止损/除权计划](plan-minute-stop-and-exdiv-fix-2026-09-26.md)、[P2](exdiv-ref-fen-p2-2026-09-27.md)。
- **δ1/δ2/δ6 延期面**：真实历史费用账、完整因子/PIT 恢复、缺 bar 权益漏记、补发/恢复、登记日/税务/修订/跨运行生命周期不重开；economics API 已有不代表这些已完成。见 [δ1](plan-industry-align-p3-fees-2026-09-19.md)、[δ2](plan-industry-align-p3-d2-exdiv-2026-09-19.md)、[δ6](plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md)。
- **δ5**：不重做已实现 cap；**#291 已接**共享 CLI `--participation-rate`（opt-in；API 先于 CLI），**仍 ≠δ5 certified ≠R4**，不据此开真实量认证、日线容量或排队/冲击。具名残项 [D5-REAL-VOLUME-INGRESS](note-delta5-real-volume-ingress-2026-09-29.md) 已获 2026-09-29 Human「D GO」仅冻结 version8 独立研究接入文档；实施/湖/生产接线仍待另 GO，无 SSOT 绿灯。version11 分钟 volume=A 的 09:30 未完成桶拒绝是既有合同，不能用未来量补开仓；TopK vwap 前桶是独立模型。见 [δ5](plan-industry-align-p3-d5-volume-cap-2026-09-19.md)、[P2 vwap](topk-exec-p2-2026-09-27.md)。
- **TopK 残余与分钟近似**：不重做 P1–P4，不启动 2025 锚/hash follow-up、Q8 或 vwap×walkdown 移交；OHLC 内部路径、同 close 先卖后买、旧报价 fallback 不扩成 tick/订单簿。见 [TopK tracker §8](topk-joint-research-tracker-2026-09-22.md)、[X-02 限制](x02-minute-cash-order-2026-09-25.md)。
- **version11 Slice D / exporter**：X-03 PASS 不等于静态档案对照完成或策略收益有效；完整 PIT 与浮点边界不由单夹具背书。见 [X-03](x03-s11-exit-domain.md)。
- **X-20/26/27/35/36 与性能线索**：未完成当前全部调用路径核验，**未证实 / needs Human**；禁止从 [D23 旧表](../reviews/2026-09-25-minute-engine-review/README.md) 未经核验直接复活为生产缺陷或实施任务。
- **Cerebro / Rolling / qlib PortAna / Exchange** 不复活；LEBS、MockQMT、OMS/live、云代理与柜台验收不搬入本仓。数据采集/供应商 merge 留在 1.3，本仓仅消费配置湖，缺输入不猜盘、不造数据。见 [定位 SSOT](engine-positioning-ssot.md) 与仓库 `AGENTS.md`。

## 5 下一刀指针（只读）

按 Kimi 调整排序；本节只列候选，**不授权任何实现、实验或默认切换**。

1. **G1**：本文 §2 已完成 docs 验收覆盖索引；未证实格仍未证实，不代表正确性缺口全部解决。
2. **G9**：本文 §1、§4 已完成 docs 状态/防倒退索引，与 G1 共用一份产物。
3. **G2 → G3 → G4 → G5 → G6 → G7**，各项均需 **separate Human GO**，不能从本次 GO 继承实施授权：

| 候选 | 下一份窄产物（未开工） | 依据 |
|---|---|---|
| G2 | 旧共享分钟缓存的来源/快照身份合同；独立 Human GO 实施，仅合成验证，勿合 | [G2 身份守卫合同](g2-minute-cache-identity-2026-09-28.md)；审计 G2；[D25 输入身份](x01-s12-price-domain.md)、[D23 X-12](../reviews/2026-09-25-minute-engine-review/README.md) |
| G3 | 申报 vs fill vs 残量规则表；Human 单独 GO 后实现默认 OFF 的 STAR 普通买入校验（勿合） | 审计 G3；D23 X-10；本页 §3 B1；[G3 合同与反例](g3-star-lot-declare-qty-2026-09-28.md) |
| G4 | Human sequential GO：s11 单一 exporter 双快照/双锚点合成取证 PASS-for-method；无生产修改，完整历史 PIT 未证，勿合 | [G4 方法、冻结桶与结果](g4-front-pit-evidence-2026-09-28.md)；审计 G4；[D27 PIT 边界](x03-s11-exit-domain.md) |
| G5 | Human sequential GO：BT 侧 MQ/BT 联合语义 tie-break 提案 + 当前规则合成锁定；旧 pack/seal 保留、replay 内核不改，政策待联合 Human GO，勿合 | [G5 窄合同与合成证据](g5-jr-semantic-tiebreak-2026-09-28.md)；审计 G5；[D30 §6b](handoff-joint-return-clock-regen-2026-09-24.md)（定位 §6b，不沿用旧页首误指 §7） |
| G6 | Human 单独 GO：v7 frame API 缺省日历冻结为 frame index 日期 ∪ pool 日期；仅 API 修复与合成对照，勿合 | [G6 日历合同与验证](g6-v7-frame-calendar-2026-09-28.md)；审计 G6；D23 X-11；标准 CLI 已传日历且不改 |
| G7 | Human 单独 GO：8.1 精确分档开关默认 OFF；边界与两侧合成验证，SMA 等号另刀，勿合 | [G7 合同与验证](g7-81-float-band-2026-09-28.md)；审计 G7；D23 X-05、D27 末段 |

**G8 另待业务人裁**：s12 lot0 全卖/部分卖/买回后的台阶锚生命周期，不能用行业规则代裁；不改 latch=A/residual=2，不新建策略版本。依据审计 G8、[D25 保留限制](x01-s12-price-domain.md)。

## 6 交叉依赖一句话

见[基线审计 §5](industry-gaps-bt-2026-09-28.md#5-与三线的交叉依赖)：先锁价格域、现金时序与输入身份，再单轴裁决 TopK/#214、参考价/权益、容量/申报量及 joint-return 独立合同；各线不互相代验，资料索引完成不构成下一刀 GO。

## 7 P1/P2 / 统一上限指针（只读 · 非第二默认表）

2026-10-02 Human：P1 docs 已合 #298；P2-A/B/C 已合 #299/#300；统一票里 H-U1=B / H-U2 / H-U3 / H-U4 / H-U7 仍是当时锁（上限=现有 L1/B；U1 docs 已合 #302）。H-U5 开票门见下表 TC1 行。**本索引不另开平行成交默认表**；入口默认继续只链 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。

| 主题 | 指针 | 边界 |
|---|---|---|
| Bar 身份 / PIN | [vendor-bar-alignment-ssot.md](ssot/vendor-bar-alignment-ssot.md) §5/§10/§11/§12；[P1 Human defaults](note-minute-engine-p1-human-defaults-2026-10-02.md) | 身份五元组；非 fill-policy 行 |
| Phase5 / P2-A recipe | vendor-bar §10/§12；[P2 adapters](note-minute-engine-p2-adapters-2026-10-02.md) §2；host `/workspace/handoffs/vendor_lake_phase5_host_20261002/` | **不可**与 START-accept 直接比 PnL |
| #291 + P2-B 预检 | 本页 §1 δ5 行；`participation_rate_precheck.py`；`run_topk_cap_compare.py` | ≠δ5 certified ≠R4；≠ capacity certified |
| P2-C L2↔共享湖 | [L1/L2 边界 §6](note-l1-l2-research-engine-boundary-2026-09-28.md)；P2 adapters §4 | 同 PIN 不同后端 → 红混比；L2 永 opt-in |
| JR-clock G hygiene | [G 回填 note](note-jr-clock-g-host-reverify-backfill-2026-10-01.md)（#297 合入 tip） | ≠δ5≠R4 |
| 统一上限 / U1 | [unify ceiling U1](note-minute-engine-unify-ceiling-u1-2026-10-02.md)；handoff `/workspace/handoffs/minute_engine_unify_plan_20261002/` | 上限=现有 L1/B（旧入口）；不碰 MatchCore/Fees/`simulate`（统一语境） |
| 真核 C-New / TC1 | [C-New TC1 合同冻结](note-true-core-c-new-tc1-contract-2026-10-02.md)；handoff `/workspace/handoffs/minute_engine_true_core_new_20261002/` | H-U6=New；H-TC1=C docs-only；冻 L2 v0；#303 MERGED `fee8f88d`；无 simulate/MatchCore 重写 |
| 真核 TC2 窄 X1 | [TC2 X1 意图适配器](note-true-core-tc2-x1-intent-adapter-2026-10-02.md) | 核外冻结 LIMIT + 现有 runner；适配器身份 only；**不** mint 新 contract/backend_id；≠δ5≠R4；#304 MERGED |
| 真核 TC3 具名消费者 | [TC3 named consumer](note-true-core-tc3-named-consumer-2026-10-02.md) | X1 CLI/HELP 闭环；合成 fixture；永 opt-in；不以 BOOKS 默认为验收；≠δ5≠R4；#305 MERGED `00ab1a24` |
| 真核 TC4 · X8 对照桥 | [TC4 X8 compare bridge](note-true-core-tc4-x8-compare-bridge-2026-10-02.md) | 仅撮合前意图；禁 fills→意图；独立 comparison 根；恒 `no_ssot_compare_authorization`；无成功 summary.json；≠δ5≠R4；#306 MERGED `79b3995c` |
| 真核 X6 合成夹具/attestation | [X6 synthetic attestation](note-true-core-x6-synthetic-attestation-2026-10-02.md) | synthetic_fixture only；Fixture PASS≠lake PASS；拒 lake；独立 tool 根；无新 contract/backend_id；≠δ5≠R4；draft **勿合** |

L2 `minute_orders` 定位：**永 opt-in**（P1 H4=A · 统一 H-U3 · 真核 H-TC9）。G3 科创板申报数量延后（H5=A）。统一语境与 TC1/TC2/TC3/TC4/X6 docs **均不授权**改 MatchCore / Fees / `simulate` / VolumeCap·clamp·完成桶。TC1 已合 #303；TC2 X1 已合 #304；TC3 已合 #305；TC4 X8 已合 #306；X6 合成差分 draft **勿合，等待 Human「合」**。
