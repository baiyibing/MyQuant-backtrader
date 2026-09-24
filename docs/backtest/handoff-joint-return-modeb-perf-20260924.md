# 交接：联合收益 Mode B 性能刀（2026-09-24）

> **状态**：perf 刀 **#181–#187 已合入 master**；**#187 4090 B-only PASS**（tip `e827529`，wall ≈384.5s，−14.3% vs #186）。Grok Bot（bt）额度将尽，**本轮停工**；接手 agent 裁下一刀（marks 残差 / 暂停）或等额度恢复。  
> **主管仓**：`baiyibing/MyQuant-backtrader` · Owner **bt**。Runner：**4090bot**。实现默认 **Codex gpt-6-astra**（Bot VM headless）；核改 **Grok CLI 4.7**；**人裁合**。一般不用 Cursor Cloud Agent。  
> **沟通格式**：【仓】【刀】【状态】【路径】【你需要做的】；术语见 [research-ops-glossary.md](../operations/research-ops-glossary.md)；RACI 见 [grok-bot-raci-workflow-ssot.md](../operations/grok-bot-raci-workflow-ssot.md)。

生产 fill / fee / clock **边界** / Decimal **成交值** / seal 默认 / validate 默认 **不动**，除非人另开 GO。

---

## 1. 现在停在哪

| 项 | 值 |
|----|----|
| master tip（截至交接起草） | **`e827529`** — `#187` capacity sparse |
| 最近量效 | **#187 4090 PASS**（见 §3.1） |
| BRIEF | Bot VM `/workspace/handoffs/joint_return_capacity_sparse_20260924/BRIEF_4090_REBENCH.md` |
| 期望 RECEIPT（4090） | `D:\PycharmProjects\MyQuant-backtrader\backtest_output\joint-return-v1-replay-panel-phase\RECEIPT_REPLAY_CAPACITY_SPARSE.md` |
| 期望 out | `out-v2-pack-spans-capacity-sparse` · phase `phase_timings_B_capacity_sparse.json` |
| 对照基线 | **#186** tip `0d4e72d`：wall ≈**448.57s** / total ≈446.79s；attempts LAG ≈**81.80s**；lifecycle ≈25.55/24.65；marks ≈80.30/74.36 |
| fills/NAV 合约 SHA（#185 起未变，#186/#187 必须 byte-identical） | fills `d6d40bc4979d462582a8c53c34591cdcca6fafd123857da9d7053aa598fe3376` · daily_nav `2cf88d08b7f50c6c54cdcb8ba64a4fb96024262f988c18d8b025259d1c572685` |
| 4090 结果 | **PASS** — 见 §3.1 |

**不要做**：自动开下一刀；翻 seal（保持 **qlib_bin**）；翻 validate 默认（保持 **v1**，v2 仅 research opt-in）；复活 industry-align P1/P2/P4（#135 已关）；覆盖 #181–#186 outs。

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
| `e827529` | #187 | eligible-instrument **capacity 稀疏读** | **PENDING 4090** | 机制：空 eligible 不建 map；只读 unique eligible；缺 bar→`Decimal(0)` |

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

证据：`/workspace/handoffs/joint_return_post185_hotspot_eval_20260924/EVAL.md`（排名曾先 capacity，后 lifecycle；lifecycle 已做）。

| 优先级 | 刀 | 风险 | 说明 |
|--------|-----|------|------|
| 人裁 | marks 残差 **或暂停** | — | #187 已证实非噪声（−14% wall）；下一最大块是 **marks ~74–80s**；attempts LAG 仍 ~49s |
| 若 attempts 仍大且 capacity 已瘦 | marks 少分配 / 批量索引专路 | LOW/MED | EVAL 刀 4；推测仅 5–25s；需新 profile |
| defer | lifecycle due-expiry 调度 | MED/HIGH | lifecycle 已 ~25s；复杂度高 |
| defer | deepcopy / snapshot 流 | MED | ROI 弱 |
| 不做 | eligible_scan 再砍、seal/validate 默认翻转、改成交值 | — | 锁死 |

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

## 7. 接手清单（最小动作）

1. §3.1 已填（#187 PASS）。若需原件向 4090bot 取 RECEIPT 路径。  
2. 人裁：暂停 / marks 残差 / 再砍 attempts（用状态行 + widget）。**无 GO 不开刀。**  
3. 实现路径：Owner（bt 或临时代班）排 Codex → Grok 核 → **人合** → 4090 B-only。  
4. Grok Bot 额度约 **2 天后**恢复；额度外优先 4090bot / 他机 Codex，避免烧 Bot 配额做实现。

---

## 8. 本交接文档维护

- 路径：`docs/backtest/handoff-joint-return-modeb-perf-20260924.md`  
- 起草：bt · 2026-09-24（额度停工交接）  
- 更新规则：#187 RECEIPT 落地后改 §1/§3.1 状态行；下一刀 GO 后另开 SPEC，不在本文堆实现细节。

EXIT:0
