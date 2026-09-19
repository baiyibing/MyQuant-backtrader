<!-- agent=codex cmd-prefix=/home/box/.local/bin/codex exec --ephemeral 你是资深 A 股量化交易系统评审专家。请评审下面五份设计稿（同一 docs-only PR 包）。

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


【你的评审侧重】优先审**实现可操作性**：函数名/文件位置/调用链/API 契约——程序员能否照此编码？哪里会卡住？哪些 import 是私有的需 wrapper？ <prompt> -->
**总裁决：GO-WITH-NITS。** 可进入人裁；未发现阻断本次 docs-only PR 的事实错误或生产授权泄漏。δ5 仍有需要在设计阶段补齐的接口与调度细节，不能直接作为生产编码规格。

已通读五份全文，核对指定 HEAD 相对 IMPLEMENTATION_BASE 仅新增这五份文档；下述源码与测试证据均在基线中存在。全程只读，未运行测试、回测或任何写操作。

**🔴 必须修**

无。本轮未发现足以判 BLOCK 的问题。

**🟡 应修**

1. **δ5 应明确“现金门按请求量还是按 cap 后数量判断”。**

   文档 `docs/backtest/plan-industry-align-p3-d5-volume-cap-2026-09-19.md:54` 写“先满足……资金门”，但没有为部分成交明确现金校验数量。基线 `backtest/research/csv_simulate_loop.py:290` 的 pool 路径先按完整预算算量并校验现金，`:365` 的 step 路径也有同类前置校验；`backtest/research/csv_ledger.py:215` 又在记账时校验一次。

   例如请求 500 股、cap 允许 200 股、现金只够 200 股及佣金：保留完整请求量校验会拒绝，按实际成交量校验则可买入。程序员仅在 `execute_buy` 内加 cap，会与前置现金门产生不同结果。

   **建议：** 在 Slice A 增加该真值表，明确两种政策的选择及各调用层责任；按最终数量计费并不自动授权改变现有现金拒绝行为。此项可随 δ5=B 设计补齐。

2. **δ5 共享容量预算还需明确跨 lot 的处理顺序，以及“桶切换重置”的准确含义。**

   文档 `docs/backtest/plan-industry-align-p3-d5-volume-cap-2026-09-19.md:52` 要求所有路径/lot 双向共用预算，`:55` 写桶切换重置，`:66` 已要求重复访问不得重置。但基线分钟书按 lot 扫描全天，而不是按时间统一调度：

   - `backtest/research/csv_minute_backtest.py:623` 遍历 lot，`:629` 对每个 lot 调用全天 `scan_held_day`。
   - `backtest/research/csv_ledger.py:298` 收集 rider，`:304` 递归卖出。

   因此扫描第二个 lot 时可能重新访问更早的桶。若用“当前桶变化就清零”的实现，会重复释放容量；即便使用按键持久保存的预算，同桶多个 lot 的先后分配也仍需定义。

   **建议：** 明确预算按完整 key 保留已用量，并裁定同桶争用顺序；补“第一 lot 命中晚桶、第二 lot 命中早桶”及母仓/rider 共享预算的 oracle。若选择重排成交顺序，应另列行为差异，不能以容量接线名义默许。

3. **δ5 的设计 DoD 应增加数量 API 与返回值契约表。**

   文档 `docs/backtest/plan-industry-align-p3-d5-volume-cap-2026-09-19.md:123` 要求状态设计，但现有接口如何承载部分成交尚未列明：

   - `backtest/research/csv_ledger.py:200`：`execute_buy` 接收预算 `per`，返回 `bool`，内部自行定量。
   - `backtest/research/csv_ledger.py:261`：私有 `_sell` 无数量参数，卖出整个 Position，并可能递归处理 rider。
   - `backtest/research/csv_minute_backtest_v7.py:205`：私有 `_buy` 接收 fraction，返回 Position 或 None。
   - `backtest/research/csv_minute_backtest_v7.py:226`：私有 `_sell_lots` 虽返回实际卖量，但没有数量上限入参。

   **建议：** B 设计增加“请求量由谁计算、谁裁剪、谁提交记账、返回实际量/费用/残量、谁更新 stage”的表。私有函数不能直接被当作稳定的新公共 API；是否引入 wrapper 留给独立 C 实施案。本包及默认 pins 不需要增加生产 wrapper。

**🟢 可选**

- 在 δ3/δ4 的测试说明中列出推荐的测试观察方式，减少实施人员摸索：优先 public simulate；需要观察中间状态时使用保留真实调用的测试 wrapper。已有示例 `tests/test_csv_minute_backtest_v7.py:336` 包装 `_rescale_position` 并继续调用原函数。
- δ4 已提醒测试 helper 不透传 kwargs 的问题，这一点准确：`tests/test_ashare_simulate_predicates.py:65` 接收 kwargs，但 v7 分支 `:68` 未透传。可直接把这个锚点补到 `docs/backtest/plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md:119`，无需修改生产接口。

**✅ 做对的地方**

- **δ3 时间语义描述准确。** `docs/backtest/plan-industry-align-p3-d3-st-pit-2026-09-19.md:36` 区分单调 resolver、空 by-day 优先与窗口前历史缺失；基线 `backtest/research/csv_common.py:85` 和 `backtest/research/ashare_session.py:81` 支持这些结论，没有把日期 as-of 冒充完整 PIT。
- **δ4 区分门通过与成交成立。** 文档 `docs/backtest/plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md:41` 的首开拒绝、held stop/add/timer 分叉，与基线 v7 调用链一致；seed 持仓和自然可达性也明确分开。
- **δ6 没有发生 C creep。** `docs/backtest/plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md:38` 对 Mode B 的限定准确；基线 `backtest/research/unified_exit_modeb.py:423` 确有 `shares /= k`，`:1029` 明示 `no cash dividend`。文档 `:87`、`:147` 坚持生产经济变更必须显式主裁决 C。
- **冻结与范围一致。** 索引 `docs/backtest/plan-industry-align-p3-d345-econ-index-2026-09-19.md:10` 的 A/A/B/A 与各稿一致，`:17` 保持 P1/P2/P4 deferred，没有借次级选项或 Slice C 授权生产。
- **未发现幽灵验收路径。** 四稿引用的 17 个不同 test/gate 路径均存在；§8 明确区分本次文档检查与未来测试。五文档 UTF-8/BOM/NUL 与提交差异 whitespace 检查通过；这不代表未来 pins 已验收。

建议人裁表：

| 项目 | 建议 | 授权边界 |
|---|---|---|
| δ3 | A | 保留分叉，后续合同与 data-free pins |
| δ4 | A | 保留 None 行为，补真实成交/拒绝对照 |
| δ5 | B（design） | 补齐上述数量、预算顺序和接口合同；生产冻结 |
| δ6 | A；账本设计可另选 B | shares/cash/NAV 变更必须显式主裁决 C、独立实施案 |
| P1/P2/P4 | 维持 deferred | 不重开 fill window、trades 列、touch↔mark |

**是否可进人裁：yes。人裁 GO 前仍禁止编码；本结论不授权合并 #124 或启动 feat/impl PR。**
