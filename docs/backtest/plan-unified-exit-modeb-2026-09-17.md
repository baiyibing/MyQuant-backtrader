# Plan：统一卖出规则网格 · 模式 B（分钟触发，2026-09-17）

> **落盘**：2026-09-17。**v1.1**（docs-only；本 PR 不写 Mode B Python）。
> **实施进度**：A–C 已提交（`2482072` / `3550c38` / `c3506bc`）；D 因提案 §十 **Q38 oracle 跌停排除粒度** STOP，待人裁；尚未完成实现合入门。
> **状态**：✅ **已人裁 GO**（2026-09-17；P1=A / P2=A / P3=A；P4/P5 锁）。本裁 commit `0ce1db5`。**可开** `feat/unified-exit-modeb` 交 Codex。
> **风险档**：**NAV 影响研究模块**——独立 `unified_exit_modeb`，与策略 1–6/8/9/10 书及 v6/v8 分钟净值**隔离**；不改引擎 `rescale_position` 语义。
> **业务源**：[stock-backtest-unified-exit-proposal-2026-09-17.md](stock-backtest-unified-exit-proposal-2026-09-17.md)（§一 Mode B 行 / §四 / §9.5 Q29=B / §十二速查）；Mode A 宿主短记 [unified-exit-modea-host-note-2026-09-17.md](unified-exit-modea-host-note-2026-09-17.md) §5（oracle 缺口证 Mode B 优先级；perf #92 已合）。
> **工作流**：走 [Codex 交接工作流](workflow-codex-handoff.md)。人裁后改头部为「✅ 已人裁 GO（commit hash）」再开 `feat/unified-exit-modeb`。
> **交接**（已 GO，可开工）：[handoff-unified-exit-modeb-codex-impl-2026-09-17.md](handoff-unified-exit-modeb-codex-impl-2026-09-17.md)。
> **数据就绪（可先做、不依赖 Mode B 代码）**：[host-runbook-unified-exit-modeb-smoke-2026-09-17.md](host-runbook-unified-exit-modeb-smoke-2026-09-17.md)。
> **基线 tip**：`e018924`（`origin/master`，含 Mode A + perf #92）。

---

## 0. 一句话

在 Mode A 已跑通的「实例 × 策略」矩阵框架上，补 **模式 B**：买入 = 名单日 **none 日线 close**；监控 = **不复权 1 分钟 high/low**；成交 = **触发那根分钟的 close**；同根双触 **先止损**；除权日在 **本网格模块内** 做 E-R6（cost/peak ×k）**且** `shares /= k`（Q29=B）；**不改** `csv_ledger.rescale_position`（1–6/8 仍只动 cost/peak）。窗口 / 现金池 / 佣金 / 名单与 Mode A 同口径；报告目录与 Mode A **永不混排**。

```text
本 PR：docs only（plan + handoff + 可选宿主分钟就绪 runbook）
GO 后：feat/unified-exit-modeb · 切片 A–D 合入门；E = 宿主全/窄网格（非合入门）
```

---

## 1. 问题锚点（禁止重做已落地项）

| 事实 | 锚点 |
|------|------|
| Mode A 库 + CLI 已合（装配 / 退出 / 聚合 / 报告形状） | `backtest/research/unified_exit_modea.py`；`scripts/research/run_unified_exit_modea.py`；handoff Mode A |
| Mode A 宿主全网格 + 四件套已完成；实开 **4167**；oracle +129.6% vs 冠军 +1.5% | [unified-exit-modea-host-note-2026-09-17.md](unified-exit-modea-host-note-2026-09-17.md) §1–§5 |
| Mode A 性能票已合（#92）——Mode B 前置 | tip `e018924` |
| 分钟加载 + `bar_cache`（`minute_none_{start}_{end}.parquet`）已有 | `csv_minute_backtest.load_minute_bars` / `minute_cache_path`；`MINUTE_LAKE_END=20260909` |
| E-R6 现成：`load_exdiv_ratios`；引擎 `rescale_position` **不动 shares**（X-R1） | `exdiv_map.py`；`csv_ledger.rescale_position` |
| 提案锁定 Mode B 价域 / 同根先止损 / Q29=B | 提案 §一、§四、§9.5、§十二 |

---

## 2. 现锁（R\* · 硬边界）

| # | 规则 |
|---|------|
| **R1** | 独立模块 `backtest/research/unified_exit_modeb.py` + CLI `scripts/research/run_unified_exit_modeb.py`。尽量复用 Mode A 的装配 / 实例身份 / 网格枚举 / 报告形状。**禁止**为策略 1–6/8 去改 `csv_ledger.rescale_position` 的 shares 语义（X-R1 保持）。 |
| **R2** | 价格域：**买 = none 日线 close**；**触发 = 1m high/low**；**成交 = 该分钟 close**。禁止 front 日线与 none 分钟混用同一判定链。 |
| **R3** | 同根分钟同时触 TP 与 SL → **先止损**（Mode B only；Mode A close-only 不会双触）。 |
| **R4** | 除权：Mode B 路径内 E-R6 式 **cost/peak ×k 且 shares/=k**（Q29=B）；现金红利仍不入账。缩放逻辑**只写在 Mode B 网格模块**，不回写引擎 ledger。 |
| **R5** | 网格轴 / 锚线 / 稳健性四件套与 Mode A **对等**（P1=A 时默认窄网格）。**Mode B 不要求** r2 N=1 ≡ r1_n1（Q37=A：盘中可先成交）；Mode A 等价性不变。 |
| **R6** | 默认 CI **data-free**（合成 fixture）；全量/窄网格 **宿主-only**（优先 4090）；禁止硬编码盘符 / cwd `stock_data/` 字面量；湖路径只经 resolvers。 |
| **R7** | 不 import qlib；不复活 backtrader / Cerebro / Rolling / Qlib PortAnaRecord。 |

**P4 升格为锁（非人裁）**：Mode A 与 Mode B **永不混排 NAV / 总收益率表**；产出分目录（建议 `backtest_output/unified_exit_modeb/`），报告头标明价域。

---

## 3. 人裁点（P\* · 2026-09-17 已裁）

> 状态：✅ **已裁**。确认人采纳建议默认。

| # | 问题 | **裁决** |
|---|------|----------|
| **P1** | 首船网格范围 | **A**：冠军族 + 锚线（窄网格）。冠军族点名（Mode A 短记）：`r2` × X∈{5,7,10} × Y∈{5,10,∞} × N∈{8,10}，另加四锚线（hold_end / N=1 / oracle / delist_zero）。全量 280 后置。 |
| **P2** | 矩阵跑在哪 | **A**：宿主 F 湖先 smoke（cache/覆盖），窄网格可先宿主；重算迁 4090。 |
| **P3** | E-R6+shares/=k 数据源 | **A**：`ex_date_index` + `exdiv_map.load_exdiv_ratios`。 |
| **P4** | A vs B 排名 | **已锁为 R**：分目录、不混表。 |
| **P5** | Smoke vs 业务网格 | **已锁**：分钟 cache/覆盖可先做；业务 Mode B 网格在 GO+impl 之后。 |

注（Grok #93 nit）：Mode A 短记 **4167 是实开实例数**，不是码数；跌停「日线收盘 vs 该分钟」以提案 Q7 为准——Mode B 卖出日若触跌停则当日不卖、下一交易日再评（分钟路径按交易日重评，不自创新语义）。

### 3.1 实施补裁（2026-09-17 · Q36/Q37 + cache）

| # | 裁决 |
|---|------|
| **Q36** | **A**：到期用当日最后一根 session 分钟 close；无分钟 K 顺延；不回退日线 close |
| **Q37** | **A**：Mode B 取消 N=1 等价；保留盘中先触发；测试用非等价反例 |
| **Cache** | 沿用 `csv_minute_backtest` warmup 起点 cache key（现成 `20251013` 超集）；不强制重建 `20251023` 字面 key |

---

## 4. 非目标

| 不做 | 原因 |
|------|------|
| 改 Mode A 代码/报告/排名 | 隔离；A 已宿主闭环 |
| 改引擎 `rescale_position` 使 shares/=k | R1 / X-R1；仅 Mode B 模块内做 |
| 完整现金红利入账 / §9.6 权息拆分表 | 提案 Q29=B 残留；表未提供 |
| GPU 内核 / CuPy 依赖进本仓第一方路径 | 提案：Mode B 排期再评估；本 plan 不引入 |
| 改 `stock_pool` / 补缺日名单 | 缺 20260525/20260605 = 当天无名单（已定性） |
| 合并 A/B 总收益率排名 | P4 锁 |
| 第二阶段规则（持有期最高 / 均线拐头） | 提案本轮不做 |
| 在本 docs PR 或未 GO 的 feat 分支写 Mode B Python | 工作流第 3 步 |

---

## 5. 切片（GO 后从当时 master 开 `feat/unified-exit-modeb`；A–D 分 commit）

| 切片 | 做什么 | 完成定义（DoD） |
|------|--------|-----------------|
| **A · 分钟装载与覆盖** | 经现成 `load_minute_bars` / `bar_cache` 读 `period=1m/dividend_type=none`；合成 fixture 单测；可选覆盖率 helper（Mode A 实开码 ∩ 分钟可得） | data-free pytest 绿；无硬编码盘符；覆盖 helper 不进 CI 湖门禁 |
| **B · 分钟退出求值器** | 1m high/low 触发 + close 成交；同根 SL-first；T+1 / 跌停顺延 / 停牌冻仓按**分钟适配**（N 仍按市场交易日）；买入侧仍用 none 日线 close + 涨停不买不追 | 合成向量表（含同根双触、跌停分钟、halt）全绿；Q37=A 的 N=1 盘中先触发非等价反例；Mode A 测试不动 |
| **C · E-R6 + shares/=k** | 仅 Mode B 路径：除权日 cost/peak ×k 且 shares/=k；接 `load_exdiv_ratios`（若 P3=A）；现金红利不入账 | 合成除权 fixture（大送转 / 派息级 / 无事件）绿；断言引擎 `rescale_position` **未被改**（或 diff 零） |
| **D · 聚合 / 锚线 / 稳健性 + CLI** | 复用 Mode A 报告形状（总收益率基数 11 亿、四锚线、Q34 四件套）；CLI `run_unified_exit_modeb.py`；产出 `backtest_output/unified_exit_modeb/`；README / AGENTS 一行 | pytest 聚合口径绿；HELP 中文；与 Mode A 目录隔离 |
| **E · 宿主跑数**（**非合入门**） | 按 P1/P2：窄或全网格 + 短记；**不在实现 PR 勾选完成** | 短记落 `docs/backtest/`；数字产物不入库 |

---

## 6. 验证

```bash
# 合入门（实现 PR；data-free）
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/   # 含 Mode B 新测

# 可选：合成数据 timing 短注（不挡合入）
# 宿主：见 host-runbook-unified-exit-modeb-smoke（数据就绪）与日后 Mode B 业务 runbook（GO+impl 后另开）
```

- CI：data-free gates（`verify_no_hardcoded_machine_paths.py` 等）必须过。
- 文本：UTF-8 无 BOM、NUL=0。
- **本 docs PR**：无 Python 实现、不跑网格、不 merge。

---

## 7. 代码落点（GO 后）

| 文件 | 动作 |
|------|------|
| `backtest/research/unified_exit_modeb.py` | **新建**库（装配复用 / 分钟求值 / Mode B 除权缩放 / 聚合） |
| `scripts/research/run_unified_exit_modeb.py` | **新建** CLI（参照 Mode A） |
| `tests/test_unified_exit_modeb_*.py` | **新建**合成 fixture |
| `backtest/research/unified_exit_modea.py` | **尽量只读复用**；非必要不改 |
| `backtest/research/csv_minute_backtest.py` | **复用** `load_minute_bars` / cache；不改成交核书行为 |
| `backtest/research/exdiv_map.py` / `csv_ledger.py` | **只读**；ledger shares 语义不动 |
| `docs/backtest/README.md` / `AGENTS.md` | 入口一行（实现 PR） |

---

## 8. 口径速查（Mode B，摘自提案）

| 项 | 锁定 |
|----|------|
| 窗口 | 20251023–20260909；`MINUTE_LAKE_END=20260909` |
| 名单 | `stock_pool/YYYYMMDD.csv`；缺 2 天 = 当天无名单 |
| 买 / 卖 | 买=名单日 **none** 日线 close；卖=触发分钟 **close**；触发看 1m high/low |
| 钱 | 每笔目标 100 万；整百股；名义现金池 **11 亿**；佣金 0.1%；**无印花税**；卖出回池 |
| 交易所 | T+1；停牌冻仓；涨停不买不追；跌停延期；**同根先止损** |
| 除权 | none + E-R6 + **shares÷k**（仅本网格）；现金红利不入账 |
| 指标 | 总收益率（基数 11 亿）第一排序；副指标同 Mode A |
| bar_cache | `backtest_output/bar_cache/minute_none_{start}_{end}.parquet` |

---

## 9. 修订程序

1. 人裁 P1–P5 → 回写本表「建议」列为「已裁」+ 改头部状态为 ✅ 已人裁 GO（hash）。
2. 刷新 handoff §0（去掉「待人裁」等待句）并标注 plan hash。
3. 开 `feat/unified-exit-modeb`；遇未覆盖语义 → **停下新开提案 Q36+**，不自裁。
4. 实现合入后回写本 plan「✅ 已实施（PR #N）」；切片 E 另短记。

---

## 10. Changelog

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-09-17 | 首版 docs-only：R1–R7、P1–P5（建议默认）、切片 A–E；状态 ⏳ 待人裁 GO |
