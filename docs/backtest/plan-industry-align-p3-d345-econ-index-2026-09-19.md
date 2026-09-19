# Index: industry-align P3 δ3–δ6 follow-up plans (2026-09-19)

> **Status**: **v0.1 · docs-only · 四份 plan 供后续人裁**，未实施其中任何未来 Slice A→B→C。
> **IMPLEMENTATION_BASE**: `1049b904bdd818dbb79f51f1830a008c8f83b141`，本 worktree 起点已用 `git rev-parse HEAD` 核实（全 40 字符；post #123，含 δ1 fee + δ2 exdiv reference contract）。
> **本 PR 范围**: 仅下列四份独立 plan 与本索引；不改生产/测试代码，不跑测试、回测或湖，不使用云端代理/嵌套 Codex。

建议顺序：**δ3 契约 → δ4 契约 → δ5 设计 → δ6 经济人裁**。这是讨论与准备顺序，不是对四刀生产改造的批量 GO，也不承诺运行行为必须逐刀改变。

| 顺序 / plan | 主要决定 | 推荐默认 / 生产边界 |
|---|---|---|
| 1. [δ3 ST PIT](plan-industry-align-p3-d3-st-pit-2026-09-19.md) | 书名单日期 as-of vs v7 窗口末次名称；先固定名字→档位→门→fill | A：未来 docs + data-free pins；不自动修 v7，不把书日期 as-of 当数据可得时刻 PIT 认证 |
| 2. [δ4 v7 limits=None](plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md) | 无昨收/未知板块，首开拒绝 vs held stop/add/timer 不拦截 | A：先合同化；改 fail-closed/显式策略须单独人裁和生产案，不能 silent 改成交 |
| 3. [δ5 participation cap](plan-industry-align-p3-d5-volume-cap-2026-09-19.md) | volume 单位/可得性、共享预算、部分成交与费用/lot 状态 | B：仅设计/契约；不在本刀接生产 cap；零量过滤不等于容量已限制 |
| 4. [δ6 exdiv economics](plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md) | 送转权益/现金红利/应收与到账/NAV 守恒 | A：残留+oracle pins；可选 B 设计账本；**生产增股/入账/NAV 只有显式人裁 C 才授权另案实施** |

[δ1](plan-industry-align-p3-fees-2026-09-19.md) 已锁研究代理佣金与调用粒度；[δ2](plan-industry-align-p3-d2-exdiv-2026-09-19.md) 已锁 E-R6 参考价缩放及其受限条件。经济残留在 δ2 继续 deferred，δ6 现在只打开供人裁；不得把它从“待裁”写成“已关”。Mode B `shares /= k` / fractional shares 是独立近似，不证明书/v7 真实经济权益已记账；本次也没有收益改善证据。

**P1/P2/P4 仍挂起**：P1=14:57 fill window，P2=trades 新列，P4=touch↔mark 耦合；[next plan](plan-industry-align-next-2026-09-19.md) 既有 A/A/A/A 是继续延后。各新 plan 的 `P3δN.*` 是局部人裁编号，不能覆盖旧裁决；`Slice C` 是未来验收阶段，与人裁选项 C 无关。主层级 B/其它次级设计选择不授权生产修改。

四份 plan 各自包含重新核对的基线 file:line、已关/仍钉/deferred、roadmap、F-R*、P* A/B/C、Non-goals、未来 slices、§8 真实命令、§9 22 文件冻结表（δ1/δ2 超集）和 v0.1 changelog。每份均可独立审阅；旧 plan、engine SSOT 与历史评审保持原文。

本次验收只执行各 plan §8.1 与 §8.3 的文档/冻结检查，并核对引用、文件/行号、数组与表一致性；§8.2 的真实 pytest/gates 是未来 data-free 实施路径，**本 PR 未执行**，不挪用历史 δ1/δ2 成绩。全路径白名单精确限制五份文档（含未跟踪、staged、unstaged、base→HEAD），比有限冻结表更严格。提交/推送后只开一个 docs PR，不合并，不触发额外云端评审或宿主任务。

本次本地文档核验（2026-09-19）：四份 plan 的 §8.1/§8.3 逐字提取执行均 exit 0；五文件 UTF-8/BOM=0/NUL=0，22 文件冻结数组/表一致且包含 δ1/δ2 全部冻结路径。静态核对 85 个 file:line 引用的文件/行号范围、41 个本地链接、316 处 Python 路径引用、11 处具名测试引用均通过，命令块 Bash 语法通过；语义锚点来自前述人工源码核对。这些数字只记录文档检查，不是生产 tests passed 数。

发布环境记录：源 worktree `/workspace/wt-p3-d345-econ-plans` 的共享 Git 元数据只读，`git add` 无法创建 `index.lock`。发布使用同一基线/分支的可写副本 `/tmp/p3-d345-econ-publish`，只复制这五份文档；源 worktree 文档保留。发布副本提交后再次检查 base→HEAD 五文档白名单、生产冻结及两处文档字节一致性；不修改共享 Git 权限或其它 worktree。

## Changelog

- **v0.1 (2026-09-19)**：建立四刀独立计划索引与顺序、默认 A/A/B/A（δ6 可 B）和显式 C 边界；固定 post #123 基线。仅 docs，P1/P2/P4 仍挂起，未实施生产/测试或运行回测/湖。
