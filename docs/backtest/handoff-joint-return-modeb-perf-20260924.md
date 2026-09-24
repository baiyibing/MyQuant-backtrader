# 交接：联合收益 Mode B 性能刀（2026-09-24）

> **状态**（2026-09-24 晚更新）：perf 刀 **#181–#187 已合入 master**，**#188（本交接文档）已合**（tip `be3ce4f`）。**marks 热集刀已开 = PR #189**（`perf/joint-return-marks-hotset`，CI PASS，4090 本地 plain 验收 **PASS**：wall 384.5→**254.1s / −33.9%**，fills/NAV/orders byte-identical，pytest 2083 绿）——**等 Grok 核（Bot 额度 ~2 天）→ 人裁合 → 合并 tip 4090 B-only 收尾**。**PR #190**（partial_sell LF golden 测试修复，CI PASS）待人合。Grok Bot 额度恢复前**不开新刀**。  
> **主管仓**：`baiyibing/MyQuant-backtrader` · Owner **bt**。Runner：**4090bot**。实现默认 **Codex gpt-6-astra**（Bot VM headless）；核改 **Grok CLI 4.7**；**人裁合**。4090 物理机本机实现可走 zcode / kimi / codex / cursor:auto（2026-09-24 人裁放行）。  
> **沟通格式**：【仓】【刀】【状态】【路径】【你需要做的】；术语见 [research-ops-glossary.md](../operations/research-ops-glossary.md)；RACI 见 [grok-bot-raci-workflow-ssot.md](../operations/grok-bot-raci-workflow-ssot.md)。

生产 fill / fee / clock **边界** / Decimal **成交值** / seal 默认 / validate 默认 **不动**，除非人另开 GO。

---

## 1. 现在停在哪（2026-09-24 晚）

| 项 | 值 |
|----|----|
| master tip | **`be3ce4f`** — `#188`（本交接文档）；其业务树 = `e827529`（`#187`） |
| 在飞 PR | **#189** marks 热集收缩（CI PASS · 本地验收 PASS，见下）· **#190** partial_sell LF golden 测试修复（CI PASS） |
| 最近量效 | **#189 本地 plain B-only PASS**（未合）：wall **384.541→254.113（−33.9%）**；marks 80.64/73.09→**15.85/9.44**；热集均值 427.8/400.3→**81.0/47.5**；回填 ~3,980 次 / 1,549 步（近零） |
| SPEC / 归因 / RECEIPT（4090 机） | `…\joint-return-v1-replay-panel-phase\`：`SPEC_REPLAY_MARKS_HOTSET_20260924.md` · `RECEIPT_REPLAY_MARKS_ATTRIB_CPROFILE_be3ce4f.md` · `RECEIPT_REPLAY_MARKS_HOTSET.md` |
| 期望 out | `out-v2-pack-spans-marks-hotset` · phase `phase_timings_B_marks_hotset.json`（归因：`out-v2-pack-spans-be3ce4f-marks-cprofile` 等） |
| 对照基线 | **#187** `e827529`：wall 384.541；marks 80.64/73.09；attempts LAG 49.17；lifecycle 26.05/24.44（#187 之前的 #186 基线见 §3.1） |
| fills/NAV 合约 SHA（#185 起未变，各刀必须 byte-identical） | fills `d6d40bc4979d462582a8c53c34591cdcca6fafd123857da9d7053aa598fe3376` · daily_nav `2cf88d08b7f50c6c54cdcb8ba64a4fb96024262f988c18d8b025259d1c572685` |
| 本地验收 | #189：**PASS**（三表 byte-identical；forbidden 201 条 0 变动；pin 恢复；pytest 2083 绿） |

**不要做**：自动开下一刀；翻 seal（保持 **qlib_bin**）；翻 validate 默认（保持 **v1**，v2 仅 research opt-in）；复活 industry-align P1/P2/P4（#135 已关）；覆盖 #181–#187 及 marks 归因/验收 outs。

---

## 2. Mode B 性能弧（已合）

输入身份（全程同一条）：CLOCK_PATCH-614 · cash=**1e9** · validate **v2**（显式）· P-BASE · fill-mode all · sealed **qlib_bin** FULL pack。

| tip | PR | 刀 | wall≈ | 备注 |
|-----|-----|-----|------:|------|
| `8cd01e7` | #182 | eligible_scan 加速 | ~789 | eligible_scan ~286→~11s |
| `710687e` | #183 | marks 固定宇宙 | ~772 | 几乎 noop（U≈panel 614） |
| `0df7697` | #184 | marks live-universe | ~687 | mean live U ~428/400 |
| `4e8fddb` | #185 | cheap trusted `_bar_decimal` | **~633** | marks ~79/73 |
| `0d4e72d` | #186 | lifecycle immutable clock cache | **~449** | lifecycle ~118→~26（−78%）；wall −29% vs #185 |
| `e827529` | #187 | eligible-instrument **capacity 稀疏读** | **~384.5** | attempts LAG 81.8→49.2（−39.9%）、REF 33.1→0.07；见 §3.1 |

在飞（未合）：**#189** marks 热集收缩（live-orders 退出 eager，`perf/joint-return-marks-hotset`）——本地 4090 plain **254.1s（−33.9% vs #187）**；合并后以 tip 复跑收尾并计入本表。

cProfile（#185 tip，归因用，**不可**与 plain wall 混算）：H-stamp ACCEPT → 先做 #186；H-cap PARTIAL → #187 收益可能远小于 attempts 全段 ~82s，近噪声则停。

---

## 3. #187 刀摘要（已合，待量效）

- **PR**：https://github.com/baiyibing/MyQuant-backtrader/pull/187  
- **改动**：`backtest/research/joint_return_replay.py` + `tests/test_joint_return_replay.py`  
- **语义**：SELL-first / intent_id 序、同分钟共享余额、M-LAG 扣 / M-REF 不扣 **不变**；不动 `attempt()` / marks / lifecycle / eligible 选择 / fees / seal / validate 默认。  
- **本地验收**：506 passed；相对 tip `0d4e72d` fills+daily_nav **字节一致**（含 timings on/off）。  
- **Grok**：GO（`GROK_REVIEW_187.md`）。CI：SUCCESS run `35973787167`。

### 3.1 4090 重剖结果（2026-09-24）

| 字段 | 值 |
|------|-----|
| PASS/FAIL | **PASS** |
| tip 核验 | `e827529966ed4f465322524503e79ef828f9b6dd` |
| wall / total | **384.541 / 382.807**（vs #186 448.571/446.792：**−64.03s / −14.3%**） |
| attempts LAG/REF Δ vs #186 | LAG **81.805→49.175**（−32.63s / −39.9%）；REF **33.079→0.073**（−33.01s / −99.8%） |
| fills/NAV byte-identical? | **是**（fills `d6d40bc4…` / daily_nav `2cf88d08…`）；orders.csv identical；summary 仅 run metadata 差 |
| 其余 spans | marks 80.638/73.089；lifecycle 26.052/24.442；eligible_scan 11.408/11.043 |
| 剩余 top | **marks** ~80/73 · attempts LAG ~49 · lifecycle ~26/24 |
| RECEIPT | `D:\PycharmProjects\MyQuant-backtrader\backtest_output\joint-return-v1-replay-panel-phase\RECEIPT_REPLAY_CAPACITY_SPARSE.md` |
| phase / out | `phase_timings_B_capacity_sparse.json` · `out-v2-pack-spans-capacity-sparse\...` |
| 注 | H-cap PARTIAL：真实加速非噪声；LAG attempts 仍剩 ~49s，勿当整段 ~82s 吃光。pin 已恢复；forbidden 未动。 |

---

## 4. 下一刀候选（人裁后再开；无 GO 不开）

证据：`/workspace/handoffs/joint_return_post185_hotspot_eval_20260924/EVAL.md`（Bot VM）+ 4090 机 `RECEIPT_REPLAY_MARKS_HOTSET.md`（#189 后剩余 top）。marks 残差刀已开（#189 在飞，见 §1）。

| 优先级 | 刀 | 风险 | 说明 |
|--------|-----|------|------|
| 人裁 | attempts LAG 再砍 / write_artifacts / **暂停** | — | #189 后 top：attempts LAG ~43s（deepcopy 主导，profiled cum 184.7s）· write_artifacts ~32s · plain_output ~27s · lifecycle ~27/25s |
| defer | lifecycle due-expiry 调度 | MED/HIGH | 复杂度高 |
| 不做 | eligible_scan 再砍、seal/validate 默认翻转、改成交值、marks 每样本再便宜化（热集收缩后 ROI 低） | — | 锁死 |

---

## 5. Bot VM 交接路径（不入库大日志）

根：`/workspace/handoffs/`

| 主题 | 目录 |
|------|------|
| #187 capacity | `joint_return_capacity_sparse_20260924/`（SPEC / CODEX_RESULT / GROK_REVIEW_187 / BRIEF_4090） |
| #186 lifecycle | `joint_return_lifecycle_clock_cache_20260924/` |
| #185 cheap-bar | `joint_return_cheap_bar_decimal_20260924/` |
| #184 live-universe | `joint_return_marks_live_universe_20260924/` |
| post-#185 评估 + capacity draft | `joint_return_post185_hotspot_eval_20260924/` |
| worktree（#187） | `/workspace/wt-capacity-sparse` · 分支已合，可弃 |

解释器：`/workspace/vanna312/bin/python`（`OSKH_MERGE_PYTHON` 同）。

---

## 6. 硬锁（接手必须遵守）

1. Seal / 默认热路径：**qlib_bin marks-v1 → DensePanel**；无生产 dual-write；不以 Arrow/Parquet 默认替换。  
2. validate：**默认 v1**；v2 仅 research opt-in。  
3. fills/NAV 与上表 SHA **byte-identical** 才算 perf PASS。  
4. 不混用 cProfile wall 与 plain Mode B 计时。  
5. industry-align P1/P2/P4 按 #135 **关闭**。  
6. 跨仓：MQ→BT→1.3 只指针；RACI SSOT 仅本仓 `docs/operations/grok-bot-raci-workflow-ssot.md`。  
7. 物理机 CLI：**headless 默认**；交互 TUI 仅人显式调试。

---

## 7. 接手清单（最小动作，2026-09-24 晚刷新）

1. ~~#187 RECEIPT~~ 已落地并复核（§3.1）。  
2. ~~人裁下一刀~~ 已裁 **GO marks** → 已实现为 **PR #189**（含归因 SPEC/RECEIPT，见 §1）。  
3. 进行中：**Grok 核 #189**（Bot 额度恢复后；PR body 已附核要点清单）→ **人裁合 #190 / #189** → 合并 tip 复跑 4090 B-only 写收尾 RECEIPT。  
4. Grok Bot 额度约 **2 天后**恢复；额度外实现走 4090 物理机本机（zcode / kimi / codex / cursor:auto，2026-09-24 人裁放行；本机 codex 需 login，kimi 即用）。  
5. 下一刀（§4）**无 GO 不开**。

---

## 8. 本交接文档维护

- 路径：`docs/backtest/handoff-joint-return-modeb-perf-20260924.md`  
- 起草：bt · 2026-09-24（额度停工交接）  
- 更新：2026-09-24 晚 · 接手 agent（zcode，4090 机）——#188 合入、marks GO→#189（本地验收 PASS）、#190 开出后的状态行刷新；#189 合并 + tip 收尾后再次更新 §1/§2。  
- 更新规则：RECEIPT 落地后改 §1 状态行；下一刀 GO 后另开 SPEC，不在本文堆实现细节。

EXIT:0
