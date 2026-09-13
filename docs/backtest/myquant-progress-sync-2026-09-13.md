# MyQuant 中期进展同步（本仓只读对照）

> **落盘**：2026-09-13。
> **对照**：MyQuant `github/master` tip `b06d124`（#20 CI）。下午路线图回写仍在 MyQuant [#21](https://github.com/baiyibing/MyQuant/pull/21)（未合）。
> **本仓动作**：不改成交核、不重开 `--asof`、不 `import qlib`。M5 二轮见 [m5-list-attribution-2026-03-09.md](m5-list-attribution-2026-03-09.md)。

---

## 0. 一句话

MyQuant 中期代码片已齐，扩展窗 pred 已交。本仓 M5 二轮已跑：长窗 **仍几乎不重叠**（129 对齐日 pred∩hand / pred∩hand10 全空）。不据此改 topk。

---

## 1. MyQuant 已合（#7–#16 / #19–#20）

| 项 | 状态 | 对本仓的含义 |
|----|------|----------------|
| M1 刷新管道 `#8` | 已合 | 本仓不刷 `~/.qlib`；F 湖仍是只读行情 |
| M4 run-manifest `#9` | 已合 | 契约在 MyQuant `docs/run-manifest-spec.md`。**本仓暂不接**；导出旁会多一份 JSON，消费侧仍只认 CSV |
| M3-A `DropLimitUpLearn` `#9` | 宿主真跑：IC 0.0183 持平；RankIC 0.0048（基线约 3.4×） | 新 pred 才进下一轮 M5；旧 16 日 pred 只作首轮档案 |
| M2 筹码 parity `#10` | **不可比，合法关门** | 不要为对齐去改 `qlib_cost` / TR |
| M3-B sweep `#11/#12/#16` | 三月窗 `topk5_ndrop2` 最好；**OOS 2026-04~08 该格垫底** | 不据此改本仓 `--topk` 或卖点 |
| M3-C 特征筛 `#11/#12` | `turnover_resist_approx` 符号翻转，四候选不入选 | 不把近似阻力当本仓新名单源 |
| M3-D | 源已入库 `#19`（`exports/m3d_industry/sw_l1_map.csv`）；实现片未开 | 行业中性化住 MyQuant |
| followups `#14` | `host_env` + manifest 启动时取 commit | 本仓无对应债 |
| CI `#20` | windows-latest + py3.12 全量 pytest | 本仓不跟它的 qlib 钉 |

OOS 预锁（MyQuant）：**不改线上 topk 默认**；改参要第三窗。本仓遵守：M5 二轮 **topk=10**，与首轮同一名单宽度。

---

## 2. MyQuant 未合 / 未交产物

| 项 | 状态 | 本仓是否等待 |
|----|------|----------------|
| 路线图下午回写 | [#21](https://github.com/baiyibing/MyQuant/pull/21) 开着 | 不阻塞；数字以本文与中期计划为准 |
| M5 二轮 Qlib 臂 | 本机 2026-09-13 已交：`预测结果_ext.csv`（713,548 行 / 132 日）+ `exports/m5r2_pred_topn10_20260302_20260908/`（131 文件） | 本仓已直读跑完三源；见 [m5-list-attribution-2026-03-09.md](m5-list-attribution-2026-03-09.md) |
| Kimi 万得续跑 | [#17](https://github.com/baiyibing/MyQuant/pull/17) | 不关本仓 |

---

## 3. 本仓现状

| 项 | 状态 |
|----|------|
| R0–R5 / 首轮 M5 工具 | 已合 #21–#27 |
| 首轮 M5 列 C 报告 | 已合 [#28](https://github.com/baiyibing/MyQuant-backtrader/pull/28) |
| `stock_pool/` | 215 个文件，`20251023`–`20260909`；二轮窗 `20260303`–`20260908` 现有 **129** 个手工日。会续写，**不是**冻结快照 |
| F 湖 | 本机有；日线应能盖到 2026-09-08（以 `resolve_period_root` 为准） |

---

## 4. 本仓现在能做 / 不能做

**已做完（2026-09-13）：** #28 已合；冻结快照 + hand10 + `version6`/`version8` 三列。结论见二轮报告。

**仍可选、不挡二轮：** `csv_daily` 接 `myquant.run-manifest/1`——单独开片。

**不要做：**

- 重开 `--asof`、改 6/8 卖点、喂策略 7、用 PortAna / 首轮 16 日 NAV 定胜负。
- 把 M3-B 三月冠军 `topk=5` 写进 M5 名单（任务书锁 topk=10）。
- 为 M2「不可比」去改本仓筹码实现。
- 技术分析出日 CSV（chip / TR → 契约名单）：仍是名单源 B，**未立项**，不和二轮绑在一起。
- L2（1.3）。
