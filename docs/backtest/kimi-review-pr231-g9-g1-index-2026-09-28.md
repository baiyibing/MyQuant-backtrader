# 评审：MyQuant-backtrader PR #231（docs-only：G9+G1 industry state/acceptance index）

评审人：Kimi（只审不改）。日期 2026-09-28（Asia/Shanghai）。

- 工作树：`/workspace/wt-g9-g1-index`，`git status` 干净。
- HEAD 核实：`git rev-parse HEAD` = `b8ede8de5a4520a159ae6cf68c8612041a1c3bfc`，与要求一致。
- 变更范围：`git diff --stat 21adb69..HEAD` = 2 个文件、+106 行：
  - `docs/backtest/industry-state-acceptance-index-2026-09-28.md`（新增 104 行，主文件）
  - `docs/backtest/plan-industry-align-next-2026-09-19.md`（+2 行，页首只读入口指针）
- 对照材料已读：主文件全文、指针 diff、`/workspace/INDUSTRY_GAPS_BT_2026-09-28.md`（基线审计，248 行）、`/workspace/KIMI_REVIEW_INDUSTRY_GAPS_BT_2026-09-28.md`（先前核稿，APPROVE_WITH_NITS）。
- 未改任何仓库文件，未 push / merge / 开 PR，未写任何 `.py`。

## 总评：APPROVE

这是一份执行精度很高的只读索引。它严格完成了 Human 批准的范围（「先做 G9+G1 合并只读索引（顺带修 B1），其余逐项单独 GO」），三种状态区分（已实现默认 OFF / docs-only 决策关闭 / API 存在但 CLI 未接）从审计原稿一路保持到索引表格；B1 引用勘误按先前核稿的建议措辞落地且明确转录边界；#230 合并状态与 defaults 未翻转的表述经 git 核实无误；G2–G7 逐项标明 separate Human GO。未发现事实漂移、未发现把未证实写成已完成的实例。仅有的瑕疵是链接/措辞级 nit，不阻塞合并。

## 必核项逐条判定

| # | 准则 | 判定 | 证据 |
|---|---|---|---|
| 1 | Docs-only？无 .py / 默认翻转 / 编造 lake 完成声称？ | **PASS** | diff 仅 2 个 `.md`，+106 行，零 `.py`、零配置、零测试变更。frontmatter `status: "docs-only index; no implementation; no default flip; no new lake GO"`；§1 表头明示「PASS 不等于翻默认 GO」；§4 专列「默认翻转」防倒退条目（hl/fen、TopK exec/walkdown/real、X-\*、δ3 保持基线）。§2 对真湖证据一律标「摘要-only」「完整细节未证实」「full host receipts not re-audited in this index」，无编造完成声称。 |
| 2 | 是否真正把 G9 state + G1 acceptance coverage 合并成一个产物？ | **PASS** | 单一文件内：§1「当前默认 vs opt-in（状态面 · G9）」13 行状态表 + §4「已裁延期/禁止重开」覆盖审计 G9 建议的「默认、opt-in、最新验收、未验范围、已裁延期」五要素；§2「正确性开关验收覆盖（G1）」9 行 × 10 列矩阵逐列对应审计 G1 建议的「价格域、现金时序、economics、真实档位、缓存、输入 hash、已验组合」。§5 明确写「G1：本文 §2 已完成…G9：本文 §1、§4 已完成…与 G1 共用一份产物」。合并方式与先前 Kimi 核稿「G1 第一、G9 提至第二、合并为同一只读产物」的建议一致。 |
| 3 | B1 引用卫生是否到位且正确？ | **PASS** | §3 完整落地先前核稿 B1：明示 SSE 链接是**发布通知页**、通知正文不含「§6.7 科创板 200 股起申报」条文、条文号未在本次抓取中直接核验；推荐措辞与核稿建议逐字吻合。仓内落盘支持经核实：`docs/reviews/2026-09-25-minute-engine-review/README.md:44`（X-10 行「科创板 688/689…规则是 200 股起」）与 `:140`（§4「科创板 200 股起、1 股递增（X-10）」）——「D23 X-10 独立记录同一规则」属实。§3 末句「本文转录该核稿结论，不声称本次重新核验附件条文号」的边界声明诚实。 |
| 4 | 是否正确写明 #230 已合于 `21adb69` 且 defaults 未翻转？ | **PASS** | git 核实：`21adb69` 的提交标题即 `docs(research): record stop/exdiv P3 true-lake A/B 20260927e (#230)`，确为 #230 的 squash-merge 且正是本 PR 的 base。索引两处表述一致：开头段「本 PR 已 rebase 到 master tip `21adb69`（#230 squash-merge：docs stop/exdiv P3 `20260927e` archive）…#230 **已合入**且 **defaults not flipped**」；§1 P3 行「[#230] **已 squash-merge** 入 master tip `21adb69`（docs archive only；本任务未合并；非本索引前置依赖）」。同时正确保留了审计基线（`8a6d6c3`）与 PR base 的区分，并说明「当前默认/opt-in 仍以审计基线为准」。 |
| 5 | 剩余 G2–G7 是否各自标明需单独 Human GO（未授权）？ | **PASS** | §5：「本节只列候选，**不授权任何实现、实验或默认切换**」+「G2 → G3 → G4 → G5 → G6 → G7，各项均需 **separate Human GO**，不能从本次 GO 继承实施授权」，并附 6 行候选表（每项含「下一份窄产物（未开工）」与依据链接）。G8 单独标明「另待业务人裁…不能用行业规则代裁」。指针文件新增段落同样写明「G2–G7 仍须逐项 Human GO」。与审计 §2 各 G 条「是否依赖人裁 GO」的判定一致。 |
| 6 | 相对已批审计有无事实漂移？ | **PASS** | 逐项抽查无漂移：(a) defaults 转述与审计 §1.1 一致——hl 默认 `close`、fen OFF、TopK `close`/walkdown OFF/`qlib`、X-01/02/03 OFF、δ3 v7 flat、δ5/δ6 API `None`（OFF）；(b) **未**声称 X-02 true-lake 完成——§2 专列「X-02 alone（真湖）」行标「未证实 / needs Human」，§1 X-02 行写「共享书/v7 的完整真湖验收未证实，不从 TopK 归档推导全书 PASS」，与审计 G1「所读资料未找到其完整真湖验收归档」一致；(c) **未**重开 #135 P1/P4——§1 末行与 §4 首条均写「A/A docs-only 关闭…不复活集合竞价模型，不因标签空值重开已交付 P2」；(d) X-01/X-03 表述精确复刻审计 §1.2 的状态纠正——「D32 已记录真湖 PASS，不能再说没跑过真湖；但 full host receipts not re-audited」，且 X-01 的 RECEIPT 文件名（`RECEIPT_X01_S12_196f7c6_20260927.md`）经核与 D32:89 原文一致，索引如实标注「本页未定位并核验其宿主完整路径/内容」；(e) TopK hash 转述（recorder `8a061ea4`、c tip `9e58bde`、d tip `5a3e6e2`）经核与 `topk-exec-6cell-2026-09-27.md:12,18`、`topk-exec-6cell-real-2026-09-27.md:13` 源文档一致；(f) X-07 行保留审计的关键警示「不能把 X-07 整体写为默认 OFF」。 |
| 7 | 链接/表格卫生 | **PASS（仅 nits）** | 索引引用的 26 个仓内相对链接逐一核文件存在性，全部命中（含 `../reviews/2026-09-25-minute-engine-review/` 的 README 与 raw/crosscheck-grok.md）；D32 附表锚点 `#附本次实验链的最终状态` 与源文档 `:83` 标题「## 附：本次实验链的最终状态」匹配。两处外置 `/workspace/` 绝对路径链接（frontmatter sources、§6）是刻意设计且正文已明示「这两份来源在 Bot VM 的 `/workspace/`、git 之外；普通 clone 不包含它们」——可接受，见 nit 1。§5 G5 行「定位 §6b，不沿用旧页首误指 §7」的勘误经核正确（D30:3 页首确写「见 §7」，实际内容在 `:61` 的「## 6b」）。无实质问题。 |

## 发现（非阻塞观察）

1. **#230 状态表述比审计原稿更准**：审计 frontmatter 写「#230 docs P3 archive open（未联网核验 PR 状态）」，索引利用 rebase 后的 git 事实将其更新为「已 squash-merge 入 `21adb69`」，并加了三重限定（docs archive only / 本任务未合并 / 非本索引前置依赖）。这是正确的状态推进，不是漂移。
2. **§2 表格的证据分级纪律**：`Y（合成）`、`摘要-only（真湖）`、`未证实 / needs Human`、`Y（拒绝），不是待补 PASS 格` 四级区分在每行独立标注，表前还有一段专门定义「Y」「摘要-only」「未证实」的语义边界。这正是审计 G1 要求而旧文档最容易糊掉的部分。
3. **指针文件的增量克制**：`plan-industry-align-next-2026-09-19.md` 仅 +2 行页首指针，明示「不改本计划人裁状态」，未触碰 P4=A closure 等历史状态区。处理正确。

## Nits

1. **外置绝对路径链接在 GitHub 渲染下为死链**：frontmatter `sources` 与 §6 的 `/workspace/INDUSTRY_GAPS_BT_2026-09-28.md`、`/workspace/KIMI_REVIEW_INDUSTRY_GAPS_BT_2026-09-28.md` 在普通 clone / GitHub 页面不可点达。正文开头已声明这一边界，属知情设计；若未来希望仓外读者可溯源，可考虑把两份外置文件以附录或 gist 形式固化（本 PR 不要求）。
2. **§2 表列宽与可读性**：10 列 × 9 行的矩阵在窄终端渲染会严重折行（尤其「evidence」与「verified?」列的长限定语）。信息完整性优先于此是合理取舍，仅提示后续如需打印/分享可考虑拆分。
3. **§1 δ3 行「审计 §1.1」是自引用外置审计的章节号**：仓内读者无法直接跳转（外置审计不在 git）。同 nit 1，属同一类知情设计，不单列。

## 结论

**APPROVE**。PR #231 精确执行了已批范围：G9 状态面与 G1 验收覆盖合并为单一 docs-only 产物，B1 引用勘误按核稿建议落地，#230 合并状态与 defaults 未翻转经 git 核实无误，G2–G7 逐项锁定 separate Human GO，相对已批审计零事实漂移。仅 3 条链接/排版级 nit，均不阻塞合并。可合。
