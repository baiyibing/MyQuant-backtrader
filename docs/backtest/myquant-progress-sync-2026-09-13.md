# MyQuant 中期进展同步（本仓只读对照）

> **落盘**：2026-09-13（晚间对齐）。
> **对照**：MyQuant `github/master` §0.2 回写 [#27](https://github.com/baiyibing/MyQuant/pull/27) → `c832fb2`（CI 绿）。
> **本仓动作**：不改成交核、不重开 `--asof`、不 `import qlib`、不改 topk。M5 二轮见 [m5-list-attribution-2026-03-09.md](m5-list-attribution-2026-03-09.md)。9/10 宿主见 [s9-s10-host-smoke-2026-09-13.md](s9-s10-host-smoke-2026-09-13.md)。

---

## 0. 一句话

MyQuant 中期最后一口已合。长窗重叠 84–92% →「不改名单」合法终点；两窗同向不过 → 不采纳、也不判有害；中性化默认关、保留实验开关、**不改 topk**。本仓 M5 二轮仍是 pred∩hand 长窗全空；9/10 是另一套人，不当第四列。

---

## 1. MyQuant 已合（中期收口）

| 项 | 状态 | 对本仓的含义 |
|----|------|----------------|
| M1 刷新管道 `#8` | 已合 | 本仓不刷 `~/.qlib`；F 湖仍是只读行情 |
| M4 run-manifest `#9` | 已合 | 契约在 MyQuant `docs/run-manifest-spec.md`。**本仓暂不接**；消费侧仍只认 CSV |
| M3-A `DropLimitUpLearn` `#9` | 宿主真跑：IC 0.0183 持平；RankIC 0.0048 | 旧 16 日 pred 只作首轮档案 |
| M2 筹码 parity `#10` | **不可比，合法关门** | 不要为对齐去改 `qlib_cost` / TR |
| M3-B sweep `#11/#12/#16` | 三月窗冠军出窗垫底 | **不改**本仓 `--topk` 或卖点 |
| M3-C 特征筛 `#11/#12` | `turnover_resist_approx` 符号翻转 | 不把近似阻力当本仓新名单源 |
| M3-D 中性化 | **默认关**；实验开关留 MyQuant；§0.2 `#27` | 不搬到本仓；不改 topk |
| followups `#14` | `host_env` + manifest 启动时取 commit | 本仓无对应债 |
| CI `#20` | windows-latest + py3.12 全量 pytest | 本仓不跟它的 qlib 钉 |
| 路线图 §0.2 | **已合 `#27` / `c832fb2`** | 中期计划收口。脚注：Top1 反升、换手与中性化无关、`__main__` guard |

OOS / 中性化预锁（MyQuant `#27`）：长窗重叠 84–92% 是「不改名单」合法终点；三月大换名单、命中原地踏步；两窗同向不过则不采纳、也不判有害。本仓遵守：M5 **topk=10**；9/10 不做 TopK 对齐赛。

---

## 2. 不再当「未合中期债」

| 项 | 状态 | 本仓是否等待 |
|----|------|----------------|
| 路线图下午回写 | 已合 `#27` | 不等 |
| M5 二轮 Qlib 臂 | 本机已交：`预测结果_ext.csv`（713,548 行 / 132 日）+ 131 个 CSV | 本仓已直读跑完三源 |
| Kimi 万得续跑 | 行业源已入库；中性化默认关 | 不关本仓 |

---

## 3. 本仓现状

| 项 | 状态 |
|----|------|
| R0–R5 / 首轮 M5 工具 | 已合 #21–#27 |
| 首轮 M5 列 C 报告 | 已合 [#28](https://github.com/baiyibing/MyQuant-backtrader/pull/28) |
| M5 二轮三源 | 已合 [#30](https://github.com/baiyibing/MyQuant-backtrader/pull/30)；129 对齐日 pred∩hand / pred∩hand10 全空 |
| 策略 9 / 10 夹具 | 已合 [#32](https://github.com/baiyibing/MyQuant-backtrader/pull/32) |
| 策略 9 / 10 宿主烟测 | 2026-09-13 本机；见 [s9-s10-host-smoke-2026-09-13.md](s9-s10-host-smoke-2026-09-13.md) |
| `stock_pool/` | 会续写，**不是**冻结快照；二轮用 `exports/m5r2_hand_snap_*` |
| F 湖 | 只读；日线应能盖到 2026-09-08 |

---

## 4. 本仓现在能做 / 不能做

**已做完：** M5 二轮三源；9 长窗能出票且几乎是第三套人；10 在带副本 + 宇宙⊆截面时能出票。

**仍可选、不挡中期：** 活 Store 补 TR 布林带 + 逐日 upsert——生产管道，会写 `F:\`，缺行仍 fail-closed，覆盖只到 `20260604`。`csv_daily` 接 `myquant.run-manifest/1`——单独开片。

**不要做：**

- 重开 `--asof`、改 6/8 卖点、喂策略 7、用 PortAna / 单窗 NAV 定胜负。
- 按 M3-B / M3-D 改 topk 或把中性化搬进本仓。
- 把 9/10 加进 M5 当第四列净值赛。
- 把默认湖宇宙的 fail-closed 改成缺行跳过。
- L2（1.3）。
