# Plan：Cerebro 全局退场（策略书栈 + chip/ma_chip 宿主薄壳）

> **落盘**：2026-09-16。
> **状态**：✅ **已实施并合入**（PR [#58](https://github.com/baiyibing/MyQuant-backtrader/pull/58)，merge `e89d1b8`，2026-09-16；切片 A→D 全部完成；合入后复核 PASS：删除集空、纯逻辑保留、SSOT 四文件同步、树内 `import backtrader` 零命中）。
> **风险档**：**L1**（纯删除 + SSOT 措辞修订；不写湖、不碰 1.3、不碰 CSV 成交核）。
> **工作流**：走 [Codex 交接工作流](../../workflow-codex-handoff.md)。
> **动因**：[plan-money-modes-v8-pername](plan-money-modes-v8-pername-2026-09-16.md) 评审 🔴1 暴露 v8 止损双真源（`ProfitStrategy.py:760` Cerebro 预设 vs `strategy8_rules.py`）；人裁方向：**全局去掉 Cerebro**——入场/筹码逻辑不依赖回测框架，框架耦合的只是薄壳。
> **上游**：[engine-positioning-ssot.md](../../engine-positioning-ssot.md)（§2/§5 已同步为 Cerebro 全局退场、chip/ma_chip 静态归档；按其 §6 四文件同 commit 修订）。

---

## 0. 一句话

删掉本仓全部 backtrader/Cerebro 代码路径（两个分组一次退场），纯逻辑（chip 计算、Rust TR、入场条件）全部保留或已有无框架 SSOT；SSOT 四文件同步修订。退场后 v8 等策略参数只剩 `strategy8_rules` 一个真源。

---

## 1. 依赖事实（2026-09-16 退场前清单，实施记录见 §7）

| 分组 | 文件 | 依赖事实 | 处置 |
|------|------|----------|------|
| **策略书栈** | `backtest/ProfitStrategy.py`（:760 v8 预设 20%、:673 构造默认） | 仅被 `preset_strategy_adapter.py` + `tests/test_backtest_profit_strategy.py` + `tests/test_profit_strategy_preset_parity.py` import | 删 |
| | `backtest/preset_strategy_adapter.py` | 仅服务 Cerebro 栈 | 删 |
| | `backtest/backtest_main_full.py`（Cerebro 菜单入口，:221 v8 文案） | 无其他模块 import | 删 |
| | `backtest/rolling_investment_strategy.py`、`backtest/portfolio_manager.py`、`backtest/qmt_utils_adv.py` | **零 import 方（已是死代码）** | 删 |
| | `backtest/LimitUpDownManager.py`、`backtest/TPlus1QueueManager.py`、`backtest/StockStatus.py` | 仅被 `portfolio_manager.py` import | 连带删 |
| **chip/ma_chip 宿主壳** | `backtest/research/ma_chip_edge_backtest.py`（:28 `import backtrader`；全文仅 14 处 `bt.`/cerebro 引用 = 薄壳） | 入场逻辑（MA + BB 突破 + cyqk 阈值 + 指数 MA5/10 过滤）为纯日频条件，框架无关 | 删（逻辑去向见 C-R2） |
| | `backtest/research/chip_backtest.py`、`chip_selection_backtest.py`、`chip_factor_analysis.py`（各自 `import backtrader as bt`） | Cerebro 宿主壳 | 删 |
| | `backtest/research/verify_cerebro_chip.py` | 存在意义 = Cerebro chip 平价校验，随框架死 | 删 |
| | `backtest/chip_indicator.py`（:44 `ChipDistribution(bt.Indicator)`、:198 `TurnoverChipFactor(bt.Indicator)`） | bt 指标子类壳 | 删 |
| | `backtest/legacy/mock_qmt_backtrader_adapter.py` | backtrader 适配器；MockQMT 真栈在 1.3 | 删（实施时确认无残余 import） |
| **纯逻辑（保留，不动）** | `backtest/chip_algorithm.py`（**无 bt 引用**） | 纯计算 | 保留 |
| | `oskh_factors/chip/`（core/bands/shares/adj_factor…，**无 bt 引用**） | 研究面筹码 SSOT（h11–h15 成果） | 保留 |
| | `turnover-resist/`（Rust） | TR/cyqk SSOT | 保留 |
| | `strategies/tr_filter`、全部 `csv_*` 引擎与 `*_rules.py` | 向量化面 | 保留 |

测试删除清单：`tests/test_backtest_profit_strategy.py`、`tests/test_preset_strategy_adapter.py`、`tests/test_profit_strategy_preset_parity.py`、`tests/test_chip_indicator_warmup_semantics.py`、`tests/test_ma_chip_edge_strategy.py`、`tests/test_backtest_mock_qmt_pipeline.py`（实施时逐个确认只测被删栈）；`tests/test_presets_cross_repo_snapshot.py` 与 `tests/fixtures/presets_cross_repo_baseline.json` **先核对**是否含 Cerebro 侧预设基线（presets CI baseline 是 hygiene H 批新增，可能锁 ProfitStrategy 预设——若是，基线随退场改版，属行为变更非放宽 gate）。

---

实施复扫补记：`backtest/tools/file_compare.py:6` 是 `backtest/qmt_utils_adv.py` 的消费者；Grok GO 已明确授权仅将该行改为 `from common.infra.qmt_utils_adv import detect_encoding, check_bom`，在切片 A 同 commit 完成。§1 原「零 import 方」记录据此纠正；删除集合未扩大，未发现新增未规划消费者。

## 2. 现锁（C-R\*）

| # | 规则 |
|---|------|
| **C-R1** | 删除范围 = §1 两分组全集；**纯逻辑清单一行不删**。实施前对每个待删文件跑一次「import 方扫描」，发现计划外消费者即停下报告，不自裁。 |
| **C-R2** | ma_chip 入场逻辑去向：**默认归档**（逻辑在 git 历史 + `docs/backtest/chip/` 文档与 h11 清单中可考；需要跑数时另开 version11 CSV 移植 plan——移植须重裁成交时点语义：ma_chip_edge 为 cheat_on_open 次日开盘买，CSV 引擎现状收盘成交，**不是平移**）。人裁可改为「本轮连做 version11 移植」，但那是扩范围，不是本 plan 默认。 |
| **C-R3** | SSOT 四文件同步（按 engine-positioning-ssot §6）：①`engine-positioning-ssot.md` §2/§5——「Cerebro/Rolling 第一方策略：观察退役」→「已退场（2026-09-16）」，「已有 chip/ma_chip 对照可跑」→「对照产物为静态档案，代码路径已删」；②根 `README.md`；③`AGENTS.md`（入口段已无 Cerebro，补一句「Cerebro 已退场，禁止复活」）；④`docs/backtest/README.md` 入口段。四处一次 commit。 |
| **C-R4** | 静态产物（`backtest_output/`、历史对照报告、`tests/fixtures/csv_engine_pre_er1/`）**不删**——它们是「下一开盘才成交」旧结果的对照档案，与代码路径无关。 |
| **C-R5** | 依赖与围栏清理：`requirements.txt` 去掉 backtrader（全仓 grep 确认零残余 import 后）；`tests/test_research_face_imports.py` 的 chip/ma_chip/verify_cerebro_\* 例外名单改为**零例外**；`tests/conftest.py` 清理相关 fixture。 |
| **C-R6** | 顺序锁：本 plan **先行于** [plan-money-modes-v8-pername](plan-money-modes-v8-pername-2026-09-16.md) 切片 B（退场后 v8 止损真源唯一，消解其 P5）。 |
| **C-R7** | 不做：version11 移植（另开）、改 CSV 成交核、动 1.3、删历史产物、重命名仓库（`MyQuant-backtrader` 名称是历史，不动）。 |

---

## 3. 切片

从**当时 master** 开 `feat/cerebro-retire`。

| 切片 | 做什么 | 完成定义 |
|------|--------|----------|
| **A · 退场删除** | §1 删除清单 + 连带测试 + conftest；每文件先跑 import 方扫描 | `pytest -q tests/` 全绿；`grep -rn 'import backtrader' backtest/ scripts/ strategies/ oskh_factors/ tests/` 零命中 |
| **B · SSOT 同步** | C-R3 四文件一次 commit | 四处口径一致；`docs/backtest/README.md` 入口仅剩 csv_\* 系列 |
| **C · 依赖清理** | requirements 去 backtrader；research 面围栏改零例外 | `D:\anaconda3\envs\vanna312\python.exe -c "import tests.test_research_face_imports"` 绿；pip 装机清单无 backtrader |
| **D · 回写** | 两 plan 状态互相回写（本 plan 已实施 + money-modes P5 消解注记） | review |

## 4. 验证命令

```bash
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
grep -rn 'import backtrader\|from backtrader' backtest/ scripts/ strategies/ oskh_factors/ tests/ common/   # 期望零命中
grep -rn 'ProfitStrategy' backtest/ scripts/ tests/ docs/backtest/README.md README.md AGENTS.md              # 期望仅历史档案/评审记录命中
```

## 5. 风险

- `test_presets_cross_repo_snapshot.py` 若锁了 ProfitStrategy 预设基线：退场即改基线（行为变更，更新断言/基线文件，非放宽）。
- ma_chip 研究线暂失可跑宿主（C-R2 已声明为归档语义；复活走 version11 plan）。
- 1.3 仓不受影响（其 vendor/backtrader 只读不 import，本来已拆）。

## 6. 修订程序

改 C-R\* 须改本文并回写状态。version11 移植另开 dated plan，不塞进本文件。

---

## 7. 实施记录（Codex 随本 PR 回写）

| 切片 | 状态 | commit | 备注 |
|------|------|--------|------|
| A · 退场删除 | ✅ | `59ba18d` | 精确删除 §1 的 16 个模块 + 6 个测试；授权仅改 file_compare 第 6 行；清理无消费者 fixture。presets 快照仅锁 trade_decision/presets.py，保留基线。复扫无新增消费者；pytest 527 passed / 3 skipped；backtrader import 扫描零命中（两处注释仅改措辞）。 |
| B · SSOT 同步 | ✅ | `aee726e` | C-R3 四文件同步：2026-09-16 已退场；chip/ma_chip 静态归档；仅 csv_* 回测入口，禁止复活。 |
| C · 依赖清理 | ✅ | `7ee79ec` | requirements 移除 backtrader；研究面 AST 全目录零例外，入口传递导入检查扩至 12 模块；65 passed；四项 data-free gate 全绿。conftest 已在 A 清理。 |
| D · 回写 | ✅ | 本行所在提交：`docs(cerebro-retire): 切片D 回写 plan 与 money-modes P5` | 本 plan 已实施（PR #58，未合并）；money-modes P5 已消解、仍待前置合入。最终验证见下；未执行 #59。 |


### 最终复核

- A/B/C/D 各一提交并推送 `origin feat/cerebro-retire`；D 的 SHA 由本行所在提交确定（避免提交自引用），完整四个 SHA 另写 `/tmp/codex-pr58-notes.md`。
- 最终 `/workspace/vanna312/bin/python -m pytest -q tests/`：**568 passed, 3 skipped, 1 warning**（15.26s；现有 TR window=80 警告）。
- 按 §4 指定范围扫描 backtrader 导入和 `ProfitStrategy`：均零命中；全仓 Python backtrader 导入扫描亦零命中。
- 四项 data-free gates 全绿；`git diff --check` 通过；修改文本 UTF-8 无 BOM、NUL=0。
- 缺陷优先复核：删除集合精确为 §1 的 16 模块 + 6 测试；file_compare 仅一行改动；presets 快照和 fixtures、backtest_output、chip 纯逻辑、Rust TR、CSV 引擎及规则均未修改。研究面静态检查覆盖全部 Python 文件，零例外。
- 阻塞：无新增阻塞；先前 file_compare 阻塞已按本轮授权解除。ma_chip 仅归档；未实现 version11 / money-modes B，未改成交核、1.3 或仓名。PR #58 未合并。
