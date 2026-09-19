你是资深 A 股量化交易系统评审专家。请评审下面五份设计稿（同一 docs-only PR 包）。

【待评审文档】请先用读文件工具读完全文：
1. docs/backtest/plan-industry-align-p3-d3-st-pit-2026-09-19.md
2. docs/backtest/plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md
3. docs/backtest/plan-industry-align-p3-d5-volume-cap-2026-09-19.md
4. docs/backtest/plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md
5. docs/backtest/plan-industry-align-p3-d345-econ-index-2026-09-19.md
需要时读仓内相关代码/文档取证（以事实为准）。IMPLEMENTATION_BASE=`1049b904bdd818dbb79f51f1830a008c8f83b141`；本 PR HEAD=`1e9994e88a67d0f5f651953fa7ad0e57b59a3677`。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作（除你被编排器要求写入的本席位评审 md）。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴；评审意见本体控制在 350 行内；时间紧时优先保 🔴 与总评。
- Docs review only：不合并 #124，不开 feat/impl PR，不改生产 Python。

【并行轮次说明】
本轮为并行 fan-out。完成时点不定——若读到其他席位已完成意见可交叉核对；没读到就独立完成，不要等待或轮询。

【特别审查焦点（本包必查）】
1) 假断言 vs as-built anchors / IMPLEMENTATION_BASE（file:line 必须可在基线核验）
2) production-freeze 泄漏（silent 行为变更、把默认 A/B 写成已授权生产）
3) δ6 C creep：Mode B fractional shares / `shares/=k` 被误读为已关闭真实经济；生产 shares/cash/NAV 必须显式人裁 C
4) P1/P2/P4 scope bleed；不得借本包重开 fill window / trades 列 / touch↔mark
5) 缺失或弱化的 F-R locks、弱人裁表、幽灵测试命令（§8 命令不可执行 / 指向不存在路径）
6) δ3–δ6 + index 互相矛盾（默认、顺序、冻结表、依赖）

【本仓背景】
- 第一方回测是向量化 CSV（日线/分钟）+ path-SSOT。Cerebro/Rolling 已退场。无实盘。
- δ1 fee / δ2 exdiv reference 已合；本包是后续契约/设计，非实施。
- 工作假设（非人裁）：δ3=A, δ4=A, δ5=B(design), δ6=A(+optional ledger B; prod C explicit)。

【裁决原则】
- 事实类 → 以代码与实验为准；经验类 → 以 A 股量化惯例为准。
- 证据优先，不计票。

【输出格式】
按严重度分级，每条尽量带 file:line：
- 🔴 必须修（事实错误 / 会误导实现 / 逻辑矛盾）
- 🟡 应修（设计缺口 / 风险；可进 Slice B / § notes）
- 🟢 可选
- ✅ 做对的地方
末尾必须给出：
1) 总裁决一句：**GO** / **GO-WITH-NITS** / **BLOCK**
2) 建议人裁表：δ3 / δ4 / δ5 / δ6（及是否维持 P1/P2/P4 deferred）
3) 是否可进人裁（yes/no；人裁 GO 前仍禁止编码）
