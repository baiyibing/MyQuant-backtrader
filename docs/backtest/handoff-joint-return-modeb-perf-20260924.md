# 交接：联合收益 Mode B 性能刀（2026-09-24）——**弧已收官**

> **状态（终版）**：性能弧**收官**。#181–#192 全合入，master tip **`95431fc`**；收尾 tip 重剖 **PASS**（wall **237.6s**，vs 弧起点 ~789s **−69.9%**，vs #187 384.5s −38.2%），fills/NAV/orders 全链 byte-identical（合约 SHA 不变）。tip 全量 pytest **2085 绿**。核改账：#189/#192 = kimi GO + codex GO 双核（B 路线代核，Grok 停摆期豁免，额度恢复后可选补核）。**剩余热点全部 <32s，不再开新刀**；回研究主线。  
> **主管仓**：`baiyibing/MyQuant-backtrader` · Owner **bt**。Runner：**4090bot**（= 4090 物理机）。实现默认 **Codex gpt-6-astra**（Bot VM headless）；核改 **Grok CLI 4.7**；**人裁合**。4090 机本地：主力 zcode + kimi，codex 替补/三方评审，cursor:auto 备用，一律 headless（2026-09-24 人裁定档）。  
> **沟通格式**：【仓】【刀】【状态】【路径】【你需要做的】；术语见 [research-ops-glossary.md](../operations/research-ops-glossary.md)；RACI 见 [grok-bot-raci-workflow-ssot.md](../operations/grok-bot-raci-workflow-ssot.md)。

生产 fill / fee / clock **边界** / Decimal **成交值** / seal 默认 / validate 默认 **不动**，除非人另开 GO。

---

## 1. 终态（2026-09-24 弧收官）

| 项 | 值 |
|----|----|
| master tip | **`95431fc`**（#188→#190→#189→#192→#191 squash 序） |
| 收尾量效 | **tip 4090 B-only PASS：wall 237.604 / total 236.093**（机器空闲实测；vs #187 −38.2%，vs 弧起点 −69.9%） |
| replay LAG/REF | 71.44 / 53.19（#187 时 182.8 / 109.6）；attempts LAG ~5.7（#187 时 49.2）；marks 15.8/10.7 |
| fills/NAV 合约 SHA（全链不变） | fills `d6d40bc4979d462582a8c53c34591cdcca6fafd123857da9d7053aa598fe3376` · daily_nav `2cf88d08b7f50c6c54cdcb8ba64a4fb96024262f988c18d8b025259d1c572685`（orders `aad1596b…185c6d` 同） |
| tip pytest | **2085 passed / 0 failed**（含 #190 LF golden 修复） |
| 核改账 | #189/#192：**kimi GO + codex GO 双核**（4090 机 `KIMI_REVIEW_189/192.md` · `CODEX_REVIEW_189/192.md`）；Grok 停摆期人裁豁免 |
| 收尾 RECEIPT（4090 机） | `RECEIPT_REPLAY_ARC_CLOSE_95431fc.md`（含第一次撞负载跑的诚实记录）· out `out-v2-pack-spans-arc-close2-95431fc` |
| 剩余 top（均 <32s，不开刀） | write_artifacts 31.8 · bundle_load 31.6 · REF lifecycle 28.4 · plain_output 27.0 · LAG lifecycle 25.7 |

**不要做**：翻 seal（保持 **qlib_bin**）；翻 validate 默认（保持 **v1**）；复活 industry-align P1/P2/P4（#135 已关）；覆盖任何历史 outs。

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
| `4a9066a` | #189 | marks **持仓热集**（live-orders 退出 eager，回填走 site 反扫） | ~254.1（验收跑） | marks 80.6/73.1→15.8/9.4；热集均值 428/400→81/47.5；kimi+codex 双核 |
| `91bb6d0` | #192 | fill **append-only 浅拷**（去 63,903 次整树 deepcopy） | — | attempts LAG 43.4→5.75（−86.8%）；kimi+codex 双核 + 复核硬化 |
| **`95431fc`** | **+#190/#191** | **弧收官 tip** | **237.6** | **−69.9% vs 弧起点**；三表 byte-identical；RECEIPT_REPLAY_ARC_CLOSE_95431fc |

归因账（4090 机，cProfile 仅归因不混算）：post-#185（H-stamp→#186、H-cap→#187）；be3ce4f marks 归因（`RECEIPT_REPLAY_MARKS_ATTRIB_CPROFILE_be3ce4f.md`：get 30% / decimal 46% / 本体 17%，宇宙 428 由活单主导→#189）；deepcopy 184.7s cum / 63,903 次→#192。

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

## 4. 后续（弧已关；无待开刀）

| 项 | 状态 |
|--------|------|
| 性能刀 | **收官，不开新刀**（剩余 top 全部 <32s：write_artifacts 31.8 / bundle_load 31.6 / REF lifecycle 28.4 / plain_output 27.0） |
| 可选补核 | Grok 额度恢复后对 #189/#192 补 `GROK_REVIEW`（B 路线已人裁豁免，纯加分项） |
| 主线回归 | joint-return-v1 的 Mode B 时钟 pack 重出与 `NOT_READY_FOR_MODE_B` 解除（见研究问题地图 §5.6）——性能前置已扫清 |
| 不做（锁死） | eligible_scan 再砍、seal/validate 默认翻转、改成交值、marks 每样本再便宜化、输出序列化重写（字节一致门风险高） |

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

## 7. 接手清单（终版；本弧无待办）

1. ~~#187 RECEIPT~~ 已落地复核。
2. ~~人裁下一刀~~ marks GO → **#189**（已合 `4a9066a`）。
3. ~~Grok 核 → 人合 → tip 收尾~~ 全链完成：#189/#192 kimi+codex 双核 GO，四 PR squash 合入，tip `95431fc` 收尾跑 PASS（**wall 237.6s**，`RECEIPT_REPLAY_ARC_CLOSE_95431fc.md`）。
4. 剩余：可选 Grok 补核；研究主线（Mode B 时钟 pack 重出）另起交接，不在本文。

## 8. 本交接文档维护

- 路径：`docs/backtest/handoff-joint-return-modeb-perf-20260924.md`
- 起草：bt · 2026-09-24（额度停工交接）
- 更新：2026-09-24 晚 · 接手 agent（zcode，4090 机）——#188 合入、marks GO→#189、#190 开出后的状态行刷新；**终版**：弧收官（#190/#189/#192/#191 合入 + tip 收尾 PASS + 弧表回填）。本文自此归档，后续性能问题另开新文档。

EXIT:0
