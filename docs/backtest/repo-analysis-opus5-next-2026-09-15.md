# MyQuant-backtrader 全面分析与下一步（对照头脑风暴 · tip `8793fd5`）

- **日期**：2026-09-15
- **状态**：docs-only。本机拟用 `cursor-agent` + `claude-opus-5-thinking-high`，但 Agent 端点鉴权失败（Origin-scoped token / `permission_denied`）；由 backtrader 助手对照头脑风暴栈与真实路径落盘。**不是** CloudAgent。
- **Tip**：`8793fd5`（Merge #56 presets CI baseline）— 覆盖 H1–H16（#34–#50）及后续 #51–#56。
- **Parents**：[brainstorm-overview-2026-09-15.md](brainstorm-overview-2026-09-15.md) · [plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md) · [plan-brainstorm-next-heavy-2026-09-15.md](plan-brainstorm-next-heavy-2026-09-15.md) · [repo-analysis-vs-brainstorm-2026-09-15.md](repo-analysis-vs-brainstorm-2026-09-15.md)（#52，tip 较旧）
- **范围**：架构对照主题 A–F；校验热路径证据；给出 **3–5 个有序改进包**。不改卖点语义、不重开 `--asof`、不跑 F 湖全窗回测。

**G 禁区（继承，不挑战）**：改 6/8 卖点；重开 `--asof`；PortAna 定胜负；缺行 fail-closed→跳过；日线/分钟卖环 big-bang 合并；物理删除 Cerebro；本仓复刻 MyQuant CYQ feeder；本仓复刻 LEBS/真栈；CloudAgent 作为交付路径。

---

## 1. 现状一句话

软卫生 **H1–H16 已收口**；#51–#56 补了文档索引、list-quality 严格校验、**分钟 `simulate()` 热路径实测**、TR 对齐 exit-code、presets 跨仓 CI 钉桩。队列头「run-manifest hard」仍延期。下一刀应优先吃 #54 的证据：真实 version8 编排下卖环约占 75%，且现有 numba trail **进不了**该路径。

---

## 2. 架构地图（真实路径）

### 2.1 向量化研究脸

| 角色 | 路径 | 备注 |
|------|------|------|
| 日线引擎 | `backtest/research/csv_daily_backtest.py` | 1–6/8/9/10；卖点=日线规则 |
| 分钟引擎 | `backtest/research/csv_minute_backtest.py` | 同书；卖点=`scan_held_day`（可选 numba trail，有条件） |
| 策略 7 | `backtest/research/csv_minute_backtest_v7.py` | 独立仓位机；强制 `--pool-dir` |
| 共用 CLI / 书 | `backtest/research/csv_strategy_books.py` | H2 `add_csv_backtest_common_args` |
| 共用买卖骨架 | `backtest/research/csv_simulate_loop.py` | chase / pool buy / mark 共用；**卖环有意分家** |
| 成交核 | `backtest/research/csv_ledger.py` | A 股板档、defer、mark |
| 名单 | `backtest/research/csv_pool.py` + [pool-csv-contract.md](pool-csv-contract.md) | H7/H9/H16 质量工具 |

本仓 **无** `backtest/lebs/`。见 [engine-positioning-ssot.md](engine-positioning-ssot.md)。

### 2.2 模拟骨架（#54 实测对象）

```
simulate()
  ├─ prepare / init_sim_state          ← csv_simulate_loop
  ├─ per day:
  │    ├─ SELL（引擎本地，分家）
  │    │    daily:  day_bar_and_prev_closes + 书规则 + _sell
  │    │    minute: scan_held_day(+numba?) + _sell + 跌停 defer
  │    ├─ run_chase_due_day
  │    ├─ run_pool_buys_day
  │    └─ append_equity_and_eod_marks  ← H5 缓存
  └─ summarize / write_run_artifacts
```

### 2.3 筹码 / TR 边界（H11–H15）

| 桶 | 权威路径 | 状态 |
|----|----------|------|
| 生产 TR | Rust `turnover-resist` → bridge → Store → 策略 10 / `export_ta_pool` | leave |
| 分钟筹码分布 | `oskh_factors.chip` `minute_chip_distribution` | H15 可选 numba；默认 Python |
| 全市场日频赢筹 CYQ | **MyQuant** `build_winner_ratio.py`（numba） | **禁止本仓复刻**（H13） |
| hybrid / curpdf | inventory later | leave |

### 2.4 CI（data-free）

Contract gates（H10/H12）→ pip（含 numba，H6）→ pytest `-m "not production and not benchmark"`。需 F 湖的 chip/TR 门禁 **不进** CI。#56 钉 presets 跨仓快照；#55 TR alignment **两指标都过才 exit 0**。

---

## 3. 主题 A–F 记分板（相对 #52 的增量）

| 主题 | H1–H16 | #51–#56 增量 | 残余 / 下一步 |
|------|--------|--------------|---------------|
| **A 性能** | H5/H8/scan_held_day numba trail | **#54**：真实 `simulate()` 卖环 ~75%；numba 请求因 `reserve_state`/callable 被拒，后端仍是 Python | 见 WP1（编排级缓存 / 有限 compiled scan） |
| **B 入口** | H2 + 书分离 | 无行为变更 | 两套卖引擎继续分家 |
| **C 名单** | H7/H9/H16 | **#53**：`--other-dir` 两侧都严格 `validate_pool_dir` | WP4 golden fixture（可选）；run-manifest hard 仍延期 |
| **D 筹码** | H11–H15 | 无新算法 | hybrid/curpdf leave；勿复刻 CYQ |
| **E CI** | H6/H10/H12 | **#55/#56** exit-code 与 presets 钉桩 | WP3 host 湖门禁 cookbook；湖门禁不进 CI |
| **F 工程脸** | H1/H3/H4 | #51/#52 文档索引 | Cerebro 观察退役 |

---

## 4. 热路径证据校验（重点：#54）

来源：[minute-simulate-profile-results-2026-09-15.md](minute-simulate-profile-results-2026-09-15.md)（version8，30 日 × 16 码 × 240 bar，合成，无湖）。

| 阶段 | 默认请求 | 设 `CSV_SCAN_HELD_DAY_BACKEND=numba` |
|------|----------|--------------------------------------|
| `simulate()` | ~1218 ms | ~1230 ms（无实质加速） |
| sell scan | **~75%** | ~75% |
| pool buy | ~5% | ~5% |
| orchestration remainder | ~19% | ~19% |
| nested prev-close prep | ~5% | ~5% |

**关键发现**：`simulate()` 为每手传入非空 `reserve_state`，version8 还有 `take_profit` callable → 可选 numba trail **被 dispatcher 拒绝**；独立 `bench_scan_held_day.py` 的 numba 加速 **不能**代表真实编排。

相对 H14/H15：分钟筹码直方图 offload 与分钟卖环 offload **正交**——不要把 D2 当卖环加速许可证。

相对 H5/H8：日线 mark / searchsorted 已落地；下一刀日线收益需要更强 profile，勿再开「又一次 `.loc` 扫荡」。

---

## 5. 跨仓边界（不变）

```
MyQuant                 MyQuant-backtrader              OSkhQuant1.3
train / export CSV      向量化 CSV 研究脸               LEBS / MockQMT
numba 全市场 CYQ        Rust TR → Store；分钟 chip      trade_decision
run-manifest 写端       消费湖只读；Cerebro 化石         Paper 同源
```

硬篱笆：不复刻 CYQ feeder；不克隆 LEBS；向量化 NAV ≠ Paper/PortAna；6/8 卖点本仓锁死；run-manifest **消费**默认延期。

---

## 6. 风险登记（相对 #52 刷新）

| ID | 风险 | 缓解 |
|----|------|------|
| R1 | big-bang 合并日/分钟卖环带动 6/8 漂移 | 继续分家；只做 golden+parity 微优化 |
| R2 | 误以为 `CSV_SCAN_HELD_DAY_BACKEND=numba` 已加速真实 simulate | #54 写清；WP1 前先读 profile 文 |
| R3 | 复刻 MyQuant CYQ | H13 / CONTRIBUTING |
| R4 | 湖门禁进 GitHub Actions | H10 workflow 注释；WP3 cookbook 强调 host-only |
| R5 | 无产品点头硬接 run-manifest | 保持延期；H16 覆盖本地名单卫生 |
| R6 | Agent CLI Origin token 误当交付路径 | 本机 Codex/Grok/Actions；本文即鉴权失败后的替补 |

---

## 7. 下一步改进方案（有序 3–5 包）

**默认立场**：停止扩张 Hx 软卫生面；**run-manifest hard 仍延期**（需产品点头）。优先吃 #54 证据，或做 docs/fixture 低风险包。

### WP1 — 主题 A：分钟 `simulate` 编排微优化（**推荐下一刀，若痛点是分钟窗**）

| | |
|--|--|
| **意图** | 在不碰卖点语义的前提下，针对 #54 的两处候选落地其一或其二：(1) 按 code/day 缓存 prev-close / close-history，跨 lots 与 sell/chase/pool 复用（现 ~5%）；(2) **仅**对明确支持的内置书合同（含 reserve/take-profit 行为）做可选 compiled scan 原型，默认仍 Python，parity 锁死。 |
| **为何现在** | 卖环 ~75%；现有 numba trail 对真实 version8 编排无效。 |
| **不做** | 日线↔分钟卖环合并；改 6/8 理由码；改默认后端；F 湖 NAV 验收。 |
| **验收** | 新/扩 plan + profile 前后对比；golden 分钟测试绿；Python 默认；Grok 核无 🔴。 |
| **体量** | 中（软代码 + 文档） |

### WP2 — 主题 E：host-only 湖门禁 cookbook（**无痛点时的默认安全刀**）

| | |
|--|--|
| **意图** | 一份清单：哪些 `scripts/gates/verify_*` / TR alignment 仅宿主、怎么跑、为何不进 CI；链 AGENTS / README。 |
| **不做** | 把湖门禁写进 `python-tests.yml`。 |
| **验收** | 新人 ≤30s 找到列表；CI 精神不变。 |
| **体量** | 小（docs） |

### WP3 — 主题 C：list-quality golden fixture（软，仍非 run-manifest）

| | |
|--|--|
| **意图** | 检入微型合成池目录 + pytest，锁住 H16 报表（churn / invalid stems / top-N / #53 other-dir 严格校验）。 |
| **不做** | 消费 `myquant.run-manifest/1`；改 simulate/sell。 |
| **验收** | data-free CI 绿；contract 一行指针。 |
| **体量** | 小–中 |

### WP4 — 主题 D：inventory「later」再钉一次（docs）

| | |
|--|--|
| **意图** | H15 后显式写清 hybrid/`calc_curpdf` **leave until 产品吞吐需要**；可选「何时重开」判据。 |
| **不做** | 新 numba/Rust 内核；迁 MyQuant feeder。 |
| **验收** | docs PR。 |
| **体量** | 极小 |

### WP5 — 产品门：run-manifest hard（**仅点头后**）

| | |
|--|--|
| **意图** | 本仓消费 MyQuant `myquant.run-manifest/1`（训练/导出溯源）。 |
| **为何仍排后** | H16 已覆盖本地名单卫生；硬接跨仓契约，无点头易脆。 |
| **不做** | 偷偷当默认必经路径；用 PortAna/NAV 当合入门。 |
| **验收** | 另开任务书；schema 对齐 `docs/run-manifest-spec.md`（MyQuant）；fixture + 可选宿主烟测。 |
| **体量** | 重（跨仓） |

---

## 8. 建议决策

1. **若分钟研究窗觉得慢** → 先开 **WP1**（先缓存 prev-close，再评估 compiled scan；每步单独测）。  
2. **若无明确性能痛点** → **WP2 或 WP3**，别再开 offload 大片。  
3. **run-manifest** → 等你点头再开 WP5；默认继续 defer。  
4. **Opus CLI**：若要坚持 agent 模型写代码，需非 Origin-scoped 的 Cursor Agent 凭证；此前失败模式已记入 R6。

---

## Appendix — #51–#56 速查

| PR | 作用 |
|----|------|
| [#51](https://github.com/baiyibing/MyQuant-backtrader/pull/51) | brainstorm overview A–F |
| [#52](https://github.com/baiyibing/MyQuant-backtrader/pull/52) | 旧 tip 自分析（本文刷新之） |
| [#53](https://github.com/baiyibing/MyQuant-backtrader/pull/53) | list-quality `--other-dir` 双侧严格校验 |
| [#54](https://github.com/baiyibing/MyQuant-backtrader/pull/54) | 分钟 `simulate` 热路径 profile（本文 WP1 依据） |
| [#55](https://github.com/baiyibing/MyQuant-backtrader/pull/55) | TR alignment 双指标才 exit 0 |
| [#56](https://github.com/baiyibing/MyQuant-backtrader/pull/56) | presets 跨仓 baseline 钉进 CI |

H1–H16 → 主题索引见 [repo-analysis-vs-brainstorm-2026-09-15.md](repo-analysis-vs-brainstorm-2026-09-15.md) Appendix；PR #34–#50 见 [brainstorm-overview-2026-09-15.md](brainstorm-overview-2026-09-15.md)。
