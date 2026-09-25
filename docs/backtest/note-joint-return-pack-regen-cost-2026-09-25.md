# 笔记：joint-return 时钟 pack 全量重生成的成本 / 时间 / 并行性分析（2026-09-25）

> **勘误（2026-09-25 晚，实测落地后）**：①portfolio 实测 **5h58m**（08:36:58→14:35:17），B→C 有效工时 **~12h20m**，原"11–14h 上界"系投影表述，现以实测为准；②"审计逐意图/逐日验哈希，彼此独立、可分块并行"的推断**不成立**——外部实测（合成数据）多进程仅 ~1.56x，且全量 A/B 证实真正大头是 JSON 重复序列化（该结论已由 MQ #102 缓存默认翻转兑现，实测 **~165x**，原 §5 触发条件事实上提前达成）；③补一条实测发现：**同分钟并列意图按 intent_id 序瓜分共享余额**（#187 语义契约），跨重生成 hash 血统不同 → 成交路径可漂移（3631 vs 4475，见专题 RECEIPT_CLOCK_REGEN_FULL），跨包对账需注意此方差。

> **性质**：观察与分析记录，**不开刀**。数据来自 4090 机（newtest_4090）时钟 pack 全量重生成专题实测。
> **上游**：[handoff-joint-return-clock-regen-2026-09-24.md](handoff-joint-return-clock-regen-2026-09-24.md)（B–G 执行序）· [handoff-joint-return-modeb-perf-20260924.md](handoff-joint-return-modeb-perf-20260924.md)（回放性能弧，已收官）。
> **写作时点**：2026-09-25 07:29，C 段 portfolio 仍在运行（见 §6 快照）。

---

## 1. 结论先行

1. **pack 全量重生成（B→C）实测 11–14 小时量级**（历史参照同量级），其中 rule_intents 6h21m（实测完成）+ portfolio ≤7.2h（历史审计上界，本次写作时仍在跑）。两段都是**单核纯 Python**。
2. **回放性能弧（789→237.6s，−69.9%）与本次耗时无关但依然有效**：弧优化的是本仓回放引擎（每份 pack 要跑几十次），pack 生成是 MQ 侧一次合同变更付一次的一次性成本。今晚的时间全花在后者上，属预期，不是优化失效。
3. **可并行性分两半**：状态链折叠（逐日 `state[d+1]=f(state[d])`）不可朴素并行；哈希/验证（疑似 CPU 大头）可分块并行且可保确定性。但当前 ROI 为负，建议不开刀，以"重生成频率"为触发条件（§5）。

## 2. 实测时间账（B→C，carryforward 权威线）

| 段 | 耗时 | 状态 | 说明 |
|----|------|------|------|
| B 时钟准备（next_session_clocks） | ~3 min | 完成 | 门禁全绿（243×09:30/15:00，0×同日 15:03，尾 session 2026-01-05） |
| C1 rule_intents | **6h21m** | 完成（02:34） | 慢速参考路径（默认，与历史成功线同配置；`--cache-plan-hash` 故意未用），产出 plans.json 657MB + rule-manifest 662MB |
| C2 freeze_snapshot | ~2 min | 完成（02:40） | 数据热缓存；两次秒级失败已修（富字段 freeze metadata + plans uri 重登记，见 §7 教训） |
| C3 portfolio（约束审计） | **≥4h46m，跑至写作时** | 运行中 | 历史上界 7.2h（9/21–22 原版审计） |
| **B→C 合计** | **11–14h 上界** | | 2026-09-24 20:13 发车 |

**机器事实**：i9-13900KF，24 核（8P+16E）/ 32 线程；全程 CPU 秒数 ≈ 墙钟秒数——**13 小时只占用 1 个核，其余 23 核闲置**。

**历史参照**：原版 rule 段窗口 9/20 21:29 → 9/21 09:17（~11.75h，含重试）；原版 portfolio 审计 7.2h。本次为"正常发挥"，无异常退化。

**额外墙钟**：撞车事件（双执行器，已拆弹，#196 勘误）浪费约 30–40 分钟，不计入上表。

## 3. 与回放性能弧的关系（为什么"优化了还是很慢"）

| 维度 | 回放引擎（性能弧标的） | pack 生成（本次大头） |
|------|----------------------|----------------------|
| 代码归属 | 本仓 `joint_return_replay.py` | MQ 仓 `joint_return_rule_intents` / `joint_return_portfolio` |
| 执行频率 | **每份 pack 几十次**（D/E/F、换 fill-mode/cash、敏感性对照） | **每次合同/时钟变更 1 次** |
| 单次耗时 | ~13 min → **~4 min**（弧后） | ~13 h（不可比） |
| 优化摊销 | 薄利多销，迭代节奏从"等咖啡"变"等泡面" | 一次性，睡一觉自己跑完 |

同一个专题里两者都会兑现：D/E（P-BASE M-LAG）与 F（Mode B）每次回放直接享受弧后速度；pack 生成慢是**补交 9/23 时钟 patch 捷径（`NOT_FULL_REGEN`）欠下的一次性诚实账**，与引擎速度无关。

## 4. 可并行性分析

两段重活是两种计算结构，答案相反：

1. **状态链折叠（不可朴素并行）**：rule_intents 主循环逐日 `make_rule_plan + _step`，今天卖谁取决于昨天持有什么（topk-dropout 持有连续性）。串行依赖链，"一天一进程"不成立。加速只能靠单核变快（numpy/Rust 重写级）。
2. **哈希/验证（可并行，疑似真正大头）**：慢速参考路径对每个 plan 做全量 canonical JSON 序列化 + SHA（源码 help 自述 "default is slow reference"）；portfolio 审计逐意图/逐日验哈希，彼此独立。教科书级分块并行：N 块各算各的、按原序归并，**字节序不变、确定性可保**（合同链命根子不伤）。24 核理论上可压到 1/10–1/20。
3. Python GIL：多线程无用，并行即 multiprocessing 重写。

## 5. 杠杆、ROI 与触发条件

| 杠杆 | 成本 | 预期收益 | 建议 |
|------|------|---------|------|
| `--cache-plan-hash`（rule_intents 自带） | 一次对比实验：快速路径跑一遍 + plans.json byte-diff | 可能吃掉 rule 段大头（未实测） | **触发后第一刀**，验证等价才可用于合同线 |
| 独占机器 | 排程纪律 | 避免共享膨胀（弧收尾教训：撞负载 392.6s vs 空闲 237.6s，~1.7x） | 立即可行，零风险 |
| 分块并行审计（重写） | 数天工程 + 确定性验证（本身需一次 ~13h 对照跑） | rule/portfolio 段 5–20x | 触发后第二刀 |
| numpy/Rust 重写规划核 | 更大 | 上限更高 | 不在射程内 |

**触发条件（明确写死）**：pack 重生成频率升到**月级及以上**时，开 MQ 侧性能专题（主管 qlib，本仓只提需求）。在此之前**不开刀**——一次性成本 13h vs 重写+验证的工程天数，负 ROI。若重生成变频繁，优先治**上游合同变更纪律**，而不是这段代码的速度。

## 6. 写作时点实验快照（2026-09-25 07:29）

- B/C1/C2 完成；C3 portfolio 运行中（4h46m CPU，无报错，PID 36144）。
- 运行根：`MyQuant/runs/joint_return_4090_20260920_pr95/handoff_bt_20260922/narrow_clock_full_20260924/`；日志 `_clock_full_pipeline_20260924_cf.log`；回执 `CLOCK_PREP.md`。
- 出包后接续（固定序）：验全量 pack（PORTFOLIO_CONSTRAINTS_PASS / 2470 / 合同 c6b85b9b）→ 收窄 614/1891 → D/E P-BASE M-LAG（对账 9/23 研究线 4475 fills）→ F Mode B → G 解除 `NOT_READY_FOR_MODE_B`。

## 7. 过程教训（已修，登记备查）

1. 派工单 §3 的 freeze `--metadata rules\metadata.json` 复刻的是历史第一次失败用法；成功线实际用富字段 `inputs\freeze_metadata.json`。本专题以它为底叠加新注册（合同/SHA/尾日历/carryforward/新 plans 双 hash）合成 `freeze_metadata.json`。
2. freeze 校验 `inputs.plans.uri` 与实参**逐字一致**——换 plans 路径必须同步重登记 uri + 双 hash。
3. scores 输入以**成功线自登记**为准（rule-manifest/snapshot 的 `inputs.scores.uri`），merge 步 manifest 会误导（#196 勘误根因）。

## 8. 维护

- 起草：bt（zcode，4090 机）· 2026-09-25 晨 · 观察记录，不随 B–G 步回填；portfolio 完成后的实测总数记入专题 RECEIPT。
