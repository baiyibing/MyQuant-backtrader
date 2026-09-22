# 交接：qlib 联合收益 → BT（2026-09-22）

> **状态**：`NOT_READY_FOR_MODE_B`。约束线已 PASS；收窄 P-BASE 回放语义绿但 **0 成交**（BUG_ALIGNMENT）；MQ #97 意图时钟已合；4090 **只重出 pack、先不回放**。pack 齐了再由 **bt 派 4090 重跑 P-BASE（M-LAG）**。Mode B 真湖在 P-BASE 有真实成交之前 **停**。  
> **主管**：成交/NAV 与 Mode B = **bt**。qlib 交 MQ 冻结意图。4090bot = 物理机 runner，由正在干活的 bot 派。  
> **归类**：qlib 分家族 · 冻结意图回放；**不是** `--strategy topk_dropout`，**不是** `stock_pool` Mode A/B 网格。总图：[research-backtest-entry.md](research-backtest-entry.md) §5.1 / §5.6。

生产 fill / scan / fee 不动。禁止造 bar、禁止 PortAna 倒推、禁止把 0 成交 NAV 当有效收益。

---

## 1. 来龙去脉（一条线，不是几条平行大活）

顺序固定：

**组合约束真数（已 PASS）→ 成交/NAV 实测（当前卡时钟重出 pack）→ Mode B 真湖（bt 主管，未开）**

| 日 | 谁 | 做了什么 |
|----|----|----------|
| 9/20 | qlib | 瘦合同 **MQ #95** 合入：缺 anti 时只跑 `control_only` → **P-BASE** |
| 9/21 | qlib + 4090 | 主线：催 4090 真数。plans ~657MB → freeze 因 metadata 缺字段挂 → 补字段后 freeze 成功（snapshot ~1GB）→ portfolio 开跑。发现 BT `code_shas` 仍是旧 tip，停掉旧 portfolio（没落盘），对齐 MQ=`b042210…` / BT=`a98b6280…` 后重 freeze，再开 P-BASE portfolio |
| 9/22 早 | 4090 | 组合约束审计 **PASS**（墙钟约 7.2h）。产物：`MyQuant/runs/joint_return_4090_20260920_pr95/portfolio/joint-return-control-only-50-5/`。换手 / 回撤 / 净超额 **NOT_RUN**（这步本来就不出成交） |
| 9/22 | bt | **BT #162** 合入：冻结 `--bars` 适配。全集回放因分钟覆盖 **INPUT_BLOCKED**（缺 3,575,860 symbol-minute：9 无 bin + 150 窗内后上市） |
| 9/22 | 人裁 | 按存活期/宇宙收窄：留 **614** 满窗，丢 9+150 |
| 9/22 | 4090 | 收窄导 bars + P-BASE（M-LAG）回放：`BT_RESEARCH_REPLAY_PASS`，但 **1891 意图 / 0 成交**（EXPIRED 1881、NOT_AVAILABLE 1891）。换手/回撤/净超额全是 **0**，不能当有效收益 |
| 9/22 | bt 只读核 | **BUG_ALIGNMENT**，不是预期空仓。意图 `available=effective=当日 15:03`、`expires=当日 16:00`；M-LAG 要会话内且 **严格晚于** `available_at` 的 open；当日最后 open≈15:00 → 空窗口。收窄和 bars 没问题 |
| 9/22 | qlib | **MQ #97** → `1c1fe43`（Grok GO）：`next_session_clocks` 可把 available/effective 打到次日 09:30。**合同 hash 变了**（新 `c6b85b9b…`），旧冻结包不可复用 |
| 现在 | 4090 | **只重出** `narrow_clock_20260922` pack（排在 s12 分钟五本后面），**先不回放**。目录里目前只有 `metadata.json` / `sessions.json` / `execution-calendar.json`，**还没有** intents/constraints/manifest |

chase / 弱信号 / anti / 线上 10/3 / pred / Mode B 真湖：全程未开、未造数。

---

## 2. 合同分界（为什么约束 PASS 却没有收益数字）

| 层 | 谁 | 产出 | 换手/回撤/净超额 |
|----|----|------|------------------|
| 组合约束 | MQ `portfolio` | intents / constraints / manifest | **NOT_RUN**（合同分界，不是失败） |
| 成交 → 持仓/现金 → 日 NAV | BT `run_joint_return_replay.py` | orders / fills / daily_nav / summary | 有真实成交才有意义 |
| Mode B 真湖 | BT 主管；qlib 只交意图；4090 runner | 同 CLI，`--bars` 真湖 JSON | P-BASE 有成交之后才开 |

顶层 freeze 仍可能标 `INPUT_BLOCKED`（上游 hash/PIT 待核）。**不挡**本次约束 PASS，也**不是**许可去造 anti/universe/labels。

研究默认 **50/5**，不改线上 10/3。`scores_mode=control_only`，只开 P-BASE。

---

## 3. 路径（宿主事实，不入库）

运行根：`D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95`

| 工件 | 路径 |
|------|------|
| 约束 PASS 包（2470 intents） | `portfolio/joint-return-control-only-50-5/` |
| 4090→BT 交接（旧钟） | `handoff_bt_20260922/HANDOFF_BT.md` |
| 收窄规则 | `handoff_bt_20260922/NARROW.md`（614 / 丢 9+150） |
| 旧钟收窄 pack | `handoff_bt_20260922/narrow_20260922/portfolio_joint-return-control-only-50-5-narrow/` |
| 旧钟 bars | `D:\exports\joint_return_pbase_narrow_20260922\frozen_explicit_bars.json` |
| 旧钟回放（0 成交） | 本仓 `backtest_output/joint-return-v1/joint-return-control-only-50-5-narrow/` |
| **新钟 pack（进行中）** | `handoff_bt_20260922/narrow_clock_20260922/`（MQ `1c1fe43`，合同 `c6b85b9b…`） |
| 湖 | `QLIB_1MIN_ROOT=C:\Users\wangc\.qlib\qlib_data\my_data_1min` |

MQ 合同：[joint-return-v1/contract.md](../../../MyQuant/docs/reviews/joint-return-v1/contract.md) · 时钟刀验收：[acceptance.md § BUG_ALIGNMENT](../../../MyQuant/docs/reviews/joint-return-v1/acceptance.md) · 重导派工：[intent-clock-4090-reexport.md](../../../MyQuant/docs/reviews/joint-return-v1/intent-clock-4090-reexport.md)  
BT CLI：[joint-return-frozen-explicit-price.md](joint-return-frozen-explicit-price.md)

旧合同 hash `9ee8cc3c…` **只解释 0 成交那刀**；新跑必须用 #97 后的 hash。

---

## 4. RACI

| 角色 | 做什么 | 不做什么 |
|------|--------|----------|
| **qlib** | MQ 冻结意图、时钟合同、#95/#97、把 pack 路径交给 bt | 不改 BT fill 核；不派 Mode B |
| **bt** | `--bars` 适配、覆盖核验、P-BASE/M-LAG 回放、**Mode B 真湖主管** | 不改 MQ 选票数量；不造 bar |
| **4090bot** | 物理机 runner（导 bars / freeze / portfolio / replay） | 不现场选参、不改合同 |

Mode B 真湖：M-REF / M-LAG 分钟成交敏感，用真湖 `--bars`，不造 bar。等当前收窄 P-BASE **有非零成交** 再由 bt 开单刀，不并行。

---

## 5. 成交/NAV 实测（旧钟收窄刀 — 无效收益）

- 状态：`BT_RESEARCH_REPLAY_PASS` + `return_status=待实测` + `real_execution_status=INPUT_BLOCKED`
- 意图 1891；成交 0；`nav_start=nav_end=1e8`；turnover / max_drawdown / net_excess = **0.0**
- 订单原因：EXPIRED 1881、NOT_AVAILABLE 1891；WAITING 10
- **VERDICT：BUG_ALIGNMENT**（意图时钟），不是资金/容量/收窄失败
- 覆盖 missing=0（相对收窄宇宙）

此段 **不是** Mode B 的绿灯。新钟 pack 重跑后另写一节，不要覆盖上表。

---

## 6. bt 下一步（pack 齐了才做）

1. 确认 `narrow_clock_20260922/` 出现 intents / constraints / manifest，且 `metadata.json` 的 `code_shas.MQ=1c1fe43…`、`contract_hash=c6b85b9b…`。
2. 按新执行窗核验 bars 覆盖（末日若落到次日 session，可能要补尾日；不足只从真湖导出，不造 bar）。旧 bars 宇宙不变时可复用，**先核再复用**。
3. 派 4090：`run_joint_return_replay.py --arm P-BASE --fill-mode M-LAG --bars <verified json>`，`--out` 新目录，禁止覆盖 `…-narrow`。
4. 验收：非零 `orders_with_fills`；换手/回撤/净超额不是全 0。仍全空 → 停，回 qlib 查时钟，不交 Mode B。
5. 仅当第 4 步有效后，bt 再开 **Mode B 真湖**单刀。M-REF 对冻结包仍可能 INPUT_BLOCKED（`reference_price=1.0` 占位）——以当时合同为准，不要拿占位当市价。

现在不要抢开 Mode B。s12 分钟五本若还在 4090 队列，pack 重出排在它后面。
