# 交接：joint-return-v1 时钟 pack 全量重生成 · NOT_READY_FOR_MODE_B 解除（2026-09-24）

> **状态（2026-09-25 终版）**：**B–G 收官，`NOT_READY_FOR_MODE_B` 解除**。全量重生成 pack（合同 `c6b85b9b…`，code_shas MQ `b072cc3`/BT `2f79375`）→ 收窄 614/1891 → P-BASE M-LAG **3631 fills / net +59.1%** → Mode B 真湖 **M-REF 21 / M-LAG 3631** 全 `BT_RESEARCH_REPLAY_PASS`。实测账与过程回执：4090 机 `…\narrow_clock_full_20260924\RECEIPT_CLOCK_REGEN_FULL.md`。跨重生成 tie-break 方差见 §7。上游交接：[handoff-joint-return-qlib-to-bt-2026-09-22.md](handoff-joint-return-qlib-to-bt-2026-09-22.md)。
> **主管**：bt（本仓）。qlib 出合同与时钟（MQ #97 已合 `1c1fe43`；MQ tip `b072cc3` 为其祖先，`contract_hash()` 复算仍 = `c6b85b9b…`）。4090bot = 本机 runner（newtest_4090）。
> **前置已扫清**：Mode B 回放性能弧收官（wall 237.6s，[handoff-joint-return-modeb-perf-20260924.md](handoff-joint-return-modeb-perf-20260924.md)）。

生产 fill / fee / clock 边界 / Decimal 成交值 / seal=qlib_bin / validate=v1 默认不动。禁止造 bar、禁止 PortAna 倒推、禁止覆盖任何历史 outs。

## 1. 为什么还差一刀

9/23 研究线（host 时钟 patch：直接改旧 `rules/plans.json` 的 available/effective/expires，再 freeze→portfolio）已经拿到全绿数字：

- P-BASE M-LAG **4475 fills**（turnover 1.3485 / maxDD 0.3132 / net +0.5928）
- Mode B（lake marks 1891/1891）cash 1e8：M-REF 34 / M-LAG 4475；cash 1e9：M-REF 376 / M-LAG 63527

但全部回执盖 **`RESEARCH_CLOCK_PATCH_NOT_FULL_REGEN`** 章——plans 是手改的，intents / manifest / hash 链不是 MQ #97 管线全量重出的合同级产物。解除 `NOT_READY_FOR_MODE_B` 必须走 MyQuant 派工单 [intent-clock-4090-reexport.md](../../../MyQuant/docs/reviews/joint-return-v1/intent-clock-4090-reexport.md) §1：sessions、metadata、plans、freeze、portfolio、intents 与所有对应 manifest/hash **重新生成**，旧 frozen packs 不可复用。

## 2. 执行序（固定，不并行）

| # | 动作 | 谁 | 门槛 / 停点 |
|---|------|----|------------|
| A | BT 锁重指（本 PR）：`FROZEN_CONTRACT_HASH` → `c6b85b9b…`，仅常量一行 + 文档 | bt | 人裁合；**合并 tip SHA 登记**为 pack `code_shas.BT` |
| B | MQ §2 时钟准备：`next_session_clocks` 重写 sessions + metadata，输出**新建**目录 `narrow_clock_full_20260924`（已存在即停） | 4090 | 无 15:03→当日 16:00 窗口；每个末日信号有下一 session；日期集合不变 |
| C | MQ §3：`rule_intents → freeze_snapshot → portfolio`（run_id `joint-return-control-only-50-5-narrow-clock`）→ 全量 pack 2470 → 按 NARROW.md 剔 9 no_file + 150 over_window 收窄（614 / 1891，constraints 10810 对账） | 4090 | PORTFOLIO_CONSTRAINTS_PASS；intent/contract hash 全新登记 |
| D | bars 覆盖核验：新执行/估值窗与 clock_patch 窗一致则复用 `frozen_explicit_bars_clock_patch_pin*.json`（先核再复用；缺口只从真湖 `my_data_1min` 导出，不造 bar） | bt | missing=0 |
| E | P-BASE M-LAG 回放（新 out 目录，不覆盖 `…-narrow*`）；**无本地 pin**（常量已官方） | 4090 | 非零 `orders_with_fills`；与 RECEIPT_614 对账（时钟语义一致应同量级） |
| F | Mode B M-REF/M-LAG（`--fill-mode all`，marks 沿用 lake_bar 证据链；cash 1e8 先行，1e9 视需要） | 4090 | 与 9/23 Mode B 回执对账 |
| G | 收尾：本表回填 + [research-backtest-entry.md](research-backtest-entry.md) §5.1/§5.6 + AGENTS.md 状态行解除 `NOT_READY_FOR_MODE_B` + RECEIPT | bt | E/F 全绿才解除 |

E 步若仍 0 成交 → 停，回 qlib 查时钟，不交 Mode B（上游交接 §6 第 4 条不变）。

## 3. 输入（2026-09-24 已核验，不猜路径）

| 输入 | 路径（MyQuant 运行根 = `D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95`） | 凭据 |
|------|------|------|
| scores | `inputs\scores_carryforward.json` | **成功线自登记**：`rules\rule-manifest.json` 与最终 `snapshot.json` 的 `inputs.scores.uri` 均 = carryforward（content_sha256 `11903c5b…`）。`merged\scores.json`（`37e87390…`）是 scores-merge 步产物；pipeline 日志中对它的引用均为被取代的失败尝试。carryforward 满足 `rule_intents` held∈ranked（SOURCE_scores_carryforward.md），换成 merged 会使计划漂移、4475-fills 对账基线作废 |
| initial_state | `inputs\initial_state.json` | `{"cash":1e8,…}` 实文件 |
| sessions | `inputs\sessions.json` | SOURCE_sessions.md：research-explicit v2 |
| metadata 模板 | `inputs\metadata.json` | — |
| execution-calendar | `handoff_bt_20260922\narrow_clock_20260922\execution-calendar.json` | 2025-01-02 → **2026-01-05**（含末日下一 session） |
| MQ SHA | `b072cc3`（#97 `1c1fe43` 祖先已验） | §2 脚本内 `git rev-parse HEAD` 自记 |
| BT SHA | 本 PR 合并 tip（合后登记） | replay 仅登记不比对本地 HEAD（`joint_return_replay.py:389-394`） |

收窄证据：`handoff_bt_20260922\NARROW.md` + `clipped_window_coverage_150.csv`（150 名单）；9 名 no_file 见 NARROW.md §Universe。

## 4. 9/23 研究线回执（对照基线，只读不覆盖）

`…\handoff_bt_20260922\narrow_clock_20260922\` 下：`REEXPORT.md` · `RECEIPT_614.md` · `RECEIPT_MODE_B.md` · `RECEIPT_MODE_B_CASH_1E9.md`（均 `RESEARCH_CLOCK_PATCH_NOT_FULL_REGEN`）。BT 侧 outs：`backtest_output/joint-return-v1/…narrow-clock-patch-614`、`joint-return-v1-modeb/…`、`joint-return-v1-modeb-cash-1e9/…`。

## 5. 硬锁

1. 本 PR 只动常量一行 + 文档；fill kernel / fee / 时钟语义零改动。
2. 全量重生成前旧 frozen packs 不可复用（hash 链不接；`9ee8cc3c…` 旧锁随本 PR 退役，只留历史解释）。
3. 性能弧的 byte-identical 合约 SHA 属 CLOCK_PATCH-614 研究身份，**不约束**本专题新 pack 首跑；新 pack 首跑后另立自己的对账基线。
4. 不混用 cProfile wall 与 plain 计时；物理机 CLI headless。

## 6. 勘误（2026-09-24 20:15）

初版 §3 scores 行误写 `merged\scores.json`（引 merge 步 manifest），已按成功线自登记改为 `inputs\scores_carryforward.json`。该误写曾触发一次双执行器撞车（B 半成品被误判 scores 错误而隔离重跑），根因即本行。执行纪律补充：**B–C 全程本机（4090）只允许一个执行器**；重跑前先核 `wmic process` 与目录时间戳，避免第二执行器写入同一 `$Out`。

## 6b. 收官补遗（2026-09-25）

- 执行实录：B ~3min；C1 rule 6h21m；C2 freeze ~4min（两次秒级失败已修：freeze 用富字段 metadata + plans uri 逐字重登记）；C3 portfolio 5h58m（D 盘 ENOSOC 作废一轮后重跑）；收窄/回放见 §2 各步。
- **同分钟 tie-break 方差（新发现）**：两包 intents 语义与序列逐位全等（仅 hash 血统不同）时，成交仍可漂移（3631 vs 4475）——根因是同分钟共享余额按 **intent_id 序** 瓜分（#187 语义契约），跨重生成 hash 不同 → day-1 部分成交拆分不同 → 持仓链蝴蝶效应。非引擎回归（旧包×新引擎复放 = 4475 整）。策略经济性对此稳健（net 59.1% vs 59.3%）。**建议**：MQ/BT 后续讨论把同分钟并列 tie-break 语义化（如 (instrument, qty) 序或轮转），否则跨包对账永远吃这个方差。
- marks 跨包复用要点：`reference_marks` 按 intent_id 挂证，重映射需等长替换 1891 键 + 按引擎约定（`joint_return_replay.py:653`，`content_hash(bundle 去字段)`）重算 bars seal；bars `content_sha256` 是强校验，不能只改键不算 seal。
- **bars 格式约定（2026-09-26 人裁，随本交接生效）**：此后 MQ 导出合同包的 bars **默认走 sealed qlib_bin pack**（`write_pack` + byte-seal），JSON 仅存档不用于回放热路径。已验证：合同级 614 pack 的 bin 版复放三表（fills/orders/daily_nav）与 JSON 版**逐字节一致**，全链 118s vs JSON 版 ~26min（13×）。回执 `backtest_output/joint-return-v1-contract-bin/RECEIPT_CONTRACT_BIN_SWITCH.md`；转换器 `MyQuant/runs/…/_convert_contract_bin_20260926.py`。MQ 侧导出待接（当前仍出 JSON，本仓先手动转）。

## 7. 维护

- 起草：bt（zcode，4090 机）· 2026-09-24 · 随 A–G 回填；G 完成后归档并改写状态行。
