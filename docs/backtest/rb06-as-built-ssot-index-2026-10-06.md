# RB-06 as-built SSOT 索引（2026-10-06）

核查 tip：`f72301c64de700b5474ec03a65b6628830f0cf14`（`f72301c`）。
授权：RB-06 docs / pointers / lists only，ZERO-DIFF；不改模拟代码、fixtures、
baselines、HELP_LOCK、书顺序、注册逻辑或 capabilities，不实施 RB-07 CI 重构。
采用 H-RB-03 A：as-built 索引 + superseded 指针 + 窄幅修订，保留历史裁定。
历史笔记可能仍写“deferred”；当前状态以本索引及明确的 superseded banner
所指向的实施记录为准，不把所有历史段落改写成最终状态。

## 当前引擎与合同

- 当前研究成交引擎为向量化 CSV 日线 / 分钟书，见
  [成交引擎定位 SSOT](engine-positioning-ssot.md)。Cerebro / Rolling
  已于 2026-09-16 退场，禁止复活或为新策略开启。
- v7 / APP 已折入主分钟 host：`csv_minute_backtest.simulate` 拥有
  version7 状态、日历与日循环；native fold 保留原生书语义，v7 shim
  与 APP 独立 CLI 可保留。version7 仅 minute-only 注册，不加入共享
  CLI / 日线 BOOKS。见 [v7 / APP 主分钟引擎迁移](v7-main-engine-migration-2026-10-06.md)。
- [A 股成交核正确性 SSOT](engine-ashare-correctness.md)：§1 已标明
  旧 v7 独立仓位机 / 路径行号被迁移记录覆盖；有用的费用与 schema
  合同记录保留，按各行记录时点和 superseded 指针阅读。
- [分钟成交假设 SSOT](minute-fill-policy-ssot.md) 保持默认锁与混比边界。
- 仓库规则：[AGENTS.md](../../AGENTS.md)、[CONTRIBUTING.md](../../CONTRIBUTING.md)。
- B7 / B8 的旧 deferred 结语是历史记录；见
  [2b 决策记录及其已实施章节](note-2b-decisions-2026-10-05.md)、
  [B7 实施说明](note-b7-on-short-cash-2026-10-05.md)、
  [B8 实施说明](note-b8-lot-rounding-2026-10-06.md)。

## RB-01–RB-04 与 capabilities

- [RB-01 GitHub branch protection 步骤](rb01-github-branch-protection-steps-2026-10-06.md)。
- [RB-02 register / alias guard](rb02-register-alias-guard-2026-10-06.md)。
- [RB-03 baseline admission checklist](rb03-baseline-admission-checklist-2026-10-06.md)。
- [RB-04 per-purpose capability truth table](rb04-book-capabilities-truth-table-2026-10-06.md)。
- [book_capabilities.py](../../backtest/research/book_capabilities.py) 是能力集合真身；
  price-add 与 S8 independent 分开，按显式 membership，无自动家族继承。
  本次不改任何集合或能力。

## 当前 CI data-free / admission gates

以下名单与 [Python CI workflow](../../.github/workflows/python-tests.yml)
的 `verify_*` 步骤一致；无湖访问。

| 阶段 | Gate |
| --- | --- |
| pre-pip | [verify_oskh_data_contract.py](../../scripts/gates/verify_oskh_data_contract.py) |
| pre-pip | [verify_data_path_ssot.py](../../scripts/gates/verify_data_path_ssot.py) |
| pre-pip | [verify_no_hardcoded_machine_paths.py](../../scripts/gates/verify_no_hardcoded_machine_paths.py) |
| pre-pip | [verify_tr_bridge_import_ssot.py](../../scripts/gates/verify_tr_bridge_import_ssot.py) |
| post-pip（需要已安装研究依赖） | [verify_book_admission.py](../../scripts/gates/verify_book_admission.py) |
| post-pip（需要已安装研究依赖） | [verify_baseline_admission.py](../../scripts/gates/verify_baseline_admission.py) |

MC-6：CI workflow 与 [pre-push hook](../../.githooks/pre-push) 共用 pytest
marker 表达式 `not production and not benchmark`；hook 仅推 master / main 时
运行该 pytest。本次只记录一致性，保留现有引号与 Windows 行为，不提取
共享 marker 文件，不重设计 workflow。
