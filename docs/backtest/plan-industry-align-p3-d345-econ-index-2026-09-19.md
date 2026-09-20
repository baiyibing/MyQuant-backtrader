# Index: industry-align P3 δ3–δ6 follow-up plans (2026-09-19)

> **状态交叉引用（2026-09-20）**：Human GO P2=B 仅授权书 trades 的 `session_phase` / `price_rule` 两列，覆盖本文历史 P2 延后记录；P1 已 closed as A，P4 仍 deferred，本文 δ 合同不重开。见 [schema SSOT](engine-ashare-correctness.md#p2-trades-标签列human-go-b2026-09-20)。
> **Status**: **v0.3 · δ6 Slice A→B→C passed（2026-09-19，Asia/Shanghai）**：δ3/#125、δ4/#126 契约/pins 已落，δ5/#127 仍 design-only；δ6 在 post #127 固定基线上完成残留+oracle 与可选账本 B docs，生产 Python 零 diff、经济残留未关闭、C 未授权/未实施。P1/P2/P4 继续挂起；本次未提交，详见 [δ6 §8.4](plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md#84-本次运行记录与验收范围)。
> **原提案 IMPLEMENTATION_BASE（历史）**: `1049b904bdd818dbb79f51f1830a008c8f83b141`，本 worktree 起点已用 `git rev-parse HEAD` 核实（全 40 字符；post #123，含 δ1 fee + δ2 exdiv reference contract）。
> **v0.2 GO 记录范围（历史）**: 仅下列四份独立 plan、本索引与 [r1 merge-consensus](../architecture/reviews/2026-09-19/plan-industry-align-p3-d345-econ-r1/merge-consensus.md)；不改生产/测试代码，不跑测试、回测或湖，不使用云端代理/嵌套 Codex。

v0.2 GO 记录（历史；当前进度见顶部与各 plan）：**合并 PR #124 → feat δ3 契约 → δ4 契约 → δ5 设计 → δ6 残留+oracle（账本可选 B docs）**。本轮 Human GO 授权 δ3/δ4 未来 **Slice A→B→C docs + data-free pins**，仅契约化、生产冻结；δ5 仅设计落地；δ6 仅残留+oracle，账本设计可选 B 且限文档。**所有生产选项 C 均未授权**；验收 Slice C 不等于生产选项 C。本次只记录 GO，不开 feat、不实施 slices、不执行合并。

| 顺序 / plan | 主要决定 | 已录入 Human GO / 生产边界 |
|---|---|---|
| 1. [δ3 ST PIT](plan-industry-align-p3-d3-st-pit-2026-09-19.md) | 书名单日期 as-of vs v7 窗口末次名称；先固定名字→档位→门→fill | δ3=A：契约 + data-free pins，不改生产 |
| 2. [δ4 v7 limits=None](plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md) | 无昨收/未知板块：首开保持拒绝，held stop/add/timer 显式 fail-closed | 新 Human GO C/B/A：生产 fail-closed 已落地，覆盖此前 δ4=A；复用 reason、无开关；验收见 δ4 §8.4 |
| 3. [δ5 participation cap](plan-industry-align-p3-d5-volume-cap-2026-09-19.md) | volume 单位/可得性、共享预算、部分成交与费用/lot 状态 | δ5=B：只设计，不接生产 cap |
| 4. [δ6 exdiv economics](plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md) | 送转权益/现金红利/应收与到账/NAV 守恒 | δ6=A：残留+oracle；账本可选 B；**生产增股/入账/NAV 须另裁 C，本轮不授权** |

[δ1](plan-industry-align-p3-fees-2026-09-19.md) 已锁研究代理佣金与调用粒度；[δ2](plan-industry-align-p3-d2-exdiv-2026-09-19.md) 已锁 E-R6 参考价缩放及其受限条件。经济残留在 δ2 继续 deferred，δ6 已人裁 A（账本可选 B docs），生产经济变更仍须另裁 C；不得把残留写成“已关”。Mode B `shares /= k` / fractional shares 是独立近似，不证明书/v7 真实经济权益已记账；本次也没有收益改善证据。

**P1/P2/P4 仍挂起**：P1=14:57 fill window，P2=trades 新列，P4=touch↔mark 耦合；[next plan](plan-industry-align-next-2026-09-19.md) 既有 A/A/A/A 是继续延后。各新 plan 的 `P3δN.*` 是局部人裁编号，不能覆盖旧裁决；`Slice C` 是验收阶段，与人裁选项 C 无关。主层级 B/其它次级设计选择不授权生产修改。

v0.1 文档范围（历史）：四份 plan 各自包含重新核对的基线 file:line、已关/仍钉/deferred、roadmap、F-R*、P* A/B/C、Non-goals、未来 slices、§8 真实命令、§9 22 文件冻结表（δ1/δ2 超集）和 v0.1 changelog。每份均可独立审阅；旧 plan、engine SSOT 与历史评审保持原文。

v0.1 原始提案验收/发布记录（历史）：当时只执行各 plan §8.1 与 §8.3 的文档/冻结检查，并核对引用、文件/行号、数组与表一致性；§8.2 的真实 pytest/gates 是未来 data-free 实施路径，**本 PR 未执行**，不挪用历史 δ1/δ2 成绩。当时全路径白名单精确限制五份文档（含未跟踪、staged、unstaged、base→HEAD），比有限冻结表更严格；提交/推送后只开一个 docs PR，不合并，不触发额外云端评审或宿主任务。本次 GO 允许 #124 合并，后续 feat 基线在合并后另行刷新；本次保持 `IMPLEMENTATION_BASE`、白名单、冻结表及 §8 命令原样。

v0.2 本地文档核验（2026-09-19，历史）：四份 plan 的 §8.1/§8.3 逐字提取执行均 exit 0；五文件 UTF-8/BOM=0/NUL=0，22 文件冻结数组/表一致且包含 δ1/δ2 全部冻结路径。静态核对 85 个 file:line 引用的文件/行号范围、41 个本地链接、316 处 Python 路径引用、11 处具名测试引用均通过，命令块 Bash 语法通过；语义锚点来自前述人工源码核对。这些数字只记录文档检查，不是生产 tests passed 数。

原提案发布环境记录（历史）：源 worktree `/workspace/wt-p3-d345-econ-plans` 的共享 Git 元数据只读，`git add` 无法创建 `index.lock`。发布使用同一基线/分支的可写副本 `/tmp/p3-d345-econ-publish`，只复制这五份文档；源 worktree 文档保留。发布副本提交后再次检查 base→HEAD 五文档白名单、生产冻结及两处文档字节一致性；不修改共享 Git 权限或其它 worktree。

## Changelog

- **v0.3 (2026-09-19，Asia/Shanghai)**：记录 δ6 在固定基线 `3668e256abec1258759b99a72e3b3c17d082e75c` 完成 Human GO A 残留+oracle、可选账本 B docs 与验收；新增4个 design_only 函数/5例，复用既有残留和 Mode B 边界，实际测试与冻结结果见 δ6 §8.4。生产经济残留未关闭，must-cut-C=NO；保留原提案记录，δ5 仍 design-only，P1/P2/P4 deferred。

- **v0.2 (2026-09-19，Asia/Shanghai)**：录入 PR #124 tip `7eeb475` 的权威 Human GO：δ3=A、δ4=A、δ5=B（只设计）、δ6=A（账本可选 B，仅 docs；生产增股/入账/NAV 须另裁 C，本轮不授权），P1/P2/P4 继续挂起。授权后续 δ3/δ4 Slice A→B→C 契约+data-free pins，δ5 设计落地、δ6 残留+oracle；未实施任何 slice，未改生产/测试或运行测试/回测/湖，基线与冻结不变。
- **v0.1 (2026-09-19)**：建立四刀独立计划索引与顺序、默认 A/A/B/A（δ6 可 B）和显式 C 边界；固定 post #123 基线。仅 docs，P1/P2/P4 仍挂起，未实施生产/测试或运行回测/湖。
